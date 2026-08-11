#!/usr/bin/env python3
"""用户数据迁移脚本（原子操作 + 文件锁防并发）。

本脚本负责将 skill 包内的用户数据（memory/ docs_rj/ outputs_rj/ server_lite_data/）
一键迁移到外置目录（~/.pdca-skill/data/），实现用户数据与框架文件物理分离。
升级 skill 包（解压覆盖）时，用户累积数据不丢失——它们存在外置目录下。

设计要点：
- 跨平台文件锁（Unix fcntl / Windows msvcrt）防并发迁移数据竞争
- shutil.copytree(dirs_exist_ok=True) 避免目录已存在冲突
- 校验文件数 + 字节数确保复制完整
- 失败时回滚（删外置半成品 + 保留包内原件）
- .migrated 标记含时间戳/文件数/字节数，供 7 天后清理判断
- _cleanup_legacy 改由 startup_tidy 独立调用（HIGH-003 方向B：与 migrate_if_needed 解耦）

函数清单（6 函数 + 1 模块级变量）：
- _acquire_lock() / _release_lock()：跨平台文件锁
- migrate_if_needed(skill_root)：检测并迁移用户数据
- _count_files(base, dirs)：统计文件数 + 字节数
- _cleanup_legacy(skill_root)：7 天后清理包内数据（由 startup_tidy 调用）
- main()：CLI 入口
- _lock_fd：模块级文件锁 fd（HIGH-001 修复）
"""
import os
import sys
import json
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_data_path

LOCK_FILE = user_data_path.CONFIG_FILE.parent / ".migrate.lock"
MIGRATED_MARKER = ".migrated"  # 包内标记文件
CLEANING_MARKER = ".cleaning"  # 清理中标记
CLEANED_MARKER = ".cleaned"    # 清理完成标记
RETENTION_DAYS = 7             # 回滚窗口

# 模块级文件锁 fd（HIGH-001 修复：原 fd 为局部变量，函数返回后引用丢失，
#   _release_lock 仅 unlink 文件名不释放 fcntl/msvcrt 锁（锁关联 inode+fd），
#   导致两进程可同时"持锁"——并发保护实际失效。改为模块级 _lock_fd 存活，
#   _release_lock 先 os.close(fd) 释放锁，再 unlink 文件名。）
_lock_fd: int | None = None


def _acquire_lock() -> bool:
    """跨平台文件锁（Unix fcntl / Windows msvcrt）。成功时把 fd 存到模块级 _lock_fd。

    Returns:
        bool: True 表示获取锁成功；False 表示锁已被其他进程持有或获取失败。
    """
    global _lock_fd
    lock_path = str(LOCK_FILE)
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                _lock_fd = fd  # 存到模块级，供 _release_lock 释放
                return True
            except OSError:
                os.close(fd)
                return False
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                _lock_fd = fd  # 存到模块级，供 _release_lock 释放
                return True
            except OSError:
                os.close(fd)
                return False
    except OSError:
        return False


def _release_lock():
    """释放文件锁：仅关闭 fd 释放 fcntl/msvcrt 锁，不 unlink 文件名。

    MEDIUM-001 修复（TOCTOU 竞态）：
    原 _release_lock 先 os.close(fd) 再 unlink 文件名，close 与 unlink 之间其他进程
    可能用 O_CREAT 创建新锁文件并获取锁（因 fd 已 close 释放），盲目 unlink 会删掉
    新进程的锁文件名 → 后续进程创建新 inode 锁文件 → "两进程同时持锁但 inode 不同"
    → 并发保护失效。

    修复方案选择（方案②：不 unlink 锁文件，残留无害）：
    - 方案①（unlink 前 fstat 校验 inode 一致）：严谨但 Windows st_ino 不可靠
      （FAT32/NTFS inode 语义不同，st_ino 常为 0），跨平台误判风险高
    - 方案②（不 unlink，残留无害）✅ 采用：锁文件是空文件，_acquire_lock 用
      O_CREAT|O_RDWR 模式打开，文件存在也能复用，不依赖文件不存在；fd 关闭即
      释放锁，文件名残留不影响下次获取锁；跨平台一致，代码最简
    - 方案③（os.open 后 fstat 比 inode 再决定 unlink）：同方案①的 Windows 问题

    锁文件残留说明：~/.pdca-skill/.migrate.lock 是迁移锁空文件，正常残留，
    O_CREAT 复用，无需清理。文档（SKILL.md/references）应注明此文件用途。
    """
    global _lock_fd
    if _lock_fd is not None:
        try:
            os.close(_lock_fd)  # 关闭 fd = 释放 fcntl/msvcrt 锁（锁关联 inode+fd）
        except OSError:
            pass
        _lock_fd = None
    # MEDIUM-001 修复：不 unlink 锁文件，残留无害（O_CREAT 复用，不依赖文件不存在）
    # 原盲目 unlink 存在 TOCTOU 竞态：close 与 unlink 之间其他进程可创建新锁文件并获取锁，
    # unlink 会误删新进程的锁文件名 → 并发保护失效。


