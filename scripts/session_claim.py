"""
会话认领锁（session claim lock）

用途：当多个 AI 对话同时改同一个 git 仓库时，动手前先“认领”要改的文件，
避免两个对话改同一批文件后互相覆盖，且事后无法判断是谁改的。

设计要点：
1. 锁记录存放在 <git-common-dir>/agents-locks/ 下。该目录在 .git 内部，
   git 永远不会把它提交进仓库，也不污染工作区。
2. 存活判断只用 TTL + 心跳，不依赖进程号。因为 AI 每次执行命令都是新进程，
   pid 在命令结束后立刻失效，用它判断存活会全部误判为过期。
3. 跨进程原子性由 msvcrt(Windows) / fcntl(Linux) 文件锁保证，与
   memory_shadow_write.py 中的 _CrossProcessLock 同源，避免两套并发模型。

用法：
    python session_claim.py acquire --task B3-记忆地基 --files scripts/a.py docs/b.md --session 对话A-修bug
    python session_claim.py acquire --task B3-记忆地基 --files docs/ --ttl 60 --session 对话A-修bug
    python session_claim.py status
    python session_claim.py release --task B3-记忆地基 --session 对话A-修bug
    python session_claim.py gc

退出码：
    0 成功
    2 冲突（目标文件正被其他未过期的任务认领；release 时表示认领不属于该对话）
    3 环境或参数错误（非 git 仓库、缺 --session、路径指向仓库外等）
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import unicodedata

DEFAULT_TTL_MINUTES = 120
LOCK_DIRNAME = "agents-locks"


# ---------------------------------------------------------------------------
# 跨进程文件锁（与 memory_shadow_write.py 同源）
# ---------------------------------------------------------------------------

try:
    import msvcrt
    _HAVE_MSVC = True
except ImportError:
    _HAVE_MSVC = False

try:
    import fcntl
    _HAVE_FCNTL = True
except ImportError:
    _HAVE_FCNTL = False


class _CrossProcessLock:
    """跨进程互斥文件锁。

    用于“读全部 claim → 判定冲突 → 写入自己的 claim”这段临界区，
    否则两个对话可能同时读到“无人认领”而都写入成功。
    """

    def __init__(self, lockpath):
        self.lockpath = lockpath
        self._state = threading.local()

    def __enter__(self):
        depth = getattr(self._state, "depth", 0)
        if depth == 0:
            os.makedirs(os.path.dirname(self.lockpath), exist_ok=True)
            self._state.fd = os.open(self.lockpath, os.O_CREAT | os.O_RDWR)
            try:
                if _HAVE_MSVC:
                    msvcrt.locking(self._state.fd, msvcrt.LK_LOCK, 1)
                elif _HAVE_FCNTL:
                    fcntl.flock(self._state.fd, fcntl.LOCK_EX)
            except OSError as exc:
                os.close(self._state.fd)
                raise RuntimeError("获取认领锁失败：%s" % exc)
        self._state.depth = depth + 1
        return self

    def __exit__(self, *exc):
        self._state.depth -= 1
        if self._state.depth == 0:
            try:
                if _HAVE_MSVC:
                    msvcrt.locking(self._state.fd, msvcrt.LK_UNLCK, 1)
                elif _HAVE_FCNTL:
                    fcntl.flock(self._state.fd, fcntl.LOCK_UN)
            finally:
                os.close(self._state.fd)


# ---------------------------------------------------------------------------
# 路径与环境
# ---------------------------------------------------------------------------

def _git_out(*args):
    """执行 git 命令并返回去空白的 stdout，失败返回 None。"""
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout.strip() or None


def repo_root():
    """返回当前 git 仓库工作区根目录，非仓库返回 None。"""
    top = _git_out("rev-parse", "--show-toplevel")
    return os.path.normpath(top) if top else None


def lock_dir():
    """返回 <git-common-dir>/agents-locks 绝对路径，非仓库返回 None。"""
    common = _git_out("rev-parse", "--git-common-dir")
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.join(os.getcwd(), common)
    path = os.path.join(os.path.normpath(common), LOCK_DIRNAME)
    return path


def slugify(task):
    """把任务名转成安全文件名，保留中文与字母数字。"""
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", task).strip("_")
    return (slug or "task")[:60]


def claim_filename(task):
    """认领文件名 = 可读 slug + 任务名哈希。

    只用 slug 会让 "B3 记忆" 与 "B3_记忆" 落到同一个文件，后写者静默覆盖前者。
    追加哈希后不同任务名必然不同文件。
    """
    digest = hashlib.md5(task.encode("utf-8")).hexdigest()[:8]
    return "%s-%s.claim" % (slugify(task), digest)


def norm_path(root, raw):
    """把用户输入的路径统一成相对仓库根、正斜杠、无尾部斜杠的形式。"""
    text = raw.strip().replace("\\", "/")
    if os.path.isabs(text):
        try:
            text = os.path.relpath(text, root).replace("\\", "/")
        except ValueError:
            pass
    text = os.path.normpath(text).replace("\\", "/")
    if text in (".", ""):
        return ""
    return text.rstrip("/")


def overlaps(a, b):
    """判断两个路径声明是否可能改到同一处。

    覆盖四种情况：空串（整仓库）、完全相同、父子目录、通配符匹配（如 docs/*.md）。
    """
    if a == "" or b == "":
        return True
    if a == b:
        return True
    if b.startswith(a + "/") or a.startswith(b + "/"):
        return True
    if fnmatch.fnmatch(b, a) or fnmatch.fnmatch(a, b):
        return True
    return False


def is_stale(claim):
    """心跳超过 TTL 即视为过期，可被抢占。"""
    ttl = claim.get("ttl_minutes")
    if ttl is None:
        # 不能用 or 兜底：ttl_minutes 为 0 是合法输入（表示立即过期），or 会把它吃成默认值
        ttl = DEFAULT_TTL_MINUTES
    hb = claim.get("heartbeat_ts") or claim.get("created_ts") or 0
    return (time.time() - hb) > ttl * 60


def read_claims(path_dir):
    """读出全部 claim 记录，返回 [(文件路径, 数据字典)]。"""
    result = []
    if not os.path.isdir(path_dir):
        # 只读命令不该创建目录，没有认领就是空
        return result
    for name in sorted(os.listdir(path_dir)):
        if not name.endswith(".claim"):
            continue
        full = os.path.join(path_dir, name)
        try:
            with open(full, "r", encoding="utf-8") as fh:
                result.append((full, json.load(fh)))
        except (OSError, ValueError) as exc:
            # 不能静默跳过：文件损坏会让这条认领的保护无声消失
            print("警告：认领文件损坏已跳过：%s（%s）" % (name, exc), file=sys.stderr)
            continue
    return result


def fmt_time(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "-"


def pad(text, width):
    """按终端显示宽度补空格：中文/全角按 2 列算，否则表格会错位。"""
    s = str(text)
    used = sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)
    return s + " " * max(0, width - used)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_acquire(args):
    root = repo_root()
    locks = lock_dir()
    if not root or not locks:
        print("错误：当前目录不是 git 仓库，认领锁需要仓库环境。", file=sys.stderr)
        return 3
    if not args.files:
        print("错误：必须用 --files 指定要改的文件或目录。", file=sys.stderr)
        return 3
    if not args.session:
        # 不用 argparse required：缺参数会退码 2，与"冲突"退码混淆
        print(
            "错误：必须用 --session 标明是哪个对话（如 --session 对话A-修bug），"
            "否则无法区分同名任务。",
            file=sys.stderr,
        )
        return 3

    mine = [norm_path(root, p) for p in args.files]
    outside = [p for p in mine if p == ".." or p.startswith("../")]
    if outside:
        print(
            "错误：认领范围必须在当前仓库内，以下路径指向仓库外：%s"
            % "、".join(outside),
            file=sys.stderr,
        )
        return 3
    active_guard = os.path.join(locks, "_guard.lock")

    with _CrossProcessLock(active_guard):
        conflicts = []
        for path, claim in read_claims(locks):
            # 身份 = 任务名 + 对话标识。只按任务名豁免会让两个对话用同名任务
            # 互相覆盖认领记录（后写入者静默顶掉前者），必须双键比较。
            if claim.get("task") == args.task and claim.get("session") == args.session:
                continue
            if is_stale(claim):
                continue
            hit = [f for f in claim.get("files", []) if any(overlaps(m, f) for m in mine)]
            if hit:
                conflicts.append((claim, hit))

        if conflicts:
            print("✗ 认领失败：目标文件正被其他任务占用。", file=sys.stderr)
            for claim, hit in conflicts:
                print(
                    "  占用方：%s（对话 %s，最后心跳 %s）"
                    % (
                        claim.get("task"),
                        claim.get("session", "未标注"),
                        fmt_time(claim.get("heartbeat_ts")),
                    ),
                    file=sys.stderr,
                )
                print("  重叠文件：%s" % "、".join(hit), file=sys.stderr)
            print(
                "  处理方式：换一个不重叠的任务，或等对方 release，或确认对方已停止后执行 gc。",
                file=sys.stderr,
            )
            return 2

        now = time.time()
        target = os.path.join(locks, claim_filename(args.task))
        payload = {
            "task": args.task,
            "session": args.session,
            "files": mine,
            "host": socket.gethostname(),
            "created_ts": now,
            "heartbeat_ts": now,
            "ttl_minutes": args.ttl,
        }
        # 原子写：先写临时文件再 replace，避免写到一半崩溃留下坏 JSON
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)

    print("✓ 认领成功：%s" % args.task)
    print("  文件范围（%d 项）：%s" % (len(mine), "、".join(mine)))
    print("  有效期：%d 分钟，超时未刷新视为放弃" % args.ttl)
    return 0


def cmd_release(args):
    locks = lock_dir()
    if not locks:
        print("错误：当前目录不是 git 仓库。", file=sys.stderr)
        return 3
    if not args.session:
        print("错误：必须用 --session 标明是哪个对话。", file=sys.stderr)
        return 3
    target = os.path.join(locks, claim_filename(args.task))
    if not os.path.exists(target):
        print("提示：未找到任务 %s 的认领记录，无需释放。" % args.task)
        return 0
    with _CrossProcessLock(os.path.join(locks, "_guard.lock")):
        try:
            with open(target, "r", encoding="utf-8") as fh:
                owner = json.load(fh).get("session")
        except (OSError, ValueError):
            owner = None
        if owner and owner != args.session:
            print(
                "✗ 拒绝释放：任务 %s 的认领属于对话 %s，不是 %s。"
                % (args.task, owner, args.session),
                file=sys.stderr,
            )
            print(
                "  若确认对方已停止，等 TTL 过期后执行 gc；否则请对方自己 release。",
                file=sys.stderr,
            )
            return 2
        os.remove(target)
    print("✓ 已释放：%s" % args.task)
    return 0


def cmd_status(args):
    locks = lock_dir()
    if not locks:
        print("错误：当前目录不是 git 仓库。", file=sys.stderr)
        return 3
    claims = read_claims(locks)
    if not claims:
        print("当前没有任何任务认领文件。")
        return 0
    print(pad("任务", 28) + pad("对话", 12) + pad("最后心跳", 18) + pad("状态", 8) + "文件范围")
    for _, claim in claims:
        state = "已过期" if is_stale(claim) else "生效中"
        files = claim.get("files", [])
        shown = "、".join(files[:3]) + ("…" if len(files) > 3 else "")
        print(
            pad(claim.get("task", "-")[:14], 28)
            + pad((claim.get("session") or "-")[:6], 12)
            + pad(fmt_time(claim.get("heartbeat_ts")), 18)
            + pad(state, 8)
            + shown
        )
    return 0


def cmd_gc(args):
    locks = lock_dir()
    if not locks:
        print("错误：当前目录不是 git 仓库。", file=sys.stderr)
        return 3
    removed = 0
    for path, claim in read_claims(locks):
        if is_stale(claim):
            os.remove(path)
            removed += 1
            print("已清理过期认领：%s（最后心跳 %s）" % (claim.get("task"), fmt_time(claim.get("heartbeat_ts"))))
    print("清理完成，共移除 %d 条。" % removed)
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="多对话并发时的文件认领锁。",
        epilog="退出码：0 成功、2 冲突、3 环境或参数错误。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_acq = sub.add_parser("acquire", help="认领一批文件，冲突则失败")
    p_acq.add_argument("--task", required=True, help="任务名，作为认领唯一标识")
    p_acq.add_argument("--files", nargs="+", required=True, help="要改的文件或目录，可多个")
    p_acq.add_argument("--session", default=None, help="对话标识，必须能让各对话区分开（如 对话A-修bug）")
    p_acq.add_argument("--ttl", type=int, default=DEFAULT_TTL_MINUTES, help="有效期（分钟）")
    p_acq.set_defaults(func=cmd_acquire)

    p_rel = sub.add_parser("release", help="释放认领")
    p_rel.add_argument("--task", required=True, help="任务名")
    p_rel.add_argument("--session", default=None, help="你的对话标识，需与认领时一致")
    p_rel.set_defaults(func=cmd_release)

    p_sta = sub.add_parser("status", help="查看所有认领")
    p_sta.set_defaults(func=cmd_status)

    p_gc = sub.add_parser("gc", help="清理过期认领")
    p_gc.set_defaults(func=cmd_gc)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())