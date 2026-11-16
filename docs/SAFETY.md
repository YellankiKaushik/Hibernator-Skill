# Safety model

## Defaults

- One explicit Git repository root per scan. Filesystem roots, the user's home directory, non-Git paths, and repository parents/subdirectories are refused.
- Git queries are read-only. Tracked paths and Git state are fingerprinted; a changed plan is rejected.
- Only versioned artifact rules with project-manifest evidence can yield `REGENERABLE` candidates.
- Tracked descendants, secret-like files, common databases/downloads/user-data directories, nested Git metadata, links/reparse points, and mount crossings block a whole candidate.
- Git ignore status is never evidence of disposability. Unknown files are preserved or marked `REVIEW`.
- Scan, plan, report, and restore preview do not install dependencies, write into the target project, or contact a network service.
- Scan and restore traversal reject existing symlinked/reparse entries, do not cross filesystem-device boundaries, and stop at nested Git repositories. Manifest files must be regular non-link files inside the selected Git root.

These path-based read-only walks are not an atomic filesystem snapshot and are not a race-resistant deletion design. Concurrent replacement during a walk can invalidate its observations; any output is advisory, and production apply remains disabled pending a separate descriptor/handle-based implementation and independent review.

## Plan and approval boundary

Plans contain canonical root, root identity, Git snapshot, all classified review items, candidate paths and identities, content tree digests, rule-pack version, exclusions, and a digest over canonical JSON. The digest detects accidental or deliberate plan edits but is not authentication. Relevant Git, classification, or candidate changes invalidate the plan.

The CLI has no generic `--yes` switch. In a direct interactive terminal, apply displays the root, digest, and exact candidate list and requires `DELETE <digest>`. It records approval or decline in a local report. Even exact approval ends with `APPROVED_BUT_UNSUPPORTED`: production deletion refuses on all platforms. This is deliberate: portable path checks alone cannot close all Windows reparse-point and time-of-check/time-of-use races, and the PRD requires an owner-reviewed platform and human-approval design before real cleanup is enabled. Noninteractive apply records `APPROVAL_REQUIRED` and changes no project files.

The test-only cleanup function is separate from the CLI and requires an exact temporary fixture directory bearing a harness marker. Tests create those directories programmatically and tear them down through their own temporary-directory owner.

## Limitations

- A content fingerprint may read large candidate trees and can take time. Changes detected while fingerprinting fail closed.
- Free-space delta and physical reclamation are not measured by this MVP. Any displayed candidate size is a logical file-length estimate, not a promise of disk space reclaimed.
- Rules are intentionally narrow. Fewer candidates may be offered than a general cleanup tool.
- No cleanup can recover local-only content after deletion. Unknown or unverified downloads stay protected.
- Windows, Linux, macOS, filesystem-specific semantics, and real host skill discovery still require validation before compatibility claims.
