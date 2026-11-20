"""Pasta de destino."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from app.ui import styles
from app.ui.components.common import Card, ElidedLabel, SectionHeader, make_button
from app.utils.system import open_folder


class FolderCard(Card):
    changed = Signal()

    def __init__(self, folder: str, open_after: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)
        root.addWidget(SectionHeader("folder", "Salvar em"))

        row = QHBoxLayout()
        row.setSpacing(8)
        self.path_label = ElidedLabel(folder)
        self.path_label.setMinimumHeight(34)
        self.choose = make_button("Alterar", "folder", "", "Escolher outra pasta")
        self.open_btn = make_button("", "external", "ghost", "Abrir pasta", styles.MUTED)
        self.open_btn.setFixedSize(34, 34)
        row.addWidget(self.path_label, 1)
        row.addWidget(self.choose)
        row.addWidget(self.open_btn)
        root.addLayout(row)

        self.open_after = QCheckBox("Abrir a pasta ao concluir o download")
        self.open_after.setChecked(open_after)
        root.addWidget(self.open_after)

        self.folder = folder
        self.choose.clicked.connect(self._pick)
        self.open_btn.clicked.connect(lambda: open_folder(self.folder))
        self.open_after.toggled.connect(lambda _: self.changed.emit())

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Escolha a pasta de destino", self.folder)
        if d:
            self.set_folder(d)

    def set_folder(self, folder: str) -> None:
        self.folder = folder
        self.path_label.setText(folder)
        self.changed.emit()
