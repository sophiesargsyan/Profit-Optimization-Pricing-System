from __future__ import annotations

from collections.abc import Mapping

from financial_formatting import format_armenian_dram_value


PLANNER_NAME = "Smart Budget Planner"
PLANNER_NAME_HY = "Խելացի բյուջեի պլանավորում"

INPUT_LABELS = {
    "available_capital": "Հասանելի կապիտալ",
    "organization_type": "Կազմակերպության տեսակ",
    "business_activity": "Գործունեության ոլորտ",
    "business_status": "Բիզնեսի ընթացիկ վիճակ",
    "business_goal": "Բիզնեսի առաջնահերթ նպատակ",
    "average_monthly_revenue": "Վերջին ամիսների միջին եկամուտ",
    "fixed_costs": "Ամսական ֆիքսված ծախսեր",
    "variable_costs": "Փոփոխական ծախսեր",
    "employees_count": "Աշխատակիցների քանակ",
}

ORGANIZATION_TYPE_OPTIONS = ("ԱՁ", "ՍՊԸ", "ՓԲԸ", "ԲԲԸ", "Այլ")
BUSINESS_ACTIVITY_OPTIONS = (
    "Օնլայն խանութ",
    "Ձեռագործ արտադրանք",
    "Ծառայություններ",
    "Մանրածախ առևտուր",
    "Այլ",
)
BUSINESS_STATUS_OPTIONS = ("Նոր բիզնես", "Գործող բիզնես")
BUSINESS_GOAL_OPTIONS = ("Աճ", "Կայունություն", "Գոյատևում", "Հավասարակշռված զարգացում")

ALLOCATION_ORDER = (
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
)

ALLOCATION_LABELS = {
    "tax_reserve": "Հարկային պահուստ",
    "payroll_admin_reserve": "Աշխատավարձային/վարչական պահուստ",
    "fixed_costs_coverage": "Ֆիքսված ծախսերի ծածկում",
    "variable_costs_coverage": "Փոփոխական ծախսերի ծածկում",
    "marketing_budget": "Մարքեթինգ",
    "inventory_or_purchase_budget": "Ապրանքների ձեռքբերում / պաշար",
    "operational_budget": "Օպերացիոն բյուջե",
    "emergency_reserve": "Արտակարգ պահուստ",
    "reinvestment_budget": "Վերաներդրման բյուջե",
    "free_cash": "Ազատ դրամական մնացորդ",
}

ORGANIZATION_TYPE_COEFFICIENTS = {
    "ԱՁ": {
        "tax_rate": 0.06,
        "payroll_admin_base_rate": 0.04,
        "payroll_admin_per_employee_rate": 0.007,
        "emergency_reserve_ratio": 0.10,
        "emergency_months": 1.0,
        "fixed_cost_coverage_months": 1.2,
        "default_fixed_cost_ratio": 0.12,
    },
    "ՍՊԸ": {
        "tax_rate": 0.10,
        "payroll_admin_base_rate": 0.06,
        "payroll_admin_per_employee_rate": 0.008,
        "emergency_reserve_ratio": 0.12,
        "emergency_months": 1.25,
        "fixed_cost_coverage_months": 1.35,
        "default_fixed_cost_ratio": 0.14,
    },
    "ՓԲԸ": {
        "tax_rate": 0.12,
        "payroll_admin_base_rate": 0.075,
        "payroll_admin_per_employee_rate": 0.009,
        "emergency_reserve_ratio": 0.14,
        "emergency_months": 1.4,
        "fixed_cost_coverage_months": 1.5,
        "default_fixed_cost_ratio": 0.16,
    },
    "ԲԲԸ": {
        "tax_rate": 0.14,
        "payroll_admin_base_rate": 0.085,
        "payroll_admin_per_employee_rate": 0.010,
        "emergency_reserve_ratio": 0.15,
        "emergency_months": 1.5,
        "fixed_cost_coverage_months": 1.6,
        "default_fixed_cost_ratio": 0.18,
    },
    "Այլ": {
        "tax_rate": 0.09,
        "payroll_admin_base_rate": 0.055,
        "payroll_admin_per_employee_rate": 0.008,
        "emergency_reserve_ratio": 0.12,
        "emergency_months": 1.2,
        "fixed_cost_coverage_months": 1.3,
        "default_fixed_cost_ratio": 0.14,
    },
}

BUSINESS_ACTIVITY_PROFILES = {
    "Օնլայն խանութ": {
        "capital_turnover": 1.55,
        "fixed_cost_ratio": 0.12,
        "variable_cost_ratio": 0.38,
        "payroll_admin_bias": 0.00,
        "revenue_bias": 1.05,
    },
    "Ձեռագործ արտադրանք": {
        "capital_turnover": 1.25,
        "fixed_cost_ratio": 0.11,
        "variable_cost_ratio": 0.34,
        "payroll_admin_bias": 0.01,
        "revenue_bias": 0.97,
    },
    "Ծառայություններ": {
        "capital_turnover": 1.35,
        "fixed_cost_ratio": 0.14,
        "variable_cost_ratio": 0.22,
        "payroll_admin_bias": 0.03,
        "revenue_bias": 1.00,
    },
    "Մանրածախ առևտուր": {
        "capital_turnover": 1.45,
        "fixed_cost_ratio": 0.13,
        "variable_cost_ratio": 0.42,
        "payroll_admin_bias": 0.01,
        "revenue_bias": 1.02,
    },
    "Այլ": {
        "capital_turnover": 1.30,
        "fixed_cost_ratio": 0.12,
        "variable_cost_ratio": 0.30,
        "payroll_admin_bias": 0.01,
        "revenue_bias": 1.00,
    },
}

BASE_PERCENTAGE_WEIGHTS = {
    "variable_costs_coverage": 0.18,
    "marketing_budget": 0.12,
    "inventory_or_purchase_budget": 0.18,
    "operational_budget": 0.15,
    "emergency_reserve": 0.14,
    "reinvestment_budget": 0.11,
    "free_cash": 0.12,
}

