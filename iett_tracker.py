"""İstanbul (İETT) toplayıcısı - İBB açık veri servislerinden (SOAP/JSON) hat, durak ve canlı araç konumu.

Ankara toplayıcısıyla aynı veritabanı şemasını kullanır (ego_tracker.SCHEMA), ayrı dosyaya yazar:
  IETT_DB (varsayılan: iett_filo.db)

Kaynaklar (İBB Açık Veri, kimlik doğrulama yok):
  SeferGerceklesme.GetFiloAracKonum_json   tüm filo tek çağrıda: KapiNo, Plaka, Enlem, Boylam, Hiz, Operator
  SeferGerceklesme.GetHatOtoKonum_json     hat bazlı: kapino, hatkodu, guzergahkodu (ör. 500T_G_D0), yon, yakinDurakKodu
  HatDurakGuzergah.GetHat_json             tüm hatlar (SHATKODU, SHATADI)
  ibb.DurakDetay_GYY                       hattın durakları: YON, SIRANO, DURAKKODU, DURAKADI, X/YKOORDINATI
  PlanlananSeferSaati.GetPlanlananSeferSaati_json  planlanan saatler (SYON G/D, SGUNTIPI I/C/P, DT)

Hat anahtarı: "<HATKODU> <G|D>" (yön ayrı hat gibi tutulur; Ankara'daki 145-1/145-2 gibi).
Komutlar: probe | init | run | saatler
"""
import argparse
import html
import json
from concurrent.futures import ThreadPoolExecutor
import os
import re
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("IETT_BASE", "https://api.ibb.gov.tr/iett").rstrip("/")
DB = os.environ.get("IETT_DB", os.path.join(HERE, "iett_filo.db"))
STOP = threading.Event()

import ego_tracker as E  # noqa: E402  (ortak şema, kayıt ve yardımcılar)

