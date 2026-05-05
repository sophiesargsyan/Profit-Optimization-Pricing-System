from __future__ import annotations

from datetime import datetime

from storage_utils import read_json_list, write_json


FINANCE_FIELDS = (
    "total_budget",
    "product_cost_budget",
    "marketing_budget",
    "delivery_budget",
    "packaging_budget",
    "operational_budget",
    "reserve_budget",
)


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def load_finance_records(file_path, user_id=None):
    records = read_json_list(file_path, list)
    if user_id is None:
        return records
    return [record for record in records if record.get("user_id") == user_id]


def save_finance_records(file_path, records):
    write_json(file_path, list(records))


def get_finance_record(file_path, user_id=None):
    if user_id is None:
        return None

    records = load_finance_records(file_path, user_id=user_id)
    return dict(records[0]) if records else None


def upsert_finance_record(file_path, finance_data, user_id):
    records = load_finance_records(file_path)
    now = _timestamp()
    payload = {
        field_name: float(finance_data.get(field_name, 0.0) or 0.0)
        for field_name in FINANCE_FIELDS
    }

    for index, record in enumerate(records):
        if record.get("user_id") != user_id:
            continue

        updated = {
            "user_id": user_id,
            **payload,
            "created_at": record.get("created_at", now),
            "updated_at": now,
        }
        records[index] = updated
        save_finance_records(file_path, records)
        return updated

    created = {
        "user_id": user_id,
        **payload,
        "created_at": now,
        "updated_at": now,
    }
    records.append(created)
    save_finance_records(file_path, records)
    return created
