import random
import sys
from pathlib import Path

import pandas as pd

from sheet_store import LISTING_COLUMNS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass



OUTPUT = Path(__file__).parent / "listings.csv"
random.seed(101)

LOCATIONS = [
    # İstanbul Avrupa
    ("İstanbul", "Başakşehir", "Bahçeşehir 1. Kısım", "Merkezi, yeşil alanları bol aile semti"),
    ("İstanbul", "Başakşehir", "Kayaşehir", "Geniş caddeleri ve yeni projeleriyle hızla gelişen bölge"),
    ("İstanbul", "Beşiktaş", "Bebek", "Boğaz hattında ultra lüks ve tarihi prestij"),
    ("İstanbul", "Beşiktaş", "Levent", "Finans ve plaza merkezine yürüme mesafesinde"),
    ("İstanbul", "Beşiktaş", "Etiler", "Seçkin restoranlar ve lüks konut dokusu"),
    ("İstanbul", "Sarıyer", "Zekeriyaköy", "Ormanla iç içe müstakil villa ve doğa yaşamı"),
    ("İstanbul", "Sarıyer", "Maslak", "İş ve finans dünyasının kalbi, yüksek kira getirisi"),
    ("İstanbul", "Sarıyer", "Tarabya", "Sahil hattı, marina ve sakin koy manzarası"),
    ("İstanbul", "Şişli", "Bomonti", "Kültür, sanat ve dinamik şehir rezidansları"),
    ("İstanbul", "Şişli", "Nişantaşı", "Moda, lüks butikler ve tarihi apartman dokusu"),
    ("İstanbul", "Bakırköy", "Ataköy", "Deniz kıyısı, marina ve oturmuş peyzajlı siteler"),
    ("İstanbul", "Bakırköy", "Florya", "Sahil, koru ve geniş bahçeli butik mülkler"),
    ("İstanbul", "Beylikdüzü", "Adnan Kahveci", "Geniş bulvarlar, yeni siteler ve uygun fiyat avantajı"),
    ("İstanbul", "Beylikdüzü", "Yakuplu", "Marina ve sahil odaklı modern yaşam"),
    
    # İstanbul Anadolu
    ("İstanbul", "Kadıköy", "Fenerbahçe", "Kalamış marina ve sahil yürüyüş hattında elit lokasyon"),
    ("İstanbul", "Kadıköy", "Caddebostan", "Bağdat Caddesi ve sahil parkı arasında en popüler semt"),
    ("İstanbul", "Kadıköy", "Moda", "Tarihi sokaklar, deniz esintisi ve canlı kafe kültürü"),
    ("İstanbul", "Kadıköy", "Suadiye", "Bağdat Caddesi merkezinde lüks kentsel dönüşüm mülkleri"),
    ("İstanbul", "Üsküdar", "Çengelköy", "Tarihi Boğaz manzarası, çınar altı ve butik siteler"),
    ("İstanbul", "Üsküdar", "Kandilli", "Eşsiz yalı ve boğaz manzaralı lüks yerleşim"),
    ("İstanbul", "Kartal", "Yakacık", "Aydos ormanı eteğinde havadar ve manzaralı"),
    ("İstanbul", "Kartal", "Sahil", "Marmaray hattı ve kesintisiz Adalar manzarası"),
    ("İstanbul", "Maltepe", "Altayçeşme", "E-5 ve metroya sıfır ulaşım kolaylığı"),
    ("İstanbul", "Maltepe", "Küçükyalı", "Sahil ve Minibüs caddesi arasında merkezi lokasyon"),
    ("İstanbul", "Çekmeköy", "Merkez", "Kuzey ormanlarına komşu, sakin villa ve siteler"),

    # Ankara
    ("Ankara", "Çankaya", "Oran", "Panoramik vadi ve ODTÜ ormanı manzaralı prestij"),
    ("Ankara", "Çankaya", "Gaziosmanpaşa", "Elçilikler bölgesi, köklü ve güvenli yerleşim"),
    ("Ankara", "Çankaya", "Çayyolu", "Geniş villalar, seçkin kolejler ve modern sosyal yaşam"),
    ("Ankara", "Çankaya", "İncek", "Yeni nesil lüks kampüs siteleri ve temiz hava"),
    ("Ankara", "Çankaya", "Ümitköy", "Metroya yakın, köklü ve ferah aile yerleşimi"),

    # İzmir
    ("İzmir", "Urla", "İskele", "Ege denizine sıfır, sakin sahil ve balıkçı kasabası ruhu"),
    ("İzmir", "Urla", "Kekliktepe", "Geniş zeytinlikler içinde ultra lüks müstakil taş villalar"),
    ("İzmir", "Çeşme", "Alaçatı", "Tarihi taş mimari, rüzgar sörfü ve butik turizm"),
    ("İzmir", "Çeşme", "Ilıca", "Ünlü plajlara yürüme mesafesinde yaz-kış yaşam"),
    ("İzmir", "Karşıyaka", "Mavişehir", "Deniz manzaralı modern rezidanslar ve AVM yanı"),
    ("İzmir", "Karşıyaka", "Bostanlı", "Sahil kordonu, canlı sosyal hayat ve tramvay"),
    ("İzmir", "Bornova", "Kazımdirik", "Üniversite ve sanayi aksında yüksek kiralama potansiyeli"),

    # Antalya & Muğla & Bursa
    ("Antalya", "Muratpaşa", "Lara", "Falezler üzeri eşsiz Akdeniz manzarası ve lüks oteller aksı"),
    ("Antalya", "Konyaaltı", "Liman", "Mavi bayraklı plajlara yürüme mesafesinde yabancıya uygun"),
    ("Muğla", "Bodrum", "Yalıkavak", "Uluslararası marina, gün batımı ve ultra lüks malikaneler"),
    ("Bursa", "Nilüfer", "Bademli", "Uludağ manzaralı geniş bahçeli malikane ve villalar"),
]

