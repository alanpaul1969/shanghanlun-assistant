"""
傷寒論助手 (Shanghan Lun Assistant) — WebUI v2 (clinical × SaaS dashboard)
Flask 3.x skeleton — Phase 1 MVP, v2 visual direction.

路由對應 v2 規劃 §4：
  S1  Home / Dashboard
  S2-1 病人基本資料  →  /intake/basic
  S2-2 起病與主訴    →  /intake/onset
  S2-3 望診          →  /intake/inspection
  S2-4 聞診          →  /intake/auscultation
  S2-5 問診（核心）  →  /intake/inquiry    ← 7 區分節 + sticky inference sidebar
  S2-6 切診          →  /intake/palpation
  S2-7 鑑別問答      →  /intake/differential
  S3  推論儀表板     →  /inference
  S4  服藥觀察       →  /observe
  S4-2 加減決策      →  /observe/modify
  S4-3 救逆模式      →  /observe/rescue
  S5  Library         →  /library

Phase 1 MVP 範圍 = 上面 5 個核心頁 + Library demo (其餘為 v2.1 之後做)。
"""
import datetime
from flask import Flask, render_template, send_from_directory, abort, request, redirect, url_for
from persistent_session import PersistentSession, init_app as init_session_app
from i18n import init_i18n, t as _t
from pathlib import Path
import os
import time

# ── 套用路徑 ────────────────────────────────────────────
WEBUI_DIR = Path(__file__).parent
STATIC_DIR = WEBUI_DIR / "static"
IMG_DIR = STATIC_DIR / "img"
REPO_ROOT = WEBUI_DIR.parent  # Treatise on Cold Injury/
VAULT_02 = REPO_ROOT.parent / "Personal Wing/Medical/TCM/傷寒論/app-design"
VAULT_00 = REPO_ROOT.parent / "Personal Wing/Medical/TCM/傷寒論"

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(WEBUI_DIR / "templates"))
app.secret_key = os.environ.get("FLASK_SECRET", "shanghanlun-v0.2-dev-key-change-in-prod")
init_session_app(app)  # 註冊 session_id cookie after_request
init_i18n(app)  # 多語言: t() global + /set-lang route

# ── Subpath mounting（Tailscale Funnel / Cloudflare Tunnel / reverse proxy）──
#  Tailscale Funnel strip /shanghanlun 前綴但 SCRIPT_NAME 環境變數沒設、
#  X-Forwarded-Prefix 也沒送。最穩的方式：自己寫 WSGI middleware 直接 rewrite。
SUBPATH = os.environ.get("SUBPATH", "/shanghanlun")  # 預設對應 Tailscale Funnel subpath

def highlight_q(text, q):
    """Jinja2 filter: 把 text 內 q 字串 (case-insensitive) 包進 <mark>。q 空或空字串 → 不動。"""
    if not q or not text:
        return text
    from markupsafe import Markup
    import re
    pattern = re.escape(q)
    highlighted = re.sub(
        f"({pattern})",
        r'<mark style="background: #FEF08A; padding: 0 2px; border-radius: 2px;">\1</mark>',
        text,
        flags=re.IGNORECASE,
    )
    return Markup(highlighted)
# 註冊 Jinja filter
app.jinja_env.filters['highlight_q'] = highlight_q


class SubpathMiddleware:
    """在 reverse proxy 已經 strip prefix 後, 讓 Flask 內部所有 url_for/redirect 都加回 prefix。"""
    def __init__(self, app, subpath):
        self.app = app
        self.subpath = subpath.rstrip("/")

    def __call__(self, environ, start_response):
        # 把 /shanghanlun 設成 SCRIPT_NAME, Flask 自動加回 url_for
        if self.subpath and self.subpath != "/":
            environ["SCRIPT_NAME"] = self.subpath
            # 確保 PATH_INFO 沒殘留 prefix
            if environ.get("PATH_INFO", "").startswith(self.subpath + "/"):
                environ["PATH_INFO"] = environ["PATH_INFO"][len(self.subpath):]
            elif environ.get("PATH_INFO") == self.subpath:
                environ["PATH_INFO"] = "/"
        return self.app(environ, start_response)

if SUBPATH and SUBPATH != "/":
    app.wsgi_app = SubpathMiddleware(app.wsgi_app, SUBPATH)

# 同時也設 Flask config (本機直接用 SCRIPT_NAME 也可生效)
if SUBPATH and SUBPATH != "/":
    app.config["SCRIPT_NAME"] = SUBPATH


# ── Demo 資料 (Phase 1 placeholder) ─────────────────────
# 這些之後要換成實際的規則庫 + 條文 DB + 推論引擎
DEMO_PATIENT = {
    "name": "張大明",
    "age": 42,
    "gender": "M",
    "chief_complaint": "頭痛、發熱 3 天",
    "onset": "3 天前淋雨後開始，漸進加重",
    "constitution": "中等",
    "habits": ["偶飲咖啡", "不抽菸"],
}

DEMO_SYMPTOMS = {
    "寒熱": "發熱 (38.5°C)，微惡風",
    "汗出": "微汗",
    "頭身": "頭痛（前額 + 整頭），項微強",
    "飲食": "口渴欲飲溫水，食慾減",
    "二便": "小便清長，大便稍硬",
    "睡眠": "入睡困難，淺眠",
    "情緒": "易煩躁",
    "脈象": "浮緩（自我評估）",
}

# 六經推論（v2 spec 用 6 種色票：太陽橙、陽明紅、少陽黃、太陰綠、少陰藍、厥陰紫）
DEMO_MERIDIAN_INFERENCE = [
    {"name": "太陽", "meridian": "taiyang",  "color": "#EA580C", "pct": 87, "bar": "████████████████████████████"},
    {"name": "陽明", "meridian": "yangming", "color": "#DC2626", "pct": 41, "bar": "█████████████"},
    {"name": "少陽", "meridian": "shaoyang", "color": "#CA8A04", "pct": 22, "bar": "███████"},
    {"name": "太陰", "meridian": "taiyin",   "color": "#65A30D", "pct":  8, "bar": "██"},
    {"name": "少陰", "meridian": "shaoyin",  "color": "#1D4ED8", "pct":  4, "bar": "█"},
    {"name": "厥陰", "meridian": "jueyin",   "color": "#7C3AED", "pct":  3, "bar": "█"},
]

