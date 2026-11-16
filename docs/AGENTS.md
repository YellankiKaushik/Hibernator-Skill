# Agent Skill setup and verification

Hibernator has two separate installable parts:

1. **The Agent Skill** provides instructions to a compatible host. It does not install Hibernator's Python code.
2. **The Python CLI** performs the local scan and plan operations. Installing it does not register a skill with an agent host.

The CLI must be installed in the Python interpreter available to the agent's local terminal. Hibernator requires Python 3.10+ and Git. See the [README installation steps](../README.md#installation).

## Codex

The cloned repository contains the workspace skill at `.agents/skills/hibernator/SKILL.md`. A compatible Codex workspace can discover skills from `.agents/skills/`. To install from this checkout with GitHub CLI's `gh skill` command:

```sh
# Run from the project where the skill should be installed.
gh skill install /path/to/Hibernator-Skill hibernator --from-local --allow-hidden-dirs --agent codex --scope project

# Use user scope for availability across the user's projects.
gh skill install /path/to/Hibernator-Skill hibernator --from-local --allow-hidden-dirs --agent codex --scope user
```

On Windows PowerShell, replace the source with a quoted Windows path, for example `"C:\work\Hibernator-Skill"`. The hidden-directory option is needed because the skill source is under `.agents/`. Review the skill before installing it. Check the host skill listing, then start or reload a session. The [`gh skill install` reference](https://cli.github.com/manual/gh_skill_install) documents repository/local-source installs and agent/scope flags.

## Gemini CLI

Gemini CLI documents `.agents/skills/` as a workspace and user-scope discovery alias. Install from the public repository into the current workspace:

```sh
gemini skills install https://github.com/YellankiKaushik/Hibernator-Skill --path .agents/skills/hibernator --scope workspace
gemini skills list
```

Alternatively, open a trusted Hibernator checkout; its skill already exists at `.agents/skills/hibernator/`. In an interactive session use `/skills list` and `/skills reload`; ask Gemini to use Hibernator for a project scan. Gemini CLI was not installed in the integration environment, so host invocation remains **unverified**. See the [official Gemini CLI Agent Skills guide](https://geminicli.com/docs/cli/skills/).

## Google Antigravity

Antigravity App, IDE, and CLI document `.agents/skills/<skill>/` for workspace skills. Open a trusted Hibernator checkout and verify the skill in the host's skill/customizations listing. In the App, skills may be invoked by their slash command (for this skill, `/hibernator`) or selected automatically based on the request.

The documented global location is `~/.gemini/config/skills/hibernator/`. A manual installation copies the full `hibernator` skill directory there; on Windows the equivalent base is `%USERPROFILE%\.gemini\config\skills\`. The Antigravity CLI also documents `/skills reload` or starting a new session after adding a skill. The Antigravity launcher was present in the integration environment, but desktop control did not initialize, so **host invocation was not tested**. See [Google's Antigravity Agent Skills guide](https://antigravity.google/docs/skills).

## Other agents

An agent that can read Agent Skills and run local commands can follow `.agents/skills/hibernator/SKILL.md`. It may run `python -m hibernator ...` directly after the CLI is installed in that same terminal environment. Do not infer host support from the presence of `SKILL.md`; check the host's documented discovery path and confirm it lists the skill.

Agents may inspect and prepare plans, but must not impersonate the user, type approval, or generate deletion commands. Production apply is disabled.

## Verification record

| Host or capability | Evidence | Status |
|---|---|---|
| GitHub Skills CLI project install | Local-source install into a disposable Git project; verified destination and `SKILL.md` contents. | Verified in isolated smoke test. |
| GitHub Skills CLI user install | User-scope install into an isolated temporary home; verified destination without changing the real user skill directory. | Verified in isolated smoke test. |
| Codex session | Followed the skill's read-only scan workflow on a disposable Git project; scan passed and the external sentinel was unchanged. | Verified for that Codex session and local CLI. |
| `codex exec` subprocess | Attempted with the installed project-scoped skill. | Not verified; configured model was rejected as unsupported for the signed-in ChatGPT account. |
| Gemini CLI | Checked executable availability. | Not tested; CLI was not installed. |
| Google Antigravity | Launcher was present; attempted desktop inspection. | Not verified; desktop control failed to initialize, so no invocation occurred. |

Official host documentation establishes documented discovery and invocation behavior; it does not replace Hibernator-specific runtime testing. The project/package matrix and host invocation results are tracked separately in the [release gate matrix](RELEASE_GATE_MATRIX.md).
