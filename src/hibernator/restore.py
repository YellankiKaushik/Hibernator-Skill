from __future__ import annotations

from pathlib import Path

from .discovery import canonical_root
from .errors import HibernatorError


def restore_preview(project: str | Path) -> dict:
    root = canonical_root(project)
    commands: list[str] = []
    warnings: list[str] = []
    package = root / "package.json"
    if package.exists():
        lockfiles = [name for name in ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock") if (root / name).exists()]
        if len(lockfiles) > 1:
            warnings.append("Multiple Node lockfiles are present; choose the intended package manager after reviewing the project.")
        elif lockfiles and lockfiles[0] in ("package-lock.json", "npm-shrinkwrap.json"):
            commands.append("npm ci")
        elif lockfiles and lockfiles[0] == "pnpm-lock.yaml":
            commands.append("pnpm install --frozen-lockfile")
        elif lockfiles and lockfiles[0] == "yarn.lock":
            commands.append("yarn install --immutable")
        else:
            warnings.append("Node manifest found without a recognized lockfile; exact dependency versions may drift.")
            commands.append("Install dependencies with the project's chosen package manager after reviewing package.json.")
    if any((root / name).exists() for name in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py")):
        commands.extend(["python -m venv .venv", "Activate .venv, then install from the preserved project manifest."])
        if (root / "requirements.txt").exists():
            commands.append("python -m pip install -r requirements.txt")
        elif (root / "pyproject.toml").exists():
            commands.append("python -m pip install -e .")
        else:
            warnings.append("Python manifest is present but no pinned requirements.txt was found; exact recreation may not be possible.")
    if not commands:
        warnings.append("No supported dependency manifest was found. Restoration is unverified.")
    warnings.extend(["This preview does not run installers, access the network, or modify the project.", "Package managers may execute lifecycle scripts and may require private registries or credentials."])
    return {"schema_version": "1", "root": str(root), "status": "RESTORE_PREVIEW" if commands else "RESTORE_UNVERIFIED", "commands": commands, "warnings": warnings}
