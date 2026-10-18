"""v0.2 規則引擎 (本地 Python, 不接 LLM/Jev)
- 症狀-經權重表從 symptom_to_meridian.json
- 候選方證表從 formula_to_meridian.json (Phase 3)

輸入: {category: [symptom_id, ...]} 症狀 dict
輸出: {
  "meridian_inference": [{"name": "太陽", "pct": 87}, ...],
  "key_features": [...], "missing_features": [...],
  "prescriptions": [top-3 ranked],
  "confidence": "High" | "Medium" | "Low"
}

規則:
1. 互斥組 (mutex_group): 同 group 只取「該 user 勾選的同組症狀中權重最高者」進入計算
2. score = Σ (symptom.weight × symptom.meridian_score) / Σ symptom.weight × 100
3. 6 經分數 normalize 成 0-100% (最高分 = 100%, 其他按比例)
4. Confidence = top1-top2 gap 決定 (≥30 = High, ≥15 = Medium, <15 = Low)
5. 候選方證: top1 經 + 該經常見主方 (formula_to_meridian) + match% 用 症狀對方證症狀清單重疊率
"""
import json
from pathlib import Path

# 載入資料
DATA_DIR = Path(__file__).parent
_SYMPTOM_DATA = json.loads((DATA_DIR / "symptom_to_meridian.json").read_text())


def load_symptom_matrix():
    """v0.4.5: 回 category → {sid: weights} 原始矩陣 (sid→category 回查用)"""
    return _SYMPTOM_DATA["symptoms"]
_FORMULA_DATA = json.loads((DATA_DIR / "formula_to_meridian.json").read_text())
SYMPTOMS = _SYMPTOM_DATA["symptoms"]
FORMULAS = _FORMULA_DATA["formulas"]
# v0.3 observations (望聞切) → 經權重表
_OBS_DATA = json.loads((DATA_DIR / "observations_to_meridian.json").read_text())
OBSERVATIONS = _OBS_DATA["fields"]

MERIDIANS = ["太陽", "陽明", "少陽", "太陰", "少陰", "厥陰"]

