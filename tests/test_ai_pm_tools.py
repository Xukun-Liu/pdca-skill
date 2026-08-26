"""test_ai_pm_tools.py - pdca-skill 7 个 AI PM 工具的测试。

文件用途
--------
对 7 个 scripts/ 工具脚本做单元/集成测试,
确保每个工具的核心公开函数行为符合预期,并在临时目录中隔离运行,
不污染项目真实文件。

测试覆盖(10 个测试函数覆盖 7 个工具 + 1 个综合集成测试)
------------------------------------------------------
1. link_indexer.py        → 2 个测试(basic_index + broken_and_reverse_link_detection)
2. check_skill_updates.py → 1 个测试(non_git_dir 降级)
3. devlog_sync.py         → 1 个测试(append_devlog 创建文件 + 文件头)
4. generate_host_rules.py → 1 个测试(dry_run 预览 + rules_count)
5. validate_global_files.py → 2 个测试(成功路径 + 错误路径)
6. route_check.py         → 1 个测试(orphan_references 检测)
7. protocol_align.py      → 1 个测试(detect_git_changed_files 非重复项)
8. 综合/集成测试          → 1 个(link_indexer.build_graph + validate_global_files.walk 协同)

设计原则
--------
- 每个测试独立,不依赖执行顺序
- 使用 pytest 标准 tmp_path fixture,不污染项目目录
- 用 importlib.util 动态导入 scripts/ 下的模块(scripts/ 不是 Python 包,无 __init__.py)
- 对 protocol 包不可用的场景,测试 _HAVE_PROTOCOL=False 时的降级行为或避开依赖项
- 验证函数返回值结构 + 关键字段,不写空 assert / skip / TBD
- 全中文注释,代码风格对齐 tests/test_negative_cases.py 与 tests/test_protocol_align.py

创建日期: 2026-07-21
任务编号: T29
"""
import importlib.util
from pathlib import Path

import pytest