DEMO_PRESCRIPTIONS = [
    {
        "rank": 1, "name": "桂枝湯", "syndrome": "太陽中風（風傷衛）",
        "match": 87, "confidence": "High",
        "matched_features": ["頭痛", "發熱", "汗出", "惡風", "脈緩"],
        "missing_features": ["脈象尚未驗證"],
        "composition": [
            {"name": "桂枝", "qty": "9.0 g"},
            {"name": "芍藥", "qty": "9.0 g"},
            {"name": "生薑", "qty": "9.0 g"},
            {"name": "大棗", "qty": "12.0 g"},
            {"name": "甘草", "qty": "6.0 g"},
        ],
        "algorithm_lens": ["#P1-001 主方樹", "#P1-007 鑑別"],
        "rationale": "5 features matched; 1 conditional rule triggered",
        "contraindications": [
            "脈浮緊 (floating-tight) → 太陽傷寒/麻黃湯",
            "瘡家 / 淋家 / 衄家 / 汗家",
        ],
        "source_text": "「太陽病，頭痛，發熱，汗出，惡風，桂枝湯主之。」",
        "source_ref": "傷寒論 宋本 13 條",
    },
    {
        "rank": 2, "name": "桂枝加葛根湯", "syndrome": "太陽中風 + 項背強",
        "match": 64, "confidence": "Medium",
        "matched_features": ["頭痛", "發熱", "汗出", "項微強"],
        "missing_features": ["項強需驗證"],
        "composition": [],
        "algorithm_lens": ["#P1-001 主方樹"],
        "rationale": "次選 — 項強症狀需明確",
        "contraindications": [],
        "source_text": "「太陽病，項背強几几，反汗出惡風者，桂枝加葛根湯主之。」",
        "source_ref": "傷寒論 宋本 14 條",
    },
    {
        "rank": 3, "name": "桂枝加厚朴杏子湯", "syndrome": "太陽中風 + 喘",
        "match": 52, "confidence": "Medium",
        "matched_features": ["頭痛", "發熱", "汗出", "惡風"],
        "missing_features": ["無喘症"],
        "composition": [],
        "algorithm_lens": ["#P1-001 主方樹"],
        "rationale": "無喘症 — 次次選",
        "contraindications": [],
        "source_text": "「喘家作，桂枝湯加厚朴杏子佳。」",
        "source_ref": "傷寒論 宋本 18 條",
    },
]

DEMO_OBSERVATION = {
    "formula": "桂枝湯",
    "session_id": "2026-10-15",
    "day": 1,
    "sop": [
        {"step": 1, "text": "水 700 mL → 煮至 300 mL → 過濾"},
        {"step": 2, "text": "服 150 mL 溫服 + 100 mL 熱稀粥（啜粥）"},
        {"step": 3, "text": "蓋被微取汗（覆汗）"},
        {"step": 4, "text": "⏹ 若已得汗則停（中病即止）"},
        {"step": 5, "text": "若未得汗，~6 小時後再服"},
    ],
    "stop_conditions": [
        "已得微汗（sweating achieved）",
        "出現新的禁忌症狀",
        "原有症狀加重",
    ],
    "timeline_nodes": [
        {"label": "服首劑",   "at": "Now",    "check": "已服 150 mL"},
        {"label": "30 分後",  "at": "+30m",   "check": "Check 汗出（24 條：反煩不解？）"},
        {"label": "1 小時後", "at": "+1h",    "check": "Recheck 症狀"},
        {"label": "2 小時後", "at": "+2h",    "check": "反煩不解 → 刺風池風府 + 再服"},
        {"label": "6 小時後", "at": "+6h",    "check": "大煩渴 + 脈洪大（26 條）→ 轉白虎加人參湯？"},
        {"label": "12 小時後", "at": "+12h",   "check": "Full re-eval"},
    ],
    "vitals": {
        "temperature": [("0h", 38.5), ("2h", 38.0), ("4h", 37.8), ("6h", 37.5), ("8h", 37.2)],
        "pain": [("0h", 7), ("2h", 5), ("4h", 4), ("6h", 3), ("8h", 2)],
    },
    "escalation": [
        "12 小時後症狀加重",
        "高燒 > 39.5°C 或新胸痛",
        "意識改變、嚴重頭痛",
    ],
}

DEMO_LIBRARY_ENTRIES = [
    # 13 條 — 桂枝湯主證
    {
        "id": 13, "category": "太陽上篇", "formula": "桂枝湯",
        "versions": {
            "宋本":   "「太陽病，頭痛，發熱，汗出，惡風，桂枝湯主之。」",
            "張卿子": "「太陽病，頭痛發熱，汗出惡風者，桂枝湯主之。（張卿子按：此太陽中風本證也。）」",
            "來蘇集": "「太陽病，頭痛，發熱，汗出，惡風者，桂枝湯證。柯韻伯：此為桂枝湯正局。」",
            "桂林":   "「太陽病，頭痛，發熱，汗出，惡風，桂枝湯主之。（第12稿 6.14）」",
        },
        "algorithm_notes": ["#P1-001 主方樹", "#P1-007 鑑別", "#P1-019 適應症"],
        "category_note": "太陽病中風本證，最常見處方起點。",
    },
    # 14 條 — 桂枝加葛根湯
    {
        "id": 14, "category": "太陽上篇", "formula": "桂枝加葛根湯",
        "versions": {
            "宋本":   "「太陽病，項背強几几，反汗出惡風者，桂枝加葛根湯主之。」",
            "張卿子": "「太陽病，項背強几几，汗出惡風者，桂枝加葛根湯主之。（按：几几，項強貌。）",
            "來蘇集": "「桂枝加葛根湯證：項背強几几，汗出惡風。」",
            "桂林":   "「太陽病，項背強几几，反汗出惡風者，桂枝加葛根湯主之。（6.15）」",
        },
        "algorithm_notes": ["#P1-001 主方樹", "#P1-013 症狀加權"],
        "category_note": "桂枝湯證 + 項背強 → 加葛根。",
    },
    # 24 條 — 刺風池風府（post-dose recheck）
    {
        "id": 24, "category": "太陽上篇", "formula": "桂枝湯 + 針刺",
        "versions": {
            "宋本":   "「服桂枝湯，反煩不解者，先刺風池、風府，卻與桂枝湯則愈。」",
            "張卿子": "「服桂枝湯，反煩不解者，先刺風池、風府，卻與桂枝湯則愈。（按：風邪仍在於經，當刺以洩之。）",
            "來蘇集": "「服桂枝湯反煩不解，此風邪猶在經也，先刺風池風府，卻與桂枝湯則愈。」",
            "桂林":   "「服桂枝湯，反煩不解者，先刺風池、風府，卻與桂枝湯則愈。（6.24）」",
        },
        "algorithm_notes": ["#P1-007 post-dose recheck", "#P1-009 條件分支"],
        "category_note": "服藥後反煩不解 = 風邪仍鬱於經 → 針瀉 + 再服。",
    },
    # 26 條 — 救逆：轉白虎加人參湯
    {
        "id": 26, "category": "太陽上篇", "formula": "白虎加人參湯",
        "versions": {
            "宋本":   "「服桂枝湯，大汗出後，大煩渴不解，脈洪大者，白虎加人參湯主之。」",
            "張卿子": "「服桂枝湯，大汗出後，大煩渴不解，脈洪大者，白虎加人參湯主之。（按：此陽明氣分熱盛也。）",
            "來蘇集": "「白虎加人參湯證：服桂枝大汗出後，大煩渴不解，脈洪大者，陽明熱盛。」",
            "桂林":   "「服桂枝湯，大汗出後，大煩渴不解，脈洪大者，白虎加人參湯主之。（6.27）」",
        },
        "algorithm_notes": ["#P1-013 錯誤注入", "#P1-014 錯誤復原", "#P1-022 救逆判斷"],
        "category_note": "服桂枝湯過汗 → 病傳陽明 → 急轉白虎加人參湯。",
    },
]


