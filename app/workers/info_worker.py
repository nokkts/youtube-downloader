"""Busca metadados do vídeo em segundo plano."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.core.errors import friendly_message
from app.core.youtube import fetch_video_info


class InfoWorker(QThread):
    succeeded = Signal(object)   # VideoInfo
    failed = Signal(str)

    def __init__(self, url: str, ffmpeg_dir: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._url, self._ffmpeg_dir = url, ffmpeg_dir

    def run(self) -> None:
        try:
            info = fetch_video_info(self._url, self._ffmpeg_dir)
            if info.is_live:
                self.failed.emit("Transmissões ao vivo em andamento não podem ser baixadas. Volte quando a live terminar.")
                return
            self.succeeded.emit(info)
        except Exception as exc:  # noqa: BLE001 — qualquer falha vira mensagem amigável
            self.failed.emit(friendly_message(exc))
