#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modeli bilinmeyen araçları sayar, nedenini gösterir ve (isteğe bağlı) güvenle çözülebilenleri toplu yazar.

  python3 bilinmeyen.py              # rapor: kaç araç bilinmiyor, hangi serilerde, örnekler
  python3 bilinmeyen.py --coz        # seri çıkarımı: bir seride bilinen araçların tamamı aynı modelse, bilinmeyenlere
                                     # "tahmini" olarak yaz (sitede "~" ile görünür, elle girilene dokunmaz)
  python3 bilinmeyen.py --coz --kuru # yazmadan ne yapacağını göster
  python3 bilinmeyen.py --csv        # kalanları 'kod;;' biçiminde yaz (Modeller sayfasındaki Toplu ekle için)

Şehir: ortam değişkeni (ego_tracker'daki veritabanı seçimiyle aynı). Ankara için ek ayar gerekmez.
Eşik: bir serinin (filo kodunun '-' öncesi) çıkarımı için en az --en-az bilinen araç ve %100 uyum (varsayılan 5).
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict

import ego_tracker as E

HERE = os.path.dirname(os.path.abspath(__file__))
KAYNAK = "Seri çıkarımı (otomatik)"


def csv_kurallar():
    kur = []
    p = os.path.join(HERE, "modeller.csv")
    try:
        with open(p, encoding="utf-8-sig") as f:
            for s in f:
                s = s.strip()
                if not s or s.startswith("#") or s.lower().startswith("onek;"):
                    continue
                a = [x.strip() for x in s.split(";")]
                if len(a) >= 2 and a[0]:
                    kur.append((a[0].upper(), a[1]))
    except OSError:
        pass
    return kur


def csv_model(kod, kur):
    kod = (kod or "").strip().upper()
    en, m = -1, ""
    for onek, model in kur:
        if kod.startswith(onek) and len(onek) > en:
            en, m = len(onek), model
    return m


def seri(kod):
    m = re.match(r"^(\d{2})-\d+", kod or "")
    return m.group(1) if m else ""


def yukle(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                 "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)")
    db = {r[0]: (r[1], r[2] or "") for r in conn.execute("SELECT anahtar, marka_model, kaynak FROM arac_bilgi")}
    gorulen = conn.execute("SELECT MAX(arac_no), plaka FROM stints WHERE arac_no<>'' GROUP BY plaka").fetchall()
    return db, gorulen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coz", action="store_true")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--en-az", type=int, default=5, dest="en_az")
    a = ap.parse_args()
    kur = csv_kurallar()
    conn = E.connect()
    try:
        db, gorulen = yukle(conn)
        bilinen, bilinmeyen = [], []
        for kod, plaka in gorulen:
            k1, k2 = E.norm(kod), E.norm(plaka)
            m = (db.get(k1) or db.get(k2) or ("", ""))[0] or csv_model(kod, kur)
            (bilinen if m else bilinmeyen).append((kod, plaka, m))
        print("Toplam araç: %d  |  modeli bilinen: %d  |  bilinmeyen: %d" % (len(gorulen), len(bilinen), len(bilinmeyen)))

        ser_bil = defaultdict(Counter)
        for kod, _, m in bilinen:
            s = seri(kod)
            if s:
                ser_bil[s][m] += 1
        ser_bilinmez = defaultdict(list)
        kodsuz = []
        for kod, plaka, _ in bilinmeyen:
            s = seri(kod)
            (ser_bilinmez[s] if s else kodsuz).append((kod, plaka))

        print("\nFilo kodlu ama modeli bilinmeyen seriler:")
        cikarim = {}
        for s in sorted(ser_bilinmez, key=lambda x: -len(ser_bilinmez[x])):
            say = ser_bil.get(s, Counter())
            toplam = sum(say.values())
            durum = "bilinen yok"
            if toplam:
                (m1, n1), = say.most_common(1)
                oran = n1 / toplam
                if toplam >= a.en_az and len(say) == 1:
                    cikarim[s] = m1
                    durum = "çıkarım yapılabilir -> %s (%d araç %%100 aynı)" % (m1, toplam)
                else:
                    durum = "karışık/az örnek: " + ", ".join("%s=%d" % (m[:28], n) for m, n in say.most_common(3))
            print("  %s- : %3d bilinmeyen | %s" % (s, len(ser_bilinmez[s]), durum))
            print("        örnek: " + ", ".join(k for k, _ in ser_bilinmez[s][:5]))
        print("\nFilo kodu olmayan (yalnız plaka) bilinmeyen: %d" % len(kodsuz))
        if kodsuz:
            pre = Counter(" ".join(p.split()[:2]) for _, p in kodsuz)
            print("  plaka ön ekleri: " + ", ".join("%s=%d" % x for x in pre.most_common(8)))

        if a.coz:
            sim = int(time.time())
            yaz = 0
            for kod, plaka, _ in bilinmeyen:
                s = seri(kod)
                if s in cikarim:
                    yaz += 1
                    if not a.kuru:
                        conn.execute("INSERT OR IGNORE INTO arac_bilgi (anahtar, marka_model, kaynak, url, durum, ts) VALUES (?,?,?,?,?,?)",
                                     (E.norm(kod), cikarim[s], KAYNAK, "", "tahmini", sim))
            if not a.kuru:
                conn.commit()
            print("\n%s: %d araç %s." % ("KURU ÇALIŞMA" if a.kuru else "Yazıldı", yaz, "yazılacaktı" if a.kuru else "(tahmini olarak)"))
            print("Kalan bilinmeyen: %d" % (len(bilinmeyen) - yaz))
        if a.csv:
            print("\n# kod;marka model;durum;kaynak")
            for s in sorted(ser_bilinmez):
                if s in cikarim and a.coz:
                    continue
                for kod, _ in ser_bilinmez[s]:
                    print("%s;;;" % kod)
            for kod, plaka in kodsuz:
                print("%s;;;" % (plaka or kod))
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
