from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import timedelta
from statistics import mean, median, pstdev

from catalog_profiles import CATEGORY_PROFILES
from data_repository import load_business_dataset


@dataclass
class ProductData:
    name: str
    category: str
    unit_cost: float
    current_price: float
    units_sold_30d: float
    competitor_price: float | None
    scenario: str = "NORMAL"
    elasticity_override: float | None = None
    return_rate_override: float | None = None
    fixed_cost_allocation_override: float | None = None
    target_margin_override: float | None = None
    marketing_factor_override: float | None = None
    inventory_constraint_override: int | None = None


SCENARIOS = {
    "LOW": {
        "label": "Soft demand",
        "demand_multiplier": 0.92,
        "competitor_multiplier": 1.02,
    },
    "NORMAL": {
        "label": "Stable demand",
        "demand_multiplier": 1.0,
        "competitor_multiplier": 1.0,
    },
    "HIGH": {
        "label": "Strong demand",
        "demand_multiplier": 1.08,
        "competitor_multiplier": 0.98,
    },
    "PROMO": {
        "label": "Campaign push",
        "demand_multiplier": 1.14,
        "competitor_multiplier": 0.97,
    },
}

DISPLAY_STRATEGIES = (
    "Current Price",
    "Competitive Parity",
    "Volume Push",
    "Margin Guardrail",
    "Premium Lift",
    "Profit Optimal",
)


def _round(value, digits=2):
    return round(float(value), digits)


def _clamp(value, lower, upper):
    return max(lower, min(value, upper))


def _safe_div(numerator, denominator, default=0.0):
    if abs(denominator) < 1e-9:
        return default
    return numerator / denominator


def _scenario_product(product, scenario_name):
    return replace(product, scenario=scenario_name)


def _confidence_from_score(score):
    if score >= 0.78:
        return "High"
    if score >= 0.58:
        return "Medium"
    return "Low"


def _estimate_payload(value, source, detail, score, sample_size=0):
    return {
        "value": _round(value, 4),
        "source": source,
        "detail": detail,
        "sample_size": int(sample_size),
        "confidence_score": _round(score * 100, 1),
        "confidence_level": _confidence_from_score(score),
    }


def validate_product(product):
    errors = []

    if not product.name.strip():
        errors.append("Product name is required.")
    if product.category not in CATEGORY_PROFILES:
        errors.append(f"Category must be one of: {', '.join(CATEGORY_PROFILES)}.")
    if product.unit_cost < 0:
        errors.append("Unit cost cannot be negative.")
    if product.current_price <= 0:
        errors.append("Current price must be greater than zero.")
    if product.units_sold_30d <= 0:
        errors.append("Units sold in the last 30 days must be greater than zero.")
    if product.competitor_price is not None and product.competitor_price <= 0:
        errors.append("Competitor price must be greater than zero when provided.")
    if product.elasticity_override is not None and not (-4.5 <= product.elasticity_override <= -0.2):
        errors.append("Elasticity override must be between -4.5 and -0.2.")
    if product.return_rate_override is not None and not (0.0 <= product.return_rate_override <= 0.45):
        errors.append("Return rate override must be between 0 and 0.45.")
    if product.fixed_cost_allocation_override is not None and product.fixed_cost_allocation_override < 0:
        errors.append("Fixed cost allocation override cannot be negative.")
    if product.target_margin_override is not None and not (0.1 <= product.target_margin_override <= 0.8):
        errors.append("Target margin override must be between 0.1 and 0.8.")
    if product.marketing_factor_override is not None and not (0.7 <= product.marketing_factor_override <= 1.5):
        errors.append("Marketing factor override must be between 0.7 and 1.5.")
    if product.inventory_constraint_override is not None and product.inventory_constraint_override <= 0:
        errors.append("Inventory constraint override must be greater than zero.")
    if product.scenario not in SCENARIOS:
        errors.append(f"Scenario must be one of: {', '.join(SCENARIOS)}.")

    if errors:
        raise ValueError(" ".join(errors))

    return True


