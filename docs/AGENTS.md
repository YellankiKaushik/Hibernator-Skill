# Set up Hibernator for a coding agent

Install the **Python CLI** in the same environment where the agent runs commands. The **Agent Skill** is a folder of instructions that helps compatible hosts discover the workflow. The two installations are separate. You can use the copy-and-paste prompt with any terminal-capable agent, even if the host has no Skill support.

1. Follow the [CLI installation steps](../README.md#installation), then run `hibernator doctor` or `python -m hibernator doctor` with the same Python the agent will use.
2. Open a trusted workspace in the agent. Give the agent read access to one Git repository you own and write access to a private output folder outside it.
3. Use the host setup below or paste the prompt. Ask for a read-only scan, a reviewable plan, and a restoration preview.

## Codex

The checkout ships [.agents/skills/hibernator/SKILL.md](../.agents/skills/hibernator/SKILL.md). Open the trusted Hibernator checkout and start a new Codex session to use its workspace skill. Select Hibernator from the available skills or ask Codex to use it for a local repository scan.

To make the skill available in another project, run this in that project using a GitHub CLI version with `gh skill` support:

```sh
gh skill install /path/to/Hibernator-Skill hibernator --from-local --allow-hidden-dirs --agent codex --scope project
```

Use `--scope user` to install it for your account instead. Replace the source path with your actual checkout path and quote Windows paths that contain spaces. The hidden-directory option gives the installer access to the source under `.agents/`. Review the skill before installing it. Restart the agent session if it does not discover a newly installed skill. [Codex skills documentation](https://developers.openai.com/codex/skills) · [GitHub CLI skill install reference](https://cli.github.com/manual/gh_skill_install)

A Codex session ran the Hibernator workflow against a disposable Git repository. A separate `codex exec` smoke could not start with the configured account and model.

## Claude Code

Copy the complete `.agents/skills/hibernator/` directory from the checkout to `.claude/skills/hibernator/` in a trusted workspace, or `~/.claude/skills/hibernator/` for your user. Start Claude Code where it can reach the installed CLI. Use the prompt below to specify the repository and output scope. Hibernator invocation in Claude Code has not been verified. [Claude Code skills documentation](https://code.claude.com/docs/en/skills)

## Gemini CLI

Gemini CLI documents `.agents/skills/` as a workspace discovery location. Open the trusted Hibernator checkout or install the skill into a trusted workspace:

```sh
gemini skills install https://github.com/YellankiKaushik/Hibernator-Skill --path .agents/skills/hibernator --scope workspace
gemini skills list
```

Run `/skills reload` in an interactive session after installation, or start a new session. Hibernator invocation in Gemini CLI has not been verified. [Gemini CLI skills documentation](https://geminicli.com/docs/cli/skills/)

## Google Antigravity

Open the trusted checkout and check the host's skill listing for the workspace skill under `.agents/skills/hibernator/`. Google also documents a user skill location under `~/.gemini/config/skills/hibernator/`. Start a new session after manual installation or use the host's documented reload action. Hibernator invocation in Antigravity has not been verified. [Antigravity skills documentation](https://antigravity.google/docs/skills)

## Cursor

Use a local Agent session in the trusted checkout. Cursor documents `.agents/skills/` and `.cursor/skills/` as project discovery locations. Start a new session and check the skill listing. Hibernator invocation in Cursor has not been verified. [Cursor Agent Skills documentation](https://cursor.com/docs/skills)

## Other agents

The CLI works independently of Skill discovery. Install it in the agent's local terminal environment and use the prompt below. Remote or cloud agent sessions can only inspect files available to their own runtime. A README and a Skill file do not grant access to files or commands.

## Copy-and-paste prompt for any terminal-capable coding agent

```text
Help me preview one inactive Git project with Hibernator.

Ask for or confirm the exact local Git repository root and an existing private
output folder outside that repository. If Hibernator is missing, help me install
the CLI from its trusted source in a separate environment. Confirm Git and local
terminal access. Run Hibernator's doctor check before inspecting the project.

Record Git status before the preview. Run a read-only scan, then explain KEEP,
REGENERABLE, REVIEW, and BLOCKED in plain English with the reasons and any
ambiguous or incomplete results. Keep source code, sensitive files, and local
changes intact. Do not open or reveal secret values.

Create a reviewable plan outside the repository. Summarize its candidates,
protected and review items, and estimated logical bytes as file sizes. Show
restoration guidance using dry-run only. Compare Git status afterward and
report what preservation checks established. Keep raw output, paths, and notes
private, and report errors, skipped checks, and limitations honestly.

Never run production apply, approve deletion, run an installer in the project,
or use shell, Git, or other commands as a substitute for deletion.
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The skill is missing | Confirm the complete `hibernator/SKILL.md` folder is under a discovery directory supported by that host. Restart the session or paste the prompt. |
| The agent finds the skill but cannot run Hibernator | Run the doctor check with Python from the CLI installation environment. The wheel includes the Skill file but does not register it with a host. |
| The agent cannot reach your project | Check that the agent runs locally, can read the exact Git root, and can write to the separate output folder. |
| The scan or plan reports an error | Ask for the exact failing step and what it could verify. Use [CLI troubleshooting](../README.md#troubleshooting-and-uninstall) or the [hands-on test guide](USER_TESTING.md). |
