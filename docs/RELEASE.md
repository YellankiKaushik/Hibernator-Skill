# Release checklists

Hibernator is a **preview-only implementation with production deletion disabled**. `apply_production()` refuses cleanup on every platform. The fixture-only POSIX deletion prototype is not connected to the CLI and is not a supported user operation. No tagged release or package has been published.

## Preview release checklist

- [x] Build the wheel, install it into fresh environments, verify the installed `hibernator` command, and verify the packaged skill file in CI. See the current evidence in [the release gate matrix](RELEASE_GATE_MATRIX.md).
- [x] Run the complete Windows, Ubuntu, and macOS matrix across Python 3.10–3.14 for the latest cleanup prototype revision. Any runner skips remain unverified; see the matrix for the exact run and skipped cases.
- [x] Document that the Agent Skill and standalone Python CLI are separate installations.
- [x] Verify one real Codex session workflow on a disposable Git project. Gemini CLI is not installed in the available environment; Antigravity invocation could not be tested because desktop control did not initialize. Neither host is claimed as verified.
- [ ] Owner selects a license and approves its attribution obligations.
- [ ] Owner reviews the exact proposed preview release diff and notes.
- [ ] Owner explicitly approves creating a tag, publishing a release, or publishing a package.

## Production release checklist

- [ ] Complete the platform-specific threat model and filesystem design in [the security review gate](SECURITY_REVIEW_GATE.md).
- [ ] Resolve root/ancestor relocation races and concurrent-writer behavior. The current fixture prototype does not satisfy this gate.
- [ ] Implement and independently review a no-follow backend for each explicitly supported operating system and filesystem. Windows deletion is unsupported in the prototype.
- [ ] Define durable replay protection and a human approval boundary that cannot be satisfied by a generic agent response.
- [ ] Run adversarial external-sentinel, race, interruption, and recovery tests on every supported OS/filesystem. Privilege-dependent skips count as unverified.
- [ ] Obtain independent filesystem-security review of the exact implementation revision and record the evidence in [the release gate matrix](RELEASE_GATE_MATRIX.md).
- [ ] Obtain explicit owner approval before any change enables production deletion.

Preview publication does not authorize production cleanup. No compatibility, reclaimed-storage, physical free-space, or restoration-success claim should exceed measured evidence.
