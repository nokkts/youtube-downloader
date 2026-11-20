"""Fila de downloads. Executa 1 por vez (max_concurrent=1), mas a arquitetura já suporta N."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.core.ffmpeg import FFmpegInfo
from app.core.models import DownloadJob, JobStatus, Progress
from app.workers.download_worker import DownloadWorker


class DownloadManager(QObject):
    job_added = Signal(object)       # DownloadJob
    job_changed = Signal(object)     # DownloadJob (já atualizado)
    job_removed = Signal(int)
    job_finished = Signal(object)    # DownloadJob concluído com sucesso

    def __init__(self, ffmpeg: FFmpegInfo | None, max_concurrent: int = 1, parent=None) -> None:
        super().__init__(parent)
        self.ffmpeg = ffmpeg
        self.max_concurrent = max_concurrent
        self.jobs: dict[int, DownloadJob] = {}
        self._workers: dict[int, DownloadWorker] = {}

    # ------------------------------------------------------------------ API
    def add(self, job: DownloadJob) -> None:
        self.jobs[job.id] = job
        self.job_added.emit(job)
        self._pump()

    def cancel(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        if job.status == JobStatus.QUEUED:
            self._set(job, JobStatus.CANCELLED, stage="Cancelado")
        elif job.status == JobStatus.RUNNING and job_id in self._workers:
            job.stage = "Cancelando…"
            self.job_changed.emit(job)
            self._workers[job_id].cancel()

    def remove(self, job_id: int) -> None:
        job = self.jobs.get(job_id)
        if job and job.status not in (JobStatus.RUNNING,):
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
            del self.jobs[job_id]
            self.job_removed.emit(job_id)

    def clear_finished(self) -> None:
        for jid in [j.id for j in self.jobs.values() if j.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)]:
            self.remove(jid)

    def has_active(self) -> bool:
        return any(j.status in (JobStatus.QUEUED, JobStatus.RUNNING) for j in self.jobs.values())

    def shutdown(self, wait_ms: int = 5000) -> None:
        for j in self.jobs.values():
            if j.status == JobStatus.QUEUED:
                j.status = JobStatus.CANCELLED
        for w in list(self._workers.values()):
            w.cancel()
        for w in list(self._workers.values()):
            w.wait(wait_ms)

    # ------------------------------------------------------------------ interno
    def _running(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == JobStatus.RUNNING)

    def _pump(self) -> None:
        for job in list(self.jobs.values()):
            if self._running() >= self.max_concurrent:
                return
            if job.status == JobStatus.QUEUED:
                self._start(job)

    def _start(self, job: DownloadJob) -> None:
        worker = DownloadWorker(job, self.ffmpeg, self)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        # método de QObject => entrega enfileirada na thread da GUI (um lambda rodaria na thread do worker)
        worker.finished.connect(self._on_worker_finished)
        self._workers[job.id] = worker
        self._set(job, JobStatus.RUNNING, stage="Iniciando…")
        worker.start()

    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if isinstance(worker, DownloadWorker):
            self._workers.pop(worker.job.id, None)
            worker.deleteLater()
        self._pump()

    def _set(self, job: DownloadJob, status: JobStatus, **fields) -> None:
        job.status = status
        for k, v in fields.items():
            setattr(job, k, v)
        self.job_changed.emit(job)

    def _on_progress(self, job_id: int, p: Progress) -> None:
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.RUNNING or job.stage == "Cancelando…":
            return
        if p.percent is not None:
            job.percent = p.percent
        job.speed, job.eta, job.stage = p.speed, p.eta, p.stage
        if p.total_bytes:
            job.total_bytes = p.total_bytes
        self.job_changed.emit(job)

    def _on_done(self, job_id: int, path: str) -> None:
        if job := self.jobs.get(job_id):
            self._set(job, JobStatus.DONE, percent=100.0, speed=None, eta=None, stage="Concluído", output_path=path)
            self.job_finished.emit(job)

    def _on_failed(self, job_id: int, message: str) -> None:
        if job := self.jobs.get(job_id):
            self._set(job, JobStatus.FAILED, error=message, speed=None, eta=None, stage="Falhou")

    def _on_cancelled(self, job_id: int) -> None:
        if job := self.jobs.get(job_id):
            self._set(job, JobStatus.CANCELLED, speed=None, eta=None, stage="Cancelado")
