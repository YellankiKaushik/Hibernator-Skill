"""One bounded working-tree pass for read-only retirement."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .errors import ScanFailure, UnsupportedRoot
from .git_state import GitReader, GitState
from .models import RetirementItem
from .paths import directory_chain, local_mounts, observed_entry, open_observed, path_key, relative_path, same_open_file, stamp
from .retire_rules import (
    MARKERS, REVIEW_DIRECTORIES, Evidence, EvidenceError, RuleEvidence, artifact_rule,
    descendant_issue, protected_entry, rule_evidence,
)
from .util import is_reparse_point, utc_now


MAX_ENTRIES = 1_000_000
MAX_DIRECTORY_ENTRIES = 100_000
MAX_DEPTH = 128
MAX_ITEMS = 20_000
GIT_BOUNDARIES = {".git", ".hg", ".svn"}
NOOP = lambda message: None


def _fingerprint_row(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"


def inert_path(value: str) -> str:
    return value if relative_path(value) else json.dumps(value, ensure_ascii=True)


@dataclass
class Inventory:
    root: Path
    started: str = field(default_factory=utc_now)
    ended: str = ""
    root_stamp: tuple[int, ...] = ()
    git: GitState | None = None
    tracked_observation: str | None = None
    tracked_unobserved: int = 0
    tracked_stat_differences: int = 0
    technologies: set[str] = field(default_factory=set)
    items: list[RetirementItem] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=lambda: {
        "primary_passes": 0, "files": 0, "directories": 0, "entry_stats": 0,
        "known_logical_bytes": 0, "unmeasured_boundaries": 0, "git_subprocesses": 0,
        "git_seconds": 0.0, "evidence_bytes_read": 0, "payload_bytes_hashed": 0,
        "phase_seconds": {},
    })

    def incomplete(self, reason: str) -> None:
        if reason not in self.reasons and len(self.reasons) < 24:
            self.reasons.append(reason)


@dataclass
class Artifact:
    path: Path
    relative: str
    rule_id: str
    observed: os.stat_result
    context: RuleEvidence | None = None
    reason: str = ""
    blocked: bool = False
    digest: object = field(default_factory=hashlib.sha256)
    files: list[tuple[Path, os.stat_result]] = field(default_factory=list)

    def protect(self, reason: str) -> None:
        if not self.blocked:
            self.reason = reason
        self.blocked = True
        self.files.clear()


class InventoryLimit(ScanFailure):
    pass


@contextmanager
def _scandir(path: Path, expected: os.stat_result):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if not observed_entry(expected, os.fstat(fd)):
                raise OSError("Directory changed before enumeration.")
            with os.scandir(fd) as entries:
                yield entries
            if not observed_entry(expected, os.fstat(fd)):
                raise OSError("Directory changed while being enumerated.")
        finally:
            os.close(fd)
    else:
        current = path.lstat()
        if not observed_entry(expected, current) or is_reparse_point(current):
            raise OSError("Directory changed before enumeration.")
        with os.scandir(path) as entries:
            yield entries
        if not observed_entry(expected, path.lstat()):
            raise OSError("Directory changed while being enumerated.")


class Collector:
    def __init__(self, root: Path, *, deep: bool, progress: Callable[[str], None]):
        self.inventory = Inventory(root)
        self.evidence = Evidence(root)
        self.deep = deep
        self.progress = progress
        self.metrics = self.inventory.metrics
        self.root = root
        self.tracked_rows: list[tuple[str, tuple[int, ...]]] = []
        self.artifacts: list[tuple[Artifact, RetirementItem]] = []
        self.item_paths: dict[str, RetirementItem] = {}
        self.last_progress = time.monotonic()
        self.device = 0
        self.seen = 0
        self.mounts: set[Path] = set()

    @contextmanager
    def phase(self, name: str):
        self.progress(name)
        start = time.monotonic()
        try:
            yield
        finally:
            self.metrics["phase_seconds"][name] = round(time.monotonic() - start, 6)

    def collect(self) -> Inventory:
        reader = GitReader(self.root)
        with self.phase("root and Git validation"):
            root_info = directory_chain(self.root)
            self.device = root_info.st_dev
            self.inventory.root_stamp = stamp(root_info)
            try:
                self.mounts = local_mounts()
                self.evidence.mount_boundaries = self.mounts
                self.inventory.git = reader.retirement_state()
            except ScanFailure as exc:
                self.inventory.incomplete(str(exc))
            except OSError:
                self.inventory.incomplete("The local mount boundaries could not be established.")
        if self.inventory.git is not None:
            try:
                with self.phase("working-tree inventory"):
                    self.metrics["primary_passes"] = 1
                    self.visit(self.root, root_info, 0, None, False)
                with self.phase("classification and consistency check"):
                    self.finish(reader, root_info)
            except (OSError, UnsupportedRoot, InventoryLimit):
                self.inventory.incomplete("The tree changed, was inaccessible, or exceeded the observation budget.")
            if self.deep and not self.inventory.reasons:
                with self.phase("eligible payload hashing"):
                    self.hash_payloads()
                with self.phase("post-hash consistency check"):
                    self.check_unchanged(reader, root_info)
        if self.inventory.reasons:
            for item in self.inventory.items:
                if item.decision == "REGENERABLE":
                    item.decision = "REVIEW"
                    item.reason = "Observation was incomplete. Preserve this path and obtain a fresh report."
                    item.observation = None
        self.inventory.ended = utc_now()
        self.metrics["git_subprocesses"] = reader.calls
        self.metrics["git_seconds"] = round(reader.seconds, 6)
        self.metrics["evidence_bytes_read"] = self.evidence.bytes_read
        return self.inventory

    def _entries(self, path: Path, expected: os.stat_result):
        result = []
        with _scandir(path, expected) as entries:
            for entry in entries:
                child = path / entry.name
                if child.name.lower() in GIT_BOUNDARIES:
                    if path != self.root:
                        return None
                    if child.name == ".git":
                        continue
                    self.metrics["unmeasured_boundaries"] += 1
                    continue
                self.seen += 1
                if self.seen > MAX_ENTRIES or len(result) >= MAX_DIRECTORY_ENTRIES:
                    raise InventoryLimit("Directory or working-tree visit limit was exceeded.")
                try:
                    info = child.lstat() if os.name == "nt" else entry.stat(follow_symlinks=False)
                    self.metrics["entry_stats"] += 1
                except OSError:
                    info = None
                result.append((child, info))
        return sorted(result, key=lambda entry: entry[0].name)

    def _remember_markers(self, entries, artifact: Artifact | None) -> set[str]:
        source_names = set()
        for path, info in entries:
            if info is None:
                continue
            if artifact is None and path.name in MARKERS or artifact is not None and (
                artifact.rule_id == "node-dependencies-v2" and path.name == "package.json"
                or artifact.rule_id == "python-venv-v2" and path == artifact.path / "pyvenv.cfg"
            ):
                self.evidence.remember(path, info)
            if artifact is None and stat.S_ISREG(info.st_mode) and not is_reparse_point(info) and info.st_nlink == 1:
                if path.suffix.lower() == ".py":
                    source_names.add(path.name)
                if path.name == "package.json":
                    self.inventory.technologies.add("Node.js")
                if path.name in {"pyproject.toml", "requirements.txt", "Pipfile", "setup.py"}:
                    self.inventory.technologies.add("Python")
                if path.name in {"Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml"} or path.suffix == ".csproj":
                    self.inventory.technologies.add({
                        "Cargo.toml": "Rust", "pom.xml": "Maven", "pubspec.yaml": "Flutter/Dart"
                    }.get(path.name, ".NET" if path.suffix == ".csproj" else "Gradle"))
        return source_names

    def visit(self, path: Path, expected: os.stat_result, depth: int, artifact: Artifact | None,
              protected: bool) -> tuple[int, bool]:
        if depth > MAX_DEPTH:
            raise InventoryLimit("Working-tree path depth exceeds the observation budget.")
        self.metrics["directories"] += 1
        try:
            entries = self._entries(path, expected)
        except OSError:
            self.inventory.incomplete("A directory became inaccessible or changed during inventory.")
            self.metrics["unmeasured_boundaries"] += 1
            return 0, False
        if entries is None:
            self.metrics["unmeasured_boundaries"] += 1
            if artifact:
                artifact.protect("Contains a nested source-control boundary.")
            else:
                relative = path.relative_to(self.root).as_posix()
                self.add_item(relative, "BLOCKED", None, "A nested source-control project was not traversed.")
            return 0, False
        try:
            sources = self._remember_markers(entries, artifact) if not protected else set()
        except EvidenceError:
            self.inventory.incomplete("The manifest observation budget was exceeded.")
            sources = set()
        total, complete = 0, True
        spellings = set()
        for child, info in entries:
            relative = child.relative_to(self.root).as_posix()
            key = path_key(child.name)
            if key in spellings:
                self.inventory.incomplete("Case or Unicode aliases make part of the tree ambiguous.")
            spellings.add(key)
            size, known = self.entry(child, relative, info, depth + 1, artifact, protected, sources)
            total += size
            complete = complete and known
            now = time.monotonic()
            if now - self.last_progress >= 2:
                self.last_progress = now
                self.progress(f"Observed {self.metrics['directories']} directories, {self.metrics['files']} files and "
                              f"{self.metrics['known_logical_bytes']} logical bytes.")
        return total, complete

    def entry(self, path: Path, relative: str, info: os.stat_result | None, depth: int,
              artifact: Artifact | None, protected: bool, sources: set[str]) -> tuple[int, bool]:
        boundary = None
        if info is None:
            self.inventory.incomplete("An entry disappeared or could not be inspected.")
            boundary = "The filesystem entry was unavailable."
        elif is_reparse_point(info) or stat.S_ISLNK(info.st_mode):
            boundary = "A link or reparse point was not followed."
        elif info.st_dev != self.device or path in self.mounts:
            boundary = "A filesystem boundary was not traversed."
        elif not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            boundary = "An unsupported filesystem entry was not opened."
        if boundary:
            self.metrics["unmeasured_boundaries"] += 1
            if artifact:
                artifact.protect(boundary)
            else:
                self.add_item(relative, "BLOCKED", None, boundary)
            return 0, False
        assert info is not None
        directory = stat.S_ISDIR(info.st_mode)
        size = 0 if directory else info.st_size
        tracked = self.inventory.git
        if not directory:
            self.metrics["files"] += 1
            self.metrics["known_logical_bytes"] += size
            if tracked and tracked.has_file(relative):
                self.tracked_rows.append((relative, stamp(info)))
                indexed = tracked.index_metadata.get(path_key(relative))
                if indexed is not None and (info.st_mtime_ns, size & 0xffffffff) != indexed[1:]:
                    self.inventory.tracked_stat_differences += 1
        danger = protected_entry(path, directory)
        if not directory and info.st_nlink != 1:
            danger = "A hard-linked file or unverifiable link count is protected."
        if artifact:
            if not relative_path(relative):
                artifact.protect("The tree contains a filename that cannot be displayed safely.")
            if danger:
                artifact.protect(danger)
            if artifact.context and not artifact.blocked:
                parts = path.relative_to(artifact.path).parts
                issue = descendant_issue(path, parts, directory, artifact.context)
                if issue:
                    artifact.protect(issue)
            if not artifact.blocked and artifact.context:
                artifact.digest.update(_fingerprint_row((relative, stamp(info))))
                if self.deep and not directory:
                    artifact.files.append((path, info))
            return self.visit(path, info, depth, artifact, protected) if directory else (size, True)
        rule = artifact_rule(relative) if directory and not protected and not danger else None
        if rule:
            candidate = Artifact(path, relative, rule, info)
            candidate.digest.update(_fingerprint_row((relative, stamp(info))))
            if tracked and tracked.protects(relative):
                candidate.protect("The path contains tracked or staged-deletion content.")
            elif not relative_path(relative):
                candidate.protect("The path cannot be displayed safely.")
            else:
                try:
                    candidate.context = rule_evidence(rule, path, self.evidence, sources)
                except EvidenceError as exc:
                    candidate.reason = str(exc)
            size, known = self.visit(path, info, depth, candidate, False)
            self.finish_artifact(candidate, size, known)
            return size, known
        if directory:
            size, known = self.visit(path, info, depth, None, protected or bool(danger) or not relative_path(relative))
        else:
            known = True
        if depth == 1 or danger and not protected or directory and path.name in REVIEW_DIRECTORIES and not protected:
            decision = "KEEP" if danger or tracked and tracked.protects(relative) else "REVIEW"
            reason = danger or ("Git-tracked content or a parent of tracked content." if decision == "KEEP" else
                                "Preserved by default. A verified recovery procedure was not established.")
            self.add_item(relative, decision, size if known else None, reason)
        return size, known

    def add_item(self, relative: str, decision: str, size: int | None, reason: str, **fields) -> RetirementItem:
        key = path_key(relative)
        previous = self.item_paths.get(key)
        if previous and previous.display_path == relative:
            return previous
        if len(self.inventory.items) >= MAX_ITEMS:
            raise InventoryLimit("Report item limit was exceeded.")
        item = RetirementItem(relative if relative_path(relative) and not previous else None,
                              inert_path(relative), decision, size, reason, **fields)
        self.item_paths[key] = item
        self.inventory.items.append(item)
        return item

    def finish_artifact(self, candidate: Artifact, size: int, known: bool) -> None:
        context = candidate.context
        if not known:
            candidate.protect("The complete artifact boundary could not be observed.")
        if context and not candidate.blocked:
            try:
                if candidate.rule_id == "python-venv-v2":
                    marker = self.evidence.text(candidate.path / "pyvenv.cfg")
                    if not any(line.startswith("home") and "=" in line and line.split("=", 1)[1].strip() for line in marker.splitlines()):
                        raise EvidenceError("The virtual-environment marker did not establish an environment.")
                    if any(line.split("=", 1)[-1].strip().lower() == "true" for line in marker.splitlines()
                           if line.split("=", 1)[0].strip().lower() == "include-system-site-packages"):
                        raise EvidenceError("The environment depends on an external Python site-packages directory.")
                candidate.reason = context.finish(self.evidence, candidate.path) or ""
            except EvidenceError as exc:
                candidate.reason = str(exc)
        if candidate.blocked or candidate.reason or not context:
            self.add_item(candidate.relative, "BLOCKED" if candidate.blocked else "REVIEW", size if known else None,
                          candidate.reason or "Required positive evidence was missing.", rule_id=candidate.rule_id)
            return
        item = self.add_item(
            candidate.relative, "REGENERABLE", size, "Positive recovery evidence and a complete descendant observation.",
            rule_id=candidate.rule_id, evidence=context.points,
            checks=["Git tracked and staged-deletion prefixes", "Filesystem boundaries, protected content and artifact structure"],
            recovery=context.recovery,
            observation={"mode": "metadata", "digest": candidate.digest.hexdigest(), "root_stamp": list(stamp(candidate.observed))},
            limitations=["Local edits can resemble package payloads. Offline inspection cannot establish identical restoration."],
        )
        self.artifacts.append((candidate, item))
        if candidate.rule_id == "next-cache-v2":
            self.inventory.technologies.add("Next.js")
        if context.vite:
            self.inventory.technologies.add("Vite")

    def check_unchanged(self, reader: GitReader, root_info: os.stat_result) -> None:
        try:
            unchanged = (observed_entry(root_info, directory_chain(self.root)) and reader.unchanged()
                         and self.mounts == local_mounts()
                         and self.evidence.unchanged()
                         and all(observed_entry(artifact.observed, artifact.path.lstat())
                                 for artifact, _ in self.artifacts))
        except (OSError, UnsupportedRoot):
            unchanged = False
        if not unchanged:
            self.inventory.incomplete("Root, Git, manifest or candidate-root evidence changed during inspection.")

    def finish(self, reader: GitReader, root_info: os.stat_result) -> None:
        tracked = self.inventory.git
        assert tracked is not None
        hasher = hashlib.sha256()
        for row in sorted(self.tracked_rows):
            hasher.update(_fingerprint_row(row))
        self.inventory.tracked_observation = hasher.hexdigest()
        self.inventory.tracked_unobserved = len({path_key(path) for path in tracked.tracked} -
                                                {path_key(path) for path, _ in self.tracked_rows})
        if self.evidence.malformed:
            self.inventory.incomplete("One or more required metadata files were malformed, unreadable, or oversized.")
        self.check_unchanged(reader, root_info)

    def hash_payloads(self) -> None:
        for artifact, item in self.artifacts:
            hasher = hashlib.sha256()
            try:
                for path, expected in artifact.files:
                    if protected_entry(path, False):
                        raise OSError("Protected payload cannot be hashed.")
                    file_hash = hashlib.sha256()
                    with open_observed(path, expected) as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            self.metrics["payload_bytes_hashed"] += len(chunk)
                            file_hash.update(chunk)
                        if not same_open_file(expected, os.fstat(handle.fileno())):
                            raise OSError("Payload changed while being hashed.")
                    hasher.update(_fingerprint_row((path.relative_to(self.root).as_posix(), file_hash.hexdigest())))
            except (OSError, UnsupportedRoot):
                self.inventory.incomplete("An eligible payload changed or could not be read in deep mode.")
                return
            assert item.observation is not None
            item.observation.update(mode="content", content_digest=hasher.hexdigest())


def collect_inventory(root: Path, *, deep: bool = False, progress: Callable[[str], None] = NOOP) -> Inventory:
    return Collector(root, deep=deep, progress=progress).collect()


def legacy_tree_metadata(root: Path, *, reparse, same_device) -> tuple[dict[Path, int], list[Path], dict[Path, set[str]]]:
    """Size each legacy path once while retaining the existing .git size scope."""
    initial = root.lstat()
    device = initial.st_dev
    mounts = local_mounts()
    sizes: dict[Path, int] = {}
    directories: list[Path] = []
    markers: dict[Path, set[str]] = {}
    seen = 0

    def visit(directory: Path, current: os.stat_result, discover: bool, depth: int) -> int:
        nonlocal seen
        if depth > MAX_DEPTH:
            raise InventoryLimit("Legacy working-tree depth exceeded the observation budget.")
        children = []
        names = set()
        total = 0
        with _scandir(directory, current) as entries:
            for entry in entries:
                path = directory / entry.name
                seen += 1
                if seen > MAX_ENTRIES:
                    raise InventoryLimit("Legacy working-tree metadata exceeded the observation budget.")
                info = path.lstat() if os.name == "nt" else entry.stat(follow_symlinks=False)
                if reparse(info) or stat.S_ISLNK(info.st_mode) or info.st_dev != device:
                    sizes[path] = 0
                elif stat.S_ISDIR(info.st_mode):
                    children.append((path, info))
                elif stat.S_ISREG(info.st_mode):
                    sizes[path] = info.st_size
                    total += info.st_size
                    names.add(entry.name)
        if directory != root and ".git" in names | {p.name for p, _ in children}:
            sizes[directory] = 0
            return 0
        if discover:
            markers[directory] = names
        for child, info in children:
            allowed = discover and child.name not in GIT_BOUNDARIES
            if allowed:
                directories.append(child)
            if child not in mounts and same_device(child, device):
                total += visit(child, info, allowed, depth + 1)
        sizes[directory] = total
        return total

    visit(root, initial, True, 0)
    return sizes, directories, markers
