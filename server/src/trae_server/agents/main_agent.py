"""主智能体：负责对话、规划、调度、委派。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models.base import ChatMessage


@dataclass
class PlanStep:
    tool: str
    args: dict[str, Any]
    description: str = ""
    risk: str = "low"


@dataclass
class Plan:
    summary: str
    steps: list[PlanStep] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"## 计划：{self.summary}", ""]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"{i}. **{s.tool}** — {s.description or s.tool}")
            lines.append(f"   - risk: `{s.risk}`")
            if s.args:
                lines.append(f"   - args: `{s.args}`")
        return "\n".join(lines)


@dataclass
class AgentContext:
    """单次 run 的运行时上下文。"""

    session_id: str
    workspace: str
    user_id: str = ""
    api_key_name: str = ""
    history: list[ChatMessage] = field(default_factory=list)
    system_prompt: str = ""
    rules: str = ""
    refs: list[str] = field(default_factory=list)
    plan: Plan | None = None
    confirm_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class MainAgent:
    """主智能体——负责任务接收、规划确认、调度工具/子智能体。"""

    def __init__(self, runner) -> None:
        self.runner = runner

    async def run(self, ctx: AgentContext, user_message: str, on_event=None) -> dict[str, Any]:
        """执行一轮用户请求，返回汇总 dict。

        on_event: 可选回调，用于把流式事件广播给 WS 客户端。
        """
        from ..tools.base import get_registry
        from ..tools.delegate_tool import DelegateTool

        ctx.history.append(ChatMessage(role="user", content=user_message))
        result = await self.runner.run(
            ctx=ctx,
            history=ctx.history,
            tools=get_registry(),
            on_event=on_event,
        )
        ctx.history.append(ChatMessage(role="assistant", content=result.answer))
        return {
            "answer": result.answer,
            "iterations": result.iterations,
            "tokens": result.tokens,
            "tool_calls": [tc.__dict__ for tc in result.tool_calls],
        }