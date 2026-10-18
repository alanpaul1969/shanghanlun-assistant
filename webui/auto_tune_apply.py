"""v0.2.1 auto_tune_apply - 把 auto_tune 結果智慧混合到現有權重表

策略:
1. 對每個 (cat, sid) 算出 auto-tune 排名 top1 經
2. 對比現有表的排名 top1
3. 如果一致: 拉高現有 top1 經的權重 (接近 1.0)
4. 如果不一致: 保留現有設定, 印 warning
5. 對「主經 vs 其他經」的比例 enforce 4:1 (主經 0.8-1.0, 其他 0.0-0.2)

輸入: 現有 symptom_to_meridian.json + auto_tune 輸出
輸出: 新 symptom_to_meridian.json (寫入 .v0.2.1.json 備份)
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent
sys.path.insert(0, str(DATA_DIR))

from auto_tune import (
    auto_tune_meridian_weights, compute_meridian_weights,
    KNOWN_PASSAGE_TO_MERIDIAN, MERIDIANS
)


def smart_merge(existing, new_weights, ratio_enforce=4.0):
    """智慧合併:
    1. 如果 auto_tune top1 經 == 現有 top1 經, 把現有 top1 拉到 0.95+
    2. 如果不一致, 保留現有 top1, 把 auto_tune top1 設到 0.5, 其他降
    3. 主經:其他經 = ratio_enforce:1
    """
    result = json.loads(json.dumps(existing))  # deep copy
    changes = []
    for (cat, sid), weights in new_weights.items():
        if cat not in result:
            result[cat] = {}
        if sid not in result[cat]:
            continue  # 跳過新症狀 (v0.2.1 範圍只改既有)

        cur = result[cat][sid]
        # 找現有 top1
        cur_top = max(MERIDIANS, key=lambda m: cur.get(m, 0))
        cur_top_v = cur.get(cur_top, 0)
        # 找 auto top1
        new_top = max(MERIDIANS, key=lambda m: weights.get(m, 0))
        new_top_v = weights.get(new_top, 0)

        if cur_top == new_top:
            # 一致 → 把現有 top1 拉到 1.0, 其他按比例降
            updated_weights = {"太陽": 0, "陽明": 0, "少陽": 0, "太陰": 0, "少陰": 0, "厥陰": 0}
            updated_weights[cur_top] = 1.0
            for m in MERIDIANS:
                if m == cur_top:
                    continue
                # 其他經 = (現有權重 / 現有 top1) × 0.2 (噪聲下界)
                if cur_top_v > 0:
                    rel = cur.get(m, 0) / cur_top_v
                    updated_weights[m] = round(rel * 0.2, 2)
                else:
                    updated_weights[m] = 0
            # 更新 + 標記 source
            for m, v in updated_weights.items():
                old_v = cur.get(m, 0)
                cur[m] = v
                if abs(old_v - v) > 0.1:
                    changes.append((f"{cat}/{sid}", m, old_v, v))
            cur["weight"] = cur.get("weight", 1.0)
        else:
            # 不一致 — 印 warning, 保留現有
            changes.append((f"{cat}/{sid}", f"⚠ 現有主經={cur_top} 建議={new_top}", cur_top_v, new_top_v))

    return result, changes


def diff_report(changes):
    print(f"權重變更 (|delta| > 0.1): {len([c for c in changes if isinstance(c[2], (int, float)) and abs(c[2] - c[3]) > 0.1])}")
    print(f"不一致警告 (現有主經 vs auto 建議不同): {len([c for c in changes if '⚠' in c[1]])}")
    print()
    print("前 20 個變更:")
    for item in changes[:20]:
        if isinstance(item[2], (int, float)):
            print(f"  {item[0]} {item[1]}: {item[2]:.2f} → {item[3]:.2f}")
        else:
            print(f"  {item[0]}: {item[1]}")


if __name__ == "__main__":
    print("=" * 60)
    print("auto_tune_apply v0.2.1 — 智慧合併權重")
    print("=" * 60)

    # 載入現有 + 算 auto
    cur = json.loads((DATA_DIR / "symptom_to_meridian.json").read_text())
    cur_symptoms = cur["symptoms"]
    counts, formula_count = auto_tune_meridian_weights()
    new_weights = compute_meridian_weights(counts, formula_count)

    # 智慧合併
    merged, changes = smart_merge(cur_symptoms, new_weights)

    # Test 一致性 (用合併版跑 engine)
    import inference_engine
    orig = inference_engine.SYMPTOMS
    inference_engine.SYMPTOMS = merged

    # 跟原表結果對比
    print("\n=== 合併版 vs 原版 unit test 對比 ===")
    test_cases = [
        ("桂枝湯主證", {"寒熱": ["發熱_微熱_惡風"], "汗出": ["微汗"], "頭身": ["頭痛_整頭"], "脈": ["脈浮緩"]}),
        ("少陽", {"寒熱": ["往來寒熱"], "胸腹": ["胸脇苦滿"], "飲食": ["食不下_默默不欲食"], "噁心嘔吐": ["心煩喜嘔"]}),
        ("少陰", {"寒熱": ["四肢厥冷"], "二便": ["腹瀉_下利清穀"], "精神情緒": ["但欲寐_嗜睡"], "脈": ["脈沉細"]}),
        ("陽明", {"汗出": ["大汗不止"], "飲食": ["口渴_大渴欲冷飲"], "脈": ["脈洪大"], "二便": ["便秘"]}),
    ]
    for label, symptoms in test_cases:
        r_orig = orig and __import__('inference_engine').infer(symptoms) if orig else None
        # 簡單: 直接看 merged 結果
        from inference_engine import infer
        r = infer(symptoms)
        top = r["meridian_inference"][0]
        top_rx = r["prescriptions"][0]["name"] if r["prescriptions"] else "None"
        print(f"  {label}: top={top['name']} {top['pct']}%, Rx={top_rx}")
    inference_engine.SYMPTOMS = orig

    # 印 diff
    print("\n=== 變更摘要 ===")
    diff_report(changes)

    # 寫入備份
    out = cur.copy()
    out["symptoms"] = merged
    out["_meta"]["v0.2.1_auto_tune"] = "從 23 候選方證 source_text 自動推導, 智慧合併保留 Alan 先驗"
    out["_meta"]["v0.2.1_changes_count"] = len([c for c in changes if isinstance(c[2], (int, float)) and abs(c[2] - c[3]) > 0.1])
    out["_meta"]["v0.2.1_warning_count"] = len([c for c in changes if '⚠' in c[1]])

    backup = DATA_DIR / "symptom_to_meridian.v0.2.1.json"
    backup.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n寫入備份 {backup}")
    print(f"  (原表 symptom_to_meridian.json 保持不動, 用此版請改 app.py)")
    print(f"  load path: {backup.name}")
