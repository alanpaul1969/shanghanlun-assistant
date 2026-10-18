"""v0.5 — 主訴 LLM 症狀抽取 (8085 thinking-off proxy)

主訴文字 → 症狀矩陣 id 封閉集分類 → 併入推論。
解決「分析結果跟主訴無關」：chief_complaint 此前只存不用。

- 候選 id = 症狀矩陣全部 sid (約 50 個, 封閉集分類對 27B 很穩)
- 失敗/timeout 安全降級: 回空 list (推論退回勾選症狀)
- session 端快取: 同一主訴只抽一次 (app.py 管)
"""
import json
import re
import urllib.request

from inference_engine import load_symptom_matrix

LLM_BASE = "http://127.0.0.1:8085"
LLM_MODEL = "qwen3.8-27b-nvfp4"
TIMEOUT_S = 25

_cache = None


def _all_sids():
    """category → [sid]; 全矩陣封閉集"""
    global _cache
    if _cache is None:
        m = load_symptom_matrix()
        _cache = {cat: list(sids.keys()) for cat, sids in m.items() if not cat.startswith("_")}
    return _cache


def extract_chief_complaint(chief: str) -> dict:
    """回 {"symptoms": {cat: [sid,...]}, "llm_used": bool, "note": str}

    失敗回 {"symptoms": {}, "llm_used": False, ...}
    """
    chief = (chief or "").strip()
    if not chief:
        return {"symptoms": {}, "llm_used": False, "note": "無主訴"}

    cats = _all_sids()
    id_lines = "\n".join(f"{cat}: {'、'.join(sids)}" for cat, sids in cats.items())

    prompt = f"""你是中醫辨證助手。病人主訴：「{chief}」

症狀代碼清單（只能從這些裡選）：
{id_lines}

任務：從主訴抽出符合的症狀代碼。規則：
- 只選主訴文字明確支持或強烈暗示的
- 「頭痛 3 天 + 發燒」→ 頭痛類 + 發熱類
- 沒提到的不選, 寧缺勿濫
- 全部不符合就輸出空陣列

只輸出 JSON（不要其他文字）：
{{"symptoms": ["<代碼>", ...]}}
"""
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{LLM_BASE}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            resp = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"symptoms": {}, "llm_used": False,
                "note": f"LLM 無回應 ({type(e).__name__})"}

    m = re.search(r'\{.*\}', content, re.DOTALL)
    if not m:
        return {"symptoms": {}, "llm_used": False, "note": "LLM 輸出非 JSON"}
    try:
        picked = json.loads(m.group(0)).get("symptoms", [])
    except Exception:
        return {"symptoms": {}, "llm_used": False, "note": "JSON 解析失敗"}

    # 白名單過濾 + 分類
    out = {}
    for sid in picked:
        for cat, sids in cats.items():
            if sid in sids:
                out.setdefault(cat, [])
                if sid not in out[cat]:
                    out[cat].append(sid)
    return {"symptoms": out, "llm_used": True,
            "note": f"從主訴抽出 {sum(len(v) for v in out.values())} 個症狀"}