# 项目根(SKILL.md 所在目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ===========================================================================
# 辅助函数:动态导入 scripts/ 下的模块
# ===========================================================================
def _import_script_module(module_name):
    """动态导入 scripts/{module_name}.py 模块。

    因为 scripts/ 不是 Python 包(无 __init__.py),用 importlib 直接按文件路径加载。
    每次调用返回新加载的模块对象,避免模块缓存干扰测试。

    Args:
        module_name: 模块名(不含 .py 后缀),如 'link_indexer'。

    Returns:
        Module 对象。

    Raises:
        FileNotFoundError: scripts/{module_name}.py 不存在。
    """
    module_path = _SCRIPTS_DIR / ("%s.py" % module_name)
    if not module_path.is_file():
        pytest.fail("待测脚本不存在: %s" % module_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ===========================================================================
# 1. link_indexer:基础索引测试
# ===========================================================================
def test_link_indexer_basic_index(tmp_path):
    """验证 link_indexer.scan_links 和 build_graph 的基础索引行为。

    测试逻辑:
    1. tmp_path 下创建 2 个 .md 文件 a.md / b.md,a.md 中链接到 b.md
    2. 调 scan_links(a.md) 验证返回 list[dict] 含 source/target/text/line_no
    3. 调 build_graph(tmp_path, max_depth=3) 验证返回 dict 含
       root/max_depth/nodes/edges/issues 5 个 keys
    4. nodes 应含 a.md 和 b.md(2 个文件)
    5. edges 至少 1 条(a.md → b.md)
    6. 因为 a→b 且 b 不→a,应检测出 missing_reverse_link(同目录)
    """
    link_indexer = _import_script_module("link_indexer")

    # 1. 创建测试文件
    a_md = tmp_path / "a.md"
    b_md = tmp_path / "b.md"
    a_md.write_text(
        "# A\n\n"
        "链接到 [B 文档](b.md) 在第 3 行。\n",
        encoding="utf-8"
    )
    b_md.write_text("# B\n\n本文件无外链。\n", encoding="utf-8")

    # 2. 测 scan_links
    links = link_indexer.scan_links(str(a_md))
    assert isinstance(links, list), f"scan_links 应返回 list,实际 {type(links)}"
    assert len(links) == 1, f"a.md 应有 1 条链接,实际 {len(links)}"
    link = links[0]
    assert set(link.keys()) == {"source", "target", "text", "line_no"}, (
        f"link dict keys 应为 source/target/text/line_no,实际 {set(link.keys())}"
    )
    assert link["target"] == "b.md", f"target 应为 b.md,实际 {link['target']}"
    assert link["text"] == "B 文档", f"text 应为 'B 文档',实际 {link['text']}"
    assert link["line_no"] == 3, f"line_no 应为 3,实际 {link['line_no']}"

    # 3-5. 测 build_graph
    graph = link_indexer.build_graph(str(tmp_path), max_depth=3)
    assert isinstance(graph, dict), f"build_graph 应返回 dict,实际 {type(graph)}"
    expected_keys = {"root", "max_depth", "nodes", "edges", "issues"}
    assert set(graph.keys()) == expected_keys, (
        f"graph keys 应为 {expected_keys},实际 {set(graph.keys())}"
    )
    assert graph["max_depth"] == 3, f"max_depth 应为 3,实际 {graph['max_depth']}"
    assert len(graph["nodes"]) == 2, (
        f"应扫到 2 个 .md 文件,实际 {len(graph['nodes'])}"
    )
    assert len(graph["edges"]) >= 1, (
        f"应至少 1 条 edge,实际 {len(graph['edges'])}"
    )

    # 6. a→b 但 b 不→a,应检测出 missing_reverse_link(同目录)
    reverse_issues = [i for i in graph["issues"]
                      if i.get("type") == "missing_reverse_link"]
    assert len(reverse_issues) >= 1, (
        "应检测出 missing_reverse_link(a→b 但 b 不→a),实际 issues: %s" % graph["issues"]
    )


# ===========================================================================
# 2. link_indexer:边界 case(broken_link + 空 + 跨目录不强制双向)
# ===========================================================================
def test_link_indexer_broken_and_reverse_link_detection(tmp_path):
    """验证 link_indexer 对 broken_link 和空文件的处理。

    测试逻辑:
    1. tmp_path 下创建 broken.md 引用不存在的 missing.md → 应检测出 broken_link
    2. 创建 empty.md(空文件) → scan_links 返回空 list []
    3. 创建 http.md 含 http/https 链接 → scan_links 排除外部 URL
    4. broken_link issue 应含 resolved 字段(解析后的绝对路径)
    """
    link_indexer = _import_script_module("link_indexer")

    # 1. broken.md 引用不存在的 missing.md
    (tmp_path / "broken.md").write_text(
        "# Broken\n\n链接到 [Missing](missing.md) 不存在。\n",
        encoding="utf-8"
    )
    # 2. empty.md 空文件
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    # 3. http.md 含 http/https 外部链接(应被排除)
    (tmp_path / "http.md").write_text(
        "# Http\n\n外部 [Google](https://google.com) 和 [MDN](http://developer.mozilla.org)。\n",
        encoding="utf-8"
    )

    # 验证 empty.md 扫描返回空 list
    empty_links = link_indexer.scan_links(str(tmp_path / "empty.md"))
    assert empty_links == [], f"空文件应返回空 list,实际 {empty_links}"

    # 验证 http.md 扫描排除外部 URL
    http_links = link_indexer.scan_links(str(tmp_path / "http.md"))
    assert http_links == [], (
        f"http/https 链接应被排除,实际 {http_links}"
    )

    # 验证 broken_link 检测
    graph = link_indexer.build_graph(str(tmp_path), max_depth=3)
    broken_issues = [i for i in graph["issues"]
                     if i.get("type") == "broken_link"]
    assert len(broken_issues) >= 1, (
        "应检测出 broken_link(引用 missing.md),实际 issues: %s" % graph["issues"]
    )
    broken = broken_issues[0]
    assert "resolved" in broken, (
        f"broken_link issue 应含 resolved 字段,实际 keys: {set(broken.keys())}"
    )
    assert broken["resolved"].endswith("missing.md"), (
        f"resolved 应指向 missing.md,实际 {broken['resolved']}"
    )


# ===========================================================================
# 3. check_skill_updates:非 git 目录降级
# ===========================================================================
def test_check_skill_updates_non_git_dir_returns_false(tmp_path, monkeypatch):
    """验证 check_skill_updates.check_updates 在非 git 目录的降级行为。

    测试逻辑:
    1. tmp_path 是非 git 仓库(无 .git 目录)
    2. 调 check_updates(tmp_path)
    3. 第一级 check_git_available 应返回 False
    4. check_updates 应返回 (False, 'not git')

    注: 这是测 4 级降级链的第一级降级(对齐脚本 docstring)。
    v1.0.4(实测报告 P1 git 上溯): 注入 GIT_CEILING_DIRECTORIES 天花板,
    防 tmp_path 恰位于上层真实仓库内部时 git rev-parse 向上误判/变慢;
    与 v1.0.4 check_git_available 的 --show-toplevel 根目录校验形成双保险。
    """
    check_skill_updates = _import_script_module("check_skill_updates")

    # v1.0.4: git 上溯天花板 = tmp_path 的父目录,禁止 rev-parse 越过 tmp_path 向上
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    # 确认 tmp_path 非 git 仓库
    assert not (tmp_path / ".git").exists(), "tmp_path 不应是 git 仓库"

    # 测第一级 check
    is_git = check_skill_updates.check_git_available(str(tmp_path))
    assert is_git is False, (
        f"非 git 目录 check_git_available 应 False,实际 {is_git}"
    )

    # 测主流程
    result = check_skill_updates.check_updates(str(tmp_path))
    assert isinstance(result, tuple), f"应返回 tuple,实际 {type(result)}"
    assert len(result) == 2, f"tuple 长度应为 2,实际 {len(result)}"
    is_up_to_date, reason = result
    assert is_up_to_date is False, (
        f"非 git 目录应返回 False,实际 {is_up_to_date}"
    )
    assert reason == "not git", (
        f"reason 应为 'not git',实际 {reason!r}"
    )


# ===========================================================================
# 4. devlog_sync:append_devlog 创建新文件 + 文件头
# ===========================================================================
def test_devlog_sync_append_devlog_creates_file_with_header(tmp_path):
    """验证 devlog_sync.append_devlog 在文件不存在时创建并写入文件头。

    测试逻辑:
    1. tmp_path/devlog.md 不存在
    2. 调 append_devlog(devlog_path, entry) 写入一条 entry
    3. 返回 dict 含 written=True 和 path
    4. 读文件验证含 '# Devlog' 文件头
    5. 读文件验证含 entry 的 title 和 actor
    6. 第二次调 append_devlog 追加 → 文件已有,written=True,文件头不重复写
    """
    devlog_sync = _import_script_module("devlog_sync")

    devlog_path = tmp_path / "devlog.md"
    entry = {
        "title": "T29 测试条目",
        "actor": "test_agent",
        "date": "2026-07-21",
        "time": "10:00",
        "stage": "do",
        "goal": "验证 append_devlog 行为",
        "action": "调 append_devlog 写入测试 entry",
        "result": "(预期)文件创建 + 文件头 + 内容",
        "conclusion": "",
        "next": "",
        "reflection": "",
        "files": "tests/test_ai_pm_tools.py",
    }

    # 1-3. 第一次写入(文件不存在 → 创建 + 写文件头)
    result1 = devlog_sync.append_devlog(str(devlog_path), entry)
    assert isinstance(result1, dict), f"应返回 dict,实际 {type(result1)}"
    assert result1["written"] is True, (
        f"第一次写入 written 应 True,实际 {result1['written']}"
    )
    assert result1["path"] == str(devlog_path.resolve()), (
        f"path 应为绝对路径,实际 {result1['path']}"
    )

    # 4-5. 验证文件内容
    content1 = devlog_path.read_text(encoding="utf-8")
    assert "# Devlog" in content1, "文件应含 '# Devlog' 文件头"
    assert "T29 测试条目" in content1, "文件应含 entry 的 title"
    assert "test_agent" in content1, "文件应含 actor"
    assert "2026-07-21" in content1, "文件应含 date"
    assert "Stage" in content1, "文件应含 Stage 元信息块"

    # 6. 第二次写入(文件已存在 → 追加,不重复写文件头)
    entry2 = dict(entry, title="T29 第二条")
    result2 = devlog_sync.append_devlog(str(devlog_path), entry2)
    assert result2["written"] is True, "第二次写入也应成功"

    content2 = devlog_path.read_text(encoding="utf-8")
    # 文件头只出现一次(用 count 验证)
    assert content2.count("# Devlog\n") == 1, (
        "文件头应只出现 1 次,实际出现 %d 次" % content2.count("# Devlog\n")
    )
    assert "T29 测试条目" in content2, "应保留第一次条目"
    assert "T29 第二条" in content2, "应含第二次条目"


# ===========================================================================
# 5. generate_host_rules:dry-run 预览 index.md
# ===========================================================================
def test_generate_host_rules_dry_run_preview(tmp_path):
    """验证 generate_host_rules.generate_host_rules 的 dry-run 模式。

    测试逻辑:
    1. tmp_path 下创建 references/ + 2 个 .md 文件(含 `# 标题`)
    2. 调 generate_host_rules(tmp_path, dry_run=True)
    3. 返回 dict 含 generated=False, rules_count=2, preview 字段
    4. preview 含表格表头 '| 文件 | 规则名 |' 和提取的标题
    5. 验证不实际创建 docs/rules/index.md(dry-run 不写盘)
    6. 再调一次 dry_run=False → 实际生成 index.md,generated=True
    """
    gen_host_rules = _import_script_module("generate_host_rules")

    # 1. 创建 references/ + 2 个 .md
    ref_dir = tmp_path / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "rule_a.md").write_text(
        "# 规则 A\n\n规则 A 正文。\n", encoding="utf-8"
    )
    (ref_dir / "rule_b.md").write_text(
        "# 规则 B 标题\n\n规则 B 正文。\n", encoding="utf-8"
    )

    # 2-3. dry-run 调用
    result = gen_host_rules.generate_host_rules(str(tmp_path), dry_run=True)
    assert isinstance(result, dict), f"应返回 dict,实际 {type(result)}"
    assert result["generated"] is False, (
        f"dry-run 时 generated 应 False,实际 {result['generated']}"
    )
    assert result["rules_count"] == 2, (
        f"rules_count 应为 2,实际 {result['rules_count']}"
    )
    assert "preview" in result, "dry-run 结果应含 preview 字段"

    # 4. 验证 preview 内容
    preview = result["preview"]
    assert "| 文件 | 规则名 |" in preview, "preview 应含表头"
    assert "规则 A" in preview, "preview 应含规则 A 标题"
    assert "规则 B 标题" in preview, "preview 应含规则 B 标题"
    assert "rule_a.md" in preview, "preview 应含 rule_a.md 文件名"
    assert "rule_b.md" in preview, "preview 应含 rule_b.md 文件名"

    # 5. dry-run 不应创建 index.md
    index_path = tmp_path / "docs" / "rules" / "index.md"
    assert not index_path.exists(), "dry-run 不应创建 index.md"

    # 6. 实际生成
    result_real = gen_host_rules.generate_host_rules(str(tmp_path), dry_run=False)
    assert result_real["generated"] is True, (
        f"实际生成时 generated 应 True,实际 {result_real['generated']}"
    )
    assert index_path.exists(), "实际生成后 index.md 应存在"
    content = index_path.read_text(encoding="utf-8")
    assert "规则 A" in content, "index.md 应含规则 A"
    assert "规则 B 标题" in content, "index.md 应含规则 B"