# ── 路由 ──────────────────────────────────────────────
@app.route("/")
def home():
    session = _s()
    lp = session.get("last_prescription") or {}
    current_session = None
    if lp.get("name"):
        current_session = {
            "date": datetime.date.today().isoformat(),
            "syndrome": (session.get("bagang", {}) or {}).get("chief_complaint", "") or "目前診次",
            "prescription": lp.get("name", ""),
            "match": lp.get("match", 0),
        }
    return render_template(
        "home.html",
        current_session=current_session,
        patient=DEMO_PATIENT,
        active_sessions=[
            {
                "date": "2026-10-15", "syndrome": "太陽中風",
                "prescription": "桂枝湯", "match": 87,
                "status": "⏸ 等待下次服藥節點",
                "status_class": "paused",
            },
            {
                "date": "2026-10-10", "syndrome": "少陽病",
                "prescription": "小柴胡湯", "match": 74,
                "status": "✓ 已結束",
                "status_class": "done",
            },
        ],
    )


# 8 步流程順序（按 v2 spec §4 S2-1 → S2-7）
INTAKE_FLOW = [
    ("basic",        1, "病人與起病"),
    ("exam",         2, "四診檢查"),
    ("inquiry",      3, "問診"),
    ("differential", 4, "鑑別問答"),
]
TOTAL_STEPS = 5  # 4 步 + inference


def _intake_next_prev(step_id):
    """給定 step_id, 回傳 (prev_step_or_None, next_step_or_None)"""
    ids = [s[0] for s in INTAKE_FLOW]
    if step_id not in ids:
        return None, None
    i = ids.index(step_id)
    prev_ = INTAKE_FLOW[i - 1][0] if i > 0 else None
    next_ = INTAKE_FLOW[i + 1][0] if i < len(ids) - 1 else "inference"
    return prev_, next_


@app.route("/intake")
@app.route("/intake/")
def intake_root():
    """預設入口 = S2-1 病人基本資料真實表單"""
    return redirect(url_for("intake_basic"))


def _s():
    """當前 request 的 PersistentSession (替代 flask.session, 用 SQLite 4GB+ 可用)"""
    return PersistentSession()


# ── S2-1 病人基本資料 ──────────────────────────────
# ── ⚡ 快診模式 (八綱 4 題, v0.4.2) ───────────────────
@app.route("/quick", methods=["GET", "POST"])
def quick():
    """快診: 主訴 + 八綱 3-4 題 → 六經直接映射 → 推論"""
    session = _s()
    if request.method == "POST":
        session["bagang"] = {
            "chief_complaint": request.form.get("chief_complaint", "").strip(),
            "病位":   request.form.get("b_wei", "裡"),
            "寒熱":   request.form.get("b_hanre", "熱"),
            "虛實":   request.form.get("b_xushi", "不確定"),
            "嚴重度": request.form.get("b_severity", "輕"),
        }
        session["quick_mode"] = True
        return redirect(url_for("quick_diagnosis"))
    return render_template("quick.html", total_steps=2)


@app.route("/quick/diagnosis")
def quick_diagnosis():
    """⚡ 快診辨六經中間頁 — 八綱 → 六經辨證結果展示, 再進方證"""
    session = _s()
    from inference_engine import infer_from_bagang
    bagang = session.get("bagang", {}) or {}
    if not bagang:
        return redirect(url_for("quick"))
    result = infer_from_bagang(
        bagang.get("chief_complaint", ""),
        bagang.get("病位", "裡"), bagang.get("寒熱", "熱"),
        bagang.get("虛實", "不確定"), bagang.get("嚴重度", "輕"),
    )
    return render_template(
        "quick_diagnosis.html",
        bagang=bagang,
        meridians=result["meridian_inference"],
        prescriptions=result.get("prescriptions", [])[:3],
        confidence=result.get("confidence", "Low"),
    )


@app.route("/quick/followup", methods=["GET", "POST"])
def quick_followup():
    """⚡ 快診追問 — 辨六經後, 該經條文差異點追問 (加減項內容)"""
    session = _s()
    from diff_qu_data import QUICK_FOLLOWUP
    from inference_engine import infer_from_bagang
    bagang = session.get("bagang", {}) or {}
    if not bagang:
        return redirect(url_for("quick"))

    result = infer_from_bagang(
        bagang.get("chief_complaint", ""),
        bagang.get("病位", "裡"), bagang.get("寒熱", "熱"),
        bagang.get("虛實", "不確定"), bagang.get("嚴重度", "輕"),
    )
    rankings = result["meridian_inference"]
    top_meridian = rankings[0]["name"] if rankings else "太陽"
    second_meridian = rankings[1]["name"] if len(rankings) > 1 and rankings[1]["pct"] >= 50 else None

    if request.method == "POST":
        # 合併追問答案 → session["differential"] (nested by meridian, 同詳診形狀)
        from diff_qu_data import FOLLOWUP_SYMPTOM_MAP
        diff = session.get("differential", {}) or {}
        symptoms = session.get("symptoms", {}) or {}

        def _collect(qs, meridian):
            for q in qs:
                v = request.form.get(q["id"])
                if not v or v in ("不確定",):
                    continue
                diff.setdefault(meridian, {})[q["id"]] = v
                mapped = FOLLOWUP_SYMPTOM_MAP.get(v)
                if mapped:
                    for cat, sid in mapped:
                        symptoms.setdefault(cat, [])
                        if sid not in symptoms[cat]:
                            symptoms[cat].append(sid)

        _collect(QUICK_FOLLOWUP.get(top_meridian, []), top_meridian)
        if second_meridian:
            _collect(QUICK_FOLLOWUP.get(second_meridian, [])[:2], second_meridian)

        # v0.4.5: LLM 生成的 x- 動態題 — 先查 GET 時存的 option→[症狀id] map,
        # 沒有再 fallback FOLLOWUP_SYMPTOM_MAP; sid 需回查 category
        from diff_qu_data import FOLLOWUP_SYMPTOM_MAP
        from inference_engine import load_symptom_matrix
        matrix = load_symptom_matrix()  # sid → category 回查用
        sid_to_cat = {}
        for cat, sids in matrix.items():
            if cat.startswith("_"):
                continue
            for sid in sids:
                sid_to_cat[sid] = cat

        def _merge_sid(sid):
            cat = sid_to_cat.get(sid)
            if not cat:
                return
            symptoms.setdefault(cat, [])
            if sid not in symptoms[cat]:
                symptoms[cat].append(sid)

        for key, v in request.form.items():
            if not key.startswith("x-") or not v or v in ("不確定",):
                continue
            diff.setdefault(top_meridian, {})[key] = v
            hit = False
            for ex in session.get("followup_extra", []) or []:
                if ex.get("id") == key:
                    sids = (ex.get("map") or {}).get(v, [])
                    for sid in sids:
                        if isinstance(sid, str):
                            _merge_sid(sid)
                        hit = True
                    break
            if not hit:
                mapped = FOLLOWUP_SYMPTOM_MAP.get(v)
                if mapped:
                    for cat, sid in mapped:
                        symptoms.setdefault(cat, [])
                        if sid not in symptoms[cat]:
                            symptoms[cat].append(sid)

        session["differential"] = diff
        session["symptoms"] = symptoms
        session["followup_done"] = True
        return redirect(url_for("inference"))

    questions = QUICK_FOLLOWUP.get(top_meridian, [])
    second_questions = QUICK_FOLLOWUP.get(second_meridian, [])[:2] if second_meridian else []

    # v0.4.5: LLM 依主訴排序題庫 + 生成主訴特異加減項追問 (失敗 fallback 靜態)
    from llm_followup import build_followup_questions
    llm_fq = build_followup_questions(
        bagang.get("chief_complaint", ""), questions,
        result.get("prescriptions", []), top_meridian,
    )
    questions = llm_fq["questions"]
    extra_questions = llm_fq.get("extra", [])
    session["followup_extra"] = extra_questions  # x- 題 + map, POST 用

    return render_template(
        "quick_followup.html",
        top_meridian=top_meridian,
        second_meridian=second_meridian,
        questions=questions,
        second_questions=second_questions,
        extra_questions=extra_questions,
        llm_note=llm_fq.get("llm_note", ""),
        llm_used=llm_fq.get("llm_used", False),
        prescriptions=result.get("prescriptions", [])[:3],
        bagang=bagang,
        confidence=result.get("confidence", "Low"),
        total_steps=3,
    )


