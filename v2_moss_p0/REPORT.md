# 傷寒論 app v2 — MOSS-Image-SFT P0 8 張渲染報告

**渲染時間**：2026-10-18（8 張全程 ~42 分鐘）
**渲染引擎**：MOSS-Image-SFT（OpenMOSS-Team，13.6B：5.1B DiT + 8.4B Qwen3.5 encoder，bf16）
**渲染平台**：Z13 FlowZ13_AMD395 ComfyUI Desktop（經 SSH 通道 18188）
**Steps/CFG/Sampler**：50 / 3 / euler + sgm_uniform + shift 5 + SkipLayerGuidance single_layers 22（MOSS 官方預設）
**文字排版**：P2/P3/P7/P8/P37/P40/P70 使用 MOSS JSON Layout（bbox yxyx abs_centralized）
**Skill**：moss-image-gen（~/.zcode/skills/moss-image-gen/SKILL.md）

## v1 (Qwen-Image-2.1) vs v2 (MOSS-Image-SFT) 對照

| P 編 | 主題 | v1 結果 | v2 結果 | 耗時 |
|------|------|---------|---------|------|
| P1 | App icon | ✅ 有 icon 元素 | ✅✅ 幾乎命中 spec：靛藍十字+方框+ECG 脈搏線、白底 flat | 412s |
| P2 | Launch screen | ❌ 純白 | ✅✅ 十字標誌+「傷寒論助手」+Shanghan Lun Assistant+進度條，還自行補了手機狀態列 | 1679s（直式最慢） |
| P3 | OG social | ❌ 純白 | ✅ 手機 mockup+問診表單+大標「傷寒論助手」+副標全對；小瑕疵：把手機欄位名渲染成奇怪字、副標下多了一行「灰色中小字」（prompt 補充語被當成畫面文字） | ~200s |
| P7 | Inference dashboard | ❌ 沒圖表 | ✅ 六色水平條圖+百分比 100/87/62/45/38/21+脈搏線+愛心；小瑕疵：左側標籤把 prompt 補充語（「六經分布水平條圖」「去飽和的」「萊姆綠」）渲染成文字而非六經名 | ~200s |
| P8 | Observation timeline | ❌ 純白 | ✅ 水平時間軸 6 節點（首點實心）+藥丸/眼睛/水滴圖示+30m/2h 徽章+底部「服藥觀察」；小瑕疵：中段多了「第四個學區描邊」等幻覺文字 | ~171s |
| P37 | 六經雷達 | ❌ 沒雷達 | ✅ 六角雷達+淡藍資料多邊形+軸標籤；小瑕疵：左軸標成「遠達」且太陽重複（7 標籤 6 軸） | 151s |
| P40 | 30 techniques grid | ❌ 純白 | ✅✅ 六欄卡片+編號 01-06+六個標題（方劑結構/劑量配比/症狀狀態/安全邊界/治療順序/時序觀察）全部正確+線稿圖示；小瑕疵：卡內描述小字為幻覺文字 | 201s |
| P70 | OG Twitter card | ✅ 唯二可用 | ✅✅ 靛藍漸層+白卡+「傷寒論臨床決策輔助系統」大標正確+問診/推論/觀察三縮圖+ v1.0·2026；小瑕疵：logo 旁多了「靛藍色」pill（prompt 補充語入畫） | 312s |

**總評：8/8 有實際內容（v1 是 2/8），6 張接近可直接用，2 張（P3/P7）的標籤文字需 prompt 修一版或後製。**
vs v1 的根本差異：MOSS 能渲染可讀中英文文字+照 JSON bbox 排版；圖表（條圖/雷達/時間軸/卡片網格）全部畫出來了。

## 教訓（寫 prompt 時）

