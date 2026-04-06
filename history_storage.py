from __future__ import annotations

from storage_utils import read_json_list, write_json


def load_history(file_path):
    return read_json_list(file_path, list)


def save_history(file_path, entries):
    write_json(file_path, list(entries))


def append_history_entry(file_path, entry):
    entries = load_history(file_path)
    entries.append(dict(entry))
    save_history(file_path, entries)
    return entry