@app.route("/intake/basic", methods=["GET", "POST"])
def intake_basic():
    session = _s()
    """S2-1 病人基本資料 (GET 表單 / POST 寫 session + 推 S2-2)"""
    if request.method == "POST":
        session["patient"] = {
            "name":      request.form.get("name", "").strip(),
            "gender":    request.form.get("gender", ""),       # M / F / O
            "age":       int(request.form.get("age", "0") or 0),
            "body_type": request.form.get("body_type", ""),    # 中等/偏胖/偏瘦/實/虛
            "habits":    request.form.getlist("habits"),        # 抽菸/喝酒/咖啡/熬夜/...
            "history":   request.form.get("history", "").strip(),  # 既往病史
            "medication": request.form.get("medication", "").strip(),  # 目前用藥
            "pregnancy": request.form.get("pregnancy", "no"),  # 孕否 (F 才問)
            "allergy":   request.form.get("allergy", "").strip(),
        }
        # v0.4.2 合併: 起病欄位同頁收
        session["onset"] = {
            "chief_complaint": request.form.get("chief_complaint", "").strip(),
            "onset_date":      request.form.get("onset_date", ""),
            "onset_speed":     request.form.get("onset_speed", ""),
            "trigger":         request.form.get("trigger", ""),
            "aggravating":     request.form.get("aggravating", "").strip(),
            "relieving":       request.form.get("relieving", "").strip(),
            "previous_treatment": request.form.get("previous_treatment", "").strip(),
        }
        return redirect(url_for("intake_exam"))
    return render_template(
        "intake_basic.html",
        step_num=1,
        total_steps=TOTAL_STEPS,
        patient=session.get("patient", {}),
        onset=session.get("onset", {}),
    )


# ── S2-2 起病與主訴 ──────────────────────────────
@app.route("/intake/onset", methods=["GET", "POST"])
def intake_onset():
    session = _s()
    """S2-2 起病與主訴 (GET 表單 / POST 寫 session + 推 S2-3)"""
    if request.method == "POST":
        session["onset"] = {
            "chief_complaint": request.form.get("chief_complaint", "").strip(),
            "onset_date":      request.form.get("onset_date", ""),       # YYYY-MM-DD
            "onset_speed":     request.form.get("onset_speed", ""),      # 急/漸
            "trigger":         request.form.get("trigger", ""),          # 淋雨/受寒/勞累/情緒/食積
            "aggravating":     request.form.get("aggravating", "").strip(),
            "relieving":       request.form.get("relieving", "").strip(),
            "previous_treatment": request.form.get("previous_treatment", "").strip(),
        }
        return redirect(url_for("intake_step", step="inspection"))
    return render_template(
        "intake_onset.html",
        step_num=2,
        total_steps=TOTAL_STEPS,
        onset=session.get("onset", {}),
    )


@app.route("/tongue-vlm-upload", methods=["POST"])
def tongue_vlm_upload():
    """v0.4.2: 舌診照片上傳 (四診檢查頁用) — 分析 → 填 observations → 回 exam"""
    session = _s()
    f = request.files.get("tongue_photo")
    vlm_result = {"ok": False, "error": "no file"}
    if f and f.filename:
        save_path = STATIC_DIR / "img" / f"tongue_upload_{int(time.time())}.png"
        f.save(str(save_path))
        from tongue_vlm import analyze_tongue_photo
        vlm_result = analyze_tongue_photo(str(save_path))
        if vlm_result.get("ok"):
            obs = session.get("observations", {}) or {}
            if vlm_result.get("tongue_body"):
                obs["tongue_body"] = vlm_result["tongue_body"]
            if vlm_result.get("tongue_coat"):
                obs["tongue_coat"] = vlm_result["tongue_coat"]
            if vlm_result.get("moisture") in ("潤", "乾", "膩"):
                obs["moisture"] = vlm_result["moisture"]
            session["observations"] = obs
    session["vlm_result"] = vlm_result
    return redirect(url_for("intake_exam"))


# ── 四診檢查 (望+聞+切 合併, v0.4.2) ──────────────────
@app.route("/intake/exam", methods=["GET", "POST"])
def intake_exam():
    """四診檢查一頁: 望(6) + 聞(5) + 切(6, 含複合脈) = 17 欄 → session['observations']"""
    session = _s()
    if request.method == "POST":
        obs = session.get("observations", {}) or {}
        # 望
        obs["complexion"]   = request.form.get("complexion", "")
        obs["tongue_body"]  = request.form.get("tongue_body", "")
        obs["tongue_coat"]  = request.form.get("tongue_coat", "")
        obs["body_form"]    = request.form.get("body_form", "")
        obs["spirit"]       = request.form.get("spirit", "")
        obs["skin"]         = request.form.get("skin", "")
        # 聞
        obs["voice"]        = request.form.get("voice", "")
        obs["speech"]       = request.form.get("speech", "")
        obs["cough"]        = request.form.get("cough", "")
        obs["breathing"]    = request.form.get("breathing", "")
        obs["odor"]         = request.form.get("odor", "")
        # 切
        obs["pulse"]        = request.form.get("pulse", "")
        obs["pulse_combo"]  = request.form.get("pulse_combo", "")
        obs["pulse_count"]  = request.form.get("pulse_count", "")
        obs["abdomen"]      = request.form.get("abdomen", "")
        obs["skin_temp"]    = request.form.get("skin_temp", "")
        obs["moisture"]     = request.form.get("moisture", "")
        session["observations"] = obs
        return redirect(url_for("intake_inquiry"))
    return render_template(
        "intake_exam.html",
        step_num=2,
        total_steps=TOTAL_STEPS,
        obs=session.get("observations", {}) or {},
    )


