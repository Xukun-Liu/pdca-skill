"""
find_similar.py — riji-skill 外部资源搜索脚本

功能：
  - scan : 按任务描述/关键词搜索 GitHub + Gitee + 国内 skill 平台，找类似 skill 或项目
  - list : 列出所有配置的搜索源

设计说明：
  本脚本是 /plan 步骤 4a.3 的执行工具，用于自动搜索外部可复用资源。
  GitHub + Gitee 用 API 调用（稳定，支持 token 避免限流）。
  国内大厂平台（Coze/腾讯 SkillHub/skills.sh）API 不公开，脚本只输出搜索链接，
  由主 agent 后续用 WebFetch 工具抓取页面内容。

对应文档：references/plan/route/agent_find.md + SKILL.md /plan 步骤 4a.3
版本：v1.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ===== 路径常量 =====
_SKILL_ROOT = Path(__file__).resolve().parent.parent
_DOCS_SPEC_DIR = _SKILL_ROOT / "docs_rj" / "spec_rj"


# ===== 搜索源配置 =====

@dataclass
class SearchSource:
    """单个搜索源配置。"""
    name: str
    url: str
    method: str  # "api" | "link"（api=脚本调 API，link=只输出链接让 agent 抓）
    lang: str  # "zh" | "en" | "multi"
    token_env: Optional[str] = None  # 环境变量名（如 GITHUB_TOKEN）
    priority: int = 1  # 1=必选，2=可选


# 6 个必选搜索源
SEARCH_SOURCES: List[SearchSource] = [
    # 第一梯队：Gitee 仓库（API 调用，国内源优先）
    SearchSource(
        name="Gitee 技能商店（shishishe/skill）",
        url="https://gitee.com/api/v5/search/repositories",
        method="api",
        lang="zh",
        token_env="GITEE_TOKEN",
        priority=1,
    ),
    SearchSource(
        name="Gitee AgentSkills（championwang/agent-skills）",
        url="https://gitee.com/api/v5/search/repositories",
        method="api",
        lang="zh",
        token_env="GITEE_TOKEN",
        priority=1,
    ),
    # 第二梯队：GitHub（API 调用，海外源）
    SearchSource(
        name="GitHub",
        url="https://api.github.com/search/repositories",
        method="api",
        lang="en",
        token_env="GITHUB_TOKEN",
        priority=1,
    ),
    # 第三梯队：国内大厂平台（API 不公开，只输出链接）
    SearchSource(
        name="Coze 技能商店",
        url="https://www.coze.cn/store/skill",
        method="link",
        lang="zh",
        priority=1,
    ),
    SearchSource(
        name="腾讯 SkillHub",
        url="https://skillhub.openanolis.cn",
        method="link",
        lang="zh",
        priority=1,
    ),
    SearchSource(
        name="skills.sh（Claude 官方生态）",
        url="https://www.skills.sh",
        method="link",
        lang="en",
        priority=1,
    ),
]


# ===== 数据结构 =====

@dataclass
class SearchResult:
    """单个搜索结果。"""
    source: str  # 来源（如 "GitHub"）
    name: str  # 仓库名/skill 名
    url: str  # 链接
    description: str  # 描述
    stars: int  # star 数（API 源有，link 源为 0）
    updated_at: str  # 最后更新时间（API 源有，link 源为空）
    language: str  # 主要语言（API 源有，link 源为空）
    score: float = 0.0  # 相关度评分（quality_filter 后计算）


@dataclass
class ScanReport:
    """扫描报告。"""
    task: str
    keywords: List[str]
    timestamp: str
    total_results: int
    results: List[SearchResult]
    link_sources: List[Dict[str, str]]  # link 类源的搜索链接
    errors: List[Dict[str, str]] = field(default_factory=list)


# ===== API 搜索函数 =====

def _build_headers(token_env: Optional[str] = None) -> Dict[str, str]:
    """构建 HTTP 请求头，支持 token 鉴权。"""
    headers = {
        "User-Agent": "riji-skill/find_similar",
        "Accept": "application/json",
    }
    if token_env and os.environ.get(token_env):
        token = os.environ[token_env]
        # GitHub 用 Bearer，Gitee 用 Bearer
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _make_request(url: str, headers: Dict[str, str], timeout: int = 10) -> Optional[Dict[str, Any]]:
    """发起 HTTP GET 请求，返回 JSON。失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"_error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"_error": f"Exception: {str(e)}"}


