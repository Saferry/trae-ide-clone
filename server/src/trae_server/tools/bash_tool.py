"""Bash 命令执行工具（沙箱化）。"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import tempfile

from .base import RiskLevel, Tool, ToolContext, ToolResult


DANGEROUS_DEFAULT = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r":\(\)\{.*\};:",  # fork bomb
    r"mkfs",
    r"dd\s+if=",
    r"shutdown",
    r"reboot",
    r"halt",
    r"poweroff",
    r"chmod\s+-R\s+777\s+/",
]


class BashTool(Tool):
    name = "bash"
    description = "在工作区中执行 shell 命令（受沙箱保护）。参数：command、cwd（可选）。"
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "cwd": {"type": "string", "description": "相对工作区的子目录，默认 '.'"},
            "max_runtime_seconds": {"type": "integer", "default": 30},
        },
        "required": ["command"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        command: str = args.get("command") or ""
        cwd_rel: str = args.get("cwd") or "."
        timeout: int = int(args.get("max_runtime_seconds") or 30)

        # 1. 高危命令拦截
        from ..config import get_config

        patterns = list(get_config().agent.dangerous_command_patterns) + DANGEROUS_DEFAULT
        for pat in patterns:
            if re.search(pat, command):
                return ToolResult(content=f"error: refused dangerous command matched pattern '{pat}'", is_error=True)

        # 2. 工作区解析
        ws = ctx.workspace or os.getcwd()
        ws_path = os.path.abspath(ws)
        cwd_path = os.path.normpath(os.path.join(ws_path, cwd_rel))
        if not cwd_path.startswith(ws_path):
            return ToolResult(content="error: cwd outside workspace", is_error=True)
        os.makedirs(cwd_path, exist_ok=True)

        # 3. 三平台沙箱封装
        system = platform.system().lower()
        if system == "linux" and shutil.which("bwrap"):
            full_cmd = self._wrap_bwrap(command, cwd_path)
        elif system == "darwin" and shutil.which("sandbox-exec"):
            full_cmd = ["sandbox-exec", "-f", self._sandbox_profile(cwd_path), "sh", "-c", command]
        else:
            # Windows / 兜底：直接执行但 timeout 强约束
            full_cmd = ["sh" if system != "windows" else "cmd", "/c" if system == "windows" else "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(content=f"error: command timeout after {timeout}s", is_error=True)

            out = (stdout or b"").decode("utf-8", errors="replace")
            err = (stderr or b"").decode("utf-8", errors="replace")
            text = out + (("\n[stderr]\n" + err) if err else "")
            return ToolResult(
                content=text,
                metadata={"exit_code": proc.returncode, "cwd": cwd_path},
                is_error=proc.returncode != 0,
            )
        except FileNotFoundError as e:
            return ToolResult(content=f"error: shell not found: {e}", is_error=True)

    def _wrap_bwrap(self, command: str, cwd: str) -> list[str]:
        """Linux Bubblewrap 封装。"""
        return [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--bind", cwd, cwd,
            "--tmpfs", "/tmp",
            "--proc", "/proc",
            "--dev", "/dev",
            "--unshare-user-try",
            "--unshare-pid",
            "--unshare-net",
            "--die-with-parent",
            "--chdir", cwd,
            "sh", "-c", command,
        ]

    def _sandbox_profile(self, cwd: str) -> str:
        """macOS sandbox-exec 简易 profile。"""
        return f"""
(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow sysctl-read)
(allow file-read* (subpath "/usr"))
(allow file-read* (subpath "/bin"))
(allow file-read* (subpath "/Library"))
(allow file-read* (subpath "/private/var"))
(allow file-read* file-write* (subpath "{cwd}"))
(allow file-read* file-write* (subpath "{tempfile.gettempdir()}"))
(deny network*)
"""