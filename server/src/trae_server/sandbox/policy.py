"""沙箱策略：解析 sandbox.json / YAML，并评估命令是否允许执行。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FilesystemRule:
    allow_write_paths: list[str] = field(default_factory=list)
    allow_read_paths: list[str] = field(default_factory=list)
    deny_paths: list[str] = field(default_factory=list)


@dataclass
class NetworkRule:
    enabled: bool = False
    allowed_domains: list[str] = field(default_factory=list)
    denied_domains: list[str] = field(default_factory=list)


@dataclass
class ProcessRule:
    max_runtime_seconds: int = 60
    max_memory_mb: int = 512
    max_cpu_percent: int = 80
    allow_pty: bool = False


@dataclass
class Policy:
    name: str
    filesystem: FilesystemRule = field(default_factory=FilesystemRule)
    network: NetworkRule = field(default_factory=NetworkRule)
    process: ProcessRule = field(default_factory=ProcessRule)
    dangerous_commands: list[str] = field(default_factory=list)

    def is_dangerous(self, command: str) -> str | None:
        for pat in self.dangerous_commands:
            if re.search(pat, command):
                return pat
        return None


def evaluate_command(policy: Policy, command: str) -> tuple[bool, str]:
    """返回 (allowed, reason)。"""
    if policy.is_dangerous(command):
        return False, "dangerous command"
    if not policy.process.allow_pty and ">&" in command:
        return False, "pty not allowed"
    return True, "ok"


def load_policy_from_file(path: str | Path) -> dict[str, Policy]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Policy] = {}
    for name, spec in (raw.get("policies") or {}).items():
        fs_spec = spec.get("filesystem", {})
        net_spec = spec.get("network", {})
        proc_spec = spec.get("process", {})
        out[name] = Policy(
            name=name,
            filesystem=FilesystemRule(
                allow_write_paths=fs_spec.get("allow_write_paths", []),
                allow_read_paths=fs_spec.get("allow_read_paths", []),
                deny_paths=fs_spec.get("deny_paths", []),
            ),
            network=NetworkRule(
                enabled=net_spec.get("enabled", False),
                allowed_domains=net_spec.get("allowed_domains", []),
                denied_domains=net_spec.get("denied_domains", []),
            ),
            process=ProcessRule(
                max_runtime_seconds=proc_spec.get("max_runtime_seconds", 60),
                max_memory_mb=proc_spec.get("max_memory_mb", 512),
                max_cpu_percent=proc_spec.get("max_cpu_percent", 80),
                allow_pty=proc_spec.get("allow_pty", False),
            ),
            dangerous_commands=spec.get("dangerous_commands", []),
        )
    return out