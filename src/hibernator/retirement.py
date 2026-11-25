"""Retirement and explicitly requested, read-only follow-up observations."""

from __future__ import annotations

import os
import re
import stat
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from . import RETIREMENT_RULE_PACK_VERSION, __version__
from .errors import InvalidPlan, ScanFailure, UnsupportedRoot
from .git_state import GitReader
from .inventory import collect_inventory
from .paths import canonical_root, directory_chain, local_mounts, path_key, relative_path, stamp
from .retirement_reports import FOOTER, SCHEMA_VERSION, load_retirement_report, new_report_id, save_pair, validate_store
from .util import is_reparse_point


MEASUREMENT = ("Observed logical file lengths in the selected working tree. Git metadata, links, filesystem boundaries "
               "and unmeasured regions are excluded. Protected parent sizes may overlap candidates. "
               "Physical disk allocation and free-space changes were not measured.")
WARNINGS = [
    "The report is advisory and can become stale. Metadata checks are not an atomic filesystem snapshot.",
    "Fast observations can miss content changes with unchanged metadata. The targeted recheck covers root, Git metadata, "
    "observed manifests and candidate roots, not every descendant.",
    "Filesystem checks can miss same-device mounts or concurrent substitutions. Keep local backups and recheck after project activity.",
    "Packages, private registries and the original toolchain may be unavailable when you resume.",
]


class PairWriteError(OSError):
    def __init__(self, report_id: str):
        super().__init__("Could not commit a verified report pair in the private output directory.")
        self.report_id = report_id


def parse_minimum(raw: str) -> int:
    try:
        if not re.fullmatch(r"[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", raw) or len(raw) > 64:
            raise InvalidOperation
        amount = Decimal(raw)
        if amount < 0 or abs(amount.as_tuple().exponent) > 128:
            raise InvalidOperation
        top, bottom = amount.as_integer_ratio()
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise UnsupportedRoot("The minimum size must be a finite nonnegative number of MiB.") from exc
    return (top * 1_048_576 + bottom - 1) // bottom


def parse_excludes(values: list[str]) -> set[str]:
    keys = set()
    for value in values:
        if not relative_path(value) or path_key(value) in keys:
            raise UnsupportedRoot("Exclusions must be unique, exact project-relative paths without globs or aliases.")
        keys.add(path_key(value))
    return set(values)


