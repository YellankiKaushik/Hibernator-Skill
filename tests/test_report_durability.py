from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from hibernator.reports import save_report
from tests.helpers import temporary_directory


class ReportDurabilityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "directory fsync is a POSIX journal guarantee")
    def test_report_flushes_file_and_parent_directory(self):
        with temporary_directory(prefix="hibernator-report-durability-") as tmp:
            real_fsync = os.fsync
            flushed: list[tuple[int, bool]] = []

            def record_fsync(fd: int) -> None:
                flushed.append((fd, stat.S_ISDIR(os.fstat(fd).st_mode)))
                real_fsync(fd)

            with patch("hibernator.reports.os.fsync", side_effect=record_fsync):
                output = save_report(
                    {"report_id": "a" * 32, "schema_version": "1", "report_type": "scan"},
                    directory=Path(tmp),
                )
            self.assertTrue(output.is_file())
            self.assertEqual(2, len(flushed), "one file flush and one directory-entry flush are required")
            self.assertFalse(flushed[0][1], "first fsync must be the report file")
            self.assertTrue(flushed[1][1], "second fsync must be the parent directory")


if __name__ == "__main__":
    unittest.main()
