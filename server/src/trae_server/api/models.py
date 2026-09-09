"""/v1/models：列出当前可用的模型与 provider。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.keys import APIKeyContext, authenticate_api_key
from ..models.router import get_router

models_router = APIRouter(prefix="/v1/models", tags=["models"])


@models_router.get("")
async def list_models(ctx: APIKeyContext = Depends(authenticate_api_key)) -> dict:
    router = get_router()
    providers = router.list_models()
    return {"providers": providers}