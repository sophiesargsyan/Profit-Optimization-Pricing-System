from __future__ import annotations

import json
import os
import re
import secrets
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4
from xml.sax.saxutils import escape
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from flask import (
    Flask,
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from auth_storage import add_user, get_user_by_email, get_user_by_id
from budget_planner import (
    BUSINESS_ACTIVITY_OPTIONS,
    BUSINESS_GOAL_OPTIONS,
    BUSINESS_STATUS_OPTIONS,
    ORGANIZATION_TYPE_OPTIONS,
    generate_smart_budget_plan,
)
from catalog_profiles import CATEGORY_PROFILES
from data_repository import load_business_dataset
from export_service import history_to_csv, history_to_json, portfolio_analysis_to_csv
from finance_storage import get_finance_record, upsert_finance_record
from financial_formatting import (
    build_financial_format_config,
    format_currency_value,
    format_number_value,
    format_percent_value,
    format_signed_currency_value,
)
from history_storage import append_history_entry, delete_history_entry, load_history
from portfolio_storage import (
    add_portfolio_product,
    update_portfolio_product,
)
from pricing_engine import ProductData
from product_defaults import DEFAULT_PRODUCT, EMPTY_PRODUCT
from product_analysis_service import analyze_product, compare_product_scenarios
from workspace_service import (
    build_dashboard_snapshot,
    build_history_entry,
    build_portfolio_comparison,
    product_record_to_data,
    summarize_portfolio,
)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DEFAULT_LANG = "en"
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hy": "Հայերեն",
    "ru": "Русский",
}
TRANSLATIONS_DIR = BASE_DIR / "translations"

app.config.setdefault("PORTFOLIO_FILE", DATA_DIR / "portfolio.json")
app.config.setdefault("HISTORY_FILE", DATA_DIR / "history.json")
app.config.setdefault("USERS_FILE", DATA_DIR / "users.json")
app.config.setdefault("FINANCE_FILE", DATA_DIR / "finance.json")
PASSWORD_MIN_LENGTH = 8

STRING_FIELDS = {
    "name": {"default": "Product", "label": "Product name", "max_length": 120},
    "category": {"default": "Accessories", "label": "Category", "max_length": 80},
}

REQUIRED_NUMERIC_FIELDS = {
    "unit_cost": {"label": "Unit cost", "min": 0, "max": 1_000_000, "type": float},
    "current_price": {"label": "Current price", "min": 0.01, "max": 1_000_000, "type": float},
    "units_sold_30d": {
        "label": "Units sold in the last 30 days",
        "min": 1,
        "max": 1_000_000,
        "type": float,
    },
}

OPTIONAL_NUMERIC_FIELDS = {
    "competitor_price": {"label": "Competitor price", "min": 0.01, "max": 1_000_000, "type": float},
    "elasticity_override": {"label": "Elasticity", "min": -4.5, "max": -0.2, "type": float},
    "return_rate_override": {
        "label": "Return rate",
        "min": 0.0,
        "max": 0.45,
        "type": float,
        "percent": True,
    },
    "fixed_cost_allocation_override": {
        "label": "Fixed cost allocation",
        "min": 0.0,
        "max": 1_000_000,
        "type": float,
    },
    "target_margin_override": {
        "label": "Target margin",
        "min": 0.1,
        "max": 0.8,
        "type": float,
        "percent": True,
    },
    "marketing_factor_override": {
        "label": "Marketing factor",
        "min": 0.7,
        "max": 1.5,
        "type": float,
    },
    "inventory_constraint_override": {
        "label": "Inventory constraint",
        "min": 1,
        "max": 1_000_000,
        "type": int,
    },
}

PRODUCT_FORM_FIELDS = (
    tuple(STRING_FIELDS.keys())
    + tuple(REQUIRED_NUMERIC_FIELDS.keys())
    + tuple(OPTIONAL_NUMERIC_FIELDS.keys())
    + ("scenario",)
)

BULK_TEMPLATE_COLUMNS = (
    "product_id",
    "product_name",
    "category",
    "current_price",
    "unit_cost",
    "base_demand",
    "elasticity",
    "competitor_price",
    "min_price",
    "max_price",
)

BULK_TEMPLATE_SAMPLE_ROW = (
    "SKU-001",
    "Luna Crossbody Bag",
    "Accessories",
    72.0,
    26.0,
    250,
    1.2,
    79.0,
    58.0,
    92.0,
)

BULK_OPTIONAL_COLUMNS = {"min_price", "max_price"}
BULK_REQUIRED_COLUMNS = tuple(
    column for column in BULK_TEMPLATE_COLUMNS if column not in BULK_OPTIONAL_COLUMNS
)
BULK_REQUIRED_TEXT_FIELDS = ("product_id", "product_name", "category")
BULK_REQUIRED_POSITIVE_NUMERIC_FIELDS = (
    "current_price",
    "unit_cost",
    "base_demand",
    "elasticity",
    "competitor_price",
)
BULK_OPTIONAL_NUMERIC_FIELDS = ("min_price", "max_price")
FINANCE_BUDGET_FIELDS = (
    "total_budget",
    "product_cost_budget",
    "marketing_budget",
    "delivery_budget",
    "packaging_budget",
    "operational_budget",
    "reserve_budget",
)
FINANCE_ALLOCATION_FIELDS = FINANCE_BUDGET_FIELDS[1:]
FINANCE_STATUS_TOLERANCE = 0.01
FINANCE_RESERVE_MIN_PERCENT = 10.0
FINANCE_MARKETING_MAX_PERCENT = 30.0
FINANCE_RECOMMENDED_ALLOCATION = (
    ("product_cost_budget", 40.0),
    ("marketing_budget", 25.0),
    ("delivery_budget", 10.0),
    ("packaging_budget", 5.0),
    ("operational_budget", 12.0),
    ("reserve_budget", 8.0),
)
FINANCE_SCENARIO_DEFINITIONS = (
    {
        "key": "conservative",
        "label_key": "finance.scenario.conservative",
        "goal_key": "finance.scenario.goal.conservative",
        "risk_key": "risk.Low",
        "risk_class": "risk-low",
        "allocations": {
            "product_cost_budget": 42.0,
            "marketing_budget": 18.0,
            "delivery_budget": 10.0,
            "packaging_budget": 5.0,
            "operational_budget": 17.0,
            "reserve_budget": 8.0,
        },
    },
    {
        "key": "balanced",
        "label_key": "finance.scenario.balanced",
        "goal_key": "finance.scenario.goal.balanced",
        "risk_key": "risk.Medium",
        "risk_class": "risk-medium",
        "allocations": {
            "product_cost_budget": 40.0,
            "marketing_budget": 25.0,
            "delivery_budget": 10.0,
            "packaging_budget": 5.0,
            "operational_budget": 12.0,
            "reserve_budget": 8.0,
        },
    },
    {
        "key": "growth",
        "label_key": "finance.scenario.growth",
        "goal_key": "finance.scenario.goal.growth",
        "risk_key": "risk.High",
        "risk_class": "risk-high",
        "allocations": {
            "product_cost_budget": 38.0,
            "marketing_budget": 32.0,
            "delivery_budget": 10.0,
            "packaging_budget": 5.0,
            "operational_budget": 7.0,
            "reserve_budget": 8.0,
        },
    },
)

SMART_BUDGET_REQUIRED_FIELDS = (
    "available_capital",
    "organization_type",
    "business_activity",
    "business_status",
    "business_goal",
)
SMART_BUDGET_OPTIONAL_FIELDS = (
    "average_monthly_revenue",
    "fixed_costs",
    "variable_costs",
    "employees_count",
)
SMART_BUDGET_INPUT_FIELDS = SMART_BUDGET_REQUIRED_FIELDS + SMART_BUDGET_OPTIONAL_FIELDS


