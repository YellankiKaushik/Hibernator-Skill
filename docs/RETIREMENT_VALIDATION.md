# Retirement verification record

The implementation baseline is GitHub `main` at `0cc9faa63d1dea858e2e1faebe2d8aeb3db15f78`. Its README and demo media were verified against that commit's exact Git tree. The earlier Technical PRD was unavailable. This revision follows the supplied retirement specification and preserves the MIT license.

## Tests and packaging

- Baseline `python -m unittest discover -v`: 81 discovered, 71 passed, zero failures, 10 skips. Baseline wheel build and installed module entry point passed.
- Final `python -m unittest discover -v`: 107 discovered, 96 passed, zero failures, 11 skips in 92.829 seconds.
- Windows 11 build 26300, Python 3.12.14 and Git 2.54.0.windows.1. Local skips cover four junction fixtures, four symlink creation fixtures, one hard-link fixture, POSIX directory fsync, and the POSIX hostile-filename fixture. Mock tests cover several boundary decisions. Actual junction, link and mount behavior across every supported filesystem remains unverified.
- A fresh 0.2.0 wheel installation passed both the Windows console executable and module entry point in a separate stable environment, as well as packaged Skill equality and the full installed CLI smoke. The launcher in the managed ephemeral temporary path returned exit 1 with empty output. The same wheel launcher passed in the stable environment.
- The existing CI matrix has 15 OS/Python jobs and three adversarial jobs. The older [18-job preview CI](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/45579668204) predates this implementation. Consult the live commit checks for CI on this revision.
- The publisher was checked against a disposable local bare Git remote. It refused a bad checksum and a moved base, fast-forwarded with a normal push, and read back the exact commit.

## One synthetic retirement

The actual mixed fixture produced `READY_FOR_MANUAL_REVIEW`, 395 observed logical bytes, 110 eligible and offered bytes, and a verified pair outside the fixture.

| Path | Logical bytes | Rule |
| --- | ---: | --- |
| `node_modules` | 57 | `node-dependencies-v2` |
| `.venv` | 53 | `python-venv-v2` |

The report preserved `.env`, package manifests, pinned requirements, `src` and `uploads`. Before/after checks matched fixture paths, modes, file bytes, index bytes, Git porcelain output and an outside sentinel. Hibernator did not modify project files. Actual bytes reclaimed by Hibernator: 0.

## Performance

Run `python benchmarks/retirement.py --baseline-src PATH_TO_BASELINE_SRC --files 10000 --trials 3 --payload-mib 128`. Measurements below are medians of three alternating trials on the Windows temporary filesystem. The cache was warm/mixed and concurrent host load varied. The baseline did a content-hashed scan and a separately content-hashed plan. Fast retirement uses advisory metadata observations. The exact offered roots and logical byte counts matched across modes on these fixtures.

| Fixture | Files / dirs | Logical bytes | Old scan + plan | Fast | Deep | Fast runtime reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Small mixed | 211 / 12 | 4,846 | 2.087 s | 0.567 s | 1.247 s | 72.8% |
| Large dependency tree | 10,011 / 110 | 220,446 | 26.590 s | 3.156 s | 25.937 s | 88.1% |
| Nested monorepo | 614 / 20 | 13,945 | 2.037 s | 0.451 s | 1.569 s | 77.8% |
| 128 MiB payload | 339 / 12 | 134,222,574 | 1.398 s | 0.345 s | 1.021 s | 75.3% |

The large fixture met the 50% fast-mode engineering target. Old scan and plan median phases were 13.619 s and 12.971 s. Git took 0.614 s across 14 calls. Fast retirement used 0.172 s for validation (0.156 s in five Git calls), 2.875 s for the inventory, 0.015 s for classification and consistency, and 0.078 s for writing and validating the pair. Old instrumentation observed 1,130 scandir and 82,626 `Path.lstat` calls across scans and Git metadata scope. Fast retirement reported one primary pass, 110 working-tree directory visits and 10,120 entry stats. These counters have different instrumentation scopes. Fast mode read 329 evidence bytes and hashed zero payload bytes. Deep mode hashed 220,096 bytes. The old sequence inferred 440,192 hashed bytes from its twice-fingerprinted candidates. Peak process working-set medians were 38.8 MiB old, 32.4 MiB fast and 52.7 MiB deep. These are synthetic Windows results, without measurements of SSD allocation or owner projects.

## Requirement coverage

| Spec | Status | Implementation and observed evidence |
| --- | --- | --- |
| 1–3 | Done | Existing Git tree and baseline suite verified. README and video preserved. |
| 4 | Done locally | `paths.py`, `git_state.py`, `cli.py`, test-only fixture backends. Root/output refusal, hostile config, dirty Git, outside sentinel and no-mutation cases in `test_retirement.py` and `wheel_smoke.py`. |
| 5.1 | Done | `retirement.py`, `inventory.py` and `retirement_reports.py`. Installed and module CLI returned matching candidate paths. |
| 5.1.1 | Done | Relative invocation, exact filters, default and explicit stores, cancellation and stderr progress exercised by `test_retirement.py`. |
| 5.2 | Done locally | Legacy `scan`, `plan`, `report`, `restore`, `doctor` and `rules` passed. `apply` returned exit 5 without accessing plan or stdin. Schema-2 same-size and staged edits stayed stale. |
| 5.3 | Done | `verify` checked pair, root and Git metadata and observed present, missing, changed and mocked unknown entries. |
| 6.1 | Done | One measured working-tree pass, bottom-up sizing, protected boundary suppression, no duplicate candidate sizes. |
| 6.2 | Done locally | Five Git subprocesses, indexed tracked paths, guarded config and HEAD/index observations. Missing and staged-deleted entries stay protected. |
| 6.3–6.3.1 | Done | Distinct fast metadata and deep content digests, bounded evidence and targeted recheck. Oversize and changed inputs suppress offers. |
| 6.4 | Done | Instrumented counters, stderr stages and progress, JSON stdout and exit 130 on interruption. |
| 7.1 | Done with conservative scope | `retire_rules.py` covers npm, pinned environments, bytecode, pytest and Next cache. Vite is included once inside verified npm paths. Legacy editable exception remains tested. |
| 7.2–7.3 | Core done, P2 deferred | Recovery inputs and limitations reported. More ecosystems, npm shim/link exceptions, broader editable provenance and physical allocation need dedicated evidence and tests. |
| 8–8.1 | Done locally | Report schema/digest, pair completion, injected write failure, concurrent writers, filters and exact totals exercised. |
| 9 | Done | Packaged Skill one-call policy, CLI documentation, historical prototype notes and preserved video attribution. |
| 10 | Done locally, CI pending | Full local suite and wheel passed. Four comparable fixtures measured. New GitHub CI requires the published commit. |
| 11 | Done locally | Baseline and synthetic safety gates, implementation, tests, package and demonstration completed. |
| 12–13 | Done locally | Real synthetic report, CLI contract, performance record and owner-only handoff. Owner UAT is separate. |
| 14 | Done locally, platform limits remain | Coverage above and named test modules. Real filesystem privileges, cross-platform CI and independent owner UAT are separate checks. |
