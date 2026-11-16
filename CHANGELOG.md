# Changelog

Changes for each unreleased version are recorded here. No GitHub Release, tag, or PyPI publication has been created.

## Unreleased — 0.1.0

- Consolidated C-01 through C-08 development into the existing implementation, preserving its commit history.
- Fixed nested cache matching and added realistic Node dependency-tree and Python editable-install classification coverage. Node package `data/` and unknown contents remain protected or for review unless safe regeneration is established.
- Hardened scan and restore-preview traversal around symlinks/reparse points, nested Git repositories, and filesystem-device boundaries; added outside-sentinel fixtures and monorepo restore guidance.
- Documented separate Agent Skill and Python CLI installation. Recorded actual Codex session testing and kept Gemini CLI and Antigravity invocation labeled unverified.
- Added an unwired POSIX descriptor-relative cleanup prototype restricted to registered synthetic test fixtures. Production deletion remains disabled.
- Made POSIX cleanup report replacement flush its parent directory and documented filesystem/security limitations.
- Updated the README, CLI/agent/release guidance, package license metadata, and hands-on preview test guide.
- Added the standard MIT License, copyright 2026 YellankiKaushik, as selected by the repository owner.
- Latest feature-branch validation passed 18/18 Windows/Ubuntu/macOS × Python 3.10–3.14 Actions jobs, including wheel install and CLI/skill package smoke checks. See the release matrix for test counts and unverified skips; final `main` CI will be recorded after consolidation.
- No production cleanup, GitHub Release, tag, or PyPI publication was performed.
