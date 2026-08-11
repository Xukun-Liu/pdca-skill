"""pytest conftest.py - pdca-skill 测试基础设施共享 fixture。

提供:
- tmp_skill_dir: 临时 skill 目录 fixture(构造最小可测结构)
- create_memory_fixture: 构造 memory_main.md 测试 fixture
- create_summary_fixture: 构造 SUMMARY_RJ.md 测试 fixture

设计原则:
- 纯 Python 标准库,零外部依赖
- fixture 自动隔离,测试结束自动清理
- 支持 overrides 参数定制内容
"""
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def tmp_skill_dir(tmp_path):
    """构造最小可测 skill 目录结构。

    创建以下骨架:
    - SKILL.md(最小 frontmatter)
    - references/(空目录)
    - scripts/(空目录)
    - protocol/(空目录)
    - memory/memory_main.md(空)
    - docs_rj/SUMMARY_RJ.md(空)
    - docs_rj/memory_rj/(空目录)

    返回 Path 对象指向 tmp_path/skill。
    """
    skill_root = tmp_path / "skill"
    for sub in ["references", "scripts", "protocol", "assets",
                "memory", "docs_rj", "docs_rj/memory_rj",
                "docs_rj/spec_rj", "docs_rj/task_rj", "docs_rj/handoff_rj"]:
        (skill_root / sub).mkdir(parents=True, exist_ok=True)

    # 最小 SKILL.md
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: pdca-skill-test\n"
        "description: test\n"
        "agent_created: true\n"
        "license: Non-Commercial Source-Available License v1.0\n"
        "version: \"1.0.0\"\n"
        "keywords: [test]\n"
        "category: workflow\n"
        "author: test\n"
        "---\n",
        encoding="utf-8"
    )

    # 空 memory_main.md
    (skill_root / "memory" / "memory_main.md").write_text(
        "# 全局聚合记忆\n\n## test-project\n\n- 暂无条目\n",
        encoding="utf-8"
    )

    # 空 SUMMARY_RJ.md
    (skill_root / "docs_rj" / "SUMMARY_RJ.md").write_text(
        "---\n"
        "title: test\n"
        "version: v1.0.0\n"
        "---\n"
        "# SUMMARY\n",
        encoding="utf-8"
    )

    return skill_root


@pytest.fixture
def create_memory_fixture(tmp_skill_dir):
    """构造 memory_main.md 测试 fixture 工厂函数。

    用法:
        def test_xxx(create_memory_fixture):
            mem = create_memory_fixture(task="my_task", content="custom")
            assert "my_task" in mem

    支持 overrides:
    - task: 任务名(默认 'test_task')
    - content: 正文内容(默认 'test memory content')
    - timestamp: 时间戳(默认 '20260718_1432')
    """
    def _create(task="test_task", content="test memory content",
                timestamp="20260718_1432"):
        mem_path = tmp_skill_dir / "memory" / "memory_main.md"
        body = (
            f"# 全局聚合记忆\n\n"
            f"## test-project\n\n"
            f"### {task}（{timestamp}）\n\n"
            f"{content}\n"
        )
        mem_path.write_text(body, encoding="utf-8")
        return mem_path.read_text(encoding="utf-8")

    return _create


@pytest.fixture
def create_summary_fixture(tmp_skill_dir):
    """构造 SUMMARY_RJ.md 测试 fixture 工厂函数。

    用法:
        def test_xxx(create_summary_fixture):
            s = create_summary_fixture(total_docs=10, version="v1.0.0")
            assert "v1.0.0" in s

    支持 overrides:
    - total_docs: 文档总数(默认 5)
    - version: 版本号(默认 'v1.0.0')
    - extra_sections: 额外章节 list(默认 [])
    """
    def _create(total_docs=5, version="v1.0.0", extra_sections=None):
        sum_path = tmp_skill_dir / "docs_rj" / "SUMMARY_RJ.md"
        sections = list(extra_sections or [])
        body = (
            f"---\n"
            f"title: test\n"
            f"version: {version}\n"
            f"total_docs: {total_docs}\n"
            f"---\n\n"
            f"# 📚 文档汇总视图\n\n"
        )
        for sec in sections:
            body += f"## {sec}\n\n- (empty)\n\n"
        sum_path.write_text(body, encoding="utf-8")
        return sum_path.read_text(encoding="utf-8")

    return _create


@pytest.fixture(autouse=True)
def _ensure_no_sys_path_pollution():
    """自动 fixture:确保测试不污染 sys.path。

    测试开始记录 sys.path,结束后恢复,防止 protocol/__init__.py
    导入副作用跨测试污染。
    """
    original_path = list(sys.path)
    yield
    sys.path[:] = original_path
