#!/usr/bin/env python3
r"""用户数据路径解析模块（三级优先级：环境变量 > 配置文件 > 默认值）。

本模块负责解析用户数据外置目录的位置，与 skill 包框架文件物理分离。
升级 skill 包（解压覆盖）时，用户累积的 memory/docs_rj/outputs_rj/server_lite_data
数据不丢失——它们存在 ~/.pdca-skill/data/ 下，与包内文件无关。

三级优先级：
1. 环境变量 PDCA_DATA_DIR（最高优先级，供测试/多实例使用）
2. 配置文件 ~/.pdca-skill/config.json 的 data_dir 字段（供前端修改）
3. 默认值 ~/.pdca-skill/data/（首次使用自动创建）

安全防护：
- MAX_PATH 检测（Windows 260 字符限制）
- UNC 路径检测（\\server\share 网络路径拒绝）
- 符号链接检测（resolve 后校验真实路径在用户目录下，防符号链接攻击）
- 权限设置（Unix 目录 700 / 配置文件 600）

外置不可创建时 raise PermissionError 告警退出，**不降级到包内**——
降级会导致用户数据双写（包内 + 外置），升级时包内数据丢失。
"""
import os
import sys
import json
import stat
from pathlib import Path

DEFAULT_DATA_DIR = Path.home() / ".pdca-skill" / "data"
CONFIG_FILE = Path.home() / ".pdca-skill" / "config.json"
MAX_PATH_LIMIT = 260  # Windows MAX_PATH 限制


def get_user_data_dir(ensure_subdirs: bool = True) -> Path:
    """三级优先级解析用户数据目录。外置不可创建时告警退出（不降级到包内）。

    Args:
        ensure_subdirs: 是否创建 4 个子目录（memory/ docs_rj/ outputs_rj/ server_lite_data/）。
            - True（默认）：创建子目录，供正常读写使用。
            - False：不创建子目录，供 migrate_if_needed 检测"外置是否为空"时调用——
              避免子目录创建导致 any(target.iterdir()) 总为 True → 迁移永远被跳过的 bug。
            迁移成功后由 migrate_if_needed 负责创建子目录（copytree 会带过来，或迁移后补建）。

    Returns:
        Path: 用户数据目录路径（已创建）。

    Raises:
        PermissionError: 默认外置目录无法创建（无权限/磁盘满/路径安全检测失败）。
            告警退出，不降级到包内（防数据双写 + 升级丢失）。
    """
    result = None
    # 1. 环境变量 PDCA_DATA_DIR
    env_path = os.environ.get("PDCA_DATA_DIR")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        # cycle 5 HIGH-1 修复：_check_path_safety raise 后 try/except 捕获降级（与 §4.1 边界情况对齐）
        try:
            _check_path_safety(p)  # MAX_PATH/UNC/符号链接检测
            if _ensure_dir(p):
                result = p
            else:
                sys.stderr.write("[WARN] 环境变量 PDCA_DATA_DIR 指向目录无权限，降级到下一级\n")
        except OSError as e:
            sys.stderr.write("[WARN] 环境变量 PDCA_DATA_DIR 路径安全检测失败(%s)，降级到下一级\n" % e)
    # 2. 配置文件 ~/.pdca-skill/config.json
    if result is None and CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg_path = cfg.get("data_dir")
            if cfg_path:
                p = Path(cfg_path).expanduser().resolve()
                # cycle 5 HIGH-1 修复：_check_path_safety raise 后 try/except 捕获降级
                try:
                    _check_path_safety(p)
                    if _ensure_dir(p):
                        result = p
                    else:
                        sys.stderr.write("[WARN] 配置文件 data_dir 指向目录无权限，降级到默认值\n")
                except OSError as e:
                    sys.stderr.write("[WARN] 配置文件 data_dir 路径安全检测失败(%s)，降级到默认值\n" % e)
        except (json.JSONDecodeError, KeyError):
            sys.stderr.write("[WARN] 配置文件 JSON 格式错误，用默认值: %s\n" % CONFIG_FILE)
    # 3. 默认值 ~/.pdca-skill/data/
    if result is None:
        # cycle 5 HIGH-1 修复：默认值路径安全检测失败也降级告警退出（不降级到包内）
        try:
            _check_path_safety(DEFAULT_DATA_DIR)
        except OSError as e:
            sys.stderr.write("[ERROR] 默认外置目录路径安全检测失败(%s)，告警退出，不降级到包内\n" % e)
            raise PermissionError("默认用户数据目录路径安全检测失败: %s" % e)
        if not _ensure_dir(DEFAULT_DATA_DIR):
            sys.stderr.write("[ERROR] 默认外置目录无法创建（无权限/磁盘满），告警退出，不降级到包内\n")
            raise PermissionError("无法创建用户数据目录，请检查权限或设置 PDCA_DATA_DIR 环境变量")
        result = DEFAULT_DATA_DIR
    # 创建子目录（memory/ docs_rj/ outputs_rj/ server_lite_data/，权限 700）
    # HIGH-009 修复：ensure_subdirs=False 时不创建，供迁移检测"外置是否为空"使用
    if ensure_subdirs:
        for sub in ["memory", "docs_rj", "outputs_rj", "server_lite_data"]:
            _ensure_dir(result / sub)
    return result


