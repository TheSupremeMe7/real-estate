# Emlak Eşleştirici

Emlak danışmanının müşteri talebini portföydeki ilanlarla eşleştirmesi için
hazırlanan web uygulamasıdır. Doğal dilde yazılan talebi Gemini ile analiz eder,
100 ilanlık örnek portföyü puanlar ve müşteriye gönderilebilir kısa liste üretir.

## Özellikler

- Google Sheets üzerinden canlı portföy yönetimi
- 100 çeşitli demo ilan ve her ilan için benzersiz satış avantajı
- Daire, bahçe katı, villa, dubleks, rezidans, müstakil ev ve çatı katı
- AI destekli müşteri talebi analizi ve açıklanabilir eşleşme puanı
- Seçilen ilanlardan indirilebilir müşteri özeti

## Kurulum

```powershell
cd D:\codex\real-estate-matcher
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Çalıştırma

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Tarayıcı otomatik açılmazsa terminalde gösterilen `http://localhost:8501`
adresini açın.

Kurulum tamamlandıktan sonra `start_app.bat` dosyasına çift tıklayarak uygulamayı
`http://localhost:8502` adresinde açabilirsiniz.

## Google Sheets portföyü

Ayrı bir Google Sheet oluşturup proje service account adresiyle Düzenleyici
olarak paylaşın. `.env.example` dosyasını `.env` adıyla oluşturup Sheet ID'yi
ekleyin:

```env
REAL_ESTATE_SHEET_ID=sheet_id_buraya
GOOGLE_CREDENTIALS_FILE=..\credentials.json
```

Uygulama ilk bağlantıda `Listings` sekmesini oluşturup örnek ilanları yükler.
Emlakçı bundan sonra ilanları bu sekmede yönetebilir. `status` değeri `active`
olan ilanlar uygulamada görünür.

## Gemini talep analizi

Yeni ve güvenli bir Gemini anahtarını `.env` içine ekledikten sonra AI modunu
açabilirsiniz:

```env
GEMINI_API_KEY=yeni_anahtar
ENABLE_GEMINI=true
```

AI kapalıysa veya API çağrısı başarısız olursa uygulama yerel kriter ayrıştırıcıya
geri döner ve çalışmaya devam eder.

## İnternette yayınlama

En kolay yöntem ücretsiz Streamlit Community Cloud kullanmaktır:

1. `real-estate-matcher` klasörünü bir GitHub deposuna yükleyin. `.env`,
   `credentials.json` ve `.streamlit/secrets.toml` dosyalarını kesinlikle
   GitHub'a yüklemeyin; `.gitignore` bunları zaten engeller.
2. `https://share.streamlit.io` adresinde GitHub ile giriş yapın ve **Create app**
   seçeneğini açın.
3. GitHub deponuzu seçin, ana dosya yolu olarak `app.py` yazın.
4. **Advanced settings > Secrets** alanına aşağıdaki ayarları girin:

```toml
REAL_ESTATE_SHEET_ID = "sheet_id"
GEMINI_API_KEY = "gemini_api_anahtari"
ENABLE_GEMINI = "true"
GOOGLE_CREDENTIALS_JSON = '''credentials.json dosyasının tek satırlık içeriği'''
```

5. **Deploy** düğmesine basın. Uygulama `https://...streamlit.app` biçiminde,
   telefondan ve bilgisayardan açılabilen bir internet adresi alır.

`credentials.json` içeriğini tek satıra çevirmek için proje üst klasöründe:

```powershell
(Get-Content .\credentials.json -Raw | ConvertFrom-Json | ConvertTo-Json -Compress)
```

Komutun çıktısını `GOOGLE_CREDENTIALS_JSON` değerindeki üç tek tırnağın arasına
yapıştırın. Bu gizli içerik yalnızca Streamlit'in **Secrets** alanında bulunmalı.