# S2-7 differential 答案 → symptom 對映
# differential question value (例: "心煩喜嘔") → (category, symptom_id)
# 對映回現有症狀表, differential 答案 = 加分症狀
_DIFF_ANSWER_TO_SYMPTOM = {
    # 陽明
    "正常": ("二便", "便秘"),  # 大便正常 → 反義 (隱含不通, 不加)
    "硬 / 便秘": ("二便", "便秘"),
    "自利清水": ("二便", "腹瀉_自利"),
    "未解": ("二便", "便秘"),
    "持續高燒": ("寒熱", "發熱_高燒_不惡寒"),
    "潮熱（日晡加劇）": ("寒熱", "發熱_高燒_不惡寒"),
    "往來寒熱": ("寒熱", "往來寒熱"),
    "微熱": ("寒熱", "發熱_微熱_惡風"),
    "微渴": ("飲食", "口渴_微渴"),
    "大渴欲冷飲": ("飲食", "口渴_大渴欲冷飲"),
    "渴不欲飲": ("飲食", "消渴_嚴重口渴"),
    "無汗": ("汗出", "無汗"),
    "微汗": ("汗出", "微汗"),
    "大汗不止": ("汗出", "大汗不止"),
    "手足濈然汗出": ("汗出", "手足濈然汗出"),
    "清醒": None,  # 反義
    "煩躁": ("精神情緒", "煩躁_易怒"),
    "譫語": ("精神情緒", "譫語_神智不清"),
    "嗜睡": ("精神情緒", "但欲寐_嗜睡"),
    # 少陽
    "明顯往來": ("寒熱", "往來寒熱"),
    "微有寒熱": ("寒熱", "往來寒熱"),
    "胸脇苦滿": ("胸腹", "胸脇苦滿"),
    "僅脇下脹": ("胸腹", "胸脇苦滿"),
    "胸悶但不痛": ("胸腹", "胸脇苦滿"),
    "微苦": ("精神情緒", "口苦"),
    "心煩喜嘔": ("噁心嘔吐", "心煩喜嘔"),
    "微嘔": ("噁心嘔吐", "乾嘔"),
    "不嘔": None,
    "默默不欲食": ("飲食", "食不下_默默不欲食"),
    "食少": ("飲食", "食不下_默默不欲食"),
    "正常": None,
    # 太陰
    "自利不渴": ("二便", "腹瀉_自利"),
    "腹瀉 + 口渴": ("二便", "腹瀉_自利"),
    "腹瀉 + 發熱": ("二便", "腹瀉_自利"),
    "腹滿時痛": ("胸腹", "腹滿時痛"),
    "腹脹不痛": ("胸腹", "腹脹_不痛"),
    "繞臍痛": ("胸腹", "腹滿時痛"),
    "食不下": ("飲食", "食不下_默默不欲食"),
    "能食但脹": ("飲食", "食不下_默默不欲食"),
    "白膩": None,  # 舌苔 - 尚未收錄
    "白潤": None,
    "黃膩": None,
    "少苔": None,
    "四肢溫": None,
    "手足溫": None,
    "手足冷": ("寒熱", "四肢厥冷"),
    # 少陰
    "但欲寐（嗜睡）": ("精神情緒", "但欲寐_嗜睡"),
    "精神萎靡": ("精神情緒", "精神萎靡"),
    "煩躁": ("精神情緒", "煩躁_易怒"),  # 少陰熱化
    "正常": None,
    "脈微細": ("脈", "脈沉細"),
    "沉細": ("脈", "脈沉細"),
    "沉緊": ("脈", "脈沉細"),
    "浮數": ("脈", "脈浮緊"),
    "清長": ("二便", "小便清長"),
    "短赤": ("二便", "小便短赤"),
    "不利": ("二便", "小便短赤"),
    "手足冷（厥冷）": ("寒熱", "四肢厥冷"),
    "四肢冷": ("寒熱", "四肢厥冷"),
    "下利清穀": ("二便", "腹瀉_下利清穀"),
    "自利而渴": ("二便", "腹瀉_自利"),
    "下利膿血": ("二便", "腹瀉_自利"),  # 簡化
    # 厥陰
    "寒熱錯雜（上熱下寒）": ("寒熱", "寒熱錯雜_上熱下寒"),
    "純寒": ("寒熱", "四肢厥冷"),
    "純熱": ("寒熱", "發熱_高燒_不惡寒"),
    "明顯消渴": ("飲食", "消渴_嚴重口渴"),
    "微渴": ("飲食", "口渴_微渴"),
    "不渴": ("飲食", "不渴"),
    "明顯": ("胸腹", "氣上撞心"),
    "微有": ("胸腹", "氣上撞心"),
    "無": None,
    "明顯": ("飲食", "飢不欲食"),
    "微": ("飲食", "飢不欲食"),
    "無": None,
    "久利不止": ("二便", "腹瀉_下利清穀"),
    "便膿血": ("二便", "腹瀉_自利"),
    "熱利": ("二便", "腹瀉_自利"),
    "無": None,
    "手足厥寒": ("寒熱", "四肢厥冷"),
    "脈細欲絕": ("脈", "脈沉細"),
    # 太陽
    "浮緩": ("脈", "脈浮緩"),
    "浮緊": ("脈", "脈浮緊"),
    "沉細": ("脈", "脈沉細"),
    "其他": None,
    "前額": ("頭身", "頭痛_前額"),
    "整頭": ("頭身", "頭痛_整頭"),
    "後頭（項強）": ("頭身", "頭痛_後頭_項強"),
    "單側": ("頭身", "頭痛_前額"),
}


