"""v0.6 — 全域設定 (kv, 存 sessions.db 的 settings table)"""
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "sessions.db"

def _conn():
    c = sqlite3.connect(str(DB), timeout=5, isolation_level=None)
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    return c

def get(key, default=None):
    try:
        with _conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default
    except Exception:
        return default

def set(key, value):
    with _conn() as c:
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, json.dumps(value, ensure_ascii=False)))
