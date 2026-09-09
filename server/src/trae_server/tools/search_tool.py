"""代码搜索工具（基于 ripgrep / grep）。"""

from __future__ import annotations

import asyncio
import os
import shutil

from .base import RiskLevel, Tool, ToolContext, ToolResult


class GrepTool(Tool):
    name = "grep"
    description = "在工作区内搜索文本模式（基于 ripgrep，回退 grep）。参数：pattern、path（可选）、glob（可选）。"
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "glob": {"type": "string"},
            "max_results": {"type": "integer", "default": 200},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        pattern = args.get("pattern") or ""
        rel = args.get("path") or "."
        glob = args.get("glob") or ""
        max_results = int(args.get("max_results") or 200)

        ws = ctx.workspace or os.getcwd()
        target = os.path.normpath(os.path.join(ws, rel))
        if not target.startswith(os.path.abspath(ws)):
            return ToolResult(content="error: path outside workspace", is_error=True)

        rg = shutil.which("rg")
        if rg:
            cmd = [rg, "--no-heading", "--line-number", "--max-columns", "300", "--max-columns-preview"]
            if glob:
                cmd.extend(["--glob", glob])
            cmd.extend([pattern, target])
        else:
            # grep 兜底（POSIX）
            cmd = ["grep", "-RIn", "--max-count", "50", "-E", pattern, target]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            out = (stdout or b"").decode("utf-8", errors="replace")
            lines = out.splitlines()[:max_results]
            return ToolResult(content="\n".join(lines), metadata={"count": len(lines), "truncated": len(lines) >= max_results})
        except asyncio.TimeoutError:
            return ToolResult(content="error: grep timeout", is_error=True)


class GlobTool(Tool):
    name = "glob"
    description = "在工作区中按通配符列出文件。参数：pattern。"
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        pattern = args.get("pattern") or ""
        ws = ctx.workspace or os.getcwd()
        # 把 pattern 限制在工作区下：若 pattern 是绝对路径则拒绝
        from pathlib import Path

        if Path(pattern).is_absolute():
            return ToolResult(content="error: absolute pattern not allowed", is_error=True)
        base = Path(ws)
        try:
            matches = sorted(str(p.relative_to(base)) for p in base.glob(pattern))
        except Exception as e:  # noqa: BLE001
            return ToolResult(content=f"error: {e}", is_error=True)
        return ToolResult(content="\n".join(matches[:500]), metadata={"count": len(matches)})