@dataclass
class BulkValidationResult:
    errors: list[str]
    valid_row_count: int = 0


BULK_ACTION_TOLERANCE_PERCENT = 2.0

LEGACY_FIELD_ALIASES = {
    "current_price": ("base_price",),
    "units_sold_30d": ("base_demand",),
    "elasticity_override": ("elasticity",),
    "return_rate_override": ("return_rate",),
    "fixed_cost_allocation_override": ("fixed_cost",),
    "target_margin_override": ("desired_margin",),
    "inventory_constraint_override": ("inventory",),
}


def _load_translation_file(lang):
    translation_file = TRANSLATIONS_DIR / f"{lang}.json"
    if not translation_file.exists():
        if lang == DEFAULT_LANG:
            return {}
        return _load_translation_file(DEFAULT_LANG)

    with translation_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_translations(lang):
    normalized_lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANG
    base = dict(_load_translation_file(DEFAULT_LANG))
    if normalized_lang == DEFAULT_LANG:
        return base

    localized = _load_translation_file(normalized_lang)
    base.update(localized)
    return base


def translated_message(key, fallback):
    translations = getattr(g, "translations", get_translations(DEFAULT_LANG))
    return translations.get(key, fallback)


def translate_dynamic(translations, prefix, value):
    return translations.get(f"{prefix}.{value}", value)


def get_current_language():
    query_lang = request.args.get("lang", "").lower()
    if query_lang in SUPPORTED_LANGUAGES:
        session["lang"] = query_lang
        return query_lang

    session_lang = str(session.get("lang", DEFAULT_LANG)).lower()
    if session_lang in SUPPORTED_LANGUAGES:
        return session_lang

    session["lang"] = DEFAULT_LANG
    return DEFAULT_LANG


def localized_url(endpoint=None, **kwargs):
    target_endpoint = endpoint or request.endpoint or "index"
    params = dict(kwargs)
    params["lang"] = g.current_lang
    return url_for(target_endpoint, **params)


def switch_language_url(lang_code):
    target_endpoint = request.endpoint or "index"
    view_args = dict(request.view_args or {})
    query_args = request.args.to_dict(flat=True)
    query_args["lang"] = lang_code
    return url_for(target_endpoint, **view_args, **query_args)


def api_success(data, status=200):
    return jsonify({"success": True, "data": data, "error": None}), status


def api_error(message, status=400):
    return jsonify({"success": False, "data": None, "error": message}), status


def get_portfolio_file():
    return Path(app.config["PORTFOLIO_FILE"])


def get_history_file():
    return Path(app.config["HISTORY_FILE"])


def get_users_file():
    return Path(app.config["USERS_FILE"])


def get_finance_file():
    return Path(app.config["FINANCE_FILE"])


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def _normalize_email(value):
    return str(value or "").strip().lower()


def _build_public_user(user):
    if not user:
        return None

    return {
        "id": user.get("id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
    }


def _load_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = get_user_by_id(get_users_file(), user_id)
    if user is None:
        session.pop("user_id", None)
        return None

    return _build_public_user(user)


def current_user():
    return getattr(g, "current_user", None)


def is_authenticated():
    return current_user() is not None


def _current_user_id():
    user = current_user()
    return user.get("id") if user else None


def _history_sort_key(entry):
    return entry.get("created_at") or entry.get("timestamp") or ""


def _current_user_history_entries():
    return sorted(
        [
        {key: value for key, value in entry.items() if key != "user_id"}
        for entry in load_history(get_history_file(), user_id=_current_user_id())
        ],
        key=_history_sort_key,
        reverse=True,
    )


def _history_entry_product(entry):
    input_snapshot = entry.get("input_data")
    if isinstance(input_snapshot, dict) and input_snapshot.get("name"):
        return product_record_to_data(input_snapshot)
    return None


def _history_entry_analysis_result(entry):
    stored_result = entry.get("result_data")
    if isinstance(stored_result, dict) and stored_result.get("best_strategy") and stored_result.get("product"):
        return stored_result

    product = _history_entry_product(entry)
    return analyze_product(product) if product else None


def protected_url(endpoint=None, **kwargs):
    target = localized_url(endpoint, **kwargs)
    if is_authenticated():
        return target
    return localized_url("sign_in_page", next=target)


def _request_target():
    query_string = request.query_string.decode("utf-8").strip()
    return f"{request.path}?{query_string}" if query_string else request.path


def _is_safe_redirect_target(target):
    if not target:
        return False

    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc


def auth_page_url(endpoint):
    next_target = request.args.get("next", "").strip()
    if next_target and _is_safe_redirect_target(next_target):
        return localized_url(endpoint, next=next_target)
    return localized_url(endpoint)


def _redirect_target(default_endpoint="index"):
    return localized_url(default_endpoint)


def _login_user(user):
    session["user_id"] = user["id"]


def _logout_user():
    session.pop("user_id", None)


def redirect_authenticated_user(default_endpoint="index"):
    if is_authenticated():
        return redirect(localized_url(default_endpoint))
    return None


def _authentication_required_response():
    message = translated_message("auth.error.login_required", "Sign in to access that page.")
    sign_in_url = localized_url("sign_in_page", next=_request_target())
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "success": False,
                    "data": {"redirect_url": sign_in_url},
                    "error": message,
                }
            ),
            401,
        )

    flash(message, "danger")
    return redirect(sign_in_url)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not is_authenticated():
            return _authentication_required_response()
        return view(*args, **kwargs)

    return wrapped_view


