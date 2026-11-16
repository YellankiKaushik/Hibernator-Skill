from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import ScanFailure, UnsupportedRoot
from .git_state import GitState, read_git_state
from .models import Item, ScanReport
from .rules import rule_for, technology_markers
from .util import identity, is_reparse_point, logical_size, tree_fingerprint, utc_now


SECRET_NAMES = {".env", ".env.local", ".env.development", ".env.production", "id_rsa", "id_ed25519", "credentials.json"}
DATA_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".dump", ".bak", ".onnx", ".pt", ".pth", ".safetensors", ".bin", ".parquet", ".csv", ".zip", ".tar", ".gz"}
USER_DIR_NAMES = {"uploads", "datasets", "dataset", "models", "model", "data", "checkpoints", "weights"}
SOURCE_DIRS = {"src", "source", "app", "tests", "test", "docs", "scripts"}
SKIP_SCAN = {".git", ".hg", ".svn"}


def canonical_root(value: str | os.PathLike[str]) -> Path:
    supplied = Path(value).expanduser()
    try:
        supplied_info = supplied.lstat()
        if stat.S_ISLNK(supplied_info.st_mode) or is_reparse_point(supplied_info):
            raise UnsupportedRoot("Project root cannot be a symlink or reparse point.")
        root = supplied.resolve(strict=True)
    except OSError as exc:
        raise UnsupportedRoot("Project root does not exist or cannot be resolved.") from exc
    if not root.is_dir() or root.is_symlink():
        raise UnsupportedRoot("Project root must be an existing real directory, not a link.")
    if root.parent == root:
        raise UnsupportedRoot("Filesystem root cannot be used as a project.")
    try:
        if root == Path.home().resolve(strict=True):
            raise UnsupportedRoot("The user home directory cannot be used as a project root.")
    except OSError:
        pass
    return root


def _tracked_under(path: Path, root: Path, git: GitState) -> bool:
    rel = path.relative_to(root).as_posix().rstrip("/")
    prefix = rel + "/"
    return any(item == rel or item.startswith(prefix) for item in git.tracked)


def _danger_reason(path: Path, candidate: Path, root: Path) -> str | None:
    try:
        def fail_on_walk_error(error):
            raise error

        for current, dirs, files in os.walk(path, topdown=True, onerror=fail_on_walk_error, followlinks=False):
            current_path = Path(current)
            try:
                if current_path.stat().st_dev != candidate.stat().st_dev:
                    return "Candidate crosses a filesystem boundary."
                for name in dirs + files:
                    child = current_path / name
                    info = child.lstat()
                    if stat.S_ISLNK(info.st_mode) or is_reparse_point(info):
                        return f"Contains a symlink or reparse point ({child.relative_to(root).as_posix()}); preserving the whole directory."
                    if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                        return f"Contains a hard-linked file ({child.relative_to(root).as_posix()}); preserving the whole directory."
                    if child.name == ".git":
                        return f"Contains a nested Git boundary ({child.relative_to(root).as_posix()})."
                    lower = child.name.lower()
                    if lower in SECRET_NAMES or lower.startswith(".env."):
                        return f"Contains a secret-like file ({child.relative_to(root).as_posix()})."
                    if lower in USER_DIR_NAMES:
                        return f"Contains a user-data directory ({child.relative_to(root).as_posix()})."
                    if child.suffix.lower() in DATA_SUFFIXES:
                        return f"Contains local data or an unverified download ({child.relative_to(root).as_posix()})."
                    rel_parts = child.relative_to(candidate).parts
                    if candidate.name == "__pycache__" and stat.S_ISREG(info.st_mode) and child.suffix.lower() != ".pyc":
                        return f"Contains a non-bytecode file in __pycache__ ({child.relative_to(root).as_posix()})."
                    if candidate.name == "__pycache__" and stat.S_ISDIR(info.st_mode):
                        return f"Contains an unrecognized directory in __pycache__ ({child.relative_to(root).as_posix()})."
                    if candidate.name == ".pytest_cache":
                        allowed_cache_file = child.name in {"README.md", "CACHEDIR.TAG"} or (
                            len(rel_parts) == 3 and rel_parts[:2] == ("v", "cache") and rel_parts[2] in {"nodeids", "lastfailed", "stepwise"}
                        )
                        allowed_cache_dir = stat.S_ISDIR(info.st_mode) and rel_parts in {("v",), ("v", "cache")}
                        if not allowed_cache_file and not allowed_cache_dir:
                            return f"Contains an unrecognized pytest cache entry ({child.relative_to(root).as_posix()})."
                    if stat.S_ISDIR(info.st_mode) and info.st_dev != candidate.stat().st_dev:
                        return "Candidate crosses a filesystem boundary."
                    if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                        return f"Contains an unsupported filesystem entry ({child.relative_to(root).as_posix()}); preserving the directory."
            except OSError:
                return f"Unable to inspect every child under {path.relative_to(root).as_posix()}; preserving it."
            dirs[:] = [d for d in dirs if d not in SKIP_SCAN]
    except OSError:
        return "Unable to inspect every descendant; preserving the candidate."
    return None


