#!/usr/bin/env python3
"""数据管理 API（路径遍历防护 + 仅 localhost 访问）

端点：
- GET /api/settings/data-path — 返回当前数据位置 + 统计信息
- POST /api/settings/data-path — 修改数据位置（写入配置文件，不立即迁移）
- POST /api/settings/migrate — 触发数据迁移到新位置

T010 实现：含 _validate_path 路径遍历防护（拒绝 ../、skill 包内、系统目录、用户目录外路径）
+ 系统目录黑名单（cycle 5 MEDIUM-7 补全）+ is_relative_to 严格子树判断（cycle 5 MEDIUM-6）
+ 必须在用户目录下（cycle 5 HIGH-1）。
migrate 端点 bug 修复：HIGH-2（先 set_user_data_dir 再 migrate_if_needed）
+ cycle 5 MEDIUM-4（环境变量临时覆盖）+ cycle 5 MEDIUM-5（配置文件回滚）
+ cycle 7 H-1-NEW（status 分流：success/skip_no_source/skip_target_not_empty 走成功路径，
  failed_*/skip_lock_busy 走失败路径恢复 env + 回滚配置）。
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import user_data_path

bp = Blueprint("settings", __name__, url_prefix="/api/settings")

# 系统目录黑名单（路径遍历防护）
# cycle 5 MEDIUM-7 修复：补全黑名单（原缺 /root /lib /lib64 /opt /srv /run /tmp /var/tmp
#   + Windows C:\Users\All Users / C:\ProgramData / C:\Program Files (x86) / C:\ProgramData 等）
SYSTEM_DIRS = [
    # Unix 系统目录
    "/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc",
    "/root", "/lib", "/lib64", "/opt", "/srv", "/run", "/tmp", "/var/tmp",
    "/dev", "/mnt", "/media",  # 挂载点/设备目录
    # Windows 系统目录
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\System32", "C:\\system32", "C:\\ProgramData",
    "C:\\Users\\All Users", "C:\\Users\\Default", "C:\\Users\\Public",
    "C:\\$Recycle.Bin",  # 回收站
]

def _validate_path(path: str) -> tuple:
    """路径校验：拒绝 ../、skill 包内、系统目录、用户目录外路径。返回 (is_valid, error_msg)

    cycle 5 HIGH-1 修复：加"必须在用户目录下"限制（与 _check_path_safety 对齐）。
    cycle 5 MEDIUM-6 修复：startswith → is_relative_to，严格子树判断（防 "/home/user2".startswith("/home/user")=True 误判）。
    cycle 5 MEDIUM-7 修复：系统目录黑名单补全（见上方 SYSTEM_DIRS 列表）。
    """
    if not path:
        return (False, "路径不能为空")
    try:
        p = Path(path).expanduser().resolve()
    except (OSError, ValueError) as e:
        return (False, "路径解析失败: %s" % str(e))

    path_str = str(p)
    # 拒绝含 .. 的原始输入（resolve 前检查）
    if ".." in path:
        return (False, "路径含 .. 拒绝路径遍历攻击")
    # 拒绝 skill 包内路径（用 is_relative_to 严格判断，防 startswith 误判）
    skill_root = Path(__file__).resolve().parent.parent
    if p.is_relative_to(skill_root):
        return (False, "不能指向 skill 包内")
    # 拒绝系统目录（用 is_relative_to 严格判断）
    for sys_dir in SYSTEM_DIRS:
        try:
            if p.is_relative_to(Path(sys_dir)):
                return (False, "不能指向系统目录: %s" % sys_dir)
        except (OSError, ValueError):
            continue  # 跨平台路径解析失败时跳过该条目
    # cycle 5 HIGH-1 修复：拒绝用户目录外路径（与 _check_path_safety 对齐）
    # 必须在用户目录下（Path.home() 子树内），防数据被升级覆盖/防写入系统敏感位置
    try:
        home = Path.home().resolve()
        if not p.is_relative_to(home):
            return (False, "路径必须在用户目录下(%s)，拒绝用户目录外路径: %s" % (home, p))
    except (OSError, ValueError) as e:
        return (False, "用户目录解析失败: %s" % str(e))
    # 校验父目录存在且可写
    if not p.parent.exists():
        return (False, "父目录不存在: %s" % p.parent)
    return (True, "")

@bp.route("/data-path", methods=["GET"])
def get_data_path():
    """返回当前数据位置 + 统计信息"""
    try:
        data_dir = user_data_path.get_user_data_dir()
        file_count = sum(1 for _ in data_dir.rglob("*") if _.is_file())
        size_bytes = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())
        size_mb = round(size_bytes / (1024 * 1024), 2)
        last_modified = datetime.fromtimestamp(data_dir.stat().st_mtime).isoformat()
        return jsonify({"path": str(data_dir), "size_mb": size_mb,
                        "file_count": file_count, "last_modified": last_modified})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/data-path", methods=["POST"])
def set_data_path():
    """修改数据位置（写入配置文件，不立即迁移）"""
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    is_valid, err = _validate_path(path)
    if not is_valid:
        return jsonify({"error": err}), 400
    try:
        user_data_path.set_user_data_dir(path)
        return jsonify({"status": "ok", "new_path": path})
    except (PermissionError, OSError) as e:
        return jsonify({"error": str(e)}), 403

@bp.route("/migrate", methods=["POST"])
def migrate_data():
    """触发数据迁移到新位置。

    HIGH-2 修复（cycle 4）：原代码接收 target_path 但没先 set_user_data_dir(target_path)
    就调 migrate_if_needed，导致 migrate_if_needed 读到的仍是旧路径，迁移迁到旧位置。
    修复：先 set_user_data_dir(target_path) 写配置 → 再调 migrate_if_needed(skill_root)
    从包内迁到新目标（与 task T010 第 155 行描述一致）。

    cycle 5 MEDIUM-4 修复（环境变量优先级导致 set_user_data_dir 无效）：
    set_user_data_dir 写配置文件，但 get_user_data_dir 优先读环境变量 PDCA_DATA_DIR——
    如果环境变量已设置，set_user_data_dir 写的配置不会生效，migrate_if_needed 读到的
    仍是旧路径（环境变量指向的旧位置）。
    修复方案：临时设置环境变量 PDCA_DATA_DIR=target_path 覆盖配置文件优先级；
    迁移成功后 pop 环境变量（让后续读配置文件 target_path），
    迁移失败时恢复原环境变量（与配置回滚一致）。
    cycle 7 H-1-NEW 修复：migrate_if_needed 返回 failed_* / skip_lock_busy 时按失败处理
    （恢复 env_backup + 回滚配置），避免假成功导致用户立即看不到老数据。

    cycle 5 MEDIUM-5 修复（迁移失败配置未回滚）：
    迁移失败后配置文件仍指向 target_path（空目录），下次启动 get_user_data_dir
    会读到这个空目录 → 用户看不到老数据。
    修复方案：迁移前备份配置文件内容，迁移失败时回滚配置文件（恢复备份）；
    迁移成功时保留新配置（target_path 已写入）。
    """
    data = request.get_json(silent=True) or {}
    target_path = data.get("target_path", "")
    is_valid, err = _validate_path(target_path)
    if not is_valid:
        return jsonify({"error": err}), 400
    # cycle 5 MEDIUM-5 修复：备份当前配置文件内容（迁移失败时回滚）
    config_backup = None
    if user_data_path.CONFIG_FILE.exists():
        try:
            config_backup = user_data_path.CONFIG_FILE.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            config_backup = None  # 配置文件读取失败时无备份可回滚
    # cycle 5 MEDIUM-4 修复：备份原环境变量（迁移后恢复）
    env_backup = os.environ.get("PDCA_DATA_DIR")
    try:
        import migrate_user_data
        # HIGH-2 修复：先写配置让 migrate_if_needed 读到新目标路径（而非旧路径）
        user_data_path.set_user_data_dir(target_path)
        # cycle 5 MEDIUM-4 修复：临时设置环境变量覆盖配置文件优先级
        # （set_user_data_dir 写配置，但 get_user_data_dir 优先读环境变量——
        #  如果环境变量已设置，配置文件不生效；临时设置环境变量强制覆盖）
        os.environ["PDCA_DATA_DIR"] = target_path
        skill_root = Path(__file__).resolve().parent.parent
        report = migrate_user_data.migrate_if_needed(str(skill_root))
        status = report.get("status", "")
        # cycle 6 H-1 修复：迁移成功后 pop 环境变量（让后续读配置文件 target_path）
        # 原 cycle 5 MEDIUM-4 finally 无条件恢复导致：env_backup 非空时恢复旧值 → 后续读旧路径（空目录）
        # cycle 7 H-1-NEW 修复：检查 migrate_if_needed 返回 status 分流（原 cycle 6 H-1 未检查 status，
        #   failed_* / skip_lock_busy 走成功路径导致 target_path 空目录 + 配置未回滚 → 用户立即看不到老数据）
        if status in ("success", "skip_no_source", "skip_target_not_empty"):
            # 成功或安全跳过：pop 环境变量，让后续读配置文件 target_path
            os.environ.pop("PDCA_DATA_DIR", None)
            return jsonify(report)
        else:
            # 失败（skip_lock_busy / failed_verify_mismatch / failed_rolled_back 等）：
            # 走失败路径——恢复 env_backup + 回滚配置（与 except 块逻辑一致）
            if env_backup is not None:
                os.environ["PDCA_DATA_DIR"] = env_backup
            else:
                os.environ.pop("PDCA_DATA_DIR", None)
            if config_backup is not None:
                try:
                    user_data_path.CONFIG_FILE.write_text(config_backup, encoding="utf-8")
                except OSError:
                    pass
            else:
                try:
                    user_data_path.CONFIG_FILE.unlink(missing_ok=True)
                except OSError:
                    pass
            return jsonify(report), 500
    except (PermissionError, OSError) as e:
        # cycle 6 H-1 修复：失败时恢复环境变量（让后续读旧路径，与配置回滚一致）
        if env_backup is not None:
            os.environ["PDCA_DATA_DIR"] = env_backup
        else:
            os.environ.pop("PDCA_DATA_DIR", None)
        # cycle 5 MEDIUM-5 修复：迁移失败回滚配置文件（恢复备份）
        # cycle 6 M-3 修复：config_backup is None 时删除配置文件（set_user_data_dir 已创建新配置）
        if config_backup is not None:
            try:
                user_data_path.CONFIG_FILE.write_text(config_backup, encoding="utf-8")
            except OSError:
                pass  # 回滚失败不抛新异常，仅告警
        else:
            try:
                user_data_path.CONFIG_FILE.unlink(missing_ok=True)
            except OSError:
                pass
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        # cycle 6 H-1 修复：失败时恢复环境变量
        if env_backup is not None:
            os.environ["PDCA_DATA_DIR"] = env_backup
        else:
            os.environ.pop("PDCA_DATA_DIR", None)
        # cycle 5 MEDIUM-5 修复：迁移失败回滚配置文件（恢复备份）
        # cycle 6 M-3 修复：config_backup is None 时删除配置文件
        if config_backup is not None:
            try:
                user_data_path.CONFIG_FILE.write_text(config_backup, encoding="utf-8")
            except OSError:
                pass
        else:
            try:
                user_data_path.CONFIG_FILE.unlink(missing_ok=True)
            except OSError:
                pass
        return jsonify({"error": str(e)}), 500