def extract_seasonality(sales_history):
    if len(sales_history) < 45:
        return None

    month_averages = {}
    for row in sales_history:
        month_averages.setdefault(row["sale_date"].month, []).append(row["units_sold"])

    overall_average = mean(
        value for values in month_averages.values() for value in values
    ) if month_averages else 0.0
    if overall_average <= 0:
        return None

    multipliers = {}
    for month in range(1, 13):
        values = month_averages.get(month)
        if not values:
            multipliers[month] = 1.0
            continue
        multipliers[month] = _round(_clamp(mean(values) / overall_average, 0.72, 1.35), 4)
    return multipliers


def _monthly_price_points(sales_history):
    buckets = {}
    for row in sales_history:
        key = (row["sale_date"].year, row["sale_date"].month)
        bucket = buckets.setdefault(key, {"units": 0, "revenue": 0.0, "days": 0, "price_total": 0.0})
        bucket["units"] += row["units_sold"]
        bucket["revenue"] += row["revenue"]
        bucket["days"] += 1
        bucket["price_total"] += row["sale_price"]

    points = []
    for key in sorted(buckets):
        bucket = buckets[key]
        avg_price = bucket["price_total"] / max(bucket["days"], 1)
        points.append(
            {
                "period": key,
                "avg_price": avg_price,
                "units": bucket["units"],
            }
        )
    return points


def _elasticity_from_points(points):
    elasticities = []
    for current, previous in zip(points[1:], points[:-1]):
        price_change = _safe_div(current["avg_price"] - previous["avg_price"], previous["avg_price"])
        demand_change = _safe_div(current["units"] - previous["units"], previous["units"])
        if abs(price_change) < 0.015 or previous["units"] <= 0:
            continue
        elasticity = demand_change / price_change
        if -4.5 <= elasticity <= -0.2:
            elasticities.append(elasticity)
    return elasticities


def estimate_product_elasticity(product_sales_history):
    points = _monthly_price_points(product_sales_history)
    elasticities = _elasticity_from_points(points)
    if len(elasticities) >= 3:
        return _round(_clamp(median(elasticities), -4.0, -0.3), 4)
    return None


def estimate_category_elasticity(category_sales_history):
    points = _monthly_price_points(category_sales_history)
    elasticities = _elasticity_from_points(points)
    if len(elasticities) >= 4:
        return _round(_clamp(median(elasticities), -3.2, -0.35), 4)
    return None


def _recent_rows(sales_history, latest_date, days):
    threshold = latest_date - timedelta(days=days - 1)
    return [row for row in sales_history if row["sale_date"] >= threshold]


def _de_seasonalized_monthly_demand(sales_history, latest_date, seasonality, days):
    rows = _recent_rows(sales_history, latest_date, days)
    if not rows:
        return None

    normalized_units = 0.0
    for row in rows:
        month_factor = max(seasonality.get(row["sale_date"].month, 1.0), 0.6)
        normalized_units += row["units_sold"] / month_factor
    return normalized_units / days * 30.0


def _category_average_monthly_demand(dataset, category, latest_date, seasonality):
    products = dataset.category_products.get(category, [])
    if not products:
        return None

    values = []
    for item in products:
        rows = dataset.sales_by_product.get(item["product_id"], [])
        demand = _de_seasonalized_monthly_demand(rows, latest_date, seasonality, 90)
        if demand:
            values.append(demand)
    return mean(values) if values else None


def _estimate_seasonality(product_rows, category_rows, all_rows, forecast_month):
    product_map = extract_seasonality(product_rows) if len(product_rows) >= 180 else None
    if product_map:
        return {
            **_estimate_payload(
                product_map[forecast_month],
                "product_history",
                "Seasonality derived from product sales history.",
                0.86,
                len(product_rows),
            ),
            "monthly_multipliers": product_map,
        }

    category_map = extract_seasonality(category_rows) if len(category_rows) >= 180 else None
    if category_map:
        return {
            **_estimate_payload(
                category_map[forecast_month],
                "category_history",
                "Seasonality derived from category sales history.",
                0.68,
                len(category_rows),
            ),
            "monthly_multipliers": category_map,
        }

    global_map = extract_seasonality(all_rows) or {month: 1.0 for month in range(1, 13)}
    return {
        **_estimate_payload(
            global_map[forecast_month],
            "global_history",
            "Seasonality derived from the full catalog history.",
            0.52,
            len(all_rows),
        ),
        "monthly_multipliers": global_map,
    }


