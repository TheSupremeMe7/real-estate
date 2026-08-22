"""Broad Turkish real-estate vocabulary used to ground AI request parsing."""

SPACES = [
    "salon", "mutfak", "ada mutfak", "kapalı mutfak", "açık mutfak",
    "ebeveyn odası", "çocuk odası", "misafir odası", "çalışma odası",
    "ev ofisi", "giyinme odası", "çamaşır odası", "kiler", "depo",
    "balkon", "teras", "veranda", "kış bahçesi", "özel bahçe",
    "hobi odası", "oyun odası", "sinema odası", "spor odası", "sauna",
    "hamam", "ebeveyn banyosu", "misafir banyosu", "kapalı garaj",
    "açık otopark", "çatı terası", "avlu", "müştemilat", "atölye",
    "kitaplık alanı", "yemek alanı", "antre", "koridor", "çocuk banyosu",
]

SPACE_QUALITIES = [
    "geniş", "ferah", "aydınlık", "güneş alan", "yüksek tavanlı",
    "manzaralı", "sessiz", "ayrı", "gömme dolaplı", "yerden ısıtmalı",
]

AMENITIES = [
    "yüzme havuzu", "açık havuz", "kapalı havuz", "çocuk havuzu",
    "spor salonu", "pilates salonu", "tenis kortu", "basketbol sahası",
    "çocuk parkı", "yürüyüş parkuru", "bisiklet parkuru", "sosyal tesis",
    "site güvenliği", "7/24 güvenlik", "kamera sistemi", "kapıcı",
    "resepsiyon", "concierge", "jeneratör", "su deposu", "hidrofor",
    "yük asansörü", "asansör", "engelli rampası", "engelsiz giriş",
    "elektrikli araç şarjı", "kapalı otopark", "misafir otoparkı",
    "vale hizmeti", "akıllı ev", "akıllı ısıtma", "akıllı panjur",
    "merkezi ısıtma", "kombi", "ısı pompası", "klima", "şömine",
    "güneş paneli", "ısı yalıtımı", "ses yalıtımı", "çift cam",
    "fiber internet", "uydu sistemi", "ankastre mutfak", "ada mutfak",
    "çelik kapı", "yangın alarmı", "sprinkler", "deprem yönetmeliği",
    "sığınak", "site içi market", "kafe", "restoran", "kreş",
    "evcil hayvan alanı", "köpek parkı", "barbekü alanı", "pergola",
    "peyzajlı bahçe", "meyve bahçesi", "özel havuz", "ortak bahçe",
    "deniz manzarası", "göl manzarası", "orman manzarası", "şehir manzarası",
    "boğaz manzarası", "doğa manzarası", "vadi manzarası", "park manzarası",
    "ön cephe", "arka cephe", "köşe daire", "ara kat", "üst kat",
    "bahçe katı", "çatı katı", "müstakil giriş", "ayrı giriş",
    "çift cephe", "güney cephe", "kuzey cephe", "doğu cephe", "batı cephe",
]

LOCATION_FEATURES = [
    "metroya yakın", "metrobüse yakın", "otobüs durağına yakın",
    "tramvaya yakın", "marmaraya yakın", "iskeleye yakın", "havaalanına yakın",
    "ana yola yakın", "otoyola yakın", "köprüye yakın", "okula yakın",
    "üniversiteye yakın", "hastaneye yakın", "aile sağlığı merkezine yakın",
    "eczane yakın", "markete yakın", "alışveriş merkezine yakın", "çarşıya yakın",
    "sahile yakın", "parka yakın", "ormana yakın", "spor tesisine yakın",
    "iş merkezine yakın", "sanayi bölgesine yakın", "merkezi konum",
    "yürünebilir konum", "sakin sokak", "az katlı bölge", "prestijli bölge",
    "yatırım bölgesi", "kira getirisi yüksek", "aile mahallesi", "öğrenciye uygun",
    "turistik bölge", "denize sıfır", "orman içinde", "site içinde",
    "müstakil yaşam", "toplu taşımaya yakın", "servis güzergahında",
]


def build_feature_catalog(limit: int = 500) -> list[str]:
    combined = [f"{quality} {space}" for space in SPACES for quality in SPACE_QUALITIES]
    catalog = list(dict.fromkeys(AMENITIES + LOCATION_FEATURES + combined))
    return catalog[:limit]


PROPERTY_FEATURE_CATALOG = build_feature_catalog()
assert len(PROPERTY_FEATURE_CATALOG) == 500
