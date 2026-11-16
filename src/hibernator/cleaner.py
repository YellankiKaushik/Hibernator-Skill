from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from .errors import ApplyRefused
from .discovery import scan
from .git_state import read_git_state
from .plans import validate_candidate_current, validate_current, validate_plan
from .reports import cleanup_report, save_report
from .util import utc_now

_TEST_OWNED_ROOTS: set[str] = set()


def _register_test_owned_root(root: Path) -> None:
    """Private test-harness hook; a marker alone never grants cleanup authority."""
    owned = Path(root).resolve(strict=True)
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if not owned.parent.name.startswith("hibernator-test-") or temp_root not in owned.parents or not ((owned / ".git").exists()):
        raise ApplyRefused("Only a Git fixture created by the test harness can be registered.")
    _TEST_OWNED_ROOTS.add(str(owned))


def _unregister_test_owned_root(root: Path) -> None:
    try:
        _TEST_OWNED_ROOTS.discard(str(Path(root).resolve(strict=False)))
    except OSError:
        pass


def apply_production(plan: dict, *, interactive: bool) -> dict:
    """Production deletion is deliberately disabled until host FS review is complete."""
    validate_plan(plan)
    if not interactive:
        raise ApplyRefused("Noninteractive apply is refused.")
    raise ApplyRefused(
        "Destructive apply is disabled in this build: Windows reparse-point, concurrent-path, and human-approval controls "
        "have not received the required platform security review. Use the CLI scan/plan/report/restore features; "
        "cleanup is currently tested only in the isolated synthetic fixture harness."
    )


