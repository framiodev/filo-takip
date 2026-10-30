#!/data/data/com.termux/files/usr/bin/sh
# Toplayıcı + web arayüzünü arka planda başlatır.
cd "$(dirname "$0")" || exit 1

if pgrep -f "ego_tracker.py hepsi" >/dev/null 2>&1; then
  echo "Zaten çalışıyor. Arayüz: http://127.0.0.1:8080"
  exit 0
fi

# Ekran kapanınca Android'in Termux'u uyutmasını engelle (Termux bildiriminden de kapatılabilir)
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

nohup python ego_tracker.py hepsi "$@" > hepsi.log 2>&1 &
echo "Başladı. Tarayıcıdan açın: http://127.0.0.1:8080"
echo "Günlük: tail -f hepsi.log   |   Durdurmak için: sh termux_durdur.sh"