@app.route("/intake/inquiry", methods=["GET", "POST"])
def intake_inquiry():
    session = _s()
    """S2-5 問診（核心）— GET 顯示表單 / POST 收症狀 + 推到 /inference"""
    if request.method == "POST":
        # 收症狀表單 → 寫 session → 推 /inference
        symptoms = {}
        for cat, ids in request.form.lists():
            if cat.startswith("cat:"):
                category = cat[4:]
                # form name pattern: cat:<category>:<symptom_id>
                # 收集每個 category 下勾選的 symptom_id
                sids = []
                for v in ids:
                    sids.append(v)
                symptoms[category] = sids
        session["symptoms"] = symptoms
        return redirect(url_for("intake_differential"))  # v0.4.2: 問診 → 鑑別 (切診已併入四診檢查)
    # GET: 顯示症狀表單
    return render_template(
        "intake_inquiry.html",
        step=3,
        total_steps=TOTAL_STEPS,
    )


# ── S2-7 鑑別問答 (differential) ──────────────────────
@app.route("/intake/differential", methods=["GET", "POST"])
def intake_differential():
    session = _s()
    """S2-7 鑑別問答 - GET 顯示 6 經追問 / POST 收答案 → 合併進 session['symptoms'] → 推 /inference"""
    if request.method == "POST":
        # 表單欄位 differential_answers 是 JS 收集的 JSON 字串
        raw = request.form.get("differential_answers", "").strip()
        diff = {}
        if raw:
            try:
                import json
                diff = json.loads(raw)
            except Exception:
                diff = {}

        # 保留原始答案供 inference.html 顯示
        session["differential"] = diff
        # base symptoms 不動 (S2-5 已經寫進 session["symptoms"])
        # 推論引擎 infer_with_differential() 會自動合併 base + diff
        return redirect(url_for("inference"))

    return render_template(
        "intake_differential.html",
        step_num=4,
        total_steps=TOTAL_STEPS,
        diff_questions=__import__("diff_qu_data").DIFF_QUESTIONS,
    )


# ── S2-3 望診 (Inspection) ─────────────────────────────
@app.route("/intake/inspection", methods=["GET", "POST"])
def intake_inspection():
    """S2-3 望診 (Observation) — 寫 session['observations']: 面色/舌/形態"""
    session = _s()
    if request.method == "POST":
        obs = session.get("observations", {}) or {}
        obs["complexion"] = request.form.get("complexion", "")  # 面色: 紅潤/正常/晦暗/蒼白/潮紅
        obs["tongue_body"] = request.form.get("tongue_body", "")  # 舌體: 淡紅/紅/暗紅/淡白/胖大/瘦薄
        obs["tongue_coat"] = request.form.get("tongue_coat", "")  # 舌苔: 白薄/白厚/黃薄/黃厚/灰黑/少苔
        obs["body_form"] = request.form.get("body_form", "")  # 形態: 正常/消瘦/肥胖/浮腫
        obs["spirit"] = request.form.get("spirit", "")  # 神態: 清晰/萎靡/煩躁/嗜睡
        obs["skin"] = request.form.get("skin", "")  # 膚色: 正常/蒼白/黃染/潮紅/瘀斑
        session["observations"] = obs
        return redirect(url_for("intake_auscultation"))
    return render_template(
        "intake_inspection.html",
        step_num=3,
        total_steps=TOTAL_STEPS,
        obs=session.get("observations", {}) or {},
        vlm_result=session.get("vlm_result", None),
    )


# ── S2-4 聞診 (Auscultation & Olfaction) ─────────────
@app.route("/intake/auscultation", methods=["GET", "POST"])
def intake_auscultation():
    """S2-4 聞診 — 寫 session['observations']: 語聲/氣味/咳嗽/呼吸"""
    session = _s()
    if request.method == "POST":
        obs = session.get("observations", {}) or {}
        obs["voice"] = request.form.get("voice", "")  # 語聲: 正常/低微/洪亮/嘶啞/重濁
        obs["speech"] = request.form.get("speech", "")  # 語言: 清晰/譫語/鄭聲/獨語/失語
        obs["cough"] = request.form.get("cough", "")  # 咳嗽: 無/輕咳/重咳/乾咳/痰咳
        obs["breathing"] = request.form.get("breathing", "")  # 呼吸: 正常/氣短/喘/促/微弱
        obs["odor"] = request.form.get("odor", "")  # 氣味: 無/酸腐/腥臭/痰腥
        session["observations"] = obs
        return redirect(url_for("intake_inquiry"))  # S2-4 完 → 進 S2-5 問診
    return render_template(
        "intake_auscultation.html",
        step_num=4,
        total_steps=TOTAL_STEPS,
        obs=session.get("observations", {}) or {},
    )


# ── S2-6 切診 (Palpation / Pulse) ───────────────────
@app.route("/intake/palpation", methods=["GET", "POST"])
def intake_palpation():
    """S2-6 切診 — 寫 session['observations']: 脈象/腹診/穴位"""
    session = _s()
    if request.method == "POST":
        obs = session.get("observations", {}) or {}
        obs["pulse"] = request.form.get("pulse", "")  # 脈象: 浮/沉/遲/數/虛/實/滑/澀/弦/緊/緩/弱
        obs["pulse_combo"] = request.form.get("pulse_combo", "")  # v0.3.x 複合脈 (優先於單脈)
        obs["pulse_count"] = request.form.get("pulse_count", "")  # 脈率
        obs["abdomen"] = request.form.get("abdomen", "")  # 腹診: 軟/硬/脹/痛/喜按/拒按
        obs["skin_temp"] = request.form.get("skin_temp", "")  # 膚溫: 正常/熱/涼
        obs["moisture"] = request.form.get("moisture", "")  # 膚潤: 潤/乾/汗
        session["observations"] = obs
        return redirect(url_for("intake_differential"))  # S2-6 完 → 進 S2-7 鑑別
    return render_template(
        "intake_palpation.html",
        step_num=6,
        total_steps=TOTAL_STEPS,
        obs=session.get("observations", {}) or {},
    )


@app.route("/intake/<step>")
def intake_step(step):
    """8 步流程其中一步 (S2-1..S2-7, 排除 S2-5 走 /intake/inquiry)"""
    titles = {s[0]: s[2] for s in INTAKE_FLOW}
    nums = {s[0]: s[1] for s in INTAKE_FLOW}
    if step not in titles:
        abort(404)
    if step == "inquiry":
        # S2-5 走專屬 /intake/inquiry route (含 POST handler)
        return redirect(url_for("intake_inquiry"))
    if step == "basic":
        return redirect(url_for("intake_basic"))
    if step == "onset":
        return redirect(url_for("intake_onset"))
    if step == "inspection":
        return redirect(url_for("intake_inspection"))
    if step == "auscultation":
        return redirect(url_for("intake_auscultation"))
    if step == "palpation":
        return redirect(url_for("intake_palpation"))
    prev_, next_ = _intake_next_prev(step)

    # S2-7 鑑別問答 走專屬 template (動態生成 6 經追問)
    if step == "differential":
        from diff_qu_data import DIFF_QUESTIONS
        return render_template(
            "intake_differential.html",
            title=titles[step],
            step_num=nums[step],
            step_id=step,
            prev_step=prev_,
            next_step=next_,
            diff_questions=DIFF_QUESTIONS,
            inference=DEMO_MERIDIAN_INFERENCE,
            total_steps=TOTAL_STEPS,
        )

    return render_template(
        "intake_step.html",
        title=titles[step],
        step_num=nums[step],
        step_id=step,
        prev_step=prev_,
        next_step=next_,
        inference=DEMO_MERIDIAN_INFERENCE,
        total_steps=TOTAL_STEPS,
    )