PATHS = {
    "fleet": "/FiloDurum/SeferGerceklesme.asmx",
    "hatoto": "/FiloDurum/SeferGerceklesme.asmx",
    "hats": "/UlasimAnaVeri/HatDurakGuzergah.asmx",
    "stops": "/ibb/ibb.asmx",
    "plan": "/UlasimAnaVeri/PlanlananSeferSaati.asmx",
}

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS stops_geo (durak TEXT PRIMARY KEY, ad TEXT, lat REAL, lng REAL);
"""


def connect():
    conn = E.connect(DB)
    conn.executescript(EXTRA_SCHEMA)
    return conn


def soap(http, group, method, **params):
    """SOAP çağrısı -> Result metni (JSON ya da XML dizesi). Hata/boş: None."""
    body = ('<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<soap:Body><{method} xmlns="http://tempuri.org/">'
            + "".join(f"<{k}>{html.escape(str(v))}</{k}>" for k, v in params.items())
            + f"</{method}></soap:Body></soap:Envelope>").encode("utf-8")
    try:
        raw = http.request(BASE + PATHS[group], data=body, timeout=(60 if group in ("fleet", "stops", "plan", "hats") else 20), retries=(2 if group in ("fleet", "stops", "plan", "hats") else 1), headers={
            "Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/" + method,
            "User-Agent": "Mozilla/5.0 (FiloTakip arsiv)"}).decode("utf-8", "replace")
    except Exception as e:
        soap.last_error = str(e)
        return None
    m = re.search(r"<\w*Result[^>]*>(.*?)</\w*Result>", raw, re.S)
    return html.unescape(m.group(1)) if m else None


soap.last_error = ""


def jrows(text):
    if not text:
        return None
    try:
        d = json.loads(text)
    except ValueError:
        return None
    return [r for r in d if isinstance(r, dict)] if isinstance(d, list) else None


def fleet(http):
    """{kapino: {plaka, lat, lng, hiz, operator, saat}} - tüm filo."""
    rows = jrows(soap(http, "fleet", "GetFiloAracKonum_json"))
    if rows is None:
        return None
    out = {}
    for r in rows:
        k = str(r.get("KapiNo") or "").strip()
        if k:
            out[k] = {"plaka": str(r.get("Plaka") or "").strip(), "lat": r.get("Enlem"), "lng": r.get("Boylam"),
                      "hiz": r.get("Hiz"), "operator": r.get("Operator"), "saat": r.get("Saat")}
    return out


def kaydet_operator(conn, fl):
    """Filo listesindeki işletmeci (Operator) bilgisini kapı numarasına göre saklar."""
    conn.execute("CREATE TABLE IF NOT EXISTS arac_operator (arac_no TEXT PRIMARY KEY, operator TEXT, ts INTEGER)")
    ts = E.now_ts()
    conn.executemany("INSERT OR REPLACE INTO arac_operator (arac_no, operator, ts) VALUES (?,?,?)",
                     [(k, str(v.get("operator") or "").strip(), ts) for k, v in fl.items() if v.get("operator")])
    conn.commit()


def yon_of(row):
    """guzergahkodu 500T_G_D0 -> 'G'; yoksa 'yon' alanından tahmin."""
    m = re.search(r"_([GD])_", str(row.get("guzergahkodu") or ""))
    return m.group(1) if m else ""


def hat_key(kod, yon):
    return f"{kod} {yon}".strip()


def list_lines(http):
    rows = jrows(soap(http, "hats", "GetHat_json", HatKodu=""))
    return [(str(r.get("SHATKODU")).strip(), str(r.get("SHATADI") or "").strip()) for r in rows or [] if r.get("SHATKODU")]


def line_stops(http, kod):
    """-> [(yon, sira, durak_kodu, ad, lat, lng)] (DurakDetay_GYY XML)."""
    text = soap(http, "stops", "DurakDetay_GYY", hat_kodu=kod)
    if not text:
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    out = []
    for t in root.iter("Table"):
        g = lambda n: (t.findtext(n) or "").strip()
        try:
            out.append((g("YON"), int(g("SIRANO")), g("DURAKKODU"), g("DURAKADI"),
                        float(g("YKOORDINATI") or 0), float(g("XKOORDINATI") or 0)))
        except ValueError:
            continue
    return out


def line_vehicles(http, kod):
    return jrows(soap(http, "hatoto", "GetHatOtoKonum_json", HatKodu=kod))


def to_ego_row(r, fl, sira_of):
    """İETT satırı + filo konumu -> ego_tracker.record_sighting'in beklediği alan adları."""
    kapi = str(r.get("kapino") or "").strip()
    f = fl.get(kapi, {})
    kod, yon = str(r.get("hatkodu") or "").strip(), yon_of(r)
    durak = str(r.get("yakinDurakKodu") or "").strip()
    return {
        "arac_no": kapi, "plaka_no": f.get("plaka") or kapi,
        "lat": r.get("enlem"), "lng": r.get("boylam"), "hiz": f.get("hiz", ""),
        "durak_no": durak, "durak_sira_no": sira_of.get((hat_key(kod, yon), durak), ""),
        "konum_tarihi": r.get("son_konum_zamani", ""), "detay": "",
    }, hat_key(kod, yon)


GUN = {"I": "haftaici", "C": "cumartesi", "P": "pazar"}


def line_plan(http, kod):
    """Planlanan sefer saatleri -> [(hat_anahtarı, gün, saat)]"""
    rows = jrows(soap(http, "plan", "GetPlanlananSeferSaati_json", HatKodu=kod))
    out = []
    for r in rows or []:
        m = re.search(r"(\d{1,2}):(\d{2})", str(r.get("DT") or ""))
        yon = str(r.get("SYON") or "").strip().upper()[:1]
        gun = GUN.get(str(r.get("SGUNTIPI") or "").strip().upper()[:1])
        if m and yon and gun:
            out.append((hat_key(kod, yon), gun, "%02d:%s" % (int(m.group(1)), m.group(2))))
    return out


