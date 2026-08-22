from google import genai
from google.genai import types
from pydantic import BaseModel, Field


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
- must_have zorunlu, nice_to_have tercih edilen özelliklerdir.
- summary kısa ve Türkçe olsun.

Mevcut ilçeler: {available_districts}
Mevcut oda seçenekleri: {available_rooms}

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
