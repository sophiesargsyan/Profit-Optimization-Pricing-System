from __future__ import annotations

from storage_utils import read_json_list, write_json


def load_users(file_path):
    return read_json_list(file_path, list)


def save_users(file_path, users):
    write_json(file_path, list(users))


def get_user_by_id(file_path, user_id):
    for user in load_users(file_path):
        if user.get("id") == user_id:
            return user
    return None


def get_user_by_email(file_path, email):
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None

    for user in load_users(file_path):
        if str(user.get("email", "")).strip().lower() == normalized_email:
            return user
    return None


def add_user(file_path, user_data):
    users = load_users(file_path)
    record = dict(user_data)
    users.append(record)
    save_users(file_path, users)
    return record
