#!/data/data/com.termux/files/usr/bin/sh
pkill -f "ego_tracker.py hepsi" && echo "Durduruldu." || echo "Çalışan toplayıcı yok."
command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
