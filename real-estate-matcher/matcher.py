"""AI kriterlerini kullanarak ilanları filtreler, puanlar, finansal analiz yapar ve müşteri sunumu üretir."""

import re
import unicodedata
import urllib.parse
from typing import Any

import pandas as pd

from criteria_parser import CustomerCriteria


MATCH_WEIGHTS = {
    "location": 25,
    "property_type": 15,
    "transaction_type": 10,
    "room_count": 20,
    "budget": 20,
    "area": 10,
    "in_complex": 8,
    "balcony": 5,
    "near_metro": 7,
    "other": 5,
}

LOCATION_ALIASES = {
    "kayasehir": {"kayasehir", "kayabasi"},
    "kayabasi": {"kayasehir", "kayabasi"},
    "basak": {"basak", "basaksehirmh", "basak mahallesi"},
}

METRO_KEYWORDS = ("metro", "istasyon", "rayli sistem", "marmaray")

FEATURE_ALIASES = {
    "deniz manzarasi": ("deniz", "adalar manzarasi"),
    "bogaz manzarasi": ("bogaz",),
    "sehir manzarasi": ("sehir manzarasi", "panoramik sehir"),
    "bahce": ("bahce", "peyzaj"),
    "teras": ("teras",),
    "kapali otopark": ("kapali otopark",),
    "otopark": ("otopark", "garaj"),
    "asansor": ("asansor",),
    "elektrikli arac sarji": ("elektrikli arac", "ev sarj", "sarj unitesi"),
    "akilli ev": ("akilli ev", "otomasyon"),
    "ebeveyn banyosu": ("ebeveyn banyo",),
    "giyinme odasi": ("giyinme oda",),
    "guvenlik": ("guvenlik", "kamera", "cctv", "kontrollu giris"),
    "yuzme havuzu": ("yuzme havuzu", "havuz"),
    "fitness": ("fitness", "spor salonu"),
    "sauna": ("sauna", "spa"),
    "cocuk parki": ("cocuk parki", "oyun alani", "cocuk kulubu"),
    "jenerator": ("jenerator",),
    "fiber internet": ("fiber",),
    "klima": ("klima", "vrf"),
    "yerden isitma": ("yerden isitma",),
    "krediye uygun": ("krediye uygun", "konut kredisine"),
    "iskanli": ("iskanli", "iskan mevcut"),
    "kat mulkiyeti": ("kat mulkiyeti",),
    "esyali": ("esyali", "mobilyali"),
}

FEATURE_COLUMNS = (
    "title", "description", "highlight", "outdoor_space", "parking", "security",
    "view", "deed_status", "credit_eligible", "iskan_status", "amenities",
    "transport_notes", "technical_details", "building_features", "smart_home",
    "pros", "cons", "heating", "elevator", "ev_charging", "master_bathroom",
)


def normalize_text(value: Any) -> str:
    """Türkçe metni karşılaştırmaya uygun küçük ve aksansız biçime getirir."""
    if value is None or pd.isna(value):
        return ""
    translation = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    text = str(value).translate(translation).lower().strip()
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", text)


def normalize_boolean(value: Any) -> bool | None:
    """Farklı üç durumlu değerleri true/false/unknown biçimine dönüştürür."""
    normalized = normalize_text(value)
    if normalized in {"true", "evet", "1", "var", "yes"}:
        return True
    if normalized in {"false", "hayir", "0", "yok", "no"}:
        return False
    return None


def location_matches(listing_value: Any, requested_value: str) -> bool:
    listing_location = normalize_text(listing_value)
    requested_location = normalize_text(requested_value)
    accepted_locations = LOCATION_ALIASES.get(
        requested_location, {requested_location}
    )
    return (
        listing_location in accepted_locations
        or any(alias in listing_location for alias in accepted_locations)
        or any(listing_location in alias for alias in accepted_locations)
    )


def is_near_metro(listing: pd.Series | dict) -> bool | None:
    """Ulaşım metninde açık metro/istasyon bilgisi arar."""
    transport_text = normalize_text(listing.get("transport_notes"))
    if not transport_text:
        return None
    return any(keyword in transport_text for keyword in METRO_KEYWORDS)


def listing_feature_blob(listing: pd.Series | dict) -> str:
    return " | ".join(normalize_text(listing.get(column)) for column in FEATURE_COLUMNS)


