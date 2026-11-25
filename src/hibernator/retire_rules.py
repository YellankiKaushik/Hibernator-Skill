"""Bounded positive evidence and descendant checks for retirement artifacts."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .paths import directory_chain, open_observed, same_open_file, stamp
from .restore import NODE_LOCKFILES, _node_command, recovery_hint
from .rules import protected_secret
from .util import is_reparse_point


ARTIFACTS = {
    "node_modules": "node-dependencies-v2",
    ".venv": "python-venv-v2",
    "venv": "python-venv-v2",
    "__pycache__": "python-bytecode-v2",
    ".pytest_cache": "pytest-cache-v2",
}
PROTECTED_DIRECTORIES = {
    "uploads", "datasets", "dataset", "models", "model", "data", "checkpoints",
    "weights", "assets", "backups", "backup", "logs", "downloads", "vendor",
}
REVIEW_DIRECTORIES = {
    "build", "dist", "target", ".next", ".dart_tool", ".gradle", "obj", "bin",
    ".ruff_cache", ".mypy_cache", ".turbo", ".parcel-cache", ".tox", ".nox",
}
PROTECTED_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".dump", ".bak", ".onnx", ".pt", ".pth", ".safetensors",
    ".bin", ".parquet", ".csv", ".zip", ".tar", ".gz", ".mp4", ".mov", ".psd", ".patch",
    ".whl", ".msi", ".pdf", ".dmg", ".7z", ".pkl", ".rds", ".dbf", ".jks",
}
MARKERS = {
    *NODE_LOCKFILES, "package.json", "pyproject.toml", "requirements.txt", "Pipfile",
    "setup.py", "setup.cfg", "pytest.ini", "next.config.js", "next.config.mjs",
    "next.config.ts", "vite.config.js", "vite.config.ts", "Cargo.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", "pubspec.yaml", ".npmrc", ".yarnrc.yml",
}
NODE_SUFFIXES = {
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".json", ".map", ".md", ".txt", ".css",
    ".scss", ".html", ".wasm", ".node", ".yml", ".yaml", ".mts", ".cts", ".svg",
}
PYTHON_SUFFIXES = {".py", ".pyi", ".pyc", ".pyd", ".so", ".txt", ".json", ".typed"}
PYTHON_DIST_FILES = {"METADATA", "RECORD", "WHEEL", "INSTALLER", "REQUESTED", "entry_points.txt", "top_level.txt"}
DEPENDENCY_GROUPS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
LIMITS = {"package-lock.json": 16 << 20, "npm-shrinkwrap.json": 16 << 20, "package.json": 1 << 20}


class EvidenceError(ValueError):
    """Missing or ambiguous regeneration evidence."""


def _unique_json(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise EvidenceError("Metadata has duplicate JSON fields.")
    return result


@dataclass
class Evidence:
    root: Path
    files: dict[Path, os.stat_result] = field(default_factory=dict)
    read_files: dict[Path, os.stat_result] = field(default_factory=dict)
    cache: dict[Path, str] = field(default_factory=dict)
    json_cache: dict[Path, dict] = field(default_factory=dict)
    bytes_read: int = 0
    malformed: bool = False
    mount_boundaries: set[Path] = field(default_factory=set)

    def remember(self, path: Path, info: os.stat_result) -> None:
        if len(self.files) >= 4096:
            raise EvidenceError("Manifest observation budget was exceeded.")
        self.files[path] = info

    def present(self, path: Path) -> bool:
        info = self.files.get(path)
        return bool(info and path not in self.mount_boundaries and stat.S_ISREG(info.st_mode)
                    and not is_reparse_point(info) and info.st_nlink == 1)

    def text(self, path: Path) -> str:
        if path not in self.cache:
            limit = LIMITS.get(path.name, 256 << 10)
            if (not self.present(path) or self.files[path].st_size > limit
                    or self.bytes_read + self.files[path].st_size > 64 << 20
                    or protected_secret(path.name)):
                self.malformed = True
                raise EvidenceError("Required metadata is unsafe, missing or exceeds the read limit.")
            try:
                before = self.files[path]
                with open_observed(path, before) as handle:
                    data = handle.read(min(limit, before.st_size) + 1)
                    self.bytes_read += len(data)
                    if len(data) != before.st_size or not same_open_file(before, os.fstat(handle.fileno())):
                        raise OSError("Evidence changed.")
                self.cache[path] = data.decode("utf-8-sig")
                self.read_files[path] = before
            except (OSError, UnicodeError) as exc:
                self.malformed = True
                raise EvidenceError("A required metadata file could not be read consistently.") from exc
        return self.cache[path]

    def json(self, path: Path) -> dict:
        if path not in self.json_cache:
            try:
                value = json.loads(self.text(path), object_pairs_hook=_unique_json)
                if not isinstance(value, dict):
                    raise EvidenceError("Expected an object in project metadata.")
            except (ValueError, RecursionError) as exc:
                self.malformed = True
                raise EvidenceError("Required JSON evidence is malformed or exceeds parsing limits.") from exc
            self.json_cache[path] = value
        return self.json_cache[path]

    def unchanged(self) -> bool:
        for path, expected in self.files.items():
            directory_chain(path.parent)
            if stamp(expected) != stamp(path.lstat()):
                return False
        return True


def artifact_rule(relative: str) -> str | None:
    if relative == ".next/cache" or relative.endswith("/.next/cache"):
        return "next-cache-v2"
    return ARTIFACTS.get(relative.rsplit("/", 1)[-1])


def _dependencies(manifest: dict) -> dict:
    deps = {}
    for key in DEPENDENCY_GROUPS:
        group = manifest.get(key, {})
        if not isinstance(group, dict):
            raise EvidenceError("A package manifest has an invalid dependency list.")
        deps.update(group)
    return deps


def _manifest_path(directory: Path, root: Path, name: str) -> str:
    return (directory / name).relative_to(root).as_posix()


def _framework(evidence: Evidence, directory: Path, name: str) -> list[str]:
    inputs = [f"{name}.config.{ext}" for ext in ("js", "mjs", "ts") if evidence.present(directory / f"{name}.config.{ext}")]
    manifest = directory / "package.json"
    if manifest in evidence.files and name in _dependencies(evidence.json(manifest)):
        inputs.append("package.json")
    return inputs


def _npm_context(evidence: Evidence, directory: Path) -> tuple[Path, str, dict]:
    project = directory
    while project.is_relative_to(evidence.root):
        locks = [name for name in NODE_LOCKFILES if project / name in evidence.files]
        if locks:
            break
        project = project.parent
    else:
        raise EvidenceError("A matching package-manager lockfile is missing.")
    if len(locks) != 1 or locks[0] not in {"package-lock.json", "npm-shrinkwrap.json"}:
        raise EvidenceError("The package-manager lockfile is ambiguous or is a guarded Yarn/pnpm layout.")
    for location in {directory, project}:
        if location / ".npmrc" in evidence.files or location / ".yarnrc.yml" in evidence.files:
            raise EvidenceError("Private or custom package-manager configuration may affect recovery.")
        manifest_file = location / "package.json"
        if manifest_file not in evidence.files:
            raise EvidenceError("The enclosing Node package manifest is missing.")
        manifest = evidence.json(manifest_file)
        manager = manifest.get("packageManager")
        if manager is not None and (not isinstance(manager, str) or not re.fullmatch(r"npm@\d+\.\d+\.\d+(?:\+[a-zA-Z0-9.]+)?", manager)):
            raise EvidenceError("The selected package manager conflicts with the lockfile.")
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9A-Za-z.^~<>=*| +-]+", value)
               for value in _dependencies(manifest).values()):
            raise EvidenceError("Local, private, workspace or unverified dependency inputs require review.")
    lock = evidence.json(project / locks[0])
    packages = lock.get("packages")
    if lock.get("lockfileVersion") not in (2, 3) or not isinstance(packages, dict):
        raise EvidenceError("The npm lockfile lacks a supported package index.")
    owning_manifest = evidence.json(project / "package.json")
    if lock.get("name") is not None and lock["name"] != owning_manifest.get("name"):
        raise EvidenceError("The package lockfile has a conflicting project name.")
    if directory != project:
        relative = directory.relative_to(project).as_posix()
        workspaces = owning_manifest.get("workspaces", [])
        if (
            not isinstance(workspaces, list) or len(workspaces) > 128
            or not any(isinstance(pattern, str) and re.fullmatch(r"[\w./*-]{1,160}", pattern)
                       and ".." not in pattern.split("/") and "**" not in pattern
                       and pattern.count("/") == relative.count("/")
                       and fnmatch.fnmatchcase(relative, pattern) for pattern in workspaces)
            or relative not in packages
        ):
            raise EvidenceError("The ancestor lockfile does not establish workspace membership.")
    return project, locks[0], packages


def _distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class RuleEvidence:
    rule: str
    recovery: dict
    points: list[str]
    project: Path
    npm_packages: dict = field(default_factory=dict)
    npm_prefix: str = ""
    python_packages: dict[str, str] = field(default_factory=dict)
    python_seen: set[str] = field(default_factory=set)
    python_unowned: set[str] = field(default_factory=set)
    vite: bool = False
    source_names: set[str] = field(default_factory=set)
    node_seen: set[str] = field(default_factory=set)

    def finish(self, evidence: Evidence, candidate: Path) -> str | None:
        if self.rule == "node-dependencies-v2":
            if not self.node_seen:
                return "The dependency tree lacks an installed package with matching lock evidence."
            for key in self.node_seen:
                record = self.npm_packages[key]
                installed = evidence.json(candidate.parent / key.removeprefix(self.npm_prefix) / "package.json")
                name = key.rsplit("node_modules/", 1)[-1]
                if installed.get("name") != name or installed.get("version") != record["version"]:
                    return "An installed package manifest conflicts with the lockfile."
        if self.rule == "python-venv-v2" and (
            self.python_seen != set(self.python_packages) or self.python_unowned - self.python_seen
        ):
            return "Installed Python distributions or import roots do not match the pinned inventory."
        return None


def rule_evidence(rule: str, candidate: Path, evidence: Evidence, sibling_sources: set[str]) -> RuleEvidence:
    root = evidence.root
    directory = candidate.parent if rule != "next-cache-v2" else candidate.parent.parent
    relative = directory.relative_to(root).as_posix()
    args = {}
    inputs = []
    points = []
    if rule == "node-dependencies-v2":
        project, lock, packages = _npm_context(evidence, directory)
        relative = project.relative_to(root).as_posix()
        prefix = "" if project == directory else directory.relative_to(project).as_posix() + "/"
        args.update(npm_packages=packages, npm_prefix=prefix, vite=bool(_framework(evidence, directory, "vite")))
        inputs = [_manifest_path(project, root, lock), _manifest_path(directory, root, "package.json")]
        if project != directory:
            inputs.append(_manifest_path(project, root, "package.json"))
        points = ["Enclosing Node manifest and one compatible npm lockfile.", "Installed package locations, names and versions checked against lock entries."]
        hint = f"Review lifecycle scripts and preserved inputs before using {_node_command(lock)}."
    elif rule == "python-venv-v2":
        requirements = directory / "requirements.txt"
        if not evidence.present(requirements):
            raise EvidenceError("The virtual environment needs a verified local pinned requirements.txt.")
        pins = {}
        for line in evidence.text(requirements).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9+_.!-]+)", line)
            if not match or _distribution(match[1]) in pins:
                raise EvidenceError("Python dependency inputs are unpinned, local, or ambiguous.")
            pins[_distribution(match[1])] = match[2]
        if not pins:
            raise EvidenceError("A pinned Python dependency set is missing.")
        args["python_packages"] = pins
        inputs = [requirements.relative_to(root).as_posix()]
        points = ["Virtual-environment marker and pinned local requirements.", "Distribution versions checked against preserved pins."]
        hint = "Use the original Python version, create a new virtual environment and install the preserved requirements."
    elif rule == "python-bytecode-v2":
        if not sibling_sources:
            raise EvidenceError("The bytecode cache has no associated Python source in the enclosing directory.")
        args["source_names"] = sibling_sources
        points = ["Associated Python source in the enclosing directory."]
        hint = "Python regenerates bytecode on a later run."
    elif rule == "pytest-cache-v2":
        for name, pattern in (("pytest.ini", r"\[pytest\]"), ("setup.cfg", r"\[tool:pytest\]"),
                              ("pyproject.toml", r"\[tool\.pytest(?:\.ini_options)?\]")):
            file = directory / name
            if file in evidence.files and re.search(r"(?m)^\s*" + pattern + r"\s*(?:#.*)?$", evidence.text(file)):
                inputs = [file.relative_to(root).as_posix()]
                break
        if not inputs:
            raise EvidenceError("The enclosing directory has no verified pytest configuration.")
        points = ["Pytest section found in enclosing configuration.", "Only recognized pytest entries."]
        hint = "Pytest regenerates the cache on a later run."
    else:
        markers = _framework(evidence, directory, "next")
        if not markers:
            raise EvidenceError("The enclosing application has no verified Next.js marker.")
        inputs = [_manifest_path(directory, root, name) for name in markers]
        points = ["Next.js context and allowlisted cache structure."]
        hint = "Next.js regenerates this cache on a later build."
    return RuleEvidence(rule, recovery_hint(inputs, relative, hint), points, directory, **args)


def protected_entry(path: Path, is_directory: bool) -> str | None:
    if protected_secret(path.name):
        return "Secret-like content is protected."
    if path.name.lower() in PROTECTED_DIRECTORIES:
        return "A local data or asset boundary is protected."
    if not is_directory and path.suffix.lower() in PROTECTED_SUFFIXES:
        return "Local data, archives, patches and unverified downloads are protected."
    return None


def _node_descendant(parts: tuple[str, ...], directory: bool, context: RuleEvidence) -> str | None:
    name = parts[-1]
    if parts[0] == ".vite":
        if context.vite and (
            directory and (parts == (".vite",) or len(parts) == 2 and re.fullmatch(r"deps(?:_temp_[a-f0-9]+)?", name))
            or not directory and len(parts) == 3 and re.fullmatch(r"deps(?:_temp_[a-f0-9]+)?", parts[1])
            and (Path(name).suffix.lower() in {".js", ".map"} or name in {"package.json", "_metadata.json"})
        ):
            return None
        return "Vite optimizer entries require verified Vite context and cache layout."
    if len(parts) == 1 and not directory and name == ".package-lock.json":
        return None
    boundaries = [0] + [i + 1 for i, part in enumerate(parts) if part == "node_modules"]
    offset = boundaries[-1]
    if offset == len(parts):
        return None if directory else "The dependency layout has an unexpected file."
    package_end = offset + (2 if parts[offset].startswith("@") else 1)
    if package_end > len(parts):
        return None if directory else "An npm scope contains an unverified file."
    key = context.npm_prefix + "node_modules/" + "/".join(parts[:package_end])
    record = context.npm_packages.get(key)
    if not isinstance(record, dict) or not isinstance(record.get("version"), str) or record.get("link"):
        return "An installed package lacks a matching non-local lockfile entry."
    try:
        url = urlsplit(record.get("resolved", ""))
        if url.scheme != "https" or url.netloc != "registry.npmjs.org" or not url.path.endswith(".tgz"):
            return "The lockfile refers to a private, local or unverified source."
    except (AttributeError, TypeError, ValueError):
        return "The package provenance is malformed."
    context.node_seen.add(key)
    if directory or name.upper().split(".")[0] in {"LICENSE", "LICENCE", "README", "NOTICE", "CHANGELOG"}:
        return None
    if Path(name).suffix.lower() in NODE_SUFFIXES and not name.startswith("."):
        return None
    return "An installed package contains an unrecognized payload type."


def _python_descendant(parts: tuple[str, ...], directory: bool, ctx: RuleEvidence) -> str | None:
    name = parts[-1]
    lower = [part.lower() for part in parts]
    if parts == ("pyvenv.cfg",) and not directory:
        return None
    if lower[0] in {"bin", "scripts"} and len(parts) == 2 and not directory:
        stem = name.lower().removesuffix(".exe")
        if re.fullmatch(r"python(?:w|\d+(?:\.\d+)?)?|pip(?:\d+(?:\.\d+)?)?", stem) or stem in {
            "activate", "activate.bat", "activate.ps1", "activate.csh", "activate.fish", "deactivate.bat",
        }:
            return None
    if directory and lower[0] in {"lib", "lib64", "include", "scripts", "bin"} and (
        len(parts) == 1 or len(parts) == 2 and re.fullmatch(r"python\d+(?:\.\d+)?", lower[-1])
    ):
        return None
    if "site-packages" in lower and lower[0] in {"lib", "lib64"}:
        inner = parts[lower.index("site-packages") + 1:]
        if not inner and directory:
            return None
        if inner and inner[0].endswith(".dist-info"):
            distribution, _, version = inner[0][:-10].rpartition("-")
            package = _distribution(distribution)
            if ctx.python_packages.get(package) == version:
                if inner[1:] == ("METADATA",) and not directory:
                    ctx.python_seen.add(package)
                if len(inner) == 1 and directory or len(inner) == 2 and not directory and name in PYTHON_DIST_FILES:
                    return None
        elif inner:
            import_name = _distribution(inner[0].split(".")[0])
            ctx.python_unowned.add(import_name)
            if not name.startswith(".") and (directory or Path(name).suffix.lower() in PYTHON_SUFFIXES):
                return None
    return "The virtual environment contains an unverified install or payload."


def descendant_issue(path: Path, parts: tuple[str, ...], directory: bool, context: RuleEvidence) -> str | None:
    protected = protected_entry(path, directory)
    if protected:
        return protected
    name = path.name
    if context.rule == "node-dependencies-v2":
        return _node_descendant(parts, directory, context)
    if context.rule == "python-venv-v2":
        return _python_descendant(parts, directory, context)
    if context.rule == "python-bytecode-v2":
        if len(parts) == 1 and not directory:
            match = re.fullmatch(r"(.+)\.(?:cpython|pypy)-\d+(?:\.opt-[12])?\.pyc", name)
            if match and match[1] + ".py" in context.source_names:
                return None
        return "The bytecode cache has an unexpected entry or missing corresponding source."
    if context.rule == "pytest-cache-v2":
        if directory and parts in {("v",), ("v", "cache")}:
            return None
        if not directory and (parts in {("README.md",), ("CACHEDIR.TAG",), (".gitignore",)}
                              or parts[:-1] == ("v", "cache") and name in {"nodeids", "lastfailed", "stepwise"}):
            return None
        return "The pytest cache contains an unexpected entry."
    if parts[0] in {"webpack", "swc"} and (directory or path.suffix.lower() in {".pack", ".json", ".cache"}):
        return None
    return "The Next.js cache contains an unexpected entry."
