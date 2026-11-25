# Testing

Use Python 3.10+ and Git. From this source checkout, set `PYTHONPATH=src` or install the package into your test environment.

```text
python -m unittest discover -v
python -m unittest -v tests.test_retirement tests.test_scan tests.test_plans
python -m pip wheel --no-deps --wheel-dir wheelhouse .
```

Install the wheel in a fresh environment with no source `PYTHONPATH`. Run `python -m tests.wheel_smoke` from the checkout using that environment's Python. It exercises both installed entry points, confirms the packaged skill and verifies that fixture-only removal backends are absent. The workflow runs the full suite and wheel checks across Windows, Ubuntu and macOS with Python 3.10–3.14, plus three adversarial jobs.

The tests use disposable Git fixtures. They compare project paths, file bytes and modes, Git index data and outside sentinels. The suite exercises guarded Git configuration and aliases, protected descendants, deep and legacy staleness, malformed or partial reports, concurrent writers, refusal and observation behavior. Links, junctions, POSIX filesystem operations and hard links may require different privileges or operating systems.

## Synthetic performance benchmark

```text
python benchmarks/retirement.py --baseline-src PATH_TO_BASELINE_SRC --files 10000 --trials 3 --payload-mib 128
```

Use the source directory from the previously verified commit for the baseline. The script prints one JSON object per fixture and compares exact candidate paths and logical sizes. Its cases cover a small mixed repo, large small-file tree, monorepo and optional payload. Runtime targets are engineering goals. CI checks primary-pass and payload counters without wall-clock thresholds. See the [retirement verification record](RETIREMENT_VALIDATION.md).
