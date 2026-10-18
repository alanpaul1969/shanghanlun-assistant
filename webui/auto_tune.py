"""v0.2.1 auto_tune - 自動推導症狀→經權重

從 formula_to_meridian.json 23 候選方證的 source_text 抽症狀 mention,
用 source_ref 條文位置 + typical_categories 算出"這個方證的"症狀 profile",
然後反推每個症狀 → 6 經權重矩陣。

策略 (v0.2.1 simple, 為日後 LLM 增強鋪路):
1. 條文文字分析: 從 source_text 抓所有與現有症狀 keyword 相符的
2. 條文屬經: source_ref 看條文號, 已知條文對應經 (13/14 太陽中風、26 陽明、96 少陽、277 太陰、323 少陰、338 厥陰)
3. 每個方證的條文=其主經 = highest weight
4. 條文 mention 到的症狀 = 該經特異性高 (weight 1.0)
5. typical_categories 給的症狀 = 該經中度 (weight 0.7-0.8)
6. 不在條文/typical 的症狀 = 0 weight (該方證不需要)

輸出: 跟 symptom_to_meridian.json 同 schema 的 update JSON
"""
import json
import re
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent

# 載入現有資料
_SYMPTOM = json.loads((DATA_DIR / "symptom_to_meridian.json").read_text())
_FORMULA = json.loads((DATA_DIR / "formula_to_meridian.json").read_text())
SYMPTOMS = _SYMPTOM["symptoms"]
FORMULAS = _FORMULA["formulas"]

MERIDIANS = ["太陽", "陽明", "少陽", "太陰", "少陰", "厥陰"]

# 條文 → 經 (簡化版, 從 source_ref 條文號 + 我們已知的 13/14 太陽 / 26 陽明 / 96 少陽 / 277 太陰 / 323 少陰 / 338 厥陰 推導)
KNOWN_PASSAGE_TO_MERIDIAN = {
    "13":  "太陽", "14":  "太陽", "18":  "太陽", "35":  "太陽", "71":  "太陽",
    "26":  "陽明", "208": "陽明", "209": "陽明", "219": "陽明", "248": "陽明",
    "96":  "少陽", "103": "少陽", "146": "少陽",
    "102": "太陰", "277": "太陰", "279": "太陰",
    "301": "少陰", "303": "少陰", "316": "少陰", "323": "少陰",
    "338": "厥陰", "351": "厥陰", "371": "厥陰",
}

# 症狀 keyword 對應表 (條文文字 → symptom_id)
KEYWORD_TO_SYMPTOM = {
    # 寒熱
    "發熱": "寒熱/發熱_微熱_惡風",  # default, 細分看 keyword
    "微熱": "寒熱/發熱_微熱_惡風",
    "高燒": "寒熱/發熱_高燒_不惡寒",
    "不惡寒": "寒熱/發熱_高燒_不惡寒",
    "往來寒熱": "寒熱/往來寒熱",
    "惡寒": "寒熱/惡寒_無熱",
    "無熱": "寒熱/惡寒_無熱",
    "厥冷": "寒熱/四肢厥冷",
    "四肢厥冷": "寒熱/四肢厥冷",
    "脈沉": "寒熱/惡寒_無熱",  # 少陰常見
    "上熱下寒": "寒熱/寒熱錯雜_上熱下寒",
    "寒熱錯雜": "寒熱/寒熱錯雜_上熱下寒",
    "翕翕發熱": "寒熱/發熱_微熱_惡風",
    "嗇嗇": "寒熱/發熱_微熱_惡風",
    # 汗
    "汗出": "汗出/微汗",
    "微汗": "汗出/微汗",
    "自汗": "汗出/自汗",
    "無汗": "汗出/無汗",
    "大汗": "汗出/大汗不止",
    "大汗出": "汗出/大汗不止",
    "手足濈然汗出": "汗出/手足濈然汗出",
    # 頭
    "頭痛": "頭身/頭痛_整頭",
    "項背": "頭身/項背強",
    "項背強": "頭身/項背強",
    "几几": "頭身/項背強",
    "頭暈": "頭身/頭暈",
    "身重": "頭身/身重",
    # 食
    "口渴": "飲食/口渴_微渴",
    "微渴": "飲食/口渴_微渴",
    "大渴": "飲食/口渴_大渴欲冷飲",
    "大煩渴": "飲食/口渴_大渴欲冷飲",
    "消渴": "飲食/消渴_嚴重口渴",
    "飢不欲食": "飲食/飢不欲食",
    "默默不欲食": "飲食/食不下_默默不欲食",
    "不欲食": "飲食/食不下_默默不欲食",
    # 便
    "便秘": "二便/便秘",
    "不大便": "二便/便秘",
    "燥屎": "二便/便秘",
    "自利": "二便/腹瀉_自利",
    "下利": "二便/腹瀉_自利",
    "下利清穀": "二便/腹瀉_下利清穀",
    "小便不利": None,  # 留個信號 — 五苓散特有
    "小便清": "二便/小便清長",
    "小便短": "二便/小便短赤",
    # 胸腹
    "胸脇苦滿": "胸腹/胸脇苦滿",
    "心下痞": "胸腹/心下痞",
    "腹滿": "胸腹/腹滿時痛",
    "腹脹": "胸腹/腹脹_不痛",
    "氣上撞心": "胸腹/氣上撞心",
    # 精神
    "譫語": "精神情緒/譫語_神智不清",
    "但欲寐": "精神情緒/但欲寐_嗜睡",
    "精神萎靡": "精神情緒/精神萎靡",
    "口苦": "精神情緒/口苦",
    "煩躁": "精神情緒/煩躁_易怒",
    "心煩": "精神情緒/煩躁_易怒",
    "不得臥": "精神情緒/但欲寐_嗜睡",  # 黃連阿膠
    "心煩喜嘔": "噁心嘔吐/心煩喜嘔",
    "心煩不得臥": "精神情緒/但欲寐_嗜睡",
    # 嘔
    "嘔": "噁心嘔吐/乾嘔",
    "乾嘔": "噁心嘔吐/乾嘔",
    "嘔不止": "噁心嘔吐/嘔不止",
    "吐蛔": "胸腹/氣上撞心",
    "嘔吐": "噁心嘔吐/嘔不止",
    # 脈
    "脈浮": "脈/脈浮緩",
    "脈浮緩": "脈/脈浮緩",
    "脈浮緊": "脈/脈浮緊",
    "脈洪大": "脈/脈洪大",
    "脈沉細": "脈/脈沉細",
    "脈微細": "脈/脈沉細",
    "脈弦": "脈/脈弦",
    "脈沉": "寒熱/惡寒_無熱",
}


