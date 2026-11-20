"""Executa um download em segundo plano."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal

from app.core.downloader import run_download
from app.core.errors import DownloadCancelled, friendly_message
from app.core.ffmpeg import FFmpegInfo
from app.core.models import DownloadJob, Progress


class DownloadWorker(QThread):
    progress = Signal(int, object)    # job_id, Progress
    succeeded = Signal(int, str)      # job_id, caminho final
    failed = Signal(int, str)         # job_id, mensagem amigável
    cancelled = Signal(int)

    def __init__(self, job: DownloadJob, ffmpeg: FFmpegInfo | None, parent=None) -> None:
        super().__init__(parent)
        self.job, self._ffmpeg = job, ffmpeg
        self._cancel = threading.Event()
        self._last_emit = 0.0
        self._last_stage = ""

    def cancel(self) -> None:
        self._cancel.set()

    def _emit(self, p: Progress) -> None:
        # limita a ~10 atualizações/s para não inundar a UI, mas nunca perde troca de etapa
        now = time.monotonic()
        if p.stage != self._last_stage or now - self._last_emit >= 0.1 or (p.percent or 0) >= 100:
            self._last_emit, self._last_stage = now, p.stage
            self.progress.emit(self.job.id, p)

    def run(self) -> None:
        try:
            path = run_download(self.job, self._ffmpeg, self._emit, self._cancel)
            self.succeeded.emit(self.job.id, path)
        except DownloadCancelled:
            self.cancelled.emit(self.job.id)
        except Exception as exc:  # noqa: BLE001
            if self._cancel.is_set():
                self.cancelled.emit(self.job.id)
            else:
                self.failed.emit(self.job.id, friendly_message(exc))
