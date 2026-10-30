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

## Arayüz özellikleri

- **Durak takibi (/durak)**: durak adı/numarasıyla arama; duraktan geçen hatlar, yaklaşan araçlar (tahmini varış dk, kaç durak kaldı, doluluk, körüklü/solo), hatların sonraki hareketi ve son 1 saatte durağı geçenler. EGO durak koordinatı vermediği için yakınlık "dakika / durak sayısı" olarak gösterilir.
- **Hat sayfası (/hat)**: duraklar sırayla, hattaki canlı araçlar bulundukları durakta, hafta içi/cumartesi/pazar hareket saatleri ve sıradaki kalkışlar. Saatler toplayıcı içinde arka planda haftada bir tazelenir (`python3 ego_tracker.py saatler` ile elle de çalışır).
- **Doluluk**: EGO'nun yoğunluk bilgisi (varsa) her kayıtla birlikte saklanır.
- Açılışta şehir seçimi (çerezle hatırlanır, üstteki şehir düğmesinden değişir). Şehir listesi `ego_web.py` içindeki `CITIES`; `aktif: False` olanlar "Yakında" görünür.
- Sorgula: filo kodu/plaka + tarih (+saat), gün gezgini, son 14 gün geçmişi
- Harita: kümeleme, işletme (EGO / ÖHO 06 HO), körüklü/solo, tam hat ve metin filtresi
- İlk hatlar: seçili gün / 7 / 30 gün için en çok araç çalıştıran 50 hat
- CSV dışa aktarma: `/csv/gun`, `/csv/hatlar`, `/csv/arac` (Excel için `;` ayraçlı, UTF-8 BOM)

## Veri
`*.db`, günlükler ve raporlar repoya **girmez** (`.gitignore`). Günlük yedek: `/opt/filo-takip/yedek/` (7 gün).

## Çok şehirli yapı (plan)
Şu an yalnız Ankara/EGO etkin. Yeni şehir eklemek için her şehrin veri kaynağı ayrı bir "şehir bağdaştırıcısı" olarak yazılacak (hat listesi, canlı konum, filo kodu/plaka alanları) ve ortak veritabanı/arayüz tekrar kullanılacak. Adaylar: İstanbul (İBB/İETT açık veri), İzmir (ESHOT açık veri). Her şehir yalnızca resmi açık veri veya herkese açık servisleri kullanır.

## İstanbul (İETT) – hazırlık aşaması
`iett_tracker.py`: İBB açık veri servislerinden (kimlik gerekmez) hat, koordinatlı durak ve canlı araç konumu toplar; Ankara ile aynı şemada ayrı veritabanına (`iett_filo.db`) yazar. `python3 iett_tracker.py probe` → servisleri dener, `init` → 782 hattın duraklarını çeker, `run` → döngü. Henüz sunucuda servis olarak çalışmıyor ve arayüze bağlı değil. Test: `python3 test_iett.py`.

### Durak konumları (Ankara)
EGO durak koordinatı yayınlamaz. `ego_tracker.py durak-konum` (ve toplayıcı içinde 3 saatte bir) araç gözlemlerinden durak konumunu tahmin eder: aracın "sonraki durak" sırası değiştiği iki ardışık gözlemin orta noktasının medyanı (en az 3 geçiş). Veri biriktikçe doğruluk artar. Durak adresleri (mahalle/sokak) EGO Hareket Saatleri sayfasından alınır. Haritada 15+ yakınlaştırmada duraklar tıklanabilir.
