# Repository instructions

- Treat `MASTER_TECHNICAL_PRD.md` supplied by the project owner as the source of truth. Unknown project content is protected by default.
- Do not run cleanup on real user projects. Destructive tests must use programmatically generated Git repositories under test-owned temporary directories.
- The production `apply` command must remain disabled until the platform-specific filesystem security design has independent review and explicit owner approval for the exact implementation. Do not connect `secure_remove.py` to production apply. Do not add `--yes`, unrestricted globs, `git clean`, or `git reset --hard`.
- Keep scan, plan, and restore preview offline and read-only with respect to the target project.
- Preserve local changes and tracked files. Tests must demonstrate that plans become stale after relevant filesystem/Git changes.
- Run the standard-library test suite with `python -m unittest discover -v` when Python 3.10+ is available.
- The owner selected the standard MIT License. Keep `LICENSE`, `pyproject.toml`, and license documentation consistent; do not change the selected license without the owner's direction.
- Do not create a GitHub Release, tag, or publish a package unless the owner separately approves.
