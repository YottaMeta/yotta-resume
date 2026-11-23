#!/usr/bin/env python3
"""R4-1 tests for non-security role depth and quickstart action packs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
CLI = HERE / "yotta_resume.py"
TODAY = "2026-11-24"
sys.path.insert(0, str(HERE))

import interview_engine as ie  # noqa: E402
import yotta_resume as yr  # noqa: E402
from contract_validate import validate_contracts  # noqa: E402


SOFTWARE_RESUME = """# 王五
13800138000 | wangwu@example.com

## 工作经历
### 示例科技 | 后端工程师 | 2023.01 - 2026.01
- 使用 TypeScript、Node.js 和 PostgreSQL 开发订单服务。
- 负责 REST API、单元测试和 CI/CD 流水线。
- 将接口平均响应时间从 320ms 降到 180ms，覆盖 12 个服务。

## 技能
TypeScript, Node.js, PostgreSQL, Docker, CI/CD
"""

DATA_RESUME = """# 李四

## 工作经历
### 示例数据团队 | 算法工程师 | 2023.01 - 2026.01
- 使用 PyTorch 和 Pandas 构建机器学习模型，覆盖 80 万条脱敏训练样本。
- 设计离线评估和线上监控，将模型 F1 从 0.72 提升到 0.79。
- 参与 RAG 检索质量评估，建立 300 条人工复核集。

## 技能
Python, PyTorch, Pandas, 机器学习, RAG
"""

BUSINESS_RESUME = """# 赵六

## 工作经历
### 示例科技 | 用户运营 | 2023.01 - 2026.01
- 负责 CRM 用户分层和站内活动运营，覆盖 20 万用户。
- 使用转化率和留存率评估活动，连续 6 周复盘渠道表现。
- 预算 30 万元，ROI 从 1.4 提升到 1.8。

