# Hibernator hands-on testing

Install the CLI separately in a trusted Hibernator environment. See [installation and updates](../README.md#installation) and the [Agent Skill setup](AGENTS.md). Hibernator 0.2.0 provides the retirement workflow.

## Start with the synthetic example

From the Hibernator checkout with `PYTHONPATH=src` or an installed package, run `python -m unittest -v tests.test_retirement`. These tests create their own disposable Git projects. They check paired outputs and byte totals, dirty Git, protected data, and prompt-free apply refusal.

## Owner read-only acceptance

1. Select an inactive local Git repository you own. Close active builds and development servers. Open a local terminal or a local coding-agent workspace for that project.
2. Run `hibernator retire --project "PATH_TO_EXACT_GIT_ROOT"`. To choose a private directory you already created outside the project and its ancestors, add `--output "PRIVATE_DIRECTORY"`. Use `python -m hibernator` in the tool's environment if needed.
3. Open the Markdown in the reported run directory. Compare the offered exact paths, logical bytes and recovery hints against your expectations. Keep the JSON and completion record private alongside the Markdown.
4. Check that source, local changes, unique files and unknown items stay protected. Stop after reviewing the report. Any later file-manager decision belongs to you.
5. If you separately want a read-only follow-up, run `hibernator verify --report "PRIVATE_RETIREMENT_JSON"`. Its observations only describe the listed paths at verification time.

Use the [universal agent request](../README.md#copy-paste-prompt) if you prefer an agent. A plain cloud chat cannot inspect your laptop's filesystem.

## Feedback template

- Operating system, filesystem, Python, Git and Hibernator versions
- Time to report and project type
- Expected versus observed decisions and byte totals
- Preserved material, warning or unexpected behavior
- Minimal synthetic reproduction with private paths and values removed
