import unittest

import pandas as pd

from criteria_parser import (
    CustomerCriteria,
    LocationCriteria,
    PriceCriteria,
    RequirementFlags,
    finalize_criteria,
)
from matcher import evaluate_listing_criteria, passes_hard_constraints


def listing(**overrides):
    base = {
        "listing_id": "TEST-001",
        "status": "active",
        "city": "İstanbul",
        "district": "Başakşehir",
        "neighborhood": "Kayaşehir",
        "property_type": "Daire",
        "transaction_type": "Satılık",
        "room_count": "3+1",
        "price": 7_850_000,
        "net_m2": 126,
        "gross_m2": 145,
        "in_complex": True,
        "balcony": True,
        "furnished": False,
        "transport_notes": "Metro İstasyonu 300 m; Okul 450 m",
        "security": "7/24 Güvenlik + CCTV",
        "description": "Ferah aile dairesi",
    }
    base.update(overrides)
    return pd.Series(base)


class ScoringTests(unittest.TestCase):
    def criteria(self):
        return finalize_criteria(
            CustomerCriteria(
                location=LocationCriteria(
                    city="İstanbul",
                    district="Başakşehir",
                    neighborhoods=["Kayaşehir"],
                ),
                property_type="Daire",
                transaction_type="Satılık",
                room_count=["3+1"],
                price=PriceCriteria(maximum=8_000_000),
                hard_requirements=RequirementFlags(in_complex=True),
                soft_preferences=RequirementFlags(balcony=True, near_metro=True),
                desired_features=["güvenlik", "ferah"],
            ),
            "Kayaşehir'de güvenlikli site içinde ferah, balkonlu, metroya yakın 3+1 satılık daire; en fazla 8 milyon TL",
        )

    def test_score_is_normalized_from_active_weight_total(self):
        evaluation = evaluate_listing_criteria(listing(), self.criteria())
        self.assertEqual(evaluation["score"], 100)
        self.assertEqual(evaluation["earned"], evaluation["possible"])
        self.assertGreater(evaluation["possible"], 0)

    def test_synonyms_are_deduplicated_and_subjective_terms_do_not_score(self):
        criteria = self.criteria()
        self.assertNotIn("güvenlik", criteria.desired_features)
        self.assertNotIn("ferah", criteria.desired_features)
        self.assertIn("ferah", criteria.unverified_preferences)
        evaluation = evaluate_listing_criteria(listing(), criteria)
        subjective = next(item for item in evaluation["breakdown"] if item["key"] == "unverified:ferah")
        self.assertEqual(subjective["max_points"], 0)
        self.assertEqual(subjective["status"], "unknown")

    def test_hard_criterion_filters_but_preference_only_reduces_score(self):
        criteria = self.criteria()
        wrong_location = listing(neighborhood="Bahçeşehir 1. Kısım")
        self.assertFalse(passes_hard_constraints(wrong_location, criteria))
        criteria.criterion_modes["location"] = "preference"
        self.assertTrue(passes_hard_constraints(wrong_location, criteria))
        self.assertLess(evaluate_listing_criteria(wrong_location, criteria)["score"], 100)

    def test_unknown_preference_is_visible_and_gets_zero_points(self):
        criteria = self.criteria()
        unknown_transport = listing(transport_notes="")
        evaluation = evaluate_listing_criteria(unknown_transport, criteria)
        metro = next(item for item in evaluation["breakdown"] if item["key"] == "near_metro")
        self.assertEqual(metro["status"], "unknown")
        self.assertEqual(metro["points"], 0)


if __name__ == "__main__":
    unittest.main()
