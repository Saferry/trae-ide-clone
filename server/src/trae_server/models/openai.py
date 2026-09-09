"""OpenAI 兼容协议的模型适配器（OpenAI、DeepSeek、Qwen、vLLM、Ollama 等）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from .base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelAdapter,
    StreamEvent,
    ToolCall,
)


class OpenAIAdapter(ModelAdapter):
    kind = "openai"

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        default_model: str = "",
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._http_client = http_client

    def _get_client(self, timeout: float | None = 120) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            item: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.name:
                item["name"] = m.name
            if m.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ]
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            out.append(item)
        return out

    async def chat(self, req: ChatRequest) -> ChatResponse:
        body: dict[str, Any] = {
            "model": req.model,
            "messages": self._convert_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": False,
        }
        if req.tools:
            body["tools"] = req.tools
        if req.stop:
            body["stop"] = req.stop

        client = self._get_client(timeout=120)
        owns_client = self._http_client is None
        try:
            r = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
            r.raise_for_status()
            data = r.json()
        finally:
            if owns_client:
                await client.aclose()

        choice = data["choices"][0]
        msg = choice["message"]
        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=args))

        return ChatResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            model=data.get("model", req.model),
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        body = {
            "model": req.model,
            "messages": self._convert_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
        if req.tools:
            body["tools"] = req.tools

        client = self._get_client(timeout=None)
        owns_client = self._http_client is None
        try:
            if owns_client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                ) as r:
                    async for evt in self._parse_stream(r):
                        yield evt
            else:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                ) as r:
                    async for evt in self._parse_stream(r):
                        yield evt
        finally:
            if owns_client:
                await client.aclose()

    async def _parse_stream(self, r: httpx.Response) -> AsyncIterator[StreamEvent]:
        r.raise_for_status()
        tool_call_buf: dict[int, dict[str, str]] = {}
        usage: dict[str, int] = {}
        finish_reason = "stop"
        async for line in r.aiter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload == "[DONE]":
                    yield StreamEvent(type="finish", finish_reason=finish_reason, usage=usage)
                    return
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield StreamEvent(type="delta", delta=content)
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        slot = tool_call_buf.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["args"] += fn["arguments"]
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                if chunk.get("usage"):
                    usage = chunk["usage"]

        for slot in tool_call_buf.values():
            try:
                args = json.loads(slot["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            yield StreamEvent(
                type="tool_call",
                tool_call=ToolCall(id=slot["id"], name=slot["name"], arguments=args),
            )
        yield StreamEvent(type="finish", finish_reason=finish_reason, usage=usage)

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        body = {"model": model or self.default_model, "input": texts}
        client = self._get_client(timeout=120)
        owns_client = self._http_client is None
        try:
            r = await client.post(f"{self.base_url}/embeddings", headers=self._headers(), json=body)
            r.raise_for_status()
            data = r.json()
        finally:
            if owns_client:
                await client.aclose()
        return [item["embedding"] for item in data["data"]]