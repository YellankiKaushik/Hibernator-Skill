from __future__ import annotations

import os
from pathlib import Path

from .discovery import canonical_root


NODE_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock")
PYTHON_MANIFESTS = ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py")
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}


def _manifest_directories(root: Path) -> tuple[list[Path], list[Path]]:
    node: list[Path] = []
    python: list[Path] = []

    def fail_on_walk_error(error: OSError) -> None:
        raise error

    for current, dirs, files in os.walk(root, topdown=True, onerror=fail_on_walk_error, followlinks=False):
        base = Path(current)
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not (base / name).is_symlink()]
        if "package.json" in files:
            node.append(base)
        if any(name in files for name in PYTHON_MANIFESTS):
            python.append(base)
    return sorted(node), sorted(python)


def _relative(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return "." if rel == "." else rel


def _nearest_node_lock(project: Path, root: Path) -> tuple[Path | None, list[str]]:
    current = project
    while True:
        lockfiles = [name for name in NODE_LOCKFILES if (current / name).is_file()]
        if lockfiles:
            return current, lockfiles
        if current == root:
            return None, []
        current = current.parent


def _node_command(lockfile: str) -> str:
    if lockfile in ("package-lock.json", "npm-shrinkwrap.json"):
        return "npm ci"
    if lockfile == "pnpm-lock.yaml":
        return "pnpm install --frozen-lockfile"
    return "yarn install --immutable"


def restore_preview(project: str | Path) -> dict:
    root = canonical_root(project)
    commands: list[str] = []
    warnings: list[str] = []
    node_projects, python_projects = _manifest_directories(root)

    # Resolve each package manifest to its nearest ancestor lockfile. Workspace
    # packages consequently share one suggestion, while independently locked
    # nested projects get their own working-directory hint.
    node_groups: dict[Path, set[str]] = {}
    for project_dir in node_projects:
        lock_root, lockfiles = _nearest_node_lock(project_dir, root)
        if lock_root is None:
            warnings.append(
                f"Node manifest at {_relative(project_dir, root)} has no recognized lockfile in this directory or its ancestors; exact versions may drift."
            )
            commands.append(
                f"Review package.json at {_relative(project_dir, root)} and use that project's chosen package manager."
            )
            continue
        if len(lockfiles) > 1:
            warnings.append(
                f"Multiple Node lockfiles are present at {_relative(lock_root, root)}; choose the intended package manager after reviewing the workspace."
            )
            continue
        node_groups.setdefault(lock_root, set()).add(lockfiles[0])

    for lock_root, lockfiles in sorted(node_groups.items()):
        if len(lockfiles) != 1:
            warnings.append(
                f"Node manifests under {_relative(lock_root, root)} resolve to conflicting lockfile managers; review the monorepo layout manually."
            )
            continue
        manager_command = _node_command(next(iter(lockfiles)))
        commands.append(f"Node project {_relative(lock_root, root)}: {manager_command}")
        if any(project_dir != lock_root and project_dir.is_relative_to(lock_root) for project_dir in node_projects):
            warnings.append(
                f"Nested Node manifests use the nearest lockfile at {_relative(lock_root, root)}; verify that this directory is the intended workspace root before installing."
            )

    for project_dir in python_projects:
        rel = _relative(project_dir, root)
        present = {name for name in PYTHON_MANIFESTS if (project_dir / name).is_file()}
        commands.append(f"Python project {rel}: python -m venv .venv")
        commands.append(f"Python project {rel}: activate .venv before installing")
        if "requirements.txt" in present:
            commands.append(f"Python project {rel}: python -m pip install -r requirements.txt")
        elif "pyproject.toml" in present:
            commands.append(f"Python project {rel}: python -m pip install -e .")
        else:
            warnings.append(
                f"Python project {rel} has no supported pinned requirements.txt or pyproject.toml; exact recreation may not be possible."
            )

    if not commands:
        warnings.append("No supported dependency manifest was found. Restoration is unverified.")
    warnings.extend([
        "This preview does not run installers, access the network, or modify the project.",
        "Package managers may execute lifecycle scripts and may require private registries or credentials.",
    ])
    return {
        "schema_version": "1",
        "root": str(root),
        "status": "RESTORE_PREVIEW" if commands else "RESTORE_UNVERIFIED",
        "commands": commands,
        "warnings": warnings,
    }
