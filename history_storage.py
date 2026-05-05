from __future__ import annotations

from storage_utils import read_json_list, write_json


def load_history(file_path, user_id=None):
    entries = read_json_list(file_path, list)
    if user_id is None:
        return entries
    return [entry for entry in entries if entry.get("user_id") == user_id]


def save_history(file_path, entries):
    write_json(file_path, list(entries))


def append_history_entry(file_path, entry, user_id=None):
    entries = load_history(file_path)
    record = dict(entry)
    if user_id is not None:
        record["user_id"] = user_id
    entries.append(record)
    save_history(file_path, entries)
    return record


def delete_history_entry(file_path, entry_id, user_id=None):
    entries = load_history(file_path)
    filtered = [
        entry
        for entry in entries
        if entry.get("id") != entry_id
        or (user_id is not None and entry.get("user_id") != user_id)
    ]
    if len(filtered) == len(entries):
        return False

    save_history(file_path, filtered)
    return True
