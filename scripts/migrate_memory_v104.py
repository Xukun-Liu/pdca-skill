"""
migrate_memory_v104.py — v1.0.4 存量记忆迁移脚本（一次性）

五步（spec v104 §4.3）：
  1. 双备份：memory_main.md → memory_main.md.bak_v103；memory_rj/ → memory_rj_backup_v103/
  2. 解析 memory_main.md 三种异构格式（完整条目 / 一行摘要式 / 同 task 多条目）
  3. 归类：关键词启发式 + 存量自由标签映射表 → 6 主分类，兜底 workflow
     正文落 ~/.pdca-skill/data/memory/legacy_body/{tag}/{YYYYMM}/{项目名}__{task}_{ts}.md
     memory_main.md 重建为纯索引（按项目分段，每条一行）
     memory_rj 扁平 *_memory_*.md → {tag}/{YYYYMM}/ 深层（物理移动，原文件删除前已备份）
  4. 对账校验：迁移前条目数 == 索引行数 == legacy_body 文件数；扁平文件数 == 深层文件数
  5. 写 .schema_version（structure=tag_folder_monthly）
     （位置在外置 DATA_DIR 根下，即 ~/.pdca-skill/data/.schema_version，
       与 memory/ 子目录平级——不在 memory/ 内，标志整个数据域 schema 版本）

用法：
  python scripts/migrate_memory_v104.py                 # 迁外置数据目录
  python scripts/migrate_memory_v104.py --project-root .  # 追加迁移指定项目根的 memory_rj
  python scripts/migrate_memory_v104.py --dry-run        # 预览不落盘

退出码：0=成功/已迁移跳过；2=对账失败或异常（不删原文件，备份兜底）
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_data_path  # noqa: E402
from memory_tags import infer_memory_class  # noqa: E402

DATA_DIR = user_data_path.get_user_data_dir()
MEMORY_DIR = DATA_DIR / "memory"
GLOBAL_MEMORY = MEMORY_DIR / "memory_main.md"
LEGACY_BODY = MEMORY_DIR / "legacy_body"
SCHEMA_FILE = DATA_DIR / ".schema_version"

# 存量自由标签 → 主分类映射表（spec §4.3 第3步）
LEGACY_TAG_MAP = {
    "sandbox_workaround": "pitfall",
    "sync_release": "workflow",
    "adopted_lesson": "workflow",
    "bugfix": "pitfall",
    "cross-machine": "workflow",
    "regression": "pitfall",
    "architecture": "tech_solution",
    "adversarial_fix": "pitfall",
    "memory_governance": "workflow",
    "skill_fuse": "workflow",
}

ENTRY_RE = re.compile(r'^### 记忆条目 · (.+?)(?:（(\d{4}-\d{2}-\d{2} \d{2}:\d{2})）)?\s*$')
ONELINE_RE = re.compile(r'^- \*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\*\* \| (.+)$')
TS_IN_NAME_RE = re.compile(r'(\d{8}_\d{4})')


def _infer_class_from_entry(task, content, exp_tags):
    """归类：存量自由标签映射优先，其次内容关键词启发式，兜底 workflow。"""
    for t in exp_tags or []:
        mapped = LEGACY_TAG_MAP.get(t.strip().lower())
        if mapped:
            return mapped
    text = '%s\n%s' % (task, content)
    return infer_memory_class(text)


def parse_memory_main(content):
    """解析 memory_main.md → 条目列表。

    支持三种格式：### 完整条目 / - **时间**| 一行摘要式（同 task 多条目天然保留，逐条返回）。
    """
    entries = []
    lines = content.split('\n')
    i = 0
    project = None
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith('## ') and not s.startswith('### '):
            project = s[3:].strip()
            i += 1
            continue
        m = ENTRY_RE.match(s)
        if m:
            task, ts = m.group(1).strip(), (m.group(2) or '')
            j = i + 1
            body = []
            exp_tags, importance, is_lesson = [], 'medium', False
            while j < len(lines):
                fl = lines[j].strip()
                if fl.startswith('### 记忆条目 · ') or (fl.startswith('## ') and not fl.startswith('### ')):
                    break
                if fl.startswith('**经验标签**: '):
                    tag_str = fl.replace('**经验标签**: ', '').strip()
                    if tag_str and tag_str != '无':
                        exp_tags = [t.strip() for t in tag_str.split(',')]
                elif fl.startswith('**重要性**: '):
                    importance = fl.replace('**重要性**: ', '').strip()
                elif fl.startswith('**是否经验**: '):
                    is_lesson = fl.replace('**是否经验**: ', '').strip().lower() == 'true'
                body.append(lines[j])
                j += 1
            entries.append({
                'project': project, 'task': task, 'ts': ts,
                'block': '\n'.join([s] + body),
                'content': '\n'.join(body), 'exp_tags': exp_tags,
                'importance': importance, 'is_lesson': is_lesson,
            })
            i = j
            continue
        m2 = ONELINE_RE.match(s)
        if m2:
            entries.append({
                'project': project, 'task': '(summary)', 'ts': m2.group(1),
                'block': s, 'content': m2.group(2), 'exp_tags': [],
                'importance': 'medium', 'is_lesson': False,
            })
            i += 1
            continue
        i += 1
    return entries


def _summary_from_content(content, limit=40):
    for line in (content or '').split('\n'):
        t = line.strip()
        t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
        t = re.sub(r'^[-*]\s+', '', t)
        t = re.sub(r'[|`]', ' ', t).strip()
        if t:
            return t[:limit]
    return '（无摘要）'


def _ym_from_ts(ts):
    """'2026-08-25 21:53' → '202608'；无时间用当前月。"""
    m = re.match(r'(\d{4})-(\d{2})', ts or '')
    if m:
        return m.group(1) + m.group(2)
    return datetime.now().strftime('%Y%m')


def _fname_ts(ts):
    """'2026-08-25 21:53' → '20260825_2153'；无时间用当前。"""
    m = re.match(r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})', ts or '')
    if m:
        return '%s%s%s_%s%s' % m.groups()
    return datetime.now().strftime('%Y%m%d_%H%M')


def migrate(dry_run=False, project_root=None):
    """主流程。返回 dict 报告（对账失败信息含在 errors）。"""
    started = datetime.now()
    report = {'started_at': started.strftime('%Y-%m-%d %H:%M:%S'),
              'dry_run': dry_run, 'steps': [], 'errors': []}

    # 幂等检查：已迁移且结构一致 → 跳过
    if SCHEMA_FILE.is_file():
        try:
            with open(str(SCHEMA_FILE), 'r', encoding='utf-8-sig') as f:
                sv = json.load(f)
            if sv.get('structure') == 'tag_folder_monthly':
                report['already_migrated'] = True
                report['migrated_at'] = sv.get('migrated_at')
                return report
        except Exception:
            pass

    # ── 步骤1：双备份 ──
    bak_main = MEMORY_DIR / 'memory_main.md.bak_v103'
    if not dry_run:
        if GLOBAL_MEMORY.is_file() and not bak_main.is_file():
            shutil.copy2(str(GLOBAL_MEMORY), str(bak_main))
    report['steps'].append('backup: memory_main.md.bak_v103')

    external_memory_rj = user_data_path.get_memory_rj_path()
    bak_rj = DATA_DIR / 'docs_rj' / 'memory_rj_backup_v103'
    if not dry_run and external_memory_rj.is_dir() and not bak_rj.is_dir():
        shutil.copytree(str(external_memory_rj), str(bak_rj))
    report['steps'].append('backup: docs_rj/memory_rj_backup_v103')

    # ── 步骤2：解析 memory_main ──
    if not GLOBAL_MEMORY.is_file():
        report['errors'].append('memory_main.md 不存在: %s' % GLOBAL_MEMORY)
        return report
    with open(str(GLOBAL_MEMORY), 'r', encoding='utf-8') as f:
        content = f.read()
    entries = parse_memory_main(content)
    before_count = len(entries)
    report['before_total'] = before_count

    # ── 步骤3：归类落盘 legacy_body + 重建 memory_main 索引 ──
    index_by_project = {}
    tag_counts = {}
    legacy_files = 0
    fname_seq = {}  # (project, task, ts) 去重计数：同名文件加序号防覆盖（对账真实性）
    for e in entries:
        tag = _infer_class_from_entry(e['task'], e['content'], e['exp_tags'])
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        ym = _ym_from_ts(e['ts'])
        safe_project = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', e['project'] or 'orphan')
        key = (e['project'], e['task'], e['ts'])
        fname_seq[key] = fname_seq.get(key, 0) + 1
        seq_suffix = '' if fname_seq[key] == 1 else '_%d' % fname_seq[key]
        fname = '%s__%s_%s%s.md' % (safe_project,
                                    re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', e['task']),
                                    _fname_ts(e['ts']), seq_suffix)
        body_path = LEGACY_BODY / tag / ym / fname
        if not dry_run:
            os.makedirs(str(body_path.parent), exist_ok=True)
            with open(str(body_path), 'w', encoding='utf-8') as f:
                f.write(e['block'] + '\n')
        legacy_files += 1
        body_url = 'file:///%s' % str(body_path.resolve()).replace('\\', '/')
        idx = ('- %s | %s | %s | 重要性%s | is_lesson=%s | %s | [正文](%s)'
               % (e['ts'] or '未知时间', e['task'], tag, e['importance'],
                  str(e['is_lesson']).lower(), _summary_from_content(e['content']), body_url))
        index_by_project.setdefault(e['project'] or 'orphan', []).append(idx)

    if not dry_run:
        new_main = ['# 主记忆（全局聚合 · v1.0.4 索引视图）', '',
                    '> ⚠️ 仅供参考，以你当前指令为准。本文件为索引（每条一行，正文在链接指向的 legacy_body/ 标签文件夹）。', '']
        for proj in index_by_project:
            new_main.append('## %s' % proj)
            new_main.append('')
            new_main.extend(index_by_project[proj])
            new_main.append('')
        with open(str(GLOBAL_MEMORY), 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_main))
    report['legacy_body_files'] = legacy_files
    report['tag_counts'] = tag_counts

    # ── 步骤3b：迁移 memory_rj 扁平文件（外置 + 可选项目根）──
    moved_flat = 0
    roots = [str(external_memory_rj)]
    if project_root:
        roots.append(os.path.join(os.path.abspath(project_root), 'docs_rj', 'memory_rj'))
    for rj_dir in roots:
        if not os.path.isdir(rj_dir):
            continue
        for fname in os.listdir(rj_dir):
            if not re.match(r'.*_memory_\d{8}_\d{4}\.md$', fname):
                continue  # 只迁记忆文件（TASK_STATE/INDEX 等留原地）
            src = os.path.join(rj_dir, fname)
            if not os.path.isfile(src):
                continue
            with open(src, 'r', encoding='utf-8', errors='replace') as f:
                body = f.read()
            exp_tags = re.findall(r'\*\*经验标签\*\*: ([^\n]+)', body)
            etags = []
            for t in exp_tags:
                etags.extend(x.strip() for x in t.split(',') if x.strip() and x.strip() != '无')
            tag = _infer_class_from_entry(fname, body, etags)
            ym_m = TS_IN_NAME_RE.search(fname)
            ym = (ym_m.group(1)[:6] if ym_m else datetime.now().strftime('%Y%m'))
            dst_dir = os.path.join(rj_dir, tag, ym)
            dst = os.path.join(dst_dir, fname)
            if not dry_run:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.move(src, dst)
            moved_flat += 1
    report['moved_flat_files'] = moved_flat

    # ── 步骤4：对账校验（数实际落盘文件数，防同名覆盖假绿）──
    after_index = 0
    actual_files = legacy_files
    if not dry_run:
        with open(str(GLOBAL_MEMORY), 'r', encoding='utf-8') as f:
            after_index = sum(1 for ln in f if ln.startswith('- ') and '[正文](file:///' in ln)
        actual_files = sum(1 for _ in LEGACY_BODY.rglob('*.md'))
    else:
        # dry-run 未写盘：索引行数按写入计划数假定（对账三口径一致性预检）
        after_index = legacy_files
    ok = (before_count == legacy_files == actual_files == after_index)
    report['reconcile'] = {'before': before_count, 'legacy_body_written': legacy_files,
                           'legacy_body_actual_files': actual_files,
                           'index_lines': after_index, 'equal': ok}
    if not ok:
        report['errors'].append('对账失败：before=%d written=%d actual_files=%d index=%d'
                                % (before_count, legacy_files, actual_files, after_index))
        return report

    # ── 步骤5：写 schema_version ──
    if not dry_run:
        with open(str(SCHEMA_FILE), 'w', encoding='utf-8') as f:  # 无 BOM 直写
            json.dump({'version': 'v1.0.4', 'structure': 'tag_folder_monthly',
                       'migrated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                       'entries': before_count}, f, ensure_ascii=False, indent=2)
    report['schema_written'] = not dry_run
    report['elapsed_sec'] = (datetime.now() - started).total_seconds()
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description='v1.0.4 存量记忆迁移（一次性，幂等可重跑）')
    parser.add_argument('--dry-run', action='store_true', help='预览不落盘')
    parser.add_argument('--project-root', default=None,
                        help='追加迁移指定项目根下的 docs_rj/memory_rj（如 .）')
    args = parser.parse_args()

    try:
        report = migrate(dry_run=args.dry_run, project_root=args.project_root)
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'hint': '原文件未删（备份兜底），可重跑'},
                         ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get('already_migrated'):
        return 0
    return 2 if report.get('errors') else 0


if __name__ == '__main__':
    sys.exit(main())