def _estimate_baseline_demand(product, dataset, product_match, seasonality):
    latest_date = dataset.latest_sale_date
    latest_month_factor = max(seasonality["monthly_multipliers"].get(latest_date.month, 1.0), 0.6)
    user_baseline = product.units_sold_30d / latest_month_factor

    if product_match.product:
        product_rows = dataset.sales_by_product.get(product_match.product["product_id"], [])
        recent_30 = _de_seasonalized_monthly_demand(product_rows, latest_date, seasonality["monthly_multipliers"], 30)
        recent_60 = _de_seasonalized_monthly_demand(product_rows, latest_date, seasonality["monthly_multipliers"], 60)
        recent_90 = _de_seasonalized_monthly_demand(product_rows, latest_date, seasonality["monthly_multipliers"], 90)
        values = [value for value in (recent_30, recent_60, recent_90) if value]
        if values:
            history_baseline = 0.5 * (recent_30 or values[0]) + 0.3 * (recent_60 or values[-1]) + 0.2 * (recent_90 or values[-1])
            blended = history_baseline * 0.65 + user_baseline * 0.35
            return _estimate_payload(
                blended,
                "product_history",
                "Baseline demand blended from product history and the latest 30-day input.",
                0.84 if len(product_rows) >= 180 else 0.72,
                len(product_rows),
            )

    category_baseline = _category_average_monthly_demand(
        dataset,
        product.category,
        latest_date,
        seasonality["monthly_multipliers"],
    )
    if category_baseline:
        blended = user_baseline * 0.75 + category_baseline * 0.25
        return _estimate_payload(
            blended,
            "category_history",
            "Baseline demand anchored to the latest 30-day input and category history.",
            0.62,
            len(dataset.sales_by_category.get(product.category, [])),
        )

    return _estimate_payload(
        user_baseline,
        "user_input",
        "Baseline demand inferred directly from the latest 30-day demand input.",
        0.44,
        0,
    )


def _estimate_elasticity(product, dataset, product_match):
    category_default = CATEGORY_PROFILES[product.category]["elasticity_default"]
    if product.elasticity_override is not None:
        return _estimate_payload(
            product.elasticity_override,
            "manual_override",
            "Elasticity set by manual override.",
            0.95,
            0,
        )

    if product_match.product:
        product_rows = dataset.sales_by_product.get(product_match.product["product_id"], [])
        product_value = estimate_product_elasticity(product_rows)
        if product_value is not None:
            score = 0.82 if len(product_rows) >= 180 else 0.7
            return _estimate_payload(
                product_value,
                "product_history",
                "Elasticity estimated from product price and demand shifts.",
                score,
                len(product_rows),
            )

    category_value = estimate_category_elasticity(dataset.sales_by_category.get(product.category, []))
    if category_value is not None:
        return _estimate_payload(
            category_value,
            "category_history",
            "Elasticity estimated from category price and demand shifts.",
            0.61,
            len(dataset.sales_by_category.get(product.category, [])),
        )

    return _estimate_payload(
        category_default,
        "category_default",
        "Elasticity fell back to the category default benchmark.",
        0.4,
        0,
    )


