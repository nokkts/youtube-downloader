"""Configurações persistentes (JSON em %APPDATA%\\NokkDownloader no Windows).

O arquivo guarda apenas preferências (pasta, formato, bitrate...). Nenhuma credencial ou cookie.
Se um dia houver histórico, o módulo pode migrar para SQLite sem alterar quem o consome.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "NokkDownloader"


def default_download_dir() -> str:
    videos = Path.home() / "Videos"
    return str(videos if videos.exists() else Path.home() / "Downloads")


@dataclass
class Settings:
    download_dir: str = ""
    format: str = "mp4"          # "mp4" | "mp3"
    mp3_bitrate: int = 320
    open_folder_after: bool = False
    notify_on_finish: bool = True
    terms_accepted: bool = False
    window_width: int = 1180
    window_height: int = 760

    def __post_init__(self) -> None:
        if not self.download_dir:
            self.download_dir = default_download_dir()


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "settings.json")
        self.data = self._load()

    def _load(self) -> Settings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {f.name for f in fields(Settings)}
            return Settings(**{k: v for k, v in raw.items() if k in allowed})
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # escrita atômica: evita corromper o arquivo se o app fechar no meio
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self.data), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass  # preferências não são críticas; nunca derrubar o app por isso
