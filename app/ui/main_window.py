"""Janela principal."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QBoxLayout, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QScrollArea,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from app.core.errors import friendly_message
from app.core.ffmpeg import INSTALL_HELP, FFmpegInfo, find_ffmpeg
from app.core.models import DownloadJob, DownloadOptions, VideoInfo
from app.ui import icons, styles
from app.ui.components.common import fade_in, make_button, repolish
from app.ui.components.downloads_panel import DownloadsPanel
from app.ui.components.folder_card import FolderCard
from app.ui.components.options_card import OptionsCard
from app.ui.components.trim_card import TrimCard
from app.ui.components.url_bar import UrlBar
from app.ui.components.video_card import VideoCard
from app.utils.settings import SettingsStore
from app.utils.system import open_folder
from app.utils.validators import RangeError, normalize_youtube_url
from app.workers.info_worker import InfoWorker
from app.workers.manager import DownloadManager

NARROW_WIDTH = 980


class Toast(QLabel):
    """Aviso flutuante discreto, no rodapé."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background:{styles.CARD_HI}; border:1px solid {styles.BORDER}; border-radius:10px; "
                           f"padding:10px 16px; color:{styles.TEXT};")
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ms: int = 3200) -> None:
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        fade_in(self, 180)
        self._timer.start(ms)

    def reposition(self) -> None:
        p = self.parentWidget()
        self.move(QPoint((p.width() - self.width()) // 2, p.height() - self.height() - 24))


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, ffmpeg: FFmpegInfo | None = None, *, use_tray: bool = True) -> None:
        super().__init__()
        self.store = store
        self.settings = store.data
        self.ffmpeg = ffmpeg
        self.info: VideoInfo | None = None
        self._info_worker: InfoWorker | None = None

        self.setWindowTitle("Nokk")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(520, 560)
        self.resize(self.settings.window_width, self.settings.window_height)

        self.manager = DownloadManager(ffmpeg, max_concurrent=1, parent=self)
        self._build_ui()
        self._wire()
        self.tray: QSystemTrayIcon | None = None
        if use_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icons.app_icon(), self)
            self.tray.setToolTip("Nokk")
            self.tray.show()
        self._refresh_actions()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 14)
        outer.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(34, 34))
        title = QLabel("Nokk")
        title.setObjectName("h1")
        sub = QLabel("Baixe vídeos, escolha a qualidade e recorte só o trecho que importa.")
        sub.setObjectName("muted")
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(title)
        tcol.addWidget(sub)
        header.addWidget(logo)
        header.addSpacing(8)
        header.addLayout(tcol)
        header.addStretch(1)
        outer.addLayout(header)

        self.banner = self._make_banner()
        outer.addWidget(self.banner)

        self.url_bar = UrlBar()
        outer.addWidget(self.url_bar)

        self.body = QBoxLayout(QBoxLayout.LeftToRight)
        self.body.setSpacing(16)
        outer.addLayout(self.body, 1)

        # coluna esquerda (rolável): preview + configurações
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.setSpacing(14)
        self.video_card = VideoCard()
        self.video_card.hide()
        self.options = OptionsCard()
        self.trim = TrimCard()
        self.folder = FolderCard(self.settings.download_dir, self.settings.open_folder_after)
        self.download_btn = make_button("Baixar", "download", "primary big")
        self.download_btn.setMinimumHeight(48)
        self.hint = QLabel("")
        self.hint.setObjectName("small")
        self.hint.setWordWrap(True)
        for w in (self.video_card, self.options, self.trim, self.folder):
            ll.addWidget(w)
        ll.addStretch(1)
        self.left_scroll.setWidget(left)

        # o botão principal fica fixo, fora da rolagem, sempre visível
        self.left_col = QWidget()
        lc = QVBoxLayout(self.left_col)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.setSpacing(8)
        lc.addWidget(self.left_scroll, 1)
        lc.addWidget(self.hint)
        lc.addWidget(self.download_btn)

        self.panel = DownloadsPanel()
        self.body.addWidget(self.left_col, 5)
        self.body.addWidget(self.panel, 6)

        self.options.set_format(self.settings.format)
        self.options.set_bitrate(self.settings.mp3_bitrate)
        self.toast = Toast(root)
        self._apply_layout_mode()

    def _make_banner(self) -> QFrame:
        b = QFrame()
        b.setObjectName("banner")
        lay = QHBoxLayout(b)
        lay.setContentsMargins(14, 10, 10, 10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("alert", styles.WARN, 20))
        self.banner_text = QLabel("FFmpeg não encontrado. Ele é necessário para combinar vídeo/áudio, recortar e gerar MP3.")
        self.banner_text.setWordWrap(True)
        how = make_button("Como instalar", None, "")
        again = make_button("Verificar novamente", None, "")
        lay.addWidget(ic)
        lay.addWidget(self.banner_text, 1)
        lay.addWidget(how)
        lay.addWidget(again)
        how.clicked.connect(lambda: QMessageBox.information(self, "Instalar o FFmpeg", INSTALL_HELP))
        again.clicked.connect(self._recheck_ffmpeg)
        b.setVisible(self.ffmpeg is None)
        return b

    def _wire(self) -> None:
        self.url_bar.analyze.connect(self.start_analysis)
        self.url_bar.cleared.connect(self.reset_video)
        self.options.changed.connect(self._refresh_actions)
        self.trim.changed.connect(self._refresh_actions)
        self.folder.changed.connect(self._persist)
        self.download_btn.clicked.connect(self.enqueue_download)
        self.panel.cancel_requested.connect(self.manager.cancel)
        self.panel.remove_requested.connect(self.manager.remove)
        self.panel.clear_requested.connect(self.manager.clear_finished)
        self.manager.job_added.connect(self.panel.add_job)
        self.manager.job_changed.connect(self.panel.update_job)
        self.manager.job_removed.connect(self.panel.remove_job)
        self.manager.job_finished.connect(self._on_finished)
        self.manager.job_changed.connect(self._on_job_changed)

    # ------------------------------------------------------------------ responsivo
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_layout_mode()
        self.toast.reposition()

    def _apply_layout_mode(self) -> None:
        narrow = self.width() < NARROW_WIDTH
        want = QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
        if self.body.direction() != want:
            self.body.setDirection(want)
        if narrow:
            self.left_col.setMaximumWidth(16777215)
            self.left_col.setMinimumWidth(0)
            self.left_col.setMinimumHeight(300)
            self.body.setStretch(0, 3)
            self.body.setStretch(1, 2)
        else:
            self.left_col.setMinimumHeight(0)
            self.left_col.setMinimumWidth(430)
            self.left_col.setMaximumWidth(560)
            self.body.setStretch(0, 5)
            self.body.setStretch(1, 6)

    # ------------------------------------------------------------------ análise
    def start_analysis(self, raw: str) -> None:
        if not raw:
            self.url_bar.set_status("Cole o link de um vídeo do YouTube para começar.")
            return
        url = normalize_youtube_url(raw)
        if not url:
            self.url_bar.set_status("Link inválido. Cole o endereço de um vídeo ou Short do YouTube "
                                    "(youtube.com/watch?v=…, youtu.be/… ou youtube.com/shorts/…).")
            return
        self.url_bar.set_status("")
        self.url_bar.set_busy(True)
        self._info_worker = InfoWorker(url, self.ffmpeg.location if self.ffmpeg else None, self)
        self._info_worker.succeeded.connect(self._on_info)
        self._info_worker.failed.connect(self._on_info_failed)
        self._info_worker.finished.connect(self._on_info_thread_finished)
        self._info_worker.start()

    def _on_info_thread_finished(self) -> None:
        worker, self._info_worker = self._info_worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_info(self, info: VideoInfo) -> None:
        self.url_bar.set_busy(False)
        self.info = info
        self.video_card.set_info(info)
        if not self.video_card.isVisible():
            self.video_card.show()
        fade_in(self.video_card)
        self.options.set_info(info)
        self.trim.set_duration(info.duration)
        self._refresh_actions()

    def _on_info_failed(self, message: str) -> None:
        self.url_bar.set_busy(False)
        self.url_bar.set_status(message)

    def reset_video(self) -> None:
        self.info = None
        self.video_card.hide()
        self.options.set_info(None)
        self.trim.reset()
        self._refresh_actions()

    # ------------------------------------------------------------------ download
    def _refresh_actions(self) -> None:
        reason = ""
        if self.info is None:
            reason = "Analise um vídeo para habilitar o download."
        elif self.ffmpeg is None:
            reason = "Instale o FFmpeg para baixar."
        elif not self.trim.is_valid():
            reason = "Corrija a minutagem do recorte."
        self.download_btn.setEnabled(not reason)
        self.hint.setText(reason)
        self.hint.setVisible(bool(reason))
        if self.info and not reason:
            fmt = self.options.format_value().upper()
            self.download_btn.setText(f"Baixar {fmt}" + (" (trecho)" if self.trim.get_range() else ""))
        else:
            self.download_btn.setText("Baixar")

    def enqueue_download(self) -> None:
        if not self.info:
            return
        if self.ffmpeg is None:
            QMessageBox.warning(self, "FFmpeg não encontrado", INSTALL_HELP)
            return
        try:
            rng = self.trim.get_range()
        except RangeError as exc:
            self.toast.show_message(str(exc))
            return
        opts = DownloadOptions(
            format=self.options.format_value(),
            quality=self.options.quality_value() if self.options.format_value() == "mp4" else None,
            mp3_bitrate=self.options.bitrate_value(),
            time_range=rng,
            dest_dir=self.folder.folder,
        )
        self._persist()
        self.manager.add(DownloadJob(self.info, opts))
        self.toast.show_message("Adicionado à fila de downloads")

    def _on_job_changed(self, _job: DownloadJob) -> None:
        pass

    def _on_finished(self, job: DownloadJob) -> None:
        name = job.output_path.replace("\\", "/").rsplit("/", 1)[-1] if job.output_path else job.info.title
        self.toast.show_message(f"✓ Download concluído: {name}", 5000)
        if self.settings.notify_on_finish and self.tray:
            self.tray.showMessage("Download concluído", name, icons.app_icon(), 6000)
        if self.folder.open_after.isChecked() and not self.manager.has_active():
            open_folder(job.options.dest_dir)

    def _recheck_ffmpeg(self) -> None:
        self.ffmpeg = find_ffmpeg()
        self.manager.ffmpeg = self.ffmpeg
        self.banner.setVisible(self.ffmpeg is None)
        self._refresh_actions()
        self.toast.show_message("FFmpeg encontrado!" if self.ffmpeg else "FFmpeg ainda não encontrado.")

    # ------------------------------------------------------------------ persistência / saída
    def _persist(self) -> None:
        s = self.settings
        s.download_dir = self.folder.folder
        s.open_folder_after = self.folder.open_after.isChecked()
        s.format = self.options.format_value()
        s.mp3_bitrate = self.options.bitrate_value()
        s.window_width, s.window_height = self.width(), self.height()
        self.store.save()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.manager.has_active():
            box = QMessageBox(self)
            box.setWindowTitle("Downloads em andamento")
            box.setText("Há downloads em andamento. Sair agora cancela todos e descarta os arquivos parciais.")
            quit_btn = box.addButton("Sair e cancelar", QMessageBox.DestructiveRole)
            box.addButton("Continuar baixando", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not quit_btn:
                event.ignore()
                return
        self._persist()
        self.manager.shutdown()
        if self._info_worker and self._info_worker.isRunning():
            self._info_worker.wait(3000)
        event.accept()