def _estimate_return_rate(product, dataset, product_match):
    category_default = CATEGORY_PROFILES[product.category]["return_rate_default"]
    if product.return_rate_override is not None:
        return _estimate_payload(
            product.return_rate_override,
            "manual_override",
            "Return rate set by manual override.",
            0.95,
            0,
        )

    if product_match.product:
        product_rows = dataset.sales_by_product.get(product_match.product["product_id"], [])
        product_units = sum(row["units_sold"] for row in product_rows)
        if product_units >= 240:
            rate = sum(row["returns"] for row in product_rows) / max(product_units, 1)
            return _estimate_payload(
                rate,
                "product_history",
                "Return rate estimated from product return history.",
                0.84,
                product_units,
            )

    category_rows = dataset.sales_by_category.get(product.category, [])
    category_units = sum(row["units_sold"] for row in category_rows)
    if category_units >= 600:
        rate = sum(row["returns"] for row in category_rows) / max(category_units, 1)
        return _estimate_payload(
            rate,
            "category_history",
            "Return rate estimated from category return history.",
            0.64,
            category_units,
        )

    return _estimate_payload(
        category_default,
        "category_default",
        "Return rate fell back to the category benchmark.",
        0.42,
        0,
    )


def _estimate_marketing_factor(product, dataset, product_match):
    category_default = CATEGORY_PROFILES[product.category]["marketing_factor_default"]
    if product.marketing_factor_override is not None:
        return _estimate_payload(
            product.marketing_factor_override,
            "manual_override",
            "Marketing factor set by manual override.",
            0.95,
            0,
        )

    if product.scenario != "PROMO":
        return _estimate_payload(
            1.0,
            "scenario_neutral",
            "Marketing factor stays neutral outside promotional scenarios.",
            0.9,
            0,
        )

    rows = []
    if product_match.product:
        rows = dataset.sales_by_product.get(product_match.product["product_id"], [])
    if not rows:
        rows = dataset.sales_by_category.get(product.category, [])

    campaign_rows = [row["units_sold"] for row in rows if row["campaign_flag"]]
    regular_rows = [row["units_sold"] for row in rows if not row["campaign_flag"]]
    if campaign_rows and regular_rows:
        lift = _clamp(mean(campaign_rows) / max(mean(regular_rows), 1.0), 1.0, 1.3)
        score = 0.76 if product_match.product else 0.58
        detail = (
            "Marketing factor estimated from product campaign history."
            if product_match.product
            else "Marketing factor estimated from category campaign history."
        )
        return _estimate_payload(lift, "campaign_history", detail, score, len(rows))

    return _estimate_payload(
        category_default,
        "category_default",
        "Marketing factor fell back to the category benchmark.",
        0.46,
        0,
    )


def _estimate_competitor_reference(product, dataset, product_match):
    if product.competitor_price is not None:
        return _estimate_payload(
            product.competitor_price,
            "user_input",
            "Competitor reference price provided in the current analysis.",
            0.92,
            1,
        )

    if product_match.product:
        latest_price = dataset.latest_competitor_price(product_match.product["product_id"])
        if latest_price:
            return _estimate_payload(
                latest_price,
                "product_snapshot",
                "Competitor reference price taken from the latest product snapshot.",
                0.74,
                len(dataset.competitor_by_product.get(product_match.product["product_id"], [])),
            )

    category_price = dataset.category_competitor_price(product.category)
    if category_price:
        return _estimate_payload(
            category_price,
            "category_snapshot",
            "Competitor reference price estimated from category snapshots.",
            0.56,
            len(dataset.category_products.get(product.category, [])),
        )

    return _estimate_payload(
        product.current_price,
        "current_price_fallback",
        "Competitor reference fell back to the current price.",
        0.32,
        0,
    )


