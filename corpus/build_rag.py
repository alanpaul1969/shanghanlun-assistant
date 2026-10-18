#!/usr/bin/env python3
"""v0.5 — 七典 RAG 語料庫建置

來源: TCM-Ancient-Books (gb18030 txt) →
  1. 解碼 + opencc 簡→繁
  2. 依 <篇名>/條文切塊 (~600 字, 重疊 80)
  3. 8082 jina-embeddings-v5 產生向量 (batch)
  4. 存 rag_chunks.json + rag_vectors.npy (cosine 檢索用)

Usage: python3 build_rag.py [--books ...] [--rebuild-vectors]
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

try:
    from opencc import OpenCC
    _cc = OpenCC("s2t")
except ImportError:
    _cc = None

HERE = Path(__file__).parent
SRC = HERE / "tcm-ancient-books"
OUT_CHUNKS = HERE / "rag_chunks.json"
OUT_VECS = HERE / "rag_vectors.npy"
EMBED_URL = "http://127.0.0.1:8082/v1/embeddings"

BOOKS = {
    "金匱要略": ["499-金匮要略方论.txt", "500-金匮要略心典.txt"],
    "溫病條辨": ["526-温病条辨.txt"],
    "備急千金要方": ["532-备急千金要方.txt"],
    "景岳全書": ["637-景岳全书.txt"],
    "萬病回春": ["647-万病回春.txt"],
    "醫宗金鑑": ["575-医宗金鉴.txt"],
    "醫林改錯": ["204-医林改错.txt"],
}

CHUNK_TARGET = 600
CHUNK_OVERLAP = 80


def to_traditional(s: str) -> str:
    return _cc.convert(s) if _cc else s


def parse_book(path: Path, book: str):
    """切塊: 依 <篇名> 分章, 章內依長度切, 保留 (book, chapter, text)"""
    raw = path.read_bytes().decode("gb18030")
    raw = re.sub(r"\n\s*\n+", "\n", raw)  # 壓空行
    raw = re.sub(r"[ \t]+", " ", raw)

    # <篇名> 分章
    parts = re.split(r"<篇名>([^\n<]*)", raw)
    chapters = []
    if parts[0].strip():
        chapters.append(("序", parts[0]))
    for i in range(1, len(parts) - 1, 2):
        chapters.append((parts[i].strip(), parts[i + 1]))

    chunks = []
    for chap_title, chap_text in chapters:
        # 去 <目錄> 區塊
        chap_text = re.sub(r"<目錄>.*?(?=<篇名>|$)", "", chap_text, flags=re.DOTALL)
        # 依 條/句 邊界合併到 ~CHUNK_TARGET
        sents = re.split(r"(?<=[。；：！？])\s*", chap_text.replace("\n", ""))
        buf = ""
        for s in sents:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) > CHUNK_TARGET and buf:
                chunks.append((book, to_traditional(chap_title), to_traditional(buf.strip())))
                # 重疊: 保留尾段
                tail = buf[-CHUNK_OVERLAP:]
                buf = tail + s
            else:
                buf += s
        if buf.strip():
            chunks.append((book, to_traditional(chap_title), to_traditional(buf.strip())))
    return chunks


def _embed_one(text):
    payload = json.dumps({"input": [text[:900]]}).encode("utf-8")
    req = urllib.request.Request(
        EMBED_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    return resp["data"][0]["embedding"]


def embed(texts, batch=32):
    """8082 jina embeddings, 回 np.ndarray (n, dim); 失敗條回 zero vector"""
    vecs = []
    n_fail = 0
    for i in range(0, len(texts), batch):
        bt = [t[:900] for t in texts[i:i + batch]]
        payload = json.dumps({"input": bt}).encode("utf-8")
        req = urllib.request.Request(
            EMBED_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        vs = None
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            vs = [d["embedding"] for d in resp["data"]]
        except Exception:
            # 拆單條, 壞條 (超長/特殊字元) 補 zero
            vs = []
            for t in bt:
                try:
                    vs.append(_embed_one(t))
                except Exception:
                    n_fail += 1
                    vs.append([0.0] * 768)
        vecs.extend(vs)
        if (i // batch) % 20 == 0:
            print(f"  embedded {i + len(bt)}/{len(texts)} (fail {n_fail})", flush=True)
    arr = np.array(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
    print(f"embed done, failed chunks: {n_fail}")
    return arr


def main():
    rebuild_vecs = "--rebuild-vectors" in sys.argv
    books = BOOKS if "--books" not in sys.argv else sys.argv[sys.argv.index("--books") + 1].split(",")

    if OUT_CHUNKS.exists() and not rebuild_vecs:
        all_chunks = [(c["book"], c["chapter"], c["text"])
                      for c in json.loads(OUT_CHUNKS.read_text())]
        print(f"loaded {len(all_chunks)} chunks from cache")
        vecs = embed([c[2] for c in all_chunks])
        np.save(OUT_VECS, vecs)
        print(f"vectors: {vecs.shape} → {OUT_VECS}")
        return

    all_chunks = []
    for book, files in BOOKS.items():
        if book not in books:
            continue
        for fn in files:
            fp = SRC / fn
            if not fp.exists():
                print(f"SKIP (missing): {fn}")
                continue
            ch = parse_book(fp, book)
            all_chunks.extend(ch)
            print(f"{book} ← {fn}: {len(ch)} chunks")

    print(f"total chunks: {len(all_chunks)}")

    if not OUT_CHUNKS.exists() or rebuild_vecs or not OUT_VECS.exists():
        OUT_CHUNKS.write_text(json.dumps(
            [{"book": b, "chapter": c, "text": t} for b, c, t in all_chunks],
            ensure_ascii=False, indent=0))
        print("chunks saved")
        t0 = time.time()
        vecs = embed([c[2] for c in all_chunks])
        np.save(OUT_VECS, vecs)
        print(f"vectors: {vecs.shape} in {time.time() - t0:.0f}s → {OUT_VECS}")
    else:
        print("chunks + vectors already exist, skip embed (use --rebuild-vectors)")


if __name__ == "__main__":
    main()
