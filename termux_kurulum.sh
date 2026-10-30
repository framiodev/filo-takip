#!/data/data/com.termux/files/usr/bin/sh
# Android tablet/telefonda (Termux) tek seferlik kurulum.
# Termux'u F-Droid'den kurun (Play Store sürümü eski ve bozuk).
set -e
pkg update -y
pkg install -y python ca-certificates
# Ortak depolama izni: raporlar Dosyalar uygulamasında "EGO-Raporlar" klasöründe görünür
termux-setup-storage || true
echo
echo "Kurulum tamam. Başlatmak için:  sh termux_baslat.sh"
