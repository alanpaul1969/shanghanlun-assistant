"""v0.3.x 多語言 — Jinja context processor + gettext-style 簡易字典
用法: template 內 {{ t('Dashboard') }} → 依 session['lang'] 翻譯
支援: zh (預設繁中) / en / ja
"""
from flask import session, redirect, request, url_for

I18N = {
    "en": {
        "Dashboard": "Dashboard", "問診": "Inquiry", "推論": "Inference",
        "服藥觀察": "Observation", "Library": "Library",
        "傷寒論助手": "Shanghan Lun Assistant",
        "進行中的診次": "Active Sessions", "開始新診": "New Session",
        "病人基本資料": "Patient Info", "起病與主訴": "Onset & Complaint",
        "望診": "Inspection", "聞診": "Auscultation", "切診": "Palpation",
        "鑑別問答": "Differential", "推論儀表板": "Inference Dashboard",
        "服藥觀察 (S4-1)": "Medication Observation",
        "加減決策": "Modification", "救逆模式": "Rescue Mode",
        "候選方證": "Candidate Formulas", "六經定位": "Six-Meridian",
        "條文搜尋": "Passage Search", "體溫": "Temperature", "脈率": "Pulse Rate",
    },
    "ja": {
        "Dashboard": "ダッシュボード", "問診": "問診", "推論": "推論",
        "服藥觀察": "服薬観察", "Library": "ライブラリ",
        "傷寒論助手": "傷寒論アシスタント",
        "進行中的診次": "進行中の診察", "開始新診": "新規診察",
        "病人基本資料": "患者基本情報", "起病與主訴": "発病と主訴",
        "望診": "望診", "聞診": "聞診", "切診": "切診",
        "鑑別問答": "鑑別質問", "推論儀表板": "推論ダッシュボード",
        "服藥觀察 (S4-1)": "服薬観察",
        "加減決策": "加減決定", "救逆模式": "救逆モード",
        "候選方證": "候補処方", "六經定位": "六経定位",
        "條文搜尋": "条文検索", "體溫": "体温", "脈率": "脈拍",
    },
}


def t(text):
    """翻譯函式 (Jinja global) — 依 session['lang'], 無翻譯就回原文"""
    lang = session.get("lang", "zh") if session else "zh"
    if lang == "zh":
        return text
    return I18N.get(lang, {}).get(text, text)


def init_i18n(app):
    """註冊 Jinja global t() + /set-lang route"""
    app.jinja_env.globals["t"] = t

    @app.route("/set-lang/<lang>")
    def set_lang(lang):
        if lang in ("zh", "en", "ja"):
            session["lang"] = lang
        return redirect(request.referrer or url_for("home"))
