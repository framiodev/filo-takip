#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BusPhoto (busphoto.eu) İzmir araç listelerinden yalnızca METİN verisini toplar:
kapı/filo numarası, plaka, marka-model, garaj/işletmeci, yapım yılı, not.

 * Fotoğraf indirmez. Yalnızca "Vehicles List" tablolarındaki satırları okar.
 * Siteye nazik davranır: tek bağlantı, istekler arası bekleme (varsayılan 4 sn), tanıtıcı User-Agent.
 * Veri BusPhoto yazarlarının emeğidir; kullanırken kaynak olarak "BusPhoto" yazılır. Ticari kullanım yoktur.
   Kalıcı/yoğun kullanım öncesi site yönetimine ("Feedback" bölümü) bilgi verilmesi önerilir.

Kullanım:
  python3 busphoto_izmir.py                 # izmir_busphoto.csv dosyasına yazar (veritabanına dokunmaz)
  python3 busphoto_izmir.py --db            # ayrıca İzmir veritabanındaki arac_bilgi tablosuna yazar
  python3 busphoto_izmir.py --model 3506    # yalnız tek model (BusPhoto mid) dene
  python3 busphoto_izmir.py --kuru          # en fazla 2 model, kaydetmeden göster
"""
import argparse
import csv
import html as htmllib
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

BASE = "https://busphoto.eu/"
CID = 3268  # İzmir
UA = "UlasimArsiv-FiloTakip/1.0 (+http://filo.ulasimarsiv.com; hobi, ticari degil; yalniz metin)"
HERE = os.path.dirname(os.path.abspath(__file__))
RE_FILO = re.compile(r"^\d{2}-\d{2,4}$")
RE_PLAKA = re.compile(r"^\d{2}\s?[A-ZÇĞİÖŞÜ]{1,3}\s?\d{1,4}$")
RE_TARIH = re.compile(r"^(\d{2}\.)?\d{2}\.\d{4}$")


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print("  istek hatası (%s): %s" % (i + 1, e), file=sys.stderr)
            time.sleep(5 * (i + 1))
    return ""


class Tablo(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self.title = [], None, None, ""
        self._intitle = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "title":
            self._intitle = True

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", htmllib.unescape("".join(self._cell))).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "title":
            self._intitle = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        if self._intitle:
            self.title += data


def satirlari_coz(rows):
    """Tablo satırlarından (filo, plaka, ser, yil, garaj, not) çıkarır."""
    out = []
    for c in rows:
        plaka = next((x for x in c if RE_PLAKA.match(x)), "")
        filo = next((x for x in c if RE_FILO.match(x)), "")
        if not plaka and not filo:
            continue
        yil = next((x for x in c if re.fullmatch(r"(19|20)\d{2}", x)), "")
        metin = [x for x in c if x and not RE_PLAKA.match(x) and not RE_FILO.match(x) and not RE_TARIH.match(x)
                 and not re.fullmatch(r"\d+", x) and not re.fullmatch(r"(19|20)\d{2}", x)]
        garaj = metin[0] if metin else ""
        notu = metin[1] if len(metin) > 1 else ""
        out.append((filo, re.sub(r"\s+", " ", plaka).strip(), yil, garaj, notu))
    return out


def model_adi(title):
    # "İzmir, Mercedes-Benz Conecto II G — Vehicles List — BUSPHOTO"
    t = re.sub(r"\s*[—-]\s*Vehicles List.*$", "", title.strip())
    return re.sub(r"^[^,]+,\s*", "", t).strip()


def model_listesi():
    t = fetch("%sshow.php?cid=%d&lang=en" % (BASE, CID))
    mids = []
    for m in re.finditer(r"list\.php\?[^\"']*?mid=(\d+)", t):
        if m.group(1) not in mids:
            mids.append(m.group(1))
    return mids


def model_cek(mid, bekle):
    sonuc, gorulen, st, model = [], set(), 0, ""
    while True:
        url = "%slist.php?cid=%d&mid=%s&lang=en" % (BASE, CID, mid) + ("&st=%d" % st if st else "")
        p = Tablo()
        p.feed(fetch(url))
        model = model or model_adi(p.title)
        rows = satirlari_coz(p.rows)
        yeni = [r for r in rows if (r[0], r[1]) not in gorulen]
        if not yeni:
            break
        for r in yeni:
            gorulen.add((r[0], r[1]))
            sonuc.append(r)
        st += len(rows) if rows else 0
        time.sleep(bekle)
        if st > 5000:
            break
    return model, sonuc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", action="store_true", help="İzmir veritabanındaki arac_bilgi tablosuna da yaz")
    ap.add_argument("--model", default="", help="yalnız bu BusPhoto model numarası")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--bekle", type=float, default=4.0)
    ap.add_argument("--cikti", default=os.path.join(HERE, "izmir_busphoto.csv"))
    a = ap.parse_args()
    mids = [a.model] if a.model else model_listesi()
    if a.kuru:
        mids = mids[:2]
    print("%d model taranacak" % len(mids), flush=True)
    tum = []
    for i, mid in enumerate(mids, 1):
        model, rows = model_cek(mid, a.bekle)
        print("[%d/%d] mid=%s %s: %d araç" % (i, len(mids), mid, model, len(rows)), flush=True)
        for filo, plaka, yil, garaj, notu in rows:
            tum.append((filo, plaka, model, garaj, yil, notu))
        time.sleep(a.bekle)
    if a.kuru:
        for r in tum[:15]:
            print(r)
        return 0
    with open(a.cikti, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["filo", "plaka", "model", "garaj", "yil", "not"])
        w.writerows(tum)
    print("Yazıldı: %s (%d satır)" % (a.cikti, len(tum)))
    if a.db:
        import ego_tracker as E
        conn = E.connect(os.environ.get("IZMIR_DB", os.path.join(HERE, "izmir_filo.db")))
        conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                     "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)")
        n = 0
        for filo, plaka, model, garaj, yil, notu in tum:
            for k in (filo, plaka):
                if not k:
                    continue
                mevcut = conn.execute("SELECT kaynak FROM arac_bilgi WHERE anahtar=?", (E.norm(k),)).fetchone()
                if mevcut and not str(mevcut[0] or "").startswith("BusPhoto"):
                    continue  # elle girilene dokunma
                conn.execute("INSERT OR REPLACE INTO arac_bilgi (anahtar, marka_model, kaynak, url, durum, ts) VALUES (?,?,?,?,?,?)",
                             (E.norm(k), model, "BusPhoto · " + (garaj or "garaj ?"), BASE, "kesin", int(time.time())))
                n += 1
        conn.commit()
        print("arac_bilgi: %d anahtar yazıldı" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
