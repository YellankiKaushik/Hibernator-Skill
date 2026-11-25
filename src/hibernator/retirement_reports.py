"""Private, versioned retirement report pairs and their completion records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import ExitStack
from pathlib import Path

from .errors import InvalidPlan, UnsupportedRoot
from .paths import (
    directory_chain, external_filesystem, local_path, mounted_filesystems, open_observed, path_key,
    pin_windows_directory, real_directory, relative_path, same_open_file, stamp,
    validate_windows_private_directory, windows_local_drive,
)
from .reports import _fsync_parent_directory, report_directory


SCHEMA_VERSION = 1
REPORT_LIMIT = 64 << 20
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
REPORT_ID = re.compile(r"[0-9a-f]{32}\Z")
FOOTER = "Hibernator did not modify project files. Actual bytes reclaimed by Hibernator: 0."
CHECKLIST = [
    "Confirm the selected Git project is inactive and close builds and development servers.",
    "Inspect the exact relative path and check whether your app still needs the artifact to run.",
    "Confirm unique data and backups are retained and the listed recovery inputs are available.",
    "Make any manual cleanup decision yourself in your file manager. Keep uncertain content.",
]


def _encode(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def report_digest(value: dict) -> str:
    return _sha(_encode({k: v for k, v in value.items() if k != "digest"}))


def _number(value, *, unknown: bool = False) -> bool:
    return (unknown and value is None) or (type(value) is int and value >= 0)


def _hex(value, pattern=DIGEST) -> bool:
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) for entry in value)


def _valid_observation(value: dict) -> bool:
    return (isinstance(value, dict) and value.get("mode") in ("metadata", "content")
            and _hex(value.get("digest")) and _stamp(value.get("root_stamp"))
            and (value["mode"] == "metadata" and "content_digest" not in value
                 or value["mode"] == "content" and _hex(value.get("content_digest"))))


def _stamp(value) -> bool:
    return isinstance(value, list) and len(value) == 7 and all(type(number) is int for number in value)


def _valid_recovery(value: dict) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("guidance"), str):
        return False
    directory = value.get("working_directory")
    inputs = value.get("preserve")
    return (directory == "." or relative_path(directory)) and _strings(inputs) and all(relative_path(path) for path in inputs)


def validate_retirement_report(value: dict) -> None:
    try:
        _validate_report(value)
    except (KeyError, TypeError, ValueError, RecursionError, UnsupportedRoot) as exc:
        raise InvalidPlan("The private retirement report has an invalid schema, totals, paths, or digest.") from exc


def _validate_report(value: dict) -> None:
    if (not isinstance(value, dict) or value.get("report_type") != "retirement"
            or type(value.get("schema_version")) is not int or value["schema_version"] != SCHEMA_VERSION
            or not _hex(value.get("report_id"), REPORT_ID) or value.get("private") is not True
            or not _hex(value.get("digest")) or value["digest"] != report_digest(value)):
        raise ValueError("Header or digest")
    status = value["status"]
    if status not in ("READY_FOR_MANUAL_REVIEW", "NO_CANDIDATES", "INCOMPLETE"):
        raise ValueError("Status")
    if value["mode"] not in ("fast", "deep") or not _stamp(value["root_stamp"]):
        raise ValueError("Root observation")
    root = value["root"]
    if not isinstance(root, str) or str(local_path(root)) != root:
        raise ValueError("Root path")
    if any(not isinstance(value[name], str) or not value[name] for name in (
        "started_at", "ended_at", "hibernator_version", "rule_pack_version", "measurement_scope",
    )):
        raise ValueError("Scope metadata")
    if not _strings(value["incomplete_reasons"]) or bool(value["incomplete_reasons"]) != (status == "INCOMPLETE"):
        raise ValueError("Completeness")
    if (not isinstance(value["metrics"], dict) or not isinstance(value["technology_coverage"], dict)
            or not _strings(value["warnings"]) or not _number(value["actual_bytes_reclaimed_by_hibernator"])
            or value["actual_bytes_reclaimed_by_hibernator"] != 0):
        raise ValueError("Metrics")
    if not all(_strings(group) for group in value["technology_coverage"].values()):
        raise ValueError("Technology coverage")
    git_observations = value["git_observations"]
    if (not _number(git_observations["staged_paths"], unknown=status == "INCOMPLETE")
            or not _number(git_observations["tracked_stat_differences"])
            or not _number(git_observations["tracked_unobserved"])):
        raise ValueError("Git comparison counts")
    for field in ("git_snapshot", "tracked_worktree_metadata_digest"):
        if value[field] is not None and not _hex(value[field]):
            raise ValueError("Git observation")
    if status != "INCOMPLETE" and (value["git_snapshot"] is None or value["tracked_worktree_metadata_digest"] is None):
        raise ValueError("Missing Git evidence")
    totals = value["totals"]
    for field in ("observed_logical_bytes", "eligible_logical_bytes", "offered_logical_bytes",
                  "offered_count", "review_count", "blocked_count", "unmeasured_boundaries"):
        if not _number(totals[field]):
            raise ValueError("Byte and count totals")
    items = value["items"]
    if not isinstance(items, list):
        raise ValueError("Items")
    paths, eligible, offered = set(), set(), []
    labels = {"KEEP": 0, "REVIEW": 0, "BLOCKED": 0, "REGENERABLE": 0}
    sums = {"offered": 0, "eligible": 0}
    for item in items:
        path, display = item["path"], item["display_path"]
        label, size = item["decision"], item["logical_bytes"]
        if (label not in labels or not _number(size, unknown=True) or not isinstance(item["reason"], str)
                or not isinstance(display, str) or any(ord(c) < 32 for c in display)
                or not _strings(item["evidence"]) or not _strings(item["checks"]) or not _strings(item["limitations"])):
            raise ValueError("Item fields")
        key = path_key(path) if path is not None else None
        if key is not None and (not relative_path(path) or path != display or key in paths):
            raise ValueError("Ambiguous item path")
        if key is not None:
            paths.add(key)
        labels[label] += 1
        disposition = item["disposition"]
        if label == "REGENERABLE":
            if (key is None or size is None or not isinstance(item["rule_id"], str)
                    or not _valid_recovery(item["recovery"]) or not _valid_observation(item["observation"])
                    or item["observation"]["mode"] != ("content" if value["mode"] == "deep" else "metadata")
                    or disposition not in ("offered", "excluded", "below_minimum")):
                raise ValueError("Candidate fields")
            eligible.add(key)
            sums["eligible"] += size
            if disposition == "offered":
                sums["offered"] += size
                offered.append(item)
        elif disposition != "preserved" or item["observation"] is not None:
            raise ValueError("Protected item offered")
    for key in eligible:
        parts = key.split("/")
        if any("/".join(parts[:i]) in eligible for i in range(1, len(parts))):
            raise ValueError("Overlapping candidates")
    if offered != sorted(offered, key=lambda item: (-item["logical_bytes"], item["path"])):
        raise ValueError("Candidate order")
    if (sums["offered"] != totals["offered_logical_bytes"] or sums["eligible"] != totals["eligible_logical_bytes"]
            or sums["eligible"] > totals["observed_logical_bytes"] or len(offered) != totals["offered_count"]
            or labels["REVIEW"] != totals["review_count"] or labels["BLOCKED"] != totals["blocked_count"]
            or bool(offered) != (status == "READY_FOR_MANUAL_REVIEW") or status == "INCOMPLETE" and eligible):
        raise ValueError("Incoherent totals or status")


def _outside(path: Path, root: Path) -> None:
    if path.is_relative_to(root) or root.is_relative_to(path):
        raise UnsupportedRoot("Report storage must be outside the project and its ancestor directories.")


def validate_store(root: Path, output: str | None) -> Path:
    store = local_path(output if output is not None else report_directory() / "retirement")
    _outside(store, root)
    try:
        if output is not None:
            directory_chain(store)
        else:
            existing = next(path for path in (store, *store.parents) if path.exists())
            directory_chain(existing)
        canonical = store.resolve(strict=output is not None)
        _outside(canonical, root)
        if store != canonical:
            raise UnsupportedRoot("Report storage uses an unsafe or noncanonical alias.")
        mounts = mounted_filesystems()
        project_device = root.lstat().st_dev
        for path in (store, *store.parents):
            if path not in mounts:
                continue
            if external_filesystem(mounts[path]) or (path != Path(store.anchor) and path.lstat().st_dev == project_device):
                raise UnsupportedRoot("Report storage crosses an unsupported mount or same-device alias.")
        if os.name == "posix" and store.exists():
            _private_posix(store)
        if os.name == "nt":
            if not windows_local_drive(store):
                raise UnsupportedRoot("Report storage must be on a local drive.")
            if store.exists():
                validate_windows_private_directory(store)
    except OSError as exc:
        raise UnsupportedRoot("Report storage must be an accessible private directory.") from exc
    return store


def _private_posix(directory: Path) -> None:
    info = real_directory(directory)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise UnsupportedRoot("Report storage must be owned by you and grant access only to you.")


def _create_store(store: Path, root: Path) -> tuple[int, ...]:
    missing = []
    current = store
    while not current.exists():
        missing.append(current)
        current = current.parent
    directory_chain(current)
    for path in reversed(missing):
        _outside(path, root)
        directory_chain(path.parent)
        path.mkdir(mode=0o700, exist_ok=True)
        real_directory(path)
    validate_store(root, str(store))
    return stamp(store.lstat())[:3]


def _commit_file(directory: Path, name: str, data: bytes, guard, directory_fd: int | None) -> Path:
    guard()
    temporary_name = ".staging-" + uuid.uuid4().hex
    temporary = directory / temporary_name
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(temporary if directory_fd is None else temporary_name, flags, 0o600, dir_fd=directory_fd)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path = directory / name
    guard()
    if path.exists() or path.is_symlink():
        raise OSError("Unexpected report destination already exists.")
    if directory_fd is None:
        os.replace(temporary, path)
        _fsync_parent_directory(path)
    else:
        os.replace(temporary_name, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    return path


def _report_bytes(path: Path) -> bytes:
    expected = path.lstat()
    if expected.st_size > REPORT_LIMIT:
        raise InvalidPlan("The report exceeds the local size limit.")
    with open_observed(path, expected) as stream:
        data = stream.read(expected.st_size + 1)
        if len(data) != expected.st_size or not same_open_file(expected, os.fstat(stream.fileno())):
            raise InvalidPlan("The report changed while being read.")
    return data


def _json(content: bytes) -> dict:
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Repeated field")
        return result
    return json.loads(content, object_pairs_hook=unique)


def save_pair(body: dict, store: Path, root: Path, *, show_paths: bool) -> dict:
    body["digest"] = report_digest(body)
    validate_retirement_report(body)
    store_stamp = _create_store(store, root)
    run = store / ("retirement-" + body["report_id"])
    with ExitStack() as locks:
        for parent in reversed((store, *store.parents)):
            if parent != Path(store.anchor):
                locks.enter_context(pin_windows_directory(parent))
        if stamp(real_directory(store))[:3] != store_stamp:
            raise OSError("Report storage changed before saving.")
        run.mkdir(mode=0o700)
        locks.enter_context(pin_windows_directory(run))
        run_stamp = stamp(real_directory(run))[:3]
        directory_fd = None
        if os.name == "posix":
            directory_fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            locks.callback(os.close, directory_fd)
            if stamp(os.fstat(directory_fd))[:3] != run_stamp:
                raise OSError("The report directory changed before saving.")
        return _publish_pair(body, store, root, run, store_stamp, run_stamp, directory_fd, show_paths)


def _publish_pair(body, store, root, run, store_stamp, run_stamp, directory_fd, show_paths) -> dict:

    def guard():
        validate_store(root, str(store))
        if stamp(real_directory(store))[:3] != store_stamp or stamp(real_directory(run))[:3] != run_stamp:
            raise OSError("Report storage changed while saving.")

    raw = _encode(body) + b"\n"
    markdown = render_retirement(body, show_paths=show_paths).encode("utf-8")
    if max(len(raw), len(markdown)) > REPORT_LIMIT:
        raise OSError("Reports exceeded the local size limit.")
    json_path = _commit_file(run, "retirement.json", raw, guard, directory_fd)
    markdown_path = _commit_file(run, "retirement.md", markdown, guard, directory_fd)
    guard()
    if _report_bytes(json_path) != raw or _report_bytes(markdown_path) != markdown:
        raise OSError("Report pair did not match its generated contents.")
    marker = {"schema_version": 1, "report_id": body["report_id"], "json_sha256": _sha(raw),
              "markdown_sha256": _sha(markdown)}
    _commit_file(run, "complete.json", _encode(marker) + b"\n", guard, directory_fd)
    _fsync_parent_directory(run)
    return {"json": str(json_path.relative_to(store)), "markdown": str(markdown_path.relative_to(store)),
            "completion": str((run / "complete.json").relative_to(store))}


def load_retirement_report(path: Path) -> dict:
    try:
        path = local_path(path)
        raw = _report_bytes(path)
        value = _json(raw)
        validate_retirement_report(value)
        marker = _json(_report_bytes(path.with_name("complete.json")))
        markdown = _report_bytes(path.with_name("retirement.md"))
        if marker != {"schema_version": 1, "report_id": value["report_id"], "json_sha256": _sha(raw),
                       "markdown_sha256": _sha(markdown)}:
            raise InvalidPlan("The retirement report pair is incomplete or does not match its completion record.")
        return value
    except (OSError, ValueError, UnicodeError, RecursionError, UnsupportedRoot) as exc:
        raise InvalidPlan("Cannot verify the private retirement report pair.") from exc


def _code(value: str) -> str:
    value = "".join(c if c.isprintable() else json.dumps(c, ensure_ascii=True)[1:-1] for c in value)
    fence = "`" * (max((len(run) for run in re.findall(r"`+", value)), default=0) + 1)
    return f"{fence} {value} {fence}"


def _escape(value: str) -> str:
    value = "".join(c if c.isprintable() else json.dumps(c, ensure_ascii=True)[1:-1] for c in value)
    return re.sub(r"([\\`*_{}\[\]<>#!|])", r"\\\1", value)


def render_retirement(body: dict, *, show_paths: bool = False) -> str:
    totals = body["totals"]
    lines = ["# Hibernator retirement report", "", "**Private local report.** Keep both reports and the completion record together.",
             "", f"Status: **{body['status']}**", f"Mode: {body['mode']}",
             f"Report ID: {_code(body['report_id'])}",
             f"Selected Git root: {_code(body['root']) if show_paths else 'private local root'}",
             f"Observed working-tree file lengths: {totals['observed_logical_bytes']:,} bytes",
             f"Unmeasured boundaries: {totals['unmeasured_boundaries']}",
             f"Eligible before filters: {totals['eligible_logical_bytes']:,} bytes",
             f"Offered for manual review: {totals['offered_logical_bytes']:,} bytes",
             "", _escape(body["measurement_scope"]), "", "## Manual candidates", ""]
    for item in body["items"]:
        if item["disposition"] != "offered":
            continue
        recovery = item["recovery"]
        lines += [f"- {_code(item['display_path'])} · {item['logical_bytes']:,} bytes · {_code(item['rule_id'])}",
                  f"  - Evidence: {_escape(' '.join(item['evidence']))}",
                  f"  - Checked: {_escape('; '.join(item['checks']))}",
                  f"  - Recovery in {_code(recovery['working_directory'])}: {_escape(recovery['guidance'])}",
                  f"  - Preserve: {', '.join(_code(path) for path in recovery['preserve']) or 'associated source and configuration'}",
                  f"  - Observation: {item['observation']['mode']}. {_escape(' '.join(item['limitations']))}"]
    if not totals["offered_count"]:
        lines.append("No paths were offered for manual review.")
    for label, title in (("KEEP", "Keep"), ("REVIEW", "Keep and investigate"), ("BLOCKED", "Blocked"),
                         ("REGENERABLE", "Eligible paths preserved by filters")):
        lines += ["", f"## {title}", ""]
        listed = [item for item in body["items"] if item["decision"] == label and item["disposition"] != "offered"]
        if not listed:
            lines.append("None recorded.")
        for item in sorted(listed, key=lambda i: (-(i["logical_bytes"] or 0), i["display_path"])):
            size = "unknown size" if item["logical_bytes"] is None else f"{item['logical_bytes']:,} bytes"
            reason = item["reason"] if label != "REGENERABLE" else "Preserved by request or size threshold."
            lines.append(f"- {_code(item['display_path'])} · {size} · {_escape(reason)}")
    lines += ["", "## Technology coverage", ""]
    for label, values in body["technology_coverage"].items():
        lines.append(f"- {_escape(label)}: {_escape(', '.join(values)) or 'none observed'}")
    lines += ["", "## Limitations", ""]
    lines += [f"- {_escape(warning)}" for warning in body["incomplete_reasons"] + body["warnings"]]
    lines += ["", "## Owner review", ""]
    lines += [f"- [ ] {step}" for step in CHECKLIST]
    lines += ["", FOOTER, "", f"Private JSON body digest: {_code(body['digest'])}", ""]
    return "\n".join(lines)


def new_report_id() -> str:
    return uuid.uuid4().hex
