"""Integração com o sistema operacional (abrir pasta, revelar arquivo)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder(path: str | Path) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def reveal_file(path: str | Path) -> None:
    """Abre a pasta com o arquivo selecionado (Explorer no Windows)."""
    path = Path(path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(str(path))])
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
            return
    except OSError:
        pass
    open_folder(path.parent)
