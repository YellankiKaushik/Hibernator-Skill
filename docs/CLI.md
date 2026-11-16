# CLI reference

Hibernator targets one existing Git repository root. Scan, plan, and restore preview are read-only with respect to that project. Reports are stored in the user's local application state directory, outside the project. Exported scan/cleanup reports redact the absolute project root; `scan` and `restore` also redact it in output by default. Use `--show-paths` only when displaying local output that should contain the absolute path. Plan files include the exact root so the owner can review the bound target before approval.

## Commands

```text
hibernator scan --project PATH [--save-report] [--show-paths] [--format text|json]
hibernator plan --project PATH [--exclude RELATIVE_PATH ...] [--output PATH] [--format text|json]
hibernator apply --plan PATH [--format text|json]
hibernator report (--id 32_HEX_ID | --file PATH) [--format text|json]
hibernator restore --project PATH --dry-run [--show-paths] [--format text|json]
hibernator doctor [--format text|json]
hibernator rules list [--format text|json]
```

The same commands work through `python -m hibernator`. Text is the default. JSON is versioned for saved reports (`schema_version: "1"`); saved plan files use plan schema `2`. Scan items carry relative paths, a decision, category, logical byte estimate, reason, matching rule where applicable, and restoration hint. Cleanup reports separate calculated candidate bytes, logical bytes removed, remaining project logical bytes, and observed volume free-space delta. The volume delta is advisory and may include unrelated activity or filesystem behavior.

## Apply and approval status

Noninteractive apply refuses and saves an `APPROVAL_REQUIRED` report (exit 5). In a direct interactive terminal, Hibernator shows the exact root, digest, candidate list, protected/blocked/review items, estimate, and recovery warning, then requests `DELETE <full-plan-digest>`. A mismatch saves `DECLINED` (exit 5). Exact approval saves `APPROVED_BUT_UNSUPPORTED` (exit 3): **it still performs no deletion** because production apply is disabled pending independent filesystem security review. Reports may be loaded with `report --id ID` or `report --file PATH`.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Command completed; for restore, a supported preview was produced |
| 2 | Invalid/unsupported root or other Hibernator input error |
| 3 | Incomplete, unverified, or unsupported operation; includes production apply refusal |
| 4 | Invalid, tampered, stale, or unreadable plan/report |
| 5 | Approval is unavailable or was declined |
| 6 | Partial cleanup outcome (reserved; production cleanup is disabled) |
| 7 | Critical preservation/integrity failure (reserved; production cleanup is disabled) |
| 8 | Internal or filesystem I/O error |

No `--yes` option exists. Do not treat a plan digest as proof of human identity or as authorization to invoke another deletion tool.
