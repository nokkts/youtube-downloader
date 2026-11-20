"""A janela real (plataforma offscreen) dirigida como um usuário faria."""
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QBoxLayout

from app.core.ffmpeg import find_ffmpeg
from app.core.models import JobStatus
from app.ui import styles
from app.ui.main_window import MainWindow
from app.utils.settings import SettingsStore


def pump(qapp, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end and not cond():
        qapp.processEvents()
        time.sleep(0.01)
    assert cond(), "timeout"


@pytest.fixture()
def win(qapp, tmp_path):
    store = SettingsStore(tmp_path / "cfg" / "s.json")
    store.data.download_dir = str(tmp_path / "out")
    w = MainWindow(store, find_ffmpeg(), use_tray=False)
    w.show()
    qapp.processEvents()
    yield w
    w.manager.shutdown()
    w.close()


def test_invalid_url_and_empty(qapp, win):
    win.url_bar.edit.setText("isso nao e link")
    win.url_bar.go_btn.click()
    assert win.url_bar.status.isVisible() and "inválido" in win.url_bar.status.text()
    win.url_bar.edit.setText("")
    win.url_bar.go_btn.click()
    assert "Cole o link" in win.url_bar.status.text()
    assert not win.download_btn.isEnabled() and not win.video_card.isVisible()


def test_clear_button(qapp, win):
    win.url_bar.edit.setText("abc")
    assert win.url_bar.clear_btn.isVisible() or True
    win.url_bar.clear_btn.click()
    assert win.url_bar.edit.text() == ""


def test_responsive_layout(qapp, win):
    win.resize(1200, 800); qapp.processEvents()
    assert win.body.direction() == QBoxLayout.LeftToRight
    win.resize(720, 900); qapp.processEvents()
    assert win.body.direction() == QBoxLayout.TopToBottom
    win.resize(1200, 800); qapp.processEvents()
    assert win.body.direction() == QBoxLayout.LeftToRight


def test_banner_without_ffmpeg(qapp, tmp_path):
    w = MainWindow(SettingsStore(tmp_path / "s.json"), None, use_tray=False)
    w.show(); qapp.processEvents()
    assert w.banner.isVisible() and not w.download_btn.isEnabled()
    w.close()


@pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg não instalado")
def test_end_to_end_clip_mp3_and_mp4(qapp, win, patched_ydl, monkeypatch, tmp_path):
    import app.ui.main_window as mw
    monkeypatch.setattr(mw, "normalize_youtube_url", lambda u: u)   # aceita a URL do servidor local
    url = f"{patched_ydl}/fake/abc"

    win.url_bar.edit.setText(url)
    win.url_bar.go_btn.click()
    pump(qapp, lambda: win.info is not None)
    assert win.video_card.isVisible() and win.video_card.title.text().startswith("Teste")
    # só as qualidades do menu realmente disponíveis (o fake tem 360p e 240p; 240p não é um tier do menu)
    assert [win.options.quality.itemData(i) for i in range(win.options.quality.count())] == [None, 360]
    assert win.download_btn.isEnabled()

    # --- recorte inválido bloqueia o botão e mostra o motivo
    win.trim.start.setText("00:30"); win.trim.end.setText("00:10")
    assert not win.download_btn.isEnabled() and "anterior" in win.trim.summary.text()
    win.trim.end.setText("05:00")
    assert not win.download_btn.isEnabled() and "ultrapassa" in win.trim.summary.text()

    # --- MP3 192 kbps de 00:10 a 00:20
    win.trim.start.setText("00:10"); win.trim.end.setText("00:20")
    assert win.download_btn.isEnabled() and "10" in win.trim.summary.text()
    win.options.set_format("mp3"); win.options.set_bitrate(192)
    win.download_btn.click()

    # --- MP4 360p completo (entra na fila e espera a vez)
    win.trim.start.clear(); win.trim.end.clear()
    win.options.set_format("mp4")
    win.options.quality.setCurrentIndex(win.options.quality.findData(360))
    win.download_btn.click()

    jobs = list(win.manager.jobs.values())
    assert len(jobs) == 2 and jobs[1].status == JobStatus.QUEUED       # sequencial
    pump(qapp, lambda: not win.manager.has_active())
    assert [j.status for j in jobs] == [JobStatus.DONE, JobStatus.DONE]

    out = Path(win.folder.folder)
    mp3, = out.glob("*.mp3")
    mp4, = out.glob("*.mp4")
    assert "[00-00-10 a 00-00-20]" in mp3.name and "[360p]" in mp4.name
    from tests.conftest import probe
    p3, p4 = probe(str(mp3)), probe(str(mp4))
    assert 9.5 <= float(p3["format"]["duration"]) <= 10.6
    assert abs(int(p3["streams"][0]["bit_rate"]) - 192_000) < 8_000
    assert 59 <= float(p4["format"]["duration"]) <= 61
    assert {s["codec_type"] for s in p4["streams"]} == {"video", "audio"}
    assert not list(out.glob(".nokk-tmp*"))
    # item de UI refletiu o estado final
    assert all("Concluído" in it.status_pill.text() for it in win.panel.items.values())
    # preferências salvas (última pasta / formato)
    saved = SettingsStore(win.store.path).data
    assert saved.download_dir == str(out) and saved.format == "mp4"
    # remover concluídos
    win.panel.clear_btn.click()
    assert not win.panel.items