def _estimate_fixed_cost_allocation(product, dataset, product_match):
    if product.fixed_cost_allocation_override is not None:
        return _estimate_payload(
            product.fixed_cost_allocation_override,
            "manual_override",
            "Fixed cost allocation set by manual override.",
            0.95,
            0,
        )

    recent_total_units = sum(row["units_sold"] for row in _recent_rows(dataset.sales_history, dataset.latest_sale_date, 90))
    if recent_total_units <= 0:
        value = dataset.business_settings.monthly_fixed_cost * 0.04
        return _estimate_payload(
            value,
            "business_default",
            "Fixed cost allocation fell back to a standard business share.",
            0.34,
            0,
        )

    if product_match.product:
        product_rows = dataset.sales_by_product.get(product_match.product["product_id"], [])
        recent_product_units = sum(row["units_sold"] for row in _recent_rows(product_rows, dataset.latest_sale_date, 90))
        recent_input_ratio = _clamp(product.units_sold_30d / max(recent_product_units / 3 if recent_product_units else product.units_sold_30d, 1), 0.65, 1.45)
        share = _clamp((recent_product_units / recent_total_units) * recent_input_ratio, 0.015, 0.18)
        value = dataset.business_settings.monthly_fixed_cost * share
        return _estimate_payload(
            value,
            "product_share",
            "Fixed cost allocation estimated from recent product demand share.",
            0.73,
            recent_product_units,
        )

    category_rows = dataset.sales_by_category.get(product.category, [])
    recent_category_units = sum(row["units_sold"] for row in _recent_rows(category_rows, dataset.latest_sale_date, 90))
    product_count = max(len(dataset.category_products.get(product.category, [])), 1)
    share = _clamp((recent_category_units / recent_total_units) / product_count, 0.015, 0.14)
    value = dataset.business_settings.monthly_fixed_cost * share
    return _estimate_payload(
        value,
        "category_share",
        "Fixed cost allocation estimated from average category demand share.",
        0.54,
        recent_category_units,
    )


def _estimate_target_margin(product, dataset):
    if product.target_margin_override is not None:
        return _estimate_payload(
            product.target_margin_override,
            "manual_override",
            "Target margin set by manual override.",
            0.95,
            0,
        )

    rows = dataset.sales_by_category.get(product.category, [])
    if rows:
        margins = []
        for row in rows:
            revenue = row["revenue"]
            if revenue <= 0:
                continue
            realized_cost = product.unit_cost * row["units_sold"]
            margin = (revenue - realized_cost) / revenue
            margins.append(margin)
        if margins:
            category_margin = _clamp(mean(margins), 0.18, 0.42)
            target = max(category_margin * 0.92, dataset.business_settings.default_margin_target)
            return _estimate_payload(
                target,
                "category_history",
                "Target margin estimated from category sales margins and business settings.",
                0.61,
                len(rows),
            )

    return _estimate_payload(
        dataset.business_settings.default_margin_target,
        "business_default",
        "Target margin fell back to the business default.",
        0.46,
        0,
    )


def _build_assumptions(product, dataset):
    product_match = dataset.match_product(product.name, product.category)
    product_rows = dataset.sales_by_product.get(product_match.product["product_id"], []) if product_match.product else []
    category_rows = dataset.sales_by_category.get(product.category, [])
    seasonality = _estimate_seasonality(
        product_rows,
        category_rows,
        dataset.sales_history,
        dataset.forecast_month,
    )

    assumptions = {
        "seasonality": seasonality,
        "baseline_demand": _estimate_baseline_demand(product, dataset, product_match, seasonality),
        "elasticity": _estimate_elasticity(product, dataset, product_match),
        "return_rate": _estimate_return_rate(product, dataset, product_match),
        "marketing_factor": _estimate_marketing_factor(product, dataset, product_match),
        "competitor_reference": _estimate_competitor_reference(product, dataset, product_match),
        "fixed_cost_allocation": _estimate_fixed_cost_allocation(product, dataset, product_match),
        "target_margin": _estimate_target_margin(product, dataset),
    }

    confidence_components = [
        assumptions["baseline_demand"]["confidence_score"] / 100,
        assumptions["seasonality"]["confidence_score"] / 100,
        assumptions["elasticity"]["confidence_score"] / 100,
        assumptions["return_rate"]["confidence_score"] / 100,
    ]
    overall_score = mean(confidence_components)
    overall_confidence = {
        "score": _round(overall_score * 100, 1),
        "level": _confidence_from_score(overall_score),
    }

    context = {
        "match_level": product_match.level,
        "matched_product": product_match.product["name"] if product_match.product else None,
        "reference_price": (
            product_match.product["reference_price"] if product_match.product else dataset.category_reference_price(product.category) or product.current_price
        ),
        "packaging_cost": (
            product_match.product["packaging_cost"] if product_match.product else mean(
                item["packaging_cost"] for item in dataset.category_products.get(product.category, [])
            )
        ),
    }
    return assumptions, overall_confidence, context


