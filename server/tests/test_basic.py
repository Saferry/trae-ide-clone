"""config / rules / tools 基础测试。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from trae_server import config as cfg_mod
from trae_server.config import load_config
from trae_server.rules.loader import RuleLoader, load_rules
from trae_server.tools.base import RiskLevel, ToolContext, ToolResult, get_registry


@pytest.fixture(autouse=True)
def setup_config(monkeypatch):
    test_yaml = Path(__file__).parent / "fixtures" / "trae.test.yaml"
    monkeypatch.setenv("TRAE_CONFIG", str(test_yaml))
    cfg_mod.reload_config()
    yield


def test_load_config_parses_yaml():
    cfg = load_config()
    assert cfg.server.port == 8088
    assert cfg.models.providers[0].id == "fake-openai"
    assert "test-key" in [k.key for k in cfg.auth.api_keys]


def test_rules_loader_parses_md():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / ".trae").mkdir()
        (p / ".trae" / "rules.md").write_text(
            "# Title\n\n## Section A\nfoo\n\n## Section B\nbar\n",
            encoding="utf-8",
        )
        rs = load_rules(str(p))
        assert [r.title for r in rs.rules] == ["Section A", "Section B"]


def test_rules_loader_parses_subagent():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / ".trae" / "agents").mkdir(parents=True)
        (p / ".trae" / "agents" / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: review code\ntools: [read_file, grep]\ncontext_window: 4096\n---\nyou are a strict reviewer",
            encoding="utf-8",
        )
        rs = load_rules(str(p))
        assert "reviewer" in rs.subagents
        assert rs.subagents["reviewer"].tools == ["read_file", "grep"]


def test_tool_registry_builtins():
    reg = get_registry()
    expected = {
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "bash",
        "grep",
        "glob",
        "codebase_query",
        "index_build",
        "web_fetch",
        "delegate",
    }
    assert expected.issubset(set(reg.list_tools()))


def test_file_tools_round_trip(tmp_path: Path):
    reg = get_registry()
    ctx = ToolContext(workspace=str(tmp_path))
    write = reg.get("write_file")
    read = reg.get("read_file")

    import asyncio

    async def run():
        r1 = await write.execute({"path": "hello.txt", "content": "hi"}, ctx)
        assert "wrote" in r1.content
        r2 = await read.execute({"path": "hello.txt"}, ctx)
        assert r2.content == "hi"

    asyncio.run(run())


def test_bash_blocks_dangerous(tmp_path: Path):
    reg = get_registry()
    ctx = ToolContext(workspace=str(tmp_path))
    bash = reg.get("bash")
    import asyncio

    async def run():
        r = await bash.execute({"command": "rm -rf /"}, ctx)
        assert r.is_error
        assert "dangerous" in r.content.lower() or "refused" in r.content.lower()

    asyncio.run(run())


def test_bash_executes_simple(tmp_path: Path):
    reg = get_registry()
    ctx = ToolContext(workspace=str(tmp_path))
    bash = reg.get("bash")
    import asyncio
    import sys

    cmd = "echo hello" if sys.platform != "win32" else "echo hello"

    async def run():
        r = await bash.execute({"command": cmd}, ctx)
        # Windows cmd echo 也会成功
        assert r.metadata.get("exit_code", 0) == 0

    asyncio.run(run())