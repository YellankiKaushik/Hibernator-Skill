# Security policy

## Scope and current status

Hibernator handles local project paths and prepares cleanup plans. The MVP's real destructive apply is disabled pending a platform-specific security review. Do not use test-only APIs on real project data.

## Reporting a vulnerability

Please do not include secrets, private project contents, or full local paths in a public issue. Contact the repository owner privately through an available GitHub security advisory/contact channel and include the affected version, operating system/filesystem, minimal synthetic reproduction, and test evidence. If private reporting is unavailable, open a minimal public issue without sensitive details and request a private channel.

## Response

No response-time guarantee is currently offered. A verified preservation or boundary violation should block the affected rule and release until a regression test and fix are reviewed.