GOAL_ALLOCATION_MULTIPLIERS = {
    "Աճ": {
        "variable_costs_coverage": 1.05,
        "marketing_budget": 1.35,
        "inventory_or_purchase_budget": 1.25,
        "operational_budget": 1.00,
        "emergency_reserve": 0.85,
        "reinvestment_budget": 1.40,
        "free_cash": 0.80,
    },
    "Կայունություն": {
        "variable_costs_coverage": 1.00,
        "marketing_budget": 0.85,
        "inventory_or_purchase_budget": 0.95,
        "operational_budget": 1.20,
        "emergency_reserve": 1.25,
        "reinvestment_budget": 0.80,
        "free_cash": 1.10,
    },
    "Գոյատևում": {
        "variable_costs_coverage": 1.10,
        "marketing_budget": 0.35,
        "inventory_or_purchase_budget": 0.80,
        "operational_budget": 0.90,
        "emergency_reserve": 1.35,
        "reinvestment_budget": 0.30,
        "free_cash": 1.20,
    },
    "Հավասարակշռված զարգացում": {
        "variable_costs_coverage": 1.00,
        "marketing_budget": 1.00,
        "inventory_or_purchase_budget": 1.00,
        "operational_budget": 1.05,
        "emergency_reserve": 1.05,
        "reinvestment_budget": 1.00,
        "free_cash": 1.00,
    },
}

ACTIVITY_ALLOCATION_MULTIPLIERS = {
    "Օնլայն խանութ": {
        "variable_costs_coverage": 1.00,
        "marketing_budget": 1.25,
        "inventory_or_purchase_budget": 1.25,
        "operational_budget": 0.95,
        "emergency_reserve": 1.00,
        "reinvestment_budget": 1.00,
        "free_cash": 0.95,
    },
    "Ձեռագործ արտադրանք": {
        "variable_costs_coverage": 1.15,
        "marketing_budget": 0.90,
        "inventory_or_purchase_budget": 1.30,
        "operational_budget": 1.10,
        "emergency_reserve": 1.00,
        "reinvestment_budget": 0.95,
        "free_cash": 0.90,
    },
    "Ծառայություններ": {
        "variable_costs_coverage": 0.85,
        "marketing_budget": 0.85,
        "inventory_or_purchase_budget": 0.45,
        "operational_budget": 1.30,
        "emergency_reserve": 1.05,
        "reinvestment_budget": 1.00,
        "free_cash": 1.05,
    },
    "Մանրածախ առևտուր": {
        "variable_costs_coverage": 1.10,
        "marketing_budget": 0.95,
        "inventory_or_purchase_budget": 1.35,
        "operational_budget": 1.15,
        "emergency_reserve": 0.95,
        "reinvestment_budget": 0.95,
        "free_cash": 0.90,
    },
    "Այլ": {
        "variable_costs_coverage": 1.00,
        "marketing_budget": 1.00,
        "inventory_or_purchase_budget": 0.95,
        "operational_budget": 1.05,
        "emergency_reserve": 1.00,
        "reinvestment_budget": 1.00,
        "free_cash": 1.00,
    },
}

BUSINESS_STATUS_PROFILES = {
    "Նոր բիզնես": {
        "revenue_factor": 0.90,
        "fixed_cost_buffer_multiplier": 1.15,
    },
    "Գործող բիզնես": {
        "revenue_factor": 1.00,
        "fixed_cost_buffer_multiplier": 1.00,
    },
}

GOAL_REVENUE_MULTIPLIERS = {
    "Աճ": 1.08,
    "Կայունություն": 0.98,
    "Գոյատևում": 0.90,
    "Հավասարակշռված զարգացում": 1.00,
}

SCENARIO_DEFINITIONS = (
    {
        "key": "minimum_growth",
        "scenario_name": "Նվազագույն աճի սցենար",
        "revenue_multiplier": 0.92,
        "marketing_usage": 0.55,
        "inventory_usage": 0.62,
        "reinvestment_usage": 0.20,
        "risk_delta": -6,
    },
    {
        "key": "stable_growth",
        "scenario_name": "Կայուն զարգացման սցենար",
        "revenue_multiplier": 1.03,
        "marketing_usage": 0.75,
        "inventory_usage": 0.78,
        "reinvestment_usage": 0.35,
        "risk_delta": 0,
    },
    {
        "key": "rapid_growth",
        "scenario_name": "Արագ աճի սցենար",
        "revenue_multiplier": 1.20,
        "marketing_usage": 0.95,
        "inventory_usage": 0.92,
        "reinvestment_usage": 0.55,
        "risk_delta": 12,
    },
)


def _round_amount(value):
    return round(float(value), 2)


def _field_error(field_name, message):
    return f"{INPUT_LABELS[field_name]} {message}"


def _required_text(source, field_name):
    value = str(source.get(field_name, "") or "").strip()
    if not value:
        raise ValueError(_field_error(field_name, "դաշտը պարտադիր է։"))
    return value


def _parse_amount(value, field_name, *, positive=False):
    if value in (None, ""):
        return None

    normalized_value = str(value).strip().replace(" ", "")
    if "," in normalized_value and "." not in normalized_value:
        normalized_value = normalized_value.replace(",", ".")
    else:
        normalized_value = normalized_value.replace(",", "")

    try:
        amount = float(normalized_value)
    except ValueError as exc:
        raise ValueError(_field_error(field_name, "պետք է լինի վավեր թիվ։")) from exc

    if positive and amount <= 0:
        raise ValueError(_field_error(field_name, "պետք է լինի 0-ից մեծ։"))
    if not positive and amount < 0:
        raise ValueError(_field_error(field_name, "չպետք է լինի բացասական։"))
    return float(amount)


def _parse_employees_count(value):
    if value in (None, ""):
        return 0

    normalized_value = str(value).strip()
    try:
        numeric = float(normalized_value)
    except ValueError as exc:
        raise ValueError(_field_error("employees_count", "պետք է լինի ամբողջ թիվ։")) from exc

    if numeric < 0 or not numeric.is_integer():
        raise ValueError(_field_error("employees_count", "պետք է լինի 0 կամ դրական ամբողջ թիվ։"))
    return int(numeric)


def _required_choice(source, field_name, options):
    value = _required_text(source, field_name)
    if value not in options:
        raise ValueError(
            _field_error(field_name, f"պետք է լինի հետևյալ տարբերակներից մեկը՝ {', '.join(options)}։")
        )
    return value


