from __future__ import annotations

import json
from pathlib import Path


def write_json(file_path, payload):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def read_json_list(file_path, default_factory):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        default_payload = default_factory()
        write_json(path, default_payload)
        return default_payload

    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError):
        default_payload = default_factory()
        write_json(path, default_payload)
        return default_payload

    if not isinstance(payload, list):
        default_payload = default_factory()
        write_json(path, default_payload)
        return default_payload

    return payload
