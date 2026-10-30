#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Referans tarayıcı: Ulaşım Platformu (forum.ulasimplatformu.com) Ankara bölümündeki
fotoğraf açıklamalarını (yalnızca METİN) okur, filo kodu / plaka -> marka-model eşleşmesini
sistemin kalıcı tablosuna (arac_bilgi) yazar.

 * Fotoğraf indirmez; sadece "12-443 / 06 DY 3503 > hat > yer" biçimindeki açıklama satırlarını okur.
 * EGO konuları: konu başlığı = marka/model (ör. "EGO / Man Lion's Classic CNG").
 * ÖHO / AHOK konuları: satır biçimi "MODEL > 06 HO 1175 > hat > yer"; 06 HO plakaları da kaydedilir.
 * Kaldığı yerden devam eder (meta tablosunda sayfa sayacı). Elle girilmiş kayıtların üzerine yazmaz.
 * Siteye nazik davranır: istekler arası bekleme, tek bağlantı, kendini tanıtan User-Agent.

Kullanım:
  python3 referans_tara.py              # kaldığı yerden tara (tam tarama ilk seferde uzun sürer)
  python3 referans_tara.py --max-minutes 12   # cron için süre sınırı
  python3 referans_tara.py --yeni       # yalnız her konunun son 2 sayfasını (günlük bakım)
  python3 referans_tara.py --kuru       # veritabanına yazmadan ne bulacağını göster
