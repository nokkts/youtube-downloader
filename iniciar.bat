@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python nao encontrado. Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
where ffmpeg >nul 2>nul || (echo [aviso] FFmpeg nao encontrado. Execute: winget install Gyan.FFmpeg  e abra de novo.)
start "" pythonw main.py
