#!/usr/bin/env python3
"""Regression tests for the user package and source-only maintenance surface."""

import json
import hashlib
import os
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


def _snapshot_tree(root):
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return snapshot


def _normalize_path_text(value):
    return str(value).replace("\\", "/").lower()


def _make_directory_link(target, link):
    if os.name == "nt":
        node = shutil.which("node")
        if not node:
            raise RuntimeError("node executable not found")
        script = "require('fs').symlinkSync({}, {}, 'junction')".format(
            json.dumps(str(target)),
            json.dumps(str(link)),
        )
        completed = subprocess.run(
            [node, "-e", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr)
        return
    link.symlink_to(target, target_is_directory=True)


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

    def test_npx_mentions_are_limited_to_pinned_install_commands(self):
        version = json.loads(
            (SKILL_DIR / "package.json").read_text(encoding="utf-8")
        )["version"]
        allowed = "npx -y @yottameta/yotta-resume@" + version
        for name in ("README.md", "README.zh-CN.md", "bin/install.js"):
            text = (SKILL_DIR / name).read_text(encoding="utf-8")
            mentions = re.findall(r"npx(?!\s+-y\s+@yottameta/yotta-resume@\d+\.\d+\.\d+)", text)
            self.assertEqual([], mentions, name)
            for line in text.splitlines():
                if "npx" in line:
                    self.assertIn(allowed, line, name)

    def test_skill_declares_minimal_tools_and_installer_boundary(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"(?m)^allowed-tools:\s*Read,\s*Write,\s*Bash\s*$",
        )
        self.assertIn("安装器权限与边界", text)
        self.assertIn("复制到用户指定的智能体技能目录", text)
        self.assertIn("只在目标 `yotta-resume` 目录内", text)

    def test_javascript_installer_rejects_fake_managed_hub_junction(self):
        node = shutil.which("node")
        self.assertTrue(node, "node executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-link-") as temp:
            root = Path(temp)
            install_root = root / "install"
            victim_root = root / "victim"
            victim_skill = victim_root / "yotta-resume"
            install_root.mkdir()
            victim_skill.mkdir(parents=True)
            (victim_root / ".yotta-hub.json").write_text(
                '{"standard":"forged"}\n',
                encoding="utf-8",
            )
            (victim_skill / "SKILL.md").write_text("# forged\n", encoding="utf-8")
            (victim_skill / "package.json").write_text(
                '{"sentinel":"must-not-be-removed"}\n',
                encoding="utf-8",
            )
            (victim_skill / "outside.txt").write_text(
                "outside-target-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim_root)
            _make_directory_link(victim_skill, install_root / "yotta-resume")

            completed = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--dir",
                    str(install_root),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim_root))

    def test_javascript_installer_rejects_linked_install_root(self):
        node = shutil.which("node")
        self.assertTrue(node, "node executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-root-link-") as temp:
            root = Path(temp)
            install_root = root / "install-root"
            victim_root = root / "victim-root"
            victim_root.mkdir()
            (victim_root / "outside.txt").write_text(
                "outside-root-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim_root)
            _make_directory_link(victim_root, install_root)

            completed = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--dir",
                    str(install_root),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim_root))

    def test_javascript_installer_rejects_nested_link_in_target(self):
        node = shutil.which("node")
        self.assertTrue(node, "node executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-nested-link-") as temp:
            root = Path(temp)
            install_root = root / "install"
            target = install_root / "yotta-resume"
            victim = root / "victim-assets"
            target.mkdir(parents=True)
            victim.mkdir()
            (target / "SKILL.md").write_text("# existing\n", encoding="utf-8")
            (victim / "outside.txt").write_text(
                "outside-nested-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim)
            _make_directory_link(victim, target / "assets")

            completed = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--dir",
                    str(install_root),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim))

    def test_shell_installer_rejects_fake_managed_hub_junction(self):
        bash = shutil.which("bash")
        self.assertTrue(bash, "bash executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-sh-link-") as temp:
            root = Path(temp)
            install_root = root / "install"
            victim_root = root / "victim"
            victim_skill = victim_root / "yotta-resume"
            install_root.mkdir()
            victim_skill.mkdir(parents=True)
            (victim_root / ".yotta-hub.json").write_text(
                '{"standard":"forged"}\n',
                encoding="utf-8",
            )
            (victim_skill / "SKILL.md").write_text("# forged\n", encoding="utf-8")
            (victim_skill / "package.json").write_text(
                '{"sentinel":"must-not-be-removed"}\n',
                encoding="utf-8",
            )
            (victim_skill / "outside.txt").write_text(
                "outside-target-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim_root)
            _make_directory_link(victim_skill, install_root / "yotta-resume")

            completed = subprocess.run(
                [
                    bash,
                    str(SKILL_DIR / "install.sh").replace("\\", "/"),
                    "--dir",
                    str(install_root).replace("\\", "/"),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim_root))

    def test_shell_installer_rejects_linked_install_root(self):
        bash = shutil.which("bash")
        self.assertTrue(bash, "bash executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-sh-root-link-") as temp:
            root = Path(temp)
            install_root = root / "install-root"
            victim_root = root / "victim-root"
            victim_root.mkdir()
            (victim_root / "outside.txt").write_text(
                "outside-root-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim_root)
            _make_directory_link(victim_root, install_root)

            completed = subprocess.run(
                [
                    bash,
                    str(SKILL_DIR / "install.sh").replace("\\", "/"),
                    "--dir",
                    str(install_root).replace("\\", "/"),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim_root))

    def test_shell_installer_rejects_nested_link_in_target(self):
        bash = shutil.which("bash")
        self.assertTrue(bash, "bash executable not found")
        with tempfile.TemporaryDirectory(
            prefix="yotta-resume-sh-nested-link-"
        ) as temp:
            root = Path(temp)
            install_root = root / "install"
            target = install_root / "yotta-resume"
            victim = root / "victim-assets"
            target.mkdir(parents=True)
            victim.mkdir()
            (target / "SKILL.md").write_text("# existing\n", encoding="utf-8")
            (victim / "outside.txt").write_text(
                "outside-nested-sentinel\n",
                encoding="utf-8",
            )
            before = _snapshot_tree(victim)
            _make_directory_link(victim, target / "assets")

            completed = subprocess.run(
                [
                    bash,
                    str(SKILL_DIR / "install.sh").replace("\\", "/"),
                    "--dir",
                    str(install_root).replace("\\", "/"),
                ],
                cwd=str(SKILL_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(4, completed.returncode, completed.stderr)
            self.assertIn("链接", completed.stderr)
            self.assertEqual(before, _snapshot_tree(victim))

    def test_javascript_installer_ignores_custom_home_env(self):
        node = shutil.which("node")
        self.assertTrue(node, "node executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-env-") as temp:
            root = Path(temp)
            fake_home = root / "home"
            codex_trap = root / "codex-trap"
            xdg_trap = root / "xdg-trap"
            fake_home.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(fake_home),
                    "USERPROFILE": str(fake_home),
                    "CODEX_HOME": str(codex_trap),
                    "XDG_CONFIG_HOME": str(xdg_trap),
                }
            )

            codex = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--agent",
                    "codex",
                    "--dry-run",
                ],
                cwd=str(SKILL_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(0, codex.returncode, codex.stderr)
            codex_out = _normalize_path_text(codex.stdout)
            self.assertIn(
                _normalize_path_text(
                    fake_home / ".codex" / "skills" / "yotta-resume"
                ),
                codex_out,
            )
            self.assertNotIn(_normalize_path_text(codex_trap), codex_out)

            opencode = subprocess.run(
                [
                    node,
                    str(SKILL_DIR / "bin" / "install.js"),
                    "--agent",
                    "opencode",
                    "--dry-run",
                ],
                cwd=str(SKILL_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(0, opencode.returncode, opencode.stderr)
            opencode_out = _normalize_path_text(opencode.stdout)
            self.assertIn(
                _normalize_path_text(
                    fake_home / ".config" / "opencode" / "skills" / "yotta-resume"
                ),
                opencode_out,
            )
            self.assertNotIn(_normalize_path_text(xdg_trap), opencode_out)

    def test_shell_installer_ignores_custom_home_env(self):
        bash = shutil.which("bash")
        self.assertTrue(bash, "bash executable not found")
        with tempfile.TemporaryDirectory(prefix="yotta-resume-sh-env-") as temp:
            root = Path(temp)
            fake_home = root / "home"
            codex_trap = root / "codex-trap"
            xdg_trap = root / "xdg-trap"
            fake_home.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(fake_home).replace("\\", "/"),
                    "USERPROFILE": str(fake_home),
                    "CODEX_HOME": str(codex_trap).replace("\\", "/"),
                    "XDG_CONFIG_HOME": str(xdg_trap).replace("\\", "/"),
                }
            )
            script = str(SKILL_DIR / "install.sh").replace("\\", "/")

            codex = subprocess.run(
                [bash, script, "--agent", "codex", "--dry-run"],
                cwd=str(SKILL_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(0, codex.returncode, codex.stderr)
            codex_out = _normalize_path_text(codex.stdout)
            self.assertIn(
                "home/.codex/skills/yotta-resume",
                codex_out,
            )
            self.assertNotIn(_normalize_path_text(codex_trap), codex_out)

            opencode = subprocess.run(
                [bash, script, "--agent", "opencode", "--dry-run"],
                cwd=str(SKILL_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(0, opencode.returncode, opencode.stderr)
            opencode_out = _normalize_path_text(opencode.stdout)
            self.assertIn(
                "home/.config/opencode/skills/yotta-resume",
                opencode_out,
            )
            self.assertNotIn(_normalize_path_text(xdg_trap), opencode_out)


if __name__ == "__main__":
    unittest.main()