def _boolean_input(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _first_payload_value(payload, field_name):
    if field_name in payload:
        return payload.get(field_name)
    for alias in LEGACY_FIELD_ALIASES.get(field_name, ()):
        if alias in payload:
            return payload.get(alias)
    return None


def _format_form_number(value, percent=False):
    if value in (None, ""):
        return ""
    numeric_value = float(value)
    if percent and abs(numeric_value) <= 1:
        numeric_value *= 100
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return str(round(numeric_value, 4))


def _portfolio_form_values(source=None):
    values = dict(EMPTY_PRODUCT)
    if source is None:
        return values

    for field in PRODUCT_FORM_FIELDS:
        raw_value = _first_payload_value(source, field)
        if raw_value in (None, ""):
            continue
        if field in {"return_rate_override", "target_margin_override"}:
            values[field] = _format_form_number(raw_value, percent=True)
        else:
            values[field] = raw_value
    return values


def _sort_portfolio_products(products):
    return sorted(products, key=lambda item: item.get("updated_at", ""), reverse=True)


def _parse_string_field(payload, field_name):
    config = STRING_FIELDS[field_name]
    value = str(_first_payload_value(payload, field_name) or config["default"]).strip()
    if not value:
        raise ValueError(f"{config['label']} is required.")
    if len(value) > config["max_length"]:
        raise ValueError(f"{config['label']} must be at most {config['max_length']} characters.")
    if field_name == "category":
        normalized = next(
            (category for category in CATEGORY_PROFILES if category.lower() == value.lower()),
            None,
        )
        if normalized is None:
            raise ValueError(f"Category must be one of: {', '.join(CATEGORY_PROFILES)}.")
        return normalized
    return value


def _parse_required_numeric_field(payload, field_name):
    config = REQUIRED_NUMERIC_FIELDS[field_name]
    raw_value = _first_payload_value(payload, field_name)
    if raw_value in (None, ""):
        raise ValueError(f"{config['label']} is required.")

    try:
        parsed = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{config['label']} must be a valid number.") from exc

    if parsed < config["min"] or parsed > config["max"]:
        raise ValueError(f"{config['label']} must be between {config['min']} and {config['max']}.")

    return int(parsed) if config["type"] is int else float(parsed)


def _parse_optional_numeric_field(payload, field_name):
    config = OPTIONAL_NUMERIC_FIELDS[field_name]
    raw_value = _first_payload_value(payload, field_name)
    if raw_value in (None, ""):
        return None

    try:
        parsed = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{config['label']} must be a valid number.") from exc

    if config.get("percent") and parsed > 1:
        parsed /= 100.0

    if parsed < config["min"] or parsed > config["max"]:
        raise ValueError(f"{config['label']} must be between {config['min']} and {config['max']}.")

    return int(parsed) if config["type"] is int else float(parsed)


def parse_product(data, scenario_override=None):
    if not isinstance(data, dict):
        raise ValueError(translated_message("api.error.invalid_payload", "Invalid request data."))

    scenario = scenario_override or str(_first_payload_value(data, "scenario") or "NORMAL").upper()
    if scenario not in {"LOW", "NORMAL", "HIGH", "PROMO"}:
        raise ValueError("Scenario must be LOW, NORMAL, HIGH, or PROMO.")

    return ProductData(
        name=_parse_string_field(data, "name"),
        category=_parse_string_field(data, "category"),
        unit_cost=_parse_required_numeric_field(data, "unit_cost"),
        current_price=_parse_required_numeric_field(data, "current_price"),
        units_sold_30d=_parse_required_numeric_field(data, "units_sold_30d"),
        competitor_price=_parse_optional_numeric_field(data, "competitor_price"),
        elasticity_override=_parse_optional_numeric_field(data, "elasticity_override"),
        return_rate_override=_parse_optional_numeric_field(data, "return_rate_override"),
        fixed_cost_allocation_override=_parse_optional_numeric_field(data, "fixed_cost_allocation_override"),
        target_margin_override=_parse_optional_numeric_field(data, "target_margin_override"),
        marketing_factor_override=_parse_optional_numeric_field(data, "marketing_factor_override"),
        inventory_constraint_override=_parse_optional_numeric_field(data, "inventory_constraint_override"),
        scenario=scenario,
    )


def build_reference_product():
    return parse_product(DEFAULT_PRODUCT)


def _format_currency(value):
    return format_currency_value(value, _currency_code())


def _round_value(value, digits=2):
    return round(float(value), digits)


def _format_percent(value):
    return format_percent_value(value, 2)


def _currency_code():
    return load_business_dataset().business_settings.currency.upper()


def format_currency_display(value, digits=2):
    return format_currency_value(value, _currency_code(), digits)


def format_percent_display(value, digits=1):
    return format_percent_value(value, digits)


def format_number_display(value, digits=0):
    return format_number_value(value, digits)


def _format_units(value):
    return str(int(round(float(value))))


def _format_multiplier(value):
    return f"{_round_value(value, 2)}x"


def _format_signed_currency(value):
    return format_signed_currency_value(value, _currency_code())


def _localized_assumption_source(translations, assumption):
    return translations.get(f"assumption_source.{assumption['source']}", assumption["detail"])


def _localized_competitor_position(translations, gap):
    absolute_gap = _round_value(abs(gap), 1)
    if gap > 0.5:
        template = translations.get(
            "position.below_competitor",
            "{gap}% below competitor reference",
        )
        return template.format(gap=absolute_gap)
    if gap < -0.5:
        template = translations.get(
            "position.above_competitor",
            "{gap}% above competitor reference",
        )
        return template.format(gap=absolute_gap)
    return translations.get("position.near_competitor", "Near competitor reference")


def _build_localized_reasons(result, translations):
    best = result["best_strategy"]
    current_option = result.get("current_option")
    assumptions = result["assumptions"]

    reasons = [
        translations.get(
            "recommendation.reason.max_profit",
            "This option produced the highest projected profit across {count} candidate prices.",
        ).format(count=len(result.get("price_profit_curve", []))),
        translations.get(
            "recommendation.reason.margin_target",
            "Projected margin is {margin} against a target of {target}.",
        ).format(
            margin=_format_percent(best["profit_margin"]),
            target=_format_percent(best["target_margin"]),
        ),
        translations.get(
            "recommendation.reason.market_position",
            "Projected demand is {demand} units with the price positioned {position}.",
        ).format(
            demand=_format_units(best["demand"]),
            position=_localized_competitor_position(translations, best["price_gap_vs_competitor"]),
        ),
    ]

    if current_option:
        reasons.append(
            translations.get(
                "recommendation.reason.profit_change",
                "Projected profit changes by {change} versus staying at the current price.",
            ).format(change=_format_signed_currency(best["profit"] - current_option["profit"]))
        )
    else:
        reasons.append(
            translations.get(
                "recommendation.reason.confidence",
                "Core assumptions range from {baseline} to {elasticity} confidence.",
            ).format(
                baseline=translate_dynamic(
                    translations,
                    "confidence",
                    assumptions["baseline_demand"]["confidence_level"],
                ),
                elasticity=translate_dynamic(
                    translations,
                    "confidence",
                    assumptions["elasticity"]["confidence_level"],
                ),
            )
        )

    return reasons


def build_dashboard_assumption_cards(result, lang):
    translations = get_translations(lang)
    assumptions = result["assumptions"]
    ordered_keys = (
        "baseline_demand",
        "seasonality",
        "elasticity",
        "return_rate",
        "competitor_reference",
        "fixed_cost_allocation",
    )

    cards = []
    for key in ordered_keys:
        assumption = assumptions[key]
        if key == "baseline_demand":
            value = f"{format_number_display(assumption['value'], 0)} {translations.get('dashboard.units', 'units')}"
        elif key == "seasonality":
            value = f"{_round_value(assumption['value'], 2)}x"
        elif key == "return_rate":
            value = format_percent_display(assumption["value"] * 100, 2)
        elif key in {"competitor_reference", "fixed_cost_allocation"}:
            value = format_currency_display(assumption["value"])
        else:
            value = format_number_display(assumption["value"], 2)

        cards.append(
            {
                "label": translations.get(f"dashboard.assumption.{key}", key.replace("_", " ").title()),
                "value": value,
                "source": _localized_assumption_source(translations, assumption),
                "confidence_level": assumption["confidence_level"],
            }
        )

    return cards


def build_localized_explanation(result, lang):
    translations = get_translations(lang)
    best = result["best_strategy"]
    product = result["product"]
    assumptions = result["assumptions"]
    confidence = result["overall_confidence"]
    current_option = result.get("current_option")
    scenario_label = translate_dynamic(translations, "scenario", product["scenario"])
    confidence_label = translate_dynamic(translations, "confidence", confidence["level"])

    assumption_cards = [
        {
            "label": translations.get("explanation.baseline", "Baseline demand"),
            "value": _format_units(assumptions["baseline_demand"]["value"]),
            "source": _localized_assumption_source(translations, assumptions["baseline_demand"]),
            "confidence": assumptions["baseline_demand"]["confidence_level"],
        },
        {
            "label": translations.get("explanation.seasonality", "Seasonality"),
            "value": _format_multiplier(assumptions["seasonality"]["value"]),
            "source": _localized_assumption_source(translations, assumptions["seasonality"]),
            "confidence": assumptions["seasonality"]["confidence_level"],
        },
        {
            "label": translations.get("explanation.elasticity", "Demand sensitivity"),
            "value": str(assumptions["elasticity"]["value"]),
            "source": _localized_assumption_source(translations, assumptions["elasticity"]),
            "confidence": assumptions["elasticity"]["confidence_level"],
        },
        {
            "label": translations.get("explanation.return_rate", "Return rate"),
            "value": _format_percent(assumptions["return_rate"]["value"] * 100),
            "source": _localized_assumption_source(translations, assumptions["return_rate"]),
            "confidence": assumptions["return_rate"]["confidence_level"],
        },
        {
            "label": translations.get("explanation.competitor", "Competitor reference"),
            "value": _format_currency(assumptions["competitor_reference"]["value"]),
            "source": _localized_assumption_source(translations, assumptions["competitor_reference"]),
            "confidence": assumptions["competitor_reference"]["confidence_level"],
        },
        {
            "label": translations.get("explanation.fixed_cost", "Fixed cost allocation"),
            "value": _format_currency(assumptions["fixed_cost_allocation"]["value"]),
            "source": _localized_assumption_source(translations, assumptions["fixed_cost_allocation"]),
            "confidence": assumptions["fixed_cost_allocation"]["confidence_level"],
        },
    ]

    caution = None
    if confidence["level"] == "Low":
        caution = translations.get(
            "explanation.caution.low",
            "Confidence is low because multiple assumptions fell back to category or default benchmarks.",
        )
    elif best["risk_level"] == "High":
        caution = translations.get(
            "explanation.caution.risk",
            "The recommendation is profitable, but it carries meaningful execution risk under the current assumptions.",
        )

    details = [
        f"{translations.get('explanation.detail.price', 'Recommended price')}: {_format_currency(best['price'])}",
        translations.get(
            "explanation.detail.financial",
            "At this price, PricePilot projects {revenue} in revenue, {total_cost} in total cost, {profit} in profit, and {margin} margin.",
        ).format(
            revenue=_format_currency(best["revenue"]),
            total_cost=_format_currency(best["total_cost"]),
            profit=_format_currency(best["profit"]),
            margin=_format_percent(best["profit_margin"]),
        ),
    ]

    if current_option:
        details.append(
            translations.get(
                "explanation.detail.profit_change",
                "Projected profit changes by {change} versus the current price.",
            ).format(change=_format_signed_currency(best["profit"] - current_option["profit"]))
        )

    source_line = translations.get("explanation.source_line", "{label} source: {source}")
    details.extend(
        [
            source_line.format(
                label=translations.get("explanation.baseline", "Baseline demand"),
                source=_localized_assumption_source(translations, assumptions["baseline_demand"]),
            ),
            source_line.format(
                label=translations.get("explanation.seasonality", "Seasonality"),
                source=_localized_assumption_source(translations, assumptions["seasonality"]),
            ),
            source_line.format(
                label=translations.get("explanation.elasticity", "Demand sensitivity"),
                source=_localized_assumption_source(translations, assumptions["elasticity"]),
            ),
            source_line.format(
                label=translations.get("explanation.return_rate", "Return rate"),
                source=_localized_assumption_source(translations, assumptions["return_rate"]),
            ),
            source_line.format(
                label=translations.get("explanation.competitor", "Competitor reference"),
                source=_localized_assumption_source(translations, assumptions["competitor_reference"]),
            ),
            translations.get(
                "explanation.confidence_line",
                "Confidence level: {confidence}.",
            ).format(confidence=confidence_label),
            f"{translations.get('explanation.detail.scenario', 'Scenario')}: {scenario_label}",
        ]
    )

    return {
        "title": translations.get(
            "explanation.title",
            f"Recommended price for {product['name']}",
        ),
        "summary": translations.get(
            "explanation.summary",
            "PricePilot combined recent demand, historical pricing behavior, seasonality, and competitor context to produce this recommendation.",
        ),
        "details": details,
        "caution": caution,
        "assumption_cards": assumption_cards,
        "confidence_label": confidence_label,
        "why_recommended": _build_localized_reasons(result, translations),
    }


def localize_analysis_result(result, lang):
    localized = dict(result)
    localized["explanation"] = build_localized_explanation(result, lang)
    return localized


@app.before_request
def set_request_context():
    g.current_lang = get_current_language()
    g.translations = get_translations(g.current_lang)
    g.current_user = _load_current_user()


@app.context_processor
def inject_i18n():
    return {
        "t": g.translations,
        "current_lang": g.current_lang,
        "supported_languages": SUPPORTED_LANGUAGES,
        "localized_url": localized_url,
        "switch_language_url": switch_language_url,
        "translate_dynamic": lambda prefix, value: translate_dynamic(g.translations, prefix, value),
        "display_currency": format_currency_display,
        "display_percent": format_percent_display,
        "display_number": format_number_display,
        "financial_format_config": build_financial_format_config(_currency_code()),
        "current_user": current_user(),
        "is_authenticated": is_authenticated(),
        "protected_url": protected_url,
        "auth_page_url": auth_page_url,
    }


def render_portfolio_workspace(form_values=None, edit_product_id=None, error_message=None, status=200):
    history_entries = _current_user_history_entries()
    comparison_rows = build_portfolio_comparison(history_entries) if history_entries else []

    return (
        render_template(
            "portfolio.html",
            page_name="portfolio",
            portfolio_products=[],
            comparison_rows=comparison_rows,
            history_entries=history_entries,
            portfolio_summary=summarize_portfolio(comparison_rows, history_entries),
            form_values=_portfolio_form_values(form_values),
            editing_product=None,
            error_message=error_message,
            categories=sorted(CATEGORY_PROFILES),
        ),
        status,
    )


def render_auth_page(
    template_name,
    page_name,
    form_values=None,
    notice_message=None,
    error_message=None,
    status=200,
):
    return (
        render_template(
            template_name,
            page_name=page_name,
            form_values=form_values or {},
            notice_message=notice_message,
            error_message=error_message,
        ),
        status,
    )


def _normalize_analysis_tab(value, default="single"):
    normalized = str(value or "").strip().lower()
    if normalized == "bulk":
        return "bulk"
    return default


def render_analysis_page(active_tab="single", validation_errors=None, bulk_results=None, status=200):
    return (
        render_template(
            "analyze.html",
            page_name="analyze",
            active_analysis_tab=_normalize_analysis_tab(active_tab),
            validation_errors=validation_errors or [],
            bulk_results=bulk_results,
            categories=sorted(CATEGORY_PROFILES),
            dataset_products=load_business_dataset().products,
        ),
        status,
    )


def render_bulk_analysis_page(validation_errors=None, bulk_results=None, status=200):
    return render_analysis_page(
        active_tab="bulk",
        validation_errors=validation_errors,
        bulk_results=bulk_results,
        status=status,
    )


def _smart_budget_form_values(source=None):
    source = source or {}
    values = {field_name: "" for field_name in SMART_BUDGET_INPUT_FIELDS}
    for field_name in SMART_BUDGET_INPUT_FIELDS:
        raw_value = source.get(field_name)
        if raw_value in (None, ""):
            continue
        if isinstance(raw_value, (int, float)):
            values[field_name] = _format_form_number(raw_value)
        else:
            values[field_name] = str(raw_value).strip()
    return values


def _smart_budget_input_values(source):
    if not isinstance(source, dict):
        return {}

    normalized = {}
    for field_name in SMART_BUDGET_INPUT_FIELDS:
        if field_name not in source:
            continue
        value = source.get(field_name)
        if value in (None, ""):
            continue
        normalized[field_name] = value
    return normalized


def _legacy_finance_prefill(record):
    if not isinstance(record, dict):
        return {}
    total_budget = record.get("total_budget")
    if total_budget in (None, "", 0, 0.0):
        return {}
    return {"available_capital": total_budget}


def _saved_finance_input_values(record):
    if not isinstance(record, dict):
        return {}

    for candidate in (record.get("input_values"), record.get("values"), record):
        normalized = _smart_budget_input_values(candidate if isinstance(candidate, dict) else {})
        if normalized:
            return normalized

    return _legacy_finance_prefill(record)


def _has_complete_smart_budget_inputs(values):
    return all(str(values.get(field_name, "") or "").strip() for field_name in SMART_BUDGET_REQUIRED_FIELDS)


def _finance_record_allocation_amount(finance_record, field_name):
    rows = finance_record.get("allocation_rows")
    if not isinstance(rows, list):
        return None

    for row in rows:
        if not isinstance(row, dict) or row.get("field_name") != field_name:
            continue
        try:
            return float(row.get("amount", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return None


def _finance_record_amount(finance_record, field_name):
    try:
        if finance_record.get(field_name) not in (None, ""):
            return float(finance_record.get(field_name) or 0.0)
    except (TypeError, ValueError):
        pass

    input_values = finance_record.get("input_values")
    summary = finance_record.get("summary")
    values = finance_record.get("values")
    allocation_mapping = {
        "marketing_budget": "marketing_budget",
        "product_cost_budget": "inventory_or_purchase_budget",
        "reserve_budget": "emergency_reserve",
    }

    if field_name == "total_budget":
        for source, source_key in (
            (input_values, "available_capital"),
            (summary, "available_capital"),
            (values, "available_capital"),
            (summary, "total_allocated"),
        ):
            if not isinstance(source, dict):
                continue
            try:
                if source.get(source_key) not in (None, ""):
                    return float(source.get(source_key) or 0.0)
            except (TypeError, ValueError):
                continue
        return 0.0

    allocation_field = allocation_mapping.get(field_name)
    if allocation_field:
        allocation_amount = _finance_record_allocation_amount(finance_record, allocation_field)
        if allocation_amount is not None:
            return allocation_amount
        if isinstance(values, dict):
            try:
                if values.get(allocation_field) not in (None, ""):
                    return float(values.get(allocation_field) or 0.0)
            except (TypeError, ValueError):
                pass

    return 0.0


def _safe_budget_ratio(amount, total_budget):
    total = float(total_budget or 0.0)
    if total <= 0:
        return None
    return float(amount or 0.0) / total


def _build_analysis_finance_insights(result):
    finance_record = get_finance_record(get_finance_file(), user_id=_current_user_id())
    if finance_record is None:
        return None

    total_budget = _finance_record_amount(finance_record, "total_budget")
    if total_budget <= 0:
        return None

    best_strategy = result.get("best_strategy") or {}
    current_option = result.get("current_option") or {}
    product_data = result.get("product") or {}

    marketing_budget = _finance_record_amount(finance_record, "marketing_budget")
    product_cost_budget = _finance_record_amount(finance_record, "product_cost_budget")
    reserve_budget = _finance_record_amount(finance_record, "reserve_budget")

    best_demand = float(best_strategy.get("demand", 0.0) or 0.0)
    current_demand = float(
        current_option.get("demand", product_data.get("units_sold_30d", 0.0)) or 0.0
    )
    best_price = float(best_strategy.get("price", 0.0) or 0.0)
    current_price = float(
        current_option.get("price", product_data.get("current_price", 0.0)) or 0.0
    )

    demand_increase_is_high = False
    if current_demand > 0 and best_demand >= current_demand * 1.2:
        demand_increase_is_high = True
    elif current_price > 0 and abs(best_price - current_price) / current_price >= 0.1:
        demand_increase_is_high = True

    insights = []

    if marketing_budget < total_budget * 0.2 and demand_increase_is_high:
        insights.append(
            {
                "level": "warning",
                "message": translated_message(
                    "analyze.finance_insights.marketing_warning",
                    "Քո մարքեթինգի բյուջեն կարող է բավարար չլինել առաջարկվող գնային ռազմավարության համար",
                ),
            }
        )

    product_cost_ratio = _safe_budget_ratio(product_cost_budget, total_budget)
    if product_cost_ratio is not None and product_cost_ratio > 0.6:
        insights.append(
            {
                "level": "warning",
                "message": translated_message(
                    "analyze.finance_insights.cost_pressure_warning",
                    "Ապրանքի ինքնարժեքի բաժինը բարձր է, ինչը կարող է սահմանափակել շահույթի աճը",
                ),
            }
        )

    if reserve_budget < total_budget * 0.1:
        insights.append(
            {
                "level": "info",
                "message": translated_message(
                    "analyze.finance_insights.reserve_info",
                    "Խորհուրդ է տրվում պահուստը պահել առնվազն 10–15%",
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "level": "info",
                "message": translated_message(
                    "analyze.finance_insights.aligned",
                    "Բյուջեն համահունչ է ընտրված ռազմավարությանը",
                ),
            }
        )

    return {"items": insights}


def _risk_class_from_label(label):
    if label == "Բարձր":
        return "risk-high"
    if label == "Միջին":
        return "risk-medium"
    return "risk-low"


def _sustainability_class(status_label):
    if status_label == "Անբավարար":
        return "risk-high"
    if status_label == "Սահմանային":
        return "risk-medium"
    return "risk-low"


def _prepare_smart_budget_result(result_payload):
    if not isinstance(result_payload, dict):
        return None

    summary = dict(result_payload.get("summary") or {})
    allocation_rows = [dict(row) for row in (result_payload.get("allocation_rows") or [])]
    scenario_rows = [dict(row) for row in (result_payload.get("scenario_rows") or [])]
    warnings = [dict(item) for item in (result_payload.get("warnings") or []) if isinstance(item, dict)]
    recommendations = [item for item in (result_payload.get("recommendations") or []) if item]
    method_notes = [item for item in (result_payload.get("method_notes") or []) if item]

    if not summary:
        return None

    summary["overall_risk_class"] = _risk_class_from_label(summary.get("overall_risk_level"))
    summary["sustainability_class"] = _sustainability_class(summary.get("sustainability_status"))

    for row in scenario_rows:
        row["risk_class"] = _risk_class_from_label(row.get("risk_level"))
        row["sustainability_class"] = _sustainability_class(row.get("sustainability_status"))

    return {
        "summary": summary,
        "allocation_rows": allocation_rows,
        "scenario_rows": scenario_rows,
        "warnings": warnings,
        "recommendations": recommendations,
        "method_notes": method_notes,
    }


def _saved_finance_result(record):
    prepared = _prepare_smart_budget_result(record)
    if prepared is not None:
        return prepared

    input_values = _saved_finance_input_values(record)
    if not _has_complete_smart_budget_inputs(input_values):
        return None

    try:
        return _prepare_smart_budget_result(generate_smart_budget_plan(input_values))
    except ValueError:
        return None


def _smart_budget_storage_payload(plan_result):
    values = dict(plan_result.get("values") or {})
    return {
        "input_values": {
            field_name: values.get(field_name)
            for field_name in SMART_BUDGET_INPUT_FIELDS
        },
        "values": values,
        "summary": dict(plan_result.get("summary") or {}),
        "allocation_rows": list(plan_result.get("allocation_rows") or []),
        "scenario_rows": list(plan_result.get("scenario_rows") or []),
        "warnings": list(plan_result.get("warnings") or []),
        "recommendations": list(plan_result.get("recommendations") or []),
        "method_notes": list(plan_result.get("method_notes") or []),
    }


def render_finance_page(
    form_values=None,
    planner_result=None,
    error_message=None,
    status=200,
):
    prepared_result = _prepare_smart_budget_result(planner_result)
    return (
        render_template(
            "finance.html",
            page_name="finance",
            form_values=_smart_budget_form_values(form_values),
            finance_summary=(prepared_result or {}).get("summary"),
            allocation_rows=(prepared_result or {}).get("allocation_rows", []),
            scenario_rows=(prepared_result or {}).get("scenario_rows", []),
            warnings=(prepared_result or {}).get("warnings", []),
            recommendations=(prepared_result or {}).get("recommendations", []),
            method_notes=(prepared_result or {}).get("method_notes", []),
            organization_type_options=ORGANIZATION_TYPE_OPTIONS,
            business_activity_options=BUSINESS_ACTIVITY_OPTIONS,
            business_status_options=BUSINESS_STATUS_OPTIONS,
            business_goal_options=BUSINESS_GOAL_OPTIONS,
            error_message=error_message,
        ),
        status,
    )


def download_response(content, filename, mimetype):
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_column_name(column_index):
    name = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(column_index, row_index, value):
    cell_ref = f"{_xlsx_column_name(column_index)}{row_index}"
    if isinstance(value, (int, float)):
        return f'<c r="{cell_ref}"><v>{value}</v></c>'
    cell_value = escape(str(value))
    return f'<c r="{cell_ref}" t="inlineStr"><is><t>{cell_value}</t></is></c>'


def _xlsx_row(row_index, values):
    cells = "".join(
        _xlsx_cell(column_index, row_index, value)
        for column_index, value in enumerate(values, start=1)
    )
    return f'<row r="{row_index}">{cells}</row>'


def _build_xlsx_workbook(rows, sheet_name="Bulk Analysis"):
    sheet_rows = "".join(
        _xlsx_row(row_index, row_values)
        for row_index, row_values in enumerate(rows, start=1)
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{sheet_rows}</sheetData>"
        "</worksheet>"
    )

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    package_relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook_relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)

    return output.getvalue()


def build_bulk_analysis_template():
    return _build_xlsx_workbook((BULK_TEMPLATE_COLUMNS, BULK_TEMPLATE_SAMPLE_ROW))


def _xml_local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_text(node, child_name):
    for child in node:
        if _xml_local_name(child.tag) == child_name:
            return child.text or ""
    return ""


def _read_shared_strings(archive):
    try:
        shared_strings_xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(shared_strings_xml)
    shared_strings = []
    for item in root:
        if _xml_local_name(item.tag) != "si":
            continue
        shared_strings.append(
            "".join(node.text or "" for node in item.iter() if _xml_local_name(node.tag) == "t")
        )
    return shared_strings


def _first_worksheet_path(archive):
    file_names = set(archive.namelist())
    default_path = "xl/worksheets/sheet1.xml"
    if default_path in file_names:
        return default_path

    worksheet_paths = sorted(
        name for name in file_names if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    if worksheet_paths:
        return worksheet_paths[0]

    raise ValueError("No worksheet found in the uploaded Excel file.")


def _xlsx_column_index_from_ref(cell_ref):
    match = re.match(r"([A-Z]+)", str(cell_ref or "").upper())
    if not match:
        return None

    column_index = 0
    for character in match.group(1):
        column_index = column_index * 26 + (ord(character) - ord("A") + 1)
    return column_index - 1


def _xlsx_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.iter() if _xml_local_name(node.tag) == "t"
        ).strip()

    raw_value = _xml_text(cell, "v").strip()
    if cell_type == "s" and raw_value:
        try:
            return shared_strings[int(raw_value)].strip()
        except (IndexError, ValueError):
            return ""

    return raw_value


def _read_xlsx_rows(xlsx_content):
    try:
        with ZipFile(BytesIO(xlsx_content)) as archive:
            shared_strings = _read_shared_strings(archive)
            worksheet_xml = archive.read(_first_worksheet_path(archive))
    except BadZipFile as exc:
        raise ValueError("Could not read the Excel file. Please upload a valid .xlsx workbook.") from exc
    except KeyError as exc:
        raise ValueError("The uploaded Excel file is missing worksheet data.") from exc

    try:
        worksheet = ET.fromstring(worksheet_xml)
    except ET.ParseError as exc:
        raise ValueError("Could not parse the uploaded Excel worksheet.") from exc

    rows = []
    fallback_row_number = 0
    for row in worksheet.iter():
        if _xml_local_name(row.tag) != "row":
            continue

        fallback_row_number += 1
        row_number = int(row.attrib.get("r") or fallback_row_number)
        cell_values = {}
        for cell in row:
            if _xml_local_name(cell.tag) != "c":
                continue

            column_index = _xlsx_column_index_from_ref(cell.attrib.get("r"))
            if column_index is None:
                continue
            cell_values[column_index] = _xlsx_cell_value(cell, shared_strings)

        if cell_values:
            values = ["" for _ in range(max(cell_values) + 1)]
            for column_index, value in cell_values.items():
                values[column_index] = value
            rows.append((row_number, values))

    return rows


def _normalize_bulk_header(value):
    return str(value or "").strip().lower()


def _bulk_header_map(header_values):
    header_map = {}
    for index, value in enumerate(header_values):
        header_name = _normalize_bulk_header(value)
        if header_name and header_name not in header_map:
            header_map[header_name] = index
    return header_map


def _is_blank_cell(value):
    return value is None or str(value).strip() == ""


def _bulk_row_value(row_values, header_map, field_name):
    column_index = header_map.get(field_name)
    if column_index is None or column_index >= len(row_values):
        return ""
    return row_values[column_index]


def _bulk_data_rows(rows):
    return [
        (row_number, row_values)
        for row_number, row_values in rows[1:]
        if any(not _is_blank_cell(value) for value in row_values)
    ]


def _parse_bulk_numeric_value(value):
    if _is_blank_cell(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    normalized_value = str(value).strip()
    if "," in normalized_value:
        if "." in normalized_value or normalized_value.count(",") > 1:
            raise ValueError("invalid")
        normalized_value = normalized_value.replace(",", ".", 1)

    try:
        return float(normalized_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid") from exc


def _parse_bulk_number(value, row_number, field_name, errors, required=False, positive=False):
    try:
        numeric_value = _parse_bulk_numeric_value(value)
    except ValueError:
        errors.append(f"Row {row_number}: {field_name} must be a valid number.")
        return None

    if numeric_value is None:
        if required:
            errors.append(f"Row {row_number}: {field_name} is required.")
        return None

    if positive and numeric_value <= 0:
        errors.append(f"Row {row_number}: {field_name} must be greater than 0.")
    return numeric_value


def _parse_valid_bulk_number(value):
    return _parse_bulk_numeric_value(value)


def validate_bulk_analysis_workbook(uploaded_file):
    xlsx_content = uploaded_file.read()
    if not xlsx_content:
        return BulkValidationResult(errors=["The uploaded file is empty."])

    rows = _read_xlsx_rows(xlsx_content)
    if not rows:
        return BulkValidationResult(
            errors=["The uploaded Excel file is empty. Use the template and add product rows."]
        )

    header_map = _bulk_header_map(rows[0][1])

    missing_columns = [column for column in BULK_REQUIRED_COLUMNS if column not in header_map]
    if missing_columns:
        return BulkValidationResult(
            errors=[f"Missing required columns: {', '.join(missing_columns)}."]
        )

    data_rows = _bulk_data_rows(rows)
    if not data_rows:
        return BulkValidationResult(
            errors=["No product rows found. Add at least one product row below the header."]
        )

    errors = []
    for row_number, row_values in data_rows:
        for field_name in BULK_REQUIRED_TEXT_FIELDS:
            if _is_blank_cell(_bulk_row_value(row_values, header_map, field_name)):
                errors.append(f"Row {row_number}: {field_name} is required.")

        numeric_values = {}
        for field_name in BULK_REQUIRED_POSITIVE_NUMERIC_FIELDS:
            numeric_values[field_name] = _parse_bulk_number(
                _bulk_row_value(row_values, header_map, field_name),
                row_number,
                field_name,
                errors,
                required=True,
                positive=True,
            )

        for field_name in BULK_OPTIONAL_NUMERIC_FIELDS:
            if field_name not in header_map:
                continue
            numeric_values[field_name] = _parse_bulk_number(
                _bulk_row_value(row_values, header_map, field_name),
                row_number,
                field_name,
                errors,
                positive=True,
            )

        min_price = numeric_values.get("min_price")
        max_price = numeric_values.get("max_price")
        if min_price is not None and max_price is not None and min_price >= max_price:
            errors.append("Row {row}: min_price must be less than max_price.".format(row=row_number))

    return BulkValidationResult(errors=errors, valid_row_count=0 if errors else len(data_rows))


def parse_bulk_analysis_products(xlsx_content):
    rows = _read_xlsx_rows(xlsx_content)
    if not rows:
        return []

    header_map = _bulk_header_map(rows[0][1])
    products = []
    for row_number, row_values in _bulk_data_rows(rows):
        product = {
            "row_number": row_number,
            "product_id": str(_bulk_row_value(row_values, header_map, "product_id")).strip(),
            "product_name": str(_bulk_row_value(row_values, header_map, "product_name")).strip(),
            "category": str(_bulk_row_value(row_values, header_map, "category")).strip(),
            "current_price": _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "current_price")
            ),
            "unit_cost": _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "unit_cost")
            ),
            "base_demand": _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "base_demand")
            ),
            "elasticity": _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "elasticity")
            ),
            "competitor_price": _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "competitor_price")
            ),
        }
        if "min_price" in header_map:
            product["min_price"] = _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "min_price")
            )
        if "max_price" in header_map:
            product["max_price"] = _parse_valid_bulk_number(
                _bulk_row_value(row_values, header_map, "max_price")
            )
        products.append(product)

    return products


