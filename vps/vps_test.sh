#!/usr/bin/env bash
# Satın almadan hemen sonra (kurulumdan önce) çalıştır: sunucunun Türkiye IP'si olup olmadığını ve servislere erişimi sınar.
echo "IP bilgisi:"; curl -s -m 10 https://ipinfo.io/country; echo
for u in \
 "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp?FNC=Otobus&VER=3.1.0&LAN=tr&HAT=590&DURAK=" \
 "https://forum.ulasimplatformu.com/forumdisplay.php?fid=48" \
 "https://api.ibb.gov.tr/iett/FiloDurum/SeferGerceklesme.asmx?wsdl" \
 "https://openapi.izmir.bel.tr/api/iztek/hatotobuskonumlari/10"; do
  printf '%s -> ' "${u%%\?*}"; curl -s -m 20 -o /dev/null -w '%{http_code} (%{time_total}s)\n' "$u" || echo "ZAMAN AŞIMI"
done
