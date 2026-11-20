"""Aviso de uso responsável, exibido uma vez."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.components.common import make_button


class TermsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Antes de começar")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        h = QLabel("Uso responsável")
        h.setObjectName("h1")
        body = QLabel(
            "O Nokk Downloader funciona 100% no seu computador, sem servidores externos.\n\n"
            "• Baixe apenas conteúdo que você tem autorização para baixar: seus próprios vídeos, "
            "conteúdo com licença que permita download ou com permissão do autor.\n"
            "• O app não contorna DRM, login, restrições de idade nem qualquer proteção de acesso.\n"
            "• Você é responsável por respeitar os Termos de Serviço do YouTube e as leis de direitos autorais do seu país."
        )
        body.setWordWrap(True)
        body.setObjectName("muted")
        row = QHBoxLayout()
        row.addStretch(1)
        no = make_button("Sair")
        ok = make_button("Entendi e concordo", None, "primary")
        row.addWidget(no)
        row.addWidget(ok)
        lay.addWidget(h)
        lay.addWidget(body)
        lay.addSpacing(6)
        lay.addLayout(row)
        ok.clicked.connect(self.accept)
        no.clicked.connect(self.reject)