def _percent_change(new_value, old_value):
    if not old_value:
        return 0.0
    return round(((float(new_value) - float(old_value)) / float(old_value)) * 100, 2)


def _recommended_bulk_action(price_change_percent):
    if price_change_percent > BULK_ACTION_TOLERANCE_PERCENT:
        return "Increase price"
    if price_change_percent < -BULK_ACTION_TOLERANCE_PERCENT:
        return "Decrease price"
    return "Keep current price"


def _contribution_margin_percent(revenue, variable_cost):
    revenue = float(revenue or 0.0)
    if revenue <= 0:
        return 0.0
    return round(((revenue - float(variable_cost or 0.0)) / revenue) * 100, 2)


def _bulk_summary_row(product_input, analysis):
    summary = analysis["analysis_summary"]
    price_change_percent = _percent_change(
        summary["optimal_price"],
        product_input["current_price"],
    )
    return {
        "row_number": product_input["row_number"],
        "product_id": product_input["product_id"],
        "product_name": product_input["product_name"],
        "category": product_input["category"],
        "current_price": product_input["current_price"],
        "optimal_price": summary["optimal_price"],
        "price_change_percent": price_change_percent,
        "expected_quantity": summary["expected_quantity"],
        "expected_revenue": summary["expected_revenue"],
        "expected_profit": summary["expected_profit"],
        "contribution_margin": _contribution_margin_percent(
            summary["expected_revenue"],
            summary["expected_variable_cost"],
        ),
        "recommended_action": _recommended_bulk_action(price_change_percent),
    }


