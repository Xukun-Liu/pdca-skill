#!/usr/bin/env python3
"""tests/test_learn_tidy_count.py - learn_tidy.py count 子命令 + scan --memory-path 单元测试。

覆盖 learn_into_act 任务的 7 个 AC：
- AC-001: count 默认 memory_main.md，JSON 含 total_entries/threshold/should_run
- AC-002: 15 条 fixture + threshold=20 → should_run=false
- AC-003: 25 条 fixture + threshold=20 → should_run=true
- AC-011: 单条 fixture，total_entries=1，格式匹配
- AC-012: 空 fixture + threshold=0 → should_run=false（H4 修复）
- AC-013: threshold=-1 → threshold=20 + warning 含"负数"（M2-4 修复）
- AC-015: scan --memory-path 支持自定义路径（H2-1 修复）

补充边界 case：
- threshold=0 + total>0 → should_run=true（H4 修复另一面）
- memory_path 不存在 → 退出码 2 + error 字段
- total=0 但文件有内容 → warning 字段（H2 修复）

设计原则：
- 每个 count 测试用 tmp_path fixture 造独立 fixture 文件，不污染真实 memory_main.md
- monkeypatch 替换 MEMORY_MAIN_PATH，避免 count 默认路径读到真实 memory
- sys.path.insert 按项目约定（conftest autouse fixture 在测试结束恢复 sys.path）
"""
import sys
import os
import json
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


def _make_memory_file(path, num_entries):
    """造含 N 条记忆条目的 memory 文件（格式匹配 MEMORY_ENTRY_RE）。"""
    content = "# 主记忆（测试 fixture）\n\n"
    for i in range(num_entries):
        content += "### 记忆条目 · test_task_%02d（2026-07-29 18:50）\n" % (i + 1)
        content += "**内容**：测试条目 %d\n\n" % (i + 1)
    Path(path).write_text(content, encoding="utf-8")


@pytest.fixture
def fixture_15(tmp_path):
    p = tmp_path / "memory_15.md"
    _make_memory_file(p, 15)
    return str(p)


@pytest.fixture
def fixture_25(tmp_path):
    p = tmp_path / "memory_25.md"
    _make_memory_file(p, 25)
    return str(p)


@pytest.fixture
def fixture_single(tmp_path):
    p = tmp_path / "memory_single.md"
    _make_memory_file(p, 1)
    return str(p)


@pytest.fixture
def fixture_5(tmp_path):
    p = tmp_path / "memory_5.md"
    _make_memory_file(p, 5)
    return str(p)


@pytest.fixture
def fixture_empty(tmp_path):
    p = tmp_path / "empty.md"
    Path(p).write_text("", encoding="utf-8")
    return str(p)


@pytest.fixture
def fixture_nonexistent(tmp_path):
    return str(tmp_path / "nonexistent.md")


@pytest.fixture
def patched_memory_path(tmp_path, monkeypatch):
    """monkeypatch 替换 learn_tidy.MEMORY_MAIN_PATH，避免默认路径读到真实 memory。"""
    import learn_tidy
    tmp_memory = tmp_path / "default_memory.md"
    tmp_memory.write_text("# 空的默认 memory（测试隔离）\n", encoding="utf-8")
    monkeypatch.setattr(learn_tidy, "MEMORY_MAIN_PATH", str(tmp_memory))
    return str(tmp_memory)


def _run_count(args_list):
    """跑 learn_tidy.py count 子命令，返回 (exit_code, parsed_json_or_None)。"""
    result = subprocess.run(
        ["python", "scripts/learn_tidy.py", "count"] + args_list,
        capture_output=True, text=True, encoding="utf-8"
    )
    try:
        parsed = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None
    return result.returncode, parsed


def test_ac_001_count_default_memory(patched_memory_path):
    """AC-001: count 不带参数，读默认 memory，输出合法 JSON 含 total/threshold/should_run。"""
    exit_code, data = _run_count([])
    assert exit_code == 0
    assert data is not None
    assert "total_entries" in data
    assert "threshold" in data
    assert "should_run" in data
    assert "memory_path" in data
    assert data["threshold"] == 20
    assert isinstance(data["should_run"], bool)


