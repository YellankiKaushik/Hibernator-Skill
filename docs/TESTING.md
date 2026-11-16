# Testing

Run from the repository root with Python 3.10 or later and Git available:

```sh
python -m unittest discover -v
python -m compileall -q src tests
python -m hibernator --help
python -m hibernator doctor
python -m hibernator rules list
python -m pip wheel --no-deps --wheel-dir dist .
```

The standard-library suite creates temporary, synthetic Git repositories. Any fixture cleanup is limited to test-owned temporary roots. Never pass a real project path to a destructive test helper. The public CLI `apply` path must continue to refuse real deletion; `secure_remove.py` is an unwired fixture-only POSIX prototype.

## Coverage

The suite covers project-root validation, Git-tracked and untracked preservation, unknown/ignored data, secret-like files, Node and Python dependency evidence, `.pth` editable-install provenance, nested cache rules, traversal boundaries, mocked reparse and mount behavior, link/hard-link guards, nested Git boundaries, plan digests and stale plans, exact approval refusal, test-fixture cleanup, reports, interruption journal outcomes, restore previews and monorepo manifest selection, CLI output/exit codes, and Agent Skill metadata.

## Latest cross-platform evidence

[GitHub Actions run #12](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43832996714) passed all 18/18 jobs on the C-08 feature branch: 15 Windows/Ubuntu/macOS × Python 3.10–3.14 test, wheel/install, CLI, and packaged-skill jobs, plus 3 OS adversarial fixture jobs. The preceding full source/security matrix, [run #11](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43831231379), ran 78 tests in each of its 15 unit jobs and 47 tests in each of 3 adversarial jobs. The unit jobs skipped four Windows-junction cases per OS/Python job; Windows also skipped the POSIX-only directory-fsync test. Each adversarial job skipped its three Windows-junction cases. These are unverified cases, not passes.

The local Windows Python 3.14.10 run completed 78 tests with 10 skips: Windows junction, symlink, and hard-link creation restrictions plus the POSIX-only directory-fsync test. The [release gate matrix](RELEASE_GATE_MATRIX.md) tracks the exact unresolved platform/security scope. Final `main` CI evidence will be added after the consolidation push.

## Packaging checks

CI builds the wheel, creates a fresh virtual environment, installs the wheel without installing extra runtime dependencies, runs the installed `hibernator --help`, and verifies that `.agents/skills/hibernator/SKILL.md` was packaged. The local wheel build may fetch the declared `setuptools>=77` build backend when it is not already available. See [the workflow](../.github/workflows/test.yml) for the exact matrix and package checks.
