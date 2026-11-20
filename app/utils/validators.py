"""Validação de URLs do YouTube e de minutagens (início/fim)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}
_PATH_PREFIXES = ("shorts", "embed", "live", "v")


def extract_video_id(text: str) -> str | None:
    """Retorna o ID de 11 caracteres de um link do YouTube, ou None se inválido.

    Aceita watch?v=, youtu.be/, /shorts/, /embed/, /live/ (e o ID puro).
    """
    text = (text or "").strip()
    if not text:
        return None
    if _VIDEO_ID.match(text):
        return text
    if "://" not in text:
        text = "https://" + text
    try:
        url = urlparse(text)
    except ValueError:
        return None
    host = (url.hostname or "").lower()
    parts = [p for p in url.path.split("/") if p]
    candidate: str | None = None
    if host in ("youtu.be", "www.youtu.be"):
        candidate = parts[0] if parts else None
    elif host in _YT_HOSTS:
        if parts and parts[0] == "watch":
            candidate = (parse_qs(url.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in _PATH_PREFIXES:
            candidate = parts[1]
    if candidate and _VIDEO_ID.match(candidate):
        return candidate
    return None


def normalize_youtube_url(text: str) -> str | None:
    """Converte qualquer link aceito em https://www.youtube.com/watch?v=ID (ignora playlists)."""
    vid = extract_video_id(text)
    return f"https://www.youtube.com/watch?v={vid}" if vid else None


# --------------------------------------------------------------------------- tempo
_PART = re.compile(r"^\d+$")
_SEC = re.compile(r"^\d+(?:[.,]\d{1,3})?$")


def parse_timecode(text: str) -> float | None:
    """'SS', 'MM:SS' ou 'HH:MM:SS[.mmm]' -> segundos. None se inválido."""
    parts = (text or "").strip().split(":")
    if not 1 <= len(parts) <= 3 or not _SEC.match(parts[-1]) or not all(_PART.match(p) for p in parts[:-1]):
        return None
    secs = float(parts[-1].replace(",", "."))
    lead = [int(p) for p in parts[:-1]]          # [] | [MM] | [HH, MM]
    if len(parts) > 1 and secs >= 60:
        return None
    if len(parts) == 3 and lead[1] >= 60:
        return None
    total = secs
    for factor, value in zip((60, 3600), reversed(lead)):
        total += value * factor
    return float(total)


def format_timecode(seconds: float, with_ms: bool = False) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    base = f"{h:02d}:{m:02d}:{s:02d}"
    return f"{base}.{ms:03d}" if with_ms and ms else base


@dataclass(frozen=True)
class TimeRange:
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


class RangeError(ValueError):
    """Erro de minutagem com mensagem pronta para exibir ao usuário."""


def validate_range(start_text: str, end_text: str, duration: float | None) -> TimeRange | None:
    """Valida o recorte. Retorna None quando ambos os campos estão vazios/zerados (vídeo completo).

    Regras: sem negativos, início < fim, nada além da duração do vídeo.
    Campo Fim vazio = até o final; campo Início vazio = desde o começo.
    """
    s_txt, e_txt = (start_text or "").strip(), (end_text or "").strip()
    if (not s_txt or parse_timecode(s_txt) == 0) and not e_txt:
        return None
    for label, txt in (("Início", s_txt), ("Fim", e_txt)):
        if txt.startswith("-"):
            raise RangeError(f"O campo {label} não pode ser negativo.")
    start = parse_timecode(s_txt) if s_txt else 0.0
    if start is None:
        raise RangeError("Início inválido. Use o formato HH:MM:SS (ex.: 00:05:30).")
    if e_txt:
        end = parse_timecode(e_txt)
        if end is None:
            raise RangeError("Fim inválido. Use o formato HH:MM:SS (ex.: 00:12:45).")
    elif duration:
        end = float(duration)
    else:
        raise RangeError("Informe o campo Fim.")
    if duration and start >= duration:
        raise RangeError(f"O início ({format_timecode(start)}) ultrapassa a duração do vídeo ({format_timecode(duration)}).")
    if duration and end > duration + 0.5:
        raise RangeError(f"O fim ({format_timecode(end)}) ultrapassa a duração do vídeo ({format_timecode(duration)}).")
    if duration:
        end = min(end, float(duration))
    if start >= end:
        raise RangeError("O início precisa ser anterior ao fim.")
    if start == 0 and duration and abs(end - duration) < 0.5:
        return None  # equivale ao vídeo completo
    return TimeRange(start, end)