def _resolve_mutex(symptom_ids_by_category):
    """對每個 mutex_group, 只保留同 group 中 weight 最高的那個症狀。
    返回: list of (category, symptom_id, weight) 經 dedup 過的症狀清單。"""
    out = []
    for category, ids in symptom_ids_by_category.items():
        for sid in ids:
            if category not in SYMPTOMS or sid not in SYMPTOMS[category]:
                continue
            out.append((category, sid, SYMPTOMS[category][sid]))
    # 對每個 (category, mutex_group) 只留 weight 最高
    # out 現在是 [(category, sid, info_dict), ...], info['weight'] 是權重
    by_mutex = {}
    for category, sid, info in out:
        w = info.get("weight", 1.0)
        mg = info.get("mutex_group")
        if not mg:
            # 非互斥, 直接留
            by_mutex[(category, sid, None)] = (category, sid, info)
            continue
        key = (category, mg)
        existing = by_mutex.get(key)
        if not existing or w > existing[2].get("weight", 1.0):
            by_mutex[key] = (category, sid, info)
    # 收集 — 直接回傳 (category, sid, info) tuple
    final = []
    seen = set()
    for v in by_mutex.values():
        key = (v[0], v[1])
        if key in seen:
            continue
        seen.add(key)
        final.append((v[0], v[1], v[2]))
    return final


def infer(symptom_ids_by_category, observations=None):
    """主推論入口。回傳 6 經分數 + 候選方證 + 信心。
    v0.3: observations (望聞切) 疊加分數 (次要證據 0.5x)。
    """
    selected = _resolve_mutex(symptom_ids_by_category)

    # v0.3: 無問診症狀但有 observations → 仍跑 observations 推論
    if not selected and not observations:
        return _empty_result()

    # 6 經 score 累加
    raw_scores = {m: 0.0 for m in MERIDIANS}
    total_weight = 0.0
    matched_features = []
    missing_required = []

    for category, sid, info in selected:
        # info = SYMPTOMS[category][sid] = {'太陽': 0.7, ..., 'weight': 1.0, 'mutex_group': '...'}
        w = info.get("weight", 1.0)
        for m in MERIDIANS:
            raw_scores[m] += info[m] * w
        total_weight += w
        matched_features.append({"category": category, "symptom": sid, "weight": w})

    # v0.3: 望聞切 observations 疊加 (次要證據)
    obs_matched = _apply_observations(raw_scores, observations or {})

    # Normalize: max score = 100%
    max_score = max(raw_scores.values()) if any(raw_scores.values()) else 0
    if max_score > 0:
        meridian_inference = []
        for m in MERIDIANS:
            pct = int(round((raw_scores[m] / max_score) * 100))
            meridian_inference.append({
                "name": m,
                "meridian": {
                    "太陽": "taiyang", "陽明": "yangming", "少陽": "shaoyang",
                    "太陰": "taiyin", "少陰": "shaoyin", "厥陰": "jueyin"
                }[m],
                "color": {
                    "太陽": "#EA580C", "陽明": "#DC2626", "少陽": "#CA8A04",
                    "太陰": "#65A30D", "少陰": "#1D4ED8", "厥陰": "#7C3AED"
                }[m],
                "pct": pct,
                "raw_score": round(raw_scores[m], 2),
            })
    else:
        return _empty_result()

    # 排序: pct 高到低
    meridian_inference.sort(key=lambda x: x["pct"], reverse=True)

    # Confidence: top1 - top2
    if len(meridian_inference) >= 2:
        gap = meridian_inference[0]["pct"] - meridian_inference[1]["pct"]
    else:
        gap = 100
    confidence = "High" if gap >= 30 else ("Medium" if gap >= 15 else "Low")

    # 候選方證: top 經的主方 + match% 計算
    top_meridian = meridian_inference[0]["name"]
    prescriptions = _rank_prescriptions(top_meridian, selected, meridian_inference)

    # 缺失特徵（top1 經特有的但 user 沒勾的）
    missing = _missing_features(top_meridian, selected)

    return {
        "meridian_inference": meridian_inference,
        "key_features": matched_features[:8],
        "missing_features": missing,
        "prescriptions": prescriptions,
        "confidence": confidence,
        "selected_count": len(selected),
        "observations_matched": obs_matched,
    }