def cmd_saatler(args):
    conn = connect()
    http = E.Http(args.insecure)
    kods = sorted({k.rsplit(" ", 1)[0] for (k,) in conn.execute("SELECT hat FROM lines")})
    if args.limit:
        kods = kods[: args.limit]
    n = 0
    for kod in kods:
        if STOP.is_set():
            break
        plan = line_plan(http, kod)
        time.sleep(args.delay)
        if not plan:
            continue
        for key in {p[0] for p in plan}:
            conn.execute("DELETE FROM line_times WHERE hat=?", (key,))
            conn.execute("INSERT OR REPLACE INTO line_info (hat, kalkis, varis, mesafe, sure, ts) VALUES (?,?,?,?,?,?)",
                         (key, "", "", "", "", E.now_ts()))
        conn.executemany("INSERT INTO line_times (hat, gun, yon, saat, nt) VALUES (?,?,0,?,'')", plan)
        n += 1
        if n % 25 == 0:
            conn.commit()
    conn.commit()
    print(f"{n} hattın planlanan saatleri kaydedildi.")
    return 0


def cmd_probe(args):
    http = E.Http(args.insecure)
    fl = fleet(http)
    print("Filo:", "yok (%s)" % soap.last_error if fl is None else f"{len(fl)} araç; örnek: {next(iter(fl.items()))}")
    lines = list_lines(http)
    print("Hat sayısı:", len(lines), lines[:3])
    v = line_vehicles(http, args.hat)
    print(f"Hat {args.hat} araçları:", None if v is None else len(v), (v or [None])[0])
    s = line_stops(http, args.hat)
    print(f"Hat {args.hat} durakları:", None if s is None else len(s), (s or [None])[:2])
    return 0


def cmd_init(args):
    conn = connect()
    http = E.Http(args.insecure)
    lines = list_lines(http)
    if not lines:
        print("Hat listesi alınamadı:", soap.last_error)
        return 1
    done = {r[0] for r in conn.execute("SELECT DISTINCT substr(hat,1,length(hat)-2) FROM line_route")}
    todo = [l for l in lines if l[0] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(lines)} hat, {len(todo)} tanesinin durakları çekilecek.")
    n = 0
    for kod, ad in todo:
        if STOP.is_set():
            break
        st = line_stops(http, kod)
        time.sleep(args.delay)
        if not st:
            continue
        for yon in sorted({s[0] for s in st}):
            key = hat_key(kod, yon)
            conn.execute("INSERT OR REPLACE INTO lines (hat, ad) VALUES (?,?)", (key, ad))
            for y, sira, durak, dad, la, lo in st:
                if y != yon:
                    continue
                conn.execute("INSERT OR REPLACE INTO line_route (hat, sira, durak, ad) VALUES (?,?,?,?)", (key, sira, durak, dad))
                conn.execute("INSERT OR IGNORE INTO line_stops (hat, durak) VALUES (?,?)", (key, durak))
                conn.execute("INSERT OR REPLACE INTO stops_geo (durak, ad, lat, lng) VALUES (?,?,?,?)", (durak, dad, la, lo))
        n += 1
        if n % 25 == 0:
            conn.commit()
            print(f"  {n}/{len(todo)}")
    conn.commit()
    print("Bitti.", conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0], "hat-yön,",
          conn.execute("SELECT COUNT(*) FROM stops_geo").fetchone()[0], "durak.")
    return 0


def _progress(conn, n, total, veh, fails, t0):
    """Tur ilerlemesini meta'ya yazar; web arayüzü yüzde olarak gösterir."""
    conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('progress', ?)",
                 (json.dumps({"ts": E.now_ts(), "n": n, "total": total, "veh": veh, "fails": fails, "t0": int(t0)}),))
    conn.commit()


