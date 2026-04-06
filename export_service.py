from __future__ import annotations

import csv
import json
from io import StringIO


PORTFOLIO_EXPORT_FIELDS = [
    "product_name",
    "category",
    "scenario",
    "base_price",
    "recommended_price",
    "expected_demand",
    "expected_revenue",
    "expected_profit",
    "margin",
    "risk_level",
    "recommended_strategy",
]

HISTORY_EXPORT_FIELDS = [
    "timestamp",
    "product_name",
    "selected_scenario",
    "recommended_strategy",
    "recommended_price",
    "expected_profit",
    "risk_level",
]


def _rows_to_csv(fieldnames, rows):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def portfolio_analysis_to_csv(rows):
    return _rows_to_csv(PORTFOLIO_EXPORT_FIELDS, rows)


def history_to_csv(entries):
    return _rows_to_csv(HISTORY_EXPORT_FIELDS, entries)


def history_to_json(entries):
    return json.dumps(list(entries), ensure_ascii=False, indent=2)
