#!/usr/bin/env bash
# EGO Filo Takip - VPS kurulumu (Ubuntu 22.04/24.04, Debian 12). root olarak çalıştır.
#
#   bash kur.sh ALAN_ADI YONETICI_SIFRESI GITHUB_SSH_ADRESI
#   ör: bash kur.sh filo.ulasimarsiv.com Sifrem123 git@github.com:framiodev/filo-takip.git
#
# ALAN_ADI   : DNS A kaydı bu sunucunun IP'sine bakmalı (boşsa yalnız http://IP açılır; "" yaz)
# YONETICI_SIFRESI : /modeller sayfası için (kullanıcı: ali); boşsa korumasız
# GITHUB_SSH_ADRESI: özel repo; kurulum bir "deploy key" üretir, sen GitHub'a eklersin
#
# Eski veritabanı (geçmiş): /root/ego_filo.db yoluna koyarsan otomatik yüklenir.
set -euo pipefail
DOMAIN="${1:-}"; PASS="${2:-}"; REPO="${3:-}"
APP=/opt/filo-takip
HOME_FILO=/var/lib/filo

[ "$(id -u)" = 0 ] || { echo "root olarak çalıştır (sudo -i)"; exit 1; }
[ -n "$REPO" ] || { echo "3. parametre (GitHub SSH adresi) gerekli"; exit 1; }

echo "== Paketler"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 sqlite3 git curl ufw gpg debian-keyring debian-archive-keyring apt-transport-https
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

echo "== Kullanıcı ve deploy anahtarı"
id filo >/dev/null 2>&1 || useradd --system --create-home --home-dir "$HOME_FILO" --shell /usr/sbin/nologin filo
install -d -o filo -g filo -m 700 "$HOME_FILO/.ssh"
if [ ! -f "$HOME_FILO/.ssh/id_ed25519" ]; then
  runuser -u filo -- ssh-keygen -t ed25519 -N "" -C "filo-vps-deploy" -f "$HOME_FILO/.ssh/id_ed25519" >/dev/null
fi
runuser -u filo -- bash -c "ssh-keyscan -t ed25519,rsa github.com >> $HOME_FILO/.ssh/known_hosts 2>/dev/null; sort -u -o $HOME_FILO/.ssh/known_hosts $HOME_FILO/.ssh/known_hosts"

if [ ! -d "$APP/.git" ]; then
  until runuser -u filo -- git ls-remote "$REPO" >/dev/null 2>&1; do
    echo
    echo "GitHub'a erişim yok. Aşağıdaki ANAHTARI GitHub'da şuraya ekle:"
    echo "  Repo > Settings > Deploy keys > Add deploy key  (başlık: filo-vps, 'Allow write access' KAPALI)"
    echo
    cat "$HOME_FILO/.ssh/id_ed25519.pub"
    echo
    read -r -p "Ekledikten sonra Enter'a bas... " _
  done
  mkdir -p "$APP"; chown filo:filo "$APP"
  runuser -u filo -- git clone "$REPO" "$APP"
fi
mkdir -p "$APP/yedek"; chown -R filo:filo "$APP"

echo "== Geçmiş veritabanı"
if [ ! -f "$APP/ego_filo.db" ]; then
  for D in /root/ego_filo.db /root/filo-paket/ego_filo.db ./ego_filo.db; do
    if [ -f "$D" ]; then
      install -o filo -g filo -m 644 "$D" "$APP/ego_filo.db"
      for X in -wal -shm; do [ -f "$D$X" ] && install -o filo -g filo -m 644 "$D$X" "$APP/ego_filo.db$X"; done
      echo "   yüklendi: $D"; break
    fi
  done
fi
if [ ! -f "$APP/ego_filo.db" ]; then
  echo "!! Eski veritabanı bulunamadı; sıfırdan başlıyor. (/root/ego_filo.db yoluna koyup tekrar çalıştırabilirsin)"
  read -r -p "Yine de devam edilsin mi? [e/H] " A; [ "${A:-}" = e ] || exit 1
  runuser -u filo -- bash -c "cd $APP && LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8 python3 ego_tracker.py init" || echo "!! init başarısız, sonra elle çalıştır"
fi

echo "== systemd servisleri"
cat > /etc/systemd/system/filo-web.service <<UNIT
[Unit]
Description=EGO Filo Takip web arayuzu
After=network-online.target
[Service]
User=filo
WorkingDirectory=$APP
Environment=LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 ego_tracker.py serve --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/filo-toplayici.service <<UNIT
[Unit]
Description=EGO Filo Takip canli veri toplayici
After=network-online.target
[Service]
User=filo
WorkingDirectory=$APP
Environment=LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 ego_tracker.py run --interval 1 --idle-max 10
Restart=always
RestartSec=20
Nice=10
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/filo-referans.service <<UNIT
[Unit]
Description=Ulasim Platformu referans taramasi
[Service]
Type=oneshot
User=filo
WorkingDirectory=$APP
Environment=LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 referans_tara.py --yeni --max-minutes 20
Nice=15
UNIT
cat > /etc/systemd/system/filo-referans.timer <<UNIT
[Unit]
Description=Gunluk referans taramasi
[Timer]
OnCalendar=*-*-* 04:20:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT
cat > /etc/systemd/system/filo-yedek.service <<UNIT
[Unit]
Description=Veritabani yedegi
[Service]
Type=oneshot
User=filo
WorkingDirectory=$APP
ExecStart=/bin/bash -c 'sqlite3 ego_filo.db ".backup yedek/ego_filo-\$(date +%%F).db" && find yedek -name "*.db" -mtime +7 -delete'
UNIT
cat > /etc/systemd/system/filo-yedek.timer <<UNIT
[Unit]
Description=Gunluk yedek
[Timer]
OnCalendar=*-*-* 03:40:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT
cat > /etc/systemd/system/filo-guncelle.service <<UNIT
[Unit]
Description=GitHub'dan otomatik guncelleme
[Service]
Type=oneshot
ExecStart=$APP/vps/guncelle.sh
UNIT
cat > /etc/systemd/system/filo-guncelle.timer <<UNIT
[Unit]
Description=5 dakikada bir guncelleme kontrolu
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
UNIT
chmod +x "$APP/vps/"*.sh

echo "== Caddy (HTTPS + şifre)"
AUTH=""
if [ -n "$PASS" ]; then
  HASH="$(caddy hash-password --plaintext "$PASS")"
  AUTH="
  @yonetim path /modeller /modeller/* /rapor-uret
  basicauth @yonetim {
    ali $HASH
  }"
fi
cat > /etc/caddy/Caddyfile <<CADDY
${DOMAIN:-:80} {
  encode gzip$AUTH
  reverse_proxy 127.0.0.1:8000
}
CADDY
if [ -n "$DOMAIN" ]; then
  cat >> /etc/caddy/Caddyfile <<CADDY

www.$DOMAIN {
  redir https://$DOMAIN{uri} permanent
}
CADDY
fi

echo "== Güvenlik duvarı"
ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null

systemctl daemon-reload
systemctl enable --now filo-web filo-toplayici filo-referans.timer filo-yedek.timer filo-guncelle.timer
systemctl restart caddy
sleep 3
echo; echo "== Durum"
systemctl is-active filo-web filo-toplayici caddy
curl -s -o /dev/null -w "yerel arayüz: HTTP %{http_code}\n" http://127.0.0.1:8000/saglik || true
echo "Adres: ${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://SUNUCU_IP}"
echo "Günlük: journalctl -u filo-toplayici -n 30 --no-pager   |   güncelleme günlüğü: $APP/guncelleme.log"
