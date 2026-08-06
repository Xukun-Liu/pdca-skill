#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_graph_extract.py — 阶段1：双轨提取

左轨（记忆挖掘）：
  多源归一化读取（riji-skill + 8白名单AI工具 + 关键词发现）
  → 规则提取技能线索 → skills_raw.json

右轨（多源全集）：
  并行拉取4源（roadmap.sh + engineer_competency + GitHub Topics + SO Survey）
  → 归一化 → 规则去重 → master_taxonomy.json

用法：
  python scripts/skill_graph_extract.py --source all --output skills_raw.json
  python scripts/skill_graph_extract.py --source ai_tools --discover-only
  python scripts/skill_graph_extract.py --source riji --no-cache

技术约束：
  - 仅 Python 标准库（os/sys/json/re/hashlib/argparse/pathlib/urllib/subprocess）
  - 零新增第三方依赖
  - LLM 函数先降级到规则版本（T2 时补 LLM 调用）
"""

import os
import sys
import json
import re
import hashlib
import argparse
import logging
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 脚本所在目录 → skill 根目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)

# 缓存目录
_CACHE_DIR = os.path.join(_SKILL_DIR, 'docs_rj', 'memory_rj', '.skill_graph_cache')
_TAXONOMY_DATA_DIR = os.path.join(_SKILL_DIR, 'skill_data', 'taxonomy_sources')

# ===========================================================================
# 配置区
# ===========================================================================

# 8 白名单 AI 工具：工具名 → 候选路径列表（按优先级）
WHITELIST_TOOLS: Dict[str, List[str]] = {
    'trae': [
        os.path.expanduser('~/.trae-cn/memory'),
    ],
    'claude_code': [
        os.path.expanduser('~/.claude'),
    ],
    'cursor': [
        os.path.expanduser('~/.cursor'),
    ],
    'openclaw': [
        os.path.expanduser('~/.openclaw'),
    ],
    'windsurf': [
        os.path.expanduser('~/.codeium'),
        os.path.expanduser('~/.windsurf'),
    ],
    'cline': [
        os.path.expanduser('~/.cline'),
    ],
    'continue': [
        os.path.expanduser('~/.continue'),
    ],
    'github_copilot': [
        os.path.expanduser('~/.github-copilot'),
    ],
}

# 6 扫描根（关键词发现用）
def _get_scan_roots() -> List[str]:
    """获取扫描根列表，自动适配操作系统。"""
    home = os.path.expanduser('~')
    roots = [
        home,
        os.path.join(home, '.config'),
        os.path.join(home, '.local', 'share'),
    ]
    # Windows
    appdata = os.environ.get('APPDATA')
    local_appdata = os.environ.get('LOCALAPPDATA')
    if appdata:
        roots.append(appdata)
    if local_appdata:
        roots.append(local_appdata)
    # macOS
    mac_lib = os.path.join(home, 'Library', 'Application Support')
    if os.path.isdir(mac_lib):
        roots.append(mac_lib)
    # 项目当前工作目录 + 父目录链（向上2层）
    cwd = os.getcwd()
    roots.append(cwd)
    parent = os.path.dirname(cwd)
    if parent and parent != cwd:
        roots.append(parent)
        grandparent = os.path.dirname(parent)
        if grandparent and grandparent != parent:
            roots.append(grandparent)
    return roots

# 8 关键词
SCAN_KEYWORDS = [
    'memory', 'agent', 'skill', 'remember',
    'assistant', 'ai', 'conversation', 'session',
]

# 黑名单目录（跳过）
BLACKLIST_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'site-packages', 'dist', 'build', '.cache', 'tmp', 'Temp',
    '.npm', '.cache', 'cache', '__pypackages__',
}

# 规则提取用：技术栈关键词表（分类 → 关键词列表）
TECH_KEYWORDS: Dict[str, List[str]] = {
    '编程语言': [
        'Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Rust', 'C++', 'C#',
        'PHP', 'Ruby', 'Swift', 'Kotlin', 'Scala', 'R', 'Julia', 'Dart',
        'Bash', 'Shell', 'PowerShell', 'Lua', 'Perl', 'Elixir', 'Clojure',
    ],
    '前端框架': [
        'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'Nuxt.js',
        'jQuery', 'Bootstrap', 'Tailwind', 'CSS', 'HTML', 'Sass', 'Less',
        'webpack', 'Vite', 'Rollup', 'ESLint', 'Prettier',
    ],
    '后端框架': [
        'Django', 'Flask', 'FastAPI', 'Express', 'Koa', 'NestJS',
        'Spring', 'Spring Boot', 'Rails', 'Laravel', 'Gin', 'Echo',
        'Actix', 'Rocket', 'Tornado', 'Aiohttp',
    ],
    '数据库': [
        'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'SQLite', 'Oracle',
        'SQL Server', 'MariaDB', 'Elasticsearch', 'Cassandra', 'DynamoDB',
        'Neo4j', 'InfluxDB', 'ClickHouse', 'Supabase',
    ],
    '消息队列': [
        'Kafka', 'RabbitMQ', 'RocketMQ', 'NATS', 'Pulsar', 'ActiveMQ',
        'ZeroMQ', 'Redis Streams', 'CKafka',
    ],
    'DevOps与云原生': [
        'Docker', 'Kubernetes', 'K8s', 'Jenkins', 'GitLab CI', 'GitHub Actions',
        'Terraform', 'Ansible', 'Consul', 'Vault', 'Helm', 'Istio',
        'Prometheus', 'Grafana', 'ELK', 'Fluentd', 'Jaeger', 'ArgoCD',
    ],
    '云平台': [
        'AWS', 'Azure', 'GCP', 'Tencent Cloud', '腾讯云', '阿里云', 'Aliyun',
        '华为云', 'Vercel', 'Netlify', 'Cloudflare', 'Heroku', 'DigitalOcean',
        'COS', 'OSS', 'S3', 'EC2', 'Lambda', 'Cloud Run',
    ],
    'AI与机器学习': [
        'TensorFlow', 'PyTorch', 'Keras', 'scikit-learn', 'pandas', 'NumPy',
        'SciPy', 'Matplotlib', 'Jupyter', 'Hugging Face', 'OpenAI', 'LangChain',
        'LlamaIndex', 'transformers', 'CUDA', 'Spark MLlib',
    ],
    '工具链': [
        'Git', 'SVN', 'Mercurial', 'npm', 'yarn', 'pnpm', 'pip', 'poetry',
        'conda', 'cargo', 'Maven', 'Gradle', 'Make', 'CMake',
    ],
    '安全': [
        'OAuth2', 'JWT', 'SSL', 'TLS', 'HTTPS', 'CORS', 'CSP',
        'XSS', 'CSRF', 'SQL注入', 'SAML', 'OpenID', '加密', '解密',
    ],
    '文档与工程': [
        'Markdown', 'LaTeX', 'Swagger', 'OpenAPI', 'Postman',
        'JIRA', 'Confluence', 'Notion', 'spec', 'DoD', 'PDCA',
    ],
}

# 硬编码降级：常见技能全集（4源拉取失败时用）
FALLBACK_TAXONOMY = [
    # 编程语言
    'Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Rust', 'C', 'C++', 'C#',
    'PHP', 'Ruby', 'Swift', 'Kotlin', 'Scala', 'R', 'Julia', 'Dart', 'Lua',
    # 前端
    'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'jQuery', 'Tailwind', 'Sass',
    # 后端
    'Django', 'Flask', 'FastAPI', 'Express', 'Koa', 'Spring Boot', 'Rails', 'Laravel',
    # 数据库
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'SQLite', 'Elasticsearch', 'Neo4j',
    # 消息队列
    'Kafka', 'RabbitMQ', 'RocketMQ', 'NATS', 'Pulsar',
    # DevOps
    'Docker', 'Kubernetes', 'Jenkins', 'Terraform', 'Ansible', 'Prometheus', 'Grafana',
    # 云
    'AWS', 'Azure', 'GCP', '腾讯云', '阿里云', 'Cloudflare', 'Vercel',
    # AI/ML
    'TensorFlow', 'PyTorch', 'Keras', 'scikit-learn', 'pandas', 'NumPy',
    'Hugging Face', 'LangChain', 'OpenAI',
    # 工具
    'Git', 'npm', 'pip', 'poetry', 'conda', 'cargo', 'Maven',
    # 安全
    'OAuth2', 'JWT', 'SSL/TLS', 'CORS', 'XSS防护', 'CSRF防护',
    # 软技能
    '系统设计', '代码审查', '技术方案', '项目管理', '需求分析', '团队协作',
    '文档编写', '沟通表达', '问题排查', '性能优化', '测试设计',
]

# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class RawMemory:
    """归一化后的记忆条目。"""
    source_tool: str          # riji / trae / claude_code / cursor / ...
    file: str                 # 文件路径
    timestamp: str            # ISO 格式或空
    content: str              # 文件内容（或摘要）
    skill_hints: List[str] = field(default_factory=list)

@dataclass
class SkillNode:
    """全集中的技能节点。"""
    id: str                   # 唯一标识（source:name 格式）
    name: str                 # 技能名
    category: str             # 分类
    source: str               # roadmap.sh / engineer_competency / github_topics / so_survey / fallback
    tags: List[str] = field(default_factory=list)
    description: str = ''
    learning_link: str = ''

@dataclass
class RawSkill:
    """从记忆中提取的已掌握技能线索。"""
    name: str
    evidence: List[Dict] = field(default_factory=list)
    category_hint: str = ''
    confidence: float = 0.0

# ===========================================================================
# 工具函数
# ===========================================================================

def _compute_hash(filepath: str) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return ''

def _atomic_write_json(filepath: str, data) -> bool:
    """原子写入 JSON 文件（先写临时文件再重命名）。"""
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    tmp = filepath + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, filepath)
        return True
    except (OSError, IOError, TypeError) as e:
        logger.error('写入 JSON 失败 %s: %s', filepath, e)
        if os.path.exists(tmp):
            os.remove(tmp)
        return False

def _safe_read_text(filepath: str, max_bytes: int = 512 * 1024) -> str:
    """安全读取文本文件，处理编码问题，限制大小。"""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(max_bytes)
        # 尝试 UTF-8，失败降级 GBK（Windows 常见）
        for enc in ('utf-8', 'utf-8-sig', 'gbk', 'latin-1'):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', errors='replace')
    except (OSError, IOError):
        return ''

def _is_tty() -> bool:
    """检测是否在交互终端。"""
    return sys.stdin.isatty()

# ===========================================================================
# 左轨：记忆归一化读取
# ===========================================================================

def read_riji_memory(skill_dir: str) -> List[RawMemory]:
    """读取 riji-skill 自身的记忆文件。"""
    memories = []

    # 1. memory/memory_main.md
    memory_main = os.path.join(skill_dir, 'memory', 'memory_main.md')
    if os.path.isfile(memory_main):
        content = _safe_read_text(memory_main)
        memories.append(RawMemory(
            source_tool='riji',
            file=memory_main,
            timestamp=datetime.fromtimestamp(
                os.path.getmtime(memory_main)
            ).strftime('%Y-%m-%d %H:%M'),
            content=content,
        ))
    else:
        logger.warning('riji memory_main.md 不存在: %s', memory_main)

    # 2. docs_rj/memory_rj/*.md
    memory_rj_dir = os.path.join(skill_dir, 'docs_rj', 'memory_rj')
    if os.path.isdir(memory_rj_dir):
        for fname in sorted(os.listdir(memory_rj_dir)):
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(memory_rj_dir, fname)
            if not os.path.isfile(fpath):
                continue
            content = _safe_read_text(fpath)
            memories.append(RawMemory(
                source_tool='riji',
                file=fpath,
                timestamp=datetime.fromtimestamp(
                    os.path.getmtime(fpath)
                ).strftime('%Y-%m-%d %H:%M'),
                content=content,
            ))

    logger.info('riji 记忆: 读取 %d 个文件', len(memories))
    return memories

def _read_tool_memory(tool_name: str, tool_path: str) -> List[RawMemory]:
    """读取单个 AI 工具的记忆文件（通用扫描器）。"""
    memories = []
    if not os.path.isdir(tool_path):
        return memories

    # 扫描 .md / .jsonl / .json 文件
    for root, dirs, files in os.walk(tool_path):
        # 黑名单剪枝
        dirs[:] = [d for d in dirs if d not in BLACKLIST_DIRS]
        # 限制深度（相对 tool_path 不超过 3 层）
        rel_depth = os.path.relpath(root, tool_path).count(os.sep)
        if rel_depth >= 3:
            dirs.clear()
            continue

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ('.md', '.jsonl', '.json', '.txt'):
                continue
            fpath = os.path.join(root, fname)
            content = _safe_read_text(fpath)
            if not content.strip():
                continue
            try:
                ts = datetime.fromtimestamp(
                    os.path.getmtime(fpath)
                ).strftime('%Y-%m-%d %H:%M')
            except OSError:
                ts = ''
            memories.append(RawMemory(
                source_tool=tool_name,
                file=fpath,
                timestamp=ts,
                content=content,
            ))

    return memories

def _whitelist_scan() -> Tuple[List[RawMemory], List[Dict]]:
    """白名单扫描器：扫描 8 个已知 AI 工具。"""
    memories = []
    hit_tools = []

    for tool_name, paths in WHITELIST_TOOLS.items():
        for path in paths:
            if not os.path.isdir(path):
                continue
            tool_mems = _read_tool_memory(tool_name, path)
            if tool_mems:
                memories.extend(tool_mems)
                hit_tools.append({
                    'tool_name': tool_name,
                    'path': path,
                    'detection': 'whitelist',
                    'confirmed': True,
                    'file_count': len(tool_mems),
                })
                logger.info('白名单命中: %s (%d 文件)', tool_name, len(tool_mems))
                break  # 同一工具只取第一个命中路径

    return memories, hit_tools

def _keyword_discover_scan(
    whitelist_paths: Set[str],
    max_depth: int = 3,
    max_dirs: int = 20,
) -> Tuple[List[RawMemory], List[Dict]]:
    """关键词发现扫描器：在扫描根下找含关键词的目录。"""
    memories = []
    discovered = []
    scan_roots = _get_scan_roots()

    found_dirs = []
    for root_path in scan_roots:
        if not os.path.isdir(root_path):
            continue
        for root, dirs, files in os.walk(root_path):
            # 黑名单剪枝
            dirs[:] = [d for d in dirs if d not in BLACKLIST_DIRS]
            # 深度限制
            rel_depth = os.path.relpath(root, root_path).count(os.sep)
            if rel_depth >= max_depth:
                dirs.clear()
                continue

            # 检查当前目录名是否命中关键词
            dir_name = os.path.basename(root).lower()
            if any(kw in dir_name for kw in SCAN_KEYWORDS):
                # 规范化路径比较
                norm_path = os.path.normpath(root)
                if norm_path in whitelist_paths:
                    continue  # 白名单已覆盖
                if norm_path in {os.path.normpath(d) for d in found_dirs}:
                    continue  # 已记录
                found_dirs.append(root)

                # 推断工具名：父目录名
                parent_name = os.path.basename(os.path.dirname(root))
                tool_name = parent_name if parent_name else 'unknown'
                discovered.append({
                    'tool_name': tool_name,
                    'path': root,
                    'detection': 'keyword_discovery',
                    'confirmed': False,
                })
                logger.info('关键词发现: %s (%s)', tool_name, root)

                # 超 20 个目录告警截断
                if len(found_dirs) >= max_dirs:
                    logger.warning('关键词发现超过 %d 个目录，截断', max_dirs)
                    break

        if len(found_dirs) >= max_dirs:
            break

    # 交互模式：问用户是否纳入新工具
    if discovered and _is_tty():
        print('\n=== 关键词发现新工具 ===')
        for i, d in enumerate(discovered):
            print(f'  {i+1}. {d["tool_name"]} ({d["path"]})')
        print('  0. 全部不纳入')
        try:
            choice = input('选择要纳入的编号（回车=全部纳入，0=全部不纳入）: ').strip()
        except (EOFError, KeyboardInterrupt):
            choice = '0'

        if choice == '0':
            discovered = []
        elif choice == '':
            pass  # 全部纳入
        else:
            selected = set()
            for part in choice.replace(',', ' ').split():
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(discovered):
                        selected.add(idx)
                except ValueError:
                    pass
            discovered = [discovered[i] for i in sorted(selected)]

    # 读取已确认的新工具记忆
    # 🔴 v1.0.1 安全修复：仅交互模式（用户已确认纳入）才读取内容；
    # 非交互模式下"未确认"的目录只记录路径、不读取内容（原实现未确认也读，可能静默读入敏感文件）
    if _is_tty():
        for d in discovered:
            tool_mems = _read_tool_memory(d['tool_name'], d['path'])
            memories.extend(tool_mems)
            d['file_count'] = len(tool_mems)

    if discovered and not _is_tty():
        logger.warning('非交互模式：发现 %d 个新工具，已记录路径（未确认，未读取内容）',
                       len(discovered))

    return memories, discovered

def read_ai_tools_memory() -> Tuple[List[RawMemory], Dict]:
    """读取多 AI 工具平台记忆（双机制：白名单 + 关键词发现）。"""
    whitelist_mems, hit_tools = _whitelist_scan()

    # 收集白名单路径用于去重
    whitelist_paths = {os.path.normpath(p) for p in
                       [path for paths in WHITELIST_TOOLS.values() for path in paths
                        if os.path.isdir(path)]}

    discover_mems, discovered_tools = _keyword_discover_scan(whitelist_paths)

    all_memories = whitelist_mems + discover_mems
    all_tools = hit_tools + discovered_tools

    logger.info('AI 工具扫描: 白名单命中 %d 个，关键词发现 %d 个，共读取 %d 个记忆文件',
                len(hit_tools), len(discovered_tools), len(all_memories))

    return all_memories, {'hit_tools': hit_tools, 'discovered_tools': discovered_tools}

def read_riji_memory() -> List[RawMemory]:
    """读取 riji.db（可选，当前返回空列表）。"""
    # 后期实现：读 riji.db L0 对话表
    return []

# ===========================================================================
# 左轨：规则提取技能线索
# ===========================================================================

def extract_skills_rulebased(memories: List[RawMemory]) -> List[RawSkill]:
    """从归一化记忆中用规则提取技能线索。

    策略：
    1. 用 TECH_KEYWORDS 表做精确匹配（大小写不敏感）
    2. 提取"动作-对象"模式（如"写了Python脚本"→ Python）
    3. 按 source_tool 去重，合并 evidence
    """
    # 构建 关键词 → 分类 映射（大小写不敏感）
    keyword_map: Dict[str, str] = {}
    for category, keywords in TECH_KEYWORDS.items():
        for kw in keywords:
            keyword_map[kw.lower()] = (category, kw)

    # 收集每个技能的证据
    skill_evidence: Dict[str, List[Dict]] = {}
    skill_category: Dict[str, str] = {}

    for mem in memories:
        # 用 splitlines 处理可能的孤立 \r（贴 project_memory 教训）
        lines = mem.content.splitlines()
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()

            # 精确匹配技术关键词
            for kw_lower, (category, kw_original) in keyword_map.items():
                if kw_lower in line_lower:
                    if kw_original not in skill_evidence:
                        skill_evidence[kw_original] = []
                        skill_category[kw_original] = category
                    # 避免同一文件同一行重复记录
                    ev_key = f'{mem.file}:{line_num}:{kw_original}'
                    if not any(e.get('key') == ev_key for e in skill_evidence[kw_original]):
                        skill_evidence[kw_original].append({
                            'source_tool': mem.source_tool,
                            'file': mem.file,
                            'line': line_num,
                            'timestamp': mem.timestamp,
                            'excerpt': line.strip()[:200],
                            'key': ev_key,
                        })

    # 构建 RawSkill 列表
    raw_skills: List[RawSkill] = []
    for name, evidence_list in skill_evidence.items():
        # 置信度：基于证据数和来源工具数
        source_count = len({e['source_tool'] for e in evidence_list})
        confidence = min(0.5 + 0.1 * len(evidence_list) + 0.15 * source_count, 0.95)

        raw_skills.append(RawSkill(
            name=name,
            evidence=evidence_list[:20],  # 限制证据数
            category_hint=skill_category[name],
            confidence=round(confidence, 2),
        ))

    # 按置信度降序
    raw_skills.sort(key=lambda s: s.confidence, reverse=True)

    logger.info('规则提取: 从 %d 个记忆文件中提取 %d 个技能线索',
                len(memories), len(raw_skills))
    return raw_skills

# ===========================================================================
# 右轨：多源全集拉取
# ===========================================================================

def _git_clone(repo_url: str, target_dir: str, timeout: int = 600) -> bool:
    """git clone --depth 1 仓库到目标目录。超时默认 600s（roadmap.sh 仓库较大）。"""
    if os.path.isdir(target_dir) and os.listdir(target_dir):
        logger.info('已存在，跳过 clone: %s', target_dir)
        return True
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, target_dir],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error('git clone 失败 %s: %s', repo_url, result.stderr[:200])
            return False
        logger.info('git clone 成功: %s', repo_url)
        return True
    except FileNotFoundError:
        logger.error('git 命令不存在')
        return False
    except subprocess.TimeoutExpired:
        logger.error('git clone 超时(%ds): %s', timeout, repo_url)
        return False

def _pull_roadmap_sh(target_dir: str, is_local: bool = False) -> List[SkillNode]:
    """拉取 roadmap.sh 角色技能树 JSON。

    Args:
        target_dir: 缓存目录（is_local=False）或本地仓库根路径（is_local=True）
        is_local: True 表示 target_dir 已是本地仓库路径，跳过 git clone
    """
    if is_local:
        repo_dir = target_dir
        logger.info('使用本地 roadmap 仓库: %s', repo_dir)
    else:
        repo_dir = os.path.join(target_dir, 'roadmap')
        success = _git_clone(
            'https://某开源仓库.git',
            repo_dir,
        )
        if not success:
            logger.warning('roadmap.sh 拉取失败，使用降级列表')
            return _build_fallback_nodes('roadmap.sh')

    nodes: List[SkillNode] = []
    roadmaps_dir = os.path.join(repo_dir, 'src', 'data', 'roadmaps')
    if not os.path.isdir(roadmaps_dir):
        logger.warning('roadmaps 目录不存在: %s', roadmaps_dir)
        return _build_fallback_nodes('roadmap.sh')

    # 遍历每个角色目录
    for role_name in os.listdir(roadmaps_dir):
        role_dir = os.path.join(roadmaps_dir, role_name)
        if not os.path.isdir(role_dir):
            continue
        # 找 {role}.json 或 {role}-beginner.json
        for json_name in [f'{role_name}.json', f'{role_name}-beginner.json']:
            json_path = os.path.join(role_dir, json_name)
            if not os.path.isfile(json_path):
                continue
            content = _safe_read_text(json_path, max_bytes=1024 * 1024)
            if not content:
                continue
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                continue

            # 提取 topic 和 subtopic 类型节点
            for node in data.get('nodes', []):
                node_type = node.get('type', '')
                if node_type not in ('topic', 'subtopic'):
                    continue
                label = node.get('data', {}).get('label', '').strip()
                if not label or len(label) < 2:
                    continue
                node_id = node.get('id', '')

                # 查找对应的 content .md 文件（描述+链接）
                content_dir = os.path.join(role_dir, 'content')
                description = ''
                learning_link = ''
                if os.path.isdir(content_dir):
                    # 文件名格式：{slug}@{nodeId}.md
                    for md_file in os.listdir(content_dir):
                        if md_file.endswith(f'@{node_id}.md'):
                            md_path = os.path.join(content_dir, md_file)
                            md_content = _safe_read_text(md_path)
                            # 第一段是描述
                            lines = md_content.splitlines()
                            for line in lines[1:]:  # 跳过标题行
                                if line.strip() and not line.startswith('Visit') and not line.startswith('-'):
                                    description = line.strip()[:300]
                                    break
                            # 找第一个链接
                            link_match = re.search(r'\[.*?\]\((https?://[^\)]+)\)', md_content)
                            if link_match:
                                learning_link = link_match.group(1)
                            break

                nodes.append(SkillNode(
                    id=f'roadmap.sh:{label.lower()}',
                    name=label,
                    category=node_type,
                    source='roadmap.sh',
                    tags=[role_name],
                    description=description,
                    learning_link=learning_link,
                ))
            break  # 只取第一个 JSON 文件（主版本）

    logger.info('roadmap.sh: 提取 %d 个技能节点', len(nodes))
    return nodes

def _pull_engineer_competency(target_dir: str) -> List[SkillNode]:
    """拉取 engineer_competency_framework 工程能力矩阵。"""
    repo_dir = os.path.join(target_dir, 'competency')
    success = _git_clone(
        'https://某开源仓库.git',
        repo_dir,
    )
    if not success:
        logger.warning('engineer_competency 拉取失败，使用降级列表')
        return _build_fallback_nodes('engineer_competency')

    nodes: List[SkillNode] = []
    # 扫描 .md 和 .xlsx 文件
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in BLACKLIST_DIRS and not d.startswith('.')]
        for fname in files:
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(root, fname)
            content = _safe_read_text(fpath)
            if not content:
                continue
            # 提取标题行作为技能名
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('#') and len(line) > 3:
                    name = line.lstrip('#').strip()
                    if 2 <= len(name) <= 50:
                        nodes.append(SkillNode(
                            id=f'engineer_competency:{name.lower()}',
                            name=name,
                            category='工程能力',
                            source='engineer_competency',
                            tags=[fname],
                        ))

    logger.info('engineer_competency: 提取 %d 个技能节点', len(nodes))
    return nodes

def _pull_github_topics(target_dir: str) -> List[SkillNode]:
    """拉取 GitHub Topics（API 有限流，降级到硬编码列表）。"""
    nodes: List[SkillNode] = []

    # 尝试 GitHub API（未认证限流 60次/小时）
    topics_url = 'https://api.某开源仓库?q=stars:>10000&sort=stars&per_page=30'
    try:
        req = urllib.request.Request(topics_url, headers={
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'skill-graph-extractor',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        topic_set: Set[str] = set()
        for item in data.get('items', []):
            for topic in item.get('topics', []):
                topic_set.add(topic)

        for topic in sorted(topic_set):
            nodes.append(SkillNode(
                id=f'github_topics:{topic.lower()}',
                name=topic,
                category='工具框架',
                source='github_topics',
                tags=['github'],
            ))

        logger.info('GitHub Topics API: 提取 %d 个技能节点', len(nodes))

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logger.warning('GitHub Topics API 失败 (%s)，使用降级列表', e)
        nodes = _build_fallback_nodes('github_topics')

    return nodes

def _pull_so_survey(target_dir: str) -> List[SkillNode]:
    """拉取 Stack Overflow Developer Survey（无直接 JSON API，用硬编码降级）。"""
    # SO Survey 没有稳定的公开 JSON API，直接用降级列表
    logger.info('SO Survey: 使用硬编码降级列表（无公开 JSON API）')
    return _build_fallback_nodes('so_survey')

def _build_fallback_nodes(source: str) -> List[SkillNode]:
    """从硬编码降级列表构建 SkillNode。"""
    nodes = []
    for skill in FALLBACK_TAXONOMY:
        # 推断分类
        category = '其他'
        for cat, keywords in TECH_KEYWORDS.items():
            if skill in keywords:
                category = cat
                break
        nodes.append(SkillNode(
            id=f'{source}:{skill.lower()}',
            name=skill,
            category=category,
            source=source,
        ))
    return nodes

def pull_taxonomy_sources(target_dir: str, roadmap_local: str = None) -> List[SkillNode]:
    """并行拉取 4 源（实际是顺序执行，但各自失败不阻断）。

    Args:
        target_dir: 缓存目录
        roadmap_local: 本地已克隆的 developer-roadmap 仓库路径（跳过 git clone）
    """
    os.makedirs(target_dir, exist_ok=True)

    all_nodes: List[SkillNode] = []
    sources_hit: List[str] = []

    # 源1: roadmap.sh
    try:
        if roadmap_local and os.path.isdir(roadmap_local):
            nodes = _pull_roadmap_sh(roadmap_local, is_local=True)
        else:
            nodes = _pull_roadmap_sh(target_dir)
        if nodes:
            all_nodes.extend(nodes)
            sources_hit.append('roadmap.sh')
    except Exception as e:
        logger.error('roadmap.sh 拉取异常: %s', e)

    # 源2: engineer_competency
    try:
        nodes = _pull_engineer_competency(target_dir)
        if nodes:
            all_nodes.extend(nodes)
            sources_hit.append('engineer_competency')
    except Exception as e:
        logger.error('engineer_competency 拉取异常: %s', e)

    # 源3: GitHub Topics
    try:
        nodes = _pull_github_topics(target_dir)
        if nodes:
            all_nodes.extend(nodes)
            sources_hit.append('github_topics')
    except Exception as e:
        logger.error('GitHub Topics 拉取异常: %s', e)

    # 源4: SO Survey
    try:
        nodes = _pull_so_survey(target_dir)
        if nodes:
            all_nodes.extend(nodes)
            sources_hit.append('so_survey')
    except Exception as e:
        logger.error('SO Survey 拉取异常: %s', e)

    logger.info('多源全集: 命中 %d 个源，共 %d 个技能节点',
                len(sources_hit), len(all_nodes))

    return all_nodes

# ===========================================================================
# 右轨：归一化 + 去重
# ===========================================================================

# 常见同义词映射（小写 → 标准名）
_SYNONYM_MAP: Dict[str, str] = {
    'python3': 'Python',
    'python 3': 'Python',
    'py': 'Python',
    'js': 'JavaScript',
    'javascript es6': 'JavaScript',
    'ts': 'TypeScript',
    'k8s': 'Kubernetes',
    'kubernetes': 'Kubernetes',
    'docker compose': 'Docker',
    'docker-compose': 'Docker',
    'postgres': 'PostgreSQL',
    'postgresql': 'PostgreSQL',
    'mongo': 'MongoDB',
    'mongodb': 'MongoDB',
    'redis': 'Redis',
    'elasticsearch': 'Elasticsearch',
    'es': 'Elasticsearch',
    'reactjs': 'React',
    'react.js': 'React',
    'vuejs': 'Vue',
    'vue.js': 'Vue',
    'node': 'Node.js',
    'nodejs': 'Node.js',
    'node.js': 'Node.js',
    'expressjs': 'Express',
    'express.js': 'Express',
    'scikit-learn': 'scikit-learn',
    'sklearn': 'scikit-learn',
    'tf': 'TensorFlow',
    'tensorflow': 'TensorFlow',
    'pytorch': 'PyTorch',
    'torch': 'PyTorch',
    'apache/kafka': 'Kafka',
    'apache kafka': 'Kafka',
    'message queue': '消息队列',
    'messagequeue': '消息队列',
    'tencent cloud': '腾讯云',
    'tencentcloud': '腾讯云',
    'aliyun': '阿里云',
    'alibaba cloud': '阿里云',
    'aws': 'AWS',
    'amazon web services': 'AWS',
    'gcp': 'GCP',
    'google cloud': 'GCP',
    'google cloud platform': 'GCP',
    'oauth2': 'OAuth2',
    'oauth 2.0': 'OAuth2',
    'oauth2.0': 'OAuth2',
    'jwt': 'JWT',
    'json web token': 'JWT',
    'ssl/tls': 'SSL/TLS',
    'ssl': 'SSL/TLS',
    'tls': 'SSL/TLS',
}

def normalize_taxonomy(skill_nodes: List[SkillNode]) -> List[SkillNode]:
    """归一化技能名（同义词统一、去空格、去大小写差异）。"""
    seen: Dict[str, SkillNode] = {}

    for node in skill_nodes:
        # 同义词映射
        name_lower = node.name.lower().strip()
        standard_name = _SYNONYM_MAP.get(name_lower, node.name.strip())

        # 去重 key：标准名小写
        key = standard_name.lower()
        if key in seen:
            # 合并 source 和 tags
            existing = seen[key]
            if node.source not in existing.tags:
                existing.tags.append(node.source)
            if node.description and not existing.description:
                existing.description = node.description
            if node.learning_link and not existing.learning_link:
                existing.learning_link = node.learning_link
        else:
            node.name = standard_name
            node.id = f'taxonomy:{key}'
            seen[key] = node

    result = list(seen.values())
    logger.info('归一化去重: %d → %d 个技能节点', len(skill_nodes), len(result))
    return result

def dedup_taxonomy_llm(skill_nodes: List[SkillNode]) -> List[SkillNode]:
    """LLM 跨源去重（T2 时补 LLM 调用，当前降级到规则版本）。

    LLM 版本会：
    1. 把所有技能名列表喂给 LLM
    2. LLM 识别同义词对
    3. 合并同义词

    当前降级：直接调 normalize_taxonomy 的规则去重。
    """
    logger.info('dedup_taxonomy_llm: 降级到规则版本（LLM 版本待 T2 补）')
    return normalize_taxonomy(skill_nodes)

def supplement_with_llm(
    skill_nodes: List[SkillNode],
    user_profile: str = '',
) -> List[SkillNode]:
    """LLM 根据用户 profile 补充前4源没有的技能（T2 时补，当前返回原列表）。

    LLM 版本会：
    1. 读取用户 profile
    2. 推断用户角色
    3. 补充角色相关但前4源没有的技能
    """
    logger.info('supplement_with_llm: 降级返回原列表（LLM 版本待 T2 补）')
    return skill_nodes

# ===========================================================================
# 主入口
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='阶段1：双轨提取（左轨记忆挖掘 + 右轨多源全集）',
    )
    parser.add_argument(
        '--source', choices=['riji', 'ai_tools', 'riji', 'all'],
        default='all', help='数据源（默认 all）',
    )
    parser.add_argument(
        '--output', default=None,
        help='skills_raw.json 输出路径（默认缓存目录）',
    )
    parser.add_argument(
        '--taxonomy-output', default=None,
        help='master_taxonomy.json 输出路径（默认缓存目录）',
    )
    parser.add_argument(
        '--no-cache', action='store_true',
        help='忽略缓存，强制重新拉取',
    )
    parser.add_argument(
        '--interactive', action='store_true', default=None,
        help='交互模式（TTY 自动检测，强制开启）',
    )
    parser.add_argument(
        '--max-depth', type=int, default=3,
        help='关键词发现最大深度（默认3）',
    )
    parser.add_argument(
        '--discover-only', action='store_true',
        help='仅输出 discovered_tools，不提取技能（调试用）',
    )
    parser.add_argument(
        '--skill-dir', default=_SKILL_DIR,
        help='riji-skill 根目录（默认自动检测）',
    )
    parser.add_argument(
        '--skip-taxonomy', action='store_true',
        help='跳过右轨多源全集拉取（调试用，仅测左轨）',
    )
    parser.add_argument(
        '--roadmap-local', default=None,
        help='本地已克隆的 developer-roadmap 仓库路径（跳过 git clone，直接读本地）',
    )

    args = parser.parse_args()

    # 确保缓存目录存在
    os.makedirs(_CACHE_DIR, exist_ok=True)

    output_path = args.output or os.path.join(_CACHE_DIR, 'skills_raw.json')
    taxonomy_output_path = (
        args.taxonomy_output or os.path.join(_CACHE_DIR, 'master_taxonomy.json')
    )

    # === 左轨：记忆归一化读取 ===
    memories: List[RawMemory] = []
    tools_info = {'hit_tools': [], 'discovered_tools': []}

    if args.source in ('riji', 'all'):
        memories.extend(read_riji_memory(args.skill_dir))

    if args.source in ('ai_tools', 'all'):
        ai_mems, ai_tools_info = read_ai_tools_memory()
        memories.extend(ai_mems)
        tools_info = ai_tools_info

    if args.source in ('riji', 'all'):
        memories.extend(read_riji_memory())

    # 仅发现模式
    if args.discover_only:
        result = {
            'discovered_tools': tools_info.get('discovered_tools', []),
            'hit_tools': tools_info.get('hit_tools', []),
        }
        _atomic_write_json(output_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        logger.info('发现模式: 结果写入 %s', output_path)
        return

    # === 左轨：规则提取 ===
    raw_skills = extract_skills_rulebased(memories)

    # === 右轨：多源全集拉取（可用 --skip-taxonomy 跳过） ===
    taxonomy_nodes = []
    if not args.skip_taxonomy:
        logger.info('=== 右轨：多源全集拉取 ===')
        taxonomy_nodes = pull_taxonomy_sources(_TAXONOMY_DATA_DIR, args.roadmap_local)

        # 归一化 + 去重
        taxonomy_nodes = normalize_taxonomy(taxonomy_nodes)
        taxonomy_nodes = dedup_taxonomy_llm(taxonomy_nodes)
        taxonomy_nodes = supplement_with_llm(taxonomy_nodes, user_profile='')
    else:
        logger.info('跳过右轨（--skip-taxonomy）')

    # === 写 skills_raw.json ===
    raw_result = {
        'schema_version': '1.0',
        'generated_at': datetime.now().astimezone().isoformat(),
        'sources_scanned': list({m.source_tool for m in memories}),
        'hit_tools': tools_info.get('hit_tools', []),
        'discovered_tools': tools_info.get('discovered_tools', []),
        'memory_file_count': len(memories),
        'raw_skills': [asdict(s) for s in raw_skills],
    }

    if _atomic_write_json(output_path, raw_result):
        logger.info('skills_raw.json 写入: %s（%d 个技能）', output_path, len(raw_skills))
    else:
        logger.error('skills_raw.json 写入失败')
        sys.exit(1)

    # === 写 master_taxonomy.json（跳过右轨时为空） ===
    taxonomy_result = {
        'schema_version': '1.0',
        'generated_at': datetime.now().astimezone().isoformat(),
        'sources_hit': list({n.source for n in taxonomy_nodes}),
        'total_skills': len(taxonomy_nodes),
        'categories': list({n.category for n in taxonomy_nodes}),
        'skills': [asdict(n) for n in taxonomy_nodes],
    }

    if taxonomy_nodes or not args.skip_taxonomy:
        if _atomic_write_json(taxonomy_output_path, taxonomy_result):
            logger.info('master_taxonomy.json 写入: %s（%d 个技能）',
                        taxonomy_output_path, len(taxonomy_nodes))
        else:
            logger.error('master_taxonomy.json 写入失败')
            sys.exit(1)

    # === 写 taxonomy_manifest.json（版本记录，跳过右轨时不写） ===
    if not args.skip_taxonomy:
        manifest_path = os.path.join(_CACHE_DIR, 'taxonomy_manifest.json')
        manifest = {
            'generated_at': datetime.now().astimezone().isoformat(),
            'sources': list({n.source for n in taxonomy_nodes}),
            'total_skills': len(taxonomy_nodes),
            'taxonomy_file': taxonomy_output_path,
            'raw_file': output_path,
        }
        _atomic_write_json(manifest_path, manifest)

    # === 汇总输出 ===
    print(f'\n=== 阶段1 提取完成 ===')
    print(f'左轨（记忆挖掘）:')
    print(f'  扫描根: {len(_get_scan_roots())} 个')
    print(f'  命中工具: {len(tools_info.get("hit_tools", []))} 个白名单 + '
          f'{len(tools_info.get("discovered_tools", []))} 个关键词发现')
    print(f'  读取记忆文件: {len(memories)} 个')
    print(f'  提取技能线索: {len(raw_skills)} 个')
    if not args.skip_taxonomy:
        print(f'右轨（多源全集）:')
        print(f'  命中源: {len(taxonomy_result["sources_hit"])} 个 '
              f'({", ".join(taxonomy_result["sources_hit"])})')
        print(f'  全集技能数: {len(taxonomy_nodes)} 个')
    else:
        print(f'右轨: 已跳过（--skip-taxonomy）')
    print(f'输出:')
    print(f'  skills_raw.json → {output_path}')
    if not args.skip_taxonomy:
        print(f'  master_taxonomy.json → {taxonomy_output_path}')
        print(f'  taxonomy_manifest.json → {manifest_path}')

if __name__ == '__main__':
    main()
