# Release gate matrix

The latest complete feature-branch evidence is [Actions run #12](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43832996714) on C-08 commit `1c865c5766eaaea59a2a061f2b94428fb1d8cd99` (2026-11-16). All **18/18 jobs passed**: 15 Windows/Ubuntu/macOS × Python 3.10–3.14 unit/package jobs and 3 OS adversarial fixture jobs. The C-07 source run [#11](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43831231379) ran 78 tests in each unit job and 47 tests in each adversarial job. Each unit job skipped four Windows-junction tests; Windows also skipped one POSIX-only directory-fsync test. Each adversarial job skipped three Windows-junction cases. Skips are unverified, not passes. A final `main` Actions run is required after consolidation and will be recorded here.

| ID | Gate | Current evidence | Status | Requirement to close |
|---|---|---|---|---|
| G-01 | Source and feature history | Remote C-01 through C-08 branch heads were verified as ancestors of C-08. C-08 is merged into the local `main` integration checkout with a normal merge; remote `main` still needs the final push. | INTEGRATION IN PROGRESS | Push validated `main` and verify final Actions. |
| G-02 | Cross-platform unit suite | C-08 run #12 passed all 15 OS/Python jobs. C-07 run #11 ran 78 tests each: four Windows-junction skips on every OS; Windows additionally skipped POSIX directory fsync. | PARTIAL | Run junction/reparse cases on a Windows host where junction creation is permitted. |
| G-03 | CLI and installed package | All 15 runtime jobs passed module help, wheel build, fresh environment install, installed `hibernator --help`, and packaged skill verification. | PASSED IN FEATURE CI | Repeat on final `main` and package metadata changes. |
| G-04 | Python 3.10–3.14 | Every version passed on Windows, Ubuntu, and macOS in C-08 run #12. | PASSED IN FEATURE CI | Confirm final `main` matrix. |
| G-05 | Linux and macOS behavior | All ten Unix runtime jobs passed, including synthetic POSIX descriptor-relative prototype tests. | PASSED FOR FIXTURES | Real supported filesystem evidence and independent review remain missing. |
| G-06 | Wheel contents | Wheel built and installed in every runtime job; the packaged skill file was verified. | PASSED IN FEATURE CI | Confirm final `main` package checks. |
| G-07 | Console command | Installed `hibernator --help` passed in all 15 runtime jobs. | PASSED IN FEATURE CI | Confirm final `main` package checks. |
| G-08 | Production deletion | `apply_production()` refuses; `secure_remove.py` is an unwired, POSIX test-fixture prototype. Root relocation and same-device bind-mount detection remain unresolved; Windows deletion is unsupported. | BLOCKED | Resolve platform design, implement supported backends, and obtain independent review of exact code. |
| G-09 | Direct human approval | Exact-digest interactive approval/refusal behavior is tested, but terminal input does not prove a human supplied it. | BLOCKED | Define and independently review an enforceable direct human approval boundary. |
| G-10 | Filesystem escape barriers | POSIX synthetic tests passed for symlinks, hard links, stale plans, mocked cross-device entries, replay, and external sentinels. Windows junctions were skipped; actual and same-device bind mounts were not exercised. | PARTIAL | Test real mount/junction/reparse scenarios on every supported OS/filesystem without relevant skips. |
| G-11 | Journal durability and interruption | POSIX tests verified file and parent-directory `fsync`; synthetic interruption/report tests passed. Windows skips the directory-fsync test; Windows deletion has no backend. | PARTIAL | Review and validate crash behavior on each supported filesystem. |
| G-12 | Agent integrations | Codex session scan workflow was invoked against a disposable Git project. Gemini CLI and Antigravity invocation remain unverified. Skill and Python CLI installation are documented separately. | PARTIAL | Verify those host invocations before claiming them tested. |
| G-13 | GitHub Actions | [C-08 run #12](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43832996714): 18/18 jobs passed. Final `main` result pending consolidation push. | PASSED IN FEATURE CI | Keep the full matrix; never treat skipped security cases as passes. |
| G-14 | License | Owner selected MIT; root `LICENSE` and PEP 639 package metadata are added in the local integration checkout. | IMPLEMENTED LOCALLY | Verify wheel metadata and final `main` contents. |
| G-15 | Preview UAT/release | The repository is being prepared for hands-on preview testing. No tag, GitHub Release, or PyPI package exists. | UAT READY AFTER PUSH | Run owner UAT before any separate release decision. |
| G-16 | Reclaimed storage | No production cleanup was run and no reclaimed-space claim is made. | NO EVIDENCE | Measure only after production cleanup is independently approved and enabled. |
| G-17 | Restore workflow | Read-only restore preview and monorepo guidance cover nested projects, lockfiles, and working-directory selection. | PASSED FOR PREVIEW | Keep restore preview non-mutating. |
| G-18 | Independent filesystem-security review | No independent review of the fixture-only prototype has been completed. | NOT PERFORMED | Obtain written review evidence for the exact proposed production implementation and supported filesystems. |

## Recommendation

**PREVIEW: READY FOR HANDS-ON USER ACCEPTANCE TESTING after final `main` CI passes.** No formal release, tag, or package publication is authorized by this readiness statement; owner UAT comes first.

**PRODUCTION: NO-GO.** Production deletion is disabled. Root relocation, same-device bind mounts, Windows cleanup, durable replay control, direct human approval, complete supported-filesystem adversarial tests, and independent security review remain open.
