"""İETT toplayıcısı için sahte SOAP sunucusuyla test (gerçek servise istek atmaz)."""
import html
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

tmp = tempfile.mkdtemp()
FLEET = [{"Operator": "X", "Garaj": None, "KapiNo": "C-456", "Saat": "13:38:58", "Boylam": "29.36", "Enlem": "40.82", "Hiz": "23", "Plaka": "34 AB 123"},
         {"Operator": "X", "Garaj": None, "KapiNo": "C-454", "Saat": "13:38:57", "Boylam": "29.37", "Enlem": "40.83", "Hiz": "0", "Plaka": "34 AB 124"}]
HATOTO = [{"kapino": "C-456", "boylam": "29.36", "enlem": "40.82", "hatkodu": "500T", "guzergahkodu": "500T_G_D0",
           "hatad": "TUZLA - 4. LEVENT", "yon": "4.LEVENT METRO", "son_konum_zamani": "2026-10-30 13:38:59", "yakinDurakKodu": "401351"}]
STOPS_XML = ("<NewDataSet xmlns=\"\">" + "".join(
    f"<Table><HATKODU>500T</HATKODU><YON>{y}</YON><SIRANO>{i}</SIRANO><DURAKKODU>{c}</DURAKKODU><DURAKADI>D{c}</DURAKADI>"
    f"<XKOORDINATI>29.0{i}</XKOORDINATI><YKOORDINATI>41.0{i}</YKOORDINATI></Table>"
    for y, i, c in (("G", 1, "301341"), ("G", 2, "401351"), ("D", 1, "401351"))) + "</NewDataSet>")


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        m = re.search(r"<(\w+) xmlns=\"http://tempuri.org/\"", body).group(1)
        if m == "GetFiloAracKonum_json":
            res = json.dumps(FLEET)
        elif m == "GetHatOtoKonum_json":
            res = json.dumps(HATOTO if "<HatKodu>500T<" in body else [])
        elif m == "GetHat_json":
            res = json.dumps([{"SHATKODU": "500T", "SHATADI": "TUZLA - 4. LEVENT"}, {"SHATKODU": "34", "SHATADI": "AVCILAR"}])
        elif m == "DurakDetay_GYY":
            res = STOPS_XML if "<hat_kodu>500T<" in body else "<NewDataSet xmlns=\"\"/>"
        elif m == "GetPlanlananSeferSaati_json":
            res = json.dumps([{"SHATKODU": "500T", "SYON": "G", "SGUNTIPI": "I", "DT": "1900-01-01 06:15:00"},
                              {"SHATKODU": "500T", "SYON": "D", "SGUNTIPI": "P", "DT": "07:40"}]) if "<HatKodu>500T<" in body else "[]"
        else:
            res = "[]"
        out = (f'<?xml version="1.0"?><soap:Envelope xmlns:soap="x"><soap:Body><{m}Response xmlns="http://tempuri.org/">'
               f"<{m}Result>{html.escape(res)}</{m}Result></{m}Response></soap:Body></soap:Envelope>").encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


srv = HTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["IETT_BASE"] = f"http://127.0.0.1:{srv.server_address[1]}/iett"
os.environ["IETT_DB"] = os.path.join(tmp, "i.db")
os.environ["EGO_DB"] = os.path.join(tmp, "e.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iett_tracker as T  # noqa: E402

ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("✓ " if cond else "✗ ") + name)


h = T.E.Http(False)
check("filo okundu", len(T.fleet(h)) == 2 and T.fleet(h)["C-456"]["plaka"] == "34 AB 123")
check("hat listesi", T.list_lines(h)[0] == ("500T", "TUZLA - 4. LEVENT"))
st = T.line_stops(h, "500T")
check("duraklar koordinatlı", len(st) == 3 and st[0][4] == 41.01 and st[0][5] == 29.01)
check("yön ayrıştırma", T.yon_of(HATOTO[0]) == "G")
T.main(["init"])
c = T.connect()
check("init: yön başına hat", {r[0] for r in c.execute("SELECT hat FROM lines")} == {"500T G", "500T D"})
check("init: durak koordinatı", c.execute("SELECT lat FROM stops_geo WHERE durak='301341'").fetchone()[0] == 41.01)
T.main(["run", "--once"])
c = T.connect()
r = c.execute("SELECT plaka, arac_no, hat, sira, lat FROM sightings").fetchall()
check("run: kayıt (plaka, kapı no, hat-yön, durak sırası)", r and r[0][:4] == ("34AB123", "C-456", "500T G", 2))
check("run: stint", c.execute("SELECT COUNT(*) FROM stints WHERE hat='500T G'").fetchone()[0] == 1)
check("run: son tur meta", json.loads(c.execute("SELECT v FROM meta WHERE k='last_cycle'").fetchone()[0])["fleet"] == 2)
T.main(["saatler"])
c = T.connect()
check("planlanan saatler", sorted(c.execute("SELECT hat, gun, saat FROM line_times").fetchall()) == [("500T D", "pazar", "07:40"), ("500T G", "haftaici", "06:15")])
check("run: tur bitince ilerleme kaydı temizlendi", c.execute("SELECT COUNT(*) FROM meta WHERE k='progress'").fetchone()[0] == 0)
# ilerleme yüzdesi web arayüzünde
import urllib.request
import ego_web  # noqa: F401,E402
T._progress(c, 50, 100, 40, 1, int(__import__("time").time()) - 60)
web = T.E.ThreadingHTTPServer(("127.0.0.1", 0), T.E.make_handler())
threading.Thread(target=web.serve_forever, daemon=True).start()
rq = urllib.request.Request("http://127.0.0.1:%d/durum" % web.server_address[1]); rq.add_header("Cookie", "sehir=istanbul")
pg = urllib.request.urlopen(rq).read().decode()
check("durum sayfasında tarama yüzdesi", "Tarama sürüyor" in pg and "%50" in pg and "50/100 hat" in pg)
print("\nSONUÇ:", "TÜM TESTLER GEÇTİ" if ok else "BAŞARISIZ")
sys.exit(0 if ok else 1)
