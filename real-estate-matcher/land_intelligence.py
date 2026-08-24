"""Arsa yapılaşma, risk ve proje fizibilitesi hesapları."""

from __future__ import annotations

import math
from typing import Any


SOURCE_CONFIDENCE = {
    "Resmî belge": 100,
    "Harita verisi": 75,
    "Danışman beyanı": 65,
    "İlan açıklaması": 45,
    "AI tahmini": 30,
    "Doğrulanmamış": 10,
}


def _require_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} negatif olamaz.")


def calculate_development_capacity(
    land_area_m2: float,
    taks: float,
    kaks: float,
    max_floors: int,
    common_area_pct: float = 20,
) -> dict[str, Any]:
    """Plan girdilerinden yaklaşık yapılaşma kapasitesini hesaplar."""
    for name, value in (
        ("Arsa alanı", land_area_m2),
        ("TAKS", taks),
        ("KAKS", kaks),
        ("Ortak alan oranı", common_area_pct),
    ):
        _require_non_negative(name, float(value))
    if land_area_m2 <= 0 or taks <= 0 or kaks <= 0 or max_floors <= 0:
        raise ValueError("Arsa alanı, TAKS, KAKS ve kat sayısı sıfırdan büyük olmalıdır.")
    if taks > 1 or kaks > 10:
        raise ValueError("TAKS 0-1, KAKS ise 0-10 aralığında olmalıdır.")
    if not 0 <= common_area_pct < 100:
        raise ValueError("Ortak alan oranı 0-100 arasında olmalıdır.")

    footprint_m2 = land_area_m2 * taks
    zoning_area_m2 = land_area_m2 * kaks
    floor_limited_area_m2 = footprint_m2 * max_floors
    gross_buildable_m2 = min(zoning_area_m2, floor_limited_area_m2)
    sellable_area_m2 = gross_buildable_m2 * (1 - common_area_pct / 100)
    binding_constraint = (
        "KAKS / emsal sınırı"
        if zoning_area_m2 <= floor_limited_area_m2
        else "TAKS ve maksimum kat sınırı"
    )

    unit_scenarios = []
    for name, average_area in (
        ("2+1 daire", 85),
        ("3+1 daire", 120),
        ("4+1 daire", 155),
        ("İkiz villa bağımsız bölümü", 180),
    ):
        unit_scenarios.append(
            {
                "scenario": name,
                "average_unit_m2": average_area,
                "estimated_units": max(0, math.floor(sellable_area_m2 / average_area)),
            }
        )

    return {
        "footprint_m2": round(footprint_m2, 2),
        "zoning_area_m2": round(zoning_area_m2, 2),
        "floor_limited_area_m2": round(floor_limited_area_m2, 2),
        "gross_buildable_m2": round(gross_buildable_m2, 2),
        "sellable_area_m2": round(sellable_area_m2, 2),
        "binding_constraint": binding_constraint,
        "unit_scenarios": unit_scenarios,
    }


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def calculate_land_risk(
    *,
    zoning_type: str,
    taks: float | None,
    kaks: float | None,
    max_floors: int | None,
    ownership_type: str,
    encumbrance_status: str,
    cadastral_status: str,
    parcel_shape: str,
    road_frontage_m: float | None,
    slope_pct: float | None,
    road_access: bool | None,
    corner_parcel: bool,
    infrastructure: dict[str, bool | None],
    hazards: dict[str, bool | None],
    regional_potential: int,
    sources: dict[str, str],
) -> dict[str, Any]:
    """Doğrulanabilir girdilerle beş bileşenli arsa puanı üretir."""
    zoning_base = {
        "Konut": 90,
        "Ticaret": 92,
        "Konut + Ticaret": 95,
        "Sanayi": 82,
        "Turizm": 80,
        "Tarım": 38,
        "İmarsız": 20,
        "Bilinmiyor": 45,
    }.get(zoning_type, 45)
    zoning_checks = [float(zoning_base)]
    zoning_checks.append(100 if taks and taks > 0 else 35)
    zoning_checks.append(100 if kaks and kaks > 0 else 35)
    zoning_checks.append(100 if max_floors and max_floors > 0 else 45)
    zoning_score = _average(zoning_checks)

    title_score = _average(
        [
            {"Müstakil": 98, "Hisseli": 48, "Bilinmiyor": 45}.get(ownership_type, 45),
            {"Yok": 100, "Var": 25, "Bilinmiyor": 45}.get(encumbrance_status, 45),
            {"Tamamlandı": 100, "Belirsiz": 50, "Sorunlu": 15}.get(cadastral_status, 45),
        ]
    )

    shape_score = {"Düzgün": 95, "Trapez": 75, "Düzensiz": 48, "Bilinmiyor": 50}.get(parcel_shape, 50)
    if road_frontage_m is None:
        frontage_score = 45
    elif road_frontage_m >= 20:
        frontage_score = 100
    elif road_frontage_m >= 12:
        frontage_score = 80
    elif road_frontage_m >= 8:
        frontage_score = 60
    else:
        frontage_score = 30
    if slope_pct is None:
        slope_score = 45
    elif slope_pct <= 5:
        slope_score = 100
    elif slope_pct <= 10:
        slope_score = 82
    elif slope_pct <= 20:
        slope_score = 58
    else:
        slope_score = 30
    access_score = 100 if road_access is True else (20 if road_access is False else 45)
    physical_score = min(100, _average([shape_score, frontage_score, slope_score, access_score]) + (4 if corner_parcel else 0))

    infrastructure_score = _average(
        [100 if value is True else (20 if value is False else 50) for value in infrastructure.values()]
    )

    risk_flags: list[dict[str, str]] = []
    hazard_penalties = {
        "Taşkın": 18,
        "Heyelan": 20,
        "Orman sınırı": 16,
        "Sit alanı": 24,
        "Su havzası": 18,
        "Tarım koruma alanı": 16,
        "Kamulaştırma": 25,
        "Enerji hattı": 12,
        "Dere yatağı": 22,
        "Zemin riski": 20,
    }
    hazard_penalty = 0.0
    for label, penalty in hazard_penalties.items():
        value = hazards.get(label)
        if value is True:
            hazard_penalty += penalty
            risk_flags.append({"severity": "Yüksek", "message": f"{label} riski işaretlendi"})
        elif value is None:
            hazard_penalty += 3
            risk_flags.append({"severity": "Bilinmiyor", "message": f"{label} bilgisi doğrulanmadı"})

    regional_score = max(0, min(100, float(regional_potential) - min(45, hazard_penalty)))
    component_scores = {
        "İmar uygunluğu": round(zoning_score),
        "Tapu güvenliği": round(title_score),
        "Fiziksel uygunluk": round(physical_score),
        "Altyapı": round(infrastructure_score),
        "Bölgesel potansiyel": round(regional_score),
    }
    overall_score = round(
        component_scores["İmar uygunluğu"] * 0.30
        + component_scores["Tapu güvenliği"] * 0.25
        + component_scores["Fiziksel uygunluk"] * 0.20
        + component_scores["Altyapı"] * 0.15
        + component_scores["Bölgesel potansiyel"] * 0.10
    )

    if ownership_type == "Hisseli":
        risk_flags.append({"severity": "Yüksek", "message": "Hisseli tapu"})
    if encumbrance_status == "Var":
        risk_flags.append({"severity": "Yüksek", "message": "İpotek veya şerh beyanı var"})
    if road_frontage_m is not None and road_frontage_m < 8:
        risk_flags.append({"severity": "Orta", "message": "Yol cephesi 8 metrenin altında"})
    if slope_pct is not None and slope_pct > 20:
        risk_flags.append({"severity": "Orta", "message": "Yüksek eğim ek mühendislik maliyeti oluşturabilir"})
    for label, value in infrastructure.items():
        if value is None:
            risk_flags.append({"severity": "Bilinmiyor", "message": f"{label} bağlantısı doğrulanmadı"})

    source_rows = []
    for group, source in sources.items():
        source_rows.append(
            {
                "Bilgi grubu": group,
                "Kaynak": source,
                "Güven düzeyi": SOURCE_CONFIDENCE.get(source, 10),
            }
        )
    confidence_score = round(_average([row["Güven düzeyi"] for row in source_rows]))

    return {
        "component_scores": component_scores,
        "overall_score": overall_score,
        "confidence_score": confidence_score,
        "risk_flags": risk_flags,
        "source_rows": source_rows,
    }