@app.route("/inference")
def inference():
    session = _s()
    """S3 推論儀表板 — 從 session 拿症狀 + differential + patient → 跑 infer_with_differential"""
    from inference_engine import infer_with_differential

    # DEBUG: 紀錄 session 內容到 log
    with open("/tmp/inference_debug.log", "a") as f:
        f.write(f"=== /inference ===\n")
        f.write(f"  session._sid = {session._sid}\n")
        f.write(f"  session._data keys = {list(session._data.keys())}\n")
        if "patient" in session._data:
            f.write(f"  patient = {session._data.get('patient')}\n")

    symptoms = session.get("symptoms", {}) or {}
    diff = session.get("differential", {}) or {}
    observations = session.get("observations", {}) or {}  # v0.3 望聞切
    bagang = session.get("bagang", {}) or {}  # v0.4.2 快診
    patient = dict(session.get("patient", {}) or {})  # copy
    # 內嵌 onset (推論引擎讀 patient['onset'] 抽 previous_treatment)
    if "onset" not in patient:
        patient["onset"] = session.get("onset", {}) or {}

    # v0.5: 主訴 LLM 症狀抽取 — chief_complaint 此前只存不用, 現在抽成症狀 id 併入推論
    from cc_extract import extract_chief_complaint
    chief = (bagang.get("chief_complaint")
             or (patient.get("onset", {}) or {}).get("chief_complaint", "")).strip()
    cc_info = {"llm_used": False, "symptoms": {}, "note": ""}
    if chief:
        cached = session.get("cc_extract") or {}
        if cached.get("chief") == chief:
            cc_info = cached
        else:
            cc_info = extract_chief_complaint(chief)
            cc_info["chief"] = chief
            session["cc_extract"] = cc_info
        if cc_info.get("symptoms"):
            symptoms = dict(symptoms) if symptoms else {}
            for cat, sids in cc_info["symptoms"].items():
                merged_sids = list(dict.fromkeys((symptoms.get(cat) or []) + sids))
                symptoms[cat] = merged_sids

    if not symptoms and not observations and bagang:
        # ⚡ 快診: 只有八綱答案 → 直接映射
        from inference_engine import infer_from_bagang
        result = infer_from_bagang(
            bagang.get("chief_complaint", ""),
            bagang.get("病位", "裡"), bagang.get("寒熱", "熱"),
            bagang.get("虛實", "不確定"), bagang.get("嚴重度", "輕"),
        )
        inference_data = result["meridian_inference"]
        prescriptions = result["prescriptions"]
        key_features, missing_features = [], []
        confidence = result["confidence"]
    elif symptoms or diff or observations:
        # v0.3: infer_with_differential 加 observations 參數 (直接打 engine 的 infer)
        from inference_engine import _DIFF_ANSWER_TO_SYMPTOM
        extra = {}
        for meridian, answers in (diff or {}).items():
            for qid, value in answers.items():
                mapped = _DIFF_ANSWER_TO_SYMPTOM.get(value)
                if mapped:
                    cat, sid = mapped
                    extra.setdefault(cat, []).append(sid)
        merged = {}
        all_cats = set(list(symptoms.keys()) + list(extra.keys()))
        for cat in all_cats:
            merged[cat] = list(set(symptoms.get(cat, []) or []) | set(extra.get(cat, []) or []))

        import inference_engine as _ie
        result = _ie.infer(merged, observations=observations)
        # patient + rescue modifiers (沿用 infer_with_differential 的 modifier 邏輯)
        result["prescriptions"] = _ie._apply_patient_modifiers(result.get("prescriptions", []), patient)
        result["prescriptions"] = _ie._apply_disease_interactions(result.get("prescriptions", []), patient)
        onset = patient.get("onset", {}) or {}
        parsed = _ie._parse_previous_treatments(onset.get("previous_treatment", ""))
        if parsed["formulas"] or parsed["rescue_signs"]:
            result["prescriptions"] = _ie._apply_rescue_modifiers(result.get("prescriptions", []), parsed)
        result["rescue_signs"] = parsed["rescue_signs"]
        result["used_formulas"] = parsed["formulas"]
        result["differential_count"] = sum(len(v) for v in (diff or {}).values())
        result["extra_symptoms_from_differential"] = {k: v for k, v in extra.items() if v}
        inference_data = result["meridian_inference"]
        prescriptions = result["prescriptions"]

        key_features = result.get("key_features", [])
        missing_features = result.get("missing_features", [])
        confidence = result.get("confidence", "Low")
    else:
        # 沒症狀 + 沒 differential → 空狀態
        result = {"differential_count": 0, "extra_symptoms_from_differential": {},
                  "observations_matched": [], "rescue_signs": [], "used_formulas": []}
        inference_data = []
        prescriptions = []
        key_features = []
        missing_features = []
        confidence = "Low"

    # v0.4.2: LLM rerank (共用, 8085 thinking-off proxy)
    rerank_info = {"llm_used": False, "llm_reason": "skipped (no candidates)"}
    _cc = (bagang.get("chief_complaint")
           or (session.get("onset", {}) or {}).get("chief_complaint", "")
           or "")
    if os.environ.get("LLM_RERANK", "1") != "0" and prescriptions:
        try:
            from llm_rerank import rerank_by_llm, build_symptoms_summary
            summary = build_symptoms_summary(symptoms)
            top_meridian = inference_data[0]["name"] if inference_data else ""
            rerank_info = rerank_by_llm(summary, prescriptions, top_meridian, chief_complaint=_cc)
            prescriptions = rerank_info["reranked"]
        except Exception as e:
            rerank_info = {"llm_used": False, "llm_reason": f"rerank error: {type(e).__name__}"}

    # v0.5.1: 存 rerank 後的最終排序 — 醫師選方用 (修: 先前在 rerank 前存 top1 導致選到 rank2)
    session["final_prescriptions"] = prescriptions
    if prescriptions and not session.get("last_prescription"):
        pass  # 不自動選, 等醫師點選

    # v0.4.1: 三版本對照 + 加減項 (所有 path 共用)
    import json as _json
    _passages = _json.loads((Path(__file__).parent / "passages_index.json").read_text())["passages"]
    import re as _re
    for _p in prescriptions:
        _m = _re.search(r'(\d+)\s*條', _p.get("source_ref", ""))
        _ver = {}
        if _m:
            _pid = int(_m.group(1))
            for _pa in _passages:
                if _pa["id"] == _pid:
                    _ver = _pa.get("versions", {})
                    break
        _p["versions"] = _ver
        _base = _p["name"].replace("湯", "")
        _mods = []
        for _pa in _passages:
            if _pa.get("formula") and _pa["formula"] != _p["name"] and _pa["formula"].startswith(_base[:3]):
                _mods.append(f"{_pa['formula']}（{_pa['id']} 條）")
        _p["modifications"] = _mods[:6]

    # v0.5: 七典 RAG — 依 主訴+主經+首選方證 檢索典籍出處 (失敗靜默)
    rag_hits = []
    try:
        import rag_search
        if rag_search.available() and (chief or inference_data or prescriptions):
            _q_parts = [p_ for p_ in [
                chief,
                inference_data[0]["name"] + "證" if inference_data else "",
                prescriptions[0]["name"] if prescriptions else "",
                " ".join(s for cat in (cc_info.get("symptoms") or {}).values() for s in cat),
            ] if p_]
            if _q_parts:
                rag_hits = rag_search.search(" ".join(_q_parts), top_k=4)
    except Exception:
        rag_hits = []

    return render_template(
        "inference.html",
        inference=inference_data,
        prescriptions=prescriptions,
        key_features=key_features,
        missing_features=missing_features,
        confidence=confidence,
        has_symptoms=bool(symptoms or diff),
        symptom_count=sum(len(v) for v in symptoms.values()) if symptoms else 0,
        diff_count=result.get("differential_count", 0),
        diff_extra=result.get("extra_symptoms_from_differential", {}),
        rerank_info=rerank_info,
        cc_info=cc_info,
        chief_text=chief,
        rag_hits=rag_hits,
        observations_matched=result.get("observations_matched", []),
        bagang=bagang,
        patient=patient,
        safety_checks={
            "pregnancy": True, "lactation": True, "pediatric": True,
            "geriatric": True, "chronic": True, "allergies": True,
            "drug_interaction": True,
        },
    )


