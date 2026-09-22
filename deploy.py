"""
deploy.py
---------
Uploaded .zip / .py file ko validate, extract, aur user ke bot-folder
mein set up karta hai.

Developed by Aditya
"""

import os
import re
import shutil
import zipfile
import uuid

BOTS_ROOT = "bots_data/users"


def safe_bot_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return name[:40] or "bot"


def prepare_folder(user_id: int, original_filename: str) -> str:
    bot_id = uuid.uuid4().hex[:8]
    folder_name = f"{safe_bot_name(os.path.splitext(original_filename)[0])}_{bot_id}"
    folder_path = os.path.join(BOTS_ROOT, str(user_id), folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def extract_upload(local_file_path: str, folder_path: str) -> str:
    """
    Uploaded file ko folder_path mein extract/copy karta hai.
    Returns entry_file (jo run hoga) ka relative path (jaise 'bot.py' ya 'main.py').
    """
    if local_file_path.endswith(".zip"):
        with zipfile.ZipFile(local_file_path, "r") as z:
            z.extractall(folder_path)
        return _find_entry_file(folder_path)
    elif local_file_path.endswith(".py"):
        dest = os.path.join(folder_path, "bot.py")
        shutil.copy(local_file_path, dest)
        return "bot.py"
    else:
        raise ValueError("Sirf .zip ya .py file allowed hai")


def _find_entry_file(folder_path: str) -> str:
    """
    Zip ke andar entry point dhoondhta hai:
    priority -> main.py, bot.py, phir koi bhi .py file jisme
    'ApplicationBuilder' ya 'Updater' ho (python-telegram-bot ka signature).
    """
    candidates = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, f), folder_path)
                candidates.append(rel)

    for preferred in ("main.py", "bot.py"):
        if preferred in candidates:
            return preferred

    for rel in candidates:
        full = os.path.join(folder_path, rel)
        try:
            with open(full, "r", errors="ignore") as fh:
                content = fh.read()
            if "ApplicationBuilder" in content or "Updater(" in content:
                return rel
        except OSError:
            continue

    if candidates:
        return candidates[0]

    raise ValueError("Koi .py file nahi mili uploaded content mein")


def validate_size(file_size_bytes: int, max_mb: int = 10):
    max_bytes = max_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValueError(f"File size {max_mb}MB se zyada hai. Allowed limit: {max_mb}MB")
