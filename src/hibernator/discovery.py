from __future__ import annotations

import os
import re
import stat
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from .errors import ScanFailure, UnsupportedRoot
from .git_state import GitState, read_git_state
from .models import Item, ScanReport
from .paths import canonical_root as _canonical_root, directory_chain, local_path, open_observed
from .rules import protected_secret, rule_for, technology_markers
from .util import identity, is_directory_nofollow, is_reparse_point, is_regular_nofollow, tree_fingerprint, utc_now


DATA_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".dump", ".bak", ".onnx", ".pt", ".pth", ".safetensors", ".bin", ".parquet", ".csv", ".zip", ".tar", ".gz"}
USER_DIR_NAMES = {"uploads", "datasets", "dataset", "models", "model", "data", "checkpoints", "weights"}
SOURCE_DIRS = {"src", "source", "app", "tests", "test", "docs", "scripts"}
SKIP_SCAN = {".git", ".hg", ".svn"}


def canonical_root(value: str | os.PathLike[str]) -> Path:
    root = _canonical_root(value)
    if is_reparse_point(root.lstat()):
        raise UnsupportedRoot("Project root is a reparse point.")
    return root


def _tracked_under(path: Path, root: Path, git: GitState) -> bool:
    return git.protects(path.relative_to(root).as_posix())


def _same_device(path: Path, device: int) -> bool:
    try:
        return int(path.lstat().st_dev) == device
    except OSError:
        return False


def _verified_editable_pth(path: Path, candidate: Path, root: Path) -> bool:
    """Recognize only pip's generated editable-install .pth backed by local metadata."""
    if path.suffix.lower() != ".pth" or not is_regular_nofollow(path):
        return False
    if "site-packages" not in {part.lower() for part in path.parts}:
        return False
    try:
        lines = [line.strip() for line in _small_metadata(path).splitlines() if line.strip()]
    except (OSError, UnicodeError):
        return False
    if len(lines) != 1:
        return False
    match = re.fullmatch(r"import (__editable__[A-Za-z0-9_]+_finder); \1\.install\(\)", lines[0])
    if not match:
        return False
    finder = path.parent / f"{match.group(1)}.py"
    if not is_regular_nofollow(finder):
        return False
    editable_name = path.stem.removeprefix("__editable__.").replace("_", "-").casefold()
    for metadata in path.parent.glob("*.dist-info"):
        if not is_directory_nofollow(metadata):
            continue
        metadata_name = metadata.name[: -len(".dist-info")].replace("_", "-").casefold()
        if metadata_name != editable_name:
            continue
        direct_url = metadata / "direct_url.json"
        if not is_regular_nofollow(direct_url):
            continue
        try:
            value = json.loads(_small_metadata(direct_url))
            parsed = urlparse(value.get("url", ""))
            if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
                continue
            if value.get("dir_info", {}).get("editable") is not True:
                continue
            source = local_path(url2pathname(parsed.path))
            try:
                source.relative_to(root)
            except ValueError:
                continue
            directory_chain(source)
            try:
                source.relative_to(candidate)
            except ValueError:
                if any(is_regular_nofollow(source / name) for name in ("pyproject.toml", "setup.py")):
                    return True
                continue
            # The editable source itself is under the venv candidate; deleting
            # the environment would remove the source too, so do not exempt it.
            continue
        except (OSError, ValueError, RecursionError, AttributeError, TypeError, UnsupportedRoot):
            continue
    return False


def _small_metadata(path: Path) -> str:
    info = path.lstat()
    if info.st_size > 64 << 10:
        raise OSError("Editable installation metadata is too large.")
    with open_observed(path, info) as stream:
        content = stream.read((64 << 10) + 1)
        if len(content) != info.st_size:
            raise OSError("Editable installation metadata changed.")
    return content.decode("utf-8")


def _danger_reason(path: Path, candidate: Path, root: Path) -> str | None:
    try:
        root_device = int(root.lstat().st_dev)
        candidate_info = candidate.lstat()
        if stat.S_ISLNK(candidate_info.st_mode) or is_reparse_point(candidate_info):
            return "Candidate is a symlink or reparse point; preserving it."
        if int(candidate_info.st_dev) != root_device:
            return "Candidate crosses a filesystem boundary."

        def fail_on_walk_error(error):
            raise error

        for current, dirs, files in os.walk(path, topdown=True, onerror=fail_on_walk_error, followlinks=False):
            current_path = Path(current)
            try:
                if not _same_device(current_path, int(candidate_info.st_dev)):
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
                    if protected_secret(lower):
                        return f"Contains a secret-like file ({child.relative_to(root).as_posix()})."
                    if lower in USER_DIR_NAMES:
                        return f"Contains a user-data directory ({child.relative_to(root).as_posix()})."
                    verified_editable_metadata = (
                        candidate.name.lower() in {".venv", "venv"}
                        and child.suffix.lower() == ".pth"
                        and _verified_editable_pth(child, candidate, root)
                    )
                    if child.suffix.lower() in DATA_SUFFIXES and not verified_editable_metadata:
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
                    if stat.S_ISDIR(info.st_mode) and not _same_device(child, int(candidate_info.st_dev)):
                        return "Candidate crosses a filesystem boundary."
                    if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                        return f"Contains an unsupported filesystem entry ({child.relative_to(root).as_posix()}); preserving the directory."
            except OSError:
                return f"Unable to inspect every child under {path.relative_to(root).as_posix()}; preserving it."
            dirs[:] = [d for d in dirs if d not in SKIP_SCAN]
    except OSError:
        return "Unable to inspect every descendant; preserving the candidate."
    return None


def scan(project: str | os.PathLike[str]) -> ScanReport:
    from .inventory import legacy_tree_metadata

    root = canonical_root(project)
    git = read_git_state(root)
    try:
        root_identity = identity(root)
        sizes, directories, markers = legacy_tree_metadata(root, reparse=is_reparse_point, same_device=_same_device)
        total = sizes[root]
        tech = technology_markers(root, observed=markers)
    except OSError as exc:
        raise ScanFailure(f"Unable to inspect project completely: {exc}") from exc

    items: list[Item] = []
    candidate_roots: list[Path] = []
    protected_roots: list[Path] = []
    candidates = []
    for path in directories:
        rule, missing = rule_for(path, root)
        if rule:
            candidates.append((path, rule))
        elif missing:
            rel = path.relative_to(root).as_posix()
            items.append(Item(rel, "unknown", "REVIEW", sizes.get(path, 0), missing, restore_hint="No verified recreation procedure."))

    for path, rule in sorted(candidates, key=lambda pair: (len(pair[0].parts), str(pair[0]))):
        if any(parent == path or parent in path.parents for parent in candidate_roots):
            continue
        rel = path.relative_to(root).as_posix()
        why = None
        if any(parent in path.parents for parent in protected_roots):
            why = "A containing artifact is protected."
        elif _tracked_under(path, root, git):
            why = "Contains Git-tracked content; tracked artifacts are always preserved."
        elif any((path / marker).exists() for marker in (".git",)):
            why = "Contains a nested Git boundary."
        else:
            why = _danger_reason(path, path, root)
        try:
            size = sizes.get(path, 0)
            item_id = identity(path)
            tree_hash = tree_fingerprint(path) if not why else None
        except OSError:
            size, item_id, tree_hash = 0, {}, None
            why = "Unable to inspect candidate completely; preserving it."
        decision = "KEEP" if why and "tracked" in why.lower() else ("BLOCKED" if why else "REGENERABLE")
        if why:
            protected_roots.append(path)
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
        size = sizes.get(child, 0)
        if protected_secret(low):
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
