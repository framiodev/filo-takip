"""Sahte EGO sunucusuyla uçtan uca mantık testi (gerçek EGO'ya istek atmaz)."""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

tmp = tempfile.mkdtemp()
HERE = os.path.dirname(os.path.abspath(__file__))

LINES = {"481": "UYANIŞ-BALGAT", "523-6": "ÇAYYOLU-KIZILAY"}
STOP_LINES = {"10940": ["481", "523-6"], "10017": ["481"], "10019": []}
BUSES = {
    "481": [{"arac_no": "22-370", "plaka_no": "06 DHC 251", "hiz": "31", "lat": "39.91", "lng": "32.85", "konum_tarihi": "",
             "durak_no": "10940", "onceki_durak_no": "10017", "durak_sira_no": "5", "doluluk": {"message": "no data"}}],
    "523-6": [{"arac_no": "21-045", "plaka_no": "06 ABC 123", "hiz": "0", "lat": "39.88", "lng": "32.80", "konum_tarihi": ""}],
}
STATE = {"swap": False}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        posted = self.rfile.read(n).decode()
        if self.path.startswith("/HareketSaatleri"):
            hat = parse_qs(posted).get("hat_no1", [""])[0]
            stops = [s for s, hats in STOP_LINES.items() if hat in hats]
            rows = "".join(f"<tr><td>{i+1}</td><td>{s}</td><td>DURAK {s}</td><td>ADRES</td></tr>" for i, s in enumerate(stops))
            page = ("<table><tr><td>Hat Adı</td><td>:</td><td>X</td></tr></table>"
                    "<table><tr><td>06:00</td><td>07:00</td><td>08:00</td></tr></table>"
                    f"<table>{rows}</table>")
            b = page.encode()
        else:  # eski AjaxData adresleri canlı sitede 404 veriyor
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/hareketsaatleri"):
            opts = '<option value="0">OTOBÜS</option>' + "".join(
                f'<option value="{k}">({k} ) - {v}</option>' for k, v in LINES.items())
            page = ('<select id="hat_liste_otobus" name="hat_no1">' + opts + '</select>'
                    '<select id="hat_liste_metro" name="hat_no2"><option value="0">METRO</option>'
                    '<option value="M1-D">(M1-D ) - ÇAYYOLU-SİNCAN</option></select>')
            b = page.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if q.get("FNC") == "Otobusler":
            rows = []
            for hat in STOP_LINES.get(q.get("DURAK"), []):
                for b in BUSES.get(hat, []):
                    rows.append({**b, "hat_no": hat, "hat_kisa_kod": hat})
                if not BUSES.get(hat):
                    rows.append({"arac_no": "-", "hat_no": hat, "sure": "12:30"})
            return self._json({"table": rows, "message": "", "status": "TRUE"})
        if q.get("FNC") == "Otobus":
            hat = q.get("HAT")
            buses = BUSES.get(hat, [])
            if STATE["swap"] and hat == "523-6":  # araç hat değiştirmiş gibi
                buses = BUSES["481"]
            rows = [{**b, "hat_no": hat, "hat_kisa_kod": hat} for b in buses]
            return self._json({"table": rows, "message": "", "status": "TRUE"})
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


srv = HTTPServer(("127.0.0.1", 0), Mock)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

os.environ["EGO_API_BASE"] = f"http://127.0.0.1:{port}/mblSrv14/service.asp"
os.environ["EGO_WEB_BASE"] = f"http://127.0.0.1:{port}"
os.environ["EGO_DB"] = os.path.join(tmp, "t.db")
os.environ["EGO_REPORT_DIR"] = os.path.join(tmp, "raporlar")
stops = os.path.join(tmp, "stops.txt")
open(stops, "w").write("10940\n10017\n10019\n")
os.environ["EGO_STOPS"] = stops

sys.path.insert(0, HERE)
import ego_tracker as E  # noqa: E402

ok = True


def check(name, cond):
    global ok
    print(("✓ " if cond else "✗ ") + name)
    ok = ok and cond


# probe
check("probe", E.main(["probe", "--durak", "10940", "--hat", "481"]) == 0)
# init
check("init", E.main(["init", "--delay", "0.01"]) == 0)
conn = E.connect()
check("hat listesi 2 hat (başlık ve metro hariç)", conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0] == 2)
check("481 durakları", {r[0] for r in conn.execute("SELECT durak FROM line_stops WHERE hat='481'")} == {"10940", "10017"})
check("saatler yöntemi: 523-6 durağı", {r[0] for r in conn.execute("SELECT durak FROM line_stops WHERE hat='523-6'")} == {"10940"})
# yedek yöntem: durak taraması (yeni DB'ye ek olarak) da çalışmalı
check("init --yontem durak", E.main(["init", "--yontem", "durak", "--delay", "0.01"]) == 0)
check("init sırasında araç görüldü", conn.execute("SELECT COUNT(*) FROM stints").fetchone()[0] >= 2)

