#!/usr/bin/env python3
"""pdca-skill 发布打包脚本

T012: 打包 skill 包为 zip，排除用户数据目录（memory/ docs_rj/ outputs_rj/ server_lite_data/ 等），
确保发布包只含框架文件，用户解压覆盖升级时数据 0 丢失。

用法：
    python scripts/package_skill.py --version v1.0.1
    python scripts/package_skill.py --version v1.0.1 --output ./dist/

输出文件名：pdca-skill-v{版本号}-{YYYYMMDD-HHMM}.zip
"""
import argparse
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path


# 排除清单（正则，匹配 zip 内的相对路径，用 / 作分隔符）
# 含 server_lite_data 和 server_lite/data 两种写法（兼容历史）
EXCLUDE_PATTERNS = [
    r"^memory/",
    r"^docs_rj/",
    r"^outputs_rj/",
    r"^server_lite_data/",
    r"^server_lite/data/",
    r"\.migrated$",
    r"\.cleaning$",
    r"\.cleaned$",
    r"^__pycache__/",
    r"__pycache__/",
    r"\.pyc$",
    r"^\.git/",
    r"^dist/",
    r"^tmp_.*\.png$",
    r"^assets/readme/.*\.png$",  # v103_t4: skillhub.cn 不允许二进制，PNG 由发布者手动替换为 placeholder 引用
    r"^\.pytest_cache/",
    r"\.pytest_cache/",  # 任意层级的 pytest 缓存（含 tests/.pytest_cache/）
    r"^\.pdca-skill/",  # 本地外置目录（若误放包内）
    r"^_test_run/",  # 测试运行快照（本地临时产物，不进发布包）
    r"^agents_rj/subagent_call_log\.jsonl$",  # 副 agent 调用日志（运行时产物，不进发布包）
    # ── v1.0.4 发布包质量修复（实测测试报告 P0/P1，2026-08-26）──
    r"^\.primary_docs_rj$",            # P0: 开发机 marker（内含开发机绝对路径，绝不能进包）
    r"^\.gitignore$",                 # 开发文件（git 元数据不随包分发）
    r"^_sync_tmp/",                   # 同步临时目录（含旧版脚本副本，与正式 scripts/ 不一致）
    r"^package_.*\.log$",             # 打包日志（内含开发机路径）
    r"^T000_backup\.sha256$",         # 备份校验残留
    r"_out\.txt$",                    # 运行时输出残留（handoff_tidy_out.txt 等）
    r"^\.playwright-mcp/",            # 浏览器调试残留
    r"^网页说明\.html$",               # skillhub 发布展示页（发布者手动上传用，用户无需）
    r"^scripts/verify_zip\.ps1$",     # 开发打包辅助脚本（硬编码版本，随包无用）
    r"^scripts/test_loop_admission\.py$",  # 测试文件误放 scripts/（历史保留原地，仅排除出包）
    # 发布骨架例外：以下文件必须进发布包（使用者首次启动需读这些空骨架）
    # 通过 _should_exclude 返回 False 后再继续判断其他规则
]

# 编译正则
_EXCLUDE_REGEX = [re.compile(p) for p in EXCLUDE_PATTERNS]

# 发布骨架白名单（优先级高于排除规则，确保 v1.0.0 发布空骨架进发布包）
# 使用者首次启动 pdca-skill 时，§1 启动检查硬性要求读这 3 个文件，缺失会触发 BLOCKER
_SKELETON_WHITELIST = {
    "memory/memory_main.md",
    "docs_rj/SUMMARY_RJ.md",
    "docs_rj/spec_rj/spec_main_rj.md",
}

