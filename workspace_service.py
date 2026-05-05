from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from pricing_engine import ProductData
from product_analysis_service import analyze_product

PRODUCT_FIELDS = tuple(ProductData.__dataclass_fields__.keys())


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def _stored_timestamp(record):
    return record.get("created_at") or record.get("updated_at") or record.get("timestamp", "")


def _stored_input_snapshot(result, input_data=None):
    product = result["product"]
    source = dict(input_data or {})
    snapshot = {
        "name": product["name"],
        "category": product["category"],
        "unit_cost": product["unit_cost"],
        "current_price": product["current_price"],
        "units_sold_30d": product["units_sold_30d"],
        "competitor_price": product.get("competitor_price"),
        "scenario": product["scenario"],
        "elasticity_override": product.get("elasticity_override"),
        "return_rate_override": product.get("return_rate_override"),
        "fixed_cost_allocation_override": product.get("fixed_cost_allocation_override"),
        "target_margin_override": product.get("target_margin_override"),
        "marketing_factor_override": product.get("marketing_factor_override"),
        "inventory_constraint_override": product.get("inventory_constraint_override"),
    }

    for key in ("product_id", "row_number", "min_price", "max_price"):
        if key in source:
            snapshot[key] = source[key]

    return snapshot


def _coerce_optional_number(value, percent=False, integer=False):
    if value in (None, ""):
        return None
    parsed = float(value)
    if percent and parsed > 1:
        parsed /= 100.0
    return int(parsed) if integer else float(parsed)


def product_record_to_data(record):
    target_margin = record.get("target_margin_override", record.get("desired_margin"))
    return ProductData(
        name=str(record.get("name", "")).strip(),
        category=str(record.get("category", "")).strip(),
        unit_cost=float(record.get("unit_cost", 0.0)),
        current_price=float(record.get("current_price", record.get("base_price", 0.0))),
        units_sold_30d=float(record.get("units_sold_30d", record.get("base_demand", 0.0))),
        competitor_price=_coerce_optional_number(record.get("competitor_price")),
        scenario=str(record.get("scenario", "NORMAL")).upper(),
        elasticity_override=_coerce_optional_number(record.get("elasticity_override", record.get("elasticity"))),
        return_rate_override=_coerce_optional_number(
            record.get("return_rate_override", record.get("return_rate")),
            percent=True,
        ),
        fixed_cost_allocation_override=_coerce_optional_number(
            record.get("fixed_cost_allocation_override", record.get("fixed_cost"))
        ),
        target_margin_override=_coerce_optional_number(target_margin, percent=True),
        marketing_factor_override=_coerce_optional_number(record.get("marketing_factor_override")),
        inventory_constraint_override=_coerce_optional_number(
            record.get("inventory_constraint_override", record.get("inventory")),
            integer=True,
        ),
    )


def build_history_entry(result, input_data=None, analysis_type="single", timestamp=None):
    best = result["best_strategy"]
    product = result["product"]
    current_option = result.get("current_option")
    created_at = timestamp or _timestamp()
    input_snapshot = _stored_input_snapshot(result, input_data=input_data)
    profit_change = None
    if current_option:
        profit_change = round(float(best["profit"]) - float(current_option["profit"]), 2)

    return {
        "id": uuid4().hex,
        "product_name": product["name"],
        "category": product["category"],
        "selected_scenario": product["scenario"],
        "analysis_type": analysis_type,
        "recommended_strategy": best["strategy"],
        "current_price": product["current_price"],
        "recommended_price": best["price"],
        "optimal_price": best["price"],
        "projected_demand": best["demand"],
        "expected_demand": best["demand"],
        "expected_revenue": best["revenue"],
        "expected_total_cost": best["total_cost"],
        "expected_profit": best["profit"],
        "profit_change": profit_change,
        "margin": best["profit_margin"],
        "profit_margin": best["profit_margin"],
        "confidence_level": result["overall_confidence"]["level"],
        "confidence_score": result["overall_confidence"]["score"],
        "risk_level": best["risk_level"],
        "risk_score": best["risk_score"],
        "match_level": result.get("matched_context", {}).get("match_level", "none"),
        "created_at": created_at,
        "timestamp": created_at,
        "input_data": input_snapshot,
        "result_data": deepcopy(result),
    }


