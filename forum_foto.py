#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ulaşım Arşiv forumundan (forum.ulasimarsiv.com, Flarum) araç fotoğraf bağlantılarını okur.

 * Herkese açık Flarum API'sini kullanır; giriş gerekmez, fotoğraf indirilmez, yalnızca bağlantı saklanır.
 * Her fotoğrafın alt metni "MODEL - FILO | PLAKA" biçimindedir; filo kodu ve plakaya göre arac_foto tablosuna yazılır.
 * Panelde fotoğraf, yazar adı ve forumdaki gönderi bağlantısıyla gösterilir.
 * Nazik: istekler arası bekleme, kendini tanıtan User-Agent.

Kullanım:
  python3 forum_foto.py                  # Ankara
  python3 forum_foto.py --sehir istanbul
  python3 forum_foto.py --kuru           # yazmadan ne bulacağını göster
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import ego_tracker as E

BASE = "https://forum.ulasimarsiv.com"
UA = "UlasimArsiv-FiloTakip/1.0 (+http://filo.ulasimarsiv.com; kendi forumumuz, hobi)"
HERE = os.path.dirname(os.path.abspath(__file__))
SEHIR = {  # etiket (tag) slug'ı, veritabanı
    "ankara": ("ankara-sehirici", os.environ.get("EGO_DB", os.path.join(HERE, "ego_filo.db"))),
    "istanbul": ("istanbul-sehirici", os.environ.get("IETT_DB", os.path.join(HERE, "iett_filo.db"))),
    "izmir": ("izmir-sehirici", os.environ.get("IZMIR_DB", os.path.join(HERE, "izmir_filo.db"))),
}
RE_IMG = re.compile(r"<img\b[^>]*?>", re.I)
RE_SRC = re.compile(r'\bsrc="([^"]+)"', re.I)
RE_ALT = re.compile(r'\balt="([^"]*)"', re.I)
RE_ALTKOD = re.compile(r"^(.*)\s+-\s+([^|\s]+)\s*\|\s*(.+)$")


def api(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params, safe="[]")
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == 2:
                print("  ! alınamadı:", url, e, file=sys.stderr)
                return None
            time.sleep(3 * (i + 1))


def sayfala(path, params, bekle):
    off = 0
    while True:
        j = api(path, dict(params, **{"page[limit]": 50, "page[offset]": off}))
        if not j:
            return
        data = j.get("data") or []
        yield j, data
        if len(data) < 50 or not (j.get("links") or {}).get("next"):
            return
        off += 50
        time.sleep(bekle)


def fotolar(html_text):
    """Gönderi HTML'inden (görsel_url, model, filo, plaka) kayıtlarını çıkarır."""
    out = []
    for tag in RE_IMG.findall(html_text or ""):
        s, a = RE_SRC.search(tag), RE_ALT.search(tag)
        if not (s and a):
            continue
        m = RE_ALTKOD.match(a.group(1).replace("&#039;", "'").replace("&amp;", "&").strip())
        if not m:
            continue
        out.append((s.group(1).replace("&amp;", "&"), m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return out


def dene(fn, deneme=12, bekle=10):
    """Toplayıcı veritabanını kilitliyken kısa aralıklarla yeniden dener."""
    import sqlite3
    for i in range(deneme):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if ("locked" not in str(e) and "busy" not in str(e)) or i == deneme - 1:
                raise
            time.sleep(bekle)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sehir", default="ankara", choices=sorted(SEHIR))
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--bekle", type=float, default=1.0)
    a = ap.parse_args()
    tag, dbpath = SEHIR[a.sehir]
    conn = dene(lambda: E.connect(dbpath))
    conn.execute("PRAGMA busy_timeout=60000")
    dene(lambda: conn.execute("CREATE TABLE IF NOT EXISTS arac_foto (anahtar TEXT PRIMARY KEY, img TEXT, post TEXT, yazar TEXT, ts INTEGER)"))
    toplam = foto = 0
    for _, tartismalar in sayfala("/api/discussions", {"filter[tag]": tag, "sort": "-lastPostedAt"}, a.bekle):
        for d in tartismalar:
            did, slug = d["id"], d["attributes"].get("slug") or d["id"]
            for j, posts in sayfala("/api/posts", {"filter[discussion]": did, "include": "user", "sort": "number"}, a.bekle):
                users = {x["id"]: x["attributes"].get("displayName", "") for x in j.get("included", []) if x["type"] == "users"}
                for p in posts:
                    uid = ((p.get("relationships") or {}).get("user") or {}).get("data") or {}
                    yazar = users.get(uid.get("id"), "")
                    url = "%s/d/%s/%s" % (BASE, slug, p["attributes"].get("number", 1))
                    for img, model, filo, plaka in fotolar(p["attributes"].get("contentHtml")):
                        toplam += 1
                        for anahtar in (E.norm(filo), E.norm(plaka)):
                            if anahtar and not a.kuru:
                                dene(lambda: conn.execute("INSERT OR REPLACE INTO arac_foto (anahtar, img, post, yazar, ts) VALUES (?,?,?,?,?)",
                                                          (anahtar, img[:400], url[:300], yazar[:60], E.now_ts())))
                                foto += 1
                        if a.kuru:
                            print("  %s | %s | %s | %s | %s" % (model, filo, plaka, yazar, img))
                time.sleep(a.bekle)
    dene(conn.commit)
    print("Bitti: %d fotoğraf bulundu, %d anahtar yazıldı%s." % (toplam, foto, " (kuru)" if a.kuru else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
