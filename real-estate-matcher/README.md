# Emlak Zekası ve Portföy Eşleştirme

Emlak danışmanları için doğal dilde müşteri talebi analizi, açıklanabilir ilan
eşleştirme, manuel filtreleme, karşılaştırma, portföy yönetimi ve piyasa analitiği
sunan Streamlit uygulaması.

## İçerik

- 500 ayrıntılı örnek ilan
- Satılık ve kiralık portföyler için ayrı KPI ve piyasa hesapları
- Gemini destekli kriter çıkarma ve API yoksa yerel kural motoru
- Konum, işlem türü, oda, bütçe, alan ve ayrıntılı donanım puanlaması
- Aktif kriter ağırlıklarından hesaplanan, 0-100 aralığında normalize edilmiş uyum yüzdesi
- Her kriter için zorunlu, tercih veya önemsiz seçimi
- Karşılanan, kısmen karşılanan, karşılanmayan ve verisi bilinmeyen kriter dökümü
- Müşteri profili, talep notları ve gönderilen ilan geçmişi
- TAKS, KAKS ve kat sınırını birlikte değerlendiren arsa yapılaşma hesabı
- İmar, tapu, fiziksel durum, altyapı ve bölgesel potansiyel arsa risk puanı
- Her arsa bilgi grubu için kaynak ve veri güven düzeyi
- Kötümser, normal ve iyimser proje fizibilitesi
- Karşılaştırılabilir örnek arsa portföyü ve CSV dışa aktarma
- 2-4 ilanı oturum durumuyla karşılaştırma
- WhatsApp müşteri sunumu
- CSV portföy yönetimi ve dışa aktarma

## Yerelde çalıştırma

Windows'ta `run_app.bat` dosyasına çift tıklayın veya PowerShell'de:

```powershell
cd real-estate-matcher
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.

## Gemini ayarı

Gemini zorunlu değildir. Anahtar yoksa uygulama yerel kural motoruyla çalışır.
Yerelde `.env` dosyası oluşturun:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Streamlit Community Cloud'da aynı değerleri uygulamanın **Secrets** alanına ekleyin:

```toml
GEMINI_API_KEY = "your_api_key_here"
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

Anahtarları GitHub'a yüklemeyin.

## Streamlit Cloud

Main file path:

```text
real-estate-matcher/app.py
```

GitHub'daki `main` dalına gönderilen her commit Streamlit Cloud tarafından otomatik
olarak yeniden yayınlanır. Uygulama veriyi `real-estate-matcher/data/listings.csv`
dosyasından, örnek arsa portföyünü ise `real-estate-matcher/data/lands.csv`
dosyasından okur.

Müşteri kayıtları yerel kullanımda `data/customers.json` dosyasında tutulur ve bu
dosya GitHub'a gönderilmez. Streamlit Community Cloud'un dosya sistemi kalıcı bir
veritabanı değildir; çok kullanıcılı ve kalıcı müşteri geçmişi için PostgreSQL veya
Supabase gibi harici bir veritabanı bağlanmalıdır.

## Puanlama mantığı

Her ilan, yalnızca puana dahil edilen kriterlerin toplam ağırlığı üzerinden hesaplanır:

```text
uyum yüzdesi = kazanılan puan / mümkün olan puan * 100
```

Zorunlu bir kriter karşılanmazsa ilan kesin sonuçlardan elenir. Tercih kriterleri
sonuçları elemez, yalnızca sıralamayı etkiler. `Ferah`, `lüks` ve `sakin` gibi ilan
verisinden güvenilir biçimde doğrulanamayan öznel istekler kullanıcıya gösterilir,
ancak uyum yüzdesine puan eklemez.

## Arsa hesaplarının kapsamı

Yapılaşma ekranı TAKS ile taban oturumunu, KAKS ile emsale dâhil alanı ve maksimum
kat sınırını ayrı ayrı hesaplar; en kısıtlayıcı değeri sonuç olarak kullanır. Risk
ekranı puanı ve veri güvenini ayrı gösterir. Fizibilite ekranı maliyet ve satış
varsayımlarını kötü, normal ve iyi senaryolarda karşılaştırır.

Bu sonuçlar ön fizibilite amaçlıdır. İmar plan notları, çekme mesafeleri, tapu
kayıtları, zemin etüdü, ruhsat koşulları ve ilgili kurum kararları resmî belgelerden
ayrıca doğrulanmalıdır.

## Veri üretimi

Örnek portföyü yeniden oluşturmak için:

```powershell
.\.venv\Scripts\python.exe generate_demo_listings.py
Move-Item -Force listings.csv data\listings.csv
```

Her kayıt, en az 10 maddelik bina özelliği ile finansal ve teknik alanlar içerir.
