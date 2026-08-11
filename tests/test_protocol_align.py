"""test_protocol_align.py - pdca-skill 协议对齐脚本测试。

测试对象: scripts/protocol_align.py（325 行）
3 个测试函数:
1. test_extract_traceability_sources_returns_valid_dict
   验证含 traceability docstring 的文件能正确提取来源
2. test_extract_traceability_sources_handles_missing_docstring
   验证无 docstring 的文件返回空 list
3. test_check_alignment_returns_correct_structure
   验证 check_alignment 返回结构正确（含 aligned / orphan 两种文件）

设计原则:
- 纯 Python 标准库,零外部依赖
- 使用 pytest 标准 tmp_path fixture（不依赖 tmp_skill_dir）
- 测试函数名精确匹配 T17 任务清单要求
- 全中文注释,代码风格与 test_negative_cases.py 一致

重要说明（与任务原始假设的差异,按任务要求 4「以实际为准」调整）:
- extract_traceability_sources 实际返回 list[str]（不是 dict）;
  章节标记 §xxx / #xxx 会被正则截掉,只保留纯路径
- check_alignment 实际返回 dict 含 keys: 'passed' / 'detail' / 'issues'
  （不是 checked / aligned / misaligned / details）
  其中 'issues' 是无根文件列表,长度 = 无根文件数
"""
import importlib.util
from pathlib import Path

import pytest

