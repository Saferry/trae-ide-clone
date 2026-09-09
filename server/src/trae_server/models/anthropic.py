"""Anthropic 协议适配器（Claude）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelAdapter,
    StreamEvent,
    ToolCall,
)


class AnthropicAdapter(ModelAdapter):
    kind = "anthropic"

    def __init__(self, provider_id: str, base_url: str, api_key: str, default_model: str = "") -> None:
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.api_version = "2023-06-01"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, Any]]]:
        """Anthropic 把 system 单独拆出来。"""
        system_prompt: str | None = None
        converted: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                system_prompt = (system_prompt or "") + (m.content or "") + "\n"
            elif m.role == "assistant":
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                if m.tool_calls:
                    for tc in m.tool_calls:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        )
                converted.append({"role": "assistant", "content": blocks})
            elif m.role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            else:
                converted.append({"role": m.role, "content": m.content})
        return (system_prompt.strip() if system_prompt else None), converted

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in tools:
            if t.get("type") == "function":
                fn = t["function"]
                out.append(
                    {
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
        return out

    async def chat(self, req: ChatRequest) -> ChatResponse:
        system, messages = self._convert_messages(req.messages)
        body: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if system:
            body["system"] = system
        if req.tools:
            body["tools"] = self._convert_tools(req.tools)

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/v1/messages", headers=self._headers(), json=body)
            r.raise_for_status()
            data = r.json()

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(id=block["id"], name=block["name"], arguments=block.get("input") or {})
                )

        return ChatResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "end_turn"),
            usage=data.get("usage", {}),
            model=data.get("model", req.model),
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        system, messages = self._convert_messages(req.messages)
        body: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": True,
        }
        if system:
            body["system"] = system
        if req.tools:
            body["tools"] = self._convert_tools(req.tools)

        tool_call_buf: dict[str, dict[str, Any]] = {}
        finish_reason = "end_turn"
        usage: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=body,
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        evt = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    etype = evt.get("type")
                    if etype == "content_block_start":
                        cb = evt.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            tool_call_buf[cb["id"]] = {"name": cb["name"], "input": ""}
                    elif etype == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield StreamEvent(type="delta", delta=delta.get("text", ""))
                        elif delta.get("type") == "input_json_delta":
                            for tid, slot in tool_call_buf.items():
                                if tid == evt.get("content_block", {}).get("id") or True:
                                    slot["input"] += delta.get("partial_json", "")
                                    break
                    elif etype == "message_delta":
                        if evt.get("delta", {}).get("stop_reason"):
                            finish_reason = evt["delta"]["stop_reason"]
                        if evt.get("usage"):
                            usage.update(evt["usage"])
                    elif etype == "message_stop":
                        for tid, slot in tool_call_buf.items():
                            try:
                                args = json.loads(slot["input"] or "{}")
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamEvent(
                                type="tool_call",
                                tool_call=ToolCall(id=tid, name=slot["name"], arguments=args),
                            )
                        yield StreamEvent(type="finish", finish_reason=finish_reason, usage=usage)
                        return

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        raise NotImplementedError("Anthropic does not provide an embeddings API in this adapter")