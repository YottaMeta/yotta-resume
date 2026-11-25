#!/usr/bin/env python3
"""Regression tests for the user package and source-only maintenance surface."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
sys.path.insert(0, str(HERE))

import yotta_resume as yr  # noqa: E402


USER_COMMANDS = {
    "audit",
    "export",
    "interview",
    "contracts",
    "doctor",
    "quickstart",
    "selftest",
}
MAINTENANCE_COMMANDS = {"sources", "bank"}


class ReleaseSurfaceTest(unittest.TestCase):
    def test_user_cli_exposes_only_user_commands(self):
        parser = yr.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if action.__class__.__name__ == "_SubParsersAction"
        )

        self.assertEqual(set(subparsers.choices), USER_COMMANDS)
        self.assertFalse(MAINTENANCE_COMMANDS & set(subparsers.choices))

    def test_npm_package_has_no_network_maintenance_surface(self):
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        self.assertTrue(npm, "npm executable not found")
        completed = subprocess.run(
            [npm, "pack", "--dry-run", "--json", "--ignore-scripts"],
            cwd=str(SKILL_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        package = payload[0] if isinstance(payload, list) else next(iter(payload.values()))
        files = {item["path"] for item in package["files"]}

        self.assertNotIn("scripts/source_watch.py", files)
        self.assertNotIn("scripts/bank_pipeline.py", files)
        self.assertNotIn("references/source-updates.md", files)
        for relative in sorted(path for path in files if path.endswith(".py")):
            text = (SKILL_DIR / relative).read_text(encoding="utf-8")
            self.assertNotIn("urllib.request", text, relative)

    def test_source_maintenance_cli_remains_available(self):
        script = (
            SKILL_DIR
            / "tools"
            / "resume_maintenance"
            / "yotta_resume_maintenance.py"
        )
        self.assertTrue(script.is_file(), "source maintenance CLI is missing")
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=str(SKILL_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for command in sorted(MAINTENANCE_COMMANDS):
            self.assertIn(command, completed.stdout)

    def test_source_installer_omits_maintenance_tools(self):
        node = shutil.which("node")
        self.assertTrue(node, "node executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-install-") as temp:
            target_root = Path(temp) / "skill"
            completed = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--dir",
                    str(target_root),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            installed = target_root / "yotta-resume"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertFalse((installed / "tools").exists())
            self.assertFalse((installed / "scripts" / "source_watch.py").exists())
            self.assertFalse((installed / "scripts" / "bank_pipeline.py").exists())

    def test_all_npx_install_examples_use_an_exact_version(self):
        version = json.loads(
            (SKILL_DIR / "package.json").read_text(encoding="utf-8")
        )["version"]
        for name in ("README.md", "README.zh-CN.md", "bin/install.js"):
            text = (SKILL_DIR / name).read_text(encoding="utf-8")
            self.assertNotRegex(
                text,
                r"npx\s+-y\s+@yottameta/yotta-resume(?!@)",
                name,
            )
            self.assertIn(
                "npx -y @yottameta/yotta-resume@{}".format(version),
                text,
                name,
            )

    def test_skill_declares_minimal_tools_and_installer_boundary(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"(?m)^allowed-tools:\s*Read,\s*Write,\s*Bash\s*$",
        )
        self.assertIn("安装器权限与边界", text)
        self.assertIn("复制到用户指定的智能体技能目录", text)
        self.assertIn("只在目标 `yotta-resume` 目录内", text)


if __name__ == "__main__":
    unittest.main()
