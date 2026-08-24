"""Müşteri talebini Gemini veya akıllı yedek motor ile doğrulanmış emlak kriterlerine dönüştürür."""

import logging
import os
import re
from enum import Enum

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError, model_validator

# SDK seviyesindeki otomatik fonksiyon çağırma (AFC) uyarılarını bastır
logging.getLogger("google.genai").setLevel(logging.ERROR)


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
FALLBACK_GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]


class SourceStatus(str, Enum):
    """Bir kriterin müşteri talebinde bulunma biçimi."""

    EXPLICIT = "explicit"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class LocationCriteria(BaseModel):
    city: str | None = None
    district: str | None = None
    neighborhoods: list[str] = Field(default_factory=list)


class PriceCriteria(BaseModel):
    minimum: int | None = Field(default=None, ge=0)
    maximum: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> "PriceCriteria":
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("Minimum fiyat maksimum fiyattan büyük olamaz.")
        return self


class AreaCriteria(BaseModel):
    minimum_net_m2: int | None = Field(default=None, ge=0)
    minimum_gross_m2: int | None = Field(default=None, ge=0)


class RequirementFlags(BaseModel):
    in_complex: bool | None = None
    balcony: bool | None = None
    furnished: bool | None = None
    near_metro: bool | None = None


class CriteriaSources(BaseModel):
    location: SourceStatus = SourceStatus.UNKNOWN
    property_type: SourceStatus = SourceStatus.UNKNOWN
    transaction_type: SourceStatus = SourceStatus.UNKNOWN
    room_count: SourceStatus = SourceStatus.UNKNOWN
    price: SourceStatus = SourceStatus.UNKNOWN
    area: SourceStatus = SourceStatus.UNKNOWN
    in_complex: SourceStatus = SourceStatus.UNKNOWN
    balcony: SourceStatus = SourceStatus.UNKNOWN
    furnished: SourceStatus = SourceStatus.UNKNOWN
    near_metro: SourceStatus = SourceStatus.UNKNOWN
    features: SourceStatus = SourceStatus.UNKNOWN


class CustomerCriteria(BaseModel):
    """Gemini veya kural motoru yanıtının uyması gereken kesin veri yapısı."""

    location: LocationCriteria = Field(default_factory=LocationCriteria)
    property_type: str | None = None
    transaction_type: str | None = None
    room_count: list[str] = Field(default_factory=list)
    price: PriceCriteria = Field(default_factory=PriceCriteria)
    area: AreaCriteria = Field(default_factory=AreaCriteria)
    hard_requirements: RequirementFlags = Field(
        default_factory=RequirementFlags,
        description=(
            "Yalnızca müşteri mutlaka, şart, zorunlu veya olmazsa olmaz diyorsa "
            "doldur. Site içinde doğrudan ev istemesi de kesin filtre sayılır."
        ),
    )
    soft_preferences: RequirementFlags = Field(
        default_factory=RequirementFlags,
        description=(
            "Tercihleri doldur. Balkon/metro/eşya için yalnızca 'olsun' denmesi "
            "soft tercihtir; mutlaka/şart/zorunlu denmedikçe hard değildir."
        ),
    )
    desired_features: list[str] = Field(
        default_factory=list,
        description="Müşterinin açıkça istediği diğer manzara, donanım, bina ve çevre özellikleri.",
    )
    excluded_features: list[str] = Field(
        default_factory=list,
        description="Müşterinin açıkça istemediği özellikler.",
    )
    sources: CriteriaSources = Field(default_factory=CriteriaSources)
    analysis_method: str = Field(default="Kural motoru", exclude=True)


class CriteriaParserError(RuntimeError):
    """Arayüzde güvenli biçimde gösterilebilecek hata."""


