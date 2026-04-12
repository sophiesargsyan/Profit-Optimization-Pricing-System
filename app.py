from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict
from pathlib import Path

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

from catalog_profiles import CATEGORY_PROFILES
from data_repository import load_business_dataset
from export_service import history_to_csv, history_to_json, portfolio_analysis_to_csv
from financial_formatting import (
    build_financial_format_config,
    format_currency_value,
    format_number_value,
    format_percent_value,
    format_signed_currency_value,
)
from history_storage import append_history_entry, load_history
from portfolio_storage import (
    add_portfolio_product,
    delete_portfolio_product,
    get_portfolio_product,
    load_portfolio,
    update_portfolio_product,
)
from pricing_engine import ProductData, compare_all_scenarios, run_full_analysis
from product_defaults import DEFAULT_PRODUCT, EMPTY_PRODUCT
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
def set_request_language():
    g.current_lang = get_current_language()
    g.translations = get_translations(g.current_lang)


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
    }


def render_portfolio_workspace(form_values=None, edit_product_id=None, error_message=None, status=200):
    portfolio_products = _sort_portfolio_products(load_portfolio(get_portfolio_file()))
    comparison_rows = build_portfolio_comparison(portfolio_products) if portfolio_products else []
    history_entries = list(reversed(load_history(get_history_file())))
    editing_product = (
        get_portfolio_product(get_portfolio_file(), edit_product_id) if edit_product_id else None
    )

    return (
        render_template(
            "portfolio.html",
            page_name="portfolio",
            portfolio_products=portfolio_products,
            comparison_rows=comparison_rows,
            history_entries=history_entries,
            portfolio_summary=summarize_portfolio(comparison_rows, history_entries),
            form_values=_portfolio_form_values(form_values or editing_product),
            editing_product=editing_product,
            error_message=error_message,
            categories=sorted(CATEGORY_PROFILES),
        ),
        status,
    )


def download_response(content, filename, mimetype):
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/")
def index():
    return render_template("index.html", page_name="home")


@app.route("/analyze")
def analyze_page():
    product_id = request.args.get("product_id", "").strip()
    selected_portfolio_product = (
        get_portfolio_product(get_portfolio_file(), product_id) if product_id else None
    )
    default_values = (
        _portfolio_form_values(selected_portfolio_product)
        if selected_portfolio_product
        else dict(DEFAULT_PRODUCT)
    )
    return render_template(
        "analyze.html",
        page_name="analyze",
        default_values=default_values,
        selected_portfolio_product=selected_portfolio_product,
        categories=sorted(CATEGORY_PROFILES),
        dataset_products=load_business_dataset().products,
    )


@app.route("/portfolio")
def portfolio_page():
    edit_product_id = request.args.get("edit", "").strip() or None
    return render_portfolio_workspace(edit_product_id=edit_product_id)


@app.route("/portfolio/save", methods=["POST"])
def portfolio_save():
    product_id = request.form.get("product_id", "").strip() or None

    try:
        product = parse_product(request.form.to_dict(flat=True))
        payload = asdict(product)

        if product_id:
            update_portfolio_product(get_portfolio_file(), product_id, payload)
            flash(translated_message("portfolio.messages.updated", "Product updated in the portfolio."), "success")
        else:
            add_portfolio_product(get_portfolio_file(), payload)
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
def portfolio_delete(product_id):
    deleted = delete_portfolio_product(get_portfolio_file(), product_id)
    message_key = "portfolio.messages.deleted" if deleted else "portfolio.messages.not_found"
    fallback = "Product deleted from the portfolio." if deleted else "The selected product could not be found."
    flash(translated_message(message_key, fallback), "success" if deleted else "danger")
    return redirect(localized_url("portfolio_page"))


@app.route("/portfolio/export.csv")
def portfolio_export_csv():
    portfolio_products = _sort_portfolio_products(load_portfolio(get_portfolio_file()))
    comparison_rows = build_portfolio_comparison(portfolio_products) if portfolio_products else []
    csv_content = "\ufeff" + portfolio_analysis_to_csv(comparison_rows)
    return download_response(csv_content, "pricepilot_portfolio_analysis.csv", "text/csv; charset=utf-8")


@app.route("/history/export.csv")
def history_export_csv():
    csv_content = "\ufeff" + history_to_csv(load_history(get_history_file()))
    return download_response(csv_content, "pricepilot_analysis_history.csv", "text/csv; charset=utf-8")


@app.route("/history/export.json")
def history_export_json():
    json_content = history_to_json(load_history(get_history_file()))
    return download_response(json_content, "pricepilot_analysis_history.json", "application/json; charset=utf-8")


@app.route("/dashboard")
def dashboard_page():
    portfolio_products = _sort_portfolio_products(load_portfolio(get_portfolio_file()))
    comparison_rows = build_portfolio_comparison(portfolio_products) if portfolio_products else []

    focus_record = None
    if comparison_rows:
        focus_row = max(
            comparison_rows,
            key=lambda row: (row["expected_profit"], row["confidence_score"], row["margin"]),
        )
        focus_record = next(
            (record for record in portfolio_products if record.get("id") == focus_row["product_id"]),
            None,
        )

    focus_product = product_record_to_data(focus_record) if focus_record else build_reference_product()
    focus_analysis = run_full_analysis(focus_product)
    focus_scenarios = compare_all_scenarios(focus_product)
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
def about_page():
    return render_template("about.html", page_name="about")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}

    try:
        product = parse_product(data)
        result = run_full_analysis(product)

        if _boolean_input(data.get("save_history"), default=True):
            append_history_entry(get_history_file(), build_history_entry(result))

        return api_success(localize_analysis_result(result, g.current_lang))
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
def api_scenario_compare():
    data = request.get_json(silent=True) or {}

    try:
        product = parse_product(data, scenario_override="NORMAL")
        result = compare_all_scenarios(product)
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
