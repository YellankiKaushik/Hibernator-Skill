from __future__ import annotations

import unittest
import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import hibernator.discovery as discovery
from hibernator.discovery import scan
from hibernator.errors import ScanFailure, UnsupportedRoot
from hibernator.plans import make_plan, validate_current
from hibernator.errors import InvalidPlan
from tests.helpers import GitFixture, make_junction, node_fixture


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()

    def tearDown(self):
        self.fixture.close()

    def test_node_dependency_candidate_and_tech_markers(self):
        report = scan(self.fixture.root)
        node = next(item for item in report.items if item.path == "node_modules")
        self.assertEqual("REGENERABLE", node.decision)
        self.assertEqual("node-dependencies-v1", node.rule_id)
        self.assertEqual(["Node.js"], report.technologies)
        self.assertGreater(node.logical_bytes, 0)

    def test_secret_database_unknown_ignored_and_source_are_preserved(self):
        self.fixture.write(".env.local", "TOKEN=synthetic-secret-value\n")
        self.fixture.write("local.sqlite", b"synthetic-db")
        self.fixture.write(".gitignore", "private-cache/\n")
        self.fixture.write("private-cache/user.dat", b"unknown")
        self.fixture.write("src/untracked.js", "export const local = 1;\n")
        report = scan(self.fixture.root)
        by_path = {item.path: item for item in report.items}
        self.assertEqual("KEEP", by_path[".env.local"].decision)
        self.assertEqual("REVIEW", by_path["local.sqlite"].decision)
        self.assertEqual("REVIEW", by_path["private-cache"].decision)
        self.assertEqual("KEEP", by_path["src"].decision)
        self.assertNotIn("synthetic-secret-value", str(report.to_dict()))

    def test_protected_child_blocks_dependency_candidate(self):
        self.fixture.write("node_modules/pkg/.env", "synthetic secret\n")
        report = scan(self.fixture.root)
        node = next(item for item in report.items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)

    def test_nested_git_boundary_blocks_dependency_candidate(self):
        (self.fixture.root / "node_modules" / "vendor" / ".git").mkdir(parents=True)
        node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)
        self.assertIn("nested Git boundary", node.reason)

    def test_case_variant_secret_blocks_or_preserves(self):
        self.fixture.write(".ENV.LOCAL", "synthetic token\n")
        self.fixture.write("node_modules/pkg/CREDENTIALS.JSON", "synthetic credential\n")
        items = {item.path: item for item in scan(self.fixture.root).items}
        self.assertEqual("KEEP", items[".ENV.LOCAL"].decision)
        self.assertEqual("BLOCKED", items["node_modules"].decision)

    def test_hardlink_to_external_sentinel_blocks_candidate(self):
        outside = self.fixture.root.parent / "outside-hardlink-sentinel.txt"
        outside.write_bytes(b"external sentinel remains unchanged")
        linked = self.fixture.root / "node_modules" / "pkg" / "linked-sentinel.txt"
        try:
            os.link(outside, linked)
        except OSError as exc:
            self.skipTest(f"hard-link creation unavailable: {exc}")
        before = hashlib.sha256(outside.read_bytes()).hexdigest()
        node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)
        self.assertEqual(before, hashlib.sha256(outside.read_bytes()).hexdigest())

    def test_tracked_descendant_blocks_dependency_candidate(self):
        self.fixture.write("node_modules/kept.js", "tracked source\n")
        self.fixture.commit("node_modules/kept.js")
        report = scan(self.fixture.root)
        node = next(item for item in report.items if item.path == "node_modules")
        self.assertEqual("KEEP", node.decision)

    def test_symlink_in_candidate_blocks_it_without_following(self):
        outside = self.fixture.root.parent / "outside-sentinel"
        outside.mkdir()
        (outside / "sentinel.txt").write_text("keep", encoding="utf-8")
        try:
            (self.fixture.root / "node_modules" / "escape").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)
        self.assertEqual("keep", (outside / "sentinel.txt").read_text(encoding="utf-8"))

    def test_missing_lockfile_makes_node_modules_review(self):
        (self.fixture.root / "package-lock.json").unlink()
        self.fixture.commit("package-lock.json")
        node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("REVIEW", node.decision)

    def test_unrecognized_file_inside_pytest_cache_blocks_it(self):
        self.fixture.write("pytest.ini", "[pytest]\n")
        self.fixture.write(".pytest_cache/v/cache/nodeids", "[]\n")
        self.fixture.write(".pytest_cache/user-notes.txt", "keep this\n")
        cache = next(item for item in scan(self.fixture.root).items if item.path == ".pytest_cache")
        self.assertEqual("BLOCKED", cache.decision)

    def test_scan_does_not_mutate_fixture_files(self):
        target = self.fixture.root / "node_modules" / "pkg" / "index.js"
        before = target.read_bytes()
        index = self.fixture.root / ".git" / "index"
        index_before = hashlib.sha256(index.read_bytes()).hexdigest()
        scan(self.fixture.root)
        self.assertEqual(before, target.read_bytes())
        self.assertEqual(index_before, hashlib.sha256(index.read_bytes()).hexdigest())

    def test_non_git_root_and_repository_subdirectory_are_refused(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="hibernator-nongit-test-") as tmp:
            with self.assertRaises(UnsupportedRoot):
                scan(Path(tmp))
        with self.assertRaises(UnsupportedRoot):
            scan(self.fixture.root / "src")

    def test_symlink_root_is_refused(self):
        link = self.fixture.root.parent / "root-link"
        try:
            link.symlink_to(self.fixture.root, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink creation unavailable: {exc}")
        with self.assertRaises(UnsupportedRoot):
            scan(link)

    def test_mocked_reparse_root_is_refused_without_link_privilege(self):
        with patch("hibernator.discovery.is_reparse_point", return_value=True):
            with self.assertRaises(UnsupportedRoot):
                scan(self.fixture.root)

    def test_mocked_reparse_descendant_blocks_candidate(self):
        target = self.fixture.root / "node_modules" / "reparse-entry"
        target.mkdir()
        target_info = target.lstat()
        real_check = discovery.is_reparse_point

        def is_mock_reparse(info):
            return (info.st_dev, info.st_ino) == (target_info.st_dev, target_info.st_ino) or real_check(info)

        with patch("hibernator.discovery.is_reparse_point", side_effect=is_mock_reparse):
            node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)
        self.assertIn("reparse point", node.reason)

    def test_root_identity_change_fails_scan(self):
        real_identity = discovery.identity
        root = self.fixture.root.resolve()
        root_calls = 0

        def changing_identity(path):
            nonlocal root_calls
            value = real_identity(path)
            if Path(path).resolve(strict=True) == root:
                root_calls += 1
                if root_calls == 2:
                    value = {**value, "inode": value["inode"] + 1}
            return value

        with patch("hibernator.discovery.identity", side_effect=changing_identity):
            with self.assertRaises(ScanFailure):
                scan(self.fixture.root)

    def test_windows_junction_inside_candidate_is_blocked(self):
        outside = self.fixture.root.parent / "outside-sentinel"
        outside.mkdir()
        (outside / "sentinel.txt").write_bytes(b"outside bytes stay unchanged")
        before = (outside / "sentinel.txt").read_bytes()
        junction = self.fixture.root / "node_modules" / "escape"
        if not make_junction(junction, outside):
            self.skipTest("Windows junction creation is unavailable")
        try:
            node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
            self.assertEqual("BLOCKED", node.decision)
            self.assertEqual(before, (outside / "sentinel.txt").read_bytes())
        finally:
            junction.rmdir()

    def test_junction_substitution_after_plan_invalidates_without_external_change(self):
        outside = self.fixture.root.parent / "outside-sentinel"
        outside.mkdir()
        (outside / "sentinel.txt").write_bytes(b"outside bytes stay unchanged")
        before = (outside / "sentinel.txt").read_bytes()
        plan = make_plan(self.fixture.root)
        candidate = self.fixture.root / "node_modules"
        moved = self.fixture.root / "node_modules-displaced"
        candidate.rename(moved)
        if not make_junction(candidate, outside):
            moved.rename(candidate)
            self.skipTest("Windows junction creation is unavailable")
        try:
            with self.assertRaises(InvalidPlan):
                validate_current(plan)
            self.assertEqual(before, (outside / "sentinel.txt").read_bytes())
        finally:
            candidate.rmdir()
            moved.rename(candidate)

    def test_repository_root_junction_is_refused(self):
        link = self.fixture.root.parent / "root-junction"
        if not make_junction(link, self.fixture.root):
            self.skipTest("Windows junction creation is unavailable")
        try:
            with self.assertRaises(UnsupportedRoot):
                scan(link)
        finally:
            link.rmdir()


if __name__ == "__main__":
    unittest.main()
