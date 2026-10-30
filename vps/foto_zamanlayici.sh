#!/usr/bin/env bash
# Ulaşım Arşiv forum fotoğraf taramasını 12 saatte bir çalıştıran zamanlayıcıyı kurar (bir kez çalıştırmak yeter).
set -e
APP=/opt/filo-takip
cat > /etc/systemd/system/filo-foto.service <<UNIT
[Unit]
Description=Ulasim Arsiv forum fotograf taramasi
[Service]
Type=oneshot
User=filo
WorkingDirectory=$APP
Environment=LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 forum_foto.py --sehir ankara
ExecStart=-/usr/bin/python3 forum_foto.py --sehir istanbul
ExecStart=-/usr/bin/python3 forum_foto.py --sehir izmir
Nice=15
UNIT
cat > /etc/systemd/system/filo-foto.timer <<UNIT
[Unit]
Description=12 saatte bir forum fotograf taramasi
[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now filo-foto.timer
systemctl start filo-foto.service --no-block
systemctl list-timers filo-foto.timer --no-pager