def _check_path_safety(path: Path) -> None:
    """路径安全检测：MAX_PATH / UNC / 符号链接指向用户目录外。失败 raise OSError。

    cycle 5 HIGH-1 修复（第五轮 fresh subagent 重验发现 3 层问题）：
    ① 与 §0 约束5 矛盾——已通过 AskUserQuestion 决策为"必须在用户目录下"，
       同步更新 §0 约束5 + §4.1 边界情况表述；
    ② raise 后不降级导致崩溃——已改为 get_user_data_dir 用 try/except 捕获后
       降级到下一级 + 告警（与 §4.1 边界情况对齐）；
    ③ 与 _validate_path 不一致——已同步在 _validate_path 加"必须在用户目录下"限制；
    ④ startswith 误判（MEDIUM-6 归并到本 HIGH-1 一起修）："/home/user2".startswith("/home/user")=True
       → 改用 is_relative_to(home)（Python 3.9+，本项目 3.11+ OK），路径组件边界比较，
       严格判断 path 是否在 home 子树内。
    """
    path_str = str(path)
    # Windows MAX_PATH 检测
    if len(path_str) > MAX_PATH_LIMIT:
        raise OSError("路径超过 Windows MAX_PATH 限制(%d)，请改用短路径" % MAX_PATH_LIMIT)
    # UNC 路径检测（\\server\share）
    if path_str.startswith("\\\\"):
        raise OSError("不支持 UNC 网络路径，请改用本地路径")
    # 符号链接检测（resolve 后校验真实路径在用户目录下）
    # cycle 5 HIGH-1 修复：startswith → is_relative_to，严格子树判断
    # cycle 6 M-1 修复：resolve 失败时 raise（不 pass 跳过符号链接检测）
    # 原 pass 会导致 home 解析失败时跳过 is_relative_to 检查，恶意符号链接可能通过
    # 保守策略：任何 resolve 失败都 raise（宁可错杀不放过）
    try:
        real = path.resolve()
        home = Path.home().resolve()
    except OSError as e:
        raise OSError("路径或用户目录 resolve 失败（可能为符号链接攻击或权限问题）: %s" % e)
    if not real.is_relative_to(home):
        raise OSError("路径 resolve 后不在用户目录下，可能为符号链接攻击: %s" % real)


