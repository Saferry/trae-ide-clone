"""智能体执行循环：ReAct + 工具调用 + 流式事件。"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field
from typing import Any

from ..config import get_config
from ..models.base import ChatMessage, ChatRequest, ToolCall
from ..models.router import get_router
from ..tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from .main_agent import AgentContext


# LLM 输出中用于调用工具的伪 XML 标签。模型按惯例产出：
# <tool_call name="...">{"arg": "value"}</tool_call>
TOOL_CALL_RE = re.compile(
    r'<tool_call\s+name="(?P<name>[^"]+)"\s*>(?P<args>.*?)</tool_call>',
    re.DOTALL,
)
PLAN_RE = re.compile(r"<plan>(?P<body>.*?)</plan>", re.DOTALL)
FINAL_RE = re.compile(r"<final_answer>(?P<body>.*?)</final_answer>", re.DOTALL)


@dataclass
class StepEvent:
    """智能体执行的一步事件（用于 WebSocket 推送）。"""

    type: str  # "text" | "tool_call" | "tool_result" | "plan" | "finish" | "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    plan: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    iteration: int = 0


@dataclass
class AgentRunResult:
    answer: str
    iterations: int = 0
    tokens: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)


class AgentRunner:
    """通用 ReAct 风格执行器。

    用法：
        runner = AgentRunner(model="gpt-4o-mini", provider="openai-default")
        result = await runner.run(ctx, history, tools, on_event)
    """

    def __init__(self, model: str = "", provider_id: str | None = None, system_prompt: str = "") -> None:
        self.model = model
        self.provider_id = provider_id
        self.system_prompt = system_prompt

    async def run(
        self,
        ctx: AgentContext,
        history: list[ChatMessage],
        tools: ToolRegistry,
        on_event: Callable[[StepEvent], Awaitable[None]] | None = None,
    ) -> AgentRunResult:
        cfg = get_config()
        max_iter = cfg.agent.max_iterations
        tool_schemas = tools.openai_tools()
        router = get_router()

        sys_msg = self._compose_system_prompt(ctx, tools)

        iter_count = 0
        all_tool_calls: list[ToolCall] = []
        total_tokens = 0
        answer_parts: list[str] = []

        for iteration in range(max_iter):
            iter_count = iteration + 1
            messages = [ChatMessage(role="system", content=sys_msg), *history]

            req = ChatRequest(
                model=self.model,
                messages=messages,
                tools=tool_schemas,
                temperature=0.2,
                max_tokens=4096,
                stream=False,
                metadata={"session_id": ctx.session_id, "workspace": ctx.workspace},
            )

            try:
                resp = await router.chat(req, task="agent", provider_id=self.provider_id)
            except Exception as e:  # noqa: BLE001
                if on_event:
                    await on_event(StepEvent(type="error", content=str(e), iteration=iter_count))
                return AgentRunResult(answer=f"error: {e}", iterations=iter_count, tokens=total_tokens)

            total_tokens += int((resp.usage or {}).get("total_tokens", 0))
            content = resp.content or ""

            # 解析工具调用（即使有 content 也优先看 tool_calls）
            tool_calls = list(resp.tool_calls)
            if not tool_calls:
                tool_calls = self._parse_tool_calls_from_text(content)

            # 解析 plan
            plan_match = PLAN_RE.search(content)
            if plan_match and not ctx.plan:
                from .main_agent import Plan

                plan = self._parse_plan(plan_match.group("body"))
                ctx.plan = plan
                if on_event:
                    await on_event(StepEvent(type="plan", plan=plan.to_markdown(), iteration=iter_count))

            # 解析 final_answer
            final_match = FINAL_RE.search(content)
            if final_match and not tool_calls:
                answer_parts.append(final_match.group("body").strip())
                if on_event:
                    await on_event(
                        StepEvent(type="finish", content=final_match.group("body").strip(), iteration=iter_count)
                    )
                break

            # 推文本增量
            if content:
                answer_parts.append(content)
                if on_event:
                    await on_event(StepEvent(type="text", content=content, iteration=iter_count))

            if not tool_calls:
                # 模型未调用工具也没给 final_answer，认为已完成
                break

            # 把 assistant 消息回填
            history.append(
                ChatMessage(
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                )
            )
            all_tool_calls.extend(tool_calls)

            # 执行工具
            tctx = ToolContext(
                workspace=ctx.workspace,
                user_id=ctx.user_id,
                api_key_name=ctx.api_key_name,
                metadata={"session_id": ctx.session_id},
            )
            for tc in tool_calls:
                if on_event:
                    await on_event(
                        StepEvent(
                            type="tool_call",
                            tool_name=tc.name,
                            tool_args=tc.arguments,
                            iteration=iter_count,
                        )
                    )
                result = await tools.execute(tc.name, tc.arguments, tctx)
                history.append(
                    ChatMessage(
                        role="tool",
                        content=result.content,
                        tool_call_id=tc.id,
                    )
                )
                if on_event:
                    await on_event(
                        StepEvent(
                            type="tool_result",
                            tool_name=tc.name,
                            tool_result=result.content,
                            iteration=iter_count,
                        )
                    )

        return AgentRunResult(
            answer="\n\n".join(p for p in answer_parts if p).strip(),
            iterations=iter_count,
            tokens=total_tokens,
            tool_calls=all_tool_calls,
        )

    def _compose_system_prompt(self, ctx: AgentContext, tools: ToolRegistry) -> str:
        parts: list[str] = []
        if self.system_prompt:
            parts.append(self.system_prompt)
        if ctx.rules:
            parts.append(ctx.rules)
        if ctx.refs:
            parts.append("# 用户引用的上下文：\n" + "\n".join(f"- {r}" for r in ctx.refs))
        tool_list = "\n".join(f"- {t.name}: {t.description}" for t in [tools.get(n) for n in tools.list_tools()] if t)
        if tool_list:
            parts.append(
                "# 可用工具\n"
                + tool_list
                + "\n\n调用工具时，使用如下伪 XML 标签：\n"
                '<tool_call name="tool_name">{"arg": "value"}</tool_call>\n'
                "需要给出最终答复时使用：\n<final_answer>你的回答</final_answer>\n"
                "如有多步计划，先输出 <plan>{JSON}</plan>。"
            )
        return "\n\n".join(parts)

    def _parse_tool_calls_from_text(self, text: str) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for i, m in enumerate(TOOL_CALL_RE.finditer(text)):
            name = m.group("name")
            args_raw = m.group("args").strip()
            try:
                args = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=f"call_{i}_{name}", name=name, arguments=args))
        return calls

    def _parse_plan(self, body: str) -> "Plan":
        """Plan body 允许是 JSON 或 Markdown 列表。"""
        from .main_agent import Plan, PlanStep

        try:
            data = json.loads(body)
            steps = [PlanStep(tool=s["tool"], args=s.get("args", {}), risk=s.get("risk", "low")) for s in data.get("steps", [])]
            return Plan(summary=data.get("summary", ""), steps=steps)
        except json.JSONDecodeError:
            return Plan(summary=body.strip()[:200], steps=[])