def test_ac_002_count_15_entries_should_run_false(fixture_15):
    """AC-002: 15 条 + threshold=20 → should_run=false。"""
    exit_code, data = _run_count(["--memory-path", fixture_15, "--threshold", "20"])
    assert exit_code == 0
    assert data["total_entries"] == 15
    assert data["threshold"] == 20
    assert data["should_run"] is False


def test_ac_003_count_25_entries_should_run_true(fixture_25):
    """AC-003: 25 条 + threshold=20 → should_run=true。"""
    exit_code, data = _run_count(["--memory-path", fixture_25, "--threshold", "20"])
    assert exit_code == 0
    assert data["total_entries"] == 25
    assert data["threshold"] == 20
    assert data["should_run"] is True


def test_ac_011_count_single_entry(fixture_single):
    """AC-011: 单条记忆，total_entries=1，格式匹配。"""
    exit_code, data = _run_count(["--memory-path", fixture_single])
    assert exit_code == 0
    assert data["total_entries"] == 1
    assert data["should_run"] is False


def test_ac_012_count_empty_threshold_zero(fixture_empty):
    """AC-012: 空文件 + threshold=0 → should_run=false（H4 修复）。"""
    exit_code, data = _run_count(["--memory-path", fixture_empty, "--threshold", "0"])
    assert exit_code == 0
    assert data["total_entries"] == 0
    assert data["threshold"] == 0
    assert data["should_run"] is False


def test_ac_013_count_negative_threshold(fixture_25):
    """AC-013: threshold=-1 → 用默认 20 + warning 含"负数"。"""
    exit_code, data = _run_count(["--memory-path", fixture_25, "--threshold", "-1"])
    assert exit_code == 0
    assert data["threshold"] == 20
    assert "warning" in data
    assert "负数" in data["warning"]
    assert "-1" in data["warning"]


def test_ac_013_count_large_negative_threshold(fixture_25):
    """AC-013 补充：threshold=-100 → 同样用默认 20。"""
    exit_code, data = _run_count(["--memory-path", fixture_25, "--threshold", "-100"])
    assert exit_code == 0
    assert data["threshold"] == 20
    assert "负数" in data["warning"]


def test_h4_threshold_zero_total_positive(fixture_5):
    """H4 修复另一面：threshold=0 + total=5 → should_run=true。"""
    exit_code, data = _run_count(["--memory-path", fixture_5, "--threshold", "0"])
    assert exit_code == 0
    assert data["total_entries"] == 5
    assert data["threshold"] == 0
    assert data["should_run"] is True


def test_memory_path_not_exist(fixture_nonexistent):
    """memory_path 不存在 → 退出码 2 + error 字段。"""
    exit_code, data = _run_count(["--memory-path", fixture_nonexistent])
    assert exit_code == 2
    assert data is not None
    assert "error" in data
    assert "not found" in data["error"]


def test_h2_total_zero_with_content(tmp_path):
    """H2 修复：文件有内容但无匹配条目 → warning 字段。"""
    p = tmp_path / "no_match.md"
    Path(p).write_text("# 这是 memory 文件\n\n但没有任何记忆条目\n", encoding="utf-8")
    exit_code, data = _run_count(["--memory-path", str(p)])
    assert exit_code == 0
    assert data["total_entries"] == 0
    assert "warning" in data
    assert "无匹配条目" in data["warning"] or "MEMORY_ENTRY_RE" in data["warning"]


def test_ac_015_scan_memory_path(fixture_25):
    """AC-015: scan --dry-run --memory-path 能正常跑。"""
    result = subprocess.run(
        ["python", "scripts/learn_tidy.py", "scan", "--dry-run", "--memory-path", fixture_25],
        capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0


def test_end_to_end_count_then_scan(fixture_25):
    """端到端：count should_run=true → scan --dry-run 不报错（模拟 /act 步骤3.6）。"""
    exit_code, data = _run_count(["--memory-path", fixture_25, "--threshold", "20"])
    assert exit_code == 0
    assert data["should_run"] is True

    result = subprocess.run(
        ["python", "scripts/learn_tidy.py", "scan", "--dry-run", "--memory-path", fixture_25],
        capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0