1. **Layout items 的 desc 只寫要出現在畫面上的東西**——說明性文字（「去飽和的」「灰色小字」）會被當成畫面內容渲染出來（P3「灰色中小字」、P7 色名標籤、P70「靛藍色」pill 都是這麼來的）。
2. 中文正文渲染正確率高，但**小字/標籤位置容易幻覺**（P8 中段、P40 卡內描述）——重要文字給精確 bbox，雜項文字寧可不提。
3. 直式大圖（1168×2528）1679s，橫式 ~200-400s；固定 seed 可重現。

## 檔案

`v2_moss_p0/P{1,2,3,7,8,37,40,70}_*.png` + 本報告。

## 後續選項

1. P3/P7 各修一版 prompt（desc 去掉說明語、六經名直接寫進標籤 desc）→ ~7 分鐘
2. P37 軸標籤給逐軸 bbox 可修「遠達」
3. 直接採用 6 張 + P3/P7 修版後全部進 webui/static/img/ 輪替

---

## v2b 批次（2026-10-18 第二輪）：3 修版 + 6 張畫面整合插圖

| 檔案 | 內容 | 結果 | 耗時 |
|------|------|------|------|
| P3_og_social（修） | desc 去說明語 | ✅ 副標乾淨了 | 282s |
| P7_inference_dashboard（修） | 六經名逐條 bbox | ✅ 太陽/陽明/少陽/太陰/厥陰 正確（少陰標籤漏一條，條圖 5 條） | 171s |
| P37_six_meridian_radar（修） | 六軸逐軸 bbox | ✅✅ 六個軸標全對，多邊形偏右上都對 | 151s |
| S23_wang_inspection | 望診（舌診特寫+舌質/舌苔/面色標籤） | ✅✅ 構圖專業；小瑕：「灰色中字」meta 語又入畫 | 292s |
| S24_wen_auscultation | 聞診（耳+聲波） | ✅ | 291s |
| S25_wen_inquiry | 問診（手機表單+對話泡） | ✅ | 282s |
| S26_qie_palpation | 切診（三指把脈+寸關尺） | ✅ 構圖好；小瑕：寸關尺標籤文字部分糊 | 292s |
| S3x_bagang_guide | 八綱辨證四象限卡 | ✅✅ 表裡/寒熱/虛實(慮)/陰陽+圖示全到位 | 342s |
| P4_onboarding_panels | 新手引導三面板 | ✅ | 231s |

**S 系列為 spec 缺口新增**：原 §7 只給了四診 icon（P19/P20），無四診八綱教學插圖；本批補齊，對應 WebUI 的 intake_exam（望聞切合頁）、intake_inquiry（問）、quick（八綱）、home onboarding。

---

## v2c 批次（2026-10-18 第三輪）：P2 層 13 張全數完成

| 檔案 | 內容 | 耗時 |
|------|------|------|
| P5_logo_monogram_dark | 深色模式「仲」monogram | 30s |
| P42_patient_hero | 病人症狀標註示意（發熱/咽痛/腹瀉+六經點） | 271s |
| P43_practitioner_portrait | 現代醫師肖像（白袍、非古裝） | 322s |
| P44_clinical_scene | 現代診間（app 在筆電螢幕上） | 392s |
| P45_medicine_preparation | 現代備藥場景（電熱壺+琥珀瓶+app 觀察畫面） | ~300s |
| P46-P49 版本封面 | 宋本/張卿子/來蘇集/桂林古本 Notion 封面風，各 191s | 4×191s |
| P66_temperature_series | 體溫折線 38.5→36.8→37.2（服前~6h） | 241s |
| P67_pain_scale | 疼痛量表 0-10 表情尺 | 191s |
| P68_pulse_monitor | 脈率卡 72bpm+心電波形 | 231s |
| P69_constitution_radar | 體質六軸雷達（氣虛/陽虛/陰虛/痰濕/血瘀/氣鬱） | 141s |

## WebUI 整合紀錄（2026-10-18）

