"""AI Emlak İlan Eşleştirme ve Portföy Zekası Uygulaması."""

import sys
import time
import re
from pathlib import Path

import pandas as pd
import streamlit as st

# Eğer doğrudan 'python app.py' veya IDE 'Çalıştır' (Run) butonu ile çalıştırıldıysa Streamlit'i başlat
if not st.runtime.exists():
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", __file__]
    sys.exit(stcli.main())


from criteria_parser import (
    DEFAULT_GEMINI_MODEL,
    FALLBACK_GEMINI_MODELS,
    CriteriaParserError,
    parse_customer_request,
)
from matcher import (
    find_near_matches,
    generate_client_pitch,
    get_whatsapp_share_url,
    match_listings,
    normalize_boolean,
)


DATA_FILE = Path(__file__).parent / "data" / "listings.csv"
REQUIRED_COLUMNS = {
    "listing_id",
    "title",
    "city",
    "district",
    "neighborhood",
    "property_type",
    "transaction_type",
    "room_count",
    "price",
    "gross_m2",
    "net_m2",
    "building_age",
    "floor",
    "heating",
    "balcony",
    "furnished",
    "in_complex",
    "transport_notes",
    "description",
    "listing_url",
    "image_url",
    "status",
}

BOOLEAN_FILTER_OPTIONS = {
    "Tümü / Fark etmez": None,
    "Evet": "true",
    "Hayır": "false",
    "Bilinmiyor": "unknown",
}

SAMPLE_PERSONAS = {
    "👨‍👩‍👧 Aile Evi (Kayaşehir 3+1)": (
        "Kayaşehir'de güvenlikli site içerisinde 3+1, maksimum 8 milyon TL, "
        "balkonlu ve metroya yürüme mesafesinde ferah bir daire arıyorum."
    ),
    "💼 Yatırımlık Rezidans (1+1 Eşyalı)": (
        "Başakşehir veya Kayaşehir'de yatırımlık, eşyalı 1+1 rezidans daire. "
        "Bütçem maksimum 4.5 milyon TL. Metroya çok yakın olmalı."
    ),
    "🌿 Müstakil & Bahçeli Ev": (
        "Sakin bir konumda, bahçe kullanımlı veya müstakil 3+1 ev arıyorum. "
        "Bütçem yaklaşık 7 milyon TL."
    ),
    "🏰 Geniş Lüks Site Dairesi (4+1)": (
        "Başakşehir'de kalabalık ailemiz için en az 180 m2 net alanı olan, "
        "yeni binada 4+1 site içi lüks daire arıyoruz. Bütçe 12 milyon TL'ye kadar."
    ),
}


# --- VERİ YÜKLEME VE YÖNETİMİ ---

