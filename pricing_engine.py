from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from statistics import mean, pstdev


@dataclass
class ProductData:
    name: str
    category: str
    unit_cost: float
    fixed_cost: float
    base_price: float
    competitor_price: float
    base_demand: float
    inventory: int
    elasticity: float
    marketing_budget: float
    return_rate: float
    desired_margin: float
    scenario: str = "NORMAL"


SCENARIOS = {
    "LOW": {
        "label": "Low Market Demand",
        "demand_multiplier": 0.84,
        "competitor_multiplier": 0.97,
        "cost_multiplier": 1.03,
        "marketing_multiplier": 0.92,
        "return_rate_multiplier": 1.06,
    },
    "NORMAL": {
        "label": "Normal Conditions",
        "demand_multiplier": 1.0,
        "competitor_multiplier": 1.0,
        "cost_multiplier": 1.0,
        "marketing_multiplier": 1.0,
        "return_rate_multiplier": 1.0,
    },
    "HIGH": {
        "label": "High Demand Window",
        "demand_multiplier": 1.18,
        "competitor_multiplier": 1.04,
        "cost_multiplier": 1.04,
        "marketing_multiplier": 1.08,
        "return_rate_multiplier": 0.96,
    },
    "PROMO": {
        "label": "Promotional Campaign",
        "demand_multiplier": 1.32,
        "competitor_multiplier": 0.95,
        "cost_multiplier": 1.0,
        "marketing_multiplier": 1.22,
        "return_rate_multiplier": 1.1,
    },
}

# Centralized weights keep the ranking explainable and easy to tune.
SCORING_WEIGHTS = {
    "profit": 0.32,
    "margin": 0.22,
    "roi": 0.18,
    "risk": 0.18,
    "stability": 0.10,
}


def _round(value, digits=2):
    return round(float(value), digits)


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def _safe_div(numerator, denominator, default=0.0):
    if abs(denominator) < 1e-9:
        return default
    return numerator / denominator


def _scenario_product(product, scenario_name):
    return replace(product, scenario=scenario_name.upper())


def validate_product(product):
    errors = []

    if not product.name.strip():
        errors.append("Product name is required.")
    if not product.category.strip():
        errors.append("Category is required.")
    if product.unit_cost < 0:
        errors.append("Unit cost cannot be negative.")
    if product.fixed_cost < 0:
        errors.append("Fixed cost cannot be negative.")
    if product.base_price <= 0:
        errors.append("Base price must be greater than zero.")
    if product.competitor_price <= 0:
        errors.append("Competitor price must be greater than zero.")
    if product.base_demand <= 0:
        errors.append("Base demand must be greater than zero.")
    if product.inventory <= 0:
        errors.append("Inventory must be greater than zero.")
    if product.elasticity >= -0.05 or product.elasticity < -5:
        errors.append("Elasticity must be a negative value between -5 and -0.05.")
    if product.marketing_budget < 0:
        errors.append("Marketing budget cannot be negative.")
    if product.return_rate < 0 or product.return_rate >= 0.5:
        errors.append("Return rate must be between 0 and 0.49.")
    if product.desired_margin <= 0 or product.desired_margin >= 90:
        errors.append("Desired margin must be between 0 and 90 percent.")
    if product.scenario not in SCENARIOS:
        errors.append(f"Scenario must be one of: {', '.join(SCENARIOS.keys())}.")

    if errors:
        raise ValueError(" ".join(errors))

    return True