def migrate_if_needed(skill_root: str) -> dict:
    """检测并迁移用户数据。

    Args:
        skill_root: skill 包根目录绝对路径。

    Returns:
        dict: 迁移报告，含以下字段：
            - status: 迁移状态（success/skip_no_source/skip_target_not_empty/
              skip_lock_busy/failed_verify_mismatch/failed_rolled_back）
            - source: 包内源路径
            - target: 外置目标路径
            - file_count: 迁移文件数
            - bytes: 迁移字节数
            - timestamp: ISO 格式时间戳
            - error: 失败时的错误信息（仅失败状态）

    注意（HIGH-003 方向B）：报告**不含** cleanup 字段——_cleanup_legacy 改由
    startup_tidy 独立调用，与 migrate_if_needed 解耦。
    """
    skill_root = Path(skill_root).resolve()
    report = {"status": "skip", "source": str(skill_root), "target": "",
              "file_count": 0, "bytes": 0, "timestamp": datetime.now().isoformat()}

    # 获取文件锁（防并发）
    if not _acquire_lock():
        time.sleep(5)  # 等 5 秒重试 1 次
        if not _acquire_lock():
            report["status"] = "skip_lock_busy"
            return report

    # cycle 5 LOW-1 修复：target 在 try 块外声明，except 块复用 try 块已获取的 target
    # （原 except 块重复调 get_user_data_dir 重新获取 target，可能因环境/配置变化返回不同路径，
    #  导致清理的不是同一目录；且重复调用浪费——try 块已 resolve 过路径，复用即可）
    target = None
    try:
        # HIGH-009 修复（方向A）：ensure_subdirs=False 不创建子目录，
        # 避免子目录创建导致 any(target.iterdir()) 总为 True → 迁移永远被跳过。
        # 迁移成功后由 copytree 带过来子目录（包内有则复制），或迁移后补建。
        target = user_data_path.get_user_data_dir(ensure_subdirs=False)
        report["target"] = str(target)

        # 检测包内是否有用户数据
        src_dirs = ["memory", "docs_rj", "outputs_rj", "server_lite_data"]
        has_source = any((skill_root / d).exists() and any((skill_root / d).rglob("*")) for d in src_dirs)
        if not has_source:
            report["status"] = "skip_no_source"
            return report

        # 检测外置目录是否为空（ensure_subdirs=False 保证了外置真的为空时 iterdir() 返回空）
        if target.exists() and any(target.iterdir()):
            report["status"] = "skip_target_not_empty"
            return report

        # 原子复制（dirs_exist_ok=True 避免目录已存在冲突）
        for d in src_dirs:
            src = skill_root / d
            if src.exists():
                dst = target / d
                shutil.copytree(src, dst, dirs_exist_ok=True)

        # 校验文件数 + 字节数
        src_count, src_bytes = _count_files(skill_root, src_dirs)
        dst_count, dst_bytes = _count_files(target, src_dirs)
        if src_count != dst_count or src_bytes != dst_bytes:
            # 校验不一致 → 回滚（删外置半成品）
            shutil.rmtree(target, ignore_errors=True)
            report["status"] = "failed_verify_mismatch"
            return report

        report["file_count"] = dst_count
        report["bytes"] = dst_bytes

        # 写 .migrated 标记（含时间戳）
        marker = skill_root / MIGRATED_MARKER
        marker.write_text(json.dumps({"migrated_at": datetime.now().isoformat(),
                                       "file_count": dst_count, "bytes": dst_bytes}), encoding="utf-8")
        report["status"] = "success"
        # HIGH-003 方向B：_cleanup_legacy 改由 startup_tidy 独立调用（与 migrate_if_needed 解耦）。
        # 迁移函数只管迁移，清理归 startup_tidy 启动时检测 .migrated 标记是否超 7 天。
        return report
    except (OSError, shutil.Error) as e:
        # 复制中断 → 保留包内原件 + 清理外置半成品
        # cycle 5 LOW-1 修复：复用 try 块已获取的 target（避免重复调 get_user_data_dir）
        if target is not None:
            shutil.rmtree(target, ignore_errors=True)
        report["status"] = "failed_rolled_back"
        report["error"] = str(e)
        return report
    finally:
        _release_lock()


