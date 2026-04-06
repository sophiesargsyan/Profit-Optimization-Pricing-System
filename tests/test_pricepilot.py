import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from app import DEFAULT_LANG, app, get_translations
from export_service import history_to_csv, history_to_json, portfolio_analysis_to_csv
from history_storage import append_history_entry, load_history, save_history
from portfolio_storage import (
    add_portfolio_product,
    delete_portfolio_product,
    load_portfolio,
    save_portfolio,
    update_portfolio_product,
)
from pricing_engine import ProductData, compare_all_scenarios, run_full_analysis, validate_product
from workspace_service import build_history_entry, build_portfolio_comparison, summarize_portfolio


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


def test_product_payload(**overrides):
    payload = asdict(TEST_PRODUCT)
    payload.update(overrides)
    return payload


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


class WorkspaceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.portfolio_file = Path(self.temp_dir.name) / "portfolio.json"
        self.history_file = Path(self.temp_dir.name) / "history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_portfolio_load_seeds_demo_products_on_first_run(self):
        products = load_portfolio(self.portfolio_file)

        self.assertGreaterEqual(len(products), 3)
        self.assertIn("id", products[0])
        self.assertIn("name", products[0])

    def test_portfolio_add_edit_delete_logic(self):
        save_portfolio(self.portfolio_file, [])

        added = add_portfolio_product(self.portfolio_file, test_product_payload())
        self.assertEqual(len(load_portfolio(self.portfolio_file)), 1)
        self.assertEqual(added["name"], "Smart Thermos Bottle")

        updated = update_portfolio_product(
            self.portfolio_file,
            added["id"],
            test_product_payload(name="Updated Bottle", scenario="HIGH"),
        )
        self.assertEqual(updated["name"], "Updated Bottle")
        self.assertEqual(updated["scenario"], "HIGH")
        self.assertEqual(len(load_portfolio(self.portfolio_file)), 1)

        deleted = delete_portfolio_product(self.portfolio_file, added["id"])
        self.assertTrue(deleted)
        self.assertEqual(load_portfolio(self.portfolio_file), [])

    def test_history_saving_persists_compact_entry(self):
        save_history(self.history_file, [])

        analysis = run_full_analysis(TEST_PRODUCT)
        entry = build_history_entry(analysis, timestamp="2026-04-06T10:00:00")
        append_history_entry(self.history_file, entry)
        history_entries = load_history(self.history_file)

        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["product_name"], "Smart Thermos Bottle")
        self.assertEqual(history_entries[0]["selected_scenario"], "NORMAL")
        self.assertIn("recommended_strategy", history_entries[0])
        self.assertEqual(history_entries[0]["timestamp"], "2026-04-06T10:00:00")

    def test_export_generation_and_summary_helpers(self):
        save_portfolio(self.portfolio_file, [])
        add_portfolio_product(self.portfolio_file, test_product_payload())
        rows = build_portfolio_comparison(load_portfolio(self.portfolio_file))
        history_entry = build_history_entry(
            run_full_analysis(TEST_PRODUCT),
            timestamp="2026-04-06T10:00:00",
        )

        portfolio_csv = portfolio_analysis_to_csv(rows)
        history_csv = history_to_csv([history_entry])
        history_json = history_to_json([history_entry])
        summary = summarize_portfolio(rows, [history_entry])

        self.assertIn("product_name,category,scenario", portfolio_csv)
        self.assertIn("recommended_strategy", history_csv)
        self.assertIn('"product_name": "Smart Thermos Bottle"', history_json)
        self.assertEqual(summary["total_products"], 1)
        self.assertEqual(summary["history_entries"], 1)


class FlaskAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.portfolio_file = Path(self.temp_dir.name) / "portfolio.json"
        self.history_file = Path(self.temp_dir.name) / "history.json"

        app.config["TESTING"] = True
        app.config["PORTFOLIO_FILE"] = self.portfolio_file
        app.config["HISTORY_FILE"] = self.history_file

        save_portfolio(self.portfolio_file, [])
        save_history(self.history_file, [])

        self.client = app.test_client()
        self.payload = test_product_payload()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pages_render_in_all_supported_languages(self):
        for lang in ("en", "hy", "ru"):
            with self.subTest(lang=lang):
                analyze_response = self.client.get(f"/analyze?lang={lang}")
                portfolio_response = self.client.get(f"/portfolio?lang={lang}")
                self.assertEqual(analyze_response.status_code, 200)
                self.assertEqual(portfolio_response.status_code, 200)

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

    def test_api_analyze_saves_history_entry(self):
        response = self.client.post("/api/analyze", json=self.payload)
        data = response.get_json()
        history_entries = load_history(self.history_file)

        self.assertTrue(data["success"])
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["product_name"], self.payload["name"])

    def test_api_scenario_compare_still_returns_expected_data(self):
        response = self.client.post("/api/scenario-compare", json=self.payload)
        data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("scenarios", data["data"])
        self.assertIn("aggregate", data["data"])

    def test_portfolio_export_csv_returns_file(self):
        add_portfolio_product(self.portfolio_file, self.payload)

        response = self.client.get("/portfolio/export.csv")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("product_name,category,scenario", body)
        self.assertIn("Smart Thermos Bottle", body)

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