# ── v1.0.4 发布包质量修复：骨架模板化（防开发机活数据污染发布包）──
# 打包时白名单文件一律写入模板内容，而非开发环境的活数据。
# memory_main 用内置纯净骨架；SUMMARY_RJ / spec_main_rj 优先从 assets/ 模板读取，
# assets 缺失（如最小化 skill 结构）时回退内置极简骨架，不阻断打包。
_MEMORY_MAIN_SKELETON_TEMPLATE = """---
title: pdca-skill global memory
version: v1.0.0
skill_version: {version}
date_created: 1970-01-01 00:00
last_updated: 1970-01-01 00:00
tags: [pdca-skill, memory, skeleton]
---

# memory_main（发布骨架）

> 此文件为 `scripts/package_skill.py` 白名单要求的最小骨架，避免发布包被打包排除。
>
> 实际全局记忆由使用者首次启动后由 Bootstrap 自动填充：
> - Bootstrap 阶段读取项目 + 跨项目知识
> - 写入路径：本机 `~/.pdca-skill/data/memory/memory_main.md`（用户数据外置，不进 git）
> - 写入时机：每次 /act 阶段 learn_tidy + handoff_tidy
>
> 本骨架仅作为发布包占位，仓库内保持空内容。
"""

# 骨架来源映射：白名单文件 -> assets 模板路径（None 表示用内置模板）
_SKELETON_TEMPLATE_SOURCES = {
    "memory/memory_main.md": None,                       # 内置 _MEMORY_MAIN_SKELETON_TEMPLATE
    "docs_rj/SUMMARY_RJ.md": "assets/summary_template.md",
    "docs_rj/spec_rj/spec_main_rj.md": "assets/spec_main_template.md",
}

# assets 模板缺失时的内置极简骨架（回退，不阻断打包）
_SUMMARY_RJ_FALLBACK = """---
title: SUMMARY_RJ
type: summary_index
---

# SUMMARY_RJ（发布骨架）

> 发布包最小骨架：实际文档索引由使用者首次启动后由 Bootstrap / summary_view 自动生成。
> 规范见 references/common/pa/summary_view.md。
"""

_SPEC_MAIN_RJ_FALLBACK = """---
title: spec_main_rj
type: project_spec_main
---

# spec_main_rj（发布骨架）

> 发布包最小骨架：项目级 source of truth 由使用者首次启动后按 SKILL.md §6 /plan 步骤1.5 初始化。
> 完整模板见 skill 仓库 assets/spec_main_template.md。
"""

_SKELETON_FALLBACKS = {
    "docs_rj/SUMMARY_RJ.md": _SUMMARY_RJ_FALLBACK,
    "docs_rj/spec_rj/spec_main_rj.md": _SPEC_MAIN_RJ_FALLBACK,
}


def _skeleton_content(rel_path: str, version: str, skill_root) -> str:
    """返回白名单骨架文件的模板内容（v1.0.4：防活数据进包）。

    Args:
        rel_path: zip 内相对路径
        version: 本次打包版本号（如 v1.0.4）
        skill_root: skill 包根目录（读 assets 模板用）

    Returns:
        模板字符串：assets 模板存在时返回其内容；缺失时回退内置极简骨架
    """
    if rel_path == "memory/memory_main.md":
        return _MEMORY_MAIN_SKELETON_TEMPLATE.format(version=version)
    template_rel = _SKELETON_TEMPLATE_SOURCES.get(rel_path)
    template_path = Path(skill_root) / template_rel
    if not template_path.is_file():
        fallback = _SKELETON_FALLBACKS.get(rel_path)
        if fallback is None:
            raise FileNotFoundError(f"骨架模板缺失且无内置降级: {template_path}")
        return fallback
    return template_path.read_text(encoding="utf-8")


# ── v1.0.4 发布包质量修复：_verify_package 独立产物嗅探 ──
# 与 _should_exclude（打包规则）同源的检查「规则漏了什么，验证就瞎什么」，
# 故验证环节用独立特征清单 + 内容嗅探，双保险。
_ARTIFACT_SNIFF_PATTERNS = [
    r"\.log$", r"_out\.txt$", r"\.sha256$", r"\.tmp$", r"\.bak$",
    r"^_sync_tmp/", r"^\.playwright-mcp/", r"^\.primary_docs_rj$", r"^\.gitignore$",
    r"^~\$", r"__pycache__/", r"\.pyc$",
]
_ARTIFACT_SNIFF_REGEX = [re.compile(p) for p in _ARTIFACT_SNIFF_PATTERNS]

