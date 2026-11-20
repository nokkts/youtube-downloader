"""Tema escuro: paleta e folha de estilo (QSS)."""
from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets"

BG = "#111111"
CARD = "#1a1a1a"
CARD_HI = "#222222"
BORDER = "#2b2b2b"
TEXT = "#ececec"
MUTED = "#8b8b8b"
ACCENT = "#7c6cff"
ACCENT_HI = "#9387ff"
ACCENT_LO = "#5f50e0"
OK = "#3ddc97"
ERR = "#ff6b6b"
WARN = "#ffb454"

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif'


def _u(name: str) -> str:
    return (ASSETS / name).as_posix()


def stylesheet() -> str:
    return f"""
* {{ font-family: {FONT_STACK}; font-size: 13px; color: {TEXT}; outline: 0; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QToolTip {{ background: {CARD_HI}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px 8px; border-radius: 6px; }}

QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#urlbar {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#urlbar[focus="true"] {{ border: 1px solid {ACCENT}; }}
QFrame#banner {{ background: #2a1f12; border: 1px solid #5a4020; border-radius: 12px; }}
QFrame#item {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}

QLabel#h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }}
QLabel#h2 {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
QLabel#title {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#small {{ color: {MUTED}; font-size: 12px; }}
QLabel#err {{ color: {ERR}; font-size: 12px; }}
QLabel#ok {{ color: {OK}; font-size: 12px; }}
QLabel#sectionIcon {{ background: transparent; }}
QLabel#pill {{ background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 9px; padding: 2px 9px; color: {MUTED}; font-size: 11px; font-weight: 600; }}
QLabel#pill[kind="accent"] {{ background: rgba(124,108,255,0.14); border: 1px solid rgba(124,108,255,0.45); color: {ACCENT_HI}; }}
QLabel#pill[kind="ok"] {{ background: rgba(61,220,151,0.12); border: 1px solid rgba(61,220,151,0.4); color: {OK}; }}
QLabel#pill[kind="err"] {{ background: rgba(255,107,107,0.12); border: 1px solid rgba(255,107,107,0.4); color: {ERR}; }}

QLineEdit {{ background: transparent; border: none; padding: 4px 2px; selection-background-color: {ACCENT}; }}
QLineEdit#time {{ background: #141414; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 10px; font-size: 14px; }}
QLineEdit#time:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit#time[invalid="true"] {{ border: 1px solid {ERR}; }}

QPushButton {{ background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 14px; font-weight: 600; }}
QPushButton:hover {{ background: #2a2a2a; border-color: #3a3a3a; }}
QPushButton:pressed {{ background: #1f1f1f; }}
QPushButton:disabled {{ color: #5a5a5a; background: #171717; border-color: #232323; }}
QPushButton#primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; }}
QPushButton#primary:hover {{ background: {ACCENT_HI}; border-color: {ACCENT_HI}; }}
QPushButton#primary:pressed {{ background: {ACCENT_LO}; }}
QPushButton#primary:disabled {{ background: #2a2750; border-color: #2a2750; color: #6c668f; }}
QPushButton#big {{ padding: 13px 18px; font-size: 14px; border-radius: 11px; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {MUTED}; padding: 6px 8px; }}
QPushButton#ghost:hover {{ background: {CARD_HI}; color: {TEXT}; }}
QPushButton#danger:hover {{ background: rgba(255,107,107,0.14); border-color: rgba(255,107,107,0.4); color: {ERR}; }}
QPushButton#seg {{ background: transparent; border: none; border-radius: 8px; padding: 8px 14px; color: {MUTED}; }}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{ background: {ACCENT}; color: white; }}
QFrame#segbox {{ background: #141414; border: 1px solid {BORDER}; border-radius: 11px; }}

QComboBox {{ background: #141414; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 12px; min-height: 18px; }}
QComboBox:hover {{ border-color: #3c3c3c; }}
QComboBox:focus, QComboBox:on {{ border-color: {ACCENT}; }}
QComboBox:disabled {{ color: #5a5a5a; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({_u('chevron-down.svg')}); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{ background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px;
    selection-background-color: {ACCENT}; selection-color: white; outline: 0; }}
QComboBox QAbstractItemView::item {{ padding: 7px 10px; border-radius: 6px; min-height: 20px; }}

QCheckBox {{ spacing: 9px; color: {TEXT}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #444; background: #141414; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url({_u('check.svg')}); }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #444; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: none; }}
QDialog {{ background: {CARD}; }}
QMessageBox {{ background: {CARD}; }}
"""
