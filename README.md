# Hibernator

Hibernator helps developers reclaim space from one inactive project while preserving its code, Git history, local-only work, secrets, databases, downloads, and unknown files.

Its workflow is **Scan → Classify → Validate → Human approval → Clean → Report**. The local CLI performs deterministic inspection without an AI model or network service. Candidate names alone never authorize removal: supported manifest or lockfile evidence is required, and any tracked, protected, unknown, linked, or unreadable content keeps a directory out of the cleanup plan.

> **Preview-only implementation — production deletion is disabled.** Scanning, classification, plans, reporting, and restore previews are available in source. Destructive apply remains disabled until filesystem-specific race safety and human approval controls receive security review. The cleanup engine is exercised only by marked synthetic Git fixtures in the test suite.

## What it does

- Reads one explicit Git repository at a time; non-Git roots and repository subdirectories are refused.
- Detects Python, Node.js, React, Next.js, and Vite project markers.
- Classifies inventory as `KEEP`, `REGENERABLE`, `REVIEW`, or `BLOCKED` with reason, size estimate, rule, and restore hint.
- Protects tracked files, `.env`-style secrets, common local data, nested Git repositories, symlinks/reparse points, and unknown ignored files.
- Creates a canonical SHA-256 plan bound to the root, Git snapshot, rule version, and candidate identities. The digest detects changes; it does not authenticate an approver.
- Shows JSON or plain-text output, and a non-mutating restore preview.
- Makes no network calls and never invokes package managers during scan or restore preview.

## Requirements

- Python 3.10 or newer
- Git available on `PATH`

The CLI has no third-party runtime dependencies. Building/installing the package uses its declared setuptools build backend, which may need to be available in the local package cache. No license has been selected yet; see [the owner decision](docs/LICENSE-DECISION.md). Until a license is added, reuse and redistribution rights are not granted by this repository.

## Quick start

From a checkout of this repository:

```text
python -m venv .venv
python -m pip install -e .
hibernator doctor
hibernator scan --project "C:\path\to\your\git-project"
hibernator plan --project "C:\path\to\your\git-project"
hibernator restore --project "C:\path\to\your\git-project" --dry-run
```

You can also use `python -m hibernator ...` instead of the installed `hibernator` command. Plans and saved reports are written under the user's local application state directory, outside the scanned project. Reports redact the absolute project root. Use `scan --save-report` to save a scan report; apply attempts save a cleanup status report even when approval is unavailable or production cleanup is disabled. Display reports with `report --id ID` or `report --file PATH`. Use `--format json` for machine-readable output. For command details, run `python -m hibernator --help`.

### Commands

| Command | Behavior |
|---|---|
| `scan --project PATH` | Read-only inventory and classification |
| `plan --project PATH [--exclude RELATIVE_PATH]` | Create an immutable, reviewable plan |
| `apply --plan PATH` | Requests the exact digest in an interactive terminal, records an approval/refusal report, and refuses production deletion in this MVP |
| `report --id ID` or `report --file PATH` | Display a saved scan or cleanup report |
| `restore --project PATH --dry-run` | Print proposed restoration steps; no install or write |
| `rules list` | Show versioned allowlisted rules |
| `doctor` | Show local runtime and safety status |

## Example

Synthetic output only; the sizes below are illustrative and not benchmark claims:

```text
REGENERABLE  node_modules | dependency | 1400000 bytes | node-dependencies-v1
  Recognized artifact with matching project manifest/lockfile; no protected descendants detected.
  Restore: use the preserved package manager lockfile.
KEEP         src | source | 240 bytes
REVIEW       .env.local | local-data | 30 bytes
```

An ignored `.env`, local database, dataset, model, upload, unrecognized cache, or user file remains protected or under review. A directory called `cache` or `build` is not eligible merely because of its name.

## Agent integrations

The canonical skill is [.agents/skills/hibernator/SKILL.md](.agents/skills/hibernator/SKILL.md). Installing this skill and installing the Python CLI are separate steps; see [agent setup](docs/AGENTS.md). The Skills CLI installation smoke test passed for both project and user scope in disposable locations. A read-only scan workflow also ran successfully in this Codex session on a disposable Git project. A separate `codex exec` invocation remains unverified because the installed CLI rejected the configured model for this ChatGPT account. Gemini CLI was unavailable; the Antigravity launcher was present, but desktop control could not initialize for a host invocation. A packaged or installed skill alone does not prove that a host can invoke it.

## Safety and recovery

Read [the safety model](docs/SAFETY.md) before using plans. A plan digest is an integrity check, not authentication. Agents must not impersonate a human approver. Real cleanup is disabled pending a platform security review. See the [independent review gate](docs/SECURITY_REVIEW_GATE.md) and [release gate matrix](docs/RELEASE_GATE_MATRIX.md). If cleanup is enabled in a later release, approval must be direct, interactive, and bound to the exact root and digest.

Restore guidance only describes regenerating supported dependencies. Monorepo grouping, nested projects, and ambiguity warnings are detailed in [restoration guidance](docs/RESTORE_GUIDANCE.md). It cannot recreate deleted personal data, private downloads, secrets, databases, or remote services. `restore --dry-run` never executes installers; package managers may use the network and run lifecycle scripts when a developer later chooses to run them.

## Development

```text
python -m unittest discover -v
```

Tests construct and delete only their own temporary Git fixtures. They do not target the checkout or any real project. See [architecture](docs/ARCHITECTURE.md), [CLI reference](docs/CLI.md), [usage examples](docs/USAGE_EXAMPLES.md), [FAQ](docs/FAQ.md), [test coverage](docs/TESTING.md), [contributing](docs/CONTRIBUTING.md), and [security reporting](SECURITY.md).

## Platform and host verification

The [GitHub Actions run for the published revision](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43814217765) completed successfully: all 18 jobs passed across Windows, Ubuntu, and macOS, with Python 3.10–3.14. Each full unittest job ran 52 tests and skipped three Windows-junction cases; those skips are unverified behavior, not passes. Wheel build, fresh-environment installation, console entry point, and packaged skill-file checks passed in the matrix.

| Environment | Status |
|---|---|
| Windows | Python 3.10–3.14 passed in GitHub Actions; three Windows-junction tests skipped in each full suite. Local Windows 3.14 run skipped six link/junction cases due host restrictions. |
| Linux | Python 3.10–3.14 passed in GitHub Actions; Windows-junction cases skipped by design. |
| macOS | Python 3.10–3.14 passed in GitHub Actions; Windows-junction cases skipped by design. |
| Codex | Skill metadata was surfaced in the current session; a separate invocation from an unrelated project is not yet verified. |
| Gemini CLI, Antigravity | Skill packaged; discovery and invocation not tested. |
| Claude Code | Not included in MVP |

Do not interpret a documented discovery path as a tested compatibility claim. See [CHANGELOG](CHANGELOG.md) for implementation status and [release checklist](docs/RELEASE.md) for outstanding owner gates.

## Uninstall

Uninstall the local Python package with `python -m pip uninstall hibernator-skill`, then remove the copied or installed skill directory if you added one. Scan reports/plans are stored separately in the user's application state directory and may be removed by the user. Uninstalling Hibernator does not change scanned projects.
