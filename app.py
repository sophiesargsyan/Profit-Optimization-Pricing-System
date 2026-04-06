import json
import os
import secrets
from functools import lru_cache
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session, url_for

from pricing_engine import ProductData, compare_all_scenarios, run_full_analysis

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
# A deployment should supply FLASK_SECRET_KEY, but local demos still work without manual setup.
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

DEFAULT_LANG = "en"
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hy": "Հայերեն",
    "ru": "Русский",
}
TRANSLATIONS_DIR = Path(__file__).resolve().parent / "translations"

STRING_FIELDS = {
    "name": {"default": "Product", "label": "Product name", "max_length": 120},
    "category": {"default": "General", "label": "Category", "max_length": 80},
}
NUMERIC_FIELDS = {
    "unit_cost": {"label": "Unit cost", "min": 0, "max": 1_000_000, "type": float},
    "fixed_cost": {"label": "Fixed cost", "min": 0, "max": 100_000_000, "type": float},
    "base_price": {"label": "Base price", "min": 0.01, "max": 1_000_000, "type": float},
    "competitor_price": {
        "label": "Competitor price",
        "min": 0.01,
        "max": 1_000_000,
        "type": float,
    },
    "base_demand": {"label": "Base demand", "min": 1, "max": 1_000_000, "type": float},
    "inventory": {"label": "Inventory", "min": 1, "max": 1_000_000, "type": int},
    "elasticity": {"label": "Elasticity", "min": -5.0, "max": -0.05, "type": float},
    "marketing_budget": {
        "label": "Marketing budget",
        "min": 0,
        "max": 100_000_000,
        "type": float,
    },
    "return_rate": {"label": "Return rate", "min": 0, "max": 0.49, "type": float},
    "desired_margin": {"label": "Desired margin", "min": 0.1, "max": 89.9, "type": float},
}


DEFAULT_PRODUCT = {
    "name": "Smart Thermos Bottle",
    "category": "Home & Lifestyle",
    "unit_cost": 18.0,
    "fixed_cost": 3200.0,
    "base_price": 39.0,
    "competitor_price": 36.0,
    "base_demand": 420.0,
    "inventory": 500,
    "elasticity": -1.35,
    "marketing_budget": 1400.0,
    "return_rate": 0.06,
    "desired_margin": 28.0,
    "scenario": "NORMAL",
}


@lru_cache(maxsize=None)
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


def translate_dynamic(translations, prefix, value):
    return translations.get(f"{prefix}.{value}", value)


def format_translation(translations, key, **kwargs):
    template = translations.get(key, key)
    return template.format(**kwargs)


def translated_message(key, fallback):
    translations = getattr(g, "translations", get_translations(DEFAULT_LANG))
    return translations.get(key, fallback)


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


def build_localized_explanation(result, lang):
    translations = get_translations(lang)
    product = result["product"]
    adjusted = result["adjusted_inputs"]
    best = result["best_strategy"]
    strategy_name = translate_dynamic(translations, "strategy", best["strategy"])
    risk_name = translate_dynamic(translations, "risk", best["risk_level"])
    scenario_name = translate_dynamic(translations, "scenario", product["scenario"])

    comparison_context = best.get("comparison_context", {})
    next_best_name = translate_dynamic(
        translations,
        "strategy",
        comparison_context.get("next_best_strategy", ""),
    )

    if best["break_even_units"] is None:
        break_even_note = translations["explanation.detail.break_even.none"]
    elif best["break_even_units"] <= product["inventory"]:
        break_even_note = format_translation(
            translations,
            "explanation.detail.break_even.inside",
            break_even_units=best["break_even_units"],
            inventory=product["inventory"],
        )
    else:
        break_even_note = format_translation(
            translations,
            "explanation.detail.break_even.outside",
            break_even_units=best["break_even_units"],
            inventory=product["inventory"],
        )

    details = [
        format_translation(
            translations,
            "explanation.detail.selection",
            strategy=strategy_name,
            price=best["price"],
            revenue=best["revenue"],
            profit=best["profit"],
        ),
        format_translation(
            translations,
            "explanation.detail.metrics",
            profit_margin=best["profit_margin"],
            contribution_margin=best["contribution_margin"],
            roi=best["ROI"],
            risk_level=risk_name,
            risk_score=best["risk_score"],
        ),
        format_translation(
            translations,
            "explanation.detail.elasticity",
            elasticity=product["elasticity"],
            elasticity_effect=best["elasticity_effect"],
        ),
        format_translation(
            translations,
            "explanation.detail.scenario",
            scenario=scenario_name,
            adjusted_demand=adjusted["adjusted_base_demand"],
            competitor_price=adjusted["adjusted_competitor_price"],
            adjusted_unit_cost=adjusted["adjusted_unit_cost"],
            adjusted_return_rate=round(adjusted["adjusted_return_rate"] * 100, 2),
        ),
    ]

    if comparison_context:
        details.append(
            format_translation(
                translations,
                "explanation.detail.preference",
                next_best_strategy=next_best_name,
                score_gap=comparison_context["score_gap"],
                profit_gap=comparison_context["profit_gap"],
                risk_gap=comparison_context["risk_gap"],
            )
        )

    stability = best.get("scenario_stability")
    if stability:
        details.append(
            format_translation(
                translations,
                "explanation.detail.stability",
                mean_profit=stability["mean_profit"],
                profit_std_dev=stability["profit_std_dev"],
                stability_score=stability["stability_score"],
            )
        )

    details.append(break_even_note)

    caution = None
    if best["risk_level"] in {"Medium", "High"}:
        caution_key = f"explanation.caution.{best['risk_level'].lower()}"
        caution = format_translation(
            translations,
            caution_key,
            risk_level=risk_name,
        )

    return {
        "title": format_translation(
            translations,
            "explanation.title",
            strategy=strategy_name,
            product=product["name"],
        ),
        "summary": format_translation(
            translations,
            "explanation.summary",
            price=best["price"],
            product=product["name"],
            profit=best["profit"],
            profit_margin=best["profit_margin"],
            roi=best["ROI"],
            risk_level=risk_name.lower(),
        ),
        "details": details,
        "caution": caution,
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
    }


