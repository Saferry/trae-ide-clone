"""基于 ChromaDB 的代码库向量存储。

为了在没有真实 chromadb（首版离线/简化）的环境下也能跑通，提供一个最小可用的 fallback：
- 如果 chromadb 不可用，使用 sqlite + 暴力 cosine 相似度。
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..config import get_config
from .embedder import embed_texts, get_default_embedding_model

try:
    import chromadb  # type: ignore[import-untyped]
    from chromadb.config import Settings  # type: ignore[import-untyped]

    _HAS_CHROMA = True
except ImportError:  # pragma: no cover
    _HAS_CHROMA = False


def _stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return h[:24]


class CodeIndexStore:
    """代码库语义检索存储。

    工作区下有独立 collection / sqlite 文件，互不干扰。
    """

    def __init__(self, storage_path: Path, workspace_hash: str) -> None:
        self.storage_path = storage_path
        self.workspace_hash = workspace_hash
        self._chroma = None
        self._collection = None
        self._sqlite: Path = storage_path / f"index-{workspace_hash}.sqlite"
        self._ready = False

    @classmethod
    def for_workspace(cls, workspace: str) -> "CodeIndexStore":
        cfg = get_config()
        base = Path(cfg.indexer.storage_dir)
        base.mkdir(parents=True, exist_ok=True)
        workspace_hash = hashlib.sha1(workspace.encode("utf-8")).hexdigest()[:16]
        return cls(storage_path=base, workspace_hash=workspace_hash)

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        if _HAS_CHROMA:
            try:
                self._chroma = chromadb.PersistentClient(
                    path=str(self.storage_path),
                    settings=Settings(anonymized_telemetry=False, allow_reset=True),
                )
                self._collection = self._chroma.get_or_create_collection(
                    name=f"ws-{self.workspace_hash}",
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:  # noqa: BLE001
                self._chroma = None
                self._collection = None
        self._init_sqlite()
        self._ready = True

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self._sqlite) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    text TEXT,
                    embedding TEXT,
                    mtime REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")

    async def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """chunks: [{path, start_line, end_line, text, mtime}]，embedding 由本方法生成。"""
        await self.ensure_ready()
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        model = get_default_embedding_model()
        vectors = await embed_texts(texts, model=model)

        if self._collection is not None:
            ids = [_stable_id(c["path"], str(c.get("start_line", 0))) for c in chunks]
            metadatas = [
                {
                    "path": c["path"],
                    "start_line": c.get("start_line", 0),
                    "end_line": c.get("end_line", 0),
                    "workspace": self.workspace_hash,
                }
                for c in chunks
            ]
            self._collection.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metadatas)

        with sqlite3.connect(self._sqlite) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO chunks (id, path, start_line, end_line, text, embedding, mtime)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        _stable_id(c["path"], str(c.get("start_line", 0))),
                        c["path"],
                        c.get("start_line", 0),
                        c.get("end_line", 0),
                        c["text"],
                        json.dumps(vectors[i]),
                        c.get("mtime", 0.0),
                    )
                    for i, c in enumerate(chunks)
                ],
            )

    async def query(self, q: str, top_k: int = 8) -> list[dict[str, Any]]:
        await self.ensure_ready()
        model = get_default_embedding_model()
        qvec = (await embed_texts([q], model=model))[0]

        if self._collection is not None:
            res = self._collection.query(query_embeddings=[qvec], n_results=top_k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            return [
                {
                    "path": m.get("path", ""),
                    "score": 1.0 - d,
                    "snippet": d_doc,
                }
                for d_doc, m, d in zip(docs, metas, dists)
            ]

        # Fallback: SQLite 暴力 cosine
        with sqlite3.connect(self._sqlite) as conn:
            rows = conn.execute("SELECT path, start_line, end_line, text, embedding FROM chunks").fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for path, sl, el, text, emb_json in rows:
            try:
                vec = json.loads(emb_json)
            except json.JSONDecodeError:
                continue
            score = _cosine(qvec, vec)
            scored.append((score, {"path": path, "start_line": sl, "end_line": el, "snippet": text[:1200], "score": score}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]


def _cosine(a: Iterable[float], b: Iterable[float]) -> float:
    a = list(a)
    b = list(b)
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)