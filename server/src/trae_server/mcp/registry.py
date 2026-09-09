"""MCP 与 Tool 的桥接：把 MCP server 暴露的 tools 注册到 ToolRegistry。

独立于 client.py 存在以避免循环导入；首版启动时调用 install_mcp_tools()。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import get_config
from ..mcp.client import MCPRegistry, get_mcp_registry
from ..tools.base import RiskLevel, Tool, ToolContext, ToolResult

if TYPE_CHECKING:
    pass


class MCPToolAdapter(Tool):
    """把 MCP server 的单个 tool 包成 ToolRegistry 内的 Tool。"""

    def __init__(self, server_name: str, mcp_name: str, description: str, input_schema: dict) -> None:
        self.name = f"mcp.{server_name}.{mcp_name}"
        self.description = description
        self.risk_level = RiskLevel.MEDIUM
        self.parameters = input_schema
        self._server_name = server_name
        self._mcp_name = mcp_name

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        reg = get_mcp_registry()
        try:
            result = await reg.call_tool(self._server_name, self._mcp_name, args)
        except Exception as e:  # noqa: BLE001
            return ToolResult(content=f"error: mcp tool call failed: {e}", is_error=True)
        # MCP 返回格式：{content: [{type, text}], isError?}
        content_items = result.get("content", []) if isinstance(result, dict) else []
        text_parts: list[str] = []
        for c in content_items:
            if isinstance(c, dict) and c.get("type") == "text":
                text_parts.append(c.get("text", ""))
        text = "\n".join(text_parts) or json_dumps(result)
        return ToolResult(
            content=text,
            is_error=bool(result.get("isError")) if isinstance(result, dict) else False,
            metadata={"mcp_server": self._server_name, "mcp_tool": self._mcp_name},
        )


def json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)


async def install_mcp_tools(registry) -> int:
    """从配置中读取 MCP server，连接后把工具注册到 ToolRegistry。

    返回注册的 MCP 工具数量。
    """
    cfg = get_config()
    if not cfg.mcp.enabled:
        return 0
    mcp_reg = get_mcp_registry()
    registered = 0
    for s in cfg.mcp.servers:
        if not s.enabled:
            continue
        mcp_reg.add_server(
            name=s.name,
            transport=s.transport,
            command=s.command,
            args=s.args,
            url=s.url,
            enabled=s.enabled,
        )
    tools = await mcp_reg.list_tools()
    for t in tools:
        adapter = MCPToolAdapter(
            server_name=t.server,
            mcp_name=t.name,
            description=t.description,
            input_schema=t.input_schema,
        )
        if registry.get(adapter.name) is None:
            registry.register(adapter)
            registered += 1
    return registered