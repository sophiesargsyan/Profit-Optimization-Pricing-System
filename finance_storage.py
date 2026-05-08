from __future__ import annotations

from datetime import datetime

from storage_utils import read_json_list, write_json


LEGACY_FINANCE_FIELDS = (
    "total_budget",
    "product_cost_budget",
    "marketing_budget",
    "delivery_budget",
    "packaging_budget",
    "operational_budget",
    "reserve_budget",
)

SMART_BUDGET_INPUT_FIELDS = (
    "available_capital",
    "organization_type",
    "business_activity",
    "business_status",
    "business_goal",
    "average_monthly_revenue",
    "fixed_costs",
    "variable_costs",
    "employees_count",
)

SMART_BUDGET_NUMERIC_FIELDS = (
    "available_capital",
    "average_monthly_revenue",
    "fixed_costs",
    "variable_costs",
)

SMART_BUDGET_RESULT_FIELDS = (
    "values",
    "summary",
    "allocation_rows",
    "scenario_rows",
    "warnings",
    "recommendations",
    "method_notes",
)


def _timestamp():
    return datetime.now().isoformat(timespec="seconds")


def _float_value(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def _dict_value(value):
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value):
    return list(value) if isinstance(value, list) else []


def _is_smart_budget_payload(finance_data):
    if not isinstance(finance_data, dict):
        return False

    if any(field_name in finance_data for field_name in SMART_BUDGET_RESULT_FIELDS):
        return True

    input_values = finance_data.get("input_values")
    return isinstance(input_values, dict) and any(
        field_name in input_values for field_name in SMART_BUDGET_INPUT_FIELDS
    )


def _normalized_input_values(finance_data):
    input_source = finance_data.get("input_values") if isinstance(finance_data, dict) else {}
    values_source = finance_data.get("values") if isinstance(finance_data, dict) else {}
    if not isinstance(input_source, dict):
        input_source = {}
    if not isinstance(values_source, dict):
        values_source = {}

    normalized = {}
    for field_name in SMART_BUDGET_INPUT_FIELDS:
        raw_value = input_source.get(field_name, values_source.get(field_name))
        if field_name == "employees_count":
            normalized[field_name] = int(_float_value(raw_value, 0.0))
        elif field_name in SMART_BUDGET_NUMERIC_FIELDS:
            normalized[field_name] = None if raw_value in (None, "") else _float_value(raw_value)
        else:
            normalized[field_name] = str(raw_value or "").strip()
    return normalized


def _allocation_lookup(rows):
    allocations = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        field_name = row.get("field_name")
        if not field_name:
            continue
        allocations[field_name] = _float_value(row.get("amount", 0.0))
    return allocations


def _compatibility_fields(input_values, values, summary, allocation_rows):
    allocations = _allocation_lookup(allocation_rows)
    values = values if isinstance(values, dict) else {}
    summary = summary if isinstance(summary, dict) else {}

    available_capital = _float_value(
        input_values.get("available_capital")
        or summary.get("available_capital")
        or values.get("available_capital")
    )
    total_allocated = _float_value(summary.get("total_allocated"), available_capital)
    marketing_budget = _float_value(
        allocations.get("marketing_budget", values.get("marketing_budget", 0.0))
    )
    product_cost_budget = _float_value(
        allocations.get("inventory_or_purchase_budget", values.get("inventory_or_purchase_budget", 0.0))
    )
    reserve_budget = _float_value(
        allocations.get("emergency_reserve", values.get("emergency_reserve", 0.0))
    )
    operational_budget = _float_value(
        allocations.get("operational_budget", values.get("operational_budget", 0.0))
    )

    return {
        "total_budget": available_capital or total_allocated,
        "product_cost_budget": product_cost_budget,
        "marketing_budget": marketing_budget,
        "delivery_budget": 0.0,
        "packaging_budget": 0.0,
        "operational_budget": operational_budget,
        "reserve_budget": reserve_budget,
    }


def _normalize_smart_budget_payload(finance_data):
    input_values = _normalized_input_values(finance_data)
    values = _dict_value(finance_data.get("values"))
    summary = _dict_value(finance_data.get("summary"))
    allocation_rows = _list_value(finance_data.get("allocation_rows"))
    scenario_rows = _list_value(finance_data.get("scenario_rows"))
    warnings = _list_value(finance_data.get("warnings"))
    recommendations = _list_value(finance_data.get("recommendations"))
    method_notes = _list_value(finance_data.get("method_notes"))
    compatibility_fields = _compatibility_fields(input_values, values, summary, allocation_rows)

    return {
        "planner_version": "smart_budget_planner_v1",
        "input_values": input_values,
        "values": values,
        "summary": summary,
        "allocation_rows": allocation_rows,
        "scenario_rows": scenario_rows,
        "warnings": warnings,
        "recommendations": recommendations,
        "method_notes": method_notes,
        **compatibility_fields,
    }


def _normalize_legacy_payload(finance_data):
    return {
        field_name: _float_value(finance_data.get(field_name, 0.0))
        for field_name in LEGACY_FINANCE_FIELDS
    }


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
    payload = (
        _normalize_smart_budget_payload(finance_data)
        if _is_smart_budget_payload(finance_data)
        else _normalize_legacy_payload(finance_data)
    )

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
