"""Fila + workers (QThread reais) contra o yt-dlp com extrator local."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core.ffmpeg import find_ffmpeg
from app.core.models import JobStatus
from app.workers.manager import DownloadManager
from tests.test_pipeline import job_for

pytestmark = pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg não instalado")


@pytest.fixture()
def app(qapp):
    return qapp


def wait(app, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    assert cond(), "timeout"


def test_sequential_queue_runs_one_at_a_time(app, patched_ydl, tmp_path):
    m = DownloadManager(find_ffmpeg())
    seen_running = []
    m.job_changed.connect(lambda j: seen_running.append(sum(x.status == JobStatus.RUNNING for x in m.jobs.values())))
    finished = []
    m.job_finished.connect(finished.append)
    jobs = [job_for(patched_ydl, tmp_path, format="mp3", mp3_bitrate=128) for _ in range(3)]
    for j in jobs:
        m.add(j)
    assert [j.status for j in jobs].count(JobStatus.QUEUED) == 2
    wait(app, lambda: not m.has_active())
    assert all(j.status == JobStatus.DONE and j.percent == 100 for j in jobs)
    assert max(seen_running) == 1 and len(finished) == 3
    assert len(list(tmp_path.glob("*.mp3"))) == 3


def test_cancel_running_and_queued(app, patched_ydl, tmp_path):
    m = DownloadManager(find_ffmpeg())
    a = job_for(patched_ydl, tmp_path, format="mp4")
    b = job_for(patched_ydl, tmp_path, format="mp4")
    m.add(a)
    m.add(b)
    m.cancel(b.id)                       # na fila: cancela na hora
    assert b.status == JobStatus.CANCELLED
    m.cancel(a.id)                       # em execução
    wait(app, lambda: not m.has_active())
    assert a.status in (JobStatus.CANCELLED, JobStatus.DONE)   # arquivo minúsculo pode terminar antes do cancelamento
    if a.status == JobStatus.CANCELLED:
        assert list(tmp_path.iterdir()) == []


def test_failure_is_reported_not_raised(app, tmp_path):
    from app.core.models import DownloadJob, DownloadOptions, VideoInfo
    m = DownloadManager(find_ffmpeg())
    job = DownloadJob(VideoInfo("x", "http://127.0.0.1:1/nada", "t", "c", 10, None), DownloadOptions(dest_dir=str(tmp_path)))
    m.add(job)
    wait(app, lambda: not m.has_active())
    assert job.status == JobStatus.FAILED and job.error


def test_missing_ffmpeg_message(app, tmp_path):
    from app.core.models import DownloadJob, DownloadOptions, VideoInfo
    m = DownloadManager(None)
    job = DownloadJob(VideoInfo("x", "http://x/y", "t", "c", 10, None), DownloadOptions(dest_dir=str(tmp_path)))
    m.add(job)
    wait(app, lambda: not m.has_active())
    assert job.status == JobStatus.FAILED and "winget install" in job.error
