@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi. https://www.python.org/downloads/ adresinden kurun ^(kurulumda "Add python.exe to PATH" kutusunu isaretleyin^).
  pause
  exit /b 1
)
if not exist ego_filo.db (
  echo Ilk kurulum: hat-durak eslesmesi cikariliyor, 10-20 dk surebilir. Pencereyi kapatmayin.
  python ego_tracker.py init
)
start "" pythonw ego_tracker.py hepsi --ac
exit /b 0
