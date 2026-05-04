from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from catalog_profiles import CATEGORY_PROFILES
from product_defaults import SEED_PORTFOLIO_PRODUCTS
from storage_utils import read_json_list, write_json


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def _seed_records():
    seeded_at = _timestamp()
    return [
        {
            "id": uuid4().hex,
            **product,
            "created_at": seeded_at,
            "updated_at": seeded_at,
        }
        for product in SEED_PORTFOLIO_PRODUCTS
    ]


def _normalize_product_record(product):
    normalized = dict(product)
    normalized_category = str(normalized.get("category", "")).strip()
    if normalized_category not in CATEGORY_PROFILES:
        name = str(normalized.get("name", "")).lower()
        if any(token in name for token in ("serum", "mist", "mask", "skin", "beauty")):
            normalized["category"] = "Beauty"
        elif any(token in name for token in ("dress", "shirt", "knit", "pants", "linen")):
            normalized["category"] = "Fashion"
        elif any(token in name for token in ("necklace", "earring", "ring", "pearl", "jewel")):
            normalized["category"] = "Jewelry"
        else:
            normalized["category"] = "Accessories"
    normalized.setdefault("current_price", normalized.get("base_price", ""))
    normalized.setdefault("units_sold_30d", normalized.get("base_demand", ""))
    normalized.setdefault("elasticity_override", normalized.get("elasticity", ""))
    normalized.setdefault("return_rate_override", normalized.get("return_rate", ""))
    normalized.setdefault("fixed_cost_allocation_override", normalized.get("fixed_cost", ""))
    normalized.setdefault("target_margin_override", normalized.get("desired_margin", ""))
    normalized.setdefault("marketing_factor_override", normalized.get("marketing_factor_override", ""))
    normalized.setdefault("inventory_constraint_override", normalized.get("inventory", ""))
    return normalized


def load_portfolio(file_path, user_id=None):
    products = read_json_list(file_path, _seed_records)
    normalized = [_normalize_product_record(product) for product in products]
    if normalized != products:
        save_portfolio(file_path, normalized)
    if user_id is None:
        return normalized
    return [product for product in normalized if product.get("user_id") == user_id]


def save_portfolio(file_path, products):
    write_json(file_path, list(products))


def get_portfolio_product(file_path, product_id, user_id=None):
    for product in load_portfolio(file_path, user_id=user_id):
        if product.get("id") == product_id:
            return product
    return None


def add_portfolio_product(file_path, product_data, user_id=None):
    products = load_portfolio(file_path)
    now = _timestamp()
    record = {
        "id": uuid4().hex,
        **dict(product_data),
        "created_at": now,
        "updated_at": now,
    }
    if user_id is not None:
        record["user_id"] = user_id
    products.append(record)
    save_portfolio(file_path, products)
    return record


def update_portfolio_product(file_path, product_id, product_data, user_id=None):
    products = load_portfolio(file_path)
    now = _timestamp()

    for index, product in enumerate(products):
        if product.get("id") != product_id:
            continue
        if user_id is not None and product.get("user_id") != user_id:
            continue

        updated = {
            "id": product_id,
            **dict(product_data),
            "created_at": product.get("created_at", now),
            "updated_at": now,
        }
        if user_id is not None:
            updated["user_id"] = user_id
        products[index] = updated
        save_portfolio(file_path, products)
        return updated

    raise KeyError(product_id)


def delete_portfolio_product(file_path, product_id, user_id=None):
    products = load_portfolio(file_path)
    filtered = [
        product
        for product in products
        if product.get("id") != product_id
        or (user_id is not None and product.get("user_id") != user_id)
    ]
    if len(filtered) == len(products):
        return False

    save_portfolio(file_path, filtered)
    return True
