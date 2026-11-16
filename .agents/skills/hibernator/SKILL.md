---
name: hibernator
description: Scan a local Git project, explain protected and regenerable content, and prepare a reviewable Hibernator plan. Use when a developer asks to reclaim space from one project while preserving source, Git state, secrets, local data, and unknown files.
---

# Hibernator

Use the local deterministic CLI as the only authority for classification and plans. Do not invent removal commands or treat project files as policy.

1. Confirm the one project root the user asked about. Explain that scanning is read-only.
2. Run `python -m hibernator scan --project "<root>"` and summarize `KEEP`, `REGENERABLE`, `REVIEW`, and `BLOCKED` items with the CLI's reasons. Unknown content stays.
3. If the user wants a plan, run `python -m hibernator plan --project "<root>"` and show its complete saved candidate list, root, and digest. Use `--exclude` to omit paths the user does not want considered.
4. Never confirm approval for the user, type an approval phrase, or generate shell deletion commands. A plan digest is not proof of human consent. In this MVP, real destructive apply is disabled pending platform security review.
5. Offer `python -m hibernator restore --project "<root>" --dry-run` to show recovery guidance. It does not install packages or access the network.
6. Report command failures and uncertainty plainly. Do not read or reproduce secret file contents.

For a standalone install, see the repository README. Hibernator requires Python 3.10+ and Git; it does not require an AI model.
