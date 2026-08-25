"""v1.0.4 50 轮全流程测试（T008 机械层）：四类任务 × 记忆数据流全链路。

每轮：write_project(类型化内容) → 断言正文落预期标签文件夹 + memory_main 索引行
含元数据 + expand_index_lines 展开 + distill 可解析。汇报类轮次额外断言
leader_report.md 六段结构。统计推断误判率（spec 未验证假设①：<30%）。

对话层抽样（/plan 读新结构记忆、/act 互动复盘行为）由 subagent 真实模拟，
报告落 docs_rj/check_rj/v104_memory_tag_act_report_test50_*.md。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import memory_shadow_write as msw  # noqa: E402
from memory_distill import expand_index_lines, parse_memory_entries  # noqa: E402

# 50 轮任务矩阵：技术修复 15 / 写作 10 / 发布 10 / 巡检 10 / 汇报 5
# (轮次, 任务类型, task名, 内容, 预期主分类)
ROUNDS = []


def _mk(round_no, kind, task, content, expected):
    ROUNDS.append((round_no, kind, task, content, expected))


# 技术修复 ×15（pitfall/tech_solution 混合）
_tech = [
    ("修复登录超时报错，根因是连接池未释放，回滚旧版后改用重试机制", "pitfall"),
    ("分层架构设计方案：接入层/服务层/存储层三段拆分，接口契约先行", "tech_solution"),
    ("踩坑记录：沙箱拦截 tempfile.mkstemp，改用 open() 直写绕过", "pitfall"),
    ("重构数据访问层：引入仓储模式，部署脚本同步更新", "tech_solution"),
    ("线上 500 报错排查：异常未捕获导致，修复方案是加兜底 try", "pitfall"),
    ("缓存穿透实现方案：布隆过滤器 + 空值缓存双层设计", "tech_solution"),
    ("bug 复盘：并发写锁竞争导致数据丢失，回滚加锁粒度", "pitfall"),
    ("接口幂等性设计：token 机制 + 去重表实现", "tech_solution"),
    ("部署失败的坑：镜像里缺 so 库，改成多阶段构建", "pitfall"),
    ("数据库分库分表技术方案落地：按用户 ID 哈希 16 库", "tech_solution"),
    ("修不好的诡异 bug：最终定位是时区配置，rollback 后统一 UTC", "pitfall"),
    ("消息队列削峰架构设计，接口层限流配合", "tech_solution"),
    ("失败经验：直接改线上配置没备份，回滚耗时 3 小时", "pitfall"),
    ("重构完成：CLI 参数解析改 argparse，实现向后兼容", "tech_solution"),
    ("报错堆栈太深难定位的坑：加了链路追踪后秒查", "pitfall"),
]
for i, (c, e) in enumerate(_tech, 1):
    _mk(i, "技术修复", "tech_task_%02d" % i, c, e)

# 写作 ×10（workflow 兜底为主 + 少量 decision）
_writing = [
    ("知乎长文初稿：从 0 到 1 搭建个人知识库的完整路径分享", "workflow"),
    ("公众号推文改写：把技术干货转成大白话，活人感文风调整", "workflow"),
    ("标题二选一拍板：选悬念式不选数字式，CTR 预期更高", "decision"),
    ("人物稿采访提纲：20 个问题按时间线组织", "workflow"),
    ("小说第三章重写：视角从第一人称改第三人称的取舍", "decision"),
    ("口播稿压缩：5 分钟版砍到 3 分钟，保留三个钩子", "workflow"),
    ("博客技术文写作：给零基础读者的入门系列规划", "workflow"),
    ("故事结构选定：三幕式，不选非线性叙事", "decision"),
    ("演讲稿开场打磨：用个人踩坑经历做开场白", "workflow"),
    ("去 AI 味改稿：删掉所有'首先其次最后'式套话", "workflow"),
]
for i, (c, e) in enumerate(_writing, 16):
    _mk(i, "写作", "writing_task_%02d" % i, c, e)

# 发布 ×10（workflow/decision/pitfall 混合）
_release = [
    ("v1.0.4 打包发布：package_skill 排除用户数据目录，验证 zip 结构", "workflow"),
    ("发布清单确认：CHANGELOG/版本徽章/README 三处同步检查", "workflow"),
    ("发布窗口拍板：选周五晚低峰，不选周中", "decision"),
    ("zip 体积超标的坑：PNG 资源没压缩，加打包前压缩步骤", "pitfall"),
    ("skillhub 上传流程：后台表单逐项填写指南记录", "workflow"),
    ("版本号回退事故复盘：tag 打错后删 tag 重打的坑", "pitfall"),
    ("gitee 与 github 双平台同步发布流程固化", "workflow"),
    ("发布前决策：LICENSE 沿用非商用条款不改", "decision"),
    ("发布后回滚预案：保留上一版 zip 供快速回退", "workflow"),
    ("CHANGELOG 编写规范沉淀：按用户可感知变化分组", "workflow"),
]
for i, (c, e) in enumerate(_release, 26):
    _mk(i, "发布", "release_task_%02d" % i, c, e)

# 巡检 ×10（status 为主）
_ops = [
    ("每周 GitHub 开源贡献巡检：PR/issue 状态逐项核对，本周无变动", "status"),
    ("巡检报告：服务器磁盘使用率 62%，环比 +3%", "status"),
    ("任务完成总结：v1.0.4 三痛点改造全部收尾，里程碑达成", "status"),
    ("周期性依赖检查：3 个依赖有新版本，暂不升级", "status"),
    ("进度更新：50 轮测试完成 40 轮，剩余按批次推进", "status"),
    ("交接准备：当前任务状态与待办梳理，收尾动作清单", "status"),
    ("周报汇总：本周完成记忆系统改造，下周启动汇报模块", "status"),
    ("巡检异常：某任务状态字段缺失，已补录", "status"),
    ("里程碑确认：阶段验收通过，进入下一阶段", "status"),
    ("定期备份检查：最近一次全量备份 3 天前，正常", "status"),
]
for i, (c, e) in enumerate(_ops, 36):
    _mk(i, "巡检", "ops_task_%02d" % i, c, e)

# 汇报 ×5（leader_report 六段结构断言 + status/workflow 归类）
_report = [
    ("给领导的周报：一句话结论先行，进展/数据/风险/计划/求助六段齐备", "workflow"),
    ("月度汇报材料：核心指标对比表 + 下一步计划两页", "status"),
    ("项目里程碑汇报：上线完成，风险项清零", "status"),
    ("向上汇报：资源不足需协调，明确到需要谁做什么", "workflow"),
    ("季度汇报文档：数据成果环比表 + 需要的支持清单", "status"),
]
for i, (c, e) in enumerate(_report, 46):
    _mk(i, "汇报", "report_task_%02d" % i, c, e)

assert len(ROUNDS) == 50, "测试矩阵必须 50 轮，当前 %d" % len(ROUNDS)

LEADER_REPORT_PATH = os.path.join(os.path.dirname(__file__), "..",
                                  "references", "common", "da", "leader_report.md")


@pytest.fixture
def iso50(tmp_path, monkeypatch):
    """隔离环境：全局 memory + 项目 memory_rj 均指 tmp，schema=v1.0.4 已迁移。"""
    tmp_memory = tmp_path / "memory_main.md"
    tmp_memory.write_text("# 主记忆\n\n", encoding="utf-8")
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_FILE", str(tmp_memory))
    monkeypatch.setattr(msw, "GLOBAL_MEMORY_DIR", str(tmp_path))
    monkeypatch.setattr(
        msw, "_GLOBAL_CP_LOCK", msw._CrossProcessLock(str(tmp_memory)))
    monkeypatch.setattr(msw, "check_schema_version", lambda: True)
    proj_dir = tmp_path / "memory_rj"
    proj_dir.mkdir()
    return {"memory": tmp_memory, "proj": proj_dir}


@pytest.mark.parametrize("round_no,kind,task,content,expected", ROUNDS,
                         ids=["r%02d_%s" % (r[0], r[1]) for r in ROUNDS])
def test_round(round_no, kind, task, content, expected, iso50):
    """单轮全链路：写入 → 标签文件夹 → 索引行元数据 → 展开可解析。"""
    result = msw.write_project(
        task=task, content=content,
        project_memory_dir=str(iso50["proj"]),
        project_name="proj_50r",
        memory_class=None,  # 不传：测启发式推断（误判率统计依据）
    )
    inferred = result["memory_class"]
    # 落点断言：正文文件存在于 {inferred}/{YYYYMM}/ 深层
    files = list(iso50["proj"].rglob("%s_memory_*.md" % task))
    assert len(files) == 1, "第 %d 轮正文应恰好 1 个文件" % round_no
    assert files[0].parent.parent.name == inferred, \
        "第 %d 轮落点文件夹 %s != 推断 %s" % (round_no, files[0].parent.parent.name, inferred)
    # 索引行断言：含 task/inferred/is_lesson/正文链接
    g = iso50["memory"].read_text(encoding="utf-8")
    idx = [l for l in g.split("\n") if "| %s |" % task in l]
    assert len(idx) == 1, "第 %d 轮应有 1 行索引" % round_no
    assert "| %s |" % inferred in idx[0]
    assert "[正文](file:///" in idx[0]
    # 展开断言：expand 后条目可被 parse 解析（distill 数据链通）
    expanded = expand_index_lines(g)
    entries = parse_memory_entries(expanded, "proj_50r")
    hit = [e for e in entries if e["task"] == task]
    assert len(hit) == 1, "第 %d 轮展开后应解析到条目" % round_no


def test_misjudgment_rate(iso50):
    """启发式误判率 <30%（spec 未验证假设①）。显式跑 50 轮统计推断 vs 预期。"""
    mismatches = []
    for round_no, kind, task, content, expected in ROUNDS:
        inferred = msw.write_project(
            task=task, content=content,
            project_memory_dir=str(iso50["proj"]),
            project_name="proj_50r")["memory_class"]
        if inferred != expected:
            mismatches.append((round_no, kind, expected, inferred))
    rate = len(mismatches) / len(ROUNDS)
    # 误判不丢数据（只影响文件夹位置），阈值 30%；超过则 spec 假设①不成立需升级人工规则
    assert rate < 0.30, "误判率 %.0f%% ≥30%%：%s" % (rate * 100, mismatches)


def test_leader_report_six_sections():
    """汇报类检查：leader_report.md 含六段结构模板（AC-011 补充，5 轮汇报的文档依据）。"""
    with open(LEADER_REPORT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    for section in ["一句话结论", "进展", "数据成果", "风险与问题", "下一步计划", "需要的支持"]:
        assert section in content, "leader_report 缺段：%s" % section
