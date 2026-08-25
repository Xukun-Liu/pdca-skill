"""memory_tags.py 单元测试（T001）：单点常量/校验函数/启发式推断。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from memory_tags import (  # noqa: E402
    FALLBACK_TAG,
    MEMORY_TAGS,
    TAG_PRIORITY,
    infer_memory_class,
    validate_memory_class,
)


class TestConstants:
    def test_memory_tags_six_values(self):
        assert MEMORY_TAGS == ["tech_solution", "pitfall", "workflow",
                               "tool_usage", "decision", "status"]

    def test_tag_priority_contains_all_tags(self):
        assert sorted(TAG_PRIORITY) == sorted(MEMORY_TAGS)

    def test_fallback_is_workflow(self):
        assert FALLBACK_TAG == "workflow"
        assert FALLBACK_TAG in MEMORY_TAGS


class TestValidate:
    def test_valid_six_tags(self):
        for tag in MEMORY_TAGS:
            assert validate_memory_class(tag) == tag

    def test_none_falls_back(self):
        assert validate_memory_class(None) == FALLBACK_TAG

    def test_empty_string_falls_back(self):
        assert validate_memory_class("") == FALLBACK_TAG
        assert validate_memory_class("   ") == FALLBACK_TAG

    def test_illegal_value_falls_back_with_warning(self, capsys):
        result = validate_memory_class("发布")
        assert result == FALLBACK_TAG
        err = capsys.readouterr().err
        assert "warning" in err and "发布" in err

    def test_case_normalized(self):
        assert validate_memory_class("Tech_Solution") == "tech_solution"
        assert validate_memory_class("  PITFALL  ") == "pitfall"

    def test_non_string_falls_back(self):
        assert validate_memory_class(123) == FALLBACK_TAG
        assert validate_memory_class(["pitfall"]) == FALLBACK_TAG


class TestInfer:
    def test_pitfall_keywords(self):
        assert infer_memory_class("这次踩坑了，报错不断") == "pitfall"
        assert infer_memory_class("任务失败后回滚") == "pitfall"

    def test_tech_solution_keywords(self):
        assert infer_memory_class("本方案采用分层架构设计") == "tech_solution"

    def test_status_keywords(self):
        assert infer_memory_class("阶段汇总：任务完成") == "status"

    def test_decision_keywords(self):
        assert infer_memory_class("拍板选定方案A") == "decision"

    def test_tool_usage_keywords(self):
        assert infer_memory_class("这个工具的安装命令是 pip") == "tool_usage"

    def test_no_hit_falls_back(self):
        assert infer_memory_class("随便一段没有关键词的文本") == FALLBACK_TAG

    def test_multi_hit_priority(self):
        # 同时命中 pitfall + status → 推断仲裁按特异度 pitfall 优先
        # （TAG_PRIORITY 的 status 优先仅用于显式分类冲突的人工仲裁，v1.0.4 修订）
        assert infer_memory_class("报错了但任务收尾") == "pitfall"

    def test_status_requires_specific_phrase(self):
        # 泛词"完成/状态"不再触发 status（迁移实测 81% 误归教训）
        assert infer_memory_class("这个功能开发完成了，用的是分层架构") == "tech_solution"
        assert infer_memory_class("阶段汇总：本周进展") == "status"

    def test_empty_content_falls_back(self):
        assert infer_memory_class("") == FALLBACK_TAG
        assert infer_memory_class(None) == FALLBACK_TAG
