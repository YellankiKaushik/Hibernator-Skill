"""Unwired descriptor-relative deletion prototype for synthetic fixtures only.

This module is intentionally not called by the CLI or production cleanup entry
point. Production deletion remains disabled pending platform-specific review.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path, PurePosixPath

from hibernator.discovery import canonical_root
from hibernator.errors import ApplyRefused, InvalidPlan
from hibernator.git_state import read_git_state
from hibernator.plans import validate_current, validate_plan


class UnsupportedDeletionPlatform(ApplyRefused):
    pass


def _open_directory_at(parent_fd: int, name: str, device: int) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or int(info.st_dev) != device:
            raise ApplyRefused("A path component is not a real directory on the selected filesystem.")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _entry_info(directory_fd: int, name: str) -> os.stat_result:
    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if stat.S_ISLNK(info.st_mode):
        raise ApplyRefused("A candidate contains a symbolic link; preserving the entire candidate.")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ApplyRefused("A candidate contains an unsupported filesystem entry.")
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise ApplyRefused("A candidate contains a hard-linked file; preserving the entire candidate.")
    return info


def _preflight(directory_fd: int, device: int) -> None:
    for name in os.listdir(directory_fd):
        info = _entry_info(directory_fd, name)
        if int(info.st_dev) != device:
            raise ApplyRefused("A candidate crosses a filesystem boundary.")
        if stat.S_ISDIR(info.st_mode):
            child_fd = _open_directory_at(directory_fd, name, device)
            try:
                _preflight(child_fd, device)
            finally:
                os.close(child_fd)


def _fsync_directory(directory_fd: int) -> None:
    # A failed directory flush is an uncertain outcome. Propagate it so callers
    # cannot report a durable completed deletion.
    os.fsync(directory_fd)


def _remove_contents(directory_fd: int, device: int) -> None:
    for name in os.listdir(directory_fd):
        info = _entry_info(directory_fd, name)
        if int(info.st_dev) != device:
            raise ApplyRefused("A candidate crosses a filesystem boundary during removal.")
        if stat.S_ISDIR(info.st_mode):
            child_fd = _open_directory_at(directory_fd, name, device)
            try:
                _remove_contents(child_fd, device)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)
        _fsync_directory(directory_fd)


def remove_test_fixture_candidate(plan: dict, relative_path: str) -> None:
    """Remove one candidate from a registered disposable fixture on POSIX.

    This function exists to exercise descriptor-relative removal. It is
    inaccessible to normal projects because it requires the test harness's
    in-memory root registration and exact synthetic fixture marker. It is not
    a production apply implementation.
    """
    if os.name != "posix" or not all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW")):
        raise UnsupportedDeletionPlatform("Descriptor-relative deletion is not implemented for this platform.")
    required_dir_fd = (os.open, os.stat, os.unlink, os.rmdir)
    if not all(function in os.supports_dir_fd for function in required_dir_fd) or os.listdir not in os.supports_fd:
        raise UnsupportedDeletionPlatform("Required directory-relative filesystem operations are unavailable.")

    from hibernator.cleaner import _TEST_OWNED_ROOTS  # Imported lazily to avoid a module cycle.

    validate_plan(plan)
    matches = [candidate for candidate in plan["candidates"] if candidate["path"] == relative_path]
    if len(matches) != 1:
        raise InvalidPlan("Candidate path is not selected exactly once in this plan.")
    candidate = matches[0]
    validate_current(plan)
    root = canonical_root(plan["root"])
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    marker = root / ".hibernator-test-owned"
    if (
        str(root) not in _TEST_OWNED_ROOTS
        or not root.parent.name.startswith("hibernator-test-")
        or temp_root not in root.parents
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != "HIBERNATOR SYNTHETIC TEST FIXTURE ONLY\n"
    ):
        raise ApplyRefused("Descriptor-relative removal is limited to a registered synthetic Git fixture.")
    read_git_state(root)

    rel = PurePosixPath(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or rel.is_absolute()
        or any(part in {"", ".", ".."} for part in rel.parts)
    ):
        raise InvalidPlan("Candidate path is not a normalized repository-relative path.")

    root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        root_flags |= os.O_CLOEXEC
    root_fd = os.open(root, root_flags)
    try:
        root_info = os.fstat(root_fd)
        if (int(root_info.st_dev), int(root_info.st_ino)) != (
            plan["root_identity"].get("device"), plan["root_identity"].get("inode")
        ):
            raise InvalidPlan("Project root identity changed after planning.")
        device = int(root_info.st_dev)
        parent_fd = os.dup(root_fd)
        try:
            for part in rel.parts[:-1]:
                child_fd = _open_directory_at(parent_fd, part, device)
                os.close(parent_fd)
                parent_fd = child_fd
            leaf = rel.parts[-1]
            candidate_fd = _open_directory_at(parent_fd, leaf, device)
            try:
                candidate_info = os.fstat(candidate_fd)
                identity = {
                    "device": int(candidate_info.st_dev),
                    "inode": int(candidate_info.st_ino),
                    "mode": int(candidate_info.st_mode),
                    "size": int(candidate_info.st_size),
                }
                if identity != candidate.get("identity"):
                    raise InvalidPlan("Candidate identity changed after planning.")
                _preflight(candidate_fd, device)
                _remove_contents(candidate_fd, device)
            finally:
                os.close(candidate_fd)
            os.rmdir(leaf, dir_fd=parent_fd)
            _fsync_directory(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        os.close(root_fd)
