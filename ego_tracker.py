#!/usr/bin/env python3
"""
EGO Filo Takip
==============
EGO'nun kendi canlı servislerinden (EGO Cep'te uygulamasının kullandığı JSON
servisi + ego.gov.tr hat listesi) hangi aracın hangi hatta çalıştığını düzenli
aralıkla kaydeder; sonradan "şu filo/plaka, şu gün, şu saatte hangi hattaydı?"
sorusuna cevap verir.

Sadece Python standart kütüphanesi kullanır (pip kurulumu gerekmez).

Komutlar:
  probe     Uç noktalar çalışıyor mu, veri formatı nasıl? (ilk bunu çalıştırın)
  init      Hat -> durak eşleşmesini çıkarır (bir kez, ~10 dk; kaldığı yerden devam eder)
  run       Sürekli çalışan toplayıcı (gece-gündüz açık kalmalı)
  sorgu     Filo kodu/plaka + tarih + saat ile hat sorgula
  rapor     Günlük araç-hat raporu (CSV) üret
  araclar   Veritabanındaki araçları ara (filo no formatını görmek için)
  alias     "EGO-22-370" gibi bir filo kodunu plakaya bağla
  serve     Tarayıcıdan sorgu yapabileceğiniz yerel web arayüzü

Resmi olmayan, ticari amaç gütmeyen kişisel kullanım içindir. EGO sunucusunu
yormamak için varsayılan ayarlar kasıtlı olarak yavaştır.
"""
import argparse
import csv
import html
import json
import os
import random
import re
import sqlite3
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    from http.server import ThreadingHTTPServer
except ImportError:  # Python 3.6
    import socketserver

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("EGO_DB", os.path.join(HERE, "ego_filo.db"))
def _default_report_dir():
    # Termux'ta (Android) raporları, dosya yöneticisinden erişilebilen ortak depolamaya yaz.
    shared = os.path.expanduser("~/storage/shared")
    if os.environ.get("TERMUX_VERSION") and os.path.isdir(shared):
        return os.path.join(shared, "EGO-Raporlar")
    return os.path.join(HERE, "raporlar")


REPORT_DIR = os.environ.get("EGO_REPORT_DIR") or _default_report_dir()
STOPS_FILE = os.environ.get("EGO_STOPS", os.path.join(HERE, "stops.txt"))
API_BASE = os.environ.get(
    "EGO_API_BASE", "https://egocptsrvand.ego.gov.tr/mblSrv14/service.asp"
)
WEB_BASE = os.environ.get("EGO_WEB_BASE", "https://www.ego.gov.tr")
UA_API = "EGO Cepte/8 CFNetwork/1568.300.101 Darwin/24.0.0"
UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# Türkiye 2016'dan beri yaz saati uygulamasında değil: sabit UTC+3.
TZ = timezone(timedelta(hours=3))

STOP = threading.Event()


# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------
def now_ts():
    return int(time.time())


def fmt_ts(ts, with_date=True):
    d = datetime.fromtimestamp(ts, TZ)
    return d.strftime("%d.%m.%Y %H:%M" if with_date else "%H:%M")


def norm(s):
    """Plaka / filo kodu karşılaştırması için: büyük harf, sadece harf-rakam."""
    return re.sub(r"[^0-9A-Z]", "", (s or "").upper())


def pretty_plate(p):
    m = re.match(r"^(\d{2})([A-Z]+)(\d+)$", p or "")
    return f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else (p or "")


def parse_day(s):
    s = (s or "").strip()
    if not s:
        return datetime.now(TZ).date()
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    raise ValueError(f"Tarih anlaşılamadı: {s!r} (örnek: 2026-11-02 veya 02.11.2026)")


def parse_time(s):
    s = (s or "").strip().replace(".", ":")
    for f in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, f).time()
        except ValueError:
            pass
    raise ValueError(f"Saat anlaşılamadı: {s!r} (örnek: 14:35)")


def to_epoch(day, tm):
    return int(datetime(day.year, day.month, day.day, tm.hour, tm.minute, tm.second, tzinfo=TZ).timestamp())


def day_bounds(day):
    start = int(datetime(day.year, day.month, day.day, tzinfo=TZ).timestamp())
    return start, start + 86400


def to_float(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Http:
    def __init__(self, insecure=False):
        self.ctx = ssl.create_default_context()
        if insecure:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def request(self, url, headers=None, data=None, timeout=15, retries=2):
        last = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers or {})
                with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as r:
                    return r.read()
            except Exception as e:  # ağ hatası, TLS, zaman aşımı...
                last = e
                time.sleep(1 + attempt)
        raise last


def api_rows(http, fnc, **params):
    """EGO mobil servisini çağırır. Liste döner; cevap boş/bozuksa None."""
    q = {"FNC": fnc, "VER": "3.1.0", "LAN": "tr"}
    q.update(params)
    url = API_BASE + "?" + urllib.parse.urlencode(q)
    try:
        body = http.request(url, headers={"User-Agent": UA_API})
    except Exception as e:
        api_rows.last_error = str(e)
        return None
    if not body or not body.strip():
        api_rows.last_error = "boş yanıt"
        return None
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        api_rows.last_error = "JSON değil"
        return None
    if isinstance(data, dict):
        t = data.get("table")
        if isinstance(t, list):
            return [r for r in t if isinstance(r, dict)]
        return []
    return None


api_rows.last_error = ""


def _parse_hat_options(block):
    out = {}
    for val, text in re.findall(r'<option\s+value="([^"]*)"[^>]*>(.*?)</option>', block, re.S | re.I):
        code = html.unescape(val).strip()
        label = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text))).strip()
        # "0|OTOBÜS" gibi başlık satırlarını ve "(kod ) - ad" biçimi olmayanları atla
        if not code or code == "0" or not label.startswith("("):
            continue
        out[code] = re.sub(r"^\(\s*[^)]*\)\s*-\s*", "", label)
    return out


def fetch_catalog(http):
    """ego.gov.tr otobüs hat listesi -> {kod: ad}

    Güncel site: liste /hareketsaatleri sayfasının içinde (select#hat_liste_otobus).
    Eski site: POST /AjaxData/HatListesi (artık 404 veriyor; yedek olarak denenir).
    """
    errors = []
    try:
        page = http.request(WEB_BASE + "/hareketsaatleri", headers={"User-Agent": UA_WEB}).decode("utf-8", "replace")
        m = re.search(r'<select[^>]*id="hat_liste_otobus"[^>]*>(.*?)</select>', page, re.S | re.I)
        out = _parse_hat_options(m.group(1)) if m else {}
        if out:
            return out
        errors.append("hareketsaatleri sayfasında hat listesi bulunamadı")
    except Exception as e:
        errors.append(f"hareketsaatleri: {e}")
    for path in ("/AjaxData/HatListesiOtobus", "/AjaxData/HatListesi"):
        try:
            body = http.request(
                WEB_BASE + path,
                headers={"User-Agent": UA_WEB, "Content-Type": "application/x-www-form-urlencoded",
                         "X-Requested-With": "XMLHttpRequest", "Referer": WEB_BASE + "/hareketsaatleri"},
                data=b"hat_no=",
            ).decode("utf-8", "replace")
            out = _parse_hat_options(body)
            if out:
                return out
        except Exception as e:
            errors.append(f"{path}: {e}")
    raise RuntimeError("Hat listesi alınamadı: " + "; ".join(errors))


