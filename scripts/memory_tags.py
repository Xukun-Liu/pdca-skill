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
INFER_RULES = {
    "pitfall": ["踩坑", "报错", "失败", "异常", "rollback", "回滚", "bug", "修不好", "拦截"],
    "tech_solution": ["方案", "架构", "实现", "部署", "设计", "改造", "重构", "技术路线", "接口"],
    "status": ["完成", "进度", "状态", "交接", "收尾", "阶段", "汇总", "巡检", "周期"],
    "decision": ["决策", "拍板", "选择", "取舍", "确认了", "选定", "评审通过"],
    "tool_usage": ["工具", "命令", "脚本", "用法", "安装", "配置", "参数", "CLI"],
    # workflow 不设关键词：默认兜底
}


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
    # 按 TAG_PRIORITY 顺序取第一个命中的
    for tag in TAG_PRIORITY:
        if tag in hits:
            return tag
    return FALLBACK_TAG