def search_github(keywords: List[str], token: Optional[str] = None) -> List[SearchResult]:
    """GitHub API 搜索仓库。用原始关键词搜索，不自动加后缀（避免重复）。"""
    if not keywords:
        return []
    q = " ".join(keywords)
    encoded_q = urllib.parse.quote(q)
    url = f"https://api.github.com/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page=10"

    headers = _build_headers("GITHUB_TOKEN")
    data = _make_request(url, headers)
    if not data or "_error" in data or "items" not in data:
        return []

    results = []
    for item in data.get("items", []):
        results.append(SearchResult(
            source="GitHub",
            name=item.get("full_name", ""),
            url=item.get("html_url", ""),
            description=item.get("description", "") or "",
            stars=item.get("stargazers_count", 0),
            updated_at=item.get("updated_at", "")[:10],  # 只取日期部分
            language=item.get("language", "") or "",
        ))
    return results


def search_gitee(keywords: List[str], token: Optional[str] = None) -> List[SearchResult]:
    """Gitee API 搜索仓库。用原始关键词搜索，不自动加 repo_keyword（避免过窄）。"""
    if not keywords:
        return []
    q = " ".join(keywords)
    encoded_q = urllib.parse.quote(q)
    url = f"https://gitee.com/api/v5/search/repositories?q={encoded_q}&per_page=10"

    headers = _build_headers("GITEE_TOKEN")
    data = _make_request(url, headers)
    # Gitee 出错时返回 dict（含 message），成功时返回 list
    if not data or isinstance(data, dict):
        return []

    results = []
    for item in data if isinstance(data, list) else []:
        results.append(SearchResult(
            source="Gitee",
            name=item.get("full_name", ""),
            url=item.get("html_url", ""),
            description=item.get("description", "") or "",
            stars=item.get("stargazers_count", 0),
            updated_at=item.get("updated_at", "")[:10],
            language=item.get("language", "") or "",
        ))
    return results


# ===== link 源（只输出搜索链接）=====

def build_link_sources(keywords: List[str]) -> List[Dict[str, str]]:
    """为 link 类源构建搜索链接。"""
    if not keywords:
        q = ""
    else:
        q = " ".join(keywords)
    encoded_q = urllib.parse.quote(q)

    links = []
    for source in SEARCH_SOURCES:
        if source.method != "link":
            continue
        # 为每个 link 源拼搜索 URL
        if "coze" in source.url:
            search_url = f"https://www.coze.cn/store/skill?keyword={encoded_q}"
        elif "skillhub" in source.url:
            search_url = f"https://skillhub.openanolis.cn/search?q={encoded_q}"
        elif "skills.sh" in source.url:
            search_url = f"https://www.skills.sh/search?q={encoded_q}"
        else:
            search_url = source.url

        links.append({
            "name": source.name,
            "search_url": search_url,
            "instruction": f"用 WebFetch 工具抓取 {search_url}，按关键词 {q} 过滤 skill 列表",
        })
    return links


# ===== 质量过滤 + 去重 =====

def quality_filter(results: List[SearchResult], min_stars: int = 5, max_age_days: int = 365) -> List[SearchResult]:
    """质量过滤：star >= min_stars + 最后更新 <= max_age_days。"""
    now = datetime.now()
    filtered = []
    for r in results:
        # star 过滤
        if r.stars < min_stars:
            continue
        # 更新时间过滤（只对有 updated_at 的源）
        if r.updated_at:
            try:
                updated = datetime.strptime(r.updated_at, "%Y-%m-%d")
                age_days = (now - updated).days
                if age_days > max_age_days:
                    continue
            except ValueError:
                pass  # 时间格式异常，保留
        filtered.append(r)
    return filtered


