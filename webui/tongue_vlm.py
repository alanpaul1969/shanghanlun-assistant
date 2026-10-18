"""v0.4 舌診照片 VLM — 8080 Qwen3.8-27B 單發呼叫 (vision)

- S2-3 望診頁上傳舌頭照片 → base64 → 8080 /v1/chat/completions (image_url data URI)
- LLM 分析舌象: 舌質顏色/舌體形態/舌苔/津液 → JSON
- timeout 180s (其他 agent 共用 8080, 排隊可能慢)
- 失敗 safe fallback (回 error 不 block 望診表單)

注意:
- 8080 是 llama.cpp server, vision 經 media_marker 或 OpenAI image_url 格式均可
- 單發呼叫 (符合 protocols/minicpm-v-not-an-agent-model 的「單發請求 OK」原則)
"""
import json
import base64
import urllib.request

LLM_BASE = "http://127.0.0.1:8085"
TIMEOUT_S = 300  # 加大: 其他 agent 共用 8080, 排隊可能慢

PROMPT = """你是中醫舌診專家。請分析這張舌頭照片，依中醫舌診標準輸出：
1. 舌質顏色（淡紅/紅/暗紅/淡白/絳）
2. 舌體形態（正常/胖大/瘦薄/齒痕/裂紋）
3. 舌苔顏色與厚薄（白薄/白厚/黃薄/黃厚/灰黑/少苔/無苔/膩苔）
4. 津液（潤/乾/膩）

只輸出 JSON（不要其他文字）：
{"tongue_body": "<舌質>", "tongue_coat": "<舌苔>", "body_form": "<形態或 normal>", "moisture": "<津液>", "summary": "<30字內總結>"}"""


def analyze_tongue_photo(image_path: str) -> dict:
    """上傳舌診照片給 8080 vision, 回傳分析結果

    Returns:
        {"ok": True, "tongue_body": ..., "tongue_coat": ..., "summary": ...}
        {"ok": False, "error": "..."}
    """
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"ok": False, "error": f"read file failed: {e}"}

    # 猜 mime
    lower = image_path.lower()
    mime = "image/jpeg"
    if lower.endswith(".png"):
        mime = "image/png"
    elif lower.endswith(".webp"):
        mime = "image/webp"

    payload = {
        "model": "qwen3.8-27b-nvfp4",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": PROMPT},
            ],
        }],
        "temperature": 0.3,
        "max_tokens": 4096,
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
        return {"ok": False, "error": f"LLM call failed: {type(e).__name__}: {e}"}

    # 寬容 JSON 解析 (reasoning 模型: content 可能空, fallback 掃 reasoning_content)
    import re
    search_in = content
    if not search_in.strip():
        search_in = str(resp["choices"][0]["message"].get("reasoning_content", ""))
    m = re.search(r'\{[^{}]*"tongue_body"[^}]*\}', search_in, re.DOTALL)
    if not m:
        m = re.search(r'\{[^}]+\}', search_in, re.DOTALL)
    if not m:
        return {"ok": False, "error": f"not JSON: content={content[:80]} reasoning={search_in[-120:]}"}
    content = m.group(0)  # 後續 parse 用找到的 JSON 段
    try:
        parsed = json.loads(m.group(0))
    except Exception:
        return {"ok": False, "error": f"JSON parse failed: {m.group(0)[:100]}"}

    return {
        "ok": True,
        "tongue_body": parsed.get("tongue_body", ""),
        "tongue_coat": parsed.get("tongue_coat", ""),
        "body_form": parsed.get("body_form", ""),
        "moisture": parsed.get("moisture", ""),
        "summary": parsed.get("summary", ""),
        "raw": content,
    }
