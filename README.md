# Hibernator

**See what takes up space in an inactive coding project, then review what could be recreated.**

Hibernator is a local, Git-aware Python tool. It scans one repository, explains what it would preserve, and prepares a plan you can inspect before making any decisions.

> **PREVIEW — PRODUCTION DELETION DISABLED**
>
> This build scans, classifies, writes plans and reports, and previews restoration. Project files stay in place.

[![Watch the Hibernator preview demo showing a synthetic Git project](docs/media/hibernator-preview-poster.jpg)](https://github.com/YellankiKaushik/Hibernator-Skill/raw/refs/heads/main/docs/media/hibernator-preview-demo.mp4)

[Watch or download the 22-second MP4](https://github.com/YellankiKaushik/Hibernator-Skill/raw/refs/heads/main/docs/media/hibernator-preview-demo.mp4) · [Demo and audio credits](docs/media/README.md)

## Contents

[Install](#installation) · [Quick start](#quick-start) · [Understand the results](#scan-classifications) · [Use an AI agent](#use-hibernator-with-your-ai-coding-agent) · [Safety](#privacy-and-security) · [Get help](#troubleshooting-and-uninstall)

## Why Hibernator?

Old projects accumulate Node dependencies, Python virtual environments, framework caches, bytecode, and build artifacts. Some of these can be recreated from the source and lockfiles. A generated-looking folder can also hold local changes, private data, or files that Git tracks. Folder names and ignore rules alone tell you little about what you can safely recreate.

## How it works

```text
Scan → Classify → Validate → Human approval → Clean → Report
```

The preview supports scan, classification, plan validation, saved reports, and restoration guidance. It can detect when a saved plan is stale. The experimental approval path always refuses real cleanup, including after an exact approval phrase. **Production Clean is disabled.** [Safety model](docs/SAFETY.md)

## Scan classifications

| Decision | What it means | Synthetic example |
| --- | --- | --- |
| **KEEP** | Hibernator will preserve this content. | Git-tracked source in `src/` or a secret-like `.env.local` file. |
| **REGENERABLE** | Project evidence supports proposing the artifact in a plan. | `node_modules/` with matching Node project metadata and a lockfile, after content checks. |
| **REVIEW** | The evidence is incomplete or the content needs human judgment. | An unrecognized `local-notes.txt` file. |
| **BLOCKED** | A protection or inspection check excluded the artifact. | A dependency folder containing a secret-like file or a link outside the project. |

**REGENERABLE** is a plan candidate label. The preview leaves every candidate in place.

## What the preview supports

- **Git-aware scanning.** Inspect one explicit repository root. The tool considers tracked files, local changes, project markers, and narrowly scoped rules for Node.js, Python, and selected framework caches.
- **Reviewable plans.** See candidate paths, logical byte estimates, reasons, and recovery hints. Exclude candidates by exact path. The plan binds to the inspected root, Git state, rules, and candidate contents, so relevant changes can invalidate it.
- **Local reports.** Save a scan report, view it by file or ID, or use JSON. Report files redact the absolute project root by default.
- **Restoration previews.** Get dependency reinstall suggestions based on manifests and lockfiles, including separate working-directory guidance for supported nested projects and monorepos.
- **CLI and Agent Skill.** Use Hibernator directly on Windows, Linux, or macOS, or let a compatible local coding agent run the same preview. The CLI needs no AI or API key.

Cleanup, automatic dependency installation, and recovery of local-only data are outside the preview. The [CLI reference](docs/CLI.md), [rule explanations](docs/DEPENDENCY_CLASSIFICATION.md), and [usage examples](docs/USAGE_EXAMPLES.md) cover the details.

## Requirements

- **Python 3.10 or later** and **Git on your PATH**. CI covers Python 3.10–3.14 on Windows, Ubuntu, and macOS.
- Source installation uses `setuptools>=77` as its build backend. The installer may download it if it is unavailable locally. The installed CLI has no third-party runtime dependencies.
- A local terminal with read access to the chosen Git repository and a writable folder outside it for plans and reports.

## Installation

Clone Hibernator into a tools folder, separate from any project you want to inspect. Create an isolated Python environment so the installation stays with this checkout.

### Windows PowerShell

```powershell
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
Set-Location Hibernator-Skill
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\hibernator.exe doctor
```

Use `python -m venv .venv` if your Windows installation provides `python` but lacks the `py` launcher. If the Hibernator executable is unavailable, run `.\.venv\Scripts\python.exe -m hibernator doctor`. This also works without enabling PowerShell activation scripts.

### Linux and macOS

```sh
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
cd Hibernator-Skill
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/hibernator doctor
```

Use `.venv/bin/python -m hibernator doctor` if the console command is unavailable. On Linux, install your distribution’s Python venv package if Python reports that it cannot create a virtual environment.

In an activated environment, `hibernator` and `python -m hibernator` run the same CLI. You can also use the full installed command or module path above from the Hibernator checkout.

## Quick start

Choose an inactive Git repository you own. Replace the example path with that repository's root and keep the quotes. On Windows you can use a path such as `C:/work/inactive-demo`. Run these commands with your installed Hibernator command from [Installation](#installation).

```text
hibernator doctor
hibernator scan --project "/work/inactive-demo"
hibernator plan --project "/work/inactive-demo"
hibernator restore --project "/work/inactive-demo" --dry-run
```

1. **Doctor** checks the runtime, Git availability, and preview status.
2. **Scan** explains each classification and displays its logical size.
3. **Plan** lists eligible candidates and saves a reviewable file outside the project. It can contain zero candidates. The command leaves the project in place.
4. **Restore preview** shows proposed steps without running installers.

Try all four steps on a [disposable Git project](docs/USER_TESTING.md) before scanning a project you care about.

## Inspect an inactive Git project

From a directory inside the chosen repository, use `git --no-optional-locks rev-parse --show-toplevel` to identify its root. Record `git --no-optional-locks status --porcelain=v1 --untracked-files=all` before starting. Scan the root, read the reasons, and review the plan. Use `--output` with an absolute file path in a private folder outside the repository if you want to control where the plan is written.

In the demo’s synthetic Node.js fixture, Hibernator classified the dependency folder as `REGENERABLE`, the source and fake secret marker as `KEEP`, and a local note as `REVIEW`. The plan listed one candidate with **24 logical bytes**. This was the sum of the candidate's file lengths. The preview reclaimed no disk space.

Run the restoration preview, then repeat the Git status command and compare it with the baseline. Git status reports changes Git can see. For a stronger check on selected files, compare their hashes before and after, including ignored files you care about. The [hands-on guide](docs/USER_TESTING.md#9-scan-a-real-repository-from-windows-powershell) walks Windows users through saving private results.

To save an inventory separately from a plan, add `--save-report` to the scan command. Reopen the saved report with `hibernator report --file PATH`. The [CLI reference](docs/CLI.md) explains JSON output and report IDs.

## Use Hibernator with Your AI Coding Agent

Open an agent with local terminal access and grant it permission to inspect only the folder you choose. The README and Agent Skill provide instructions. Filesystem and command access depend on the agent host and its permissions.

- **Codex:** The checkout carries a discoverable project skill. A Codex session has run a synthetic scan with the Hibernator workflow.
- **Claude Code, Gemini CLI, Google Antigravity, and Cursor:** Their documented skill discovery or manual setup is covered in the [Agent Skill guide](docs/AGENTS.md). Hibernator invocation in these hosts has not been verified.
- **Other terminal-capable agents:** Install the CLI where the agent's terminal runs, then paste the prompt below. The prompt works without native skill discovery if the agent can run the CLI.

### Copy-paste prompt

```text
Help me preview one inactive Git project with Hibernator.

Ask for or confirm the exact local Git repository root and an existing private
output folder outside that repository. If Hibernator is missing, help me install
the CLI from its trusted source in a separate environment. Confirm Git and local
terminal access. Run Hibernator's doctor check before inspecting the project.

Record Git status before the preview. Run a read-only scan, then explain KEEP,
REGENERABLE, REVIEW, and BLOCKED in plain English with the reasons and any
ambiguous or incomplete results. Keep source code, sensitive files, and local
changes intact. Do not open or reveal secret values.

Create a reviewable plan outside the repository. Summarize its candidates,
protected and review items, and estimated logical bytes as file sizes. Show
restoration guidance using dry-run only. Compare Git status afterward and
report what preservation checks established. Keep raw output, paths, and notes
private, and report errors, skipped checks, and limitations honestly.

Never run production apply, approve deletion, run an installer in the project,
or use shell, Git, or other commands as a substitute for deletion.
```

See [Agent Skill installation, discovery, and troubleshooting](docs/AGENTS.md). The CLI and skill are installed separately.

## Restoration guidance

`restore --dry-run` reads supported manifests and lockfiles. For example, an npm lockfile can produce a suggested `npm ci` step. Nested projects can receive their own working-directory hints. Review the suggestion and any warnings before running a package manager yourself.

The preview leaves installers unexecuted. Reinstalling dependencies cannot recover local-only files, secrets, databases, custom edits inside generated directories, or data that exists nowhere else. See the [restoration guide](docs/RESTORE_GUIDANCE.md).

## Privacy and security

- Scan, plan, and restore preview work offline and leave the target repository untouched. Plans and saved reports are written outside it.
- Git-tracked content and local changes are protected by conservative rules. Unknown content is preserved or flagged for review. Secret-like names are protected without reading their values for classification.
- Traversal rejects or skips filesystem boundaries such as symlinks, reparse points, nested Git repositories, and different-device entries where applicable. Actual filesystem behavior varies by platform.
- A plan digest detects changes to the recorded plan. It provides no proof of human approval. Plans may contain absolute paths, and even redacted reports can reveal filenames and project structure. Keep raw results private.

Production deletion requires platform-specific filesystem evidence, an independent review of the exact implementation, and explicit owner approval. The [safety model](docs/SAFETY.md), [independent review gate](docs/SECURITY_REVIEW_GATE.md), and [security policy](SECURITY.md) govern this boundary.

## Testing and validation

The [verified baseline CI run](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/45579668204) passed 18 of 18 jobs for commit `76fda646ec9b9d42f2fc2b87ad84d1502a413fd2`. It covers Python 3.10–3.14 on Windows, Ubuntu, and macOS, including synthetic fixtures, wheel build and installation, installed console startup, and Agent Skill packaging. Windows junction fixture checks and other platform-specific cases can skip. Those cases remain unverified. CI does not certify production deletion.

See [testing instructions](docs/TESTING.md) and the [release gate matrix](docs/RELEASE_GATE_MATRIX.md) for coverage and remaining checks.

## Architecture

`git_state` and `discovery` inspect the repository. `rules` assigns classifications, `plans` creates and validates plans, and `reports` and `restore` produce review output. `cli` exposes these workflows. The Agent Skill tells compatible agents how to operate the CLI. [Architecture notes](docs/ARCHITECTURE.md)

## Roadmap and limitations

The next step is owner-led, read-only acceptance testing on an inactive repository, followed by usability improvements based on that feedback. Production deletion needs further filesystem engineering and independent review. Release and cleanup decisions remain separate from this preview.

## Contribute or report a problem

Open a [GitHub issue](https://github.com/YellankiKaushik/Hibernator-Skill/issues) with your OS, Python and Git versions, observed behavior, and a minimal synthetic reproduction. Keep secrets and raw project data private. Follow the [contribution guide](docs/CONTRIBUTING.md) and use the [security reporting process](SECURITY.md) for suspected vulnerabilities.

Hibernator is distributed under the [MIT License](LICENSE).

## Troubleshooting and uninstall

| Problem | What to try |
| --- | --- |
| Python or Git is unavailable | Check the installed versions with `python --version` or `py -3 --version` and `git --version`. Restart the terminal after installation. |
| Python cannot create the environment, or pip cannot build the package | Check venv support and whether pip can obtain the declared build dependency. Retry from the Hibernator checkout. |
| The Hibernator command is unavailable | Use the installation environment's Python with `-m hibernator`. |
| The agent cannot find the Skill | Open a trusted checkout, check the host-specific discovery path and permissions, then start a new session. Use the copy-paste prompt if needed. |
| A scan is refused or incomplete | Confirm you selected the Git root and have read access. Review the exact reported reason before trying again. [FAQ](docs/FAQ.md) |

To uninstall, run `python -m pip uninstall hibernator-skill` with the Python from the same environment you installed into. Remove any separately installed Agent Skill through its host. Keep or remove saved plans and reports according to your needs.
