"""v0.5.1 — 選方後 RAG × LLM 加減項分析 (8085)

輸入: 選定方劑 (name/composition/syndrome) + 七典 RAG 檢索段落 + 症狀摘要
LLM 做:
  1. 相關性分析 — RAG 段落裡提到此方/同源方的條文, 與傷寒論原方比較
  2. 加減項建議 — 依病人症狀 + 典籍出處, 給 加/減/替換 建議 (附典籍出處)
輸出 JSON 寬容解析, 失敗回 None (面板顯示不可用)。
"""
import json
import re
import urllib.request
from llm_config import get_llm

TIMEOUT_S = 60


def analyze_prescription(prescription: dict, rag_hits: list, symptoms_summary: str) -> dict | None:
    """回 {"relevance": str, "suggestions": [{"type","item","reason","source"}], "llm_used": True}

    失敗回 None。
    """
    name = prescription.get("name", "")
    comp = prescription.get("composition", "")
    if not name:
        return None

    hits_text = ""
    for i, h in enumerate(rag_hits or [], 1):
        hits_text += f"\n【段落{i}】{h['book']}·{h['chapter']}：\n{h['text'][:500]}\n"
    if not hits_text.strip():
        return None

    prompt = f"""你是中醫方劑分析助手。醫師選定方劑：{name}
組成：{comp}
病人症狀摘要：{symptoms_summary or "（未提供）"}

從七部典籍（金匱要略/溫病條辨/備急千金要方/景岳全書/萬病回春/醫宗金鑑/醫林改錯）RAG 檢索到的相關段落：
{hits_text}

請分析：
1. relevance：這些段落與「{name}」（傷寒論方）的相關性——哪些段落講到同源方、化裁方、或同證異治？跟傷寒論原方有何異同？（150 字內）
2. suggestions：依病人症狀 + 段落出處，給 0-4 條加減項建議。type 只能是「加」「減」「替換」。每條附典籍出處（書名·篇章）。

只輸出 JSON（不要其他文字）：
{{"relevance": "...", "suggestions": [{{"type": "加", "item": "厚朴、杏子", "reason": "喘者加...", "source": "金匱要略·..."}}, ...]}}
"""
    payload = {
        "model": get_llm()[1],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 900,
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
    except Exception:
        return None

    m = re.search(r'\{.*\}', content, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except Exception:
        return None

    sugg = []
    for s in parsed.get("suggestions", [])[:4]:
        if isinstance(s, dict) and s.get("item"):
            sugg.append({
                "type": str(s.get("type", "加")),
                "item": str(s["item"]),
                "reason": str(s.get("reason", ""))[:150],
                "source": str(s.get("source", "")),
            })
    return {"relevance": str(parsed.get("relevance", ""))[:500],
            "suggestions": sugg, "llm_used": True}