def listing_has_feature(listing: pd.Series | dict, feature: str) -> bool:
    blob = listing_feature_blob(listing)
    normalized_feature = normalize_text(feature)
    aliases = FEATURE_ALIASES.get(normalized_feature, (normalized_feature,))
    return any(alias and alias in blob for alias in aliases)


def calculate_financial_metrics(price: float, net_m2: float | None, gross_m2: float | None) -> dict[str, Any]:
    """İlan için m² birim fiyatı, net/brüt verimliliği ve tahmini kira/amortisman metriklerini hesaplar."""
    price_per_net_m2 = round(price / net_m2) if (net_m2 and net_m2 > 0) else None
    price_per_gross_m2 = round(price / gross_m2) if (gross_m2 and gross_m2 > 0) else None
    efficiency_ratio = round((net_m2 / gross_m2) * 100, 1) if (net_m2 and gross_m2 and gross_m2 > 0) else None

    # İstanbul geneli ortalama kira çarpanı (~%0.42 - %0.48 aylık getiri)
    estimated_monthly_rent = round(price * 0.0045)
    amortization_years = round(price / (estimated_monthly_rent * 12), 1) if estimated_monthly_rent > 0 else 18.5

    return {
        "price_per_net_m2": price_per_net_m2,
        "price_per_gross_m2": price_per_gross_m2,
        "efficiency_ratio": efficiency_ratio,
        "estimated_monthly_rent": estimated_monthly_rent,
        "amortization_years": amortization_years,
    }


def _legacy_passes_hard_constraints(
    listing: pd.Series | dict, criteria: CustomerCriteria
) -> bool:
    """Bir ilan bütün kesin kriterleri karşılıyorsa True döndürür."""
    if normalize_text(listing.get("status")) != "active":
        return False

    location = criteria.location
    if location.city and not location_matches(listing.get("city"), location.city):
        return False
    if location.district and not location_matches(
        listing.get("district"), location.district
    ):
        return False
    if location.neighborhoods and not any(
        location_matches(listing.get("neighborhood"), neighborhood)
        for neighborhood in location.neighborhoods
    ):
        return False

    if criteria.property_type and normalize_text(
        listing.get("property_type")
    ) != normalize_text(criteria.property_type):
        return False
    if criteria.transaction_type and normalize_text(
        listing.get("transaction_type")
    ) != normalize_text(criteria.transaction_type):
        return False
    if criteria.room_count and normalize_text(listing.get("room_count")) not in {
        normalize_text(room) for room in criteria.room_count
    }:
        return False

    price = pd.to_numeric(listing.get("price"), errors="coerce")
    if pd.isna(price):
        return False
    if criteria.price.minimum is not None and price < criteria.price.minimum:
        return False
    if criteria.price.maximum is not None and price > criteria.price.maximum:
        return False

    net_m2 = pd.to_numeric(listing.get("net_m2"), errors="coerce")
    gross_m2 = pd.to_numeric(listing.get("gross_m2"), errors="coerce")
    if criteria.area.minimum_net_m2 is not None and (
        pd.isna(net_m2) or net_m2 < criteria.area.minimum_net_m2
    ):
        return False
    if criteria.area.minimum_gross_m2 is not None and (
        pd.isna(gross_m2) or gross_m2 < criteria.area.minimum_gross_m2
    ):
        return False

    hard = criteria.hard_requirements
    boolean_checks = {
        "in_complex": hard.in_complex,
        "balcony": hard.balcony,
        "furnished": hard.furnished,
    }
    for column, required_value in boolean_checks.items():
        if required_value is not None and normalize_boolean(
            listing.get(column)
        ) is not required_value:
            return False
    if hard.near_metro is not None and is_near_metro(listing) is not hard.near_metro:
        return False

    if any(listing_has_feature(listing, feature) for feature in criteria.excluded_features):
        return False

    return True


def budget_quality(price: float, criteria: CustomerCriteria) -> float:
    """Bütçe içindeki fiyatı, en ucuz her zaman en iyi demeden puanlar."""
    minimum = criteria.price.minimum
    maximum = criteria.price.maximum
    if minimum is not None and maximum is not None:
        midpoint = (minimum + maximum) / 2
        half_range = max((maximum - minimum) / 2, 1)
        return max(0.85, 1 - (abs(price - midpoint) / half_range) * 0.15)
    if maximum is not None:
        ratio = price / maximum
        return 1.0 if 0.75 <= ratio <= 1 else max(0.85, ratio / 0.75)
    if minimum is not None:
        return 1.0
    return 0.0