SYSTEM_INSTRUCTION = """
Sen Türkçe emlak müşteri taleplerini yapılandırılmış kriterlere dönüştüren bir
veri çıkarma motorusun. Yalnızca müşterinin söylediği bilgileri kullan.

Kurallar:
- Söylenmeyen değerleri asla uydurma; null, boş liste ve unknown kullan.
- Para değerlerini tam TL olarak yaz: "8 milyon" -> 8000000, "7.5 milyon" -> 7500000, "500 bin" -> 500000.
- Oda sayısını standartlaştır: "3 oda 1 salon" ve "üç artı bir" -> "3+1".
- Konum yazımını standart Türkçe biçime getir.
- Kesin, zorunlu, "olmazsa olmaz", "geçmesin", "şart", "mutlaka" ifadeleri hard requirement.
- Balkon, metro, eşya gibi özelliklerde tek başına "olsun/olmasın" ifadesini soft preference say.
  Bunları ancak "mutlaka", "şart", "zorunlu" veya "olmazsa olmaz" açıkça denmişse hard requirement yap.
- "Olsa iyi olur", "tercih ederim", "mümkünse" ifadeleri soft preference.
- Aynı özellik hem hard_requirements hem soft_preferences içinde dolu olamaz.
- Açıkça söylenen bilgi explicit, yalnızca güvenli/coğrafi normalizasyon inferred, talepte bulunmayan bilgi unknown olmalıdır.
- "Kayaşehir" semt ifadesini neighborhood olarak Kayaşehir yaz; ilçe açıkça söylenmediyse Başakşehir'i inferred ekle.
- near_metro yalnızca metro/istasyon/yürüme bağlantısı açıkça istenmişse dolsun.
- Manzara, otopark, asansör, akıllı ev, elektrikli araç şarjı, havuz, güvenlik,
  ebeveyn banyosu, iskan, kredi uygunluğu ve benzeri açık istekleri desired_features listesine kısa Türkçe ifadelerle ekle.
- Müşteri bir özelliği istemediğini söylüyorsa excluded_features listesine ekle.
- Müşterinin metnindeki kişisel bilgileri çıktıya alma.

Kesin sınıflandırma örneği:
"Kayaşehir'de site içerisinde 3+1, maksimum 8 milyon TL. Metro yakın olsun, balkon da tercih ederim."
Bu örnekte in_complex=true hard_requirements içindedir; near_metro=true ve balcony=true ise soft_preferences içindedir.
"""


LOCATION_CATALOG = [
    ("İstanbul", "Başakşehir", "Bahçeşehir 1. Kısım"),
    ("İstanbul", "Başakşehir", "Kayaşehir"),
    ("İstanbul", "Beşiktaş", "Bebek"),
    ("İstanbul", "Beşiktaş", "Levent"),
    ("İstanbul", "Beşiktaş", "Etiler"),
    ("İstanbul", "Sarıyer", "Zekeriyaköy"),
    ("İstanbul", "Sarıyer", "Maslak"),
    ("İstanbul", "Sarıyer", "Tarabya"),
    ("İstanbul", "Şişli", "Bomonti"),
    ("İstanbul", "Şişli", "Nişantaşı"),
    ("İstanbul", "Bakırköy", "Ataköy"),
    ("İstanbul", "Bakırköy", "Florya"),
    ("İstanbul", "Beylikdüzü", "Adnan Kahveci"),
    ("İstanbul", "Beylikdüzü", "Yakuplu"),
    ("İstanbul", "Kadıköy", "Fenerbahçe"),
    ("İstanbul", "Kadıköy", "Caddebostan"),
    ("İstanbul", "Kadıköy", "Moda"),
    ("İstanbul", "Kadıköy", "Suadiye"),
    ("İstanbul", "Üsküdar", "Çengelköy"),
    ("İstanbul", "Üsküdar", "Kandilli"),
    ("İstanbul", "Kartal", "Yakacık"),
    ("İstanbul", "Maltepe", "Altayçeşme"),
    ("İstanbul", "Maltepe", "Küçükyalı"),
    ("İstanbul", "Çekmeköy", "Merkez"),
    ("Ankara", "Çankaya", "Oran"),
    ("Ankara", "Çankaya", "Gaziosmanpaşa"),
    ("Ankara", "Çankaya", "Çayyolu"),
    ("Ankara", "Çankaya", "İncek"),
    ("Ankara", "Çankaya", "Ümitköy"),
    ("İzmir", "Urla", "İskele"),
    ("İzmir", "Urla", "Kekliktepe"),
    ("İzmir", "Çeşme", "Alaçatı"),
    ("İzmir", "Çeşme", "Ilıca"),
    ("İzmir", "Karşıyaka", "Mavişehir"),
    ("İzmir", "Karşıyaka", "Bostanlı"),
    ("İzmir", "Bornova", "Kazımdirik"),
    ("Antalya", "Muratpaşa", "Lara"),
    ("Antalya", "Konyaaltı", "Liman"),
    ("Muğla", "Bodrum", "Yalıkavak"),
    ("Bursa", "Nilüfer", "Bademli"),
]

