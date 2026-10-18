"""v0.6 — 使用者可選 LLM/VLM 後端 (設定頁 /settings)

預設:
  LLM = 8085 thinking-off proxy (grammar-400 繞道)
  VLM = 8085 (舌診 VLM 同 proxy)
使用者可切到 8080 直連 / 8083 Bonsai / 自訂 URL+model。
所有 LLM 模組一律經 llm_config.get_llm() / get_vlm() 取端點。
"""
import urllib.request

from settings_store import get, set as _set

LLM_PRESETS = [
    {"id": "proxy8085", "name": "8085 thinking-off proxy（預設，繞 grammar-400）",
     "base": "http://127.0.0.1:8085", "model": "qwen3.8-27b-nvfp4"},
    {"id": "direct8080", "name": "8080 直連（256K ctx；結構化輸出可能 400）",
     "base": "http://127.0.0.1:8080", "model": "qwen3.8-27b-nvfp4"},
    {"id": "bonsai8083", "name": "8083 Bonsai-2-27B（快但事實飄）",
     "base": "http://127.0.0.1:8083", "model": "bonsai-2-27b"},
]
VLM_PRESETS = [
    {"id": "proxy8085", "name": "8085 proxy（預設）",
     "base": "http://127.0.0.1:8085", "model": "qwen3.8-27b-nvfp4"},
    {"id": "direct8080", "name": "8080 直連（vision mmproj 在此）",
     "base": "http://127.0.0.1:8080", "model": "qwen3.8-27b-nvfp4"},
]

DEFAULTS = {"llm": "proxy8085", "vlm": "proxy8085",
            "llm_custom_base": "", "llm_custom_model": "",
            "vlm_custom_base": "", "vlm_custom_model": ""}


def _resolve(kind):
    sel = get(f"{kind}_backend", DEFAULTS[kind])
    presets = LLM_PRESETS if kind == "llm" else VLM_PRESETS
    for p in presets:
        if p["id"] == sel:
            return p["base"], p["model"]
    base = get(f"{kind}_custom_base", "")
    model = get(f"{kind}_custom_model", "")
    if base:
        return base.rstrip("/"), model or "default"
    d = presets[0]
    return d["base"], d["model"]


# v0.6.1: embedding 後端 (RAG 檢索用) — local :8082 或雲端 (建議 Jina)
EMBED_PRESETS = [
    {"id": "local8082", "name": "本機 :8082 jina-embeddings-v5-small（預設，免金鑰）",
     "base": "http://127.0.0.1:8082", "model": "jina-embeedings-v5-small-retrieval-Q8_0", "key": ""},
    {"id": "jina_cloud", "name": "Jina AI 雲端 API（建議模型 jina-embeddings-v5-small-retrieval，需金鑰）",
     "base": "https://api.jina.ai/v1", "model": "jina-embeddings-v5-small-retrieval", "key": ""},
]


def get_embed():
    """回 (base, model, api_key) — embedding 端點"""
    sel = get("embed_backend", "local8082")
    for p in EMBED_PRESETS:
        if p["id"] == sel:
            key = p["key"] or (get("jina_api_key", "") if sel == "jina_cloud" else "")
            return p["base"], p["model"], key
    base = get("embed_custom_base", "")
    if base:
        return base.rstrip("/"), get("embed_custom_model", "default"), get("embed_api_key", "")
    d = EMBED_PRESETS[0]
    return d["base"], d["model"], ""


def get_llm():
    return _resolve("llm")


def get_vlm():
    return _resolve("vlm")


def probe(base):
    try:
        urllib.request.urlopen(f"{base}/health", timeout=4)
        return "ok"
    except Exception:
        try:
            urllib.request.urlopen(f"{base}/v1/models", timeout=4)
            return "ok (no /health)"
        except Exception as e:
            return f"unreachable ({type(e).__name__})"
