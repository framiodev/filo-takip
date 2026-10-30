@echo off
chcp 65001 >nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*ego_tracker.py*hepsi*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Toplayici durduruldu.
pause
