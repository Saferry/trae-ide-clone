"""Embedding 接口：默认委托 ModelRouter，复用 OpenAI 兼容协议。"""

from __future__ import annotations

from ..models.router import get_router


async def embed_texts(texts: list[str], model: str | None = None, provider_id: str | None = None) -> list[list[float]]:
    """批量生成 embedding。"""
    router = get_router()
    return await router.embed(texts=texts, model=model, provider_id=provider_id)


def get_default_embedding_model() -> str:
    from ..config import get_config

    cfg = get_config()
    return cfg.indexer.embedding_model