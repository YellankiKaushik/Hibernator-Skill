# Release checklist

The source repository is public, but Hibernator remains a **preview-only implementation with production deletion disabled**. No tagged release or package has been published. The current cross-platform build and test evidence is [GitHub Actions run #2](https://github.com/YellankiKaushik/Hibernator-Skill/actions/runs/43814217765): 18 of 18 jobs passed on Windows, Ubuntu, and macOS for Python 3.10–3.14. Each full unittest job ran 52 tests; three Windows-junction tests were skipped because the runner did not permit junction creation. Those cases remain unverified.

Before a preview release:

- [x] Build the wheel and install it into a fresh virtual environment on Windows, Ubuntu, and macOS; verify the `hibernator` entry point and packaged skill file in CI.
- [x] Run the Python 3.10–3.14 test matrix on Windows, Ubuntu, and macOS.
- [ ] Verify actual invocation from Codex in an unrelated project and test other agent hosts before claiming support. Keep unavailable hosts labeled unverified.
- [ ] Owner selects a license and confirms attribution obligations.
- [ ] Review the exact proposed release diff and release notes.
- [ ] Obtain explicit owner approval before creating a tag, publishing a release, or publishing a package.

Before enabling production deletion, all of the following are required independently of preview publication:

- [ ] Complete the platform-specific filesystem design and the threat model in [the security review gate](SECURITY_REVIEW_GATE.md).
- [ ] Run external-sentinel, race, interruption, and recovery tests on each supported OS/filesystem combination, including the skipped Windows junction scenarios.
- [ ] Obtain independent filesystem-security review of the exact source revision and record reviewer evidence in [the release matrix](RELEASE_GATE_MATRIX.md).
- [ ] Obtain explicit owner approval for any change that enables production deletion.

No compatibility, benchmark, physical free-space, or restoration-success claim should exceed measured evidence. A successful preview CI run does not establish production deletion safety.