@app.route("/select/<int:idx>", methods=["POST"])
def select_prescription(idx):
    """v0.5.1 醫師選方 — 從 rerank 後 final_prescriptions 選定 → session['last_prescription'] → 服藥觀察"""
    session = _s()
    finals = session.get("final_prescriptions", []) or []
    if 0 <= idx < len(finals):
        chosen = dict(finals[idx])
        chosen["doctor_selected"] = True
        chosen["selected_rank"] = idx + 1
        session["last_prescription"] = chosen
        session.pop("rag_analysis", None)  # 換方 → 清舊分析
    return redirect(url_for("observe"))


@app.route("/observe", methods=["GET", "POST"])
def observe():
    """S4-1 服藥觀察 — GET 顯示 SOP+timeline+vitals / POST 寫 session['medication_log']"""
    session = _s()
    # 用 session 資料組 obs (從 S3 推論 + formula_to_meridian 動態 SOP)
    presc = session.get("last_prescription", {}) or {}
    if not presc:
        # v0.5.1: 醫師未選方 → 回推論頁選
        return redirect(url_for("inference"))
    formula_name = presc.get("name", "")
    # 依方證動態 SOP (桂枝湯是標準, 其他方 generic)
    sop = DEMO_OBSERVATION["sop"] if formula_name == "桂枝湯" else [
        {"step": 1, "text": "依處方煎藥 (水適量 → 煮至指定量 → 過濾)"},
        {"step": 2, "text": "溫服一服 (依處方劑量)"},
        {"step": 3, "text": "服後觀察反應"},
        {"step": 4, "text": "⏹ 若症狀緩解則停 (中病即止)"},
        {"step": 5, "text": "若未緩解，依醫囑再服"},
    ]
    obs = {
        "formula": formula_name,
        "session_id": session.get("_sid", "")[:8] if hasattr(session, "_sid") else "",
        "day": 1,
        "sop": sop,
        "stop_conditions": DEMO_OBSERVATION["stop_conditions"],
        "timeline_nodes": DEMO_OBSERVATION["timeline_nodes"],
        "vitals": DEMO_OBSERVATION["vitals"],
        "escalation": DEMO_OBSERVATION["escalation"],
    }

    if request.method == "POST":
        # 收服藥觀察 log
        log = {
            "timestamp": str(int(time.time())),
            "formula": formula_name,
            "node": request.form.get("node", ""),  # timeline 節點 (Now/+30m/+1h/+2h/+6h/+12h)
            "sweat": request.form.get("sweat", ""),  # 已汗/未汗/微汗/大汗
            "symptom_change": request.form.get("symptom_change", ""),  # better/same/worse
            "temperature": request.form.get("temperature", ""),
            "pulse_rate": request.form.get("pulse_rate", ""),
            "pain_scale": request.form.get("pain_scale", ""),
            "notes": request.form.get("notes", ""),
            "escalation_triggered": request.form.get("escalation_triggered", "no"),
        }
        med_log = session.get("medication_log", []) or []
        med_log.append(log)
        session["medication_log"] = med_log
        # 若 escalation_triggered=yes → 推救逆
        if log["escalation_triggered"] == "yes":
            return redirect(url_for("observe_rescue"))
        return redirect(url_for("observe"))

    med_log = session.get("medication_log", []) or []

    # v0.5.1: 選方後 RAG × LLM 加減項分析 (per formula 快取, 失敗靜默)
    rag_analysis = session.get("rag_analysis") or {}
    if rag_analysis.get("formula") != formula_name:
        rag_analysis = {"formula": formula_name, "hits": [], "analysis": None}
        try:
            import rag_search
            from llm_rag_analysis import analyze_prescription
            from llm_rerank import build_symptoms_summary
            if rag_search.available():
                _q = f"{formula_name} {presc.get('syndrome', '')} {build_symptoms_summary(session.get('symptoms', {}) or {})}"
                hits = rag_search.search(_q, top_k=5, books=None)
                rag_analysis["hits"] = hits
                if hits:
                    rag_analysis["analysis"] = analyze_prescription(
                        presc, hits,
                        build_symptoms_summary(session.get("symptoms", {}) or {}))
            session["rag_analysis"] = rag_analysis
        except Exception:
            pass

    return render_template(
        "observe.html",
        obs=obs,
        med_log=med_log,
        rag_hits=rag_analysis.get("hits", []),
        rag_analysis=rag_analysis.get("analysis"),
    )


@app.route("/observe/modify", methods=["GET", "POST"])
def observe_modify():
    """S4-2 加減決策 — GET 顯示 branch options / POST 寫 session['modification']"""
    session = _s()
    presc = session.get("last_prescription", {}) or {}
    formula = presc.get("name", "桂枝湯")
    # 依方證的 branch options (從 formula_to_meridian 抓 or 用 demo)
    branches = [
        {"n": 1, "text": f"原方續服 + 觀察 (1 劑後重評)", "source": "臨床常規", "lens": "#P1-006 迭代"},
        {"n": 2, "text": f"原方加減 (症狀微調)", "source": "加減項規則", "lens": "#P1-003 條件分支"},
        {"n": 3, "text": "換方 (主證判斷改變)", "source": "重新推論", "lens": "#P1-013 錯誤注入"},
    ]
    if request.method == "POST":
        session["modification"] = {
            "formula": formula,
            "branch": request.form.get("branch", ""),
            "reason": request.form.get("reason", ""),
            "new_symptoms": request.form.get("new_symptoms", ""),
            "timestamp": str(int(time.time())),
        }
        return redirect(url_for("observe"))
    return render_template(
        "observe_modify.html",
        formula=formula,
        branches=branches,
    )


