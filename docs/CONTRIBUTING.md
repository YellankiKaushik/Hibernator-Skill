# Contributing

Hibernator handles destructive filesystem workflows. Changes must preserve the preview-only production boundary unless an independent platform security review and owner approval explicitly authorize a separate change.

## Development

- Python 3.10+ and Git are required. Runtime code uses the Python standard library. Installing/building the package uses the declared setuptools build backend and may need access to a package cache or package index.
- Run `python -m unittest discover -v` from the repository root.
- Tests that remove files must use generated, marked Git fixtures under a temporary directory. Never target a developer's real project.
- Add regression tests for observed failures. Tests must verify preservation of source, Git state, secrets, unknown content, and outside sentinels where relevant.
- Keep exported reports free of absolute project paths and secrets. Do not introduce telemetry, network calls, package-manager execution, or model-dependent safety decisions.
- Document platform-specific test limitations instead of skipping them silently or claiming compatibility. A skipped adversarial case is unverified.

## Changes and review

Use focused changes and include the exact test command and result in a pull request. Security-sensitive changes need a threat model, adversarial fixtures, and independent review. Never add generic approval bypasses, broad deletion commands, or implicit cleanup. Production deletion must remain disabled unless a separate owner-approved change passes the platform security gates.

## License

Hibernator is licensed under the MIT License in the root [`LICENSE`](../LICENSE). Contributions must be submitted by people who have the right to contribute them. No separate contributor license agreement is required by this repository. Do not submit third-party code or assets unless their license permits inclusion and required attribution is retained.