def get_adjusted_values(product):
    validate_product(product)
    scenario = SCENARIOS[product.scenario]
    adjusted_return_rate = min(
        0.45,
        max(0.0, product.return_rate * scenario["return_rate_multiplier"]),
    )

    adjusted_values = {
        "scenario": product.scenario,
        "scenario_label": scenario["label"],
        "adjusted_unit_cost": _round(product.unit_cost * scenario["cost_multiplier"]),
        "adjusted_competitor_price": _round(
            product.competitor_price * scenario["competitor_multiplier"]
        ),
        "adjusted_base_demand": _round(
            product.base_demand * scenario["demand_multiplier"]
        ),
        "adjusted_marketing_budget": _round(
            product.marketing_budget * scenario["marketing_multiplier"]
        ),
        "adjusted_return_rate": _round(adjusted_return_rate, 4),
        "demand_multiplier": scenario["demand_multiplier"],
        "competitor_multiplier": scenario["competitor_multiplier"],
        "cost_multiplier": scenario["cost_multiplier"],
    }
    adjusted_values["reference_price"] = _round(
        product.base_price * 0.45 + adjusted_values["adjusted_competitor_price"] * 0.55
    )
    return adjusted_values


def marketing_effect(marketing_budget):
    # Marketing contributes diminishing demand lift instead of linear growth.
    normalized_budget = max(marketing_budget, 0.0)
    lift = min(0.32, math.log1p(normalized_budget / 250.0) * 0.12)
    return 1.0 + lift


def _demand_context(product, price, adjusted):
    safe_price = max(price, 0.01)
    reference_price = max(adjusted["reference_price"], 0.01)
    competitor_price = max(adjusted["adjusted_competitor_price"], 0.01)

    price_factor = (safe_price / reference_price) ** product.elasticity
    price_gap_vs_competitor = _safe_div(competitor_price - safe_price, competitor_price)
    competitiveness = _clamp(1.0 + price_gap_vs_competitor * 0.22, 0.78, 1.16)
    promotion_lift = marketing_effect(adjusted["adjusted_marketing_budget"])

    expected_demand = (
        adjusted["adjusted_base_demand"]
        * price_factor
        * competitiveness
        * promotion_lift
    )

    return {
        "expected_demand": _round(max(expected_demand, 0.0)),
        "price_factor": price_factor,
        "competitiveness": competitiveness,
        "promotion_lift": promotion_lift,
        "price_gap_vs_competitor": _round(price_gap_vs_competitor * 100, 2),
        "elasticity_effect": _round((price_factor - 1.0) * 100, 2),
    }


def demand_model(product, price):
    adjusted = get_adjusted_values(product)
    return _demand_context(product, price, adjusted)["expected_demand"]


def effective_sold_quantity(product, demand):
    adjusted = get_adjusted_values(product)
    gross_units = min(max(demand, 0.0), float(product.inventory))
    net_units = gross_units * (1.0 - adjusted["adjusted_return_rate"])
    return _round(max(net_units, 0.0))


def _risk_evaluation(
    product,
    price,
    unit_cost,
    adjusted_competitor_price,
    contribution_margin,
    profit_margin,
    break_even_units,
    sold_quantity,
    adjusted_return_rate,
    profit,
):
    risk_score = 0
    risk_factors = []

    desired_margin_gap = max(product.desired_margin - profit_margin, 0.0)
    sales_ratio = _safe_div(sold_quantity, product.inventory)
    aggressive_discount = max(
        0.0,
        _safe_div(adjusted_competitor_price - price, adjusted_competitor_price),
    )
    markup_ratio = _safe_div(price - unit_cost, unit_cost)

    if contribution_margin < 18:
        risk_score += 22
        risk_factors.append("Contribution margin is thin, leaving little buffer per unit sold.")
    elif contribution_margin < 28:
        risk_score += 12
        risk_factors.append("Contribution margin is moderate and should be monitored closely.")

    if desired_margin_gap > 0:
        risk_score += min(22, 7 + desired_margin_gap * 0.7)
        risk_factors.append(
            "Projected profit margin stays below the target margin set for the product."
        )

    if break_even_units is None:
        risk_score += 26
        risk_factors.append("The current price does not cover the variable cost base.")
    elif break_even_units > product.inventory:
        risk_score += 22
        risk_factors.append("Break-even units exceed available inventory.")
    elif break_even_units > product.inventory * 0.85:
        risk_score += 12
        risk_factors.append("Break-even volume is close to the inventory ceiling.")

    if sales_ratio < 0.35:
        risk_score += 18
        risk_factors.append("Expected sold quantity is weak relative to available inventory.")
    elif sales_ratio < 0.55:
        risk_score += 10
        risk_factors.append("Expected sold quantity is moderate rather than strong.")

    if adjusted_return_rate > 0.12:
        risk_score += 14
        risk_factors.append("Return rate is high and may erode realized sales.")
    elif adjusted_return_rate > 0.08:
        risk_score += 7
        risk_factors.append("Return rate is elevated compared with a stable retail benchmark.")

    if aggressive_discount > 0.12:
        risk_score += 12
        risk_factors.append("The strategy depends on an aggressive discount versus competitors.")
    elif aggressive_discount > 0.06:
        risk_score += 6
        risk_factors.append("The price relies on noticeable discounting to stimulate demand.")

    if markup_ratio < 0.18:
        risk_score += 10
        risk_factors.append("Markup above unit cost is narrow for a consumer product setting.")

    if profit <= 0:
        risk_score += 24
        risk_factors.append("Expected profit is non-positive under the current assumptions.")

    risk_score = int(_clamp(round(risk_score), 0, 100))
    if risk_score < 35:
        risk_level = "Low"
    elif risk_score < 65:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return risk_score, risk_level, risk_factors[:4]


