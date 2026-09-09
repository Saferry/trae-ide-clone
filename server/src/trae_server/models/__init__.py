"""模型适配层：OpenAI 兼容协议、Anthropic 协议、Router。"""

from .base import ChatMessage, ChatRequest, ChatResponse, ModelAdapter, StreamEvent, ToolCall
from .router import ModelRouter

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ModelAdapter",
    "StreamEvent",
    "ToolCall",
    "ModelRouter",
]