"""
import argparse
import html as htmllib
import re
import sys
import time
import urllib.parse
import urllib.request

import ego_tracker as E

BASE = "https://forum.ulasimplatformu.com/"
FIDS = (48,)  # Ankara
UA = "UlasimArsiv-FiloTakip/1.0 (+http://filo.ulasimarsiv.com; hobi, ticari degil)"
KAYNAK = "Ulaşım Platformu (otomatik)"

RE_PLAKA = re.compile(r"\b(06)\s?([A-ZÇĞİÖŞÜ]{1,3})\s?(\d{2,4})\b")
RE_FILO = re.compile(r"\b(\d{2}-\d{3,4})\b")

# Konu başlığı -> (marka_model, ekleme). Sözlükte yoksa başlıktan türetilir.
BASLIK_MODEL = (
    (r"otokar kent lf.*k[öo]r[üu]kl", "Otokar Kent LF Körüklü"),
    (r"otokar kent lf", "Otokar Kent LF (Yeni Jenerasyon)"),
    (r"conecto.*k[öo]r[üu]kl", "Mercedes-Benz Conecto Körüklü"),
    (r"conecto", "Mercedes-Benz Conecto (Yeni Jenerasyon)"),
    (r"lion.s city.*k[öo]r[üu]kl", "MAN Lion's City CNG Körüklü"),
    (r"lion.s classic cng", "MAN Lion's Classic CNG (A74 / SL313)"),
    (r"lion.s classic dizel", "MAN Lion's Classic Dizel"),
    (r"interliner", "Isuzu Interliner"),
    (r"sileo", "Bozankaya Sileo S 12 Elektrikli"),
    (r"karsan atak", "Karsan Atak"),
    (r"d[öo]n[üu][şs]t[üu]r[üu]lm[üu][şs]", "Dönüştürülmüş Elektrikli Otobüs"),
    (r"o345", "Mercedes-Benz O345 / O345K"),
)
# Bu konularda satırın kendisi modeli taşır (başlık genel).
SATIR_MODELLI = re.compile(r"(h[o0]k|ö?ho|yan yana|belko)", re.I)


def norm_plaka(m):
    return "06 %s %s" % (m.group(2), m.group(3))


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                print("  ! indirilemedi:", url, e, file=sys.stderr)
                return None
            time.sleep(3 * (i + 1))


def konular(delay):
    """fid listesindeki konuları (tid, başlık) olarak döndürür."""
    out = []
    for fid in FIDS:
        page = 1
        while True:
            t = fetch("%sforumdisplay.php?fid=%d&page=%d" % (BASE, fid, page))
            if not t:
                break
            found = re.findall(r'<a href="showthread\.php\?tid=(\d+)"[^>]*class="[^"]*subject_[^"]*"[^>]*>([^<]+)</a>', t)
            if not found:
                found = re.findall(r'href="showthread\.php\?tid=(\d+)"[^>]*>([^<]{6,})</a>', t)
            for tid, title in found:
                tid = int(tid)
                if tid not in [x[0] for x in out]:
                    out.append((tid, htmllib.unescape(title).strip()))
            if ("page=%d" % (page + 1)) not in t:
                break
            page += 1
            time.sleep(delay)
    return out


def sayfa_sayisi(t):
    nums = [int(x) for x in re.findall(r"showthread\.php\?tid=\d+&(?:amp;)?page=(\d+)", t)]
    return max(nums) if nums else 1


def satirlar(t):
    """Konu sayfasından açıklama satırlarını ('> ... > ...') döndürür."""
    for blk in re.split(r'<div class="post_body', t)[1:]:
        txt = re.sub(r"<br\s*/?>", "\n", blk)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = htmllib.unescape(txt)
        for ln in txt.split("\n"):
            ln = ln.strip()
            if ln.startswith(">"):
                yield ln
            elif ">" in ln and (RE_PLAKA.search(ln) or RE_FILO.search(ln)):
                yield "> " + ln[ln.index(">") + 1:].strip()


RE_IMG = re.compile(r'<img\b[^>]*?\bsrc="([^"]+)"[^>]*>', re.I)


def _foto_url(tag_html, src):
    low = tag_html.lower()
    if "smilie" in low or "/smilies/" in src.lower() or "avatar" in low or src.startswith("data:"):
        return ""
    return urllib.parse.urljoin(BASE, htmllib.unescape(src))


def satirlar_foto(t, sayfa_url):
    """(satır, foto_url, gönderi_url, yazar) üçlüleri. Fotoğraf: açıklamadan önce gelen son görsel
    (yoksa sonraki ilk görsel). Yalnızca bağlantı saklanır, dosya indirilmez."""
    parcalar = re.split(r'<div class="post_body', t)
    for k, blk in enumerate(parcalar[1:], 1):
        onc = parcalar[k - 1][-4000:]
        pid = re.findall(r'(?:pid=|id="post_|id="pid_)(\d+)', onc)
        post = sayfa_url.split("#")[0] + ("#pid%s" % pid[-1] if pid else "")
        ya = re.findall(r'class="largetext"[^>]*>(?:\s*<a[^>]*>)?\s*([^<]{2,40})', onc)
        yazar = htmllib.unescape(ya[-1]).strip() if ya else ""
        sonu = blk.find('<div class="post_foot')
        body = blk if sonu < 0 else blk[:sonu]
        body = RE_IMG.sub(lambda m: "\n\x00%s\x00\n" % _foto_url(m.group(0), m.group(1)) if _foto_url(m.group(0), m.group(1)) else "", body)
        txt = re.sub(r"<br\s*/?>", "\n", body)
        txt = htmllib.unescape(re.sub(r"<[^>]+>", " ", txt))
        son = ""
        bekleyen = []
        for ln in txt.split("\n"):
            ln = ln.strip()
            if ln.startswith("\x00") and ln.endswith("\x00") and len(ln) > 2:
                son = ln.strip("\x00")
                for b in bekleyen:
                    yield b[0], son, post, yazar
                bekleyen = []
                continue
            aday = None
            if ln.startswith(">"):
                aday = ln
            elif ">" in ln and (RE_PLAKA.search(ln) or RE_FILO.search(ln)):
                aday = "> " + ln[ln.index(">") + 1:].strip()
            if aday:
                if son:
                    yield aday, son, post, yazar
                else:
                    bekleyen.append((aday,))
        for b in bekleyen:
            yield b[0], "", post, yazar


def baslik_model(title):
    low = title.lower()
    for pat, model in BASLIK_MODEL:
        if re.search(pat, low):
            return model
    return None


def ayikla(satir, konu_modeli, satir_modelli):
    """Bir açıklama satırından (anahtarlar, model) çıkarır. Bulamazsa None."""
    parcalar = [p.strip() for p in satir.lstrip("> ").split(">")]
    if not parcalar:
        return None
    pl = RE_PLAKA.search(satir)
    fl = RE_FILO.search(satir)
    plaka = norm_plaka(pl) if pl else ""
    filo = fl.group(1) if fl else ""
    if not (plaka or filo):
        return None
    model = konu_modeli
    if satir_modelli:
        ilk = parcalar[0]
        if ilk and not RE_PLAKA.search(ilk) and not RE_FILO.search(ilk) and len(ilk) < 70:
            model = ilk
        else:
            model = None
    if not model:
        return None
    return filo, plaka, model


def yaz(conn, filo, plaka, model, url, tid, kuru):
    n = 0
    for anahtar in (filo, plaka):
        k = E.norm(anahtar)
        if not k:
            continue
        mevcut = conn.execute("SELECT kaynak, marka_model FROM arac_bilgi WHERE anahtar=?", (k,)).fetchone()
        if mevcut and not (mevcut[0] or "").startswith(KAYNAK[:20]):
            continue  # elle girilmiş kayda dokunma
        if mevcut and mevcut[1] == model:
            continue
        n += 1
        if not kuru:
            conn.execute(
                "INSERT OR REPLACE INTO arac_bilgi (anahtar, marka_model, kaynak, url, durum, ts) VALUES (?,?,?,?,?,?)",
                (k, model[:120], KAYNAK, url[:300], "kesin", E.now_ts()),
            )
    return n


def yaz_foto(conn, filo, plaka, foto, post, yazar, kuru):
    n = 0
    if not foto:
        return 0
    for anahtar in (filo, plaka):
        k = E.norm(anahtar)
        if not k:
            continue
        if conn.execute("SELECT 1 FROM arac_foto WHERE anahtar=?", (k,)).fetchone():
            continue  # ilk bulunan fotoğraf kalır
        n += 1
        if not kuru:
            conn.execute("INSERT INTO arac_foto (anahtar, img, post, yazar, ts) VALUES (?,?,?,?,?)",
                         (k, foto[:400], post[:300], yazar[:60], E.now_ts()))
    return n


def yaz_dene(fn, bekle=10, deneme=40):
    """Toplayıcı veritabanını kilitliyken (tur sırasında) kısa aralıklarla yeniden dener."""
    import sqlite3
    for i in range(deneme):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) and "busy" not in str(e):
                raise
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(bekle)
    raise RuntimeError("veritabanı uzun süre kilitli kaldı")


def main():
    global conn
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-minutes", type=float, default=0, help="bu süreden sonra bırak, sonraki çalışmada devam et")
    ap.add_argument("--yeni", action="store_true", help="her konunun yalnız son 2 sayfasına bak")
    ap.add_argument("--kuru", action="store_true", help="veritabanına yazma")
    ap.add_argument("--bekle", type=float, default=1.5, help="istekler arası saniye (varsayılan 1.5)")
    ap.add_argument("--sifirla", action="store_true", help="sayfa sayaçlarını sıfırla, baştan tara")
    a = ap.parse_args()

    t0 = time.time()
    conn = E.connect()
    conn.execute("PRAGMA busy_timeout=60000")
    yaz_dene(lambda: conn.execute("CREATE TABLE IF NOT EXISTS arac_bilgi (anahtar TEXT PRIMARY KEY, marka_model TEXT, "
                 "kaynak TEXT, url TEXT, durum TEXT, ts INTEGER)"))
    yaz_dene(lambda: conn.execute("CREATE TABLE IF NOT EXISTS arac_foto (anahtar TEXT PRIMARY KEY, img TEXT, post TEXT, yazar TEXT, ts INTEGER)"))
    toplam_yeni = toplam_satir = toplam_foto = 0

    def zaman_doldu():
        return a.max_minutes and (time.time() - t0) > a.max_minutes * 60

    liste = konular(a.bekle)
    if not liste:
        print("Konu listesi alınamadı (site erişilemiyor olabilir).")
        return 1
    print("%d konu bulundu." % len(liste))
    for tid, title in liste:
        if zaman_doldu():
            break
        konu_modeli = baslik_model(title)
        satir_modelli = bool(SATIR_MODELLI.search(title)) and not konu_modeli
        if not konu_modeli and not satir_modelli:
            print("- atlandı (model çıkarılamadı):", title)
            continue
        key = "ref:%d" % tid
        r = conn.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        bitti = 0 if (a.sifirla or not r) else int(r[0])
        t = fetch("%sshowthread.php?tid=%d&page=1" % (BASE, tid))
        if not t:
            continue
        son = sayfa_sayisi(t)
        baslangic = max(1, son - 1) if a.yeni else max(1, bitti)
        print("- %s: %d sayfa, %d. sayfadan devam" % (title, son, baslangic))
        for p in range(baslangic, son + 1):
            if zaman_doldu():
                print("  süre doldu, sonra devam edilecek")
                break
            url = "%sshowthread.php?tid=%d&page=%d" % (BASE, tid, p)
            t = fetch(url)
            if t is None:
                break
            kayitlar = []
            for ln, foto, post, yazar in satirlar_foto(t, url):
                toplam_satir += 1
                s = ayikla(ln, konu_modeli, satir_modelli)
                if s:
                    kayitlar.append(s + (foto, post, yazar))

            def sayfayi_yaz():
                n = 0
                for s in kayitlar:
                    n += yaz(conn, s[0], s[1], s[2], url, tid, a.kuru)
                    yaz_foto(conn, s[0], s[1], s[3], s[4], s[5], a.kuru)
                if not a.kuru:
                    conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", (key, str(p)))
                    conn.commit()
                return n

            toplam_yeni += yaz_dene(sayfayi_yaz)
            time.sleep(a.bekle)
    conn.commit()
    print("Bitti: %d satır okundu, %d kayıt eklendi/güncellendi%s." % (toplam_satir, toplam_yeni, " (kuru)" if a.kuru else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
