import unittest

from land_intelligence import (
    calculate_development_capacity,
    calculate_feasibility,
    calculate_land_risk,
)


class DevelopmentCapacityTests(unittest.TestCase):
    def test_example_capacity_uses_taks_and_kaks(self):
        result = calculate_development_capacity(1000, 0.30, 0.90, 3, 20)
        self.assertEqual(result["footprint_m2"], 300)
        self.assertEqual(result["gross_buildable_m2"], 900)
        self.assertEqual(result["sellable_area_m2"], 720)
        self.assertEqual(result["binding_constraint"], "KAKS / emsal sınırı")

    def test_floor_limit_can_be_more_restrictive_than_kaks(self):
        result = calculate_development_capacity(1000, 0.20, 1.20, 3, 20)
        self.assertEqual(result["zoning_area_m2"], 1200)
        self.assertEqual(result["gross_buildable_m2"], 600)
        self.assertEqual(result["binding_constraint"], "TAKS ve maksimum kat sınırı")

    def test_invalid_capacity_input_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_development_capacity(0, 0.30, 0.90, 3)


class LandRiskTests(unittest.TestCase):
    def risk(self, **overrides):
        values = {
            "zoning_type": "Konut",
            "taks": 0.30,
            "kaks": 0.90,
            "max_floors": 3,
            "ownership_type": "Müstakil",
            "encumbrance_status": "Yok",
            "cadastral_status": "Tamamlandı",
            "parcel_shape": "Düzgün",
            "road_frontage_m": 24,
            "slope_pct": 4,
            "road_access": True,
            "corner_parcel": True,
            "infrastructure": {"Elektrik": True, "Su": True, "Kanalizasyon": True},
            "hazards": {"Taşkın": False, "Heyelan": False, "Zemin riski": False},
            "regional_potential": 85,
            "sources": {"Tapu": "Resmî belge", "İmar": "Resmî belge"},
        }
        values.update(overrides)
        return calculate_land_risk(**values)

    def test_risky_title_and_hazard_reduce_score(self):
        safe = self.risk()
        risky = self.risk(
            ownership_type="Hisseli",
            encumbrance_status="Var",
            hazards={"Taşkın": True, "Heyelan": True, "Zemin riski": None},
        )
        self.assertGreater(safe["overall_score"], risky["overall_score"])
        self.assertTrue(any(flag["message"] == "Hisseli tapu" for flag in risky["risk_flags"]))

    def test_source_confidence_is_separate_and_visible(self):
        result = self.risk(sources={"Tapu": "Resmî belge", "İmar": "Doğrulanmamış"})
        self.assertEqual(result["confidence_score"], 55)
        self.assertEqual(len(result["source_rows"]), 2)


class FeasibilityTests(unittest.TestCase):
    def test_scenarios_are_ordered_by_profit(self):
        results = calculate_feasibility(
            land_price=10_000_000,
            closing_cost=500_000,
            construction_area_m2=900,
            sellable_area_m2=720,
            construction_cost_per_m2=20_000,
            project_cost=1_500_000,
            ground_improvement_cost=500_000,
            financing_cost=3_200_000,
            sale_price_per_m2=60_000,
            contingency_pct=10,
        )
        profits = [result["Brüt kâr"] for result in results]
        self.assertEqual([result["Senaryo"] for result in results], ["Kötümser", "Normal", "İyimser"])
        self.assertLess(profits[0], profits[1])
        self.assertLess(profits[1], profits[2])
        self.assertEqual(results[1]["Toplam maliyet"], 35_700_000)
        self.assertEqual(results[1]["Tahmini gelir"], 43_200_000)


if __name__ == "__main__":
    unittest.main()
