"""Download de um item (vídeo/áudio, completo ou recortado). Sem Qt: roda em qualquer thread."""
from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, download_range_func, sanitize_filename

from app.core import converter
from app.core.errors import DownloadCancelled, FFmpegMissing, NokkError
from app.core.ffmpeg import FFmpegInfo, INSTALL_HELP
from app.core.models import DownloadJob, Progress
from app.core.youtube import base_ydl_opts, make_format_selector, pick_video, short_side
from app.utils.validators import format_timecode

ProgressCb = Callable[[Progress], None]


class ProgressTracker:
    """Agrega os eventos do yt-dlp (vários streams + pós-processamento) em um único percentual."""

    def __init__(self, emit: ProgressCb, expected_total: int | None = None, clip_seconds: float | None = None) -> None:
        self.emit = emit
        self.expected_total = expected_total
        self.clip_seconds = clip_seconds
        self._done: dict[str, int] = {}
        self._totals: dict[str, int] = {}
        self._stream_count = 0
        self._current = ""
        self._last_pct = 0.0
        self._stage = "Baixando"

    def hook(self, d: dict) -> None:
        status, key = d.get("status"), d.get("filename") or d.get("tmpfilename") or ""
        if key and key != self._current and status == "downloading":
            if key not in self._totals and key not in self._done:
                self._stream_count += 1
            self._current = key
            self._stage = "Baixando trecho" if self.clip_seconds else (
                "Baixando vídeo" if self._stream_count == 1 else "Baixando áudio")
        done = int(d.get("downloaded_bytes") or 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if status == "finished":
            self._done[key] = int(d.get("total_bytes") or done)
            self._totals[key] = self._done[key]
            self._emit(speed=None, eta=None)
            return
        if status != "downloading":
            return
        self._done[key] = done
        if total:
            self._totals[key] = int(total)
        self._emit(speed=d.get("speed"), eta=d.get("eta"))

    def _emit(self, speed: float | None, eta: int | None) -> None:
        downloaded = sum(self._done.values())
        known_total = sum(self._totals.values())
        total = max(self.expected_total or 0, known_total) or None
        pct: float | None = None
        if total:
            pct = min(99.0, downloaded / total * 100)
            pct = max(pct, self._last_pct)           # nunca regride (mudança de estimativa)
            self._last_pct = pct
        self.emit(Progress(percent=pct, speed=speed, eta=eta, total_bytes=total, stage=self._stage))

    def post(self, d: dict) -> None:
        name = d.get("postprocessor", "")
        if d.get("status") == "started":
            stage = {"FFmpegExtractAudio": "Convertendo para MP3", "Merger": "Combinando vídeo e áudio",
                     "VideoConvertor": "Convertendo", "FFmpegVideoRemuxer": "Finalizando"}.get(name, "Processando")
            self.emit(Progress(percent=99.0, stage=stage))


def expected_size(job: DownloadJob) -> int | None:
    """Tamanho estimado (bytes) do download, quando o YouTube informa. Para recortes, proporcional ao trecho."""
    info, opts = job.info, job.options
    formats = info.formats
    if not formats:
        return None
    if opts.format == "mp3":
        from app.core.youtube import pick_audio
        chosen = [pick_audio(formats, prefer_aac=False)]
    else:
        from app.core.youtube import pick_audio
        chosen = [pick_video(formats, opts.quality), pick_audio(formats, prefer_aac=True)]
    sizes = [(c.get("filesize") or c.get("filesize_approx")) for c in chosen if c]
    if not sizes or any(s is None for s in sizes):
        return None
    total = int(sum(sizes))
    if opts.time_range and info.duration:
        total = int(total * opts.time_range.length / info.duration)
    return total


def build_basename(job: DownloadJob) -> str:
    title = sanitize_filename(job.info.title, restricted=False).strip(" .") or job.info.video_id or "video"
    title = title[:120].rstrip(" .")
    opts = job.options
    parts = [title]
    if opts.format == "mp4":
        video = pick_video(job.info.formats, opts.quality)
        height = short_side(video) if video else (opts.quality or 0)
        if height:
            parts.append(f"[{height}p]")
    if opts.time_range:
        tr = opts.time_range
        parts.append("[" + format_timecode(tr.start).replace(":", "-") + " a " + format_timecode(tr.end).replace(":", "-") + "]")
    return " ".join(parts)


def run_download(job: DownloadJob, ff: FFmpegInfo | None, emit: ProgressCb, cancel: threading.Event) -> str:
    """Executa o download e devolve o caminho final do arquivo. Lança DownloadCancelled/NokkError/DownloadError."""
    if ff is None:
        raise FFmpegMissing(INSTALL_HELP)
    opts = job.options
    dest = Path(opts.dest_dir)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise NokkError(f"Não foi possível acessar a pasta de destino: {exc}") from exc

    ext = "mp3" if opts.format == "mp3" else "mp4"
    final = converter.unique_path(dest / f"{build_basename(job)}.{ext}")
    tmp = dest / f".nokk-tmp-{job.id}"
    tmp.mkdir(exist_ok=True)

    clip = opts.time_range
    tracker = ProgressTracker(emit, expected_size(job), clip.length if clip else None)

    def hook(d: dict) -> None:
        if cancel.is_set():
            raise DownloadCancelled()
        tracker.hook(d)

    def post_hook(d: dict) -> None:
        if cancel.is_set():
            raise DownloadCancelled()
        tracker.post(d)

    ydl_opts = base_ydl_opts(ff.location)
    ydl_opts.update({
        "format": make_format_selector(opts.format, opts.quality),
        "paths": {"home": str(tmp)},
        "outtmpl": "dl.%(ext)s",
        "progress_hooks": [hook],
        "postprocessor_hooks": [post_hook],
        "overwrites": True,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
    })
    if opts.format == "mp4":
        ydl_opts["merge_output_format"] = "mp4"
    # MP3: o yt-dlp baixa só a melhor trilha de áudio; a conversão é feita abaixo com nosso FFmpeg
    # (não depende do ffprobe estar na mesma pasta e permite progresso/cancelamento).
    if clip:
        # Baixa apenas o trecho (o yt-dlp pede só essa janela ao servidor via FFmpeg).
        ydl_opts["download_ranges"] = download_range_func(None, [(clip.start, clip.end)])
        if opts.format == "mp4":
            # corte exato no frame; recodifica o trecho em H.264 de alta qualidade (CRF 17)
            ydl_opts["force_keyframes_at_cuts"] = True
            ydl_opts["downloader_args"] = {"ffmpeg_o": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                                                          "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart"]}

    try:
        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(job.info.url, download=True)
        except DownloadError as exc:
            if cancel.is_set() or "DownloadCancelled" in repr(exc.exc_info):
                raise DownloadCancelled() from exc
            if clip and _is_range_failure(exc):
                result = None
                _fallback_full_then_trim(job, ff, tmp, ydl_opts, emit, cancel)
            else:
                raise
        else:
            if cancel.is_set():
                raise DownloadCancelled()
        produced = _find_output(tmp, ext)
        if produced is None and ext == "mp3":
            source = _find_source_audio(tmp)
            if source is not None:
                produced = _convert_to_mp3(job, ff, source, tmp / "dl.mp3", emit, cancel)
        if produced is None:
            raise NokkError("O download terminou, mas o arquivo final não foi gerado. Tente novamente.")
        shutil.move(str(produced), str(final))
        emit(Progress(percent=100.0, stage="Concluído"))
        return str(final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _find_source_audio(tmp: Path) -> Path | None:
    files = [p for p in tmp.glob("dl.*") if p.is_file() and p.suffix not in (".part", ".ytdl", ".mp3")]
    return files[0] if files else None


def _convert_to_mp3(job: DownloadJob, ff: FFmpegInfo, src: Path, dst: Path, emit: ProgressCb,
                    cancel: threading.Event) -> Path:
    clip = job.options.time_range
    total = clip.length if clip else job.info.duration
    emit(Progress(percent=99.0, stage="Convertendo para MP3"))

    def prog(p: float) -> None:
        emit(Progress(percent=99.0, stage=f"Convertendo para MP3 ({p:.0f}%)"))

    converter.to_mp3(ff.ffmpeg, str(src), str(dst), job.options.mp3_bitrate, on_progress=prog, cancel=cancel,
                     total=total)
    return dst


def _find_output(tmp: Path, ext: str) -> Path | None:
    files = [p for p in tmp.glob(f"dl.{ext}") if p.is_file()]
    return files[0] if files else None


def _is_range_failure(exc: Exception) -> bool:
    low = str(exc).lower()
    return any(k in low for k in ("ffmpeg exited with code", "section", "conversion failed", "invalid data"))


def _fallback_full_then_trim(job: DownloadJob, ff: FFmpegInfo, tmp: Path, ydl_opts: dict,
                             emit: ProgressCb, cancel: threading.Event) -> None:
    """Plano B: o recorte remoto falhou -> baixa completo e recorta localmente com FFmpeg."""
    clip = job.options.time_range
    assert clip is not None
    full = dict(ydl_opts)
    for k in ("download_ranges", "force_keyframes_at_cuts", "downloader_args"):
        full.pop(k, None)
    full["outtmpl"] = "full.%(ext)s"
    full["postprocessors"] = []
    full["format"] = make_format_selector("mp3" if job.options.format == "mp3" else "mp4", job.options.quality)
    if job.options.format == "mp3":
        full["format"] = make_format_selector("mp3", None)
    tracker = ProgressTracker(emit, expected_size(job))
    full["progress_hooks"] = [lambda d: (_ for _ in ()).throw(DownloadCancelled()) if cancel.is_set() else tracker.hook(d)]
    emit(Progress(percent=None, stage="Recorte direto falhou; baixando o vídeo inteiro"))
    with YoutubeDL(full) as ydl:
        ydl.extract_info(job.info.url, download=True)
    src = next((p for p in tmp.glob("full.*") if p.is_file() and p.suffix not in (".part", ".ytdl")), None)
    if src is None:
        raise NokkError("Não foi possível baixar o vídeo para recortar.")
    dst = tmp / ("dl.mp3" if job.options.format == "mp3" else "dl.mp4")

    def prog(p: float) -> None:
        emit(Progress(percent=p, stage="Recortando com FFmpeg"))

    if job.options.format == "mp3":
        converter.to_mp3(ff.ffmpeg, str(src), str(dst), job.options.mp3_bitrate, clip.start, clip.end, prog, cancel)
    else:
        converter.trim(ff.ffmpeg, str(src), str(dst), clip.start, clip.end, on_progress=prog, cancel=cancel)
