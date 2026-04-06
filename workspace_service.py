from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pricing_engine import ProductData, run_full_analysis

PRODUCT_FIELDS = tuple(ProductData.__dataclass_fields__.keys())


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def product_record_to_data(record):
    return ProductData(**{field: record[field] for field in PRODUCT_FIELDS})


def build_history_entry(result, timestamp=None):
    best = result["best_strategy"]
    product = result["product"]
    return {
        "id": uuid4().hex,
        "product_name": product["name"],
        "selected_scenario": product["scenario"],
        "recommended_strategy": best["strategy"],
        "recommended_price": best["price"],
        "expected_profit": best["profit"],
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
                "base_price": record["base_price"],
                "recommended_price": best["price"],
                "expected_demand": best["demand"],
                "expected_revenue": best["revenue"],
                "expected_profit": best["profit"],
                "margin": best["profit_margin"],
                "risk_level": best["risk_level"],
                "recommended_strategy": best["strategy"],
            }
        )
    return rows


def summarize_portfolio(rows, history_entries):
    total_products = len(rows)
    total_revenue = round(sum(row["expected_revenue"] for row in rows), 2)
    total_profit = round(sum(row["expected_profit"] for row in rows), 2)
    low_risk_products = sum(1 for row in rows if row["risk_level"] == "Low")

    return {
        "total_products": total_products,
        "projected_revenue": total_revenue,
        "projected_profit": total_profit,
        "low_risk_products": low_risk_products,
        "history_entries": len(history_entries),
    }
