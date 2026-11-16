# Independent filesystem security review gate

**Scope:** Production cleanup. This checklist is a review protocol, not evidence that Hibernator is safe. Production `apply` remains disabled until an independent reviewer approves an exact implementation revision for named platforms and filesystems.

## Required review evidence

| Gate | Required evidence | Rule |
|---|---|---|
| SEC-01 | Threat model names adversary privileges, supported filesystems, and attacker-controlled directories | No generic “safe on Windows/Linux” claims |
| SEC-02 | Root pinned by filesystem identity with no root/home/parent ambiguity | Refuse on ambiguity |
| SEC-03 | Verified no-follow traversal and prevention of parent/candidate swaps | Repeated negative/stress tests on each supported OS |
| SEC-04 | Junction, reparse, mount-point, and symlink semantics established | Real fixtures where supported; a skipped test is not a pass |
| SEC-05 | Tracked/local source protection survives concurrent Git changes | Synthetic before/after hashes and Git state |
| SEC-06 | Approval binds plan, candidate identities/content, Git state, and rules | Any mismatch refuses |
| SEC-07 | Direct human approval cannot be silently supplied by an agent | Human-presence boundary independently reviewed |
| SEC-08 | Journal/replay/interruption behavior tested under forced errors | No silent success or stale automatic replay |
| SEC-09 | No deletion escapes the fixture root or affects an outside sentinel | Verify sentinel identity and content |
| SEC-10 | Reviewer independent from implementation author records scope/revision/findings | Review record required |

## Platform scenarios

**Windows:** NTFS junction to an external sentinel; directory symlink to an external sentinel; explicit behavior when symlink privilege is denied; UNC and long paths; alternate separators; trailing space/dot normalization; case-insensitivity; path substitution between validation and removal; reparse and volume mount points; locked files; ACL changes; open handles/share modes; hardlinks; interruption; antivirus interference. Record Windows version, filesystem, Python version, privilege level, and exact failures/skips.

**Linux and macOS:** symlink swaps; descriptor-relative/no-follow behavior; mount/bind-mount boundaries where permitted; hardlinks; case-sensitive and case-insensitive filesystems where available; permission-denied directories; concurrent processes/Git changes; crashes and interruption. Record filesystem details.

**Cross-platform:** ignored unknown files, nested Git/worktrees/submodules, tracked generated output, staged/unstaged work, secrets, SQLite, datasets, downloads, model weights, partial deletions, restoration-manifest integrity, and truthful free-space accounting.

All destructive tests must use programmatically generated temporary Git fixtures. Include an outside sentinel and verify its identity/content before and after. Never use a real project as a deletion target. The current host denied real symlink/junction/hard-link creation; the mocked reparse tests are supplementary and do not close this gate.

## Reviewer decision record

```text
Review identifier:
Reviewer and independence statement:
Exact code revision SHA / source snapshot digest:
Target OS, filesystem, version, and privilege assumptions:
Threat model / excluded attacker:
Design artifacts examined:
Tools and tests actually executed:
High-severity findings / open defects:
Required remediation / retest evidence:
APPROVED / APPROVED WITH LIMITATIONS / REJECTED:
Approval date and scope:
```

`APPROVED WITH LIMITATIONS` must name excluded platforms, filesystems, and privilege contexts. Without this independent review, status is **NOT REVIEWED** and production apply must stay disabled. A model self-check is not an independent review.

Python documents that `shutil.rmtree` symlink-attack resistance varies by platform and exposes `rmtree.avoids_symlink_attacks`; this capability flag alone is not a complete race-safety proof. See the [Python shutil documentation](https://docs.python.org/3/library/shutil.html).
