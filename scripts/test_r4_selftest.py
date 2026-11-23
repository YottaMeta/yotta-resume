#!/usr/bin/env python3
"""R4-1 regression tests for package selftest and stable error codes."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
CLI = HERE / "yotta_resume.py"
TODAY = "2026-11-24"
sys.path.insert(0, str(HERE))

import yotta_resume as yr  # noqa: E402


class SelftestEngineTest(unittest.TestCase):
    def test_quick_selftest_runs_core_checks_without_user_input(self):
        report = yr.run_selftest(mode="quick", today=TODAY)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mode"], "quick")
        self.assertTrue(report["schema_version"])
        checks = {item["id"]: item for item in report["checks"]}
        for check_id in (
            "contracts",
            "audit_analysis",
            "interview_roundtrip",
            "export_docx_html",
            "export_rollback",
            "temp_cleanup",
        ):
            self.assertIn(check_id, checks)
            self.assertIn(checks[check_id]["status"], ("PASS", "WARN"))
        self.assertEqual(checks["contracts"]["status"], "PASS")
        self.assertEqual(checks["audit_analysis"]["status"], "PASS")
        self.assertEqual(checks["interview_roundtrip"]["status"], "PASS")
        self.assertTrue(report["summary"]["check_count"] >= 6)

    def test_quick_selftest_validates_expanded_question_bank(self):
        report = yr.run_selftest(mode="quick", today=TODAY)
        contracts = next(
            item for item in report["checks"] if item["id"] == "contracts"
        )
        self.assertEqual(contracts["status"], "PASS")
        self.assertIn("15", contracts["message"])

    def test_full_selftest_reports_missing_pdf_browser_as_warn(self):
        original = yr.find_pdf_browser
        try:
            yr.find_pdf_browser = lambda: None
            report = yr.run_selftest(mode="full", today=TODAY)
        finally:
            yr.find_pdf_browser = original
        checks = {item["id"]: item for item in report["checks"]}
        self.assertIn("pdf_export", checks)
        self.assertEqual(checks["pdf_export"]["status"], "WARN")
        self.assertEqual(checks["pdf_export"]["code"], "YRS-PDF-001")
        self.assertTrue(checks["pdf_export"]["impact"])
        self.assertTrue(checks["pdf_export"]["next_action"])
        self.assertTrue(report["warnings"])

    def test_selftest_invalid_contracts_fail_with_stable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            root.mkdir()
            for source in (SKILL_DIR / "data").glob("*.json"):
                (root / source.name).write_bytes(source.read_bytes())
            (root / "question-bank.json").write_text("{}", encoding="utf-8")
            report = yr.run_selftest(mode="quick", root=root, today=TODAY)
        self.assertFalse(report["ok"])
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["contracts"]["status"], "FAIL")
        self.assertEqual(checks["contracts"]["code"], "YRS-DATA-001")
        self.assertTrue(checks["contracts"]["impact"])
        self.assertTrue(checks["contracts"]["next_action"])


class SelftestCliTest(unittest.TestCase):
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

    def test_quick_selftest_json_cli(self):
        completed = self.run_cli([
            "selftest",
            "--quick",
            "--json",
            "--today",
            TODAY,
        ])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "quick")
        self.assertTrue(payload["checks"])

    def test_selftest_failure_returns_six(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            root.mkdir()
            completed = self.run_cli([
                "selftest",
                "--quick",
                "--json",
                "--root",
                str(root),
                "--today",
                TODAY,
            ])
        self.assertEqual(completed.returncode, 6)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn(
            "YRS-DATA-001",
            {item.get("code") for item in payload["checks"]},
        )


class StableErrorCodeTest(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stderr(err):
            code = yr.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_missing_resume_has_code_impact_and_next_action(self):
        code, _, err = self.run_cli([
            "audit",
            "--resume",
            "no-such-resume.md",
            "--format",
            "json",
        ])
        self.assertEqual(code, 3)
        self.assertIn("YRS-INPUT-001", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)

    def test_unsupported_doc_has_code_impact_and_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.doc"
            source.write_bytes(b"\xd0\xcf\x11\xe0legacy")
            code, _, err = self.run_cli([
                "audit",
                "--resume",
                str(source),
                "--format",
                "json",
            ])
        self.assertEqual(code, 5)
        self.assertIn("YRS-INPUT-003", err)
        self.assertIn("--resume-text", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)

    def test_malformed_pdf_has_stable_input_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "broken.pdf"
            source.write_bytes(b"%PDF-1.4\nnot a real pdf\n")
            code, _, err = self.run_cli([
                "audit",
                "--resume",
                str(source),
                "--format",
                "json",
            ])
        self.assertEqual(code, 5)
        self.assertIn("YRS-INPUT-002", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)

    def test_export_without_targets_has_stable_export_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "resume.md"
            source.write_text("# 张三\n", encoding="utf-8")
            code, _, err = self.run_cli([
                "export",
                "--input",
                str(source),
            ])
        self.assertEqual(code, 2)
        self.assertIn("YRS-EXPORT-001", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)

    def test_quickstart_missing_resume_has_stable_input_error(self):
        code, _, err = self.run_cli([
            "quickstart",
            "--resume",
            "no-such-resume.md",
        ])
        self.assertEqual(code, 3)
        self.assertIn("YRS-INPUT-001", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)

    def test_existing_interview_session_has_stable_conflict_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session.json"
            session.write_text("{}", encoding="utf-8")
            code, _, err = self.run_cli([
                "interview",
                "start",
                "--resume",
                "no-such-resume.md",
                "--session",
                str(session),
            ])
        self.assertEqual(code, 2)
        self.assertIn("YRS-INTERVIEW-002", err)
        self.assertIn("影响：", err)
        self.assertIn("下一步：", err)


if __name__ == "__main__":
    unittest.main()