@app.route("/observe/rescue", methods=["GET", "POST"])
def observe_rescue():
    """S4-3 救逆模式 — GET 顯示救逆推薦 / POST 寫 session['rescue']"""
    session = _s()
    presc = session.get("last_prescription", {}) or {}
    old_formula = presc.get("name", "桂枝湯")
    # 救逆推薦: 依條文 26 條 (桂枝→白虎加人參) 或通用
    if "桂枝" in old_formula:
        rescue_formula = "白虎加人參湯"
        rescue_source = "傷寒論 26 條：服桂枝湯，大汗出後，大煩渴不解，脈洪大者，白虎加人參湯主之。"
    else:
        rescue_formula = "(依證重新推論)"
        rescue_source = "壞病：觀其脈證，知犯何逆，隨證治之。(16 條)"
    if request.method == "POST":
        session["rescue"] = {
            "old_formula": old_formula,
            "new_formula": request.form.get("new_formula", rescue_formula),
            "reason": request.form.get("reason", ""),
            "source": rescue_source,
            "timestamp": str(int(time.time())),
        }
        return redirect(url_for("inference"))  # 重新推論
    return render_template(
        "observe_rescue.html",
        old_formula=old_formula,
        rescue_formula=rescue_formula,
        rescue_source=rescue_source,
    )


@app.route("/library")
def library():
    """S5 條文搜尋 (v0.2.3 全文搜尋 passages_index.json 4 版本)"""
    from pathlib import Path
    import json

    passages_path = Path(__file__).parent / "passages_index.json"
    data = json.loads(passages_path.read_text())
    all_passages = data["passages"]
    version_legend = data["version_legend"]

    # 搜尋 query
    q = (request.args.get("q", "") or "").strip()
    version = request.args.get("version", "all")  # all/song/zhang/laisu/guilin

    # 過濾
    if not q:
        results = all_passages
    else:
        q_lower = q.lower()
        results = []
        for p in all_passages:
            haystack_parts = []
            for ver, txt in p.get("versions", {}).items():
                if version == "all" or ver == version:
                    haystack_parts.append(txt)
            haystack_parts.extend(p.get("keywords", []))
            haystack_parts.extend(p.get("alias", []))
            haystack = " ".join(haystack_parts).lower()
            if q_lower in haystack:
                results.append(p)

    stats = {
        "total": len(all_passages),
        "matched": len(results),
        "version_counts": {v: sum(1 for p in all_passages if v in p["versions"]) for v in version_legend},
    }

    # v0.5: 七典 RAG 跨典搜尋 (有 query 時附帶, 失敗靜默)
    corpus_hits = []
    if q:
        try:
            import rag_search
            if rag_search.available():
                corpus_hits = rag_search.search(q, top_k=5)
        except Exception:
            corpus_hits = []

    return render_template(
        "library.html",
        passages=results,
        q=q,
        version=version,
        version_legend=version_legend,
        stats=stats,
        corpus_hits=corpus_hits,
    )


@app.route("/img/<path:filename>")
def img(filename):
    """靜態圖片（用於 HTML 內嵌 demo 用 P0 PNG）"""
    return send_from_directory(str(IMG_DIR), filename)


# 版號單一來源 = pyproject.toml; pip 安裝後自動讀 metadata, 原始碼執行時 fallback
try:
    from importlib.metadata import version as _pkg_version
    APP_VERSION = _pkg_version("shanghanlun-assistant")
except Exception:
    APP_VERSION = "0.6.3"

@app.context_processor
def _inject_version():
    return {"app_version": APP_VERSION}

# ── v0.6 設定: LLM/VLM 後端選擇 ──────────────────────
@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    import llm_config
    from settings_store import set as sset, get as sget
    probes = {}
    if request.method == "POST":
        sset("llm_backend", request.form.get("llm_backend", "proxy8085"))
        sset("vlm_backend", request.form.get("vlm_backend", "proxy8085"))
        sset("embed_backend", request.form.get("embed_backend", "local8082"))
        sset("llm_custom_base", request.form.get("llm_custom_base", "").strip())
        sset("llm_custom_model", request.form.get("llm_custom_model", "").strip())
        sset("vlm_custom_base", request.form.get("vlm_custom_base", "").strip())
        sset("vlm_custom_model", request.form.get("vlm_custom_model", "").strip())
        # API key: 留空 = 不變更 (避免每次儲存都要重貼)
        if request.form.get("llm_api_key", "").strip():
            sset("llm_api_key", request.form.get("llm_api_key").strip())
        if request.form.get("vlm_api_key", "").strip():
            sset("vlm_api_key", request.form.get("vlm_api_key").strip())
        sset("embed_custom_base", request.form.get("embed_custom_base", "").strip())
        sset("embed_custom_model", request.form.get("embed_custom_model", "").strip())
        sset("embed_api_key", request.form.get("embed_api_key", "").strip())
        return redirect(url_for("settings_page"))
    for p_ in [x["base"] for x in llm_config.LLM_PRESETS] + [x["base"] for x in llm_config.VLM_PRESETS] +               [sget("llm_custom_base", ""), sget("vlm_custom_base", "")]:
        if p_ and p_ not in probes:
            probes[p_] = llm_config.probe(p_)
    return render_template(
        "settings.html",
        embed_presets=llm_config.EMBED_PRESETS,
        embed_sel=sget("embed_backend", "local8082"),
        embed_custom=(sget("embed_custom_base", ""), sget("embed_custom_model", "")),
        embed_key_set=bool(sget("jina_api_key", "")),
        llm_presets=llm_config.LLM_PRESETS,
        vlm_presets=llm_config.VLM_PRESETS,
        llm_sel=sget("llm_backend", "proxy8085"),
        vlm_sel=sget("vlm_backend", "proxy8085"),
        llm_custom=(sget("llm_custom_base", ""), sget("llm_custom_model", "")),
        vlm_custom=(sget("vlm_custom_base", ""), sget("vlm_custom_model", "")),
        llm_key_set=bool(sget("llm_api_key", "")),
        vlm_key_set=bool(sget("vlm_api_key", "")),
        probes=probes,
        llm_now=llm_config.get_llm(),
        vlm_now=llm_config.get_vlm(),
    )


# ── v0.6.2 診次歷史 ──────────────────────────────────
@app.route("/history")
def history_page():
    """列出所有有選定方證的真實診次 (新→舊), 點入看該診次的觀察紀錄"""
    from session_store import list_sessions
    import datetime as _dt
    sessions = []
    for row in list_sessions():
        d = row["data"]
        lp = d.get("last_prescription") or {}
        if not lp.get("name"):
            continue
        sessions.append({
            "sid": row["sid"][:8],
            "date": _dt.datetime.fromtimestamp(row["updated_at"]).strftime("%Y-%m-%d %H:%M"),
            "chief": (d.get("bagang", {}) or {}).get("chief_complaint", "") or "（未填主訴）",
            "formula": lp.get("name", "?"),
            "match": lp.get("match", 0),
            "meridian": next(iter((d.get("differential", {}) or {}).keys()), ""),
            "med_logs": len(d.get("medication_log", []) or []),
            "is_current": row["sid"] == _s()._sid,
        })
    return render_template("history.html", sessions=sessions)


@app.route("/healthz")
def healthz():
    return {"status": "ok", "service": "shanghanlun-webui", "version": APP_VERSION}


# ── 啟動 ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    port = int(os.environ.get("PORT", 8501))
    host = "0.0.0.0"
    print(f"🌿 傷寒論助手 WebUI v{APP_VERSION} 啟動 http://{host}:{port}/")
    app.run(host=host, port=port, debug=True, use_reloader=False)
