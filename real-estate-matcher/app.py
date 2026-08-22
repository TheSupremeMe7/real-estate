import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ai_request_parser import GEMINI_MODEL, parse_customer_request
from sheet_store import LISTING_COLUMNS, load_sheet_listings


APP_DIR = Path(__file__).parent
LISTINGS_FILE = APP_DIR / "listings.csv"
ENV_FILE = APP_DIR / ".env"
DEFAULT_CREDENTIALS_FILE = APP_DIR.parent / "credentials.json"


def setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except FileNotFoundError:
        return default


@st.cache_data(ttl=30)
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


def parse_request(request: str, districts: list[str]) -> dict[str, object]:
    """Extract a few useful criteria locally; Gemini will replace this later."""
    request_lower = request.lower()
    parsed: dict[str, object] = {}

    room_match = re.search(r"(\d)\s*\+\s*(\d)", request_lower)
    if room_match:
        parsed["room_count"] = f"{room_match.group(1)}+{room_match.group(2)}"

    million_match = re.search(r"([\d.,]+)\s*milyon", request_lower)
    if million_match:
        value = float(million_match.group(1).replace(",", "."))
        parsed["max_price"] = int(value * 1_000_000)

    for district in districts:
        if district.lower() in request_lower:
            parsed["district"] = district
            break

    parsed["balcony"] = "balkon" in request_lower
    parsed["in_complex"] = any(word in request_lower for word in ("site içinde", "sitede"))
    parsed["near_metro"] = "metro" in request_lower
    return parsed


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
) -> tuple[int, list[str]]:
    earned_points = 0
    possible_points = 0
    reasons: list[str] = []

    if max_price > 0:
        possible_points += 20
    if max_price > 0 and listing["price"] <= max_price:
        earned_points += 20
        reasons.append("Bütçeye uygun")

    if selected_districts:
        possible_points += 15
    if selected_districts and listing["district"] in selected_districts:
        earned_points += 15
        reasons.append("Bölge tercihiyle eşleşiyor")

    if selected_neighborhoods:
        possible_points += 10
    if selected_neighborhoods and listing["neighborhood"] in selected_neighborhoods:
        earned_points += 10
        reasons.append("Mahalle tercihiyle eşleşiyor")

    if selected_rooms:
        possible_points += 15
    if selected_rooms and listing["room_count"] in selected_rooms:
        earned_points += 15
        reasons.append(f"{listing['room_count']} oda planı uygun")

    if selected_property_types:
        possible_points += 10
    if selected_property_types and listing["property_type"] in selected_property_types:
        earned_points += 10
        reasons.append(f"{listing['property_type']} tipi uygun")

    if min_gross_m2 > 0:
        possible_points += 10
    if min_gross_m2 > 0 and listing["gross_m2"] >= min_gross_m2:
        earned_points += 10
        reasons.append(f"En az {min_gross_m2} m² şartını karşılıyor")

    feature_checks = [
        (balcony, bool(listing["balcony"]), "Balkonlu", 8),
        (in_complex, bool(listing["in_complex"]), "Site içinde", 8),
        (near_metro, bool(listing["near_metro"]), "Metroya yakın", 8),
    ]
    for requested, available, label, weight in feature_checks:
        if requested:
            possible_points += weight
        if requested and available:
            earned_points += weight
            reasons.append(label)

    if possible_points == 0:
        return 50, ["Karşılaştırma için daha fazla kriter gerekli"]
    score = round(earned_points / possible_points * 100)
    return score, reasons


def format_price(price: int) -> str:
    return f"{price:,.0f} TL".replace(",", ".")


