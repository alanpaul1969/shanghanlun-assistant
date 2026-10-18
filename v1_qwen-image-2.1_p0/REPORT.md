# 傷寒論 app v2 — P0 8 張圖片素材 v1 渲染報告

**渲染時間**：2026-10-17 07:26-07:31 (5 分鐘，0.41.2 環境)
**渲染引擎**：Qwen-Image-2.1 (qwen_image_2.1_int8_convrot + qwen3vl_8b_int8_convrot + qwen_image_2.1_vae_bf16)
**渲染平台**：Z13 ASUS Flow Z13 (AMD AI Bundle 0.41.2, ROCm 7.14, 128GB unified / 115GB VRAM free)
**解析度**：1024×1024（spec 原本 P1=1024² / P2=1170×2532 / P3=P70=1200×630 / P7=P8=1200×750 / P37=600² / P40=1200×800，統一改成 1024²）
**Steps/CFG/Sampler**：25 / 1.0 / euler+simple（Qwen-Image-2.1 SOP 預設）
**Prompt 來源**：02-UI-UX規劃.md §7.1-7.10 P0 v2 spec（重寫成「場景式 app screenshot」語言，移除設計師 spec 細節）

---

## 像素分析（v2 spec 對齊度）

| P 編 | 主題 | white% | indigo% (#4F46E5) | blue family | 結果 |
|------|------|-------:|------------------:|------------:|------|
| **P1** | App icon | 73.0% | 0.58% | **26.50%** | ✅ 有 icon 元素（純 indigo 6%、其他 indigo 系 26%）|
| **P2** | Launch screen | 99.2% | 0% | 0.27% | ❌ 純白 |
| **P3** | OG social preview | 96.8% | 0% | 0.14% | ❌ 純白 |
| **P7** | Inference dashboard | 92.4% | 0% | 0.03% | ❌ 沒圖表 |
| **P8** | Observation timeline | 99.0% | 0.11% | 0.40% | ❌ 純白 |
| **P37** | Six-meridian radar | 90.5% | 0% | 0.21% | ❌ 沒雷達 |
| **P40** | 30 techniques grid | 98.3% | 0.01% | 0.18% | ❌ 純白 |
| **P70** | OG Twitter card | 52.8% | 0% | **28.45%** | ✅ indigo 背景 + 卡片（最高對齊）|

---

## 結論

**v1 失敗**：8 張只有 2 張（P1 + P70）有實際內容，其餘 6 張 90%+ 純白 = Qwen-Image-2.1 對 v2 spec 的「線稿 icon / 圖表 / 文字版面」**完全不對口**。

**Qwen-Image-2.1 強項**（從 P1 + P70 推得）：
- ✅ 場景式 app screenshot（能合成 indigo + 簡單幾何元素）
- ✅ 漸層背景（OG card 類）
- ✅ 大塊純色區域

**Qwen-Image-2.1 弱項**：
- ❌ 文字渲染（logo、wordmark、條文）— 沒產出可讀字
- ❌ 圖表（bar chart / radar / line chart）— 完全沒畫
- ❌ 文字 + 線稿混排版面
- ❌ 抽象 spec → 視覺（如「1.5px stroke on 64px cross」這種設計師語言 diffusion 不會解）

---

## 建議 v2 渲染策略

| 類別 | P 編 | 推薦引擎 | 備註 |
|------|------|---------|------|
| **icon / logo** | P1 | Krea2 Turbo（int8_convrot） | icon 渲染強、8 steps 速度 3× |
| **純場景 / 漸層 OG** | P3 / P70 | Qwen-Image-2.1 保留 | 已驗證能出 indigo 場景 |
| **文字 + 版面** | P2 | Qwen-Image-2.1 文字強化（25 steps ↑，多加「sans-serif」「typographic」關鍵字）| 或 Krea2 |
| **圖表 (bar / line / radar)** | P7 / P8 / P37 / P40 | **SVG 程式生成**（ComfyUI 不是這類工具）| 改用 Python matplotlib + 自訂 color palette，**0 token 渲染** |
| **30 grid (P40)** | P40 | Krea2 + 場景 prompt | 或 SVG grid 程式生成 |

---

## 檔案位置

```
/home/alanpaul1969/ai-labs/projects/alaya-love/AutoPKM_Neo_app/Treatise on Cold Injury/v1_qwen-image-2.1_p0/
├── P0_P1.png    (1024×1024, 695KB)
├── P0_P2.png    (1024×1024, 718KB)
├── P0_P3.png    (1024×1024, 724KB)
├── P0_P7.png    (1024×1024, 827KB)
├── P0_P8.png    (1024×1024, 762KB)
├── P0_P37.png   (1024×1024, 902KB)
├── P0_P40.png   (1024×1024, 771KB)
├── P0_P70.png   (1024×1024, 803KB)
└── REPORT.md    (本檔)
```

---

## 後續選項

1. **重跑 v2**：P7 / P8 / P37 / P40 改用 SVG 程式生成（最快、無 token），P1 / P2 / P3 / P70 改用 Krea2 Turbo
2. **重跑 v2**：保留 qwen-image-2.1 但加強 prompt（「sans-serif typography」「minimal flat infographic」「data visualization」關鍵字）
3. **接受現狀**：用 P1 + P70 兩張先做 v1 demo，其餘等下個 sprint 重跑

建議路 1（速度最快、結果最對 v2 spec）。

---

**渲染者**：ZCode ⚡（DGX session 2026-10-17）
**工具鏈**：
- `ssh -f -N -L 18188:127.0.0.1:8188 alanp@100.73.5.104`（DGX→Z13 tunnel）
- `python3 /tmp/qi21_t2i_workflow.py`（ComfyUI API client）
- Z13 ComfyUI 0.41.2 Qwen-Image-2.1 custom node `TextEncodeQwenImage21`
