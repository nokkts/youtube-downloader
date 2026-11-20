from app.core.errors import NokkError, friendly_message
from app.core.youtube import available_tiers, make_format_selector, pick_audio, pick_video
from app.utils.settings import SettingsStore


def F(fid, h, w, vc="avc1", ac="none", **kw):
    return {"format_id": fid, "height": h, "width": w, "vcodec": vc, "acodec": ac, "protocol": "https", **kw}


YT = [
    F("a-opus", 0, 0, "none", "opus", abr=130), F("a-m4a", 0, 0, "none", "mp4a.40.2", abr=129),
    F("v2160-vp9", 2160, 3840, "vp09"), F("v2160-av1", 2160, 3840, "av01"),
    F("v1440-vp9", 1440, 2560, "vp09"),
    F("v1080-avc", 1080, 1920, "avc1"), F("v1080-vp9", 1080, 1920, "vp09"),
    F("v720-avc", 720, 1280, "avc1"), F("v360-avc", 360, 640, "avc1"),
]


def test_tiers_only_available():
    assert available_tiers(YT) == [2160, 1440, 1080, 720, 360]   # 480 não existe -> não aparece
    assert available_tiers([f for f in YT if f["height"] <= 720]) == [720, 360]


def test_vertical_short_counts_as_1080p():
    short = [F("v", 1920, 1080), F("a", 0, 0, "none", "mp4a")]
    assert available_tiers(short) == [1080]
    assert pick_video(short, 1080)["format_id"] == "v"


def test_pick_prefers_h264_at_same_res_and_aac_audio():
    assert pick_video(YT, 1080)["format_id"] == "v1080-avc"
    assert pick_video(YT, None)["format_id"] == "v2160-vp9"      # 4K: só VP9/AV1 existem
    assert pick_video(YT, 480)["format_id"] == "v360-avc"        # nunca passa do limite
    assert pick_audio(YT, True)["format_id"] == "a-m4a"
    assert pick_audio(YT, False)["format_id"] == "a-opus"        # MP3: melhor bitrate de origem


def test_selector_merges_separate_streams():
    out = list(make_format_selector("mp4", 720)({"formats": YT}))
    assert out[0]["format_id"] == "v720-avc+a-m4a" and len(out[0]["requested_formats"]) == 2
    mp3 = list(make_format_selector("mp3", None)({"formats": YT}))
    assert mp3[0]["format_id"] == "a-opus"


def test_selector_progressive_fallback():
    prog = [F("18", 360, 640, "avc1", "mp4a")]
    assert list(make_format_selector("mp4", None)({"formats": prog}))[0]["format_id"] == "18"


def test_friendly_errors():
    assert "privado" in friendly_message(Exception("ERROR: [youtube] x: Private video. Sign in"))
    assert "indisponível" in friendly_message(Exception("Video unavailable"))
    assert "conexão" in friendly_message(Exception("<urlopen error [Errno -2] Name or service not known>"))
    assert "FFmpeg" in friendly_message(Exception("ffmpeg exited with code 1"))
    assert friendly_message(NokkError("oi")) == "oi"


def test_settings_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = SettingsStore(p)
    s.data.download_dir = str(tmp_path)
    s.data.format = "mp3"
    s.save()
    s2 = SettingsStore(p)
    assert s2.data.download_dir == str(tmp_path) and s2.data.format == "mp3"
    p.write_text("{corrompido")
    assert SettingsStore(p).data.format == "mp4"   # arquivo corrompido não derruba o app
