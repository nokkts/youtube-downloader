"""Linha da fila de downloads."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.models import DownloadJob, JobStatus
from app.ui import styles
from app.ui.components.common import (ElidedLabel, Pill, SmoothProgress, fmt_bytes, fmt_duration, fmt_eta, fmt_speed,
                                      make_button, repolish, rounded_pixmap)
from app.utils.system import open_folder, reveal_file
from app.utils.validators import format_timecode


class DownloadItem(QFrame):
    cancel_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, job: DownloadJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("item")
        self.job_id = job.id
        self._path: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(112, 63)
        self.thumb.setPixmap(rounded_pixmap(job.info.thumbnail_bytes, 112, 63, 8))
        root.addWidget(self.thumb)

        col = QVBoxLayout()
        col.setSpacing(6)
        self.title = ElidedLabel(job.info.title)
        self.title.setObjectName("title")
        self.title.setMinimumHeight(20)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        opts = job.options
        chips.addWidget(Pill(opts.format.upper(), "accent"))
        chips.addWidget(Pill(opts.quality_label))
        if opts.time_range:
            chips.addWidget(Pill(f"✂ {format_timecode(opts.time_range.start)} → {format_timecode(opts.time_range.end)}"))
        chips.addStretch(1)
        self.status_pill = Pill("Na fila")
        chips.addWidget(self.status_pill)

        self.bar = SmoothProgress()
        self.stats = QLabel("")
        self.stats.setObjectName("small")
        self.stats.setWordWrap(True)

        col.addWidget(self.title)
        col.addLayout(chips)
        col.addWidget(self.bar)
        col.addWidget(self.stats)
        root.addLayout(col, 1)

        btns = QVBoxLayout()
        btns.setSpacing(4)
        self.cancel_btn = make_button("", "x", "ghost danger", "Cancelar download", styles.MUTED)
        self.show_btn = make_button("", "folder", "ghost", "Mostrar arquivo na pasta", styles.MUTED)
        self.remove_btn = make_button("", "trash", "ghost", "Remover da lista", styles.MUTED)
        for b in (self.cancel_btn, self.show_btn, self.remove_btn):
            b.setFixedSize(32, 32)
            btns.addWidget(b)
        btns.addStretch(1)
        root.addLayout(btns)
        self.show_btn.hide()
        self.remove_btn.hide()

        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.job_id))
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.job_id))
        self.show_btn.clicked.connect(self._show)
        self.update_job(job)

    def _show(self) -> None:
        if self._path:
            reveal_file(self._path)

    def update_job(self, job: DownloadJob) -> None:
        st = job.status
        running = st in (JobStatus.QUEUED, JobStatus.RUNNING)
        self.cancel_btn.setVisible(running)
        self.cancel_btn.setEnabled(job.stage != "Cancelando…")
        self.remove_btn.setVisible(not running)
        self.show_btn.setVisible(st == JobStatus.DONE)
        self._path = job.output_path

        kind = {JobStatus.DONE: "ok", JobStatus.FAILED: "err"}.get(st, "")
        self.status_pill.set_kind(kind)
        self.status_pill.setText({JobStatus.QUEUED: "Na fila", JobStatus.DONE: "✓ Concluído", JobStatus.FAILED: "Falhou",
                                  JobStatus.CANCELLED: "Cancelado", JobStatus.RUNNING: "Baixando"}.get(st, job.stage))
        self.bar.set_color(styles.OK if st == JobStatus.DONE else styles.ERR if st == JobStatus.FAILED else styles.ACCENT)

        if st == JobStatus.RUNNING:
            indeterminate = job.percent <= 0
            self.bar.set_indeterminate(indeterminate)
            self.bar.set_value(job.percent)
            parts = [f"{job.percent:.0f}%" if not indeterminate else "", job.stage]
            if job.speed:
                parts.append(fmt_speed(job.speed))
            if job.total_bytes:
                parts.append(f"~{fmt_bytes(job.total_bytes)}")
            if job.eta is not None:
                parts.append(f"faltam {fmt_eta(job.eta)}")
            self.stats.setText("  ·  ".join(p for p in parts if p))
        else:
            self.bar.set_indeterminate(False)
            self.bar.set_value(100.0 if st == JobStatus.DONE else job.percent)
            if st == JobStatus.DONE:
                size = ""
                try:
                    import os
                    size = f"  ·  {fmt_bytes(os.path.getsize(job.output_path))}" if job.output_path else ""
                except OSError:
                    pass
                self.stats.setText("Salvo em " + (job.output_path or "") + size)
                self.stats.setToolTip(job.output_path or "")
            elif st == JobStatus.FAILED:
                self.stats.setObjectName("err")
                repolish(self.stats)
                self.stats.setText(job.error or "Erro desconhecido.")
            elif st == JobStatus.CANCELLED:
                self.stats.setText("Download cancelado. Nenhum arquivo foi mantido.")
            else:
                self.stats.setText("Aguardando a vez…")
