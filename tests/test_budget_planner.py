import unittest

from budget_planner import generate_smart_budget_plan


def allocation_map(result):
    return {row["field_name"]: row["amount"] for row in result["allocation_rows"]}


def allocation_row_map(result):
    return {row["field_name"]: row for row in result["allocation_rows"]}


class SmartBudgetPlannerTests(unittest.TestCase):
    def test_generate_plan_returns_expected_structure_and_method_note(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 10000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Օնլայն խանութ",
                "business_status": "Նոր բիզնես",
                "business_goal": "Հավասարակշռված զարգացում",
            }
        )

        self.assertEqual(
            set(result.keys()),
            {
                "values",
                "summary",
                "allocation_rows",
                "scenario_rows",
                "warnings",
                "recommendations",
                "method_notes",
            },
        )
        self.assertIn("Hybrid budget formation and allocation method", result["method_notes"])
        self.assertEqual(len(result["scenario_rows"]), 3)
        self.assertEqual(
            [row["field_name"] for row in result["allocation_rows"]],
            [
                "tax_reserve",
                "payroll_admin_reserve",
                "fixed_costs_coverage",
                "variable_costs_coverage",
                "marketing_budget",
                "inventory_or_purchase_budget",
                "operational_budget",
                "emergency_reserve",
                "reinvestment_budget",
                "free_cash",
            ],
        )
        self.assertEqual(result["summary"]["planner_name"], "Smart Budget Planner")
        self.assertEqual(result["summary"]["planner_name_hy"], "Խելացի բյուջեի պլանավորում")
        self.assertIn("stability_score", result["summary"])
        self.assertIn("recommended_scenario_reason", result["summary"])

    def test_new_business_can_work_without_average_monthly_revenue(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 7500,
                "organization_type": "ԱՁ",
                "business_activity": "Ձեռագործ արտադրանք",
                "business_status": "Նոր բիզնես",
                "business_goal": "Կայունություն",
            }
        )

        self.assertEqual(result["summary"]["revenue_source"], "estimated_from_capital_profile")
        self.assertGreater(result["summary"]["estimated_average_monthly_revenue"], 0)

    def test_existing_business_uses_average_monthly_revenue_when_provided(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 12000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Ծառայություններ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Կայունություն",
                "average_monthly_revenue": 18000,
                "fixed_costs": 3200,
                "variable_costs": 4200,
                "employees_count": 6,
            }
        )

        self.assertEqual(result["summary"]["revenue_source"], "provided_average_monthly_revenue")
        self.assertEqual(result["summary"]["estimated_average_monthly_revenue"], 18000.0)
        stable_row = next(
            row for row in result["scenario_rows"] if row["scenario_name"] == "Կայուն զարգացման սցենար"
        )
        self.assertGreater(stable_row["expected_revenue"], 0)
        self.assertIn(stable_row["risk_level"], {"Ցածր", "Միջին", "Բարձր"})

    def test_growth_goal_pushes_marketing_inventory_and_reinvestment_higher_than_survival(self):
        shared_payload = {
            "available_capital": 15000,
            "organization_type": "ՍՊԸ",
            "business_activity": "Օնլայն խանութ",
            "business_status": "Գործող բիզնես",
            "average_monthly_revenue": 17000,
            "fixed_costs": 2200,
            "variable_costs": 5100,
            "employees_count": 4,
        }
        growth = generate_smart_budget_plan({**shared_payload, "business_goal": "Աճ"})
        survival = generate_smart_budget_plan({**shared_payload, "business_goal": "Գոյատևում"})

        growth_allocations = allocation_map(growth)
        survival_allocations = allocation_map(survival)

        self.assertGreater(growth_allocations["marketing_budget"], survival_allocations["marketing_budget"])
        self.assertGreater(
            growth_allocations["inventory_or_purchase_budget"],
            survival_allocations["inventory_or_purchase_budget"],
        )
        self.assertGreater(
            growth_allocations["reinvestment_budget"],
            survival_allocations["reinvestment_budget"],
        )
        self.assertTrue(
            any("մարքեթինգային բյուջեն" in recommendation for recommendation in growth["recommendations"])
        )

    def test_survival_goal_prioritizes_tax_fixed_costs_and_emergency_reserve(self):
        shared_payload = {
            "available_capital": 15000,
            "organization_type": "ՍՊԸ",
            "business_activity": "Օնլայն խանութ",
            "business_status": "Գործող բիզնես",
            "average_monthly_revenue": 17000,
            "fixed_costs": 2200,
            "variable_costs": 5100,
            "employees_count": 4,
        }
        growth = generate_smart_budget_plan({**shared_payload, "business_goal": "Աճ"})
        survival = generate_smart_budget_plan({**shared_payload, "business_goal": "Գոյատևում"})

        growth_allocations = allocation_map(growth)
        survival_allocations = allocation_map(survival)
        survival_rows = allocation_row_map(survival)

        self.assertGreater(survival_allocations["emergency_reserve"], growth_allocations["emergency_reserve"])
        for field_name in ("tax_reserve", "fixed_costs_coverage", "emergency_reserve"):
            self.assertEqual(survival_rows[field_name]["priority_type"], "normative")
            self.assertEqual(survival_rows[field_name]["importance_label"], "Պարտադիր և առաջնային")
            self.assertGreater(survival_allocations[field_name], survival_allocations["marketing_budget"])
            self.assertGreater(survival_allocations[field_name], survival_allocations["reinvestment_budget"])
        self.assertIn("Հարկային պարտավորությունների ապահովում", survival_rows["tax_reserve"]["purpose_description"])
        self.assertIn("Ֆինանսական ռիսկերի նվազեցում", survival_rows["emergency_reserve"]["purpose_description"])

    def test_organization_type_changes_planning_coefficients(self):
        shared_payload = {
            "available_capital": 10000,
            "business_activity": "Ծառայություններ",
            "business_status": "Գործող բիզնես",
            "business_goal": "Կայունություն",
            "average_monthly_revenue": 14000,
            "fixed_costs": 1800,
            "variable_costs": 3200,
            "employees_count": 3,
        }
        sole_proprietor = generate_smart_budget_plan({**shared_payload, "organization_type": "ԱՁ"})
        open_joint_stock = generate_smart_budget_plan({**shared_payload, "organization_type": "ԲԲԸ"})

        sole_proprietor_allocations = allocation_map(sole_proprietor)
        open_joint_stock_allocations = allocation_map(open_joint_stock)

        self.assertGreater(
            open_joint_stock_allocations["tax_reserve"],
            sole_proprietor_allocations["tax_reserve"],
        )
        self.assertGreater(
            open_joint_stock_allocations["payroll_admin_reserve"],
            sole_proprietor_allocations["payroll_admin_reserve"],
        )
        self.assertGreater(
            open_joint_stock_allocations["fixed_costs_coverage"],
            sole_proprietor_allocations["fixed_costs_coverage"],
        )
        self.assertGreater(
            open_joint_stock["summary"]["stability_score"],
            0,
        )

    def test_insufficient_capital_emits_negative_free_cash_warning(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 1000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Ծառայություններ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Աճ",
                "fixed_costs": 1600,
                "variable_costs": 600,
                "employees_count": 3,
            }
        )

        warnings_by_code = {warning["code"]: warning["message"] for warning in result["warnings"]}
        self.assertLess(result["summary"]["free_cash"], 0)
        self.assertIn("negative_free_cash", warnings_by_code)
        self.assertIn("ազատ դրամական մնացորդը բացասական է", warnings_by_code["negative_free_cash"])
        self.assertEqual(result["summary"]["stability_label"], "Ռիսկային")

    def test_low_capital_and_high_fixed_costs_trigger_risk_warnings(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 1000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Ծառայություններ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Աճ",
                "fixed_costs": 1600,
                "variable_costs": 600,
                "employees_count": 3,
            }
        )

        warning_codes = {warning["code"] for warning in result["warnings"]}
        self.assertLess(result["summary"]["free_cash"], 0)
        self.assertIn("capital_below_fixed_costs", warning_codes)
        self.assertIn("negative_free_cash", warning_codes)
        self.assertIn("fixed_cost_pressure", warning_codes)
        self.assertIn("growth_goal_high_risk", warning_codes)
        self.assertEqual(result["summary"]["overall_risk_level"], "Բարձր")

    def test_service_activity_changes_allocation_and_recommendation_focus(self):
        online_shop = generate_smart_budget_plan(
            {
                "available_capital": 12000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Օնլայն խանութ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Հավասարակշռված զարգացում",
                "average_monthly_revenue": 16000,
                "fixed_costs": 1800,
                "variable_costs": 3600,
                "employees_count": 3,
            }
        )
        services = generate_smart_budget_plan(
            {
                "available_capital": 12000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Ծառայություններ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Հավասարակշռված զարգացում",
                "average_monthly_revenue": 16000,
                "fixed_costs": 1800,
                "variable_costs": 3600,
                "employees_count": 3,
            }
        )

        online_allocations = allocation_map(online_shop)
        service_allocations = allocation_map(services)

        self.assertGreater(online_allocations["marketing_budget"], service_allocations["marketing_budget"])
        self.assertGreater(
            online_allocations["inventory_or_purchase_budget"],
            service_allocations["inventory_or_purchase_budget"],
        )
        self.assertGreater(
            service_allocations["payroll_admin_reserve"],
            online_allocations["payroll_admin_reserve"],
        )
        self.assertGreater(
            service_allocations["operational_budget"],
            online_allocations["operational_budget"],
        )
        self.assertTrue(
            any("Ծառայությունների ոլորտի համար համակարգը մեծացնում է աշխատավարձային" in item for item in services["recommendations"])
        )

    def test_recommended_scenario_includes_reason_based_on_risk_and_profitability(self):
        result = generate_smart_budget_plan(
            {
                "available_capital": 12000,
                "organization_type": "ՍՊԸ",
                "business_activity": "Ծառայություններ",
                "business_status": "Գործող բիզնես",
                "business_goal": "Կայունություն",
                "average_monthly_revenue": 18000,
                "fixed_costs": 3200,
                "variable_costs": 4200,
                "employees_count": 6,
            }
        )

        recommended_row = next(row for row in result["scenario_rows"] if row["is_recommended"])
        self.assertTrue(recommended_row["selection_reason"])
        self.assertEqual(result["summary"]["recommended_scenario_reason"], recommended_row["selection_reason"])

    def test_invalid_inputs_raise_validation_errors(self):
        with self.assertRaisesRegex(ValueError, "Հասանելի կապիտալ"):
            generate_smart_budget_plan(
                {
                    "available_capital": 0,
                    "organization_type": "ՍՊԸ",
                    "business_activity": "Օնլայն խանութ",
                    "business_status": "Նոր բիզնես",
                    "business_goal": "Աճ",
                }
            )

        with self.assertRaisesRegex(ValueError, "Փոփոխական ծախսեր"):
            generate_smart_budget_plan(
                {
                    "available_capital": 5000,
                    "organization_type": "ՍՊԸ",
                    "business_activity": "Օնլայն խանութ",
                    "business_status": "Նոր բիզնես",
                    "business_goal": "Աճ",
                    "variable_costs": -10,
                }
            )

        with self.assertRaisesRegex(ValueError, "Աշխատակիցների քանակ"):
            generate_smart_budget_plan(
                {
                    "available_capital": 5000,
                    "organization_type": "ՍՊԸ",
                    "business_activity": "Օնլայն խանութ",
                    "business_status": "Նոր բիզնես",
                    "business_goal": "Աճ",
                    "employees_count": 2.5,
                }
            )


if __name__ == "__main__":
    unittest.main()
