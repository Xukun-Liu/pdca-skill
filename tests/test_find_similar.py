#!/usr/bin/env python3
"""tests/test_find_similar.py - find_similar.py 单元测试。

覆盖：
- test_list_command: list 命令正常输出 6 个搜索源
- test_scan_missing_task: scan 缺少 --task 参数报错
- test_search_github_returns_list: search_github 返回 list 类型
- test_search_gitee_returns_list: search_gitee 返回 list 类型
- test_quality_filter_by_stars: 质量过滤按 star 数
- test_quality_filter_by_age: 质量过滤按更新时间
- test_deduplicate_by_url: 去重按 URL
- test_score_results_sort: 评分排序降序
- test_build_link_sources_count: link 源构建数量
- test_generate_report_creates_file: 报告生成创建文件
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from find_similar import (
    SEARCH_SOURCES,
    ScanReport,
    SearchResult,
    build_link_sources,
    deduplicate,
    generate_report,
    quality_filter,
    score_results,
    search_github,
    search_gitee,
)


def _run_script(*args):
    """辅助：运行 find_similar.py 子命令。"""
    cmd = [sys.executable, "scripts/find_similar.py"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL_ROOT,
                          encoding='utf-8', errors='replace')


class TestListCommand:
    """list 子命令测试。"""

    def test_list_command_returns_zero(self):
        """测试 list 命令返回码 0。"""
        result = _run_script("list")
        assert result.returncode == 0, f"stderr={result.stderr}"

    def test_list_command_outputs_6_sources(self):
        """测试 list 命令输出 6 个搜索源。"""
        result = _run_script("list")
        assert "共 6 个搜索源" in result.stdout

    def test_list_command_contains_github(self):
        """测试 list 命令包含 GitHub。"""
        result = _run_script("list")
        assert "GitHub" in result.stdout

    def test_list_command_contains_coze(self):
        """测试 list 命令包含 Coze。"""
        result = _run_script("list")
        assert "Coze" in result.stdout


class TestScanCommand:
    """scan 子命令测试。"""

    def test_scan_missing_task_returns_error(self):
        """测试 scan 缺少 --task 参数返回非 0。"""
        result = _run_script("scan")
        assert result.returncode != 0

    def test_scan_with_task_returns_zero(self):
        """测试 scan 带 --task 参数返回 0（网络冒烟测试）。"""
        result = _run_script("scan", "--task", "test", "--min-stars", "999")
        assert result.returncode == 0, f"stderr={result.stderr}"


class TestSearchFunctions:
    """搜索函数测试（网络相关，冒烟测试）。"""

    def test_search_github_returns_list(self):
        """测试 search_github 返回 list 类型。"""
        results = search_github(["nonexistent_keyword_xyz123"])
        assert isinstance(results, list)

    def test_search_gitee_returns_list(self):
        """测试 search_gitee 返回 list 类型。"""
        results = search_gitee(["nonexistent_keyword_xyz123"])
        assert isinstance(results, list)

    def test_search_github_empty_keywords_returns_empty(self):
        """测试 search_github 空关键词返回空列表。"""
        results = search_github([])
        assert results == []


class TestQualityFilter:
    """质量过滤测试。"""

    def test_filter_by_min_stars(self):
        """测试按 star 数过滤。"""
        results = [
            SearchResult("GitHub", "low", "url1", "desc", 3, "2026-07-01", "Python"),
            SearchResult("GitHub", "high", "url2", "desc", 100, "2026-07-01", "Python"),
        ]
        filtered = quality_filter(results, min_stars=10, max_age_days=365)
        assert len(filtered) == 1
        assert filtered[0].name == "high"

    def test_filter_by_max_age(self):
        """测试按更新时间过滤。"""
        old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        results = [
            SearchResult("GitHub", "old", "url1", "desc", 100, old_date, "Python"),
            SearchResult("GitHub", "recent", "url2", "desc", 100, recent_date, "Python"),
        ]
        filtered = quality_filter(results, min_stars=5, max_age_days=365)
        assert len(filtered) == 1
        assert filtered[0].name == "recent"

    def test_filter_no_updated_at_keeps(self):
        """测试无 updated_at 的结果保留。"""
        results = [
            SearchResult("link", "name", "url", "desc", 0, "", ""),
        ]
        filtered = quality_filter(results, min_stars=0, max_age_days=365)
        assert len(filtered) == 1


class TestDeduplicate:
    """去重测试。"""

    def test_dedup_by_url(self):
        """测试按 URL 去重。"""
        results = [
            SearchResult("GitHub", "repo1", "https://example.com/repo", "desc1", 100, "2026-07-01", "Python"),
            SearchResult("Gitee", "repo2", "https://example.com/repo", "desc2", 50, "2026-07-01", "Python"),
            SearchResult("GitHub", "repo3", "https://example.com/other", "desc3", 80, "2026-07-01", "Python"),
        ]
        unique = deduplicate(results)
        assert len(unique) == 2

    def test_dedup_empty_url_filtered(self):
        """测试空 URL 的结果被过滤（无意义的空 URL 不保留）。"""
        results = [
            SearchResult("link", "name1", "", "desc", 0, "", ""),
            SearchResult("link", "name2", "https://example.com", "desc", 0, "", ""),
        ]
        unique = deduplicate(results)
        assert len(unique) == 1
        assert unique[0].url == "https://example.com"


class TestScoreResults:
    """评分排序测试。"""

    def test_sort_by_stars_desc(self):
        """测试按 star 数降序排序。"""
        results = [
            SearchResult("GitHub", "low", "url1", "desc", 50, "2026-07-01", "Python"),
            SearchResult("GitHub", "high", "url2", "desc", 200, "2026-07-01", "Python"),
            SearchResult("GitHub", "mid", "url3", "desc", 100, "2026-07-01", "Python"),
        ]
        scored = score_results(results)
        assert scored[0].name == "high"
        assert scored[1].name == "mid"
        assert scored[2].name == "low"

    def test_gitee_weighted_higher(self):
        """测试 Gitee 源加权后评分更高。"""
        results = [
            SearchResult("GitHub", "gh", "url1", "desc", 100, "2026-07-01", "Python"),
            SearchResult("Gitee", "gitee", "url2", "desc", 100, "2026-07-01", "Python"),
        ]
        scored = score_results(results)
        # 同样 star 数，Gitee 加权 1.2 倍，应该排前面
        assert scored[0].source == "Gitee"
        assert scored[0].score > scored[1].score


class TestBuildLinkSources:
    """link 源构建测试。"""

    def test_link_sources_count(self):
        """测试 link 源数量为 3（Coze + 腾讯 + skills.sh）。"""
        links = build_link_sources(["test"])
        assert len(links) == 3

    def test_link_sources_contain_coze(self):
        """测试 link 源包含 Coze。"""
        links = build_link_sources(["test"])
        assert any("Coze" in link["name"] for link in links)

    def test_link_sources_contain_search_url(self):
        """测试 link 源包含 search_url 字段。"""
        links = build_link_sources(["test"])
        for link in links:
            assert "search_url" in link
            assert link["search_url"].startswith("https://")

    def test_link_sources_empty_keywords(self):
        """测试空关键词也能构建 link 源。"""
        links = build_link_sources([])
        assert len(links) == 3


class TestGenerateReport:
    """报告生成测试。"""

    def test_generate_report_creates_file(self, tmp_path):
        """测试报告生成创建文件。"""
        report = ScanReport(
            task="test task",
            keywords=["test"],
            timestamp="2026-07-25 10:00:00",
            total_results=1,
            results=[
                SearchResult("GitHub", "test/repo", "https://example.com", "desc", 100, "2026-07-01", "Python"),
            ],
            link_sources=[],
            errors=[],
        )
        output_path = tmp_path / "test_report.md"
        result_path = generate_report(report, output_path)
        assert result_path.exists()
        content = result_path.read_text(encoding="utf-8")
        assert "test task" in content
        assert "test/repo" in content

    def test_generate_report_with_link_sources(self, tmp_path):
        """测试报告生成包含 link 源。"""
        report = ScanReport(
            task="test task",
            keywords=["test"],
            timestamp="2026-07-25 10:00:00",
            total_results=0,
            results=[],
            link_sources=[
                {"name": "Coze 技能商店", "search_url": "https://coze.cn", "instruction": "抓取页面"},
            ],
            errors=[],
        )
        output_path = tmp_path / "test_report.md"
        result_path = generate_report(report, output_path)
        content = result_path.read_text(encoding="utf-8")
        assert "Coze 技能商店" in content
        assert "https://coze.cn" in content

    def test_generate_report_with_errors(self, tmp_path):
        """测试报告生成包含错误信息。"""
        report = ScanReport(
            task="test task",
            keywords=["test"],
            timestamp="2026-07-25 10:00:00",
            total_results=0,
            results=[],
            link_sources=[],
            errors=[{"source": "GitHub", "error": "rate limit"}],
        )
        output_path = tmp_path / "test_report.md"
        result_path = generate_report(report, output_path)
        content = result_path.read_text(encoding="utf-8")
        assert "GitHub" in content
        assert "rate limit" in content
