"""Localização e verificação do FFmpeg."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_EXE = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
_PROBE = "ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"

INSTALL_HELP = (
    "O FFmpeg não foi encontrado neste computador.\n\n"
    "Como instalar no Windows:\n"
    "  1. Abra o Prompt de Comando ou o PowerShell e execute:\n"
    "       winget install Gyan.FFmpeg\n"
    "  2. Feche e abra o Nokk Downloader novamente.\n\n"
    "Alternativa: baixe em https://www.gyan.dev/ffmpeg/builds/, extraia e coloque "
    "ffmpeg.exe e ffprobe.exe dentro da pasta 'ffmpeg' ao lado do aplicativo, "
    "ou adicione a pasta 'bin' ao PATH do Windows."
)


@dataclass(frozen=True)
class FFmpegInfo:
    ffmpeg: str
    ffprobe: str | None
    version: str

    @property
    def location(self) -> str:
        return str(Path(self.ffmpeg).parent)


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def _candidates() -> list[Path]:
    app = _app_dir()
    cands = [app / "ffmpeg" / _EXE, app / "ffmpeg" / "bin" / _EXE, app / _EXE]
    if sys.platform.startswith("win"):
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        cands += [
            Path(r"C:\ffmpeg\bin") / _EXE,
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ffmpeg" / "bin" / _EXE,
        ]
        # winget (Gyan.FFmpeg) instala em um diretório com hash; o PATH costuma resolver,
        # mas mantemos um fallback por varredura.
        links = local / "Microsoft" / "WinGet" / "Links" / _EXE
        cands.append(links)
        pkgs = local / "Microsoft" / "WinGet" / "Packages"
        if pkgs.exists():
            cands += sorted(pkgs.glob(f"Gyan.FFmpeg*/**/bin/{_EXE}"))
    return cands


def _version_of(path: str) -> str | None:
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10, creationflags=flags)
        if out.returncode == 0 and out.stdout:
            return out.stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def find_ffmpeg() -> FFmpegInfo | None:
    """Procura ffmpeg ao lado do app, no PATH e em locais comuns. None se não achar/funcionar."""
    found = [str(p) for p in _candidates() if p.is_file()]
    on_path = shutil.which("ffmpeg")
    if on_path:
        found.append(on_path)
    for path in found:
        version = _version_of(path)
        if version:
            probe = Path(path).with_name(_PROBE)
            probe_path = str(probe) if probe.is_file() else shutil.which("ffprobe")
            return FFmpegInfo(ffmpeg=path, ffprobe=probe_path, version=version)
    return None
