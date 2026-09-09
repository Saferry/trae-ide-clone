"""子智能体委派工具。"""

from __future__ import annotations

import json

from .base import RiskLevel, Tool, ToolContext, ToolResult


class DelegateTool(Tool):
    name = "delegate"
    description = "委派一个子智能体执行独立任务（独立上下文）。参数：subagent、task、context（可选）。"
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "subagent": {"type": "string", "description": ".trae/agents/*.md 中声明的 name"},
            "task": {"type": "string"},
            "context": {"type": "string"},
        },
        "required": ["subagent", "task"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        from ..agents.subagent import run_subagent
        from ..rules.loader import load_rules

        spec_name = args.get("subagent") or ""
        task = args.get("task") or ""
        extra_ctx = args.get("context") or ""

        rules = load_rules(ctx.workspace)
        if spec_name not in rules.subagents:
            return ToolResult(
                content=json.dumps(
                    {
                        "error": f"Subagent '{spec_name}' not found",
                        "available": list(rules.subagents.keys()),
                    }
                ),
                is_error=True,
            )

        spec = rules.subagents[spec_name]
        result = await run_subagent(
            spec=spec,
            task=task,
            context=extra_ctx,
            workspace=ctx.workspace,
            user_id=ctx.user_id,
        )
        return ToolResult(
            content=result["answer"],
            metadata={"subagent": spec_name, "iterations": result.get("iterations", 0), "tokens": result.get("tokens", 0)},
        )