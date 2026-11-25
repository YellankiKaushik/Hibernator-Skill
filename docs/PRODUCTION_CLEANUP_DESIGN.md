# Production cleanup engineering status

> This document records the retired fixture-only deletion design. Production deletion is outside Hibernator’s scope. The prototype now lives under `tests/`.

## Status

Production deletion remains **disabled**. `apply_production()` always refuses, and the CLI only records that an approved plan was not attempted. The descriptor-relative module in `src/hibernator/secure_remove.py` is unwired and can only be exercised against in-memory registered test fixtures with a synthetic marker under the system temporary directory. It is an engineering prototype, not an enabled cleanup backend.

No independent filesystem security review has been completed for this implementation revision. No supported filesystem has been approved for production deletion.

## Prototype design

On POSIX, the fixture-only prototype opens the Git root and each directory using directory file descriptors with `O_NOFOLLOW`, then performs `stat`, `open`, `unlink`, and `rmdir` relative to pinned parent descriptors. It compares the root and candidate identities with the saved plan, revalidates the plan and current scan, refuses symbolic links, special files, hard-linked regular files, and device changes, and preflights the complete candidate before removing entries. It flushes affected parent directories after namespace changes. Required descriptor-relative operations are checked at runtime; unavailable capabilities fail closed.

The cleanup journal writes and flushes the report file, atomically replaces the destination, then flushes the containing directory on POSIX. Failure to flush that directory propagates as an error because the rename’s crash durability is uncertain. Windows has no equivalent implementation in this prototype; directory flushing is not claimed there.

The plan is content-digested and current project/Git state is checked immediately before fixture deletion. Replaying a consumed plan fails because its candidate no longer matches the plan. This is not a durable global nonce store and does not prove that an identical path recreated later is the same object; identity and current-state validation are the present replay barriers.

## Known security limitations

- Descriptor-relative operations prevent following a swapped symbolic link and constrain each operation to an already opened directory object. They do not prevent another process with write access from renaming the selected project root or an ancestor while deletion is in progress. The opened root could then be reachable outside the originally selected pathname. Root relocation, ancestor mutation, and concurrent writers require further platform-specific design and adversarial review.
- The preflight and removal passes are separate. Entries are rechecked during removal, but concurrent mutation can still cause a partial cleanup. The journal must report uncertainty; it cannot promise transaction rollback.
- The POSIX prototype has not been independently reviewed on ext4, XFS, APFS, or other filesystems. Directory `fsync` behavior, network filesystems, overlay filesystems, snapshots, and mount namespaces are not certified.
- The prototype compares `st_dev`; this detects ordinary cross-device mounts but does not reliably identify same-device bind mounts. Platform-specific mount identity checks and adversarial tests are still required.
- Windows cleanup is explicitly unsupported by this module. Junctions, mount points, reparse tags, sharing modes, volume identity, and Windows handle-relative deletion need a separate reviewed implementation and tests on real Windows filesystems.
- Direct terminal confirmation is an interaction requirement, not cryptographic evidence that a human rather than an agent supplied the response. Production approval needs an enforceable human-control boundary.
- Plan validation and journal durability do not establish that all files classified regenerable are unwanted. Classification remains conservative and product behavior remains preview-only.
- These tests exercise synthetic repositories only. Privilege-dependent hard-link, symlink, junction, and mount cases may be skipped in a given environment; any skip is unverified on that platform.

## Required gates before enabling deletion

1. Define supported operating systems and filesystems explicitly and provide a platform-specific no-follow backend for each.
2. Resolve root/ancestor relocation and concurrent-writer races, including a reviewed policy for whether any partial deletion can occur after a race is detected.
3. Define durable replay protection and human confirmation that cannot be satisfied by a generic agent response.
4. Run the adversarial suite on each supported OS/filesystem, with no relevant skipped security cases, including outside-root sentinels and race injection.
5. Obtain independent filesystem-security review of the exact implementation commit and test evidence.
6. Keep the public CLI and package defaults fail-closed until the owner explicitly approves the reviewed production release.

Until every gate is complete, preview-only is the only supported product mode.
