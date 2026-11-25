from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def identity(path: Path) -> dict[str, int]:
    info = path.lstat()
    return {"device": int(info.st_dev), "inode": int(info.st_ino), "mode": int(info.st_mode), "size": int(info.st_size)}


def is_reparse_point(info: os.stat_result) -> bool:
    attrs = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def is_regular_nofollow(path: Path) -> bool:
    """Return true only for a regular, non-link/non-reparse directory entry."""
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and not is_reparse_point(info)


def is_directory_nofollow(path: Path) -> bool:
    """Return true only for a real directory entry, never a link or reparse point."""
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not is_reparse_point(info)


def tree_fingerprint(path: Path) -> str:
    """Hash metadata and regular file contents using the legacy schema-2 representation."""
    from .paths import open_observed, same_open_file
    from .rules import protected_secret

    rows: list[tuple] = []
    stack = [path]
    device = path.lstat().st_dev
    while stack:
        current = stack.pop()
        info = current.lstat()
        if info.st_dev != device or is_reparse_point(info) or stat.S_ISLNK(info.st_mode):
            raise OSError("An artifact directory changed or crossed a filesystem boundary.")
        if current != path:
            rel = current.relative_to(path).as_posix()
            rows.append((rel, int(info.st_mode), int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns)))
        if stat.S_ISDIR(info.st_mode) and not is_reparse_point(info):
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    child_info = child.lstat()
                    if child_info.st_dev != device or protected_secret(child.name):
                        raise OSError("An artifact entry is protected.")
                    if stat.S_ISLNK(child_info.st_mode) or is_reparse_point(child_info):
                        raise OSError("An artifact entry became a link or reparse point.")
                    elif stat.S_ISDIR(child_info.st_mode):
                        stack.append(child)
                    else:
                        file_hash = None
                        if stat.S_ISREG(child_info.st_mode):
                            hasher = hashlib.sha256()
                            with open_observed(child, child_info) as handle:
                                before = os.fstat(handle.fileno())
                                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                                    hasher.update(chunk)
                                after = os.fstat(handle.fileno())
                            if not same_open_file(before, after):
                                raise OSError(f"File changed while fingerprinting: {child}")
                            file_hash = hasher.hexdigest()
                        rows.append((child.relative_to(path).as_posix(), int(child_info.st_mode), int(child_info.st_dev), int(child_info.st_ino), int(child_info.st_size), int(child_info.st_mtime_ns), file_hash))
    rows.sort()
    return hashlib.sha256(canonical_json(rows)).hexdigest()


def logical_size(path: Path, *, boundary_device: int | None = None) -> int:
    total = 0
    if boundary_device is None:
        boundary_device = int(path.lstat().st_dev)
    stack = [path]
    while stack:
        current = stack.pop()
        info = current.lstat()
        if int(info.st_dev) != boundary_device:
            continue
        if stat.S_ISLNK(info.st_mode) or is_reparse_point(info):
            continue
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    child_info = child.lstat()
                    if int(child_info.st_dev) != boundary_device:
                        continue
                    if stat.S_ISDIR(child_info.st_mode) and not stat.S_ISLNK(child_info.st_mode) and not is_reparse_point(child_info):
                        stack.append(child)
                    elif stat.S_ISREG(child_info.st_mode):
                        total += child_info.st_size
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total