PROPERTY_PROFILES = [
    # Konut
    ("Konut", "Daire", ["1+1", "2+1", "3+1", "4+1"], "assets/city-apartment-thumb.webp"),
    ("Konut", "Bahçe Katı", ["2+1", "3+1", "4+1"], "assets/garden-flat-thumb.webp"),
    ("Konut", "Villa", ["4+1", "5+1", "6+2", "7+2"], "assets/villa-garden-thumb.webp"),
    ("Konut", "Dubleks", ["3+1", "4+1", "5+1"], "assets/penthouse-terrace-thumb.webp"),
    ("Konut", "Rezidans", ["1+0", "1+1", "2+1", "3+1"], "assets/smart-studio-thumb.webp"),
    ("Konut", "Müstakil Ev", ["3+1", "4+1", "5+2"], "assets/villa-garden-thumb.webp"),
    ("Konut", "Çatı Katı", ["2+1", "3+1", "4+1"], "assets/penthouse-terrace-thumb.webp"),
    
    # Ticari
    ("Ticari", "Dükkan / Mağaza", ["Açık Alan / 2 Bölüm", "Açık Alan / 4 Bölüm", "Düz Giriş + Asma Kat"], "assets/commercial-shop-thumb.webp"),
    ("Ticari", "Ofis / Büro", ["2+1", "3+1", "Açık Alan / 4 Bölüm", "Açık Alan / 8 Bölüm"], "assets/office-plaza-thumb.webp"),
    ("Ticari", "Plaza Katı", ["Tam Kat Açık Ofis", "Bölümlü Plaza Katı", "Panoramik Executive Kat"], "assets/office-plaza-thumb.webp"),
    ("Ticari", "Depo / Atölye", ["Açık Yüksek Tavan Alan", "Depo + Ofis Bölümü"], "assets/warehouse-logistics-thumb.webp"),
    
    # Arsa
    ("Arsa", "İmarlı Arsa", ["Müstakil Parsel", "Konut İmarlı", "Ticari + Konut İmarlı"], "assets/villa-garden-thumb.webp"),
]

PROS_POOL = {
    "genel": [
        "2018 sonrası güncel deprem yönetmeliğine uygun C35 betonarme taşıyıcı sistem",
        "Metro / Marmaray istasyonuna sadece 3-5 dakika yürüme mesafesinde",
        "Kat mülkiyeti tapulu, iskanlı ve konut kredisine %100 uygun",
        "Kapanmaz panoramik deniz ve adalar manzarası",
        "Geniş ve güneş alan ferah salon yerleşimi",
        "Ada tezgahlı ve Miele / Franke lüks ankastre setli özel mutfak tasarımı",
        "Ebeveyn yatak odasında özel banyo ve müstakil giyinme odası",
        "Kapalı otoparkta elektrikli araç (EV) şarj istasyonu altyapısı hazır",
        "Salondan ve mutfaktan doğrudan çıkışlı 30 m² geniş cam balkon",
        "Akıllı ev otomasyonu ile aydınlatma, panjur ve ısıtma cepten kontrol edilebilir",
        "Aylık yüksek kira potansiyeli ve 14-16 yıl gibi hızlı amortisman süresi",
        "Açık/kapalı yüzme havuzu, fitness ve sauna gibi zengin sosyal tesis donatısı",
        "7/24 üniformalı güvenlik, CCTV kamera ve kontrollü lobi girişi",
        "Jeneratör, su deposu ve fiber internet altyapısı eksiksiz",
        "Müstakil 180 m² çim bahçe ve otomatik sulama sistemi",
        "Kuzey-güney çift cepheli olması sayesinde gün boyu doğal hava sirkülasyonu",
        "Merkezi konumu sayesinde okul, hastane ve seçkin AVM'lere yürüme mesafesinde",
    ],
    "ticari": [
        "Ana cadde üzerinde yüksek yaya ve araç trafiğine sahip tabela değeri",
        "Geniş vitrin cephesi (12 metre) ve düzayak engelsiz müşteri girişi",
        "Baca ve havalandırma altyapısı hazır, kafe/restoran/klinik ruhsatına uygun",
        "Kurumsal kiracıya hemen verilebilir veya yüksek ciro potansiyeli",
        "Yük asansörü, rampa ve kamyonet yanaşma alanı mevcut",
        "Metro çıkışına sıfır konumda, personel ve müşteriler için çok rahat ulaşım",
        "Plaza katında prestijli lobi, resepsiyon ve kartlı turnike güvenliği",
    ]
}

