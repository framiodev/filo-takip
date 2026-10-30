"""İzmir (ESHOT) toplayıcısı - İzmir Büyükşehir açık veri (CKAN) + iztek web servisleri, kimlik doğrulama yok.

Ankara/İstanbul ile aynı veritabanı şemasını kullanır (ego_tracker.SCHEMA), ayrı dosyaya yazar:
  IZMIR_DB (varsayılan: izmir_filo.db)

Kaynaklar:
  acikveri.bizizmir.com (CKAN datastore): eshot-otobus-hat-listesi, eshot-otobus-duraklari (resmi koordinat,
      DURAKTAN_GECEN_HATLAR), otobus-hareket-saatleri (TARIFE_ID, GIDIS/DONUS_SAATI)
  openapi.izmir.bel.tr/api/iztek/hatotobuskonumlari/{hatId}: OtobusId, Yon, KoorX (=enlem), KoorY (=boylam), ondalık virgüllü

Notlar:
  - Canlı serviste plaka ve hız yok; OtobusId (kapı no) kimlik olarak kullanılır.
  - Veri setlerinde durak sırası yok; bu yüzden line_route doldurulmaz (durak sırası/varış tahmini yapılmaz).
  - Hat anahtarı yalın hat numarasıdır (ör. "446"); yön bilgisi kayıtta tutulmaz.
Komutlar: probe | init | saatler | run
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("IZMIR_DB", os.path.join(HERE, "izmir_filo.db"))
CKAN = os.environ.get("IZMIR_CKAN", "https://acikveri.bizizmir.com").rstrip("/")
LIVE = os.environ.get("IZMIR_LIVE", "https://openapi.izmir.bel.tr/api/iztek").rstrip("/")
STOP = threading.Event()

import ego_tracker as E  # noqa: E402

# TARIFE_ID -> gün tipi (veri seti açıklaması sırası: hafta içi, cumartesi, pazar; canlı veriyle doğrulanacak)
TARIFE = {1: "haftaici", 2: "cumartesi", 3: "pazar"}

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS stops_geo (durak TEXT PRIMARY KEY, ad TEXT, lat REAL, lng REAL);
"""


def connect():
    conn = E.connect(DB)
    conn.executescript(EXTRA_SCHEMA)
    return conn


def get_json(http, url, timeout=60):
    try:
        raw = http.request(url, timeout=timeout, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (FiloTakip arsiv)"})
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        get_json.last_error = str(e)
        return None


get_json.last_error = ""


def resource_id(http, package):
    j = get_json(http, f"{CKAN}/api/3/action/package_show?id={package}")
    for r in ((j or {}).get("result") or {}).get("resources", []):
        if r.get("datastore_active"):
            return r["id"]
    return None


def ckan_rows(http, package, page=20000):
    rid = resource_id(http, package)
    if not rid:
        return None
    out, off = [], 0
    while True:
        j = get_json(http, f"{CKAN}/api/3/action/datastore_search?resource_id={rid}&limit={page}&offset={off}", timeout=120)
        recs = ((j or {}).get("result") or {}).get("records")
        if recs is None:
            return None if not out else out
        out += recs
        if len(recs) < page:
            return out
        off += page


def num(v):
    """'27,070275' veya 27.07 -> float; geçersiz/0 -> None."""
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if x else None


def hat_key(no):
    s = str(no).strip()
    return s[:-2] if s.endswith(".0") else s


def line_vehicles(http, hat_no):
    """Hattaki araçlar -> [{id, yon, lat, lng}] (aynı araç tekrarlıysa son geçerli konum)."""
    j = get_json(http, f"{LIVE}/hatotobuskonumlari/{urllib.parse.quote(str(hat_no))}")
    if j is None:
        return None
    seen = {}
    for r in j.get("HatOtobusKonumlari") or []:
        la, lo = num(r.get("KoorX")), num(r.get("KoorY"))
        if la is None or lo is None:
            continue
        seen[str(r.get("OtobusId"))] = {"id": str(r.get("OtobusId")), "yon": r.get("Yon"), "lat": la, "lng": lo}
    return list(seen.values())


def to_ego_row(v):
    return {"arac_no": v["id"], "plaka_no": v["id"], "lat": v["lat"], "lng": v["lng"], "hiz": "",
            "durak_no": "", "durak_sira_no": "", "konum_tarihi": "", "detay": ""}


def cmd_probe(args):
    http = E.Http(args.insecure)
    v = line_vehicles(http, args.hat)
    print(f"Hat {args.hat} araçları:", None if v is None else len(v), (v or [None])[0], get_json.last_error)
    lines = ckan_rows(http, "eshot-otobus-hat-listesi")
    print("Hat sayısı:", None if lines is None else len(lines), (lines or [None])[0])
    return 0


def cmd_init(args):
    conn = connect()
    http = E.Http(args.insecure)
    lines = ckan_rows(http, "eshot-otobus-hat-listesi")
    stops = ckan_rows(http, "eshot-otobus-duraklari")
    if not lines or not stops:
        print("Veri alınamadı:", get_json.last_error)
        return 1
    now = E.now_ts()
    for r in lines:
        k = hat_key(r.get("HAT_NO"))
        conn.execute("INSERT OR REPLACE INTO lines (hat, ad) VALUES (?,?)", (k, (r.get("HAT_ADI") or "").strip()))
        conn.execute("INSERT OR REPLACE INTO line_info (hat, kalkis, varis, mesafe, sure, ts) VALUES (?,?,?,?,?,?)",
                     (k, (r.get("HAT_BASLANGIC") or "").strip(), (r.get("HAT_BITIS") or "").strip(), "", "", now))
    known = {hat_key(r.get("HAT_NO")) for r in lines}
    for r in stops:
        d = hat_key(r.get("DURAK_ID"))
        la, lo = num(r.get("ENLEM")), num(r.get("BOYLAM"))
        if la is not None and lo is not None:
            conn.execute("INSERT OR REPLACE INTO stops_geo (durak, ad, lat, lng) VALUES (?,?,?,?)",
                         (d, (r.get("DURAK_ADI") or "").strip(), la, lo))
        for h in re.findall(r"\d+", str(r.get("DURAKTAN_GECEN_HATLAR") or "")):
            if h in known:
                conn.execute("INSERT OR IGNORE INTO line_stops (hat, durak) VALUES (?,?)", (h, d))
    conn.commit()
    print("Bitti.", conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0], "hat,",
          conn.execute("SELECT COUNT(*) FROM stops_geo").fetchone()[0], "durak,",
          conn.execute("SELECT COUNT(*) FROM line_stops").fetchone()[0], "hat-durak bağı.")
    return 0