def calculate_financials(product, price, strategy_name):
    validate_product(product)
    adjusted = get_adjusted_values(product)
    demand_context = _demand_context(product, price, adjusted)

    demand = demand_context["expected_demand"]
    gross_units = min(float(product.inventory), demand)
    sold_quantity = effective_sold_quantity(product, demand)
    returned_units = _round(max(gross_units - sold_quantity, 0.0))

    unit_cost = adjusted["adjusted_unit_cost"]
    revenue = sold_quantity * price
    total_cost = (
        product.fixed_cost
        + adjusted["adjusted_marketing_budget"]
        + gross_units * unit_cost
    )
    profit = revenue - total_cost

    unit_contribution = price - unit_cost
    contribution_margin = _safe_div(unit_contribution, price) * 100 if price > 0 else 0.0
    profit_margin = _safe_div(profit, revenue, -1.0) * 100 if revenue > 0 else -100.0

    break_even_units = None
    if unit_contribution > 0:
        break_even_units = (
            (product.fixed_cost + adjusted["adjusted_marketing_budget"]) / unit_contribution
        )

    roi = _safe_div(profit, total_cost) * 100 if total_cost > 0 else 0.0
    revenue_per_unit = _safe_div(revenue, sold_quantity)
    inventory_utilization = _safe_div(gross_units, product.inventory) * 100

    risk_score, risk_level, risk_factors = _risk_evaluation(
        product=product,
        price=price,
        unit_cost=unit_cost,
        adjusted_competitor_price=adjusted["adjusted_competitor_price"],
        contribution_margin=contribution_margin,
        profit_margin=profit_margin,
        break_even_units=break_even_units,
        sold_quantity=sold_quantity,
        adjusted_return_rate=adjusted["adjusted_return_rate"],
        profit=profit,
    )

    return {
        "strategy": strategy_name,
        "scenario": product.scenario,
        "scenario_label": adjusted["scenario_label"],
        "price": _round(price),
        "demand": _round(demand),
        "gross_units": _round(gross_units),
        "sold_quantity": _round(sold_quantity),
        "returned_units": returned_units,
        "inventory_utilization": _round(inventory_utilization),
        "revenue": _round(revenue),
        "total_cost": _round(total_cost),
        "profit": _round(profit),
        "profit_margin": _round(profit_margin),
        "contribution_margin": _round(contribution_margin),
        "break_even_units": None if break_even_units is None else _round(break_even_units),
        "ROI": _round(roi),
        "revenue_per_unit": _round(revenue_per_unit),
        "price_gap_vs_competitor": demand_context["price_gap_vs_competitor"],
        "elasticity_effect": demand_context["elasticity_effect"],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
    }