def process_bulk_analysis_products(products, history_file=None, user_id=None):
    result = {
        "summary": {
            "total_products": len(products),
            "processed_count": 0,
            "failed_count": 0,
        },
        "products": [],
        "errors": [],
    }

    for product in products:
        try:
            analysis = analyze_product(product)
            result["products"].append(_bulk_summary_row(product, analysis))
            if history_file is not None and user_id is not None:
                append_history_entry(
                    history_file,
                    build_history_entry(
                        analysis,
                        input_data=product,
                        analysis_type="bulk",
                    ),
                    user_id=user_id,
                )
        except Exception as exc:
            app.logger.info("Bulk analysis failed for row %s: %s", product.get("row_number"), exc)
            result["errors"].append(
                "Row {row}: {product_id} could not be analyzed. {error}".format(
                    row=product.get("row_number"),
                    product_id=product.get("product_id") or product.get("product_name") or "Product",
                    error=str(exc),
                )
            )

    result["summary"]["processed_count"] = len(result["products"])
    result["summary"]["failed_count"] = len(result["errors"])
    return result


@app.route("/")
def index():
    return render_template("index.html", page_name="home")


def _handle_bulk_analysis_submission():
    uploaded_file = request.files.get("product_file")
    if not uploaded_file or not uploaded_file.filename:
        return render_analysis_page(
            active_tab="bulk",
            validation_errors=[
                translated_message(
                    "bulk_analysis.upload_required",
                    "Choose an .xlsx file before starting bulk analysis.",
                )
            ],
            status=400,
        )

    if Path(uploaded_file.filename).suffix.lower() != ".xlsx":
        return render_analysis_page(
            active_tab="bulk",
            validation_errors=[
                translated_message(
                    "bulk_analysis.upload_invalid",
                    "Please upload an .xlsx file.",
                )
            ],
            status=400,
        )

    uploaded_content = uploaded_file.read()
    try:
        validation_result = validate_bulk_analysis_workbook(BytesIO(uploaded_content))
    except ValueError as exc:
        validation_result = BulkValidationResult(errors=[str(exc)])

    if validation_result.errors:
        return render_analysis_page(
            active_tab="bulk",
            validation_errors=validation_result.errors,
            status=400,
        )

    bulk_products = parse_bulk_analysis_products(uploaded_content)
    bulk_results = process_bulk_analysis_products(
        bulk_products,
        history_file=get_history_file(),
        user_id=_current_user_id(),
    )
    return render_analysis_page(active_tab="bulk", bulk_results=bulk_results)