# 开发机隐私嗅探：绝对路径 + 真实用户名模式（命中即告警，防泄露开发者机器信息）。
# 排除规则（负向前瞻）：占位词/系统目录（xxx/你/All Users/Default/Public/.../{用户名}）后
# 不跟字母数字 = 完整占位词 -> 豁免；只抓真实用户名（如 86029 / liu.xukun）。
# Default/Public 为 Windows 系统内置用户目录（server_lite 合法白名单），非开发者信息。
_DEV_MACHINE_PATTERN = re.compile(
    r"C:[\\/]+Users[\\/]+"
    r"(?!(?:xxx|你|All[ ]Users|Default|Public|\.\.\.)(?![A-Za-z0-9_\u4e00-\u9fa5]))"
    r"[A-Za-z0-9_.\u4e00-\u9fa5-]+")

# 骨架活数据嗅探：白名单文件若含开发环境活数据特征则告警
_SKELETON_DIRTY_PATTERNS = [
    re.compile(r"owner:\s*\d+"),                    # owner: 86029（开发机用户名）
    re.compile(r"total_docs:\s*[1-9]\d*"),          # total_docs: 112（开发仓库真数据）
    re.compile(r"title:\s*riji-skill"),             # 开发仓库自己的文档索引
]


def _should_exclude(rel_path: str) -> bool:
    """判断相对路径是否应被排除。

    Args:
        rel_path: 相对于 skill 包根目录的路径（用 / 作分隔符，zip 标准格式）

    Returns:
        True=排除，False=保留
    """
    # 白名单优先：发布骨架文件必须保留
    if rel_path in _SKELETON_WHITELIST:
        return False
    for rx in _EXCLUDE_REGEX:
        if rx.search(rel_path):
            return True
    return False


def _should_exclude_dir(rel_path: str) -> bool:
    """判断目录是否应被排除（剪枝用）。

    与 _should_exclude 的区别：检查该目录下是否含白名单骨架文件，
    若含骨架文件则不剪枝（让骨架文件有机会被 _should_exclude 检查）。

    Args:
        rel_path: 目录的相对路径（用 / 作分隔符）

    Returns:
        True=剪枝排除，False=保留目录
    """
    # 先按文件规则判断
    if _should_exclude(rel_path):
        # 检查该目录下是否含骨架文件（如 docs_rj/spec_rj/ 含 spec_main_rj.md）
        for skeleton in _SKELETON_WHITELIST:
            if skeleton.startswith(rel_path + "/"):
                return False  # 含骨架文件，不剪枝
        return True
    return False


def package_skill(version: str, output_dir: str, skill_root: str = None) -> str:
    """打包 skill 包为 zip。

    Args:
        version: 版本号（如 v1.0.1）
        output_dir: 输出目录
        skill_root: skill 包根目录（默认当前目录的上级，即脚本所在目录的上级）

    Returns:
        生成的 zip 文件绝对路径

    Raises:
        FileNotFoundError: skill_root 不存在
        OSError: 输出目录创建失败 / zip 写入失败
    """
    if skill_root is None:
        # 脚本在 scripts/ 下，skill 根是 scripts/ 的上级
        skill_root = str(Path(__file__).resolve().parent.parent)

    skill_root_path = Path(skill_root).resolve()
    if not skill_root_path.exists():
        raise FileNotFoundError(f"skill_root 不存在: {skill_root_path}")

    # 输出目录
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # 文件名：pdca-skill-v{版本号}-{YYYYMMDD-HHMM}.zip
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    zip_name = f"pdca-skill-{version}-{timestamp}.zip"
    zip_path = output_path / zip_name

    # 遍历 skill_root，写入 zip
    included_count = 0
    excluded_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_root_path):
            # 原地修改 dirs 跳过排除目录（剪枝，提升性能）
            # 白名单例外：若目录下含骨架文件，不剪枝该目录（让骨架文件有机会被检查）
            dirs[:] = [d for d in dirs
                       if not _should_exclude_dir(
                           str(Path(root, d).relative_to(skill_root_path)).replace("\\", "/")
                       )
                   ]
            for fname in files:
                abs_file = Path(root, fname)
                rel_path = str(abs_file.relative_to(skill_root_path)).replace("\\", "/")
                if _should_exclude(rel_path):
                    excluded_count += 1
                    continue
                # v1.0.4: 白名单骨架文件写模板内容（防开发机活数据进包）
                if rel_path in _SKELETON_WHITELIST:
                    zf.writestr(rel_path,
                                _skeleton_content(rel_path, version, skill_root_path))
                else:
                    zf.write(abs_file, arcname=rel_path)
                included_count += 1

    print(f"[package] 打包完成: {zip_path}")
    print(f"[package] 包含文件: {included_count}，排除文件: {excluded_count}")
    return str(zip_path)