def build_customer_report(
    customer_request: str,
    selected_matches: list[tuple[int, list[str], pd.Series]],
) -> str:
    lines = ["EMLAK İLAN ÖNERİLERİ", ""]
    if customer_request.strip():
        lines.extend([f"Müşteri talebi: {customer_request.strip()}", ""])

    for index, (score, reasons, listing) in enumerate(selected_matches, start=1):
        lines.extend(
            [
                f"{index}. {listing['title']} - %{score} eşleşme",
                f"Konum: {listing['district']} / {listing['neighborhood']}",
                f"Özellikler: {listing['room_count']} · {listing['gross_m2']} m² · {listing['property_type']}",
                f"Fiyat: {format_price(int(listing['price']))}",
                f"Öne çıkanlar: {', '.join(reasons[:4])}",
                f"İlan: {listing['listing_url']}",
                "",
            ]
        )
    return "\n".join(lines)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f8faf9; color: #16211d; }
        [data-testid="stHeader"] { background: rgba(248,250,249,.94); }
        [data-testid="stSidebar"] {
            background: #edf4f1;
            border-right: 1px solid #dce7e2;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border: 1px solid #dfe7e3;
            border-radius: 8px;
            box-shadow: 0 5px 18px rgba(30, 58, 48, .055);
        }
        [data-testid="stMetric"] {
            background: transparent;
            border-left: 3px solid #f07b55;
            padding-left: 12px;
        }
        [data-testid="stImage"] img { border-radius: 6px; }
        .app-kicker { color: #14765b; font-size: 13px; font-weight: 750; }
        .app-kicker::before {
            content: "";
            display: inline-block;
            width: 8px;
            height: 8px;
            margin-right: 8px;
            border-radius: 50%;
            background: #f07b55;
        }
        .match-score { color: #d95f3b; font-size: 24px; font-weight: 780; }
        .listing-meta { color: #596761; font-size: 14px; }
        .reason-tag {
            display: inline-block;
            margin: 8px 5px 0 0;
            padding: 4px 7px;
            border: 1px solid #d7e5df;
            border-radius: 4px;
            background: #f2f7f5;
            color: #315d50;
            font-size: 12px;
        }
        .stButton > button, .stLinkButton > a,
        [data-testid="stFormSubmitButton"] > button {
            min-height: 42px;
            border-radius: 6px;
            font-weight: 700;
        }
        [data-testid="stForm"] { border-color: #d8e4df; }
        h1, h2, h3, p, button, label { letter-spacing: 0 !important; }
        h1 { font-size: 32px !important; }
        h2 { font-size: 22px !important; }
        h3 { font-size: 18px !important; }
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
        search_clicked = st.form_submit_button(
            "Uygun ilanları bul",
            type="primary",
            use_container_width=True,
        )

    load_dotenv(ENV_FILE, override=True)
    gemini_enabled = setting("ENABLE_GEMINI", "false").lower() == "true"
    gemini_key = setting("GEMINI_API_KEY")
    if search_clicked and request:
        if gemini_enabled and gemini_key:
            try:
                with st.spinner(f"Talep Gemini ile analiz ediliyor ({GEMINI_MODEL})..."):
                    ai_criteria = parse_customer_request(gemini_key, request, districts, rooms)
                parsed = ai_criteria.model_dump(exclude_none=True)
                st.session_state["criteria_source"] = "Gemini"
            except Exception as error:
                st.warning(f"AI analizi kullanılamadı, yerel analiz uygulandı: {error}")
                parsed = parse_request(request, districts)
                st.session_state["criteria_source"] = "Yerel"
        else:
            parsed = parse_request(request, districts)
            st.session_state["criteria_source"] = "Yerel"
        st.session_state["parsed_criteria"] = parsed
        st.session_state["parsed_request"] = request
    elif st.session_state.get("parsed_request") == request:
        parsed = st.session_state.get("parsed_criteria", {})
    else:
        parsed = parse_request(request, districts)

    parsed_districts = parsed.get("district", [])
    if isinstance(parsed_districts, str):
        parsed_districts = [parsed_districts]
    parsed_districts = [str(value) for value in parsed_districts]
    default_districts = [value for value in parsed_districts if value in districts]

    parsed_rooms = parsed.get("room_count", [])
    if isinstance(parsed_rooms, str):
        parsed_rooms = [parsed_rooms]
    parsed_rooms = [str(value) for value in parsed_rooms]
    default_rooms = [value for value in parsed_rooms if value in rooms]

    parsed_neighborhoods = parsed.get("neighborhood", [])
    if isinstance(parsed_neighborhoods, str):
        parsed_neighborhoods = [parsed_neighborhoods]
    default_neighborhoods = [
        str(value) for value in parsed_neighborhoods if str(value) in neighborhoods
    ]

    parsed_property_types = parsed.get("property_type", [])
    if isinstance(parsed_property_types, str):
        parsed_property_types = [parsed_property_types]
    default_property_types = [
        str(value) for value in parsed_property_types if str(value) in property_types
    ]

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
        result_limit = st.slider("Gösterilecek ilan", 5, 30, 12, 1)

    effective_max_price = int(parsed.get("max_price", max_price))
    effective_districts = default_districts or selected_districts
    effective_neighborhoods = default_neighborhoods or selected_neighborhoods
    effective_rooms = default_rooms or selected_rooms
    effective_property_types = default_property_types or selected_property_types
    effective_min_gross_m2 = int(parsed.get("min_gross_m2", min_gross_m2))
    effective_balcony = balcony or bool(parsed.get("balcony"))
    effective_in_complex = in_complex or bool(parsed.get("in_complex"))
    effective_near_metro = near_metro or bool(parsed.get("near_metro"))

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
        source = st.session_state.get("criteria_source", "Yerel")
        st.caption(
            f"Talepte algılanan kriterler ({source}): " + " · ".join(detected_labels)
        )

    scored: list[tuple[int, list[str], pd.Series]] = []
    for _, listing in listings.iterrows():
        score, reasons = score_listing(
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
        )
        scored.append((score, reasons, listing))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_matches = scored[:result_limit]

    st.subheader(f"En uygun ilanlar ({len(top_matches)})")
    selected_matches: list[tuple[int, list[str], pd.Series]] = []
    for score, reasons, listing in top_matches:
        with st.container(border=True):
            image_column, detail_column, action_column = st.columns([1.15, 2.4, 0.8])
            with image_column:
                image_source = str(listing["image_url"])
                if not image_source.lower().startswith(("http://", "https://")):
                    image_source = str(APP_DIR / image_source)
                st.image(image_source, use_container_width=True)
            with detail_column:
                st.markdown(f"### {listing['title']}")
                st.markdown(
                    f'<div class="listing-meta">{listing["district"]} / {listing["neighborhood"]} · '
                    f'{listing["room_count"]} · {listing["gross_m2"]} m²</div>',
                    unsafe_allow_html=True,
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
            with action_column:
                st.markdown(f'<div class="match-score">%{score}</div>', unsafe_allow_html=True)
                st.caption("eşleşme")
                st.markdown(f"**{format_price(int(listing['price']))}**")
                st.link_button("İlanı aç", listing["listing_url"], use_container_width=True)
                selected = st.checkbox(
                    "Kısa liste",
                    key=f"shortlist_{listing['listing_id']}",
                )
                if selected:
                    selected_matches.append((score, reasons, listing))

    if selected_matches:
        report = build_customer_report(request, selected_matches)
        st.markdown(f"**Kısa liste: {len(selected_matches)} ilan**")
        st.download_button(
            "Müşteri özetini indir",
            data=report.encode("utf-8-sig"),
            file_name="musteri_ilan_onerileri.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.caption(f"Mod: {mode}. Eşleşme puanı öneridir; nihai değerlendirme emlak danışmanına aittir.")


if __name__ == "__main__":
    main()