def _normalize_input(input_data):
    if not isinstance(input_data, Mapping):
        raise ValueError("Մուտքային տվյալները պետք է լինեն բառարանային կառուցվածքով։")

    normalized = {
        "available_capital": _parse_amount(input_data.get("available_capital"), "available_capital", positive=True),
        "organization_type": _required_choice(input_data, "organization_type", ORGANIZATION_TYPE_OPTIONS),
        "business_activity": _required_choice(input_data, "business_activity", BUSINESS_ACTIVITY_OPTIONS),
        "business_status": _required_choice(input_data, "business_status", BUSINESS_STATUS_OPTIONS),
        "business_goal": _required_choice(input_data, "business_goal", BUSINESS_GOAL_OPTIONS),
        "average_monthly_revenue": _parse_amount(
            input_data.get("average_monthly_revenue"),
            "average_monthly_revenue",
        ),
        "fixed_costs": _parse_amount(input_data.get("fixed_costs"), "fixed_costs"),
        "variable_costs": _parse_amount(input_data.get("variable_costs"), "variable_costs"),
        "employees_count": _parse_employees_count(input_data.get("employees_count")),
    }
    return normalized


def _estimate_revenue(values, activity_profile, status_profile):
    if values["average_monthly_revenue"] is not None:
        return values["average_monthly_revenue"], "provided_average_monthly_revenue"

    estimated = (
        values["available_capital"]
        * activity_profile["capital_turnover"]
        * status_profile["revenue_factor"]
    )
    return _round_amount(estimated), "estimated_from_capital_profile"


def _estimate_fixed_costs(values, base_revenue, org_coeffs, activity_profile):
    if values["fixed_costs"] is not None:
        return values["fixed_costs"], "provided_fixed_costs"

    estimate = max(
        values["available_capital"] * org_coeffs["default_fixed_cost_ratio"],
        base_revenue * activity_profile["fixed_cost_ratio"],
    )
    return _round_amount(estimate), "estimated_fixed_costs"


def _estimate_variable_costs(values, base_revenue, activity_profile):
    if values["variable_costs"] is not None:
        return values["variable_costs"], "provided_variable_costs"

    estimate = base_revenue * activity_profile["variable_cost_ratio"]
    return _round_amount(estimate), "estimated_variable_costs"


def _recommended_tax_reserve(available_capital, base_revenue, org_coeffs):
    return _round_amount(
        max(
            available_capital * org_coeffs["tax_rate"],
            base_revenue * org_coeffs["tax_rate"] * 0.25,
        )
    )


def _recommended_payroll_admin_reserve(values, available_capital, org_coeffs, activity_profile):
    effective_rate = (
        org_coeffs["payroll_admin_base_rate"]
        + (values["employees_count"] * org_coeffs["payroll_admin_per_employee_rate"])
        + activity_profile["payroll_admin_bias"]
    )
    return _round_amount(available_capital * min(effective_rate, 0.30))


def _recommended_fixed_cost_coverage(monthly_fixed_costs, org_coeffs, status_profile):
    return _round_amount(
        monthly_fixed_costs
        * org_coeffs["fixed_cost_coverage_months"]
        * status_profile["fixed_cost_buffer_multiplier"]
    )


def _recommended_emergency_reserve(available_capital, monthly_fixed_costs, monthly_variable_costs, org_coeffs):
    return _round_amount(
        max(
            available_capital * org_coeffs["emergency_reserve_ratio"],
            (monthly_fixed_costs + (monthly_variable_costs * 0.15))
            * org_coeffs["emergency_months"]
            * 0.70,
        )
    )


def _apply_multipliers(distribution, multipliers):
    total = sum(distribution.values())
    if total <= 0:
        return {key: 0.0 for key in distribution}

    adjusted = {
        key: max(distribution[key] * multipliers.get(key, 1.0), 0.0)
        for key in distribution
    }
    adjusted_total = sum(adjusted.values())
    if adjusted_total <= 0:
        return {key: 0.0 for key in distribution}

    scaling_factor = total / adjusted_total
    return {key: adjusted[key] * scaling_factor for key in adjusted}


def _round_distribution(distribution, target_total, fallback_key):
    rounded = {key: _round_amount(value) for key, value in distribution.items()}
    difference = _round_amount(target_total - sum(rounded.values()))
    rounded[fallback_key] = _round_amount(rounded.get(fallback_key, 0.0) + difference)
    return rounded


def _risk_label(score):
    if score >= 60:
        return "Բարձր"
    if score >= 35:
        return "Միջին"
    return "Ցածր"


def _sustainability_status(buffer_months, expected_profit, expected_revenue):
    if buffer_months >= 1.25 and expected_profit >= 0:
        return "Կայուն"
    if buffer_months >= 0.75 or expected_profit >= -(expected_revenue * 0.08):
        return "Միջին"
    return "Ռիսկային"


def _recommended_scenario_key(values, overall_risk_level, free_cash, monthly_fixed_costs):
    if values["business_goal"] == "Գոյատևում" or overall_risk_level == "Բարձր":
        return "minimum_growth"
    if (
        values["business_goal"] == "Աճ"
        and free_cash >= values["available_capital"] * 0.08
        and values["available_capital"] >= monthly_fixed_costs * 1.5
        and overall_risk_level != "Բարձր"
    ):
        return "rapid_growth"
    return "stable_growth"