def deduplicate(results: List[SearchResult]) -> List[SearchResult]:
    """按 URL 去重。"""
    seen_urls = set()
    unique = []
    for r in results:
        if r.url and r.url not in seen_urls:
            seen_urls.add(r.url)
            unique.append(r)
    return unique


def score_results(results: List[SearchResult]) -> List[SearchResult]:
    """按 star 数 + 是否中文源 计算相关度评分，降序排序。"""
    for r in results:
        score = float(r.stars)
        # 中文源加权（用户偏好国内）
        if r.source == "Gitee":
            score *= 1.2
        r.score = score
    # 按评分降序
    results.sort(key=lambda x: x.score, reverse=True)
    return results


# ===== 报告生成 =====

def generate_report(report: ScanReport, output_path: Optional[Path] = None) -> Path:
    """生成复用资源清单 markdown。"""
    if output_path is None:
        # 默认输出到 docs_rj/spec_rj/{task}_reuse_YYYYMMDD_HHMM.md
        safe_task = "".join(c if c.isalnum() or c in "-_" else "_" for c in report.task[:30])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = _DOCS_SPEC_DIR / f"{safe_task}_reuse_{timestamp}.md"

    # 确保目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# 复用资源清单：{report.task}")
    lines.append("")
    lines.append(f"> 生成时间：{report.timestamp}")
    lines.append(f"> 搜索关键词：{', '.join(report.keywords) if report.keywords else '（未指定，用任务描述提取）'}")
    lines.append(f"> 结果总数：{report.total_results}")
    lines.append(f"> 来源：脚本生成（find_similar.py v1.0）")
    lines.append("")
    lines.append("---")
    lines.append("")

    # API 源结果
    if report.results:
        lines.append("## 一、API 源搜索结果（GitHub + Gitee）")
        lines.append("")
        lines.append("| # | 来源 | 名称 | Stars | 最后更新 | 语言 | 描述 |")
        lines.append("|---|------|------|-------|---------|------|------|")
        for i, r in enumerate(report.results, 1):
            desc = r.description[:60].replace("|", "\\|") if r.description else ""
            lines.append(f"| {i} | {r.source} | [{r.name}]({r.url}) | {r.stars} | {r.updated_at} | {r.language} | {desc} |")
        lines.append("")

    # link 源（需 agent 后续 WebFetch）
    if report.link_sources:
        lines.append("## 二、国内大厂平台（需 agent 用 WebFetch 抓取）")
        lines.append("")
        lines.append("以下平台 API 不公开，脚本只输出搜索链接。主 agent 应依次用 WebFetch 工具抓取页面，按关键词过滤 skill 列表。")
        lines.append("")
        for link in report.link_sources:
            lines.append(f"### {link['name']}")
            lines.append(f"- 搜索链接：{link['search_url']}")
            lines.append(f"- 操作：{link['instruction']}")
            lines.append("")
    else:
        if not report.results:
            lines.append("## 搜索结果")
            lines.append("")
            lines.append("（无结果）")
            lines.append("")

    # 错误信息
    if report.errors:
        lines.append("## 三、错误信息")
        lines.append("")
        for err in report.errors:
            lines.append(f"- **{err['source']}**: {err['error']}")
        lines.append("")

    # 后续建议
    lines.append("## 四、后续建议")
    lines.append("")
    lines.append("1. 优先评估高 star + 最近更新的项目")
    lines.append("2. 中文场景优先看 Gitee 源")
    lines.append("3. 对 link 源，用 WebFetch 抓取后按关键词过滤")
    lines.append("4. 找到候选 skill 后，走 skill_management.md 安装流程 + skill_security.md 安全扫描")
    lines.append("5. 找到候选项目后，评估：直接引用 / 封装适配 / 参考架构 / 仅学习")
    lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ===== 命令实现 =====

