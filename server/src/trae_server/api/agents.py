"""智能体 REST 端点。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..agents.main_agent import AgentContext, MainAgent
from ..agents.runner import AgentRunner
from ..auth.keys import APIKeyContext, authenticate_api_key
from ..config import get_config
from ..models.base import ChatMessage
from ..rules.loader import load_rules
from ..tools.base import get_registry

agent_router = APIRouter(prefix="/v1/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    session_id: str | None = None
    workspace: str | None = None
    task: str
    model: str | None = None
    provider_id: str | None = None
    refs: list[str] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    answer: str
    iterations: int = 0
    tokens: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


@agent_router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    ctx: APIKeyContext = Depends(authenticate_api_key),
) -> AgentRunResponse:
    cfg = get_config()

    workspace = req.workspace or ""
    rules = load_rules(workspace)
    provider_id = req.provider_id
    model = req.model or ""
    if not model and cfg.models.providers:
        p0 = next((p for p in cfg.models.providers if p.enabled), None)
        if p0:
            model = p0.default_model
            provider_id = provider_id or p0.id

    if not model:
        raise HTTPException(status_code=503, detail="no model configured")

    agent_ctx = AgentContext(
        session_id=req.session_id or "adhoc",
        workspace=workspace,
        user_id=ctx.user_id,
        api_key_name=ctx.name,
        rules=rules.as_system_prompt(),
        refs=req.refs,
        confirm_required=False,
    )
    runner = AgentRunner(model=model, provider_id=provider_id)
    main = MainAgent(runner)
    result = await main.run(agent_ctx, req.task)
    return AgentRunResponse(
        answer=result["answer"],
        iterations=result["iterations"],
        tokens=result["tokens"],
        tool_calls=result["tool_calls"],
    )