@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze_page():
    if request.method == "POST":
        return _handle_bulk_analysis_submission()

    active_tab = _normalize_analysis_tab(request.args.get("tab"), default="single")
    return render_analysis_page(active_tab=active_tab)


@app.route("/bulk-analysis", methods=["GET", "POST"])
@login_required
def bulk_analysis_page():
    if request.method == "POST":
        return _handle_bulk_analysis_submission()

    return render_analysis_page(active_tab="bulk")


@app.route("/bulk-analysis/template.xlsx")
@login_required
def bulk_analysis_template():
    return download_response(
        build_bulk_analysis_template(),
        "pricepilot_bulk_product_template.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/finance", methods=["GET", "POST"])
@login_required
def finance_page():
    if request.method == "POST":
        form_values = request.form.to_dict(flat=True)
        try:
            planner_result = generate_smart_budget_plan(form_values)
        except ValueError as exc:
            return render_finance_page(
                form_values=form_values,
                error_message=str(exc),
                status=400,
            )

        saved_record = upsert_finance_record(
            get_finance_file(),
            _smart_budget_storage_payload(planner_result),
            user_id=_current_user_id(),
        )
        return render_finance_page(
            form_values=_saved_finance_input_values(saved_record),
            planner_result=saved_record,
        )

    saved_record = get_finance_record(get_finance_file(), user_id=_current_user_id())
    if saved_record is None:
        return render_finance_page()

    return render_finance_page(
        form_values=_saved_finance_input_values(saved_record),
        planner_result=_saved_finance_result(saved_record) or saved_record,
    )