def cmd_scan(args: argparse.Namespace) -> int:
    """scan 命令：搜索外部资源。"""
    task = args.task
    keywords = args.keywords.split(",") if args.keywords else []
    min_stars = args.min_stars
    max_age_days = args.max_age_days

    # 如果没指定关键词，从任务描述提取（简单分词）
    if not keywords:
        # 简单提取：去掉常见停用词，取前 5 个词
        stop_words = {"的", "了", "和", "是", "在", "我", "有", "一个", "这个", "那个", "帮", "帮我", "实现", "做", "写"}
        words = [w for w in task.replace(",", " ").split() if w and w not in stop_words]
        keywords = words[:5] if words else [task]

    print(f"[find_similar] 任务：{task}")
    print(f"[find_similar] 关键词：{', '.join(keywords)}")
    print(f"[find_similar] 质量过滤：min_stars={min_stars}, max_age_days={max_age_days}")
    print()

    all_results: List[SearchResult] = []
    errors: List[Dict[str, str]] = []

    # GitHub
    print("[find_similar] 搜索 GitHub...")
    github_results = search_github(keywords)
    print(f"  -> {len(github_results)} 条结果")
    all_results.extend(github_results)

    # Gitee（用原始关键词搜索，一次调用即可覆盖所有仓库）
    print("[find_similar] 搜索 Gitee...")
    gitee_results = search_gitee(keywords)
    print(f"  -> {len(gitee_results)} 条结果")
    all_results.extend(gitee_results)

    # link 源
    print("[find_similar] 构建国内大厂平台搜索链接...")
    link_sources = build_link_sources(keywords)
    print(f"  -> {len(link_sources)} 个 link 源")

    # 质量过滤
    print(f"[find_similar] 质量过滤（min_stars={min_stars}, max_age_days={max_age_days}）...")
    filtered = quality_filter(all_results, min_stars=min_stars, max_age_days=max_age_days)
    print(f"  -> 过滤前 {len(all_results)} 条，过滤后 {len(filtered)} 条")

    # 去重
    print("[find_similar] 去重...")
    unique = deduplicate(filtered)
    print(f"  -> 去重前 {len(filtered)} 条，去重后 {len(unique)} 条")

    # 评分排序
    print("[find_similar] 评分排序...")
    scored = score_results(unique)

    # 生成报告
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = ScanReport(
        task=task,
        keywords=keywords,
        timestamp=timestamp,
        total_results=len(scored),
        results=scored,
        link_sources=link_sources,
        errors=errors,
    )

    output_path = Path(args.output) if args.output else None
    report_path = generate_report(report, output_path)

    print()
    print(f"[find_similar] 报告已生成：{report_path}")
    print(f"[find_similar] API 源结果：{len(scored)} 条")
    print(f"[find_similar] link 源：{len(link_sources)} 个（需 agent 后续 WebFetch）")

    # 输出 JSON 摘要到 stdout（供 agent 解析）
    summary = {
        "task": task,
        "keywords": keywords,
        "timestamp": timestamp,
        "total_api_results": len(scored),
        "total_link_sources": len(link_sources),
        "report_path": str(report_path),
        "top_5": [
            {"name": r.name, "url": r.url, "stars": r.stars, "source": r.source}
            for r in scored[:5]
        ],
    }
    print()
    print("=== JSON 摘要 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """list 命令：列出所有搜索源。"""
    print(f"共 {len(SEARCH_SOURCES)} 个搜索源：")
    print()
    print("| # | 名称 | 方法 | 语言 | token | 优先级 |")
    print("|---|------|------|------|-------|--------|")
    for i, s in enumerate(SEARCH_SOURCES, 1):
        print(f"| {i} | {s.name} | {s.method} | {s.lang} | {s.token_env or '无'} | P{s.priority} |")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="riji-skill 外部资源搜索脚本（/plan 步骤 4a.3 执行工具）"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # scan 子命令
    scan_parser = subparsers.add_parser("scan", help="搜索外部资源")
    scan_parser.add_argument("--task", required=True, help="任务描述")
    scan_parser.add_argument("--keywords", help="搜索关键词（逗号分隔，默认从任务描述提取）")
    scan_parser.add_argument("--output", help="输出文件路径（默认自动生成）")
    scan_parser.add_argument("--min-stars", type=int, default=5, help="最小 star 数（默认 5）")
    scan_parser.add_argument("--max-age-days", type=int, default=365, help="最大更新天数（默认 365）")

    # list 子命令
    subparsers.add_parser("list", help="列出所有搜索源")

    args = parser.parse_args()
    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
