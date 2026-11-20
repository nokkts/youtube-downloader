import functools
import http.server
import re
import socketserver
import subprocess
import threading
from pathlib import Path

import pytest
from yt_dlp.extractor.common import InfoExtractor

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
FF = "ffmpeg"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    from app.ui import styles
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(styles.stylesheet())
    return app


def _gen(path: Path, *args: str) -> None:
    subprocess.run([FF, "-y", "-v", "error", *args, str(path)], check=True)


@pytest.fixture(scope="session")
def media_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("srv")
    _gen(root / "v360.mp4", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=10:duration=60", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart")
    _gen(root / "v240.mp4", "-f", "lavfi", "-i", "testsrc2=size=426x240:rate=10:duration=60", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart")
    _gen(root / "a.m4a", "-f", "lavfi", "-i", "sine=frequency=440:duration=60", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None  # type: ignore
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def install_first(ydl, ie_cls) -> None:
    """Registra o extrator falso ANTES do 'generic' (que casaria qualquer URL http)."""
    ie = ie_cls(ydl)
    ydl.add_info_extractor(ie)
    key = ie.ie_key()
    ydl._ies = {key: ydl._ies.pop(key), **ydl._ies}


def make_fake_ie(base: str):
    class FakeIE(InfoExtractor):
        IE_NAME = "nokkfake"
        _VALID_URL = r"https?://127\.0\.0\.1:\d+/fake/(?P<id>\w+)"

        def _real_extract(self, url):
            vid = self._match_id(url)
            return {
                "id": vid, "title": "Teste: vídeo/ação?", "duration": 60, "uploader": "Canal Teste",
                "formats": [
                    {"format_id": "v240", "url": f"{base}/v240.mp4", "ext": "mp4", "vcodec": "avc1.42c01e", "acodec": "none",
                     "height": 240, "width": 426, "tbr": 200, "protocol": "http", "filesize": 100_000},
                    {"format_id": "v360", "url": f"{base}/v360.mp4", "ext": "mp4", "vcodec": "avc1.4d401e", "acodec": "none",
                     "height": 360, "width": 640, "tbr": 400, "protocol": "http", "filesize": 200_000},
                    {"format_id": "a128", "url": f"{base}/a.m4a", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2",
                     "abr": 128, "protocol": "http", "filesize": 50_000},
                ],
            }

    return FakeIE


@pytest.fixture()
def patched_ydl(media_server, monkeypatch):
    """Faz o downloader usar o extrator falso (mesmo yt-dlp real, mesma rede local)."""
    import app.core.downloader as dl
    from yt_dlp import YoutubeDL

    fake = make_fake_ie(media_server)

    class Patched(YoutubeDL):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            install_first(self, fake)

    import app.core.youtube as yt
    monkeypatch.setattr(dl, "YoutubeDL", Patched)
    monkeypatch.setattr(yt, "YoutubeDL", Patched)
    return media_server


def probe(path: str) -> dict:
    import json
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)
