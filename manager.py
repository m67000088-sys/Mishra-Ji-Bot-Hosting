"""
manager.py
----------
Deployed user-bots ko subprocess ke through run/stop karta hai.
Har bot ka apna virtual environment hota hai (dependencies isolate rehte
hain), aur token env variable BOT_TOKEN ke through pass hota hai.

Security note: subprocess isolation OS-level sandbox nahi deta.
Production ke liye Docker/gVisor jaisa container sandbox use karo,
warna untrusted code se server compromise ho sakta hai.

Developed by Aditya
"""

import os
import subprocess
import sys
import signal
import db

MAX_FILE_SIZE_MB = 10
MAX_BOTS_PER_USER = 5
PYTHON_MIN_VERSION = (3, 11)


def make_venv(folder_path: str):
    """Bot ke folder ke andar ek alag venv banata hai."""
    venv_path = os.path.join(folder_path, ".venv")
    if not os.path.exists(venv_path):
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
    return venv_path


def install_requirements(folder_path: str, venv_path: str):
    req_file = os.path.join(folder_path, "requirements.txt")
    pip_bin = os.path.join(venv_path, "bin", "pip")
    if os.path.exists(req_file):
        subprocess.run(
            [pip_bin, "install", "--no-cache-dir", "-r", req_file],
            check=True,
            cwd=folder_path,
        )
    # python-telegram-bot library hamesha available honi chahiye
    subprocess.run(
        [pip_bin, "install", "--no-cache-dir", "python-telegram-bot"],
        check=True,
    )


def start_bot(bot_row) -> int:
    """Bot ko background process ke roop mein start karta hai. Returns PID."""
    folder_path = bot_row["folder_path"]
    entry_file = bot_row["entry_file"]
    venv_path = os.path.join(folder_path, ".venv")
    python_bin = os.path.join(venv_path, "bin", "python")

    env = os.environ.copy()
    env["BOT_TOKEN"] = bot_row["bot_token"] or ""

    log_path = os.path.join(folder_path, "run.log")
    log_file = open(log_path, "a")

    process = subprocess.Popen(
        [python_bin, entry_file],
        cwd=folder_path,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # taaki isko alag se kill kar sake
    )
    return process.pid


def stop_bot(pid: int):
    """Ek chal rahe bot process ko band karta hai."""
    if not pid:
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass  # pehle se hi band hai


def is_running(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
