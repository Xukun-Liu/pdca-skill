#!/usr/bin/env python3
"""tests/test_skill_graph_scan_gate.py - skill_graph_extract.py 扫描确认门控单元测试。

对应 v1.0.1 安全修复：非交互模式下"未确认"的工具目录只记录路径、不读取内容。

覆盖：
- test_non_tty_discovery_not_read: 非交互模式发现新工具只记录路径，不读取内容
- test_non_tty_no_scan_roots_no_read: 非交互模式无命中目录时干净返回
- test_tty_confirm_all_reads_content: 交互模式用户确认纳入后读取内容
- test_tty_confirm_specific_reads_content: 交互模式用户只选择部分目录纳入
- test_tty_skip_all_no_read: 交互模式用户全部不纳入时不读取
"""

import os
import sys
from pathlib import Path

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from skill_graph_extract import _get_scan_roots, _keyword_discover_scan, _is_tty


def _make_tool_dir(root: Path, dirname: str) -> Path:
    """构造一个命中 SCAN_KEYWORDS 的工具目录，内含一个记忆文件。"""
    tool_dir = root / dirname
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "memory.md").write_text(
        "# agent memory\n\n- 用户偏好：使用 Python 脚本\n",
        encoding="utf-8"
    )
    return tool_dir


class TestNonTtyScanGate:
    """非交互模式：未确认的目录不得读取内容（v1.0.1 安全修复）。"""

    def test_non_tty_discovery_not_read(self, tmp_path, monkeypatch):
        tool_dir = _make_tool_dir(tmp_path, ".someagent")

        monkeypatch.setattr(
            "skill_graph_extract._get_scan_roots",
            lambda: [str(tmp_path)],
        )
        monkeypatch.setattr("skill_graph_extract._is_tty", lambda: False)

        memories, discovered = _keyword_discover_scan(set())

        # 发现已记录，但路径是唯一产物
        assert len(discovered) == 1
        assert os.path.normpath(discovered[0]["path"]) == os.path.normpath(str(tool_dir))
        assert discovered[0]["confirmed"] is False
        assert "file_count" not in discovered[0]

        # 关键断言：未确认 → 内容未被读取
        assert memories == []

    def test_non_tty_no_scan_roots_no_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "skill_graph_extract._get_scan_roots",
            lambda: [str(tmp_path)],
        )
        monkeypatch.setattr("skill_graph_extract._is_tty", lambda: False)

        memories, discovered = _keyword_discover_scan(set())

        assert memories == []
        assert discovered == []

    def test_non_tty_real_scan_roots_are_task_outside(self, monkeypatch):
        """真实 _get_scan_roots 应包含任务外目录（~ / APPDATA），
        这正是需要 L2 确认门控的原因。"""
        roots = _get_scan_roots()
        assert roots, "_get_scan_roots 不应为空"
        home = os.path.expanduser("~")
        assert any(os.path.normpath(r) == os.path.normpath(home) for r in roots), \
            f"扫描根应包含用户主目录，实际: {roots}"


class TestTtyScanGate:
    """交互模式：用户确认纳入后才读取内容（行为保持 v1.0.0 不变）。"""

    def test_tty_confirm_all_reads_content(self, tmp_path, monkeypatch):
        _make_tool_dir(tmp_path, ".someagent")

        monkeypatch.setattr(
            "skill_graph_extract._get_scan_roots",
            lambda: [str(tmp_path)],
        )
        monkeypatch.setattr("skill_graph_extract._is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: "")

        memories, discovered = _keyword_discover_scan(set())

        assert len(discovered) == 1
        assert len(memories) == 1
        assert discovered[0]["file_count"] == 1
        assert "Python" in memories[0].content

    def test_tty_confirm_specific_reads_content(self, tmp_path, monkeypatch):
        _make_tool_dir(tmp_path, ".someagent")
        _make_tool_dir(tmp_path, ".otheragent")

        monkeypatch.setattr(
            "skill_graph_extract._get_scan_roots",
            lambda: [str(tmp_path)],
        )
        monkeypatch.setattr("skill_graph_extract._is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: "1")

        memories, discovered = _keyword_discover_scan(set())

        assert len(discovered) == 1
        assert len(memories) == 1

    def test_tty_skip_all_no_read(self, tmp_path, monkeypatch):
        _make_tool_dir(tmp_path, ".someagent")

        monkeypatch.setattr(
            "skill_graph_extract._get_scan_roots",
            lambda: [str(tmp_path)],
        )
        monkeypatch.setattr("skill_graph_extract._is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt: "0")

        memories, discovered = _keyword_discover_scan(set())

        assert discovered == []
        assert memories == []