def _verify_package(zip_path: str) -> dict:
    """验证 zip 包不含用户数据目录。

    v1.0.4 升级为三层验证：
    ① 排除规则复查（原有，与打包同源）
    ② 独立产物嗅探（特征清单与打包规则解耦，规则漏了也能拦）
    ③ 内容嗅探（开发机路径 / 骨架活数据）

    Args:
        zip_path: zip 文件路径

    Returns:
        dict: {"valid": bool, "violations": [str], "total_files": int}
    """
    violations = []
    total_files = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            total_files += 1
            if _should_exclude(name):
                violations.append(f"[排除规则命中] {name}")
            # ② 独立产物嗅探（与打包规则解耦的双保险）
            for rx in _ARTIFACT_SNIFF_REGEX:
                if rx.search(name):
                    violations.append(f"[产物残留] {name}")
                    break
            # ③a 开发机路径嗅探（文本文件 ≤ 2MB 才读，避免读大二进制）
            if name.endswith((".md", ".txt", ".json", ".py", ".ps1", ".cmd", ".html", ".jsonl", ".log", ".yaml", ".yml")):
                try:
                    info = zf.getinfo(name)
                    if info.file_size <= 2 * 1024 * 1024:
                        content = zf.read(name).decode("utf-8", errors="replace")
                        if _DEV_MACHINE_PATTERN.search(content):
                            violations.append(f"[开发机路径泄露] {name}")
                        # ③b 骨架活数据嗅探
                        if name in _SKELETON_WHITELIST:
                            for dirty_rx in _SKELETON_DIRTY_PATTERNS:
                                if dirty_rx.search(content):
                                    violations.append(f"[骨架活数据污染] {name}")
                                    break
                except (OSError, zipfile.BadZipFile):
                    pass

    valid = len(violations) == 0
    report = {
        "valid": valid,
        "violations": violations[:20],  # 最多列 20 条避免刷屏
        "violations_count": len(violations),
        "total_files": total_files,
    }
    print(f"[verify] 验证结果: {'PASS' if valid else 'FAIL'}")
    print(f"[verify] 总文件数: {total_files}，违规文件数: {len(violations)}")
    if violations:
        print(f"[verify] 违规示例: {violations[:5]}")
    return report


def main():
    parser = argparse.ArgumentParser(description="pdca-skill 发布打包脚本")
    parser.add_argument("--version", required=True, help="版本号（如 v1.0.1）")
    parser.add_argument("--output", default="./dist/", help="输出目录（默认 ./dist/）")
    parser.add_argument("--skill-root", default=None, help="skill 包根目录（默认自动检测）")
    parser.add_argument("--no-verify", action="store_true", help="跳过打包后验证")
    args = parser.parse_args()

    try:
        zip_path = package_skill(args.version, args.output, args.skill_root)
        if not args.no_verify:
            report = _verify_package(zip_path)
            if not report["valid"]:
                print(f"[ERROR] 打包验证失败：发现 {report['violations_count']} 个违规文件")
                sys.exit(1)
        print(f"[done] 发布包: {zip_path}")
    except (FileNotFoundError, OSError) as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