# --------------------------------------------------------------------------
# Satır ayrıştırma
# --------------------------------------------------------------------------
def sv(row, key):
    v = row.get(key)
    return "" if v is None else str(v).strip()


def is_live(row):
    return sv(row, "arac_no") not in ("", "-")


def row_hat(row, catalog, fallback=""):
    cands = [sv(row, k) for k in ("hat_kisa_kod", "hat_no", "hat_kod")]
    cands = [c for c in cands if c]
    for c in cands:
        if c in catalog:
            return c
    if fallback:
        return fallback
    return "" if catalog else (cands[0] if cands else "")


def parse_konum(s):
    s = (s or "").strip()
    for f in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(datetime.strptime(s, f).replace(tzinfo=TZ).timestamp())
        except ValueError:
            pass
    return None


# --------------------------------------------------------------------------
# Veritabanı
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS lines (hat TEXT PRIMARY KEY, ad TEXT);
CREATE TABLE IF NOT EXISTS line_stops (hat TEXT, durak TEXT, PRIMARY KEY (hat, durak));
CREATE TABLE IF NOT EXISTS swept_stops (durak TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS swept_lines (hat TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS stints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plaka TEXT NOT NULL, arac_no TEXT, hat TEXT NOT NULL,
    first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, n INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_stints_plaka ON stints (plaka, last_ts);
CREATE INDEX IF NOT EXISTS ix_stints_time ON stints (last_ts, first_ts);
CREATE TABLE IF NOT EXISTS sightings (
    ts INTEGER NOT NULL, plaka TEXT NOT NULL, arac_no TEXT, hat TEXT NOT NULL,
    lat REAL, lng REAL, hiz REAL,
    durak TEXT, sira INTEGER, onceki TEXT, kts INTEGER
);
CREATE INDEX IF NOT EXISTS ix_sight_plaka ON sightings (plaka, ts);
CREATE INDEX IF NOT EXISTS ix_sight_ts ON sightings (ts);
CREATE TABLE IF NOT EXISTS line_route (
    hat TEXT NOT NULL, sira INTEGER NOT NULL, durak TEXT NOT NULL, ad TEXT,
    PRIMARY KEY (hat, sira)
);
CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, plaka TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS arac_tip (anahtar TEXT PRIMARY KEY, tip TEXT, detay TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS line_info (hat TEXT PRIMARY KEY, kalkis TEXT, varis TEXT, mesafe TEXT, sure TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS line_times (hat TEXT NOT NULL, gun TEXT NOT NULL, yon INTEGER NOT NULL DEFAULT 0, saat TEXT NOT NULL, nt TEXT);
CREATE INDEX IF NOT EXISTS ix_line_times ON line_times (hat, gun);
"""


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    # Eski sürümle oluşturulmuş veritabanlarına yeni sütunları ekle
    have = {r[1] for r in conn.execute("PRAGMA table_info(sightings)")}
    for col, typ in (("durak", "TEXT"), ("sira", "INTEGER"), ("onceki", "TEXT"), ("kts", "INTEGER"), ("dol", "TEXT")):
        if col not in have:
            conn.execute(f"ALTER TABLE sightings ADD COLUMN {col} {typ}")
    conn.commit()
    return conn


_LAST_KTS = {}  # (plaka, hat) -> son kaydedilen GPS zamanı; durağan araçta tekrar kayıt yazmamak için


def to_int(x):
    try:
        return int(float(str(x).strip()))
    except (TypeError, ValueError):
        return None


_TIP_CACHE = {}


def parse_tip(detay):
    d = (detay or "").lower().replace("İ", "i").replace("I", "ı")
    if "körük" in d or "korük" in d:
        return "Körüklü"
    if "solo" in d:
        return "Solo"
    return None


def record_tip(conn, ts, row, plaka_key, arac_no):
    """EGO 'detay' alanından körüklü/solo bilgisini kalıcı kaydeder (yalnız değişince yazar)."""
    detay = (sv(row, "detay") or "").strip()
    tip = parse_tip(detay)
    if not tip:
        return
    for k in {plaka_key, norm(arac_no)}:
        if k and _TIP_CACHE.get(k) != (tip, detay):
            conn.execute("INSERT OR REPLACE INTO arac_tip (anahtar, tip, detay, ts) VALUES (?,?,?,?)", (k, tip, detay[:80], ts))
            _TIP_CACHE[k] = (tip, detay)


DOL_AD = {"az yoğun": 1, "orta yoğun": 2, "çok yoğun": 3, "dolu": 3}


def parse_dol(row):
    """EGO 'doluluk' alanından yoğunluk metni (yoksa None). {"message":"no data"} -> None."""
    d = row.get("doluluk") if isinstance(row, dict) else None
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            d = {"densityLevel": d}
    if isinstance(d, dict):
        v = str(d.get("densityLevel") or "").strip().lower().replace("İ", "i").replace("I", "ı")
        return v[:20] or None
    return None


def record_sighting(conn, ts, row, hat, gap, keep_raw=True):
    """Bir canlı araç satırını kaydeder; aynı araç+hat ardışıksa 'stint'i uzatır."""
    arac_no = sv(row, "arac_no")
    key = norm(sv(row, "plaka_no")) or norm(arac_no)
    if not key or not hat:
        return False
    record_tip(conn, ts, row, key, arac_no)
    lat, lng, hiz = to_float(sv(row, "lat")), to_float(sv(row, "lng")), to_float(sv(row, "hiz"))
    durak, sira, onceki = sv(row, "durak_no"), to_int(sv(row, "durak_sira_no")), sv(row, "onceki_durak_no")
    kts = parse_konum(sv(row, "konum_tarihi"))
    cur = conn.execute(
        "SELECT id, last_ts FROM stints WHERE plaka=? AND hat=? AND last_ts>=? ORDER BY last_ts DESC LIMIT 1",
        (key, hat, ts - gap),
    ).fetchone()
    new = False
    if cur:
        conn.execute(
            "UPDATE stints SET last_ts=MAX(last_ts, ?), n=n+1, arac_no=COALESCE(NULLIF(?, ''), arac_no) WHERE id=?",
            (ts, arac_no, cur[0]),
        )
    else:
        conn.execute(
            "INSERT INTO stints (plaka, arac_no, hat, first_ts, last_ts, n) VALUES (?,?,?,?,?,1)",
            (key, arac_no, hat, ts, ts),
        )
        new = True
    if keep_raw and not (kts and _LAST_KTS.get((key, hat)) == kts):
        conn.execute(
            "INSERT INTO sightings (ts, plaka, arac_no, hat, lat, lng, hiz, durak, sira, onceki, kts, dol) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, key, arac_no, hat, lat, lng, hiz, durak or None, sira, onceki or None, kts, parse_dol(row)),
        )
        if kts:
            _LAST_KTS[(key, hat)] = kts
    conn.execute("INSERT OR IGNORE INTO meta (k, v) VALUES ('first_data_ts', ?)", (str(ts),))
    return new


def load_catalog_set(conn):
    return {r[0] for r in conn.execute("SELECT hat FROM lines")}


def run_parallel(fn, items, workers, chunk=60):
    """Parçalar halinde paralel çalıştır (Ctrl-C ile hızlı çıkış için)."""
    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(items), chunk):
            if STOP.is_set():
                return
            for r in ex.map(fn, items[i:i + chunk]):
                yield r


# --------------------------------------------------------------------------
# probe
# --------------------------------------------------------------------------
def cmd_probe(args):
    http = Http(args.insecure)
    ok = True
    print("1) Hat listesi (ego.gov.tr) ...")
    catalog = {}
    try:
        catalog = fetch_catalog(http)
        print(f"   ✓ {len(catalog)} hat bulundu. Örnek: {list(catalog.items())[:2]}")
    except Exception as e:
        ok = False
        print(f"   ✗ alınamadı: {e}")

    print(f"2) Durağa göre canlı araçlar (FNC=Otobusler, durak {args.durak}) ...")
    rows = api_rows(http, "Otobusler", DURAK=args.durak)
    if rows is None:
        ok = False
        print(f"   ✗ cevap yok ({api_rows.last_error})")
    else:
        live = [r for r in rows if is_live(r)]
        print(f"   ✓ {len(rows)} satır, {len(live)} canlı araç")
        for r in rows[:6]:
            print("   ham satır:", json.dumps(r, ensure_ascii=False)[:400])

    print(f"3) Hattaki tüm canlı araçlar (FNC=Otobus, hat {args.hat}, durak {args.durak}) ...")
    rows = api_rows(http, "Otobus", HAT=args.hat, DURAK=args.durak)
    if rows is None:
        ok = False
        print(f"   ✗ cevap yok ({api_rows.last_error})")
    else:
        live = [r for r in rows if is_live(r)]
        print(f"   ✓ {len(rows)} satır, {len(live)} canlı araç")
        for r in rows[:6]:
            print("   ham satır:", json.dumps(r, ensure_ascii=False)[:400])
    print()
    if ok:
        print("Hepsi çalışıyor. Sıradaki adım: python ego_tracker.py init")
    else:
        print("Bazı uç noktalar cevap vermedi. TLS sertifika hatası görüyorsanız --insecure ekleyin")
        print("(python ego_tracker.py --insecure probe). EGO uç noktaları değişmiş de olabilir.")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------
def fetch_line_stops(http, hat):
    """ego.gov.tr/HareketSaatleri sayfasından hattın duraklarını çıkarır -> [(sıra, durak_no, ad), ...]"""
    body = http.request(
        WEB_BASE + "/HareketSaatleri",
        headers={
            "User-Agent": UA_WEB,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": WEB_BASE + "/hareketsaatleri",
        },
        data=urllib.parse.urlencode({"hat_no1": hat}).encode(),
    ).decode("utf-8", "replace")
    stops = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        # durak satırı: sıra | durak_no | durak adı | adres
        if len(cells) >= 4 and cells[0].isdigit() and re.fullmatch(r"\d{4,6}", cells[1]):
            stops.append((int(cells[0]), cells[1], cells[2]))
    return stops


def _cells(tr):
    return [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]


def parse_line_page(body):
    """HareketSaatleri HTML -> {'info': {...}, 'times': [(gun, yon, saat, not)], 'stops': [...]}"""
    info = {}
    m = re.search(r'<table[^>]*hs-kv[^>]*>(.*?)</table>', body, re.S | re.I)
    if m:
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S | re.I):
            c = [x for x in _cells(tr) if x != ":"]
            if len(c) >= 2:
                info[re.sub(r"\s+", " ", c[0]).strip(" :").lower()] = re.sub(r"\s+", " ", c[1]).strip()
    times = []
    tm = re.search(r'<table[^>]*hs-table[^>]*>(.*?)</table>', body, re.S | re.I)
    if tm:
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(1), re.S | re.I)
        heads = []
        for tr in trs:  # başlık satırı: Hafta içi | Cumartesi | Pazar
            if "hs-times" not in tr:
                heads = [h.lower() for h in _cells(tr)]
                break
        for tr in trs:
            if "hs-times" not in tr:
                continue
            for idx, cell in enumerate(re.findall(r'<td[^>]*hs-times[^>]*>(.*?)</td>', tr, re.S | re.I)):
                h = heads[idx] if idx < len(heads) else ""
                gun = "pazar" if "pazar" in h else "cumartesi" if "cumartesi" in h else "haftaici"
                if not h and idx in (1, 2):
                    gun = ("cumartesi", "pazar")[idx - 1]
                for part in re.split(r"<br\s*/?>", cell, flags=re.I):
                    t = html.unescape(re.sub(r"<[^>]+>", " ", part)).strip()
                    mm = re.match(r"(\d{1,2}):(\d{2})\s*(.*)$", t)
                    if mm:
                        note = re.sub(r"^-$", "", mm.group(3).strip())
                        times.append((gun, 0, "%02d:%s" % (int(mm.group(1)), mm.group(2)), note[:60]))
    return {"info": info, "times": times, "stops": fetch_stops_from_html(body)}


def fetch_stops_from_html(body):
    stops = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
        cells = _cells(tr)
        if len(cells) >= 4 and cells[0].isdigit() and re.fullmatch(r"\d{4,6}", cells[1]):
            stops.append((int(cells[0]), cells[1], cells[2]))
    return stops


def post_line_page(http, hat):
    return http.request(
        WEB_BASE + "/HareketSaatleri",
        headers={"User-Agent": UA_WEB, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": WEB_BASE + "/hareketsaatleri"},
        data=urllib.parse.urlencode({"hat_no1": hat}).encode(),
    ).decode("utf-8", "replace")


def save_line_page(conn, hat, page):
    i = page["info"]
    def pick(*keys):
        for k, v in i.items():
            if any(x in k for x in keys):
                return v
        return ""
    conn.execute("INSERT OR REPLACE INTO line_info (hat, kalkis, varis, mesafe, sure, ts) VALUES (?,?,?,?,?,?)",
                 (hat, pick("kalkış", "kalkis"), pick("varış", "varis"), pick("mesafe"), pick("süre", "sure"), now_ts()))
    conn.execute("DELETE FROM line_times WHERE hat=?", (hat,))
    conn.executemany("INSERT INTO line_times (hat, gun, yon, saat, nt) VALUES (?,?,?,?,?)",
                     [(hat, g, y, t, n) for g, y, t, n in page["times"]])


def refresh_timetables(http, max_age_days=7, delay=1.5, limit=0):
    """Hat bilgisi/hareket saatlerini yavaşça tazeler (toplayıcı içinde arka planda çalışır)."""
    conn = connect()
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        old = now_ts() - max_age_days * 86400
        have = {r[0]: r[1] for r in conn.execute("SELECT hat, ts FROM line_info")}
        todo = [r[0] for r in conn.execute("SELECT hat FROM lines ORDER BY hat") if have.get(r[0], 0) < old]
        if limit:
            todo = todo[:limit]
        n = 0
        for hat in todo:
            if STOP.is_set():
                break
            try:
                page = parse_line_page(post_line_page(http, hat))  # ağ isteği kilit tutmadan yapılır
                save_line_page(conn, hat, page)
                conn.commit()  # yazma kilidini hemen bırak; toplayıcı beklemesin
                n += 1
            except Exception as e:
                api_rows.last_error = str(e)
            STOP.wait(delay)
        conn.commit()
        return n
    finally:
        conn.close()


def timetable_worker(http, delay=1.5):
    while not STOP.is_set():
        try:
            refresh_timetables(http, delay=delay)
        except Exception:
            pass
        STOP.wait(6 * 3600)


def init_from_schedules(conn, http, catalog, args):
    """Her hattın Hareket Saatleri sayfasından sıralı durak listesini al (~660 istek)."""
    done = {r[0] for r in conn.execute("SELECT DISTINCT hat FROM line_route")}
    todo = [h for h in catalog if h not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"Hareket Saatleri taraması: {len(todo)} hat kaldı ({len(done)} tamamlanmıştı). Ctrl-C ile durdurabilirsiniz; devam eder.")

    def work(hat):
        if STOP.is_set():
            return hat, None
        time.sleep(args.delay + random.random() * args.delay)
        try:
            return hat, fetch_line_stops(http, hat)
        except Exception as e:
            api_rows.last_error = str(e)
            return hat, None

    n = errors = empty = 0
    recent = []
    try:
        for hat, stops in run_parallel(work, todo, args.workers):
            n += 1
            if stops is None:
                errors += 1
                recent.append(False)
                if len(recent) == 15 and not any(recent):
                    print(f"İlk 15 istek de başarısız ({api_rows.last_error}). 'probe' komutunu çalıştırın.")
                    conn.commit()
                    return 1
                continue
            if len(recent) < 15:
                recent.append(True)
            if not stops:
                empty += 1
            for sira, durak, ad in stops:
                conn.execute("INSERT OR IGNORE INTO line_stops (hat, durak) VALUES (?, ?)", (hat, durak))
                conn.execute("INSERT OR REPLACE INTO line_route (hat, sira, durak, ad) VALUES (?, ?, ?, ?)",
                             (hat, sira, durak, ad))
            conn.execute("INSERT OR IGNORE INTO swept_lines (hat) VALUES (?)", (hat,))
            if n % 50 == 0:
                conn.commit()
                print(f"  {n}/{len(todo)} hat, hata: {errors}, durak bulunamayan: {empty}")
    except KeyboardInterrupt:
        print("\nDurduruldu; kaldığı yerden devam edecek.")
    conn.commit()
    known = conn.execute("SELECT COUNT(DISTINCT hat) FROM line_stops").fetchone()[0]
    print(f"Bitti: {n} hat tarandı, {errors} hata, {empty} hatta durak tablosu çıkmadı. Durağı bilinen hat: {known}/{len(catalog)}.")
    if empty or known < len(catalog):
        print("Eksik hatlar için alternatif: python ego_tracker.py init --yontem durak  (durak durak tarar, daha yavaş)")
    print("Sıradaki adım: python ego_tracker.py run")
    return 0


def cmd_init(args):
    conn = connect()
    http = Http(args.insecure)
    print("Hat listesi alınıyor ...")
    catalog = fetch_catalog(http)
    if not catalog:
        print("Hat listesi boş geldi; 'probe' komutuyla kontrol edin.")
        return 1
    conn.executemany("INSERT OR REPLACE INTO lines (hat, ad) VALUES (?, ?)", list(catalog.items()))
    conn.commit()
    print(f"{len(catalog)} hat kaydedildi.")

    if args.yontem == "saatler":
        return init_from_schedules(conn, http, catalog, args)

    if not os.path.exists(STOPS_FILE):
        print(f"Durak listesi bulunamadı: {STOPS_FILE}")
        return 1
    stops = [x.strip() for x in open(STOPS_FILE, encoding="utf-8") if x.strip()]
    swept = {r[0] for r in conn.execute("SELECT durak FROM swept_stops")}
    todo = [s for s in stops if s not in swept]
    if args.limit:
        todo = todo[: args.limit]
    print(f"Durak taraması: {len(todo)} durak kaldı ({len(swept)} tamamlanmıştı). Ctrl-C ile durdurabilirsiniz; devam eder.")

    def fetch_stop(stop):
        if STOP.is_set():
            return stop, None
        time.sleep(args.delay + random.random() * args.delay)
        return stop, api_rows(http, "Otobusler", DURAK=stop)

    gap = 1800
    done = errors = pairs = 0
    first_batch = []
    try:
        for stop, rows in run_parallel(fetch_stop, todo, args.workers):
            done += 1
            if rows is None:
                errors += 1
                if len(first_batch) < 15:
                    first_batch.append(False)
                    if len(first_batch) == 15 and not any(first_batch):
                        print("İlk 15 istek de başarısız. EGO erişilemiyor olabilir "
                              f"({api_rows.last_error}). 'probe' komutunu çalıştırın.")
                        conn.commit()
                        return 1
                continue
            if len(first_batch) < 15:
                first_batch.append(True)
            conn.execute("INSERT OR IGNORE INTO swept_stops (durak) VALUES (?)", (stop,))
            ts = now_ts()
            for row in rows:
                hat = row_hat(row, set(catalog))
                if hat:
                    conn.execute("INSERT OR IGNORE INTO line_stops (hat, durak) VALUES (?, ?)", (hat, stop))
                    pairs += 1
                    if is_live(row):
                        record_sighting(conn, ts, row, hat, gap, keep_raw=not args.no_raw)
            if done % 50 == 0:
                conn.commit()
            if done % 100 == 0:
                print(f"  {done}/{len(todo)} durak, hata: {errors}")
    except KeyboardInterrupt:
        print("\nDurduruldu; kaldığı yerden devam edecek.")
    conn.commit()
    n_lines = conn.execute("SELECT COUNT(DISTINCT hat) FROM line_stops").fetchone()[0]
    print(f"Bitti: {done} durak tarandı, {errors} hata. Durağı bilinen hat sayısı: {n_lines}/{len(catalog)}.")
    if errors > done * 0.2:
        print("Hata oranı yüksek; 'init' komutunu tekrar çalıştırırsanız eksik duraklar yeniden denenir.")
    print("Sıradaki adım: python ego_tracker.py run")
    return 0


# --------------------------------------------------------------------------
# run (sürekli toplayıcı)
# --------------------------------------------------------------------------
def write_report(conn, day):
    os.makedirs(REPORT_DIR, exist_ok=True)
    start, end = day_bounds(day)
    rows = conn.execute(
        "SELECT plaka, arac_no, hat, first_ts, last_ts, n FROM stints "
        "WHERE last_ts >= ? AND first_ts < ? ORDER BY plaka, first_ts",
        (start, end),
    ).fetchall()
    p1 = os.path.join(REPORT_DIR, f"rapor-{day.isoformat()}.csv")
    p2 = os.path.join(REPORT_DIR, f"arac-ozet-{day.isoformat()}.csv")
    summary = {}
    with open(p1, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["plaka", "filo_no", "hat", "ilk_gorulme", "son_gorulme", "gozlem_sayisi"])
        for plaka, arac_no, hat, a, b, n in rows:
            a2, b2 = max(a, start), min(b, end - 1)
            w.writerow([pretty_plate(plaka), arac_no or "", hat, fmt_ts(a2, False), fmt_ts(b2, False), n])
            s = summary.setdefault(plaka, {"arac_no": arac_no or "", "parts": []})
            s["arac_no"] = arac_no or s["arac_no"]
            s["parts"].append(f"{hat} ({fmt_ts(a2, False)}-{fmt_ts(b2, False)})")
    with open(p2, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["plaka", "filo_no", "hat_sayisi", "hatlar_ve_saatler"])
        for plaka, s in sorted(summary.items()):
            w.writerow([pretty_plate(plaka), s["arac_no"], len({p.split(' ')[0] for p in s["parts"]}), " | ".join(s["parts"])])
    return p1, p2, len(summary)


def cmd_run(args):
    max_min = getattr(args, "max_minutes", 0) or 0
    t_start = time.time()
    if getattr(args, "once", False) or max_min:
        try:
            import fcntl
            _lk = open(DB_PATH + ".lock", "w")
            fcntl.flock(_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            print("Önceki tur hâlâ çalışıyor; bu tur atlandı.")
            return 0
    conn = connect()
    http = Http(args.insecure)
    catalog = load_catalog_set(conn)
    if not catalog:
        print("Önce 'python ego_tracker.py init' çalıştırın.")
        return 1
    stops_by_line = {}
    for hat, durak in conn.execute("SELECT hat, durak FROM line_stops"):
        stops_by_line.setdefault(hat, []).append(durak)
    hats = sorted(stops_by_line)
    if not hats:
        print("Hat-durak eşleşmesi yok; 'init' komutunu çalıştırın.")
        return 1
    missing = len(catalog) - len(hats)
    if missing > 0:
        print(f"Not: {missing} hat için durak bilinmiyor, bunlar izlenmeyecek (gece hatları vb. olabilir).")

    if not getattr(args, "once", False) and not max_min and os.environ.get("EGO_NO_TIMETABLES") != "1":
        threading.Thread(target=timetable_worker, args=(http,), daemon=True).start()

    interval = args.interval * 60
    gap = max(1800, int(3 * interval))
    sample_shown = False
    next_due = {}
    idle = {}
    once = getattr(args, "once", False)
    persist = once or bool(max_min)
    idle_cap = getattr(args, "idle_max", 2)
    if persist:  # her cron çağrısı ayrı süreç: zamanlamayı veritabanında sakla
        _st = conn.execute("SELECT v FROM meta WHERE k='schedule'").fetchone()
        if _st:
            try:
                _d = json.loads(_st[0])
                next_due = {k: float(v) for k, v in _d.get("nd", {}).items()}
                idle = {k: int(v) for k, v in _d.get("idle", {}).items()}
            except (ValueError, TypeError):
                pass
    cur_day = datetime.now(TZ).date()
    yp = os.path.join(REPORT_DIR, f"rapor-{(cur_day - timedelta(days=1)).isoformat()}.csv")
    if not os.path.exists(yp) and conn.execute("SELECT 1 FROM stints LIMIT 1").fetchone():
        write_report(conn, cur_day - timedelta(days=1))

    def poll(hat):
        if STOP.is_set():
            return hat, None
        stops = stops_by_line[hat][:]
        random.shuffle(stops)
        for stop in stops[:2]:
            time.sleep(args.delay + random.random() * args.delay)
            rows = api_rows(http, "Otobus", HAT=hat, DURAK=stop)
            if rows is not None:
                return hat, rows
        return hat, None

    print(f"Toplayıcı başladı: {len(hats)} hat, {args.interval} dk aralık, {args.workers} eşzamanlı istek. Durdurmak için Ctrl-C.")
    try:
        while not STOP.is_set():
            t0 = time.time()
            today = datetime.now(TZ).date()
            if today != cur_day:
                p1, p2, n = write_report(conn, cur_day)
                print(f"[{fmt_ts(now_ts(), False)}] {cur_day} raporu yazıldı ({n} araç): {p1}")
                if args.raw_days > 0:
                    cutoff = now_ts() - args.raw_days * 86400
                    conn.execute("DELETE FROM sightings WHERE ts < ?", (cutoff,))
                    conn.commit()
                cur_day = today
            due = [h for h in hats if next_due.get(h, 0) <= t0]
            vehicles = new = fails = 0
            ts = now_ts()
            for hat, rows in run_parallel(poll, due, args.workers):
                if rows is None:
                    fails += 1
                    next_due[hat] = t0 + interval
                    continue
                live = [r for r in rows if is_live(r)]
                if args.stale_min:
                    live = [r for r in live if not (parse_konum(sv(r, "konum_tarihi")) and
                                                    ts - parse_konum(sv(r, "konum_tarihi")) > args.stale_min * 60)]
                if live and not sample_shown:
                    sample_shown = True
                    print("İlk canlı araç satırı (alan adlarını doğrulamak için):",
                          json.dumps(live[0], ensure_ascii=False)[:600], flush=True)
                    if not sv(live[0], "plaka_no"):
                        print("UYARI: canlı satırda 'plaka_no' alanı yok; filo no ile devam edilecek.", flush=True)
                idle[hat] = 0 if live else min(idle.get(hat, 0) + 1, idle_cap)
                next_due[hat] = t0 + interval * (1 + idle[hat])
                for r in live:
                    h = row_hat(r, catalog, fallback=hat)
                    if record_sighting(conn, ts, r, h, gap, keep_raw=not args.no_raw):
                        new += 1
                    vehicles += 1
            if persist:
                conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('schedule', ?)",
                             (json.dumps({"nd": next_due, "idle": idle}),))
            conn.execute(
                "INSERT OR REPLACE INTO meta (k, v) VALUES ('last_cycle', ?)",
                (json.dumps({"ts": now_ts(), "due": len(due), "vehicles": vehicles, "fails": fails,
                             "interval": args.interval}),),
            )
            conn.commit()
            msg = f"[{fmt_ts(now_ts(), False)}] {len(due)} hat sorgulandı, {vehicles} araç, {new} yeni kayıt, {fails} hata"
            if due and fails == len(due):
                msg += "  <-- hiç cevap alınamadı (internet/EGO?)"
            print(msg, flush=True)
            if once:
                break
            wait = max(5, interval - (time.time() - t0))
            if max_min and time.time() + wait - t_start > max_min * 60:
                break  # süre doldu; sonraki cron çağrısı devralır
            STOP.wait(wait)
    except KeyboardInterrupt:
        pass
    conn.commit()
    print("Toplayıcı durdu.")
    return 0


# --------------------------------------------------------------------------
# Sorgu
# --------------------------------------------------------------------------
def resolve_vehicle(conn, q):
    """-> (plakalar, eşleşme_türü)  tür: 'alias' | 'tam' | 'yaklasik' | 'yok'"""
    n = norm(q)
    if not n:
        return [], "yok"
    r = conn.execute("SELECT plaka FROM aliases WHERE alias=?", (n,)).fetchone()
    if r:
        return [r[0]], "alias"
    n2 = n[3:] if n.startswith("EGO") and len(n) > 3 else n
    pairs = conn.execute("SELECT DISTINCT plaka, arac_no FROM stints").fetchall()
    exact = sorted({p for p, a in pairs if p == n or norm(a) == n or (n2 and norm(a) == n2)})
    if exact:
        return exact, "tam"
    digits = n2
    fuzzy = set()
    if len(digits) >= 3:
        for p, a in pairs:
            na = norm(a)
            if len(na) >= 3 and (na.endswith(digits) or digits.endswith(na)):
                fuzzy.add(p)
    if fuzzy:
        return sorted(fuzzy), "yaklasik"
    return [], "yok"


def query_vehicle(conn, q, when, tol_min=30):
    tol = tol_min * 60
    plates, kind = resolve_vehicle(conn, q)
    res = {"q": q, "when": when, "tol_min": tol_min, "kind": kind, "vehicles": [], "warnings": []}
    first = conn.execute("SELECT v FROM meta WHERE k='first_data_ts'").fetchone()
    last = conn.execute("SELECT MAX(last_ts) FROM stints").fetchone()[0]
    res["first_data"] = int(first[0]) if first else None
    res["last_data"] = last
    if res["first_data"] and when < res["first_data"] - tol:
        res["warnings"].append(
            f"Bu saat kayıt başlangıcından ({fmt_ts(res['first_data'])}) önce; o tarihte veri toplanmamış.")
    if last and when > last + tol:
        res["warnings"].append(f"Bu saat son kaydın ({fmt_ts(last)}) sonrasında; veri henüz yok.")
    for plaka in plates:
        arac_no = (conn.execute(
            "SELECT arac_no FROM stints WHERE plaka=? AND arac_no<>'' ORDER BY last_ts DESC LIMIT 1", (plaka,)
        ).fetchone() or [""])[0]
        stints = conn.execute(
            "SELECT hat, first_ts, last_ts, n FROM stints WHERE plaka=? AND first_ts<=? AND last_ts>=? "
            "ORDER BY ABS(((first_ts+last_ts)/2) - ?)",
            (plaka, when + tol, when - tol, when),
        ).fetchall()
        items = []
        for hat, a, b, n in stints:
            if a <= when <= b:
                conf, diff = "kesin", 0
            else:
                diff = (a - when) if when < a else (when - b)
                conf = "yakın"
            pos = conn.execute(
                "SELECT ts, lat, lng, hiz FROM sightings WHERE plaka=? AND hat=? AND ts BETWEEN ? AND ? "
                "ORDER BY ABS(ts-?) LIMIT 1",
                (plaka, hat, when - tol, when + tol, when),
            ).fetchone()
            ad = (conn.execute("SELECT ad FROM lines WHERE hat=?", (hat,)).fetchone() or [""])[0]
            items.append({"hat": hat, "ad": ad, "first": a, "last": b, "n": n, "conf": conf,
                          "diff_min": round(diff / 60), "pos": pos})
        before = after = None
        if not items:
            before = conn.execute(
                "SELECT hat, first_ts, last_ts FROM stints WHERE plaka=? AND last_ts<? ORDER BY last_ts DESC LIMIT 1",
                (plaka, when)).fetchone()
            after = conn.execute(
                "SELECT hat, first_ts, last_ts FROM stints WHERE plaka=? AND first_ts>? ORDER BY first_ts LIMIT 1",
                (plaka, when)).fetchone()
        res["vehicles"].append({"plaka": plaka, "arac_no": arac_no, "items": items, "before": before, "after": after})
    return res


def format_result(res):
    out = []
    when = fmt_ts(res["when"])
    out.append(f"Sorgu: {res['q']}  |  {when}  (±{res['tol_min']} dk)")
    for w in res["warnings"]:
        out.append(f"! {w}")
    if not res["vehicles"]:
        out.append("Bu kodla eşleşen araç kayıtlarda yok. Plakayla deneyin veya 'araclar --ara ...' ile filo no formatına bakın.")
        return "\n".join(out)
    if res["kind"] == "yaklasik":
        out.append("! Filo kodu yaklaşık eşleşti (birden fazla araç olabilir). Kesin sonuç için plaka kullanın "
                   "ya da 'alias' ile filo kodunu plakaya bağlayın.")
    for v in res["vehicles"]:
        out.append("")
        out.append(f"Araç: {pretty_plate(v['plaka'])}  filo no: {v['arac_no'] or '-'}")
        if v["items"]:
            for it in v["items"]:
                span = f"{fmt_ts(it['first'])} – {fmt_ts(it['last'], False)}"
                tag = "aralığın içinde" if it["conf"] == "kesin" else f"{it['diff_min']} dk fark"
                out.append(f"  HAT {it['hat']}  {it['ad']}")
                out.append(f"     görüldü: {span}  ({tag}, {it['n']} gözlem)")
                if it["pos"]:
                    ts, lat, lng, hiz = it["pos"]
                    if lat and lng:
                        out.append(f"     en yakın konum: {fmt_ts(ts, False)}  https://maps.google.com/?q={lat},{lng}")
        else:
            out.append("  Bu zaman aralığında kayıt yok.")
            for label, st in (("önceki", v["before"]), ("sonraki", v["after"])):
                if st:
                    out.append(f"  {label} kayıt: hat {st[0]}  {fmt_ts(st[1])} – {fmt_ts(st[2], False)}")
    return "\n".join(out)


TRIP_GAP = 40 * 60  # aynı hatta bu kadar süre görünmezse yeni sefer


def build_trips(samples):
    """samples: [dict(t, hat, sira, durak, lat, lng, hiz)] -> sefer listesi.

    Yeni sefer: hat değişti, 40 dk'dan uzun boşluk var ya da durak sırası belirgin şekilde geri sardı
    (araç hattın başına dönmüş = yeni tur)."""
    trips, cur, prev = [], None, None
    for s in samples:
        new = prev is None or s["hat"] != prev["hat"] or s["t"] - prev["t"] > TRIP_GAP
        if not new and s["sira"] is not None and prev["sira"] is not None and s["sira"] < prev["sira"] - 3:
            new = True
        if new:
            cur = {"hat": s["hat"], "samples": []}
            trips.append(cur)
        cur["samples"].append(s)
        prev = s
    return trips


def stop_passages(samples, route):
    """Gözlemlerden durak geçiş saatlerini doğrusal ara değerlemeyle tahmin eder.

    Her gözlemde araç 'sira' numaralı durağa doğru gidiyor (bir önceki durağı geçmiş) kabul edilir,
    konum = sira - 0.5. Gözlem aralığının dışındaki duraklar için tahmin yapılmaz."""
    pts = []
    for s in samples:
        if s["sira"] is None:
            continue
        p = s["sira"] - 0.5
        if pts and p < pts[-1][1]:
            continue  # geriye giden gürültüyü at
        if pts and p == pts[-1][1]:
            continue  # aynı konumda bekleme
        pts.append((s["t"], p))
    out = []
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        k = int(p0) + 1
        while k <= p1:
            if k > p0:
                gercek = (p1 - p0) <= 1.0 and (t1 - t0) <= 150  # tek durak atladı, ardışık taramada yakalandı
                t = t1 if gercek else t0 + (k - p0) / (p1 - p0) * (t1 - t0)
                durak, ad = route.get(k, ("", ""))
                out.append({"sira": k, "durak": durak, "ad": ad, "t": int(t), "gercek": gercek})
            k += 1
    return out


def query_day(conn, q, day):
    start, end = day_bounds(day)
    plates, kind = resolve_vehicle(conn, q)
    res = {"q": q, "day": day, "kind": kind, "vehicles": [], "warnings": []}
    first = conn.execute("SELECT v FROM meta WHERE k='first_data_ts'").fetchone()
    last = conn.execute("SELECT MAX(last_ts) FROM stints").fetchone()[0]
    if first and end < int(first[0]):
        res["warnings"].append(f"Bu tarih kayıt başlangıcından ({fmt_ts(int(first[0]))}) önce; veri toplanmamış.")
    elif last and start > last:
        res["warnings"].append(f"Bu tarih son kaydın ({fmt_ts(last)}) sonrasında.")
    elif first and start < int(first[0]) < end:
        res["warnings"].append(f"Kayıt bu gün {fmt_ts(int(first[0]), False)}'de başladı; öncesi yok.")
    routes, names = {}, {}
    for plaka in plates:
        arac_no = (conn.execute(
            "SELECT arac_no FROM stints WHERE plaka=? AND arac_no<>'' ORDER BY last_ts DESC LIMIT 1", (plaka,)
        ).fetchone() or [""])[0]
        rows = conn.execute(
            "SELECT ts, hat, sira, durak, lat, lng, hiz, kts FROM sightings "
            "WHERE plaka=? AND ts>=? AND ts<? ORDER BY COALESCE(kts, ts), ts", (plaka, start, end)).fetchall()
        samples = []
        for ts, hat, sira, durak, lat, lng, hiz, kts in rows:
            t = kts or ts
            if samples and samples[-1]["t"] == t and samples[-1]["hat"] == hat:
                continue
            samples.append({"t": t, "hat": hat, "sira": sira, "durak": durak, "lat": lat, "lng": lng, "hiz": hiz})
        trips = build_trips(samples)
        for trip in trips:
            hat = trip["hat"]
            if hat not in routes:
                routes[hat] = {r[0]: (r[1], r[2]) for r in conn.execute(
                    "SELECT sira, durak, ad FROM line_route WHERE hat=?", (hat,))}
                names[hat] = (conn.execute("SELECT ad FROM lines WHERE hat=?", (hat,)).fetchone() or [""])[0]
            trip["ad"] = names[hat]
            trip["route"] = routes[hat]
            trip["passages"] = stop_passages(trip["samples"], routes[hat])
        stints = []
        if not trips:  # ham kayıt yoksa (eski veri / --no-raw) hat aralıklarını göster
            stints = conn.execute(
                "SELECT hat, first_ts, last_ts, n FROM stints WHERE plaka=? AND last_ts>=? AND first_ts<? ORDER BY first_ts",
                (plaka, start, end)).fetchall()
        res["vehicles"].append({"plaka": plaka, "arac_no": arac_no, "trips": trips, "stints": stints})
    return res


def format_day(res, max_stops=400):
    out = [f"Sorgu: {res['q']}  |  {res['day'].strftime('%d.%m.%Y')}"]
    for w in res["warnings"]:
        out.append(f"! {w}")
    if not res["vehicles"]:
        out.append("Bu kodla eşleşen araç kayıtlarda yok. Plakayla deneyin veya 'araclar --ara ...' ile bakın.")
        return "\n".join(out)
    if res["kind"] == "yaklasik":
        out.append("! Filo kodu yaklaşık eşleşti (birden fazla araç olabilir); kesin sonuç için plaka kullanın.")
    for v in res["vehicles"]:
        out.append("")
        out.append(f"ARAÇ {pretty_plate(v['plaka'])}   filo no: {v['arac_no'] or '-'}")
        if not v["trips"] and not v["stints"]:
            out.append("  Bu tarihte kayıt yok.")
        for st in v["stints"]:
            out.append(f"  hat {st[0]}: {fmt_ts(st[1], False)} – {fmt_ts(st[2], False)} ({st[3]} gözlem, durak ayrıntısı yok)")
        for i, tr in enumerate(v["trips"], 1):
            s0, s1 = tr["samples"][0], tr["samples"][-1]
            out.append("")
            out.append(f"  SEFER {i}: HAT {tr['hat']}  {tr['ad']}")
            sira_txt = ""
            if s0["sira"] is not None and s1["sira"] is not None:
                sira_txt = f"   durak sırası {s0['sira']} → {s1['sira']}"
            out.append(f"    {fmt_ts(s0['t'], False)} – {fmt_ts(s1['t'], False)}  ({len(tr['samples'])} gözlem){sira_txt}")
            # gözlemler: aracın o anda hangi iki durak arasında olduğu
            for s in tr["samples"][:1] + tr["samples"][-1:] if len(tr["samples"]) > 1 else tr["samples"]:
                if s["sira"] is not None:
                    prev = tr["route"].get(s["sira"] - 1, ("", ""))[1]
                    nxt = tr["route"].get(s["sira"], ("", ""))[1]
                    out.append(f"    gözlem {fmt_ts(s['t'], False)}: {prev or '?'} → {nxt or '?'} arasında")
            if tr["passages"]:
                out.append("    Durak geçişleri (tahmini; gözlemler arası doğrusal ara değer, birkaç dk sapabilir):")
                for p in tr["passages"][:max_stops]:
                    out.append(f"      {p['sira']:>3}  {p['durak']:<6} {p['ad'][:38]:<38} ~{fmt_ts(p['t'], False)}")
            else:
                out.append("    Durak geçişi tahmini için yeterli gözlem yok.")
    return "\n".join(out)


def cmd_sorgu(args):
    conn = connect()
    try:
        day = parse_day(args.tarih)
        when = to_epoch(day, parse_time(args.saat)) if args.saat else None
    except ValueError as e:
        print(e)
        return 2
    if when is None:
        print(format_day(query_day(conn, args.arac, day)))
    else:
        print(format_result(query_vehicle(conn, args.arac, when, args.tolerans)))
    return 0


def cmd_rapor(args):
    conn = connect()
    day = parse_day(args.tarih) if args.tarih else datetime.now(TZ).date() - timedelta(days=1)
    p1, p2, n = write_report(conn, day)
    print(f"{day}: {n} araç.\n  {p1}\n  {p2}")
    return 0


def cmd_araclar(args):
    conn = connect()
    q = f"%{norm(args.ara)}%" if args.ara else "%"
    rows = conn.execute(
        "SELECT plaka, MAX(arac_no), GROUP_CONCAT(DISTINCT hat), MAX(last_ts) FROM stints "
        "WHERE plaka LIKE ? OR REPLACE(REPLACE(UPPER(arac_no),'-',''),' ','') LIKE ? "
        "GROUP BY plaka ORDER BY MAX(last_ts) DESC LIMIT ?",
        (q, q, args.limit),
    ).fetchall()
    for plaka, arac_no, hats, last in rows:
        print(f"{pretty_plate(plaka):<12} filo no: {arac_no or '-':<10} hatlar: {hats}  son: {fmt_ts(last)}")
    print(f"({len(rows)} araç)")
    return 0


def cmd_alias(args):
    conn = connect()
    plaka = norm(args.plaka)
    conn.execute("INSERT OR REPLACE INTO aliases (alias, plaka) VALUES (?, ?)", (norm(args.kod), plaka))
    conn.commit()
    print(f"{args.kod} -> {pretty_plate(plaka)} bağlandı.")
    return 0


# --------------------------------------------------------------------------
# Web arayüzü
# --------------------------------------------------------------------------
def make_handler():
    import ego_web
    return ego_web.make_handler(sys.modules[__name__])


def open_browser(host, port):
    """Windows'ta uygulama penceresi (Edge/Chrome --app), değilse varsayılan tarayıcı."""
    import webbrowser
    url = f"http://{host}:{port}"
    if os.name == "nt":
        import subprocess
        pf = [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""), os.environ.get("LocalAppData", "")]
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            for base in pf:
                exe = os.path.join(base, rel) if base else ""
                if exe and os.path.isfile(exe):
                    try:
                        subprocess.Popen([exe, f"--app={url}"])
                        return
                    except OSError:
                        pass
    webbrowser.open(url)


def make_server(host, port):
    """Sunucu; port doluysa None (büyük olasılıkla zaten çalışıyor)."""
    try:
        return ThreadingHTTPServer((host, port), make_handler())
    except OSError:
        return None


def cmd_serve(args):
    srv = make_server(args.host, args.port)
    if srv is None:
        print(f"Port {args.port} dolu; arayüz zaten açık olabilir: http://{args.host}:{args.port}")
        if getattr(args, "ac", False):
            open_browser(args.host, args.port)
        return 0
    print(f"Arayüz: http://{args.host}:{args.port}  (durdurmak için Ctrl-C)")
    if getattr(args, "ac", False):
        open_browser(args.host, args.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def add_run_args(p):
    p.add_argument("--interval", type=float, default=5, help="tarama aralığı (dk); kısaldıkça durak saatleri daha doğru, EGO sunucusuna yük artar")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--delay", type=float, default=0.3)
    p.add_argument("--raw-days", type=int, default=0, help="ham konum kayıtlarını kaç gün tut (0 = hiç silme, varsayılan)")
    p.add_argument("--no-raw", action="store_true", help="ham konum tutma, sadece hat aralıklarını kaydet")
    p.add_argument("--stale-min", type=int, default=20, help="konum zamanı N dk'dan eski araçları yok say (0=kapalı)")
    p.add_argument("--once", action="store_true", help="tek tur tara ve çık (cron için)")
    p.add_argument("--max-minutes", type=float, default=0,
                   help="N dakika döngüde çalışıp çık (cron en az 15 dk ise: --max-minutes 14 ile kesintisiz tarama)")
    p.add_argument("--idle-max", type=int, default=2,
                   help="boş hat en fazla (1+N) tur seyrek taransın; cron dakikada bir ise 10 önerilir")


def cmd_hepsi(args):
    """Toplayıcıyı arka plan iş parçacığında, web arayüzünü ana iş parçacığında çalıştırır."""
    conn = connect()
    ready = conn.execute("SELECT 1 FROM line_route LIMIT 1").fetchone()
    conn.close()
    if not ready:
        print("Hat rotaları (durak sırası ve adları) çıkarılıyor, birkaç dakika sürer ...")
        rc = main((["--insecure"] if args.insecure else []) + ["init"])
        if rc != 0 or STOP.is_set():
            return rc or 1
    srv = make_server(args.host, args.port)
    if srv is None:
        print(f"Port {args.port} dolu: toplayıcı zaten çalışıyor olabilir. Arayüz açılıyor.")
        if args.ac:
            open_browser(args.host, args.port)
        return 0
    collector = threading.Thread(target=cmd_run, args=(args,), daemon=True)
    collector.start()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Arayüz: http://{args.host}:{args.port}  (tarayıcıdan açın). Durdurmak için Ctrl-C.")
    if args.ac:
        open_browser(args.host, args.port)
    try:
        while not STOP.is_set() and collector.is_alive():
            STOP.wait(1)
    except KeyboardInterrupt:
        pass
    STOP.set()
    srv.shutdown()
    collector.join(timeout=30)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="EGO Filo Takip", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--insecure", action="store_true",
                    help="TLS sertifikasını doğrulama (yalnızca sertifika hatası alırsanız)")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    p = sub.add_parser("probe", help="uç noktaları dene")
    p.add_argument("--durak", default="10940")
    p.add_argument("--hat", default="481")
    p.set_defaults(fn=cmd_probe)

    p = sub.add_parser("init", help="hat/durak eşleşmesini çıkar")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--delay", type=float, default=0.3, help="istek başına bekleme (sn)")
    p.add_argument("--limit", type=int, default=0, help="en fazla N hat/durak (test için)")
    p.add_argument("--no-raw", action="store_true")
    p.add_argument("--yontem", choices=["saatler", "durak"], default="saatler",
                   help="saatler: her hattın Hareket Saatleri sayfasından (hızlı, varsayılan); "
                        "durak: tüm durakları Otobusler servisiyle tarar (yavaş, yedek yöntem)")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("saatler", help="hat bilgisi ve hareket saatlerini çek/tazele")
    p.add_argument("--gun", type=float, default=7, help="bu günden eski kayıtları tazele")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=lambda a: print("Tazelenen hat:", refresh_timetables(Http(a.insecure), a.gun, 0.8, a.limit)) or 0)

    p = sub.add_parser("run", help="sürekli toplayıcı")
    add_run_args(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("hepsi", help="toplayıcı + web arayüzü tek komutta (tablet/telefon için ideal)")
    add_run_args(p)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--ac", action="store_true", help="başlayınca arayüzü pencerede/tarayıcıda aç")
    p.set_defaults(fn=cmd_hepsi)

    p = sub.add_parser("sorgu", help="filo/plaka + saat ile hat bul")
    p.add_argument("arac", help="EGO-22-370 veya 06DHC251")
    p.add_argument("--tarih", default="", help="2026-11-02 (boşsa bugün)")
    p.add_argument("--saat", default="", help="14:35 (boşsa o günün tüm seferleri ve durak saatleri)")
    p.add_argument("--tolerans", type=int, default=30, help="dakika")
    p.set_defaults(fn=cmd_sorgu)

    p = sub.add_parser("rapor", help="günlük CSV raporu")
    p.add_argument("--tarih", default="", help="boşsa dün")
    p.set_defaults(fn=cmd_rapor)

    p = sub.add_parser("araclar", help="araç ara/listele")
    p.add_argument("--ara", default="")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(fn=cmd_araclar)

    p = sub.add_parser("alias", help="filo kodunu plakaya bağla")
    p.add_argument("kod")
    p.add_argument("plaka")
    p.set_defaults(fn=cmd_alias)

    p = sub.add_parser("serve", help="yerel web arayüzü")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--ac", action="store_true", help="arayüzü tarayıcıda aç")
    p.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:  # pythonw: konsol yok, günlüğe yaz
        _log = open(os.path.join(HERE, "hepsi.log"), "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stdout or _log
        sys.stderr = sys.stderr or _log
    sys.exit(main())
