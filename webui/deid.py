"""v0.6.2 — 診次資料去識別化 (統計/研究匯出用)

剝除: sid、病人姓名、年齡(改區間)、性別保留(統計必要, 屬敏感但常用)——
嚴格場景可開 strip_gender。所有自由文字欄位 (主訴/筆記/previous_treatment) 剝除,
只留結構化臨床欄位 (症狀 id、八綱、經絡、方證、觀察數值)。
時間統一為 Unix updated_at (研究端自行轉換), 不輸出可讀日期。
"""
import hashlib


def _pseudo_id(sid: str) -> str:
    """sid → 穩定假名化 ID (不可逆)"""
    return "CASE-" + hashlib.sha256(sid.encode()).hexdigest()[:12]


def _age_band(age):
    """年齡 → 10 歲區間"""
    try:
        a = int(str(age).strip())
        return f"{(a // 10) * 10}-{(a // 10) * 10 + 9}"
    except Exception:
        return None


def deidentify(row: dict, strip_gender: bool = False) -> dict:
    d = row["data"]
    patient = d.get("patient") or {}
    bagang = d.get("bagang") or {}
    lp = d.get("last_prescription") or {}

    out = {
        "case_id": _pseudo_id(row["sid"]),
        "updated_at": row["updated_at"],
        "created_at": row["created_at"],
        # 病人: 只留統計必要且去識別的欄位
        "age_band": _age_band(patient.get("age")),
        "gender": None if strip_gender else patient.get("gender") or None,
        "body_type": patient.get("body_type") or None,
        "chronic_history": bool(patient.get("history")),
        "on_medication": bool(patient.get("medication")),
        "pregnant": bool(patient.get("pregnancy")),
        "allergy": bool(patient.get("allergy")),
        # 八綱
        "bagang": {k: bagang.get(k) for k in ("病位", "寒熱", "虛實", "嚴重度") if bagang.get(k)},
        # 症狀 (結構化 id)
        "symptoms": d.get("symptoms") or {},
        "differential_meridians": list((d.get("differential") or {}).keys()),
        # 推論/選方
        "selected_formula": lp.get("name"),
        "formula_match": lp.get("match"),
        "observations": d.get("observations") or {},
        # 服藥觀察 log: 只留結構化欄位, 剝 notes 自由文字
        "medication_log": [
            {k: e.get(k) for k in ("node", "sweat", "symptom_change",
                                    "temperature", "pulse_rate", "pain_scale",
                                    "escalation_triggered") if e.get(k)}
            for e in (d.get("medication_log") or [])
        ],
    }
    return out