def _legacy_calculate_match_score(
    listing: pd.Series | dict, criteria: CustomerCriteria
) -> tuple[int, list[str], list[str]]:
    """İlanın aktif kriterlerdeki puanını, nedenlerini ve eksiklerini döndürür."""
    earned = 0.0
    possible = 0.0
    reasons: list[str] = []
    missing: list[str] = []

    location = criteria.location
    if location.city or location.district or location.neighborhoods:
        possible += MATCH_WEIGHTS["location"]
        earned += MATCH_WEIGHTS["location"]
        reasons.append(f"Konum uygun: {listing.get('neighborhood')} (+{MATCH_WEIGHTS['location']})")

    if criteria.property_type:
        possible += MATCH_WEIGHTS["property_type"]
        earned += MATCH_WEIGHTS["property_type"]
        reasons.append(f"Gayrimenkul türü uygun: {listing.get('property_type')} (+{MATCH_WEIGHTS['property_type']})")

    if criteria.transaction_type:
        possible += MATCH_WEIGHTS["transaction_type"]
        earned += MATCH_WEIGHTS["transaction_type"]
        reasons.append(f"İlan türü uygun: {listing.get('transaction_type')} (+{MATCH_WEIGHTS['transaction_type']})")

    if criteria.room_count:
        possible += MATCH_WEIGHTS["room_count"]
        earned += MATCH_WEIGHTS["room_count"]
        reasons.append(f"Oda sayısı uygun: {listing.get('room_count')} (+{MATCH_WEIGHTS['room_count']})")

    if criteria.price.minimum is not None or criteria.price.maximum is not None:
        possible += MATCH_WEIGHTS["budget"]
        price = float(listing["price"])
        budget_points = MATCH_WEIGHTS["budget"] * budget_quality(price, criteria)
        earned += budget_points
        reasons.append((f"Fiyat bütçe içinde: {price:,.0f} TL (+{budget_points:.1f}/{MATCH_WEIGHTS['budget']})").replace(",", "."))

    if (
        criteria.area.minimum_net_m2 is not None
        or criteria.area.minimum_gross_m2 is not None
    ):
        possible += MATCH_WEIGHTS["area"]
        earned += MATCH_WEIGHTS["area"]
        reasons.append(f"Alan uygun: {listing.get('net_m2')} m² net (+{MATCH_WEIGHTS['area']})")

    hard = criteria.hard_requirements
    hard_requirements = (
        ("in_complex", hard.in_complex, "in_complex", "Site tercihi kesin olarak karşılanıyor"),
        ("balcony", hard.balcony, "balcony", "Balkon şartı karşılanıyor"),
        ("furnished", hard.furnished, "other", "Eşya şartı karşılanıyor"),
    )
    for column, wanted, weight_key, reason in hard_requirements:
        if wanted is None:
            continue
        possible += MATCH_WEIGHTS[weight_key]
        earned += MATCH_WEIGHTS[weight_key]
        reasons.append(f"{reason} (+{MATCH_WEIGHTS[weight_key]})")

    if hard.near_metro is not None:
        possible += MATCH_WEIGHTS["near_metro"]
        earned += MATCH_WEIGHTS["near_metro"]
        reasons.append(f"Metro şartı karşılanıyor (+{MATCH_WEIGHTS['near_metro']})")

    preferences = criteria.soft_preferences
    scored_preferences = (
        ("in_complex", preferences.in_complex, "Site içerisinde (Güvenlikli)", "Site bilgisi"),
        ("balcony", preferences.balcony, "Balkonlu", "Balkon bilgisi"),
        ("furnished", preferences.furnished, "Eşya tercihi uygun", "Eşya bilgisi"),
    )
    for column, wanted, reason, missing_label in scored_preferences:
        if wanted is None:
            continue
        weight_key = "other" if column == "furnished" else column
        possible += MATCH_WEIGHTS[weight_key]
        actual = normalize_boolean(listing.get(column))
        if actual is wanted:
            earned += MATCH_WEIGHTS[weight_key]
            reasons.append(f"{reason} (+{MATCH_WEIGHTS[weight_key]})")
        elif actual is None:
            missing.append(f"{missing_label} belirtilmemiş; bu kriterden puan verilmedi")
        else:
            missing.append(f"{missing_label} müşteri tercihiyle uyuşmuyor")

    if preferences.near_metro is not None:
        possible += MATCH_WEIGHTS["near_metro"]
        metro_status = is_near_metro(listing)
        if metro_status is preferences.near_metro:
            earned += MATCH_WEIGHTS["near_metro"]
            reasons.append(f"Metro ve toplu taşımaya çok yakın (+{MATCH_WEIGHTS['near_metro']})")
        elif metro_status is None:
            missing.append("Ulaşım bilgisi net değil; metro kriterinden puan verilmedi")
        else:
            missing.append("Metro yakınlığı müşteri tercihiyle uyuşmuyor")

    for feature in criteria.desired_features:
        possible += MATCH_WEIGHTS["other"]
        if listing_has_feature(listing, feature):
            earned += MATCH_WEIGHTS["other"]
            reasons.append(f"İstenen özellik mevcut: {feature} (+{MATCH_WEIGHTS['other']})")
        else:
            missing.append(f"İstenen özellik bulunamadı: {feature}")

    score = round((earned / possible) * 100) if possible else 0
    return score, reasons, missing