def cmd_run(args):
    conn = connect()
    http = E.Http(args.insecure)
    kods = sorted({k.rsplit(" ", 1)[0] for (k,) in conn.execute("SELECT hat FROM lines")})
    if getattr(args, "hatlar", ""):
        want = [x.strip().upper() for x in args.hatlar.split(",") if x.strip()]
        bulunan = [k for k in kods if k.upper() in want]
        yok = [w for w in want if w not in {k.upper() for k in kods}]
        if yok:
            print("Listede olmayan hatlar atlandı:", ", ".join(yok), flush=True)
        kods = bulunan
    if not kods:
        print("Önce 'python3 iett_tracker.py init' çalıştırın.")
        return 1
    sira_of = {(h, d): s for h, d, s in conn.execute("SELECT hat, durak, sira FROM line_route")}
    gap = max(int(args.interval * 60 * 3), 1800)  # tur ~13 dk sürebilir; aynı aracın kaydı 30 dk içinde sürer
    idle = {}
    fl_warned, last_fl, fl_ts, backoff = False, {}, 0.0, 0
    veh_hat = {}   # kapı no -> (hat anahtarı, son doğrulama ts): filo konumu bu hatta yazılır
    lastq = {}     # hat -> son sorgu zamanı
    adapt = [float(args.delay)]  # geçerli hat arası bekleme (sn); hatada artar, başarıda azalır
    print(f"İETT toplayıcı: {len(kods)} hat, {args.interval} dk aralık.", flush=True)
    while not STOP.is_set():
        t0 = time.time()
        ts = E.now_ts()
        fl = fleet(http) if time.time() - fl_ts >= max(120, args.interval * 60 - 30) else last_fl
        fresh = fl is not None and fl is not last_fl
        if fl is not None and fl is not last_fl:
            fl_ts = time.time()
            try:
                kaydet_operator(conn, fl)
            except Exception as e:  # noqa: BLE001
                print("İşletmeci kaydı yazılamadı:", e, flush=True)
        if fl is None:
            fl_ts = time.time() - 600  # başarısızsa 5 dk sonra yeniden dene
            # Filo listesi (plaka eşlemesi) alınamazsa hat sorgularıyla devam et; son iyi listeyi kullan
            if not fl_warned:
                print("Filo listesi alınamadı, plakasız devam ediliyor:", soap.last_error, flush=True)
                fl_warned = True
            fl = last_fl
        else:
            fl_warned, last_fl = False, fl
        due = [k for k in kods if idle.get(k, 0) <= 0]
        for k in kods:
            if k not in due:
                idle[k] -= 1
        if args.hat_per_cycle and len(due) > args.hat_per_cycle:
            due = sorted(due, key=lambda k: lastq.get(k, 0))[:args.hat_per_cycle]  # en eskiden sorgulananlar
        new = veh = fails = consec = 0
        fveh = 0
        if fresh and fl:
            for kapi, f in fl.items():  # filo-önce: tek çağrıdaki tüm konumlar, hattı bilinen araçlara yazılır
                vh = veh_hat.get(kapi)
                if not vh or ts - vh[1] > 5400 or f.get("lat") in (None, ""):
                    continue
                row = {"arac_no": kapi, "plaka_no": f.get("plaka") or kapi, "lat": f.get("lat"), "lng": f.get("lng"),
                       "hiz": f.get("hiz", ""), "durak_no": "", "durak_sira_no": "", "konum_tarihi": f.get("saat", ""), "detay": ""}
                if E.record_sighting(conn, ts, row, vh[0], gap, keep_raw=not args.no_raw):
                    new += 1
                fveh += 1

        abort = threading.Event()

        def _fetch(kod):
            if STOP.is_set() or abort.is_set():
                return kod, None
            rows = line_vehicles(http, kod)
            if rows is None and not STOP.is_set():
                adapt[0] = min(max(adapt[0] * 2, args.delay * 2), 60.0)
                time.sleep(min(20 + adapt[0], 60))  # İBB geçici 500 döner; bekleyip bir kez daha dene
                rows = line_vehicles(http, kod)
            if rows is None:
                adapt[0] = min(max(adapt[0] * 2, args.delay * 2), 60.0)
            else:
                adapt[0] = max(args.delay, adapt[0] * 0.9)
            time.sleep(adapt[0])
            return kod, rows

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for n, (kod, rows) in enumerate(pool.map(_fetch, due), 1):
                if STOP.is_set():
                    break
                if n == 1 or n % 10 == 0:
                    _progress(conn, n, len(due), veh, fails, t0)
                if n == 1 or (rows is None and fails < 3):
                    print(f"  ilk sonuç: hat {kod} -> {None if rows is None else len(rows)} araç ({int(time.time() - t0)} sn) {soap.last_error if rows is None else ''}", flush=True)
                if rows is None:
                    fails += 1
                    consec += 1
                    if consec >= 5 and veh == 0 or consec >= 25:
                        abort.set()  # İBB hız sınırı: kalan sorguları gönderme
                        break
                    continue
                consec = 0
                idle[kod] = 0 if rows else args.idle_max
                lastq[kod] = ts
                for r in rows:
                    row, key = to_ego_row(r, fl, sira_of)
                    if row["arac_no"]:
                        veh_hat[row["arac_no"]] = (key, ts)
                    if E.record_sighting(conn, ts, row, key, gap, keep_raw=not args.no_raw):
                        new += 1
                    veh += 1
                if n % 25 == 0:
                    conn.commit()
                    print(f"  ... {n}/{len(due)} hat, {veh} araç, {fails} hata, {int(time.time() - t0)} sn", flush=True)
        if due and veh == 0 and fails >= 1:
            backoff = min(backoff * 2 if backoff else 600, 7200)
            print(f"Hat sorguları başarısız ({fails}): {soap.last_error} - hız sınırı olabilir, {backoff // 60} dk bekleniyor", flush=True)
            STOP.wait(backoff)
            fl_ts = 0.0
            continue
        backoff = 0
        conn.execute("DELETE FROM meta WHERE k='progress'")
        conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('last_cycle', ?)",
                     (json.dumps({"ts": E.now_ts(), "due": len(due), "vehicles": veh, "fails": fails, "interval": args.interval,
                                  "fleet": len(fl)}),))
        conn.commit()
        print(f"[{E.fmt_ts(E.now_ts(), False)}] filo {len(fl)} ({fveh} konum filodan) · {len(due)} hat, {veh} araç, {new} yeni, {fails} hata", flush=True)
        if args.once:
            break
        STOP.wait(max(10, args.interval * 60 - (time.time() - t0)))
    conn.commit()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="İETT (İstanbul) filo takip", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--insecure", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    p = sub.add_parser("probe")
    p.add_argument("--hat", default="500T")
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("init")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--delay", type=float, default=0.3)
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("saatler", help="planlanan sefer saatlerini çek")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--delay", type=float, default=0.3)
    p.set_defaults(fn=cmd_saatler)
    p = sub.add_parser("run")
    p.add_argument("--interval", type=float, default=3, help="tur aralığı (dk)")
    p.add_argument("--delay", type=float, default=2.0, help="her sorgudan sonra bekleme (sn); İBB hız sınırı için düşük tutmayın")
    p.add_argument("--idle-max", type=int, default=3)
    p.add_argument("--workers", type=int, default=1, help="paralel sorgu sayısı")
    p.add_argument("--no-raw", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--hat-per-cycle", type=int, default=25, dest="hat_per_cycle", help="her turda en fazla bu kadar hat sorgula (filo-önce modu; 0 = hepsi)")
    p.add_argument("--hatlar", default="", help="yalnızca bu hatları tara (virgülle ayrılmış, ör. 500T,15F); deneme için")
    p.set_defaults(fn=cmd_run)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
