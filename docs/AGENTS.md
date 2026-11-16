# Agent setup and verification

## Canonical skill

The repository includes `.agents/skills/hibernator/SKILL.md` using the shared Agent Skills `name` and `description` frontmatter. It asks the host to invoke the local deterministic CLI and forbids agent approval or deletion commands. A packaged skill file alone does not prove a host can discover or invoke it.

The Skills CLI supports installing a local skill into either a project or the current user's shared skill directory. From the project that should receive the skill, run:

```text
gh skill install <path-to-Hibernator-Skill> hibernator --from-local --allow-hidden-dirs --agent codex --scope project
```

For the current user-wide installation, run:

```text
gh skill install <path-to-Hibernator-Skill> hibernator --from-local --allow-hidden-dirs --agent codex --scope user
```

The `--allow-hidden-dirs` option is needed because the source skill is under `.agents/`. Review the skill contents before trusting it; the CLI warns that hidden-directory skills may be untrusted. Project installation places the skill in the project's `.agents/skills/hibernator/`; user installation uses the host's shared user skill directory. The official [Codex CLI skills documentation](https://developers.openai.com/api/reference/cli) describes project and user scope installation. These commands install the skill; they do not install the Hibernator Python package or its CLI dependency.

## Verification status

| Host or capability | Evidence | Status and limitation |
|---|---|---|
| Skills CLI project install | Ran the local-source command against a disposable Git project and verified the installed `SKILL.md` path and contents. | Verified in an isolated smoke test. |
| Skills CLI user install | Ran the user-scope command with an isolated temporary user home and verified the installed `SKILL.md` path and contents. | Verified without changing the real user skill directory. |
| Codex host invocation | Attempted `codex exec` against a disposable project with the installed project-scoped skill. | **Not verified.** The installed Codex CLI rejected the configured model as unsupported for this ChatGPT account. No host task completed. |
| Gemini CLI | Checked availability. | **Not tested:** CLI not installed. |
| Google Antigravity | Desktop launcher was present. | **Not tested:** no host invocation performed. |
| Current Codex session discovery | The skill metadata was present in the session catalog. | Discovery only; this is not evidence of host invocation. |

## Any other agent

An agent with local terminal access may use `python -m hibernator ...` directly. If it cannot run local commands, it can only explain the documentation and cannot inspect a developer's local project. Colab and remote agents can only access files explicitly mounted or provided to their runtime.

Agents may scan and prepare plans but cannot approve real deletion. Production apply is disabled in this preview implementation.