@app.route("/sign-in", methods=["GET", "POST"])
def sign_in_page():
    redirect_response = redirect_authenticated_user()
    if redirect_response is not None:
        return redirect_response

    form_values = {}
    error_message = None

    if request.method == "POST":
        form_values = {"identifier": request.form.get("identifier", "").strip()}
        password = request.form.get("password", "")
        normalized_email = _normalize_email(form_values["identifier"])
        user = get_user_by_email(get_users_file(), normalized_email)
        stored_password_hash = user.get("password_hash", "") if user else ""

        if user is None or not stored_password_hash or not check_password_hash(stored_password_hash, password):
            error_message = translated_message(
                "auth.error.invalid_credentials",
                "Incorrect email or password.",
            )
            return render_auth_page(
                "sign_in.html",
                page_name="sign-in",
                form_values=form_values,
                error_message=error_message,
                status=401,
            )

        _login_user(user)
        return redirect(_redirect_target())

    return render_auth_page(
        "sign_in.html",
        page_name="sign-in",
        form_values=form_values,
    )


@app.route("/sign-up", methods=["GET", "POST"])
def sign_up_page():
    redirect_response = redirect_authenticated_user()
    if redirect_response is not None:
        return redirect_response

    form_values = {}
    error_message = None

    if request.method == "POST":
        form_values = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
        }
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        normalized_email = _normalize_email(form_values["email"])

        if not form_values["name"]:
            error_message = translated_message("auth.error.name_required", "Name is required.")
        elif len(form_values["name"]) > 120:
            error_message = translated_message(
                "auth.error.name_too_long",
                "Name must be at most 120 characters.",
            )
        elif "@" not in normalized_email or "." not in normalized_email.split("@", 1)[-1]:
            error_message = translated_message(
                "auth.error.invalid_email",
                "Enter a valid email address.",
            )
        elif get_user_by_email(get_users_file(), normalized_email):
            error_message = translated_message(
                "auth.error.email_taken",
                "An account with this email already exists.",
            )
        elif len(password) < PASSWORD_MIN_LENGTH:
            error_message = translated_message(
                "auth.error.password_too_short",
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters.",
            )
        elif password != confirm_password:
            error_message = translated_message(
                "auth.error.password_mismatch",
                "Passwords do not match.",
            )

        if error_message:
            return render_auth_page(
                "sign_up.html",
                page_name="sign-up",
                form_values=form_values,
                error_message=error_message,
                status=400,
            )

        user = add_user(
            get_users_file(),
            {
                "id": uuid4().hex,
                "name": form_values["name"],
                "email": normalized_email,
                "password_hash": generate_password_hash(password),
                "created_at": _timestamp(),
            },
        )
        _login_user(user)
        return redirect(_redirect_target())

    return render_auth_page(
        "sign_up.html",
        page_name="sign-up",
        form_values=form_values,
    )


