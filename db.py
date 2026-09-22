"""
db.py
-----
SQLite database layer for TheHostServer.
Har deployed bot ka record yaha store hota hai: kis user ne, kaunsa bot,
kaha (file path) deploy kiya, uska token, aur uska current status/PID.

Developed by Aditya
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "bots_data/hoster.db"


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_name TEXT NOT NULL,
                folder_path TEXT NOT NULL,
                entry_file TEXT NOT NULL,
                bot_token TEXT,
                pid INTEGER,
                status TEXT DEFAULT 'stopped',   -- stopped | running | crashed
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def count_user_bots(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM bots WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["c"]


def add_bot(user_id, bot_name, folder_path, entry_file, bot_token):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bots
               (user_id, bot_name, folder_path, entry_file, bot_token, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'stopped', ?)""",
            (user_id, bot_name, folder_path, entry_file, bot_token, int(time.time())),
        )
        conn.commit()
        return cur.lastrowid


def list_bots(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()


def get_bot(bot_id, user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)
        ).fetchone()


def update_status(bot_id, status, pid=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bots SET status = ?, pid = ? WHERE id = ?",
            (status, pid, bot_id),
        )
        conn.commit()


def delete_bot(bot_id, user_id):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM bots WHERE id = ? AND user_id = ?", (bot_id, user_id)
        )
        conn.commit()