def retire(project: str, *, output: str | None, deep: bool, minimum: str, excludes: list[str], show_paths: bool,
           progress: Callable[[str], None]) -> dict:
    minimum_bytes = parse_minimum(minimum)
    excluded = parse_excludes(excludes)
    root = canonical_root(project)
    store = validate_store(root, output)
    inventory = collect_inventory(root, deep=deep, progress=progress)
    eligible = sorted((item for item in inventory.items if item.decision == "REGENERABLE"),
                      key=lambda item: (-item.logical_bytes, item.path))
    if excluded - {item.path for item in eligible} and not inventory.reasons:
        raise UnsupportedRoot("Every exclusion must exactly match a verified retirement candidate.")
    for item in eligible:
        item.disposition = ("excluded" if item.path in excluded else
                            "below_minimum" if item.logical_bytes < minimum_bytes else "offered")
    offered = [item for item in eligible if item.disposition == "offered"]
    preserved = sorted((item for item in inventory.items if item.decision != "REGENERABLE"),
                       key=lambda item: item.display_path)
    status = ("INCOMPLETE" if inventory.reasons else "READY_FOR_MANUAL_REVIEW" if offered else "NO_CANDIDATES")
    totals = {
        "observed_logical_bytes": inventory.metrics["known_logical_bytes"],
        "unmeasured_boundaries": inventory.metrics["unmeasured_boundaries"],
        "eligible_logical_bytes": sum(item.logical_bytes for item in eligible),
        "offered_logical_bytes": sum(item.logical_bytes for item in offered),
        "offered_count": len(offered),
        "review_count": sum(item.decision == "REVIEW" for item in preserved),
        "blocked_count": sum(item.decision == "BLOCKED" for item in preserved),
    }
    technologies = {
        "detected": sorted(inventory.technologies),
        "supported_artifacts": ["npm lockfile dependencies", "pinned Python virtual environments",
                                "Python bytecode", "pytest cache", "Next.js cache", "Vite cache within eligible npm artifacts"],
        "partial_or_unsupported": ["Yarn/pnpm linked layouts", "Python editable and external environments",
                                   "Rust", "Maven", "Gradle", ".NET", "Flutter/Dart", "generic build and release outputs"],
    }
    warnings = [*WARNINGS]
    if inventory.tracked_unobserved:
        warnings.append(f"{inventory.tracked_unobserved} tracked or staged-deletion paths were missing or unobserved and remain protected.")
    if os.name == "nt":
        warnings.append("Windows report access is governed by the selected directory's local ACL.")
    body = {
        "report_type": "retirement", "schema_version": SCHEMA_VERSION, "report_id": new_report_id(),
        "private": True, "started_at": inventory.started, "ended_at": inventory.ended,
        "hibernator_version": __version__, "rule_pack_version": RETIREMENT_RULE_PACK_VERSION,
        "status": status, "mode": "deep" if deep else "fast", "root": str(root),
        "root_stamp": list(inventory.root_stamp), "git_snapshot": inventory.git.snapshot if inventory.git else None,
        "tracked_worktree_metadata_digest": inventory.tracked_observation,
        "git_observations": {
            "staged_paths": inventory.git.staged_paths if inventory.git else None,
            "tracked_stat_differences": inventory.tracked_stat_differences,
            "tracked_unobserved": inventory.tracked_unobserved,
        },
        "measurement_scope": MEASUREMENT, "incomplete_reasons": inventory.reasons,
        "technology_coverage": technologies, "items": [item.to_dict() for item in eligible + preserved],
        "metrics": inventory.metrics, "totals": totals, "warnings": warnings,
        "actual_bytes_reclaimed_by_hibernator": 0,
    }
    progress("private report writing")
    writing = time.monotonic()
    try:
        reports = save_pair(body, store, root, show_paths=show_paths)
    except (OSError, UnsupportedRoot, InvalidPlan) as exc:
        raise PairWriteError(body["report_id"]) from exc
    metrics = {**inventory.metrics, "phase_seconds": {**inventory.metrics["phase_seconds"],
               "private report writing": round(time.monotonic() - writing, 6)}}
    summary = {
        "status": status, "report_id": body["report_id"], "mode": body["mode"], "totals": totals,
        "candidates": [{"path": item.path, "rule_id": item.rule_id, "logical_bytes": item.logical_bytes,
                        "reason": item.reason} for item in offered[:8]],
        "candidate_sample_limit": 8, "incomplete_reasons": inventory.reasons, "warnings": warnings,
        "reports": reports, "report_store": "selected output directory" if output else "default local retirement report store",
        "metrics": metrics, "actual_bytes_reclaimed_by_hibernator": 0, "message": FOOTER,
        "git_observations": body["git_observations"],
    }
    if show_paths:
        summary["root"] = str(root)
        summary["report_store"] = str(store)
        summary["reports"] = {kind: str(store / path) for kind, path in reports.items()}
    return summary


def _observe_path(root: Path, item: dict, mounts: set[Path]) -> str:
    relative = item["path"]
    current = root
    for part in relative.split("/"):
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return "MISSING_SINCE_SCAN"
        except OSError:
            return "UNKNOWN"
        if (current in mounts or is_reparse_point(info) or stat.S_ISLNK(info.st_mode)
                or info.st_dev != item["observation"]["root_stamp"][0]):
            return "UNKNOWN"
        if not stat.S_ISDIR(info.st_mode):
            return "CHANGED"
    return "PRESENT" if list(stamp(info)) == item["observation"]["root_stamp"] else "CHANGED"


def verify(path: Path) -> dict:
    body = load_retirement_report(path)
    if body["status"] == "INCOMPLETE":
        raise InvalidPlan("The report has incomplete observations. Obtain a fresh retirement report.")
    try:
        root = canonical_root(body["root"])
        initial = directory_chain(root)
        if stamp(initial)[:3] != tuple(body["root_stamp"][:3]):
            raise InvalidPlan("The bound project root identity changed.")
        reader = GitReader(root)
        git = reader.retirement_state()
        mounts = local_mounts()
        outcomes = [{"path": item["path"], "observation": _observe_path(root, item, mounts)}
                    for item in body["items"] if item["disposition"] == "offered"]
        if not reader.unchanged() or stamp(initial) != stamp(directory_chain(root)) or mounts != local_mounts():
            raise InvalidPlan("Git metadata or the selected root changed during verification.")
    except (OSError, ScanFailure, UnsupportedRoot) as exc:
        raise InvalidPlan("The bound Git project could not be safely rechecked.") from exc
    return {
        "status": "OBSERVED", "report_id": body["report_id"],
        "git_metadata_changed": git.snapshot != body["git_snapshot"],
        "observations": outcomes,
        "limitations": "Checks cover only listed directory entries and local Git index/HEAD metadata. "
                       "A present path can have changed descendants. Missing is an observation, not an attribution or free-space measurement.",
        "message": FOOTER, "actual_bytes_reclaimed_by_hibernator": 0,
    }
