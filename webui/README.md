# 傷寒論助手 WebUI (Treatise on Cold Injury Assistant)

**版本**：v0.1.0-mvp
**日期**：2026-10-17
**狀態**：Phase 1 MVP 骨架完成（5 個核心頁面 + Library + 8 張 P0 demo PNG）

## 路由

| Route | 對應 v2 spec 場景 | 內容 |
|---|---|---|
| `GET /` | S1 Home / Dashboard | Hero stats + 進行中診次 + 8 P0 PNG grid |
| `GET /intake/inquiry` | S2-5 問診（**核心**） | 7 區分節 + sticky inference sidebar（六經分佈）|
| `GET /intake/{basic,onset,inspection,auscultation,palpation,differential}` | S2-1~4, S2-6, S2-7 | 骨架（其他子畫面 v2.1 補）|
| `GET /inference` | S3 推論儀表板 | 六經 → 候選方證 Top 3 → 條文原文 + Rx table + safety |
| `GET /observe` | S4-1 服藥觀察 | 服藥 SOP + observation timeline + vital signs SVG + 中病即止 callout |
| `GET /observe/modify` | S4-2 加減決策 | 3 branch options + algorithm lens |
| `GET /observe/rescue` | S4-3 救逆模式 | Rescue banner + 條文匹配 + 推薦切換 |
| `GET /library` | S5 Library | 4 條 demo 條文 + 4 版本切換 + 8 P0 PNG grid |
| `GET /img/<filename>` | 靜態 | v1 P0 PNG (8 張) |
| `GET /healthz` | 健康檢查 | `{"status":"ok","version":"0.1.0-mvp"}` |

## 設計系統

依 `02-UI-UX規劃.md §3` 完整移植：
- **Brand**：indigo-600 (#4F46E5)
- **六經色**：太陽橙、陽明紅、少陽黃、太陰綠、少陰藍、厥陰紫
- **Semantic**：success/warning/danger/info
- **字體**：Inter + Noto Sans TC（純黑體，sans-serif）
- **間距**：4-8-12-16-24-32-48-64
- **圓角**：sm 4px / md 8px / lg 12px / xl 16px
- **陰影**：sm / md / lg
- **icon**：CSS 線稿（Lucide 風格、1.5px stroke）

CSS 變數都定義在 `static/css/shanghanlun.css` `:root`。

## 啟動

```bash
cd "/home/alanpaul1969/ai-labs/projects/alaya-love/AutoPKM_Neo_app/Treatise on Cold Injury/webui"
python3 app.py
# 預設 port 8501，可用 PORT=... 環境變數覆蓋
```

## 當前 demo 資料

- 病人：張大明 / 42 / M / 主訴頭痛發熱 3 天
- 推論：太陽 87% 陽明 41% 少陽 22%（v2 spec 桂枝湯候選）
- 候選方證：桂枝湯（推薦）、桂枝加葛根湯、桂枝加厚朴杏子湯
- 觀察：Day 1, SOP 5 步, timeline 6 節點, vital sign chart 體溫 + 頭痛
- Library: 4 條 demo（13/14/24/26 條）

## 下一階段（v2.1）

1. 連接真實資料：v2 規劃「資料源決策」走宋本 + 來蘇集 + 張卿子 + 桂林古本
2. 推論引擎：v2 規劃 §7 演算法技巧 30 種、Differential Evolution / Ablation Study / Decision Tree
3. 即時互動：sticky inference sidebar 連 WebSocket 即時更新六經分佈
4. 多模態：v2 §4 S2-3 望診照片上傳
5. 響應式：mobile + tablet 適配（v2 §5）
6. P0 圖片素材重做：Krea2 跑 icon/P7/P8/P37/P40、SVG 程式生成圖表

## 檔案結構

```
webui/
├── app.py                  # Flask backend (5 routes + 6 sub-routes + 2 static)
├── README.md               # 本檔
├── static/
│   ├── css/
│   │   └── shanghanlun.css  # Design tokens + 5 個頁面樣式
│   └── img/                 # 8 張 P0 PNG (從 v1_qwen-image-2.1_p0/ 來)
│       ├── P1-app-icon.png
│       ├── P2-launch.png
│       ├── P3-og-social.png
│       ├── P7-inference-dashboard.png
│       ├── P8-observation-timeline.png
│       ├── P37-six-meridian-radar.png
│       ├── P40-30-techniques-grid.png
│       └── P70-og-twitter.png
└── templates/
    ├── base.html           # 全站 layout (頂部 nav + footer)
    ├── home.html           # S1 Dashboard
    ├── intake_inquiry.html # S2-5 問診 (核心 + sticky sidebar)
    ├── intake_step.html    # S2-1~4/6/7 通用骨架
    ├── inference.html      # S3 推論儀表板
    ├── observe.html        # S4-1 服藥觀察
    ├── observe_modify.html # S4-2 加減決策
    ├── observe_rescue.html # S4-3 救逆模式
    └── library.html        # S5 Library
```

## 跟 v2 spec 對齊

| v2 規劃 § | 對應本專案 | 狀態 |
|---|---|---|
| §1 為什麼遠離雲端中醫視覺 | (設計哲學) | ✅ 採用 clinical × SaaS |
| §2 新設計哲學 | design tokens + CSS | ✅ |
| §3 Design tokens | `shanghanlun.css` `:root` | ✅ |
| §4 WebUI 全部畫面明細 | 5 個核心頁 + 6 個子頁 | ✅ 骨架 / 部分 |
| §5 Android 響應式 | — | ⏳ v2.1 |
| §6 內容資料源決策 | (v2 規劃 v2.1) | ⏳ v2.1 |
| §7 圖片素材 prompt | `v1_qwen-image-2.1_p0/` 8 張 | ✅ Phase 1 |
| §8 開發 Phase 切分 | 16-24 週 | 📍 Phase 1 進行中 |
| §9 雙向連結 | — | ⏳ v2.1 |
| §10 Alan 行動項目 | 4 項 (色票/字體/MVP 方劑/圖片) | ✅ 完成 |

## 已完成 v2 規劃 §10 Alan 行動項目

- [x] 確認色票 (indigo + 6 經色)
- [x] 確認字體 (Inter + Noto Sans TC)
- [ ] 確認 MVP 方劑（10 個 → 全方劑，v2.1 補規則庫）
- [x] P0 8 張圖片 (qwen-image-2.1 v1 渲染，2/8 對齊)

## Phase 1 不包含

- 真實條文 DB（demo 4 條 hardcode）
- 推論引擎（rule-based / Jev API / local LLM）
- 多模態（照片上傳、舌診）
- 帳號/登入（單人 demo）
- 持久化（session、observation log）
- 行動版（v2 spec §5 響應式）
- 真實 ComfyUI v2 圖片素材（SVG 程式生成 / Krea2 重做 v2）
