import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from app import DEFAULT_LANG, app, get_translations
from data_repository import load_business_dataset
from export_service import history_to_csv, history_to_json, portfolio_analysis_to_csv
from financial_formatting import (
    EMPTY_DISPLAY,
    format_currency_value,
    format_number_value,
    format_percent_value,
    format_signed_currency_value,
)
from history_storage import append_history_entry, load_history, save_history
from portfolio_storage import (
    add_portfolio_product,
    delete_portfolio_product,
    load_portfolio,
    save_portfolio,
    update_portfolio_product,
)
from pricing_engine import (
    ProductData,
    compare_all_scenarios,
    run_full_analysis,
    validate_product,
)
from workspace_service import build_history_entry, build_portfolio_comparison, summarize_portfolio


TEST_PRODUCT = ProductData(
    name="Luna Crossbody Bag",
    category="Accessories",
    unit_cost=26.0,
    current_price=72.0,
    units_sold_30d=250.0,
    competitor_price=None,
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
        self.assertIn("assumptions", analysis)
        self.assertIn("overall_confidence", analysis)
        self.assertGreaterEqual(len(analysis["strategies"]), 5)
        self.assertIn("confidence_level", analysis["best_strategy"])
        self.assertIn("baseline_demand", analysis["assumptions"])

    def test_matching_product_uses_history_backed_estimates(self):
        analysis = run_full_analysis(TEST_PRODUCT)

        self.assertEqual(analysis["assumptions"]["baseline_demand"]["source"], "product_history")
        self.assertEqual(analysis["assumptions"]["elasticity"]["source"], "product_history")
        self.assertEqual(analysis["assumptions"]["return_rate"]["source"], "product_history")
        self.assertIn(analysis["overall_confidence"]["level"], {"High", "Medium"})

    def test_unmatched_product_falls_back_to_category_logic(self):
        product = ProductData(
            name="New Capsule Accessory",
            category="Accessories",
            unit_cost=24.0,
            current_price=69.0,
            units_sold_30d=180.0,
            competitor_price=None,
            scenario="NORMAL",
        )
        analysis = run_full_analysis(product)

        self.assertIn(
            analysis["assumptions"]["elasticity"]["source"],
            {"category_history", "category_default"},
        )
        self.assertIn(
            analysis["assumptions"]["return_rate"]["source"],
            {"category_history", "category_default"},
        )
        self.assertIn(analysis["overall_confidence"]["level"], {"Medium", "Low"})

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

    def test_financial_formatters_handle_empty_and_signed_values(self):
        currency_code = load_business_dataset().business_settings.currency

        self.assertEqual(format_currency_value(None, currency_code), EMPTY_DISPLAY)
        self.assertEqual(format_number_value(None), EMPTY_DISPLAY)
        self.assertEqual(format_percent_value(None), EMPTY_DISPLAY)
        self.assertTrue(format_signed_currency_value(125.5, currency_code).startswith("+"))
        self.assertTrue(format_signed_currency_value(-125.5, currency_code).startswith("-"))


class WorkspaceStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.portfolio_file = Path(self.temp_dir.name) / "portfolio.json"
        self.history_file = Path(self.temp_dir.name) / "history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_portfolio_load_seeds_initial_products_on_first_run(self):
        products = load_portfolio(self.portfolio_file)

        self.assertGreaterEqual(len(products), 3)
        self.assertIn("id", products[0])
        self.assertIn("name", products[0])
        self.assertIn("current_price", products[0])

    def test_portfolio_add_edit_delete_logic(self):
        save_portfolio(self.portfolio_file, [])

        added = add_portfolio_product(self.portfolio_file, test_product_payload())
        self.assertEqual(len(load_portfolio(self.portfolio_file)), 1)
        self.assertEqual(added["name"], "Luna Crossbody Bag")

        updated = update_portfolio_product(
            self.portfolio_file,
            added["id"],
            test_product_payload(name="Updated Bag", scenario="HIGH"),
        )
        self.assertEqual(updated["name"], "Updated Bag")
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
        self.assertEqual(history_entries[0]["product_name"], "Luna Crossbody Bag")
        self.assertEqual(history_entries[0]["selected_scenario"], "NORMAL")
        self.assertIn("recommended_strategy", history_entries[0])
        self.assertEqual(history_entries[0]["confidence_level"], analysis["overall_confidence"]["level"])
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

        self.assertIn("product_name,category,scenario,current_price", portfolio_csv)
        self.assertIn("confidence_level", history_csv)
        self.assertIn('"product_name": "Luna Crossbody Bag"', history_json)
        self.assertIn("match_level", rows[0])
        self.assertEqual(summary["total_products"], 1)
        self.assertIn("projected_total_cost", summary)
        self.assertIn("average_margin", summary)
        self.assertIn("best_performing_product", summary)
        self.assertIn("weakest_performing_product", summary)
        self.assertIn("highest_profit_product", summary)
        self.assertEqual(summary["history_entries"], 1)

    def test_portfolio_summary_calculates_totals_and_contribution_shares(self):
        save_portfolio(self.portfolio_file, [])
        add_portfolio_product(self.portfolio_file, test_product_payload())
        add_portfolio_product(
            self.portfolio_file,
            test_product_payload(
                name="Nova Mini Satchel",
                current_price=84.0,
                unit_cost=31.0,
                units_sold_30d=180.0,
                scenario="HIGH",
            ),
        )

        rows = build_portfolio_comparison(load_portfolio(self.portfolio_file))
        summary = summarize_portfolio(rows, [])

        expected_total_revenue = round(sum(row["portfolio_revenue"] for row in rows), 2)
        expected_total_cost = round(sum(row["portfolio_cost"] for row in rows), 2)
        expected_total_profit = round(sum(row["product_profit"] for row in rows), 2)

        self.assertEqual(summary["total_revenue"], expected_total_revenue)
        self.assertEqual(summary["total_cost"], expected_total_cost)
        self.assertEqual(summary["total_profit"], expected_total_profit)
        self.assertIn("profit_contribution_share", rows[0])
        self.assertTrue(all("product_profit" in row for row in rows))

        if expected_total_profit != 0:
            contribution_total = round(sum(row["profit_contribution_share"] for row in rows), 2)
            self.assertAlmostEqual(contribution_total, 100.0, places=1)

        best_profit = max(row["product_profit"] for row in rows)
        worst_profit = min(row["product_profit"] for row in rows)
        self.assertEqual(summary["best_performing_product"]["product_profit"], best_profit)
        self.assertEqual(summary["weakest_performing_product"]["product_profit"], worst_profit)


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
                dashboard_response = self.client.get(f"/dashboard?lang={lang}")
                self.assertEqual(analyze_response.status_code, 200)
                self.assertEqual(portfolio_response.status_code, 200)
                self.assertEqual(dashboard_response.status_code, 200)

    def test_analyze_page_injects_configured_currency_format(self):
        currency_code = load_business_dataset().business_settings.currency.upper()
        response = self.client.get("/analyze?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("window.pricePilotFormatting", body)
        self.assertIn(f'"currencyCode": "{currency_code}"', body)

    def test_language_is_saved_in_session(self):
        with self.client as client:
            client.get("/?lang=hy")
            with client.session_transaction() as session:
                self.assertEqual(session["lang"], "hy")

    def test_api_analyze_returns_explanation_and_assumptions(self):
        with self.client as client:
            client.get("/?lang=ru")
            response = client.post("/api/analyze", json=self.payload)
            data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("title", data["data"]["explanation"])
        self.assertGreater(len(data["data"]["explanation"]["assumption_cards"]), 0)
        self.assertIn("overall_confidence", data["data"])

    def test_api_analyze_saves_history_entry(self):
        response = self.client.post("/api/analyze", json=self.payload)
        data = response.get_json()
        history_entries = load_history(self.history_file)

        self.assertTrue(data["success"])
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["product_name"], self.payload["name"])
        self.assertIn("confidence_level", history_entries[0])

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
        self.assertIn("product_name,category,scenario,current_price", body)
        self.assertIn("Luna Crossbody Bag", body)

    def test_portfolio_page_renders_financial_summary_and_contribution_analysis(self):
        add_portfolio_product(self.portfolio_file, self.payload)

        response = self.client.get("/portfolio?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Total Revenue", body)
        self.assertIn("Total Cost", body)
        self.assertIn("Total Profit", body)
        self.assertIn("Contribution Share", body)

    def test_api_validation_errors_are_consistent(self):
        invalid_payload = dict(self.payload)
        invalid_payload["current_price"] = 0

        response = self.client.post("/api/analyze", json=invalid_payload)
        data = response.get_json()

        self.assertFalse(data["success"])
        self.assertIsNone(data["data"])
        self.assertIsInstance(data["error"], str)


if __name__ == "__main__":
    unittest.main()
