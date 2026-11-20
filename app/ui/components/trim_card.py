"""Recorte por minutagem (Início/Fim) com validação e visualização do trecho."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QRegularExpression, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRegularExpressionValidator
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.ui import styles
from app.ui.components.common import Card, SectionHeader, fmt_duration, repolish
from app.utils.validators import (RangeError, TimeRange, format_timecode, parse_timecode, validate_range)


class RangeBar(QWidget):
    """Linha do tempo: mostra qual parte do vídeo foi selecionada."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self._duration: float | None = None
        self._start = 0.0
        self._end = 0.0
        self._valid = True

    def set_state(self, duration: float | None, start: float | None, end: float | None, valid: bool) -> None:
        self._duration = duration
        self._start, self._end, self._valid = start or 0.0, end or 0.0, valid
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 7, self.width(), 8)
        track = QPainterPath()
        track.addRoundedRect(r, 4, 4)
        p.fillPath(track, QColor("#2a2a2a"))
        if not self._duration:
            return
        full = self._end <= self._start
        s, e = (0.0, self._duration) if full else (self._start, self._end)
        x1 = r.width() * max(0.0, min(1.0, s / self._duration))
        x2 = r.width() * max(0.0, min(1.0, e / self._duration))
        sel = QPainterPath()
        sel.addRoundedRect(QRectF(x1, 4, max(x2 - x1, 3), 14), 5, 5)
        color = QColor(styles.ACCENT if self._valid else styles.ERR)
        if full:
            color.setAlpha(70)
        p.fillPath(sel, color)


class TrimCard(Card):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration: float | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        root.addWidget(SectionHeader("scissors", "Recorte por minutagem"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        rx = QRegularExpressionValidator(QRegularExpression(r"[0-9:.,]{0,12}"))
        self.start = QLineEdit()
        self.end = QLineEdit()
        for edit, placeholder in ((self.start, "00:00:00"), (self.end, "00:00:00")):
            edit.setObjectName("time")
            edit.setPlaceholderText(placeholder)
            edit.setValidator(rx)
            edit.setAlignment(Qt.AlignCenter)
            edit.textChanged.connect(self._validate)
            edit.editingFinished.connect(lambda e=edit: self._normalize(e))
        lbl_s, lbl_e = QLabel("Início"), QLabel("Fim")
        lbl_s.setObjectName("muted")
        lbl_e.setObjectName("muted")
        grid.addWidget(lbl_s, 0, 0)
        grid.addWidget(lbl_e, 0, 1)
        grid.addWidget(self.start, 1, 0)
        grid.addWidget(self.end, 1, 1)
        root.addLayout(grid)

        self.bar = RangeBar()
        root.addWidget(self.bar)
        self.summary = QLabel("")
        self.summary.setObjectName("small")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self._validate()

    # ---- API
    def set_duration(self, seconds: float | None) -> None:
        self._duration = seconds
        self.end.setPlaceholderText(format_timecode(seconds) if seconds else "00:00:00")
        self.start.clear()
        self.end.clear()
        self._validate()

    def reset(self) -> None:
        self.set_duration(None)

    def get_range(self) -> TimeRange | None:
        """None = vídeo completo. Lança RangeError se os campos estiverem inválidos."""
        return validate_range(self.start.text(), self.end.text(), self._duration)

    def is_valid(self) -> bool:
        try:
            self.get_range()
            return True
        except RangeError:
            return False

    # ---- interno
    def _normalize(self, edit: QLineEdit) -> None:
        v = parse_timecode(edit.text())
        if v is not None and edit.text().strip():
            edit.setText(format_timecode(v, with_ms=True))

    def _validate(self) -> None:
        err = None
        rng = None
        try:
            rng = self.get_range()
        except RangeError as exc:
            err = str(exc)
        for edit in (self.start, self.end):
            bad = err is not None and bool(edit.text().strip()) and (
                parse_timecode(edit.text()) is None or (self._duration and (parse_timecode(edit.text()) or 0) > self._duration + 0.5))
            edit.setProperty("invalid", bool(bad))
            repolish(edit)
        if err:
            self.summary.setObjectName("err")
            self.summary.setText(err)
            self.bar.set_state(self._duration, None, None, False)
        else:
            self.summary.setObjectName("small")
            if rng:
                pct = rng.length / self._duration * 100 if self._duration else 0
                self.summary.setText(f"Trecho selecionado: {fmt_duration(rng.length)}"
                                     f"  ({fmt_duration(rng.start)} → {fmt_duration(rng.end)}"
                                     + (f", {pct:.0f}% do vídeo)" if pct else ")")
                                     + "  ·  só esse trecho será baixado.")
            elif self._duration:
                self.summary.setText(f"Vídeo completo ({fmt_duration(self._duration)}). Preencha Início e/ou Fim para baixar só um trecho.")
            else:
                self.summary.setText("Analise um vídeo para definir o trecho.")
            self.bar.set_state(self._duration, rng.start if rng else 0, rng.end if rng else 0, True)
        repolish(self.summary)
        self.changed.emit()
