"""子智能体：独立上下文，独立 runner。"""

from __future__ import annotations

from typing import Any

from ..models.router import get_router
from ..rules.loader import SubagentSpec
from ..tools.base import get_registry
from .runner import AgentRunner, AgentRunResult


async def run_subagent(
    spec: SubagentSpec,
    task: str,
    context: str = "",
    workspace: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    """运行子智能体并返回结果摘要。"""
    from ..agents.main_agent import AgentContext

    reg = get_registry()
    tools = reg
    if spec.tools:
        # 限制子智能体可用工具
        names = set(spec.tools)
        from ..tools.base import ToolRegistry

        scoped = ToolRegistry()
        for n in reg.list_tools():
            t = reg.get(n)
            if t and n in names:
                scoped.register(t)
        tools = scoped

    # 选模型
    provider_id = None
    model = spec.model
    if "/" in model:
        provider_id, model = model.split("/", 1)

    runner = AgentRunner(
        model=model,
        provider_id=provider_id,
        system_prompt=spec.body,
    )
    ctx = AgentContext(
        session_id=f"sub:{spec.name}:{user_id}",
        workspace=workspace,
        user_id=user_id,
        rules=context,
        confirm_required=False,
        metadata={"subagent": spec.name},
    )
    from ..models.base import ChatMessage

    history: list[ChatMessage] = [ChatMessage(role="user", content=task)]

    result: AgentRunResult = await runner.run(ctx, history, tools)
    return {
        "answer": result.answer,
        "iterations": result.iterations,
        "tokens": result.tokens,
        "tool_calls": [tc.__dict__ for tc in result.tool_calls],
    }