def criterion_mode(criteria: CustomerCriteria, key: str, default: str) -> str:
    modes = getattr(criteria, "criterion_modes", {}) or {}
    mode = modes.get(key, default) if isinstance(modes, dict) else default
    return mode if mode in {"hard", "preference", "ignore"} else default


def _breakdown_item(
    key: str,
    label: str,
    mode: str,
    status: str,
    points: float,
    max_points: float,
    detail: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "mode": mode,
        "status": status,
        "points": round(points, 1),
        "max_points": round(max_points, 1),
        "detail": detail,
    }


def evaluate_listing_criteria(
    listing: pd.Series | dict, criteria: CustomerCriteria
) -> dict[str, Any]:
    """Tüm aktif kriterleri tek kez değerlendirip normalize edilmiş puan dökümü üretir."""
    breakdown: list[dict[str, Any]] = []

    def add_boolean(
        key: str,
        label: str,
        wanted: bool,
        actual: bool | None,
        weight_key: str,
        default_mode: str,
    ) -> None:
        mode = criterion_mode(criteria, key, default_mode)
        if mode == "ignore":
            return
        weight = MATCH_WEIGHTS[weight_key]
        if actual is None:
            status, points, detail = "unknown", 0.0, "İlan verisinde bilgi bulunmuyor"
        elif actual is wanted:
            status, points = "matched", float(weight)
            detail = "İstenen değer mevcut" if wanted else "İstenmeyen özellik bulunmuyor"
        else:
            status, points = "unmatched", 0.0
            detail = "Müşteri tercihiyle uyuşmuyor"
        breakdown.append(_breakdown_item(key, label, mode, status, points, weight, detail))

    location = criteria.location
    if location.city or location.district or location.neighborhoods:
        mode = criterion_mode(criteria, "location", "hard")
        if mode != "ignore":
            checks: list[tuple[str, bool]] = []
            if location.city:
                checks.append((location.city, location_matches(listing.get("city"), location.city)))
            if location.district:
                checks.append((location.district, location_matches(listing.get("district"), location.district)))
            if location.neighborhoods:
                requested = ", ".join(location.neighborhoods)
                matched = any(
                    location_matches(listing.get("neighborhood"), neighborhood)
                    for neighborhood in location.neighborhoods
                )
                checks.append((requested, matched))
            ratio = sum(int(matched) for _, matched in checks) / len(checks)
            status = "matched" if ratio == 1 else ("partial" if ratio > 0 else "unmatched")
            detail = (
                f"İlan: {listing.get('city')} / {listing.get('district')} / {listing.get('neighborhood')}"
            )
            breakdown.append(
                _breakdown_item(
                    "location", "Konum", mode, status,
                    MATCH_WEIGHTS["location"] * ratio, MATCH_WEIGHTS["location"], detail,
                )
            )

    simple_checks = (
        ("property_type", "Gayrimenkul türü", criteria.property_type, listing.get("property_type"), "property_type"),
        ("transaction_type", "İlan türü", criteria.transaction_type, listing.get("transaction_type"), "transaction_type"),
    )
    for key, label, wanted, actual, weight_key in simple_checks:
        if not wanted:
            continue
        mode = criterion_mode(criteria, key, "hard")
        if mode == "ignore":
            continue
        matched = normalize_text(actual) == normalize_text(wanted)
        breakdown.append(
            _breakdown_item(
                key, label, mode, "matched" if matched else "unmatched",
                MATCH_WEIGHTS[weight_key] if matched else 0, MATCH_WEIGHTS[weight_key],
                f"İstenen: {wanted} · İlan: {actual}",
            )
        )

    if criteria.room_count:
        mode = criterion_mode(criteria, "room_count", "hard")
        if mode != "ignore":
            actual_room = normalize_text(listing.get("room_count"))
            matched = actual_room in {normalize_text(room) for room in criteria.room_count}
            breakdown.append(
                _breakdown_item(
                    "room_count", "Oda sayısı", mode,
                    "matched" if matched else "unmatched",
                    MATCH_WEIGHTS["room_count"] if matched else 0,
                    MATCH_WEIGHTS["room_count"],
                    f"İstenen: {', '.join(criteria.room_count)} · İlan: {listing.get('room_count')}",
                )
            )

    if criteria.price.minimum is not None or criteria.price.maximum is not None:
        mode = criterion_mode(criteria, "budget", "hard")
        if mode != "ignore":
            price = pd.to_numeric(listing.get("price"), errors="coerce")
            weight = MATCH_WEIGHTS["budget"]
            if pd.isna(price):
                status, points, detail = "unknown", 0.0, "Fiyat bilgisi bulunmuyor"
            else:
                below = criteria.price.minimum is not None and price < criteria.price.minimum
                above = criteria.price.maximum is not None and price > criteria.price.maximum
                if not below and not above:
                    status, points = "matched", float(weight)
                    detail = f"Bütçe içinde: {price:,.0f} TL".replace(",", ".")
                else:
                    reference = criteria.price.minimum if below else criteria.price.maximum
                    difference = abs(float(price) - float(reference))
                    deviation = difference / max(float(reference), 1)
                    if deviation <= 0.15:
                        status = "partial"
                        points = weight * max(0.0, 1 - deviation / 0.15) * 0.75
                        direction = "altında" if below else "üzerinde"
                        detail = (
                            f"Sınırın {difference:,.0f} TL (%{deviation * 100:.1f}) {direction}"
                        ).replace(",", ".")
                    else:
                        status, points = "unmatched", 0.0
                        detail = f"Bütçe sınırıyla uyuşmuyor: {price:,.0f} TL".replace(",", ".")
            breakdown.append(_breakdown_item("budget", "Bütçe", mode, status, points, weight, detail))

    if criteria.area.minimum_net_m2 is not None or criteria.area.minimum_gross_m2 is not None:
        mode = criterion_mode(criteria, "area", "hard")
        if mode != "ignore":
            ratios = []
            details = []
            for column, wanted, label in (
                ("net_m2", criteria.area.minimum_net_m2, "net"),
                ("gross_m2", criteria.area.minimum_gross_m2, "brüt"),
            ):
                if wanted is None:
                    continue
                actual = pd.to_numeric(listing.get(column), errors="coerce")
                if pd.isna(actual):
                    ratios.append(None)
                    details.append(f"{label} alan bilinmiyor")
                else:
                    ratios.append(min(float(actual) / max(wanted, 1), 1.0))
                    details.append(f"{actual:g} m² {label} / en az {wanted} m²")
            known_ratios = [ratio for ratio in ratios if ratio is not None]
            if not known_ratios:
                status, ratio = "unknown", 0.0
            else:
                ratio = min(known_ratios)
                status = "matched" if ratio >= 1 else ("partial" if ratio >= 0.75 else "unmatched")
            breakdown.append(
                _breakdown_item(
                    "area", "Alan", mode, status, MATCH_WEIGHTS["area"] * ratio,
                    MATCH_WEIGHTS["area"], " · ".join(details),
                )
            )

    hard = criteria.hard_requirements
    soft = criteria.soft_preferences
    boolean_definitions = (
        ("in_complex", "Site içinde", "in_complex", "in_complex"),
        ("balcony", "Balkon", "balcony", "balcony"),
        ("furnished", "Eşyalı", "furnished", "other"),
    )
    for key, label, column, weight_key in boolean_definitions:
        hard_value = getattr(hard, key)
        soft_value = getattr(soft, key)
        wanted = hard_value if hard_value is not None else soft_value
        if wanted is not None:
            add_boolean(
                key, label, wanted, normalize_boolean(listing.get(column)), weight_key,
                "hard" if hard_value is not None else "preference",
            )

    hard_metro = hard.near_metro
    soft_metro = soft.near_metro
    wanted_metro = hard_metro if hard_metro is not None else soft_metro
    if wanted_metro is not None:
        add_boolean(
            "near_metro", "Metro yakınlığı", wanted_metro, is_near_metro(listing),
            "near_metro", "hard" if hard_metro is not None else "preference",
        )

    for feature in criteria.desired_features:
        key = f"feature:{feature}"
        mode = criterion_mode(criteria, key, "preference")
        if mode == "ignore":
            continue
        matched = listing_has_feature(listing, feature)
        breakdown.append(
            _breakdown_item(
                key, feature.title(), mode, "matched" if matched else "unmatched",
                MATCH_WEIGHTS["other"] if matched else 0, MATCH_WEIGHTS["other"],
                "İlan verisinde doğrulandı" if matched else "İlan verisinde doğrulanamadı",
            )
        )

    for feature in criteria.excluded_features:
        key = f"exclude:{feature}"
        mode = criterion_mode(criteria, key, "hard")
        if mode == "ignore":
            continue
        found = listing_has_feature(listing, feature)
        breakdown.append(
            _breakdown_item(
                key, f"Olmamalı: {feature}", mode, "unmatched" if found else "matched",
                0 if found else MATCH_WEIGHTS["other"], MATCH_WEIGHTS["other"],
                "İstenmeyen özellik ilanda var" if found else "İstenmeyen özellik bulunmuyor",
            )
        )

    for preference in criteria.unverified_preferences:
        breakdown.append(
            _breakdown_item(
                f"unverified:{preference}", preference.title(), "preference", "unknown",
                0, 0, "Ölçülebilir portföy verisi olmadığı için puanlanmadı",
            )
        )

    scored_items = [item for item in breakdown if item["max_points"] > 0]
    earned = sum(item["points"] for item in scored_items)
    possible = sum(item["max_points"] for item in scored_items)
    score = round((earned / possible) * 100) if possible else 0
    score = max(0, min(100, score))
    matched = [item for item in breakdown if item["status"] == "matched"]
    partial = [item for item in breakdown if item["status"] == "partial"]
    unmatched = [item for item in breakdown if item["status"] == "unmatched"]
    unknown = [item for item in breakdown if item["status"] == "unknown"]
    return {
        "score": score,
        "earned": round(earned, 1),
        "possible": round(possible, 1),
        "breakdown": breakdown,
        "matched": matched,
        "partial": partial,
        "unmatched": unmatched,
        "unknown": unknown,
    }


