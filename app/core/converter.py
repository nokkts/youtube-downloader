"""Operações diretas com FFmpeg (recorte local e MP3).

O caminho principal usa o yt-dlp (que baixa só o trecho e chama o FFmpeg). Estas funções são:
  * o plano B quando o recorte remoto falha (baixa o arquivo inteiro e recorta localmente);
  * utilitários testáveis isoladamente.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from app.core.errors import DownloadCancelled, NokkError

_TIME = re.compile(r"out_time_ms=(\d+)")
_NOWIN = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0


def _run(cmd: list[str], total: float | None, on_progress: Callable[[float], None] | None,
         cancel: threading.Event | None) -> None:
    proc = subprocess.Popen(
        cmd + ["-progress", "pipe:1", "-nostats"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=_NOWIN,
    )
    err_chunks: list[str] = []
    t = threading.Thread(target=lambda: err_chunks.append(proc.stderr.read()), daemon=True)
    t.start()
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if cancel and cancel.is_set():
                proc.kill()
                proc.wait()
                raise DownloadCancelled()
            m = _TIME.match(line.strip())
            if m and total and on_progress:
                on_progress(min(100.0, int(m.group(1)) / 1_000_000 / total * 100))
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    t.join(timeout=2)
    if proc.returncode != 0:
        tail = (err_chunks[0] if err_chunks else "").strip().splitlines()[-3:]
        raise NokkError("O FFmpeg falhou ao processar o arquivo: " + " | ".join(tail))


def trim(ffmpeg: str, src: str, dst: str, start: float, end: float, *, reencode_audio_only: bool = False,
         on_progress: Callable[[float], None] | None = None, cancel: threading.Event | None = None) -> None:
    """Recorta [start, end] de src para dst.

    Vídeo é recodificado em H.264 (CRF 17, visualmente sem perdas) para que o corte seja exato no frame
    e não haja trecho congelado no início, comum com `-c copy` fora de keyframes.
    """
    length = end - start
    cmd = [ffmpeg, "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{length:.3f}"]
    if reencode_audio_only:
        cmd += ["-vn", "-c:a", "aac", "-b:a", "256k"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart"]
    cmd.append(dst)
    _run(cmd, length, on_progress, cancel)


def to_mp3(ffmpeg: str, src: str, dst: str, bitrate: int = 320, start: float | None = None, end: float | None = None,
           on_progress: Callable[[float], None] | None = None, cancel: threading.Event | None = None,
           total: float | None = None) -> None:
    """Converte para MP3 CBR no bitrate pedido. `total` (s) só serve para calcular o progresso."""
    cmd = [ffmpeg, "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", src]
    if start is not None and end is not None:
        total = end - start
        cmd += ["-t", f"{total:.3f}"]
    cmd += ["-vn", "-c:a", "libmp3lame", "-b:a", f"{bitrate}k", "-id3v2_version", "3", dst]
    _run(cmd, total, on_progress, cancel)


def probe_duration(ffprobe: str | None, path: str) -> float | None:
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=20, creationflags=_NOWIN)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def unique_path(path: Path) -> Path:
    """Evita sobrescrever: 'video.mp4' -> 'video (1).mp4'."""
    if not path.exists():
        return path
    for i in range(1, 1000):
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
    return path