FEATURE_PATTERNS = {
    "deniz manzarası": ("deniz manzar", "adalar manzar"),
    "boğaz manzarası": ("boğaz manzar", "bogaz manzar"),
    "şehir manzarası": ("şehir manzar", "sehir manzar"),
    "bahçe": ("bahçe", "bahceli", "müstakil bahçe", "mustakil bahce"),
    "teras": ("teras",),
    "kapalı otopark": ("kapalı otopark", "kapali otopark"),
    "otopark": ("otopark", "garaj"),
    "asansör": ("asansör", "asansor"),
    "elektrikli araç şarjı": ("ev şarj", "ev sarj", "elektrikli araç", "elektrikli arac"),
    "akıllı ev": ("akıllı ev", "akilli ev", "ev otomasyon"),
    "ebeveyn banyosu": ("ebeveyn banyo",),
    "giyinme odası": ("giyinme oda",),
    "güvenlik": ("güvenlik", "guvenlik", "kamera", "cctv"),
    "yüzme havuzu": ("havuz",),
    "fitness": ("fitness", "spor salon"),
    "sauna": ("sauna", "spa"),
    "çocuk parkı": ("çocuk park", "cocuk park", "oyun alan"),
    "jeneratör": ("jeneratör", "jenerator"),
    "fiber internet": ("fiber", "hızlı internet", "hizli internet"),
    "klima": ("klima", "vrf"),
    "yerden ısıtma": ("yerden ısıtma", "yerden isitma"),
    "krediye uygun": ("krediye uygun", "konut kredisi"),
    "iskanlı": ("iskanlı", "iskanli", "iskan mevcut"),
    "kat mülkiyeti": ("kat mülkiyet", "kat mulkiyet"),
    "eşyalı": ("eşyalı", "esyali", "mobilyalı", "mobilyali"),
}


def _search_text(value: str) -> str:
    translation = str.maketrans("çğıöşü", "cgiosu")
    return value.lower().translate(translation)


