from __future__ import annotations

import csv
import errno
import io
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from hibernator import inventory, retirement_reports
from hibernator.cli import main
from hibernator.errors import InvalidPlan
from hibernator.paths import pin_windows_directory
from hibernator.plans import make_plan, validate_current
from hibernator.retirement import retire
from tests.helpers import node_fixture


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = node_fixture()
        self.addCleanup(self.fixture.close)
        self.root = self.fixture.root
        self.output = self.root.parent / "reports"
        self.output.mkdir(mode=0o700)
        self.sentinel = self.root.parent / "sentinel"
        self.sentinel.write_bytes(b"private outside fixture")
        self.fixture.write(".env", "private fixture value")
        self.fixture.write("uploads/item.db", b"unique fixture data")
        self.fixture.write("requirements.txt", "sample==1.0\n")
        self.fixture.write(".venv/pyvenv.cfg", "home = synthetic\n")
        self.fixture.write(".venv/Lib/site-packages/sample-1.0.dist-info/METADATA", "Name: sample\nVersion: 1.0\n")
        self.fixture.write(".venv/Lib/site-packages/sample.py", "VALUE = 1\n")
        self.fixture.write("package-lock.json", '{"lockfileVersion":3,"packages":{"":{"name":"fixture"},"node_modules/pkg":{"version":"1.0.0","resolved":"https://registry.npmjs.org/pkg/-/pkg-1.0.0.tgz"}}}')

    def invoke(self, *options, root=None, output=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["retire", "--project", str(root or self.root), "--output",
                         str(output or self.output), "--format", "json", *options])
        return code, json.loads(stdout.getvalue()), stderr.getvalue()

    def snapshot(self):
        return {
            p.relative_to(self.root).as_posix(): (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
            for p in self.root.rglob("*")
        }

    def test_output_inside_or_ancestor_of_project_is_refused(self):
        before = self.snapshot()
        for destination in (self.root, self.root.parent, self.root / "uncreated"):
            with self.subTest(destination=destination):
                code, _, _ = self.invoke(output=destination)
                self.assertEqual(2, code)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(b"private outside fixture", self.sentinel.read_bytes())

    def test_git_file_and_wrong_root_are_refused_without_following_external_path(self):
        for root in (self.root.parent, self.root / "src"):
            with self.subTest(root=root):
                self.assertEqual(2, self.invoke(root=root)[0])
        indirect = self.root.parent / "indirect"
        indirect.mkdir()
        (indirect / ".git").write_text("gitdir: ../project/.git\n", encoding="utf-8")
        code, report, _ = self.invoke(root=indirect)
        self.assertIn(code, (2, 3))
        self.assertFalse(report.get("candidates"))
        self.assertEqual([], list(self.output.iterdir()))

    def test_home_and_filesystem_roots_are_refused_without_inventory(self):
        with patch("hibernator.paths.Path.home", return_value=self.root):
            self.assertEqual(2, self.invoke()[0])
        self.assertEqual(2, self.invoke(root=Path(self.root.anchor))[0])
        self.assertEqual([], list(self.output.iterdir()))

    def test_output_reparse_alias_is_refused_before_inspection(self):
        real = inventory.is_reparse_point
        output_inode = self.output.lstat().st_ino
        with patch("hibernator.paths.is_reparse_point", side_effect=lambda info: info.st_ino == output_inode or real(info)), \
                patch("hibernator.retirement.collect_inventory", side_effect=AssertionError("inventory started")):
            self.assertEqual(2, self.invoke()[0])
        self.assertEqual([], list(self.output.iterdir()))

    def test_default_output_is_created_in_local_state_outside_the_fixture(self):
        state = self.root.parent / "local-state"
        with patch("hibernator.retirement_reports.report_directory", return_value=state / "reports"):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                result = main(["retire", "--project", str(self.root), "--format", "json"])
        self.assertEqual(0, result)
        payload = json.loads(out.getvalue())
        self.assertTrue((state / "reports" / "retirement" / payload["reports"]["completion"]).is_file())
        self.assertNotIn(str(self.root), out.getvalue())

    def test_git_configuration_and_environment_cannot_invoke_external_programs(self):
        config = self.root / ".git/config"
        with config.open("ab") as handle:
            handle.write(b'\n[include]\n  path = ../../sentinel\n[filter "malicious"]\n  process = forbidden\n')
        before = self.snapshot()
        run = subprocess.run
        with patch.dict(os.environ, {"GIT_DIR": str(self.root.parent / "elsewhere"),
                                     "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor",
                                     "GIT_CONFIG_VALUE_0": "forbidden"}), patch("hibernator.git_state.subprocess.run", wraps=run) as git:
            code, summary, progress = self.invoke()
        self.assertEqual(1, git.call_count)
        args, options = git.call_args
        self.assertIn("--no-includes", args[0])
        self.assertFalse(options["shell"])
        self.assertNotIn("GIT_DIR", options["env"])
        self.assertNotIn("GIT_CONFIG_COUNT", options["env"])
        self.assertIn(code, (2, 3))
        self.assertFalse(summary.get("candidates"))
        self.assertEqual(before, self.snapshot())
        self.assertNotIn(str(self.root), progress)
        self.assertEqual(b"private outside fixture", self.sentinel.read_bytes())

    def test_invalid_filter_inputs_fail_before_report_creation(self):
        cases = [("--min-size-mib", value) for value in ("-1", "NaN", "Infinity")]
        cases += [("--exclude", value) for value in ("C:node_modules", "../node_modules", "*", "./node_modules",
                                                       r"\\server\share", r"\\?\C:\node_modules")]
        for options in cases:
            with self.subTest(options=options):
                self.assertEqual(2, self.invoke(*options)[0])
        self.assertEqual([], list(self.output.iterdir()))

    def test_candidate_tree_and_git_index_remain_unchanged(self):
        subprocess.run(["git", "-C", str(self.root), "add", "package-lock.json"], check=True)
        self.fixture.write("src/app.js", "local unstaged change\n")
        before = self.snapshot()
        code, summary, progress = self.invoke()
        self.assertEqual(0, code)
        self.assertEqual("READY_FOR_MANUAL_REVIEW", summary["status"])
        self.assertEqual({"node_modules", ".venv"}, {entry["path"] for entry in summary["candidates"]})
        self.assertEqual(1, summary["metrics"]["primary_passes"])
        self.assertEqual(0, summary["metrics"]["payload_bytes_hashed"])
        self.assertEqual(1, summary["git_observations"]["staged_paths"])
        self.assertGreaterEqual(summary["git_observations"]["tracked_stat_differences"], 1)
        self.assertEqual(5, summary["metrics"]["git_subprocesses"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(b"private outside fixture", self.sentinel.read_bytes())
        self.assertNotIn("private fixture value", json.dumps(summary) + progress)

    def test_blocked_parent_suppresses_candidate_child(self):
        self.fixture.write("node_modules/pkg/.env", "protected nested secret")
        self.fixture.write("node_modules/.vite/deps/package.json", '{"type":"module"}')
        self.fixture.write("vite.config.js", "throw Error('must never run');")
        code, summary, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertEqual([".venv"], [entry["path"] for entry in summary["candidates"]])

    def test_apply_refusal_does_not_access_plan_or_stdin(self):
        out = io.StringIO()
        with redirect_stdout(out), patch("builtins.input", side_effect=AssertionError("stdin")), \
                patch("sys.stdin.isatty", side_effect=AssertionError("stdin")):
            code = main(["apply", "--plan", str(self.root / "missing.plan"), "--format", "json"])
        self.assertEqual(5, code)
        self.assertEqual("APPLY_UNSUPPORTED", json.loads(out.getvalue())["status"])

    def read_pair(self, summary):
        paths = {name: self.output / path for name, path in summary["reports"].items()}
        return paths, retirement_reports.load_retirement_report(paths["json"])

    def test_pair_totals_exact_filters_and_round_trip(self):
        code, summary, _ = self.invoke("--exclude", "node_modules", "--min-size-mib", "0.001")
        self.assertEqual(0, code)
        self.assertEqual("NO_CANDIDATES", summary["status"])
        paths, report = self.read_pair(summary)
        self.assertEqual(self.root, Path(report["root"]))
        markdown = paths["markdown"].read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), markdown)
        self.assertIn(retirement_reports.FOOTER, markdown)
        self.assertEqual({"node_modules": "excluded", ".venv": "below_minimum"},
                         {item["path"]: item["disposition"] for item in report["items"] if item["decision"] == "REGENERABLE"})
        sizes = {path: sum(p.stat().st_size for p in (self.root / path).rglob("*") if p.is_file())
                 for path in ("node_modules", ".venv")}
        self.assertEqual(sum(sizes.values()), report["totals"]["eligible_logical_bytes"])
        self.assertEqual(0, report["totals"]["offered_logical_bytes"])
        self.assertIn("node_modules", markdown)
        self.assertIn(".venv", markdown)
        self.assertEqual(2, self.invoke("--exclude", "NODE_MODULES")[0])
        self.assertEqual(2, self.invoke("--exclude", "node_modules", "--exclude", "NODE_MODULES")[0])

    @unittest.skipUnless(os.name == "nt", "Windows inherited file permissions")
    def test_windows_report_pair_publishes_without_reopening_staging_files(self):
        identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], encoding="oem")
        sid = next(csv.reader(identity.splitlines()))[1]
        original = retirement_reports._publish_pair
        before = self.snapshot()

        def publish_with_restricted_staging(body, store, root, run, *args, **kwargs):
            def acl(*arguments):
                subprocess.run(["icacls", str(run), *arguments], check=True, capture_output=True)

            staging = run / "preflight-staging"
            try:
                # Let the writer create and flush a file. Deny DELETE when that
                # file is reopened and deny FILE_DELETE_CHILD on its directory.
                acl("/grant", f"*{sid}:(OI)(IO)(RX,W)")
                acl("/deny", f"*{sid}:(OI)(IO)(DE)")
                acl("/deny", f"*{sid}:(DC)")
                with staging.open("xb") as stream:
                    stream.write(b"synthetic preflight")
                    stream.flush()
                    os.fsync(stream.fileno())
                with self.assertRaises(PermissionError) as denied:
                    os.replace(staging, run / "preflight-destination")
                self.assertEqual(5, denied.exception.winerror)
                paths = original(body, store, root, run, *args, **kwargs)
                validated = retirement_reports.load_retirement_report(store / paths["json"])
                self.assertEqual(body["report_id"], validated["report_id"])
                return paths
            finally:
                acl("/remove:d", f"*{sid}")
                staging.unlink(missing_ok=True)

        with patch.object(retirement_reports, "_publish_pair", publish_with_restricted_staging):
            code, summary, _ = self.invoke()
        self.assertEqual(0, code, summary)
        run = (self.output / summary["reports"]["json"]).parent
        self.assertEqual({"retirement.json", "retirement.md", "complete.json"},
                         {path.name for path in run.iterdir()})
        self.assertEqual(before, self.snapshot())
        self.assertEqual(b"private outside fixture", self.sentinel.read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows directory handle sharing")
    def test_windows_directory_pin_blocks_rename_until_released(self):
        directory = self.output / "original"
        moved = self.output / "moved"
        directory.mkdir()
        with pin_windows_directory(directory):
            with self.assertRaises(PermissionError):
                directory.rename(moved)
        directory.rename(moved)
        self.assertTrue(moved.is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows atomic rename")
    def test_windows_report_rename_refuses_destination_created_during_write(self):
        destination = self.output / "retirement.json"
        original = b"outside fixture sentinel"

        def create_destination_during_write():
            if any(self.output.glob(".staging-*")) and not destination.exists():
                destination.write_bytes(original)

        with self.assertRaisesRegex(retirement_reports.ReportOperationError, "atomically rename retirement.json") as failure:
            retirement_reports._commit_file(self.output, destination.name, b"replacement",
                                            create_destination_during_write, None)
        self.assertIsInstance(failure.exception.__cause__, FileExistsError)
        self.assertEqual(original, destination.read_bytes())

    def test_private_reader_rejects_corrupt_pair_wrong_schema_and_overlap(self):
        _, summary, _ = self.invoke()
        paths, report = self.read_pair(summary)
        values = [
            {**report, "schema_version": 91},
            {**report, "items": [*report["items"], {**report["items"][0], "path": "../outside"}]},
            {**report, "items": [*report["items"], report["items"][0]]},
            {**report, "items": [*report["items"], {
                **report["items"][0], "path": report["items"][0]["path"] + "/child",
                "display_path": report["items"][0]["path"] + "/child",
            }]},
        ]
        for value in values:
            value["digest"] = retirement_reports.report_digest(value)
            with self.assertRaises(InvalidPlan):
                retirement_reports.validate_retirement_report(value)
        paths["markdown"].write_text("Synthetic tamper", encoding="utf-8")
        with self.assertRaises(InvalidPlan):
            retirement_reports.load_retirement_report(paths["json"])
        paths["json"].write_bytes(b'{"partial":')
        with self.assertRaises(InvalidPlan):
            retirement_reports.load_retirement_report(paths["json"])

    def test_report_failure_is_incomplete_and_preserves_prior_pair(self):
        _, summary, _ = self.invoke()
        complete, _ = self.read_pair(summary)
        before = {name: path.read_bytes() for name, path in complete.items()}
        commit = retirement_reports._commit_file

        def disk_full(directory, name, *args):
            if name == "retirement.md":
                raise OSError(errno.ENOSPC, "simulated disk full", str(self.output))
            return commit(directory, name, *args)

        with patch.object(retirement_reports, "_commit_file", side_effect=disk_full):
            code, partial, _ = self.invoke()
        self.assertEqual(8, code)
        self.assertEqual("INCOMPLETE", partial["status"])
        self.assertEqual("REPORT_PAIR_WRITE_FAILED", partial["code"])
        self.assertEqual("OSError", partial["cause"]["exception"])
        self.assertEqual(errno.ENOSPC, partial["cause"]["errno"])
        self.assertNotIn(str(self.output), partial["message"])
        self.assertNotIn(str(self.output), partial["cause"]["operation"])
        self.assertNotIn("reports", partial)
        run = self.output / ("retirement-" + partial["report_id"])
        self.assertTrue((run / "retirement.json").is_file())
        self.assertFalse((run / "complete.json").exists())
        self.assertEqual(before, {name: path.read_bytes() for name, path in complete.items()})

    def test_concurrent_report_writers_produce_different_complete_pairs(self):
        def execute():
            return retire(str(self.root), output=str(self.output), deep=False, minimum="0", excludes=[],
                          show_paths=False, progress=lambda _: None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(execute)
            second = pool.submit(execute)
            results = [first.result(timeout=30), second.result(timeout=30)]
        self.assertNotEqual(results[0]["report_id"], results[1]["report_id"])
        for result in results:
            self.assertEqual("READY_FOR_MANUAL_REVIEW", self.read_pair(result)[1]["status"])

    def test_deep_and_schema_two_detect_same_size_content_edit(self):
        with patch.object(inventory, "open_observed", side_effect=AssertionError("fast payload open")):
            self.assertEqual(0, self.invoke()[0])
        plan = make_plan(self.root)
        _, first, _ = self.invoke("--deep")
        _, before = self.read_pair(first)
        file = self.root / "node_modules/pkg/index.js"
        saved = file.stat()
        file.write_bytes(b"x" * saved.st_size)
        os.utime(file, ns=(saved.st_atime_ns, saved.st_mtime_ns))
        _, second, _ = self.invoke("--deep")
        _, after = self.read_pair(second)
        get_digest = lambda body: next(item["observation"]["content_digest"] for item in body["items"]
                                       if item["path"] == "node_modules")
        self.assertNotEqual(get_digest(before), get_digest(after))
        self.assertEqual(after["totals"]["eligible_logical_bytes"], second["metrics"]["payload_bytes_hashed"])
        with self.assertRaises(InvalidPlan):
            validate_current(plan)

    def test_dirty_missing_and_staged_deleted_paths_stay_protected(self):
        protected = self.fixture.write("node_modules/pkg/local.js", "unique tracked file")
        self.fixture.commit("node_modules/pkg/local.js")
        subprocess.run(["git", "-C", str(self.root), "rm", "--cached", "node_modules/pkg/local.js"], check=True,
                       stdout=subprocess.DEVNULL)
        protected.unlink()
        code, summary, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertEqual([".venv"], [entry["path"] for entry in summary["candidates"]])
        self.assertGreaterEqual(summary["git_observations"]["tracked_unobserved"], 1)

    def test_oversize_and_changed_metadata_suppress_candidates(self):
        self.fixture.write("package.json", b" " * ((1 << 20) + 1))
        code, summary, _ = self.invoke()
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", summary["status"])
        self.assertEqual([], summary["candidates"])
        self.fixture.write("package.json", '{"name":"fixture"}')
        real = inventory.Collector.check_unchanged

        def drift(collector, *args):
            self.fixture.write("package.json", '{"name":"changed"}')
            return real(collector, *args)

        with patch.object(inventory.Collector, "check_unchanged", drift):
            self.assertEqual(3, self.invoke()[0])

    def test_unreadable_candidate_child_marks_observation_incomplete(self):
        scandir = inventory._scandir

        def inaccessible(path, expected):
            if path.name == "pkg":
                raise PermissionError("synthetic access failure")
            return scandir(path, expected)

        with patch.object(inventory, "_scandir", side_effect=inaccessible):
            code, summary, _ = self.invoke()
        self.assertEqual(3, code)
        self.assertEqual([], summary["candidates"])
        _, report = self.read_pair(summary)
        node = next(item for item in report["items"] if item["path"] == "node_modules")
        self.assertEqual("BLOCKED", node["decision"])
        self.assertIsNone(node["logical_bytes"])

    def test_verification_observes_present_missing_changed_and_git_drift(self):
        _, summary, _ = self.invoke()
        paths, _ = self.read_pair(summary)

        def observe():
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["verify", "--report", str(paths["json"]), "--format", "json"])
            self.assertEqual(0, code)
            return json.loads(out.getvalue())

        self.assertEqual({"PRESENT"}, {item["observation"] for item in observe()["observations"]})
        (self.root / ".venv").rename(self.root.parent / "moved-venv")
        self.fixture.write("node_modules/unique.txt", "synthetic local change")
        self.fixture.write("src/app.js", "synthetic Git change")
        subprocess.run(["git", "-C", str(self.root), "add", "src/app.js"], check=True)
        before = self.snapshot()
        result = observe()
        self.assertTrue(result["git_metadata_changed"])
        self.assertEqual({"node_modules": "CHANGED", ".venv": "MISSING_SINCE_SCAN"},
                         {entry["path"]: entry["observation"] for entry in result["observations"]})
        self.assertEqual(before, self.snapshot())
        self.assertEqual(0, result["actual_bytes_reclaimed_by_hibernator"])

    def test_verify_replacement_boundary_is_unknown_and_root_replacement_is_stale(self):
        _, summary, _ = self.invoke()
        paths, _ = self.read_pair(summary)
        replacement = (self.root / "node_modules").lstat().st_ino
        real = inventory.is_reparse_point
        out = io.StringIO()
        args = ["verify", "--report", str(paths["json"]), "--format", "json"]
        with redirect_stdout(out), patch("hibernator.retirement.is_reparse_point",
                                        side_effect=lambda info: info.st_ino == replacement or real(info)):
            self.assertEqual(3, main(args))
        result = json.loads(out.getvalue())
        self.assertIn({"path": "node_modules", "observation": "UNKNOWN"}, result["observations"])
        archived = self.root.parent / "moved-root"
        self.root.rename(archived)
        self.root.mkdir()
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(4, main(args))
        finally:
            self.root.rmdir()
            archived.rename(self.root)

    def test_module_cli_resolves_caller_relative_project_and_keeps_stderr_separate(self):
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, "-m", "hibernator", "retire", "--project", self.root.name,
                                 "--output", self.output.name, "--format", "json"],
                                cwd=self.root.parent, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual("READY_FOR_MANUAL_REVIEW", json.loads(result.stdout)["status"])
        self.assertIn("working-tree inventory", result.stderr)
        with patch("hibernator.retirement.collect_inventory", side_effect=KeyboardInterrupt):
            code, value, progress = self.invoke()
        self.assertEqual(130, code)
        self.assertEqual("INTERRUPTED", value["code"])
        self.assertIn("interrupted", progress)

    def test_cache_evidence_and_unknown_descendants(self):
        self.fixture.write("src/main.py", "VALUE = 1")
        self.fixture.write("src/__pycache__/main.cpython-312.pyc", b"synthetic bytecode")
        self.fixture.write("pytest.ini", "[pytest]\n")
        self.fixture.write(".pytest_cache/v/cache/nodeids", "[]")
        self.fixture.write("next.config.js", "throw Error('must never run');")
        self.fixture.write(".next/cache/webpack/client/0.pack", b"cache")
        code, first, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertTrue({".pytest_cache", "src/__pycache__", ".next/cache"} <=
                        {entry["path"] for entry in first["candidates"]})
        self.fixture.write(".pytest_cache/v/cache/local.txt", "unknown")
        self.fixture.write("src/__pycache__/other.cpython-312.pyc", "unassociated")
        self.fixture.write(".next/cache/webpack/client/export.zip", "unique archive")
        code, second, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertFalse({".pytest_cache", "src/__pycache__", ".next/cache"} &
                         {entry["path"] for entry in second["candidates"]})

    def test_unlocked_local_package_and_manager_conflict_do_not_qualify(self):
        self.fixture.write("node_modules/local/index.js", "local dependency payload")
        self.assertNotIn("node_modules", [item["path"] for item in self.invoke()[1]["candidates"]])
        self.fixture.write("yarn.lock", "# conflicting lockfile")
        _, summary, _ = self.invoke()
        _, report = self.read_pair(summary)
        item = next(item for item in report["items"] if item["path"] == "node_modules")
        self.assertIn("ambiguous", item["reason"])

    def test_python_unpinned_and_unverified_editable_environments_are_preserved(self):
        self.fixture.write("requirements.txt", "sample>=1.0\n")
        self.assertNotIn(".venv", [item["path"] for item in self.invoke()[1]["candidates"]])
        self.fixture.write("requirements.txt", "sample==1.0\n")
        self.fixture.write(".venv/Lib/site-packages/local-project.pth", "synthetic path")
        _, summary, _ = self.invoke()
        _, report = self.read_pair(summary)
        venv = next(item for item in report["items"] if item["path"] == ".venv")
        self.assertEqual("BLOCKED", venv["decision"])

    def test_vite_optimizer_is_included_once_inside_verified_npm_candidate(self):
        self.fixture.write("vite.config.js", "throw Error('must never run');")
        self.fixture.write("node_modules/.vite/deps/_metadata.json", "{}")
        self.fixture.write("node_modules/.vite/deps/chunk.js", "export {}")
        code, summary, _ = self.invoke()
        self.assertEqual(0, code)
        self.assertEqual({"node_modules", ".venv"}, {item["path"] for item in summary["candidates"]})
        expected = sum(path.stat().st_size for path in (self.root / "node_modules").rglob("*") if path.is_file())
        self.assertEqual(expected, next(item["logical_bytes"] for item in summary["candidates"] if item["path"] == "node_modules"))
        _, report = self.read_pair(summary)
        self.assertIn("Vite", report["technology_coverage"]["detected"])

    @unittest.skipIf(os.name == "nt", "POSIX filenames can contain control characters and Markdown punctuation")
    def test_hostile_names_render_inert_and_never_become_candidates(self):
        self.fixture.write("host\n\u202e[bad]/__pycache__/main.cpython-312.pyc", "synthetic")
        _, summary, stderr = self.invoke()
        paths, report = self.read_pair(summary)
        markdown = paths["markdown"].read_text(encoding="utf-8")
        self.assertNotIn("\u202e", markdown + stderr)
        self.assertFalse(any(entry["path"] and "host" in entry["path"] and entry["disposition"] == "offered"
                             for entry in report["items"]))