# ===========================================================================
# 6. validate_global_files:成功路径(required 字段齐全)
# ===========================================================================
def test_validate_file_against_contract_passes_when_required_present(tmp_path):
    """验证 validate_file_against_contract 在 required 字段齐全时通过。

    测试逻辑:
    1. 创建 md 文件含 `**Task**: xxx` 和 `**Timestamp**: 2026-07-21` 两个字段
    2. 构造 contract dict 含 required 字段 'task' / 'timestamp'
    3. 调 validate_file_against_contract
    4. 验证返回 passed=True, missing_fields=[], found_fields 含 task/timestamp
    """
    validate_global_files = _import_script_module("validate_global_files")

    # 1. 创建 md 文件(含 2 个 required 字段)
    md_file = tmp_path / "sample.md"
    md_file.write_text(
        "# Sample\n\n"
        "**Task**: 完成测试任务\n\n"
        "**Timestamp**: 2026-07-21 10:00\n\n"
        "正文内容。\n",
        encoding="utf-8"
    )

    # 2. 构造 contract(只验证 required 字段)
    contract = {
        "required_when": "always",
        "fields": {
            "task": {"level": "required", "source": "file"},
            "timestamp": {"level": "required", "source": "file"},
            "optional_note": {"level": "optional", "source": "file"},
        },
    }

    # 3. 调被测函数
    result = validate_global_files.validate_file_against_contract(
        str(md_file), contract
    )

    # 4. 断言
    assert isinstance(result, dict), f"应返回 dict,实际 {type(result)}"
    assert result["passed"] is True, (
        f"required 齐全应 passed=True,实际 {result['passed']}"
    )
    assert result["missing_fields"] == [], (
        f"missing_fields 应为空,实际 {result['missing_fields']}"
    )
    assert "task" in result["found_fields"], (
        f"found_fields 应含 task,实际 {result['found_fields']}"
    )
    assert "timestamp" in result["found_fields"], (
        f"found_fields 应含 timestamp,实际 {result['found_fields']}"
    )
    # optional 字段不验证,不出现在 found/missing
    assert "optional_note" not in result["found_fields"], (
        "optional 字段不应在 found_fields 中"
    )


