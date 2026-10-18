"""v0.2.3 server-side session store (SQLite)
取代 Flask cookie session 的 4KB 上限。
- session id 是 32-byte random string 存 cookie
- session data 存 SQLite BLOB (JSON)
- 30 天 TTL
"""
import sqlite3
import json
import secrets
import time
from pathlib import Path
from threading import Lock

DB_PATH = Path(__file__).parent / "sessions.db"
DB_PATH.touch(exist_ok=True)

_lock = Lock()


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=5, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            sid        TEXT PRIMARY KEY,
            data       BLOB NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    return conn


def init_db():
    """啟動時建表"""
    with _lock, _get_conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                sid        TEXT PRIMARY KEY,
                data       BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
        """)
        # 清過期 session
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))


def create_session(data: dict, ttl_seconds: int = 30 * 86400) -> str:
    """建立新 session, 回傳 32-byte hex sid"""
    sid = secrets.token_urlsafe(32)
    now = int(time.time())
    expires = now + ttl_seconds
    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with _lock, _get_conn() as c:
        c.execute(
            "INSERT INTO sessions (sid, data, created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (sid, blob, now, now, expires),
        )
    return sid


def get_session(sid: str) -> dict | None:
    if not sid:
        return None
    with _lock, _get_conn() as c:
        row = c.execute(
            "SELECT data, expires_at FROM sessions WHERE sid = ?", (sid,)
        ).fetchone()
    if not row:
        return None
    blob, expires_at = row
    if expires_at < int(time.time()):
        return None
    return json.loads(blob.decode("utf-8"))


def update_session(sid: str, data: dict, ttl_seconds: int = 30 * 86400) -> bool:
    """更新 session, 順便 reset expires"""
    now = int(time.time())
    expires = now + ttl_seconds
    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    with _lock, _get_conn() as c:
        cur = c.execute(
            "UPDATE sessions SET data = ?, updated_at = ?, expires_at = ? WHERE sid = ?",
            (blob, now, expires, sid),
        )
    return cur.rowcount > 0


def delete_session(sid: str):
    if not sid:
        return
    with _lock, _get_conn() as c:
        c.execute("DELETE FROM sessions WHERE sid = ?", (sid,))


# 啟動時建表
init_db()


def list_sessions():
    """v0.6.2: 列出所有 sessions (新→舊), 供 /history 頁"""
    out = []
    with _lock, _get_conn() as c:
        rows = c.execute(
            "SELECT sid, data, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    import json
    for sid, blob, created, updated in rows:
        try:
            d = json.loads(blob)
        except Exception:
            continue
        out.append({"sid": sid, "data": d, "created_at": created, "updated_at": updated})
    return out
