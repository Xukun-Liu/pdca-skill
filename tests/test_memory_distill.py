#!/usr/bin/env python3
"""tests/test_memory_distill.py - memory_distill + write_project 评估参数单元测试。

覆盖：
- T001: write_project 扩展评估参数（importance_level/is_lesson/experience_tags）
  - test_write_project_with_importance: 传评估参数 → memory 文件含标记
  - test_write_project_backward_compat: 不传新参数 → 向后兼容（默认值 medium/false/无）
- T002: memory_distill.py 蒸馏中间层
  - test_distill_output: 解析 is_lesson=true 条目产出经验库 JSON
  - test_distill_empty: 无 is_lesson=true 条目输出空经验库

设计原则：
- 每个测试用 tmp_path fixture 隔离，不污染真实 memory_main.md
- monkeypatch 替换 GLOBAL_MEMORY_FILE / GLOBAL_MEMORY_DIR / _GLOBAL_CP_LOCK 到 tmp_path
- sys.path.insert 按项目约定（conftest autouse fixture 在测试结束恢复 sys.path）
"""
import sys
import os
import json
import pytest
from pathlib import Path

# 确保 scripts/ 在 path 中（conftest autouse fixture 会在测试结束恢复 sys.path）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


# ---------------------------------------------------------------------------
# 共享 fixture：隔离全局 memory 文件，避免污染真实 memory_main.md
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    """隔离 memory_shadow_write 的全局 memory 路径到 tmp_path。

    write_project 内部会 upsert_global_memory 写全局 memory_main.md，
    若不隔离会污染真实的 skill 包内 memory/memory_main.md。
    v1.0.4：默认固定 schema=False（未迁移模式，v1.0.3 扁平行为）——
    旧测试语义不变；v1.0.4 新模式用 isolated_memory_v104 fixture。
    """
    import memory_shadow_write

    tmp_memory = tmp_path / "memory_main.md"
    tmp_memory.write_text(
        "# 主记忆（全局聚合 · 主次跟进）\n\n"
        "> ⚠️ 仅供参考，以你当前指令为准。\n\n",
        encoding="utf-8"
    )
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", str(tmp_memory))
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", str(tmp_path))
    # 重新构造跨进程锁指向 tmp_memory，避免锁真实文件
    monkeypatch.setattr(
        memory_shadow_write, "_GLOBAL_CP_LOCK",
        memory_shadow_write._CrossProcessLock(str(tmp_memory))
    )
    # v1.0.4：固定未迁移模式（与真实数据目录的 .schema_version 状态解耦）
    monkeypatch.setattr(memory_shadow_write, "check_schema_version", lambda: False)
    return tmp_memory


@pytest.fixture
def isolated_memory_v104(tmp_path, monkeypatch):
    """v1.0.4 已迁移模式：schema=True → 标签文件夹深层落盘 + 全局索引行。"""
    import memory_shadow_write

    tmp_memory = tmp_path / "memory_main.md"
    tmp_memory.write_text(
        "# 主记忆（全局聚合 · 主次跟进）\n\n"
        "> ⚠️ 仅供参考，以你当前指令为准。\n\n",
        encoding="utf-8"
    )
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", str(tmp_memory))
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", str(tmp_path))
    monkeypatch.setattr(
        memory_shadow_write, "_GLOBAL_CP_LOCK",
        memory_shadow_write._CrossProcessLock(str(tmp_memory))
    )
    monkeypatch.setattr(memory_shadow_write, "check_schema_version", lambda: True)
    return tmp_memory


# ---------------------------------------------------------------------------
# T001: write_project 扩展评估参数
# ---------------------------------------------------------------------------

def test_write_project_with_importance(tmp_path, isolated_memory):
    """测试 write_project 支持重要性参数（AC-001）。

    Given: write_project 调用时传 importance_level="high"
    When: 写入 memory 文件
    Then: 条目含 `**重要性**: high` 标记
    """
    import memory_shadow_write

    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()

    memory_shadow_write.write_project(
        task="test_task",
        content="测试内容",
        project_memory_dir=str(proj_dir),
        project_name="test_project",
        importance_level="high",
        is_lesson=True,
        experience_tags=["bugfix", "auth"],
    )

    # 读取项目级 memory 文件
    files = list(proj_dir.glob("test_task_memory_*.md"))
    assert len(files) == 1, "应生成 1 个项目级 memory 文件"
    content = files[0].read_text(encoding="utf-8")
    assert "**重要性**: high" in content, "应含重要性标记"
    assert "**是否经验**: true" in content, "应含经验标记（小写 true）"
    assert "**经验标签**: bugfix, auth" in content, "应含经验标签"

    # 同时验证全局 memory_main.md 也含标记（upsert_global_memory 双写）
    global_content = isolated_memory.read_text(encoding="utf-8")
    assert "**重要性**: high" in global_content, "全局 memory 也应含标记"
    assert "**是否经验**: true" in global_content