def _allocation_purpose(field_name, values):
    activity = values["business_activity"]
    goal = values["business_goal"]

    if field_name == "tax_reserve":
        return "Հարկային պարտավորությունների ապահովում"
    if field_name == "payroll_admin_reserve":
        if activity == "Ծառայություններ":
            return "Թիմի աշխատանքի և վարչական կայունության ապահովում"
        return "Աշխատավարձերի և վարչական ծախսերի ապահովում"
    if field_name == "fixed_costs_coverage":
        return "Ֆիքսված պարտավորությունների շարունակական ծածկում"
    if field_name == "variable_costs_coverage":
        if activity == "Ձեռագործ արտադրանք":
            return "Նյութերի և արտադրական փոփոխական ծախսերի կառավարում"
        return "Շրջանառու և փոփոխական ծախսերի ֆինանսավորում"
    if field_name == "marketing_budget":
        if activity == "Օնլայն խանութ":
            return "Առցանց հաճախորդների ներգրավում և վաճառքի աճ"
        return "Հաճախորդների ներգրավում և վաճառքի աճ"
    if field_name == "inventory_or_purchase_budget":
        if activity == "Ծառայություններ":
            return "Սպասարկման գործիքների և ընթացիկ ռեսուրսների ապահովում"
        if activity == "Ձեռագործ արտադրանք":
            return "Նյութերի, պաշարների և պատվերների կատարման ապահովում"
        return "Ապրանքների ձեռքբերում և շրջանառու պաշարի ձևավորում"
    if field_name == "operational_budget":
        if activity == "Ծառայություններ":
            return "Սպասարկման որակի և գործառնական կայունության ապահովում"
        return "Գործառնական կայունության և ընթացիկ գործընթացների ապահովում"
    if field_name == "emergency_reserve":
        if goal == "Գոյատևում":
            return "Ֆինանսական ռիսկերի նվազեցում և վճարունակության պահպանում"
        return "Անկանխատեսելի ռիսկերի դեմ ֆինանսական բուֆերի ձևավորում"
    if field_name == "reinvestment_budget":
        if goal == "Աճ":
            return "Բիզնեսի աճի և ընդլայնման ակտիվ ֆինանսավորում"
        return "Բիզնեսի զարգացման և ընդլայնման աջակցություն"
    return "Կարճաժամկետ իրացվելիության և արագ որոշումների պահուստ"


def _fixed_cost_pressure_ratio(monthly_fixed_costs, available_capital):
    if available_capital <= 0:
        return 1.0
    return monthly_fixed_costs / available_capital


def _allocation_balance_score(allocations, available_capital):
    if available_capital <= 0:
        return 0.0

    adaptive_fields = (
        "variable_costs_coverage",
        "marketing_budget",
        "inventory_or_purchase_budget",
        "operational_budget",
        "emergency_reserve",
        "reinvestment_budget",
    )
    shares = [allocations[field_name] / available_capital for field_name in adaptive_fields]
    mean_deviation = sum(abs(share - 0.15) for share in shares) / len(shares)
    deviation_score = max(0.0, 1.0 - (mean_deviation / 0.20))
    concentration_score = max(0.0, 1.0 - (max(shares) - 0.30) / 0.20)
    return min(max((deviation_score * 0.65) + (concentration_score * 0.35), 0.0), 1.0)


def _stability_label(score):
    if score >= 70:
        return "Կայուն"
    if score >= 45:
        return "Միջին"
    return "Ռիսկային"


def _calculate_stability_profile(
    allocations,
    available_capital,
    monthly_fixed_costs,
    recommended_emergency_reserve,
    overall_risk_score,
):
    reserve_ratio = (
        allocations["emergency_reserve"] / recommended_emergency_reserve
        if recommended_emergency_reserve > 0
        else 1.0
    )
    free_cash_ratio = allocations["free_cash"] / available_capital if available_capital else 0.0
    fixed_cost_ratio = _fixed_cost_pressure_ratio(monthly_fixed_costs, available_capital)
    balance_score = _allocation_balance_score(allocations, available_capital)

    reserve_score = min(max(reserve_ratio / 1.2, 0.0), 1.0)
    free_cash_score = min(max((free_cash_ratio + 0.05) / 0.15, 0.0), 1.0)
    fixed_cost_score = min(max(1.0 - max(fixed_cost_ratio - 0.22, 0.0) / 0.45, 0.0), 1.0)
    risk_score_component = min(max(1.0 - (overall_risk_score / 100.0), 0.0), 1.0)

    score = int(
        round(
            (reserve_score * 30)
            + (free_cash_score * 25)
            + (fixed_cost_score * 20)
            + (risk_score_component * 15)
            + (balance_score * 10)
        )
    )
    score = max(0, min(score, 100))
    label = _stability_label(score)

    if reserve_ratio < 1.0:
        reason = "Արտակարգ պահուստը դեռ չի հասնում առաջարկվող շեմին, ուստի կայունությունը սահմանափակ է։"
    elif free_cash_ratio < 0:
        reason = "Ազատ դրամական մնացորդը բացասական է, ինչի պատճառով պլանը բարձր ճնշման տակ է։"
    elif fixed_cost_ratio > 0.45:
        reason = "Ֆիքսված ծախսերի ճնշումը բարձր է և նվազեցնում է բյուջեի ճկունությունը։"
    elif label == "Կայուն":
        reason = "Պահուստների և ազատ դրամական բուֆերի մակարդակը բավարար է վերահսկվող աշխատանքի համար։"
    else:
        reason = "Բյուջեն աշխատունակ է, սակայն պահանջում է պարբերական վերահսկում և ռիսկերի վերագնահատում։"

    return {
        "stability_score": score,
        "stability_label": label,
        "stability_reason": reason,
        "reserve_ratio": reserve_ratio,
        "free_cash_ratio": free_cash_ratio,
        "fixed_cost_ratio": fixed_cost_ratio,
        "allocation_balance_score": balance_score,
    }


def _scenario_goal_bonus(goal, scenario_key):
    bonuses = {
        "Աճ": {"rapid_growth": 6.0, "stable_growth": 3.0, "minimum_growth": 0.0},
        "Կայունություն": {"rapid_growth": 1.5, "stable_growth": 6.0, "minimum_growth": 3.0},
        "Գոյատևում": {"rapid_growth": 0.0, "stable_growth": 2.5, "minimum_growth": 6.0},
        "Հավասարակշռված զարգացում": {"rapid_growth": 2.5, "stable_growth": 5.0, "minimum_growth": 2.5},
    }
    return bonuses.get(goal, {}).get(scenario_key, 0.0)


def _scenario_selection_score(row, goal, max_profit):
    profit_score = 0.0
    if max_profit > 0:
        profit_score = (max(row["expected_profit"], 0.0) / max_profit) * 38.0
    elif row["expected_profit"] >= 0:
        profit_score = 18.0
    if row["expected_profit"] < 0:
        profit_score -= 10.0

    sustainability_points = {
        "Կայուն": 28.0,
        "Միջին": 18.0,
        "Ռիսկային": 8.0,
    }.get(row["sustainability_status"], 12.0)
    risk_points = max(0.0, 24.0 - max(row["risk_score"] - 20, 0) * 0.35)
    buffer_points = min(row["buffer_months"] / 1.5, 1.0) * 8.0
    goal_bonus = _scenario_goal_bonus(goal, row["scenario_key"])
    return round(profit_score + sustainability_points + risk_points + buffer_points + goal_bonus, 2)