CONS_POOL = {
    "genel": [
        "Site sosyal tesisleri sebebiyle aylık aidat bedeli bölge ortalamasının üzerinde",
        "Bina yaşı 15+ yıl; ortak alanlarda periyodik yenileme ihtiyacı bulunabilir",
        "Kuzey cepheli odalarda kış aylarında ısınma maliyeti biraz daha yüksek olabilir",
        "Merkezi caddeye yakınlığı nedeniyle yoğun saatlerde hafif trafik sesi alabilir",
        "Otopark açık alandadır, her daireye 1 adet tahsisli numara bulunmaktadır",
        "Ebeveyn banyosu bulunmamaktadır, tek geniş aile banyosu mevcuttur",
        "Balkon alanı standart boyuttadır, geniş masa koymak için sınırlı kalabilir",
        "Metroya yürüme mesafesi 12-15 dk civarındadır, ring servisi kullanılmaktadır",
        "Dairede mevcut kiracı bulunmaktadır, tahliye için makul süre gerekebilir",
    ],
    "ticari": [
        "Akşam saatlerinde cadde otoparkı yoğunlaşabilmektedir",
        "Ticari aidat ve tabela vergisi giderleri göz önünde bulundurulmalıdır",
        "Tadilat ve kurumsal dekorasyon için ilk etapta masraf gerektirebilir",
        "Hafta sonu iş merkezi kapalı otoparkında giriş kısıtlaması olabilir",
    ]
}

