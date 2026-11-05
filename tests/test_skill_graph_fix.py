#!/usr/bin/env python3
"""tests/test_skill_graph_fix.py - skill_graph 断链修复 + --auto 自动模式 + 提取升级 测试。

覆盖 skill_graph 改造 v1.1（对抗审查后修订版）的关键修复：
- AC-101: read_pdca_memory 单一入口（无参死桩已删，签名带 skill_dir）
- AC-102: read_pdca_memory 外置优先（mock user_data_path 指向 tmp_path）
- AC-103: --source choices 去重（无重复 'pdca'）
- AC-104: build --auto 且 taxonomy 缓存缺失 → [SKIP] 提示 + exit 0
- AC-105: render_csv 技能名 CSV 注入防护（= + - @ 前缀加单引号）
- AC-106: _extract_lesson_skill_names 识别 is_lesson=true 条目内容中的技能
- AC-107: 经验条目技能置信度加权（+0.1）

设计原则：
- 用 tmp_path fixture 隔离，不污染真实 ~/.pdca-skill/data
- monkeypatch user_data_path 路径函数指向 tmp_path
- 每个测试独立 fixture，不共享状态
"""
import sys
import os
import json
import subprocess
import inspect
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import skill_graph_extract
import skill_graph_render
import skill_graph_build
import user_data_path


# ===========================================================================
# AC-101: read_pdca_memory 单一入口
# ===========================================================================

def test_read_pdca_memory_single_entry_point():
    """read_pdca_memory 应只有带 skill_dir 参数的版本，无 0 参死桩。"""
    fn = getattr(skill_graph_extract, "read_pdca_memory")
    sig = inspect.signature(fn)
    params = list(sig.parameters)
    assert params == ["skill_dir"], "read_pdca_memory 必须只接受 skill_dir 参数"


def test_source_choices_deduplicated():
    """--source choices 不应有重复的 'pdca'。"""
    args = ["--source", "pdca", "--skip-taxonomy"]
    parser = skill_graph_extract.main  # 不直接执行 main，验证 argparse 定义
    # 直接检查源码级别的 choices 去重：通过构造 parser 校验
    import argparse
    # 简单验证：从 main 的 argparse 定义里无法直接取，改用黑盒验证重复值会报错
    from unittest.mock import patch
    with patch("sys.argv", ["skill_graph_extract.py"] + args):
        pass  # main 内部解析，此处仅验证 choices 字符串不再重复
    # 读取源码确认 choices 无重复
    src = inspect.getsource(skill_graph_extract)
    assert "choices=['pdca', 'ai_tools', 'pdca', 'all']" not in src, "旧版重复 choices 仍存在"
    assert "choices=['pdca', 'ai_tools', 'all']" in src, "去重后的 choices 未生效"


# ===========================================================================
# AC-102: read_pdca_memory 外置优先
# ===========================================================================

@pytest.fixture
def ext_memory(tmp_path, monkeypatch):
    """造外置记忆目录结构，monkeypatch user_data_path 指向 tmp_path。"""
    mem_main = tmp_path / "memory" / "memory_main.md"
    mem_rj = tmp_path / "docs_rj" / "memory_rj"
    mem_main.parent.mkdir(parents=True)
    mem_rj.mkdir(parents=True)
    mem_main.write_text(
        "## 测试项目\n\n### 记忆条目 · t1（2026-08-01 10:00）\n**内容**：Python 脚本\n",
        encoding="utf-8",
    )
    (mem_rj / "t1_memory_20260801_1000.md").write_text("Docker 部署", encoding="utf-8")
    monkeypatch.setattr(user_data_path, "get_memory_main_path_with_fallback",
                        lambda skill_dir=None: str(mem_main))
    monkeypatch.setattr(user_data_path, "get_memory_rj_path", lambda: mem_rj)
    return {"main": str(mem_main), "rj": str(mem_rj)}


def test_read_pdca_memory_external_priority(ext_memory):
    """read_pdca_memory 应读外置目录（memory_main + memory_rj 各 1 个文件）。"""
    mems = skill_graph_extract.read_pdca_memory("C:/fake_skill_dir")
    files = [m.file for m in mems]
    assert len(files) == 2, "应读到 2 个外置记忆文件: %s" % files
    assert ext_memory["main"] in files
    assert any(f.endswith("t1_memory_20260801_1000.md") for f in files)


def test_read_pdca_memory_layered_dirs(ext_memory):
    """v1.1.0：{memory_class}/{YYYYMM}/ 分层记忆也要被扫描到（不再只扫一级）。"""
    month_dir = os.path.join(ext_memory["rj"], "decision", "202608")
    os.makedirs(month_dir, exist_ok=True)
    with open(os.path.join(month_dir, "t2_memory_20260802_1000.md"), "w", encoding="utf-8") as f:
        f.write("分层记忆")
    files = [m.file for m in skill_graph_extract.read_pdca_memory("C:/fake_skill_dir")]
    assert any(f.endswith("t2_memory_20260802_1000.md") for f in files), files


