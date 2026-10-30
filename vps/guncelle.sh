#!/usr/bin/env bash
# GitHub'daki yeni sürümü çeker; değişiklik varsa servisleri yeniden başlatır. systemd zamanlayıcısı 5 dk'da bir çağırır.
set -u
APP=/opt/filo-takip
cd "$APP" || exit 1
runuser -u filo -- git fetch -q origin || exit 0
if [ "$(runuser -u filo -- git rev-parse HEAD)" != "$(runuser -u filo -- git rev-parse '@{u}')" ]; then
  runuser -u filo -- git pull -q --ff-only || exit 0
  # test geçmeden yeniden başlatma (bozuk sürüm canlıya çıkmasın)
  if runuser -u filo -- python3 test_mock.py >/tmp/filo-test.log 2>&1; then
    systemctl restart filo-web filo-toplayici
    echo "$(date '+%F %T') güncellendi: $(git rev-parse --short HEAD)" >> "$APP/guncelleme.log"
  else
    echo "$(date '+%F %T') TEST BAŞARISIZ, servisler yeniden başlatılmadı: $(git rev-parse --short HEAD)" >> "$APP/guncelleme.log"
  fi
fi
