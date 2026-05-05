import io
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from auth_storage import load_users
from app import (
    BULK_TEMPLATE_COLUMNS,
    DEFAULT_LANG,
    _build_xlsx_workbook,
    app,
    build_bulk_analysis_template,
    get_translations,
    parse_bulk_analysis_products,
    validate_bulk_analysis_workbook,
)
from data_repository import load_business_dataset
from export_service import history_to_csv, history_to_json, portfolio_analysis_to_csv
from finance_storage import load_finance_records, save_finance_records
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
from product_analysis_service import analyze_product, compare_product_scenarios
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

    def test_reusable_analysis_service_accepts_structured_product_input(self):
        analysis = analyze_product(
            {
                "product_name": "Luna Crossbody Bag",
                "category": "Accessories",
                "unit_cost": 26.0,
                "current_price": 72.0,
                "base_demand": 250.0,
                "competitor_price": 79.0,
                "elasticity": 1.2,
                "min_price": 58.0,
                "max_price": 92.0,
            }
        )

        self.assertIn("best_strategy", analysis)
        self.assertIn("price_profit_curve", analysis)
        self.assertIn("analysis_summary", analysis)
        self.assertIn("strategy_comparison", analysis["analysis_summary"])
        self.assertEqual(analysis["product"]["name"], "Luna Crossbody Bag")
        self.assertEqual(analysis["product"]["elasticity_override"], -1.2)
        self.assertEqual(
            analysis["analysis_summary"]["optimal_price"],
            analysis["best_strategy"]["price"],
        )
        self.assertGreater(len(analysis["analysis_summary"]["candidate_prices"]), 0)
        prices = [point["price"] for point in analysis["analysis_summary"]["candidate_prices"]]
        self.assertGreaterEqual(min(prices), 58.0)
        self.assertLessEqual(max(prices), 92.0)

    def test_reusable_scenario_service_accepts_product_data(self):
        comparison = compare_product_scenarios(TEST_PRODUCT)

        self.assertEqual(len(comparison["scenarios"]), 4)
        self.assertIn("aggregate", comparison)

    def test_reusable_analysis_service_maps_free_form_categories(self):
        analysis = analyze_product(
            {
                "product_name": "City Tote Bag",
                "category": "bags",
                "unit_cost": 28.0,
                "current_price": 74.0,
                "base_demand": 160.0,
                "competitor_price": 79.0,
                "elasticity": 1.15,
            }
        )

        self.assertEqual(analysis["product"]["category"], "Accessories")
        self.assertIn("analysis_summary", analysis)

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

    def test_history_saving_persists_rich_entry(self):
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
        self.assertEqual(history_entries[0]["created_at"], "2026-04-06T10:00:00")
        self.assertEqual(history_entries[0]["analysis_type"], "single")
        self.assertEqual(history_entries[0]["current_price"], TEST_PRODUCT.current_price)
        self.assertIn("input_data", history_entries[0])
        self.assertIn("result_data", history_entries[0])
        self.assertEqual(history_entries[0]["input_data"]["name"], TEST_PRODUCT.name)

    def test_export_generation_and_summary_helpers(self):
        history_entry = build_history_entry(
            run_full_analysis(TEST_PRODUCT),
            timestamp="2026-04-06T10:00:00",
        )
        rows = build_portfolio_comparison([history_entry])

        portfolio_csv = portfolio_analysis_to_csv(rows)
        history_csv = history_to_csv([history_entry])
        history_json = history_to_json([history_entry])
        summary = summarize_portfolio(rows, [history_entry])

        self.assertIn("product_name,category,scenario,current_price", portfolio_csv)
        self.assertIn("confidence_level", history_csv)
        self.assertIn('"product_name": "Luna Crossbody Bag"', history_json)
        self.assertIn('"analysis_type": "single"', history_json)
        self.assertIn("match_level", rows[0])
        self.assertEqual(summary["total_products"], 1)
        self.assertIn("projected_total_cost", summary)
        self.assertIn("average_margin", summary)
        self.assertIn("total_expected_profit", summary)
        self.assertIn("average_profit_improvement_percent", summary)
        self.assertIn("top_expected_profit_product", summary)
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
        self.users_file = Path(self.temp_dir.name) / "users.json"
        self.finance_file = Path(self.temp_dir.name) / "finance.json"

        app.config["TESTING"] = True
        app.config["PORTFOLIO_FILE"] = self.portfolio_file
        app.config["HISTORY_FILE"] = self.history_file
        app.config["USERS_FILE"] = self.users_file
        app.config["FINANCE_FILE"] = self.finance_file

        save_portfolio(self.portfolio_file, [])
        save_history(self.history_file, [])
        save_finance_records(self.finance_file, [])

        self.client = app.test_client()
        self.payload = test_product_payload()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _sign_up(self, client, **overrides):
        payload = {
            "name": "Demo User",
            "email": "demo@example.com",
            "password": "password123",
            "confirm_password": "password123",
        }
        payload.update(overrides)
        return client.post("/sign-up?lang=en", data=payload)

    def _sign_in(self, client, **overrides):
        payload = {
            "identifier": "demo@example.com",
            "password": "password123",
        }
        payload.update(overrides)
        return client.post("/sign-in?lang=en", data=payload)

    def _user_by_email(self, email):
        normalized_email = email.strip().lower()
        return next(user for user in load_users(self.users_file) if user["email"] == normalized_email)

    def test_public_pages_render_while_protected_pages_redirect_in_all_supported_languages(self):
        for lang in ("en", "hy", "ru"):
            with self.subTest(lang=lang):
                home_response = self.client.get(f"/?lang={lang}")
                analyze_response = self.client.get(f"/analyze?lang={lang}")
                finance_response = self.client.get(f"/finance?lang={lang}")
                portfolio_response = self.client.get(f"/portfolio?lang={lang}")
                dashboard_response = self.client.get(f"/dashboard?lang={lang}")
                about_response = self.client.get(f"/about?lang={lang}")
                sign_in_response = self.client.get(f"/sign-in?lang={lang}")
                sign_up_response = self.client.get(f"/sign-up?lang={lang}")
                self.assertEqual(home_response.status_code, 200)
                self.assertEqual(analyze_response.status_code, 302)
                self.assertIn("/sign-in?", analyze_response.location)
                self.assertIn(f"next=/analyze?lang%3D{lang}", analyze_response.location)
                self.assertIn(f"&lang={lang}", analyze_response.location)
                self.assertEqual(finance_response.status_code, 302)
                self.assertEqual(portfolio_response.status_code, 302)
                self.assertEqual(dashboard_response.status_code, 302)
                self.assertEqual(about_response.status_code, 302)
                self.assertEqual(sign_in_response.status_code, 200)
                self.assertEqual(sign_up_response.status_code, 200)

    def test_authenticated_user_can_access_protected_pages_in_all_supported_languages(self):
        with self.client as client:
            self._sign_up(client)

            for lang in ("en", "hy", "ru"):
                with self.subTest(lang=lang):
                    analyze_response = client.get(f"/analyze?lang={lang}")
                    bulk_response = client.get(f"/bulk-analysis?lang={lang}")
                    finance_response = client.get(f"/finance?lang={lang}")
                    portfolio_response = client.get(f"/portfolio?lang={lang}")
                    dashboard_response = client.get(f"/dashboard?lang={lang}")
                    about_response = client.get(f"/about?lang={lang}")
                    self.assertEqual(analyze_response.status_code, 200)
                    self.assertEqual(bulk_response.status_code, 200)
                    self.assertEqual(finance_response.status_code, 200)
                    self.assertEqual(portfolio_response.status_code, 200)
                    self.assertEqual(dashboard_response.status_code, 200)
                    self.assertEqual(about_response.status_code, 200)

    def test_analyze_page_injects_configured_currency_format(self):
        currency_code = load_business_dataset().business_settings.currency.upper()
        with self.client as client:
            self._sign_up(client)
            response = client.get("/analyze?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("window.pricePilotFormatting", body)
        self.assertIn(f'"currencyCode": "{currency_code}"', body)

    def test_analyze_page_uses_tabbed_workspace_with_empty_inputs(self):
        with self.client as client:
            self._sign_up(client)
            response = client.get("/analyze?lang=hy")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Մեկ ապրանք", body)
        self.assertIn("Բազմաթիվ ապրանքներ", body)
        self.assertIn("Ապրանքի տվյալները", body)
        self.assertIn("Ապրանքի անվանումը", body)
        self.assertIn("Կատեգորիա", body)
        self.assertIn("Միավորի ինքնարժեքը", body)
        self.assertIn("Ընթացիկ գինը", body)
        self.assertIn("Վերջին 30 օրվա վաճառքի քանակը", body)
        self.assertIn("Մրցակցի գինը", body)
        self.assertIn("Շուկայական սցենար", body)
        self.assertIn("Ընդլայնված վերլուծություն", body)
        self.assertIn("Ընդլայնված ռեժիմ", body)
        self.assertIn("Բացել դաշտերը", body)
        self.assertIn("Պահեստի սահմանափակում", body)
        self.assertIn("Հաշվել", body)
        self.assertIn('placeholder="Մուտքագրիր ապրանքի անունը"', body)
        self.assertLess(body.index('for="current_price"'), body.index('for="competitor_price"'))
        self.assertLess(body.index('for="competitor_price"'), body.index('for="units_sold_30d"'))
        self.assertNotIn('placeholder="26.00"', body)
        self.assertNotIn('placeholder="72.00"', body)
        self.assertNotIn('placeholder="79.00"', body)
        self.assertNotIn('placeholder="250"', body)
        self.assertNotIn('placeholder="1.10"', body)
        self.assertNotIn('placeholder="8.0"', body)
        self.assertNotIn('placeholder="40.00"', body)
        self.assertNotIn('placeholder="35.0"', body)
        self.assertNotIn('placeholder="1.05"', body)
        self.assertNotIn('placeholder="500"', body)
        self.assertIn('action="/analyze?tab=bulk&amp;lang=hy"', body)
        self.assertNotIn("Սկսիր ամենակարևոր տվյալներից։", body)
        self.assertNotIn("Վերագրիր մոդելի գնահատականները միայն այն դեպքում", body)
        self.assertNotIn("Օգտագործեք այն ապրանքի անվանումը", body)
        self.assertIn('id="elasticity_override"', body)
        self.assertIn('id="return_rate_override"', body)
        self.assertIn('id="fixed_cost_allocation_override"', body)
        self.assertIn('id="target_margin_override"', body)
        self.assertIn('id="marketing_factor_override"', body)
        self.assertIn('id="inventory_constraint_override"', body)
        self.assertIn('id="analysisResultsShell" class="analysis-results-shell mt-4" hidden', body)

    def test_language_is_saved_in_session(self):
        with self.client as client:
            client.get("/?lang=hy")
            with client.session_transaction() as session:
                self.assertEqual(session["lang"], "hy")

    def test_api_analyze_returns_explanation_and_assumptions(self):
        with self.client as client:
            self._sign_up(client)
            client.get("/?lang=ru")
            response = client.post("/api/analyze", json=self.payload)
            data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("title", data["data"]["explanation"])
        self.assertGreater(len(data["data"]["explanation"]["assumption_cards"]), 0)
        self.assertIn("overall_confidence", data["data"])

    def test_api_analyze_saves_history_entry(self):
        with self.client as client:
            self._sign_up(client)
            response = client.post("/api/analyze", json=self.payload)
            data = response.get_json()
            history_entries = load_history(self.history_file)
            current_user = self._user_by_email("demo@example.com")

        self.assertTrue(data["success"])
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["product_name"], self.payload["name"])
        self.assertIn("confidence_level", history_entries[0])
        self.assertEqual(history_entries[0]["user_id"], current_user["id"])
        self.assertEqual(history_entries[0]["analysis_type"], "single")
        self.assertEqual(history_entries[0]["input_data"]["name"], self.payload["name"])
        self.assertIn("result_data", history_entries[0])

    def test_portfolio_page_shows_saved_products_after_analysis(self):
        with self.client as client:
            self._sign_up(client)
            client.post("/api/analyze", json=self.payload)
            response = client.get("/portfolio?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Saved Analyses", body)
        self.assertIn(self.payload["name"], body)
        self.assertNotIn('<div class="empty-state empty-state-block">', body)

    def test_finance_page_renders_armenian_budget_form(self):
        with self.client as client:
            self._sign_up(client)
            response = client.get("/finance?lang=hy")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ֆինանսներ և բյուջեի կառավարում", body)
        self.assertIn("Բյուջեի մուտքեր", body)
        self.assertIn("Ընդհանուր բյուջե", body)
        self.assertIn("Ապրանքի ծախսերի բյուջե", body)
        self.assertIn("Պահուստային բյուջե", body)
        self.assertIn('href="/finance?lang=hy"', body)

    def test_finance_page_calculates_budget_summary_and_recommendations(self):
        currency_code = load_business_dataset().business_settings.currency.upper()

        with self.client as client:
            self._sign_up(client)
            response = client.post(
                "/finance?lang=en",
                data={
                    "total_budget": "1000",
                    "product_cost_budget": "400",
                    "marketing_budget": "350",
                    "delivery_budget": "100",
                    "packaging_budget": "50",
                    "operational_budget": "70",
                    "reserve_budget": "30",
                },
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Budget summary", body)
        self.assertIn("Allocated amount", body)
        self.assertIn("Remaining budget", body)
        self.assertIn("Budget status", body)
        self.assertIn(format_currency_value(1000, currency_code), body)
        self.assertIn(format_currency_value(30, currency_code), body)
        self.assertIn("35.0%", body)
        self.assertIn("3.0%", body)
        self.assertIn("Balanced", body)
        self.assertIn("Reserve budget is below 10% of the total budget.", body)
        self.assertIn("Marketing budget is above 30% of the total budget.", body)
        self.assertIn("Budget is balanced. Current allocations match the total budget.", body)

    def test_finance_data_is_saved_after_post(self):
        with self.client as client:
            self._sign_up(client)
            client.post(
                "/finance?lang=en",
                data={
                    "total_budget": "1000",
                    "product_cost_budget": "400",
                    "marketing_budget": "120",
                    "delivery_budget": "90",
                    "packaging_budget": "40",
                    "operational_budget": "200",
                    "reserve_budget": "150",
                },
            )
            current_user = self._user_by_email("demo@example.com")

        finance_records = load_finance_records(self.finance_file)
        self.assertEqual(len(finance_records), 1)
        self.assertEqual(finance_records[0]["user_id"], current_user["id"])
        self.assertEqual(finance_records[0]["total_budget"], 1000.0)
        self.assertEqual(finance_records[0]["marketing_budget"], 120.0)
        self.assertIn("created_at", finance_records[0])
        self.assertIn("updated_at", finance_records[0])
        self.assertNotIn("budget_summary", finance_records[0])
        self.assertNotIn("status", finance_records[0])
        self.assertNotIn("recommendations", finance_records[0])

    def test_finance_get_preloads_saved_data(self):
        with self.client as client:
            self._sign_up(client)
            client.post(
                "/finance?lang=en",
                data={
                    "total_budget": "1500",
                    "product_cost_budget": "500",
                    "marketing_budget": "250",
                    "delivery_budget": "125",
                    "packaging_budget": "75",
                    "operational_budget": "300",
                    "reserve_budget": "250",
                },
            )
            response = client.get("/finance?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="1500"', body)
        self.assertIn('value="500"', body)
        self.assertIn('value="250"', body)
        self.assertIn("Budget summary", body)
        self.assertIn("Balanced", body)

    def test_finance_user_isolation_hides_other_users_budget(self):
        client_a = app.test_client()
        client_b = app.test_client()

        self._sign_up(client_a, name="User A", email="usera@example.com")
        self._sign_up(client_b, name="User B", email="userb@example.com")
        client_b.post(
            "/finance?lang=en",
            data={
                "total_budget": "7777",
                "product_cost_budget": "3000",
                "marketing_budget": "1000",
                "delivery_budget": "500",
                "packaging_budget": "250",
                "operational_budget": "1500",
                "reserve_budget": "1527",
            },
        )

        response = client_a.get("/finance?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('value="7777"', body)
        self.assertNotIn('value="3000"', body)
        self.assertNotIn('<span class="risk-pill ', body)

    def test_saved_history_persists_after_logout_and_login(self):
        product_name = "Persisted Workspace Product"

        with self.client as client:
            self._sign_up(client)
            client.post("/api/analyze", json=test_product_payload(name=product_name))
            client.post("/sign-out?lang=en")
            self._sign_in(client)
            response = client.get("/portfolio?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(product_name, body)

    def test_api_scenario_compare_still_returns_expected_data(self):
        with self.client as client:
            self._sign_up(client)
            response = client.post("/api/scenario-compare", json=self.payload)
            data = response.get_json()

        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertIn("scenarios", data["data"])
        self.assertIn("aggregate", data["data"])

    def test_api_routes_require_authentication(self):
        response = self.client.post("/api/analyze", json=self.payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 401)
        self.assertFalse(data["success"])
        self.assertIn("redirect_url", data["data"])
        self.assertIsInstance(data["error"], str)

    def test_portfolio_export_csv_returns_file(self):
        client_b = app.test_client()

        with self.client as client:
            self._sign_up(client)
            self._sign_up(client_b, name="Other User", email="other@example.com")
            client.post("/api/analyze", json=self.payload)
            client_b.post("/api/analyze", json=test_product_payload(name="Other User Product"))

            response = client.get("/portfolio/export.csv")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("product_name,category,scenario,current_price", body)
        self.assertIn("Luna Crossbody Bag", body)
        self.assertNotIn("Other User Product", body)

    def test_portfolio_page_shows_only_current_users_products(self):
        client_a = app.test_client()
        client_b = app.test_client()

        self._sign_up(client_a, name="User A", email="usera@example.com")
        self._sign_up(client_b, name="User B", email="userb@example.com")
        client_a.post("/api/analyze", json=test_product_payload(name="User A Product"))
        client_b.post("/api/analyze", json=test_product_payload(name="User B Product"))

        response = client_a.get("/portfolio?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("User A Product", body)
        self.assertNotIn("User B Product", body)

    def test_portfolio_page_hides_other_users_products_and_shows_empty_state(self):
        client_a = app.test_client()
        client_b = app.test_client()

        self._sign_up(client_a, name="User A", email="usera@example.com")
        self._sign_up(client_b, name="User B", email="userb@example.com")
        client_b.post("/api/analyze", json=test_product_payload(name="User B Product"))

        response = client_a.get("/portfolio?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("User B Product", body)
        self.assertIn("0 saved analyses", body)
        self.assertIn("0.0%", body)
        self.assertIn("N/A", body)
        self.assertIn("No saved analyses yet. Run an analysis to start your workspace history.", body)

    def test_history_export_json_returns_only_current_users_entries(self):
        client_a = app.test_client()
        client_b = app.test_client()

        self._sign_up(client_a, name="User A", email="usera@example.com")
        self._sign_up(client_b, name="User B", email="userb@example.com")
        client_a.post(
            "/api/analyze",
            json=test_product_payload(name="User A Analysis"),
        )
        client_b.post(
            "/api/analyze",
            json=test_product_payload(name="User B Analysis"),
        )

        response = client_a.get("/history/export.json")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.content_type)
        self.assertIn("User A Analysis", body)
        self.assertNotIn("User B Analysis", body)

    def test_dashboard_shows_only_current_users_saved_analyses(self):
        client_a = app.test_client()
        client_b = app.test_client()

        self._sign_up(client_a, name="User A", email="usera@example.com")
        self._sign_up(client_b, name="User B", email="userb@example.com")
        client_a.post("/api/analyze", json=test_product_payload(name="User A Dashboard Product"))
        client_b.post("/api/analyze", json=test_product_payload(name="User B Dashboard Product"))

        response = client_a.get("/dashboard?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("User A Dashboard Product", body)
        self.assertNotIn("User B Dashboard Product", body)

    def test_bulk_analysis_saves_only_successful_rows(self):
        workbook_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-SUCCESS",
                    "Bulk Success Product",
                    "Accessories",
                    72,
                    26,
                    250,
                    1.2,
                    79,
                    "",
                    "",
                ),
                (
                    "SKU-FAIL",
                    "Bulk Failure Product",
                    "Accessories",
                    75,
                    28,
                    210,
                    1.1,
                    82,
                    "",
                    "",
                ),
            )
        )

        def bulk_side_effect(product_input, options=None):
            if isinstance(product_input, dict) and product_input.get("product_id") == "SKU-FAIL":
                raise ValueError("Synthetic bulk failure")
            return analyze_product(product_input, options)

        with self.client as client:
            self._sign_up(client)
            with mock.patch("app.analyze_product", side_effect=bulk_side_effect):
                response = client.post(
                    "/bulk-analysis?lang=en",
                    data={"product_file": (io.BytesIO(workbook_content), "products.xlsx")},
                    content_type="multipart/form-data",
                )
                body = response.get_data(as_text=True)
            history_entries = load_history(self.history_file)
            current_user = self._user_by_email("demo@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertIn("1 of 2 products were analyzed successfully. 1 products failed.", body)
        self.assertIn("Bulk Success Product", body)
        self.assertIn("SKU-FAIL could not be analyzed", body)
        self.assertEqual(len(history_entries), 1)
        self.assertEqual(history_entries[0]["user_id"], current_user["id"])
        self.assertEqual(history_entries[0]["analysis_type"], "bulk")
        self.assertEqual(history_entries[0]["product_name"], "Bulk Success Product")
        self.assertNotIn("Bulk Failure Product", [entry["product_name"] for entry in history_entries])

    def test_bulk_template_download_validates_successfully(self):
        template_content = build_bulk_analysis_template()
        validation_result = validate_bulk_analysis_workbook(io.BytesIO(template_content))
        products = parse_bulk_analysis_products(template_content)

        self.assertEqual(validation_result.errors, [])
        self.assertEqual(validation_result.valid_row_count, 1)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["current_price"], 72.0)
        self.assertEqual(products[0]["unit_cost"], 26.0)
        self.assertEqual(products[0]["base_demand"], 250.0)
        self.assertEqual(products[0]["elasticity"], 1.2)
        self.assertEqual(products[0]["competitor_price"], 79.0)
        self.assertEqual(products[0]["min_price"], 58.0)
        self.assertEqual(products[0]["max_price"], 92.0)

        with self.client as client:
            self._sign_up(client)
            download_response = client.get("/bulk-analysis/template.xlsx?lang=en")
            upload_response = client.post(
                "/bulk-analysis?lang=en",
                data={"product_file": (io.BytesIO(template_content), "products.xlsx")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            body = upload_response.get_data(as_text=True)

        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.data[:2], b"PK")
        self.assertIn("spreadsheetml.sheet", download_response.content_type)
        self.assertEqual(upload_response.status_code, 200)
        self.assertIn("Bulk analysis summary is ready.", body)
        self.assertIn("1 of 1 products were analyzed successfully. 0 products failed.", body)
        self.assertIn("SKU-001", body)
        self.assertIn("Optimal Price", body)

    def test_bulk_validation_accepts_decimal_dot_strings(self):
        workbook_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-DOT",
                    "Dot Decimal Product",
                    "Accessories",
                    " 72.5 ",
                    "26.1",
                    "250",
                    "1.2",
                    "79.4",
                    "58.2",
                    "92.8",
                ),
            )
        )

        validation_result = validate_bulk_analysis_workbook(io.BytesIO(workbook_content))
        products = parse_bulk_analysis_products(workbook_content)

        self.assertEqual(validation_result.errors, [])
        self.assertEqual(validation_result.valid_row_count, 1)
        self.assertEqual(products[0]["current_price"], 72.5)
        self.assertEqual(products[0]["unit_cost"], 26.1)
        self.assertEqual(products[0]["base_demand"], 250.0)
        self.assertEqual(products[0]["elasticity"], 1.2)
        self.assertEqual(products[0]["competitor_price"], 79.4)
        self.assertEqual(products[0]["min_price"], 58.2)
        self.assertEqual(products[0]["max_price"], 92.8)

    def test_bulk_validation_accepts_decimal_comma_strings(self):
        workbook_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-COMMA",
                    "Comma Decimal Product",
                    "Accessories",
                    " 72,5 ",
                    "26,1",
                    "250",
                    "1,2",
                    "79,4",
                    "58,2",
                    "92,8",
                ),
            )
        )

        validation_result = validate_bulk_analysis_workbook(io.BytesIO(workbook_content))
        products = parse_bulk_analysis_products(workbook_content)

        self.assertEqual(validation_result.errors, [])
        self.assertEqual(validation_result.valid_row_count, 1)
        self.assertEqual(products[0]["current_price"], 72.5)
        self.assertEqual(products[0]["unit_cost"], 26.1)
        self.assertEqual(products[0]["base_demand"], 250.0)
        self.assertEqual(products[0]["elasticity"], 1.2)
        self.assertEqual(products[0]["competitor_price"], 79.4)
        self.assertEqual(products[0]["min_price"], 58.2)
        self.assertEqual(products[0]["max_price"], 92.8)

    def test_bulk_upload_accepts_free_form_categories(self):
        workbook_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-BAG",
                    "City Tote Bag",
                    "bags",
                    72,
                    26,
                    250,
                    1.2,
                    79,
                    "",
                    "",
                ),
                (
                    "SKU-RING",
                    "Stacking Ring",
                    "rings",
                    50,
                    20,
                    100,
                    1.1,
                    55,
                    "",
                    "",
                ),
            )
        )

        with self.client as client:
            self._sign_up(client)
            response = client.post(
                "/bulk-analysis?lang=en",
                data={"product_file": (io.BytesIO(workbook_content), "products.xlsx")},
                content_type="multipart/form-data",
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("2 of 2 products were analyzed successfully. 0 products failed.", body)
        self.assertIn("SKU-BAG", body)
        self.assertIn("SKU-RING", body)
        self.assertNotIn("Category must be one of", body)

    def test_bulk_upload_reports_missing_required_columns_together(self):
        invalid_content = _build_xlsx_workbook(
            (
                ("product_id", "product_name", "category", "unit_cost", "base_demand", "competitor_price"),
                ("SKU-002", "Invalid Product", "Accessories", 12, 100, 15),
            )
        )

        with self.client as client:
            self._sign_up(client)
            response = client.post(
                "/bulk-analysis?lang=en",
                data={"product_file": (io.BytesIO(invalid_content), "products.xlsx")},
                content_type="multipart/form-data",
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required columns: current_price, elasticity.", body)

    def test_bulk_upload_reports_missing_required_numeric_values(self):
        invalid_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-004",
                    "Missing Required Numbers",
                    "Accessories",
                    "",
                    12,
                    "",
                    "",
                    15,
                    "",
                    "",
                ),
            )
        )

        with self.client as client:
            self._sign_up(client)
            response = client.post(
                "/bulk-analysis?lang=en",
                data={"product_file": (io.BytesIO(invalid_content), "products.xlsx")},
                content_type="multipart/form-data",
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Row 2: current_price is required.", body)
        self.assertIn("Row 2: base_demand is required.", body)
        self.assertIn("Row 2: elasticity is required.", body)

    def test_bulk_upload_reports_row_level_validation_errors(self):
        invalid_content = _build_xlsx_workbook(
            (
                BULK_TEMPLATE_COLUMNS,
                (
                    "SKU-002",
                    "Invalid Product",
                    "Accessories",
                    0,
                    "not-a-number",
                    15,
                    0,
                    "bad-price",
                    100,
                    90,
                ),
                (
                    "SKU-003",
                    "Invalid Optional Prices",
                    "Accessories",
                    25,
                    10,
                    80,
                    1.1,
                    27,
                    -1,
                    0,
                ),
            )
        )

        with self.client as client:
            self._sign_up(client)
            response = client.post(
                "/bulk-analysis?lang=en",
                data={"product_file": (io.BytesIO(invalid_content), "products.xlsx")},
                content_type="multipart/form-data",
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Row 2: current_price must be greater than 0.", body)
        self.assertIn("Row 2: unit_cost must be a valid number.", body)
        self.assertIn("Row 2: elasticity must be greater than 0.", body)
        self.assertIn("Row 2: competitor_price must be a valid number.", body)
        self.assertIn("Row 2: min_price must be less than max_price.", body)
        self.assertIn("Row 3: min_price must be greater than 0.", body)
        self.assertIn("Row 3: max_price must be greater than 0.", body)

    def test_portfolio_page_renders_user_focused_summary_and_print_action(self):
        with self.client as client:
            self._sign_up(client)
            client.post("/api/analyze", json=self.payload)
            response = client.get("/portfolio?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Portfolio Summary Metrics", body)
        self.assertIn("Saved analyses", body)
        self.assertIn("Total expected profit", body)
        self.assertIn("Average profit improvement", body)
        self.assertIn("Best-performing product", body)
        self.assertIn("Print analyses", body)
        self.assertNotIn('href="/portfolio/export.csv"', body)
        self.assertNotIn('href="/history/export.csv"', body)
        self.assertNotIn('href="/history/export.json"', body)

    def test_api_validation_errors_are_consistent(self):
        invalid_payload = dict(self.payload)
        invalid_payload["current_price"] = 0

        with self.client as client:
            self._sign_up(client)
            response = client.post("/api/analyze", json=invalid_payload)
            data = response.get_json()

        self.assertFalse(data["success"])
        self.assertIsNone(data["data"])
        self.assertIsInstance(data["error"], str)

    def test_sign_up_creates_hashed_user_and_logs_in(self):
        with self.client as client:
            response = self._sign_up(client)
            users = load_users(self.users_file)

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/?lang=en"))
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]["email"], "demo@example.com")
            self.assertNotEqual(users[0]["password_hash"], "password123")

            with client.session_transaction() as session:
                self.assertEqual(session["user_id"], users[0]["id"])

    def test_sign_in_authenticates_existing_user(self):
        with self.client as client:
            self._sign_up(client)
            client.post("/sign-out?lang=en")

            response = self._sign_in(client)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith("/?lang=en"))

    def test_sign_in_rejects_invalid_credentials(self):
        with self.client as client:
            self._sign_up(client)
            client.post("/sign-out?lang=en")
            response = self._sign_in(client, password="wrong-password")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 401)
        self.assertIn("Incorrect email or password.", body)
        self.assertIn('value="demo@example.com"', body)

    def test_sign_out_clears_session(self):
        with self.client as client:
            self._sign_up(client)
            response = client.post("/sign-out?lang=en", follow_redirects=True)
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("You have been signed out.", body)
            with client.session_transaction() as session:
                self.assertNotIn("user_id", session)

    def test_navbar_changes_after_authentication(self):
        public_body = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn('href="/sign-up?lang=en"', public_body)
        self.assertIn('href="/sign-in?next=/analyze?lang%3Den&amp;lang=en"', public_body)
        self.assertIn("Start Analysis", public_body)
        self.assertNotIn('href="#home-capabilities"', public_body)
        self.assertNotIn('href="/?lang=en">Home</a>', public_body)
        self.assertNotIn('href="/sign-in?lang=en"', public_body)
        self.assertNotIn('action="/sign-out?lang=en"', public_body)

        with self.client as client:
            self._sign_up(client)
            private_body = client.get("/?lang=en").get_data(as_text=True)

        self.assertIn('href="/analyze?lang=en"', private_body)
        self.assertIn('href="/portfolio?lang=en"', private_body)
        self.assertIn('href="/dashboard?lang=en"', private_body)
        self.assertIn('href="/finance?lang=en"', private_body)
        self.assertIn('href="/about?lang=en"', private_body)
        self.assertIn('action="/sign-out?lang=en"', private_body)
        self.assertNotIn('href="/sign-in?lang=en"', private_body)
        self.assertNotIn('href="/sign-up?lang=en"', private_body)

    def test_shared_footer_renders_on_public_and_authenticated_pages(self):
        public_home = self.client.get("/?lang=en").get_data(as_text=True)
        public_sign_in = self.client.get("/sign-in?lang=en").get_data(as_text=True)
        public_home_footer = public_home.split('<footer class="app-footer">', 1)[1].split("</footer>", 1)[0]
        public_sign_in_footer = public_sign_in.split('<footer class="app-footer">', 1)[1].split("</footer>", 1)[0]

        self.assertIn("© 2026 PricePilot. All rights reserved.", public_home)
        self.assertNotIn('class="footer-copy"', public_home_footer)
        self.assertNotIn("btn btn-outline-secondary btn-sm", public_home_footer)
        self.assertIn("© 2026 PricePilot. All rights reserved.", public_sign_in)
        self.assertNotIn('class="footer-copy"', public_sign_in_footer)
        self.assertNotIn("btn btn-outline-secondary btn-sm", public_sign_in_footer)

        with self.client as client:
            self._sign_up(client)
            private_dashboard = client.get("/dashboard?lang=en").get_data(as_text=True)
            private_dashboard_footer = private_dashboard.split('<footer class="app-footer">', 1)[1].split("</footer>", 1)[0]

        self.assertIn("© 2026 PricePilot. All rights reserved.", private_dashboard)
        self.assertNotIn('class="footer-copy"', private_dashboard_footer)
        self.assertNotIn("btn btn-outline-secondary btn-sm", private_dashboard_footer)

    def test_about_page_uses_simplified_three_section_structure(self):
        with self.client as client:
            self._sign_up(client)
            response = client.get("/about?lang=en")
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>About the system</h1>", body)
        self.assertIn("<h2>Core capabilities</h2>", body)
        self.assertIn("<h2>Why it is useful</h2>", body)
        self.assertNotIn("about-hero-card", body)
        self.assertNotIn("about-help-card", body)
        self.assertNotIn("about-closing-card", body)


if __name__ == "__main__":
    unittest.main()
