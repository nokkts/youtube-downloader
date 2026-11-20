"""Área de downloads: lista rolável + estado vazio."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QStackedLayout, QVBoxLayout, QWidget

from app.core.models import DownloadJob, JobStatus
from app.ui import styles
from app.ui.components.common import Card, SectionHeader, fade_in, make_button
from app.ui.components.download_item import DownloadItem
from app.ui import icons


class DownloadsPanel(Card):
    cancel_requested = Signal(int)
    remove_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

        head = SectionHeader("download", "Downloads")
        self.count = QLabel("")
        self.count.setObjectName("small")
        self.clear_btn = make_button("Limpar concluídos", None, "ghost")
        head.right.addWidget(self.count)
        head.right.addWidget(self.clear_btn)
        root.addWidget(head)

        host = QWidget()
        self.stack = QStackedLayout(host)

        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignCenter)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("inbox", "#3a3a3a", 44))
        ic.setAlignment(Qt.AlignCenter)
        t = QLabel("Nenhum download ainda")
        t.setObjectName("h2")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("Os downloads aparecem aqui com progresso,\nvelocidade e tamanho.")
        s.setObjectName("muted")
        s.setAlignment(Qt.AlignCenter)
        for w in (ic, t, s):
            el.addWidget(w)
        self.stack.addWidget(empty)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 4, 0)
        self.list.setSpacing(10)
        self.list.addStretch(1)
        self.scroll.setWidget(inner)
        self.stack.addWidget(self.scroll)
        root.addWidget(host, 1)

        self.items: dict[int, DownloadItem] = {}
        self.clear_btn.clicked.connect(self.clear_requested)
        self._refresh()

    def add_job(self, job: DownloadJob) -> None:
        item = DownloadItem(job)
        item.cancel_requested.connect(self.cancel_requested)
        item.remove_requested.connect(self.remove_requested)
        self.items[job.id] = item
        self.list.insertWidget(0, item)           # mais novo no topo
        fade_in(item)
        self._refresh()

    def update_job(self, job: DownloadJob) -> None:
        if item := self.items.get(job.id):
            item.update_job(job)
        self._refresh()

    def remove_job(self, job_id: int) -> None:
        if item := self.items.pop(job_id, None):
            self.list.removeWidget(item)
            item.deleteLater()
        self._refresh()

    def _refresh(self) -> None:
        self.stack.setCurrentIndex(1 if self.items else 0)
        self.count.setText(f"{len(self.items)} item(ns)" if self.items else "")
        self.clear_btn.setVisible(bool(self.items))