def _walk_dirs(root: Path):
    def fail_on_walk_error(error):
        raise error

    for current, dirs, _files in os.walk(root, topdown=True, onerror=fail_on_walk_error, followlinks=False):
        base = Path(current)
        dirs[:] = [name for name in dirs if name not in SKIP_SCAN and not (base / name).is_symlink() and not is_reparse_point((base / name).lstat())]
        for name in list(dirs):
            yield base / name


def scan(project: str | os.PathLike[str]) -> ScanReport:
    root = canonical_root(project)
    git = read_git_state(root)
    try:
        root_identity = identity(root)
        total = logical_size(root)
        tech = technology_markers(root)
    except OSError as exc:
        raise ScanFailure(f"Unable to inspect project completely: {exc}") from exc

    items: list[Item] = []
    candidate_roots: list[Path] = []
    candidates = []
    for path in _walk_dirs(root):
        rule, missing = rule_for(path, root)
        if rule:
            candidates.append((path, rule))
        elif missing:
            rel = path.relative_to(root).as_posix()
            items.append(Item(rel, "unknown", "REVIEW", logical_size(path), missing, restore_hint="No verified recreation procedure."))

    for path, rule in sorted(candidates, key=lambda pair: (len(pair[0].parts), str(pair[0]))):
        if any(parent == path or parent in path.parents for parent in candidate_roots):
            continue
        rel = path.relative_to(root).as_posix()
        why = None
        if _tracked_under(path, root, git):
            why = "Contains Git-tracked content; tracked artifacts are always preserved."
        elif any((path / marker).exists() for marker in (".git",)):
            why = "Contains a nested Git boundary."
        else:
            why = _danger_reason(path, path, root)
        try:
            size = logical_size(path)
            item_id = identity(path)
            tree_hash = tree_fingerprint(path) if not why else None
        except OSError:
            size, item_id, tree_hash = 0, {}, None
            why = "Unable to inspect candidate completely; preserving it."
        decision = "KEEP" if why and "tracked" in why.lower() else ("BLOCKED" if why else "REGENERABLE")
        if why:
            items.append(Item(rel, rule["kind"], decision, size, why, rule["id"], rule["restore"], identity=item_id, tree_digest=tree_hash))
        else:
            candidate_roots.append(path)
            items.append(Item(rel, rule["kind"], decision, size, "Recognized artifact with matching project manifest/lockfile; no protected descendants detected.", rule["id"], rule["restore"], identity=item_id, tree_digest=tree_hash))

    # Explicitly surface top-level unknowns and local data without traversing links.
    for child in root.iterdir():
        if child.name in SKIP_SCAN or any(parent == child or parent in child.parents for parent in candidate_roots):
            continue
        if any(item.path == child.name for item in items):
            continue
        low = child.name.lower()
        try:
            size = logical_size(child)
        except OSError:
            size = 0
        if low in SECRET_NAMES or low.startswith(".env."):
            items.append(Item(child.name, "local-data", "KEEP", size, "Secret-like content is protected."))
        elif low in USER_DIR_NAMES or child.suffix.lower() in DATA_SUFFIXES:
            items.append(Item(child.name, "download" if child.suffix.lower() in DATA_SUFFIXES else "local-data", "REVIEW", size, "Local data or download has no verified recovery source."))
        elif child.name in SOURCE_DIRS or _tracked_under(child, root, git):
            items.append(Item(child.name, "source", "KEEP", size, "Source, configuration, or Git-tracked content is preserved."))
        else:
            items.append(Item(child.name, "unknown", "REVIEW", size, "Unknown project content is preserved by default."))

    if identity(root) != root_identity:
        raise ScanFailure("Project root identity changed during scan; no result is trusted.")
    items.sort(key=lambda item: item.path.casefold())
    return ScanReport("1", str(root), str(git.root), utc_now(), tech, total, "logical bytes (file lengths; links not followed)", git.snapshot, git.tracked_snapshot, items)