def _empty_result():
    return {
        "meridian_inference": [{
            "name": m, "meridian": ["taiyang","yangming","shaoyang","taiyin","shaoyin","jueyin"][i],
            "color": ["#EA580C","#DC2626","#CA8A04","#65A30D","#1D4ED8","#7C3AED"][i],
            "pct": 0, "raw_score": 0
        } for i, m in enumerate(MERIDIANS)],
        "key_features": [],
        "missing_features": [],
        "prescriptions": [],
        "confidence": "Low",
        "selected_count": 0,
    }


def _rank_prescriptions(top_meridian, selected, meridian_inference):
    """給 top 經的候選方證排名。
    match% = 該方證「症狀 profile」與 user 勾選症狀重疊率。"""
    cands = FORMULAS.get(top_meridian, [])
    meridian_pct = meridian_inference[0]["pct"]

    ranked = []
    for f in cands:
        # 重疊計算: user 勾選的 category 集合 ∩ f['typical_symptoms'] category 集合
        user_cats = {s[0] for s in selected}
        f_cats = set(f.get("typical_categories", []))
        overlap = len(user_cats & f_cats) / max(len(f_cats), 1) if f_cats else 0
        # 加權: meridian 分數 (0-1) * 0.5 + category overlap * 0.5
        meridian_factor = meridian_pct / 100
        match = int(round((meridian_factor * 0.5 + overlap * 0.5) * 100))
        match = min(match, meridian_pct)  # 不能超過主經分數

        ranked.append({
            "rank": len(ranked) + 1,
            "name": f["name"],
            "syndrome": f["syndrome"],
            "match": match,
            "confidence": "High" if match >= 75 else ("Medium" if match >= 50 else "Low"),
            "matched_features": f.get("typical_categories", []),
            "missing_features": list(f_cats - user_cats),
            "composition": f.get("composition", []),
            "algorithm_lens": f.get("algorithm_lens", []),
            "rationale": f.get("rationale", ""),
            "contraindications": f.get("contraindications", []),
            "source_text": f.get("source_text", ""),
            "source_ref": f.get("source_ref", ""),
        })

    # 排序: match 降冪
    ranked.sort(key=lambda x: x["match"], reverse=True)
    # 重新 rank
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ranked[:5]  # top 5


def _missing_features(top_meridian, selected):
    """top1 經特有症狀（權重高）但 user 沒勾的。"""
    required_high_weight = []
    user_cats = {s[0] for s in selected}
    for category in SYMPTOMS:
        for sid, info in SYMPTOMS[category].items():
            if info.get(top_meridian, 0) >= 0.7:  # 該經特異性
                if category not in user_cats:
                    required_high_weight.append({"category": category, "symptom": sid})
    return required_high_weight[:5]


def meridian_inference_to_dict(result):
    """把 result 序列化成 JSON-friendly dict (方便 template 渲染)"""
    return result


