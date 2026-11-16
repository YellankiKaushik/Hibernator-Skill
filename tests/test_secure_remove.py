from __future__ import annotations

import hashlib
import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from hibernator.errors import ApplyRefused, InvalidPlan
from hibernator.plans import make_plan
from hibernator.secure_remove import UnsupportedDeletionPlatform, _preflight, remove_test_fixture_candidate
from tests.helpers import node_fixture


class DescriptorRelativeRemovalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()
        self.fixture.mark_test_owned()
        self.sentinel = self.fixture.root.parent / "external-sentinel.txt"
        self.sentinel.write_bytes(b"synthetic external sentinel\n")
        self.sentinel_before = hashlib.sha256(self.sentinel.read_bytes()).hexdigest()
        self.plan = make_plan(self.fixture.root)

    def tearDown(self):
        self.fixture.close()

    def _preflight_package(self):
        package = self.fixture.root / "node_modules/pkg"
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory_fd = os.open(package, flags)
        try:
            _preflight(directory_fd, os.fstat(directory_fd).st_dev)
        finally:
            os.close(directory_fd)

    def test_posix_removes_only_planned_fixture_candidate_and_preserves_external_sentinel(self):
        if os.name == "nt":
            with self.assertRaises(UnsupportedDeletionPlatform):
                remove_test_fixture_candidate(self.plan, "node_modules")
            self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())
        else:
            remove_test_fixture_candidate(self.plan, "node_modules")
            self.assertFalse((self.fixture.root / "node_modules").exists())
            self.assertTrue((self.fixture.root / "src/app.js").is_file())
            self.assertTrue((self.fixture.root / ".hibernator-test-owned").is_file())
        self.assertEqual(self.sentinel_before, hashlib.sha256(self.sentinel.read_bytes()).hexdigest())

    def test_stale_plan_is_rejected_before_fixture_removal(self):
        (self.fixture.root / "node_modules/pkg/new-file.js").write_text("changed\n", encoding="utf-8")
        expected_error = UnsupportedDeletionPlatform if os.name == "nt" else InvalidPlan
        with self.assertRaises(expected_error):
            remove_test_fixture_candidate(self.plan, "node_modules")
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())
        self.assertEqual(self.sentinel_before, hashlib.sha256(self.sentinel.read_bytes()).hexdigest())

    def test_consumed_plan_cannot_be_replayed(self):
        if os.name == "nt":
            with self.assertRaises(UnsupportedDeletionPlatform):
                remove_test_fixture_candidate(self.plan, "node_modules")
            return
        remove_test_fixture_candidate(self.plan, "node_modules")
        with self.assertRaises(InvalidPlan):
            remove_test_fixture_candidate(self.plan, "node_modules")
        self.assertEqual(self.sentinel_before, hashlib.sha256(self.sentinel.read_bytes()).hexdigest())

    def test_symlink_entry_refuses_before_removing_any_candidate_file(self):
        if os.name == "nt":
            with self.assertRaises(UnsupportedDeletionPlatform):
                remove_test_fixture_candidate(self.plan, "node_modules")
            return
        outside = self.fixture.root.parent / "outside-link-target"
        outside.mkdir()
        target = outside / "sentinel.txt"
        target.write_bytes(b"outside link target\n")
        link = self.fixture.root / "node_modules/pkg/external-link"
        try:
            link.symlink_to(target)
        except OSError as exc:
            if os.name == "nt":
                with self.assertRaises(UnsupportedDeletionPlatform):
                    remove_test_fixture_candidate(self.plan, "node_modules")
                return
            self.skipTest(f"symlink creation unavailable: {exc}")
        expected_error = UnsupportedDeletionPlatform if os.name == "nt" else ApplyRefused
        with self.assertRaises(expected_error):
            self._preflight_package()
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())
        self.assertEqual(b"outside link target\n", target.read_bytes())

    def test_hardlink_entry_refuses_and_external_sentinel_stays_unchanged(self):
        if os.name == "nt":
            with self.assertRaises(UnsupportedDeletionPlatform):
                remove_test_fixture_candidate(self.plan, "node_modules")
            return
        linked = self.fixture.root / "node_modules/pkg/external-hardlink"
        try:
            os.link(self.sentinel, linked)
        except OSError as exc:
            if os.name == "nt":
                with self.assertRaises(UnsupportedDeletionPlatform):
                    remove_test_fixture_candidate(self.plan, "node_modules")
                return
            self.skipTest(f"hard-link creation unavailable: {exc}")
        expected_error = UnsupportedDeletionPlatform if os.name == "nt" else ApplyRefused
        with self.assertRaises(expected_error):
            self._preflight_package()
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())
        self.assertEqual(self.sentinel_before, hashlib.sha256(self.sentinel.read_bytes()).hexdigest())

    def test_cross_device_entry_refuses_before_candidate_changes(self):
        if os.name == "nt":
            with self.assertRaises(UnsupportedDeletionPlatform):
                remove_test_fixture_candidate(self.plan, "node_modules")
            return
        real_entry_info = __import__("hibernator.secure_remove", fromlist=["_entry_info"])._entry_info
        mount = self.fixture.root / "node_modules/pkg/mounted"
        mount.mkdir()
        self.plan = make_plan(self.fixture.root)
        mount_identity = (mount.lstat().st_dev, mount.lstat().st_ino)

        def fake_mount_info(directory_fd, name):
            info = real_entry_info(directory_fd, name)
            if name == "mounted" and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[2] = int(info.st_dev) + 1
                return os.stat_result(fields)
            return info

        with patch("hibernator.secure_remove._entry_info", side_effect=fake_mount_info):
            with self.assertRaises(ApplyRefused):
                remove_test_fixture_candidate(self.plan, "node_modules")
        self.assertTrue((self.fixture.root / "node_modules/pkg/index.js").is_file())
        self.assertEqual(self.sentinel_before, hashlib.sha256(self.sentinel.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
