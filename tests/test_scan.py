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
from tests.helpers import GitFixture, make_junction, node_fixture, temporary_directory


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

    def test_nested_cache_rules_match_and_plan_inside_monorepo(self):
        fixture = GitFixture()
        try:
            fixture.write(
                "packages/web/package.json",
                '{"dependencies":{"next":"synthetic","vite":"synthetic"}}\n',
            )
            fixture.commit("packages/web/package.json")
            fixture.write("packages/web/.next/cache/build-manifest.json", "{}\n")
            fixture.write("packages/web/node_modules/.vite/deps/chunk.js", "export {};\n")

            report = scan(fixture.root)
            by_path = {item.path: item for item in report.items}
            next_cache = "packages/web/.next/cache"
            vite_cache = "packages/web/node_modules/.vite"

            self.assertEqual("REGENERABLE", by_path[next_cache].decision)
            self.assertEqual("next-cache-v1", by_path[next_cache].rule_id)
            self.assertEqual("REGENERABLE", by_path[vite_cache].decision)
            self.assertEqual("vite-cache-v1", by_path[vite_cache].rule_id)

            plan = make_plan(fixture.root)
            candidates = {candidate["path"] for candidate in plan["candidates"]}
            self.assertIn(next_cache, candidates)
            self.assertIn(vite_cache, candidates)
        finally:
            fixture.close()

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

    def test_nested_git_repository_is_not_searched_for_technology_markers(self):
        nested = self.fixture.root / "vendor" / "nested-repository"
        (nested / ".git").mkdir(parents=True)
        (nested / "pyproject.toml").write_text("[project]\nname='nested'\n", encoding="utf-8")
        report = scan(self.fixture.root)
        self.assertNotIn("Python", report.technologies)

    def test_mocked_reparse_subtree_is_not_searched_for_manifests(self):
        linked = self.fixture.root / "vendor" / "reparse-project"
        linked.mkdir(parents=True)
        (linked / "pyproject.toml").write_text("[project]\nname='linked'\n", encoding="utf-8")
        info = linked.lstat()
        target_identity = (info.st_dev, info.st_ino)
        real_check = discovery.is_reparse_point

        def is_mock_reparse(value):
            return (value.st_dev, value.st_ino) == target_identity or real_check(value)

        with patch("hibernator.discovery.is_reparse_point", side_effect=is_mock_reparse), patch(
            "hibernator.rules.is_reparse_point", side_effect=is_mock_reparse
        ), patch("hibernator.util.is_reparse_point", side_effect=is_mock_reparse):
            report = scan(self.fixture.root)
        self.assertNotIn("Python", report.technologies)

    def test_symlinked_manifest_outside_root_is_not_read_as_project_context(self):
        fixture = GitFixture()
        outside = fixture.root.parent / "outside-manifest"
        outside.write_text('{"dependencies":{"react":"synthetic"}}\n', encoding="utf-8")
        try:
            (fixture.root / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
            (fixture.root / "package.json").symlink_to(outside)
        except OSError as exc:
            fixture.close()
            self.skipTest(f"file symlink creation unavailable: {exc}")
        try:
            report = scan(fixture.root)
            self.assertNotIn("Node.js", report.technologies)
            self.assertEqual(outside.read_text(encoding="utf-8"), '{"dependencies":{"react":"synthetic"}}\n')
        finally:
            fixture.close()

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
        with temporary_directory(prefix="hibernator-nongit-test-") as tmp:
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

    def test_mocked_mount_crossing_blocks_candidate_before_counting_child_tree(self):
        mount = self.fixture.root / "node_modules" / "mounted-package"
        mount.mkdir()
        (mount / "package.json").write_text('{"name":"mounted"}\n', encoding="utf-8")
        real_same_device = discovery._same_device
        mount_identity = (mount.lstat().st_dev, mount.lstat().st_ino)

        def same_device(path, device):
            info = Path(path).lstat()
            if (info.st_dev, info.st_ino) == mount_identity:
                return False
            return real_same_device(path, device)

        with patch("hibernator.discovery._same_device", side_effect=same_device):
            node = next(item for item in scan(self.fixture.root).items if item.path == "node_modules")
        self.assertEqual("BLOCKED", node.decision)
        self.assertIn("filesystem boundary", node.reason)

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
