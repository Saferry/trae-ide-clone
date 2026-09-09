"""代码库索引构建器：扫描、分块、embedding、入库。"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from ..config import get_config
from .store import CodeIndexStore


DEFAULT_IGNORE = [
    "node_modules/**",
    ".git/**",
    "dist/**",
    "build/**",
    "__pycache__/**",
    ".venv/**",
    "venv/**",
    ".trae/**",
    "*.min.js",
    "*.lock",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar.gz",
]


MAX_CHARS = 4000  # 约 1000 tokens


def _is_ignored(path: str, patterns: list[str]) -> bool:
    rel = path.replace("\\", "/")
    for p in patterns:
        if fnmatch.fnmatch(rel, p.rstrip("/**")) or fnmatch.fnmatch(rel, p):
            return True
    return False


def _walk_files(workspace: Path, ignore: list[str], max_kb: int) -> Iterable[tuple[Path, float]]:
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not _is_ignored(os.path.relpath(os.path.join(root, d), workspace), ignore)]
        for f in files:
            p = Path(root) / f
            rel = str(p.relative_to(workspace))
            if _is_ignored(rel, ignore):
                continue
            try:
                if p.stat().st_size > max_kb * 1024:
                    continue
                yield p, p.stat().st_mtime
            except FileNotFoundError:
                continue


def _chunk_text(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    chunks: list[str] = []
    for i in range(0, len(text), MAX_CHARS):
        chunks.append(text[i : i + MAX_CHARS])
    return chunks


class IndexBuilder:
    def __init__(self, workspace: str | None) -> None:
        self.workspace = Path(workspace) if workspace else None

    async def build(self, full: bool = False) -> dict[str, int]:
        if not self.workspace:
            return {"files": 0, "chunks": 0, "skipped": 0}
        cfg = get_config()
        ignore = cfg.indexer.ignore_patterns or DEFAULT_IGNORE
        max_kb = cfg.indexer.max_file_size_kb

        store = CodeIndexStore.for_workspace(str(self.workspace))
        await store.ensure_ready()

        files = 0
        chunks: list[dict] = []
        skipped = 0
        for path, mtime in _walk_files(self.workspace, ignore, max_kb):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                skipped += 1
                continue
            rel = str(path.relative_to(self.workspace))
            for idx, chunk in enumerate(_chunk_text(text)):
                start_line = sum(len(c) for c in _chunk_text(text[:idx * MAX_CHARS]) if True) // 80 + 1
                end_line = start_line + chunk.count("\n")
                chunks.append(
                    {
                        "path": rel,
                        "start_line": start_line,
                        "end_line": end_line,
                        "text": chunk,
                        "mtime": mtime,
                    }
                )
            files += 1
            if files % 50 == 0:
                # 流式入库，避免内存压力
                await store.upsert_chunks(chunks)
                chunks = []

        if chunks:
            await store.upsert_chunks(chunks)

        return {"files": files, "chunks": files, "skipped": skipped}