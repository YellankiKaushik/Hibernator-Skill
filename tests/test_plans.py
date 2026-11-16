from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hibernator.errors import InvalidPlan
from hibernator.plans import load_plan, make_plan, plan_digest, save_plan, validate_current, validate_plan
from tests.helpers import node_fixture


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()

    def tearDown(self):
        self.fixture.close()

    def test_plan_digest_is_stable_except_creation_metadata(self):
        one = make_plan(self.fixture.root)
        same = dict(one)
        self.assertEqual(one["digest"], plan_digest(same))
        self.assertEqual(1, len(one["candidates"]))

    def test_exclusion_changes_exact_candidate_selection_and_digest(self):
        one = make_plan(self.fixture.root)
        two = make_plan(self.fixture.root, ["node_modules"])
        self.assertNotEqual(one["digest"], two["digest"])
        self.assertEqual([], two["candidates"])

    def test_unknown_exclusion_rejected(self):
        with self.assertRaises(InvalidPlan):
            make_plan(self.fixture.root, ["../outside"])

    def test_plan_roundtrip_and_tamper_rejected(self):
        value = make_plan(self.fixture.root)
        with tempfile.TemporaryDirectory(prefix="hibernator-plan-test-") as tmp:
            path = Path(tmp) / "plan.json"
            save_plan(value, path)
            self.assertEqual(value, load_plan(path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["candidates"][0]["path"] = "../escape"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidPlan):
                load_plan(path)

    def test_plan_must_be_saved_outside_target_project(self):
        with self.assertRaises(InvalidPlan):
            save_plan(make_plan(self.fixture.root), self.fixture.root / "plan.json")

    def test_changed_candidate_invalidates_plan(self):
        plan = make_plan(self.fixture.root)
        file = self.fixture.root / "node_modules/pkg/index.js"
        original = file.read_bytes()
        file.write_bytes(b"x" * len(original))
        with self.assertRaises(InvalidPlan):
            validate_current(plan)

    def test_git_change_invalidates_plan(self):
        plan = make_plan(self.fixture.root)
        (self.fixture.root / "src/app.js").write_text("modified", encoding="utf-8")
        with self.assertRaises(InvalidPlan):
            validate_current(plan)

    def test_staged_git_change_invalidates_plan(self):
        plan = make_plan(self.fixture.root)
        source = self.fixture.root / "src/app.js"
        source.write_text("staged source change\n", encoding="utf-8")
        import subprocess
        subprocess.run(["git", "-C", str(self.fixture.root), "add", "src/app.js"], check=True)
        with self.assertRaises(InvalidPlan):
            validate_current(plan)

    def test_malformed_candidate_rejected(self):
        plan = make_plan(self.fixture.root)
        plan["candidates"][0]["path"] = "C:/outside"
        plan["digest"] = plan_digest(plan)
        with self.assertRaises(InvalidPlan):
            validate_plan(plan)

    def test_tampered_review_context_is_rejected(self):
        plan = make_plan(self.fixture.root)
        plan["review_items"][0]["reason"] = "display untrusted data"
        plan["digest"] = plan_digest(plan)
        with self.assertRaises(InvalidPlan):
            validate_current(plan)


if __name__ == "__main__":
    unittest.main()
