"""Integração: yt-dlp real + FFmpeg real, com um extrator falso servindo arquivos locais."""
import threading
from pathlib import Path

import pytest

from app.core import converter
from app.core.downloader import run_download
from app.core.errors import DownloadCancelled
from app.core.ffmpeg import find_ffmpeg
from app.core.models import DownloadJob, DownloadOptions, VideoInfo
from app.utils.validators import TimeRange
from tests.conftest import install_first, make_fake_ie, probe

pytestmark = pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg não instalado")


def job_for(base, tmp_path, **opts):
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True}) as y:
        install_first(y, make_fake_ie(base))
        data = y.extract_info(f"{base}/fake/abc", download=False)
    info = VideoInfo("abc", f"{base}/fake/abc", data["title"], "Canal Teste", 60, None, formats=data["formats"])
    return DownloadJob(info, DownloadOptions(dest_dir=str(tmp_path), **opts))


def streams(path):
    d = probe(path)
    return {s["codec_type"]: s for s in d["streams"]}, float(d["format"]["duration"])


def run(job, cancel=None, events=None):
    events = events if events is not None else []
    return run_download(job, find_ffmpeg(), events.append, cancel or threading.Event())


def test_mp4_full_merges_separate_video_and_audio(patched_ydl, tmp_path):
    ev = []
    out = run(job_for(patched_ydl, tmp_path, format="mp4", quality=None), events=ev)
    s, dur = streams(out)
    assert Path(out).suffix == ".mp4" and Path(out).parent == tmp_path
    assert s["video"]["height"] == 360 and s["video"]["codec_name"] == "h264" and s["audio"]["codec_name"] == "aac"
    assert 59 <= dur <= 61
    assert "[360p]" in Path(out).name and "/" not in Path(out).name and "?" not in Path(out).name
    assert ev[-1].percent == 100.0 and ev[-1].stage == "Concluído"
    pcts = [e.percent for e in ev if e.percent is not None]
    assert pcts == sorted(pcts)                                  # progresso nunca regride
    assert not list(tmp_path.glob(".nokk-tmp-*"))                # temporários limpos


def test_quality_cap_picks_lower_stream(patched_ydl, tmp_path):
    out = run(job_for(patched_ydl, tmp_path, format="mp4", quality=240))
    assert streams(out)[0]["video"]["height"] == 240


def test_clip_downloads_only_selected_range(patched_ydl, tmp_path):
    out = run(job_for(patched_ydl, tmp_path, format="mp4", quality=None, time_range=TimeRange(10, 25)))
    s, dur = streams(out)
    assert 14.5 <= dur <= 15.6, dur                              # 15 s pedidos
    assert s["video"]["height"] == 360 and "audio" in s          # qualidade preservada, com áudio
    assert "00-00-10 a 00-00-25" in Path(out).name


def test_mp3_with_bitrate_and_clip(patched_ydl, tmp_path):
    out = run(job_for(patched_ydl, tmp_path, format="mp3", mp3_bitrate=192, time_range=TimeRange(5, 20)))
    s, dur = streams(out)
    assert Path(out).suffix == ".mp3" and s["audio"]["codec_name"] == "mp3"
    assert abs(int(s["audio"]["bit_rate"]) - 192_000) < 8_000
    assert 14.5 <= dur <= 15.6, dur


def test_mp3_full(patched_ydl, tmp_path):
    out = run(job_for(patched_ydl, tmp_path, format="mp3", mp3_bitrate=128))
    s, dur = streams(out)
    assert abs(int(s["audio"]["bit_rate"]) - 128_000) < 8_000 and 59 <= dur <= 61


def test_never_overwrites_existing_file(patched_ydl, tmp_path):
    a = run(job_for(patched_ydl, tmp_path, format="mp3"))
    b = run(job_for(patched_ydl, tmp_path, format="mp3"))
    assert a != b and Path(a).exists() and Path(b).exists() and "(1)" in b


def test_cancel_leaves_no_files(patched_ydl, tmp_path):
    cancel = threading.Event()
    job = job_for(patched_ydl, tmp_path, format="mp4")
    with pytest.raises(DownloadCancelled):
        run_download(job, find_ffmpeg(), lambda p: cancel.set(), cancel)
    assert list(tmp_path.iterdir()) == []


def test_converter_trim_and_mp3_direct(patched_ydl, tmp_path):
    ff = find_ffmpeg().ffmpeg
    full = run(job_for(patched_ydl, tmp_path, format="mp4"))
    cut = tmp_path / "cut.mp4"
    seen = []
    converter.trim(ff, full, str(cut), 20, 30, on_progress=seen.append)
    assert 9.5 <= streams(str(cut))[1] <= 10.6 and seen and seen[-1] > 90
    mp3 = tmp_path / "x.mp3"
    converter.to_mp3(ff, full, str(mp3), 256, 0, 12)
    assert 11.5 <= streams(str(mp3))[1] <= 12.6


def test_converter_cancel(patched_ydl, tmp_path):
    ff = find_ffmpeg().ffmpeg
    full = run(job_for(patched_ydl, tmp_path, format="mp4"))
    ev = threading.Event()
    ev.set()
    with pytest.raises(DownloadCancelled):
        converter.trim(ff, full, str(tmp_path / "c.mp4"), 0, 30, cancel=ev)
