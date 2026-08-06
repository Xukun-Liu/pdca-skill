#!/usr/bin/env python3
"""tests/test_skill_graph_scan_gate.py - skill_graph_extract.py 扫描确认门控单元测试。

对应 v1.0.1 安全修复：非交互模式下"未确认"的工具目录只记录路径、不读取内容；
敏感行摘录不入库；main() 无同名函数崩溃；扫描根不含父目录链。

覆盖：
- test_non_tty_discovery_not_read: 非交互模式发现新工具只记录路径，不读取内容
- test_non_tty_no_scan_roots_no_read: 非交互模式无命中目录时干净返回
- test_tty_confirm_all_reads_content: 交互模式用户确认纳入后读取内容
- test_tty_confirm_specific_reads_content: 交互模式用户只选择部分目录纳入
- test_tty_skip_all_no_read: 交互模式用户全部不纳入时不读取
- test_excerpt_sensitive_line_omitted: 敏感行摘录替换为占位，不持久化原文
- test_excerpt_normal_line_kept: 正常行摘录保留原文
- test_scan_roots_exclude_parent_chain: 扫描根含 cwd 但不含父目录链
- test_main_riji_source_smoke: main() 冒烟（--source riji 不崩溃，修复同名函数重定义）
"""

import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from skill_graph_extract import (
    RawMemory,
    _get_scan_roots,
    _keyword_discover_scan,
    _is_tty,
    extract_skills_rulebased,
)


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


class TestExcerptSensitiveFilter:
    """v1.0.1 敏感行摘录过滤：命中敏感模式的行不持久化原文。"""

    def test_excerpt_sensitive_line_omitted(self):
        mem = RawMemory(
            source_tool="test",
            file=r"C:\fake\memory.md",
            timestamp="2026-08-06 10:00",
            content="user Python login password: sk-abc123\n",
        )
        skills = extract_skills_rulebased([mem])
        python_skill = next(s for s in skills if s.name == "Python")
        assert python_skill.evidence[0]["excerpt"] == "[sensitive line omitted]"

    def test_excerpt_spaced_variant_omitted(self):
        """空格变体（api key / session id / pwd =）与裸 sk- 密钥值均须过滤。"""
        for line in (
            "Python api key = sk-abc123xyz",
            "Python session id: 0xdeadbeef",
            "Python pwd = hunter2",
            "Python 用 sk-abcdef123456789 调接口",
        ):
            mem = RawMemory(
                source_tool="test",
                file=r"C:\fake\memory.md",
                timestamp="2026-08-06 10:00",
                content=line + "\n",
            )
            skills = extract_skills_rulebased([mem])
            python_skill = next(s for s in skills if s.name == "Python")
            assert python_skill.evidence[0]["excerpt"] == "[sensitive line omitted]", line

    def test_excerpt_tokenizer_not_omitted(self):
        """词边界防误伤：tokenizer/tokens 属正常技术词，不应被过滤。"""
        mem = RawMemory(
            source_tool="test",
            file=r"C:\fake\memory.md",
            timestamp="2026-08-06 10:00",
            content="用 Python 训练 tokenizer 模型\n",
        )
        skills = extract_skills_rulebased([mem])
        python_skill = next(s for s in skills if s.name == "Python")
        assert python_skill.evidence[0]["excerpt"] == "用 Python 训练 tokenizer 模型"

    def test_excerpt_normal_line_kept(self):
        mem = RawMemory(
            source_tool="test",
            file=r"C:\fake\memory.md",
            timestamp="2026-08-06 10:00",
            content="# 用户偏好：使用 Python 写脚本\n",
        )
        skills = extract_skills_rulebased([mem])
        python_skill = next(s for s in skills if s.name == "Python")
        assert python_skill.evidence[0]["excerpt"].startswith("# 用户偏好：使用 Python")
        assert python_skill.evidence[0]["excerpt"] != "[sensitive line omitted]"


class TestScanRootsParentChain:
    """v1.0.1 扫描根对齐 L0：含 cwd，不含父目录链。"""

    def test_scan_roots_exclude_parent_chain(self):
        roots = [os.path.normpath(r) for r in _get_scan_roots()]
        cwd = os.path.normpath(os.getcwd())
        assert cwd in roots
        parent = os.path.normpath(os.path.dirname(cwd))
        assert parent not in roots, f"父目录不应是扫描根: {parent}"


class TestMainSmoke:
    """main() 冒烟：修复 v1.0.1 审查发现的同名函数重定义崩溃。"""

    def test_main_riji_source_smoke(self, tmp_path):
        skill_dir = tmp_path / "skill"
        (skill_dir / "memory").mkdir(parents=True)
        (skill_dir / "memory" / "memory_main.md").write_text(
            "# 全局聚合记忆\n\n## test\n\n- 使用 Python\n",
            encoding="utf-8",
        )
        out = tmp_path / "out.json"
        data_dir = tmp_path / "data"
        proc = subprocess.run(
            [sys.executable, os.path.join(SKILL_ROOT, "scripts", "skill_graph_extract.py"),
             "--source", "riji", "--skill-dir", str(skill_dir),
             "--skip-taxonomy", "--no-cache", "--output", str(out)],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "utf-8",
                 "RIJI_DATA_DIR": str(data_dir)},
        )
        assert proc.returncode == 0, f"main 崩溃: {proc.stderr[-500:]}"
        assert out.exists()
