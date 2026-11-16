from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from unittest.mock import patch

from hibernator.approval import confirm_exact_plan
from hibernator.cleaner import _unregister_test_owned_root, apply_production, apply_test_fixture
from hibernator.errors import ApplyRefused, InvalidPlan
from hibernator.plans import make_plan
from tests.helpers import node_fixture


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()
        self.fixture.mark_test_owned()

    def tearDown(self):
        self.fixture.close()

    def test_production_apply_is_disabled_even_with_interactive_flag(self):
        with self.assertRaises(ApplyRefused):
            apply_production(make_plan(self.fixture.root), interactive=True)

    def test_noninteractive_apply_refuses(self):
        with self.assertRaises(ApplyRefused):
            apply_production(make_plan(self.fixture.root), interactive=False)

    def test_exact_digest_approval_contract_and_decline(self):
        plan = make_plan(self.fixture.root)
        approval_output = StringIO()
        with patch("sys.stdin.isatty", return_value=True):
            with redirect_stdout(StringIO()):
                confirm_exact_plan(plan, input_fn=lambda: f"DELETE {plan['digest']}", output=approval_output)
                self.assertIn("Protected, blocked, and review items", approval_output.getvalue())
                self.assertIn("src", approval_output.getvalue())
                with self.assertRaises(ApplyRefused):
                    confirm_exact_plan(plan, input_fn=lambda: "yes")

    def test_synthetic_fixture_cleanup_removes_only_approved_candidate(self):
        plan = make_plan(self.fixture.root)
        report = apply_test_fixture(plan, self.fixture.root)
        self.assertEqual("COMPLETED", report["status"])
        self.assertFalse((self.fixture.root / "node_modules").exists())
        self.assertTrue((self.fixture.root / "src/app.js").is_file())
        self.assertTrue((self.fixture.root / ".hibernator-test-owned").is_file())

    def test_excluded_candidate_is_never_removed(self):
        self.fixture.write("requirements.txt", "example==1.0\n")
        self.fixture.commit("requirements.txt")
        self.fixture.write(".venv/pyvenv.cfg", "home = synthetic\n")
        plan = make_plan(self.fixture.root, [".venv"])
        report = apply_test_fixture(plan, self.fixture.root)
        self.assertEqual("COMPLETED", report["status"])
        self.assertFalse((self.fixture.root / "node_modules").exists())
        self.assertTrue((self.fixture.root / ".venv/pyvenv.cfg").is_file())

    def test_synthetic_cleanup_rejects_unmarked_or_wrong_root(self):
        plan = make_plan(self.fixture.root)
        with self.assertRaises(ApplyRefused):
            apply_test_fixture(plan, self.fixture.root.parent)

    def test_marker_alone_does_not_authorize_fixture_cleanup(self):
        plan = make_plan(self.fixture.root)
        _unregister_test_owned_root(self.fixture.root)
        with self.assertRaises(ApplyRefused):
            apply_test_fixture(plan, self.fixture.root)
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())

    def test_synthetic_cleanup_rejects_stale_plan(self):
        plan = make_plan(self.fixture.root)
        (self.fixture.root / "node_modules/pkg/added.js").write_text("new", encoding="utf-8")
        with self.assertRaises(InvalidPlan):
            apply_test_fixture(plan, self.fixture.root)
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())

    def test_replay_of_consumed_synthetic_plan_is_rejected(self):
        plan = make_plan(self.fixture.root)
        apply_test_fixture(plan, self.fixture.root)
        with self.assertRaises(InvalidPlan):
            apply_test_fixture(plan, self.fixture.root)

    def test_concurrent_fixture_apply_fails_closed(self):
        plan = make_plan(self.fixture.root)
        lock = self.fixture.root.parent / (self.fixture.root.name + ".hibernator-test-lock")
        lock.write_text("busy", encoding="utf-8")
        try:
            with self.assertRaises(ApplyRefused):
                apply_test_fixture(plan, self.fixture.root)
            self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())
        finally:
            lock.unlink(missing_ok=True)

    def test_interrupted_fixture_cleanup_leaves_durable_partial_report(self):
        plan = make_plan(self.fixture.root)
        with patch("hibernator.cleaner.shutil.rmtree", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                apply_test_fixture(plan, self.fixture.root)
        reports = list(self.fixture.root.parent.glob("report-*.json"))
        self.assertEqual(1, len(reports))
        import json
        result = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual("INTERRUPTED", result["status"])
        self.assertEqual("UNKNOWN", result["outcomes"][0]["status"])
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())

    def test_removal_error_is_reported_unknown_not_complete_failure(self):
        plan = make_plan(self.fixture.root)
        with patch("hibernator.cleaner.shutil.rmtree", side_effect=PermissionError("synthetic locked entry")):
            result = apply_test_fixture(plan, self.fixture.root)
        self.assertEqual("PARTIAL", result["status"])
        self.assertEqual("UNKNOWN", result["outcomes"][0]["status"])
        self.assertEqual(0, result["removed_logical_bytes"])
        self.assertIn("may have partially changed", result["outcomes"][0]["reason"])
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())

    def test_prejournal_failure_prevents_fixture_deletion(self):
        plan = make_plan(self.fixture.root)
        with patch("hibernator.cleaner.save_report", side_effect=OSError("synthetic journal failure")):
            with self.assertRaises(OSError):
                apply_test_fixture(plan, self.fixture.root)
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").exists())


if __name__ == "__main__":
    unittest.main()
