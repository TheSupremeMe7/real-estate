import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ai_request_parser import GEMINI_MODEL, parse_customer_request
from feature_catalog import PROPERTY_FEATURE_CATALOG
from sheet_store import LISTING_COLUMNS, load_sheet_listings


APP_DIR = Path(__file__).parent
LISTINGS_FILE = APP_DIR / "listings.csv"
ENV_FILE = APP_DIR / ".env"
DEFAULT_CREDENTIALS_FILE = APP_DIR.parent / "credentials.json"
FEATURE_ALIASES = {
    "bahçe": ("bahçe", "özel yeşil alan"),
    "manzara": ("manzara", "ön cephe"),
    "deniz": ("deniz", "su manzarası"),
    "otopark": ("otopark", "araçlık"),
    "havuz": ("havuz", "yüzme"),
    "teras": ("teras", "pergola", "açık hava"),
    "depo": ("depo", "kiler", "depolama", "gömme dolap"),
    "ofis": ("ofis", "çalışma alanı"),
    "akıllı ev": ("akıllı", "telefonla kontrol"),
    "asansör": ("asansör", "engelsiz giriş"),
    "evcil hayvan": ("evcil hayvan", "çevrili özel bahçe"),
    "ebeveyn": ("ebeveyn", "giyinme odası"),
    "yüksek tavan": ("yüksek tavan", "tavandan zemine"),
    "güneş": ("güneş", "gün ışığı", "sabah ışığı"),
    "okul": ("okul", "günlük ihtiyaç"),
}


def setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except FileNotFoundError:
        return default


@st.cache_data(ttl=300)
def load_listings() -> tuple[pd.DataFrame, str]:
    load_dotenv(ENV_FILE, override=True)
    sample_listings = pd.read_csv(LISTINGS_FILE, encoding="utf-8-sig")
    spreadsheet_id = setting("REAL_ESTATE_SHEET_ID")
    credentials_path = Path(
        setting("GOOGLE_CREDENTIALS_FILE", str(DEFAULT_CREDENTIALS_FILE))
    )
    credentials_json = setting("GOOGLE_CREDENTIALS_JSON")

    if not spreadsheet_id:
        return sample_listings, "Örnek portföy"
    if credentials_json:
        credentials_source = json.loads(credentials_json)
    elif credentials_path.exists():
        credentials_source = credentials_path
    else:
        raise FileNotFoundError(f"Google credentials bulunamadı: {credentials_path}")

    listings = load_sheet_listings(spreadsheet_id, credentials_source, sample_listings)
    return listings, "Google Sheets"


@st.cache_data(ttl=3600, show_spinner=False)
def analyze_request(
    api_key: str,
    request: str,
    districts: tuple[str, ...],
    rooms: tuple[str, ...],
):
    return parse_customer_request(api_key, request, list(districts), list(rooms))


def normalize_option_values(values: object, options: list[str]) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    lookup = {option.casefold().replace(" ", ""): option for option in options}
    normalized = []
    for value in values:
        key = str(value).casefold().replace(" ", "")
        if key in lookup and lookup[key] not in normalized:
            normalized.append(lookup[key])
    return normalized


def feature_matches_listing(feature: str, listing: pd.Series) -> bool:
    searchable = " ".join(
        str(listing.get(column, ""))
        for column in (
            "title", "property_type", "description", "highlight", "heating",
            "facade", "parking", "security", "view", "outdoor_space",
            "kitchen_type", "amenities", "nearby_places", "technical_details",
        )
    ).casefold()
    feature_text = feature.casefold().strip()
    for canonical, aliases in FEATURE_ALIASES.items():
        if canonical in feature_text or any(alias in feature_text for alias in aliases):
            return any(alias in searchable for alias in aliases)
    words = [word for word in re.findall(r"\w+", feature_text) if len(word) >= 4]
    return bool(words) and all(word in searchable for word in words)