def test_write_project_backward_compat(tmp_path, isolated_memory):
    """测试不传新参数时向后兼容（AC-002）。

    Given: write_project 不传 importance_level/is_lesson/experience_tags
    When: 写入 memory 文件
    Then: 行为与改造前一致 + 含默认值标记（medium/false/无）
    """
    import memory_shadow_write

    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()

    # 不传新参数（向后兼容）
    memory_shadow_write.write_project(
        task="test_compat",
        content="兼容性测试",
        project_memory_dir=str(proj_dir),
        project_name="test_project",
    )

    files = list(proj_dir.glob("test_compat_memory_*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    # 默认值应存在（H6 修复：旧格式分支也注入 eval_frontmatter）
    assert "**重要性**: medium" in content, "默认 importance_level=medium"
    assert "**是否经验**: false" in content, "默认 is_lesson=false"
    assert "**经验标签**: 无" in content, "无经验标签时显示'无'"


def test_write_project_invalid_importance_falls_back(tmp_path, isolated_memory):
    """测试非法 importance_level 降级为默认值（边界 case）。"""
    import memory_shadow_write

    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()

    memory_shadow_write.write_project(
        task="test_invalid",
        content="非法值测试",
        project_memory_dir=str(proj_dir),
        project_name="test_project",
        importance_level="critical",  # 非法值
    )

    files = list(proj_dir.glob("test_invalid_memory_*.md"))
    content = files[0].read_text(encoding="utf-8")
    # 非法值应降级为 medium
    assert "**重要性**: medium" in content


# ---------------------------------------------------------------------------
# T002: memory_distill.py 蒸馏中间层
# ---------------------------------------------------------------------------

def test_distill_output(tmp_path):
    """测试 distill 产出经验库 JSON（AC-003）。

    Given: memory_main.md 含 is_lesson=true 条目
    When: 运行 distill 命令
    Then: 产出 lessons.json 含 lesson_id/title/content 字段
    """
    memory_file = tmp_path / "memory_main.md"
    memory_file.write_text("""# 主记忆

## test_project

### 记忆条目 · bugfix_login（2026-07-24 09:00）
**重要性**: high
**是否经验**: true
**经验标签**: bugfix, auth

登录超时 bug 修复：增加 retry 机制。

### 记忆条目 · daily_log（2026-07-24 10:00）
**重要性**: low
**是否经验**: false
**经验标签**: 无

日常记录，无特殊经验。
""", encoding="utf-8")

    from memory_distill import distill
    output_dir = tmp_path / "learn_rj"
    result = distill(project_name="test_project", memory_file=str(memory_file), output_dir=str(output_dir))

    assert result["total_lessons"] == 1, "只应提取 1 条 is_lesson=true 条目"
    assert len(result["lessons"]) == 1
    lesson = result["lessons"][0]
    assert "lesson_id" in lesson
    assert "title" in lesson
    assert "content" in lesson
    assert "source_memory" in lesson
    assert lesson["title"] == "bugfix_login"
    assert "登录超时" in lesson["content"]

    # 验证 lessons.json 已落盘
    json_files = list(output_dir.glob("*/lessons.json"))
    assert len(json_files) == 1, "应产出 1 个 lessons.json"
    saved = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert saved["total_lessons"] == 1


def test_distill_empty(tmp_path):
    """测试无 is_lesson=true 条目时输出空经验库（AC-004）。"""
    memory_file = tmp_path / "memory_main.md"
    memory_file.write_text("""# 主记忆

## test_project

### 记忆条目 · daily（2026-07-24 09:00）
**重要性**: low
**是否经验**: false
**经验标签**: 无

日常记录。
""", encoding="utf-8")

    from memory_distill import distill
    result = distill(project_name="test_project", memory_file=str(memory_file))
    assert result["total_lessons"] == 0
    assert result["lessons"] == []


# ---------------------------------------------------------------------------
# T003 (v1.0.4): write_project 标签文件夹路由 + 索引行 + distill 索引展开
# ---------------------------------------------------------------------------

def test_write_project_v104_tag_folder_routing(tmp_path, isolated_memory_v104):
    """v1.0.4 已迁移模式：memory_class=pitfall → 正文落 {memory_rj}/pitfall/{YYYYMM}/，
    全局写索引行（含 task/tag/重要性/is_lesson/摘要/正文链接）。"""
    import memory_shadow_write

    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()

    result = memory_shadow_write.write_project(
        task="v104_route_test",
        content="这次踩坑了：mkstemp 被沙箱拦截",
        project_memory_dir=str(proj_dir),
        project_name="test_project",
        memory_class="pitfall",
    )

    assert result["memory_class"] == "pitfall"
    assert result["schema_v104"] is True
    # 正文落标签文件夹（深层 rglob）
    files = list(proj_dir.rglob("v104_route_test_memory_*.md"))
    assert len(files) == 1, "正文应落 pitfall/{YYYYMM}/ 深层目录"
    assert files[0].parent.parent.name == "pitfall"
    body = files[0].read_text(encoding="utf-8")
    assert "**重要性**: medium" in body  # 正文仍含完整 frontmatter
    # 全局只有索引行（无完整条目）
    global_content = isolated_memory_v104.read_text(encoding="utf-8")
    assert "### 记忆条目 · v104_route_test" not in global_content, "已迁移模式全局不应写完整条目"
    idx_line = [l for l in global_content.split("\n") if "v104_route_test" in l]
    assert len(idx_line) == 1, "应有 1 行索引行"
    assert "| pitfall |" in idx_line[0]
    assert "is_lesson=false" in idx_line[0]
    assert "[正文](file:///" in idx_line[0]


def test_write_project_v104_illegal_class_falls_back(tmp_path, isolated_memory_v104):
    """v1.0.4 非法 memory_class → 兜底 workflow 落盘。"""
    import memory_shadow_write

    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()

    result = memory_shadow_write.write_project(
        task="v104_fallback_test",
        content="非法值测试",
        project_memory_dir=str(proj_dir),
        project_name="test_project",
        memory_class="发布",  # 非法中文值
    )

    assert result["memory_class"] == "workflow", "非法值应兜底 workflow"
    files = list(proj_dir.rglob("v104_fallback_test_memory_*.md"))
    assert len(files) == 1
    assert files[0].parent.parent.name == "workflow"


def test_distill_expands_index_lines(tmp_path):
    """v1.0.4 索引行展开：memory_main.md 只有索引行时 distill 仍能经 file:/// 链接
    读到正文并提取 is_lesson=true 条目（对抗审查 H1 修复的回归测试）。"""
    # 构造正文文件（write_project block 格式）
    body_dir = tmp_path / "memory_rj" / "pitfall" / "202608"
    body_dir.mkdir(parents=True)
    body_file = body_dir / "lesson_task_memory_20260825_1200.md"
    body_file.write_text(
        "### 记忆条目 · lesson_task（2026-08-25 12:00）\n"
        "**重要性**: high\n"
        "**是否经验**: true\n"
        "**经验标签**: bugfix, sandbox\n"
        "**状态**: active\n\n"
        "沙箱拦截 mkstemp 的规避方案：open() 直写。\n",
        encoding="utf-8"
    )
    # 构造只有索引行的 memory_main.md
    memory_file = tmp_path / "memory_main.md"
    body_url = body_file.resolve().as_posix()
    memory_file.write_text(
        "# 主记忆\n\n## test_project\n\n"
        "- 2026-08-25 12:00 | lesson_task | pitfall | 重要性high | is_lesson=true | "
        "沙箱拦截 mkstemp 规避 | [正文](file:///%s)\n" % body_url,
        encoding="utf-8"
    )

    from memory_distill import distill
    result = distill(project_name="test_project", memory_file=str(memory_file))
    assert result["total_lessons"] == 1, "索引行应展开为正文条目并提取经验"
    assert result["lessons"][0]["title"] == "lesson_task"
    assert "沙箱拦截" in result["lessons"][0]["content"]
