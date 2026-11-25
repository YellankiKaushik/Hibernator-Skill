from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from hibernator.errors import InvalidPlan
from hibernator.plans import load_plan, make_plan, plan_digest, save_plan, validate_current, validate_plan
from tests.helpers import make_junction, node_fixture, temporary_directory


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
        with temporary_directory(prefix="hibernator-plan-test-") as tmp:
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

    def test_fixture_temp_alias_is_resolved_before_saving_but_explicit_alias_is_refused(self):
        plan = make_plan(self.fixture.root)
        parent = self.fixture.root.parent
        external = parent / "external"
        external.mkdir()
        for destination in (external, self.fixture.root):
            with self.subTest(destination=destination.name):
                alias = parent / "temp-alias"
                if os.name == "nt":
                    self.assertTrue(make_junction(alias, destination))
                else:
                    alias.symlink_to(destination, target_is_directory=True)
                try:
                    with self.assertRaisesRegex(InvalidPlan, "unaliased local destination"):
                        save_plan(plan, alias / "missing-parent" / "plan.json")
                    self.assertFalse((destination / "missing-parent").exists())

                    if destination == external:
                        with patch("tests.helpers.tempfile.gettempdir", return_value=str(alias)):
                            with temporary_directory(prefix="hibernator-output-") as tmp:
                                output = Path(tmp)
                                self.assertEqual(external, output.parent)
                                path = output / "plan.json"
                                save_plan(plan, path)
                                self.assertEqual(plan, load_plan(path))
                        self.assertFalse(output.exists())
                finally:
                    if os.name == "nt":
                        alias.rmdir()
                    else:
                        alias.unlink()

    def test_failed_save_preserves_existing_plan_and_removes_temporary_file(self):
        original = make_plan(self.fixture.root)
        replacement = make_plan(self.fixture.root, ["node_modules"])
        with temporary_directory(prefix="hibernator-plan-test-") as tmp:
            path = Path(tmp) / "plan.json"
            save_plan(original, path)

            with patch("hibernator.plans.os.replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaisesRegex(OSError, "simulated replace failure"):
                    save_plan(replacement, path)

            self.assertEqual(original, load_plan(path))
            self.assertEqual([path], list(Path(tmp).iterdir()))
            save_plan(replacement, path)
            self.assertEqual(replacement, load_plan(path))

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
        subprocess.run(["git", "-C", str(self.fixture.root), "add", "src/app.js"], check=True)
        with self.assertRaises(InvalidPlan):
            validate_current(plan)

    def test_second_staged_edit_with_same_status_and_size_invalidates_plan(self):
        git = ["git", "-C", str(self.fixture.root)]
        stage_source = [*git, "add", "src/app.js"]
        next_revision = b"export const app = 2;\n"
        # Pre-store the second blob so staging it does not change the .git byte count.
        subprocess.run([*git, "hash-object", "-w", "--stdin"], input=next_revision, stdout=subprocess.DEVNULL, check=True)
        self.fixture.write("src/app.js", "export const app = 1;\n")
        subprocess.run(stage_source, check=True)
        plan = make_plan(self.fixture.root)
        validate_current(plan)

        self.fixture.write("src/app.js", next_revision)
        subprocess.run(stage_source, check=True)

        with self.assertRaisesRegex(InvalidPlan, "Git state changed"):
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