# ===========================================================================
# 7. validate_global_files:错误路径(required 字段缺失)
# ===========================================================================
def test_validate_file_against_contract_fails_when_required_missing(tmp_path):
    """验证 validate_file_against_contract 在 required 字段缺失时失败。

    测试逻辑:
    1. 创建 md 文件只含 `**Task**: xxx`(缺 timestamp)
    2. 同样 contract(required: task + timestamp)
    3. 调 validate_file_against_contract
    4. 验证 passed=False, missing_fields=['timestamp'], found_fields=['task']

    额外验证:对空文件(读取失败),应 passed=False 含 reason 字段
    """
    validate_global_files = _import_script_module("validate_global_files")

    # 1. 创建 md 文件(只含 task,缺 timestamp)
    md_file = tmp_path / "incomplete.md"
    md_file.write_text(
        "# Incomplete\n\n"
        "**Task**: 缺 timestamp 的任务\n\n",
        encoding="utf-8"
    )

    # 2. 同样 contract
    contract = {
        "required_when": "always",
        "fields": {
            "task": {"level": "required", "source": "file"},
            "timestamp": {"level": "required", "source": "file"},
        },
    }

    # 3. 调被测函数
    result = validate_global_files.validate_file_against_contract(
        str(md_file), contract
    )

    # 4. 断言错误路径
    assert isinstance(result, dict), f"应返回 dict,实际 {type(result)}"
    assert result["passed"] is False, (
        f"缺 required 应 passed=False,实际 {result['passed']}"
    )
    assert "timestamp" in result["missing_fields"], (
        f"missing_fields 应含 timestamp,实际 {result['missing_fields']}"
    )
    assert "task" in result["found_fields"], (
        f"found_fields 应含 task,实际 {result['found_fields']}"
    )
    assert "timestamp" not in result["found_fields"], (
        "timestamp 缺失,不应在 found_fields 中"
    )

    # 额外:空文件读取失败场景
    empty_file = tmp_path / "empty.md"
    empty_file.write_text("", encoding="utf-8")
    empty_result = validate_global_files.validate_file_against_contract(
        str(empty_file), contract
    )
    assert empty_result["passed"] is False, "空文件应 passed=False"
    assert "reason" in empty_result, "空文件应附 reason 字段说明原因"


