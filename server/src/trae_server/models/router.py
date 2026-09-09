"""模型路由：根据任务选择 provider。"""

from __future__ import annotations

from typing import Any

from ..config import ModelProviderConfig, get_config
from .base import ChatRequest, ModelAdapter, StreamEvent
from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter


class ModelRouter:
    """根据 routing 配置为不同任务选择 provider。"""

    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        self.reload()

    def reload(self) -> None:
        cfg = get_config()
        self._adapters.clear()
        for p in cfg.models.providers:
            if not p.enabled:
                continue
            adapter: ModelAdapter
            if p.kind == "openai":
                adapter = OpenAIAdapter(p.id, p.base_url, p.api_key, p.default_model)
            elif p.kind == "anthropic":
                adapter = AnthropicAdapter(p.id, p.base_url, p.api_key, p.default_model)
            else:
                continue
            self._adapters[p.id] = adapter

    def _resolve(self, task: str, override: str | None = None) -> ModelAdapter:
        cfg = get_config()
        provider_id = override
        if not provider_id:
            routing: dict[str, Any] = {
                "chat": cfg.models.routing.chat,
                "agent": cfg.models.routing.agent,
                "completion": cfg.models.routing.completion,
                "embedding": cfg.models.routing.embedding,
            }
            provider_id = routing.get(task) or ""
        if not provider_id and cfg.models.providers:
            provider_id = next((p.id for p in cfg.models.providers if p.enabled), "")
        if not provider_id or provider_id not in self._adapters:
            raise RuntimeError(f"No model provider available for task={task}")
        return self._adapters[provider_id]

    async def chat(self, req: ChatRequest, task: str = "chat", provider_id: str | None = None) -> Any:
        adapter = self._resolve(task, provider_id)
        return await adapter.chat(req)

    async def stream(self, req: ChatRequest, task: str = "chat", provider_id: str | None = None):
        adapter = self._resolve(task, provider_id)
        async for evt in adapter.stream_chat(req):
            yield evt

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
        provider_id: str | None = None,
    ) -> list[list[float]]:
        adapter = self._resolve("embedding", provider_id)
        return await adapter.embed(texts, model)

    def list_models(self) -> list[dict[str, Any]]:
        cfg = get_config()
        out: list[dict[str, Any]] = []
        for p in cfg.models.providers:
            if p.enabled and p.id in self._adapters:
                out.append(
                    {
                        "id": p.id,
                        "kind": p.kind,
                        "default_model": p.default_model,
                    }
                )
        return out


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router