"""Exercise both entry points from a wheel installed in a fresh environment."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.helpers import node_fixture


def smoke(*, module_only: bool = False) -> None:
    assert importlib.util.find_spec("hibernator.approval") is None
    assert importlib.util.find_spec("hibernator.secure_remove") is None
    package_skill = Path(sys.prefix) / ".agents" / "skills" / "hibernator" / "SKILL.md"
    source_skill = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "hibernator" / "SKILL.md"
    assert package_skill.read_text(encoding="utf-8") == source_skill.read_text(encoding="utf-8")
    console = Path(sys.executable).parent / ("hibernator.exe" if os.name == "nt" else "hibernator")
    module = [sys.executable, "-m", "hibernator"]
    installed = module if module_only else [str(console)]

    def run(prefix, *args, expected=0):
        result = subprocess.run([*prefix, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, timeout=45)
        assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
        return result.stdout

    fixture = node_fixture()
    try:
        root = str(fixture.root)
        fixture.write("package-lock.json", '{"lockfileVersion":3,"packages":{"node_modules/pkg":{"version":"1.0.0","resolved":"https://registry.npmjs.org/pkg/-/pkg-1.0.0.tgz"}}}')
        fixture.write(".env", "SYNTHETIC=private")
        fixture.write("uploads/local.db", "synthetic unique data")
        reports = fixture.root.parent / "reports"
        reports.mkdir(mode=0o700)
        sentinel = fixture.root.parent / "outside-sentinel"
        sentinel.write_bytes(b"synthetic sentinel")

        def project_observation():
            status = subprocess.check_output(["git", "--no-optional-locks", "-C", root, "status", "--porcelain=v1", "-z"])
            files = {path.relative_to(fixture.root).as_posix():
                     (path.stat().st_mode, path.read_bytes() if path.is_file() else None)
                     for path in fixture.root.rglob("*")}
            return status, files, sentinel.read_bytes()

        before = project_observation()

        def project_command(prefix, *args, expected=0):
            result = run(prefix, *args, expected=expected)
            assert before == project_observation(), (args, "project or sentinel changed")
            return result

        arguments = ("retire", "--project", root, "--output", str(reports), "--format", "json")
        module_result = json.loads(project_command(module, *arguments))
        console_result = module_result if module_only else json.loads(project_command(installed, *arguments))
        assert module_result["candidates"] == console_result["candidates"]
        assert module_result["status"] == console_result["status"] == "READY_FOR_MANUAL_REVIEW"
        match = run(module, "retire", "--help")
        assert match == run(installed, "retire", "--help")
        print(match, end="")
        report = str(reports / console_result["reports"]["json"])
        plan = str(fixture.root.parent / "plan.json")
        project_command(installed, "doctor")
        project_command(installed, "rules", "list")
        project_command(installed, "scan", "--project", root, "--format", "json")
        project_command(installed, "plan", "--project", root, "--output", plan)
        project_command(installed, "restore", "--project", root, "--dry-run")
        project_command(installed, "report", "--retirement-file", report)
        observed = json.loads(project_command(installed, "verify", "--report", report, "--format", "json"))
        assert observed["observations"] == [{"path": "node_modules", "observation": "PRESENT"}]
        refusal = json.loads(project_command(installed, "apply", "--plan", plan, "--format", "json", expected=5))
        assert refusal["status"] == "APPLY_UNSUPPORTED"
        entry_points = "Installed module" if module_only else "Installed module and console"
        print(f"{entry_points} retirement, packaged skill, legacy commands and verify passed.")
    finally:
        fixture.close()


if __name__ == "__main__":
    smoke(module_only=sys.argv[1:] == ["--module-only"])