# ===========================================================================
# 8. route_check:orphan_references 检测
# ===========================================================================
def test_route_check_orphan_references_detects_unreferenced(tmp_path):
    """验证 route_check.check_orphan_references 检测孤儿引用。

    测试逻辑:
    1. tmp_path 下创建 references/ + 2 个 .md 文件
       - referenced.md:在 SKILL.md 中被引用(非孤儿)
       - orphan.md:不被任何 .md 文件引用(孤儿)
    2. 创建 SKILL.md 含 `references/referenced.md` 引用字符串
    3. 调 check_orphan_references(tmp_path)
    4. 验证 passed=False, issues 含 orphan.md,不含 referenced.md
    """
    route_check = _import_script_module("route_check")

    # 1. 创建 references/ + 2 个 .md
    ref_dir = tmp_path / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "referenced.md").write_text(
        "# Referenced\n\n被 SKILL.md 引用。\n", encoding="utf-8"
    )
    (ref_dir / "orphan.md").write_text(
        "# Orphan\n\n孤儿文件,无人引用。\n", encoding="utf-8"
    )

    # 2. 创建 SKILL.md 含 referenced.md 的引用字符串
    (tmp_path / "SKILL.md").write_text(
        "# Skill\n\n"
        "本 skill 引用了 [Referenced](references/referenced.md)。\n",
        encoding="utf-8"
    )

    # 3. 调被测函数
    result = route_check.check_orphan_references(str(tmp_path))
    assert isinstance(result, dict), f"应返回 dict,实际 {type(result)}"
    expected_keys = {"passed", "detail", "issues"}
    assert set(result.keys()) == expected_keys, (
        f"返回 keys 应为 {expected_keys},实际 {set(result.keys())}"
    )

    # 4. 验证孤儿检测
    assert result["passed"] is False, (
        f"有孤儿文件应 passed=False,实际 {result['passed']}"
    )
    orphan_files_in_issues = [
        i.get("file", "") for i in result["issues"]
    ]
    assert any("orphan.md" in f for f in orphan_files_in_issues), (
        f"issues 应含 orphan.md,实际 {orphan_files_in_issues}"
    )
    assert not any("referenced.md" in f for f in orphan_files_in_issues), (
        f"issues 不应含 referenced.md(已被引用),实际 {orphan_files_in_issues}"
    )


