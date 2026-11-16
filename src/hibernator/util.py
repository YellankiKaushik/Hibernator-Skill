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


def tree_fingerprint(path: Path) -> str:
    """Hash names, types, identities, and sizes without following links."""
    rows: list[tuple] = []
    stack = [path]
    while stack:
        current = stack.pop()
        info = current.lstat()
        if current != path:
            rel = current.relative_to(path).as_posix()
            rows.append((rel, int(info.st_mode), int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns)))
        if stat.S_ISDIR(info.st_mode) and not is_reparse_point(info):
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    child_info = child.lstat()
                    if stat.S_ISLNK(child_info.st_mode) or is_reparse_point(child_info):
                        rows.append((child.relative_to(path).as_posix(), int(child_info.st_mode), int(child_info.st_dev), int(child_info.st_ino), int(child_info.st_size), int(child_info.st_mtime_ns)))
                    elif stat.S_ISDIR(child_info.st_mode):
                        stack.append(child)
                    else:
                        file_hash = None
                        if stat.S_ISREG(child_info.st_mode):
                            hasher = hashlib.sha256()
                            with child.open("rb") as handle:
                                before = os.fstat(handle.fileno())
                                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                                    hasher.update(chunk)
                                after = os.fstat(handle.fileno())
                            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                                raise OSError(f"File changed while fingerprinting: {child}")
                            file_hash = hasher.hexdigest()
                        rows.append((child.relative_to(path).as_posix(), int(child_info.st_mode), int(child_info.st_dev), int(child_info.st_ino), int(child_info.st_size), int(child_info.st_mtime_ns), file_hash))
    rows.sort()
    return hashlib.sha256(canonical_json(rows)).hexdigest()


def logical_size(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or is_reparse_point(info):
            continue
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    child_info = child.lstat()
                    if stat.S_ISDIR(child_info.st_mode) and not stat.S_ISLNK(child_info.st_mode) and not is_reparse_point(child_info):
                        stack.append(child)
                    elif stat.S_ISREG(child_info.st_mode):
                        total += child_info.st_size
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total
