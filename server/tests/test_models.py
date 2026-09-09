"""模型适配器单元测试（使用假 endpoint）。"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from trae_server.models.base import ChatMessage, ChatRequest
from trae_server.models.openai import OpenAIAdapter


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


@pytest.mark.asyncio
async def test_openai_chat_returns_content():
    captured: dict[str, Any] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                "model": "fake-model",
            },
        )

    mock_client = httpx.AsyncClient(transport=MockTransport(h))
    adapter = OpenAIAdapter("test", "http://fake/v1", "k", http_client=mock_client)
    req = ChatRequest(model="fake-model", messages=[ChatMessage(role="user", content="hi")])
    resp = await adapter.chat(req)
    await mock_client.aclose()
    assert resp.content == "hello"
    assert resp.usage["total_tokens"] == 7
    assert captured["body"]["model"] == "fake-model"


@pytest.mark.asyncio
async def test_openai_chat_parses_tool_calls():
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "bash", "arguments": '{"command":"ls"}'},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"total_tokens": 3},
                "model": "fake-model",
            },
        )

    mock_client = httpx.AsyncClient(transport=MockTransport(h))
    adapter = OpenAIAdapter("test", "http://fake/v1", "k", http_client=mock_client)
    req = ChatRequest(model="fake-model", messages=[ChatMessage(role="user", content="run ls")])
    resp = await adapter.chat(req)
    await mock_client.aclose()
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "bash"
    assert resp.tool_calls[0].arguments == {"command": "ls"}