def _apply_observations(raw_scores, observations):
    """v0.3: 望聞切 17 欄 → 經分數修正。
    observations 值 → OBSERVATIONS[field][value] → 6 經分 × weight × 0.5 (次要證據)
    疊加進 raw_scores (in-place)。
    pulse_count 數字另行換算 (<60 遲 → 少陰, >100 數 → 陽明)。
    回傳: matched observation list (給 template 顯示)
    """
    matched = []
    if not observations:
        return matched
    for field, value in observations.items():
        if not value:
            continue
        # pulse_count 特例
        if field == "pulse_count":
            try:
                n = int(value)
                if n < 60:
                    raw_scores["太陰"] += 0.2
                    raw_scores["少陰"] += 0.4
                    matched.append({"field": "pulse_count", "value": f"{n} (遲)", "weight": 0.4})
                elif n > 100:
                    raw_scores["陽明"] += 0.4
                    matched.append({"field": "pulse_count", "value": f"{n} (數)", "weight": 0.4})
            except (ValueError, TypeError):
                pass
            continue
        # v0.3.x 複合脈: 拆字疊加 (e.g. 浮緊 = 浮 + 緊 兩脈各計一次)
        if field == "pulse_combo" and len(value) >= 2:
            combo_scores = {"太陽": 0, "陽明": 0, "少陽": 0, "太陰": 0, "少陰": 0, "厥陰": 0}
            n_chars = 0
            for ch in value:
                single = OBSERVATIONS.get("pulse", {}).get(ch)
                if single:
                    w = single.get("weight", 0)
                    for m in MERIDIANS:
                        combo_scores[m] += single.get(m, 0) * w
                    n_chars += 1
            if n_chars:
                for m in MERIDIANS:
                    raw_scores[m] += combo_scores[m] * 0.6  # 複合脈臨床權重略高於單脈 (0.5)
                matched.append({"field": "pulse_combo", "value": value, "weight": 0.6})
            continue

        field_data = OBSERVATIONS.get(field, {})
        value_data = field_data.get(value)
        if not value_data:
            continue
        w = value_data.get("weight", 0)
        if w <= 0:
            continue
        for m in MERIDIANS:
            raw_scores[m] += value_data.get(m, 0) * w * 0.5  # 次要證據 0.5x
        matched.append({"field": field, "value": value, "weight": w})
    return matched


def _apply_patient_modifiers(prescriptions, patient):
    """根據病人基本資料 (年齡、性別、體型、孕否) 修飾 confidence
    規則:
    - 孕婦 (pregnancy='yes'): 禁用峻下/有毒方, confidence -1
    - 幼兒 (age < 6): 禁用大劑量方, confidence -1
    - 老年 (age > 70): 慎用大熱大寒方, confidence -1
    - 體型虛: 慎用汗下, 偏補
    - 體型實: 偏瀉
    回傳: 修飾後的 prescriptions list (每個加上 patient_modifier note)
    """
    if not patient or not prescriptions:
        return prescriptions
    mods = []
    age = patient.get("age", 0)
    if patient.get("pregnancy") == "yes":
        mods.append("⚠ 孕婦 — 禁用峻下 (承氣、十棗)、慎用破血 (抵當)")
    if 0 < age < 6:
        mods.append(f"⚠ 幼兒 ({age}y) — 劑量按體重折半")
    if age >= 70:
        mods.append(f"⚠ 老年 ({age}y) — 慎用大熱大寒 (四逆 / 白虎 大劑)")
    body = patient.get("body_type", "")
    if "虛" in body or "瘦" in body:
        mods.append("⚠ 體虛 — 慎用汗下峻攻, 偏好補益 (理中、黃連阿膠)")
    if "實" in body or "胖" in body:
        mods.append("⚠ 體實 — 偏好瀉法 (承氣、大柴胡), 慎峻補")

    if not mods:
        return prescriptions

    # 把 mods 加到每個候選方證的 notes
    for p in prescriptions:
        if "patient_modifiers" not in p:
            p["patient_modifiers"] = []
        p["patient_modifiers"].extend(mods)
    return prescriptions


# ── 救逆標籤: previous_treatment 解析 ─────────────────
# 從 onset.previous_treatment 文字抽方名, 套用「錯誤注入/救逆」modifier
# 規則:
#   - 若文字含「服 X 湯」/「已用 X」/「服過 X」 → 該 X 方名標 rescue
#   - 若含「大汗後」「反煩不解」等症狀關鍵字 → 觸發 26 條 / 24 條 救逆
#   - 若含「已服 + 症狀加重」組合 → 整張 prescription 加 「⚠ 已服 X、勿重複」

FORMULA_NAME_PATTERNS = [
    "桂枝湯", "桂枝加葛根湯", "桂枝加厚朴杏子湯", "桂枝加附子湯",
    "桂枝加芍藥湯", "桂枝去芍藥湯", "桂枝去芍藥加附子湯",
    "麻黃湯", "五苓散", "小柴胡湯", "大柴胡湯", "柴胡桂枝湯",
    "白虎湯", "白虎加人參湯", "大承氣湯", "小承氣湯", "調胃承氣湯",
    "理中湯", "理中丸", "四逆湯", "四逆加人參湯", "當歸四逆湯",
    "真武湯", "麻黃附子細辛湯", "黃連阿膠湯",
    "烏梅丸", "白頭翁湯", "小建中湯", "炙甘草湯", "半夏瀉心湯",
    "葛根湯", "葛根芩連湯",
]


