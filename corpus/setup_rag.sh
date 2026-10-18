#!/bin/bash
# 七典 RAG 語料一鍵建置 — clone 古籍庫 → 切塊繁化 → embedding → rag_vectors.npy
# 需求: 本機 llama.cpp embeddings server (:8082 jina) 或改 build_rag.py 的 EMBED_URL
set -e
cd "$(dirname "$0")"
[ -d tcm-ancient-books ] || git clone --depth 1 https://github.com/xiaopangxia/TCM-Ancient-Books.git tcm-ancient-books
python3 build_rag.py --rebuild-vectors
echo "完成。重啟 webui 後, 推論頁「典籍出處」與 Library「七典跨典檢索」自動出現。"
