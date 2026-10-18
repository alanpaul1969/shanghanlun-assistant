"""v0.2.3 PersistentSession - dict-like interface backed by SQLite
取代 flask.session 的 4KB cookie 上限。
- 啟動時發 sid (32-byte random)
- sid 存 client cookie (1KB 以下)
- 資料存 server SQLite
- 介面同 dict (session["key"] = value, session.get("key"))
"""
import threading
import secrets
from flask import request, g, current_app

from session_store import (
    create_session, get_session, update_session, delete_session
)

_local = threading.local()


def _get_sid():
    """取得當前 request 的 sid, 沒 sid 就發一個

    用 flask.g cache 確保同一個 request 內 sid 一致。
    """
    if not hasattr(g, "_session_id"):
        sid = request.cookies.get("session_id")
        if not sid:
            sid = secrets.token_urlsafe(32)
        g._session_id = sid
        # DEBUG
        import os
        with open("/tmp/sid_debug.log", "a") as f:
            f.write(f"NEW sid={sid[:15]}... from_cookie={request.cookies.get('session_id')[:15] if request.cookies.get('session_id') else None} method={request.method} path={request.path}\n")
    return g._session_id


def _get_data(sid):
    """取得 sid 對應的 session data dict, 不存在就 empty"""
    data = get_session(sid)
    return data if data is not None else {}


def _save(sid, data):
    """存回 sid, 創建或更新 (傳 sid 確保不另開新 row)"""
    import session_store
    import time
    import json
    now = int(time.time())
    expires = now + 30 * 86400
    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    existed = get_session(sid) is not None
    with session_store._lock, session_store._get_conn() as c:
        if existed:
            c.execute(
                "UPDATE sessions SET data = ?, updated_at = ?, expires_at = ? WHERE sid = ?",
                (blob, now, expires, sid),
            )
        else:
            c.execute(
                "INSERT INTO sessions (sid, data, created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (sid, blob, now, now, expires),
            )
    # DEBUG
    with open("/tmp/save_debug.log", "a") as f:
        f.write(f"_save sid={sid[:15]}... existed={existed} data_keys={list(data.keys())}\n")


class PersistentSession:
    """dict-like 包裝, 對應 SQLite session 資料

    用法跟 flask.session 幾乎一樣:
        s = PersistentSession()
        s["patient"] = {...}      # 自動保存
        patient = s.get("patient")  # 自動載入
        s.pop("foo", None)
    """

    def __init__(self):
        self._sid = _get_sid()
        self._data = _get_data(self._sid)
        self._dirty = False

    def _save(self):
        if self._dirty:
            _save(self._sid, self._data)
            self._dirty = False

    def __setitem__(self, key, value):
        self._data[key] = value
        self._dirty = True
        self._save()

    def __getitem__(self, key):
        return self._data[key]

    def __delitem__(self, key):
        del self._data[key]
        self._dirty = True
        self._save()

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def pop(self, key, default=None):
        if key in self._data:
            val = self._data.pop(key)
            self._dirty = True
            self._save()
            return val
        return default

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def clear(self):
        self._data.clear()
        self._dirty = True
        self._save()

    def update(self, other):
        self._data.update(other)
        self._dirty = True
        self._save()

    def __repr__(self):
        return f"PersistentSession(sid={self._sid[:10]}..., data_keys={list(self._data.keys())})"


def init_app(app):
    """註冊 after_request: 自動把 sid 寫到 client cookie"""
    @app.after_request
    def _set_sid_cookie(response):
        sid = _get_sid()
        # 30 天 max-age
        response.set_cookie(
            "session_id",
            sid,
            max_age=30 * 86400,
            httponly=True,
            samesite="Lax",
        )
        return response
