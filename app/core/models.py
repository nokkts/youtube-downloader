"""Modelos de dados compartilhados entre core, workers e UI."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

from app.utils.validators import TimeRange

QUALITY_TIERS = (2160, 1440, 1080, 720, 480, 360)
MP3_BITRATES = (320, 256, 192, 128)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class VideoInfo:
    video_id: str
    url: str
    title: str
    channel: str
    duration: float | None
    thumbnail_url: str | None
    thumbnail_bytes: bytes | None = None
    available_heights: list[int] = field(default_factory=list)  # tiers realmente disponíveis, desc
    max_height: int = 0
    is_live: bool = False
    has_audio: bool = True
    # formatos crus (dicts do yt-dlp) usados no seletor de formato; não são exibidos
    formats: list[dict] = field(default_factory=list, repr=False)


@dataclass
class DownloadOptions:
    format: str = "mp4"            # "mp4" | "mp3"
    quality: int | None = None     # None = melhor disponível; senão tier (ex.: 1080)
    mp3_bitrate: int = 320
    time_range: TimeRange | None = None
    dest_dir: str = ""

    @property
    def quality_label(self) -> str:
        if self.format == "mp3":
            return f"{self.mp3_bitrate} kbps"
        return "Melhor" if self.quality is None else f"{self.quality}p"


_ids = itertools.count(1)


@dataclass
class DownloadJob:
    info: VideoInfo
    options: DownloadOptions
    id: int = field(default_factory=lambda: next(_ids))
    status: JobStatus = JobStatus.QUEUED
    percent: float = 0.0
    speed: float | None = None       # bytes/s
    eta: int | None = None
    total_bytes: int | None = None
    stage: str = "Na fila"
    error: str | None = None
    output_path: str | None = None


@dataclass
class Progress:
    """Snapshot emitido pelo worker para a UI."""
    percent: float | None          # None = indeterminado
    speed: float | None = None
    eta: int | None = None
    total_bytes: int | None = None
    stage: str = ""