# run: bir tur çalıştır, sonra durdur
threading.Timer(2.5, E.STOP.set).start()
check("run", E.main(["run", "--interval", "10", "--delay", "0.01"]) == 0)
E.STOP.clear()

# elle zaman damgalı kayıtlar ekleyerek gün boyu senaryo kur (aynı araç iki hatta)
conn = E.connect()
base = E.to_epoch(E.parse_day("2026-11-02"), E.parse_time("08:00"))
row = {"arac_no": "22-370", "plaka_no": "06 DHC 251", "lat": "39.9", "lng": "32.8", "hiz": "20"}
for i in range(0, 12):          # 08:00-09:50 hat 481 (10 dk aralık)
    E.record_sighting(conn, base + i * 600, row, "481", 1800)
for i in range(0, 6):           # 10:30-11:20 hat 523-6
    E.record_sighting(conn, base + 9000 + i * 600, row, "523-6", 1800)
conn.commit()

stints = conn.execute("SELECT hat, first_ts, last_ts, n FROM stints WHERE plaka='06DHC251' AND first_ts>=? ORDER BY first_ts", (base,)).fetchall()
check("hat 481 tek aralık", stints[0][0] == "481" and stints[0][3] == 12 and stints[0][2] - stints[0][1] == 11 * 600)
check("hat değişince yeni aralık", stints[1][0] == "523-6")

d = E.parse_day("2026-11-02")
q1 = E.query_vehicle(conn, "EGO-22-370", E.to_epoch(d, E.parse_time("09:15")))
check("filo kodu ile bulundu (tam)", q1["kind"] == "tam" and q1["vehicles"][0]["items"][0]["hat"] == "481"
      and q1["vehicles"][0]["items"][0]["conf"] == "kesin")
q2 = E.query_vehicle(conn, "06 dhc 251", E.to_epoch(d, E.parse_time("10:45")))
check("plaka ile 2. hat", q2["vehicles"][0]["items"][0]["hat"] == "523-6")
q3 = E.query_vehicle(conn, "06DHC251", E.to_epoch(d, E.parse_time("13:30")), 30)
check("kayıt yoksa önceki/sonraki gösterilir", not q3["vehicles"][0]["items"] and q3["vehicles"][0]["before"] is not None)
q4 = E.query_vehicle(conn, "EGO-99-999", E.to_epoch(d, E.parse_time("09:00")))
check("bilinmeyen araç", q4["vehicles"] == [])
old = E.query_vehicle(conn, "06DHC251", base - 40 * 86400)
check("kayıt öncesi uyarısı", any("önce" in w for w in old["warnings"]))
print(E.format_result(q1))

E.main(["alias", "EGO-22-371", "06 DHC 251"])
q5 = E.query_vehicle(conn, "ego-22-371", E.to_epoch(d, E.parse_time("09:15")))
check("alias çalışıyor", q5["kind"] == "alias" and q5["vehicles"][0]["items"])

# --- durak bilgisi kaydı (mock canlı satırından) ve sütun geçişi ---
r = conn.execute("SELECT durak, sira, onceki FROM sightings WHERE plaka='06DHC251' AND sira IS NOT NULL LIMIT 1").fetchone()
check("gözleme durak/sıra yazıldı", r == ("10940", 5, "10017"))
import sqlite3
old = os.path.join(tmp, "eski.db")
oc = sqlite3.connect(old)
oc.execute("CREATE TABLE sightings (ts INTEGER NOT NULL, plaka TEXT NOT NULL, arac_no TEXT, hat TEXT NOT NULL, lat REAL, lng REAL, hiz REAL)")
oc.commit(); oc.close()
mc = E.connect(old)
cols = {x[1] for x in mc.execute("PRAGMA table_info(sightings)")}
check("eski veritabanına yeni sütunlar eklendi", {"durak", "sira", "onceki", "kts"} <= cols)
mc.close()

# --- gün sorgusu: sefer ayrımı ve durak geçiş saatleri ---
day2 = E.parse_day("2026-11-03")
b2 = E.to_epoch(day2, E.parse_time("08:00"))
for k in range(1, 21):
    conn.execute("INSERT OR REPLACE INTO line_route (hat, sira, durak, ad) VALUES ('481', ?, ?, ?)", (k, f"{20000+k}", f"DURAK-{k}"))