def passes_hard_constraints(
    listing: pd.Series | dict, criteria: CustomerCriteria
) -> bool:
    if normalize_text(listing.get("status")) != "active":
        return False
    evaluation = evaluate_listing_criteria(listing, criteria)
    return not any(
        item["mode"] == "hard" and item["status"] != "matched"
        for item in evaluation["breakdown"]
    )


def calculate_match_score(
    listing: pd.Series | dict, criteria: CustomerCriteria
) -> tuple[int, list[str], list[str]]:
    evaluation = evaluate_listing_criteria(listing, criteria)
    reasons = [
        f"{item['label']}: {item['detail']} (+{item['points']:g}/{item['max_points']:g})"
        for item in evaluation["matched"]
    ]
    missing = [
        f"{item['label']}: {item['detail']}"
        for item in [*evaluation["partial"], *evaluation["unmatched"], *evaluation["unknown"]]
    ]
    return evaluation["score"], reasons, missing


def match_listings(
    listings: pd.DataFrame, criteria: CustomerCriteria
) -> list[dict[str, Any]]:
    """Hard filtreleri uygular ve kalan ilanları yüksek puandan düşüğe sıralar."""
    results: list[dict[str, Any]] = []
    for _, listing in listings.iterrows():
        if not passes_hard_constraints(listing, criteria):
            continue
        evaluation = evaluate_listing_criteria(listing, criteria)
        score, reasons, missing = calculate_match_score(listing, criteria)
        result = listing.where(pd.notna(listing), None).to_dict()

        price = float(result.get("price") or 0)
        net_m2 = float(result.get("net_m2")) if result.get("net_m2") else None
        gross_m2 = float(result.get("gross_m2")) if result.get("gross_m2") else None
        financials = calculate_financial_metrics(price, net_m2, gross_m2)

        result.update(
            match_score=score,
            match_points_earned=evaluation["earned"],
            match_points_possible=evaluation["possible"],
            match_breakdown=evaluation["breakdown"],
            matched_criteria=evaluation["matched"],
            partial_criteria=evaluation["partial"],
            unmatched_criteria=evaluation["unmatched"],
            unknown_criteria=evaluation["unknown"],
            match_reasons=reasons,
            missing_information=missing,
            **financials,
        )
        results.append(result)

    return sorted(results, key=lambda item: item["match_score"], reverse=True)


