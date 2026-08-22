import random
from pathlib import Path

import pandas as pd

from sheet_store import LISTING_COLUMNS


OUTPUT = Path(__file__).parent / "listings.csv"
random.seed(42)

LOCATIONS = [
    ("İstanbul", "Başakşehir", "Kayaşehir"),
    ("İstanbul", "Başakşehir", "Bahçeşehir"),
    ("İstanbul", "Beylikdüzü", "Adnan Kahveci"),
    ("İstanbul", "Kadıköy", "Fenerbahçe"),
    ("İstanbul", "Üsküdar", "Çengelköy"),
    ("İstanbul", "Sarıyer", "Zekeriyaköy"),
    ("İstanbul", "Şişli", "Bomonti"),
    ("İstanbul", "Bakırköy", "Ataköy"),
    ("İstanbul", "Kartal", "Yakacık"),
    ("İstanbul", "Maltepe", "Altayçeşme"),
    ("Ankara", "Çankaya", "Oran"),
    ("İzmir", "Urla", "İskele"),
]

TYPES = [
    ("Daire", ["1+1", "2+1", "3+1", "4+1"], "assets/city-apartment-thumb.webp"),
    ("Bahçe Katı", ["2+1", "3+1", "4+1"], "assets/garden-flat-thumb.webp"),
    ("Villa", ["4+1", "5+1", "6+2", "7+2"], "assets/villa-garden-thumb.webp"),
    ("Dubleks", ["3+1", "4+1", "5+1"], "assets/penthouse-terrace-thumb.webp"),
    ("Rezidans", ["1+0", "1+1", "2+1", "3+1"], "assets/smart-studio-thumb.webp"),
    ("Müstakil Ev", ["2+1", "3+1", "4+1", "5+2"], "assets/villa-garden-thumb.webp"),
    ("Çatı Katı", ["2+1", "3+1", "4+1"], "assets/penthouse-terrace-thumb.webp"),
]

HIGHLIGHTS = [
    "Salondan çıkılan, gün boyu güneş alan geniş özel bahçe",
    "Kesintisiz şehir manzaralı 28 m² köşe balkon",
    "Elektrikli araç şarj ünitesine hazır iki araçlık kapalı otopark",
    "Ebeveyn banyosu ve bağımsız giyinme odası",
    "Metro girişine yürüyerek yalnızca üç dakika",
    "Sessiz avluya bakan ve çalışma alanına dönüşebilen kış bahçesi",
    "Çocuk parkını doğrudan gören güvenli aile yerleşimi",
    "Masrafsız, ankastreleri yenilenmiş ve hemen taşınmaya hazır",
    "Yüksek tavanı ve tavandan zemine camlarıyla ferah yaşam alanı",
    "Ayrı girişli misafir odası veya ev ofisi kullanımı",
    "Deniz manzarasının kapanmayacağı ön cephe konumu",
    "Isı pompası ve güneş paneli altyapısıyla düşük enerji gideri",
    "Ada mutfak ve sekiz kişilik yemek alanıyla güçlü sosyal plan",
    "Site içindeki spor salonu ve yüzme havuzuna yakın blok",
    "Evcil hayvanlar için çevrili özel bahçe ve yıkama alanı",
    "Kiler, çamaşır odası ve gömme dolaplarla yüksek depolama kapasitesi",
    "İki aile kullanımına uygun bölünebilir dubleks plan",
    "Geniş terasında pergola ve açık hava mutfağı altyapısı",
    "Kuzey-güney çift cephe sayesinde doğal hava dolaşımı",
    "Okul ve günlük ihtiyaçlara araçsız ulaşılabilen merkezi konum",
]

ADJECTIVES = ["Ferah", "Modern", "Bahçeli", "Manzaralı", "Aile Dostu", "Yatırımlık", "Sakin", "Prestijli"]
EXTRA_DETAILS = [
    "doğu cephesindeki odaları sabah ışığını doğrudan alıyor",
    "telefonla kontrol edilen akıllı ısıtma ve panjur sistemi bulunuyor",
    "daireye ait kilitli depo alanı satış fiyatına dahil",
    "aynı kattaki tek daire olması sayesinde yüksek mahremiyet sunuyor",
    "engelsiz giriş ve geniş asansörle her yaş için rahat kullanım sağlıyor",
]


def make_listings(count: int = 100) -> pd.DataFrame:
    rows = []
    for index in range(count):
        city, district, neighborhood = LOCATIONS[index % len(LOCATIONS)]
        property_type, rooms, image = TYPES[index % len(TYPES)]
        room = rooms[(index // len(TYPES)) % len(rooms)]
        room_total = sum(int(part) for part in room.split("+"))
        gross_m2 = 38 + room_total * 24 + (index * 7) % 65
        if property_type in {"Villa", "Müstakil Ev"}:
            gross_m2 += 90
        price = 2_150_000 + gross_m2 * 41_000 + (index % 12) * 175_000
        highlight = (
            f"{HIGHLIGHTS[index % len(HIGHLIGHTS)]}; "
            f"{EXTRA_DETAILS[(index // len(HIGHLIGHTS)) % len(EXTRA_DETAILS)]}"
        )
        balcony = property_type not in {"Rezidans"} or index % 3 != 0
        in_complex = property_type not in {"Müstakil Ev"} and index % 5 != 0
        near_metro = district not in {"Urla", "Sarıyer"} and index % 4 != 0
        rows.append(
            {
                "listing_id": f"ILN-{index + 1:03d}",
                "title": f"{neighborhood}'de {ADJECTIVES[index % len(ADJECTIVES)]} {room} {property_type}",
                "city": city,
                "district": district,
                "neighborhood": neighborhood,
                "property_type": property_type,
                "room_count": room,
                "price": price,
                "gross_m2": gross_m2,
                "balcony": balcony,
                "in_complex": in_complex,
                "near_metro": near_metro,
                "description": f"{neighborhood} merkezine yakın, iyi planlanmış {gross_m2} m² yaşam alanı. {highlight}.",
                "highlight": highlight,
                "listing_url": f"https://example.com/ilan/ILN-{index + 1:03d}",
                "image_url": image if index % 6 else "assets/family-complex-thumb.webp",
                "status": "active",
            }
        )
    return pd.DataFrame(rows, columns=LISTING_COLUMNS)


if __name__ == "__main__":
    listings = make_listings()
    listings.to_csv(OUTPUT, index=False, encoding="utf-8-sig", lineterminator="\n")
    print(f"{len(listings)} ilan yazıldı: {OUTPUT}")
