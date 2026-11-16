from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from hibernator.cleaner import _register_test_owned_root, _unregister_test_owned_root


class GitFixture:
    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="hibernator-test-")
        self.root = Path(self._temp.name) / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "core.autocrlf", "false"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "maintenance.auto", "false"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "gc.auto", "0"], check=True)
        _register_test_owned_root(self.root)
        self.closed = False

    def write(self, rel: str, content: str | bytes = "synthetic\n") -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def commit(self, *paths: str) -> None:
        if paths:
            subprocess.run(["git", "-C", str(self.root), "add", *paths], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "fixture"], check=True)

    def mark_test_owned(self) -> None:
        self.write(".hibernator-test-owned", "HIBERNATOR SYNTHETIC TEST FIXTURE ONLY\n")

    def close(self) -> None:
        if not self.closed:
            _unregister_test_owned_root(self.root)
            self._temp.cleanup()
            self.closed = True


def node_fixture() -> GitFixture:
    fixture = GitFixture()
    fixture.write("package.json", '{"name":"fixture","scripts":{"test":"node test.js"}}\n')
    fixture.write("package-lock.json", '{"name":"fixture","lockfileVersion":3,"packages":{}}\n')
    fixture.write("src/app.js", "export const app = true;\n")
    fixture.commit("package.json", "package-lock.json", "src/app.js")
    fixture.write("node_modules/pkg/index.js", "// synthetic dependency\n")
    fixture.write("node_modules/pkg/package.json", '{"name":"pkg","version":"1.0.0"}\n')
    return fixture


def make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        return False
    command = f'mklink /J "{link}" "{target}"'
    result = subprocess.run(["cmd.exe", "/c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0