conn.commit()


def live(sira, t, prev):
    return {"arac_no": "09-524", "plaka_no": "06 BT 3809", "lat": "39.9", "lng": "32.8", "hiz": "20",
            "durak_no": str(20000 + sira), "onceki_durak_no": str(20000 + sira - 1), "durak_sira_no": str(sira),
            "konum_tarihi": E.datetime.fromtimestamp(t, E.TZ).strftime("%d.%m.%Y %H:%M:%S")}


for i, sira in enumerate([3, 6, 10, 14, 18]):          # sefer 1: 08:00-08:20, hat 481
    t = b2 + i * 300
    E.record_sighting(conn, t, live(sira, t, 0), "481", 1800)
for i, sira in enumerate([2, 5, 9]):                    # sefer 2: aynı hat, hat başına dönmüş (sıra geri sarıyor)
    t = b2 + 3600 + i * 300
    E.record_sighting(conn, t, live(sira, t, 0), "481", 1800)
for i, sira in enumerate([4, 8]):                       # sefer 3: başka hat
    t = b2 + 9000 + i * 300
    E.record_sighting(conn, t, live(sira, t, 0), "523-6", 1800)
conn.commit()

res = E.query_day(conn, "09-524", day2)
trips = res["vehicles"][0]["trips"] if res["vehicles"] else []
check("filo no 09-524 bulundu", res["kind"] == "tam" and len(res["vehicles"]) == 1)
check("3 sefer ayrıştırıldı (aynı hatta tur dönüşü dahil)", [t["hat"] for t in trips] == ["481", "481", "523-6"])
p1_ = {p["sira"]: p for p in trips[0]["passages"]}
check("sefer 1: 3..17. duraklar tahmin edildi", sorted(p1_) == list(range(3, 18)))
# sıra 3 -> 6 arası: 08:00 (p=2.5) .. 08:05 (p=5.5): durak 4 = 08:00 + (4-2.5)/3*300 = 08:02:30
check("durak geçiş saati doğrusal ara değer", abs(p1_[4]["t"] - (b2 + 150)) <= 1)
check("geçiş saatleri artan", all(a["t"] < b["t"] for a, b in zip(trips[0]["passages"], trips[0]["passages"][1:])))
check("durak adı rotadan geldi", p1_[4]["ad"] == "DURAK-4")
txt = E.format_day(res)
check("gün çıktısı: SEFER 1/2/3 ve durak adı", all(s in txt for s in ("SEFER 1", "SEFER 2", "SEFER 3", "DURAK-4", "09-524")))
res_none = E.query_day(conn, "09-524", E.parse_day("2026-11-10"))
check("kayıt olmayan gün temiz mesaj", "kayıt yok" in E.format_day(res_none).lower() or res_none["warnings"])

p1, p2, n = E.write_report(conn, d)
rep = open(p1, encoding="utf-8-sig").read()
check("rapor CSV", "06 DHC 251" in rep and "523-6" in rep and "481" in rep)
print(open(p2, encoding="utf-8-sig").read())

# web arayüzü
web = E.ThreadingHTTPServer(("127.0.0.1", 0), E.make_handler())
wp = web.server_address[1]
threading.Thread(target=web.serve_forever, daemon=True).start()
page = urllib.request.urlopen(f"http://127.0.0.1:{wp}/?q=EGO-22-370&tarih=2026-11-02&saat=09:15&tol=30").read().decode()
check("web sorgu sonucu", "<b>481</b>" in page)
page2 = urllib.request.urlopen(f"http://127.0.0.1:{wp}/?q=%3Cscript%3E&tarih=2026-11-02&saat=09:15").read().decode()
check("web XSS kaçışı", "<script>" not in page2.split("<h1>")[1])
page4 = urllib.request.urlopen(f"http://127.0.0.1:{wp}/?q=09-524&tarih=2026-11-03&saat=").read().decode()
check("web: saat boşsa tüm gün (seferler)", "Sefer 1" in page4 and "DURAK-4" in page4)

