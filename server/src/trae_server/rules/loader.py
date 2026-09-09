"""Rules 加载器：从工作区读取 .trae/rules.md 并支持子智能体定义。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Rule:
    """通用规则条目。"""

    title: str
    content: str


@dataclass
class SubagentSpec:
    """从 Markdown frontmatter 解析的子智能体定义。"""

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    context_window: int = 8000
    model: str = ""
    body: str = ""


@dataclass
class RuleSet:
    workspace: Path | None
    rules: list[Rule] = field(default_factory=list)
    subagents: dict[str, SubagentSpec] = field(default_factory=dict)

    def as_system_prompt(self) -> str:
        if not self.rules:
            return ""
        parts = ["# 工作区规则 (.trae/rules.md)"]
        for r in self.rules:
            parts.append(f"\n## {r.title}\n{r.content}")
        return "\n".join(parts)


class RuleLoader:
    """加载工作区的 .trae 目录。"""

    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

    def __init__(self, workspace: str | Path | None) -> None:
        self.workspace = Path(workspace) if workspace else None

    def load(self) -> RuleSet:
        rs = RuleSet(workspace=self.workspace)
        if not self.workspace:
            return rs
        trae_dir = self.workspace / ".trae"
        if not trae_dir.exists():
            return rs

        # 主规则
        rules_file = trae_dir / "rules.md"
        if rules_file.exists():
            rs.rules = self._parse_rules(rules_file.read_text(encoding="utf-8"))

        # 子智能体
        agents_dir = trae_dir / "agents"
        if agents_dir.exists():
            for f in agents_dir.glob("*.md"):
                spec = self._parse_subagent(f.read_text(encoding="utf-8"))
                if spec:
                    rs.subagents[spec.name] = spec

        return rs

    def _parse_rules(self, text: str) -> list[Rule]:
        """解析 rules.md：按 ## 切分。"""
        lines = text.splitlines()
        rules: list[Rule] = []
        current_title: str | None = None
        buf: list[str] = []

        def flush() -> None:
            if current_title is not None:
                rules.append(Rule(title=current_title, content="\n".join(buf).strip()))

        for line in lines:
            if line.startswith("## "):
                flush()
                current_title = line[3:].strip()
                buf = []
            elif line.startswith("# "):
                # 顶层标题，跳过
                continue
            else:
                buf.append(line)
        flush()
        return rules

    def _parse_subagent(self, text: str) -> SubagentSpec | None:
        """解析 Markdown frontmatter 格式的子智能体定义。"""
        m = self.FRONTMATTER_RE.match(text.strip())
        if not m:
            return None
        meta_text, body = m.group(1), m.group(2).strip()
        meta: dict[str, object] = {}
        for line in meta_text.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                meta[k] = [s.strip().strip('"').strip("'") for s in v[1:-1].split(",") if s.strip()]
            elif v.startswith('"') and v.endswith('"'):
                meta[k] = v[1:-1]
            elif v.isdigit():
                meta[k] = int(v)
            else:
                meta[k] = v

        name = str(meta.get("name", "")).strip()
        if not name:
            return None

        tools_raw = meta.get("tools", [])
        tools = tools_raw if isinstance(tools_raw, list) else []

        return SubagentSpec(
            name=name,
            description=str(meta.get("description", "")).strip(),
            tools=[str(t) for t in tools],
            context_window=int(meta.get("context_window", 8000)),  # type: ignore[arg-type]
            model=str(meta.get("model", "")),
            body=body,
        )


def load_rules(workspace: str | Path | None) -> RuleSet:
    """便捷函数。"""
    return RuleLoader(workspace).load()