#!/usr/bin/env python3
"""R4-1 deterministic expression clarity tests."""

import unittest
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import yotta_resume as yr  # noqa: E402


class ClarityReviewTest(unittest.TestCase):
    def test_unverifiable_result_creates_confirmation_question(self):
        resume = """# 张三

## 工作经历
### 某科技公司 | 后端工程师 | 2023.01 - 2025.01
- 负责核心服务性能优化，显著提升系统稳定性，效果良好。
"""
        review = yr.audit_resume(resume)["clarity_review"]
        codes = {item["code"] for item in review["signals"]}
        self.assertIn("unverifiable_result", codes)
        questions = " ".join(item["question"] for item in review["questions"])
        self.assertIn("基线", questions)
        self.assertIn("验证", questions)
        self.assertEqual(review["status"], "attention")

    def test_quantified_result_is_not_flagged_as_unverifiable(self):
        resume = """# 李四

## 工作经历
### 某科技公司 | 后端工程师 | 2023.01 - 2025.01
- 主导订单接口优化，覆盖 12 个服务，将平均响应时间从 320ms 降到 180ms，
  抽样验证 2000 次请求，故障率下降 35%。

## 技能
Java, Spring, PostgreSQL
"""
        review = yr.audit_resume(resume)["clarity_review"]
        codes = {item["code"] for item in review["signals"]}
        self.assertNotIn("unverifiable_result", codes)
        self.assertEqual(review["status"], "clear")
        self.assertFalse(review["questions"])

    def test_skill_level_without_project_evidence_is_flagged(self):
        resume = """# 王五

## 技能
- 精通 Rust，熟悉分布式系统。
"""
        review = yr.audit_resume(resume)["clarity_review"]
        codes = {item["code"] for item in review["signals"]}
        self.assertIn("unsupported_skill_level", codes)
        questions = " ".join(item["question"] for item in review["questions"])
        self.assertIn("项目", questions)
        self.assertIn("证据", questions)

    def test_unclear_responsibility_is_flagged(self):
        resume = """# 赵六

## 工作经历
### 某公司 | 项目成员 | 2023.01 - 2025.01
- 参与跨部门交付项目，配合完成需求整理和上线。
"""
        review = yr.audit_resume(resume)["clarity_review"]
        codes = {item["code"] for item in review["signals"]}
        self.assertIn("unclear_responsibility", codes)
        questions = " ".join(item["question"] for item in review["questions"])
        self.assertIn("独立负责", questions)
        self.assertIn("牵头", questions)
        self.assertIn("参与", questions)

    def test_clarity_review_has_deterministic_boundary_and_markdown(self):
        resume = """# 钱七

## 工作经历
- 优化业务流程，取得良好效果。
"""
        report = yr.audit_resume(resume)
        review = report["clarity_review"]
        self.assertIn("固定规则", review["limitations"])
        self.assertNotIn("clarity_score", review)
        markdown = yr.render_audit_markdown(report)
        self.assertIn("## 表达清晰度", markdown)
        self.assertIn("固定规则", markdown)


if __name__ == "__main__":
    unittest.main()
