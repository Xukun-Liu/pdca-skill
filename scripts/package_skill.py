#!/usr/bin/env python3
"""pdca-skill 发布打包脚本

T012: 打包 skill 包为 zip，排除用户数据目录（memory/ docs_rj/ outputs_rj/ server_lite_data/ 等），
确保发布包只含框架文件，用户解压覆盖升级时数据 0 丢失。

用法：
    python scripts/package_skill.py --version v1.0.2
    python scripts/package_skill.py --version v1.0.2 --output ./dist/

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
    r"^\.pytest_cache/",
    r"\.pytest_cache/",  # 任意层级的 pytest 缓存（含 tests/.pytest_cache/）
    r"^\.pdca-skill/",  # 本地外置目录（若误放包内）
    r"^_test_run/",  # 测试运行快照（本地临时产物，不进发布包）
    r"^agents_rj/subagent_call_log\.jsonl$",  # 副 agent 调用日志（运行时产物，不进发布包）
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
                zf.write(abs_file, arcname=rel_path)
                included_count += 1

    print(f"[package] 打包完成: {zip_path}")
    print(f"[package] 包含文件: {included_count}，排除文件: {excluded_count}")
    return str(zip_path)


def _verify_package(zip_path: str) -> dict:
    """验证 zip 包不含用户数据目录。

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
                violations.append(name)

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
