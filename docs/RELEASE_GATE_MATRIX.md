# Release gate matrix

Current CI evidence is from [GitHub Actions run #2](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43814217765) at published commit `3e0dd39be4a68b6ed5f075cbafd7cf68df16ed01` (2026-11-16). All 18 jobs passed. Full test jobs ran 52 tests; three Windows-junction tests were skipped per job because the current runner policy did not permit junction creation. A skip is unverified, not a pass. The earlier local validation snapshot remains in [the final validation report](FINAL_VALIDATION_REPORT.md); its pre-publication status is historical.

| ID | Gate | Current evidence | Status | Requirement to close |
|---|---|---|---|---|
| G-01 | Source exists and is preserved | Published `main` contains the CLI, tests, docs, skill, package metadata, and CI. | PASSED | Keep the reviewed source history. |
| G-02 | Windows unit suite | Python 3.10–3.14 jobs passed; each ran 52 tests with 3 junction skips. Local Python 3.14 run had 6 link/junction skips under host policy. | PARTIAL | Run junction cases on an authorized Windows host that permits them. |
| G-03 | CLI read-only smoke | Local standalone CLI smoke passed on a disposable Git project; CI help checks passed in all 15 runtime jobs. | PASSED WITH SCOPE | Keep real-project scans read-only and separately verify any new workflow. |
| G-04 | Python 3.10 runtime | Python 3.10 jobs passed on Windows, Ubuntu, and macOS. | PASSED IN CI | Keep Python 3.10 in the matrix. |
| G-05 | Linux/macOS runtime | Python 3.10–3.14 matrix jobs passed on Ubuntu and macOS. | PASSED IN CI | Platform-specific deletion safety remains unverified. |
| G-06 | Wheel build and contents | Matrix built the wheel, installed it into fresh virtual environments, and verified the packaged skill file. | PASSED IN CI | Repeat for changes to package data or build configuration. |
| G-07 | Installed console script | Fresh-environment `hibernator --help` passed on Windows, Ubuntu, and macOS matrix jobs. | PASSED IN CI | Verify future entry-point changes in the same way. |
| G-08 | Production deletion safety | `apply_production()` refuses deletion on every platform; no independent review exists. | BLOCKED | Close [the security review gate](SECURITY_REVIEW_GATE.md) for each supported OS/filesystem before any production connection. |
| G-09 | Direct human approval | Exact-digest approval/refusal behavior is covered; no production apply state transition exists. | PARTIAL | Obtain independent review of the approval boundary before enabling production deletion. |
| G-10 | Symlink/junction/hardlink anti-escape | CI passed; link/symlink cases ran where supported. Three Windows-junction tests skipped in full test jobs; local Windows host also skipped symlink/hardlink cases under policy. | PARTIAL | Run external-sentinel junction/reparse cases on an authorized Windows host; keep unsupported cases disabled. |
| G-11 | Interruption and journaling | Synthetic interruption and removal-error reporting tests passed. | PARTIAL | Verify crash durability and recovery behavior on supported filesystems and obtain review. |
| G-12 | Agent Skills portability | Skill metadata is packaged. Current Codex session surfaced it, but separate-host invocation has not been proven; Gemini CLI and Antigravity are untested. | PARTIAL | Exercise actual host discovery/invocation; label unavailable hosts unverified. |
| G-13 | GitHub Actions | [Run #2](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43814217765): 18/18 jobs passed on Windows, Ubuntu, and macOS, Python 3.10–3.14. | PASSED IN CI | Keep the matrix enabled; do not treat the junction skips as security evidence. |
| G-14 | License | No license has been selected. | OWNER DECISION | Owner selects and approves a license; MIT remains only a proposal. |
| G-15 | Repository publication | Public repository `main` is published at `3e0dd39be4a68b6ed5f075cbafd7cf68df16ed01`. No tag, release, or package was published. | PUBLISHED | Owner approval is still required for any release or package publication. |
| G-16 | Real reclaimed storage | No production cleanup was performed. | NO EVIDENCE | Measure only after secure production cleanup is separately approved. |
| G-17 | Restore workflow | Restore preview is read-only and covered by tests; monorepo guidance is tracked separately. | PARTIAL BY DESIGN | Verify monorepo manifest selection and guidance before claiming complete restoration coverage. |
| G-18 | Independent source/security review | Post-publication code review findings are being addressed; no independent filesystem-security signoff exists. | NOT PERFORMED | Independent reviewer assesses the exact deletion design and source revision. |

## Release scope decision

**NO-GO for production deletion.** Hibernator remains a preview-only implementation with production deletion disabled. The public source repository and CI-validated package workflow do not constitute security approval for deleting project files.

- A preview release remains an owner decision and requires a selected license and updated installation/host evidence.
- A production-cleanup release requires platform-specific adversarial filesystem evidence, an independent security review of the exact source revision, and explicit owner approval.
- No release, tag, package, or production-deletion enablement has been performed.