def _price_bounds(product):
    adjusted = get_adjusted_values(product)
    lower_bound = max(
        adjusted["adjusted_unit_cost"] * 1.02,
        product.base_price * 0.6,
        1.0,
    )
    upper_bound = max(
        product.base_price * 1.7,
        adjusted["adjusted_competitor_price"] * 1.6,
        adjusted["adjusted_unit_cost"] * 2.5,
    )
    return _round(lower_bound), _round(upper_bound)


def _bounded_price(product, candidate_price):
    lower_bound, upper_bound = _price_bounds(product)
    bounded = min(max(candidate_price, lower_bound), upper_bound)
    return _round(bounded)


def _strategy_base_prices(product):
    adjusted = get_adjusted_values(product)
    desired_margin_ratio = product.desired_margin / 100.0
    elasticity_abs = abs(product.elasticity)
    inventory_ratio = product.inventory / max(adjusted["adjusted_base_demand"], 1.0)

    cost_plus = (
        adjusted["adjusted_unit_cost"] + (product.fixed_cost / max(product.inventory, 1)) * 0.2
    ) * (1.0 + desired_margin_ratio)

    competitive = (
        product.base_price * 0.4 + adjusted["adjusted_competitor_price"] * 0.6
    ) * (0.98 if inventory_ratio > 1.05 else 1.02 if inventory_ratio < 0.75 else 1.0)

    demand_bias = (
        1.0
        + max(0.0, 1.1 - elasticity_abs) * 0.12
        - max(0.0, elasticity_abs - 1.1) * 0.07
    )
    demand_based = adjusted["reference_price"] * demand_bias

    if inventory_ratio > 1.2:
        inventory_shift = -0.09
    elif inventory_ratio > 1.0:
        inventory_shift = -0.04
    elif inventory_ratio < 0.7:
        inventory_shift = 0.08
    else:
        inventory_shift = 0.02
    inventory_based = product.base_price * (1.0 + inventory_shift)

    target_margin = adjusted["adjusted_unit_cost"] / max(1.0 - desired_margin_ratio, 0.1)

    return {
        "Cost-Plus": _bounded_price(product, cost_plus),
        "Competitive": _bounded_price(product, competitive),
        "Demand-Based": _bounded_price(product, demand_based),
        "Inventory-Based": _bounded_price(product, inventory_based),
        "Target-Margin": _bounded_price(product, target_margin),
    }


def _scenario_stability(product, price, strategy_name):
    # Stability is measured by reusing the same price in every scenario.
    scenario_results = []
    for scenario_name in SCENARIOS:
        scenario_product = _scenario_product(product, scenario_name)
        scenario_results.append(
            calculate_financials(scenario_product, price, strategy_name)
        )

    profits = [result["profit"] for result in scenario_results]
    risk_scores = [result["risk_score"] for result in scenario_results]
    mean_profit = mean(profits)
    profit_std_dev = pstdev(profits) if len(profits) > 1 else 0.0
    volatility_ratio = abs(profit_std_dev) / (abs(mean_profit) + 1.0)
    negative_profit_count = sum(1 for item in profits if item <= 0)
    average_risk = mean(risk_scores)

    stability_score = 100.0
    stability_score -= min(38.0, volatility_ratio * 55.0)
    stability_score -= average_risk * 0.22
    stability_score -= negative_profit_count * 12.0
    stability_score = _clamp(stability_score, 0.0, 100.0)

    best_scenario = max(
        scenario_results,
        key=lambda item: (item["profit"], -item["risk_score"]),
    )
    worst_scenario = min(
        scenario_results,
        key=lambda item: (item["profit"], -item["risk_score"]),
    )

    return {
        "stability_score": _round(stability_score),
        "mean_profit": _round(mean_profit),
        "profit_std_dev": _round(profit_std_dev),
        "average_risk_score": _round(average_risk),
        "best_scenario": best_scenario["scenario"],
        "worst_scenario": worst_scenario["scenario"],
    }


