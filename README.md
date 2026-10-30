# Filo Takip (şehir içi otobüs arşivi)

Ankara EGO otobüslerinin hangi hatta, hangi saatte ve hangi duraklardan geçtiğini kaydeden, filo kodu/plaka ile sorgulanabilen kişisel arşiv sistemi (ticari değil). Standart kütüphane Python 3, SQLite.

## Dosyalar
- `ego_tracker.py` toplayıcı + komut satırı, `ego_web.py` web arayüzü (PWA), `referans_tara.py` Ulaşım Platformu referans taraması
- `modeller.csv` filo ön eki → model kuralları
- `vps/kur.sh` sunucu kurulumu, `vps/guncelle.sh` GitHub'dan otomatik güncelleme, `vps/vps_test.sh` erişim testi
- `test_mock.py` sahte EGO sunucusuyla uçtan uca test: `python3 test_mock.py`

## Sunucu kurulumu (Ubuntu/Debian VPS)
1. `bash vps/vps_test.sh` (IP Türkiye mi, servisler açılıyor mu)
2. Eski veritabanını `/root/ego_filo.db` olarak yükle
3. `bash vps/kur.sh filo.ulasimarsiv.com SIFRE git@github.com:framiodev/filo-takip.git`
   Betik bir deploy anahtarı yazdırır; GitHub > Settings > Deploy keys'e ekle.

## Güncelleme akışı
`main` dalına push → sunucu 5 dakikada bir çeker → `test_mock.py` geçerse servisler yeniden başlar (başarısızsa eski sürüm çalışmaya devam eder, `guncelleme.log`).

## Veri
`*.db`, günlükler ve raporlar repoya **girmez** (`.gitignore`). Günlük yedek: `/opt/filo-takip/yedek/` (7 gün).

## Çok şehirli yapı (plan)
Şu an yalnız Ankara/EGO etkin. Yeni şehir eklemek için her şehrin veri kaynağı ayrı bir "şehir bağdaştırıcısı" olarak yazılacak (hat listesi, canlı konum, filo kodu/plaka alanları) ve ortak veritabanı/arayüz tekrar kullanılacak. Adaylar: İstanbul (İBB/İETT açık veri), İzmir (ESHOT açık veri). Her şehir yalnızca resmi açık veri veya herkese açık servisleri kullanır.
