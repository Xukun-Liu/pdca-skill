"""server_lite 配置"""
import os
import sys

# server_lite 包目录（server_lite/）
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# pdca-skill 项目根目录（server_lite 的上级）
SKILL_ROOT = os.path.dirname(PACKAGE_DIR)

# 把 scripts/ 目录加入 sys.path，以便 import user_data_path
# user_data_path.py 在 scripts/ 目录下，提供用户数据外置路径解析（三级优先级 + 安全检测）
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
import user_data_path  # noqa: E402  用户数据外置路径解析模块

# 扫描根目录 = 项目上级目录（扫上级一层，不递归）
SCAN_ROOT = os.path.dirname(SKILL_ROOT)


class DefaultConfig:
    """默认配置"""
    # 扫描根目录（扫上级一层子目录，只列含 docs_rj/ 的）
    SCAN_ROOT = SCAN_ROOT
    # pdca-skill 根目录
    SKILL_ROOT = SKILL_ROOT
    # references/ 目录
    REFERENCES_DIR = os.path.join(SKILL_ROOT, "references")
    # agents_rj/ 目录
    AGENTS_DIR = os.path.join(SKILL_ROOT, "agents_rj")
    # 数据目录（用户数据外置：~/.pdca-skill/data/server_lite_data/）
    DATA_DIR = str(user_data_path.get_server_lite_data_path())
    # sidecar JSON 目录（与 references/ 同级，存频率元数据）
    METADATA_DIR = str(user_data_path.get_server_lite_data_path() / "metadata")
    # 端口
    PORT = 5210
    # JSON 排序键
    JSON_SORT_KEYS = False