import json as _j
api = _j.loads(urllib.request.urlopen(f"http://127.0.0.1:{wp}/api/araclar?saat=720").read().decode())
check("harita API araç döndürdü", api["n"] >= 1 and "la" in api["araclar"][0])
hp_ = urllib.request.urlopen(f"http://127.0.0.1:{wp}/harita").read().decode()
check("harita sayfası", "leaflet" in hp_ and 'id="map"' in hp_)
gun_ = urllib.request.urlopen(f"http://127.0.0.1:{wp}/gun?tarih=2026-11-03").read().decode()
check("gün özeti açılıyor", "<h1>Gün özeti" in gun_ and "Hata:" not in gun_)
check("araç durum rozeti", "Listede yok" in page4 or "Şu an hatta" in page4)
_cj = _j.loads(urllib.request.urlopen(f"http://127.0.0.1:{wp}/api/canli?hat=481").read().decode())
check("anlık hat sorgusu", len(_cj.get("araclar", [])) >= 1 and "la" in _cj["araclar"][0])
_cx = _j.loads(urllib.request.urlopen(f"http://127.0.0.1:{wp}/api/canli?hat=YOKYOK").read().decode())
check("anlık sorgu: bilinmeyen hat", _cx.get("araclar") == [] and "hata" in _cx)
_rc = E.main(["run", "--once", "--interval", "1", "--idle-max", "10", "--delay", "0.01"])
_c2 = E.connect(); _sch = _c2.execute("SELECT v FROM meta WHERE k='schedule'").fetchone(); _c2.close()
check("--once zamanlamayı saklıyor", _rc == 0 and _sch and "481" in _j.loads(_sch[0])["nd"])
_t0 = time.time()
_rc2 = E.main(["run", "--max-minutes", "0.05", "--interval", "0.02", "--delay", "0.01"])
check("--max-minutes süre dolunca çıkıyor", _rc2 == 0 and time.time() - _t0 < 30)
import ego_web as _ew
_h = _ew.make_handler(E)
check("model kuralı (ön ek)", "MAN Lion" in page4)
_api2 = _j.loads(urllib.request.urlopen(f"http://127.0.0.1:{wp}/api/araclar?saat=720").read().decode())
check("api model alanı", all("m" in a for a in _api2["araclar"]))
import urllib.parse as _up
_req = urllib.request.Request(f"http://127.0.0.1:{wp}/modeller/kaydet", data=_up.urlencode(
    {"anahtar": "22-370", "marka_model": "TEST Model <b>", "durum": "kesin", "kaynak": "deneme", "url": "https://example.org/x"}).encode())
_req.add_header("Origin", f"http://127.0.0.1:{wp}")
class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
try:
    urllib.request.build_opener(_NoRedir).open(_req)
except urllib.error.HTTPError as _e:
    check("modeller kaydet (POST → yönlendirme)", _e.code == 303)
_mp = urllib.request.urlopen(f"http://127.0.0.1:{wp}/modeller").read().decode()
check("modeller sayfası kaydı gösteriyor (XSS kaçışlı)", "TEST Model &lt;b&gt;" in _mp and "TEST Model <b>" not in _mp)
_p22 = urllib.request.urlopen(f"http://127.0.0.1:{wp}/?q=22-370&tarih=2026-11-02").read().decode()
check("DB modeli sorguda görünüyor", "TEST Model" in _p22)
_bad = urllib.request.Request(f"http://127.0.0.1:{wp}/modeller/sil", data=b"anahtar=22-370")
_bad.add_header("Origin", "http://evil.example")
try:
    urllib.request.urlopen(_bad); check("farklı kaynaktan POST reddedilir", False)
except urllib.error.HTTPError as _e:
    check("farklı kaynaktan POST reddedilir", _e.code == 403)
check("durum satırı (toplayıcı çalışıyor)", "Toplayıcı çalışıyor" in page)

# hepsi: tek komutla toplayıcı + arayüz (mevcut DB hazır olduğu için init atlanır)
import socket
s = socket.socket(); s.bind(("127.0.0.1", 0)); hp = s.getsockname()[1]; s.close()
hep = threading.Thread(target=E.main, args=(["hepsi", "--port", str(hp), "--delay", "0.01", "--interval", "10"],))
hep.start()
time.sleep(3)
page3 = urllib.request.urlopen(f"http://127.0.0.1:{hp}/?q=06DHC251&tarih=2026-11-02&saat=09:15").read().decode()
check("hepsi: arayüz açıldı", "EGO Filo Takip" in page3 and "<b>481</b>" in page3)
E.STOP.set()
hep.join(timeout=40)
check("hepsi: temiz kapandı", not hep.is_alive())
E.STOP.clear()

E.main(["araclar", "--ara", "370"])
print("\nSONUÇ:", "TÜM TESTLER GEÇTİ" if ok else "BAŞARISIZ")
sys.exit(0 if ok else 1)
