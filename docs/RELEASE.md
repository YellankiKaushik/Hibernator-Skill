# Preview and production release gates

Hibernator is a **preview-only implementation with production deletion disabled**. The Python CLI can scan, classify, plan, report, and preview restoration. Production `apply` refuses on every platform. No GitHub Release, tag, or PyPI package has been published.

## Preview and hands-on testing

- [x] Owner selected the standard MIT License; root `LICENSE` and package metadata identify MIT.
- [x] C-01 through C-08 source history was consolidated into the local main integration branch without rewriting commits.
- [x] Windows, Ubuntu, and macOS CI matrix passed for Python 3.10–3.14, including wheel installation, CLI startup, and packaged skill verification. Junction and Windows directory-fsync skips remain unverified; see [the release gate matrix](RELEASE_GATE_MATRIX.md).
- [x] Readme, CLI, safety, agent, restore, and test documentation are aligned with preview behavior.
- [x] Repeatable disposable-project instructions are in [the user testing guide](USER_TESTING.md).
- [ ] Run owner hands-on user acceptance testing and record feedback.
- [ ] After UAT, owner reviews the exact release diff and decides whether a tagged release or PyPI publication is wanted.

The current objective is to prepare a preview for hands-on testing. Consolidation does not itself publish a formal release or package.

## Production cleanup — separate gate

- [ ] Define supported operating systems/filesystems and platform-specific no-follow implementations.
- [ ] Resolve root/ancestor relocation races, same-device bind-mount identification, concurrent mutation, interruption, and recovery behavior.
- [ ] Implement durable replay protection and an approval boundary that establishes direct human control.
- [ ] Run adversarial external-sentinel and filesystem tests on every supported OS/filesystem with no relevant security skips.
- [ ] Obtain independent filesystem-security review of the exact proposed implementation revision.
- [ ] Obtain separate owner approval before connecting any reviewed implementation to production `apply`.

The current POSIX cleanup prototype is unwired and restricted to synthetic test fixtures. It does not close the production gate. No compatibility, reclaimed-storage, physical free-space, or restoration-success claim may exceed measured evidence.
