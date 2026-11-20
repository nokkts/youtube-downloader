"""Nokk Downloader — ponto de entrada."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.ffmpeg import find_ffmpeg
from app.ui import icons, styles
from app.ui.main_window import MainWindow
from app.ui.terms_dialog import TermsDialog
from app.utils.settings import SettingsStore


def main() -> int:
    if sys.platform.startswith("win"):
        try:  # agrupa corretamente o ícone na barra de tarefas
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nokk.Downloader")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Nokk Downloader")
    app.setWindowIcon(icons.app_icon())
    app.setStyleSheet(styles.stylesheet())

    store = SettingsStore()
    if not store.data.terms_accepted:
        if TermsDialog().exec() != TermsDialog.Accepted:
            return 0
        store.data.terms_accepted = True
        store.save()

    window = MainWindow(store, find_ffmpeg())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