def parse_customer_request_heuristic(customer_request: str) -> CustomerCriteria:
    """Gemini API anahtarı olmadığında veya bağlantı hatasında çalışan akıllı kural motoru."""
    text = customer_request.lower()

    # 1. Konum Çıkarma
    neighborhoods = []
    district = None
    city = None
    sources_location = SourceStatus.UNKNOWN
    searchable_text = _search_text(text)
    for candidate_city, candidate_district, candidate_neighborhood in LOCATION_CATALOG:
        if _search_text(candidate_neighborhood) in searchable_text:
            city = candidate_city
            district = candidate_district
            neighborhoods = [candidate_neighborhood]
            sources_location = SourceStatus.EXPLICIT
            break
    if not neighborhoods:
        for candidate_city, candidate_district, _ in LOCATION_CATALOG:
            if _search_text(candidate_district) in searchable_text:
                city = candidate_city
                district = candidate_district
                sources_location = SourceStatus.EXPLICIT
                break
    if city is None:
        for candidate_city in sorted({item[0] for item in LOCATION_CATALOG}, key=len, reverse=True):
            if _search_text(candidate_city) in searchable_text:
                city = candidate_city
                sources_location = SourceStatus.EXPLICIT
                break

    # 2. Oda Sayısı Çıkarma
    room_counts = []
    sources_room = SourceStatus.UNKNOWN
    room_patterns = [
        (r"1\s*\+\s*0|stüdyo|studyo", "1+0"),
        (r"1\s*\+\s*1|bir\s*artı\s*bir|1\s*oda", "1+1"),
        (r"2\s*\+\s*1|iki\s*artı\s*bir|2\s*oda", "2+1"),
        (r"3\s*\+\s*1|üç\s*artı\s*bir|3\s*oda", "3+1"),
        (r"4\s*\+\s*1|dört\s*artı\s*bir|4\s*oda", "4+1"),
        (r"5\s*\+\s*1|beş\s*artı\s*bir", "5+1"),
        (r"5\s*\+\s*2", "5+2"),
        (r"6\s*\+\s*2", "6+2"),
        (r"7\s*\+\s*2", "7+2"),
    ]
    for pattern, room_label in room_patterns:
        if re.search(pattern, text):
            room_counts.append(room_label)
            sources_room = SourceStatus.EXPLICIT

    # 3. Fiyat Çıkarma
    min_price = None
    max_price = None
    sources_price = SourceStatus.UNKNOWN

    # "8 milyon", "7.5 milyon", "500 bin", "8.000.000"
    million_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:milyon|m)\b", text)
    if million_matches:
        prices = [int(float(m.replace(",", ".")) * 1_000_000) for m in million_matches]
        if len(prices) == 1:
            max_price = prices[0]
        else:
            min_price = min(prices)
            max_price = max(prices)
        sources_price = SourceStatus.EXPLICIT
    else:
        thousand_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*bin\b", text)
        if thousand_matches:
            prices = [int(float(value.replace(",", ".")) * 1_000) for value in thousand_matches]
            if len(prices) == 1:
                max_price = prices[0]
            else:
                min_price = min(prices)
                max_price = max(prices)
            sources_price = SourceStatus.EXPLICIT

    if sources_price is SourceStatus.UNKNOWN:
        num_matches = re.findall(r"(\d{1,3}(?:\.\d{3}){1,2})\s*(?:tl)?", text)
        if num_matches:
            prices = [int(n.replace(".", "")) for n in num_matches if int(n.replace(".", "")) > 100_000]
            if prices:
                if len(prices) == 1:
                    max_price = prices[0]
                else:
                    min_price = min(prices)
                    max_price = max(prices)
                sources_price = SourceStatus.EXPLICIT

    # 4. Alan Çıkarma
    min_m2 = None
    sources_area = SourceStatus.UNKNOWN
    m2_match = re.search(r"(\d{2,3})\s*(?:m2|m²|metrekare)", text)
    if m2_match:
        min_m2 = int(m2_match.group(1))
        sources_area = SourceStatus.EXPLICIT

    # 5. Emlak Tipi & İşlem Tipi
    property_type = None
    sources_prop = SourceStatus.UNKNOWN
    if "bahçe katı" in text or "bahce kati" in searchable_text or "bahçeli daire" in text:
        property_type = "Bahçe Katı"
        sources_prop = SourceStatus.EXPLICIT
    elif "rezidans" in text or "residence" in text:
        property_type = "Rezidans"
        sources_prop = SourceStatus.EXPLICIT
    elif "villa" in text:
        property_type = "Villa"
        sources_prop = SourceStatus.EXPLICIT
    elif "müstakil" in text or "mustakil" in text:
        property_type = "Müstakil Ev"
        sources_prop = SourceStatus.EXPLICIT
    elif "dubleks" in text:
        property_type = "Dubleks"
        sources_prop = SourceStatus.EXPLICIT
    elif "çatı katı" in text or "cati kati" in searchable_text:
        property_type = "Çatı Katı"
        sources_prop = SourceStatus.EXPLICIT
    elif any(keyword in text for keyword in ("dükkan", "dukkan", "mağaza", "magaza")):
        property_type = "Dükkan / Mağaza"
        sources_prop = SourceStatus.EXPLICIT
    elif "ofis" in text or "büro" in text or "buro" in text:
        property_type = "Ofis / Büro"
        sources_prop = SourceStatus.EXPLICIT
    elif "plaza katı" in text or "plaza kati" in searchable_text:
        property_type = "Plaza Katı"
        sources_prop = SourceStatus.EXPLICIT
    elif any(keyword in text for keyword in ("depo", "atölye", "atolye")):
        property_type = "Depo / Atölye"
        sources_prop = SourceStatus.EXPLICIT
    elif "arsa" in text:
        property_type = "İmarlı Arsa"
        sources_prop = SourceStatus.EXPLICIT
    elif "daire" in text or "ev" in text:
        property_type = "Daire"
        sources_prop = SourceStatus.EXPLICIT

    transaction_type = None
    if any(keyword in text for keyword in ("kiralık", "kiralik", "kiralamak", "kiraya")):
        transaction_type = "Kiralık"
    elif any(keyword in text for keyword in ("satılık", "satilik", "satın almak", "satın al")):
        transaction_type = "Satılık"

    # 6. Hard vs Soft Tercih Ayrıştırma
    is_hard_rule = any(kw in text for kw in ["mutlaka", "şart", "zorunlu", "olmazsa olmaz", "kesinlikle"])

    in_complex_val = True if any(kw in text for kw in ["site içi", "site icinde", "site içerisinde", "güvenlikli site", "projede"]) else None
    balcony_val = True if any(kw in text for kw in ["balkon", "balkonlu", "teras"]) else None
    furnished_val = True if any(kw in text for kw in ["eşyalı", "esyali", "mobilyalı"]) else None
    near_metro_val = True if any(kw in text for kw in ["metro", "istasyon", "raylı sistem", "marmaray"]) else None

    hard_req = RequirementFlags()
    soft_pref = RequirementFlags()

    if in_complex_val is not None:
        if is_hard_rule or "site" in text:
            hard_req.in_complex = True
        else:
            soft_pref.in_complex = True

    if balcony_val is not None:
        if is_hard_rule and "balkon" in text:
            hard_req.balcony = True
        else:
            soft_pref.balcony = True

    if furnished_val is not None:
        if is_hard_rule and ("eşyalı" in text or "esyali" in text):
            hard_req.furnished = True
        else:
            soft_pref.furnished = True

    if near_metro_val is not None:
        if is_hard_rule and "metro" in text:
            hard_req.near_metro = True
        else:
            soft_pref.near_metro = True

    desired_features: list[str] = []
    excluded_features: list[str] = []
    negative_words = ("istemiyorum", "olmasın", "olmasin", "olmayacak", "hariç", "haric")
    for feature_name, patterns in FEATURE_PATTERNS.items():
        matched_positions = [searchable_text.find(_search_text(pattern)) for pattern in patterns]
        matched_positions = [position for position in matched_positions if position >= 0]
        if not matched_positions:
            continue
        if feature_name == "otopark" and (
            "kapalı otopark" in desired_features or "kapalı otopark" in excluded_features
        ):
            continue
        position = min(matched_positions)
        nearby_text = searchable_text[max(0, position - 20): position + 50]
        target = excluded_features if any(_search_text(word) in nearby_text for word in negative_words) else desired_features
        if feature_name not in target:
            target.append(feature_name)

    sources = CriteriaSources(
        location=sources_location,
        property_type=sources_prop,
        transaction_type=SourceStatus.EXPLICIT if transaction_type else SourceStatus.UNKNOWN,
        room_count=sources_room,
        price=sources_price,
        area=sources_area,
        in_complex=SourceStatus.EXPLICIT if in_complex_val else SourceStatus.UNKNOWN,
        balcony=SourceStatus.EXPLICIT if balcony_val else SourceStatus.UNKNOWN,
        furnished=SourceStatus.EXPLICIT if furnished_val else SourceStatus.UNKNOWN,
        near_metro=SourceStatus.EXPLICIT if near_metro_val else SourceStatus.UNKNOWN,
        features=SourceStatus.EXPLICIT if desired_features or excluded_features else SourceStatus.UNKNOWN,
    )

    return CustomerCriteria(
        location=LocationCriteria(city=city, district=district, neighborhoods=neighborhoods),
        property_type=property_type,
        transaction_type=transaction_type,
        room_count=room_counts,
        price=PriceCriteria(minimum=min_price, maximum=max_price),
        area=AreaCriteria(minimum_net_m2=min_m2),
        hard_requirements=hard_req,
        soft_preferences=soft_pref,
        desired_features=desired_features,
        excluded_features=excluded_features,
        sources=sources,
        analysis_method="Kural motoru",
    )


