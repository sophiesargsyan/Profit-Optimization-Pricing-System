from __future__ import annotations

from datetime import datetime
from uuid import uuid4

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


def load_portfolio(file_path):
    return read_json_list(file_path, _seed_records)


def save_portfolio(file_path, products):
    write_json(file_path, list(products))


def get_portfolio_product(file_path, product_id):
    for product in load_portfolio(file_path):
        if product.get("id") == product_id:
            return product
    return None


def add_portfolio_product(file_path, product_data):
    products = load_portfolio(file_path)
    now = _timestamp()
    record = {
        "id": uuid4().hex,
        **dict(product_data),
        "created_at": now,
        "updated_at": now,
    }
    products.append(record)
    save_portfolio(file_path, products)
    return record


def update_portfolio_product(file_path, product_id, product_data):
    products = load_portfolio(file_path)
    now = _timestamp()

    for index, product in enumerate(products):
        if product.get("id") != product_id:
            continue

        updated = {
            "id": product_id,
            **dict(product_data),
            "created_at": product.get("created_at", now),
            "updated_at": now,
        }
        products[index] = updated
        save_portfolio(file_path, products)
        return updated

    raise KeyError(product_id)


def delete_portfolio_product(file_path, product_id):
    products = load_portfolio(file_path)
    filtered = [product for product in products if product.get("id") != product_id]
    if len(filtered) == len(products):
        return False

    save_portfolio(file_path, filtered)
    return True