def cmd_saatler(args):
    conn = connect()
    http = E.Http(args.insecure)
    rows = ckan_rows(http, "otobus-hareket-saatleri")
    if not rows:
        print("Saatler alınamadı:", get_json.last_error)
        return 1
    plan = {}
    for r in rows:
        gun = TARIFE.get(int(r.get("TARIFE_ID") or 0))
        k = hat_key(r.get("HAT_NO"))
        for alan, yon in (("GIDIS_SAATI", 0), ("DONUS_SAATI", 1)):
            m = re.search(r"(\d{1,2}):(\d{2})", str(r.get(alan) or ""))
            if gun and m:
                plan.setdefault(k, []).append((k, gun, yon, "%02d:%s" % (int(m.group(1)), m.group(2))))
    for k, items in plan.items():
        conn.execute("DELETE FROM line_times WHERE hat=?", (k,))
        conn.executemany("INSERT INTO line_times (hat, gun, yon, saat, nt) VALUES (?,?,?,?,'')", items)
    conn.commit()
    print(f"{len(plan)} hattın planlanan saatleri kaydedildi.")
    return 0


def cmd_run(args):
    conn = connect()
    http = E.Http(args.insecure)
    hats = [r[0] for r in conn.execute("SELECT hat FROM lines")]
    if not hats:
        print("Önce 'python3 izmir_tracker.py init' çalıştırın.")
        return 1
    gap = int(args.interval * 60 * 3)
    idle = {}
    print(f"İzmir toplayıcı: {len(hats)} hat, {args.interval} dk aralık.", flush=True)
    while not STOP.is_set():
        t0 = time.time()
        ts = E.now_ts()
        due = [h for h in hats if idle.get(h, 0) <= 0]
        for h in hats:
            if h not in due:
                idle[h] -= 1
        new = veh = fails = 0
        for h in due:
            if STOP.is_set():
                break
            rows = line_vehicles(http, h)
            time.sleep(args.delay)
            if rows is None:
                fails += 1
                if fails >= 30 and veh == 0:
                    break
                continue
            idle[h] = 0 if rows else args.idle_max
            for v in rows:
                if E.record_sighting(conn, ts, to_ego_row(v), h, gap, keep_raw=not args.no_raw):
                    new += 1
                veh += 1
            if veh and veh % 200 == 0:
                conn.commit()
        if due and veh == 0 and fails >= 30:
            print(f"Hat sorguları başarısız ({fails}): {get_json.last_error} - 10 dk bekleniyor", flush=True)
            STOP.wait(600)
            continue
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('last_cycle', ?)",
                     (json.dumps({"ts": E.now_ts(), "due": len(due), "vehicles": veh, "fails": fails,
                                  "interval": args.interval, "fleet": veh}),))
        conn.commit()
        print(f"[{E.fmt_ts(E.now_ts(), False)}] {len(due)} hat, {veh} araç, {new} yeni, {fails} hata", flush=True)
        if args.once:
            break
        STOP.wait(max(10, args.interval * 60 - (time.time() - t0)))
    conn.commit()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="İzmir (ESHOT) filo takip", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--insecure", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    p = sub.add_parser("probe")
    p.add_argument("--hat", default="446")
    p.set_defaults(fn=cmd_probe)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("saatler").set_defaults(fn=cmd_saatler)
    p = sub.add_parser("run")
    p.add_argument("--interval", type=float, default=3, help="tur aralığı (dk)")
    p.add_argument("--delay", type=float, default=0.2)
    p.add_argument("--idle-max", type=int, default=3)
    p.add_argument("--no-raw", action="store_true")
    p.add_argument("--once", action="store_true")
    p.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
