"""Agent runner 解析测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from trae_server import config as cfg_mod


@pytest.fixture(autouse=True)
def setup_config(monkeypatch):
    test_yaml = Path(__file__).parent / "fixtures" / "trae.test.yaml"
    monkeypatch.setenv("TRAE_CONFIG", str(test_yaml))
    cfg_mod.reload_config()


def test_runner_parses_inline_tool_call():
    from trae_server.agents.runner import AgentRunner

    runner = AgentRunner()
    calls = runner._parse_tool_calls_from_text(
        'before\n<tool_call name="read_file">{"path":"a.txt"}</tool_call>\nafter'
    )
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "a.txt"}


def test_runner_parses_plan():
    from trae_server.agents.runner import AgentRunner

    runner = AgentRunner()
    plan = runner._parse_plan(
        '{"summary":"build it","steps":[{"tool":"bash","args":{"command":"ls"},"risk":"low"}]}'
    )
    assert plan.summary == "build it"
    assert len(plan.steps) == 1
    assert plan.steps[0].tool == "bash"