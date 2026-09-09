"""模型抽象基类与统一数据结构。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatRequest:
    model: str
    messages: list[ChatMessage]
    tools: list[dict[str, Any]] = field(default_factory=list)
    temperature: float = 0.2
    max_tokens: int = 4096
    stream: bool = True
    stop: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


@dataclass
class StreamEvent:
    """模型流式输出的统一事件。"""

    type: str  # "delta" | "tool_call" | "finish" | "error"
    delta: str = ""
    tool_call: ToolCall | None = None
    finish_reason: str = ""
    usage: dict[str, int] | None = None
    error: str | None = None


class ModelAdapter(ABC):
    """统一的模型适配器接口。"""

    provider_id: str
    kind: str  # "openai" / "anthropic"

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """非流式调用。"""

    @abstractmethod
    def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        """流式调用。"""

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Embedding 批量生成。"""