def _attach_stability(product, result):
    stability = _scenario_stability(product, result["price"], result["strategy"])
    return {
        **result,
        "stability_score": stability["stability_score"],
        "scenario_stability": stability,
    }


def _scale_metric(values, current_value):
    lower = min(values)
    upper = max(values)
    if math.isclose(lower, upper):
        return 100.0
    return ((current_value - lower) / (upper - lower)) * 100.0


def _score_result(result, profits, margins, rois):
    profit_score = _scale_metric(profits, result["profit"])
    margin_score = _scale_metric(margins, result["profit_margin"])
    roi_score = _scale_metric(rois, result["ROI"])
    risk_score = 100.0 - result["risk_score"]
    stability_score = result.get("stability_score", 50.0)
    weight_total = sum(SCORING_WEIGHTS.values()) or 1.0

    balanced_score = (
        profit_score * SCORING_WEIGHTS["profit"]
        + margin_score * SCORING_WEIGHTS["margin"]
        + roi_score * SCORING_WEIGHTS["roi"]
        + risk_score * SCORING_WEIGHTS["risk"]
        + stability_score * SCORING_WEIGHTS["stability"]
    ) / weight_total

    return {
        "balanced_score": _round(balanced_score),
        "score_breakdown": {
            "profit_score": _round(profit_score),
            "margin_score": _round(margin_score),
            "roi_score": _round(roi_score),
            "risk_adjusted_score": _round(risk_score),
            "stability_score": _round(stability_score),
        },
    }


def get_strategy_prices(product):
    validate_product(product)
    optimizer = optimize_price(product)
    strategy_prices = _strategy_base_prices(product)
    strategy_prices["AI Recommended"] = optimizer["best_price"]
    return strategy_prices


def optimize_price(product):
    validate_product(product)
    lower_bound, upper_bound = _price_bounds(product)
    steps = 36
    interval = (upper_bound - lower_bound) / (steps - 1)

    candidates = []
    price_profit_curve = []

    for index in range(steps):
        price = lower_bound + interval * index
        result = calculate_financials(product, price, "AI Recommended")
        result = _attach_stability(product, result)
        candidates.append(result)
        price_profit_curve.append(
            {
                "price": result["price"],
                "profit": result["profit"],
                "revenue": result["revenue"],
                "risk_score": result["risk_score"],
            }
        )

    profits = [result["profit"] for result in candidates]
    margins = [result["profit_margin"] for result in candidates]
    rois = [result["ROI"] for result in candidates]

    ranked_candidates = []
    for candidate in candidates:
        score_payload = _score_result(candidate, profits, margins, rois)
        ranked_candidates.append(
            {
                **candidate,
                "optimization_score": score_payload["balanced_score"],
                "score_breakdown": score_payload["score_breakdown"],
            }
        )

    ranked_candidates.sort(
        key=lambda item: (
            item["optimization_score"],
            item["profit"],
            -item["risk_score"],
        ),
        reverse=True,
    )
    best_result = ranked_candidates[0]

    return {
        "best_price": best_result["price"],
        "best_profit": best_result["profit"],
        "best_result": best_result,
        "price_profit_curve": price_profit_curve,
        "search_range": {"min": lower_bound, "max": upper_bound, "steps": steps},
        "top_candidates": ranked_candidates[:5],
    }


def balanced_ranking(results):
    profits = [result["profit"] for result in results]
    margins = [result["profit_margin"] for result in results]
    rois = [result["ROI"] for result in results]

    ranked = []
    for result in results:
        score_payload = _score_result(result, profits, margins, rois)
        ranked.append(
            {
                **result,
                "balanced_score": score_payload["balanced_score"],
                "score_breakdown": score_payload["score_breakdown"],
            }
        )

    ranked.sort(
        key=lambda item: (
            item["balanced_score"],
            item["profit"],
            -item["risk_score"],
        ),
        reverse=True,
    )
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index

    return ranked


