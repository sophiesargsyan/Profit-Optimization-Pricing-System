from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from statistics import median

from synthetic_data import ensure_synthetic_dataset

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"


def _normalize(value):
    return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class BusinessSettings:
    monthly_fixed_cost: float
    payment_fee_rate: float
    shipping_cost_avg: float
    default_margin_target: float
    currency: str


@dataclass(frozen=True)
class ProductMatch:
    product: dict | None
    level: str


@dataclass
class Dataset:
    data_dir: Path
    products: list
    sales_history: list
    competitor_prices: list
    business_settings: BusinessSettings
    market_calendar: list
    products_by_id: dict
    products_by_name: dict
    category_products: dict
    sales_by_product: dict
    sales_by_category: dict
    competitor_by_product: dict
    latest_competitor_by_product: dict
    market_by_date: dict
    latest_sale_date: date
    forecast_month: int

    def match_product(self, name, category):
        normalized_name = _normalize(name)
        normalized_category = _normalize(category)
        if normalized_name in self.products_by_name:
            return ProductMatch(self.products_by_name[normalized_name], "product")

        category_products = [
            product
            for product in self.category_products.get(category, [])
            if _normalize(product.get("category")) == normalized_category
        ]
        if normalized_name and category_products:
            category_names = {_normalize(item["name"]): item for item in category_products}
            matches = get_close_matches(normalized_name, list(category_names.keys()), n=1, cutoff=0.82)
            if matches:
                return ProductMatch(category_names[matches[0]], "product")

        if category_products:
            return ProductMatch(None, "category")
        return ProductMatch(None, "none")

    def latest_competitor_price(self, product_id):
        snapshot = self.latest_competitor_by_product.get(product_id)
        if snapshot:
            return snapshot["competitor_price"]
        return None

    def category_competitor_price(self, category):
        prices = []
        for product in self.category_products.get(category, []):
            snapshot = self.latest_competitor_by_product.get(product["product_id"])
            if snapshot:
                prices.append(snapshot["competitor_price"])
        return round(median(prices), 2) if prices else None

    def category_reference_price(self, category):
        products = self.category_products.get(category, [])
        if not products:
            return None
        prices = [product["reference_price"] for product in products if product.get("reference_price")]
        return round(median(prices), 2) if prices else None


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_csv(path):
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _parse_products(path):
    products = _load_json(path)
    parsed = []
    for item in products:
        parsed.append(
            {
                **item,
                "unit_cost": float(item["unit_cost"]),
                "packaging_cost": float(item["packaging_cost"]),
                "default_return_rate": float(item["default_return_rate"]),
                "reference_price": float(item["reference_price"]),
                "base_monthly_demand": float(item["base_monthly_demand"]),
            }
        )
    return parsed


def _parse_sales_history(path):
    rows = []
    for row in _load_csv(path):
        rows.append(
            {
                **row,
                "sale_date": date.fromisoformat(row["sale_date"]),
                "sale_price": float(row["sale_price"]),
                "units_sold": int(row["units_sold"]),
                "revenue": float(row["revenue"]),
                "returns": int(row["returns"]),
                "campaign_flag": bool(int(row["campaign_flag"])),
            }
        )
    return rows


def _parse_competitor_prices(path):
    rows = []
    for row in _load_csv(path):
        rows.append(
            {
                **row,
                "observed_date": date.fromisoformat(row["observed_date"]),
                "competitor_price": float(row["competitor_price"]),
            }
        )
    return rows


def _parse_business_settings(path):
    payload = _load_json(path)
    return BusinessSettings(
        monthly_fixed_cost=float(payload["monthly_fixed_cost"]),
        payment_fee_rate=float(payload["payment_fee_rate"]),
        shipping_cost_avg=float(payload["shipping_cost_avg"]),
        default_margin_target=float(payload["default_margin_target"]),
        currency=str(payload["currency"]),
    )


def _parse_market_calendar(path):
    rows = []
    for row in _load_csv(path):
        rows.append(
            {
                **row,
                "date": date.fromisoformat(row["date"]),
                "month": int(row["month"]),
                "holiday_flag": bool(int(row["holiday_flag"])),
                "demand_multiplier": float(row["demand_multiplier"]),
            }
        )
    return rows


def _group_products_by_category(products):
    grouped = {}
    for product in products:
        grouped.setdefault(product["category"], []).append(product)
    return grouped


def _group_sales(sales_history, products_by_id):
    by_product = {}
    by_category = {}
    for row in sales_history:
        by_product.setdefault(row["product_id"], []).append(row)
        product = products_by_id.get(row["product_id"])
        if product:
            by_category.setdefault(product["category"], []).append(row)
    return by_product, by_category


def _group_competitors(competitor_prices):
    by_product = {}
    latest = {}
    for row in sorted(competitor_prices, key=lambda item: (item["product_id"], item["observed_date"])):
        by_product.setdefault(row["product_id"], []).append(row)
        latest[row["product_id"]] = row
    return by_product, latest


@lru_cache(maxsize=4)
def load_business_dataset(data_dir=None):
    target_dir = Path(data_dir or DEFAULT_DATA_DIR)
    ensure_synthetic_dataset(target_dir)

    products = _parse_products(target_dir / "products.json")
    sales_history = _parse_sales_history(target_dir / "sales_history.csv")
    competitor_prices = _parse_competitor_prices(target_dir / "competitor_prices.csv")
    business_settings = _parse_business_settings(target_dir / "business_settings.json")
    market_calendar = _parse_market_calendar(target_dir / "market_calendar.csv")

    products_by_id = {item["product_id"]: item for item in products}
    products_by_name = {_normalize(item["name"]): item for item in products}
    category_products = _group_products_by_category(products)
    sales_by_product, sales_by_category = _group_sales(sales_history, products_by_id)
    competitor_by_product, latest_competitor_by_product = _group_competitors(competitor_prices)
    market_by_date = {item["date"]: item for item in market_calendar}
    latest_sale_date = max(item["sale_date"] for item in sales_history)
    forecast_month = max(item["date"] for item in market_calendar).month

    return Dataset(
        data_dir=target_dir,
        products=products,
        sales_history=sales_history,
        competitor_prices=competitor_prices,
        business_settings=business_settings,
        market_calendar=market_calendar,
        products_by_id=products_by_id,
        products_by_name=products_by_name,
        category_products=category_products,
        sales_by_product=sales_by_product,
        sales_by_category=sales_by_category,
        competitor_by_product=competitor_by_product,
        latest_competitor_by_product=latest_competitor_by_product,
        market_by_date=market_by_date,
        latest_sale_date=latest_sale_date,
        forecast_month=forecast_month,
    )


def clear_dataset_cache():
    load_business_dataset.cache_clear()
