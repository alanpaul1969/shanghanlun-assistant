"""v0.5 — 典籍 RAG 檢索 (七典: 金匱/溫病條辨/千金/景岳/回春/金鑑/醫林改錯)

向量: 8082 jina-embeddings-v5-small, cosine
語料: ../corpus/rag_chunks.json + rag_vectors.npy (9452 chunks)
用於推論頁「典籍出處」面板 + Library 跨典搜尋。
"""
import json
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
CHUNKS_PATH = HERE.parent / "corpus" / "rag_chunks.json"
VECS_PATH = HERE.parent / "corpus" / "rag_vectors.npy"
EMBED_URL = "http://127.0.0.1:8082/v1/embeddings"

_chunks = None
_vecs = None


def _load():
    global _chunks, _vecs
    if _chunks is None:
        if not CHUNKS_PATH.exists() or not VECS_PATH.exists():
            return False
        _chunks = json.loads(CHUNKS_PATH.read_text())
        _vecs = np.load(VECS_PATH)
    return True


def available() -> bool:
    return _load()


def _embed_query(text: str):
    from llm_config import get_embed
    base, model, key = get_embed()
    payload = json.dumps({"input": [text], "model": model}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/v1/embeddings", data=payload,
        headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    v = np.array(resp["data"][0]["embedding"], dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def search(query: str, top_k: int = 5, books: list | None = None):
    """回 [{"book","chapter","text","score"}] top_k; 失敗回 []"""
    if not _load():
        return []
    try:
        qv = _embed_query(query)
    except Exception:
        return []
    vecs = _vecs
    idx_map = None
    if books:
        idx_map = np.array([i for i, c in enumerate(_chunks) if c["book"] in books])
        if len(idx_map) == 0:
            return []
        vecs = _vecs[idx_map]
    scores = vecs @ qv
    k = min(top_k, len(scores))
    top = np.argsort(-scores)[:k]
    out = []
    for ti in top:
        i = int(idx_map[ti]) if idx_map is not None else int(ti)
        c = _chunks[i]
        out.append({"book": c["book"], "chapter": c["chapter"],
                    "text": c["text"], "score": float(scores[ti])})
    return out
