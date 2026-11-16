# Dependency-tree classification evidence

The fixtures in `tests/test_realistic_dependency_trees.py` generate disposable Git repositories. They do not download packages, create real virtual environments, run install hooks, or target personal projects. The Windows fixture uses `Scripts/` and `Lib/` paths; POSIX fixtures use `bin/` and a `lib/python<runtime-version>/` site-packages path.

| Synthetic layout | Candidate result | Eligible logical bytes | Evidence |
|---|---:|---:|---|
| Node `node_modules` with scoped and unscoped package files | `REGENERABLE` | 160 | The scan's byte estimate and plan estimate equal the lengths of the five files beneath the candidate. |
| Python `.venv` with interpreter placeholder and installed-package metadata | `REGENERABLE` | 136 | The scan's byte estimate and plan estimate equal the lengths of the four files beneath the candidate. |
| Node package containing a package-owned `data/` directory | `BLOCKED` | 0 | The conservative user-data directory heuristic blocks the whole dependency tree. |
| Python site-packages containing an editable-install `.pth` file | `BLOCKED` | 0 | The conservative data-suffix heuristic blocks the whole virtual environment. |

Each test hashes an external synthetic sentinel before and after scanning and planning and asserts the hash is unchanged. The byte figures are logical file lengths for these tiny fixtures. They are not reclaimed-space measurements or estimates for real dependency trees.

The two blocked layouts document false-block tradeoffs in broad descendant heuristics. The tests deliberately preserve those rules. Do not relax them based only on package ownership or file names; any provenance-aware change must prove that unknown user files and local modifications remain protected. Realistic package trees vary by platform and package version, so this fixture evidence does not establish a universal eligibility percentage.
