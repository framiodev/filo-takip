#!/bin/bash
# İstanbul (İETT) toplayıcısını systemd servisi olarak kurar. Sunucuda root olarak bir kez çalıştırın:
#   cd /opt/filo-takip && bash vps/istanbul_kur.sh
set -e
APP=/opt/filo-takip
cat > /etc/systemd/system/filo-istanbul.service <<UNIT
[Unit]
Description=Istanbul (IETT) Filo Takip canli veri toplayici
After=network-online.target
[Service]
User=filo
WorkingDirectory=$APP
Environment=LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 iett_tracker.py run --interval 3 --delay 2 --workers 1
Restart=always
RestartSec=60
Nice=10
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now filo-istanbul.service
sleep 5
systemctl --no-pager status filo-istanbul.service | head -8
echo "Günlük: journalctl -u filo-istanbul -n 20 --no-pager"
