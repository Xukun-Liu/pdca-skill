"""test_negative_cases.py - pdca-skill 负向测试。

3 个负向断言:
1. test_no_circular_imports: protocol/ 包无循环 import
2. test_no_personal_paths: 项目源码无硬编码个人路径(C:\\Users\\xxx)
3. test_no_dead_references: SKILL.md 引用的关键文件确实存在

设计原则:
- 负向测试 = "不应该出现 X"
- 失败立即给出具体位置(哪个文件哪一行)
- 纯 Python 标准库
"""
import os
import sys
import re
from pathlib import Path

import pytest

# 项目根(SKILL.md 所在目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_no_circular_imports():
    """验证 protocol/ 包导入不产生循环依赖。

    实现方式:
    - 临时把项目根加入 sys.path
    - import protocol
    - 验证所有子模块可独立导入
    - 无 RecursionError 即通过

    失败原因:
    - 模块 A 导入模块 B,B 又导入 A → RecursionError
    - 缺少 __init__.py → ImportError
    """
    skill_root = str(PROJECT_ROOT)
    if skill_root not in sys.path:
        sys.path.insert(0, skill_root)
    try:
        # 清理可能残留的 protocol 缓存
        for mod_name in list(sys.modules.keys()):
            if mod_name == "protocol" or mod_name.startswith("protocol."):
                del sys.modules[mod_name]

        # 触发导入
        import protocol  # noqa: F401
        from protocol import (  # noqa: F401
            IRON_RULE_IDS, HARD_GATE_TRI_STATES, STAGE_IDS, FIELD_LEVELS,
            FIELD_SOURCES, FILE_ROLES, FIELD_CONTRACTS,
            STAGE_DECISION_RULES, GLOBAL_COMPANION_ABILITIES,
            ROUTE_TARGETS, GATE_STATES, ARBITRATION_RULES,
            VALIDATION_POLICY, COMMON_SECTIONS, MARKDOWN_TEMPLATES,
            CHANGE_IMPACT_MAP, get_impacted_files,
        )

        # 关键符号非空
        assert len(IRON_RULE_IDS) == 8, f"IRON_RULE_IDS 应有 8 条,实际 {len(IRON_RULE_IDS)}"
        assert len(STAGE_IDS) == 4, f"STAGE_IDS 应有 4 环,实际 {len(STAGE_IDS)}"
        assert len(FILE_ROLES) == 10, f"FILE_ROLES 应有 10 角色,实际 {len(FILE_ROLES)}"

    except RecursionError as e:
        pytest.fail(f"protocol/ 包存在循环 import: {e}")
    except ImportError as e:
        pytest.fail(f"protocol/ 包导入失败: {e}")
    finally:
        # 不清理 sys.path(其他测试可能也用),只清理模块缓存
        for mod_name in list(sys.modules.keys()):
            if mod_name == "protocol" or mod_name.startswith("protocol."):
                del sys.modules[mod_name]


def test_no_personal_paths():
    """验证 Python 源码不硬编码个人路径。

    检测范围:仅 .py 文件(scripts/*.py + protocol/*.py + tests/*.py)
    检测模式:C:\\Users\\<name>  (个人 Windows 用户目录)

    设计原则:
    - 只检测 .py 源码(可执行逻辑,硬编码 = bug)
    - 不检测 .md 文档(用户画像/示例路径合法)
    - 白名单:protocol/validation.py 的 stale_patterns(故意列出做检测器)

    .md 文件中的示例路径应为 /path/to/... 形式,不应有真实用户路径。
    """
    patterns_to_scan = []
    for dir_name in ["scripts", "protocol", "tests"]:
        d = PROJECT_ROOT / dir_name
        if d.exists():
            patterns_to_scan.extend(d.glob("**/*.py"))

    # 个人路径正则(匹配 C:\Users\xxx 或 C:\\Users\\xxx)
    personal_re = re.compile(r'C:\\\\?Users\\\\?[A-Za-z0-9_\-]+')

    # 白名单:允许出现个人路径的文件(这些是检测器)
    whitelist_files = {
        "protocol/validation.py",  # stale_patterns 检测器
        "tests/test_negative_cases.py",  # 本测试文件
        "scripts/validate_skill.py",  # INT-04 stale_patterns 检测器(规则定义本身,非硬编码 bug)
    }

    violations = []
    for fpath in patterns_to_scan:
        try:
            rel = fpath.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            continue

        if rel in whitelist_files:
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception:
            continue

        for i, line in enumerate(content.splitlines(), start=1):
            # 跳过注释行
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue

            m = personal_re.search(line)
            if m:
                violations.append(f"{rel}:{i}: {line.strip()}")

    if violations:
        pytest.fail(
            "发现硬编码个人路径(应改用相对路径或环境变量):\n" +
            "\n".join(violations)
        )