def _legacy_find_near_matches(
    listings: pd.DataFrame, criteria: CustomerCriteria, budget_tolerance_pct: float = 0.15, max_results: int = 4
) -> list[dict[str, Any]]:
    """Kesin filtreleri hafifçe aşan (örneğin bütçeyi %5-15 aşan veya komşu lokasyondaki) alternatif fırsatları bulur."""
    near_matches: list[dict[str, Any]] = []

    # Zaten tam eşleşen ilanların ID'lerini bul
    exact_matched_ids = {
        listing["listing_id"] for listing in match_listings(listings, criteria)
    }

    for _, listing in listings.iterrows():
        if normalize_text(listing.get("status")) != "active":
            continue
        if listing.get("listing_id") in exact_matched_ids:
            continue

        price = pd.to_numeric(listing.get("price"), errors="coerce")
        if pd.isna(price):
            continue

        relaxation_reasons: list[str] = []

        # 1. Bütçe esnetme kontrolü
        max_budget = criteria.price.maximum
        if max_budget and price > max_budget:
            diff = price - max_budget
            diff_pct = (diff / max_budget) * 100
            if diff_pct <= (budget_tolerance_pct * 100):
                relaxation_reasons.append(
                    f"Bütçe %{diff_pct:.1f} aşıldı (+{diff:,.0f} TL)".replace(",", ".")
                )
            else:
                continue

        # 2. Oda sayısı kontrolü
        room = normalize_text(listing.get("room_count"))
        if criteria.room_count and room not in {normalize_text(r) for r in criteria.room_count}:
            # Yakın oda sayısı
            relaxation_reasons.append(f"Farklı oda tipi: {listing.get('room_count')}")

        # 3. Lokasyon kontrolü
        loc = criteria.location
        if loc.neighborhoods and not any(location_matches(listing.get("neighborhood"), n) for n in loc.neighborhoods):
            relaxation_reasons.append(f"Alternatif lokasyon: {listing.get('neighborhood')}")

        if not relaxation_reasons:
            continue

        score, reasons, missing = calculate_match_score(listing, criteria)
        # Esnetme olduğu için skoru hafifçe ölçekle
        adjusted_score = max(50, round(score * 0.88))

        result = listing.where(pd.notna(listing), None).to_dict()
        net_m2 = float(result.get("net_m2")) if result.get("net_m2") else None
        gross_m2 = float(result.get("gross_m2")) if result.get("gross_m2") else None
        financials = calculate_financial_metrics(price, net_m2, gross_m2)

        result.update(
            match_score=adjusted_score,
            match_reasons=reasons,
            missing_information=missing,
            relaxation_notes=relaxation_reasons,
            **financials,
        )
        near_matches.append(result)

    near_matches.sort(key=lambda item: item["match_score"], reverse=True)
    return near_matches[:max_results]