def _parse_previous_treatments(text):
    """從 onset.previous_treatment 文字抽方名 + 症狀關鍵字

    回傳: {
        "formulas": ["桂枝湯", ...],          # 用過的方
        "rescue_signs": ["反煩不解", ...],     # 觸發救逆的症狀
    }
    """
    if not text:
        return {"formulas": [], "rescue_signs": []}
    formulas = []
    for fn in FORMULA_NAME_PATTERNS:
        if fn in text:
            formulas.append(fn)
    rescue_signs = []
    for kw in ["反煩不解", "大汗出", "大汗後", "大煩渴", "脈洪大", "身重疼痛", "壞病"]:
        if kw in text:
            rescue_signs.append(kw)
    return {"formulas": formulas, "rescue_signs": rescue_signs}


def _apply_rescue_modifiers(prescriptions, parsed_treatments):
    """根據 _parse_previous_treatments() 結果, 對每個 prescription 加 rescue_from modifier

    規則:
    1. 若該方 = used_formulas[0] (user 已用過) → 標 "⚠ 已服 X、勿重複"
    2. 若 rescue_signs 有 "反煩不解" → 加 "⚠ 反煩不解 → 刺風池風府 (24 條)"
    3. 若 rescue_signs 有 "大汗後" + "大煩渴" → 加 "⚠ 大汗後大煩渴 → 轉白虎加人參 (26 條)"
    4. 若 rescue_signs 有 "壞病" → 加 "⚠ 壞病 → 隨證治之 (16 條)"
    """
    if not prescriptions:
        return prescriptions
    used = parsed_treatments.get("formulas", [])
    signs = parsed_treatments.get("rescue_signs", [])

    for p in prescriptions:
        # 1. user 已用過的方 → 標 "勿重複"
        if p["name"] in used:
            p.setdefault("rescue_from", []).append(
                f"⚠ 已服 {p['name']}、不建議重複處方 (改方或轉方)"
            )
        # 2-4. rescue_signs
        if "反煩不解" in signs:
            p.setdefault("rescue_from", []).append(
                "⚠ 反煩不解 → 刺風池風府 + 再與桂枝湯 (傷寒論 24 條)"
            )
        if ("大汗後" in signs or "大汗出" in signs) and "大煩渴" in signs:
            p.setdefault("rescue_from", []).append(
                "⚠ 大汗後大煩渴 → 轉白虎加人參湯 (傷寒論 26 條)"
            )
        if "壞病" in signs:
            p.setdefault("rescue_from", []).append(
                "⚠ 壞病 → 隨證治之 (傷寒論 16 條)"
            )

    return prescriptions


def _parse_patient_history(patient):
    """v0.2.3 Phase 5: 從 patient.history + medication + age + gender 匹配 disease_formula_interactions.json rules

    回傳: [{"rule_id": ..., "modifiers": [...], "severity": ...}, ...]
    """
    if not patient:
        return []
    from pathlib import Path
    import json

    rules_path = Path(__file__).parent / "disease_formula_interactions.json"
    try:
        data = json.loads(rules_path.read_text())
    except Exception:
        return []
    rules = data.get("rules", [])

    # 拼接 searchable text (小寫)
    history = (patient.get("history", "") or "").lower()
    medication = (patient.get("medication", "") or "").lower()
    allergy = (patient.get("allergy", "") or "").lower()
    text = " ".join([history, medication, allergy]).lower()
    age = patient.get("age", 0) or 0
    gender = (patient.get("gender", "") or "").upper()

    matched = []
    for rule in rules:
        # age range match
        age_min = rule.get("match_age_min")
        age_max = rule.get("match_age_max")
        if age_min is not None and age < age_min:
            continue
        if age_max is not None and age > age_max:
            continue
        # sex match (若 rule 有指定)
        rule_sex = rule.get("match_sex")
        if rule_sex and gender and gender != rule_sex:
            continue

        # disease match (在 history 找)
        matched_flag = False
        for d in rule.get("match_diseases", []):
            if d.lower() in history:
                matched_flag = True
                break
        if not matched_flag:
            # keyword match (history + medication + allergy)
            for kw in rule.get("match_keywords", []):
                if kw.lower() in text:
                    matched_flag = True
                    break
        if matched_flag:
            matched.append({
                "rule_id": rule.get("id"),
                "modifiers": rule.get("modifiers", []),
                "severity": rule.get("severity", "warn"),
            })
    return matched


