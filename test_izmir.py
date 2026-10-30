"""İzmir toplayıcısı için sahte CKAN + canlı servis testi (gerçek servise istek atmaz)."""
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

tmp = tempfile.mkdtemp()
HATLAR = [{"HAT_NO": 446, "HAT_ADI": "TEST - HAT", "HAT_BASLANGIC": "A", "HAT_BITIS": "B"}, {"HAT_NO": 5, "HAT_ADI": "BESHAT", "HAT_BASLANGIC": "C", "HAT_BITIS": "D"}]
DURAK = [{"DURAK_ID": 10005, "DURAK_ADI": "Bahribaba", "ENLEM": 38.41, "BOYLAM": 27.12, "DURAKTAN_GECEN_HATLAR": "5, 446, 999"},
         {"DURAK_ID": 10006, "DURAK_ADI": "Yok", "ENLEM": 0, "BOYLAM": 0, "DURAKTAN_GECEN_HATLAR": "446"}]
SAAT = [{"HAT_NO": 446, "TARIFE_ID": 1, "GIDIS_SAATI": "06:05", "DONUS_SAATI": "06:40"}, {"HAT_NO": 446, "TARIFE_ID": 3, "GIDIS_SAATI": "07:00", "DONUS_SAATI": ""}]
RES = {"eshot-otobus-hat-listesi": ("r1", HATLAR), "eshot-otobus-duraklari": ("r2", DURAK), "otobus-hareket-saatleri": ("r3", SAAT)}
LIVE = {"HataMesaj": "", "HatOtobusKonumlari": [
    {"OtobusId": 11848, "Yon": 0, "KoorY": "0", "KoorX": "0"},
    {"OtobusId": 2212, "Yon": 1, "KoorY": "27,070275", "KoorX": "38,48502833"},
    {"OtobusId": 2212, "Yon": 1, "KoorY": "27,07457833", "KoorX": "38,47509333"}], "HataVarMi": False}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path
        if "package_show" in p:
            name = re.search(r"id=([\w-]+)", p).group(1)
            out = {"result": {"resources": [{"id": RES[name][0], "datastore_active": True}]}}
        elif "datastore_search" in p:
            rid = re.search(r"resource_id=(\w+)", p).group(1)
            off = int(re.search(r"offset=(\d+)", p).group(1))
            rows = [v[1] for v in RES.values() if v[0] == rid][0]
            out = {"result": {"records": rows[off:off + 20000]}}
        elif "hatotobuskonumlari" in p:
            out = LIVE if p.endswith("/446") else {"HatOtobusKonumlari": []}
        else:
            self.send_response(404); self.end_headers(); return
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = HTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_port
os.environ.update(IZMIR_DB=os.path.join(tmp, "iz.db"), IZMIR_CKAN=base, IZMIR_LIVE=base + "/api/iztek")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import izmir_tracker as Z  # noqa: E402

fail = 0


def ok(c, m):
    global fail
    print(("✓ " if c else "✗ ") + m)
    fail += 0 if c else 1


ok(Z.main(["init"]) == 0, "init")
c = Z.connect()
ok(c.execute("SELECT COUNT(*) FROM lines").fetchone()[0] == 2, "2 hat")
ok(c.execute("SELECT lat FROM stops_geo WHERE durak='10005'").fetchone()[0] == 38.41, "durak koordinatı; 0,0 olan atlandı: %d" % c.execute("SELECT COUNT(*) FROM stops_geo").fetchone()[0])
ok(sorted(r[0] for r in c.execute("SELECT hat FROM line_stops WHERE durak='10005'")) == ["446", "5"], "hat-durak bağı (bilinmeyen 999 atlandı)")
ok(Z.main(["saatler"]) == 0, "saatler")
ok(sorted(c.execute("SELECT gun, yon, saat FROM line_times WHERE hat='446'")) == [("haftaici", 0, "06:05"), ("haftaici", 1, "06:40"), ("pazar", 0, "07:00")], "saat satırları")
v = Z.line_vehicles(Z.E.Http(False), "446")
ok(len(v) == 1 and v[0]["id"] == "2212" and abs(v[0]["lat"] - 38.47509333) < 1e-6 and abs(v[0]["lng"] - 27.07457833) < 1e-6, "canlı: virgüllü ondalık, enlem=KoorX, tekrar/0 temizlendi")
ok(Z.main(["run", "--once", "--delay", "0"]) == 0, "run --once")
ok(c.execute("SELECT COUNT(*) FROM stints WHERE hat='446'").fetchone()[0] == 1, "stint kaydı")
print("\nSONUÇ:", "TÜM TESTLER GEÇTİ" if not fail else f"{fail} HATA")
sys.exit(1 if fail else 0)