def build_portfolio_comparison(records):
    rows = []
    for record in records:
        input_snapshot = record.get("input_data")
        if isinstance(input_snapshot, dict) and input_snapshot.get("name"):
            product = product_record_to_data(input_snapshot)
            stored_result = record.get("result_data")
            if isinstance(stored_result, dict) and stored_result.get("best_strategy") and stored_result.get("product"):
                analysis = stored_result
            else:
                analysis = analyze_product(product)
            record_id = record.get("id")
            product_name = record.get("product_name", product.name)
            category = record.get("category", product.category)
            scenario = record.get("selected_scenario", product.scenario)
            updated_at = _stored_timestamp(record)
        elif "name" in record and "category" in record:
            product = product_record_to_data(record)
            analysis = analyze_product(product)
            record_id = record.get("id")
            product_name = record["name"]
            category = record["category"]
            scenario = record["scenario"]
            updated_at = _stored_timestamp(record)
        else:
            continue

        best = analysis["best_strategy"]
        current_option = analysis.get("current_option")
        projected_quantity = float(best.get("demand", 0.0) or 0.0)
        current_profit = None
        profit_improvement_percent = None

        if isinstance(current_option, dict) and current_option.get("profit") is not None:
            current_profit = round(float(current_option["profit"]), 2)
            if current_profit != 0:
                profit_improvement_percent = round(
                    ((float(best.get("profit", 0.0)) - current_profit) / abs(current_profit)) * 100,
                    2,
                )

        # Keep a simple portfolio finance layer alongside the full pricing model.
        # This is used for portfolio-wide revenue, cost, profit, and contribution rollups.
        portfolio_revenue = round(float(best.get("price", 0.0)) * projected_quantity, 2)
        portfolio_cost = round(float(product.unit_cost) * projected_quantity, 2)
        product_profit = round(portfolio_revenue - portfolio_cost, 2)
        portfolio_margin = round((product_profit / portfolio_revenue) * 100, 2) if portfolio_revenue > 0 else 0.0

        rows.append(
            {
                "product_id": record_id,
                "product_name": product_name,
                "category": category,
                "scenario": scenario,
                "updated_at": updated_at,
                "unit_cost": product.unit_cost,
                "current_price": product.current_price,
                "recommended_price": best["price"],
                "projected_demand": best["demand"],
                "expected_revenue": best["revenue"],
                "expected_total_cost": best["total_cost"],
                "expected_profit": best["profit"],
                "current_profit": current_profit,
                "profit_improvement_percent": profit_improvement_percent,
                "margin": best["profit_margin"],
                "portfolio_revenue": portfolio_revenue,
                "portfolio_cost": portfolio_cost,
                "product_profit": product_profit,
                "portfolio_margin": portfolio_margin,
                "profit_contribution_share": 0.0,
                "confidence_level": record.get("confidence_level", analysis["overall_confidence"]["level"]),
                "confidence_score": record.get("confidence_score", analysis["overall_confidence"]["score"]),
                "risk_level": best["risk_level"],
                "risk_score": best["risk_score"],
                "recommended_strategy": record.get("recommended_strategy", best["strategy"]),
                "match_level": record.get(
                    "match_level",
                    analysis.get("matched_context", {}).get("match_level", "none"),
                ),
            }
        )
    return rows