def generate_explanation(best, product):
    adjusted = get_adjusted_values(product)
    break_even_units = best["break_even_units"]

    if break_even_units is None:
        break_even_note = (
            "Break-even is not reached because the recommended price does not fully cover variable cost."
        )
    elif break_even_units <= product.inventory:
        break_even_note = (
            f"Break-even is estimated at {break_even_units} units, which remains inside the current inventory level."
        )
    else:
        break_even_note = (
            f"Break-even is estimated at {break_even_units} units, which exceeds inventory and increases execution risk."
        )

    elasticity_note = (
        f"The elasticity value of {product.elasticity} means demand is price-sensitive; "
        f"at the recommended price, the modeled price effect changes demand by {best['elasticity_effect']}% "
        f"relative to the blended market reference."
    )

    scenario_note = (
        f"The {adjusted['scenario_label'].lower()} adjusts baseline demand to {adjusted['adjusted_base_demand']} units, "
        f"competitor reference price to ${adjusted['adjusted_competitor_price']}, "
        f"unit cost to ${adjusted['adjusted_unit_cost']}, and return rate to "
        f"{_round(adjusted['adjusted_return_rate'] * 100, 2)}%."
    )

    comparison_context = best.get("comparison_context")
    if comparison_context:
        preference_note = (
            f"It ranks ahead of {comparison_context['next_best_strategy']} by "
            f"{comparison_context['score_gap']} score points. "
            f"The selected option improves profit by ${comparison_context['profit_gap']} "
            f"and changes risk by {comparison_context['risk_gap']} points versus the next-best strategy."
        )
    else:
        preference_note = (
            "It is preferred because it provides the strongest balance between profitability, margin quality, ROI, and risk."
        )

    stability = best.get("scenario_stability", {})
    stability_note = None
    if stability:
        stability_note = (
            f"Across all scenarios, the same price yields mean profit of ${stability['mean_profit']} "
            f"with a profit standard deviation of ${stability['profit_std_dev']}. "
            f"This results in a stability score of {stability['stability_score']}."
        )

    caution = None
    if best["risk_level"] != "Low":
        if best.get("risk_factors"):
            caution = "Key risk drivers: " + " ".join(best["risk_factors"][:2])
        else:
            caution = (
                f"The recommendation still carries {best['risk_level'].lower()} risk under the selected scenario."
            )

    details = [
        f"The selected strategy is {best['strategy']} with a recommended price of ${best['price']}. "
        f"Expected revenue is ${best['revenue']} and expected profit is ${best['profit']}.",
        f"Projected profit margin is {best['profit_margin']}%, contribution margin is {best['contribution_margin']}%, "
        f"ROI is {best['ROI']}%, and the overall risk level is {best['risk_level']} ({best['risk_score']}/100).",
        elasticity_note,
        scenario_note,
        preference_note,
        break_even_note,
    ]
    if stability_note:
        details.insert(5, stability_note)

    return {
        "title": f"{best['strategy']} is the recommended pricing strategy for {product.name}",
        "summary": (
            f"PricePilot recommends ${best['price']} for {product.name} because this option delivers "
            f"the strongest balanced decision score, not just the highest raw profit. "
            f"It combines ${best['profit']} expected profit, {best['profit_margin']}% margin, "
            f"{best['ROI']}% ROI, and {best['risk_level'].lower()} operational risk."
        ),
        "details": details,
        "caution": caution,
    }


def scenario_snapshot(product, scenario_name):
    scenario_product = _scenario_product(product, scenario_name)
    analysis = run_full_analysis(scenario_product)
    best = analysis["best_strategy"]

    return {
        "scenario": scenario_name.upper(),
        "scenario_label": SCENARIOS[scenario_name.upper()]["label"],
        "best_strategy": best["strategy"],
        "recommended_price": best["price"],
        "price": best["price"],
        "profit": best["profit"],
        "revenue": best["revenue"],
        "profit_margin": best["profit_margin"],
        "ROI": best["ROI"],
        "sold_quantity": best["sold_quantity"],
        "risk_score": best["risk_score"],
        "risk_level": best["risk_level"],
        "balanced_score": best["balanced_score"],
        "stability_score": best.get("stability_score", 50.0),
    }