def _scenario_selection_reason(row, goal):
    if row["scenario_key"] == "minimum_growth":
        if goal == "Գոյատևում" or row["risk_level"] == "Բարձր":
            return "Լավագույն հավասարակշռությունը իրացվելիության պահպանման և ռիսկի նվազեցման միջև"
        return "Առաջարկվող սցենար՝ ծախսերի զսպվածության և կանխիկ հոսքի պահպանման համար"
    if row["scenario_key"] == "rapid_growth":
        if row["buffer_months"] >= 1.0 and row["expected_profit"] > 0:
            return "Առաջարկվող սցենար՝ բարձր շահութաբերության և բավարար պահուստի համադրության համար"
        return "Ընտրվել է աճի ավելի բարձր ներուժի պատճառով, սակայն պահանջում է խիստ վերահսկում"
    if goal == "Կայունություն":
        return "Առաջարկվող սցենար՝ կանխատեսելի շահույթի և վերահսկվող ռիսկի համար"
    return "Առաջարկվող սցենար՝ կայուն աճի և վերահսկվող ռիսկի համար"


def _select_recommended_scenario(
    scenario_rows,
    goal,
    overall_risk_level,
    free_cash,
    available_capital,
):
    max_profit = max((row["expected_profit"] for row in scenario_rows), default=0.0)
    for row in scenario_rows:
        row["selection_score"] = _scenario_selection_score(row, goal, max_profit)
        row["selection_reason"] = _scenario_selection_reason(row, goal)

    candidate_rows = list(scenario_rows)
    if goal == "Գոյատևում" or overall_risk_level == "Բարձր" or free_cash < 0:
        candidate_rows = [row for row in scenario_rows if row["scenario_key"] != "rapid_growth"]
    elif goal == "Աճ" and free_cash < (available_capital * 0.05):
        candidate_rows = [row for row in scenario_rows if row["scenario_key"] != "rapid_growth"]

    return max(
        candidate_rows,
        key=lambda row: (
            row["selection_score"],
            row["expected_profit"],
            row["buffer_months"],
            -row["risk_score"],
        ),
    )


def _build_warnings(values, allocations, monthly_fixed_costs, recommended_emergency_reserve, tax_reserve_target):
    warnings = []
    available_capital = values["available_capital"]
    free_cash = allocations["free_cash"]

    if available_capital < monthly_fixed_costs:
        warnings.append(
            {
                "code": "capital_below_fixed_costs",
                "level": "warning",
                "message": "Հասանելի կապիտալը պակաս է ամսական ֆիքսված ծախսերից։",
            }
        )

    if free_cash < 0:
        warnings.append(
            {
                "code": "negative_free_cash",
                "level": "warning",
                "message": "Պլանավորված բյուջեն գերազանցում է հասանելի կապիտալը, և ազատ դրամական մնացորդը բացասական է։",
            }
        )

    if allocations["emergency_reserve"] < recommended_emergency_reserve:
        warnings.append(
            {
                "code": "low_emergency_reserve",
                "level": "warning",
                "message": "Արտակարգ պահուստը ցածր է առաջարկվող նվազագույն մակարդակից։",
            }
        )

    if available_capital < (tax_reserve_target + allocations["fixed_costs_coverage"] + recommended_emergency_reserve):
        warnings.append(
            {
                "code": "weak_tax_reserve_formation",
                "level": "warning",
                "message": "Հարկային պահուստը ձևավորվում է թույլ բուֆերով և պահանջում է լրացուցիչ վերահսկում։",
            }
        )

    if (
        values["business_goal"] == "Աճ"
        and (available_capital < monthly_fixed_costs * 1.5 or free_cash < available_capital * 0.05)
    ):
        warnings.append(
            {
                "code": "growth_goal_high_risk",
                "level": "warning",
                "message": "Ընտրված աճի նպատակը բարձր ռիսկային է, քանի որ կապիտալի պահուստը սահմանափակ է։",
            }
        )

    if monthly_fixed_costs > available_capital * 0.45:
        warnings.append(
            {
                "code": "fixed_cost_pressure",
                "level": "warning",
                "message": "Ֆիքսված ծախսերը չափազանց բարձր են հասանելի կապիտալի համեմատ։",
            }
        )

    return warnings