def calculate_feasibility(
    *,
    land_price: float,
    closing_cost: float,
    construction_area_m2: float,
    sellable_area_m2: float,
    construction_cost_per_m2: float,
    project_cost: float,
    ground_improvement_cost: float,
    financing_cost: float,
    sale_price_per_m2: float,
    contingency_pct: float,
) -> list[dict[str, float | str]]:
    """Üç senaryoda maliyet, gelir, kâr ve başabaş fiyatı hesaplar."""
    inputs = {
        "Arsa fiyatı": land_price,
        "Tapu ve komisyon": closing_cost,
        "İnşaat alanı": construction_area_m2,
        "Satılabilir alan": sellable_area_m2,
        "İnşaat birim maliyeti": construction_cost_per_m2,
        "Ruhsat ve proje": project_cost,
        "Zemin iyileştirme": ground_improvement_cost,
        "Finansman": financing_cost,
        "Satış birim fiyatı": sale_price_per_m2,
        "Beklenmeyen gider oranı": contingency_pct,
    }
    for name, value in inputs.items():
        _require_non_negative(name, float(value))
    if construction_area_m2 <= 0 or sellable_area_m2 <= 0:
        raise ValueError("İnşaat ve satılabilir alan sıfırdan büyük olmalıdır.")

    scenarios = (
        ("Kötümser", 1.15, 0.90, 1.25),
        ("Normal", 1.00, 1.00, 1.00),
        ("İyimser", 0.95, 1.08, 0.75),
    )
    results: list[dict[str, float | str]] = []
    for name, construction_multiplier, sales_multiplier, contingency_multiplier in scenarios:
        construction_cost = construction_area_m2 * construction_cost_per_m2 * construction_multiplier
        direct_cost = construction_cost + project_cost + ground_improvement_cost
        contingency_cost = direct_cost * (contingency_pct / 100) * contingency_multiplier
        total_cost = land_price + closing_cost + direct_cost + financing_cost + contingency_cost
        revenue = sellable_area_m2 * sale_price_per_m2 * sales_multiplier
        gross_profit = revenue - total_cost
        profitability_pct = (gross_profit / total_cost * 100) if total_cost else 0
        margin_pct = (gross_profit / revenue * 100) if revenue else 0
        break_even_m2 = total_cost / sellable_area_m2
        results.append(
            {
                "Senaryo": name,
                "Toplam maliyet": round(total_cost),
                "Tahmini gelir": round(revenue),
                "Brüt kâr": round(gross_profit),
                "Kârlılık %": round(profitability_pct, 1),
                "Kâr marjı %": round(margin_pct, 1),
                "Başabaş TL/m²": round(break_even_m2),
            }
        )
    return results
