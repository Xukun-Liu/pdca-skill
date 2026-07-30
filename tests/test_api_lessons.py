#!/usr/bin/env python3
"""tests/test_api_lessons.py - T004 /api/knowledge/lessons 端点单元测试。

覆盖：
- test_get_lessons: lessons.json 存在 → 返回 200 + 经验列表
- test_get_lessons_empty: 无 learn_rj 目录 → 返回 200 + 空经验库
- test_get_lessons_corrupted_json: lessons.json 损坏 → 返回 502 + 错误信息

设计原则：
- monkeypatch user_data_path.get_docs_rj_path 返回 tmp_path（隔离真实 docs_rj/）
- 测试数据格式严格对齐 memory_distill.py 产出的 lessons.json 结构
- sys.path.insert 按项目约定（conftest autouse fixture 在测试结束恢复 sys.path）

路径对齐说明（T004 修复 task.md 原代码路径 Bug）：
- learn_rj/ 实际在 docs_rj/learn_rj/（由 learn_tidy.py / memory_distill.py 产出）
- 端点应通过 user_data_path.get_docs_rj_path() / "learn_rj" 取真实路径
- 不是 DATA_DIR/learn_rj（DATA_DIR 是 server_lite_data/，与 docs_rj/ 平级兄弟）
"""
import os
import sys
import json
import pytest
from pathlib import Path

# 把 riji-skill-public v1.0 加入 sys.path
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_ROOT)
# 把 scripts/ 加入 sys.path 以便 import user_data_path
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  测试需 monkeypatch user_data_path 函数

from server_lite.app import create_app


# ---------------------------------------------------------------------------
# 共享 fixture：隔离 user_data_path.get_docs_rj_path 到 tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_tmp_docs(monkeypatch, tmp_path):
    """隔离测试环境：monkeypatch get_docs_rj_path 返回 tmp_path。

    使 api_knowledge.py 内调用的 user_data_path.get_docs_rj_path() 返回 tmp_path，
    从而 learn_rj/ 目录落在 tmp_path/learn_rj/ 下，不污染真实 docs_rj/。
    """
    monkeypatch.setattr(user_data_path, "get_docs_rj_path", lambda: tmp_path)
    app = create_app({"TESTING": True})
    yield app


@pytest.fixture
def c(app_with_tmp_docs):
    return app_with_tmp_docs.test_client()


# ---------------------------------------------------------------------------
# 测试用 lessons.json 数据（对齐 memory_distill.py 产出格式）
# ---------------------------------------------------------------------------

LESSONS_DATA = {
    "total_lessons": 1,
    "lessons": [{
        "lesson_id": "lesson_001",
        "title": "test_lesson",
        "content": "测试经验内容",
        "source_memory": "test_project/test_lesson(2026-07-24 09:00)",
        "importance_level": "high",
        "experience_tags": ["bugfix", "auth"],
        "reflection": "",
        "adopted": False,
    }],
    "distill_time": "2026-07-24 09:22",
    "source_file": "/tmp/memory_main.md",
}


# ---------------------------------------------------------------------------
# T004: /api/knowledge/lessons 端点
# ---------------------------------------------------------------------------

class TestGetLessons:
    """GET /api/knowledge/lessons"""

    def test_get_lessons(self, c, tmp_path):
        """测试 lessons.json 存在时返回 200 + 经验列表"""
        # 构造 lessons.json（路径：tmp_path/learn_rj/{timestamp}/lessons.json）
        learn_dir = tmp_path / "learn_rj" / "20260724-092200"
        learn_dir.mkdir(parents=True)
        (learn_dir / "lessons.json").write_text(
            json.dumps(LESSONS_DATA, ensure_ascii=False), encoding="utf-8"
        )

        resp = c.get("/api/knowledge/lessons")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_lessons"] == 1
        assert len(data["lessons"]) == 1
        lesson = data["lessons"][0]
        assert lesson["lesson_id"] == "lesson_001"
        assert lesson["title"] == "test_lesson"
        assert lesson["importance_level"] == "high"
        assert lesson["experience_tags"] == ["bugfix", "auth"]

    def test_get_lessons_empty(self, c, tmp_path):
        """测试无 learn_rj 目录时返回 200 + 空经验库"""
        # 不创建 learn_rj 目录
        resp = c.get("/api/knowledge/lessons")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_lessons"] == 0
        assert data["lessons"] == []
        # message 字段说明原因
        assert "message" in data

    def test_get_lessons_latest_timestamp(self, c, tmp_path):
        """测试多个时间戳目录时返回最新的 lessons.json"""
        learn_root = tmp_path / "learn_rj"
        # 构造 3 个时间戳目录，20260725-100000 最新
        for ts in ["20260723-090000", "20260724-092200", "20260725-100000"]:
            d = learn_root / ts
            d.mkdir(parents=True)
            data = dict(LESSONS_DATA)
            data["distill_time"] = ts
            data["lessons"] = [{
                **LESSONS_DATA["lessons"][0],
                "title": f"lesson_at_{ts}",
            }]
            (d / "lessons.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )

        resp = c.get("/api/knowledge/lessons")
        assert resp.status_code == 200
        data = resp.get_json()
        # 应返回最新的 20260725-100000
        assert data["lessons"][0]["title"] == "lesson_at_20260725-100000"

    def test_get_lessons_corrupted_json(self, c, tmp_path):
        """测试 lessons.json 损坏时返回 502 + 错误信息"""
        learn_dir = tmp_path / "learn_rj" / "20260724-092200"
        learn_dir.mkdir(parents=True)
        # 写入损坏的 JSON
        (learn_dir / "lessons.json").write_text(
            "{invalid json content", encoding="utf-8"
        )

        resp = c.get("/api/knowledge/lessons")
        assert resp.status_code == 502
        data = resp.get_json()
        assert "error" in data
        assert "json" in data["error"].lower() or "parse" in data["error"].lower()

    def test_get_lessons_no_lessons_json(self, c, tmp_path):
        """测试 learn_rj 目录存在但无 lessons.json 时返回 200 + 空经验库"""
        learn_dir = tmp_path / "learn_rj" / "20260724-092200"
        learn_dir.mkdir(parents=True)
        # 目录存在但不含 lessons.json

        resp = c.get("/api/knowledge/lessons")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_lessons"] == 0
        assert data["lessons"] == []