def _build_recommendations(
    values,
    allocations,
    monthly_fixed_costs,
    recommended_emergency_reserve,
    overall_risk_level,
    stability_profile,
):
    recommendations = []
    goal = values["business_goal"]
    activity = values["business_activity"]
    status = values["business_status"]
    available_capital = values["available_capital"]
    free_cash = allocations["free_cash"]
    free_cash_ratio = stability_profile["free_cash_ratio"]
    reserve_ratio = stability_profile["reserve_ratio"]
    fixed_cost_ratio = stability_profile["fixed_cost_ratio"]

    if goal == "Աճ":
        recommendations.append(
            "Համակարգը մեծացնում է վերաներդրման և մարքեթինգային բյուջեն՝ բիզնեսի աճի արագացման նպատակով, քանի որ ընտրված նպատակը պահանջում է պահանջարկի և վաճառքի ակտիվ խթանում։"
        )
    elif goal == "Կայունություն":
        recommendations.append(
            "Համակարգը մեծացնում է արտակարգ և օպերացիոն բյուջեի մասնաբաժինը, որպեսզի բիզնեսը պահպանի կանխատեսելի աշխատանքային ռիթմ և ֆինանսական բուֆեր։"
        )
    elif goal == "Գոյատևում":
        recommendations.append(
            "Գոյատևման նպատակի դեպքում համակարգը բարձրացնում է հարկային, ֆիքսված ծախսերի և արտակարգ պահուստների մասնաբաժինը, իսկ մարքեթինգն ու վերաներդրումը սահմանափակում է։"
        )
    else:
        recommendations.append(
            "Հավասարակշռված զարգացման համար բաշխումը պահում է աճային ուղղությունները ակտիվ, բայց միաժամանակ պահպանում է ռիսկերը մեղմող պահուստներ։"
        )

    if activity == "Օնլայն խանութ":
        recommendations.append(
            "Օնլայն խանութի համար համակարգը մեծացնում է մարքեթինգի և պաշարների բյուջեն, քանի որ վաճառքը կախված է ինչպես ներգրավումից, այնպես էլ արագ համալրումից։"
        )
    elif activity == "Ծառայություններ":
        recommendations.append(
            "Ծառայությունների ոլորտի համար համակարգը մեծացնում է աշխատավարձային և օպերացիոն բյուջեի մասնաբաժինը, որովհետև սպասարկման որակը հիմնվում է թիմի և ընթացիկ գործընթացների վրա։"
        )
    elif activity == "Ձեռագործ արտադրանք":
        recommendations.append(
            "Ձեռագործ արտադրանքի դեպքում համակարգը ուժեղացնում է նյութերի և օպերացիոն ծախսերի բյուջեն, որպեսզի պատվերների կատարումը չխաթարվի արտադրական ցիկլով։"
        )
    elif activity == "Մանրածախ առևտուր":
        recommendations.append(
            "Մանրածախ առևտրի համար բարձրացվում է գնման և օպերացիոն բյուջեի մասնաբաժինը, քանի որ հասանելի պաշարն ու կետային աշխատանքը անմիջապես ազդում են վաճառքի վրա։"
        )

    if status == "Նոր բիզնես":
        recommendations.append(
            "Նոր բիզնեսի համար սցենարները հաշվարկվում են գնահատողական գործակիցներով, ուստի առաջին ամիսների փաստացի վաճառքից հետո ցանկալի է վերաթարմացնել պլանը։"
        )
    elif values["average_monthly_revenue"] is not None:
        recommendations.append(
            "Գործող բիզնեսի դեպքում սցենարային հաշվարկը հենված է մուտքագրված միջին ամսական եկամտի վրա, ինչի շնորհիվ շահույթի և ռիսկի պատկերը դառնում է ավելի իրատեսական։"
        )
    else:
        recommendations.append(
            "Քանի որ գործող բիզնեսի միջին եկամուտը չի տրամադրվել, սցենարային գնահատումը պահպանողական է և կարող է թարմացվել փաստացի եկամուտների հիմքով։"
        )

    if reserve_ratio < 1.0:
        recommendations.append(
            "Արտակարգ պահուստը ցածր է առաջարկվող մակարդակից, ինչը կարող է բարձրացնել ֆինանսական ռիսկերը և սահմանափակել արագ արձագանքը ծախսային շոկերին։"
        )
    elif reserve_ratio >= 1.2:
        recommendations.append(
            "Արտակարգ պահուստը ձևավորվել է առաջարկվող շեմից բարձր, ինչը բարելավում է անսպասելի ծախսերը կլանելու կարողությունը։"
        )

    if free_cash < 0:
        recommendations.append(
            f"Ազատ դրամական մնացորդը դարձել է {format_armenian_dram_value(free_cash)}, ուստի անհրաժեշտ է կրճատել երկրորդական ծախսերը կամ փուլավորել աճային ուղղությունները։"
        )
    elif free_cash_ratio < 0.05:
        recommendations.append(
            f"Ազատ դրամական բուֆերը պահպանվում է միայն {format_armenian_dram_value(free_cash)} մակարդակում, ինչը սահմանափակում է ակտիվ աճի ռազմավարության արդյունավետ իրականացումը։"
        )
    else:
        recommendations.append(
            f"Ազատ դրամական մնացորդը {format_armenian_dram_value(free_cash)} է, ինչը ստեղծում է հավելյալ ճկունություն ընթացիկ բյուջեի կառավարման համար։"
        )

    if fixed_cost_ratio > 0.45:
        recommendations.append(
            "Ֆիքսված ծախսերի ծանրաբեռնվածությունը բարձր է հասանելի կապիտալի համեմատ, ուստի համակարգը խիստ զգուշորեն է պահում աճային ուղղությունների բաշխումը։"
        )
    elif fixed_cost_ratio > 0.30:
        recommendations.append(
            "Ֆիքսված ծախսերը զգալի ճնշում են ստեղծում կապիտալի վրա, և հարկավոր է դրանք համադրել ազատ դրամական բուֆերի հետ ամեն ամսվա վերջում։"
        )

    if overall_risk_level == "Բարձր":
        recommendations.append(
            "Ընդհանուր ռիսկայնությունը բարձր է, ուստի մինչև կայունացման փուլը նպատակահարմար է զսպել վերաներդրումը և պահել ավելի մեծ արտակարգ պահուստ։"
        )
    elif overall_risk_level == "Միջին":
        recommendations.append(
            "Ռիսկի մակարդակը միջին է, այդ պատճառով պլանը պետք է վերահսկել հատկապես հարկային պահուստի, ֆիքսված ծախսերի և ազատ դրամական բուֆերի տեսանկյունից։"
        )
    elif stability_profile["stability_label"] == "Կայուն":
        recommendations.append(
            "Կայունության գնահատականը բարձր է, ինչը նշանակում է, որ ընթացիկ բաշխումը հնարավոր է պահել առանց կտրուկ վերաձևումների, եթե վաճառքի տեմպը պահպանվի։"
        )

    unique_recommendations = []
    for message in recommendations:
        if message not in unique_recommendations:
            unique_recommendations.append(message)
    return unique_recommendations


