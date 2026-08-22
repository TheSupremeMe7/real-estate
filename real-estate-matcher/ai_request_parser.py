from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from feature_catalog import PROPERTY_FEATURE_CATALOG


GEMINI_MODEL = "gemini-3.5-flash-lite"


class CustomerCriteria(BaseModel):
    district: list[str] = Field(default_factory=list)
    neighborhood: list[str] = Field(default_factory=list)
    property_type: list[str] = Field(default_factory=list)
    room_count: list[str] = Field(default_factory=list)
    max_price: int | None = Field(default=None, ge=0)
    min_gross_m2: int | None = Field(default=None, ge=0)
    balcony: bool | None = None
    in_complex: bool | None = None
    near_metro: bool | None = None
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    summary: str


def parse_customer_request(
    api_key: str,
    request: str,
    available_districts: list[str],
    available_rooms: list[str],
) -> CustomerCriteria:
    """Convert a Turkish customer request into validated search criteria."""
    prompt = f"""
Bir emlak müşterisinin talebini yapılandırılmış arama kriterlerine çevir.

Kurallar:
- Yalnızca müşterinin açıkça söylediği bilgileri çıkar.
- Söylenmeyen özellikler için null veya boş liste kullan.
- "8 milyon altı" ifadesini 8000000 olarak yaz.
- İlçe ve oda değerlerini mümkünse aşağıdaki mevcut seçeneklerle aynı yaz.
- Balkon, site, metro, oda, konut tipi, bölge, fiyat ve metrekareyi kendi
  alanlarına yaz; bunları must_have veya nice_to_have içinde tekrarlama.
- Bahçe, deniz manzarası, otopark, teras, havuz, yüksek tavan, ev ofisi gibi
  diğer tüm özellikleri kısa Türkçe arama terimleri olarak çıkar.
- "mutlaka", "şart", "olmalı", "istiyorum" denilen ek özellikleri must_have;
  "olsa iyi olur", "tercihen" denilenleri nice_to_have içine yaz.
- "metro olsa iyi olur" gibi tercih cümlelerinde near_metro alanını null bırak ve
  "metroya yakın" ifadesini nice_to_have içine yaz. Aynı kural balkon ve site
  tercihleri için de geçerlidir; boolean alanları yalnızca zorunluysa true yap.
- summary kısa ve Türkçe olsun.

Mevcut ilçeler: {available_districts}
Mevcut oda seçenekleri: {available_rooms}
Emlak özellik sözlüğü (örnek ve eş anlam referansı, bununla sınırlı değilsin):
{PROPERTY_FEATURE_CATALOG}

Müşteri talebi:
{request}
""".strip()

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=10_000),
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CustomerCriteria,
            temperature=0.1,
        ),
    )
    if not response.text:
        raise ValueError("Gemini boş yanıt döndürdü")
    return CustomerCriteria.model_validate_json(response.text)