def parse_request(
    request: str,
    districts: list[str],
    neighborhoods: list[str] | None = None,
    property_types: list[str] | None = None,
) -> dict[str, object]:
    """Extract common Turkish property criteria without an API call."""
    request_lower = request.casefold()
    parsed: dict[str, object] = {}

    number_words = {
        "sıfır": "0", "bir": "1", "iki": "2", "üç": "3", "dört": "4",
        "beş": "5", "altı": "6", "yedi": "7", "sekiz": "8", "dokuz": "9",
    }
    normalized_request = request_lower.replace("artı", "+").replace("arti", "+")
    for word, digit in number_words.items():
        normalized_request = re.sub(rf"\b{word}\b", digit, normalized_request)
    room_match = re.search(r"(\d+)\s*\+\s*(\d+)", normalized_request)
    if room_match:
        parsed["room_count"] = f"{room_match.group(1)}+{room_match.group(2)}"

    million_match = re.search(r"([\d.,]+)\s*milyon", request_lower)
    if million_match:
        value = float(million_match.group(1).replace(",", "."))
        parsed["max_price"] = int(value * 1_000_000)

    for district in districts:
        if district.casefold() in request_lower:
            parsed["district"] = district
            break

    for neighborhood in neighborhoods or []:
        if neighborhood.casefold() in request_lower:
            parsed["neighborhood"] = neighborhood
            break

    for property_type in property_types or []:
        if property_type.casefold() in request_lower:
            parsed["property_type"] = property_type
            break

    parsed["balcony"] = "balkon" in request_lower
    parsed["in_complex"] = any(word in request_lower for word in ("site içinde", "sitede"))
    parsed["near_metro"] = "metro" in request_lower
    detected_features = []
    for canonical, aliases in FEATURE_ALIASES.items():
        if canonical in request_lower or any(alias in request_lower for alias in aliases):
            detected_features.append(canonical)
    catalog_matches = [
        feature for feature in PROPERTY_FEATURE_CATALOG
        if feature in request_lower
    ]
    if not detected_features:
        detected_features.extend(sorted(catalog_matches, key=len, reverse=True)[:8])
    detected_features = list(dict.fromkeys(detected_features))
    parsed["must_have"] = detected_features
    return parsed


def listing_matches_required_criteria(
    listing: pd.Series,
    max_price: int,
    districts: list[str],
    neighborhoods: list[str],
    rooms: list[str],
    property_types: list[str],
    min_gross_m2: int,
    balcony: bool,
    in_complex: bool,
    near_metro: bool,
    required_features: list[str] | None = None,
) -> bool:
    return all(
        [
            not max_price or int(listing["price"]) <= max_price,
            not districts or listing["district"] in districts,
            not neighborhoods or listing["neighborhood"] in neighborhoods,
            not rooms or listing["room_count"] in rooms,
            not property_types or listing["property_type"] in property_types,
            not min_gross_m2 or int(listing["gross_m2"]) >= min_gross_m2,
            not balcony or bool(listing["balcony"]),
            not in_complex or bool(listing["in_complex"]),
            not near_metro or bool(listing["near_metro"]),
            all(
                feature_matches_listing(feature, listing)
                for feature in (required_features or [])
            ),
        ]
    )


