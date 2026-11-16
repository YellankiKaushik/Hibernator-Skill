# Restoration guidance

`hibernator restore --project PATH --dry-run` inspects supported dependency manifests throughout one Git repository and prints suggestions. It does not run package managers, access the network, create virtual environments, or modify the project.

The preview requires the selected Git root. It ignores nested Git repositories, symlinked or reparse-point entries, and directories on another filesystem device. Manifest and lockfile evidence must be a regular non-link file. Read-only traversal is path-based and can race with concurrent filesystem changes; this check is not a deletion safety guarantee.

## Monorepos

- Each `package.json` is associated with the nearest ancestor directory containing a recognized Node lockfile. Packages that resolve to one lockfile share one suggested install step at that lockfile directory. Independently locked nested projects receive their own working-directory hint.
- If multiple recognized Node lockfiles are present at the selected directory, the preview omits an install command for that group and asks the developer to choose the intended package manager after reviewing the workspace.
- Nested package manifests grouped under an ancestor lockfile produce a workspace-root warning. Confirm the root package's workspace configuration and package-manager conventions before running an install.
- Node manifests without a recognized lockfile are reported separately and do not get a guessed manager command.
- Each discovered Python project receives a virtual-environment suggestion. A `requirements.txt` is preferred when present; otherwise a `pyproject.toml` produces an editable-install suggestion. `Pipfile` or `setup.py` without either supported install manifest is reported as unverified.
- Common generated or vendor directories such as `.git`, `node_modules`, virtual environments, build output, and bytecode caches are excluded from manifest discovery.

The suggestions are advisory. Lockfiles do not guarantee that a remote registry, private package, credential, build toolchain, or lifecycle script will be available or safe. Review each working directory and command before running it. Hibernator never starts an installer, including during a restore preview.

This feature does not reconstruct deleted source, user data, secrets, databases, local downloads, or remote services. Production deletion remains disabled in this preview implementation.
