# Emlak Zekası ve Portföy Eşleştirme

Emlak danışmanları için doğal dilde müşteri talebi analizi, açıklanabilir ilan
eşleştirme, manuel filtreleme, karşılaştırma, portföy yönetimi ve piyasa analitiği
sunan Streamlit uygulaması.

## İçerik

- 500 ayrıntılı örnek ilan
- Satılık ve kiralık portföyler için ayrı KPI ve piyasa hesapları
- Gemini destekli kriter çıkarma ve API yoksa yerel kural motoru
- Konum, işlem türü, oda, bütçe, alan ve ayrıntılı donanım puanlaması
- Her sonuçta puan dökümü, karşılanan ve eksik kriterler
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
dosyasından okur.

## Veri üretimi

Örnek portföyü yeniden oluşturmak için:

```powershell
.\.venv\Scripts\python.exe generate_demo_listings.py
Move-Item -Force listings.csv data\listings.csv
```

Her kayıt, en az 10 maddelik bina özelliği ile finansal ve teknik alanlar içerir.
