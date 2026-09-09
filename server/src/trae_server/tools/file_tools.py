"""文件读写与目录工具。"""

from __future__ import annotations

from pathlib import Path

from .base import RiskLevel, Tool, ToolContext, ToolResult


def _resolve_safe(workspace: str, rel: str) -> Path | None:
    """将相对路径解析到工作区，禁止越界。"""
    ws = Path(workspace).resolve()
    target = (ws / rel).resolve() if not Path(rel).is_absolute() else Path(rel).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        return None
    return target


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取工作区内文件的完整内容。参数：path（相对工作区）。"
    risk_level = RiskLevel.LOW
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "相对工作区的文件路径"}},
        "required": ["path"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = args.get("path") or ""
        target = _resolve_safe(ctx.workspace, path)
        if not target:
            return ToolResult(content="error: path outside workspace", is_error=True)
        if not target.exists() or not target.is_file():
            return ToolResult(content=f"error: file not found: {path}", is_error=True)
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = target.read_text(encoding="latin-1", errors="replace")
        return ToolResult(content=content, metadata={"size": len(content), "path": str(target)})


class WriteFileTool(Tool):
    name = "write_file"
    description = "在工作区内创建或覆盖文件。参数：path、content。"
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = args.get("path") or ""
        content = args.get("content") or ""
        target = _resolve_safe(ctx.workspace, path)
        if not target:
            return ToolResult(content="error: path outside workspace", is_error=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(content=f"wrote {len(content)} bytes to {path}", metadata={"path": str(target), "bytes": len(content)})


class EditFileTool(Tool):
    name = "edit_file"
    description = "在工作区内对文件做精确替换。参数：path、old_text、new_text。"
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        },
        "required": ["path", "old_text", "new_text"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = args.get("path") or ""
        old_text = args.get("old_text") or ""
        new_text = args.get("new_text") or ""
        target = _resolve_safe(ctx.workspace, path)
        if not target:
            return ToolResult(content="error: path outside workspace", is_error=True)
        if not target.exists():
            return ToolResult(content=f"error: file not found: {path}", is_error=True)
        content = target.read_text(encoding="utf-8")
        if old_text not in content:
            return ToolResult(content="error: old_text not found", is_error=True)
        new_content = content.replace(old_text, new_text, 1)
        target.write_text(new_content, encoding="utf-8")
        return ToolResult(content=f"edited {path}", metadata={"path": str(target)})


class ListDirTool(Tool):
    name = "list_dir"
    description = "列出工作区子目录内容。参数：path（默认 '.'）。"
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {"path": {"type": "string", "default": "."}}}

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        rel = args.get("path") or "."
        target = _resolve_safe(ctx.workspace, rel)
        if not target:
            return ToolResult(content="error: path outside workspace", is_error=True)
        if not target.exists():
            return ToolResult(content=f"error: dir not found: {rel}", is_error=True)
        items = []
        for p in sorted(target.iterdir()):
            items.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else 0})
        import json

        return ToolResult(content=json.dumps(items, ensure_ascii=False, indent=2))