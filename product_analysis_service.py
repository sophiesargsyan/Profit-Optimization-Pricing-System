from __future__ import annotations

from collections.abc import Mapping

from catalog_profiles import CATEGORY_PROFILES
from pricing_engine import ProductData, compare_all_scenarios, run_full_analysis


FREE_FORM_CATEGORY_KEYWORDS = (
    ("Jewelry", ("jewelry", "jewel", "ring", "bracelet", "necklace", "earring", "watch")),
    ("Fashion", ("fashion", "apparel", "clothing", "dress", "shirt", "pants", "shoe", "sneaker", "jacket", "coat")),
    ("Beauty", ("beauty", "cosmetic", "makeup", "skin", "serum", "cream", "fragrance", "perfume")),
    ("Accessories", ("accessory", "accessories", "bag", "wallet", "belt", "hat", "scarf", "sunglass")),
)


def _first_value(source, field_name, *aliases):
    for key in (field_name, *aliases):
        if key in source:
            return source.get(key)
    return None


def _required_text(source, field_name, *aliases):
    value = _first_value(source, field_name, *aliases)
    return str(value or "").strip()


def _required_number(source, field_name, *aliases):
    return float(_first_value(source, field_name, *aliases))


def _optional_number(source, field_name, *aliases, percent=False, integer=False):
    value = _first_value(source, field_name, *aliases)
    if value in (None, ""):
        return None

    parsed = float(value)
    if percent and parsed > 1:
        parsed /= 100.0
    return int(parsed) if integer else float(parsed)


def _options_mapping(options):
    return options if isinstance(options, Mapping) else {}


def _canonical_category(category):
    value = str(category or "").strip()
    matched_category = next(
        (
            profile_category
            for profile_category in CATEGORY_PROFILES
            if profile_category.lower() == value.lower()
        ),
        None,
    )
    if matched_category:
        return matched_category

    normalized = value.lower()
    for profile_category, keywords in FREE_FORM_CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return profile_category

    return "Accessories"


def _analysis_price_bounds(product_input, options=None):
    options = _options_mapping(options)
    price_bounds = options.get("price_bounds") if isinstance(options.get("price_bounds"), Mapping) else {}
    sources = [price_bounds, options]
    if isinstance(product_input, Mapping):
        sources.append(product_input)

    bounds = {}
    for output_key, aliases in {
        "min_price": ("min_price", "lower_bound"),
        "max_price": ("max_price", "upper_bound"),
    }.items():
        for source in sources:
            value = _first_value(source, *aliases)
            if value in (None, ""):
                continue
            parsed = float(value)
            if parsed > 0:
                bounds[output_key] = parsed
                break

    return bounds or None


def _optional_elasticity(source):
    parsed = _optional_number(source, "elasticity_override", "elasticity")
    if parsed is None:
        return None

    # Bulk upload templates usually express elasticity as a positive magnitude.
    # The pricing model expects signed price elasticity, where demand falls as price rises.
    return -abs(parsed) if parsed > 0 else parsed


def normalize_product_input(product_input):
    if isinstance(product_input, ProductData):
        return product_input
    if not isinstance(product_input, Mapping):
        raise TypeError("Product input must be a ProductData instance or mapping.")

    return ProductData(
        name=_required_text(product_input, "name", "product_name"),
        category=_canonical_category(_required_text(product_input, "category")),
        unit_cost=_required_number(product_input, "unit_cost"),
        current_price=_required_number(product_input, "current_price", "base_price"),
        units_sold_30d=_required_number(product_input, "units_sold_30d", "base_demand"),
        competitor_price=_optional_number(product_input, "competitor_price"),
        scenario=str(_first_value(product_input, "scenario") or "NORMAL").upper(),
        elasticity_override=_optional_elasticity(product_input),
        return_rate_override=_optional_number(
            product_input,
            "return_rate_override",
            "return_rate",
            percent=True,
        ),
        fixed_cost_allocation_override=_optional_number(
            product_input,
            "fixed_cost_allocation_override",
            "fixed_cost",
        ),
        target_margin_override=_optional_number(
            product_input,
            "target_margin_override",
            "desired_margin",
            percent=True,
        ),
        marketing_factor_override=_optional_number(product_input, "marketing_factor_override"),
        inventory_constraint_override=_optional_number(
            product_input,
            "inventory_constraint_override",
            "inventory",
            integer=True,
        ),
    )


def _strategy_projection(strategy):
    return {
        "strategy": strategy["strategy"],
        "price": strategy["price"],
        "demand": strategy["demand"],
        "revenue": strategy["revenue"],
        "variable_cost": strategy["variable_cost"],
        "total_cost": strategy["total_cost"],
        "profit": strategy["profit"],
        "profit_margin": strategy["profit_margin"],
        "break_even_quantity": strategy["break_even_units"],
        "risk_level": strategy["risk_level"],
        "risk_score": strategy["risk_score"],
    }


def _analysis_summary(analysis):
    best = analysis["best_strategy"]
    return {
        "current_price": analysis["product"]["current_price"],
        "candidate_prices": analysis["price_profit_curve"],
        "optimal_price": best["price"],
        "expected_quantity": best["demand"],
        "expected_revenue": best["revenue"],
        "expected_profit": best["profit"],
        "expected_total_cost": best["total_cost"],
        "expected_variable_cost": best["variable_cost"],
        "profit_margin": best["profit_margin"],
        "break_even_quantity": best["break_even_units"],
        "strategy_comparison": [
            _strategy_projection(strategy)
            for strategy in analysis["strategies"]
        ],
        "chart_data": {
            "price_profit_curve": analysis["price_profit_curve"],
        },
    }


def analyze_product(product_input, options=None):
    """Analyze one product and return the full UI-compatible pricing result.

    `product_input` may be a ProductData instance or a mapping with the canonical
    product fields. The returned dictionary preserves the existing
    `run_full_analysis` shape and adds `analysis_summary` for future bulk usage.
    """
    product = normalize_product_input(product_input)
    result = run_full_analysis(product, price_bounds=_analysis_price_bounds(product_input, options))
    result["analysis_summary"] = _analysis_summary(result)
    return result


def compare_product_scenarios(product_input, options=None):
    product = normalize_product_input(product_input)
    return compare_all_scenarios(product, price_bounds=_analysis_price_bounds(product_input, options))