HEATING_TYPES = [
    "Yerden Isıtma",
    "Doğalgaz Kombi",
    "VRF Merkezi İklimlendirme",
    "Isı Pompası (Düşük Tüketim)",
    "Merkezi Pay Ölçer",
]
FACADES = [
    "Güney-Doğu (Sabah ve Öğle Güneşi)",
    "Kuzey-Güney (Çift Cephe & Havadar)",
    "Güney-Batı (Akşam Güneşi & Aydınlık)",
    "Güney (Tüm Gün Güneş)",
    "Doğu (Sabah Güneşi)",
    "Batı (Gün Batımı Manzaralı)",
]
PARKING_TYPES = [
    "2 Araçlık Kapalı + EV Şarj",
    "1 Araçlık Kapalı Otopark",
    "Açık Tahsisli Otopark",
    "Açık + Kapalı Otopark",
    "Özel Vale & Kapalı Otopark",
    "Cadde Üstü Park İmkanı",
]
SECURITY_TYPES = [
    "7/24 Güvenlik & CCTV Kamera",
    "Lobi / Resepsiyon & Kartlı Geçiş",
    "Güvenlikli Site Girişi",
    "Görüntülü Diafon & Şifreli Giriş",
]
VIEW_TYPES = [
    "Boğaz & Deniz",
    "Panoramik Şehir",
    "Orman & Doğa",
    "Peyzaj & Havuz",
    "Cadde & Şehir",
    "Park & Yeşil Alan",
    "Kısmi Deniz Manzaralı",
]
OUTDOOR_SPACES = [
    "25 m² Geniş Teras & Barbekü",
    "120 m² Müstakil Çim Bahçe",
    "Panoramik Cam Balkon",
    "Fransız Balkon",
    "Kış Bahçesi",
    "Vitrin Önü Teras Alanı",
    "Balkonsuz (Geniş İç Mekan)",
]
KITCHEN_TYPES = [
    "Ada Tezgahlı Lüks Mutfak",
    "Kapalı Lüks Ankastre Mutfak",
    "Amerikan Açık Mutfak",
    "Ofis Tipi Mutfak / Kitchenette",
    "Yarı Açık Mutfak",
]
AMENITY_SETS = [
    "Açık/Kapalı Yüzme Havuzu; Fitness & Pilates Salonu; Sauna & Buhar Odası; Çocuk Parkı; Yürüyüş Parkuru; Tenis Kortu",
    "Peyzajlı Bahçe; Sosyal Tesis; Basketbol Sahası; Bisiklet Parkı; Çocuk Oyun Alanı; Kamelya & Dinlenme Alanı",
    "Yarı Olimpik Havuz; SPA & Masaj Odası; Kapalı Spor Salonu; Kafe & Dinlenme Alanı; Açık Sinema Alanı",
    "Çocuk Kulübü; Hobi ve Oyun Odası; Toplantı & Çalışma Salonu; Misafir Otoparkı; Barbekü Alanı",
    "Geniş Yeşil Alan; Yürüyüş Yolu; Evcil Hayvan Parkı; 7/24 Güvenlik; Kapalı Otopark",
    "Modern Lobi; Resepsiyon Hizmeti; Ortak Toplantı Odaları; Dinlenme Terası; Jeneratör",
]
NEARBY_SETS = [
    "Metro İstasyonu 300 m; Prestijli Kolej 450 m; Süpermarket 100 m; Tam Donanımlı Hastane 1.8 km",
    "Marmaray 600 m; Sahil Kordonu 400 m; Butik Kafeler 150 m; Eczane ve Sağlık Ocağı 200 m",
    "Metrobüs 350 m; Alışveriş Merkezi (AVM) 800 m; Üniversite Kampüsü 1.2 km; E-5 Bağlantısı 200 m",
    "Marina ve Sahil Parkı 500 m; Gurme Restoranlar 250 m; Tenis Kulübü 700 m; Özel Hastane 1.5 km",
    "TEM Otoyol Çıkışı 1.2 km; Uluslararası Okul 900 m; Organik Pazar 300 m; Doğa Parkı 600 m",
    "Havalimanı Bağlantı Yolu 4 km; Organize Sanayi / İş Merkezi 1.5 km; Toplu Taşıma Durağı 80 m",
]
TECHNICAL_SETS = [
    "Akıllı ev otomasyon sistemi; Çift camlı Schüco alüminyum doğrama; Fiber optik internet; Tam güç jeneratör",
    "Isı ve ses yalıtımlı taş yünü mantolama; Yerden ısıtma; VRF klima altyapısı; Merkezi su arıtma ve hidrofor",
    "Güneş paneli elektrik üretimi; Merkezi yangın sprinkler sistemi; Duman dedektörü; Şifreli çelik kapı",
    "Otomatik elektrikli panjur; Kilitli müstakil depo alanı; Merkezi uydu yayını; Görüntülü akıllı diafon",
    "Deprem sensörlü gaz kesme sistemi; Çift asansör; Acil kaçış merdiveni; Kesintisiz UPS güç hattı",
]
BUILDING_FEATURE_SETS = [
    "2018 Deprem Yönetmeliğine uygun C35 hazır betonarme karkas sistem; Radye jeneral temel ve perde beton uygulaması",
    "Zemin etüdü ve sismik testleri yapılmış güvenli yapı; Dış cephede A1 sınıfı yanmaz taş yünü ısı yalıtımı",
    "Katta çift sedye asansörü; Kapalı otoparktan kata doğrudan asansör bağlantısı; Engelsiz rampa girişi",
    "Profesyonel site yönetimi ve peyzaj bakım ekibi; 7/24 güvenlik kamera kayıt merkezi; Plaka tanıma bariyeri",
    "Ses ve titreşim yalıtımlı döşeme plakaları; Yangın algılama ve duman tahliye basınçlandırma santrali",
]

TITLES_RESIDENTIAL = [
    "Lüks Tasarımlı ve Taşınmaya Hazır",
    "Panoramik Manzaralı ve Geniş Teraslı",
    "Özel Bahçeli ve Havuz Manzaralı",
    "Metroya Yürüme Mesafesinde Masrafsız",
    "Prestijli Sitede Aileye Uygun",
    "Yatırıma Uygun Yüksek Kira Getirili",
    "Geniş Salonlu ve Ada Mutfaklı",
    "Giyinme Odalı ve Ebeveyn Banyolu",
    "Doğa ile İç İçe Sakin ve Huzurlu",
    "Merkezi Lokasyonda Akıllı Ev Donanımlı",
]

TITLES_COMMERCIAL = [
    "Ana Cadde Üstü Yüksek Cirolu ve Prestijli",
    "Tabela Değeri Yüksek Kurumsal Kiracılı",
    "Metro Çıkışına Sıfır Geniş Vitrinli",
    "Plaza Katında Taşınmaya Hazır Lüks Ofis",
    "Bölümlü ve Toplantı Odalı Executive Ofis",
    "Geniş Cepheli ve Asma Katlı Ticari Mağaza",
    "TIR ve Kamyon Girişine Uygun Yüksek Tavanlı Depo",
    "Klinik, Kafe veya Banka Şubesine Uygun Köşe",
]