## 技能
CRM, KPI, 用户增长, 活动运营, 转化率, 留存率
"""

JD = """岗位职责：
- 负责核心服务设计、质量验证和线上稳定性。
- 参与性能优化、监控和故障复盘。
"""


class IndustryDepthTest(unittest.TestCase):
    def test_contracts_cover_ten_roles_and_270_questions(self):
        report = validate_contracts(today=TODAY)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["role_family_count"], 10)
        self.assertEqual(report["question_count"], 270)
        role_map = json.loads(
            (SKILL_DIR / "data" / "security-role-map.json").read_text(
                encoding="utf-8"
            )
        )
        roles = {item["id"] for item in role_map["role_families"]}
        self.assertTrue({
            "software_engineering",
            "data_ai",
            "business_operations",
        }.issubset(roles))

    def test_question_bank_has_ten_roles_each_with_27_unique_questions(self):
        bank = json.loads(
            (SKILL_DIR / "data" / "question-bank.json").read_text(
                encoding="utf-8"
            )
        )
        questions = bank["questions"]
        self.assertEqual(len(questions), 270)
        self.assertEqual(len({item["question_id"] for item in questions}), 270)
        self.assertEqual(len({item["prompt"] for item in questions}), 270)
        counts = {
            role: sum(
                1 for item in questions
                if item["role_family"] == role
            )
            for role in {
                item["role_family"] for item in questions
            }
        }
        self.assertEqual(
            counts,
            {
                "soc": 27,
                "incident_response": 27,
                "offensive_security": 27,
                "appsec": 27,
                "security_engineering": 27,
                "grc_data_security": 27,
                "generic": 27,
                "software_engineering": 27,
                "data_ai": 27,
                "business_operations": 27,
            },
        )

    def test_industry_registry_maps_three_non_security_roles(self):
        registry = json.loads(
            (SKILL_DIR / "data" / "industry-registry.json").read_text(
                encoding="utf-8"
            )
        )
        industries = {item["id"]: item for item in registry["industries"]}
        for industry_id in (
            "software_engineering",
            "data_ai",
            "business_operations",
        ):
            self.assertEqual(
                industries[industry_id]["role_map_ref"],
                "security-role-map.json",
            )

    def test_interview_uses_industry_role_instead_of_generic(self):
        cases = (
            (SOFTWARE_RESUME, "software_engineering"),
            (DATA_RESUME, "data_ai"),
            (BUSINESS_RESUME, "business_operations"),
        )
        for resume, expected_role in cases:
            with self.subTest(role=expected_role):
                report = yr.audit_resume(resume, JD)
                session = ie.build_session(
                    resume,
                    JD,
                    report,
                    count=3,
                    seed="r4-industry",
                    today=TODAY,
                    now="2026-11-24T08:00:00Z",
                )
                self.assertEqual(
                    session["inputs"]["role_family"],
                    expected_role,
                )
                self.assertEqual(
                    session["inputs"]["role_source"],
                    "industry_mapping",
                )
                self.assertEqual(
                    {item["role_family"] for item in session["questions"]},
                    {expected_role},
                )

    def test_ambiguous_industry_still_requires_confirmation(self):
        resume = "# 张三\n## 技能\nReact, SIEM\n"
        report = yr.audit_resume(resume)
        with self.assertRaises(ie.InterviewError):
            ie.build_session(
                resume,
                "",
                report,
                count=3,
                seed="ambiguous",
                today=TODAY,
                now="2026-11-24T08:01:00Z",
            )


class QuickstartActionPackTest(unittest.TestCase):
    def run_cli(self, argv):
        return subprocess.run(
            [sys.executable, str(CLI), *argv],
            cwd=str(SKILL_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_quickstart_creates_single_entry_action_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resume = root / "resume.md"
            jd = root / "jd.txt"
            out_dir = root / "action-pack"
            resume.write_text(SOFTWARE_RESUME, encoding="utf-8")
            jd.write_text(JD, encoding="utf-8")
            completed = self.run_cli([
                "quickstart",
                "--resume",
                str(resume),
                "--jd",
                str(jd),
                "--out-dir",
                str(out_dir),
                "--format",
                "json",
                "--today",
                TODAY,
            ])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            action_pack = payload["action_pack"]
            self.assertEqual(action_pack["status"], "created")
            self.assertEqual(
                action_pack["industry"],
                "software_engineering",
            )
            files = {item["name"]: item for item in action_pack["files"]}
            self.assertEqual(
                set(files),
                {"action-plan.md", "audit-report.md", "action-pack.json"},
            )
            for item in files.values():
                target = Path(item["path"])
                self.assertTrue(target.is_file())
                self.assertTrue(item["sha256"])

            combined = "\n".join(
                Path(item["path"]).read_text(encoding="utf-8")
                for item in files.values()
            )
            self.assertNotIn("13800138000", combined)
            self.assertNotIn("wangwu@example.com", combined)
            self.assertIn("软件研发", combined)
            self.assertIn("下一步", combined)
            self.assertFalse(any(
                "python scripts/" in item
                for item in payload["next_steps"]
            ))
            self.assertTrue(payload["advanced_commands"])

    def test_quickstart_refuses_non_empty_action_pack_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resume = root / "resume.md"
            out_dir = root / "action-pack"
            out_dir.mkdir()
            (out_dir / "existing.txt").write_text("keep", encoding="utf-8")
            resume.write_text(SOFTWARE_RESUME, encoding="utf-8")
            completed = self.run_cli([
                "quickstart",
                "--resume",
                str(resume),
                "--out-dir",
                str(out_dir),
                "--format",
                "json",
                "--today",
                TODAY,
            ])
            self.assertEqual(completed.returncode, 2)
            self.assertIn("YRS-EXPORT-003", completed.stderr)
            self.assertEqual(
                (out_dir / "existing.txt").read_text(encoding="utf-8"),
                "keep",
            )


if __name__ == "__main__":
    unittest.main()
