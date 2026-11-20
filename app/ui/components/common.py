"""Widgets e helpers reutilizáveis."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal, Property
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QWidget)

from app.ui import icons, styles


# ------------------------------------------------------------------ formatação
def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def fmt_bytes(n: float | None) -> str:
    if not n:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def fmt_speed(bps: float | None) -> str:
    return f"{fmt_bytes(bps)}/s" if bps else ""


def fmt_eta(seconds: int | None) -> str:
    return fmt_duration(seconds) if seconds is not None else ""


# ------------------------------------------------------------------ imagens
def rounded_pixmap(data: bytes | None, w: int, h: int, radius: int = 10, dpr: float = 2.0) -> QPixmap:
    out = QPixmap(int(w * dpr), int(h * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(QColor("#232323"))
    if data:
        src = QPixmap()
        if src.loadFromData(data):
            scaled = src.scaled(int(w * dpr), int(h * dpr), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x, y = (scaled.width() - out.width()) // 2, (scaled.height() - out.height()) // 2
            out = scaled.copy(x, y, out.width(), out.height())
            out.setDevicePixelRatio(dpr)
    mask = QPixmap(out.size())
    mask.setDevicePixelRatio(dpr)
    mask.fill(Qt.transparent)
    p = QPainter(mask)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.fillPath(path, Qt.white)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.drawPixmap(0, 0, out)
    p.end()
    return mask


def fade_in(widget: QWidget, ms: int = 240) -> None:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    widget._fade_anim = anim  # type: ignore[attr-defined]  # mantém referência


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


# ------------------------------------------------------------------ widgets
class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")


class ElidedLabel(QLabel):
    """Rótulo de uma linha que corta com '…' em vez de forçar a largura mínima da janela."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._full = text

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        super().setText(text)
        self.setToolTip(text)
        self.update()

    def minimumSizeHint(self):  # noqa: N802
        return QSize(10, super().minimumSizeHint().height())

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        fm = QFontMetrics(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(self.rect(), int(self.alignment()) | Qt.AlignVCenter,
                   fm.elidedText(self._full, Qt.ElideRight, self.width()))


class Pill(QLabel):
    def __init__(self, text: str, kind: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("pill")
        self.setProperty("kind", kind)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set_kind(self, kind: str) -> None:
        self.setProperty("kind", kind)
        repolish(self)


class SectionHeader(QWidget):
    def __init__(self, icon_name: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, styles.MUTED, 16))
        ic.setObjectName("sectionIcon")
        lbl = QLabel(text)
        lbl.setObjectName("h2")
        lay.addWidget(ic)
        lay.addWidget(lbl)
        lay.addStretch(1)
        self.right = lay


class SegmentedControl(QFrame):
    """Dois ou mais botões exclusivos (ex.: MP4 | MP3)."""
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segbox")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label, icon_name in options:
            b = QPushButton(label)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(icons.icon(icon_name, "#ffffff", "#777777", 16))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._group.addButton(b)
            self._buttons[key] = b
            lay.addWidget(b)
            b.toggled.connect(lambda on, k=key: on and self.changed.emit(k))
        next(iter(self._buttons.values())).setChecked(True)

    def value(self) -> str:
        return next(k for k, b in self._buttons.items() if b.isChecked())

    def set_value(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)


class SmoothProgress(QWidget):
    """Barra de progresso arredondada com animação suave e modo indeterminado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self._shown = 0.0
        self._target = 0.0
        self._indeterminate = False
        self._phase = 0.0
        self._color = QColor(styles.ACCENT)
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def _get(self) -> float:
        return self._shown

    def _set(self, v: float) -> None:
        self._shown = v
        self.update()

    shown = Property(float, _get, _set)

    def set_value(self, pct: float) -> None:
        pct = max(0.0, min(100.0, pct))
        if abs(pct - self._target) < 0.01:
            return
        self._target = pct
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(pct)
        self._anim.start()

    def value(self) -> float:
        return self._target

    def set_indeterminate(self, on: bool) -> None:
        if on == self._indeterminate:
            return
        self._indeterminate = on
        self._timer.start() if on else self._timer.stop()
        self.update()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.025) % 1.0
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        rad = r.height() / 2
        track = QPainterPath()
        track.addRoundedRect(r, rad, rad)
        p.fillPath(track, QColor("#2a2a2a"))
        if self._indeterminate:
            w = r.width() * 0.32
            x = -w + (r.width() + w) * self._phase
            seg = QPainterPath()
            seg.addRoundedRect(QRectF(max(0, x), 0, min(w, r.width() - max(0, x), x + w), r.height()), rad, rad)
            p.fillPath(seg.intersected(track), self._color)
            return
        w = r.width() * self._shown / 100.0
        if w <= 0:
            return
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(0, 0, max(w, r.height()), r.height()), rad, rad)
        grad = QLinearGradient(0, 0, r.width(), 0)
        grad.setColorAt(0, self._color.darker(115))
        grad.setColorAt(1, self._color.lighter(120))
        p.fillPath(bar, grad)


def make_button(text: str, icon_name: str | None = None, kind: str = "", tooltip: str = "",
                icon_color: str = "#ececec") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind.split()[0])
    if icon_name:
        b.setIcon(icons.icon(icon_name, "#ffffff" if kind.startswith("primary") else icon_color))
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    return b
