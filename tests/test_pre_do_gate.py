#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_pre_do_gate.py - /do 文档门禁单元测试（v1.3.0）。

覆盖：
- test_full_pass: spec + task 齐全 → 退码 0
- test_missing_spec: 没有 spec → 退码 1
- test_missing_task: 有 spec 没 task → 退码 2
- test_lite_pass: --lite 且 lite spec 有 3 行 → 退码 0（不要求 task）
- test_lite_empty_spec: --lite 但 spec 不足 3 行 → 退码 1
- test_exempt_pass: --exempt 直接放行 → 退码 0
- test_docs_dir_missing: 指定不存在的 docs 目录 → 退码 3
- test_bad_task_name: 任务名非法 → 退码 3
"""

import os
import shutil
import sys
import tempfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))

from pre_do_gate import main  # noqa: E402


def _build(tmpdir, spec_lines=None, with_task=False):
    """构造 docs 骨架；spec_lines=None 表示不建 spec。"""
    docs = os.path.join(tmpdir, "docs_rj")
    for sub in ("spec_rj", "task_rj"):
        os.makedirs(os.path.join(docs, sub), exist_ok=True)
    if spec_lines is not None:
        path = os.path.join(docs, "spec_rj", "demo_spec_20261105_1200.md")
        with open(path, "w", encoding="utf-8") as handle:
            for i in range(spec_lines):
                handle.write("第%d行\n" % (i + 1))
    if with_task:
        path = os.path.join(docs, "task_rj", "demo_task_20261105_1200.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# task\n")
    return docs


def test_full_pass():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=5, with_task=True)
        assert main(["--task", "demo", "--docs-dir", docs]) == 0
    finally:
        shutil.rmtree(tmpdir)


def test_missing_spec():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=None, with_task=True)
        assert main(["--task", "demo", "--docs-dir", docs]) == 1
    finally:
        shutil.rmtree(tmpdir)


def test_missing_task():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=5, with_task=False)
        assert main(["--task", "demo", "--docs-dir", docs]) == 2
    finally:
        shutil.rmtree(tmpdir)


def test_lite_pass():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=3, with_task=False)
        assert main(["--task", "demo", "--docs-dir", docs, "--lite"]) == 0
    finally:
        shutil.rmtree(tmpdir)


def test_lite_empty_spec():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=1, with_task=False)
        assert main(["--task", "demo", "--docs-dir", docs, "--lite"]) == 1
    finally:
        shutil.rmtree(tmpdir)


def test_exempt_pass():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=None, with_task=False)
        code = main(["--task", "demo", "--docs-dir", docs,
                     "--exempt", "--reason", "写公众号文章"])
        assert code == 0
    finally:
        shutil.rmtree(tmpdir)


def test_docs_dir_missing():
    tmpdir = tempfile.mkdtemp()
    try:
        missing = os.path.join(tmpdir, "not_exist")
        assert main(["--task", "demo", "--docs-dir", missing]) == 3
    finally:
        shutil.rmtree(tmpdir)


def test_bad_task_name():
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=5, with_task=True)
        assert main(["--task", "Bad-Task", "--docs-dir", docs]) == 3
    finally:
        shutil.rmtree(tmpdir)


def test_prefixed_naming_pass():
    """真实仓库用的是 20261105_1026_pdca-skill_spec_{task}.md 这种带前缀命名。"""
    tmpdir = tempfile.mkdtemp()
    try:
        docs = _build(tmpdir, spec_lines=None, with_task=False)
        spec = os.path.join(docs, "spec_rj",
                            "20261105_1026_pdca-skill_spec_gate_demo.md")
        with open(spec, "w", encoding="utf-8") as handle:
            handle.write("# spec\n")
        assert main(["--task", "gate_demo", "--docs-dir", docs]) == 2
    finally:
        shutil.rmtree(tmpdir)