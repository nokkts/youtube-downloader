@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python nao encontrado. Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv (python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt pyinstaller
pyinstaller --noconfirm --noconsole --name NokkDownloader --collect-all yt_dlp --collect-all yt_dlp_ejs --add-data "assets;assets" main.py
where ffmpeg >nul 2>nul && (
  mkdir dist\NokkDownloader\ffmpeg 2>nul
  for /f "delims=" %%i in ('where ffmpeg') do copy /y "%%i" dist\NokkDownloader\ffmpeg\ >nul
  for /f "delims=" %%i in ('where ffprobe') do copy /y "%%i" dist\NokkDownloader\ffmpeg\ >nul
)
echo.
echo Pronto: dist\NokkDownloader\NokkDownloader.exe
pause
