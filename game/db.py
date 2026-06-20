import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


def db_path() -> Path:
    return Path(os.getenv("GAME_DB_PATH", "providnyk.sqlite3"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timeout_seconds = max(1, int(os.getenv("DB_BUSY_TIMEOUT_MS", "10000"))) / 1000
    conn = sqlite3.connect(path, timeout=timeout_seconds)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(f"PRAGMA busy_timeout={int(timeout_seconds * 1000)};")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_state (
                telegram_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                entry TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_journal_player_id ON journal (telegram_id, id DESC)"
        )


def get_state(telegram_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT state_json FROM player_state WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def save_state(telegram_id: int, state: Dict[str, Any]) -> None:
    data = json.dumps(state, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO player_state (telegram_id, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, data),
        )


def delete_state(telegram_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM player_state WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM journal WHERE telegram_id = ?", (telegram_id,))


def add_journal(telegram_id: int, entry: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO journal (telegram_id, entry) VALUES (?, ?)",
            (telegram_id, entry[:1000]),
        )


def get_journal(telegram_id: int, limit: int = 10) -> List[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT entry FROM journal WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit),
        ).fetchall()
    return [row[0] for row in rows]
