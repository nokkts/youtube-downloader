"""Campo de URL + Analisar + Limpar."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.ui import icons, styles
from app.ui.components.common import make_button, repolish


class UrlBar(QWidget):
    analyze = Signal(str)
    cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.box = QFrame()
        self.box.setObjectName("urlbar")
        row = QHBoxLayout(self.box)
        row.setContentsMargins(14, 6, 6, 6)
        row.setSpacing(8)
        lead = QLabel()
        lead.setPixmap(icons.pixmap("link", styles.MUTED, 18))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Cole aqui o link do vídeo ou Short do YouTube")
        self.edit.setClearButtonEnabled(False)
        self.edit.installEventFilter(self)
        self.clear_btn = make_button("", "x", "ghost", "Limpar", styles.MUTED)
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.hide()
        self.go_btn = make_button("Analisar", "search", "primary")
        self.go_btn.setMinimumHeight(38)
        row.addWidget(lead)
        row.addWidget(self.edit, 1)
        row.addWidget(self.clear_btn)
        row.addWidget(self.go_btn)
        outer.addWidget(self.box)

        self.status = QLabel("")
        self.status.setObjectName("err")
        self.status.setWordWrap(True)
        self.status.hide()
        outer.addWidget(self.status)

        self.edit.textChanged.connect(lambda t: self.clear_btn.setVisible(bool(t)))
        self.edit.returnPressed.connect(self._go)
        self.go_btn.clicked.connect(self._go)
        self.clear_btn.clicked.connect(self.clear)

    def eventFilter(self, obj, event):  # noqa: N802 — destaca a borda quando o campo tem foco
        if obj is self.edit and event.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.box.setProperty("focus", event.type() == QEvent.FocusIn)
            repolish(self.box)
        return super().eventFilter(obj, event)

    def text(self) -> str:
        return self.edit.text().strip()

    def _go(self) -> None:
        if self.go_btn.isEnabled():
            self.analyze.emit(self.text())

    def clear(self) -> None:
        self.edit.clear()
        self.set_status("")
        self.edit.setFocus()
        self.cleared.emit()

    def set_busy(self, busy: bool) -> None:
        self.go_btn.setEnabled(not busy)
        self.go_btn.setText("Analisando…" if busy else "Analisar")
        self.edit.setEnabled(not busy)

    def set_status(self, message: str, kind: str = "err") -> None:
        self.status.setObjectName("ok" if kind == "ok" else "err")
        repolish(self.status)
        self.status.setText(message)
        self.status.setVisible(bool(message))
