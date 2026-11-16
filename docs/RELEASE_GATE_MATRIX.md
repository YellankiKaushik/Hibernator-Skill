# Release gate matrix

The latest full evidence is [GitHub Actions run #11](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43831231379) for cleanup prototype commit `de8b558efe465394ea39b4bdd0022152f90b4dd0` (2026-11-16). All **18/18 jobs passed**: 15 Windows/Ubuntu/macOS × Python 3.10–3.14 unit/package jobs and 3 OS-specific adversarial fixture jobs. Each unit job ran 78 tests; Ubuntu and macOS each skipped 4 unavailable Windows junction cases, while each Windows unit job skipped those same 4 junction cases plus the POSIX-only directory-fsync test. Each adversarial job ran 47 tests and skipped the 3 unavailable Windows junction cases. Skips are unverified cases, never passes.

| ID | Gate | Current evidence | Status | Requirement to close |
|---|---|---|---|---|
| G-01 | Source and feature history | Public `main` remains published; current work is in review branches based on the existing source. No history was rewritten. | PASSED | Review and merge focused branches. |
| G-02 | Cross-platform unit suite | Run #11 passed all 15 OS/Python jobs. Each ran 78 tests: 4 junction skips on Ubuntu/macOS; Windows had those 4 plus the POSIX-only directory-fsync test. | PARTIAL | Run junction/reparse cases on a Windows host where junction creation is allowed. |
| G-03 | CLI and installed package | All 15 runtime jobs passed `python -m hibernator --help`, wheel build, fresh environment install, installed `hibernator --help`, and packaged skill-file verification. | PASSED IN CI | Repeat on package metadata or entry-point changes. |
| G-04 | Python 3.10–3.14 | Every supported Python version passed on Windows, Ubuntu, and macOS in run #11. | PASSED IN CI | Keep the matrix enabled. |
| G-05 | Linux and macOS behavior | All ten Unix OS/Python jobs passed; the synthetic POSIX descriptor-relative cleanup cases ran. | PASSED FOR FIXTURES | Real supported filesystem coverage and independent review are still missing. |
| G-06 | Wheel contents | The wheel built and installed in each of the 15 runtime jobs; the installed skill file was found. | PASSED IN CI | Repeat after packaging changes. |
| G-07 | Console command | Installed `hibernator --help` passed on all 15 runtime jobs. | PASSED IN CI | Repeat after entry-point changes. |
| G-08 | Production deletion | `apply_production()` still refuses; `secure_remove.py` is an unwired POSIX test-fixture prototype. Root relocation and same-device bind-mount identification remain unresolved. | BLOCKED | Resolve the design, implement supported platform backends, and obtain independent review of the exact revision. |
| G-09 | Direct human approval | Exact-digest interactive approval behavior is tested, but terminal input does not establish that a human rather than an agent supplied it. | BLOCKED | Define and independently review an enforceable human-approval boundary before production apply. |
| G-10 | Filesystem escape barriers | POSIX synthetic tests passed for symlinks, hard links, stale plans, mocked device crossing, replay, and outside sentinels. Windows junction cases were skipped; real and same-device bind mounts were not exercised. | PARTIAL | Test actual mount/junction/reparse cases on every supported OS/filesystem without relevant skips. |
| G-11 | Journal durability and interruption | POSIX test verified file and parent-directory `fsync`; existing synthetic interruption/report tests passed. Windows directory-fsync test is skipped and production cleanup is unsupported there. | PARTIAL | Review crash behavior and provide supported-platform durability evidence. |
| G-12 | Agent integrations | Agent Skill and Python CLI installation are documented separately. One Codex session invoked the scan workflow on a disposable Git project. Gemini CLI is not installed; Antigravity invocation was unavailable because desktop control did not initialize. | PARTIAL | Test actual invocation in Gemini CLI and Antigravity before claiming those integrations. |
| G-13 | GitHub Actions | [Run #11](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43831231379): 18/18 jobs passed. | PASSED IN CI | Keep all matrix jobs enabled; do not treat skipped junction or Windows journal cases as security evidence. |
| G-14 | License | No license has been selected. | OWNER DECISION | Owner selects a license and approves attribution obligations. |
| G-15 | Preview release | No tag, release, or package has been published. | OWNER DECISION | Owner reviews exact release diff, chooses a license, and explicitly approves publication. |
| G-16 | Reclaimed storage | No production cleanup was run. | NO EVIDENCE | Measure only after production cleanup independently passes its gates and is approved. |
| G-17 | Restore workflow | Read-only restore preview and monorepo guidance have tests for nested manifests, lockfiles, and working-directory selection. | PASSED FOR PREVIEW | Continue to keep restore preview non-mutating. |
| G-18 | Independent filesystem-security review | No independent review of this exact cleanup prototype revision has been completed. | NOT PERFORMED | Obtain written review evidence for the exact proposed production implementation and supported filesystems. |

## Release recommendation

**PREVIEW: NO-GO for a tagged/public release today.** The preview source, installed CLI, documentation, and full Actions matrix are technically ready, but license selection and explicit owner release approval remain open. Current work is on feature branches and has not been merged into `main`.

**PRODUCTION: NO-GO.** Production deletion is disabled. The POSIX prototype is fixture-only and unwired; root relocation, same-device bind mounts, Windows deletion, durable replay control, and a human-enforceable approval boundary remain unresolved. There is no independent filesystem-security signoff.
