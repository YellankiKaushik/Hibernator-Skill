from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import hibernator.restore as restore_module
import hibernator.util as util
from hibernator.cli import main
from hibernator.cleaner import apply_test_fixture
from hibernator.plans import load_plan, make_plan
from hibernator.restore import restore_preview
from hibernator.reports import write_scan_report
from tests.helpers import GitFixture, make_junction, node_fixture


REPO = Path(__file__).resolve().parents[1]


class RestoreAndCliTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()

    def tearDown(self):
        self.fixture.close()

    def test_npm_restore_preview_is_non_mutating(self):
        before = sorted(p.relative_to(self.fixture.root).as_posix() for p in self.fixture.root.rglob("*"))
        preview = restore_preview(self.fixture.root)
        after = sorted(p.relative_to(self.fixture.root).as_posix() for p in self.fixture.root.rglob("*"))
        self.assertIn("Node project .: npm ci", preview["commands"])
        self.assertEqual(before, after)
        self.assertTrue(all("network" in warning.lower() or "lifecycle" in warning.lower() for warning in preview["warnings"]))

    def test_restore_reports_unverified_without_manifests(self):
        other = GitFixture()
        try:
            result = restore_preview(other.root)
            self.assertEqual("RESTORE_UNVERIFIED", result["status"])
        finally:
            other.close()

    def test_multiple_node_lockfiles_require_manual_choice(self):
        self.fixture.write("yarn.lock", "# synthetic lock\n")
        result = restore_preview(self.fixture.root)
        self.assertEqual([], result["commands"])
        self.assertTrue(any("Multiple Node lockfiles" in warning for warning in result["warnings"]))

    def test_monorepo_restore_groups_node_workspace_and_lists_nested_python_project(self):
        self.fixture.write("apps/web/package.json", '{"name":"web"}\n')
        self.fixture.write("services/api/pyproject.toml", "[project]\nname='api'\n")
        self.fixture.write("services/api/requirements.txt", "flask==3.0.0\n")
        self.fixture.write("apps/web/node_modules/ignored/package.json", '{"name":"not-a-project"}\n')
        before = sorted(path.relative_to(self.fixture.root).as_posix() for path in self.fixture.root.rglob("*"))

        result = restore_preview(self.fixture.root)

        after = sorted(path.relative_to(self.fixture.root).as_posix() for path in self.fixture.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertEqual(1, sum("npm ci" in command for command in result["commands"]))
        self.assertIn("Node project .: npm ci", result["commands"])
        self.assertIn("Python project services/api: python -m venv .venv", result["commands"])
        self.assertIn("Python project services/api: python -m pip install -r requirements.txt", result["commands"])
        self.assertTrue(any("Nested Node manifests" in warning for warning in result["warnings"]))
        self.assertTrue(all("ignored" not in command for command in result["commands"]))

    def test_nested_node_lockfile_gets_own_restore_working_directory(self):
        self.fixture.write("apps/isolated/package.json", '{"name":"isolated"}\n')
        self.fixture.write("apps/isolated/yarn.lock", "# synthetic lock\n")
        result = restore_preview(self.fixture.root)
        self.assertIn("Node project apps/isolated: yarn install --immutable", result["commands"])
        self.assertIn("Node project .: npm ci", result["commands"])

    def test_nested_node_project_without_lockfile_warns_without_guessing_manager(self):
        other = GitFixture()
        try:
            other.write("tools/independent/package.json", '{"name":"independent"}\n')
            result = restore_preview(other.root)
            self.assertTrue(any("Node manifest at tools/independent has no recognized lockfile" in warning for warning in result["warnings"]))
            self.assertIn("Review package.json at tools/independent and use that project's chosen package manager.", result["commands"])
        finally:
            other.close()

    def test_restore_prunes_nested_git_repository_boundary(self):
        nested = self.fixture.root / "vendor" / "nested-repository"
        nested.mkdir(parents=True)
        (nested / ".git").mkdir()
        (nested / "pyproject.toml").write_text("[project]\nname='nested'\n", encoding="utf-8")
        result = restore_preview(self.fixture.root)
        self.assertFalse(any(command.startswith("Python project vendor/nested-repository:") for command in result["commands"]))

    def test_restore_prunes_mocked_reparse_directory(self):
        linked = self.fixture.root / "vendor" / "linked-package"
        linked.mkdir(parents=True)
        (linked / "package.json").write_text('{"name":"linked"}\n', encoding="utf-8")
        (linked / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
        info = linked.lstat()
        target_identity = (info.st_dev, info.st_ino)
        real_check = util.is_reparse_point

        def is_mock_reparse(value):
            return (value.st_dev, value.st_ino) == target_identity or real_check(value)

        with patch("hibernator.restore.is_reparse_point", side_effect=is_mock_reparse), patch(
            "hibernator.util.is_reparse_point", side_effect=is_mock_reparse
        ):
            result = restore_preview(self.fixture.root)
        self.assertFalse(any("vendor/linked-package" in command for command in result["commands"]))

    def test_restore_prunes_mocked_mount_crossing(self):
        mounted = self.fixture.root / "vendor" / "mounted-project"
        mounted.mkdir(parents=True)
        (mounted / "package.json").write_text('{"name":"mounted"}\n', encoding="utf-8")
        (mounted / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
        info = mounted.lstat()
        target_identity = (info.st_dev, info.st_ino)
        real_same_device = restore_module._same_device

        def same_device(path, device):
            entry = Path(path).lstat()
            if (entry.st_dev, entry.st_ino) == target_identity:
                return False
            return real_same_device(path, device)

        with patch("hibernator.restore._same_device", side_effect=same_device):
            result = restore_preview(self.fixture.root)
        self.assertFalse(any("vendor/mounted-project" in command for command in result["commands"]))

    def test_restore_does_not_follow_external_manifest_symlink(self):
        outside = self.fixture.root.parent / "outside-project"
        outside.mkdir()
        sentinel = outside / "package.json"
        sentinel.write_text('{"name":"outside"}\n', encoding="utf-8")
        before = sentinel.read_bytes()
        project_manifest = self.fixture.root / "vendor" / "external-package" / "package.json"
        project_manifest.parent.mkdir(parents=True, exist_ok=True)
        try:
            project_manifest.symlink_to(sentinel)
        except OSError as exc:
            self.skipTest(f"file symlink creation unavailable: {exc}")
        result = restore_preview(self.fixture.root)
        self.assertEqual(before, sentinel.read_bytes())
        self.assertFalse(any("external-package" in command for command in result["commands"]))

    def test_restore_does_not_traverse_external_junction(self):
        outside = self.fixture.root.parent / "outside-junction-project"
        outside.mkdir()
        sentinel = outside / "package.json"
        sentinel.write_text('{"name":"outside"}\n', encoding="utf-8")
        (outside / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
        before = sentinel.read_bytes()
        junction = self.fixture.root / "vendor" / "external-junction"
        junction.parent.mkdir(parents=True, exist_ok=True)
        if not make_junction(junction, outside):
            self.skipTest("Windows junction creation is unavailable")
        try:
            result = restore_preview(self.fixture.root)
            self.assertFalse(any("external-junction" in command for command in result["commands"]))
            self.assertEqual(before, sentinel.read_bytes())
        finally:
            junction.rmdir()

    def test_scan_json_is_valid_and_clean(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["scan", "--project", str(self.fixture.root), "--format", "json"])
        self.assertEqual(0, code)
        payload = json.loads(out.getvalue())
        self.assertEqual(".", payload["root"])
        self.assertTrue(payload["root_redacted"])
        self.assertNotIn("synthetic-secret", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["scan", "--project", str(self.fixture.root), "--show-paths", "--format", "json"])
        self.assertEqual(0, code)
        self.assertEqual(str(self.fixture.root.resolve()), json.loads(out.getvalue())["root"])

    def test_saved_report_redacts_absolute_root(self):
        report = __import__("hibernator.discovery", fromlist=["scan"]).scan(self.fixture.root).to_dict()
        with tempfile.TemporaryDirectory(prefix="hibernator-report-test-") as tmp:
            with patch("hibernator.reports.report_directory", return_value=Path(tmp)):
                path = write_scan_report(str(self.fixture.root), report)
            stored_text = path.read_text(encoding="utf-8")
            stored = json.loads(stored_text)
            self.assertEqual(".", stored["root"])
            self.assertEqual(".", stored["git_root"])
            self.assertTrue(stored["root_redacted"])
            self.assertNotIn(str(self.fixture.root), stored_text)

    def test_plans_created_in_the_same_second_have_distinct_default_files(self):
        argv = ["plan", "--project", str(self.fixture.root), "--format", "json"]
        with tempfile.TemporaryDirectory(prefix="hibernator-cli-test-") as tmp:
            with patch("hibernator.cli.report_directory", return_value=Path(tmp)), patch(
                "hibernator.plans.utc_now", return_value="2026-11-25T00:00:00+00:00"
            ):
                first_output = io.StringIO()
                with redirect_stdout(first_output):
                    self.assertEqual(0, main(argv))
                second_output = io.StringIO()
                with redirect_stdout(second_output):
                    self.assertEqual(0, main([*argv, "--exclude", "node_modules"]))

            first = json.loads(first_output.getvalue())
            second = json.loads(second_output.getvalue())
            self.assertNotEqual(first["saved_plan"], second["saved_plan"])
            first_plan = load_plan(Path(first["saved_plan"]))
            self.assertEqual(["node_modules"], [item["path"] for item in first_plan["candidates"]])
            self.assertEqual([], load_plan(Path(second["saved_plan"]))["candidates"])

    def test_noninteractive_apply_returns_refusal_code(self):
        from hibernator.plans import save_plan

        with tempfile.TemporaryDirectory(prefix="hibernator-cli-test-") as tmp:
            plan_path = Path(tmp) / "plan.json"
            save_plan(make_plan(self.fixture.root), plan_path)
            out = io.StringIO()
            with patch("hibernator.cli.report_directory", return_value=Path(tmp)), patch("sys.stdin.isatty", return_value=False):
                with redirect_stdout(out):
                    code = main(["apply", "--plan", str(plan_path), "--format", "json"])
            self.assertEqual(5, code)
            result = json.loads(out.getvalue())
            self.assertEqual("APPROVAL_REQUIRED", result["status"])
            self.assertEqual(0, result["removed_logical_bytes"])

    def test_interactive_apply_records_unsupported_without_deleting(self):
        import tempfile
        from hibernator.plans import save_plan

        with tempfile.TemporaryDirectory(prefix="hibernator-cli-test-") as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan = make_plan(self.fixture.root)
            save_plan(plan, plan_path)
            out = io.StringIO()
            with patch("hibernator.cli.report_directory", return_value=Path(tmp)), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value=f"DELETE {plan['digest']}"):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    code = main(["apply", "--plan", str(plan_path), "--format", "json"])
            result = json.loads(out.getvalue())
            self.assertEqual(3, code)
            self.assertEqual("APPROVED_BUT_UNSUPPORTED", result["status"])
            self.assertEqual(0, result["removed_logical_bytes"])
            self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())

    def test_interactive_apply_decline_is_saved_without_deleting(self):
        from hibernator.plans import save_plan

        with tempfile.TemporaryDirectory(prefix="hibernator-cli-test-") as tmp:
            plan_path = Path(tmp) / "plan.json"
            save_plan(make_plan(self.fixture.root), plan_path)
            out = io.StringIO()
            with patch("hibernator.cli.report_directory", return_value=Path(tmp)), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="no"):
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    code = main(["apply", "--plan", str(plan_path), "--format", "json"])
            result = json.loads(out.getvalue())
            self.assertEqual(5, code)
            self.assertEqual("DECLINED", result["status"])
            self.assertEqual(0, result["removed_logical_bytes"])
            self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())

    def test_cleanup_report_is_saved_and_available_by_id_and_file(self):
        self.fixture.mark_test_owned()
        plan = make_plan(self.fixture.root)
        report = apply_test_fixture(plan, self.fixture.root)
        report_path = self.fixture.root.parent / f"report-{report['report_id']}.json"
        self.assertTrue(report_path.is_file())
        stored_report_text = report_path.read_text(encoding="utf-8")
        stored_report = json.loads(stored_report_text)
        self.assertEqual("cleanup", stored_report["report_type"])
        self.assertEqual(".", stored_report["root"])
        self.assertNotIn(str(self.fixture.root), stored_report_text)
        out = io.StringIO()
        with patch("hibernator.reports.report_directory", return_value=self.fixture.root.parent):
            with redirect_stdout(out):
                code = main(["report", "--id", report["report_id"], "--format", "json"])
        self.assertEqual(0, code)
        loaded = json.loads(out.getvalue())
        self.assertEqual(report["report_id"], loaded["report_id"])
        self.assertEqual("COMPLETED", loaded["status"])
        self.assertEqual(report["calculated_candidate_bytes"], loaded["calculated_candidate_bytes"])
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["report", "--file", str(report_path)])
        self.assertEqual(0, code)
        self.assertIn("Logical bytes removed:", out.getvalue())

    def test_skill_frontmatter_and_policy(self):
        content = (REPO / ".agents" / "skills" / "hibernator" / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\nname: ([a-z0-9-]+)\ndescription: .+\n---\n", content, re.S)
        self.assertIsNotNone(match)
        self.assertEqual("hibernator", match.group(1))
        self.assertIn("Never confirm approval", content)
        self.assertNotIn("rm -rf", content)
        project_config = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(project_config, r'(?s)\[tool\.setuptools\.data-files\].*?"\.agents/skills/hibernator"\s*=\s*\["\.agents/skills/hibernator/SKILL\.md"\]')


if __name__ == "__main__":
    unittest.main()
