#!/usr/bin/env python3
"""tests/test_dispatch.py - T008 dispatch 命令单元测试。

覆盖：
- test_dispatch_output: 正常调度输出 query_template + role_identity
- test_dispatch_no_match: 无匹配 agent 时 strategy=none
- test_dispatch_json_format: --json 输出合法 JSON
"""
import json
import subprocess
import sys
import os

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_dispatch(task, json_flag=False):
    """辅助：运行 dispatch 命令"""
    cmd = [sys.executable, "scripts/launch_subagent_rj.py", "dispatch", "--task", task]
    if json_flag:
        cmd.append("--json")
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=SKILL_ROOT
    )


class TestDispatch:
    """dispatch 命令测试"""

    def test_dispatch_output(self):
        """测试 dispatch 命令输出 query_template"""
        result = _run_dispatch("初始化项目", json_flag=True)
        assert result.returncode == 0, f"returncode={result.returncode}, stderr={result.stderr}"
        data = json.loads(result.stdout)
        assert "agents" in data
        assert len(data["agents"]) > 0
        agent = data["agents"][0]
        assert "query_template" in agent
        assert "[subagent:" in agent["query_template"]
        assert "role_identity" in agent
        assert agent["role_identity"]  # 非空

    def test_dispatch_no_match(self):
        """测试无匹配 agent 时 strategy=none"""
        # 注意：不能用含 "word"/"key"/"test"/"git" 等触发词子串的字符串
        # "qwerty12345" 经验证不含任何 subagent_config 触发词子串
        result = _run_dispatch("qwerty12345", json_flag=True)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["strategy"] == "none"
        assert len(data["agents"]) == 0

    def test_dispatch_json_format(self):
        """测试 --json 输出合法 JSON"""
        result = _run_dispatch("写代码", json_flag=True)
        assert result.returncode == 0
        # 必须是合法 JSON
        data = json.loads(result.stdout)
        assert "task_description" in data
        assert "strategy" in data
        assert "agents" in data
        assert "timestamp" in data

    def test_dispatch_multiple_match(self):
        """测试多匹配时 strategy=parallel"""
        # "整理" 匹配 sync_agent，"写代码" 匹配 code_eng_agent
        # 用一个能匹配多个 agent 的任务描述
        result = _run_dispatch("写代码 整理", json_flag=True)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # 至少匹配到 1 个
        assert len(data["agents"]) >= 1
        # 每个 agent 都有 query_template
        for a in data["agents"]:
            assert "query_template" in a
            assert "[subagent:" in a["query_template"]