@app.route("/portfolio")
@login_required
def portfolio_page():
    edit_product_id = request.args.get("edit", "").strip() or None
    return render_portfolio_workspace(edit_product_id=edit_product_id)


@app.route("/portfolio/save", methods=["POST"])
@login_required
def portfolio_save():
    product_id = request.form.get("product_id", "").strip() or None

    try:
        product = parse_product(request.form.to_dict(flat=True))
        payload = asdict(product)

        if product_id:
            update_portfolio_product(
                get_portfolio_file(),
                product_id,
                payload,
                user_id=_current_user_id(),
            )
            flash(translated_message("portfolio.messages.updated", "Product updated in the portfolio."), "success")
        else:
            add_portfolio_product(
                get_portfolio_file(),
                payload,
                user_id=_current_user_id(),
            )
            flash(translated_message("portfolio.messages.added", "Product added to the portfolio."), "success")

        return redirect(localized_url("portfolio_page"))
    except KeyError:
        flash(translated_message("portfolio.messages.not_found", "The selected product could not be found."), "danger")
        return redirect(localized_url("portfolio_page"))
    except ValueError as exc:
        app.logger.info("Validation error on /portfolio/save: %s", exc)
        return render_portfolio_workspace(
            form_values=request.form.to_dict(flat=True),
            edit_product_id=product_id,
            error_message=str(exc),
            status=400,
        )


@app.route("/portfolio/<product_id>/delete", methods=["POST"])
@login_required
def portfolio_delete(product_id):
    deleted = delete_history_entry(
        get_history_file(),
        product_id,
        user_id=_current_user_id(),
    )
    message_key = "portfolio.messages.deleted" if deleted else "portfolio.messages.not_found"
    fallback = (
        "Saved analysis removed from the workspace."
        if deleted
        else "The selected saved analysis could not be found."
    )
    flash(translated_message(message_key, fallback), "success" if deleted else "danger")
    return redirect(localized_url("portfolio_page"))


@app.route("/portfolio/export.csv")
@login_required
def portfolio_export_csv():
    history_entries = _current_user_history_entries()
    comparison_rows = build_portfolio_comparison(history_entries) if history_entries else []
    csv_content = "\ufeff" + portfolio_analysis_to_csv(comparison_rows)
    return download_response(csv_content, "pricepilot_portfolio_analysis.csv", "text/csv; charset=utf-8")


@app.route("/history/export.csv")
@login_required
def history_export_csv():
    csv_content = "\ufeff" + history_to_csv(_current_user_history_entries())
    return download_response(csv_content, "pricepilot_analysis_history.csv", "text/csv; charset=utf-8")


@app.route("/history/export.json")
@login_required
def history_export_json():
    json_content = history_to_json(_current_user_history_entries())
    return download_response(json_content, "pricepilot_analysis_history.json", "application/json; charset=utf-8")


@app.route("/dashboard")
@login_required
def dashboard_page():
    history_entries = _current_user_history_entries()
    comparison_rows = build_portfolio_comparison(history_entries) if history_entries else []

    focus_record = None
    if comparison_rows:
        focus_row = max(
            comparison_rows,
            key=lambda row: (row["expected_profit"], row["confidence_score"], row["margin"]),
        )
        focus_record = next(
            (record for record in history_entries if record.get("id") == focus_row["product_id"]),
            None,
        )

    focus_product = _history_entry_product(focus_record) if focus_record else None
    if focus_product is None:
        focus_product = build_reference_product()

    focus_analysis = _history_entry_analysis_result(focus_record) if focus_record else None
    if focus_analysis is None:
        focus_analysis = analyze_product(focus_product)

    focus_scenarios = compare_product_scenarios(focus_product)
    dashboard_snapshot = build_dashboard_snapshot(comparison_rows, focus_analysis, focus_scenarios)

    return render_template(
        "dashboard.html",
        page_name="dashboard",
        dashboard_snapshot=dashboard_snapshot,
        comparison_rows=comparison_rows,
        focus_analysis=focus_analysis,
        focus_scenarios=focus_scenarios,
        dashboard_assumptions=build_dashboard_assumption_cards(focus_analysis, g.current_lang),
    )


@app.route("/about")
@login_required
def about_page():
    return render_template("about.html", page_name="about")


@app.route("/sign-out", methods=["POST"])
@login_required
def sign_out():
    _logout_user()
    flash(translated_message("auth.message.signed_out", "You have been signed out."), "success")
    return redirect(localized_url("sign_in_page"))


@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    data = request.get_json(silent=True) or {}

    try:
        product = parse_product(data)
        result = analyze_product(product)
        localized_result = localize_analysis_result(result, g.current_lang)
        localized_result["finance_insights"] = _build_analysis_finance_insights(result)

        if _boolean_input(data.get("save_history"), default=True):
            append_history_entry(
                get_history_file(),
                build_history_entry(
                    result,
                    input_data=asdict(product),
                    analysis_type="single",
                ),
                user_id=_current_user_id(),
            )

        return api_success(localized_result)
    except ValueError as exc:
        app.logger.info("Validation error on /api/analyze: %s", exc)
        return api_error(str(exc), status=400)
    except Exception:
        app.logger.exception("Unexpected error on /api/analyze")
        return api_error(
            translated_message(
                "api.error.unexpected_analysis",
                "The analysis could not be completed. Please review the inputs and try again.",
            ),
            status=500,
        )


@app.route("/api/scenario-compare", methods=["POST"])
@login_required
def api_scenario_compare():
    data = request.get_json(silent=True) or {}

    try:
        product = parse_product(data, scenario_override="NORMAL")
        result = compare_product_scenarios(product)
        return api_success(result)
    except ValueError as exc:
        app.logger.info("Validation error on /api/scenario-compare: %s", exc)
        return api_error(str(exc), status=400)
    except Exception:
        app.logger.exception("Unexpected error on /api/scenario-compare")
        return api_error(
            translated_message(
                "api.error.unexpected_scenario_compare",
                "The scenario comparison could not be completed. Please review the inputs and try again.",
            ),
            status=500,
        )


if __name__ == "__main__":
    app.run(debug=True)