def _parse_string_field(payload, field_name):
    config = STRING_FIELDS[field_name]
    value = str(payload.get(field_name, config["default"])).strip()
    if not value:
        raise ValueError(f"{config['label']} is required.")
    if len(value) > config["max_length"]:
        raise ValueError(f"{config['label']} must be at most {config['max_length']} characters.")
    return value


def _parse_numeric_field(payload, field_name):
    config = NUMERIC_FIELDS[field_name]
    raw_value = payload.get(field_name)
    if raw_value in (None, ""):
        raise ValueError(f"{config['label']} is required.")

    try:
        parsed = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{config['label']} must be a valid number.") from exc

    if parsed < config["min"] or parsed > config["max"]:
        raise ValueError(
            f"{config['label']} must be between {config['min']} and {config['max']}."
        )

    return int(parsed) if config["type"] is int else float(parsed)


def parse_product(data, scenario_override=None):
    if not isinstance(data, dict):
        raise ValueError(translated_message("api.error.invalid_payload", "Invalid request data."))

    scenario = scenario_override or str(data.get("scenario", "NORMAL")).upper()
    if scenario not in {"LOW", "NORMAL", "HIGH", "PROMO"}:
        raise ValueError("Scenario must be LOW, NORMAL, HIGH, or PROMO.")

    return ProductData(
        name=_parse_string_field(data, "name"),
        category=_parse_string_field(data, "category"),
        unit_cost=_parse_numeric_field(data, "unit_cost"),
        fixed_cost=_parse_numeric_field(data, "fixed_cost"),
        base_price=_parse_numeric_field(data, "base_price"),
        competitor_price=_parse_numeric_field(data, "competitor_price"),
        base_demand=_parse_numeric_field(data, "base_demand"),
        inventory=_parse_numeric_field(data, "inventory"),
        elasticity=_parse_numeric_field(data, "elasticity"),
        marketing_budget=_parse_numeric_field(data, "marketing_budget"),
        return_rate=_parse_numeric_field(data, "return_rate"),
        desired_margin=_parse_numeric_field(data, "desired_margin"),
        scenario=scenario,
    )


def build_demo_product():
    return parse_product(DEFAULT_PRODUCT)


@app.route("/")
def index():
    return render_template("index.html", page_name="home")


@app.route("/analyze")
def analyze_page():
    return render_template(
        "analyze.html",
        page_name="analyze",
        default_values=DEFAULT_PRODUCT,
    )


@app.route("/dashboard")
def dashboard_page():
    demo_product = build_demo_product()
    demo_analysis = run_full_analysis(demo_product)
    demo_scenarios = compare_all_scenarios(demo_product)
    return render_template(
        "dashboard.html",
        page_name="dashboard",
        demo_analysis=demo_analysis,
        demo_scenarios=demo_scenarios,
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
