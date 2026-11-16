# Agent setup

## Canonical skill

The repository includes `.agents/skills/hibernator/SKILL.md`. It uses the shared Agent Skills `name` and `description` frontmatter and calls the local CLI. Its metadata was present in the current Codex session's available-skill catalog. An end-to-end invocation through the host was not tested; Gemini CLI and Antigravity were unavailable.

## Codex

Keep the repository-level `.agents/skills/hibernator/` directory in the workspace. **Discovery verified with limitation:** the current Codex session listed Hibernator from the workspace skill directory. A separate host invocation smoke test was not performed. Use the standalone CLI if the skill is not discovered in another Codex setup.

## Gemini CLI

Keep `.agents/skills/hibernator/` in the workspace. Gemini CLI may use `.agents/skills` or its documented `.gemini/skills` integration; this project's discovery is **Not Tested**. Use the standalone CLI if needed.

## Google Antigravity

Keep `.agents/skills/hibernator/` in the workspace. Antigravity's discovery is **Not Tested for Hibernator**. Use the standalone CLI if needed.

## Any other agent

An agent with local terminal access may use `python -m hibernator ...` directly. If it cannot run local commands, it can only explain the documentation and cannot inspect or clean a laptop project. Google Colab can only access files mounted into its runtime; it cannot reclaim laptop storage by default.

Agents may scan and prepare plans but cannot approve real deletion. Production apply is disabled in this MVP.
