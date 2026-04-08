from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path
from random import Random

from catalog_profiles import CATEGORY_PROFILES, COMPETITOR_NAMES, PRODUCT_BLUEPRINTS
from storage_utils import write_json

DATASET_FILES = (
    "products.json",
    "sales_history.csv",
    "competitor_prices.csv",
    "business_settings.json",
    "market_calendar.csv",
)

START_DATE = date(2025, 5, 1)
END_DATE = date(2026, 4, 30)
RANDOM_SEED = 41

MARKET_MONTH_FACTORS = {
    1: 0.88,
    2: 0.95,
    3: 1.03,
    4: 1.08,
    5: 1.02,
    6: 0.97,
    7: 0.94,
    8: 0.99,
    9: 1.04,
    10: 1.09,
    11: 1.18,
    12: 1.24,
}

BUSINESS_SETTINGS = {
    "monthly_fixed_cost": 48500.0,
    "payment_fee_rate": 0.029,
    "shipping_cost_avg": 4.6,
    "default_margin_target": 0.29,
    "currency": "USD",
}

HOLIDAY_DATES = {
    date(2025, 5, 11),
    date(2025, 11, 28),
    date(2025, 12, 1),
    date(2025, 12, 19),
    date(2025, 12, 20),
    date(2025, 12, 21),
    date(2026, 2, 14),
    date(2026, 3, 8),
}

CAMPAIGN_WINDOWS = (
    (date(2025, 8, 18), date(2025, 8, 31)),
    (date(2025, 11, 24), date(2025, 12, 2)),
    (date(2026, 3, 1), date(2026, 3, 14)),
)


def _clamp(value, lower, upper):
    return max(lower, min(value, upper))


def _date_range(start_date, end_date):
    total_days = (end_date - start_date).days
    for offset in range(total_days + 1):
        yield start_date + timedelta(days=offset)


def _month_start_points():
    current = START_DATE.replace(day=1)
    months = []
    while current <= END_DATE:
        months.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


def _season_name(current_date):
    if current_date.month in (12, 1, 2):
        return "Winter"
    if current_date.month in (3, 4, 5):
        return "Spring"
    if current_date.month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def _campaign_flag(current_date):
    return any(start <= current_date <= end for start, end in CAMPAIGN_WINDOWS)


def _market_calendar_rows():
    rows = []
    for current_date in _date_range(START_DATE, END_DATE):
        multiplier = MARKET_MONTH_FACTORS[current_date.month]
        if _campaign_flag(current_date):
            multiplier *= 1.04
        if current_date in HOLIDAY_DATES:
            multiplier *= 1.12

        rows.append(
            {
                "date": current_date.isoformat(),
                "month": current_date.month,
                "season": _season_name(current_date),
                "holiday_flag": int(current_date in HOLIDAY_DATES),
                "demand_multiplier": round(multiplier, 4),
            }
        )
    return rows


def _monthly_price_schedule(rng, product):
    movement = 0.0
    schedule = {}
    for month_start in _month_start_points():
        movement = movement * 0.35 + rng.uniform(-0.05, 0.05)
        movement = _clamp(movement, -0.08, 0.09)
        schedule[(month_start.year, month_start.month)] = movement
    return schedule


def _competitor_snapshots(rng, market_lookup):
    rows = []
    latest_by_product = {}

    for blueprint in PRODUCT_BLUEPRINTS:
        category = blueprint["category"]
        competitor_name = COMPETITOR_NAMES[category][
            int(blueprint["product_id"][-1]) % len(COMPETITOR_NAMES[category])
        ]
        base_price = blueprint["base_price"] * rng.uniform(0.93, 1.04)
        weekly_index = 0

        for current_date in _date_range(START_DATE, END_DATE):
            if current_date.weekday() != 1:
                continue

            market_multiplier = market_lookup[current_date.isoformat()]["demand_multiplier"]
            seasonal_shift = (market_multiplier - 1.0) * 0.18
            pulse = math.sin(weekly_index / 2.9 + len(category)) * 0.024
            campaign_shift = -0.05 if _campaign_flag(current_date) else 0.0
            noise = rng.uniform(-0.018, 0.018)
            competitor_price = base_price * (1.0 + seasonal_shift + pulse + campaign_shift + noise)
            competitor_price = _clamp(competitor_price, blueprint["unit_cost"] * 1.8, blueprint["base_price"] * 1.22)

            snapshot = {
                "record_id": f"{blueprint['product_id']}-{current_date.isoformat()}",
                "product_id": blueprint["product_id"],
                "competitor_name": competitor_name,
                "observed_date": current_date.isoformat(),
                "competitor_price": round(competitor_price, 2),
            }
            rows.append(snapshot)
            latest_by_product.setdefault(blueprint["product_id"], {})[current_date.isoformat()] = snapshot
            weekly_index += 1

    return rows, latest_by_product


