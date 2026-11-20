"""Formato (MP4/MP3), qualidade de vídeo e bitrate de MP3."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.models import MP3_BITRATES, VideoInfo
from app.ui.components.common import Card, SectionHeader, SegmentedControl

TIER_NAMES = {2160: "2160p (4K)", 1440: "1440p (2K)", 1080: "1080p (Full HD)", 720: "720p (HD)", 480: "480p", 360: "360p"}


class OptionsCard(Card):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)
        root.addWidget(SectionHeader("video", "Formato e qualidade"))

        self.format = SegmentedControl([("mp4", "MP4 · Vídeo", "video"), ("mp3", "MP3 · Áudio", "music")])
        root.addWidget(self.format)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.label = QLabel("Qualidade")
        self.label.setObjectName("muted")
        self.quality = QComboBox()
        self.bitrate = QComboBox()
        for b in MP3_BITRATES:
            self.bitrate.addItem(f"{b} kbps", b)
        row.addWidget(self.label)
        row.addWidget(self.quality, 1)
        row.addWidget(self.bitrate, 1)
        root.addLayout(row)

        self.hint = QLabel("")
        self.hint.setObjectName("small")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.format.changed.connect(self._on_format)
        self.quality.currentIndexChanged.connect(lambda _: self.changed.emit())
        self.bitrate.currentIndexChanged.connect(lambda _: self.changed.emit())
        self._on_format("mp4")

    # ---- API
    def set_info(self, info: VideoInfo | None) -> None:
        self.quality.blockSignals(True)
        self.quality.clear()
        if info:
            best = f"Melhor disponível ({info.available_heights[0]}p)" if info.available_heights else "Melhor disponível"
            self.quality.addItem(best, None)
            for h in info.available_heights:
                self.quality.addItem(TIER_NAMES.get(h, f"{h}p"), h)
        self.quality.blockSignals(False)
        self._refresh_hint()

    def format_value(self) -> str:
        return self.format.value()

    def quality_value(self) -> int | None:
        return self.quality.currentData()

    def bitrate_value(self) -> int:
        return int(self.bitrate.currentData() or 320)

    def set_format(self, fmt: str) -> None:
        self.format.set_value(fmt)

    def set_bitrate(self, kbps: int) -> None:
        i = self.bitrate.findData(kbps)
        if i >= 0:
            self.bitrate.setCurrentIndex(i)

    # ---- interno
    def _on_format(self, fmt: str) -> None:
        mp3 = fmt == "mp3"
        self.label.setText("Bitrate" if mp3 else "Qualidade")
        self.quality.setVisible(not mp3)
        self.bitrate.setVisible(mp3)
        self._refresh_hint()
        self.changed.emit()

    def _refresh_hint(self) -> None:
        if self.format.value() == "mp3":
            self.hint.setText("O áudio é baixado na melhor qualidade original e convertido para MP3 pelo FFmpeg.")
        else:
            self.hint.setText("Vídeo e áudio são baixados separadamente na melhor qualidade e combinados pelo FFmpeg. "
                              "Acima de 1080p o YouTube usa codecs VP9/AV1.")