def summarize_portfolio(rows, history_entries):
    total_products = len(rows)
    # Portfolio finance totals intentionally use the simple management view:
    # price x quantity for revenue and unit cost x quantity for cost.
    total_revenue = round(sum(row.get("portfolio_revenue", 0.0) for row in rows), 2)
    total_cost = round(sum(row.get("portfolio_cost", 0.0) for row in rows), 2)
    total_profit = round(total_revenue - total_cost, 2)
    total_expected_profit = round(sum(row.get("expected_profit", 0.0) for row in rows), 2)
    average_margin = round((total_profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0
    high_confidence_products = sum(1 for row in rows if row["confidence_level"] == "High")
    profit_improvement_values = [
        row["profit_improvement_percent"]
        for row in rows
        if row.get("profit_improvement_percent") is not None
    ]
    average_profit_improvement_percent = (
        round(sum(profit_improvement_values) / len(profit_improvement_values), 2)
        if profit_improvement_values
        else 0.0
    )

    # Contribution share stays safe when the portfolio profit pool is zero.
    for row in rows:
        row_profit = round(row.get("product_profit", 0.0), 2)
        row["product_profit"] = row_profit
        row["profit_contribution_share"] = round((row_profit / total_profit) * 100, 2) if total_profit else 0.0

    best_performing_product = (
        max(rows, key=lambda row: (row["product_profit"], row["profit_contribution_share"], row["confidence_score"]))
        if rows
        else None
    )
    weakest_performing_product = (
        min(rows, key=lambda row: (row["product_profit"], row["profit_contribution_share"], row["confidence_score"]))
        if rows
        else None
    )
    highest_profit_product = (
        max(rows, key=lambda row: (row["product_profit"], row["profit_contribution_share"], row["confidence_score"]))
        if rows
        else None
    )
    top_expected_profit_product = (
        max(rows, key=lambda row: (row["expected_profit"], row["confidence_score"], row["margin"]))
        if rows
        else None
    )

    return {
        "total_products": total_products,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_expected_profit": total_expected_profit,
        "projected_revenue": total_revenue,
        "projected_total_cost": total_cost,
        "projected_profit": total_profit,
        "average_margin": average_margin,
        "average_profit_improvement_percent": average_profit_improvement_percent,
        "high_confidence_products": high_confidence_products,
        "best_performing_product": best_performing_product,
        "weakest_performing_product": weakest_performing_product,
        "highest_profit_product": highest_profit_product,
        "top_expected_profit_product": top_expected_profit_product,
        "best_product": best_performing_product,
        "worst_product": weakest_performing_product,
        "history_entries": len(history_entries),
    }


def build_dashboard_snapshot(rows, focus_analysis, focus_scenarios):
    if rows:
        total_revenue = round(sum(row["expected_revenue"] for row in rows), 2)
        total_cost = round(sum(row.get("expected_total_cost", 0.0) for row in rows), 2)
        total_profit = round(sum(row["expected_profit"] for row in rows), 2)
        average_margin = round((total_profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0
        strongest_profit_product = max(rows, key=lambda row: (row["expected_profit"], row["margin"], row["confidence_score"]))
        top_margin_product = max(rows, key=lambda row: (row["margin"], row["expected_profit"], row["confidence_score"]))
        strongest_confidence_product = max(rows, key=lambda row: (row["confidence_score"], row["expected_profit"], row["margin"]))
        scope = "portfolio"
        item_count = len(rows)
    else:
        best = focus_analysis["best_strategy"]
        fallback_row = {
            "product_name": focus_analysis["product"]["name"],
            "scenario": focus_analysis["product"]["scenario"],
            "recommended_strategy": best["strategy"],
            "recommended_price": best["price"],
            "expected_revenue": best["revenue"],
            "expected_total_cost": best["total_cost"],
            "expected_profit": best["profit"],
            "projected_demand": best["demand"],
            "margin": best["profit_margin"],
            "confidence_level": focus_analysis["overall_confidence"]["level"],
            "confidence_score": focus_analysis["overall_confidence"]["score"],
            "risk_level": best["risk_level"],
            "risk_score": best["risk_score"],
        }
        total_revenue = best["revenue"]
        total_cost = best["total_cost"]
        total_profit = best["profit"]
        average_margin = best["profit_margin"]
        strongest_profit_product = fallback_row
        top_margin_product = fallback_row
        strongest_confidence_product = fallback_row
        scope = "reference"
        item_count = 1

    scenarios = focus_scenarios["scenarios"]
    strongest_profit_scenario = max(scenarios, key=lambda item: (item["profit"], item["revenue"], item["confidence_score"]))
    highest_risk_scenario = max(scenarios, key=lambda item: (item["risk_score"], item["profit"]))
    best_confidence_scenario = max(scenarios, key=lambda item: (item["confidence_score"], item["profit"]))

    return {
        "scope": scope,
        "item_count": item_count,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "average_margin": average_margin,
        "strongest_profit_product": strongest_profit_product,
        "top_margin_product": top_margin_product,
        "strongest_confidence_product": strongest_confidence_product,
        "strongest_profit_scenario": strongest_profit_scenario,
        "highest_risk_scenario": highest_risk_scenario,
        "best_confidence_scenario": best_confidence_scenario,
        "winning_scenario": focus_scenarios["winning_scenario"],
    }