def _evaluate_price(product, dataset, assumptions, context, price, strategy_name):
    scenario = SCENARIOS[product.scenario]
    baseline_demand = assumptions["baseline_demand"]["value"]
    elasticity = assumptions["elasticity"]["value"]
    seasonality_factor = assumptions["seasonality"]["value"]
    competitor_reference = assumptions["competitor_reference"]["value"]
    competitor_sensitivity = CATEGORY_PROFILES[product.category]["competitor_sensitivity"]
    return_rate = assumptions["return_rate"]["value"]
    marketing_factor = assumptions["marketing_factor"]["value"] if product.scenario == "PROMO" else 1.0
    target_margin = assumptions["target_margin"]["value"]
    fixed_cost = assumptions["fixed_cost_allocation"]["value"]
    packaging_cost = context["packaging_cost"]

    price_effect = (max(price, 0.01) / max(product.current_price, 0.01)) ** elasticity
    competitor_gap = _safe_div((competitor_reference * scenario["competitor_multiplier"]) - price, competitor_reference, 0.0)
    competitor_factor = _clamp(1.0 + competitor_gap * competitor_sensitivity, 0.84, 1.16)
    scenario_factor = scenario["demand_multiplier"]

    demand = baseline_demand * price_effect * seasonality_factor * competitor_factor * scenario_factor * marketing_factor
    if product.inventory_constraint_override is not None:
        demand = min(demand, product.inventory_constraint_override)

    demand = max(demand, 0.0)
    revenue = price * demand
    variable_cost = (product.unit_cost + packaging_cost + dataset.business_settings.shipping_cost_avg) * demand
    returns_cost = (product.unit_cost + packaging_cost) * demand * return_rate
    payment_fees = revenue * dataset.business_settings.payment_fee_rate
    total_cost = variable_cost + returns_cost + fixed_cost + payment_fees
    profit = revenue - total_cost
    profit_margin = _safe_div(profit, revenue, 0.0) * 100 if revenue > 0 else -100.0
    roi = _safe_div(profit, total_cost, 0.0) * 100 if total_cost > 0 else 0.0

    per_unit_contribution = price - (
        product.unit_cost
        + packaging_cost
        + dataset.business_settings.shipping_cost_avg
        + (product.unit_cost + packaging_cost) * return_rate
        + price * dataset.business_settings.payment_fee_rate
    )
    break_even_units = None
    if per_unit_contribution > 0:
        break_even_units = fixed_cost / per_unit_contribution

    risk_score = 12
    if profit_margin < target_margin * 100:
        risk_score += 18
    if assumptions["elasticity"]["confidence_level"] == "Low":
        risk_score += 10
    if assumptions["baseline_demand"]["confidence_level"] == "Low":
        risk_score += 8
    if competitor_gap < -0.08:
        risk_score += 12
    if product.inventory_constraint_override is not None and demand >= product.inventory_constraint_override * 0.95:
        risk_score += 8
    if profit <= 0:
        risk_score += 22

    risk_score = int(_clamp(risk_score, 0, 100))
    if risk_score < 35:
        risk_level = "Low"
    elif risk_score < 65:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "strategy": strategy_name,
        "scenario": product.scenario,
        "scenario_label": scenario["label"],
        "price": _round(price),
        "demand": _round(demand),
        "revenue": _round(revenue),
        "profit": _round(profit),
        "profit_margin": _round(profit_margin),
        "ROI": _round(roi),
        "break_even_units": None if break_even_units is None else _round(break_even_units),
        "price_gap_vs_competitor": _round(competitor_gap * 100, 2),
        "price_effect": _round(price_effect, 4),
        "seasonality_factor": _round(seasonality_factor, 4),
        "competitor_factor": _round(competitor_factor, 4),
        "scenario_factor": _round(scenario_factor, 4),
        "marketing_factor": _round(marketing_factor, 4),
        "return_rate": _round(return_rate * 100, 2),
        "allocated_fixed_cost": _round(fixed_cost),
        "payment_fees": _round(payment_fees),
        "returns_cost": _round(returns_cost),
        "variable_cost": _round(variable_cost),
        "total_cost": _round(total_cost),
        "target_margin": _round(target_margin * 100, 2),
        "risk_score": risk_score,
        "risk_level": risk_level,
    }


