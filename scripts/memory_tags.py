"""
记忆主分类单点常量模块（v1.0.4）
所有脚本统一 import 本模块获取主分类定义，禁止在别处重复定义标签字符串。
未来新增主分类：只改本文件 MEMORY_TAGS/TAG_PRIORITY/INFER_RULES 三处 + 文档一处。
"""

import sys

# 6 主分类（决定记忆文件落哪个文件夹）+ 兜底
MEMORY_TAGS = ["tech_solution", "pitfall", "workflow", "tool_usage", "decision", "status"]

# 主分类优先级（一条记忆符合多分类时，按此列表顺序取最靠前者）
TAG_PRIORITY = ["status", "decision", "pitfall", "tech_solution", "tool_usage", "workflow"]

# 兜底分类（非法值/无法推断时落此）
FALLBACK_TAG = "workflow"

# 启发式推断规则：关键词 → 主分类（infer_memory_class 用）
# 关键词设计原则：特异词优先（踩坑/沙箱/架构），泛词（完成/状态）收紧或排除——
# v1.0.4 迁移实测教训：status 含"完成/状态"时 81% 条目被误归 status
INFER_RULES = {
    "pitfall": ["踩坑", "报错", "失败", "异常", "rollback", "回滚", "bug", "修不好", "拦截", "沙箱", "坑"],
    "tech_solution": ["方案", "架构", "实现", "部署", "设计", "改造", "重构", "技术路线", "接口", "修复方案"],
    "decision": ["决策", "拍板", "选定", "取舍", "评审通过", "确认方案", "最终选择"],
    "tool_usage": ["工具", "命令", "脚本", "用法", "安装", "配置", "参数", "CLI"],
    "status": ["任务完成总结", "进度更新", "交接", "收尾", "巡检", "周报", "里程碑", "阶段汇总"],
    # workflow 不设关键词：默认兜底
}

# 推断仲裁顺序：按关键词特异度（特异→泛），不是 TAG_PRIORITY——
# TAG_PRIORITY 用于"显式多分类冲突时人工仲裁"；机器推断必须特异词优先，
# 否则泛词（status 类）抢走一切（迁移实测 81% 误归）。
# decision 的"拍板/选定"（动作强信号）特异于 tech_solution 的"方案"（高频名词泛词）
INFER_ARBITRATION = ["pitfall", "decision", "tech_solution", "tool_usage", "status", "workflow"]


def validate_memory_class(value):
    """
    校验主分类合法性（写通道安全阀，永不抛异常）。
    输入：任意字符串或 None。
    输出：MEMORY_TAGS 中的合法值。非法输入返回 FALLBACK_TAG 并打 warning 到 stderr。
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return FALLBACK_TAG
    if not isinstance(value, str):
        return FALLBACK_TAG
    normalized = value.strip().lower()
    if normalized in MEMORY_TAGS:
        return normalized
    sys.stderr.write("[memory_tags] warning: 非法主分类 '%s'（合法值：%s），已兜底落 %s\n"
                     % (value, ", ".join(MEMORY_TAGS), FALLBACK_TAG))
    return FALLBACK_TAG


def infer_memory_class(content):
    """
    按内容关键词启发式推断主分类（write_project 未显式传 memory_class 时用）。
    输入：记忆正文文本。
    输出：推断的主分类；多命中按 TAG_PRIORITY 取最高；无命中返回 FALLBACK_TAG。
    """
    if not content or not isinstance(content, str):
        return FALLBACK_TAG
    hits = []
    for tag, keywords in INFER_RULES.items():
        for kw in keywords:
            if kw in content:
                hits.append(tag)
                break
    if not hits:
        return FALLBACK_TAG
    # 按 INFER_ARBITRATION 顺序取第一个命中的（特异词优先，防泛词抢归类）
    for tag in INFER_ARBITRATION:
        if tag in hits:
            return tag
    return FALLBACK_TAG


# ---------------------------------------------------------------------------
# CLI（v1.1.0 · B2 / 任务 2.3）：核对某个任务的记忆文件分类落点是否与推断一致
# 常量区保持不变，CLI 只追加在文件末尾。
# ---------------------------------------------------------------------------

import argparse  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402

TASK_NAME_RE = re.compile(r'^[a-z0-9_]+$')


def _collect_task_memories(memory_root, task):
    """递归收集 memory_rj 下 {task}_memory_*.md，返回 [(路径, 目录分类 or '')]。"""
    prefix = '%s_memory_' % task
    hits = []
    for root, dirs, files in os.walk(memory_root):
        dirs.sort()
        for name in sorted(files):
            if name.startswith(prefix) and name.endswith('.md'):
                rel = os.path.relpath(root, memory_root)
                first = '' if rel == '.' else rel.split(os.sep)[0].replace('\\', '/')
                hits.append((os.path.join(root, name), first))
    return hits


def _read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''


def _cli_main(argv=None):
    parser = argparse.ArgumentParser(
        description='核对任务记忆文件的主分类落点（只读，不做任何写入）')
    parser.add_argument('--task', required=True, help='任务名（仅 [a-z0-9_]+）')
    parser.add_argument('--docs-dir', default=None, help='显式指定主 docs（默认走 marker）')
    parser.add_argument('--dry-run', action='store_true',
                        help='只打印，不落盘（本命令本就只读，保留以对齐验收命令）')
    args = parser.parse_args(argv)

    if not TASK_NAME_RE.match(args.task):
        sys.stderr.write('错误：非法任务名 "%s"（仅允许 [a-z0-9_]+）\n' % args.task)
        return 2

    try:
        import tidy_common
        docs = tidy_common.resolve_primary_docs(args.docs_dir)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write('错误：解析主 docs 失败: %s\n' % exc)
        return 2
    if not docs or not os.path.isdir(docs):
        sys.stderr.write('错误：未解析到主 docs 目录（可传 --docs-dir）\n')
        return 2

    memory_root = os.path.join(docs, 'memory_rj')
    if not os.path.isdir(memory_root):
        sys.stderr.write('错误：memory_rj 不存在: %s\n' % memory_root)
        return 2

    entries = _collect_task_memories(memory_root, args.task)
    print('## memory_tags 核对（task=%s）' % args.task)
    print('- memory_rj: %s' % memory_root)
    if not entries:
        print('- 0 个记忆文件（该任务尚无记忆）')
        return 0

    illegal = []
    mismatch = []
    print('\n| 文件 | 目录分类 | 推断分类 | 一致 |')
    print('|---|---|---|---|')
    for path, dir_class in entries:
        rel = os.path.relpath(path, memory_root).replace('\\', '/')
        inferred = infer_memory_class(_read_text(path))
        if dir_class and dir_class not in MEMORY_TAGS:
            illegal.append((rel, dir_class))
            flag = '目录非法'
        elif not dir_class:
            flag = '遗留平铺'
        elif dir_class == inferred:
            flag = '是'
        else:
            flag = '否'
            mismatch.append((rel, dir_class, inferred))
        print('| %s | %s | %s | %s |' % (rel, dir_class or '(平铺)', inferred, flag))

    print('\n## 小结')
    print('- 文件 %d / 非法目录 %d / 分类不一致 %d'
          % (len(entries), len(illegal), len(mismatch)))
    for rel, dir_class in illegal:
        print('  [非法] %s → 目录 "%s" 不在 %s'
              % (rel, dir_class, ', '.join(MEMORY_TAGS)))
    for rel, dir_class, inferred in mismatch:
        print('  [提示] %s → 目录 %s，内容更像 %s（仅提示，不改文件）'
              % (rel, dir_class, inferred))
    if illegal:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(_cli_main())