# 项目根(SKILL.md 所在目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def _import_protocol_align():
    """辅助函数: 动态导入 scripts/protocol_align.py 模块。

    因为 scripts/ 不是 Python 包(无 __init__.py),用 importlib 直接加载文件。
    每次调用返回新加载的模块对象,避免模块缓存干扰测试。

    Returns:
        Module 对象（含 extract_traceability_sources / check_alignment 等）
    """
    module_path = _SCRIPTS_DIR / "protocol_align.py"
    spec = importlib.util.spec_from_file_location("protocol_align", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_traceability_sources_returns_valid_dict(tmp_path):
    """验证 extract_traceability_sources 能从 docstring 提取设计来源。

    测试逻辑:
    1. 创建临时 .py 文件,docstring 中含
       `设计来源: SKILL.md §0, references/common/pa/trigger_hooks.md`
    2. 调用 extract_traceability_sources 读取该文件
    3. 断言返回的 list 含 'SKILL.md' 和 'references/common/pa/trigger_hooks.md'
       （章节标记 §0 被正则截掉,只保留纯路径）

    注: 实际函数返回 list[str]（去重保序）,不是 dict;
    章节标记 §xxx 会被截掉。函数名保留任务原始命名(精确匹配要求)。
    """
    protocol_align = _import_protocol_align()

    # 创建含 traceability docstring 的临时 .py 文件
    py_file = tmp_path / "has_traceability.py"
    py_file.write_text(
        '"""\n'
        'test_module - 测试模块。\n'
        '\n'
        '设计来源: SKILL.md §0, references/common/pa/trigger_hooks.md\n'
        '"""\n'
        'x = 1\n',
        encoding="utf-8"
    )

    # 调用被测函数
    result = protocol_align.extract_traceability_sources(str(py_file))

    # 断言返回 list 且含预期来源(章节标记 §0 被截掉)
    assert isinstance(result, list), f"应返回 list,实际 {type(result)}"
    assert "SKILL.md" in result, f"应含 SKILL.md,实际 {result}"
    assert "references/common/pa/trigger_hooks.md" in result, (
        f"应含 references/common/pa/trigger_hooks.md,实际 {result}"
    )


def test_extract_traceability_sources_handles_missing_docstring(tmp_path):
    """验证 extract_traceability_sources 对无 docstring 文件返回空 list。

    测试逻辑:
    1. 创建临时 .py 文件,不含任何 docstring(纯代码 `x = 1`)
    2. 调用 extract_traceability_sources
    3. 断言返回空 list []

    注: 实际函数对读取失败/无匹配行都返回空 list([]),不是 dict。
    """
    protocol_align = _import_protocol_align()

    # 创建无 docstring 的临时 .py 文件
    py_file = tmp_path / "no_docstring.py"
    py_file.write_text(
        'x = 1\n',
        encoding="utf-8"
    )

    # 调用被测函数
    result = protocol_align.extract_traceability_sources(str(py_file))

    # 断言返回空 list
    assert isinstance(result, list), f"应返回 list,实际 {type(result)}"
    assert result == [], f"无 docstring 应返回空 list,实际 {result}"


def test_check_alignment_returns_correct_structure(tmp_path):
    """验证 check_alignment 返回结构正确。

    测试逻辑:
    1. 在 tmp_path 下创建 protocol/ 子目录
    2. 在 protocol/ 下创建 2 个 .py 文件:
       - aligned.py: 含 traceability docstring
         (设计来源: SKILL.md §0, references/common/pa/trigger_hooks.md)
       - orphan.py: 不含 docstring(协议无根)
    3. 调用 check_alignment(skill_dir=tmp_path)
    4. 断言返回 dict 含 keys: 'passed' / 'detail' / 'issues'
    5. 断言 'passed' == False(因为 orphan.py 协议无根)
    6. 断言 'issues' 是 list 且 len == 1(只 orphan.py 一个无根)
    7. 额外验证: issue 中含 'orphan.py' 文件名

    注: 实际返回 dict keys 是 'passed' / 'detail' / 'issues'
    (不是任务假设的 checked / aligned / misaligned / details)。
    按任务要求 4「以实际为准」调整断言:
    - 用 'passed' == False 代替 'misaligned' == 1
    - 用 len('issues') == 1 代替 'misaligned' == 1
    - 用 len(扫描文件) == 2 通过创建 2 个文件隐式验证(issues 只列无根的)
    """
    protocol_align = _import_protocol_align()

    # 1. 创建 protocol/ 子目录
    protocol_dir = tmp_path / "protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)

    # 2. 创建 2 个 .py 文件
    # aligned.py: 含 traceability docstring(协议有根)
    (protocol_dir / "aligned.py").write_text(
        '"""\n'
        'aligned - 含反向链的模块。\n'
        '\n'
        '设计来源: SKILL.md §0, references/common/pa/trigger_hooks.md\n'
        '"""\n'
        'VALUE = 1\n',
        encoding="utf-8"
    )
    # orphan.py: 不含 docstring(协议无根)
    (protocol_dir / "orphan.py").write_text(
        'VALUE = 2\n',
        encoding="utf-8"
    )

    # 3. 调用被测函数
    result = protocol_align.check_alignment(str(tmp_path))

    # 4. 断言返回 dict 含预期 keys(以实际为准)
    assert isinstance(result, dict), f"应返回 dict,实际 {type(result)}"
    expected_keys = {"passed", "detail", "issues"}
    assert set(result.keys()) == expected_keys, (
        f"返回 dict keys 应为 {expected_keys},实际 {set(result.keys())}"
    )

    # 5. 断言 passed == False(有 1 个无根文件 orphan.py)
    assert result["passed"] is False, (
        f"有 1 个无根文件,passed 应为 False,实际 {result['passed']}"
    )

    # 6. 断言 issues 是 list 且 len == 1(只 orphan.py 一个无根)
    assert isinstance(result["issues"], list), (
        f"issues 应为 list,实际 {type(result['issues'])}"
    )
    assert len(result["issues"]) == 1, (
        f"应只有 1 个无根文件 issue,实际 {len(result['issues'])}"
    )

    # 7. 额外验证: issue 中的文件名正确(指向 orphan.py)
    issue = result["issues"][0]
    assert isinstance(issue, dict), f"issue 应为 dict,实际 {type(issue)}"
    assert "orphan.py" in issue.get("file", ""), (
        f"issue file 应含 orphan.py,实际 {issue}"
    )

    # 8. 额外验证: detail 字段是字符串(含描述信息)
    assert isinstance(result["detail"], str), (
        f"detail 应为 str,实际 {type(result['detail'])}"
    )
    assert len(result["detail"]) > 0, "detail 不应为空字符串"
