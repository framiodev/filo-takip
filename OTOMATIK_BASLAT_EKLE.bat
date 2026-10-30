@echo off
chcp 65001 >nul
set "T=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\EGO Filo Takip.bat"
>"%T%" echo @echo off
>>"%T%" echo cd /d "%~dp0"
>>"%T%" echo start "" pythonw ego_tracker.py hepsi
echo Bilgisayar acildiginda toplayici kendiliginden baslayacak ^(arayuz acilmaz; BASLAT.bat ile acarsiniz^).
pause