def _ensure_dir(path: Path) -> bool:
    """确保目录存在 + 设权限 700，无权限返回 False。

    Args:
        path: 要创建的目录路径。

    Returns:
        bool: True 表示目录已存在或创建成功；False 表示无权限或磁盘满。
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Unix 设权限 700（Windows 无效但不报错）
        if sys.platform != "win32":
            os.chmod(path, stat.S_IRWXU)
        return True
    except (PermissionError, OSError) as e:
        sys.stderr.write("[WARN] 创建目录失败 %s: %s\n" % (path, e))
        return False


def set_user_data_dir(path: str) -> bool:
    """写入配置文件（供前端修改）。先校验路径安全再写入。

    cycle 5 LOW-2 修复：写完配置文件后设权限 600（仅所有者可读写），
    防其他用户读取配置中的路径信息（原仅 _ensure_dir 设目录权限 700，
    但配置文件本身权限未设，可能默认 644 让其他用户可读）。
    Windows chmod 600 无效但不报错（与 _ensure_dir 一致）。

    Args:
        path: 新的用户数据目录路径。

    Returns:
        bool: True 表示写入成功。

    Raises:
        OSError: 路径安全检测失败（MAX_PATH/UNC/符号链接）。
    """
    p = Path(path).expanduser().resolve()
    _check_path_safety(p)  # 校验新路径安全
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    cfg["data_dir"] = str(p)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    # cycle 5 LOW-2 修复：设权限 600（仅所有者可读写，防其他用户读取配置路径信息）
    if sys.platform != "win32":
        try:
            os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # 权限设置失败不阻断（与 _ensure_dir 一致，告警但继续）
    return True


def get_memory_main_path() -> Path:
    """返回全局聚合记忆文件路径（memory/memory_main.md）。"""
    return get_user_data_dir() / "memory" / "memory_main.md"


def get_memory_main_path_with_fallback(skill_dir=None):
    """返回 memory_main.md 路径，优先外部，失败/不存在则退回包内。

    用于 route_check / loop_admission / skill_graph_extract / skill_graph_build
    等脚本兼容老用户（包内 memory_main.md）+ 新用户（外部 memory_main.md）。

    优先级：
    1. 外部路径 ~/.pdca-skill/data/memory/memory_main.md（经 get_memory_main_path 三级解析）
       —— 仅当文件存在时采用（避免新用户/未迁移时把检查指向空路径）
    2. 包内路径 {skill_dir}/memory/memory_main.md（退回兜底）
       —— 老用户未迁移 / 外部路径解析失败 / 外部文件不存在 时使用

    Args:
        skill_dir: skill 包根目录绝对路径。None 时自动检测（user_data_path.py
            所在 scripts/ 的上级目录 = skill 包根）。

    Returns:
        str: memory_main.md 绝对路径（可能在外部或包内）。
    """
    # 1. 优先外部
    try:
        external = get_memory_main_path()
        if os.path.isfile(external):
            return str(external)
    except (PermissionError, OSError) as e:
        sys.stderr.write("[WARN] 外部 memory_main.md 解析失败(%s)，退回包内\n" % e)

    # 2. 退回包内
    if skill_dir is None:
        # 自动检测：user_data_path.py 位于 scripts/，上一级即 skill 包根
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(skill_dir, 'memory', 'memory_main.md')


def get_docs_rj_path() -> Path:
    """返回项目文档目录路径（docs_rj/）。"""
    return get_user_data_dir() / "docs_rj"


def get_memory_rj_path() -> Path:
    """返回项目记忆目录路径（docs_rj/memory_rj/）。

    统一封装，消除 4 处调用方重复拼接 / "memory_rj" 的漂移风险。
    注意：此路径为外置用户数据目录下的回退路径；
    若项目存在 .primary_docs_rj 标记，调用方应优先使用 primary/memory_rj。
    """
    return get_docs_rj_path() / "memory_rj"


def get_outputs_rj_path() -> Path:
    """返回输出目录路径（outputs_rj/）。"""
    return get_user_data_dir() / "outputs_rj"


def get_server_lite_data_path() -> Path:
    """返回 server_lite 数据目录路径（server_lite_data/）。"""
    return get_user_data_dir() / "server_lite_data"


def external_docs_has_content() -> bool:
    """判断外置用户数据目录下是否有真实遗留文档（递归数 *.md 文件，>0 返 True）。

    v1.0.4 新增（REQ-108，对抗审查 H1/H2 共用检测源）：
    - 供 generate_docs.find_docs_dir 与 startup_tidy._ensure_project_structure 共用，
      禁止各自实现判定（防两套标准漂移）。
    - ⚠️ 不得用"目录存在/子目录非空"判断——get_user_data_dir(ensure_subdirs=True)
      会为所有用户自动创建 memory/docs_rj/outputs_rj/server_lite_data 空子目录，
      目录存在性判断会把新项目全部误判为"有遗留"而路由回外置（复现旧版
      "文档跑去主目录"问题）。
    - 目录不存在/任意异常一律返 False（宽捕获：守卫有不抛出契约，
      Path.resolve 符号链接死循环会抛 RuntimeError，不可穿透）。
    """
    try:
        docs_dir = get_docs_rj_path()
        if not docs_dir.is_dir():
            return False
        for _ in docs_dir.rglob('*.md'):
            return True
        return False
    except Exception:
        return False
