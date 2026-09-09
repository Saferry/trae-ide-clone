"""工具抽象与注册中心。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolContext:
    """工具执行上下文：工作区、用户、配额、回调。"""

    workspace: str = ""
    user_id: str = ""
    api_key_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """工具返回结构（与 LLM tool message 对齐）。"""

    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """工具抽象类。"""

    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        """执行工具。"""

    def to_openai_tool(self) -> dict[str, Any]:
        """导出为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


class ToolRegistry:
    """工具注册中心。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def openai_tools(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        items = self._tools.values()
        if names:
            items = [t for t in items if t.name in names]
        return [t.to_openai_tool() for t in items]

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(content=json.dumps({"error": f"Unknown tool: {name}"}), is_error=True)
        try:
            return await tool.execute(args, ctx)
        except Exception as e:  # noqa: BLE001
            return ToolResult(content=json.dumps({"error": str(e), "type": type(e).__name__}), is_error=True)


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin(_registry)
    return _registry


def _register_builtin(reg: ToolRegistry) -> None:
    # 这里避免循环导入
    from .file_tools import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
    from .bash_tool import BashTool
    from .search_tool import GrepTool, GlobTool
    from .codebase_tool import CodebaseQueryTool, IndexBuildTool
    from .web_tool import WebFetchTool
    from .delegate_tool import DelegateTool

    for tool in [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        ListDirTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        CodebaseQueryTool(),
        IndexBuildTool(),
        WebFetchTool(),
        DelegateTool(),
    ]:
        reg.register(tool)