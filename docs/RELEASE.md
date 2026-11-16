# Release checklist

The implementation has local validation, but is not ready to enable production cleanup or publish a public release. Before either:

- [ ] Owner reviews the P0 filesystem and human-approval decisions (OQ-001/OQ-002).
- [ ] A platform security review validates path-race, junction/reparse, mount, hardlink, and interruption controls.
- [ ] Close the evidence and reviewer fields in [the independent security gate](SECURITY_REVIEW_GATE.md) and [release matrix](RELEASE_GATE_MATRIX.md).
- [ ] Automated tests run successfully on Windows, Linux, and macOS; the current Windows run has 6 policy-driven link/reparse/hard-link skips, and Linux/macOS remain untested.
- [ ] Codex invocation is smoke-tested (workspace discovery was observed in this session); Gemini CLI and Antigravity remain labeled Not Tested until their hosts can be exercised.
- [ ] Owner selects a license and confirms attribution obligations.
- [ ] Build the wheel and install-test its `hibernator` console entry point and packaged skill file in an environment with setuptools available; local build could not fetch the backend due network name-resolution failure.
- [ ] Review docs, test evidence, release notes, and the exact proposed diff.
- [ ] Obtain separate owner approval before push, tag, or public release.

No compatibility, benchmark, free-space, or restoration-success claim should be made without actual evidence.
