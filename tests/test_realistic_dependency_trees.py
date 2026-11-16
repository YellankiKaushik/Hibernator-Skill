from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from hibernator.discovery import scan
from hibernator.plans import make_plan
from tests.helpers import GitFixture


class RealisticDependencyTreeTests(unittest.TestCase):
    def test_node_modules_safe_fixture_measures_eligible_bytes(self):
        fixture = GitFixture()
        sentinel = fixture.root.parent / "external-sentinel.txt"
        sentinel.write_bytes(b"synthetic external sentinel\n")
        sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        try:
            fixture.write("package.json", '{"dependencies":{"react":"synthetic"}}\n')
            fixture.write("package-lock.json", '{"lockfileVersion":3,"packages":{}}\n')
            fixture.commit("package.json", "package-lock.json")
            files = {
                "node_modules/react/package.json": '{"name":"react","version":"18.0.0"}\n',
                "node_modules/react/index.js": "module.exports = {};\n",
                "node_modules/@scope/runtime/package.json": '{"name":"@scope/runtime","version":"1.0.0"}\n',
                "node_modules/@scope/runtime/dist/index.js": "export const ready = true;\n",
                "node_modules/@scope/runtime/README.md": "synthetic package documentation\n",
            }
            for path, content in files.items():
                fixture.write(path, content)
            expected_bytes = sum(len(content.encode("utf-8")) for content in files.values())

            report = scan(fixture.root)
            item = next(entry for entry in report.items if entry.path == "node_modules")
            plan = make_plan(fixture.root)

            self.assertEqual("REGENERABLE", item.decision)
            self.assertEqual(expected_bytes, item.logical_bytes)
            self.assertEqual(expected_bytes, plan["estimated_logical_bytes"])
            self.assertEqual(["node_modules"], [entry["path"] for entry in plan["candidates"]])
            self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
        finally:
            fixture.close()

    def test_node_modules_common_package_data_directory_is_reported_as_false_block(self):
        fixture = GitFixture()
        sentinel = fixture.root.parent / "external-sentinel.txt"
        sentinel.write_bytes(b"synthetic external sentinel\n")
        sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        try:
            fixture.write("package.json", '{"dependencies":{"geo-data":"synthetic"}}\n')
            fixture.write("package-lock.json", '{"lockfileVersion":3,"packages":{}}\n')
            fixture.commit("package.json", "package-lock.json")
            fixture.write("node_modules/geo-data/package.json", '{"name":"geo-data"}\n')
            fixture.write("node_modules/geo-data/data/countries.json", '{"US":"United States"}\n')

            report = scan(fixture.root)
            item = next(entry for entry in report.items if entry.path == "node_modules")
            plan = make_plan(fixture.root)

            self.assertEqual("BLOCKED", item.decision)
            self.assertIn("user-data directory", item.reason)
            self.assertEqual(0, plan["estimated_logical_bytes"])
            self.assertEqual([], plan["candidates"])
            self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
        finally:
            fixture.close()

    def test_python_venv_safe_fixture_measures_eligible_bytes(self):
        fixture = GitFixture()
        sentinel = fixture.root.parent / "external-sentinel.txt"
        sentinel.write_bytes(b"synthetic external sentinel\n")
        sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        try:
            fixture.write("pyproject.toml", "[project]\nname = 'fixture'\n")
            fixture.commit("pyproject.toml")
            if os.name == "nt":
                site = ".venv/Lib/site-packages"
                interpreter = ".venv/Scripts/python.exe"
            else:
                site = f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
                interpreter = ".venv/bin/python"
            files = {
                ".venv/pyvenv.cfg": "home = synthetic-runtime\ninclude-system-site-packages = false\n",
                interpreter: b"synthetic interpreter placeholder\n",
                f"{site}/sample_pkg/__init__.py": "VALUE = 1\n",
                f"{site}/sample_pkg-1.0.dist-info/METADATA": "Name: sample-pkg\nVersion: 1.0\n",
            }
            for path, content in files.items():
                fixture.write(path, content)
            expected_bytes = sum(
                len(content if isinstance(content, bytes) else content.encode("utf-8"))
                for content in files.values()
            )

            report = scan(fixture.root)
            item = next(entry for entry in report.items if entry.path == ".venv")
            plan = make_plan(fixture.root)

            self.assertEqual("REGENERABLE", item.decision)
            self.assertEqual(expected_bytes, item.logical_bytes)
            self.assertEqual(expected_bytes, plan["estimated_logical_bytes"])
            self.assertEqual([".venv"], [entry["path"] for entry in plan["candidates"]])
            self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
        finally:
            fixture.close()

    def test_python_venv_editable_install_pth_is_reported_as_false_block(self):
        fixture = GitFixture()
        sentinel = fixture.root.parent / "external-sentinel.txt"
        sentinel.write_bytes(b"synthetic external sentinel\n")
        sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        try:
            fixture.write("pyproject.toml", "[project]\nname = 'fixture'\n")
            fixture.commit("pyproject.toml")
            site = (
                ".venv/Lib/site-packages"
                if os.name == "nt"
                else f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
            )
            fixture.write(".venv/pyvenv.cfg", "home = synthetic-runtime\n")
            fixture.write(f"{site}/__editable__.fixture.pth", "synthetic source path\n")

            report = scan(fixture.root)
            item = next(entry for entry in report.items if entry.path == ".venv")
            plan = make_plan(fixture.root)

            self.assertEqual("BLOCKED", item.decision)
            self.assertIn("local data or an unverified download", item.reason)
            self.assertEqual(0, plan["estimated_logical_bytes"])
            self.assertEqual([], plan["candidates"])
            self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
        finally:
            fixture.close()

    def test_python_venv_verified_local_editable_install_pth_is_regenerable(self):
        fixture = GitFixture()
        sentinel = fixture.root.parent / "external-sentinel.txt"
        sentinel.write_bytes(b"synthetic external sentinel\n")
        sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
        try:
            fixture.write("pyproject.toml", "[project]\nname = 'fixture'\n")
            fixture.commit("pyproject.toml")
            site = (
                ".venv/Lib/site-packages"
                if os.name == "nt"
                else f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
            )
            pth = f"{site}/__editable__.fixture-1.0.pth"
            finder = f"{site}/__editable___fixture_1_0_finder.py"
            metadata = f"{site}/fixture-1.0.dist-info"
            files = {
                ".venv/pyvenv.cfg": "home = synthetic-runtime\n",
                pth: "import __editable___fixture_1_0_finder; __editable___fixture_1_0_finder.install()\n",
                finder: "MAPPING = {}\n",
                f"{metadata}/METADATA": "Name: fixture\nVersion: 1.0\n",
                f"{metadata}/direct_url.json": json.dumps({"url": fixture.root.as_uri(), "dir_info": {"editable": True}}) + "\n",
            }
            for path, content in files.items():
                fixture.write(path, content)
            expected_bytes = sum(len(content.encode("utf-8")) for content in files.values())

            report = scan(fixture.root)
            item = next(entry for entry in report.items if entry.path == ".venv")
            plan = make_plan(fixture.root)

            self.assertEqual("REGENERABLE", item.decision)
            self.assertEqual(expected_bytes, item.logical_bytes)
            self.assertEqual([".venv"], [entry["path"] for entry in plan["candidates"]])
            self.assertEqual(expected_bytes, plan["estimated_logical_bytes"])
            self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
        finally:
            fixture.close()

    def test_python_venv_editable_install_pth_pointing_outside_root_stays_blocked(self):
        fixture = GitFixture()
        with tempfile.TemporaryDirectory(prefix="hibernator-external-editable-") as external:
            external_source = Path(external)
            (external_source / "pyproject.toml").write_text("[project]\nname='external'\n", encoding="utf-8")
            sentinel = external_source / "sentinel.txt"
            sentinel.write_bytes(b"outside source sentinel\n")
            sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
            try:
                fixture.write("pyproject.toml", "[project]\nname = 'fixture'\n")
                fixture.commit("pyproject.toml")
                site = (
                    ".venv/Lib/site-packages"
                    if os.name == "nt"
                    else f".venv/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
                )
                metadata = f"{site}/fixture-1.0.dist-info"
                fixture.write(".venv/pyvenv.cfg", "home = synthetic-runtime\n")
                fixture.write(
                    f"{site}/__editable__.fixture-1.0.pth",
                    "import __editable___fixture_1_0_finder; __editable___fixture_1_0_finder.install()\n",
                )
                fixture.write(f"{site}/__editable___fixture_1_0_finder.py", "MAPPING = {}\n")
                fixture.write(f"{metadata}/METADATA", "Name: fixture\nVersion: 1.0\n")
                fixture.write(
                    f"{metadata}/direct_url.json",
                    json.dumps({"url": external_source.as_uri(), "dir_info": {"editable": True}}) + "\n",
                )

                item = next(entry for entry in scan(fixture.root).items if entry.path == ".venv")
                self.assertEqual("BLOCKED", item.decision)
                self.assertIn("local data or an unverified download", item.reason)
                self.assertEqual(sentinel_before, hashlib.sha256(sentinel.read_bytes()).hexdigest())
            finally:
                fixture.close()


if __name__ == "__main__":
    unittest.main()