@st.cache_data
def load_listings_from_disk(file_path: Path) -> pd.DataFrame:
    """CSV dosyasını okur, eski/yeni portföy şemalarını tek biçime getirir."""
    if not file_path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    listings = pd.read_csv(file_path, encoding="utf-8-sig")
    listings.columns = listings.columns.astype(str).str.strip()
    aliases = {
        "listing_type": "transaction_type",
        "nearby_places": "transport_notes",
    }
    for source, target in aliases.items():
        if target not in listings.columns and source in listings.columns:
            listings[target] = listings[source]

    defaults = {
        "transaction_type": "Satılık",
        "transport_notes": "",
        "listing_url": "",
        "image_url": "",
        "status": "active",
    }
    for column, default in defaults.items():
        if column not in listings.columns:
            listings[column] = default

    transaction_normalized = (
        listings["transaction_type"].fillna("").astype(str).str.strip().str.lower()
    )
    listings["transaction_type"] = transaction_normalized.replace(
        {
            "satilik": "Satılık", "satılık": "Satılık",
            "kira": "Kiralık", "kiralik": "Kiralık", "kiralık": "Kiralık",
        }
    )
    for column in (
        "price", "gross_m2", "net_m2", "building_age", "dues",
        "estimated_monthly_rent", "roi_years", "annual_roi_pct",
    ):
        if column in listings.columns:
            cleaned = (
                listings[column].astype(str)
                .str.replace(r"[^0-9,.-]", "", regex=True)
                .str.replace(",", ".", regex=False)
            )
            listings[column] = pd.to_numeric(cleaned, errors="coerce")
    missing_columns = REQUIRED_COLUMNS - set(listings.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Eksik kolonlar: {missing_text}")
    return listings


def get_listings_df() -> pd.DataFrame:
    """Session state'deki güncel ilan verisini veya diskten yüklenen veriyi döndürür."""
    if "listings_df" not in st.session_state or st.session_state["listings_df"] is None:
        try:
            st.session_state["listings_df"] = load_listings_from_disk(DATA_FILE)
        except Exception as error:
            st.session_state["listings_df"] = pd.DataFrame(columns=list(REQUIRED_COLUMNS))
            st.error(f"İlan verisi okunamadı: {error}")
    return st.session_state["listings_df"]


def filter_manual_listings(
    listings: pd.DataFrame,
    city: str | None,
    district: str | None,
    neighborhood: str | None,
    transaction_type: str | None,
    property_type: str | None,
    room_count: str | None,
    minimum_price: int,
    maximum_price: int,
    minimum_net_m2: int,
    in_complex: str | None,
    balcony: str | None,
    furnished: str | None,
    status: str = "active",
) -> pd.DataFrame:
    """Manuel filtrelere göre ilanları süzer."""
    filtered = listings.copy()
    if status and status != "Tümü":
        filtered = filtered[
            filtered["status"].fillna("").astype(str).str.lower().eq(status.lower())
        ]

    text_filters = {
        "city": city,
        "district": district,
        "neighborhood": neighborhood,
        "transaction_type": transaction_type,
        "property_type": property_type,
        "room_count": room_count,
    }
    for column, selected_value in text_filters.items():
        if selected_value and selected_value != "Tümü":
            filtered = filtered[
                filtered[column].fillna("").astype(str).eq(selected_value)
            ]

    numeric_columns = ["price", "net_m2", "gross_m2"]
    for column in numeric_columns:
        if column in filtered.columns:
            filtered[column] = pd.to_numeric(filtered[column], errors="coerce")

    if minimum_price > 0:
        filtered = filtered[filtered["price"] >= minimum_price]
    if maximum_price > 0:
        filtered = filtered[filtered["price"] <= maximum_price]
    if minimum_net_m2 > 0:
        filtered = filtered[filtered["net_m2"] >= minimum_net_m2]

    boolean_filters = {
        "in_complex": in_complex,
        "balcony": balcony,
        "furnished": furnished,
    }
    for column, selected_value in boolean_filters.items():
        if selected_value is not None:
            normalized_values = (
                filtered[column].fillna("unknown").astype(str).str.lower()
            )
            filtered = filtered[normalized_values.eq(selected_value)]

    return filtered.sort_values("price", ascending=True)


def optional_values(listings: pd.DataFrame, column: str) -> list[str]:
    """Bir filtre kolonu için boş olmayan benzersiz seçenekleri döndürür."""
    if column not in listings.columns:
        return []
    values = listings[column].dropna().astype(str).unique().tolist()
    return sorted([v for v in values if v.strip() and v.lower() != "nan"])


def mask_personal_data(text: str) -> str:
    """AI servisine gitmeden önce e-posta ve telefonları maskeler."""
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[E-POSTA]", text)
    return re.sub(r"(?<!\d)(?:\+?90\s*)?0?5\d{2}(?:[\s.-]*\d{2,3}){3,4}(?!\d)", "[TELEFON]", text)


def count_detected_criteria(criteria_data: dict) -> int:
    ignored = {"sources", "analysis_method"}

    def count(value, key="") -> int:
        if key in ignored or value in (None, "", [], {}):
            return 0
        if isinstance(value, dict):
            return sum(count(child, child_key) for child_key, child in value.items())
        if isinstance(value, list):
            return len(value)
        return int(value is not False)

    return count(criteria_data)


def select_customer_example(text: str) -> None:
    st.session_state["customer_request_input"] = text
    st.session_state["search_performed"] = False


def clear_ai_search() -> None:
    st.session_state["customer_request_input"] = ""
    st.session_state["search_performed"] = False
    for key in ("ai_matches", "near_matches", "parsed_criteria", "parsed_criteria_obj", "analysis_warning"):
        st.session_state.pop(key, None)


def toggle_compare(listing_id: str) -> None:
    selected = st.session_state.setdefault("compare_selected", [])
    st.session_state.pop("compare_warning", None)
    if listing_id in selected:
        selected.remove(listing_id)
    elif len(selected) < 4:
        selected.append(listing_id)
    else:
        st.session_state["compare_warning"] = "En fazla 4 ilan karşılaştırabilirsiniz."


def sync_compare_picker() -> None:
    st.session_state["compare_selected"] = st.session_state.get("compare_picker", [])[:4]


def has_real_listing_url(value: object) -> bool:
    """Demo ve boş bağlantıları kullanıcıya gerçek ilan linki gibi göstermez."""
    url = str(value or "").strip()
    return url.startswith(("http://", "https://")) and "example.com" not in url.lower()


def resolve_listing_image(value: object) -> Path | None:
    image_value = str(value or "").strip().replace("/", "\\")
    if not image_value or image_value.startswith(("http://", "https://")):
        return None
    image_path = (Path(__file__).parent / image_value).resolve()
    return image_path if image_path.is_file() else None


def render_criteria_summary(criteria_data: dict) -> None:
    """Ham JSON yerine danışmanın hızlıca doğrulayabileceği bir kriter özeti gösterir."""
    location = criteria_data.get("location", {})
    price = criteria_data.get("price", {})
    area = criteria_data.get("area", {})
    hard = criteria_data.get("hard_requirements", {})
    soft = criteria_data.get("soft_preferences", {})
    items = []

    if location.get("city"):
        items.append(("Şehir", location["city"]))
    if location.get("district"):
        items.append(("İlçe", location["district"]))
    if location.get("neighborhoods"):
        items.append(("Mahalle", ", ".join(location["neighborhoods"])))
    if criteria_data.get("transaction_type"):
        items.append(("İlan türü", criteria_data["transaction_type"]))
    if criteria_data.get("property_type"):
        items.append(("Gayrimenkul", criteria_data["property_type"]))
    if criteria_data.get("room_count"):
        items.append(("Oda", ", ".join(criteria_data["room_count"])))
    if price.get("minimum") is not None:
        items.append(("Minimum fiyat", f"{price['minimum']:,.0f} TL".replace(",", ".")))
    if price.get("maximum") is not None:
        items.append(("Maksimum fiyat", f"{price['maximum']:,.0f} TL".replace(",", ".")))
    if area.get("minimum_net_m2") is not None:
        items.append(("Minimum net alan", f"{area['minimum_net_m2']} m²"))

    flag_labels = {
        "in_complex": "Site içinde",
        "balcony": "Balkon",
        "furnished": "Eşyalı",
        "near_metro": "Metro yakınlığı",
    }
    for key, label in flag_labels.items():
        if hard.get(key) is not None:
            items.append((f"Zorunlu · {label}", "Evet" if hard[key] else "Hayır"))
        elif soft.get(key) is not None:
            items.append((f"Tercih · {label}", "Evet" if soft[key] else "Hayır"))
    for feature in criteria_data.get("desired_features", []):
        items.append(("İstenen özellik", feature.title()))
    for feature in criteria_data.get("excluded_features", []):
        items.append(("İstenmeyen özellik", feature.title()))

    if not items:
        st.info("Metinden puanlanabilir bir emlak kriteri çıkarılamadı.")
        return
    columns = st.columns(min(3, len(items)))
    for index, (label, value) in enumerate(items):
        columns[index % len(columns)].metric(label, value)


# --- SAYFA YAPILANDIRMASI VE CSS ---

st.set_page_config(
    page_title="AI Emlak İlan Eşleştirme & Portföy Zekası",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* Genel Arayüz ve Kart Tasarımı */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        color: #f8fafc;
        margin-bottom: 12px;
    }
    .score-badge-high {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.95rem;
        display: inline-block;
    }
    .score-badge-med {
        background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.95rem;
        display: inline-block;
    }
    .score-badge-low {
        background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.95rem;
        display: inline-block;
    }
    .pill-tag {
        background-color: #334155;
        color: #e2e8f0;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        margin-right: 6px;
        display: inline-block;
    }
    .pitch-box {
        background-color: #022c22;
        border: 1px solid #059669;
        border-radius: 10px;
        padding: 16px;
        color: #ecfdf5;
        font-family: monospace;
        white-space: pre-wrap;
    }
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        margin: 8px 0 14px;
    }
    .kpi-item {
        background: var(--secondary-background-color);
        border: 1px solid rgba(100, 116, 139, 0.28);
        border-left: 4px solid #047857;
        border-radius: 8px;
        min-width: 0;
        padding: 12px 14px;
    }
    .kpi-label {
        color: var(--text-color);
        font-size: 0.82rem;
        opacity: 0.72;
    }
    .kpi-value {
        color: var(--text-color);
        font-size: 1.55rem;
        line-height: 1.2;
        margin-top: 6px;
        overflow-wrap: anywhere;
    }
    @media (max-width: 700px) {
        .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
        .kpi-item { padding: 10px; }
        .kpi-value { font-size: 1.15rem; }
        h1 { font-size: 2rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("customer_request_input", "")
st.session_state.setdefault("search_performed", False)
st.session_state.setdefault("compare_selected", [])


# --- YAN PANEL (SIDEBAR) ---

with st.sidebar:
    st.title("🏠 Portföy Zekası")
    st.caption("AI Destekli Gayrimenkul Eşleştirme Sistemi")

    # API Ayarları
    with st.expander("⚙️ Gemini API Ayarları", expanded=False):
        api_key_input = st.text_input(
            "Gemini API Anahtarı",
            type="password",
            help="Boş bırakılırsa .env dosyasındaki anahtar veya akıllı yerel demo motoru kullanılır.",
        )
        model_choice = st.selectbox(
            "Gemini Modeli",
            FALLBACK_GEMINI_MODELS,
            index=0,
        )
        if api_key_input:
            st.session_state["custom_api_key"] = api_key_input
        st.session_state["custom_model"] = model_choice

    # Portföy Durum Özeti
    listings_data = get_listings_df()
    active_df = listings_data[
        listings_data["status"].fillna("").astype(str).str.lower().eq("active")
    ]
    
    st.divider()
    st.subheader("📊 Portföy Özeti")
    col_sb1, col_sb2 = st.columns(2)
    col_sb1.metric("Aktif İlan", len(active_df))
    sidebar_sale_count = active_df["transaction_type"].eq("Satılık").sum()
    sidebar_rent_count = active_df["transaction_type"].eq("Kiralık").sum()
    col_sb2.metric("Satılık / Kiralık", f"{sidebar_sale_count} / {sidebar_rent_count}")

    st.divider()
    st.subheader("⚡ Hızlı Müşteri Senaryoları")
    st.caption("Danışman senaryolarını tek tıkla test edin:")
    for persona_name, persona_text in SAMPLE_PERSONAS.items():
        st.button(
            persona_name,
            width="stretch",
            on_click=select_customer_example,
            args=(persona_text,),
        )


if "compare_selected" not in st.session_state:
    st.session_state["compare_selected"] = []

sale_df = active_df[active_df["transaction_type"].eq("Satılık")].copy()
rent_df = active_df[active_df["transaction_type"].eq("Kiralık")].copy()
sale_prices = pd.to_numeric(sale_df.get("price"), errors="coerce").dropna()
rent_prices = pd.to_numeric(rent_df.get("price"), errors="coerce").dropna()
roi_values = pd.to_numeric(sale_df.get("roi_years"), errors="coerce").dropna()

st.title("Emlak Zekası & Portföy Eşleştirme Portalı")
sale_average_text = f"{sale_prices.mean() / 1_000_000:.1f} Mn TL" if not sale_prices.empty else "Veri yok"
rent_average_text = f"{rent_prices.mean():,.0f} TL".replace(",", ".") if not rent_prices.empty else "Veri yok"
roi_average_text = f"{roi_values.mean():.1f} yıl" if not roi_values.empty else "Veri yok"
st.markdown(
    f"""
    <div class="kpi-grid">
      <div class="kpi-item"><div class="kpi-label">Aktif ilan</div><div class="kpi-value">{len(active_df)}</div></div>
      <div class="kpi-item"><div class="kpi-label">Satılık / Kiralık</div><div class="kpi-value">{len(sale_df)} / {len(rent_df)}</div></div>
      <div class="kpi-item"><div class="kpi-label">Ort. satış</div><div class="kpi-value">{sale_average_text}</div></div>
      <div class="kpi-item"><div class="kpi-label">Ort. kira</div><div class="kpi-value">{rent_average_text}</div></div>
      <div class="kpi-item"><div class="kpi-label">Ort. amortisman</div><div class="kpi-value">{roi_average_text}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)
data_updated_at = time.strftime("%d.%m.%Y %H:%M", time.localtime(DATA_FILE.stat().st_mtime)) if DATA_FILE.exists() else "Bilinmiyor"
st.caption(
    f"Veri kaynağı: örnek portföy CSV · Son güncelleme: {data_updated_at} · "
    "Fiyat, kira ve getiri hesapları tahminidir; yatırım tavsiyesi değildir."
)


# --- ANA SEKMELER ---

tab_ai, tab_manual, tab_compare, tab_portfolio, tab_analytics = st.tabs(
    [
        "🤖 AI Eşleştirme",
        "🔍 İlanlar",
        f"⚖️ Karşılaştır ({len(st.session_state['compare_selected'])})",
        "➕ Portföy",
        "📈 Piyasa",
    ]
)


# ==========================================
# SEKME 1: AI AKILLI EŞLEŞTİRME & WHATSAPP
# ==========================================
with tab_ai:
    st.subheader("🎯 Doğal Dil ile Müşteri Talebi Eşleştirme")
    st.write(
        "Müşterinizin WhatsApp veya telefon görüşmesinde söylediği talebi doğrudan yapıştırın. "
        "Yapay zeka kriterleri otomatik çıkarıp en uygun portföyleri gerekçeleriyle sunar."
    )

    customer_request = st.text_area(
        "Müşteri Talebi Metni",
        key="customer_request_input",
        placeholder="Örn: Başakşehir'de 3+1, 8.5 milyona kadar, site içi, metroya yürüme mesafesinde...",
        height=110,
    )

    col_btn1, col_btn2 = st.columns([4, 1])
    with col_btn1:
        search_clicked = st.button("🚀 Akıllı İlanları Eşleştir", type="primary", width="stretch")
    with col_btn2:
        st.button("🧹 Temizle", width="stretch", on_click=clear_ai_search)

    if search_clicked:
        clean_request = customer_request.strip()
        if len(clean_request) < 10:
            st.warning("Lütfen en az 10 karakterlik bir müşteri talebi girin veya örnek senaryolardan birini seçin.")
        else:
            api_key = st.session_state.get("custom_api_key")
            model = st.session_state.get("custom_model", DEFAULT_GEMINI_MODEL)
            started_at = time.perf_counter()
            with st.spinner("AI müşteri talebini analiz ediyor ve portföy taranıyor..."):
                try:
                    parsed = parse_customer_request(
                        mask_personal_data(clean_request),
                        api_key=api_key,
                        model_name=model,
                        allow_fallback=True,
                    )
                    parsed_data = parsed.model_dump(mode="json")
                    st.session_state["parsed_criteria"] = parsed_data
                    st.session_state["parsed_criteria_obj"] = parsed
                    if count_detected_criteria(parsed_data) == 0:
                        st.session_state["ai_matches"] = []
                        st.session_state["near_matches"] = []
                        st.session_state["analysis_warning"] = (
                            "Talepte puanlanabilir bir kriter bulunamadı. Konum, oda, bütçe veya istediğiniz özelliklerden en az birini yazın."
                        )
                    else:
                        st.session_state.pop("analysis_warning", None)
                        st.session_state["ai_matches"] = match_listings(active_df, parsed)
                        st.session_state["near_matches"] = find_near_matches(active_df, parsed)
                    st.session_state["search_performed"] = True
                    st.session_state["analysis_elapsed"] = time.perf_counter() - started_at
                    st.session_state["analysis_method"] = parsed.analysis_method
                except CriteriaParserError as err:
                    st.error(str(err))

    if st.session_state.get("search_performed"):
        criteria_count = count_detected_criteria(st.session_state.get("parsed_criteria", {}))
        elapsed = st.session_state.get("analysis_elapsed", 0.0)
        method = st.session_state.get("analysis_method", "Kural motoru")
        st.success(
            f"{criteria_count} kriter çıkarıldı · {len(active_df)} ilan değerlendirildi · "
            f"{elapsed:.1f} saniyede hazırlandı · Yöntem: {method}"
        )
        if st.session_state.get("analysis_warning"):
            st.warning(st.session_state["analysis_warning"])

    # Kriterler Özeti
    if st.session_state.get("search_performed") and "parsed_criteria" in st.session_state:
        criteria_data = st.session_state["parsed_criteria"]
        with st.expander("📋 AI Tarafından Algılanan Kriter Özeti", expanded=False):
            render_criteria_summary(criteria_data)
            with st.expander("Teknik kriter verisini göster", expanded=False):
                st.json(criteria_data)

    # Eşleşme Sonuçları
    if st.session_state.get("search_performed") and "ai_matches" in st.session_state:
        matches = st.session_state["ai_matches"]
        near_matches = st.session_state.get("near_matches", [])

        st.divider()
        col_res1, col_res2 = st.columns([3, 1])
        with col_res1:
            st.subheader(f"✨ Bulunan Eşleşmeler ({len(matches)} İlan)")
        with col_res2:
            result_limit = st.selectbox("Gösterilecek Sonuç", [3, 5, 10, "Tümü"], index=1)
            limit_count = len(matches) if result_limit == "Tümü" else int(result_limit)

        if not matches:
            st.warning("⚠️ Kesin kriterlerin tamamına uyan aktif ilan bulunamadı.")
        else:
            if "compare_selected" not in st.session_state:
                st.session_state["compare_selected"] = []

            for idx, listing in enumerate(matches[:limit_count]):
                score = listing.get("match_score", 0)
                if score >= 85:
                    badge_html = f"<span class='score-badge-high'>%{score} Mükemmel Uyum</span>"
                elif score >= 70:
                    badge_html = f"<span class='score-badge-med'>%{score} Güçlü Eşleşme</span>"
                else:
                    badge_html = f"<span class='score-badge-low'>%{score} Kısmi Uyum</span>"

                price_num = float(listing["price"])
                price_str = f"{price_num:,.0f} TL".replace(",", ".")
                price_m2_str = f"{listing.get('price_per_net_m2', 0):,.0f} TL/m²".replace(",", ".")

                with st.container(border=True):
                    col_t0, col_t1, col_t2 = st.columns([1.1, 2.6, 1])
                    with col_t0:
                        local_image = resolve_listing_image(listing.get("image_url"))
                        if local_image:
                            st.image(str(local_image), caption=listing["title"], width="stretch")
                    with col_t1:
                        st.markdown(f"### {listing['title']} &nbsp; {badge_html}", unsafe_allow_html=True)
                        st.caption(
                            f"{listing.get('transaction_type', '')} · {listing.get('property_type', '')} · "
                            f"İlan No: `{listing['listing_id']}` · {listing['neighborhood']}, {listing['district']}"
                        )
                    with col_t2:
                        st.metric("Fiyat", price_str)

                    # Metrikler
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    col_m1.metric("Oda & Alan", f"{listing['room_count']} • {listing['net_m2']} m²")
                    col_m2.metric("m² Birim Fiyatı", price_m2_str)
                    col_m3.metric("Bina Yaşı / Kat", f"{listing.get('building_age', '-')} yaş • Kat: {listing.get('floor', '-')}")
                    est_rent = listing.get("estimated_monthly_rent", 0)
                    col_m4.metric("Tahmini Kira", f"{est_rent:,.0f} TL/ay".replace(",", "."))

                    # Rozetler
                    tags_html = []
                    if normalize_boolean(listing.get("in_complex")) is True:
                        tags_html.append("<span class='pill-tag'>🏢 Site İçerisinde</span>")
                    if normalize_boolean(listing.get("balcony")) is True:
                        tags_html.append("<span class='pill-tag'>🪴 Balkonlu</span>")
                    if normalize_boolean(listing.get("furnished")) is True:
                        tags_html.append("<span class='pill-tag'>🛋️ Eşyalı</span>")
                    if listing.get("transport_notes"):
                        tags_html.append(f"<span class='pill-tag'>🚇 {listing['transport_notes']}</span>")

                    if tags_html:
                        st.markdown("".join(tags_html), unsafe_allow_html=True)

                    st.markdown("**✨ Neden Bu İlan Uygun?**")
                    for reason in listing.get("match_reasons", []):
                        st.write(f"✓ {reason}")

                    missing = listing.get("missing_information", [])
                    if missing:
                        for m_info in missing:
                            st.caption(f"⚠️ Bilgi: {m_info}")

                    with st.expander("Tüm ilan ayrıntıları ve 10 maddelik bina özellikleri", expanded=False):
                        detail_left, detail_right = st.columns(2)
                        with detail_left:
                            st.write(f"**Brüt / net alan:** {listing.get('gross_m2', '-')} / {listing.get('net_m2', '-')} m²")
                            st.write(f"**Banyo:** {listing.get('bathroom_count', '-')} · **Isıtma:** {listing.get('heating', '-')}")
                            st.write(f"**Cephe / manzara:** {listing.get('facade', '-')} · {listing.get('view', '-')}")
                            st.write(f"**Otopark:** {listing.get('parking', '-')}")
                            st.write(f"**Tapu / iskan:** {listing.get('deed_status', '-')} · {listing.get('iskan_status', '-')}")
                        with detail_right:
                            st.write(f"**Öne çıkan avantaj:** {listing.get('highlight', '-')}")
                            st.write(f"**Artılar:** {listing.get('pros', '-')}")
                            st.write(f"**Dikkat noktaları:** {listing.get('cons', '-')}")
                            st.write(f"**Yakın çevre:** {listing.get('transport_notes', '-')}")
                        st.markdown("**Bina özellikleri**")
                        st.text(str(listing.get("building_features") or "Bilgi bulunmuyor"))

                    # Butonlar
                    col_act1, col_act2 = st.columns([1, 1])
                    with col_act1:
                        if has_real_listing_url(listing.get("listing_url")):
                            st.link_button("🌐 İlan Sayfasına Git", listing["listing_url"], width="stretch")
                        else:
                            st.button("Demo ilanı · dış bağlantı yok", disabled=True, width="stretch", key=f"demo_{listing['listing_id']}_{idx}")
                    with col_act2:
                        lid = listing["listing_id"]
                        is_selected = lid in st.session_state["compare_selected"]
                        st.button(
                            "Karşılaştırmadan çıkar" if is_selected else "⚖️ Karşılaştır",
                            width="stretch",
                            key=f"comp_{lid}_{idx}",
                            on_click=toggle_compare,
                            args=(lid,),
                        )

        # --- YAKIN EŞLEŞMELER (SMART RELAXATION) ---
        if near_matches:
            with st.expander(f"💡 Akıllı Esnetme & Alternatif Fırsatlar ({len(near_matches)} İlan)", expanded=False):
                st.info(
                    "Müşterinizin bütçesini hafifçe (%5-15) esnettiğinizde veya alternatif lokasyonlarda "
                    "kaçırılmaması gereken şu fırsatlar bulunuyor:"
                )
                for near in near_matches:
                    with st.container(border=True):
                        n_price = float(near["price"])
                        st.write(f"**{near['title']}** — **{n_price:,.0f} TL** ({near['room_count']}, {near['net_m2']} m²)".replace(",", "."))
                        for note in near.get("relaxation_notes", []):
                            st.markdown(f"🔸 *{note}*")
                        if near.get("match_reasons"):
                            st.caption("Avantajlar: " + " • ".join(near["match_reasons"][:2]))

        # --- WHATSAPP VE MÜŞTERİ SUNUMU ---
        if matches:
            st.divider()
            st.subheader("📲 Müşteri WhatsApp Sunum Oluşturucu")
            st.write("Eşleşen en iyi ilanları tek tıkla müşterinize gönderebileceğiniz şık bir WhatsApp mesajına dönüştürün.")

            col_w1, col_w2, col_w3 = st.columns([2, 2, 2])
            with col_w1:
                client_name_in = st.text_input("Müşteri Adı / Hitap", value="Ahmet Bey")
            with col_w2:
                consultant_name_in = st.text_input("Danışman Adınız", value="Emlak Danışmanınız")
            with col_w3:
                client_phone_in = st.text_input("Müşteri Telefon No (Opsiyonel)", placeholder="905xxxxxxxxx")

            pitch_text = generate_client_pitch(
                matches,
                client_name=client_name_in or "Değerli Müşterimiz",
                consultant_name=consultant_name_in or "Emlak Danışmanınız",
            )

            st.text_area("Hazırlanan WhatsApp Mesajı", value=pitch_text, height=220)

            wa_url = get_whatsapp_share_url(pitch_text, client_phone_in)
            st.link_button("💬 WhatsApp ile Hemen Gönder", wa_url, type="primary", width="stretch")


# ==========================================
# SEKME 2: MANUEL DETAYLI ARAMA
# ==========================================
with tab_manual:
    st.subheader("🔍 Kriter Bazlı Manuel Portföy Arama")
    
    with st.form("manual_search_form"):
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            m_city = st.selectbox("Şehir", ["Tümü", *optional_values(active_df, "city")])
            m_district = st.selectbox("İlçe", ["Tümü", *optional_values(active_df, "district")])
            m_neighborhood = st.selectbox("Mahalle", ["Tümü", *optional_values(active_df, "neighborhood")])
        with col_m2:
            m_transaction = st.selectbox("İlan Türü", ["Tümü", *optional_values(active_df, "transaction_type")])
            m_type = st.selectbox("Emlak Tipi", ["Tümü", *optional_values(active_df, "property_type")])
            m_room = st.selectbox("Oda Sayısı", ["Tümü", *optional_values(active_df, "room_count")])
            m_complex = st.selectbox("Site İçerisinde", list(BOOLEAN_FILTER_OPTIONS.keys()))
        with col_m3:
            m_min_price = st.number_input("Min Fiyat (TL)", min_value=0, step=250_000)
            m_max_price = st.number_input("Max Fiyat (TL)", min_value=0, step=250_000, help="0 değeri üst fiyat sınırı uygulanmayacağı anlamına gelir.")
            m_min_m2 = st.number_input("Min Net m²", min_value=0, step=10)
            m_balcony = st.selectbox("Balkon", list(BOOLEAN_FILTER_OPTIONS.keys()))
            m_furnished = st.selectbox("Eşyalı", list(BOOLEAN_FILTER_OPTIONS.keys()))

        manual_submit = st.form_submit_button("Filtrele ve İlanları Listele", type="primary", width="stretch")

    manual_results = filter_manual_listings(
        listings=listings_data,
        city=None if m_city == "Tümü" else m_city,
        district=None if m_district == "Tümü" else m_district,
        neighborhood=None if m_neighborhood == "Tümü" else m_neighborhood,
        transaction_type=None if m_transaction == "Tümü" else m_transaction,
        property_type=None if m_type == "Tümü" else m_type,
        room_count=None if m_room == "Tümü" else m_room,
        minimum_price=int(m_min_price),
        maximum_price=int(m_max_price),
        minimum_net_m2=int(m_min_m2),
        in_complex=BOOLEAN_FILTER_OPTIONS[m_complex],
        balcony=BOOLEAN_FILTER_OPTIONS[m_balcony],
        furnished=BOOLEAN_FILTER_OPTIONS[m_furnished],
        status="active",
    )

    st.write(f"**Toplam Bulunan:** {len(manual_results)} aktif ilan")
    if not manual_results.empty:
        display_cols = [
            "listing_id",
            "title",
            "neighborhood",
            "room_count",
            "price",
            "net_m2",
            "in_complex",
            "balcony",
            "transport_notes",
        ]
        st.dataframe(
            manual_results[display_cols],
            hide_index=True,
            width="stretch",
            column_config={
                "listing_id": "İlan No",
                "title": "Başlık",
                "neighborhood": "Mahalle",
                "room_count": "Oda",
                "price": st.column_config.NumberColumn("Fiyat", format="%d TL"),
                "net_m2": "Net m²",
                "in_complex": "Site",
                "balcony": "Balkon",
                "transport_notes": "Ulaşım",
            },
        )
        csv_bytes = manual_results.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Sonuçları CSV İndir", csv_bytes, "filtrelenmis_ilanlar.csv", "text/csv")


# ==========================================
# SEKME 3: İLAN KARŞILAŞTIRMA MATRİSİ
# ==========================================
with tab_compare:
    st.subheader("⚖️ İlan Karşılaştırma Matrisi")
    st.write("Müşterinize alternatif sunarken veya karar verme aşamasında 2-4 ilanı yan yana kıyaslayın.")

    all_active_ids = active_df["listing_id"].tolist()
    pre_selected = [lid for lid in st.session_state.get("compare_selected", []) if lid in all_active_ids]
    if st.session_state.get("compare_picker") != pre_selected[:4]:
        st.session_state["compare_picker"] = pre_selected[:4]

    selected_ids = st.multiselect(
        "Karşılaştırılacak İlanları Seçin:",
        options=all_active_ids,
        max_selections=4,
        key="compare_picker",
        on_change=sync_compare_picker,
        format_func=lambda x: f"{x} - {active_df[active_df['listing_id'] == x]['title'].values[0]}" if not active_df[active_df['listing_id'] == x].empty else x,
    )

    if st.session_state.pop("compare_warning", None):
        st.warning("En fazla 4 ilan karşılaştırabilirsiniz.")

    if len(selected_ids) < 2:
        st.info("Kıyaslama yapabilmek için lütfen en az 2 ilan seçin (AI Eşleştirme sekmesindeki kutucukları da kullanabilirsiniz).")
    else:
        comp_df = active_df[active_df["listing_id"].isin(selected_ids)].copy()
        
        # Karşılaştırma kolonları
        cols = st.columns(len(selected_ids))
        for i, (_, row) in enumerate(comp_df.iterrows()):
            with cols[i]:
                price_f = float(row["price"])
                net_m2_f = float(row["net_m2"]) if pd.notna(row["net_m2"]) else 1
                gross_m2_f = float(row["gross_m2"]) if pd.notna(row["gross_m2"]) else 1
                m2_price = price_f / net_m2_f
                efficiency = (net_m2_f / gross_m2_f) * 100 if gross_m2_f > 0 else 0

                with st.container(border=True):
                    st.subheader(row["title"])
                    st.caption(f"İlan No: `{row['listing_id']}`")
                    st.metric("Fiyat", f"{price_f:,.0f} TL".replace(",", "."))
                    st.metric("m² Birim Fiyatı", f"{m2_price:,.0f} TL/m²".replace(",", "."))
                    st.write(f"📍 **Konum:** {row['neighborhood']} / {row['district']}")
                    st.write(f"📐 **Alan:** {row['net_m2']} m² Net / {row['gross_m2']} m² Brüt")
                    st.write(f"📊 **Net/Brüt Verim:** %{efficiency:.1f}")
                    st.write(f"🚪 **Oda:** {row['room_count']}")
                    st.write(f"🏢 **Bina Yaşı / Kat:** {row.get('building_age', '-')} yaş • Kat: {row.get('floor', '-')}")
                    st.write(f"🔥 **Isıtma:** {row.get('heating', '-')}")
                    st.write(f"🪴 **Balkon:** {'Evet' if normalize_boolean(row.get('balcony')) else 'Hayır'}")
                    st.write(f"🛡️ **Site İçi:** {'Evet' if normalize_boolean(row.get('in_complex')) else 'Hayır'}")
                    st.write(f"🚇 **Ulaşım:** {row.get('transport_notes', '-')}")


# ==========================================
# SEKME 4: PORTFÖY YÖNETİMİ & YENİ İLAN
# ==========================================
with tab_portfolio:
    st.subheader("➕ Portföy Yönetimi ve Yeni İlan Ekleme")
    st.write("Veritabanına anında yeni bir portföy ekleyin veya mevcut ilanları yönetin.")

    with st.expander("📝 Yeni İlan Ekle", expanded=False):
        with st.form("add_listing_form"):
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1:
                new_id = st.text_input("İlan No *", value=f"PRT{len(listings_data) + 1:03d}")
                new_title = st.text_input("Başlık *", placeholder="Örn: Kayaşehir Yeni Projede 3+1 Daire")
                new_city = st.text_input("Şehir", value="İstanbul")
                new_district = st.text_input("İlçe", value="Başakşehir")
                new_neighborhood = st.text_input("Mahalle *", placeholder="Kayabaşı")
            with col_a2:
                new_transaction = st.selectbox("İlan Türü", ["Satılık", "Kiralık"])
                new_prop_type = st.selectbox("Emlak Tipi", ["Daire", "Rezidans", "Müstakil Ev", "Villa", "Ofis"])
                new_room = st.selectbox("Oda Sayısı", ["1+1", "2+1", "3+1", "4+1", "5+1"])
                new_price = st.number_input("Fiyat (TL) *", min_value=100_000, step=100_000, value=7_500_000)
                new_net_m2 = st.number_input("Net m² *", min_value=10, step=5, value=120)
                new_gross_m2 = st.number_input("Brüt m²", min_value=10, step=5, value=140)
            with col_a3:
                new_age = st.number_input("Bina Yaşı", min_value=0, max_value=100, value=2)
                new_floor = st.text_input("Kat", value="4")
                new_heating = st.selectbox("Isıtma", ["Merkezi", "Kombi", "Yerden Isıtma"])
                new_complex = st.checkbox("Site İçerisinde", value=True)
                new_balcony = st.checkbox("Balkonlu", value=True)
                new_furnished = st.checkbox("Eşyalı", value=False)

            new_transport = st.text_input("Ulaşım Notları", placeholder="Metroya 5 dakika yürüme mesafesinde...")
            new_desc = st.text_area("Açıklama", placeholder="Geniş, aydınlık, aileye uygun lüks daire...")
            new_url = st.text_input("İlan Web Linki (Opsiyonel)")

            add_submitted = st.form_submit_button("💾 İlanı Portföye Kaydet", type="primary", width="stretch")

            if add_submitted:
                if not new_title.strip() or not new_neighborhood.strip():
                    st.error("Lütfen başlık ve mahalle alanlarını doldurun.")
                else:
                    new_row = {
                        "listing_id": new_id,
                        "title": new_title,
                        "city": new_city,
                        "district": new_district,
                        "neighborhood": new_neighborhood,
                        "property_type": new_prop_type,
                        "transaction_type": new_transaction,
                        "listing_type": new_transaction,
                        "price_period": "Aylık" if new_transaction == "Kiralık" else "Satış",
                        "room_count": new_room,
                        "price": new_price,
                        "gross_m2": new_gross_m2,
                        "net_m2": new_net_m2,
                        "building_age": new_age,
                        "floor": new_floor,
                        "heating": new_heating,
                        "balcony": "true" if new_balcony else "false",
                        "furnished": "true" if new_furnished else "false",
                        "in_complex": "true" if new_complex else "false",
                        "transport_notes": new_transport,
                        "description": new_desc,
                        "listing_url": new_url,
                        "image_url": "",
                        "status": "active",
                    }
                    updated_df = pd.concat([listings_data, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state["listings_df"] = updated_df
                    try:
                        updated_df.to_csv(DATA_FILE, index=False)
                        st.success(f"İlan `{new_id}` başarıyla eklendi ve diske kaydedildi!")
                    except Exception as ex:
                        st.warning(f"İlan hafızaya eklendi ancak diske yazılamadı: {ex}")
                    st.rerun()

    st.subheader("📋 Tüm Portföy Listesi")
    st.dataframe(listings_data, hide_index=True, width="stretch")
    all_csv = listings_data.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Tüm Portföyü CSV Olarak İndir", all_csv, "tum_portfoy.csv", "text/csv")


# ==========================================
# SEKME 5: PİYASA VE PORTFÖY ANALİTİĞİ
# ==========================================
with tab_analytics:
    st.subheader("📈 Piyasa ve Portföy İstatistikleri")
    st.caption("Satılık ve kiralık portföyler ayrı hesaplanır; boş veya geçersiz değerler ortalamalara katılmaz.")

    analytics_df = active_df.copy()
    analytics_df["price_num"] = pd.to_numeric(analytics_df["price"], errors="coerce")
    analytics_df["net_m2_num"] = pd.to_numeric(analytics_df["net_m2"], errors="coerce")
    analytics_df = analytics_df.dropna(subset=["price_num"])

    if analytics_df.empty:
        st.info("Analiz üretmek için geçerli fiyatı olan aktif ilan bulunmuyor.")
    else:
        analytics_sale = analytics_df[analytics_df["transaction_type"].eq("Satılık")].copy()
        analytics_rent = analytics_df[analytics_df["transaction_type"].eq("Kiralık")].copy()

        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        metric_a.metric("Medyan satış", f"{analytics_sale['price_num'].median() / 1_000_000:.1f} Mn TL" if not analytics_sale.empty else "Veri yok")
        metric_b.metric("Medyan kira", f"{analytics_rent['price_num'].median():,.0f} TL".replace(",", ".") if not analytics_rent.empty else "Veri yok")
        metric_c.metric("Satılık portföy", len(analytics_sale))
        metric_d.metric("Kiralık portföy", len(analytics_rent))

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Mahalle bazında medyan satılık fiyatı**")
            sale_neighborhood = (
                analytics_sale.groupby("neighborhood")["price_num"].median().sort_values(ascending=False)
                if not analytics_sale.empty else pd.Series(dtype=float)
            )
            if sale_neighborhood.empty:
                st.info("Satılık fiyat grafiği için veri yok.")
            else:
                st.bar_chart(sale_neighborhood)

        with col_g2:
            st.write("**Mahalle bazında medyan kira**")
            rent_neighborhood = (
                analytics_rent.groupby("neighborhood")["price_num"].median().sort_values(ascending=False)
                if not analytics_rent.empty else pd.Series(dtype=float)
            )
            if rent_neighborhood.empty:
                st.info("Kiralık fiyat grafiği için veri yok.")
            else:
                st.bar_chart(rent_neighborhood)

        col_g3, col_g4 = st.columns(2)
        with col_g3:
            st.write("**Oda sayısına göre ilan dağılımı**")
            room_counts = analytics_df["room_count"].fillna("Belirtilmemiş").value_counts()
            st.bar_chart(room_counts)
        with col_g4:
            st.write("**Emlak türüne göre ilan dağılımı**")
            property_counts = analytics_df["property_type"].fillna("Belirtilmemiş").value_counts()
            st.bar_chart(property_counts)

        st.divider()
        st.write("**Yatırım fırsatları: en düşük m² birim fiyatlı satılık ilanlar**")
        investment_df = analytics_sale[analytics_sale["net_m2_num"].gt(0)].copy()
        investment_df["m2_price"] = investment_df["price_num"] / investment_df["net_m2_num"]
        investment_df = investment_df.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["m2_price"])
        sorted_invest = investment_df.nsmallest(25, "m2_price")[[
            "listing_id", "title", "neighborhood", "room_count", "price_num", "net_m2_num", "m2_price"
        ]]

        if sorted_invest.empty:
            st.info("Birim fiyat analizi için uygun satılık ilan bulunmuyor.")
        else:
            st.dataframe(
                sorted_invest,
                hide_index=True,
                width="stretch",
                column_config={
                    "listing_id": "İlan No",
                    "title": "Başlık",
                    "neighborhood": "Mahalle",
                    "room_count": "Oda",
                    "price_num": st.column_config.NumberColumn("Fiyat", format="%d TL"),
                    "net_m2_num": "Net m²",
                    "m2_price": st.column_config.NumberColumn("Birim Fiyat", format="%d TL/m²"),
                },
            )