def test_collect_input_files_layered_dirs(ext_memory, tmp_path):
    """v1.1.0：skill_graph_build 的输入收集也要覆盖分层目录。"""
    month_dir = os.path.join(ext_memory["rj"], "status", "202609")
    os.makedirs(month_dir, exist_ok=True)
    with open(os.path.join(month_dir, "t3_memory_20260901_1000.md"), "w", encoding="utf-8") as f:
        f.write("分层记忆")
    files = skill_graph_build._collect_input_files(str(tmp_path))
    assert any(f.endswith("t3_memory_20260901_1000.md") for f in files), files


def test_read_pdca_memory_fallback_when_external_missing(tmp_path, monkeypatch):
    """外置目录不存在时退回包内路径（不崩溃，读包内）。"""
    monkeypatch.setattr(user_data_path, "get_memory_main_path_with_fallback",
                        lambda skill_dir=None: os.path.join(skill_dir, "memory", "memory_main.md"))
    monkeypatch.setattr(user_data_path, "get_memory_rj_path",
                        lambda: tmp_path / "no_such_memory_rj")
    # skill_dir 指向 tmp_path 下造一个包内 memory_rj
    pkg_rj = tmp_path / "docs_rj" / "memory_rj"
    pkg_rj.mkdir(parents=True)
    (pkg_rj / "pkg_memory_20260801_1000.md").write_text("test", encoding="utf-8")
    mems = skill_graph_extract.read_pdca_memory(str(tmp_path))
    assert any(f.endswith("pkg_memory_20260801_1000.md") for f in [m.file for m in mems])


# ===========================================================================
# AC-104: build --auto taxonomy 缺失 → [SKIP]
# ===========================================================================

def test_build_auto_skip_without_taxonomy(tmp_path, monkeypatch):
    """--auto 且 master_taxonomy.json 缺失 → [SKIP] 提示 + exit 0。

    用 PDCA_DATA_DIR 环境变量做跨进程隔离（monkeypatch 不跨 subprocess）。
    """
    (tmp_path / "memory").mkdir(parents=True)
    (tmp_path / "memory" / "memory_main.md").write_text("", encoding="utf-8")
    (tmp_path / "docs_rj" / "memory_rj").mkdir(parents=True)
    env = dict(os.environ)
    env["PDCA_DATA_DIR"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(skill_graph_build.__file__), "skill_graph_build.py"),
         "--auto"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    out = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, "auto 模式 taxonomy 缺失应 exit 0: %s" % out[-500:]
    assert "[SKIP]" in out, "应输出 [SKIP] 提示: %s" % out[-500:]


# ===========================================================================
# AC-105: render_csv CSV 注入防护
# ===========================================================================

def test_render_csv_injection_safe():
    """技能名以 = + - @ 开头时应加单引号前缀（Excel 公式注入防护）。"""
    skills = [
        {"name": "=cmd", "category": "x", "status": "mastered", "confidence": 0.9,
         "evidence_count": 1, "source_tools": ["pdca"], "evidence_refs": []},
        {"name": "normal_skill", "category": "y", "status": "extra_mastered",
         "confidence": 0.8, "evidence_count": 2, "source_tools": ["pdca"],
         "evidence_refs": []},
    ]
    csv_out = skill_graph_render.render_csv(skills)
    lines = csv_out.lstrip("\ufeff").splitlines()
    assert lines[1].startswith("'=cmd"), "公式注入防护未生效: %s" % lines[1]
    assert lines[2].startswith("normal_skill")
    assert "=cmd(" not in csv_out


# ===========================================================================
# AC-106 / AC-107: 经验加权
# ===========================================================================

@pytest.fixture
def lesson_memory():
    """含 is_lesson=true 条目的 memory_main 内容。"""
    return (
        "## test\n\n"
        "### 记忆条目 · t1（2026-08-01 10:00）\n"
        "**重要性**: high\n"
        "**是否经验**: true\n"
        "**经验标签**: bugfix, python\n"
        "用 Python 和 pytest 写了 15 个测试。\n"
    )


def test_extract_lesson_skill_names(lesson_memory):
    """is_lesson=true 条目内容中的技能应被识别为经验技能。"""
    from skill_graph_extract import RawMemory, _extract_lesson_skill_names
    mems = [RawMemory(source_tool="pdca", file="C:/x/memory_main.md",
                      timestamp="2026-08-01", content=lesson_memory)]
    ls = _extract_lesson_skill_names(mems)
    assert "Python" in ls


def test_lesson_skill_confidence_boost(lesson_memory):
    """经验条目的技能置信度应加权（0.75 → 0.85）。"""
    from skill_graph_extract import RawMemory, extract_skills_rulebased
    mems = [RawMemory(source_tool="pdca", file="C:/x/memory_main.md",
                      timestamp="2026-08-01", content=lesson_memory)]
    skills = extract_skills_rulebased(mems)
    by_name = {s.name: s.confidence for s in skills}
    assert by_name.get("Python", 0) > 0.75, "经验加权未生效: %s" % by_name
