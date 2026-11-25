from __future__ import annotations

import os
import unittest
from pathlib import Path

from hibernator.errors import UnsupportedRoot
from hibernator.paths import local_path, relative_path


class PathTests(unittest.TestCase):
    def test_report_paths_reject_reserved_windows_names_on_all_platforms(self):
        for name in (
            "nUl.txt", "PRN .log", "CONIN$", "conout$.json", "aux", "Com\u00b9.bin",
            "lpt\u00b3", "file.", "file ", "x:stream", "a\x1fb", "a?b", "a[b]", "a\\b",
        ):
            with self.subTest(name=name):
                self.assertFalse(relative_path(f"cache/{name}/file"))
        for name in ("console.log", "com10", "lpt0", "name with spaces", ".cache"):
            with self.subTest(name=name):
                self.assertTrue(relative_path(f"cache/{name}/file"))

    @unittest.skipUnless(os.name == "nt", "Windows local paths use Windows component rules")
    def test_windows_local_paths_reject_reserved_intermediate_components(self):
        for name in ("CON.txt", "lpt\u00b2", "directory.", "directory ", "a:stream", "a|b"):
            with self.subTest(name=name):
                with self.assertRaises(UnsupportedRoot):
                    local_path(f"C:/safe/{name}/output.json")
        self.assertEqual(Path("C:/safe/.cache/com10.json"), local_path("C:/safe/.cache/com10.json"))
