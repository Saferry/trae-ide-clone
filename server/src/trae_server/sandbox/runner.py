"""沙箱执行器（macOS / Linux）。"""

from __future__ import annotations

import asyncio
import platform
import shutil
import tempfile

from .policy import Policy, evaluate_command


class SandboxRunner:
    def __init__(self, policy: Policy, workspace: str) -> None:
        self.policy = policy
        self.workspace = workspace
        self.system = platform.system().lower()

    async def run(self, command: str, cwd: str = ".", timeout: int | None = None) -> tuple[int, str, str]:
        ok, reason = evaluate_command(self.policy, command)
        if not ok:
            return 1, "", f"sandbox denied: {reason}"
        timeout = timeout or self.policy.process.max_runtime_seconds
        cwd_path = self._resolve_cwd(cwd)
        full_cmd = self._wrap(command, cwd_path)
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
                return 124, "", f"timeout after {timeout}s"
            return (
                proc.returncode or 0,
                (stdout or b"").decode("utf-8", errors="replace"),
                (stderr or b"").decode("utf-8", errors="replace"),
            )
        except FileNotFoundError as e:
            return 127, "", str(e)

    def _resolve_cwd(self, rel: str) -> str:
        import os

        ws = self.workspace
        target = os.path.normpath(os.path.join(ws, rel))
        if not target.startswith(os.path.abspath(ws)):
            return os.path.abspath(ws)
        return target

    def _wrap(self, command: str, cwd: str) -> list[str]:
        if self.system == "linux" and shutil.which("bwrap"):
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
        if self.system == "darwin" and shutil.which("sandbox-exec"):
            return ["sandbox-exec", "-f", self._macos_profile(cwd), "sh", "-c", command]
        if self.system == "windows":
            return ["cmd", "/c", command]
        return ["sh", "-c", command]

    def _macos_profile(self, cwd: str) -> str:
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