# ===========================================================================
# 9. protocol_align:detect_git_changed_files 非重复项
# ===========================================================================
def test_protocol_align_detect_git_changed_files_non_git_dir(tmp_path):
    """验证 protocol_align.detect_git_changed_files 在非 git 目录降级返回空 list。

    测试逻辑:
    1. tmp_path 是非 git 仓库
    2. 调 detect_git_changed_files(tmp_path)
    3. 验证返回空 list [](降级,不抛异常)

    注: 本测试避开 tests/test_protocol_align.py 已覆盖的 3 个函数
    (extract_traceability_sources / check_alignment),
    改测 detect_git_changed_files 这一独立工具函数(脚本中第 3 个公开函数)。
    """
    protocol_align = _import_script_module("protocol_align")

    # 确认 tmp_path 非 git 仓库
    assert not (tmp_path / ".git").exists(), "tmp_path 不应是 git 仓库"

    # 调被测函数(默认 timeout=10s)
    result = protocol_align.detect_git_changed_files(str(tmp_path))
    assert isinstance(result, list), (
        f"应返回 list(即使降级),实际 {type(result)}"
    )
    assert result == [], (
        f"非 git 目录应降级返回空 list,实际 {result}"
    )

    # 额外验证:对不存在的目录也应降级返回空 list(不抛异常)
    nonexistent = tmp_path / "does_not_exist"
    result2 = protocol_align.detect_git_changed_files(str(nonexistent))
    assert isinstance(result2, list), (
        f"不存在的目录应返回 list,实际 {type(result2)}"
    )
    assert result2 == [], (
        f"不存在的目录应返回空 list,实际 {result2}"
    )