def score_listing(
    listing: pd.Series,
    max_price: int,
    selected_districts: list[str],
    selected_neighborhoods: list[str],
    selected_rooms: list[str],
    selected_property_types: list[str],
    min_gross_m2: int,
    balcony: bool,
    in_complex: bool,
    near_metro: bool,
    requested_features: list[str] | None = None,
) -> tuple[int, list[str], list[dict[str, object]]]:
    earned_points = 0.0
    possible_points = 0.0
    reasons: list[str] = []
    breakdown: list[dict[str, object]] = []

    def add_criterion(label: str, weight: int, earned: float, detail: str) -> None:
        nonlocal earned_points, possible_points
        possible_points += weight
        earned_points += earned
        breakdown.append(
            {"label": label, "earned": earned, "possible": weight, "detail": detail}
        )

    if max_price > 0:
        price = int(listing["price"])
        if price <= max_price:
            budget_points = 20
            budget_detail = "Bütçe içinde"
            reasons.append("Bütçeye uygun")
        elif price <= max_price * 1.10:
            budget_points = 10
            budget_detail = f"Bütçenin %{round((price / max_price - 1) * 100)} üzerinde"
        elif price <= max_price * 1.25:
            budget_points = 5
            budget_detail = f"Bütçenin %{round((price / max_price - 1) * 100)} üzerinde"
        else:
            budget_points = 0
            budget_detail = "Bütçenin belirgin üzerinde"
        add_criterion("Bütçe", 20, budget_points, budget_detail)

    if selected_districts:
        matched = listing["district"] in selected_districts
        add_criterion("İlçe", 15, 15 if matched else 0, str(listing["district"]))
        if matched:
            reasons.append("Bölge tercihiyle eşleşiyor")

    if selected_neighborhoods:
        matched = listing["neighborhood"] in selected_neighborhoods
        add_criterion("Mahalle", 10, 10 if matched else 0, str(listing["neighborhood"]))
        if matched:
            reasons.append("Mahalle tercihiyle eşleşiyor")

    if selected_rooms:
        matched = listing["room_count"] in selected_rooms
        add_criterion("Oda planı", 15, 15 if matched else 0, str(listing["room_count"]))
        if matched:
            reasons.append(f"{listing['room_count']} oda planı uygun")

    if selected_property_types:
        matched = listing["property_type"] in selected_property_types
        add_criterion("Konut tipi", 10, 10 if matched else 0, str(listing["property_type"]))
        if matched:
            reasons.append(f"{listing['property_type']} tipi uygun")

    if min_gross_m2 > 0:
        matched = int(listing["gross_m2"]) >= min_gross_m2
        add_criterion("Brüt alan", 10, 10 if matched else 0, f"{listing['gross_m2']} m²")
        if matched:
            reasons.append(f"En az {min_gross_m2} m² şartını karşılıyor")

    feature_checks = [
        (balcony, bool(listing["balcony"]), "Balkonlu", 8),
        (in_complex, bool(listing["in_complex"]), "Site içinde", 8),
        (near_metro, bool(listing["near_metro"]), "Metroya yakın", 8),
    ]
    for requested, available, label, weight in feature_checks:
        if requested:
            add_criterion(label, weight, weight if available else 0, "Var" if available else "Yok")
            if available:
                reasons.append(label)

    for feature in requested_features or []:
        matched = feature_matches_listing(feature, listing)
        add_criterion(feature.capitalize(), 7, 7 if matched else 0, "Eşleşti" if matched else "Bulunamadı")
        if matched:
            reasons.append(f"{feature.capitalize()} tercihiyle eşleşiyor")

    if possible_points == 0:
        return 50, ["Karşılaştırma için daha fazla kriter gerekli"], []
    score = round(earned_points / possible_points * 100)
    return score, reasons, breakdown


def format_price(price: int) -> str:
    return f"{price:,.0f} TL".replace(",", ".")


def build_customer_report(
    customer_request: str,
    selected_matches: list[tuple[int, list[str], list[dict[str, object]], pd.Series]],
) -> str:
    lines = ["EMLAK İLAN ÖNERİLERİ", ""]
    if customer_request.strip():
        lines.extend([f"Müşteri talebi: {customer_request.strip()}", ""])

    for index, (score, reasons, breakdown, listing) in enumerate(selected_matches, start=1):
        score_details = "; ".join(
            f"{item['label']} {item['earned']:.0f}/{item['possible']}"
            for item in breakdown
        )
        lines.extend(
            [
                f"{index}. {listing['title']} - %{score} eşleşme",
                f"Konum: {listing['district']} / {listing['neighborhood']}",
                f"Özellikler: {listing['room_count']} · {listing['gross_m2']} m² · {listing['property_type']}",
                f"Net alan: {listing.get('net_m2', 0)} m² · Kat: {listing.get('floor', '-')} / {listing.get('total_floors', '-')} · Banyo: {listing.get('bathroom_count', '-')}",
                f"Isıtma: {listing.get('heating', '-')} · Cephe: {listing.get('facade', '-')} · Mutfak: {listing.get('kitchen_type', '-')}",
                f"Otopark: {listing.get('parking', '-')} · Güvenlik: {listing.get('security', '-')} · Manzara: {listing.get('view', '-')}",
                f"Site olanakları: {listing.get('amenities', '-')}",
                f"Yakın çevre: {listing.get('nearby_places', '-')}",
                f"Teknik: {listing.get('technical_details', '-')}",
                f"Fiyat: {format_price(int(listing['price']))}",
                f"Öne çıkanlar: {', '.join(reasons[:4])}",
                f"Puan dökümü: {score_details}",
                f"İlan: {listing['listing_url']}",
                "",
            ]
        )
    return "\n".join(lines)


