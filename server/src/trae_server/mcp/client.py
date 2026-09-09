"""MCP 客户端（stdio / sse 简化版）。

说明：本项目采用精简版 MCP 客户端，遵循 JSON-RPC 2.0 + MCP 协议子集
（initialize / tools/list / tools/call），不依赖官方 SDK 以便快速首版交付。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server: str


@dataclass
class MCPServerState:
    name: str
    transport: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    process: asyncio.subprocess.Process | None = None
    http: httpx.AsyncClient | None = None
    tools: dict[str, MCPTool] = field(default_factory=dict)
    request_id: int = 0
    pending: dict[int, asyncio.Future] = field(default_factory=dict)
    enabled: bool = True
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def next_id(self) -> int:
        self.request_id += 1
        return self.request_id


class MCPStdioClient:
    """stdio MCP server 包装。"""

    def __init__(self, state: MCPServerState) -> None:
        self.state = state

    async def start(self) -> None:
        cmd = self.state.command
        if not cmd:
            raise RuntimeError("stdio server requires command")
        proc = await asyncio.create_subprocess_exec(
            cmd,
            *self.state.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PAGER": "cat"},
        )
        self.state.process = proc
        asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        assert self.state.process
        while True:
            line = await self.state.process.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                fut = self.state.pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.get_loop().call_soon_threadsafe(fut.set_result, msg)

    async def _request(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        rid = self.state.next_id()
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self.state.pending[rid] = fut
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        assert self.state.process and self.state.process.stdin
        self.state.process.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        await self.state.process.stdin.drain()
        return await asyncio.wait_for(fut, timeout=timeout)

    async def initialize(self) -> dict:
        return await self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trae-ide-clone", "version": "0.1.0"},
            },
        )

    async def list_tools(self) -> list[dict]:
        r = await self._request("tools/list")
        return r.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        r = await self._request("tools/call", {"name": name, "arguments": arguments})
        return r.get("result", {})

    async def stop(self) -> None:
        if self.state.process:
            try:
                self.state.process.terminate()
                await asyncio.wait_for(self.state.process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                pass


class MCPSseClient:
    """SSE MCP server 包装（POST + EventSource 简化版）。

    真实 MCP over SSE 需要长连接读取事件；此处使用 HTTP POST + 轮询简单实现，
    首版足以支持大多数本地 / 局域网 SSE MCP server。
    """

    def __init__(self, state: MCPServerState) -> None:
        self.state = state

    async def start(self) -> None:
        self.state.http = httpx.AsyncClient(timeout=30)

    async def _post(self, path: str, payload: dict) -> dict:
        assert self.state.http
        r = await self.state.http.post(self.state.url.rstrip("/") + path, json=payload)
        r.raise_for_status()
        return r.json()

    async def initialize(self) -> dict:
        return await self._post(
            "/initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trae-ide-clone", "version": "0.1.0"},
            },
        )

    async def list_tools(self) -> list[dict]:
        r = await self._post("/tools/list", {})
        return r.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        r = await self._post("/tools/call", {"name": name, "arguments": arguments})
        return r.get("result", {})

    async def stop(self) -> None:
        if self.state.http:
            await self.state.http.aclose()


class MCPRegistry:
    """MCP server 注册表。"""

    def __init__(self) -> None:
        self._states: dict[str, MCPServerState] = {}
        self._clients: dict[str, MCPStdioClient | MCPSseClient] = {}

    def add_server(
        self,
        name: str,
        transport: str,
        command: str = "",
        args: list[str] | None = None,
        url: str = "",
        enabled: bool = True,
    ) -> None:
        state = MCPServerState(
            name=name,
            transport=transport,
            command=command,
            args=list(args or []),
            url=url,
            enabled=enabled,
        )
        self._states[name] = state

    async def connect(self, name: str) -> None:
        s = self._states[name]
        if not s.enabled:
            return
        async with s.lock:
            if name in self._clients:
                return
            if s.transport == "stdio":
                client: MCPStdioClient | MCPSseClient = MCPStdioClient(s)
            elif s.transport == "sse":
                client = MCPSseClient(s)
            else:
                raise ValueError(f"Unsupported MCP transport: {s.transport}")
            await client.start()
            await client.initialize()
            tools = await client.list_tools()
            for t in tools:
                s.tools[t["name"]] = MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema") or {"type": "object", "properties": {}},
                    server=name,
                )
            self._clients[name] = client

    async def list_tools(self) -> list[MCPTool]:
        out: list[MCPTool] = []
        for name in list(self._states.keys()):
            try:
                await self.connect(name)
                out.extend(self._states[name].tools.values())
            except Exception:  # noqa: BLE001
                continue
        return out

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        if server_name not in self._clients:
            await self.connect(server_name)
        client = self._clients[server_name]
        return await client.call_tool(tool_name, arguments)

    async def shutdown(self) -> None:
        for c in self._clients.values():
            try:
                await c.stop()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()


_registry: MCPRegistry | None = None


def get_mcp_registry() -> MCPRegistry:
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry