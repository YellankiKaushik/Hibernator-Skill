from __future__ import annotations

import json
import os
import stat
import tempfile
import uuid
from pathlib import Path, PureWindowsPath
from typing import Any

from . import PLAN_SCHEMA_VERSION, RULE_PACK_VERSION
from .discovery import scan
from .errors import InvalidPlan, UnsupportedRoot
from .models import ScanReport
from .paths import external_directory, local_path
from .util import canonical_json, digest, utc_now


def make_plan(project: str | Path, excluded: list[str] | None = None) -> dict[str, Any]:
    return plan_from_scan(scan(project), excluded)


def plan_from_scan(report: ScanReport, excluded: list[str] | None = None) -> dict[str, Any]:
    exclude = set(excluded or [])
    candidates = [item.to_dict() for item in report.items if item.decision == "REGENERABLE" and item.path not in exclude]
    review_items = [item.to_dict() for item in report.items if item.decision != "REGENERABLE"]
    invalid_exclusions = exclude - {item.path for item in report.items if item.decision == "REGENERABLE"}
    if invalid_exclusions:
        raise InvalidPlan("Exclusions must exactly match REGENERABLE paths: " + ", ".join(sorted(invalid_exclusions)))
    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": uuid.uuid4().hex,
        "created_at": utc_now(),
        "state": "PLANNED",
        "root": report.root,
        "git_root": report.git_root,
        "root_identity": _root_identity(Path(report.root)),
        "git_snapshot": report.git_snapshot,
        "tracked_snapshot": report.tracked_snapshot,
        "rule_pack_version": RULE_PACK_VERSION,
        "candidates": candidates,
        "review_items": review_items,
        "classification_snapshot": digest({"items": [item.to_dict() for item in report.items], "total_logical_bytes": report.total_logical_bytes}),
        "excluded": sorted(exclude),
        "warnings": ["A digest detects accidental plan changes; it does not authenticate a human approver."],
        "estimated_logical_bytes": sum(item["logical_bytes"] for item in candidates),
    }
    payload["digest"] = plan_digest(payload)
    return payload


def _root_identity(root: Path) -> dict[str, int]:
    info = root.stat()
    return {"device": int(info.st_dev), "inode": int(info.st_ino)}


def plan_digest(plan: dict[str, Any]) -> str:
    body = {key: value for key, value in plan.items() if key != "digest"}
    return digest(body)


def validate_plan(plan: dict[str, Any]) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise InvalidPlan("Unsupported or malformed plan schema.")
    required = {"plan_id", "root", "git_root", "root_identity", "git_snapshot", "tracked_snapshot", "rule_pack_version", "candidates", "review_items", "classification_snapshot", "digest", "state"}
    if not required.issubset(plan) or plan.get("state") != "PLANNED":
        raise InvalidPlan("Plan is incomplete or no longer usable.")
    if plan.get("rule_pack_version") != RULE_PACK_VERSION:
        raise InvalidPlan("Plan rule version is stale; create a new plan.")
    if plan_digest(plan) != plan.get("digest"):
        raise InvalidPlan("Plan digest does not match its contents.")
    if not isinstance(plan["candidates"], list):
        raise InvalidPlan("Plan candidates must be a list.")
    for candidate in plan["candidates"]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("path"), str):
            raise InvalidPlan("Plan candidate is malformed.")
        raw_path = candidate.get("path", "")
        rel = Path(raw_path)
        win_path = PureWindowsPath(raw_path)
        if not isinstance(raw_path, str) or "\0" in raw_path or rel.is_absolute() or win_path.is_absolute() or win_path.drive or ".." in rel.parts or ".." in win_path.parts or not rel.parts or raw_path in (".", "..") or candidate.get("decision") != "REGENERABLE":
            raise InvalidPlan("Plan contains an invalid or ineligible candidate path.")
    if not isinstance(plan["review_items"], list):
        raise InvalidPlan("Plan review items must be a list.")
    for item in plan["review_items"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise InvalidPlan("Plan review item is malformed.")
        raw_path = item["path"]
        rel = Path(raw_path)
        win_path = PureWindowsPath(raw_path)
        if "\0" in raw_path or rel.is_absolute() or win_path.is_absolute() or win_path.drive or ".." in rel.parts or ".." in win_path.parts or not rel.parts or raw_path in (".", ".."):
            raise InvalidPlan("Plan contains an invalid review-item path.")
        decision = item.get("decision")
        logical_bytes = item.get("logical_bytes")
        if not isinstance(decision, str) or decision not in {"KEEP", "REVIEW", "BLOCKED"} or not isinstance(item.get("reason"), str) or type(logical_bytes) is not int or logical_bytes < 0:
            raise InvalidPlan("Plan review item has invalid classification data.")


def save_plan(plan: dict[str, Any], path: Path) -> None:
    validate_plan(plan)
    target = local_path(path)
    project_root = Path(plan["root"]).resolve(strict=True)
    try:
        target.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise InvalidPlan("Plan files must be saved outside the scanned project.")
    try:
        external_directory(target.parent, project_root)
        if target.exists() or target.is_symlink():
            info = target.lstat()
            from .util import is_reparse_point
            if not stat.S_ISREG(info.st_mode) or is_reparse_point(info) or info.st_nlink != 1:
                raise InvalidPlan("The plan destination is linked or unsupported.")
    except UnsupportedRoot as exc:
        raise InvalidPlan("The plan must use an unaliased local destination outside the project.") from exc
    fd, temp_name = tempfile.mkstemp(prefix=".hibernator-plan-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_json(plan) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidPlan(f"Cannot read a valid plan: {exc}") from exc
    validate_plan(value)
    return value


def validate_current(plan: dict[str, Any]) -> None:
    validate_plan(plan)
    current = scan(plan["root"])
    if (
        current.root != plan["root"]
        or current.git_snapshot != plan["git_snapshot"]
        or current.tracked_snapshot != plan["tracked_snapshot"]
    ):
        raise InvalidPlan("Project or Git state changed after planning; scan and create a new plan.")
    current_classification = digest({"items": [item.to_dict() for item in current.items], "total_logical_bytes": current.total_logical_bytes})
    if current_classification != plan["classification_snapshot"]:
        raise InvalidPlan("Project classifications changed after planning; scan and create a new plan.")
    current_review_items = [item.to_dict() for item in current.items if item.decision != "REGENERABLE"]
    if current_review_items != plan["review_items"]:
        raise InvalidPlan("Plan review items do not match the current project classifications.")
    if _root_identity(Path(plan["root"])) != plan["root_identity"]:
        raise InvalidPlan("Project root identity changed after planning.")
    by_path = {item.path: item for item in current.items}
    for candidate in plan["candidates"]:
        _validate_candidate_item(candidate, by_path.get(candidate["path"]))


def validate_candidate_current(plan: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Recheck one candidate while tolerating prior approved removals in a fixture run."""
    validate_plan(plan)
    current = scan(plan["root"])
    if current.root != plan["root"] or current.tracked_snapshot != plan["tracked_snapshot"]:
        raise InvalidPlan("Tracked Git state changed during apply; stopping cleanup.")
    by_path = {item.path: item for item in current.items}
    _validate_candidate_item(candidate, by_path.get(candidate["path"]))


def _validate_candidate_item(candidate: dict[str, Any], item) -> None:
    if not item or item.decision != "REGENERABLE" or item.tree_digest != candidate.get("tree_digest") or item.identity != candidate.get("identity"):
        raise InvalidPlan(f"Candidate changed or is no longer eligible: {candidate['path']}")