def apply_test_fixture(plan: dict, owned_root: Path) -> dict:
    """Test-only deletion path, bounded to an explicitly marked temporary fixture."""
    validate_plan(plan)
    root = Path(plan["root"]).resolve(strict=True)
    owned = Path(owned_root).resolve(strict=True)
    marker = owned / ".hibernator-test-owned"
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if (
        root != owned
        or str(owned) not in _TEST_OWNED_ROOTS
        or not owned.parent.name.startswith("hibernator-test-")
        or temp_root not in owned.parents
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != "HIBERNATOR SYNTHETIC TEST FIXTURE ONLY\n"
    ):
        raise ApplyRefused("Synthetic cleanup requires the exact marked test-owned root.")
    validate_current(plan)
    before_scan = scan(root).to_dict()
    before_free = shutil.disk_usage(root).free
    outcomes = [{"path": item["path"], "status": "NOT_ATTEMPTED", "reason": "Waiting for the approved candidate sequence."} for item in plan["candidates"]]
    report_id = uuid.uuid4().hex
    journal = cleanup_report(plan, outcomes, "APPLYING", before_scan=before_scan, before_free=before_free, git_integrity="tracked Git snapshot verified before fixture cleanup", report_id=report_id)
    lock = owned.parent / (owned.name + ".hibernator-test-lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ApplyRefused("Another fixture cleanup is already running.") from exc
    try:
        os.close(fd)
        report_file = save_report(journal, directory=owned.parent, project_root=root)
        active_candidate: int | None = None
        try:
            for index, candidate in enumerate(plan["candidates"]):
                try:
                    validate_candidate_current(plan, candidate)
                except Exception as exc:
                    outcomes[index] = {"path": candidate["path"], "status": "SKIPPED", "reason": f"Candidate revalidation failed: {exc}"}
                    journal = cleanup_report(plan, outcomes, "PARTIAL", before_scan=before_scan, before_free=before_free, git_integrity="tracked Git snapshot checked before every fixture candidate", report_id=report_id)
                    save_report(journal, directory=owned.parent, project_root=root)
                    continue
                target = root / Path(candidate["path"])
                if target.is_symlink() or not target.is_dir() or target.resolve(strict=True).parent != target.parent.resolve(strict=True):
                    outcomes[index] = {"path": candidate["path"], "status": "SKIPPED", "reason": "Path identity or type changed."}
                    continue
                outcomes[index] = {"path": candidate["path"], "status": "STARTED", "reason": "Removal started; inspect this candidate if the operation is interrupted."}
                journal = cleanup_report(plan, outcomes, "APPLYING", before_scan=before_scan, before_free=before_free, git_integrity="tracked Git snapshot checked before each fixture candidate", report_id=report_id)
                save_report(journal, directory=owned.parent, project_root=root)
                active_candidate = index
                try:
                    shutil.rmtree(target)
                except OSError as exc:
                    outcomes[index] = {"path": candidate["path"], "status": "UNKNOWN", "reason": f"Removal returned an error and may have partially changed the candidate; inspect it manually: {exc}"}
                    active_candidate = None
                    journal = cleanup_report(plan, outcomes, "PARTIAL", before_scan=before_scan, before_free=before_free, after_scan=scan(root).to_dict(), after_free=shutil.disk_usage(root).free, git_integrity="tracked Git snapshot checked; candidate outcome unknown", report_id=report_id)
                    save_report(journal, directory=owned.parent, project_root=root)
                    continue
                if target.exists() or target.is_symlink():
                    outcomes[index] = {"path": candidate["path"], "status": "UNKNOWN", "reason": "Removal returned successfully but the candidate path still exists; inspect it manually."}
                    active_candidate = None
                    journal = cleanup_report(plan, outcomes, "PARTIAL", before_scan=before_scan, before_free=before_free, after_scan=scan(root).to_dict(), after_free=shutil.disk_usage(root).free, git_integrity="tracked Git snapshot checked; candidate outcome unknown", report_id=report_id)
                    save_report(journal, directory=owned.parent, project_root=root)
                    continue
                if read_git_state(root).tracked_snapshot != plan["tracked_snapshot"]:
                    outcomes[index] = {"path": candidate["path"], "status": "CRITICAL", "reason": "Tracked Git state changed during cleanup."}
                    active_candidate = None
                    journal = cleanup_report(plan, outcomes, "CRITICAL_FAILURE", before_scan=before_scan, before_free=before_free, after_scan=scan(root).to_dict(), after_free=shutil.disk_usage(root).free, git_integrity="CRITICAL: tracked Git state changed", report_id=report_id)
                    save_report(journal, directory=owned.parent, project_root=root)
                    raise ApplyRefused("Critical preservation check failed; fixture cleanup stopped.")
                outcomes[index] = {"path": candidate["path"], "status": "DELETED", "logical_bytes": candidate["logical_bytes"]}
                active_candidate = None
                journal = cleanup_report(plan, outcomes, "PARTIAL", before_scan=before_scan, before_free=before_free, git_integrity="tracked Git snapshot unchanged after deletion", report_id=report_id)
                save_report(journal, directory=owned.parent, project_root=root)
        except ApplyRefused:
            raise
        except BaseException:
            if active_candidate is not None:
                candidate = plan["candidates"][active_candidate]
                outcomes[active_candidate] = {"path": candidate["path"], "status": "UNKNOWN", "reason": "The cleanup was interrupted after removal started; the candidate may be partially changed and must be inspected."}
            journal = cleanup_report(plan, outcomes, "INTERRUPTED", before_scan=before_scan, before_free=before_free, after_scan=scan(root).to_dict(), after_free=shutil.disk_usage(root).free, git_integrity="partial outcome; tracked state requires review", report_id=report_id)
            save_report(journal, directory=owned.parent, project_root=root)
            raise
        final_scan = scan(root).to_dict()
        status = "COMPLETED" if all(item["status"] == "DELETED" for item in outcomes) else "PARTIAL"
        journal = cleanup_report(plan, outcomes, status, before_scan=before_scan, after_scan=final_scan, before_free=before_free, after_free=shutil.disk_usage(root).free, git_integrity="tracked Git snapshot unchanged after fixture cleanup", report_id=report_id)
        save_report(journal, directory=owned.parent, project_root=root)
        return journal
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