def _count_files(base: Path, dirs: list) -> tuple:
    """统计目录下文件数 + 总字节数。

    Args:
        base: 基准目录路径。
        dirs: 要统计的子目录名列表。

    Returns:
        tuple: (文件数, 总字节数)。
    """
    count, total = 0, 0
    for d in dirs:
        p = base / d
        if p.exists():
            for f in p.rglob("*"):
                if f.is_file():
                    count += 1
                    total += f.stat().st_size
    return (count, total)


def _cleanup_legacy(skill_root: str) -> dict:
    """7 天后清理包内数据（原子操作：标记→删除→标记）。

    由 startup_tidy 独立调用（HIGH-003 方向B：与 migrate_if_needed 解耦）。
    启动时检测 .migrated 标记是否超 7 天回滚窗口，超期则清理包内数据。

    原子清理流程：
    1. 写 .cleaning 标记（表示清理中，中断可续）
    2. 删除包内 memory/ docs_rj/ outputs_rj/ server_lite_data/
    3. 写 .cleaned 标记（表示清理完成）
    4. 删除 .migrated 标记（cycle 5 LOW-6 修复：表示清理流程已完结）

    Args:
        skill_root: skill 包根目录绝对路径。

    Returns:
        dict: 清理报告，含 status 字段：
            - skip_no_marker: 无 .migrated 标记（未迁移过）
            - skip_within_retention: 未超 7 天回滚窗口
            - skip_invalid_marker: .migrated 标记格式无效
            - cleaned: 清理完成
    """
    skill_root = Path(skill_root).resolve()
    marker = skill_root / MIGRATED_MARKER
    if not marker.exists():
        return {"status": "skip_no_marker"}

    try:
        info = json.loads(marker.read_text(encoding="utf-8"))
        migrated_at = datetime.fromisoformat(info["migrated_at"])
        if datetime.now() - migrated_at < timedelta(days=RETENTION_DAYS):
            return {"status": "skip_within_retention"}
    except (json.JSONDecodeError, KeyError, ValueError):
        return {"status": "skip_invalid_marker"}

    # 原子清理：写 .cleaning → 删除 → 写 .cleaned
    cleaning = skill_root / CLEANING_MARKER
    cleaning.write_text(datetime.now().isoformat(), encoding="utf-8")

    src_dirs = ["memory", "docs_rj", "outputs_rj", "server_lite_data"]
    for d in src_dirs:
        p = skill_root / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    cleaning.unlink(missing_ok=True)
    (skill_root / CLEANED_MARKER).write_text(datetime.now().isoformat(), encoding="utf-8")
    # cycle 5 LOW-6 修复：清理后删除 .migrated 标记（原不删导致下次启动再次检测 .migrated
    #   → 再次跑清理逻辑（虽然数据已清空不会重复删，但无意义且增加日志噪声）；
    #   .cleaned 标记保留作为"已清理"的证据，.migrated 标记删除表示"清理流程已完结"）
    marker.unlink(missing_ok=True)
    return {"status": "cleaned"}


def main():
    """CLI 入口：支持 --dry-run 预览 + --skill-root 指定包根。"""
    import argparse
    parser = argparse.ArgumentParser(description="用户数据迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际迁移")
    parser.add_argument("--skill-root", default=os.getcwd(), help="skill 包根目录路径")
    args = parser.parse_args()
    report = migrate_if_needed(args.skill_root) if not args.dry_run else {"dry_run": True, "target": str(user_data_path.get_user_data_dir())}
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
