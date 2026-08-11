#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_skill.py — pdca-skill 工具调用校验 loop 脚本
============================================================

用途
----
给 pdca-skill 装上一道"硬校验"：暴露"声明了但没真正跑"的环节。
用户已发现「doc 归档」指令未被执行，本脚本即是对此类缺口的可执行体检。

技术约束
--------
* 仅使用 Python 标准库（argparse / subprocess / json / pathlib / tempfile /
  re / sys / os / time / shutil），无 pip 依赖。
* 兼容 Python >= 3.8。

================================================================================
验收标准（STANDARDS）
================================================================================
每条 check 返回三元组 (passed: bool, detail: str, transient: bool)。
* transient=True  → 瞬时错误（网络/超时），loop 模式会重试。
* transient=False → 结构缺口，永不自动通过（记为 MUST FIX + 修复建议）。

以下是全部 17 条 check 及其通过条件（category 顺序）：

[integrity]
  INT-01  SKILL.md 存在、含 YAML frontmatter（含 name + license）、非空。
  INT-02  解析触发钩子表 + 决策树，提取所有 references/*.md 与 assets/*.md
          引用路径，断言每个文件在磁盘存在（死链检查），缺的逐个列出。
  INT-03  evals/evals.json 是合法 JSON 且含非空 evals 数组（>0 条）。

[scripts]
  SCR-01  generate_docs.py 能通过 py_compile 编译。
  SCR-02  在临时目录实跑 `generate_docs.py --task demo_validate --type all
          --docs-dir <tmp>`，断言生成 5 个子目录（spec_rj / task_rj /
          handoff_rj / memory_rj / archive_rj）及对应模板文件。
  SCR-03  `generate_docs.py --scan-docs` 能跑且 stdout 输出合法 JSON（数组）。
  SCR-04  `generate_docs.py --archive-scattered --dry-run` 无报错（rc=0 + JSON）。
  SCR-05  `generate_docs.py --migrate-rj --dry-run` 无报错（rc=0 + JSON）。

[routing]
  ROUT-01 SKILL.md 含 /plan 触发行且引用 brainstorming、writing-plans；
          决策树含 /plan 分支且带 HARD-GATE 门控。
  ROUT-02 反向链路审计：对 references/ 下每个 .md，断言其从 SKILL.md 出发沿
          markdown 链接 BFS 可达（无孤儿文件）。与 INT-02（正向死链）互补——
          INT-02 防「链接了但文件不存在」，ROUT-02 防「文件存在但无人链接」。
  ROUT-03 阶段标签完整性：对 references/ 下每个 .md，断言其含「阶段标签：」
          元数据行（文件头）。护住「标签持续增长」纪律——新增 reference 必须
          贴阶段标签；缺标签记 MUST FIX，loop 模式永不自动通过。

[skills]
  SKL-01  brainstorming 在任一搜索目录存在（其下 SKILL.md 存在）→ /plan 验收。
  SKL-02  writing-plans 在任一搜索目录存在 → /plan 验收。

[archiving]
  ARC-01  SKILL.md 记载 write_project 归档机制：含 "write_project"、
          "自动落盘"、"upsert" 三个关键词（重构后归档机制改为
          "write_project 自动落盘+自动全局跟进，无独立归档步骤"）。
  ARC-02  references/common/pa/summary_view.md 存在且记载三触发（启动/归档/交接）。
  ARC-03  check_archive(memory_dir) 助手作为可演示单元：构造临时
          MEMORY_RJ.md（含「当日工作记录」条目）→ 返回"未归档"；清空该区块后
          → 返回"已归档"。验证归档自校验逻辑可用。
  ARC-04  docs_rj/SUMMARY_RJ.md 存在性硬校验：缺失即 MUST FIX（transient=False，
          永不自动过），补救指向 summary_view.md 三触发①引导式创建（读
          assets/summary_template.md + 扫描 docs_rj 各子目录，或 startup_tidy.py
          --create-summary 经确认后生成）。与 startup_tidy 的 [BLOCKER] 警告构成双防线。

================================================================================
运行方式
================================================================================
  python validate_skill.py [--skill-dir PATH] [--loop] [--retries N]
                           [--interval SEC] [--max-iter M] [--json OUT.json]
                           [--quiet]

  * 默认 skill-dir = 脚本所在 scripts/ 的上级目录（即仓库根）。
  * 全部通过 exit 0；任一失败 exit 1。
  * --loop 开启时：全套每 --interval 秒重跑，直到全绿或达 --max-iter 次；
    transient FAIL 重试最多 --retries 次，结构缺口（transient=False）永不自动过。
"""

import argparse
import subprocess
import json
import tempfile
import re
import sys
import os
import time
import shutil
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_data_path  # noqa: E402  用户数据外置：提供 get_docs_rj_path()

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
EXPECTED_SUBDIRS = [
    'spec_rj', 'task_rj', 'handoff_rj',
    'memory_rj', 'archive_rj',
]
# 这 3 类目录在 --type all 实跑后应当各自含至少 1 个 .md 模板文件
# 修复 SCR-02：memory_rj 是动态目录（由 write_project 写入），generate_docs 不预置模板
DOC_DIRS_WITH_FILES = [
    'spec_rj', 'task_rj', 'handoff_rj',
]

# 提取 references/xxx.md 与 assets/xxx.md 引用
# references/ 已迁移到 PDCA 子文件夹结构，支持子目录路径（如 references/plan/bootstrap/xxx.md）
# assets/ 保持平铺，不支持子目录
REF_RE = re.compile(r'references/(?:[A-Za-z0-9_\-/]+/)*[A-Za-z0-9_\-]+\.md|assets/[A-Za-z0-9_\-]+\.md')
# 统计编号步骤：行首形如 "1. "
STEP_RE = re.compile(r'^\d+\.\s')

DEFAULT_TIMEOUT = 120  # 子进程超时（秒）


# ---------------------------------------------------------------------------
# 通用辅助函数
# ---------------------------------------------------------------------------
def read_text(path):
    """读取文本文件，失败时返回空串（调用方据此判定为缺口）。"""
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ''


def parse_frontmatter(text):
    """从 SKILL.md 文本解析 YAML frontmatter（简化的 key: value 解析）。

    返回 dict；若不存在合法 frontmatter 返回 None。
    """
    if not text.startswith('---'):
        return None
    lines = text.splitlines()
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == '---':
            end = idx
            break
    if end is None:
        return None
    frontmatter = {}
    for line in lines[1:end]:
        if ':' in line:
            key, value = line.split(':', 1)
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def extract_section(text, heading_keyword):
    """提取以 heading_keyword 为标题的区块内容（到下一个 '#' 标题为止）。

    返回区块文本；未找到返回空串。
    """
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.lstrip().startswith('#') and heading_keyword in line:
            start = idx
            break
    if start is None:
        return ''
    collected = []
    for line in lines[start + 1:]:
        if line.lstrip().startswith('#'):
            break
        collected.append(line)
    return '\n'.join(collected)


def count_numbered_steps(section):
    """统计区块内行首为 'N. ' 的编号步骤数量。"""
    count = 0
    for line in section.splitlines():
        if STEP_RE.match(line.strip()):
            count += 1
    return count


def build_skill_search_roots():
    """构造 skill 搜索根目录清单（跨用户，基于 USERPROFILE / HOME）。

    覆盖：
      ~/.workbuddy/skills/
      ~/.pdca-memory/skills/
      ~/.trae-cn/skills/
      ~/.trae-cn/builtin/work/*/skills/   （glob 展开）
      ~/.codebuddy/plugins/marketplaces/codebuddy-plugins-official/plugins/
    """
    home = os.environ.get('USERPROFILE') or os.environ.get('HOME') or ''
    roots = []
    for sub in ['.workbuddy/skills', '.pdca-memory/skills', '.trae-cn/skills']:
        roots.append(os.path.join(home, *sub.split('/')))

    work_base = os.path.join(home, '.trae-cn', 'builtin', 'work')
    if os.path.isdir(work_base):
        try:
            for entry in os.listdir(work_base):
                candidate = os.path.join(work_base, entry, 'skills')
                if os.path.isdir(candidate):
                    roots.append(candidate)
        except OSError:
            pass

    roots.append(os.path.join(
        home, '.codebuddy', 'plugins', 'marketplaces',
        'codebuddy-plugins-official', 'plugins',
    ))
    return roots


def find_skill(name, roots):
    """在搜索根目录中查找某个 skill（其下需含 SKILL.md）。

    返回 (found_anywhere, found_in_workbuddy, locations)。
    """
    locations = []
    for root in roots:
        candidate = os.path.join(root, name, 'SKILL.md')
        if os.path.isfile(candidate):
            locations.append(os.path.dirname(candidate))
    found_anywhere = len(locations) > 0

    home = os.environ.get('USERPROFILE') or os.environ.get('HOME') or ''
    workbuddy_skills = os.path.join(home, '.workbuddy', 'skills')
    found_in_workbuddy = any(loc.startswith(workbuddy_skills) for loc in locations)

    return found_anywhere, found_in_workbuddy, locations


def check_archive(memory_dir):
    """归档自校验助手（可独立调用 / 导入）。

    检查 memory_dir/MEMORY_RJ.md 的「当日工作记录」区块：
      * 区块含条目  → ('unarchived', detail)   尚未归档
      * 区块已清空  → ('archived', detail)      已归档
      * 文件/区块缺失 → ('missing_file' / 'missing_section', detail)

    返回 (status: str, detail: str)。
    """
    mem_path = os.path.join(memory_dir, 'MEMORY_RJ.md')
    if not os.path.isfile(mem_path):
        return ('missing_file', 'MEMORY_RJ.md 不存在')
    try:
        with open(mem_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        return ('read_error', '读取 MEMORY_RJ.md 失败: %s' % exc)

    lines = content.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.lstrip().startswith('#') and '当日工作记录' in line:
            start = idx
            break
    if start is None:
        return ('missing_section', '未找到「当日工作记录」区块')

    entry_count = 0
    for line in lines[start + 1:]:
        if line.lstrip().startswith('#'):
            break  # 遇到下一个标题，区块结束
        stripped = line.strip()
        if stripped.startswith('-') or stripped.startswith('*'):
            entry_count += 1

    if entry_count > 0:
        return ('unarchived', '「当日工作记录」有 %d 条未归档' % entry_count)
    return ('archived', '「当日工作记录」已清空')


def run_subprocess(python, script, cwd, extra_args, timeout=DEFAULT_TIMEOUT):
    """运行子进程并返回 (returncode, stdout, stderr)。

    启动失败 / 超时返回 (None, None, error_msg)。
    Windows 兼容（v1.0.2）：text=True 默认按 cp936 解码，子进程 UTF-8 输出
    （含中文/emoji）会导致 reader 线程 UnicodeDecodeError 静默吞掉 stdout，
    表现为"输出非合法 JSON"。修复：显式 utf-8 + errors='replace' 解码，
    并向子进程注入 PYTHONIOENCODING=utf-8（防 GBK 控制台 print emoji 崩溃）。
    """
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    command = [python, script] + list(extra_args)
    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace', env=env,
        )
    except subprocess.TimeoutExpired:
        return None, None, 'subprocess 超时（%ss）' % timeout
    except OSError as exc:
        return None, None, 'subprocess 启动失败: %s' % exc
    return proc.returncode, proc.stdout, proc.stderr


def extract_json(text):
    """从子进程 stdout（可能含前置文本头）中提取合法 JSON。

    generate_docs.py 的各模式会在 stdout 先打印分隔线/标题再打印 JSON，
    因此这里跳过前置文本，从第一个 '[' 或 '{' 开始解析。
    解析成功返回对象，否则返回 None。
    """
    if not text:
        return None
    start = None
    for idx, char in enumerate(text):
        if char in '[{':
            start = idx
            break
    if start is None:
        return None
    try:
        return json.loads(text[start:])
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CHECK 构造器：闭包捕获 skill_dir / skill_md / gen_script / python / roots
# 每条 check 返回 (passed: bool, detail: str, transient: bool)
# ---------------------------------------------------------------------------
def build_checks(skill_dir, skill_md, gen_script, python, roots):
    """构造 CHECKS 注册表：[(id, name, category, callable), ...]。"""

    # ---- [integrity] ----
    def c_frontmatter():
        if not skill_md.strip():
            return (False, 'SKILL.md 为空', False)
        frontmatter = parse_frontmatter(skill_md)
        if frontmatter is None:
            return (False, 'SKILL.md 缺少 YAML frontmatter（未以 --- 包裹）', False)
        if 'name' not in frontmatter or 'license' not in frontmatter:
            return (False, 'frontmatter 缺少 name 或 license 字段', False)
        return (True, 'frontmatter 含 name=%s, license=%s'
                % (frontmatter.get('name'), frontmatter.get('license')), False)

    def c_deadlinks():
        refs = sorted(set(REF_RE.findall(skill_md)))
        if not refs:
            return (True, '未检测到 references/assets 引用', False)
        missing = [r for r in refs if not os.path.isfile(os.path.join(skill_dir, r))]
        if missing:
            return (False, '死链(%d): %s' % (len(missing), ', '.join(missing)), False)
        return (True, '全部 %d 个引用路径均存在' % len(refs), False)

    def c_evals():
        evals_path = os.path.join(skill_dir, 'evals', 'evals.json')
        if not os.path.isfile(evals_path):
            return (False, 'evals/evals.json 不存在', False)
        try:
            with open(evals_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            return (False, 'evals.json 解析失败: %s' % exc, False)
        evals = data.get('evals') if isinstance(data, dict) else None
        if not isinstance(evals, list) or len(evals) == 0:
            return (False, 'evals.json 缺少非空 evals 数组', False)
        return (True, 'evals.json 合法，含 %d 条用例' % len(evals), False)

    # ---- [scripts] ----
    def c_pycompile():
        if not os.path.isfile(gen_script):
            return (False, 'generate_docs.py 不存在: %s' % gen_script, False)
        import py_compile
        try:
            py_compile.compile(gen_script, doraise=True)
        except py_compile.PyCompileError as exc:
            return (False, 'generate_docs.py 编译失败: %s' % exc, False)
        return (True, 'generate_docs.py 通过 py_compile', False)

    def c_run_generate():
        if not os.path.isfile(gen_script):
            return (False, 'generate_docs.py 不存在', False)
        tmp = tempfile.mkdtemp(prefix='hh_validate_')
        try:
            rc, _out, err = run_subprocess(
                python, gen_script, skill_dir,
                ['--task', 'demo_validate', '--type', 'all', '--docs-dir', tmp],
            )
            if rc != 0:
                return (False, 'generate_docs 退出码 %s; stderr=%s'
                        % (rc, (err or '')[-500:]), False)
            task_dir = tmp  # 修复 SCR-02：generate_docs 扁平化后不再嵌套 task_name 层
            missing_dirs = [d for d in EXPECTED_SUBDIRS
                            if not os.path.isdir(os.path.join(task_dir, d))]
            empty_dirs = []
            for d in DOC_DIRS_WITH_FILES:
                dpath = os.path.join(task_dir, d)
                if not os.path.isdir(dpath):
                    empty_dirs.append(d + '(缺)')
                    continue
                try:
                    files = [f for f in os.listdir(dpath) if f.endswith('.md')]
                except OSError:
                    files = []
                if not files:
                    empty_dirs.append(d)
            if missing_dirs or empty_dirs:
                return (False, '缺失子目录=%s; 空模板目录=%s'
                        % (missing_dirs, empty_dirs), False)
            return (True, '生成 6 子目录 + 5 类模板文件均成功', False)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c_scan_docs():
        rc, out, err = run_subprocess(python, gen_script, skill_dir, ['--scan-docs'])
        if rc != 0:
            return (False, 'scan-docs 退出码 %s; stderr=%s'
                    % (rc, (err or '')[-400:]), False)
        data = extract_json(out)
        if not isinstance(data, list):
            return (False, 'scan-docs 输出非合法 JSON; stdout=%s'
                    % (out or '')[:200], False)
        return (True, 'scan-docs 运行成功，返回 %d 个 docs 目录' % len(data), False)

    def c_archive_dry():
        rc, out, err = run_subprocess(
            python, gen_script, skill_dir, ['--archive-scattered', '--dry-run'])
        if rc != 0:
            return (False, 'archive-scattered --dry-run 退出码 %s; stderr=%s'
                    % (rc, (err or '')[-400:]), False)
        data = extract_json(out)
        if not isinstance(data, dict):
            return (False, 'archive-scattered 输出非合法 JSON', False)
        return (True, 'archive-scattered --dry-run 无报错', False)

    def c_migrate_dry():
        rc, out, err = run_subprocess(
            python, gen_script, skill_dir, ['--migrate-rj', '--dry-run'])
        if rc != 0:
            return (False, 'migrate-rj --dry-run 退出码 %s; stderr=%s'
                    % (rc, (err or '')[-400:]), False)
        data = extract_json(out)
        if not isinstance(data, dict):
            return (False, 'migrate-rj 输出非合法 JSON', False)
        return (True, 'migrate-rj --dry-run 无报错', False)

    # ---- [scripts] SCR-06: loop_audit.py 输出 PDCA Ready Score ----
    def c_loop_audit():
        audit_script = os.path.join(skill_dir, 'scripts', 'loop_audit.py')
        if not os.path.isfile(audit_script):
            return (False, 'loop_audit.py 不存在', False)
        rc, out, err = run_subprocess(
            python, audit_script, skill_dir, ['--json', os.devnull])
        if rc != 0:
            return (False, 'loop_audit.py 退出码 %s; stderr=%s'
                    % (rc, (err or '')[-400:]), False)
        data = extract_json(out)
        if not isinstance(data, dict):
            return (False, 'loop_audit.py 输出非合法 JSON', False)
        score = data.get('pdca_ready_score')
        level = data.get('level')
        if score is None or level is None:
            return (False, 'loop_audit.py 输出缺少 pdca_ready_score 或 level', False)
        return (True, 'loop_audit.py 输出 PDCA Ready Score=%s, level=%s'
                % (score, level), False)

    # ---- [scripts] SCR-07: spec_template.md 含 BRD 5 子项 + §10 Clarifications ----
    def c_spec_brd():
        spec_tpl = os.path.join(skill_dir, 'assets', 'spec_template.md')
        if not os.path.isfile(spec_tpl):
            return (False, 'assets/spec_template.md 不存在', False)
        try:
            with open(spec_tpl, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return (False, '读取 spec_template.md 失败: %s' % e, False)
        required_subsections = [
            '### §1.0 业务背景与痛点',
            '### §1.1 业务价值',
            '### §1.2 不做的代价',
            '### §1.3 成功指标',
            '### §1.4 干系人',
            '## 10. Clarifications',
        ]
        missing = [s for s in required_subsections if s not in content]
        if missing:
            return (False, 'spec_template.md 缺少 BRD 要素: %s' % missing, False)
        # 校验 Self-Review 9 维度
        if 'BRD 业务价值对齐' not in content:
            return (False, 'spec_template.md Self-Review 缺少第9维度 BRD 业务价值对齐', False)
        return (True, 'spec_template.md 含 BRD 5 子项 + §10 Clarifications + Self-Review 9 维度', False)

    # ---- [scripts] SCR-08: loop_constraints.md 含 max_iterations 类型校验规则 ----
    def c_loop_max_iter():
        constraints = os.path.join(skill_dir, 'references', 'do', 'danger', 'loop_constraints.md')
        if not os.path.isfile(constraints):
            return (False, 'references/do/danger/loop_constraints.md 不存在', False)
        try:
            with open(constraints, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return (False, '读取 loop_constraints.md 失败: %s' % e, False)
        if 'max_iterations' not in content:
            return (False, 'loop_constraints.md 缺少 max_iterations 配置', False)
        if 'isinstance(val, bool)' not in content:
            return (False, 'loop_constraints.md 缺少 bool 类型校验规则', False)
        if 'SCR-08' not in content:
            return (False, 'loop_constraints.md 未引用 SCR-08 代码层校验', False)
        return (True, 'loop_constraints.md 含 max_iterations 配置 + bool 类型校验 + SCR-08 引用', False)

    # ---- [scripts] SCR-09: SKILL.md HTML注释版本号格式 ----
    def c_skill_version_html():
        skill_md_path = os.path.join(skill_dir, 'SKILL.md')
        if not os.path.isfile(skill_md_path):
            return (False, 'SKILL.md 不存在', False)
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return (False, '读取 SKILL.md 失败: %s' % e, False)
        import re
        m = re.search(r'<!--\s*Skill\s+版本[：:]\s*v(\d+\.\d+)', content)
        if m:
            return (True, 'SKILL.md HTML注释版本号格式正确: v%s' % m.group(1), False)
        return (False, 'SKILL.md 缺少 HTML注释版本号', False)

    # ---- [scripts] SCR-10: references/*.md 引用块版本号格式 ----
    def c_ref_version_block():
        ref_dir = os.path.join(skill_dir, 'references')
        if not os.path.isdir(ref_dir):
            return (True, 'references/ 目录不存在，跳过', False)
        import re
        # 递归遍历 references/ 子目录，收集所有 .md 的 POSIX 相对路径
        md_files = []
        for root, dirs, files in os.walk(ref_dir):
            for f in sorted(files):
                if f.endswith('.md'):
                    rel = os.path.relpath(os.path.join(root, f), ref_dir)
                    md_files.append(rel.replace(os.sep, '/'))
        md_files.sort()
        missing = []
        for fname in md_files:
            fpath = os.path.join(ref_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                missing.append('%s (读取失败)' % fname)
                continue
            if not re.search(r'> 版本[：:]\s*v\d+\.\d+', content):
                missing.append(fname)
        if missing:
            return (False, '缺少版本号引用块: %s' % ', '.join(missing), False)
        return (True, '%d 个 references 含版本号引用块' % len(md_files), False)

    # ---- [scripts] SCR-11: HISTORY.md YAML frontmatter 版本号格式 ----
    def c_history_version_yaml():
        hist_path = os.path.join(skill_dir, 'HISTORY.md')
        if not os.path.isfile(hist_path):
            return (False, 'HISTORY.md 不存在', False)
        try:
            with open(hist_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return (False, '读取 HISTORY.md 失败: %s' % e, False)
        import re
        m = re.search(r'version:\s*v(\d+\.\d+)', content)
        if m:
            return (True, 'HISTORY.md YAML frontmatter 版本号格式正确: v%s' % m.group(1), False)
        return (False, 'HISTORY.md 缺少 version 字段', False)

    # ---- [scripts] SCR-12: evals.json JSON 版本号格式 ----
    def c_evals_version_json():
        evals_path = os.path.join(skill_dir, 'evals', 'evals.json')
        if not os.path.isfile(evals_path):
            return (False, 'evals/evals.json 不存在', False)
        import json
        try:
            with open(evals_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return (False, 'evals.json 解析失败: %s' % e, False)
        ver = data.get('version', '')
        import re
        if re.match(r'v\d+\.\d+', str(ver)):
            return (True, 'evals.json JSON 版本号格式正确: %s' % ver, False)
        return (False, 'evals.json 缺少 version 字段或格式错误', False)

    # ---- [routing] ----
    def c_plan_routing():
        lines = skill_md.splitlines()
        trigger_ok = any(
            ('/plan' in ln and 'brainstorming' in ln and 'writing-plans' in ln)
            for ln in lines
        )
        decision_tree = extract_section(skill_md, '流程决策树')
        dt_ok = ('/plan' in decision_tree) and ('HARD-GATE' in decision_tree)
        if trigger_ok and dt_ok:
            return (True, '/plan 触发行引用 brainstorming+writing-plans；'
                    '决策树含 /plan 分支且带 HARD-GATE', False)
        return (False, 'trigger_row_ok=%s, decision_tree_ok=%s'
                % (trigger_ok, dt_ok), False)

    # ---- [routing] ROUT-02：反向链路审计（无孤儿 reference 文件） ----
    def c_reference_reachability():
        ref_dir = os.path.join(skill_dir, 'references')
        if not os.path.isdir(ref_dir):
            return (True, 'references/ 目录不存在，跳过', False)
        try:
            # 递归遍历 references/ 子目录，收集所有 .md 的 POSIX 相对路径
            all_refs = []
            for root, dirs, files in os.walk(ref_dir):
                for f in sorted(files):
                    if f.endswith('.md'):
                        rel = os.path.relpath(os.path.join(root, f), ref_dir)
                        all_refs.append(rel.replace(os.sep, '/'))
            all_refs.sort()
        except OSError:
            return (False, '无法列举 references/ 目录', False)
        if not all_refs:
            return (True, 'references/ 下无 .md 文件', False)

        # 从 SKILL.md 出发，沿引用 BFS 遍历可达文件。
        # 两种匹配口径互补：
        #   prefixed_re —— 匹配「references/X.md / references/sub/X.md / assets/X.md」纯文本或链接
        #                  （覆盖触发钩子表中的纯文本引用，如 references/common/dc/debugging.md）
        #                  references/ 支持子目录路径，assets/ 保持平铺
        #   bare_re      —— 匹配相对路径裸链接 [X.md](X.md) 或 [X.md](sub/X.md)
        #                  （覆盖 references/ 内部互相引用，含子目录相对路径）
        prefixed_re = re.compile(r'references/(?:[A-Za-z0-9_\-/]+/)*[A-Za-z0-9_\-]+\.md|assets/[A-Za-z0-9_\-]+\.md')
        bare_re = re.compile(r'\]\(([A-Za-z0-9_\-./]+\.md)\)')
        visited = set()
        queue = [os.path.join(skill_dir, 'SKILL.md')]
        while queue:
            cur = queue.pop()
            if cur in visited:
                continue
            visited.add(cur)
            txt = read_text(cur)
            for m in prefixed_re.finditer(txt):
                target = os.path.normpath(
                    os.path.join(os.path.dirname(cur), m.group(0)))
                if os.path.isfile(target) and target not in visited:
                    queue.append(target)
            for m in bare_re.finditer(txt):
                target = os.path.normpath(
                    os.path.join(os.path.dirname(cur), m.group(1)))
                if os.path.isfile(target) and target not in visited:
                    queue.append(target)

        reachable = set()
        for v in visited:
            # 只统计 references/ 树下的文件，转成 POSIX 相对路径与 all_refs 对齐
            if v.startswith(ref_dir + os.sep):
                rel = os.path.relpath(v, ref_dir).replace(os.sep, '/')
                reachable.add(rel)
        orphans = [r for r in all_refs if r not in reachable]
        if orphans:
            return (False, '孤儿 reference 文件(未被 SKILL.md 链接图触达): %s'
                    % ', '.join(orphans), False)
        return (True, '全部 %d 个 references/*.md 均从 SKILL.md 链接图可达'
                % len(all_refs), False)

    # ---- [routing] ROUT-03：参考模块阶段标签完整性（护住「标签持续增长」纪律） ----
    def c_reference_tagged():
        ref_dir = os.path.join(skill_dir, 'references')
        if not os.path.isdir(ref_dir):
            return (True, 'references/ 目录不存在，跳过', False)
        try:
            # 递归遍历 references/ 子目录，收集所有 .md 的 POSIX 相对路径
            all_refs = []
            for root, dirs, files in os.walk(ref_dir):
                for f in sorted(files):
                    if f.endswith('.md'):
                        rel = os.path.relpath(os.path.join(root, f), ref_dir)
                        all_refs.append(rel.replace(os.sep, '/'))
            all_refs.sort()
        except OSError:
            return (False, '无法列举 references/ 目录', False)
        if not all_refs:
            return (True, 'references/ 下无 .md 文件', False)

        tag_re = re.compile(r'阶段标签：')
        untagged = []
        for fn in all_refs:
            txt = read_text(os.path.join(ref_dir, fn))
            # 约定标签置于文件头（line 2）；放宽到全文，避免误判（标签被意外下移仍算有）
            if not tag_re.search(txt):
                untagged.append(fn)
        if untagged:
            return (False, '缺阶段标签的 reference 文件(%d): %s'
                    % (len(untagged), ', '.join(untagged)), False)
        return (True, '全部 %d 个 references/*.md 均含「阶段标签」'
                % len(all_refs), False)

    # ---- [skills] ----
    def c_skill_brainstorming():
        found, _in_wb, locs = find_skill('brainstorming', roots)
        if found:
            return (True, 'brainstorming 存在于: %s' % '; '.join(locs), False)
        return (False, 'brainstorming skill 未在任何搜索目录找到（/plan 链路断裂）', False)

    def c_skill_writing_plans():
        found, _in_wb, locs = find_skill('writing-plans', roots)
        if found:
            return (True, 'writing-plans 存在于: %s' % '; '.join(locs), False)
        return (False, 'writing-plans skill 未在任何搜索目录找到（/plan 链路断裂）', False)

    # ---- [archiving] ----
    def c_archive_mechanism():
        # 重构后归档机制改为"write_project 自动落盘+自动全局跟进，
        # 无独立归档步骤"，故不再数步骤数；改为检查 SKILL.md 是否记载
        # write_project 机制的三个关键特征词。
        # 注：SKILL.md 中表述为"写入即落盘"/"落盘"，检查词用"落盘"以覆盖
        # "自动落盘"/"写入即落盘"/"落盘"等多种表述。
        has_write_project = 'write_project' in skill_md
        has_dump = '落盘' in skill_md
        has_upsert = 'upsert' in skill_md
        has_summary = 'summary_view.md' in skill_md
        if has_write_project and has_dump and has_upsert and has_summary:
            return (True, '归档机制记载 write_project 落盘+upsert，'
                    '并引用 summary_view.md', False)
        return (False, '归档机制缺失关键词: write_project=%s, 落盘=%s, '
                'upsert=%s, summary_view引用=%s'
                % (has_write_project, has_dump, has_upsert, has_summary), False)

    def c_summary_view():
        sv = os.path.join(skill_dir, 'references', 'common', 'pa', 'summary_view.md')
        if not os.path.isfile(sv):
            return (False, 'references/common/pa/summary_view.md 不存在', False)
        txt = read_text(sv)
        has_three = (('启动' in txt) and ('归档' in txt) and ('交接' in txt)
                     and (('三触发' in txt) or ('三个触发' in txt)))
        if has_three:
            return (True, 'summary_view.md 记载三触发（启动/归档/交接）', False)
        return (False, 'summary_view.md 未完整记载三触发（启动/归档/交接）', False)

    def c_summary_exists():
        """SUMMARY_RJ.md 存在性硬校验（ARC-04，与 startup_tidy 的 [BLOCKER] 警告互补）。

        双路径检查（兼容本地开发环境与用户安装环境）：
        - 用户安装后：检查外置路径 ~/.pdca-skill/data/docs_rj/SUMMARY_RJ.md
        - 本地开发环境（pdca-skill 仓库本身，未迁移）：回退检查项目根 docs_rj/SUMMARY_RJ.md
        两者任一存在即 PASS。两者都不存在才 FAIL。
        """
        # 优先检查外置路径（用户安装后场景）
        external_path = None
        try:
            external_path = str(user_data_path.get_docs_rj_path() / 'SUMMARY_RJ.md')
        except Exception:
            pass  # 外置目录不可用，回退项目根
        if external_path and os.path.isfile(external_path):
            return (True, '外置 docs_rj/SUMMARY_RJ.md 存在（启动/归档/交接索引齐备）', False)
        # 回退检查项目根（本地开发环境场景）
        project_root_path = os.path.join(skill_dir, 'docs_rj', 'SUMMARY_RJ.md')
        if os.path.isfile(project_root_path):
            return (True, '项目根 docs_rj/SUMMARY_RJ.md 存在（本地开发环境，未迁移到外置目录）', False)
        return (False,
                'SUMMARY_RJ.md 不存在（外置路径与项目根均未找到），按 summary_view.md 三触发①由 agent 引导式创建'
                '（脚本不静默创建）；补救：读 assets/summary_template.md + 扫描 docs_rj 各子目录生成，'
                '或跑 startup_tidy.py --create-summary 经确认后生成',
                False)

    def c_check_archive_demo():
        tmp = tempfile.mkdtemp(prefix='hh_archive_')
        try:
            mem = os.path.join(tmp, 'MEMORY_RJ.md')
            # 含「当日工作记录」条目 → 应判未归档
            with open(mem, 'w', encoding='utf-8') as handle:
                handle.write(
                    '# MEMORY_RJ\n\n'
                    '## 当日工作记录\n'
                    '- [2026-07-11 10:00] 完成 validate_skill 脚本初版\n\n'
                    '## 关键决策\n'
                    '- 用 stdlib 实现\n'
                )
            status_with, _ = check_archive(tmp)
            # 清空该区块 → 应判已归档
            with open(mem, 'w', encoding='utf-8') as handle:
                handle.write(
                    '# MEMORY_RJ\n\n'
                    '## 当日工作记录\n\n'
                    '## 关键决策\n'
                    '- 用 stdlib 实现\n'
                )
            status_cleared, _ = check_archive(tmp)
            if status_with == 'unarchived' and status_cleared == 'archived':
                return (True, 'check_archive 自校验逻辑可用'
                        '（有记录→未归档；清空→已归档）', False)
            return (False, 'check_archive 行为异常: 有记录时=%s, 清空后=%s'
                    % (status_with, status_cleared), False)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c_task_state_status_whitelist():
        """TASK_STATE.md status 字段白名单校验（ARC-05，H4 修复）。

        扫描 docs_rj/memory_rj/TASK_STATE_*.md，检查 frontmatter 的 status
        字段值是否在合法白名单内。非法值报 MUST FIX，防止 agent 误写
        （如 status: Pauseed 大小写错、status: paused_reason 字段名当值）。

        白名单（与 handoff_tidy.py 状态机一致）：
        - pending：任务进行中未完成
        - completed：任务完成
        - failed：任务失败
        - archived：任务已归档
        - ready_to_close：任务待关闭（GAP4 状态机）
        - paused：任务挂起（SKILL.md §6 /do 第10项，插入新任务时）
        """
        valid_statuses = {'pending', 'completed', 'failed', 'archived',
                          'ready_to_close', 'paused'}
        # 双路径扫描（兼容外置 docs_rj 与项目根 docs_rj）
        scan_dirs = []
        try:
            external = user_data_path.get_docs_rj_path() / 'memory_rj'
            scan_dirs.append(str(external))
        except Exception:
            pass
        scan_dirs.append(os.path.join(skill_dir, 'docs_rj', 'memory_rj'))

        violations = []
        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            for fname in os.listdir(scan_dir):
                if not (fname.startswith('TASK_STATE_') and fname.endswith('.md')):
                    continue
                fpath = os.path.join(scan_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 提取 frontmatter status 字段
                    m = re.search(r'^status:\s*(\S+)', content, re.MULTILINE)
                    if m:
                        val = m.group(1).strip()
                        if val not in valid_statuses:
                            violations.append('%s: status=%s' % (fname, val))
                except OSError:
                    pass  # 读取失败不阻断，跳过该文件

        if not violations:
            return (True, 'TASK_STATE.md status 字段全部合法（白名单：%s）'
                    % '/'.join(sorted(valid_statuses)), False)
        return (False,
                'TASK_STATE.md status 字段非法值（不在白名单 %s）：\n%s\n'
                '补救：手工修正 frontmatter status 为合法值'
                % ('/'.join(sorted(valid_statuses)), '\n'.join(violations)),
                False)

    # ---- [integrity] INT-04: 负向断言（陈旧口径 + 多文件一致性） ----
    def c_int04_negative_assertions():
        """T09: 检测陈旧口径残留 + trigger_hooks.md 与 SKILL.md 一致性。

        陈旧口径 3 项（任何 .py 出现即记 MUST FIX）：
          * C:\\Users\\ 或 /Users/  硬编码个人路径（应脱敏）
          * _skillhub_meta.json  已废弃的元数据文件名
          * 36 条场景  已废弃的旧场景数描述
        例外：protocol/validation.py 的 stale_patterns 段落允许出现（那是规则定义本身）。

        设计原则：只扫描 .py 源码（可执行逻辑硬编码 = bug），
        不扫描 .md 文档（用户画像/示例路径合法）。

        多文件一致性：trigger_hooks.md 与 SKILL.md 关于"市场调研触发词"的描述
        必须一致（两文件都应含"市场调研"或"market_research"关键词）。
        """
        # 收集待扫描文件：仅 .py 源码（scripts/*.py + protocol/*.py + tests/*.py）
        scan_files = []
        for sub in ['scripts', 'protocol', 'tests']:
            sub_dir = os.path.join(skill_dir, sub)
            if os.path.isdir(sub_dir):
                for fp in glob.glob(os.path.join(sub_dir, '*.py')):
                    scan_files.append(fp)

        # 测试器自身免疫：跳过 validate_skill.py 自身（其内部含检测字面量，
        # 那是规则定义本身，不是陈旧口径残留）
        self_path = os.path.normpath(os.path.abspath(__file__))
        scan_files = [fp for fp in scan_files
                      if os.path.normpath(os.path.abspath(fp)) != self_path]

        stale_patterns = ['C:\\\\Users\\\\', '/Users/', '_skillhub_meta.json', '36 条场景']
        # 例外文件：protocol/validation.py 自身定义 stale_patterns，允许出现
        validation_path = os.path.normpath(
            os.path.join(skill_dir, 'protocol', 'validation.py'))
        # 例外文件：tests/test_negative_cases.py 是检测器本身，含字面量做正则匹配
        test_negative_path = os.path.normpath(
            os.path.join(skill_dir, 'tests', 'test_negative_cases.py'))
        violations = []
        for fp in scan_files:
            txt = read_text(fp)
            if not txt:
                continue
            for pat in stale_patterns:
                if pat not in txt:
                    continue
                # 例外：protocol/validation.py 中作为 stale_patterns 定义
                if os.path.normpath(fp) == validation_path:
                    continue
                # 例外：tests/test_negative_cases.py 自身是检测器，含字面量做正则
                if os.path.normpath(fp) == test_negative_path:
                    continue
                rel = os.path.relpath(fp, skill_dir)
                violations.append('%s 含 "%s"' % (rel, pat))

        # 多文件一致性：trigger_hooks.md 与 SKILL.md 都应含"市场调研"或"market_research"
        th_path = os.path.join(skill_dir, 'references', 'common', 'pa', 'trigger_hooks.md')
        th_txt = read_text(th_path)
        sk_txt = skill_md
        th_hit = ('市场调研' in th_txt) or ('market_research' in th_txt) or ('market research' in th_txt)
        sk_hit = ('市场调研' in sk_txt) or ('market_research' in sk_txt) or ('market research' in sk_txt)
        consistency_ok = th_hit and sk_hit

        if violations:
            detail = '陈旧口径残留(%d): %s' % (len(violations),
                                            '; '.join(violations[:5]))
            if not consistency_ok:
                detail += '; 多文件不一致(市场调研触发词 trigger_hooks=%s / SKILL=%s)' % (
                    th_hit, sk_hit)
            return (False, detail, False)
        if not consistency_ok:
            return (False,
                    '多文件不一致: trigger_hooks.md 命中=%s, SKILL.md 命中=%s'
                    % (th_hit, sk_hit), False)
        return (True, '无陈旧口径残留；trigger_hooks.md 与 SKILL.md 市场调研触发词一致',
                False)

    # ---- [protocol] PROT-01: protocol/ 9 .py 齐全 + 可 import ----
    def c_protocol_structure():
        """T22: 验证 protocol/ 下 9 个 .py 齐全 + from protocol import FILE_ROLES 成功。"""
        expected_files = [
            '__init__.py', 'constants.py', 'file_roles.py',
            'field_contracts.py', 'stages.py', 'routing.py',
            'validation.py', 'markdown_structure.py', 'change_impact_map.py',
        ]
        protocol_dir = os.path.join(skill_dir, 'protocol')
        missing = []
        for fn in expected_files:
            if not os.path.isfile(os.path.join(protocol_dir, fn)):
                missing.append(fn)
        if missing:
            return (False, 'protocol/ 缺失文件(%d): %s'
                    % (len(missing), ', '.join(missing)), False)
        # 验证 import 成功
        try:
            if str(skill_dir) not in sys.path:
                sys.path.insert(0, str(skill_dir))
            from protocol import FILE_ROLES  # noqa: F401
        except Exception as exc:
            return (False, 'from protocol import FILE_ROLES 失败: %s' % exc, False)
        return (True, 'protocol/ 9 文件齐全 + import FILE_ROLES 成功', False)

    # ---- [protocol] PROT-02: protocol/*.py 回指 SKILL.md/references ----
    def c_protocol_reverse_links():
        """T23: grep protocol/*.py 的 docstring 中"设计来源"或"Traceability"行,
        检查是否含 SKILL.md 或 references/。

        当前 protocol/*.py 未加 traceability docstring，预期 FAIL（批次5 修复）。
        """
        protocol_dir = os.path.join(skill_dir, 'protocol')
        if not os.path.isdir(protocol_dir):
            return (False, 'protocol/ 目录不存在', False)
        py_files = sorted(glob.glob(os.path.join(protocol_dir, '*.py')))
        if not py_files:
            return (False, 'protocol/ 下无 .py 文件', False)
        trace_re = re.compile(r'(设计来源|Traceability)', re.IGNORECASE)
        ref_re = re.compile(r'(SKILL\.md|references/)')
        files_with_trace = []
        files_missing_trace = []
        for fp in py_files:
            txt = read_text(fp)
            has_trace = False
            for line in txt.splitlines():
                if trace_re.search(line) and ref_re.search(line):
                    has_trace = True
                    break
            if has_trace:
                files_with_trace.append(os.path.basename(fp))
            else:
                files_missing_trace.append(os.path.basename(fp))
        # 通过条件：每个文件至少 1 个回指（即 files_missing_trace 为空）
        if files_missing_trace:
            return (False,
                    'protocol/*.py 缺 traceability 回指(%d/%d): %s'
                    % (len(files_missing_trace), len(py_files),
                       ', '.join(files_missing_trace)),
                    False)
        return (True, '全部 %d 个 protocol/*.py 含 traceability 回指'
                % len(py_files), False)

    # ---- [protocol] PROT-03: file_roles 完整性 ----
    def c_file_roles_completeness():
        """T24: 验证 protocol.file_roles.FILE_ROLES 10 角色齐全 +
        每个含 written_by / read_by 字段。"""
        try:
            if str(skill_dir) not in sys.path:
                sys.path.insert(0, str(skill_dir))
            from protocol import FILE_ROLES
        except Exception as exc:
            return (False, 'from protocol import FILE_ROLES 失败: %s' % exc, False)
        if not isinstance(FILE_ROLES, dict):
            return (False, 'FILE_ROLES 不是 dict 类型: %s' % type(FILE_ROLES), False)
        if len(FILE_ROLES) != 10:
            return (False, 'FILE_ROLES 角色数=%d（预期 10）' % len(FILE_ROLES), False)
        missing_fields = []
        for role_name, role_def in FILE_ROLES.items():
            if not isinstance(role_def, dict):
                missing_fields.append('%s (非 dict)' % role_name)
                continue
            if 'written_by' not in role_def:
                missing_fields.append('%s.written_by' % role_name)
            if 'read_by' not in role_def:
                missing_fields.append('%s.read_by' % role_name)
        if missing_fields:
            return (False, 'FILE_ROLES 字段缺失(%d): %s'
                    % (len(missing_fields), ', '.join(missing_fields)), False)
        return (True, 'FILE_ROLES 10 角色齐全 + written_by/read_by 字段完整', False)

    # ---- [protocol] PROT-04: markdown_structure 章节检查 ----
    def c_markdown_structure_sections():
        """T25: 验证 assets/*_template.md 三模板(spec/task/handoff)齐全 + 章节数达标。"""
        try:
            if str(skill_dir) not in sys.path:
                sys.path.insert(0, str(skill_dir))
            from protocol import MARKDOWN_TEMPLATES
        except Exception as exc:
            return (False, 'from protocol import MARKDOWN_TEMPLATES 失败: %s' % exc,
                    False)
        if not isinstance(MARKDOWN_TEMPLATES, dict):
            return (False, 'MARKDOWN_TEMPLATES 不是 dict: %s'
                    % type(MARKDOWN_TEMPLATES), False)
        target_keys = ['spec', 'task', 'handoff']
        missing_templates = []
        section_failures = []
        for key in target_keys:
            tpl = MARKDOWN_TEMPLATES.get(key)
            if not isinstance(tpl, dict):
                missing_templates.append('%s (未定义/非 dict)' % key)
                continue
            tpl_file = tpl.get('template_file')
            if not tpl_file:
                missing_templates.append('%s.template_file' % key)
                continue
            tpl_path = os.path.join(skill_dir, tpl_file)
            if not os.path.isfile(tpl_path):
                missing_templates.append(tpl_file)
                continue
            # 统计 ## 章节数（行首 ## 后非 #）
            txt = read_text(tpl_path)
            section_count = 0
            for line in txt.splitlines():
                if re.match(r'^##\s+', line):
                    section_count += 1
            min_sections = tpl.get('min_sections', 0)
            if section_count < min_sections:
                section_failures.append('%s: %d 章节 < min=%d'
                                        % (tpl_file, section_count, min_sections))
        if missing_templates:
            return (False, '模板文件缺失(%d): %s'
                    % (len(missing_templates), ', '.join(missing_templates)), False)
        if section_failures:
            return (False, '章节数不达标(%d): %s'
                    % (len(section_failures), '; '.join(section_failures)), False)
        return (True, 'spec/task/handoff 三模板齐全 + 章节数均达标', False)

    # ---- [global] GLOBAL-01: SKILL.md frontmatter 8 字段完整性 ----
    def c_frontmatter_completeness():
        """T26: 验证 SKILL.md frontmatter 含 8 字段:
        name/description/agent_created/license/version/keywords/category/author。

        keywords 是 list，需检测 `^keywords:` 后跟 list 项。
        """
        if not skill_md.strip():
            return (False, 'SKILL.md 为空', False)
        frontmatter = parse_frontmatter(skill_md)
        if frontmatter is None:
            return (False, 'SKILL.md 缺少 YAML frontmatter', False)
        required_scalar = ['name', 'description', 'agent_created',
                           'license', 'version', 'category', 'author']
        missing = [f for f in required_scalar if f not in frontmatter]
        # keywords 单独检测（list 形式，parse_frontmatter 解析为空字符串）
        has_keywords = 'keywords' in frontmatter
        if not has_keywords:
            missing.append('keywords')
        elif not frontmatter.get('keywords'):
            # 解析后 keywords 值为空字符串（实际是 list），需进一步验证文件中存在 list 项
            lines = skill_md.splitlines()
            in_fm = False
            has_list_item = False
            for line in lines:
                if line.strip() == '---':
                    if in_fm:
                        break
                    in_fm = True
                    continue
                if in_fm and line.startswith('  - '):
                    has_list_item = True
                    break
            if not has_list_item:
                missing.append('keywords (list 项缺失)')
        if missing:
            return (False, 'frontmatter 缺字段(%d): %s'
                    % (len(missing), ', '.join(missing)), False)
        return (True, 'frontmatter 8 字段齐全 (name/description/agent_created/'
                'license/version/keywords/category/author)', False)

    # ---- [global] GLOBAL-02: trigger_hooks.md 含"市场调研"触发词 ----
    def c_trigger_hooks_completeness():
        """T27: 验证 references/common/pa/trigger_hooks.md 含"市场调研"或"market_research"关键词。"""
        th_path = os.path.join(skill_dir, 'references', 'common', 'pa', 'trigger_hooks.md')
        if not os.path.isfile(th_path):
            return (False, 'references/common/pa/trigger_hooks.md 不存在', False)
        txt = read_text(th_path)
        hit_zh = '市场调研' in txt
        hit_en = 'market_research' in txt
        # 表格里写作 "market research"（带空格），放宽匹配
        hit_en_loose = ('market research' in txt.lower())
        if hit_zh or hit_en or hit_en_loose:
            hits = []
            if hit_zh:
                hits.append('市场调研')
            if hit_en:
                hits.append('market_research')
            if hit_en_loose and not hit_en:
                hits.append('market research')
            return (True, 'trigger_hooks.md 含市场调研触发词(%s)'
                    % '/'.join(hits), False)
        return (False, 'trigger_hooks.md 不含"市场调研"或"market_research"关键词', False)

    # CHECKS 注册表（顺序即报告顺序）
    checks = [
        ('INT-01', 'SKILL.md frontmatter 完整', 'integrity', c_frontmatter),
        ('INT-02', 'references/assets 引用无死链', 'integrity', c_deadlinks),
        ('INT-03', 'evals.json 合法且非空', 'integrity', c_evals),
        ('SCR-01', 'generate_docs.py 可编译', 'scripts', c_pycompile),
        ('SCR-02', 'generate_docs --task 实跑生成文档', 'scripts', c_run_generate),
        ('SCR-03', 'generate_docs --scan-docs 合法 JSON', 'scripts', c_scan_docs),
        ('SCR-04', 'generate_docs --archive-scattered --dry-run', 'scripts', c_archive_dry),
        ('SCR-05', 'generate_docs --migrate-rj --dry-run', 'scripts', c_migrate_dry),
        ('SCR-06', 'loop_audit.py 输出 PDCA Ready Score', 'scripts', c_loop_audit),
        ('SCR-07', 'spec_template.md 含 BRD 5 子项+§10 Clarifications+Self-Review 9 维度', 'scripts', c_spec_brd),
        ('SCR-08', 'loop_constraints.md 含 max_iterations+bool 类型校验+SCR-08 引用', 'scripts', c_loop_max_iter),
        ('SCR-09', 'SKILL.md HTML注释版本号格式', 'scripts', c_skill_version_html),
        ('SCR-10', 'references/*.md 引用块版本号格式', 'scripts', c_ref_version_block),
        ('SCR-11', 'HISTORY.md YAML frontmatter 版本号格式', 'scripts', c_history_version_yaml),
        ('SCR-12', 'evals.json JSON 版本号格式', 'scripts', c_evals_version_json),
        ('ROUT-01', '/plan 触发+决策树 HARD-GATE', 'routing', c_plan_routing),
        ('ROUT-02', 'references/*.md 链接图可达(无孤儿)', 'routing', c_reference_reachability),
        ('ROUT-03', 'references/*.md 均含阶段标签', 'routing', c_reference_tagged),
        ('SKL-01', 'brainstorming skill 存在', 'skills', c_skill_brainstorming),
        ('SKL-02', 'writing-plans skill 存在', 'skills', c_skill_writing_plans),
        ('ARC-01', '归档机制write_project+自动落盘+upsert', 'archiving', c_archive_mechanism),
        ('ARC-02', 'summary_view 三触发', 'archiving', c_summary_view),
        ('ARC-03', 'check_archive 自校验演示', 'archiving', c_check_archive_demo),
        ('ARC-04', 'SUMMARY_RJ.md 存在（启动/归档/交接索引）', 'archiving', c_summary_exists),
        ('ARC-05', 'TASK_STATE.md status 字段白名单校验（含 paused）', 'archiving',
         c_task_state_status_whitelist),
        # ---- 新增（T09 + T22-T26 + T27） ----
        ('INT-04', '负向断言(陈旧口径+市场调研一致性)', 'integrity',
         c_int04_negative_assertions),
        ('PROT-01', 'protocol/ 9 .py 齐全+import 成功', 'protocol',
         c_protocol_structure),
        ('PROT-02', 'protocol/*.py 含 traceability 回指', 'protocol',
         c_protocol_reverse_links),
        ('PROT-03', 'FILE_ROLES 10 角色+written_by/read_by 字段', 'protocol',
         c_file_roles_completeness),
        ('PROT-04', 'markdown_structure 三模板齐全+章节数达标', 'protocol',
         c_markdown_structure_sections),
        ('GLOBAL-01', 'SKILL.md frontmatter 8 字段齐全', 'global',
         c_frontmatter_completeness),
        ('GLOBAL-02', 'trigger_hooks.md 含市场调研触发词', 'global',
         c_trigger_hooks_completeness),
    ]
    return checks


# ---------------------------------------------------------------------------
# 运行 / 报告 / Loop
# ---------------------------------------------------------------------------
def run_single(func, retries, interval, in_loop):
    """运行单个 check；loop 模式下对 transient FAIL 重试。"""
    passed, detail, transient = func()
    if in_loop and (not passed) and transient:
        for _ in range(retries):
            time.sleep(interval)
            passed, detail, transient = func()
            if passed:
                break
    return passed, detail, transient


def run_suite(checks, retries, interval, in_loop):
    """运行整套 check，返回结果列表。"""
    results = []
    for (cid, name, category, func) in checks:
        passed, detail, transient = run_single(func, retries, interval, in_loop)
        results.append({
            'id': cid,
            'name': name,
            'category': category,
            'passed': passed,
            'detail': detail,
            'transient': transient,
        })
    return results


def print_report(results, quiet):
    """打印报告表 + 汇总。quiet 时跳过明细表，仅打印汇总。"""
    if not quiet:
        print('\n' + '=' * 80)
        print('%-8s %-36s %-10s %-5s' % ('ID', 'NAME', 'CATEGORY', 'RESULT'))
        print('-' * 80)
        for r in results:
            result = 'PASS' if r['passed'] else 'FAIL'
            print('%-8s %-36s %-10s %-5s'
                  % (r['id'], r['name'][:36], r['category'], result))
            if not r['passed']:
                print('         └─ %s' % r['detail'])
        print('=' * 80)

    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed
    must_fix = [r for r in results if (not r['passed']) and (not r['transient'])]
    rate = (passed / total * 100) if total else 0.0
    print('\nSUMMARY: %d/%d pass (%.1f%%); FAIL=%d; MUST FIX=%d'
          % (passed, total, rate, failed, len(must_fix)))
    if must_fix:
        print('MUST FIX (结构缺口，永不自动通过):')
        for r in must_fix:
            print('  - [%s] %s: %s' % (r['id'], r['name'], r['detail']))


def write_json(results, path):
    """将结果写入 JSON 文件。"""
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    must_fix = [r['id'] for r in results
                if (not r['passed']) and (not r['transient'])]
    payload = {
        'summary': {
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': round(passed / total * 100, 2) if total else 0.0,
            'must_fix': must_fix,
        },
        'checks': [
            {
                'id': r['id'],
                'name': r['name'],
                'category': r['category'],
                'passed': r['passed'],
                'detail': r['detail'],
                'transient': r['transient'],
            }
            for r in results
        ],
    }
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        print('警告：写入 JSON 失败: %s' % exc, file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------
def resolve_skill_dir(arg):
    """解析 skill 根目录；默认取 scripts/ 的上级目录。"""
    if arg:
        return os.path.abspath(arg)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..'))


def parse_args():
    parser = argparse.ArgumentParser(
        description='pdca-skill 工具调用校验 loop 脚本（stdlib-only）')
    parser.add_argument('--skill-dir', default=None,
                        help='skill 根目录（默认 scripts/ 的上级）')
    parser.add_argument('--loop', action='store_true',
                        help='开启 loop 模式（持续重跑直到全绿或达 --max-iter）')
    parser.add_argument('--retries', type=int, default=3,
                        help='transient FAIL 重试次数（默认 3）')
    parser.add_argument('--interval', type=float, default=5.0,
                        help='重试/重跑间隔秒（默认 5）')
    parser.add_argument('--max-iter', type=int, default=10,
                        help='loop 最大迭代次数（默认 10）')
    parser.add_argument('--json', default=None,
                        help='将结果写入 JSON 文件')
    parser.add_argument('--quiet', action='store_true',
                        help='精简输出（仅汇总 / loop 迭代摘要）')
    return parser.parse_args()


def main():
    args = parse_args()
    skill_dir = resolve_skill_dir(args.skill_dir)
    if not os.path.isdir(skill_dir):
        print('错误：skill 目录不存在: %s' % skill_dir, file=sys.stderr)
        return 2

    skill_md_path = os.path.join(skill_dir, 'SKILL.md')
    skill_md = read_text(skill_md_path)
    gen_script = os.path.join(skill_dir, 'scripts', 'generate_docs.py')
    python = sys.executable
    roots = build_skill_search_roots()
    checks = build_checks(skill_dir, skill_md, gen_script, python, roots)

    if not args.loop:
        results = run_suite(checks, args.retries, args.interval, False)
        print_report(results, args.quiet)
        if args.json:
            write_json(results, args.json)
        return 0 if all(r['passed'] for r in results) else 1

    # ---- loop 模式 ----
    final = None
    for iteration in range(1, args.max_iter + 1):
        results = run_suite(checks, args.retries, args.interval, True)
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        must_fix = [r for r in results if (not r['passed']) and (not r['transient'])]
        transient_fail = [r for r in results
                          if (not r['passed']) and r['transient']]

        summary = '[iter %d/%d] %d/%d pass; %d MUST FIX' % (
            iteration, args.max_iter, passed, total, len(must_fix))
        if must_fix:
            summary += ': ' + ', '.join(r['id'] for r in must_fix)
        if transient_fail:
            summary += '; %d transient' % len(transient_fail)
        print(summary)

        final = results
        if not must_fix and not transient_fail:
            break
        if iteration >= args.max_iter:
            break
        time.sleep(args.interval)

    print_report(final, args.quiet)
    if args.json:
        write_json(final, args.json)
    return 0 if all(r['passed'] for r in final) else 1


if __name__ == '__main__':
    sys.exit(main())