def generate_500_listings() -> pd.DataFrame:
    rows = []
    building_feature_pool = [
        item.strip()
        for feature_set in BUILDING_FEATURE_SETS
        for item in feature_set.split(";")
        if item.strip()
    ]
    
    for i in range(500):
        row_rng = random.Random(101_003 + i * 7_919)
        # 1. Lokasyon seçimi
        loc = LOCATIONS[i % len(LOCATIONS)]
        city, district, neighborhood, loc_desc = loc
        
        # 2. İlan Tipi: Yaklaşık %68 Satılık, %32 Kiralık
        is_rental = (i % 3 == 2) or (i % 7 == 0)
        listing_type = "Kiralık" if is_rental else "Satılık"
        price_period = "Aylık" if is_rental else "Satış"
        
        # 3. Mülk Profili: Konut / Ticari / Arsa
        profile_index = (i + i // len(LOCATIONS)) % len(PROPERTY_PROFILES)
        profile = PROPERTY_PROFILES[profile_index]
        category, prop_type, room_options, img_path = profile
        room = row_rng.choice(room_options)
        
        # 4. Alan Hesabı
        if category == "Arsa":
            gross_m2 = 350 + (i * 37) % 1200
            net_m2 = gross_m2
            room = "Müstakil Parsel"
        elif "Açık" in room or "Plaza" in prop_type or "Depo" in prop_type:
            gross_m2 = 120 + (i * 29) % 650
            net_m2 = int(gross_m2 * 0.88)
        else:
            try:
                parts = room.split("+")
                room_num = sum(int(p) for p in parts)
            except Exception:
                room_num = 3
            gross_m2 = 45 + room_num * 28 + (i * 11) % 75
            if prop_type in {"Villa", "Müstakil Ev"}:
                gross_m2 += 140
            net_m2 = int(gross_m2 * (0.80 + (i % 5) * 0.015))
        
        # 5. Bina Yaşı ve Deprem Yönetmeliği
        building_age = row_rng.randint(0, 23)
        if building_age <= 6:
            earthquake_reg = "2018 Sonrası Deprem Yönetmeliği"
        elif building_age <= 17:
            earthquake_reg = "2007-2018 Deprem Yönetmeliği"
        else:
            earthquake_reg = "2007 Öncesi Yapı"
            
        total_floors = 3 + (i % 18)
        if prop_type in {"Villa", "Müstakil Ev"}:
            total_floors = 2 + (i % 2)
            floor = "Müstakil"
        elif prop_type == "Bahçe Katı":
            floor = "Bahçe Katı"
        elif prop_type == "Çatı Katı":
            floor = f"{total_floors}. Kat (Çatı)"
        elif prop_type == "Dükkan / Mağaza":
            floor = "Düz Giriş"
        elif prop_type == "Depo / Atölye":
            floor = "Zemin / Rampa"
        elif category == "Arsa":
            floor = "-"
            total_floors = 0
        else:
            floor = str(1 + (i % total_floors))
            
        # 6. Fiyatlandırma
        # Bölgesel Çarpan
        base_multiplier = 1.0
        if district in {"Bebek", "Etiler", "Fenerbahçe", "Caddebostan", "Kekliktepe", "Yalıkavak", "Levent"}:
            base_multiplier = 2.4
        elif district in {"Sarıyer", "Suadiye", "Çengelköy", "Moda", "Alaçatı", "Oran", "Bademli"}:
            base_multiplier = 1.8
        elif district in {"Bakırköy", "Ataköy", "Bomonti", "Nişantaşı", "Maslak", "Mavişehir", "Lara"}:
            base_multiplier = 1.4
        elif district in {"Başakşehir", "Çankaya", "Kartal", "Maltepe", "Konyaaltı", "Bornova"}:
            base_multiplier = 1.1
        else:
            base_multiplier = 0.85
            
        if is_rental:
            # Kiralık Fiyatı: 18.000 TL - 350.000 TL
            base_rental = 180 * gross_m2 * base_multiplier
            if category == "Ticari":
                base_rental *= 1.3
            elif prop_type == "Villa":
                base_rental *= 1.5
            price = int(round(base_rental / 1000) * 1000)
            price = max(15_000, min(380_000, price))
            estimated_rent = price
            # Satış değeri eşdeğeri
            equiv_sale_price = price * row_rng.randint(180, 240)
            roi_years = round(equiv_sale_price / (price * 12), 1)
            annual_roi = round((price * 12 / equiv_sale_price) * 100, 2)
        else:
            # Satılık Fiyatı: 2.800.000 TL - 95.000.000 TL
            base_sale = 42_000 * gross_m2 * base_multiplier
            if prop_type == "Villa":
                base_sale *= 1.45
            elif category == "Ticari":
                base_sale *= 1.25
            price = int(round(base_sale / 50_000) * 50_000)
            price = max(2_600_000, min(95_000_000, price))
            # Tahmini kira getirisi
            estimated_rent = int(price / row_rng.randint(190, 240))
            roi_years = round(price / (estimated_rent * 12), 1)
            annual_roi = round((estimated_rent * 12 / price) * 100, 2)
            
        # 7. Kriter Değerleri
        bathrooms = 1
        if category != "Arsa":
            bathrooms = max(1, min(5, int(gross_m2 / 65)))
        master_bath = bathrooms >= 2 and prop_type not in {"Dükkan / Mağaza", "Depo / Atölye"}
        
        balcony = prop_type not in {"Dükkan / Mağaza", "Depo / Atölye"} and row_rng.random() < 0.72
        in_complex = (category != "Arsa") and (prop_type not in {"Müstakil Ev"}) and row_rng.random() < 0.76
        near_metro = (district not in {"Urla", "Çeşme", "Bodrum"}) and row_rng.random() < 0.68
        furnished = row_rng.random() < (0.55 if is_rental else 0.18)
        elevator = total_floors > 3 or prop_type == "Plaza Katı"
        smart_home = (building_age <= 5 and row_rng.random() < 0.8) or row_rng.random() < 0.22
        ev_charging = in_complex and row_rng.random() < (0.65 if building_age <= 6 else 0.18)
        
        parking = row_rng.choice(PARKING_TYPES)
        if ev_charging and "EV Şarj" not in parking:
            parking = "2 Araçlık Kapalı + EV Şarj"
            
        heating = row_rng.choice(HEATING_TYPES)
        facade = row_rng.choice(FACADES)
        security = row_rng.choice(SECURITY_TYPES)
        view = row_rng.choice(VIEW_TYPES)
        outdoor = row_rng.choice(OUTDOOR_SPACES)
        kitchen = row_rng.choice(KITCHEN_TYPES)
        
        deed = "Kat Mülkiyeti (İskanlı)" if building_age <= 18 else "Kat İrtifakı (İskanlı)"
        if category == "Arsa":
            deed = "Müstakil Parsel Tapu"
        credit_eligible = i % 12 != 0
        iskan_status = "İskanlı / Yapı Kullanım İzinli" if credit_eligible else "İskan Başvurusunda"
        
        if is_rental:
            usage = "Boş (Hemen Taşınmaya Hazır)" if i % 3 == 0 else "Kiracıya Uygun / Tahliye Edilecek"
        else:
            usage = "Boş (Hemen Taşınmaya Hazır)" if i % 2 == 0 else ("Kiracılı (Yüksek Getirili)" if i % 3 == 0 else "Mülk Sahibi Oturuyor")
            
        dues = 650 + (i % 15) * 350
        if in_complex and "Lüks" in security:
            dues += 1500
        if category == "Arsa":
            dues = 0
            
        # 8. Başlık ve Açıklama
        if category == "Ticari":
            adjective = TITLES_COMMERCIAL[i % len(TITLES_COMMERCIAL)]
        else:
            adjective = TITLES_RESIDENTIAL[i % len(TITLES_RESIDENTIAL)]
            
        title = f"{neighborhood} bölgesinde {listing_type} {room} {prop_type} - {adjective}"
        
        # 9. Pros & Cons (Artılar & Eksiler)
        pros_list = []
        cons_list = []
        
        # Dinamik Artılar
        if earthquake_reg == "2018 Sonrası Deprem Yönetmeliği":
            pros_list.append("2018 sonrası güncel deprem yönetmeliğine tam uygun radye temel ve C35 betonarme yapı")
        if near_metro:
            pros_list.append("Metro / toplu taşıma istasyonuna 3-5 dakika yürüme mesafesinde üstün ulaşım avantajı")
        if "Deniz" in view or "Boğaz" in view:
            pros_list.append(f"Kapanmaz ferah {view} manzarası")
        if ev_charging:
            pros_list.append("Kapalı otoparkta elektrikli araç (EV) şarj ünitesi hazır")
        if master_bath:
            pros_list.append("Ebeveyn banyosu ve bağımsız giyinme odası konforu")
        if smart_home:
            pros_list.append("Akıllı ev otomasyonu ile aydınlatma, iklimlendirme ve güvenlik uzaktan kontrol edilebilir")
        if in_complex:
            pros_list.append("7/24 güvenlikli ve zengin sosyal donatılı prestijli site yerleşimi")
        if annual_roi >= 6.0:
            pros_list.append(f"Yıllık %{annual_roi} brüt getiri ve {roi_years} yıl hızlı amortisman potansiyeli")
            
        # Fallback pros
        while len(pros_list) < 4:
            pool = PROS_POOL["ticari"] if category == "Ticari" else PROS_POOL["genel"]
            p_cand = pool[(i * 3 + len(pros_list)) % len(pool)]
            if p_cand not in pros_list:
                pros_list.append(p_cand)
        pros_text = " • ".join(pros_list[:4])
        
        # Dinamik Eksiler
        if dues >= 3500:
            cons_list.append(f"Aylık {dues:,} TL site aidat bedeli bütçe planlamasında dikkate alınmalıdır")
        if building_age >= 18:
            cons_list.append(f"Bina yaşı {building_age} yıl; ortak alanlarda periyodik bakım veya yenileme gerekebilir")
        if not near_metro:
            cons_list.append("Metroya yürüme mesafesi uzaktır; şahsi araç veya servis/otobüs gerekmektedir")
        if "Kuzey" in facade:
            cons_list.append("Kuzey cephe olması nedeniyle kış aylarında ısınma gideri bir miktar yüksek olabilir")
        if not balcony:
            cons_list.append("Açık balkon alanı bulunmamaktadır; iç mekan net alanı maksimize edilmiştir")
        if not elevator and total_floors > 2:
            cons_list.append("Binada asansör bulunmamaktadır; merdiven kullanımı gerektirir")
            
        # Fallback cons
        while len(cons_list) < 2:
            pool = CONS_POOL["ticari"] if category == "Ticari" else CONS_POOL["genel"]
            c_cand = pool[(i * 2 + len(cons_list)) % len(pool)]
            if c_cand not in cons_list:
                cons_list.append(c_cand)
        cons_text = " • ".join(cons_list[:3])
        
        highlight = (
            f"{loc_desc}. {pros_list[0]}. {gross_m2} m² brüt / {net_m2} m² net kullanım alanı sunmaktadır."
        )
        
        description = (
            f"{city} {district}, {neighborhood} mevkiinde yer alan {listing_type.lower()} {prop_type}. "
            f"{room} planında, {gross_m2} m² brüt alana sahip. {earthquake_reg} standartlarında inşa edilmiş, "
            f"{facade} cepheli ve {heating} sistemlidir. {highlight}"
        )
        
        rows.append({
            "listing_id": f"PRT-{i + 1:03d}",
            "title": title,
            "listing_type": listing_type,
            "city": city,
            "district": district,
            "neighborhood": neighborhood,
            "property_category": category,
            "property_type": prop_type,
            "room_count": room,
            "price": price,
            "price_period": price_period,
            "gross_m2": gross_m2,
            "net_m2": net_m2,
            "building_age": building_age,
            "earthquake_regulation": earthquake_reg,
            "floor": floor,
            "total_floors": total_floors,
            "bathroom_count": bathrooms,
            "master_bathroom": master_bath,
            "heating": heating,
            "facade": facade,
            "balcony": balcony,
            "outdoor_space": outdoor,
            "in_complex": in_complex,
            "near_metro": near_metro,
            "furnished": furnished,
            "elevator": elevator,
            "parking": parking,
            "ev_charging": ev_charging,
            "security": security,
            "view": view,
            "kitchen_type": kitchen,
            "deed_status": deed,
            "credit_eligible": credit_eligible,
            "iskan_status": iskan_status,
            "usage_status": usage,
            "dues": dues,
            "amenities": AMENITY_SETS[i % len(AMENITY_SETS)],
            "nearby_places": NEARBY_SETS[i % len(NEARBY_SETS)],
            "technical_details": TECHNICAL_SETS[i % len(TECHNICAL_SETS)],
            "building_features": "\n".join(
                f"{feature_number + 1}. {feature}"
                for feature_number, feature in enumerate(row_rng.sample(building_feature_pool, 10))
            ),
            "smart_home": smart_home,
            "estimated_monthly_rent": estimated_rent,
            "roi_years": roi_years,
            "annual_roi_pct": annual_roi,
            "pros": pros_text,
            "cons": cons_text,
            "description": description,
            "highlight": highlight,
            "listing_url": f"https://example.com/ilan/PRT-{i + 1:03d}",
            "image_url": img_path,
            "status": "active",
        })
        
    listings = pd.DataFrame(rows, columns=LISTING_COLUMNS)

    scenario_overrides = [
        {
            "title": "Kayaşehir bölgesinde Satılık 3+1 Daire - Metroya Yakın Aile Evi",
            "listing_type": "Satılık", "city": "İstanbul", "district": "Başakşehir",
            "neighborhood": "Kayaşehir", "property_category": "Konut", "property_type": "Daire",
            "room_count": "3+1", "price": 7_850_000, "price_period": "Satış", "gross_m2": 145,
            "net_m2": 126, "building_age": 3, "floor": "5", "total_floors": 12,
            "balcony": True, "in_complex": True, "near_metro": True, "furnished": False,
            "parking": "2 Araçlık Kapalı Otopark", "security": "7/24 Güvenlik + CCTV + Kartlı Geçiş",
            "outdoor_space": "Geniş Cam Balkon", "view": "Açık Yeşil Alan Manzarası",
            "estimated_monthly_rent": 39_000, "roi_years": 16.8, "annual_roi_pct": 5.96,
            "highlight": "Metroya yürüyerek 4 dakika; okul ve parka yakın, güvenlikli aile sitesi.",
            "description": "Kayaşehir'de güvenlikli sitede, balkonlu, ferah ve masrafsız 3+1 aile dairesi.",
            "image_url": "assets/family-complex-thumb.webp",
        },
        {
            "title": "Kayaşehir bölgesinde Satılık 1+1 Rezidans - Eşyalı Yatırım Fırsatı",
            "listing_type": "Satılık", "city": "İstanbul", "district": "Başakşehir",
            "neighborhood": "Kayaşehir", "property_category": "Konut", "property_type": "Rezidans",
            "room_count": "1+1", "price": 4_350_000, "price_period": "Satış", "gross_m2": 68,
            "net_m2": 55, "building_age": 2, "floor": "9", "total_floors": 18,
            "balcony": True, "in_complex": True, "near_metro": True, "furnished": True,
            "smart_home": True, "parking": "1 Araçlık Kapalı Otopark + EV Şarj",
            "estimated_monthly_rent": 28_500, "roi_years": 12.7, "annual_roi_pct": 7.86,
            "highlight": "Tam eşyalı, metroya yakın ve yüksek kira talebi olan anahtar teslim rezidans.",
            "description": "Kısa ve uzun dönem kiralamaya uygun, yönetimi kolay, eşyalı 1+1 yatırım dairesi.",
            "image_url": "assets/smart-studio-thumb.webp",
        },
        {
            "title": "Zekeriyaköy bölgesinde Satılık 3+1 Müstakil Ev - Özel Bahçeli",
            "listing_type": "Satılık", "city": "İstanbul", "district": "Sarıyer",
            "neighborhood": "Zekeriyaköy", "property_category": "Konut", "property_type": "Müstakil Ev",
            "room_count": "3+1", "price": 6_950_000, "price_period": "Satış", "gross_m2": 190,
            "net_m2": 155, "building_age": 7, "floor": "Müstakil", "total_floors": 2,
            "balcony": True, "in_complex": False, "near_metro": False, "furnished": False,
            "outdoor_space": "180 m² Müstakil Bahçe + Veranda", "view": "Orman / Doğa Manzarası",
            "estimated_monthly_rent": 34_000, "roi_years": 17.0, "annual_roi_pct": 5.87,
            "highlight": "Sessiz sokakta 180 m² bağımsız bahçe, veranda ve iki araçlık otopark.",
            "description": "Doğayla iç içe, çocuklu aile ve evcil hayvan yaşamına uygun müstakil 3+1 ev.",
            "image_url": "assets/villa-garden-thumb.webp",
        },
        {
            "title": "Başakşehir bölgesinde Satılık 4+1 Daire - Geniş ve Yeni",
            "listing_type": "Satılık", "city": "İstanbul", "district": "Başakşehir",
            "neighborhood": "Bahçeşehir 1. Kısım", "property_category": "Konut", "property_type": "Daire",
            "room_count": "4+1", "price": 11_850_000, "price_period": "Satış", "gross_m2": 220,
            "net_m2": 188, "building_age": 2, "floor": "7", "total_floors": 14,
            "balcony": True, "in_complex": True, "near_metro": True, "furnished": False,
            "master_bathroom": True, "parking": "2 Araçlık Kapalı Otopark + EV Şarj",
            "estimated_monthly_rent": 59_000, "roi_years": 16.7, "annual_roi_pct": 5.97,
            "highlight": "188 m² net kullanım, ebeveyn banyosu ve geniş aile yaşamına uygun plan.",
            "description": "Yeni binada, çift cepheli, geniş salonlu ve güvenlikli site içinde 4+1 daire.",
            "image_url": "assets/family-complex-thumb.webp",
        },
    ]
    for row_index, override in enumerate(scenario_overrides):
        for column, value in override.items():
            listings.at[row_index, column] = value

    return listings


if __name__ == "__main__":
    df = generate_500_listings()
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig", lineterminator="\n")
    print(f"500 listings created: {OUTPUT}")
    print("Listing types:", df["listing_type"].value_counts().to_dict())
    print("Categories:", df["property_category"].value_counts().to_dict())
    print("Property types:", df["property_type"].value_counts().to_dict())
