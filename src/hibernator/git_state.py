from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import ScanFailure, UnsupportedRoot


@dataclass(frozen=True)
class GitState:
    root: Path
    tracked: frozenset[str]
    snapshot: str
    tracked_snapshot: str


def _git(root: Path, *args: str) -> bytes:
    try:
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "-C", str(root), *args],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
    except FileNotFoundError as exc:
        raise ScanFailure("Git is required; install Git and retry.") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", "replace").strip()
        raise ScanFailure(f"Git could not read repository state: {message or 'unknown Git error'}") from exc
    return result.stdout


def read_git_state(project: Path) -> GitState:
    try:
        raw_root = _git(project, "rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
        git_root = Path(raw_root).resolve(strict=True)
    except ScanFailure as exc:
        if "not a git repository" in str(exc).lower():
            raise UnsupportedRoot("Project root is not a Git working tree.") from exc
        raise
    except (UnicodeError, OSError) as exc:
        raise UnsupportedRoot("Project root is not a supported Git working tree.") from exc
    if git_root != project:
        raise UnsupportedRoot("Select the Git repository root explicitly; repository parents and subdirectories are not accepted.")
    tracked_raw = _git(project, "ls-files", "-z", "--cached")
    tracked = frozenset(os_path.decode("utf-8", "surrogateescape") for os_path in tracked_raw.split(b"\0") if os_path)
    status = _git(project, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
    index = _git(project, "ls-files", "--stage", "-z")
    unstaged = _git(project, "diff", "--raw", "--no-ext-diff", "--no-textconv")
    staged = _git(project, "diff", "--cached", "--raw", "--no-ext-diff", "--no-textconv")
    try:
        head = _git(project, "rev-parse", "--verify", "HEAD")
    except ScanFailure:
        head = b"UNBORN"
    snapshot = hashlib.sha256(b"\0".join((head.strip(), tracked_raw, status))).hexdigest()
    tracked_snapshot = hashlib.sha256(b"\0".join((head.strip(), index, unstaged, staged))).hexdigest()
    return GitState(git_root, tracked, snapshot, tracked_snapshot)
