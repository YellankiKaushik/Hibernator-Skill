# Release gate matrix

Status updated from local source inspection and executed evidence on 2026-11-16. A test skip is not a pass. See [the final validation report](FINAL_VALIDATION_REPORT.md) for commands, counts, and detailed limitations.

| ID | Gate | Current evidence | Status | Requirement to close |
|---|---|---|---|---|
| G-01 | Source exists and preserved | Existing untracked source inspected; pre-R3 workspace backup including `.git` created before edits | EVIDENCE | Keep the source and backup until owner accepts the final diff |
| G-02 | Windows unit suite | 52 ran, 46 passed, 6 skipped, 0 failed | PARTIAL | Run real link/hardlink cases where permitted; preserve skip status otherwise |
| G-03 | CLI read-only smoke | Standalone and reviewed audit smoke passed on disposable Git projects | PASSED LOCALLY | Keep platform/host scope narrow |
| G-04 | Python 3.10 runtime | Python 3.10 grammar parse only; no 3.10 interpreter run | NOT VERIFIED | Run on an actual supported Python 3.10 runtime |
| G-05 | Linux/macOS runtime | CI configured but not run | NOT VERIFIED | Obtain real platform test results |
| G-06 | Wheel build and contents | `setuptools>=68` unavailable; PyPI DNS failed. Skill data-file mapping is configured but artifact not built | BLOCKED | Build/install wheel in network-enabled or pre-provisioned environment; inspect installed skill resource |
| G-07 | Installed console script | Not run | NOT VERIFIED | Fresh-venv `hibernator --help`, `doctor`, and synthetic scan |
| G-08 | Production deletion safety | Apply deliberately disabled; independent review absent | BLOCKED | Close [security review gate](SECURITY_REVIEW_GATE.md) for each supported OS/filesystem |
| G-09 | Direct human approval | Exact digest prompt and refusal/status reporting tested; no production apply state transition | PARTIAL | Independent approval-boundary review before any production connection |
| G-10 | Symlink/junction/hardlink anti-escape | 5 real link/reparse cases and 1 hardlink case skipped; mocked reparse tests passed | BLOCKED | Run external-sentinel fixtures on a host permitting these links, or keep host unsupported |
| G-11 | Interruption and journaling | Synthetic interruption and removal-error reports tested; outcomes marked unknown when partial | PARTIAL | Test power-loss/crash durability and reviewer assessment |
| G-12 | Agent Skills portability | Current Codex session surfaced skill; no separate invocation; Gemini/Antigravity unavailable | PARTIAL | Smoke-test each available host, label others not tested |
| G-13 | GitHub Actions | Windows/Ubuntu/macOS and Python 3.10–3.14 configured; no run | NOT RUN | Push only after owner approval, then record workflow URLs/logs |
| G-14 | License | No license selected | OWNER DECISION | Choose and approve license; MIT is only a proposal |
| G-15 | Repository publication | Public GitHub target empty; local remote absent and `.git/config` unwritable | NOT STARTED | Restore legitimate Git config access and obtain explicit push approval |
| G-16 | Real reclaimed storage | No production cleanup performed | NO EVIDENCE | Only claim after secure cleanup is approved and measured accurately |
| G-17 | Restore workflow | Preview-only commands and no-mutation test passed | PARTIAL BY DESIGN | Keep execution outside this release scope or separately verify it |
| G-18 | Independent source/security review | No independent reviewer report | NOT PERFORMED | Review exact source revision and record findings |

## Release scope decision

**Current recommendation: NO-GO.** The repository is a locally validated preview candidate, but wheel/console verification, CI execution, license, and publication decisions remain open. Production deletion is blocked by missing platform-specific evidence and independent review.

- **Preview pre-release:** could be considered only after wheel/console and supported-host evidence plus owner license/publication gates, with prominent `PREVIEW — DELETION DISABLED` labeling.
- **Production cleanup release:** requires all relevant gates above, independent approval of the exact revision, adversarial platform evidence, and explicit owner publication approval.
