"""Chat REST 端点 + WebSocket 流式端点。"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..agents.main_agent import AgentContext, MainAgent
from ..agents.runner import AgentRunner, StepEvent
from ..auth.keys import APIKeyContext, authenticate_api_key
from ..auth.quota import check_quota, record_token_usage
from ..config import get_config
from ..logging import get_logger
from ..models.base import ChatMessage
from ..rules.loader import load_rules
from ..storage.audit import write_audit
from ..storage.db import get_session
from ..storage.models import Message, Session
from ..tools.base import get_registry

chat_router = APIRouter(prefix="/v1/chat", tags=["chat"])
completion_router = APIRouter(prefix="/v1/completion", tags=["completion"])
log = get_logger("api.chat")


class ChatMessageIn(BaseModel):
    role: str
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    title: str | None = None
    workspace: str | None = None
    model: str | None = None
    provider_id: str | None = None
    messages: list[ChatMessageIn]
    refs: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    iterations: int = 0
    tokens: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


@chat_router.post("", response_model=ChatResponse)
async def post_chat(
    req: ChatRequest,
    ctx: APIKeyContext = Depends(authenticate_api_key),
    db: DbSession = Depends(get_session),
) -> ChatResponse:
    cfg = get_config()

    ok, reason = check_quota(ctx.user_id, ctx.quota)
    if not ok:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"quota: {reason}")

    # 创建 / 获取会话
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    sess = db.get(Session, session_id)
    if sess is None:
        sess = Session(
            id=session_id,
            user_id=ctx.user_id,
            title=req.title or "",
            workspace=req.workspace or "",
            model=req.model or "",
        )
        db.add(sess)
        db.commit()
    else:
        sess.updated_at = __import__("datetime").datetime.utcnow()
        db.commit()

    # 拼装 Agent 上下文
    rules = load_rules(req.workspace or "")
    agent_ctx = AgentContext(
        session_id=session_id,
        workspace=req.workspace or "",
        user_id=ctx.user_id,
        api_key_name=ctx.name,
        history=[ChatMessage(role=m.role, content=m.content, tool_call_id=m.tool_call_id, name=m.name) for m in req.messages],
        rules=rules.as_system_prompt(),
        refs=req.refs,
        confirm_required=cfg.agent.require_plan_confirmation,
    )

    # 选择模型
    model = req.model or ""
    provider_id = req.provider_id
    if not model and cfg.models.providers:
        first = next((p for p in cfg.models.providers if p.enabled), None)
        if first:
            model = first.default_model
            provider_id = provider_id or first.id

    runner = AgentRunner(model=model, provider_id=provider_id)
    main = MainAgent(runner)

    user_message = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    result = await main.run(agent_ctx, user_message)

    # 持久化消息
    for m in req.messages:
        db.add(
            Message(
                session_id=session_id,
                role=m.role,
                content=m.content,
                tool_call_id=m.tool_call_id,
            )
        )
    db.add(
        Message(
            session_id=session_id,
            role="assistant",
            content=result["answer"],
        )
    )
    db.commit()

    # 审计 + 配额
    write_audit(db, user_id=ctx.user_id, action="chat", resource=session_id, payload={"tokens": result["tokens"]})
    record_token_usage(ctx.user_id, result["tokens"], ctx.quota)

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        iterations=result["iterations"],
        tokens=result["tokens"],
        tool_calls=result["tool_calls"],
    )


class CompletionRequest(BaseModel):
    prefix: str
    suffix: str = ""
    language: str = "text"
    max_tokens: int = 200


class CompletionResponse(BaseModel):
    text: str
    model: str = ""


@completion_router.post("", response_model=CompletionResponse)
async def post_completion(
    req: CompletionRequest,
    ctx: APIKeyContext = Depends(authenticate_api_key),
) -> CompletionResponse:
    """简单的行内补全：调用 LLM 给出一个续写。"""
    from ..models.router import get_router

    cfg = get_config()
    if not cfg.models.providers:
        raise HTTPException(status_code=503, detail="no model provider configured")

    provider = next((p for p in cfg.models.providers if p.enabled), None)
    if not provider:
        raise HTTPException(status_code=503, detail="no enabled provider")
    model = provider.default_model

    router = get_router()
    chat_req = ChatRequest  # noqa: F841
    req_messages = [
        ChatMessage(
            role="system",
            content="You are a code completion engine. Output ONLY the completion text, no explanations.",
        ),
        ChatMessage(
            role="user",
            content=f"```\n{req.prefix}<<<CURSOR>>>\n{req.suffix}\n```\nLanguage: {req.language}\nComplete the code at <<<CURSOR>>>.",
        ),
    ]
    resp = await router.chat(
        type("R", (), {"model": model, "messages": req_messages, "temperature": 0.1, "max_tokens": req.max_tokens, "stream": False})(),
        task="completion",
        provider_id=provider.id,
    )
    return CompletionResponse(text=resp.content, model=resp.content and model or model)


@chat_router.websocket("/ws")
async def ws_chat(ws: WebSocket):
    """WebSocket 流式 Chat。"""
    await ws.accept()
    api_key = ws.headers.get("x-api-key") or ws.query_params.get("api_key") or ""
    cfg = get_config()
    key_entry = next((k for k in cfg.auth.api_keys if k.key == api_key), None)
    if not key_entry:
        await ws.send_json({"type": "error", "content": "invalid api key"})
        await ws.close()
        return
    user_id = f"apikey:{key_entry.name}"

    try:
        while True:
            payload = await ws.receive_json()
            req_data = payload
            session_id = req_data.get("session_id") or f"sess_{uuid.uuid4().hex[:12]}"
            workspace = req_data.get("workspace") or ""
            user_message = req_data.get("message", "")
            refs = req_data.get("refs", [])

            rules = load_rules(workspace)
            agent_ctx = AgentContext(
                session_id=session_id,
                workspace=workspace,
                user_id=user_id,
                rules=rules.as_system_prompt(),
                refs=refs,
            )
            provider_id = req_data.get("provider_id")
            model = req_data.get("model") or ""
            if not model and cfg.models.providers:
                p0 = next((p for p in cfg.models.providers if p.enabled), None)
                if p0:
                    model = p0.default_model
                    provider_id = provider_id or p0.id
            runner = AgentRunner(model=model, provider_id=provider_id)
            main = MainAgent(runner)

            await ws.send_json({"type": "session", "session_id": session_id})

            async def on_event(evt: StepEvent):
                data = {"type": evt.type, "iteration": evt.iteration}
                if evt.type == "text":
                    data["content"] = evt.content
                elif evt.type == "tool_call":
                    data["tool"] = evt.tool_name
                    data["args"] = evt.tool_args
                elif evt.type == "tool_result":
                    data["tool"] = evt.tool_name
                    data["result"] = evt.tool_result
                elif evt.type == "plan":
                    data["plan"] = evt.plan
                elif evt.type == "finish":
                    data["content"] = evt.content
                elif evt.type == "error":
                    data["content"] = evt.content
                await ws.send_json(data)

            await main.run(agent_ctx, user_message, on_event=on_event)
            await ws.send_json({"type": "done", "session_id": session_id})
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001
        log.error("ws_chat error", error=str(e), exc_info=True)
        try:
            await ws.send_json({"type": "error", "content": str(e)})
        except RuntimeError:
            pass