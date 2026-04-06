import unittest

from app import DEFAULT_LANG, app, get_translations
from pricing_engine import ProductData, compare_all_scenarios, run_full_analysis, validate_product


TEST_PRODUCT = ProductData(
    name="Smart Thermos Bottle",
    category="Home & Lifestyle",
    unit_cost=18.0,
    fixed_cost=3200.0,
    base_price=39.0,
    competitor_price=36.0,
    base_demand=420.0,
    inventory=500,
    elasticity=-1.35,
    marketing_budget=1400.0,
    return_rate=0.06,
    desired_margin=28.0,
    scenario="NORMAL",
)


class PricingEngineTests(unittest.TestCase):
    def test_validate_product_accepts_valid_product(self):
        self.assertTrue(validate_product(TEST_PRODUCT))

    def test_run_full_analysis_returns_expected_structure(self):
        analysis = run_full_analysis(TEST_PRODUCT)

        self.assertIn("best_strategy", analysis)
        self.assertIn("strategies", analysis)
        self.assertIn("price_profit_curve", analysis)
        self.assertIn("explanation", analysis)
        self.assertGreaterEqual(len(analysis["strategies"]), 6)
        self.assertIn("balanced_score", analysis["best_strategy"])
        self.assertIn("risk_level", analysis["best_strategy"])

    def test_compare_all_scenarios_returns_aggregate_metrics(self):
        comparison = compare_all_scenarios(TEST_PRODUCT)

        self.assertEqual(len(comparison["scenarios"]), 4)
        self.assertIn("aggregate", comparison)
        self.assertIn("mean_profit", comparison["aggregate"])
        self.assertIn("profit_std_dev", comparison["aggregate"])
        self.assertIn("best_overall_scenario", comparison)

    def test_translation_fallback_defaults_to_english(self):
        fallback = get_translations("de")
        english = get_translations(DEFAULT_LANG)

        self.assertEqual(fallback["nav.home"], english["nav.home"])
        self.assertEqual(fallback["nav.analyze"], english["nav.analyze"])


class FlaskAppTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.payload = {
            "name": "Smart Thermos Bottle",
            "category": "Home & Lifestyle",
            "unit_cost": 18,
            "fixed_cost": 3200,
            "base_price": 39,
            "competitor_price": 36,
            "base_demand": 420,
            "inventory": 500,
            "elasticity": -1.35,
            "marketing_budget": 1400,
            "return_rate": 0.06,
            "desired_margin": 28,
            "scenario": "NORMAL",
        }

    def test_pages_render_in_all_supported_languages(self):
        for lang in ("en", "hy", "ru"):
            with self.subTest(lang=lang):
                response = self.client.get(f"/analyze?lang={lang}")
                self.assertEqual(response.status_code, 200)

    def test_language_is_saved_in_session(self):
        with self.client as client:
            client.get("/?lang=hy")
            with client.session_transaction() as session:
                self.assertEqual(session["lang"], "hy")

    def test_api_analyze_returns_localized_explanation(self):
        with self.client as client:
            client.get("/?lang=ru")
            response = client.post("/api/analyze", json=self.payload)
            data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("Рекомендация", data["data"]["explanation"]["title"])

    def test_api_scenario_compare_still_returns_expected_data(self):
        response = self.client.post("/api/scenario-compare", json=self.payload)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("scenarios", data["data"])
        self.assertIn("aggregate", data["data"])

    def test_api_validation_errors_are_consistent(self):
        invalid_payload = dict(self.payload)
        invalid_payload["base_price"] = 0

        response = self.client.post("/api/analyze", json=invalid_payload)
        data = response.get_json()

        self.assertFalse(data["success"])
        self.assertIsNone(data["data"])
        self.assertIsInstance(data["error"], str)


if __name__ == "__main__":
    unittest.main()
