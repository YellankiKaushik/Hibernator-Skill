---
name: hibernator
description: Prepare a fast read-only retirement report for one inactive local Git project so its owner can review reproducible artifacts and preserve source and important data.
---
# Hibernator

Confirm one explicit local Git repository root. Use the root already provided by the owner. Run `doctor` only when setup is uncertain.

Run `python -m hibernator retire --project "<root>" --format json` once in the authorized local terminal and wait for it to finish. Use the trusted Hibernator Python environment from a trusted working directory outside the target, and pass the target's exact absolute path. Report a version mismatch or missing access and give the owner the read-only invocation if needed. Never substitute a clone or cloud workspace, fall back to a chain of legacy commands, or automatically enable deep mode.

Summarize the observed and offered logical bytes, largest candidate paths, protection decisions, limitations, and the private local report locations. Keep raw private results and absolute paths out of chat unless the owner requests them. Use the CLI's classifications and report failures accurately. The report is advisory.

**STOP after reporting.** The owner alone decides and performs manual cleanup in their file manager. Never delete, move, trash, quarantine, overwrite, automate a file manager, run or generate deletion commands, invoke apply, enter approval phrases, or use another tool to perform those actions. A report or subsequent confirmation cannot authorize the agent to do so.

Only on a separate owner request, run `python -m hibernator verify --report "<private report file>" --format json` to observe the listed paths. Give recovery guidance when requested and never install dependencies, execute project code, or run recovery commands.
