"""v0.4.5 — LLM 依主訴動態出追問題 (8085 thinking-off proxy)

輸入: 主訴文字 + 該經靜態題庫 QUICK_FOLLOWUP + 候選方證 (matched/missing features)
LLM 做兩件事:
  1. reorder: 從靜態題庫挑與主訴相關的題並排序 (id list)
  2. extra: 生成 0-3 題主訴特異的加減項追問 (含 options + 每選項可映射的症狀 id)

輸出 JSON 寬容解析, 任何失敗 fallback 靜態題庫原順序 (safe degrade, 同 llm_rerank 模式)。
"""
import json
import re
import urllib.request
from llm_config import get_llm

TIMEOUT_S = 30


def _call_llm(prompt: str, max_tokens: int = 900) -> str | None:
    payload = {
        "model": get_llm()[1],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{get_llm()[0]}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + get_llm()[2]} if get_llm()[2] else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def build_followup_questions(chief_complaint: str, questions: list,
                             prescriptions: list, meridian_top: str) -> dict:
    """回 {"questions": [題目 list], "llm_used": bool, "llm_note": str, "extra_count": int}

    questions 元素形狀與 QUICK_FOLLOWUP 相同: {id, question, options}
    (extra 題 id 一律 "x-" 前綴, route POST 會接受並嘗試映射)
    """
    if not chief_complaint.strip():
        return {"questions": questions, "llm_used": False,
                "llm_note": "無主訴文字, 用靜態題庫", "extra_count": 0}

    q_lines = "\n".join(
        f'  {{"id": "{q["id"]}", "question": "{q["question"][:60]}"}}'
        for q in questions
    )
    p_lines = "\n".join(
        f"- {p['name']}：符合={p.get('matched_features', [])[:4]}，缺少={p.get('missing_features', [])[:4]}"
        for p in prescriptions[:3]
    ) or "  (尚無候選方證)"

    prompt = f"""你是傷寒論辨證助手。病人主訴：「{chief_complaint}」
初步辨證：{meridian_top} 證。

候選方證差異點：
{p_lines}

題庫中可用的追問題：
[
{q_lines}
]

請做兩件事：
1. 從題庫挑出與主訴最相關的題（依鑑別價值排序，最多全部），輸出 id 順序。
2. 依主訴與候選方證的「加減項差異」生成最多 3 題新追問（題庫沒問到的關鍵細節，例如《18條》喘者加厚朴杏子）。每題給 options（3-4 個，最後一個是「不確定」），並對能對應症狀的選項給 "map"（症狀 id 只能用這些：汗出/無汗/微汗/大汗不止/手足濈然汗出/項背強/頭暈/口渴_微渴/口渴_大渴欲冷飲/消渴_嚴重口渴/不渴/食不下_默默不欲食/便秘/腹瀉_自利/腹瀉_下利清穀/胸脇苦滿/腹滿時痛/心下痞/氣上撞心/口苦/煩躁_易怒/但欲寐_嗜睡/四肢厥冷/往來寒熱/心煩喜嘔/乾嘔/脈浮緩/脈浮緊/脈洪大/脈沉細/脈弦）。無法對應就省略 map。

只輸出 JSON（不要其他文字）：
{{"order": ["<題庫id>", ...], "extra": [{{"question": "...", "options": ["..."], "map": {{"<option>": ["<症狀id>"]}}}}]}}
"""

    content = _call_llm(prompt)
    if not content:
        return {"questions": questions, "llm_used": False,
                "llm_note": "LLM 無回應, 用靜態題庫", "extra_count": 0}

    m = re.search(r'\{.*\}', content, re.DOTALL)
    if not m:
        return {"questions": questions, "llm_used": False,
                "llm_note": "LLM 輸出非 JSON, 用靜態題庫", "extra_count": 0}
    try:
        parsed = json.loads(m.group(0))
    except Exception:
        return {"questions": questions, "llm_used": False,
                "llm_note": "JSON 解析失敗, 用靜態題庫", "extra_count": 0}

    # 1. reorder 靜態題
    by_id = {q["id"]: q for q in questions}
    ordered = [by_id[i] for i in parsed.get("order", []) if i in by_id]
    skipped = [q for q in questions if q["id"] not in {x["id"] for x in ordered}]
    # 被略過的題放最後 (不刪, 醫師仍可答)
    questions_out = ordered + skipped

    # 2. extra 題 (x- 前綴)
    extra_out = []
    for i, ex in enumerate(parsed.get("extra", [])[:3]):
        q_text = str(ex.get("question", "")).strip()
        opts = [str(o).strip() for o in ex.get("options", []) if str(o).strip()]
        if not q_text or len(opts) < 2:
            continue
        qid = f"x-{i+1}"
        extra_out.append({"id": qid, "question": q_text, "options": opts,
                          "map": ex.get("map", {}) or {}})

    note = f"LLM 已依主訴排序{'，並生成 %d 題加減項追問' % len(extra_out) if extra_out else ''}" if (ordered or extra_out) else "LLM 無有效建議, 用靜態題庫"
    return {"questions": questions_out, "extra": extra_out,
            "llm_used": bool(ordered or extra_out), "llm_note": note,
            "extra_count": len(extra_out)}