# ===========================================================================
# 10. 综合/集成测试:link_indexer.build_graph + validate_global_files.walk_markdown_files 协同
# ===========================================================================
def test_integration_link_indexer_walk_and_validate_walk(tmp_path):
    """验证 link_indexer.build_graph 和 validate_global_files.walk_markdown_files 协同。

    综合测试:两个工具各自独立扫描 .md 文件,结果应一致。

    测试逻辑:
    1. tmp_path 下构造最小项目结构:
       - SKILL.md(根)
       - docs_rj/a.md(子目录)
       - docs_rj/sub/b.md(孙目录,深度 2)
       - docs_rj/sub/deeper/c.md(深度 3,在 max_depth=3 范围内)
    2. 调 link_indexer.build_graph(tmp_path, max_depth=3)
    3. 调 validate_global_files.walk_markdown_files(tmp_path, max_depth=3)
    4. 两者返回的 .md 文件集合应一致(都含 4 个 .md 文件)
    5. build_graph 的 edges 中,SKILL.md 应有指向 docs_rj/a.md 的链接
       (验证 link_indexer 能正确处理跨目录链接)
    6. walk_markdown_files 返回的路径都是绝对路径(规范一致性)
    """
    link_indexer = _import_script_module("link_indexer")
    validate_global_files = _import_script_module("validate_global_files")

    # 1. 构造测试结构
    (tmp_path / "SKILL.md").write_text(
        "# Skill\n\n"
        "链接到 [A](docs_rj/a.md)。\n",
        encoding="utf-8"
    )
    docs_dir = tmp_path / "docs_rj"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "a.md").write_text(
        "# A\n\n链接到 [B](sub/b.md)。\n", encoding="utf-8"
    )
    sub_dir = docs_dir / "sub"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "b.md").write_text(
        "# B\n\n链接回 [A](../a.md)。\n", encoding="utf-8"
    )
    deeper_dir = sub_dir / "deeper"
    deeper_dir.mkdir(parents=True, exist_ok=True)
    (deeper_dir / "c.md").write_text(
        "# C\n\n深度 3 的文件。\n", encoding="utf-8"
    )

    # 2. 调 link_indexer.build_graph
    graph = link_indexer.build_graph(str(tmp_path), max_depth=3)
    # build_graph 用绝对路径
    link_indexer_files = set(Path(p).name for p in graph["nodes"])

    # 3. 调 validate_global_files.walk_markdown_files
    walked = validate_global_files.walk_markdown_files(str(tmp_path), max_depth=3)
    walked_files = set(Path(p).name for p in walked)

    # 4. 两者扫到的文件集合应一致(都含 SKILL.md / a.md / b.md / c.md)
    expected_files = {"SKILL.md", "a.md", "b.md", "c.md"}
    assert link_indexer_files == expected_files, (
        f"link_indexer 应扫到 {expected_files},实际 {link_indexer_files}"
    )
    assert walked_files == expected_files, (
        f"walk_markdown_files 应扫到 {expected_files},实际 {walked_files}"
    )
    assert link_indexer_files == walked_files, (
        "两个工具扫到的 .md 文件集合应一致"
    )

    # 5. build_graph 的 edges 中,SKILL.md 应有指向 docs_rj/a.md 的链接
    skill_edges = [e for e in graph["edges"]
                   if Path(e["source"]).name == "SKILL.md"]
    assert len(skill_edges) >= 1, (
        f"SKILL.md 应至少 1 条 edge,实际 {skill_edges}"
    )
    # 验证 link_indexer 能正确处理跨目录链接(target 字段保留原始 markdown 写法)
    assert any(e["target"] == "docs_rj/a.md" for e in skill_edges), (
        f"SKILL.md 应有指向 docs_rj/a.md 的 edge,实际 {skill_edges}"
    )

    # 6. walk_markdown_files 返回的路径都是绝对路径
    for p in walked:
        assert Path(p).is_absolute(), (
            f"walk_markdown_files 应返回绝对路径,实际 {p}"
        )
