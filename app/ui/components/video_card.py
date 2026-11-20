"""Card com preview do vídeo: miniatura, título, canal, duração e qualidades disponíveis."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.models import VideoInfo
from app.ui import icons, styles
from app.ui.components.common import Card, Pill, fmt_duration, rounded_pixmap

THUMB_W, THUMB_H = 184, 104


def tier_label(h: int) -> str:
    return {2160: "4K", 1440: "2K"}.get(h, f"{h}p") if h >= 1440 else f"{h}p"


class VideoCard(Card):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        top.addWidget(self.thumb, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(5)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(66)  # ~3 linhas
        self.channel = QLabel()
        self.channel.setObjectName("muted")
        meta = QHBoxLayout()
        meta.setSpacing(6)
        self.duration = Pill("", "accent")
        self.maxq = Pill("")
        meta.addWidget(self.duration)
        meta.addWidget(self.maxq)
        meta.addStretch(1)
        text.addWidget(self.title)
        text.addWidget(self.channel)
        text.addStretch(1)
        text.addLayout(meta)
        top.addLayout(text, 1)
        root.addLayout(top)

        self.avail_label = QLabel("Qualidades disponíveis")
        self.avail_label.setObjectName("small")
        self.avail_row = QHBoxLayout()
        self.avail_row.setSpacing(6)
        root.addWidget(self.avail_label)
        root.addLayout(self.avail_row)

    def set_info(self, info: VideoInfo) -> None:
        self.thumb.setPixmap(rounded_pixmap(info.thumbnail_bytes, THUMB_W, THUMB_H, 10))
        self.title.setText(info.title)
        self.title.setToolTip(info.title)
        self.channel.setText(info.channel)
        self.duration.setText(fmt_duration(info.duration))
        self.maxq.setText(f"até {tier_label(info.available_heights[0])}" if info.available_heights else "somente áudio")
        while self.avail_row.count():
            item = self.avail_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if info.available_heights:
            for h in info.available_heights:
                self.avail_row.addWidget(Pill(f"{h}p" + (" 4K" if h == 2160 else ""), "accent" if h == info.available_heights[0] else ""))
            self.avail_label.setText("Qualidades disponíveis")
        else:
            self.avail_label.setText("Nenhuma qualidade de vídeo padrão encontrada; use MP3 ou 'Melhor disponível'.")
        self.avail_row.addStretch(1)
