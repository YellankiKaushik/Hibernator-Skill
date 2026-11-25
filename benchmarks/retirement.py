"""Compare retirement with the old scan-plus-plan sequence on disposable Git fixtures."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def peak_memory() -> int:
    if os.name == "posix":
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value if sys.platform == "darwin" else value * 1024
    from ctypes import wintypes

    class Memory(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("peak", "working", "peak_paged", "paged",
                                               "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")
        ]

    memory = Memory()
    memory.size = ctypes.sizeof(memory)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    query = ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes = (wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD)
    return memory.peak if query(get_process(), ctypes.byref(memory), memory.size) else 0


def worker(mode: str, root: str, output: Path) -> None:
    from hibernator.cli import main

    def invoke(argv):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(io.StringIO()):
            result = main(argv)
        if result:
            raise RuntimeError(f"{mode} failed with {result}: {capture.getvalue()}")
        return json.loads(capture.getvalue())

    start = time.perf_counter()
    if mode == "baseline":
        calls = {"scandir_calls": 0, "path_lstat_calls": 0, "git_subprocesses": 0, "git_seconds": 0.0}
        scandir, lstat, run = os.scandir, Path.lstat, subprocess.run

        def count_scan(*args, **kwargs):
            calls["scandir_calls"] += 1
            return scandir(*args, **kwargs)

        def count_stat(*args, **kwargs):
            calls["path_lstat_calls"] += 1
            return lstat(*args, **kwargs)

        def count_git(args, **kwargs):
            started = time.perf_counter()
            calls["git_subprocesses"] += 1
            try:
                return run(args, **kwargs)
            finally:
                calls["git_seconds"] += time.perf_counter() - started

        with patch("os.scandir", count_scan), patch.object(Path, "lstat", count_stat), patch("subprocess.run", count_git):
            scan = invoke(["scan", "--project", root, "--format", "json"])
            scanned = time.perf_counter()
            plan = invoke(["plan", "--project", root, "--output", str(output / "baseline.json"), "--format", "json"])
        candidates = {item["path"]: item["logical_bytes"] for item in plan["candidates"]}
        result = {"candidates": candidates, "metrics": {**calls, "phase_seconds": {
            "scan": scanned - start, "plan": time.perf_counter() - scanned,
        }, "inferred_payload_bytes_hashed": sum(candidates.values()) +
            sum(item["logical_bytes"] for item in scan["items"] if item["decision"] == "REGENERABLE")}}
    else:
        options = ["--deep"] if mode == "deep" else []
        summary = invoke(["retire", "--project", root, "--output", str(output), "--format", "json", *options])
        report = json.loads((output / summary["reports"]["json"]).read_bytes())
        result = {"metrics": summary["metrics"], "candidates": {
            item["path"]: item["logical_bytes"] for item in report["items"] if item["disposition"] == "offered"
        }}
    result.update(seconds=time.perf_counter() - start, peak_process_bytes=peak_memory())
    print(json.dumps(result, sort_keys=True))


def populate(fixture, count: int, *, monorepo: bool, payload_mib: int) -> None:
    for prefix in ("", "apps/web/") if monorepo else ("",):
        fixture.write(prefix + "package.json", '{"name":"fixture","dependencies":{"pkg":"1.0.0"}}')
        fixture.write(prefix + "package-lock.json", json.dumps({
            "name": "fixture", "lockfileVersion": 3, "packages": {
                "": {"name": "fixture", "dependencies": {"pkg": "1.0.0"}},
                "node_modules/pkg": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/pkg/-/pkg-1.0.0.tgz"},
            },
        }))
        fixture.write(prefix + "node_modules/pkg/package.json", '{"name":"pkg","version":"1.0.0"}')
        for i in range(count):
            fixture.write(f"{prefix}node_modules/pkg/lib{i // 100}/module{i}.js", "module.exports = 123;\n")
        for i in range(payload_mib):
            fixture.write(f"{prefix}node_modules/pkg/payload{i}.js", b" " * (1 << 20))
    fixture.write("requirements.txt", "example==1.0\n")
    fixture.write(".venv/pyvenv.cfg", "home = synthetic\n")
    fixture.write(".venv/Scripts/python.exe", "synthetic\n")
    fixture.write(".venv/Lib/site-packages/example-1.0.dist-info/METADATA", "Name: example\nVersion: 1.0\n")
    fixture.write(".venv/Lib/site-packages/example.py", "VALUE = 1\n")
    fixture.write("src/app.js", "export const app = true;\n")
    fixture.commit("src/app.js", "package.json", "package-lock.json", "requirements.txt")
    fixture.write("uploads/synthetic.db", "unique synthetic data\n")
    fixture.write(".env", "BENCHMARK_ONLY=fixture\n")


def benchmark(args) -> None:
    from tests.helpers import GitFixture

    cases = [("small", 200, False), ("large", args.files, False), ("monorepo", 300, True)]
    if args.payload_mib:
        cases.append(("large-payload", 200, False))
    print(json.dumps({"os": platform.platform(), "python": sys.version.split()[0],
                      "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                      "storage": "OS temporary filesystem", "cache": "warm/mixed, alternating run order",
                      "trials": args.trials}), flush=True)
    for name, count, monorepo in cases:
        fixture = GitFixture()
        try:
            populate(fixture, count, monorepo=monorepo, payload_mib=args.payload_mib if name == "large-payload" else 0)
            entries = [p for p in fixture.root.rglob("*") if ".git" not in p.relative_to(fixture.root).parts]
            files = [p for p in entries if p.is_file()]
            modes = (["baseline"] if args.baseline_src else []) + ["fast", "deep"]
            results = {mode: [] for mode in modes}
            for trial in range(args.trials):
                for mode in modes if trial % 2 == 0 else reversed(modes):
                    source = Path(args.baseline_src).resolve() if mode == "baseline" else ROOT / "src"
                    output = fixture.root.parent / f"{mode}-{trial}"
                    output.mkdir(mode=0o700)
                    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
                    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", mode,
                                             str(fixture.root), str(output)], env=env, capture_output=True,
                                            text=True, timeout=300)
                    if result.returncode:
                        raise RuntimeError(f"Benchmark worker failed for {name}/{mode}: {result.stderr}")
                    results[mode].append(json.loads(result.stdout))
            medians = {mode: statistics.median(item["seconds"] for item in runs) for mode, runs in results.items()}
            candidates = results["fast"][0]["candidates"]
            if any(run["candidates"] != candidates for runs in results.values() for run in runs):
                raise RuntimeError("Candidate paths or sizes differ across benchmark modes.")
            print(json.dumps({"fixture": name, "files": len(files), "directories": 1 + len(entries) - len(files),
                              "logical_bytes": sum(p.stat().st_size for p in files), "median_seconds": medians,
                              "candidates": candidates, "runs": results}), flush=True)
        finally:
            fixture.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--baseline-src", help="The src directory from the previous source checkout")
        parser.add_argument("--files", type=int, default=10_000, help="File count for the large dependency tree")
        parser.add_argument("--trials", type=int, default=3)
        parser.add_argument("--payload-mib", type=int, default=0)
        arguments = parser.parse_args()
        if not 1 <= arguments.trials <= 10 or not 1 <= arguments.files <= 50_000 or not 0 <= arguments.payload_mib <= 1024:
            parser.error("Use 1-10 trials, 1-50,000 files and 0-1,024 MiB of optional payload.")
        benchmark(arguments)
