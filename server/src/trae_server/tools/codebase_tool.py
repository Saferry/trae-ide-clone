"""代码库语义检索工具（基于 index 模块）。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .base import RiskLevel, Tool, ToolContext, ToolResult

if TYPE_CHECKING:
    from ..index.store import CodeIndexStore


class CodebaseQueryTool(Tool):
    name = "codebase_query"
    description = "在工作区代码库上做语义检索（基于向量索引）。参数：query、top_k（默认 8）。"
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 8},
            "path_filter": {"type": "string"},
        },
        "required": ["query"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        from ..index.store import CodeIndexStore

        store: CodeIndexStore = CodeIndexStore.for_workspace(ctx.workspace)
        await store.ensure_ready()
        hits = await store.query(args.get("query") or "", top_k=int(args.get("top_k") or 8))
        results = []
        for h in hits:
            results.append(
                {
                    "path": h["path"],
                    "score": h["score"],
                    "snippet": h["snippet"],
                }
            )
        return ToolResult(content=json.dumps(results, ensure_ascii=False, indent=2))


class IndexBuildTool(Tool):
    name = "index_build"
    description = "构建 / 重建工作区代码库索引（首次或大批量变更后调用）。参数：full（默认 false）。"
    risk_level = RiskLevel.MEDIUM
    parameters = {"type": "object", "properties": {"full": {"type": "boolean", "default": False}}}

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        from ..index.builder import IndexBuilder

        builder = IndexBuilder(workspace=ctx.workspace)
        full = bool(args.get("full"))
        stats = await builder.build(full=full)
        return ToolResult(content=json.dumps(stats), metadata=stats)