def extract_passage_id(source_ref):
    """從 '傷寒論 宋本 13 條' 抽 '13' """
    m = re.search(r'(\d+)\s*條', source_ref)
    return m.group(1) if m else None


def extract_symptoms_from_text(text):
    """從條文 text 抽所有符合 symptom 的 keyword 對應 (category, sid)"""
    found = []
    for kw, sym in KEYWORD_TO_SYMPTOM.items():
        if kw in text and sym:
            cat, sid = sym.split("/")
            found.append((cat, sid))
    return list(set(found))  # 去重


def meridian_from_source_ref(source_ref):
    """從 source_ref 找條文號 → 已知條文對應經"""
    pid = extract_passage_id(source_ref)
    if not pid:
        return None
    return KNOWN_PASSAGE_TO_MERIDIAN.get(pid)


def auto_tune_meridian_weights():
    """為每個方證:
    1. 從 source_text 抽條文症狀 mention
    2. 用條文號 = 該方證主經 → 那些症狀給 weight 1.0
    3. typical_categories 的症狀 = 該方證次要 → 給 weight 0.7
    4. 其他方證提到但本方未提 = 給 0.05 (噪聲下界)

    累積: 對每個 (cat, sid) 統計「它在哪些方證是主經症狀」
    """
    # 累加每個 (cat, sid) 在 6 經的「方證提及次數」
    counts = {}  # {(cat, sid): {"太陽": n, "陽明": n, ...}}
    formula_count_by_meridian = {m: 0 for m in MERIDIANS}

    for meridian, formulas in FORMULAS.items():
        formula_count_by_meridian[meridian] = len(formulas)
        for f in formulas:
            text_symptoms = extract_symptoms_from_text(f.get("source_text", ""))
            passage_meridian = meridian_from_source_ref(f.get("source_ref", ""))
            # 如果條文沒對到 known, 跳過
            if passage_meridian and passage_meridian != meridian:
                # 條文跨經 (例: 277 太陰條文講少陰方) — fallback 用方證經
                passage_meridian = meridian
            # 條文提及的症狀 = 主經強信號
            for cat, sid in text_symptoms:
                key = (cat, sid)
                if key not in counts:
                    counts[key] = {m: 0 for m in MERIDIANS}
                if passage_meridian:
                    counts[key][passage_meridian] += 2  # 條文級 — 雙倍加權
                else:
                    counts[key][meridian] += 1
            # typical_categories 給的症狀 = 次要
            for cat in f.get("typical_categories", []):
                # cat 層級 — 所有在該 cat 的 symptom 都算該方證
                for sid in SYMPTOMS.get(cat, {}).keys():
                    key = (cat, sid)
                    if key not in counts:
                        counts[key] = {m: 0 for m in MERIDIANS}
                    counts[key][meridian] += 1

    return counts, formula_count_by_meridian


def compute_meridian_weights(counts, formula_count_by_meridian):
    """從 counts 算每個症狀的 6 經權重 (0-1)
    公式: weight[m] = (counts[(cat,sid)][m] / formula_count_by_meridian[m]) ** 0.5
    sqrt 抑制高頻過度; 再 normalize: weight[m] = weight[m] / max(weight)"""
    new_weights = {}
    for (cat, sid), merid_counts in counts.items():
        # ratio
        ratios = {}
        for m in MERIDIANS:
            n_formulas = formula_count_by_meridian[m] or 1
            ratios[m] = (merid_counts[m] / n_formulas) ** 0.5
        # normalize: max = 1.0
        max_r = max(ratios.values()) if ratios else 0
        if max_r > 0:
            norm = {m: round(r / max_r, 3) for m, r in ratios.items()}
        else:
            norm = {m: 0 for m in MERIDIANS}
        new_weights[(cat, sid)] = norm
    return new_weights