def _build_method_notes(revenue_source, fixed_cost_source, variable_cost_source):
    source_labels = {
        "provided_average_monthly_revenue": "օգտատիրոջ մուտքագրած միջին եկամուտ",
        "estimated_from_capital_profile": "կապիտալի և գործունեության պրոֆիլի վրա հիմնված գնահատում",
        "provided_fixed_costs": "օգտատիրոջ մուտքագրած ֆիքսված ծախսեր",
        "estimated_fixed_costs": "գնահատված ֆիքսված ծախսեր",
        "provided_variable_costs": "օգտատիրոջ մուտքագրած փոփոխական ծախսեր",
        "estimated_variable_costs": "գնահատված փոփոխական ծախսեր",
    }
    return [
        "Hybrid budget formation and allocation method",
        "Պլանը համադրում է նորմատիվային, տոկոսային, առաջնահերթային և սցենարային բյուջետավորման տրամաբանությունները։",
        "Կազմակերպության տեսակի գործակիցները կոնֆիգուրացվող են և օգտագործվում են որպես պարզեցված պլանավորման կանոններ, ոչ թե իրավական կամ հարկային խորհրդատվություն։",
        "Հաշվարկների հիմքերն են՝ "
        f"եկամուտ՝ {source_labels.get(revenue_source, revenue_source)}, "
        f"ֆիքսված ծախսեր՝ {source_labels.get(fixed_cost_source, fixed_cost_source)}, "
        f"փոփոխական ծախսեր՝ {source_labels.get(variable_cost_source, variable_cost_source)}։",
    ]


def _allocation_rows(allocations, available_capital, values):
    rows = []
    for field_name in ALLOCATION_ORDER:
        amount = allocations[field_name]
        percentage = _round_amount((amount / available_capital) * 100) if available_capital else 0.0
        if field_name == "free_cash":
            importance_label = "Ֆինանսական ճկունություն"
        elif field_name in {
            "tax_reserve",
            "payroll_admin_reserve",
            "fixed_costs_coverage",
            "emergency_reserve",
        }:
            importance_label = "Պարտադիր և առաջնային"
        else:
            importance_label = "Աջակցող և զարգացնող"
        rows.append(
            {
                "field_name": field_name,
                "label": ALLOCATION_LABELS[field_name],
                "amount": amount,
                "percentage": percentage,
                "priority_type": "normative"
                if field_name in {"tax_reserve", "payroll_admin_reserve", "fixed_costs_coverage", "emergency_reserve"}
                else "adaptive",
                "importance_label": importance_label,
                "purpose_description": _allocation_purpose(field_name, values),
            }
        )
    return rows


def _scenario_rows(
    values,
    allocations,
    base_revenue,
    monthly_fixed_costs,
    monthly_variable_costs,
    org_coeffs,
    activity_profile,
    base_risk_score,
):
    scenario_rows = []
    variable_rate = activity_profile["variable_cost_ratio"]
    if values["average_monthly_revenue"] and values["variable_costs"] is not None and values["average_monthly_revenue"] > 0:
        variable_rate = min(max(values["variable_costs"] / values["average_monthly_revenue"], 0.10), 0.85)

    goal_revenue_multiplier = GOAL_REVENUE_MULTIPLIERS[values["business_goal"]]
    sustainability_buffer = (
        max(allocations["free_cash"], 0.0)
        + allocations["emergency_reserve"]
        + (allocations["fixed_costs_coverage"] * 0.25)
    )

    for scenario in SCENARIO_DEFINITIONS:
        expected_revenue = _round_amount(
            base_revenue
            * goal_revenue_multiplier
            * activity_profile["revenue_bias"]
            * scenario["revenue_multiplier"]
        )
        variable_expense = expected_revenue * variable_rate
        tax_expense = min(allocations["tax_reserve"] * 0.55, expected_revenue * org_coeffs["tax_rate"] * 0.85)
        payroll_expense = allocations["payroll_admin_reserve"] * 0.60
        operational_expense = allocations["operational_budget"] * 0.40
        marketing_expense = allocations["marketing_budget"] * scenario["marketing_usage"]
        inventory_expense = allocations["inventory_or_purchase_budget"] * scenario["inventory_usage"]
        reinvestment_expense = allocations["reinvestment_budget"] * scenario["reinvestment_usage"]

        estimated_expenses = _round_amount(
            monthly_fixed_costs
            + variable_expense
            + tax_expense
            + payroll_expense
            + operational_expense
            + marketing_expense
            + inventory_expense
            + reinvestment_expense
        )
        expected_profit = _round_amount(expected_revenue - estimated_expenses)
        buffer_months = sustainability_buffer / estimated_expenses if estimated_expenses > 0 else 0.0

        risk_score = base_risk_score + scenario["risk_delta"]
        if expected_profit < 0:
            risk_score += 20
        elif expected_profit < expected_revenue * 0.08:
            risk_score += 8
        if buffer_months < 0.75:
            risk_score += 12
        elif buffer_months < 1.00:
            risk_score += 6

        scenario_rows.append(
            {
                "scenario_key": scenario["key"],
                "scenario_name": scenario["scenario_name"],
                "expected_revenue": expected_revenue,
                "estimated_expenses": estimated_expenses,
                "expected_profit": expected_profit,
                "risk_level": _risk_label(risk_score),
                "risk_score": int(round(risk_score)),
                "sustainability_status": _sustainability_status(
                    buffer_months,
                    expected_profit,
                    expected_revenue,
                ),
                "buffer_months": _round_amount(buffer_months),
            }
        )

    return scenario_rows