def find_near_matches(
    listings: pd.DataFrame,
    criteria: CustomerCriteria,
    budget_tolerance_pct: float = 0.15,
    max_results: int = 4,
) -> list[dict[str, Any]]:
    """En fazla iki zorunlu kriteri kaçıran, gerekçesi açık alternatifleri döndürür."""
    exact_ids = {item["listing_id"] for item in match_listings(listings, criteria)}
    alternatives: list[dict[str, Any]] = []

    for _, listing in listings.iterrows():
        if normalize_text(listing.get("status")) != "active":
            continue
        if listing.get("listing_id") in exact_ids:
            continue

        evaluation = evaluate_listing_criteria(listing, criteria)
        hard_failures = [
            item for item in evaluation["breakdown"]
            if item["mode"] == "hard" and item["status"] != "matched"
        ]
        if not hard_failures or len(hard_failures) > 2:
            continue

        budget_failure = next((item for item in hard_failures if item["key"] == "budget"), None)
        if budget_failure and criteria.price.maximum:
            price = pd.to_numeric(listing.get("price"), errors="coerce")
            if pd.isna(price) or price > criteria.price.maximum * (1 + budget_tolerance_pct):
                continue

        if evaluation["score"] < 45:
            continue

        relaxation_notes = [
            f"{item['label']}: {item['detail']}"
            for item in hard_failures
        ]
        score, reasons, missing = calculate_match_score(listing, criteria)
        result = listing.where(pd.notna(listing), None).to_dict()
        price = float(result.get("price") or 0)
        net_m2 = float(result.get("net_m2")) if result.get("net_m2") else None
        gross_m2 = float(result.get("gross_m2")) if result.get("gross_m2") else None
        result.update(
            match_score=score,
            match_points_earned=evaluation["earned"],
            match_points_possible=evaluation["possible"],
            match_breakdown=evaluation["breakdown"],
            matched_criteria=evaluation["matched"],
            partial_criteria=evaluation["partial"],
            unmatched_criteria=evaluation["unmatched"],
            unknown_criteria=evaluation["unknown"],
            match_reasons=reasons,
            missing_information=missing,
            relaxation_notes=relaxation_notes,
            **calculate_financial_metrics(price, net_m2, gross_m2),
        )
        alternatives.append(result)

    alternatives.sort(
        key=lambda item: (
            len([entry for entry in item["match_breakdown"] if entry["mode"] == "hard" and entry["status"] != "matched"]),
            -item["match_score"],
        )
    )
    return alternatives[:max_results]


