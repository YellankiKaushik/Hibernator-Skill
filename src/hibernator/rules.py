"""Conservative, versioned positive-evidence artifact rules."""

from __future__ import annotations

import json
from pathlib import Path

from . import RULE_PACK_VERSION


RULES = [
    {"id": "python-venv-v1", "paths": [".venv", "venv"], "kind": "dependency", "context": ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py"], "restore": "Create a virtual environment, then install from the preserved project manifest."},
    {"id": "python-bytecode-v1", "paths": ["__pycache__"], "kind": "cache", "context": ["*.py"], "restore": "Python recreates bytecode when the project runs."},
    {"id": "node-dependencies-v1", "paths": ["node_modules"], "kind": "dependency", "requires": ["package.json"], "context": ["package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"], "restore": "Use the preserved package manager lockfile (for example npm ci, yarn install --immutable, or pnpm install --frozen-lockfile)."},
    {"id": "next-cache-v1", "paths": [".next/cache"], "kind": "cache", "context": ["next.config.js", "next.config.mjs", "next.config.ts", "package.json:next"], "restore": "Next.js recreates this build cache."},
    {"id": "vite-cache-v1", "paths": ["node_modules/.vite"], "kind": "cache", "context": ["vite.config.js", "vite.config.ts", "package.json:vite"], "restore": "Vite recreates its dependency optimization cache."},
    {"id": "pytest-cache-v1", "paths": [".pytest_cache"], "kind": "cache", "context": ["pytest.ini", "pyproject.toml", "setup.cfg"], "restore": "Pytest recreates its cache on the next run."},
]


def _marker_exists(marker: str, start: Path, project_root: Path) -> bool:
    current = start
    while True:
        if marker.startswith("package.json:"):
            package = current / "package.json"
            if package.is_file():
                try:
                    data = json.loads(package.read_text(encoding="utf-8"))
                    dependency = marker.split(":", 1)[1]
                    groups = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
                    if any(dependency in data.get(group, {}) for group in groups if isinstance(data.get(group, {}), dict)):
                        return True
                except (OSError, UnicodeError, json.JSONDecodeError):
                    pass
        elif "*" in marker:
            if any(current.glob(marker)):
                return True
        elif (current / marker).is_file():
            return True
        if current == project_root or current.parent == current:
            return False
        try:
            current.relative_to(project_root)
        except ValueError:
            return False
        current = current.parent


def rule_for(path: Path, project_root: Path) -> tuple[dict | None, str | None]:
    name = path.name
    for rule in RULES:
        if name not in rule["paths"]:
            continue
        required = rule.get("requires", [])
        if not all(_marker_exists(marker, path.parent, project_root) for marker in required):
            return None, "A required project manifest is missing; the directory name alone is insufficient evidence."
        context = rule["context"]
        if any(_marker_exists(marker, path.parent, project_root) for marker in context):
            return rule, None
        return None, "A regeneration marker or lockfile is missing; the directory name alone is insufficient evidence."
    return None, None


def technology_markers(root: Path) -> list[str]:
    found: set[str] = set()
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__"}
    for current, dirs, files in __import__("os").walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in skip and not (Path(current) / d).is_symlink()]
        names = set(files)
        if names & {"pyproject.toml", "requirements.txt", "Pipfile", "setup.py"}:
            found.add("Python")
        if "package.json" in names:
            found.add("Node.js")
            try:
                text = (Path(current) / "package.json").read_text(encoding="utf-8")
                if any(key in text for key in ('"react"', '"react-dom"')):
                    found.add("React")
                if '"next"' in text or any((Path(current) / marker).exists() for marker in ("next.config.js", "next.config.mjs", "next.config.ts")):
                    found.add("Next.js")
                if '"vite"' in text or any((Path(current) / marker).exists() for marker in ("vite.config.js", "vite.config.ts")):
                    found.add("Vite")
            except (OSError, UnicodeError):
                pass
    return sorted(found)