- `intake_exam.html`：望/聞/切三 section 標題列縮圖（點擊展開 220px）
- `intake_inquiry.html`：S25 問診頁首橫幅
- `quick.html`：「什麼是八綱辨證」摺疊說明卡（S3x）
- `home.html`：P4 onboarding 三面板條（CTA 上方）
- `library.html`：P37 六經雷達 hero（右上角）
- `base.html` favicon → MOSS P1_app_icon

## 剩餘庫存與建議做法

- 26 張 24px UI line icon（P11-P36）：**建議 Lucide/Heroicons 直接引 CDN**，MOSS 出 24px 線稿不銳利（spec 同結論）
- P50-P55 空狀態/警示小 icon（64px）：CSS/SVG 內聯即可，不需要生圖
- P71 App Store banner / P72 Email cover：行銷用，需要時再跑
- 教學插畫 P42-P45、版本封面 P46-P49、vital signs P66-69：✅ 本輪完成
- P2 批次 13 張 + WebUI 整合完成

---

## v2d 壓力測試（2026-10-18 第四輪）：MOSS-Image 能耐實測（7 張，stress_test/）

| 測試 | 內容 | 結果 |
|------|------|------|
| T1 單一線稿 icon 512 | 寒熱溫度計（Lucide 風） | ✅✅ 驚豔——線稿銳利、teal/orange 色點全對 |
| T2 4-icon 一張表 | 寒熱/汗/頭痛/飲食 2×2 | ✅✅ 四個 icon 全部正確，風格統一 |
| T3 64px 警示 icon（256 畫布） | 紅色八邊形禁忌 | ✅ 幾何完美 |
| T4 spinner 208 | 4-dash 轉圈靜態幀 | ⚠️ 形狀對但 dash 數不對；動畫幀本來就該 CSS 做 |
| T5 空狀態 400 | 剪貼板空狀態 | ✅ |
| T6 App Store banner 1920 | 中英混排大標+手機 mockup+商店按鈕 | ⚠️ 版面/手機 mockup/App Store·Google Play 按鈕（含真實 logo）驚豔；但**中英混排標題 garbled**＋我的 meta 語（「混合中英文大字」）被渲染成文字 |
| T7 Email cover | 「四診整合上線」 | ✅✅ 幾乎完美，app 截圖 mockup + 雲紋背景都漂亮；「中字」meta 語又入畫 |

## 能耐結論（修正先前判斷）

1. **24px 線稿 icon 可以用 MOSS 做**——之前「不銳利」的判斷錯了：512 畫布生成再縮小，Lucide 風格立得住、多 icon 表格風格統一。26 張症狀 icon 可批量生成（512 單張 ~1.5 分鐘，或 4-up 表裁切）。
2. **行銷 banner 可行**，但 prompt 鐵律：desc 只寫畫面內容；**一個 desc 內不要中英混排長句**（會 garble），中英分開兩個 item。
3. spinner/動畫幀 → CSS（本來就不是生圖的活）。
4. 50 步大圖（1920 寬）~17 分鐘；小圖 30-90 秒。

---

## v2e 批次（2026-10-18 第五輪）：25 張 UI 線稿 icon 全數生成 + 整合

- `icons/`（P5_… 除 P34 spinner 全套）：512px MOSS 生成，97s/張，風格統一 Lucide-like
- 抽檢 8 張全數 spec 命中（P11 溫度計+teal/orange、P15 水滴+波紋、P19 開口紅舌、P23 靛藍卷軸、P26 加減雙圈 indigo/amber、P29 clipboard+check、P31 紅三角、P36 放大鏡）
- **WebUI 整合 10 處**：inquiry 九分類標題動態掛 icon、exam 望/聞/切卡題（換掉 emoji）、basic 起病卡、inference 候選方證標題+三版本/加減 toggle 按鈕、observe 標題+救逆提示
- 至此 spec §7.3 的 26 張 icon：25 張 MOSS 完成、P34 spinner 留 CSS
