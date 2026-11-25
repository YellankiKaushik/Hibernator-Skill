from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .discovery import scan
from .paths import external_directory
from .util import is_reparse_point, utc_now


def report_directory() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "hibernator" / "reports"


def write_scan_report(root: str, report: dict[str, Any] | None = None) -> Path:
    if report is None:
        report = scan(root).to_dict()
    directory = report_directory()
    project_root = Path(report["root"]).resolve(strict=True)
    try:
        directory.resolve(strict=False).relative_to(project_root)
    except ValueError:
        pass
    else:
        directory = project_root.parent / ".hibernator-state" / "reports"
    try:
        directory.resolve(strict=False).relative_to(project_root)
    except ValueError:
        pass
    else:
        raise OSError("Cannot find a default report location outside the scanned project.")
    safe_report = dict(report)
    safe_report["report_type"] = "scan"
    safe_report["report_id"] = uuid.uuid4().hex
    safe_report["root"] = "."
    safe_report["git_root"] = "."
    safe_report["root_redacted"] = True
    _redact_project_path(safe_report, project_root)
    return save_report(safe_report, directory=directory, project_root=project_root)


def _redact_project_path(value: Any, project_root: Path) -> None:
    """Remove an absolute project path from nested report text before persistence."""
    native = str(project_root)
    variants = {native, native.replace("\\", "/")}
    flags = re.IGNORECASE if os.name == "nt" else 0
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                for variant in variants:
                    value[key] = re.sub(re.escape(variant), "<project>", value[key], flags=flags)
            else:
                _redact_project_path(child, project_root)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                for variant in variants:
                    value[index] = re.sub(re.escape(variant), "<project>", value[index], flags=flags)
            else:
                _redact_project_path(child, project_root)


def cleanup_report(
    plan: dict,
    outcomes: list[dict],
    status: str,
    *,
    before_scan: dict | None = None,
    after_scan: dict | None = None,
    before_free: int | None = None,
    after_free: int | None = None,
    git_integrity: str = "not verified",
    report_id: str | None = None,
) -> dict:
    removed = sum(entry.get("logical_bytes", 0) for entry in outcomes if entry.get("status") == "DELETED")
    selected = [
        {"path": item["path"], "rule_id": item.get("rule_id"), "logical_bytes": item.get("logical_bytes", 0), "reason": item.get("reason", "")}
        for item in plan["candidates"]
    ]
    classifications = (before_scan or {}).get("items", [])
    report = {
        "schema_version": "1",
        "report_type": "cleanup",
        "report_id": report_id or uuid.uuid4().hex,
        "created_at": utc_now(),
        "plan_id": plan["plan_id"],
        "plan_digest": plan["digest"],
        "root": ".",
        "root_redacted": True,
        "status": status,
        "selected": selected,
        "outcomes": outcomes,
        "calculated_candidate_bytes": sum(item["logical_bytes"] for item in selected),
        "estimated_logical_bytes": plan["estimated_logical_bytes"],
        "removed_logical_bytes": removed,
        "actual_free_space_delta_bytes": (after_free - before_free) if before_free is not None and after_free is not None else None,
        "free_space_delta_note": "Actual free-space change is contextual and may include concurrent activity, allocation units, snapshots, or compression.",
        "logical_bytes_before": (before_scan or {}).get("total_logical_bytes"),
        "logical_bytes_after": (after_scan or {}).get("total_logical_bytes"),
        "remaining_project_logical_bytes": (after_scan or {}).get("total_logical_bytes"),
        "protected_and_review_items": [
            {"path": item["path"], "decision": item["decision"], "reason": item["reason"], "logical_bytes": item["logical_bytes"]}
            for item in classifications if item["decision"] != "REGENERABLE"
        ],
        "git_integrity": git_integrity,
        "restore": "See the restore --dry-run instructions; deleted local data cannot be reconstructed by this tool.",
    }
    _redact_project_path(report, Path(plan["root"]).resolve(strict=False))
    return report


def _safe_directory(directory: Path, project_root: Path | None) -> Path:
    return external_directory(directory, project_root)


def _fsync_parent_directory(path: Path) -> None:
    """Persist a rename on POSIX filesystems that expose directory handles."""
    if os.name != "posix":
        return
    if not hasattr(os, "O_DIRECTORY"):
        raise OSError("Cannot durably journal report: directory fsync is unavailable.")
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    directory_fd = os.open(path.parent, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def save_report(report: dict[str, Any], *, directory: Path | None = None, project_root: Path | None = None) -> Path:
    directory = _safe_directory(directory or report_directory(), project_root)
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or not re.fullmatch(r"[0-9a-f]{32}", report_id):
        raise ValueError("Report ID must be a 32-character lowercase hexadecimal identifier.")
    path = directory / f"report-{report_id}.json"
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or is_reparse_point(info) or info.st_nlink != 1:
            raise OSError("The report destination is linked or unsupported.")
    fd, temp_name = tempfile.mkstemp(prefix=".hibernator-report-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        _fsync_parent_directory(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return path
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def load_report(report_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{32}", report_id):
        raise ValueError("Report ID must be a 32-character lowercase hexadecimal identifier.")
    path = report_directory() / f"report-{report_id}.json"
    return load_report_file(path)


def load_report_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "1" or value.get("report_type") not in {"scan", "cleanup"}:
        raise ValueError("Unsupported or malformed Hibernator report.")
    return value


def render_report(report: dict[str, Any]) -> str:
    lines = [f"Report: {report.get('report_id', 'unknown')}", f"Type: {report.get('report_type', 'unknown')}", f"Project: {report.get('root', 'unknown')}"]
    if report.get("report_type") == "cleanup":
        lines.extend([
            f"Status: {report.get('status', 'unknown')}",
            f"Selected candidate bytes: {report.get('calculated_candidate_bytes', 0)}",
            f"Logical bytes removed: {report.get('removed_logical_bytes', 0)}",
            f"Remaining project logical bytes: {report.get('remaining_project_logical_bytes')}",
            f"Observed free-space delta: {report.get('actual_free_space_delta_bytes')} (advisory)",
            f"Git integrity: {report.get('git_integrity', 'unknown')}",
        ])
        for outcome in report.get("outcomes", []):
            lines.append(f"  {outcome.get('status', 'UNKNOWN'):<16} {outcome.get('path', '')} {outcome.get('reason', '')}".rstrip())
        lines.append(report.get("free_space_delta_note", ""))
    else:
        lines.append(f"Total logical bytes: {report.get('total_logical_bytes', 0)}")
        for item in report.get("items", []):
            lines.append(f"  {item.get('decision', 'UNKNOWN'):<12} {item.get('path', '')} ({item.get('logical_bytes', 0)} bytes) - {item.get('reason', '')}")
    return "\n".join(line for line in lines if line)
