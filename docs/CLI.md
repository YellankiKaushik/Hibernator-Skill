# CLI reference

Use the installed `hibernator` command or the corresponding `python -m hibernator` invocation. Project commands accept one explicit local Git working-tree root.

## Commands

```text
hibernator retire --project PATH [--output DIRECTORY] [--deep] [--min-size-mib N] [--exclude RELATIVE_PATH ...] [--show-paths] [--format text|json]
hibernator verify --report FILE [--format text|json]
hibernator report --retirement-file FILE [--format text|json]
hibernator scan --project PATH [--save-report] [--show-paths] [--format text|json]
hibernator plan --project PATH [--output FILE] [--exclude RELATIVE_PATH ...] [--format text|json]
hibernator apply --plan PATH [--format text|json]
hibernator report (--id ID | --file FILE) [--format text|json]
hibernator restore --project PATH --dry-run [--show-paths] [--format text|json]
hibernator doctor [--format text|json]
hibernator rules list [--format text|json]
```

## Retirement and private reports

- A relative project path is resolved from the caller's current directory. Use an existing private `--output` directory outside the project and its ancestors. The default is `%LOCALAPPDATA%\hibernator\reports\retirement` on Windows or `${XDG_STATE_HOME:-$HOME/.local/state}/hibernator/reports/retirement` on Linux and macOS.
- The output lists report paths relative to the report store. `--show-paths` exposes absolute paths for local use. Every run has a unique directory.
- `--exclude` accepts exact normalized candidate paths separated by forward slashes. Repeat the option for additional paths. Globs, traversal, aliases and unknown exclusions are rejected.
- One MiB is 1,048,576 bytes. The minimum is converted to the smallest whole-byte threshold satisfying the given decimal. Excluded and below-minimum artifacts remain recorded as preserved and do not contribute to offered bytes.
- Fast mode observes metadata and reads bounded recovery evidence. Deep mode also hashes eligible file contents. Both modes describe uncertainty. JSON stdout carries one summary object and the largest eight paths. Stages and throttled progress go to stderr.

### Report schema 1

A retirement run holds `retirement.json`, `retirement.md` and `complete.json`. JSON contains the report type, version, run ID, private root and identity, mode, local Git and tracked metadata observations, timestamps, incomplete reasons, technology coverage, measurements, decisions, evidence and recovery fields. The body digest is SHA-256 over an ASCII JSON serialization with sorted keys, compact separators, escaped non-ASCII characters, no NaN, and the digest field omitted. The completion record binds exact bytes of both reports to the run ID. Files are flushed and committed individually, and the marker is committed last. This detects incomplete pairs after interruption. Digests provide consistency checks. Keep all three files in the same private directory.

`report --retirement-file` validates and renders the retirement pair. `report --file` and `report --id` continue to read legacy scan and fixture reports. `verify` validates the private pair, rechecks the bound project and observes only the offered directory entries. It reports `PRESENT`, `CHANGED`, `MISSING_SINCE_SCAN` or `UNKNOWN`. Candidate descendants and tracked working-tree contents are outside follow-up verification. Run it only on a separate request.

## Legacy apply and exit statuses

`apply` accepts the old option shape and immediately returns `APPLY_UNSUPPORTED`. It reads no plan, receives no input, runs no inspection and writes no refusal file. Legacy plans retain their distinct schema-2 content fingerprints.

| Exit | Meaning |
| --- | --- |
| 0 | Completed retirement (`READY_FOR_MANUAL_REVIEW` or `NO_CANDIDATES`), successful observation or legacy command |
| 2 | Invalid input, root or output directory |
| 3 | Incomplete inspection or unknown verification entry |
| 4 | Invalid, tampered, incomplete or stale report or plan |
| 5 | Legacy apply refused |
| 6–7 | Reserved legacy statuses |
| 8 | Unexpected I/O failure, including incomplete report-pair write |
| 130 | Interrupted |

`READY_FOR_MANUAL_REVIEW` means an advisory pair exists. `FAILED` indicates an invalid request or unexpected inspection error. `INCOMPLETE` suppresses actionable candidates. Hibernator reclaims zero bytes.