def _apply_disease_interactions(prescriptions, patient):
    """v0.2.3 Phase 5: 對每個 prescription 加 disease interaction modifiers"""
    if not prescriptions or not patient:
        return prescriptions
    matched = _parse_patient_history(patient)
    if not matched:
        return prescriptions
    for p in prescriptions:
        for m in matched:
            p.setdefault("disease_interactions", []).extend(m["modifiers"])
    return prescriptions


def infer_with_differential(base_symptoms, diff_answers, patient=None):
    """v0.2.2 完整推論: base symptoms + differential 答案 → 6 經 + 候選方證
    differential 答案透過 _DIFF_ANSWER_TO_SYMPTOM 映射回症狀, 跟 base 合併用。
    """
    extra = {}
    for meridian, answers in (diff_answers or {}).items():
        for qid, value in answers.items():
            mapped = _DIFF_ANSWER_TO_SYMPTOM.get(value)
            if mapped:
                cat, sid = mapped
                extra.setdefault(cat, []).append(sid)

    merged = {}
    all_cats = set(list((base_symptoms or {}).keys()) + list(extra.keys()))
    for cat in all_cats:
        b = set((base_symptoms or {}).get(cat, []) or [])
        e = set(extra.get(cat, []) or [])
        merged[cat] = list(b | e)

    result = infer(merged)
    if patient:
        result["prescriptions"] = _apply_patient_modifiers(result.get("prescriptions", []), patient)
    # v0.2.3 Phase 5: 病史-方證互動 (disease_formula_interactions.json)
    if patient:
        result["prescriptions"] = _apply_disease_interactions(result.get("prescriptions", []), patient)
    # v0.2.3 Phase 4: 救逆 modifier (從 onset.previous_treatment 抽)
    onset = (patient or {}).get("onset", {}) if isinstance(patient, dict) else {}
    prev_text = onset.get("previous_treatment", "") if isinstance(onset, dict) else ""
    parsed = _parse_previous_treatments(prev_text)
    if parsed["formulas"] or parsed["rescue_signs"]:
        result["prescriptions"] = _apply_rescue_modifiers(result.get("prescriptions", []), parsed)
    result["rescue_signs"] = parsed["rescue_signs"]
    result["used_formulas"] = parsed["formulas"]
    result["differential_count"] = sum(len(v) for v in (diff_answers or {}).values())
    result["extra_symptoms_from_differential"] = {k: v for k, v in extra.items() if v}
    return result


# ── v0.4.2 快診: 八綱 → 六經直接映射 ──────────────────
# 正典: 先辨八綱再定六經 (表裡/寒熱/虛實 → 六經)
BAGANG_MAP = {
    # (病位, 寒熱, 虛實, 嚴重度) → 六經
    ("表", "熱", "實"): "太陽",
    ("表", "寒", "實"): "太陽",
    ("表", "熱", "虛"): "太陽",
    ("表", "寒", "虛"): "太陽",
    ("裡", "熱", "實"): "陽明",
    ("裡", "寒", "實"): "陽明",
    ("半表半裡", "熱", "實"): "少陽",
    ("半表半裡", "寒", "虛"): "少陽",
    ("半表半裡", "熱", "虛"): "少陽",
    ("裡", "寒", "虛", "輕"): "太陰",
    ("裡", "寒", "虛", "重"): "少陰",
    ("裡", "寒熱錯雜", "虛"): "厥陰",
    ("裡", "寒熱錯雜", "實"): "厥陰",
}