def generate_smart_budget_plan(input_data):
    """Build a Smart Budget Planner result using a hybrid allocation model.

    The planner uses a “Hybrid budget formation and allocation method”.
    """

    values = _normalize_input(input_data)
    org_coeffs = ORGANIZATION_TYPE_COEFFICIENTS[values["organization_type"]]
    activity_profile = BUSINESS_ACTIVITY_PROFILES[values["business_activity"]]
    status_profile = BUSINESS_STATUS_PROFILES[values["business_status"]]

    base_revenue, revenue_source = _estimate_revenue(values, activity_profile, status_profile)
    monthly_fixed_costs, fixed_cost_source = _estimate_fixed_costs(
        values,
        base_revenue,
        org_coeffs,
        activity_profile,
    )
    monthly_variable_costs, variable_cost_source = _estimate_variable_costs(
        values,
        base_revenue,
        activity_profile,
    )

    available_capital = values["available_capital"]

    # Hybrid budget formation and allocation method:
    # apply normative reserves first, then percentage distribution, then
    # goal-specific and activity-specific rebalancing.
    tax_reserve = _recommended_tax_reserve(available_capital, base_revenue, org_coeffs)
    payroll_admin_reserve = _recommended_payroll_admin_reserve(
        values,
        available_capital,
        org_coeffs,
        activity_profile,
    )
    fixed_costs_coverage = _recommended_fixed_cost_coverage(
        monthly_fixed_costs,
        org_coeffs,
        status_profile,
    )
    emergency_reserve_min = _recommended_emergency_reserve(
        available_capital,
        monthly_fixed_costs,
        monthly_variable_costs,
        org_coeffs,
    )

    normative_allocations = {
        "tax_reserve": tax_reserve,
        "payroll_admin_reserve": payroll_admin_reserve,
        "fixed_costs_coverage": fixed_costs_coverage,
        "emergency_reserve": emergency_reserve_min,
    }
    normative_total = sum(normative_allocations.values())
    remaining_capital = available_capital - normative_total

    base_distribution = {
        field_name: max(remaining_capital, 0.0) * weight
        for field_name, weight in BASE_PERCENTAGE_WEIGHTS.items()
    }
    goal_distribution = _apply_multipliers(
        base_distribution,
        GOAL_ALLOCATION_MULTIPLIERS[values["business_goal"]],
    )
    activity_distribution = _apply_multipliers(
        goal_distribution,
        ACTIVITY_ALLOCATION_MULTIPLIERS[values["business_activity"]],
    )
    adaptive_allocations = _round_distribution(
        activity_distribution,
        max(remaining_capital, 0.0),
        "free_cash",
    )

    allocations = {
        "tax_reserve": tax_reserve,
        "payroll_admin_reserve": payroll_admin_reserve,
        "fixed_costs_coverage": fixed_costs_coverage,
        "variable_costs_coverage": adaptive_allocations.get("variable_costs_coverage", 0.0),
        "marketing_budget": adaptive_allocations.get("marketing_budget", 0.0),
        "inventory_or_purchase_budget": adaptive_allocations.get("inventory_or_purchase_budget", 0.0),
        "operational_budget": adaptive_allocations.get("operational_budget", 0.0),
        "emergency_reserve": _round_amount(
            emergency_reserve_min + adaptive_allocations.get("emergency_reserve", 0.0)
        ),
        "reinvestment_budget": adaptive_allocations.get("reinvestment_budget", 0.0),
        "free_cash": adaptive_allocations.get("free_cash", 0.0) if remaining_capital >= 0 else _round_amount(remaining_capital),
    }

    total_allocated = _round_amount(
        sum(amount for field_name, amount in allocations.items() if field_name != "free_cash")
    )
    free_cash = _round_amount(available_capital - total_allocated)
    allocations["free_cash"] = free_cash

    base_risk_score = 15
    if monthly_fixed_costs > available_capital:
        base_risk_score += 20
    elif monthly_fixed_costs > available_capital * 0.50:
        base_risk_score += 14
    elif monthly_fixed_costs > available_capital * 0.30:
        base_risk_score += 8
    if allocations["emergency_reserve"] < emergency_reserve_min:
        base_risk_score += 15
    if free_cash < 0:
        base_risk_score += 22
    elif free_cash < available_capital * 0.05:
        base_risk_score += 8
    if values["business_goal"] == "Աճ" and available_capital < monthly_fixed_costs * 1.5:
        base_risk_score += 15
    if values["business_status"] == "Գործող բիզնես" and values["average_monthly_revenue"] is None:
        base_risk_score += 8
    if available_capital < tax_reserve + fixed_costs_coverage + emergency_reserve_min:
        base_risk_score += 10

    warnings = _build_warnings(
        values,
        allocations,
        monthly_fixed_costs,
        emergency_reserve_min,
        tax_reserve,
    )
    scenario_rows = _scenario_rows(
        values,
        allocations,
        base_revenue,
        monthly_fixed_costs,
        monthly_variable_costs,
        org_coeffs,
        activity_profile,
        base_risk_score,
    )

    overall_risk_score = max(
        int(round(base_risk_score)),
        max((row["risk_score"] for row in scenario_rows), default=int(round(base_risk_score))),
    )
    overall_risk_level = _risk_label(overall_risk_score)
    stability_profile = _calculate_stability_profile(
        allocations,
        available_capital,
        monthly_fixed_costs,
        emergency_reserve_min,
        overall_risk_score,
    )
    recommended_scenario = _select_recommended_scenario(
        scenario_rows,
        values["business_goal"],
        overall_risk_level,
        free_cash,
        available_capital,
    )
    for row in scenario_rows:
        row["is_recommended"] = row["scenario_key"] == recommended_scenario["scenario_key"]

    recommendations = _build_recommendations(
        values,
        allocations,
        monthly_fixed_costs,
        emergency_reserve_min,
        overall_risk_level,
        stability_profile,
    )
    allocation_rows = _allocation_rows(allocations, available_capital, values)
    method_notes = _build_method_notes(revenue_source, fixed_cost_source, variable_cost_source)

    output_values = dict(values)
    output_values.update({field_name: allocations[field_name] for field_name in ALLOCATION_ORDER})

    return {
        "values": output_values,
        "summary": {
            "planner_name": PLANNER_NAME,
            "planner_name_hy": PLANNER_NAME_HY,
            "method": "Hybrid budget formation and allocation method",
            "available_capital": _round_amount(available_capital),
            "total_allocated": total_allocated,
            "free_cash": free_cash,
            "estimated_average_monthly_revenue": _round_amount(base_revenue),
            "estimated_fixed_costs": _round_amount(monthly_fixed_costs),
            "estimated_variable_costs": _round_amount(monthly_variable_costs),
            "revenue_source": revenue_source,
            "recommended_emergency_reserve": _round_amount(emergency_reserve_min),
            "overall_risk_level": overall_risk_level,
            "overall_risk_score": overall_risk_score,
            "sustainability_status": recommended_scenario["sustainability_status"],
            "stability_label": stability_profile["stability_label"],
            "stability_score": stability_profile["stability_score"],
            "stability_reason": stability_profile["stability_reason"],
            "recommended_scenario": recommended_scenario["scenario_name"],
            "recommended_scenario_reason": recommended_scenario["selection_reason"],
        },
        "allocation_rows": allocation_rows,
        "scenario_rows": scenario_rows,
        "warnings": warnings,
        "recommendations": recommendations,
        "method_notes": method_notes,
    }
