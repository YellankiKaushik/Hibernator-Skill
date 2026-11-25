# Release gate matrix

> This matrix records the earlier preview. The current owner-only boundary is permanent. See the [retirement verification record](RETIREMENT_VALIDATION.md) for this revision and its publication status.

The consolidated implementation commit `b43430893d890183498a85c49c85d47bc642a998` passed [GitHub Actions run #13](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43848601766) (2026-11-16): **18/18 jobs passed**—15 Windows/Ubuntu/macOS × Python 3.10–3.14 unit/package jobs plus 3 OS adversarial fixture jobs. Every unit job ran 78 tests; each adversarial job ran 47. Linux/macOS unit jobs each skipped four Windows-junction cases; Windows unit jobs each skipped four junction cases plus the POSIX-only directory-fsync case. All three adversarial jobs skipped three Windows-junction cases. These remain unverified, not passes. Wheel builds, fresh environment installs, installed CLI checks, and packaged Agent Skill verification completed in the matrix. The subsequent documentation/branch-state commit `9797f70e90569b5fc6ac28ae9b6f4559318416a5` passed [run #14](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43849418766), also **18/18 jobs passed**.

| ID | Gate | Current evidence | Status | Requirement to close |
|---|---|---|---|---|
| G-01 | Source and feature history | All eight remote C-01 through C-08 branch heads were verified as ancestors of `main` before deletion. GitHub now lists only `main`; no unrelated branches were present. | COMPLETE | All eight authorized obsolete branches were safely removed after green CI; remote inventory contains only `main`. |
| G-02 | Cross-platform unit suite | Final `main` run #13 passed all 15 OS/Python jobs, each running 78 tests. Linux/macOS jobs skipped four Windows-junction cases each; Windows jobs skipped four junction cases plus POSIX directory fsync. | PARTIAL | Windows junction/reparse fixture cases remain skipped on the hosted runner; verify on a host where junction creation is permitted. |
| G-03 | CLI and installed package | All 15 final `main` runtime jobs passed module help, wheel build, fresh environment install, installed `hibernator --help`, and packaged skill verification. | PASSED ON MAIN | |
| G-04 | Python 3.10–3.14 | Every version passed on Windows, Ubuntu, and macOS in final `main` run #13. | PASSED ON MAIN | |
| G-05 | Linux and macOS behavior | All ten Linux/macOS runtime jobs and both Unix adversarial-fixture jobs passed, including synthetic POSIX descriptor-relative prototype tests. | PASSED FOR FIXTURES | Real supported filesystem evidence and independent review remain missing. |
| G-06 | Wheel contents | Wheel built and installed in every runtime job; the packaged skill file and license metadata were verified. | PASSED ON MAIN | |
| G-07 | Console command | Installed `hibernator --help` passed in all 15 runtime jobs. | PASSED ON MAIN | |
| G-08 | Production deletion | `apply_production()` refuses; `secure_remove.py` is an unwired, POSIX test-fixture prototype. Root relocation and same-device bind-mount detection remain unresolved; Windows deletion is unsupported. | BLOCKED | Resolve platform design, implement supported backends, and obtain independent review of exact code. |
| G-09 | Direct human approval | Exact-digest interactive approval/refusal behavior is tested, but terminal input does not prove a human supplied it. | BLOCKED | Define and independently review an enforceable direct human approval boundary. |
| G-10 | Filesystem escape barriers | POSIX synthetic tests passed for symlinks, hard links, stale plans, mocked cross-device entries, replay, and external sentinels. Windows junctions were skipped; actual and same-device bind mounts were not exercised. | PARTIAL | Test real mount/junction/reparse scenarios on every supported OS/filesystem without relevant skips. |
| G-11 | Journal durability and interruption | POSIX tests verified file and parent-directory `fsync`; synthetic interruption/report tests passed. Windows skips the directory-fsync test; Windows deletion has no backend. | PARTIAL | Review and validate crash behavior on each supported filesystem. |
| G-12 | Agent integrations | Codex session scan workflow was invoked against a disposable Git project. Gemini CLI and Antigravity invocation remain unverified. Skill and Python CLI installation are documented separately. | PARTIAL | Verify those host invocations before claiming them tested. |
| G-13 | GitHub Actions | [Main run #14](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43849418766): 18/18 jobs passed on commit `9797f70e90569b5fc6ac28ae9b6f4559318416a5`; the complete source/package matrix is detailed above from run #13. | PASSED ON MAIN | Keep the full matrix; never treat skipped security cases as passes. |
| G-14 | License | Owner-approved root `LICENSE` and PEP 639 package metadata are present on `main`; wheel metadata and the packaged license were verified. | VERIFIED ON MAIN | |
| G-15 | Preview UAT/release | Preview is ready for owner hands-on testing. No tag, GitHub Release, or PyPI package exists. | UAT READY | Run owner UAT before any separate release decision. |
| G-16 | Reclaimed storage | No production cleanup was run and no reclaimed-space claim is made. | NO EVIDENCE | Measure only after production cleanup is independently approved and enabled. |
| G-17 | Restore workflow | Read-only restore preview and monorepo guidance cover nested projects, lockfiles, and working-directory selection. | PASSED FOR PREVIEW | Keep restore preview non-mutating. |
| G-18 | Independent filesystem-security review | No independent review of the fixture-only prototype has been completed. | NOT PERFORMED | Obtain written review evidence for the exact proposed production implementation and supported filesystems. |

## Recommendation

**PREVIEW: GO for hands-on user acceptance testing.** Final `main` CI run #13 passed 18/18 jobs. Junction cases remain unverified as listed above. No formal release, tag, or package publication is authorized by this readiness statement; owner UAT comes first.

**PRODUCTION: NO-GO.** Production deletion is disabled. Root relocation, same-device bind mounts, Windows cleanup, durable replay control, direct human approval, complete supported-filesystem adversarial tests, and independent security review remain open.
