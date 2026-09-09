"""MCP（Model Context Protocol）客户端（stdio + sse）。"""

from .registry import MCPRegistry, get_mcp_registry

__all__ = ["MCPRegistry", "get_mcp_registry"]