def _price_bounds(product, dataset, assumptions):
    competitor_reference = assumptions["competitor_reference"]["value"]
    floor = max(product.unit_cost * 1.35, product.current_price * 0.82, 8.0)
    if competitor_reference:
        floor = max(floor, competitor_reference * 0.78)

    ceiling = max(product.current_price * 1.3, product.unit_cost * 4.0)
    if competitor_reference:
        ceiling = max(ceiling, competitor_reference * 1.24)

    return _round(floor), _round(ceiling)


def optimize_price(product, dataset=None, assumptions=None, context=None):
    dataset = dataset or load_business_dataset()
    if assumptions is None or context is None:
        built_assumptions, _, built_context = _build_assumptions(product, dataset)
        assumptions = assumptions or built_assumptions
        context = context or built_context
    lower_bound, upper_bound = _price_bounds(product, dataset, assumptions)
    steps = 28
    interval = (upper_bound - lower_bound) / max(steps - 1, 1)

    candidates = []
    curve = []
    for index in range(steps):
        price = lower_bound + interval * index
        result = _evaluate_price(product, dataset, assumptions, context, price, "Profit Optimal")
        candidates.append(result)
        curve.append(
            {
                "price": result["price"],
                "profit": result["profit"],
                "revenue": result["revenue"],
                "demand": result["demand"],
                "margin": result["profit_margin"],
            }
        )

    best = max(candidates, key=lambda item: (item["profit"], item["revenue"], -item["risk_score"]))
    return {
        "best_price": best["price"],
        "best_result": best,
        "candidates": candidates,
        "price_profit_curve": curve,
    }


def _strategy_prices(product, dataset, assumptions, context):
    lower_bound, upper_bound = _price_bounds(product, dataset, assumptions)
    competitor_reference = assumptions["competitor_reference"]["value"]
    target_margin = assumptions["target_margin"]["value"]
    return_rate = assumptions["return_rate"]["value"]
    required_price = (
        product.unit_cost
        + dataset.business_settings.shipping_cost_avg
        + product.unit_cost * return_rate
    ) / max(1.0 - target_margin - dataset.business_settings.payment_fee_rate, 0.18)

    optimizer = optimize_price(product, dataset=dataset, assumptions=assumptions, context=context)

    candidates = {
        "Current Price": product.current_price,
        "Competitive Parity": competitor_reference * 0.995 if competitor_reference else product.current_price,
        "Volume Push": min(product.current_price * 0.93, (competitor_reference or product.current_price) * 0.98),
        "Margin Guardrail": required_price,
        "Premium Lift": max(product.current_price * 1.08, (competitor_reference or product.current_price) * 1.04),
    }

    bounded = {}
    for name, raw_price in candidates.items():
        bounded[name] = _round(_clamp(raw_price, lower_bound, upper_bound))

    best_profit_price = optimizer["best_price"]
    best_profit_value = optimizer["best_result"]["profit"]
    for raw_price in bounded.values():
        evaluated = _evaluate_price(product, dataset, assumptions, context, raw_price, "Profit Optimal")
        if evaluated["profit"] > best_profit_value:
            best_profit_value = evaluated["profit"]
            best_profit_price = evaluated["price"]

    bounded["Profit Optimal"] = best_profit_price
    return bounded, optimizer