def test_no_dead_references():
    """验证 SKILL.md 引用的关键文件确实存在。

    检测范围:SKILL.md 中所有 [text](path) 形式的相对路径引用,
    但只检测指向项目真实目录的链接:
    - references/xxx.md
    - assets/xxx.md
    - scripts/xxx.py
    - docs_rj/xxx.md
    - memory/xxx.md
    - HISTORY.md / README.md / SKILL.md 等顶级文件

    跳过(不算死链):
    - 外部 URL(http/https/mailto/#)
    - file:// 协议(示例链接)
    - 含占位符/通配符的模板链接({task}/{date}/* /< >/ 等)
    - 文档示例链接(链接文字含"文件名"或链接目标是"相对路径")
    - 不指向已知目录的链接(纯文件名如 summary_view.md 可能是文档内引用示例)
    """
    skill_path = PROJECT_ROOT / "SKILL.md"
    if not skill_path.exists():
        pytest.skip("SKILL.md 不存在(可能在 tmp_skill_dir fixture 中)")

    content = skill_path.read_text(encoding="utf-8")

    # 真实目录前缀(只有这些目录的链接才检测)
    real_dir_prefixes = (
        "references/", "assets/", "scripts/", "docs_rj/",
        "memory/", "tests/", "protocol/",
    )
    # 顶级真实文件(检测这些文件名的链接)
    real_top_files = {"HISTORY.md", "README.md", "SKILL.md"}

    # 匹配 markdown 链接 [text](path)
    link_re = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    dead = []
    for m in link_re.finditer(content):
        link_text = m.group(1)
        link_target = m.group(2).strip()

        # 跳过外部 URL
        if link_target.startswith(("http://", "https://", "mailto:", "#", "file://")):
            continue

        # 跳过含占位符/通配符的模板链接
        if any(p in link_target for p in ["{", "}", "*", "<", ">"]):
            continue

        # 跳过文档示例链接(明显占位)
        if "相对路径" in link_target or link_text == "文件名":
            continue

        # 取路径部分(去掉 #anchor)
        path_str = link_target.split("#")[0].split("?")[0]
        if not path_str:
            continue

        # 只检测指向真实目录的链接(跳过纯文件名等文档内引用)
        is_real_dir_link = any(path_str.startswith(p) or
                                path_str.startswith("./" + p) or
                                path_str.startswith("../" + p)
                                for p in real_dir_prefixes)
        is_top_file = path_str in real_top_files
        if not is_real_dir_link and not is_top_file:
            continue

        # 解析相对路径(相对 SKILL.md 所在目录)
        target_path = (PROJECT_ROOT / path_str).resolve()
        if not target_path.exists():
            dead.append(f"[{link_text}]({link_target}) → {target_path}")

    if dead:
        pytest.fail(
            f"SKILL.md 存在 {len(dead)} 个死引用:\n" +
            "\n".join(dead)
        )


# 额外的导入性测试(轻量,不依赖 fixture)
def test_protocol_importable_without_errors():
    """protocol/ 包应可独立导入,不抛异常。"""
    skill_root = str(PROJECT_ROOT)
    if skill_root not in sys.path:
        sys.path.insert(0, skill_root)
    try:
        import protocol  # noqa: F401
        assert hasattr(protocol, "FILE_ROLES")
        assert hasattr(protocol, "IRON_RULE_IDS")
        assert hasattr(protocol, "get_impacted_files")
    finally:
        for mod_name in list(sys.modules.keys()):
            if mod_name == "protocol" or mod_name.startswith("protocol."):
                del sys.modules[mod_name]