def parse_customer_request(
    customer_request: str,
    api_key: str | None = None,
    model_name: str | None = None,
    allow_fallback: bool = True,
) -> CustomerCriteria:
    """Doğal dil talebini Gemini API veya akıllı yedek motor ile doğrulanmış kriterlere çevirir."""
    if not customer_request.strip():
        raise CriteriaParserError("Lütfen önce müşteri talebini yazın.")

    load_dotenv()
    resolved_api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    resolved_model = (model_name or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)).strip()

    if not resolved_api_key:
        if allow_fallback:
            return parse_customer_request_heuristic(customer_request)
        raise CriteriaParserError(
            "Gemini API anahtarı bulunamadı. GEMINI_API_KEY değerini .env "
            "dosyasına veya kenar çubuğuna ekleyin."
        )

    # Gemini modellerini dene
    models_to_try = [resolved_model]
    for fallback_model in FALLBACK_GEMINI_MODELS:
        if fallback_model not in models_to_try:
            models_to_try.append(fallback_model)

    last_error: Exception | None = None

    for current_model in models_to_try:
        try:
            client = genai.Client(
                api_key=resolved_api_key,
                http_options=types.HttpOptions(timeout=25_000),
            )
            response = client.models.generate_content(
                model=current_model,
                contents=customer_request.strip(),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=CustomerCriteria,
                    temperature=0,
                ),
            )

            if isinstance(response.parsed, CustomerCriteria):
                response.parsed.analysis_method = f"Gemini / {current_model}"
                return response.parsed
            if response.text:
                parsed = CustomerCriteria.model_validate_json(response.text)
                parsed.analysis_method = f"Gemini / {current_model}"
                return parsed
        except (ValidationError, errors.ClientError, errors.ServerError, TimeoutError, Exception) as error:
            last_error = error
            continue

    # Eğer API modelleri başarısız olduysa ve fallback serbestse kural motoruna dön
    if allow_fallback:
        return parse_customer_request_heuristic(customer_request)

    if isinstance(last_error, ValidationError):
        raise CriteriaParserError(
            "AI yanıtı doğrulanamadı. Talebi daha açık yazıp tekrar deneyin."
        ) from last_error
    if isinstance(last_error, errors.ClientError):
        status_code = getattr(last_error, "code", None)
        if status_code == 429:
            message = "Gemini kullanım limiti doldu. Biraz bekleyip tekrar deneyin."
        elif status_code in {401, 403}:
            message = "Gemini API anahtarı geçersiz veya yetkisiz."
        else:
            message = "Gemini isteği kabul edilmedi. Lütfen tekrar deneyin."
        raise CriteriaParserError(message) from last_error
    if isinstance(last_error, (errors.ServerError, TimeoutError)):
        raise CriteriaParserError(
            "Gemini şu anda yanıt vermiyor. Lütfen biraz sonra tekrar deneyin."
        ) from last_error

    raise CriteriaParserError(
        f"AI kriter çıkarma başarısız oldu: {last_error}"
    ) from last_error
