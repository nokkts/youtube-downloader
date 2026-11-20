"""Consulta de metadados via yt-dlp e seleção de formatos (sem UI, sem Qt)."""
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterator

from yt_dlp import YoutubeDL

from app.core.models import QUALITY_TIERS, VideoInfo
from app.utils.validators import normalize_youtube_url


class _QuietLogger:
    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def detect_js_runtimes() -> dict[str, dict]:
    """Runtimes JavaScript (Deno/Node/Bun) que o yt-dlp usa para resolver o player do YouTube."""
    found: dict[str, dict] = {}
    for name in ("deno", "node", "bun"):
        path = shutil.which(name)
        if not path and name == "deno":
            exe = "deno.exe" if sys.platform.startswith("win") else "deno"
            cand = Path.home() / ".deno" / "bin" / exe
            path = str(cand) if cand.is_file() else None
        if path:
            found[name] = {"path": path}
    return found


def base_ydl_opts(ffmpeg_dir: str | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": _QuietLogger(),
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "windowsfilenames": True,
        "noprogress": True,
        "color": "never",
        # Nunca lemos cookies do navegador nem pedimos login: só conteúdo acessível publicamente.
        "cookiefile": None,
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    runtimes = detect_js_runtimes()
    if runtimes:
        opts["js_runtimes"] = runtimes
    return opts


def short_side(fmt: dict) -> int:
    """Resolução 'comercial' do formato: lado menor (Shorts verticais 1080x1920 contam como 1080p)."""
    h, w = fmt.get("height") or 0, fmt.get("width") or 0
    if h and w:
        return min(h, w)
    return h or w or 0


def _has_video(f: dict) -> bool:
    return f.get("vcodec") not in (None, "none") and short_side(f) > 0


def _has_audio(f: dict) -> bool:
    return f.get("acodec") not in (None, "none")


def available_tiers(formats: list[dict]) -> list[int]:
    """Qualidades do menu (2160…360) realmente oferecidas pelo vídeo, da maior para a menor.

    Um tier só aparece se existir um formato com aquela resolução (tolerância de 8%:
    vídeos 21:9 ou 'quase 1080' como 1920x800 ainda contam como 1080p pela largura).
    """
    sides = {short_side(f) for f in formats if _has_video(f)}
    tiers = []
    for tier in QUALITY_TIERS:
        if any(abs(s - tier) <= tier * 0.08 or (s == tier) for s in sides):
            tiers.append(tier)
    return tiers


def _tier_ceiling(tier: int) -> int:
    return int(tier * 1.08)


# --------------------------------------------------------------------------- seleção
def _vcodec_rank(f: dict) -> int:
    codec = (f.get("vcodec") or "").lower()
    if codec.startswith(("avc1", "h264")):
        return 3          # compatível com qualquer player do Windows
    if codec.startswith("vp09") or codec.startswith("vp9"):
        return 2
    if codec.startswith("av01"):
        return 1
    return 0


def _acodec_rank(f: dict) -> int:
    codec = (f.get("acodec") or "").lower()
    return 1 if codec.startswith(("mp4a", "aac")) else 0


def pick_video(formats: list[dict], max_side: int | None) -> dict | None:
    pool = [f for f in formats if _has_video(f) and not _has_audio(f)]
    if max_side:
        pool = [f for f in pool if short_side(f) <= _tier_ceiling(max_side)]
    if not pool:
        return None
    # resolução > codec compatível > bitrate
    return max(pool, key=lambda f: (short_side(f), _vcodec_rank(f), f.get("fps") or 0, f.get("tbr") or 0))


def pick_audio(formats: list[dict], prefer_aac: bool) -> dict | None:
    pool = [f for f in formats if _has_audio(f) and not _has_video(f)]
    if not pool:
        return None
    key_aac = lambda f: (_acodec_rank(f), f.get("abr") or f.get("tbr") or 0)  # noqa: E731
    key_best = lambda f: (f.get("abr") or f.get("tbr") or 0, _acodec_rank(f))  # noqa: E731
    return max(pool, key=key_aac if prefer_aac else key_best)


def pick_progressive(formats: list[dict], max_side: int | None) -> dict | None:
    pool = [f for f in formats if _has_video(f) and _has_audio(f)]
    if max_side:
        pool = [f for f in pool if short_side(f) <= _tier_ceiling(max_side)]
    if not pool:
        return None
    return max(pool, key=lambda f: (short_side(f), _vcodec_rank(f), f.get("tbr") or 0))


def make_format_selector(fmt: str, quality: int | None) -> Callable[[dict], Iterator[dict]]:
    """Seletor de formato para o yt-dlp.

    MP4: baixa a melhor trilha de vídeo (<= qualidade) e a melhor trilha de áudio SEPARADAMENTE
         e deixa o yt-dlp/FFmpeg combiná-las em MP4. Prefere H.264 + AAC (reproduz em qualquer
         lugar); em 1440p/2160p o YouTube só oferece VP9/AV1, então esses são usados.
    MP3: melhor trilha de áudio; a conversão para MP3 é feita pelo FFmpeg depois.
    """

    def selector(ctx: dict) -> Iterator[dict]:
        formats = ctx["formats"]
        if fmt == "mp3":
            audio = pick_audio(formats, prefer_aac=False) or pick_progressive(formats, None)
            if audio is None and formats:
                audio = formats[-1]
            if audio is not None:
                yield audio
            return

        video = pick_video(formats, quality)
        audio = pick_audio(formats, prefer_aac=True)
        if video and audio:
            yield {
                "format_id": f"{video['format_id']}+{audio['format_id']}",
                "ext": "mp4",
                "requested_formats": [video, audio],
                "protocol": f"{video.get('protocol')}+{audio.get('protocol')}",
            }
            return
        prog = pick_progressive(formats, quality)
        if prog:
            yield prog
        elif formats:
            yield formats[-1]  # rede de segurança: fontes sem metadados de codec

    return selector


# --------------------------------------------------------------------------- info
def _fetch_thumbnail(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (URL vem do próprio YouTube)
            return resp.read()
    except Exception:  # noqa: BLE001 — miniatura é opcional
        return None


def _best_thumbnail_url(data: dict) -> str | None:
    thumbs = [t for t in (data.get("thumbnails") or []) if t.get("url", "").startswith("http")]
    # prefere jpg (Qt lê nativamente; webp pode não ter plugin) com largura moderada
    jpgs = [t for t in thumbs if ".jpg" in t["url"].split("?")[0]]
    pool = jpgs or thumbs
    if pool:
        pool = sorted(pool, key=lambda t: t.get("width") or t.get("preference") or 0)
        mid = [t for t in pool if (t.get("width") or 0) >= 320] or pool
        return mid[0]["url"] if jpgs else mid[-1]["url"]
    return data.get("thumbnail")


def fetch_video_info(raw_url: str, ffmpeg_dir: str | None = None, with_thumbnail: bool = True) -> VideoInfo:
    url = normalize_youtube_url(raw_url) or raw_url
    with YoutubeDL(base_ydl_opts(ffmpeg_dir)) as ydl:
        data = ydl.extract_info(url, download=False)
    if data is None:
        raise ValueError("unavailable")
    if data.get("_type") == "playlist" and data.get("entries"):
        data = next(e for e in data["entries"] if e)
    formats = data.get("formats") or []
    tiers = available_tiers(formats)
    thumb_url = _best_thumbnail_url(data)
    return VideoInfo(
        video_id=data.get("id", ""),
        url=data.get("webpage_url") or url,
        title=data.get("title") or "Sem título",
        channel=data.get("channel") or data.get("uploader") or "Canal desconhecido",
        duration=float(data["duration"]) if data.get("duration") else None,
        thumbnail_url=thumb_url,
        thumbnail_bytes=_fetch_thumbnail(thumb_url) if with_thumbnail else None,
        available_heights=tiers,
        max_height=max((short_side(f) for f in formats if _has_video(f)), default=0),
        is_live=bool(data.get("is_live")),
        has_audio=any(_has_audio(f) for f in formats),
        formats=formats,
    )
