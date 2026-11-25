# Dependency-tree classification evidence

## Retirement rule pack 2026.11.2

| Rule | Positive evidence | Preserved boundaries |
| --- | --- | --- |
| `node-dependencies-v2` | Enclosing npm manifest and one npm lockfile v2/v3; workspace membership when relevant; installed paths, names and versions match lock entries on the public npm registry. | Local, custom or private sources; ambiguous managers; links, package data, unrecognized files and npm shim layouts without verified provenance. |
| `python-venv-v2` | Local `pyvenv.cfg`, simple pinned `requirements.txt`, and matching installed distribution directories. | Editable or external dependencies, uncertain import roots, archives, local data, hard links and unverified `.pth` entries. |
| `python-bytecode-v2` | An associated source file for every recognized CPython or PyPy bytecode entry. | Unknown entries, orphaned bytecode and tracked contents. |
| `pytest-cache-v2` | A pytest configuration section and recognized cache structure. | Arbitrary files and tracked contents. |
| `next-cache-v2` | Enclosing Next.js manifest/config and recognized webpack or SWC cache files. | Whole builds, deployments, unique output and unverified contents. |

A Vite optimizer subtree can be included inside an eligible npm candidate when project context and the cache structure match. A protected or uncertain parent suppresses child suggestions. The report lists detected, partially supported and unsupported technologies. Yarn/pnpm linked stores and generic Rust, Java, .NET, Flutter, Ruff, mypy and other build artifacts stay review-only.

## Legacy scan and schema-2 preview

The fixtures in `tests/test_realistic_dependency_trees.py` generate disposable Git repositories. They do not download packages, create real virtual environments, run install hooks, or target personal projects. The Windows fixture uses `Scripts/` and `Lib/` paths; POSIX fixtures use `bin/` and a `lib/python<runtime-version>/` site-packages path.

| Synthetic layout | Candidate result | Eligible logical bytes | Evidence |
|---|---:|---:|---|
| Node `node_modules` with scoped and unscoped package files | `REGENERABLE` | 160 | The scan's byte estimate and plan estimate equal the lengths of the five files beneath the candidate. |
| Python `.venv` with interpreter placeholder and installed-package metadata | `REGENERABLE` | 136 | The scan's byte estimate and plan estimate equal the lengths of the four files beneath the candidate. |
| Node package containing a package-owned `data/` directory | `BLOCKED` | 0 | The conservative user-data directory heuristic blocks the whole dependency tree. |
| Python site-packages containing an arbitrary `.pth` file | `BLOCKED` | 0 | A custom path or executable startup hook has no verified recreation source. |
| Python site-packages containing a pip-shaped editable `.pth`, matching finder and `.dist-info/direct_url.json` for a project inside the repository | `REGENERABLE` | Measured in test | The scanner accepts only the exact generated finder line, matching distribution metadata, `editable: true`, and a local source with `pyproject.toml` or `setup.py` inside the selected repository. The test checks scan and plan byte totals against all synthetic environment files. |
| Same editable metadata pointing outside the selected repository | `BLOCKED` | 0 candidates | The external source is not part of the restoration scope; its sentinel is unchanged. |

Each test hashes an external synthetic sentinel before and after scanning and planning and asserts the hash is unchanged. The byte figures are logical file lengths for these tiny fixtures. They are not reclaimed-space measurements or estimates for real dependency trees.

Node package `data/` directories remain blocked: a package name and lockfile cannot prove that a nested file has not been downloaded or locally changed since installation. Arbitrary or externally sourced Python `.pth` files remain blocked as well. Only the narrow pip editable-install shape with corroborating local metadata is exempted. This does not establish a universal eligibility percentage, and the scanner still preserves all other unknown user files.