def _build_recommendation_reasons(best, current_option, assumptions, optimizer):
    reasons = [
        f"This option produced the highest projected profit across {len(optimizer['candidates'])} candidate prices.",
        f"Projected profit margin is {best['profit_margin']}% against a target of {best['target_margin']}%.",
        f"Projected demand lands at {best['demand']} units with a competitor gap of {best['price_gap_vs_competitor']}%.",
        f"Confidence is {assumptions['baseline_demand']['confidence_level']} to {assumptions['elasticity']['confidence_level']} across the core estimates.",
    ]
    if current_option:
        profit_lift = _round(best["profit"] - current_option["profit"])
        if profit_lift > 0:
            reasons.append(
                f"It improves projected profit by {profit_lift} versus staying at the current price."
            )
    return reasons[:4]


def run_full_analysis(product):
    validate_product(product)
    dataset = load_business_dataset()
    assumptions, overall_confidence, context = _build_assumptions(product, dataset)
    strategy_prices, optimizer = _strategy_prices(product, dataset, assumptions, context)

    evaluated = []
    for strategy_name in DISPLAY_STRATEGIES:
        result = _evaluate_price(
            product,
            dataset,
            assumptions,
            context,
            strategy_prices[strategy_name],
            strategy_name,
        )
        result["confidence_level"] = overall_confidence["level"]
        result["confidence_score"] = overall_confidence["score"]
        evaluated.append(result)

    evaluated.sort(
        key=lambda item: (
            item["profit"],
            item["revenue"],
            1 if item["strategy"] == "Profit Optimal" else 0,
            -item["risk_score"],
        ),
        reverse=True,
    )
    for rank, item in enumerate(evaluated, start=1):
        item["rank"] = rank

    best = evaluated[0]
    current_option = next((item for item in evaluated if item["strategy"] == "Current Price"), None)
    next_best = evaluated[1] if len(evaluated) > 1 else None
    comparison_context = None
    if next_best:
        comparison_context = {
            "next_best_strategy": next_best["strategy"],
            "profit_gap": _round(best["profit"] - next_best["profit"]),
            "revenue_gap": _round(best["revenue"] - next_best["revenue"]),
        }
        best["comparison_context"] = comparison_context

    best["recommendation_reasons"] = _build_recommendation_reasons(best, current_option, assumptions, optimizer)

    return {
        "product": asdict(product),
        "matched_context": {
            "match_level": context["match_level"],
            "matched_product": context.get("matched_product"),
            "reference_price": context["reference_price"],
        },
        "assumptions": assumptions,
        "overall_confidence": overall_confidence,
        "best_strategy": best,
        "strategies": evaluated,
        "price_profit_curve": optimizer["price_profit_curve"],
        "current_option": current_option,
        "explanation": {
            "title": "",
            "summary": "",
            "details": [],
            "caution": None,
        },
    }


def compare_all_scenarios(product):
    validate_product(product)
    scenarios = []

    for scenario_name in SCENARIOS:
        result = run_full_analysis(_scenario_product(product, scenario_name))
        best = result["best_strategy"]
        scenarios.append(
            {
                "scenario": scenario_name,
                "best_strategy": best["strategy"],
                "price": best["price"],
                "demand": best["demand"],
                "revenue": best["revenue"],
                "profit": best["profit"],
                "profit_margin": best["profit_margin"],
                "confidence_level": result["overall_confidence"]["level"],
                "confidence_score": result["overall_confidence"]["score"],
                "risk_level": best["risk_level"],
                "risk_score": best["risk_score"],
            }
        )

    profits = [item["profit"] for item in scenarios]
    winning = max(scenarios, key=lambda item: (item["profit"], item["revenue"], item["confidence_score"]))
    return {
        "scenarios": scenarios,
        "winning_scenario": winning["scenario"],
        "best_overall_scenario": winning["scenario"],
        "aggregate": {
            "mean_profit": _round(mean(profits)),
            "profit_std_dev": _round(pstdev(profits) if len(profits) > 1 else 0.0),
            "mean_revenue": _round(mean(item["revenue"] for item in scenarios)),
        },
    }
