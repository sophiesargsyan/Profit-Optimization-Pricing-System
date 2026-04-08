from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pricing_engine import ProductData, run_full_analysis

PRODUCT_FIELDS = tuple(ProductData.__dataclass_fields__.keys())


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


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


def build_history_entry(result, timestamp=None):
    best = result["best_strategy"]
    product = result["product"]
    return {
        "id": uuid4().hex,
        "product_name": product["name"],
        "selected_scenario": product["scenario"],
        "recommended_strategy": best["strategy"],
        "recommended_price": best["price"],
        "projected_demand": best["demand"],
        "expected_profit": best["profit"],
        "confidence_level": result["overall_confidence"]["level"],
        "risk_level": best["risk_level"],
        "timestamp": timestamp or _timestamp(),
    }


def build_portfolio_comparison(records):
    rows = []
    for record in records:
        analysis = run_full_analysis(product_record_to_data(record))
        best = analysis["best_strategy"]
        rows.append(
            {
                "product_id": record["id"],
                "product_name": record["name"],
                "category": record["category"],
                "scenario": record["scenario"],
                "current_price": product_record_to_data(record).current_price,
                "recommended_price": best["price"],
                "projected_demand": best["demand"],
                "expected_revenue": best["revenue"],
                "expected_profit": best["profit"],
                "margin": best["profit_margin"],
                "confidence_level": analysis["overall_confidence"]["level"],
                "confidence_score": analysis["overall_confidence"]["score"],
                "risk_level": best["risk_level"],
                "risk_score": best["risk_score"],
                "recommended_strategy": best["strategy"],
            }
        )
    return rows


def summarize_portfolio(rows, history_entries):
    total_products = len(rows)
    total_revenue = round(sum(row["expected_revenue"] for row in rows), 2)
    total_profit = round(sum(row["expected_profit"] for row in rows), 2)
    high_confidence_products = sum(1 for row in rows if row["confidence_level"] == "High")

    return {
        "total_products": total_products,
        "projected_revenue": total_revenue,
        "projected_profit": total_profit,
        "high_confidence_products": high_confidence_products,
        "history_entries": len(history_entries),
    }
