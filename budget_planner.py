from __future__ import annotations

from collections.abc import Mapping


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
        return "Սահմանային"
    return "Անբավարար"


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


def _build_recommendations(values, overall_risk_level):
    recommendations = []
    goal = values["business_goal"]
    status = values["business_status"]

    if goal == "Աճ":
        recommendations.append("Աճի պլանը փուլավորիր, որպեսզի մարքեթինգի և գնումների բյուջեն չսպառի աշխատանքային կապիտալը։")
    elif goal == "Կայունություն":
        recommendations.append("Կայունության նպատակի դեպքում պահիր արտակարգ և օպերացիոն բյուջեն առնվազն մեկ ամսվա շեմին մոտ։")
    elif goal == "Գոյատևում":
        recommendations.append("Գոյատևման փուլում կենտրոնացիր հարկային, ֆիքսված և արտակարգ պահուստների վրա, իսկ աճային ծախսերը նվազեցրու։")
    else:
        recommendations.append("Հավասարակշռված զարգացման համար ամեն ամիս վերանայիր բյուջեի բաշխումը և պահիր ազատ դրամական բուֆեր։")

    if status == "Նոր բիզնես":
        recommendations.append("Նոր բիզնեսի համար պլանը հիմնված է գնահատողական գործակիցների վրա, ուստի առաջին ամիսներին թարմացրու այն փաստացի տվյալներով։")
    elif values["average_monthly_revenue"] is not None:
        recommendations.append("Գործող բիզնեսի դեպքում համադրիր պլանը միջին ամսական եկամտի փաստացի դինամիկայի հետ։")
    else:
        recommendations.append("Գործող բիզնեսի համար ավելացրու միջին ամսական եկամուտը, որպեսզի սցենարային հաշվարկներն ավելի ճշգրիտ լինեն։")

    if overall_risk_level == "Բարձր":
        recommendations.append("Մինչև ռիսկի նվազեցումը սահմանափակիր վերաներդրումները և ավելացրու ազատ դրամական կամ արտակարգ բուֆերը։")
    elif overall_risk_level == "Միջին":
        recommendations.append("Վերահսկիր ֆիքսված ծախսերի և հարկային պահուստի հարաբերակցությունը ամեն ամսվա վերջում։")
    else:
        recommendations.append("Պահպանիր ընթացիկ բաշխման կարգապահությունը և պարբերաբար վերանայիր հարկային ու արտակարգ պահուստները։")

    return recommendations


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


def _allocation_rows(allocations, available_capital):
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
    recommended_scenario_key = _recommended_scenario_key(
        values,
        overall_risk_level,
        free_cash,
        monthly_fixed_costs,
    )

    recommended_scenario = next(
        row for row in scenario_rows if row["scenario_key"] == recommended_scenario_key
    )
    for row in scenario_rows:
        row["is_recommended"] = row["scenario_key"] == recommended_scenario_key

    recommendations = _build_recommendations(values, overall_risk_level)
    allocation_rows = _allocation_rows(allocations, available_capital)
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
            "recommended_scenario": recommended_scenario["scenario_name"],
        },
        "allocation_rows": allocation_rows,
        "scenario_rows": scenario_rows,
        "warnings": warnings,
        "recommendations": recommendations,
        "method_notes": method_notes,
    }
