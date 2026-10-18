# 傷寒論臨床決策輔助 WebUI (shanghanlun-assistant)

以《傷寒論》六經辨證為骨架的臨床決策支援 WebUI：八綱快診 → 六經定位 → LLM 追問 → 方證推論 → 醫囑選方 → 服藥觀察 → 加減/救逆。

## 功能（v0.5.1）

- **雙診模式**：⚡ 快診（主訴 LLM 抽取 + 八綱 4 題）/ 📋 詳診（望聞問切 8 步）
- **推論引擎**：症狀×六經權重矩陣 + 互斥組 + 鑑別問答 + 病人 modifier（孕/老/小/病史×方證禁忌）+ 救逆標籤
- **LLM 整合**（本地 llama.cpp，全部安全降級）：主訴症狀抽取、依主訴動態追問（含加減項生成題）、方證 rerank、選方後 RAG×LLM 加減項建議、舌診照片 VLM
- **七典 RAG**：金匱要略/溫病條辨/備急千金要方/景岳全書/萬病回春/醫宗金鑑/醫林改錯，9,452 chunks + jina embeddings，推論頁「典籍出處」+ Library 跨典檢索
- **Library**：傷寒論 398 條 × 4 版本對照（宋本/張卿子/來蘇集/桂林古本）全文搜尋
- **UI 素材**：59 張 MOSS-Image-SFT 生成（icon/教學插圖/海報），詳見 `v2_moss_p0/REPORT.md`
- SQLite server-side session（非 cookie）、多語系 zh/en/ja、Flask SubpathMiddleware（Tailscale Funnel `/shanghanlun/`）

## 執行

```bash
cd webui
pip install flask
python3 app.py   # :8501, http://localhost:8501/shanghanlun/
```

LLM 端點（可選，無則規則引擎獨立運作）：llama.cpp :8080（主模型）、:8085 thinking-off proxy、:8082 jina embeddings。
RAG 語料重建：`corpus/build_rag.py`（需先 clone TCM-Ancient-Books，見 script 內說明）。

## RAG 語料（可選）

語料檔（246MB 古籍 clone + embedding 向量）不入 git，由腳本重建：

```bash
pip install -r requirements.txt   # numpy + opencc 一併裝
./corpus/setup_rag.sh             # clone 古籍庫 → 切塊繁化 → embedding
```

不建置也能正常使用——RAG 相關面板自動隱藏，其餘功能不受影響。

### Embedding 後端選擇（本機或雲端）

到 webui 的「⚙ 設定」頁可切換：

- **本機 `:8082`**（預設）：llama.cpp 跑 `jina-embeddings-v5-small-retrieval-Q8_0`，免金鑰、免費
- **Jina AI 雲端**（建議給沒有本機 embedding server 的部署）：
  建議模型 `jina-embeddings-v5-small-retrieval`（與本機同款）。
  **申請方式**：
  1. 到 [jina.ai](https://jina.ai/) → 右上 **Sign up**（Google / GitHub 登入即可，免信用卡）
  2. 到 [jina.ai/api-key](https://jina.ai/api-key) 點 **Create API Key**，複製 `jina_xxxx...`
  3. 貼進「⚙ 設定 → Embedding 後端 → Jina API Key」儲存
  免費額度對建置整個七典語料（約 150 萬 tokens）綽綽有餘。
- **自訂**：任何 OpenAI 相容 `/v1/embeddings` 端點

建置腳本 `corpus/build_rag.py` 會自動讀 webui 設定頁的 embedding 設定，也可用環境變數覆蓋：`EMBED_URL` / `EMBED_MODEL` / `EMBED_KEY`。

## 授權

Apache-2.0（見 LICENSE）。UI 素材由 MOSS-Image-SFT 生成（該模型 Apache-2.0）。
七典文本來源：[TCM-Ancient-Books](https://github.com/xiaopangxia/TCM-Ancient-Books)（古籍公有領域）。
