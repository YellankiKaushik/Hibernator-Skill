from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from hibernator.cli import main
from hibernator.cleaner import apply_test_fixture
from hibernator.plans import make_plan
from hibernator.restore import restore_preview
from hibernator.reports import write_scan_report
from tests.helpers import GitFixture, node_fixture


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
        self.assertIn("npm ci", preview["commands"])
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
