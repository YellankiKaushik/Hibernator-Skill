from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from . import RULE_PACK_VERSION, __version__
from .approval import confirm_exact_plan
from .discovery import scan
from .errors import ApplyRefused, HibernatorError, InvalidPlan
from .plans import load_plan, make_plan, save_plan, validate_current
from .reports import cleanup_report, load_report, load_report_file, render_report, report_directory, save_report, write_scan_report
from .restore import restore_preview
from .rules import RULES


EXIT = {"ok": 0, "input": 2, "incomplete": 3, "plan": 4, "approval": 5, "partial": 6, "critical": 7, "internal": 8}


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hibernator", description="Scan, classify, and prepare a safe local project hibernation plan.")
    parser.add_argument("--version", action="version", version=f"Hibernator {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_cmd = commands.add_parser("scan", help="Read-only project inventory and classification")
    scan_cmd.add_argument("--project", required=True, metavar="PATH")
    scan_cmd.add_argument("--save-report", action="store_true")
    scan_cmd.add_argument("--show-paths", action="store_true", help="Include absolute project paths in this local output")
    _add_format(scan_cmd)
    plan_cmd = commands.add_parser("plan", help="Create a reviewable immutable cleanup plan")
    plan_cmd.add_argument("--project", required=True, metavar="PATH")
    plan_cmd.add_argument("--exclude", action="append", default=[], metavar="RELATIVE_PATH")
    plan_cmd.add_argument("--output", type=Path)
    _add_format(plan_cmd)
    apply_cmd = commands.add_parser("apply", help="Request exact human approval for a plan")
    apply_cmd.add_argument("--plan", required=True, type=Path)
    _add_format(apply_cmd)
    report_cmd = commands.add_parser("report", help="Display a saved JSON report")
    report_source = report_cmd.add_mutually_exclusive_group(required=True)
    report_source.add_argument("--id", help="Load a report from the local report store")
    report_source.add_argument("--file", type=Path, help="Load a report JSON file by path")
    _add_format(report_cmd)
    restore_cmd = commands.add_parser("restore", help="Show a non-mutating restoration preview")
    restore_cmd.add_argument("--project", required=True, metavar="PATH")
    restore_cmd.add_argument("--dry-run", action="store_true", required=True)
    restore_cmd.add_argument("--show-paths", action="store_true", help="Include the absolute project path in this local output")
    _add_format(restore_cmd)
    doctor_cmd = commands.add_parser("doctor", help="Check local runtime capabilities")
    _add_format(doctor_cmd)
    rules_cmd = commands.add_parser("rules", help="Inspect the versioned artifact rules")
    rules_sub = rules_cmd.add_subparsers(dest="rules_command", required=True)
    list_cmd = rules_sub.add_parser("list", help="List allowlisted artifact rules")
    _add_format(list_cmd)
    return parser


def _print_json(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _render_scan(report: dict) -> str:
    lines = [f"Project: {report['root']}", f"Technologies: {', '.join(report['technologies']) or 'not detected'}", f"Total logical size: {report['total_logical_bytes']} bytes", "", "CLASSIFICATION"]
    for item in report["items"]:
        size = f"{item['logical_bytes']} bytes" if item["logical_bytes"] else "size unavailable/zero"
        rule = f" | {item['rule_id']}" if item["rule_id"] else ""
        lines.append(f"{item['decision']:<12} {item['path']} | {item['category']} | {size}{rule}")
        lines.append(f"  {item['reason']}")
        if item["decision"] == "REGENERABLE":
            lines.append(f"  Restore: {item['restore_hint']}")
    lines.append("No files were changed by this scan.")
    return "\n".join(lines)


def _default_plan_path(plan: dict) -> Path:
    directory = report_directory()
    root = Path(plan["root"]).resolve(strict=True)
    try:
        directory.resolve(strict=False).relative_to(root)
    except ValueError:
        pass
    else:
        directory = root.parent / ".hibernator-state" / "plans"
    return directory / f"plan-{plan['plan_id']}.json"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_format = getattr(args, "format", "text")
    try:
        if args.command == "scan":
            value = scan(args.project).to_dict()
            if args.save_report:
                value["saved_report"] = str(write_scan_report(args.project, value))
            if not args.show_paths:
                value["root"] = "."
                value["git_root"] = "."
                value["root_redacted"] = True
            if output_format == "json":
                _print_json(value)
            else:
                print(_render_scan(value))
                if args.save_report:
                    print(f"Saved report: {value['saved_report']}")
            return EXIT["incomplete"] if value["errors"] else EXIT["ok"]
        if args.command == "plan":
            value = make_plan(args.project, args.exclude)
            target = args.output or _default_plan_path(value)
            save_plan(value, target)
            display = {**value, "saved_plan": str(target)}
            if output_format == "json":
                _print_json(display)
            else:
                print(f"Project root: {value['root']}")
                print(f"Plan digest: {value['digest']}")
                print(f"Eligible candidates: {len(value['candidates'])}; estimated logical bytes: {value['estimated_logical_bytes']}")
                for candidate in value["candidates"]:
                    print(f"  {candidate['path']} ({candidate['logical_bytes']} bytes) - {candidate['reason']}")
                print(f"Saved plan: {target}")
                print("Review the complete list. Production apply is disabled pending platform security review.")
            return EXIT["ok"]
        if args.command == "apply":
            plan = load_plan(args.plan)
            validate_current(plan)
            root = Path(plan["root"])
            before_scan = scan(root).to_dict()
            before_free = shutil.disk_usage(root).free
            if not sys.stdin.isatty():
                status = "APPROVAL_REQUIRED"
                outcomes = [{"path": item["path"], "status": "NOT_ATTEMPTED", "reason": "A direct human-operated terminal is required."} for item in plan["candidates"]]
                integrity = "verified before apply request; no files changed"
                exit_code = EXIT["approval"]
            else:
                try:
                    confirm_exact_plan(plan, input_fn=input, output=sys.stderr if output_format == "json" else sys.stdout)
                except (ApplyRefused, EOFError) as exc:
                    status = "DECLINED"
                    outcomes = [{"path": item["path"], "status": "NOT_ATTEMPTED", "reason": str(exc) or "No approval was provided."} for item in plan["candidates"]]
                    integrity = "verified before approval refusal; no files changed"
                    exit_code = EXIT["approval"]
                else:
                    status = "APPROVED_BUT_UNSUPPORTED"
                    outcomes = [{"path": item["path"], "status": "NOT_ATTEMPTED", "reason": "Exact plan approval was recorded, but production cleanup is disabled pending platform security review."} for item in plan["candidates"]]
                    integrity = "verified before unsupported apply; no files changed"
                    exit_code = EXIT["incomplete"]
            after_scan = scan(root).to_dict()
            after_free = shutil.disk_usage(root).free
            report = cleanup_report(
                plan, outcomes, status, before_scan=before_scan, after_scan=after_scan,
                before_free=before_free, after_free=after_free, git_integrity=integrity,
            )
            report_path = save_report(report, directory=report_directory(), project_root=root)
            report["saved_report"] = str(report_path)
            if output_format == "json":
                _print_json(report)
            else:
                print(render_report(report))
                print("No files were changed. Real cleanup is unsupported in this build.")
            return exit_code
        if args.command == "report":
            try:
                value = load_report(args.id) if args.id else load_report_file(args.file)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise InvalidPlan(f"Cannot read report: {exc}") from exc
            if output_format == "json":
                _print_json(value)
            else:
                print(render_report(value))
            return EXIT["ok"]
        if args.command == "restore":
            value = restore_preview(args.project)
            if not args.show_paths:
                value["root"] = "."
                value["root_redacted"] = True
            if output_format == "json":
                _print_json(value)
            else:
                print(f"Restore status: {value['status']}\nProject: {value['root']}\n")
                for command in value["commands"]:
                    print(f"  {command}")
                for warning in value["warnings"]:
                    print(f"Warning: {warning}")
            return EXIT["ok"] if value["commands"] else EXIT["incomplete"]
        if args.command == "doctor":
            value = {
                "version": __version__, "python": platform.python_version(), "minimum_python": "3.10",
                "git_available": shutil.which("git") is not None, "platform": platform.platform(),
                "destructive_apply": "disabled pending platform security review",
                "reports_directory": str(report_directory()),
            }
            if output_format == "json":
                _print_json(value)
            else:
                for key, item in value.items():
                    print(f"{key.replace('_', ' ').title()}: {item}")
            return EXIT["ok"] if value["git_available"] else EXIT["input"]
        if args.command == "rules":
            value = {"rule_pack_version": RULE_PACK_VERSION, "rules": RULES}
            if output_format == "json":
                _print_json(value)
            else:
                print(f"Rule pack {RULE_PACK_VERSION}")
                for rule in RULES:
                    required = f"; required={', '.join(rule['requires'])}" if rule.get("requires") else ""
                    print(f"{rule['id']}: {rule['kind']} paths={', '.join(rule['paths'])}{required}; any-context={', '.join(rule['context'])}")
            return EXIT["ok"]
    except ApplyRefused as exc:
        if output_format == "json":
            _print_json({"error": str(exc), "code": "APPLY_REFUSED"})
        else:
            print(f"Apply refused: {exc}", file=sys.stderr)
        return EXIT["approval"]
    except InvalidPlan as exc:
        if output_format == "json":
            _print_json({"error": str(exc), "code": "INVALID_PLAN"})
        else:
            print(f"Invalid plan/report: {exc}", file=sys.stderr)
        return EXIT["plan"]
    except HibernatorError as exc:
        if output_format == "json":
            _print_json({"error": str(exc), "code": "HIBERNATOR_ERROR"})
        else:
            print(f"Hibernator: {exc}", file=sys.stderr)
        return EXIT["input"]
    except OSError as exc:
        if output_format == "json":
            _print_json({"error": str(exc), "code": "IO_ERROR"})
        else:
            print(f"I/O error: {exc}", file=sys.stderr)
        return EXIT["internal"]
    return EXIT["internal"]


if __name__ == "__main__":
    raise SystemExit(main())