def merge_with_existing(new_weights, existing_symptoms, threshold=0.1):
    """把 new_weights merge 進現有 SYMPTOMS 表 — 保留現有 weight (Alan 改過的優先)
    只在現有缺值時填新值, 或差異 > threshold 時混合。
    """
    merged = json.loads(json.dumps(existing_symptoms))  # deep copy
    added = 0
    updated = 0
    skipped = 0

    for (cat, sid), weights in new_weights.items():
        if cat not in merged:
            merged[cat] = {}
        if sid not in merged[cat]:
            # 新症狀 (auto-tune 從條文抽出、現有表沒收錄)
            merged[cat][sid] = {
                "太陽": weights.get("太陽", 0), "陽明": weights.get("陽明", 0),
                "少陽": weights.get("少陽", 0), "太陰": weights.get("太陰", 0),
                "少陰": weights.get("少陰", 0), "厥陰": weights.get("厥陰", 0),
                "weight": 0.6, "mutex_group": None, "_source": "auto-tune-v0.2.1"
            }
            added += 1
        else:
            # 既有 — 只在差異大時提示
            cur = merged[cat][sid]
            for m in MERIDIANS:
                cur_v = cur.get(m, 0)
                new_v = weights.get(m, 0)
                if abs(cur_v - new_v) > threshold and cur.get("_source") != "auto-tune-v0.2.1":
                    # 不自動覆蓋 (Alan 設定優先), 但記 diff
                    pass
            skipped += 1
    return merged, added, updated, skipped


def diff_weights(new_weights, existing):
    """列印新舊權重 diff 給 Alan review"""
    diffs = []
    for (cat, sid), weights in new_weights.items():
        if cat in existing and sid in existing[cat]:
            cur = existing[cat][sid]
            for m in MERIDIANS:
                cur_v = cur.get(m, 0)
                new_v = weights.get(m, 0)
                if abs(cur_v - new_v) > 0.15:
                    diffs.append((f"{cat}/{sid}", m, cur_v, new_v))
    return diffs


if __name__ == "__main__":
    print("=" * 60)
    print("Auto-tune v0.2.1 — 從 23 候選方證 source_text 自動推導症狀→經權重")
    print("=" * 60)

    counts, formula_count = auto_tune_meridian_weights()
    new_weights = compute_meridian_weights(counts, formula_count)

    print(f"\n發現症狀數: {len(new_weights)}")
    print(f"6 經方證數: {formula_count}")
    print(f"總 counts (cat, sid, meridian) 數: {sum(len(mc) for mc in counts.values())}")

    # Diff vs 現有
    diffs = diff_weights(new_weights, SYMPTOMS)
    print(f"\n權重差異 > 0.15 的 (新 vs 現有): {len(diffs)} 個")
    if diffs:
        print("前 10 個差異:")
        for cat_sid, m, cur_v, new_v in diffs[:10]:
            print(f"  {cat_sid} {m}: 現有 {cur_v} → 建議 {new_v}")

    # Merge
    merged, added, updated, skipped = merge_with_existing(new_weights, SYMPTOMS)
    print(f"\nMerge 結果: +{added} 新症狀, {skipped} 既有不動")

    # 寫檔 (新檔, 不覆蓋原)
    out_path = DATA_DIR / "symptom_to_meridian.auto-tuned.json"
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    print(f"\n寫入 {out_path}")

    # Test 跟現有引擎匹配
    import sys
    sys.path.insert(0, str(DATA_DIR))
    from inference_engine import infer
    test_cases = [
        ("桂枝湯主證", {"寒熱": ["發熱_微熱_惡風"], "汗出": ["微汗"], "頭身": ["頭痛_整頭"], "脈": ["脈浮緩"]}),
        ("少陽", {"寒熱": ["往來寒熱"], "胸腹": ["胸脇苦滿"], "飲食": ["食不下_默默不欲食"], "噁心嘔吐": ["心煩喜嘔"]}),
        ("少陰", {"寒熱": ["四肢厥冷"], "二便": ["腹瀉_下利清穀"], "精神情緒": ["但欲寐_嗜睡"], "脈": ["脈沉細"]}),
    ]
    print("\n=== 用 auto-tuned weights 跑 unit test ===")
    # Test 需要替換 SYMPTOMS 全域, 簡單做法: 暫時 monkey-patch
    import inference_engine
    orig = inference_engine.SYMPTOMS
    inference_engine.SYMPTOMS = merged
    for label, symptoms in test_cases:
        r = infer(symptoms)
        top = r["meridian_inference"][0]
        top_rx = r["prescriptions"][0]["name"] if r["prescriptions"] else "None"
        print(f"  {label}: top={top['name']} {top['pct']}%, Rx={top_rx}")
    inference_engine.SYMPTOMS = orig
