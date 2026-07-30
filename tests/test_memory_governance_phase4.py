# -*- coding: utf-8 -*-
"""记忆治理体系 3-R 阶段4 测试：rethink + 自动蒸馏

覆盖：
- T019: memory_rethink（LLM 重评建议）
- T020: handoff_tidy 自动触发 distill
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import user_data_path
import memory_shadow_write
import learn_tidy


class _DummyLock:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


def _setup_memory_with_entries(monkeypatch, tmp_path, entries):
    """构造 memory_main.md，entries 是 list of dict"""
    monkeypatch.setenv("RIJI_DATA_DIR", str(tmp_path))
    import generate_docs
    monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
    fake_global = str(tmp_path / "memory" / "memory_main.md")
    os.makedirs(os.path.dirname(fake_global), exist_ok=True)
    content = "# 主记忆\n\n## test_project\n\n"
    for e in entries:
        content += "### 记忆条目 · %s（%s）\n**重要性**: %s\n**是否经验**: %s\n**经验标签**: %s\n%s\n\n" % (
            e['task'], e['ts'], e['importance'], str(e.get('is_lesson', False)).lower(),
            e.get('tags', '无'), e.get('content', '内容')
        )
    with open(fake_global, "w", encoding="utf-8") as f:
        f.write(content)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", fake_global)
    monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_DIR", os.path.dirname(fake_global))
    return fake_global


# T019: memory_rethink
class TestMemoryRethink:
    def test_rethink_stale_scope(self, monkeypatch, tmp_path):
        """stale 范围应识别超 90 天的条目"""
        old_ts = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d %H:%M')
        _setup_memory_with_entries(monkeypatch, tmp_path, [
            {'task': 'old_task', 'ts': old_ts, 'importance': 'low', 'content': '老条目'},
        ])
        result = learn_tidy.memory_rethink(project_name='test_project', scope='stale')
        assert result['total_scanned'] == 1
        assert result['total_suggestions'] == 1
        assert result['suggestions'][0]['suggestion'] == 'archive'
        assert '超 90 天' in result['suggestions'][0]['reason']

    def test_rethink_stale_high_importance_keep(self, monkeypatch, tmp_path):
        """stale + importance=high 应建议保留"""
        old_ts = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d %H:%M')
        _setup_memory_with_entries(monkeypatch, tmp_path, [
            {'task': 'old_high', 'ts': old_ts, 'importance': 'high', 'content': '老但重要'},
        ])
        result = learn_tidy.memory_rethink(project_name='test_project', scope='stale')
        assert result['suggestions'][0]['suggestion'] == 'keep'

    def test_rethink_low_scope(self, monkeypatch, tmp_path):
        """low 范围应识别 importance=low"""
        _setup_memory_with_entries(monkeypatch, tmp_path, [
            {'task': 'low_task', 'ts': '2026-07-30 14:35', 'importance': 'low', 'content': '低重要'},
        ])
        result = learn_tidy.memory_rethink(project_name='test_project', scope='low')
        assert result['total_suggestions'] == 1
        assert result['suggestions'][0]['suggestion'] == 'archive'

    def test_rethink_no_memory_main(self, monkeypatch, tmp_path):
        """memory_main 不存在应返回空"""
        monkeypatch.setenv("RIJI_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(memory_shadow_write, "GLOBAL_MEMORY_FILE", str(tmp_path / "nonexistent.md"))
        result = learn_tidy.memory_rethink(project_name='test_project')
        assert result['total_scanned'] == 0
        assert result['total_suggestions'] == 0

    def test_rethink_all_scope(self, monkeypatch, tmp_path):
        """all 范围应扫描全部"""
        _setup_memory_with_entries(monkeypatch, tmp_path, [
            {'task': 'task1', 'ts': '2026-07-30 14:35', 'importance': 'high', 'content': '内容1'},
            {'task': 'task2', 'ts': '2026-07-30 14:35', 'importance': 'low', 'content': '内容2'},
        ])
        result = learn_tidy.memory_rethink(project_name='test_project', scope='all')
        assert result['total_scanned'] == 2
        assert result['total_suggestions'] == 2
        # all 模式默认建议 keep
        for s in result['suggestions']:
            assert s['suggestion'] == 'keep'

    def test_rethink_by_task_name(self, monkeypatch, tmp_path):
        """按 task_name 过滤"""
        _setup_memory_with_entries(monkeypatch, tmp_path, [
            {'task': 'target_task', 'ts': '2026-07-30 14:35', 'importance': 'low', 'content': '目标'},
            {'task': 'other_task', 'ts': '2026-07-30 14:35', 'importance': 'low', 'content': '其他'},
        ])
        result = learn_tidy.memory_rethink(project_name='test_project', task_name='target_task', scope='low')
        assert result['total_scanned'] == 1
        assert result['suggestions'][0]['task'] == 'target_task'


# T020: handoff_tidy 自动触发 distill
class TestHandoffAutoDistill:
    def test_distill_failure_does_not_block_handoff(self, monkeypatch, tmp_path):
        """distill 失败不应阻断 handoff（隔离机制）"""
        monkeypatch.setenv("RIJI_DATA_DIR", str(tmp_path))
        import generate_docs
        monkeypatch.setattr(generate_docs, "read_primary_docs_marker", lambda: None)
        # mock distill 抛异常
        import memory_distill
        def _raise(*a, **kw):
            raise RuntimeError("distill failed")
        monkeypatch.setattr(memory_distill, 'distill', _raise)
        # 创建 handoff_tidy 实例并跑 run()
        import handoff_tidy
        runner = handoff_tidy.HandoffTidy(dry_run=True, task_name='test')
        # run() 应正常返回（distill 失败被 try/except 隔离）
        result = runner.run()
        assert result is not None  # 未抛异常说明隔离成功