def _latest_competitor_price(product_snapshots, current_date):
    latest_snapshot = None
    for snapshot_date in sorted(product_snapshots):
        if snapshot_date > current_date.isoformat():
            break
        latest_snapshot = product_snapshots[snapshot_date]
    return latest_snapshot["competitor_price"] if latest_snapshot else None


def _sales_history_rows(rng, market_lookup, competitor_lookup):
    rows = []

    for blueprint in PRODUCT_BLUEPRINTS:
        category_profile = CATEGORY_PROFILES[blueprint["category"]]
        base_daily_demand = blueprint["base_monthly_demand"] / 30.4
        price_schedule = _monthly_price_schedule(rng, blueprint)

        for current_date in _date_range(START_DATE, END_DATE):
            market_row = market_lookup[current_date.isoformat()]
            monthly_bias = category_profile["monthly_bias"][current_date.month]
            market_factor = market_row["demand_multiplier"]
            campaign_flag = _campaign_flag(current_date)
            weekday_factor = 1.04 if current_date.weekday() in {4, 5} else 0.98 if current_date.weekday() == 1 else 1.0
            latest_competitor = _latest_competitor_price(
                competitor_lookup.get(blueprint["product_id"], {}),
                current_date,
            )
            schedule_factor = price_schedule[(current_date.year, current_date.month)]
            campaign_discount = rng.uniform(0.06, 0.12) if campaign_flag else 0.0
            sale_price = blueprint["base_price"] * (1.0 + schedule_factor - campaign_discount)
            sale_price = _clamp(sale_price, blueprint["unit_cost"] * 1.8, blueprint["base_price"] * 1.24)

            price_effect = (sale_price / blueprint["base_price"]) ** blueprint["elasticity"]
            competitor_gap = 0.0
            if latest_competitor:
                competitor_gap = (latest_competitor - sale_price) / latest_competitor
            competitor_effect = _clamp(
                1.0 + competitor_gap * blueprint["competitor_sensitivity"],
                0.82,
                1.18,
            )
            marketing_effect = blueprint["campaign_lift"] if campaign_flag else 1.0
            noise = _clamp(rng.gauss(1.0, 0.08), 0.8, 1.22)

            demand = (
                base_daily_demand
                * monthly_bias
                * market_factor
                * weekday_factor
                * price_effect
                * competitor_effect
                * marketing_effect
                * noise
            )
            units_sold = max(0, round(demand))

            return_noise = _clamp(rng.gauss(1.0, 0.09), 0.78, 1.25)
            return_rate = blueprint["default_return_rate"] * (1.05 if campaign_flag else 1.0) * return_noise
            returns = min(units_sold, round(units_sold * _clamp(return_rate, 0.0, 0.28)))
            revenue = round(units_sold * sale_price, 2)

            rows.append(
                {
                    "sale_id": f"{blueprint['product_id']}-{current_date.isoformat()}",
                    "product_id": blueprint["product_id"],
                    "sale_date": current_date.isoformat(),
                    "sale_price": round(sale_price, 2),
                    "units_sold": units_sold,
                    "revenue": revenue,
                    "returns": returns,
                    "campaign_flag": int(campaign_flag),
                }
            )

    return rows


def _products_payload():
    payload = []
    for blueprint in PRODUCT_BLUEPRINTS:
        payload.append(
            {
                "product_id": blueprint["product_id"],
                "name": blueprint["name"],
                "category": blueprint["category"],
                "unit_cost": blueprint["unit_cost"],
                "packaging_cost": blueprint["packaging_cost"],
                "default_return_rate": blueprint["default_return_rate"],
                "reference_price": blueprint["base_price"],
                "base_monthly_demand": blueprint["base_monthly_demand"],
            }
        )
    return payload


def _write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_synthetic_dataset(output_dir, seed=RANDOM_SEED):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rng = Random(seed)
    market_calendar = _market_calendar_rows()
    market_lookup = {row["date"]: row for row in market_calendar}
    competitor_rows, competitor_lookup = _competitor_snapshots(rng, market_lookup)
    sales_history = _sales_history_rows(rng, market_lookup, competitor_lookup)

    write_json(output_path / "products.json", _products_payload())
    _write_csv(
        output_path / "sales_history.csv",
        ["sale_id", "product_id", "sale_date", "sale_price", "units_sold", "revenue", "returns", "campaign_flag"],
        sales_history,
    )
    _write_csv(
        output_path / "competitor_prices.csv",
        ["record_id", "product_id", "competitor_name", "observed_date", "competitor_price"],
        competitor_rows,
    )
    write_json(output_path / "business_settings.json", BUSINESS_SETTINGS)
    _write_csv(
        output_path / "market_calendar.csv",
        ["date", "month", "season", "holiday_flag", "demand_multiplier"],
        market_calendar,
    )


def ensure_synthetic_dataset(data_dir):
    data_path = Path(data_dir)
    missing = [filename for filename in DATASET_FILES if not (data_path / filename).exists()]
    if missing:
        generate_synthetic_dataset(data_path)


if __name__ == "__main__":
    generate_synthetic_dataset(Path(__file__).resolve().parent / "data")
