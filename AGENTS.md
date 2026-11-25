# Repository instructions

- Treat the owner's retirement implementation specification as the product scope. Unknown project content is protected by default.
- Do not run cleanup on real user projects. Destructive tests must use programmatically generated Git repositories under test-owned temporary directories.
- The owner alone can perform manual cleanup outside Hibernator and the agent. Production `apply` is a noninteractive refusal. Keep fixture-only prototypes outside the installed package.
- Keep retire, verify, scan, plan, and restore preview offline and read-only with respect to the target project.
- Preserve local changes and tracked files. Tests must demonstrate that plans become stale after relevant filesystem/Git changes.
- Run the standard-library test suite with `python -m unittest discover -v` when Python 3.10+ is available.
- The owner selected the standard MIT License. Keep `LICENSE`, `pyproject.toml`, and license documentation consistent; do not change the selected license without the owner's direction.
- Do not create a GitHub Release, tag, or publish a package unless the owner separately approves.
