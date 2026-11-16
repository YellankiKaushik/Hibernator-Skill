# Repository instructions

- Treat `MASTER_TECHNICAL_PRD.md` supplied by the project owner as the source of truth. Unknown project content is protected by default.
- Do not run cleanup on real user projects. Destructive tests must use programmatically generated Git repositories under test-owned temporary directories.
- The production `apply` command must remain disabled until an owner-reviewed filesystem security design supports the actual host and platform. Do not add `--yes`, unrestricted globs, `git clean`, or `git reset --hard`.
- Keep scan, plan, and restore preview offline and read-only with respect to the target project.
- Preserve local changes and tracked files. Tests must demonstrate that plans become stale after relevant filesystem/Git changes.
- Run the standard-library test suite with `python -m unittest discover -v` when Python 3.10+ is available.
- Do not add a LICENSE until the repository owner selects one. Do not push or release without separate approval.
