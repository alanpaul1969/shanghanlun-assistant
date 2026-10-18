"""v0.2.4 Phase 3 — LLM rerank (本地 8080 Qwen3.8-27B)

推論 top 3 候選方證丟本地 llama.cpp (127.0.0.1:8080) 重排。
- 用 generate endpoint (非 chat), OpenAI-compat /v1/chat/completions
- LLM 評分: 給症狀 + 3 候選方證, 請輸出 JSON {best: "桂枝湯", reason: "..."}
- 解析失敗 fallback 原規則排序 (safe degrade)
- timeout 30s, 失敗靜默 (不 block 推論)

注意:
- 8080 是 llama.cpp server (Qwen3.8-27B NVFP4, n_ctx 256K)
- grammar-400 限制: 不用 structured output (schema 會 400), 用自然語言 prompt + regex 解析
"""
import json
import re
import urllib.request
from pathlib import Path

from llm_config import get_llm
TIMEOUT_S = 45


def rerank_by_llm(symptoms_summary: str, prescriptions: list, meridian_top: str, chief_complaint: str = "") -> dict:
    """用本地 LLM 重排 top 3 候選方證

    Args:
        symptoms_summary: 症狀摘要 (人話, e.g. "頭痛發熱汗出惡風脈浮緩")
        prescriptions: 規則引擎的候選 list [{name, syndrome, match, ...}]
        meridian_top: 主經名 (e.g. "太陽")

    Returns:
        {"reranked": [改名排序後 prescriptions], "llm_used": True/False,
         "llm_reason": "...", "llm_best": "..."}
        失敗時回 {"reranked": prescriptions 原樣, "llm_used": False, "llm_reason": "..."}
    """
    if not prescriptions or len(prescriptions) < 2:
        return {"reranked": prescriptions, "llm_used": False, "llm_reason": "too few candidates"}

    top3 = prescriptions[:3]
    cand_lines = "\n".join([
        f"{i+1}. {p['name']} — {p['syndrome']} (規則 match {p['match']}%)"
        for i, p in enumerate(top3)
    ])

    cc = f"\n病人主訴：{chief_complaint}" if chief_complaint else ""
    prompt = f"""你是中醫傷寒論辨證助手。病人症狀：{symptoms_summary}{cc}
主經：{meridian_top}

候選方證（規則引擎初步排序）：
{cand_lines}

請從上面 {len(top3)} 個候選中，選出「最適合」的一個方證（主訴與症狀都要吻合）。
只輸出 JSON（不要其他文字）：
{{"best": "<方證名>", "reason": "<50 字內理由>"}}
"""

    payload = {
        "model": get_llm()[1],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 200,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{get_llm()[0]}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            resp = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"reranked": prescriptions, "llm_used": False,
                "llm_reason": f"LLM call failed: {type(e).__name__}"}

    # 解析 JSON (從 content 抓 {...} 區塊, 寬容解析)
    m = re.search(r'\{[^}]+\}', content, re.DOTALL)
    if not m:
        return {"reranked": prescriptions, "llm_used": False,
                "llm_reason": f"LLM output not JSON: {content[:80]}"}
    try:
        parsed = json.loads(m.group(0))
        llm_best = parsed.get("best", "").strip()
        llm_reason = parsed.get("reason", "").strip()
    except Exception:
        return {"reranked": prescriptions, "llm_used": False,
                "llm_reason": f"JSON parse failed: {m.group(0)[:80]}"}

    # 找 llm_best 在 candidates 的位置
    best_idx = None
    for i, p in enumerate(top3):
        if p["name"] == llm_best or llm_best in p["name"] or p["name"] in llm_best:
            best_idx = i
            break

    if best_idx is None:
        return {"reranked": prescriptions, "llm_used": True,
                "llm_best": llm_best, "llm_reason": llm_reason,
                "llm_note": f"LLM 選了「{llm_best}」但不在候選 top3, 保留規則排序"}

    # 重排: best 移到 #1, 其他照原順序
    if best_idx > 0:
        best_p = top3.pop(best_idx)
        top3.insert(0, best_p)
        for i, p in enumerate(top3):
            p["rank"] = i + 1
            # LLM top1 升級 confidence
            if i == 0:
                p["confidence"] = "High (LLM+規則一致)" if best_idx == 0 else "High (LLM rerank)"

    return {
        "reranked": top3 + prescriptions[3:],
        "llm_used": True,
        "llm_best": llm_best,
        "llm_reason": llm_reason,
    }


def build_symptoms_summary(symptom_ids_by_category):
    """把症狀 dict 轉成人話摘要給 LLM"""
    parts = []
    for category, sids in (symptom_ids_by_category or {}).items():
        if sids:
            parts.append(f"{category}: {'、'.join(sids)}")
    return "; ".join(parts)