def generate_client_pitch(
    matched_listings: list[dict[str, Any]],
    client_name: str = "Değerli Müşterimiz",
    consultant_name: str = "Emlak Danışmanınız",
    consultant_phone: str = "",
) -> str:
    """Eşleşen ilanlar için danışmanın doğrudan WhatsApp veya e-posta ile gönderebileceği Türkçe metin üretir."""
    if not matched_listings:
        return f"Merhaba {client_name},\n\nAradığınız kriterlere uygun güncel bir ilanımız şu an bulunmuyor. Yeni bir portföy girdiğinde ilk size bilgi vereceğim."

    top_listings = matched_listings[:3]
    count = len(top_listings)

    lines = [
        f"Merhaba {client_name}, 👋",
        "",
        f"Belirttiğiniz kriterlere göre öne çıkan *{count} gayrimenkulü* sizin için seçtim:",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    for index, listing in enumerate(top_listings, start=1):
        price_str = f"{float(listing['price']):,.0f} TL".replace(",", ".")
        m2_str = f"{listing.get('net_m2')} m² net" if listing.get("net_m2") else ""
        room_str = listing.get("room_count", "")
        neighborhood = listing.get("neighborhood", "")
        title = listing.get("title", "")

        transport = str(listing.get("transport_notes") or "")
        metro_match = re.search(r"(?:metro|istasyon)[^0-9]{0,15}(\d+(?:[.,]\d+)?)\s*(m|km)", transport, re.IGNORECASE)
        metro_text = f"{metro_match.group(1)} {metro_match.group(2)}" if metro_match else "Mesafe teyit edilmeli"
        lines.append(f"🏡 *SEÇENEK {index}: {title}*")
        lines.append(f"📊 *Müşteri uyumu:* %{listing.get('match_score', 0)}")
        lines.append(f"📍 *Konum:* {neighborhood} / {listing.get('district', '')}")
        lines.append(f"💰 *Fiyat:* {price_str}")
        lines.append(f"📐 *Özellikler:* {room_str} • {m2_str} • Kat: {listing.get('floor', '-')}")
        lines.append(f"🏢 *Bina yaşı:* {listing.get('building_age', 'Bilinmiyor')}")
        lines.append(f"🚇 *Metro:* {metro_text}")
        lines.append(f"🔢 *İlan numarası:* {listing.get('listing_id', '-')}")

        reasons = listing.get("match_reasons", [])
        if reasons:
            top_reasons = " • ".join(reasons[:2])
            lines.append(f"✨ *Neden uygun?* {top_reasons}")

        listing_url = str(listing.get("listing_url") or "").strip()
        if listing_url.startswith(("http://", "https://")) and "example.com" not in listing_url.lower():
            lines.append(f"🔗 *İlan linki:* {listing['listing_url']}")

        lines.append("─────────────────────")

    lines.extend([
        "Hangi ilanı birlikte yerinde görmek istersiniz? Size uygun gün ve saati iletirseniz randevu organize edebilirim. ☕",
        "",
        f"Saygılarımla,\n*{consultant_name}*",
    ])
    if consultant_phone.strip():
        lines.append(f"📞 {consultant_phone.strip()}")

    return "\n".join(lines)


def get_whatsapp_share_url(message: str, phone: str = "") -> str:
    """WhatsApp web / mobil paylaşım linkini döndürür."""
    encoded_text = urllib.parse.quote(message)
    clean_phone = re.sub(r"[^\d]", "", phone)
    if clean_phone:
        return f"https://wa.me/{clean_phone}?text={encoded_text}"
    return f"https://api.whatsapp.com/send?text={encoded_text}"
