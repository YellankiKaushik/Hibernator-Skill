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

## Install the Python CLI separately

The skill is only the agent-facing instructions. Install the Python package from the cloned repository as a separate step:

```text
python -m pip install .
python -m hibernator doctor
```

For development from a checkout, `python -m pip install -e .` is also supported. The skill invokes `python -m hibernator`, so the Python interpreter available to the host's terminal must be the one where Hibernator was installed. `doctor` verifies the command environment. Installing only the skill leaves the CLI dependency unavailable; installing only the package does not install a host skill.

## Verification status

| Host or capability | Evidence | Status and limitation |
|---|---|---|
| Skills CLI project install | Ran the local-source command against a disposable Git project and verified the installed `SKILL.md` path and contents. | Verified in an isolated smoke test. |
| Skills CLI user install | Ran the user-scope command with an isolated temporary user home and verified the installed `SKILL.md` path and contents. | Verified without changing the real user skill directory. |
| Codex skill workflow | In the current Codex session, followed the skill's read-only scan workflow against a disposable Git project. | Verified for this session and local CLI environment; this does not establish that `codex exec` works with the installed CLI configuration. |
| Codex CLI subprocess | Attempted `codex exec` against a disposable project with the installed project-scoped skill. | **Not verified.** The installed Codex CLI rejected the configured model as unsupported for this ChatGPT account. No CLI-hosted task completed. |
| Gemini CLI | Checked availability. | **Not tested:** CLI not installed. |
| Google Antigravity | Desktop launcher was present; attempted to inspect the app through the available desktop control. | **Not verified:** desktop control failed to initialize, so no host invocation was performed. |
| Current Codex session discovery | The skill metadata was present in the session catalog. | Discovery only; this is not evidence of host invocation. |

## Any other agent

An agent with local terminal access may use `python -m hibernator ...` directly. If it cannot run local commands, it can only explain the documentation and cannot inspect a developer's local project. Colab and remote agents can only access files explicitly mounted or provided to their runtime.

Agents may scan and prepare plans but cannot approve real deletion. Production apply is disabled in this preview implementation.