# 六經相關度 (主經 100%, 相鄰經給背景分) — 快診 bar 顯示用
MERIDIAN_RELATION = {
    "太陽": {"太陽": 100, "陽明": 25, "少陽": 20, "太陰": 5, "少陰": 5, "厥陰": 5},
    "陽明": {"陽明": 100, "太陽": 20, "少陽": 20, "太陰": 8, "少陰": 8, "厥陰": 12},
    "少陽": {"少陽": 100, "太陽": 15, "陽明": 25, "太陰": 10, "少陰": 5, "厥陰": 18},
    "太陰": {"太陰": 100, "少陰": 40, "厥陰": 20, "太陽": 5, "陽明": 5, "少陽": 8},
    "少陰": {"少陰": 100, "太陰": 40, "厥陰": 30, "太陽": 3, "陽明": 3, "少陽": 5},
    "厥陰": {"厥陰": 100, "少陰": 30, "太陰": 20, "太陽": 5, "陽明": 12, "少陽": 15},
}


def infer_from_bagang(chief_complaint, b_wei, b_hanre, b_xushi, b_severity):
    """v0.4.2 快診: 八綱 3-4 題 → 六經直接映射 + 候選方證。

    Args:
        chief_complaint: 主訴文字 (記錄用)
        b_wei: 表 / 裡 / 半表半裡
        b_hanre: 熱 / 寒 / 寒熱錯雜
        b_xushi: 實 / 虛 / 不確定
        b_severity: 輕 / 重
    Returns: 同 infer() 格式
    """
    # 嚴重度只在 裡+寒+虛 時區分太陰/少陰
    key = (b_wei, b_hanre, b_xushi, b_severity) if b_wei == "裡" and b_hanre == "寒" and b_xushi == "虛" else (b_wei, b_hanre, b_xushi)
    # 不確定虛實: 試不帶虛實的 key
    top = BAGANG_MAP.get(key)
    if not top and b_xushi == "不確定":
        for alt in ("實", "虛"):
            k2 = (b_wei, b_hanre, alt, b_severity) if (b_wei, b_hanre, alt) == ("裡", "寒", "虛") else (b_wei, b_hanre, alt)
            top = BAGANG_MAP.get(k2)
            if top:
                break
    if not top:
        # fallback: 只看病位
        for k2, v in BAGANG_MAP.items():
            if k2[0] == b_wei:
                top = v
                break
    if not top:
        return _empty_result()

    mer = MERIDIAN_RELATION[top]
    meridian_inference = []
    for m in MERIDIANS:
        code = {"太陽": "taiyang", "陽明": "yangming", "少陽": "shaoyang",
                "太陰": "taiyin", "少陰": "shaoyin", "厥陰": "jueyin"}[m]
        color = {"太陽": "#EA580C", "陽明": "#DC2626", "少陽": "#CA8A04",
                 "太陰": "#65A30D", "少陰": "#1D4ED8", "厥陰": "#7C3AED"}[m]
        meridian_inference.append({"name": m, "meridian": code, "color": color,
                                   "pct": mer.get(m, 0), "raw_score": mer.get(m, 0)})
    meridian_inference.sort(key=lambda x: x["pct"], reverse=True)

    gap = meridian_inference[0]["pct"] - meridian_inference[1]["pct"]
    confidence = "High" if gap >= 30 else ("Medium" if gap >= 15 else "Low")

    prescriptions = _rank_prescriptions(top, [], meridian_inference)
    return {
        "meridian_inference": meridian_inference,
        "key_features": [], "missing_features": [],
        "prescriptions": prescriptions,
        "confidence": confidence, "selected_count": 0,
        "observations_matched": [],
        "bagang": {"病位": b_wei, "寒熱": b_hanre, "虛實": b_xushi, "嚴重度": b_severity},
    }