def compare_all_scenarios(product):
    validate_product(product)
    scenario_results = [scenario_snapshot(product, name) for name in SCENARIOS]

    profits = [item["profit"] for item in scenario_results]
    margins = [item["profit_margin"] for item in scenario_results]
    rois = [item["ROI"] for item in scenario_results]

    scored_results = []
    for item in scenario_results:
        score_payload = _score_result(
            {
                **item,
                "stability_score": item.get("stability_score", 50.0),
            },
            profits,
            margins,
            rois,
        )
        scored_results.append(
            {
                **item,
                "scenario_score": score_payload["balanced_score"],
            }
        )

    winning_scenario = max(
        scored_results,
        key=lambda item: (item["profit"], -item["risk_score"]),
    )
    best_overall_scenario = max(
        scored_results,
        key=lambda item: (item["scenario_score"], item["profit"]),
    )

    aggregate = {
        "mean_profit": _round(mean(profits)),
        "profit_std_dev": _round(pstdev(profits) if len(profits) > 1 else 0.0),
        "mean_risk_score": _round(mean([item["risk_score"] for item in scored_results])),
        "mean_ROI": _round(mean([item["ROI"] for item in scored_results])),
        "best_overall_scenario": best_overall_scenario["scenario"],
    }

    return {
        "scenarios": scored_results,
        "winning_scenario": winning_scenario["scenario"],
        "winning_summary": winning_scenario,
        "best_overall_scenario": best_overall_scenario["scenario"],
        "aggregate": aggregate,
        "labels": [item["scenario"] for item in scored_results],
        "profits": [item["profit"] for item in scored_results],
        "revenues": [item["revenue"] for item in scored_results],
        "risk_scores": [item["risk_score"] for item in scored_results],
    }


def run_full_analysis(product):
    validate_product(product)
    adjusted = get_adjusted_values(product)
    optimizer = optimize_price(product)
    strategy_prices = _strategy_base_prices(product)

    strategy_results = []
    for strategy_name, price in strategy_prices.items():
        result = calculate_financials(product, price, strategy_name)
        strategy_results.append(_attach_stability(product, result))

    ai_result = optimizer["best_result"]
    strategy_results.append(
        {
            **ai_result,
            "strategy": "AI Recommended",
        }
    )

    ranked_results = balanced_ranking(strategy_results)
    best_strategy = ranked_results[0]

    if len(ranked_results) > 1:
        next_best = ranked_results[1]
        best_strategy["comparison_context"] = {
            "next_best_strategy": next_best["strategy"],
            "score_gap": _round(best_strategy["balanced_score"] - next_best["balanced_score"]),
            "profit_gap": _round(best_strategy["profit"] - next_best["profit"]),
            "risk_gap": int(best_strategy["risk_score"] - next_best["risk_score"]),
        }

    return {
        "product": asdict(product),
        "adjusted_inputs": adjusted,
        "summary": {
            "best_strategy": best_strategy["strategy"],
            "recommended_price": best_strategy["price"],
            "expected_profit": best_strategy["profit"],
            "profit_margin": best_strategy["profit_margin"],
            "ROI": best_strategy["ROI"],
            "risk_level": best_strategy["risk_level"],
            "stability_score": best_strategy.get("stability_score", 50.0),
        },
        "best_strategy": best_strategy,
        "strategies": ranked_results,
        "optimizer": {
            "best_price": optimizer["best_price"],
            "best_profit": optimizer["best_profit"],
            "best_score": optimizer["best_result"]["optimization_score"],
            "search_range": optimizer["search_range"],
        },
        "price_profit_curve": optimizer["price_profit_curve"],
        "explanation": generate_explanation(best_strategy, product),
    }