def apply_styles() -> None:
    theme_type = getattr(st.context.theme, "type", "light")
    if theme_type == "dark":
        palette = {
            "bg": "#111714",
            "surface": "#18221E",
            "sidebar": "#17211D",
            "text": "#EDF6F2",
            "muted": "#A8BBB2",
            "primary": "#61D0A8",
            "accent": "#FF9A78",
            "border": "#34463E",
            "shadow": "rgba(0, 0, 0, .24)",
        }
    else:
        palette = {
            "bg": "#F7FAF8",
            "surface": "#FFFFFF",
            "sidebar": "#EAF2EE",
            "text": "#17241F",
            "muted": "#5B6C64",
            "primary": "#17735A",
            "accent": "#D75F3C",
            "border": "#D4E1DB",
            "shadow": "rgba(24, 55, 44, .08)",
        }
    st.markdown(
        f"""
        <style>
        :root {{
            --app-bg: {palette['bg']};
            --app-surface: {palette['surface']};
            --app-sidebar: {palette['sidebar']};
            --app-text: {palette['text']};
            --app-muted: {palette['muted']};
            --app-primary: {palette['primary']};
            --app-accent: {palette['accent']};
            --app-border: {palette['border']};
            --app-shadow: {palette['shadow']};
        }}
        .stApp {{
            background: var(--app-bg);
            color: var(--app-text);
        }}
        [data-testid="stHeader"] {{
            background: color-mix(in srgb, var(--app-bg) 92%, transparent);
            border-bottom: 1px solid var(--app-border);
        }}
        [data-testid="stSidebar"] {{
            background: var(--app-sidebar);
            border-right: 1px solid var(--app-border);
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--app-surface);
            border: 1px solid var(--app-border);
            border-radius: 8px;
            box-shadow: 0 7px 22px var(--app-shadow);
        }}
        [data-testid="stMetric"] {{
            background: transparent;
            border-left: 3px solid var(--app-accent);
            padding-left: 12px;
        }}
        [data-testid="stImage"] img {{ border-radius: 6px; }}
        .app-kicker {{ color: var(--app-primary); font-size: 13px; font-weight: 750; }}
        .app-kicker::before {{
            content: "";
            display: inline-block;
            width: 8px;
            height: 8px;
            margin-right: 8px;
            border-radius: 50%;
            background: var(--app-accent);
        }}
        .match-score {{
            color: var(--app-accent);
            font-size: 24px;
            font-weight: 780;
        }}
        .listing-meta {{
            color: var(--app-muted);
            font-size: 14px;
        }}
        .reason-tag {{
            display: inline-block;
            margin: 8px 5px 0 0;
            padding: 4px 7px;
            border: 1px solid var(--app-border);
            border-radius: 4px;
            background: color-mix(in srgb, var(--app-primary) 14%, var(--app-surface));
            color: var(--app-text);
            font-size: 12px;
        }}
        .stButton > button, .stLinkButton > a,
        [data-testid="stFormSubmitButton"] > button {{
            min-height: 42px;
            border-radius: 6px;
            font-weight: 700;
        }}
        [data-testid="stForm"] {{ border-color: var(--app-border); }}
        [data-testid="stAlert"] {{ border: 1px solid var(--app-border); }}
        h1, h2, h3, p, button, label {{ letter-spacing: 0 !important; }}
        h1 {{ font-size: 32px !important; }}
        h2 {{ font-size: 22px !important; }}
        h3 {{ font-size: 18px !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Emlak Eşleştirici", page_icon=None, layout="wide")
    apply_styles()
    try:
        listings, data_source = load_listings()
    except Exception as error:
        st.error(f"İlanlar yüklenemedi: {error}")
        st.stop()
    if listings.empty:
        st.warning("Aktif ilan bulunamadı.")
        st.stop()
    districts = sorted(listings["district"].unique().tolist())
    neighborhoods = sorted(listings["neighborhood"].unique().tolist())
    rooms = sorted(listings["room_count"].unique().tolist())
    property_types = sorted(listings["property_type"].unique().tolist())

    st.markdown('<div class="app-kicker">PORTFÖY EŞLEŞTİRME</div>', unsafe_allow_html=True)
    st.title("Emlak Eşleştirici")
    st.caption("Müşterinin aradığı evi portföy içinde hızlıca bulun.")

    summary_columns = st.columns(3)
    with summary_columns[0]:
        st.metric("Aktif ilan", len(listings))
    with summary_columns[1]:
        st.metric("Bölge", listings["district"].nunique())
    with summary_columns[2]:
        average_price = int(listings["price"].mean())
        st.metric("Ortalama fiyat", f"{average_price / 1_000_000:.1f} Mn TL")

    mode = st.radio(
        "Kullanım modu",
        ["Emlak danışmanı", "Müşteri"],
        horizontal=True,
        label_visibility="collapsed",
    )

    with st.form("property_search"):
        request = st.text_area(
            "Müşteri talebi",
            placeholder="Başakşehir'de site içinde, balkonlu, 3+1 ve 8 milyon TL altı daire arıyorum.",
            height=92,
        )
        detailed_ai = st.toggle("AI ile detaylı analiz", value=True)
        search_clicked = st.form_submit_button(
            "Uygun ilanları bul",
            type="primary",
            width="stretch",
        )

    load_dotenv(ENV_FILE, override=True)
    gemini_enabled = setting("ENABLE_GEMINI", "true").lower() == "true"
    gemini_key = setting("GEMINI_API_KEY")
    if search_clicked and request:
        if detailed_ai and gemini_enabled and gemini_key:
            try:
                with st.spinner(f"Talep analiz ediliyor ({GEMINI_MODEL})..."):
                    ai_criteria = analyze_request(
                        gemini_key,
                        request,
                        tuple(districts),
                        tuple(rooms),
                    )
                parsed = ai_criteria.model_dump(exclude_none=True)
                st.session_state["criteria_source"] = "Gemini"
                st.session_state["search_notice"] = "Talep Gemini ile analiz edildi ve ilanlar yeniden sıralandı."
            except Exception as error:
                st.warning(f"AI analizi kullanılamadı, yerel analiz uygulandı: {error}")
                parsed = parse_request(request, districts, neighborhoods, property_types)
                st.session_state["criteria_source"] = "Yerel"
                st.session_state["search_notice"] = "Talep hızlı arama ile analiz edildi ve ilanlar yeniden sıralandı."
        else:
            parsed = parse_request(request, districts, neighborhoods, property_types)
            st.session_state["criteria_source"] = "Yerel"
            st.session_state["search_notice"] = "Talep hızlı arama ile analiz edildi ve ilanlar yeniden sıralandı."
        st.session_state["parsed_criteria"] = parsed
        st.session_state["parsed_request"] = request
    elif st.session_state.get("parsed_request") == request:
        parsed = st.session_state.get("parsed_criteria", {})
    else:
        parsed = parse_request(request, districts, neighborhoods, property_types)

    if request and st.session_state.get("parsed_request") == request:
        st.success(st.session_state.get("search_notice", "İlanlar yeniden sıralandı."))

    default_districts = normalize_option_values(parsed.get("district", []), districts)
    default_rooms = normalize_option_values(parsed.get("room_count", []), rooms)
    default_neighborhoods = normalize_option_values(
        parsed.get("neighborhood", []), neighborhoods
    )
    default_property_types = normalize_option_values(
        parsed.get("property_type", []), property_types
    )

    with st.sidebar:
        st.header("Arama kriterleri")
        st.caption(f"Portföy kaynağı: {data_source}")
        if st.button("İlanları yenile", help="Google Sheet'teki son değişiklikleri yükler"):
            st.cache_data.clear()
            st.rerun()
        max_price = st.number_input(
            "Maksimum bütçe (TL)",
            min_value=1_000_000,
            max_value=100_000_000,
            value=int(parsed.get("max_price", 10_000_000)),
            step=250_000,
        )
        selected_districts = st.multiselect(
            "İlçe", districts, default=default_districts, placeholder="İlçe seçin"
        )
        selected_neighborhoods = st.multiselect(
            "Mahalle",
            neighborhoods,
            default=default_neighborhoods,
            placeholder="Mahalle seçin",
        )
        selected_rooms = st.multiselect(
            "Oda sayısı", rooms, default=default_rooms, placeholder="Oda seçin"
        )
        selected_property_types = st.multiselect(
            "Konut tipi",
            property_types,
            default=default_property_types,
            placeholder="Konut tipi seçin",
        )
        min_gross_m2 = st.number_input(
            "Minimum brüt m²",
            min_value=0,
            max_value=1_000,
            value=int(parsed.get("min_gross_m2", 0)),
            step=5,
        )
        st.subheader("Olmazsa olmazlar")
        balcony = st.checkbox("Balkon", value=bool(parsed.get("balcony")))
        in_complex = st.checkbox("Site içinde", value=bool(parsed.get("in_complex")))
        near_metro = st.checkbox("Metroya yakın", value=bool(parsed.get("near_metro")))
        result_limit = st.slider("Gösterilecek ilan", 5, 30, 8, 1)

    effective_max_price = int(parsed.get("max_price", max_price))
    effective_districts = default_districts or selected_districts
    effective_neighborhoods = default_neighborhoods or selected_neighborhoods
    effective_rooms = default_rooms or selected_rooms
    effective_property_types = default_property_types or selected_property_types
    effective_min_gross_m2 = int(parsed.get("min_gross_m2", min_gross_m2))
    effective_balcony = balcony or bool(parsed.get("balcony"))
    effective_in_complex = in_complex or bool(parsed.get("in_complex"))
    effective_near_metro = near_metro or bool(parsed.get("near_metro"))
    required_features = [
        str(value).strip()
        for value in parsed.get("must_have", [])
        if str(value).strip()
    ]
    preferred_features = [
        str(value).strip()
        for value in parsed.get("nice_to_have", [])
        if str(value).strip()
    ]
    requested_features = list(dict.fromkeys(required_features + preferred_features))

    if request and parsed:
        detected_labels: list[str] = []
        if "max_price" in parsed:
            detected_labels.append(f"bütçe: {format_price(effective_max_price)}")
        if effective_districts:
            detected_labels.append(f"ilçe: {', '.join(effective_districts)}")
        if effective_rooms:
            detected_labels.append(f"oda: {', '.join(effective_rooms)}")
        if effective_neighborhoods:
            detected_labels.append(f"mahalle: {', '.join(effective_neighborhoods)}")
        if effective_min_gross_m2:
            detected_labels.append(f"min: {effective_min_gross_m2} m²")
        if requested_features:
            detected_labels.append(f"özellik: {', '.join(requested_features)}")
        source = st.session_state.get("criteria_source", "Yerel")
        st.caption(
            f"Talepte algılanan kriterler ({source}): " + " · ".join(detected_labels)
        )

    scored: list[tuple[int, list[str], list[dict[str, object]], pd.Series]] = []
    closest: list[tuple[int, list[str], list[dict[str, object]], pd.Series]] = []
    for _, listing in listings.iterrows():
        score, reasons, breakdown = score_listing(
            listing,
            effective_max_price,
            effective_districts,
            effective_neighborhoods,
            effective_rooms,
            effective_property_types,
            effective_min_gross_m2,
            effective_balcony,
            effective_in_complex,
            effective_near_metro,
            requested_features,
        )
        candidate = (score, reasons, breakdown, listing)
        closest.append(candidate)
        if listing_matches_required_criteria(
            listing,
            effective_max_price,
            effective_districts,
            effective_neighborhoods,
            effective_rooms,
            effective_property_types,
            effective_min_gross_m2,
            effective_balcony,
            effective_in_complex,
            effective_near_metro,
            required_features,
        ):
            scored.append(candidate)
    scored.sort(key=lambda item: item[0], reverse=True)
    closest.sort(key=lambda item: item[0], reverse=True)
    showing_closest = not scored and bool(request)
    if showing_closest:
        scored = closest
    top_matches = scored[:result_limit]

    heading = "En yakın alternatifler" if showing_closest else "Eşleşen ilanlar"
    st.subheader(f"{heading} ({len(scored)})")
    if showing_closest:
        st.warning("Tüm zorunlu kriterleri aynı anda karşılayan ilan yok; en yakın alternatifler gösteriliyor.")
    if not top_matches:
        st.warning("Bu kriterlerin tamamına uyan aktif ilan bulunamadı.")
    selected_matches: list[tuple[int, list[str], list[dict[str, object]], pd.Series]] = []
    for score, reasons, breakdown, listing in top_matches:
        with st.container(border=True):
            image_column, detail_column, action_column = st.columns([1.15, 2.4, 0.8])
            with image_column:
                image_source = str(listing["image_url"])
                if not image_source.lower().startswith(("http://", "https://")):
                    image_source = str(APP_DIR / image_source)
                st.image(image_source, width="stretch")
            with detail_column:
                st.markdown(f"### {listing['title']}")
                st.markdown(
                    f'<div class="listing-meta">{listing["district"]} / {listing["neighborhood"]} · '
                    f'{listing["room_count"]} · {listing["gross_m2"]} m² brüt · '
                    f'{listing.get("net_m2", 0)} m² net</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**{listing.get('floor', '-')} / {listing.get('total_floors', '-')} kat** · "
                    f"{listing.get('bathroom_count', '-')} banyo · "
                    f"{listing.get('heating', '-')} · {listing.get('facade', '-')} cephe"
                )
                st.write(listing["description"])
                highlight = str(listing.get("highlight", "")).strip()
                if highlight and highlight.lower() != "nan":
                    st.markdown(f"**Bu evin avantajı:** {highlight}")
                if reasons:
                    reason_html = "".join(
                        f'<span class="reason-tag">{reason}</span>' for reason in reasons[:4]
                    )
                    st.markdown(reason_html, unsafe_allow_html=True)
                else:
                    st.caption("Kriterlerle sınırlı eşleşme")
                with st.expander("Tüm ilan detayları"):
                    details_left, details_right = st.columns(2)
                    with details_left:
                        st.markdown(
                            f"**Konut ve bina**  \n"
                            f"Bina yaşı: {listing.get('building_age', '-')}  \n"
                            f"Mutfak: {listing.get('kitchen_type', '-')}  \n"
                            f"Açık alan: {listing.get('outdoor_space', '-')}  \n"
                            f"Manzara: {listing.get('view', '-')}  \n"
                            f"Otopark: {listing.get('parking', '-')}  \n"
                            f"Asansör: {'Var' if listing.get('elevator') else 'Yok'}"
                        )
                    with details_right:
                        st.markdown(
                            f"**Mülkiyet ve kullanım**  \n"
                            f"Tapu: {listing.get('deed_status', '-')}  \n"
                            f"Kredi: {'Uygun' if listing.get('credit_eligible') else 'Uygun değil'}  \n"
                            f"Kullanım: {listing.get('usage_status', '-')}  \n"
                            f"Eşyalı: {'Evet' if listing.get('furnished') else 'Hayır'}  \n"
                            f"Aidat: {format_price(int(listing.get('dues', 0)))}  \n"
                            f"Güvenlik: {listing.get('security', '-')}"
                        )
                    st.markdown(f"**Site olanakları:** {listing.get('amenities', '-')}")
                    st.markdown(f"**Yakın çevre:** {listing.get('nearby_places', '-')}")
                    st.markdown(f"**Teknik donanım:** {listing.get('technical_details', '-')}")
                with st.expander("Eşleşme hesabı"):
                    for criterion in breakdown:
                        ratio = float(criterion["earned"]) / float(criterion["possible"])
                        st.progress(
                            ratio,
                            text=(
                                f"{criterion['label']}: "
                                f"{criterion['earned']:.0f}/{criterion['possible']} puan · "
                                f"{criterion['detail']}"
                            ),
                        )
            with action_column:
                st.markdown(f'<div class="match-score">%{score}</div>', unsafe_allow_html=True)
                st.caption("eşleşme")
                st.markdown(f"**{format_price(int(listing['price']))}**")
                st.link_button("İlanı aç", listing["listing_url"], width="stretch")
                selected = st.checkbox(
                    "Kısa liste",
                    key=f"shortlist_{listing['listing_id']}",
                )
                if selected:
                    selected_matches.append((score, reasons, breakdown, listing))

    if selected_matches:
        report = build_customer_report(request, selected_matches)
        st.markdown(f"**Kısa liste: {len(selected_matches)} ilan**")
        st.download_button(
            "Müşteri özetini indir",
            data=report.encode("utf-8-sig"),
            file_name="musteri_ilan_onerileri.txt",
            mime="text/plain",
            width="stretch",
        )

    st.caption(f"Mod: {mode}. Eşleşme puanı öneridir; nihai değerlendirme emlak danışmanına aittir.")


if __name__ == "__main__":
    main()
