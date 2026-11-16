# Hibernator

**PREVIEW — PRODUCTION DELETION DISABLED**

Hibernator is a local, Git-aware Python tool for inspecting one development repository, identifying a small set of well-evidenced generated dependencies or caches, and preparing a reviewable plan. It helps developers understand why inactive projects grow: package installations, virtual environments, bytecode, and framework caches can remain long after the work is done.

The preview can scan, classify, validate plans, save reports, and show restoration guidance. It **cannot delete files from a user's project**. Even a correct interactive approval ends with an unsupported-operation report and no project changes. No disk space is reclaimed by this version.

Current cross-platform validation: [GitHub Actions run #13](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43848601766) passed 18/18 jobs on the consolidated `main` commit. See the [release gate matrix](docs/RELEASE_GATE_MATRIX.md) for platform skips and remaining security gates.

## Contents

- [Overview](#overview)
- [How it works](#how-it-works)
- [Features and supported project types](#features-and-supported-project-types)
- [Requirements and verified platforms](#requirements-and-verified-platforms)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Command reference](#command-reference)
- [Examples](#examples)
- [AI-agent integrations](#ai-agent-integrations)
- [Security and privacy](#security-and-privacy)
- [Restoration and recovery](#restoration-and-recovery)
- [Troubleshooting](#troubleshooting)
- [Development and contributions](#development-and-contributions)
- [License and roadmap](#license-and-roadmap)
- [Uninstall](#uninstall)

## Overview

Inactive repositories can retain `node_modules`, Python virtual environments, test caches, bytecode, and framework build caches. Their names alone do not prove that their contents are safe to remove. A dependency directory may also contain local patches, secrets, downloaded data, or files somebody deliberately saved there.

Hibernator is for developers reviewing **one existing Git repository at a time**. It gives a conservative inventory, explains its decisions, estimates logical file lengths, and creates a plan bound to the repository and its current state. It does not replace backups, version control, or human review.

### Decisions shown by a scan

| Decision | Meaning |
|---|---|
| `KEEP` | Known source, tracked content, secret-like content, or other content that the scanner preserves. |
| `REGENERABLE` | A narrow artifact rule matched project evidence and the candidate contains no detected protected descendants. It can be proposed in a plan; this preview still will not delete it. |
| `REVIEW` | The scanner cannot establish safe regeneration, such as for unknown files, local data, downloads, missing manifests, or ambiguous project context. |
| `BLOCKED` | A recognized candidate failed a safety check, for example because it contains tracked content, a link/reparse point, nested Git data, a filesystem boundary, or unreadable content. |

Ignore rules, download source, generated-looking names, or a directory called `cache`, `build`, `.venv`, or `node_modules` are never enough on their own. Unknown files remain protected or visible for review.

Tracked files, untracked local work, `.env` secrets, local databases, datasets, uploads, model files, and unknown content are preserved or marked for review. If any protected content is inside a candidate directory, the whole candidate is blocked.

## How it works

The intended product workflow is **Scan → Classify → Validate → Human approval → Clean → Report**:

1. **Scan:** read one selected Git repository and summarize technologies, paths, and logical sizes.
2. **Classify:** apply versioned, positive-evidence rules and report a reason for every surfaced item.
3. **Validate:** bind a plan to the project root identity, Git state, candidate identity and contents, exclusions, and rule version. A later change makes the plan stale.
4. **Human approval:** display the exact plan and request its full digest in an interactive terminal. A digest is an integrity check, not proof of who typed it.
5. **Clean:** **unavailable for real projects in this preview**. The production `apply` path refuses on every platform. A separate POSIX prototype is wired only to synthetic test fixtures.
6. **Report:** save a local status report. The report distinguishes candidate logical bytes and observed volume free-space changes; it does not attribute free-space changes to Hibernator.

## Features and supported project types

### Available in the preview

- Standalone Python CLI and `python -m hibernator` entry point.
- Git root, tracked-file, and worktree-state checks.
- Conservative artifact classification and digest-bound plans with stale-plan validation.
- Text and JSON scan, plan, rule, report, and restore-preview output.
- React, Next.js, and Vite technology markers within Node.js projects.
- Monorepo restoration suggestions that group Node workspace packages by lockfile and show per-project working directories.
- Local scan and cleanup status reports with redacted project root fields.
- Packaged Agent Skill at `.agents/skills/hibernator/SKILL.md`.

### Currently recognized rules

| Artifact | Evidence required | Example restoration suggestion |
|---|---|---|
| `node_modules` | `package.json` and a recognized npm, pnpm, or Yarn lockfile | `npm ci`, `pnpm install --frozen-lockfile`, or `yarn install --immutable` |
| `.venv` or `venv` | Python project manifest evidence, plus conservative content checks | Create a virtual environment and reinstall from preserved project metadata |
| `__pycache__` | Python source marker | Python recreates bytecode when run |
| `.pytest_cache` | Pytest configuration or project metadata | Pytest recreates its cache |
| `.next/cache` | Next.js configuration or a `next` package dependency | Next.js recreates the framework cache |
| `node_modules/.vite` | Vite configuration or package dependency | Vite recreates its optimization cache |

Rules are intentionally limited. Node package `data/` directories and arbitrary editable-install `.pth` files are not assumed disposable. See [classification details](docs/DEPENDENCY_CLASSIFICATION.md).

### Not available

- Deleting or moving real project files.
- Installing or uninstalling dependencies during scan or restore preview.
- Network access during scan, plan, report, or restore preview.
- Guaranteed storage savings or physical block-reclamation estimates.
- Recovery of local-only files, private downloads, secrets, databases, credentials, or remote services.

## Requirements and verified platforms

- Windows, Linux, or macOS with Python **3.10–3.14** and Git available on `PATH`.
- The CLI uses the Python standard library at runtime.
- Package installation/build uses `setuptools>=77` through PEP 517. An isolated build may need a package index or a compatible setuptools build dependency already available.
- Hibernator does not require an AI model. Agent invocation requires a compatible host with local terminal access and a separately installed Python CLI.

The full workflow matrix has passed on GitHub Actions for Windows, Ubuntu, and macOS with Python 3.10–3.14. That verifies preview tests, wheel construction, console command startup, and packaged skill-file presence. It does **not** certify production deletion or every filesystem. Windows junction cases are skipped on the hosted runners; skips remain unverified. See [the release gate matrix](docs/RELEASE_GATE_MATRIX.md) for the current evidence.

## Installation

Clone the repository, then install the Python package into a virtual environment. Skill installation is a separate step; see [AI-agent integrations](#ai-agent-integrations).

### Windows PowerShell

```powershell
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
Set-Location Hibernator-Skill
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\hibernator.exe doctor
```

### Linux shell

```sh
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
cd Hibernator-Skill
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/hibernator doctor
```

### macOS Terminal

```sh
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
cd Hibernator-Skill
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/hibernator doctor
```

For development, use `python -m pip install -e .` instead of `python -m pip install .`. Activation is optional: invoke the virtual environment's `python` and `hibernator` paths directly, as above. If PowerShell blocks activation scripts, these direct paths avoid activation entirely.

To use the module without installing the console entry point from a checkout, run `python -m hibernator ...` from the checkout with the same interpreter that has the package available. Check the interpreter with `python --version`; Hibernator requires 3.10 or later.

## Quick start

Use a repository you own and have reviewed. The commands below only scan, plan, and preview restoration; the preview cannot delete files.

```sh
hibernator doctor
hibernator scan --project PATH
hibernator plan --project PATH
hibernator restore --project PATH --dry-run
```

On Windows PowerShell, quote paths that contain spaces:

```powershell
hibernator scan --project "C:\work\My Project"
hibernator plan --project "C:\work\My Project" --output "$env:TEMP\hibernator-plan.json"
hibernator restore --project "C:\work\My Project" --dry-run
```

On Unix-like shells:

```sh
hibernator scan --project "$HOME/work/my-project"
hibernator plan --project "$HOME/work/my-project" --output "$HOME/hibernator-plan.json"
hibernator restore --project "$HOME/work/my-project" --dry-run
```

Read each scan reason and the complete plan before continuing. `apply` revalidates the saved plan, but it always refuses actual cleanup in this version—even after an exact interactive digest is entered. For a safe hands-on walkthrough, use only the generated disposable fixture in [`docs/USER_TESTING.md`](docs/USER_TESTING.md).

### Inspecting output and reports

Use `--format json` on supported commands for structured output. `scan --save-report` stores a local scan report. An `apply` request stores a cleanup status report even though it does not delete. Each report includes a report ID that can be read with `report --id ID`; a report file can also be read with `report --file PATH`.

Reports are stored outside the scanned project: under `%LOCALAPPDATA%\hibernator\reports` on Windows, or `$XDG_STATE_HOME/hibernator/reports` (falling back to `~/.local/state/hibernator/reports`) on Linux/macOS. Saved reports redact the absolute project root, but still contain relative filenames and project structure; review them before sharing. Plan files include the selected absolute root and should also be treated as local project metadata.

## Command reference

Run `hibernator --help` or `python -m hibernator --help` for current syntax.

| Command | Options | Purpose |
|---|---|---|
| `hibernator doctor` | `--format text\|json` | Show Python, Git availability, platform, reports directory, and deletion-disabled status. |
| `hibernator scan --project PATH` | `--format text\|json`, `--show-paths`, `--save-report` | Read-only inventory, technology markers, classifications, and logical byte lengths. Absolute paths are redacted by default. |
| `hibernator plan --project PATH` | `--format text\|json`, repeatable `--exclude RELATIVE_PATH`, `--output PATH` | Create and save a reviewable plan outside the selected project. |
| `hibernator apply --plan PATH` | `--format text\|json` | Revalidate and request exact interactive confirmation; then records `APPROVED_BUT_UNSUPPORTED` without deleting. Noninteractive use records `APPROVAL_REQUIRED`. |
| `hibernator report --id ID` | `--format text\|json` | Load a report by its 32-character ID from the local report store. |
| `hibernator report --file PATH` | `--format text\|json` | Load a report from a specified JSON file. |
| `hibernator restore --project PATH --dry-run` | `--format text\|json`, `--show-paths` | Print non-mutating dependency restoration suggestions. `--dry-run` is required. |
| `hibernator rules list` | `--format text\|json` | Display the versioned artifact rules. |

`--show-paths` includes absolute project paths in local output. Scan and restore default to redacting them. Plans deliberately retain the full root because validation is bound to the exact target.

### Exit codes

| Code | Meaning |
|---:|---|
| `0` | Command completed; restore produced at least one suggestion. |
| `2` | Invalid or unsupported input/project root, or Git is unavailable to `doctor`. |
| `3` | Incomplete, unverified, or unsupported operation; includes exact approval with production cleanup disabled, or restore with no supported command. |
| `4` | Invalid, tampered, stale, or unreadable plan/report. |
| `5` | Approval is unavailable or was declined. |
| `6` | Partial cleanup outcome; reserved while production cleanup is disabled. |
| `7` | Critical preservation/integrity failure; reserved while production cleanup is disabled. |
| `8` | Internal or filesystem I/O error. |

For details, refer to the [CLI reference](docs/CLI.md).

## Examples

All paths and data descriptions in this section are illustrative; examples are not benchmark results.

### Node.js

With `package.json`, `package-lock.json`, `src/`, and `node_modules/`, Hibernator can identify the dependency directory as a candidate when the tree contains no protected or unknown descendants. The plan remains a proposal; real cleanup is unavailable.

```sh
hibernator scan --project ./sample-node-app
hibernator plan --project ./sample-node-app --exclude node_modules
hibernator restore --project ./sample-node-app --dry-run
```

An untracked patch or `.env` file inside `node_modules`, a nested Git repository, a link, or an unknown file blocks the whole candidate. Package `data/` directories remain conservative because downloaded or modified content cannot be ruled out by package name alone.

### Python

With `pyproject.toml` and `.venv/`, Hibernator reports the Python project markers and may classify a verified environment as regenerable. Editable-install files are accepted only when their generated metadata verifies a local editable source inside the project. External or unverified `.pth` targets stay protected.

```sh
hibernator scan --project ./sample-python-app --format json
hibernator plan --project ./sample-python-app
hibernator restore --project ./sample-python-app --dry-run
```

### React, Next.js, and Vite

The scanner detects React from package dependencies, Next.js from its dependency or configuration, and Vite from its dependency or configuration. A `.next/cache` candidate needs Next.js evidence. Lockfiles determine Node restore suggestions; multiple lockfiles cause an ambiguity warning instead of a guessed package manager.

```sh
hibernator scan --project ./sample-next-app
hibernator restore --project ./sample-next-app --dry-run
```

### Monorepo

The restore preview groups Node manifests by their nearest recognized ancestor lockfile. Independently locked nested projects get separate working-directory suggestions; conflicting lockfiles and packages without a supported lockfile are reported for review. Python projects receive per-project virtual-environment suggestions.

```sh
hibernator restore --project ./sample-monorepo --dry-run --format json
```

Restoration commands are suggestions only. Review the working directory, lockfile, private registry requirements, and lifecycle scripts before running any package manager yourself.

## AI-agent integrations

An **Agent Skill** is a folder containing `SKILL.md` instructions that a compatible host can discover and apply to relevant tasks. Hibernator's skill delegates classification to the local CLI; the skill does not install that CLI. Install the skill and Python package separately.

### OpenAI Codex

The repository includes a project-level skill at `.agents/skills/hibernator/SKILL.md`. When using the cloned project as the target workspace, Codex can discover that project skill. To install it through GitHub CLI (`gh skill`) from a local checkout:

```sh
gh skill install /path/to/Hibernator-Skill hibernator --from-local --allow-hidden-dirs --agent codex --scope project
```

Use `--scope user` for a user-wide installation. Verify the resulting skill with Codex's skill listing. This installs instructions only; install the Python package separately. In this project environment, a Codex session successfully followed the skill's scan workflow on a disposable Git repository. A separate `codex exec` run with the configured model was not verified.

### Gemini CLI

Gemini CLI documents `.agents/skills/` as a workspace and user discovery location. With Gemini CLI installed, you can install this skill into the current workspace with:

```sh
gemini skills install https://github.com/YellankiKaushik/Hibernator-Skill --path .agents/skills/hibernator --scope workspace
gemini skills list
```

Or use the skill already present in a trusted clone of this repository. In an interactive session, check `/skills list`, reload with `/skills reload` if needed, then ask Gemini to inspect a project. Gemini CLI was not installed in the validation environment, so invocation has not been tested here. See the [official Gemini CLI skill guide](https://geminicli.com/docs/cli/skills/).

### Google Antigravity

The Antigravity App, IDE, and CLI document `.agents/skills/` for workspace skills. Open the cloned Hibernator repository as the workspace, inspect the discovered skill, and invoke `/hibernator` in the app/CLI or request a Hibernator scan. The documented global skill location is `~/.gemini/config/skills/hibernator/`. The Antigravity host was not successfully launched in this validation environment; invocation is unverified. See [Google's Antigravity Agent Skills guide](https://antigravity.google/docs/skills).

### Other terminal-capable agents

An agent that can run local commands may follow the same skill instructions or call `python -m hibernator` itself. It must have the Python package installed in the interpreter available to that terminal. An agent without local filesystem access can only explain the documentation; it cannot inspect files that are not provided to its runtime. Agents must not approve or perform real deletion.

See [agent setup and verification](docs/AGENTS.md) for the installation matrix and verification history.

## Security and privacy

- Scan, plan, report, and restore preview do not contact network services, invoke package managers, or write into the selected project. Package installation may access a package index to obtain build dependencies.
- Scan and restore traversal refuse or skip symlinks/reparse points, nested Git repositories, and different-device crossings. These read-only path walks are not atomic snapshots and are not race-resistant deletion controls.
- Plans include the absolute root, Git snapshots, candidate identities, tree digests, exclusions, rule version, and plan digest. The digest detects stale or edited state; it does not authenticate a user.
- Saved reports redact the project root, but can still disclose relative file names and project structure. `--show-paths`, terminal output, and plan files can expose absolute local paths. Review before sharing.
- The scanner does not read secret file contents for classification. Secret-like files are preserved. Do not post reports or plans publicly without reviewing them.
- No telemetry or remote account is used by scan or restore preview.

Production cleanup is disabled because no independently reviewed, race-resistant deletion design is available for the supported host filesystems. The current POSIX descriptor-relative prototype is unwired and limited to test-owned fixtures. Root relocation, same-device bind mounts, Windows handle/reparse behavior, durable replay barriers, and a human-enforceable approval boundary remain open. Read [the safety model](docs/SAFETY.md), [cleanup design status](docs/PRODUCTION_CLEANUP_DESIGN.md), and [security review gate](docs/SECURITY_REVIEW_GATE.md).

## Restoration and recovery

`restore --dry-run` reads supported manifests and lockfiles and prints suggested commands; it does not create a virtual environment or install anything. For Node workspaces it associates manifests with the nearest recognized lockfile and warns about ambiguous managers. For Python it suggests a virtual environment and may suggest installing from `requirements.txt` or `pyproject.toml`.

This preview has not deleted project files, and its restore guide is not a backup system. It cannot reconstruct local-only files, ignored datasets, secrets, uploads, databases, private packages, or services. Read [restoration guidance](docs/RESTORE_GUIDANCE.md) before using suggestions.

## Troubleshooting

| Problem | What to check |
|---|---|
| `python` or `hibernator` is not found | Confirm Python 3.10+ and Git are on `PATH`. Use the virtual environment's direct Python/CLI path or `python -m hibernator`. |
| `doctor` reports Git unavailable | Install Git for your OS and reopen the terminal so `git` is on `PATH`. |
| Project root is unsupported | Pass the root of one existing Git repository, not a parent folder, filesystem root, or nested subdirectory. |
| A candidate is `REVIEW` or `BLOCKED` | Read its reason. Missing lockfiles, tracked descendants, unknown files, links, nested Git, local data, unreadable entries, and device crossings are conservative blockers. Do not remove them manually based on the label. |
| Node dependencies have no restore command | Keep the lockfile with the package manifest. Without a recognized lockfile, Hibernator does not guess which package manager to use. |
| `apply` refuses after a plan | The plan may be stale; scan and plan again. Even a fresh, exactly approved plan is unsupported in this preview and will not delete. |
| Skill is not available in an agent | Verify the host's skill directory and workspace trust, list/reload skills, then start a new session. Installing the Python package alone does not install a skill. |
| Gemini CLI or Antigravity cannot run Hibernator | Install the host and the Python package in the environment its terminal uses. These invocations are documented but not verified in this project environment. |
| Wheel build cannot fetch setuptools | Provide a package index or a compatible `setuptools>=77` build dependency/cache, then retry. The application itself has no third-party runtime dependencies. |
| A filesystem test is skipped | Read the skip reason. Link/junction privileges and platform-only fsync behavior vary; skipped adversarial tests are unverified, not passed. |

## Development and contributions

```sh
python -m unittest discover -v
python -m compileall -q src tests
python -m hibernator --help
python -m pip wheel --no-deps --wheel-dir dist .
```

Tests construct and remove only their own temporary Git fixtures. Do not run destructive tests on a real project. The architecture is split across `discovery` (Git-aware inventory/classification), `rules` (positive-evidence rules), `plans` (canonical plan/staleness validation), `restore` (read-only suggestions), `reports`, and `cleaner` (production refusal plus isolated test fixture pathway). `secure_remove` is a fixture-only POSIX prototype and must remain disconnected from the public apply path.

See [testing](docs/TESTING.md), [architecture](docs/ARCHITECTURE.md), [CLI reference](docs/CLI.md), [classification details](docs/DEPENDENCY_CLASSIFICATION.md), and [contribution guidance](docs/CONTRIBUTING.md). Report vulnerabilities privately according to [SECURITY.md](SECURITY.md); do not include secrets, private project contents, or full local paths in a public issue.

## License and roadmap

Hibernator is distributed under the [MIT License](LICENSE), copyright 2026 YellankiKaushik. Third-party tools and package-manager ecosystems remain subject to their own licenses and terms; no third-party license or permission is implied by this project.

The supported scope is the preview workflow: scan, classify, plan, report, and restore suggestions. Future production cleanup would require a defined supported-filesystem matrix, platform-specific no-follow implementation, race and mount-boundary controls, durable journaling and replay protection, direct human approval, adversarial tests with no relevant skips, and independent review of the exact source revision. No release, tag, or PyPI publication is part of this consolidation.

## Uninstall

Uninstall the Python package from the same environment where it was installed:

```sh
python -m pip uninstall hibernator-skill
```

For a skill installed into a different project or user directory, remove only that Hibernator skill directory after checking its exact path. The GitHub CLI skill command currently has no uninstall command; the project copy in this repository is source-controlled and should normally remain in place. Removing Hibernator does not change scanned projects. Local reports and plans live separately in the Hibernator application-state directory and may be removed by their owner.
