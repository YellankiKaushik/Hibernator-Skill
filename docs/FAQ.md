# Frequently asked questions

## Does Hibernator delete files today?

No. The CLI can scan, classify, create plans, display reports, and show restore guidance. `apply` records whether approval was unavailable, declined, or exact, but production deletion remains disabled on every platform pending independent filesystem security review.

## Does an ignored or generated-looking folder become removable automatically?

No. Ignore status and names such as `build`, `cache`, `.venv`, or `node_modules` are not enough. Rules require relevant project evidence and preserve candidates containing tracked data, secrets, links, local data, unknown content, or unreadable entries.

## Are the byte counts guaranteed storage savings?

No. File lengths are logical estimates. The cleanup report keeps candidate bytes, removed logical bytes, remaining project bytes, and observed volume free-space delta separate. A free-space delta is advisory and is not attributed solely to Hibernator.

## Will restore preview reinstall dependencies?

No. `restore --dry-run` only prints suggestions. A developer may later run a package manager manually after reviewing the commands; package managers can use the network and execute lifecycle scripts.

## Does scanning work offline?

The CLI scan, plan, report, and restore preview make no network calls. Installing the package may require setuptools from a local cache or package index. A checkout can be used with `PYTHONPATH=src` and `python -m hibernator` without a package install.

## Which agents discover the skill?

The canonical `.agents/skills/hibernator/SKILL.md` is included and validated for its metadata and policy. Actual discovery has not been tested in Codex, Gemini CLI, or Antigravity in this environment. Use the standalone CLI when native discovery is unavailable.

## Can I use this on a Colab notebook to clean my laptop?

No. Colab can only access files mounted into that runtime. It cannot reclaim space from a laptop filesystem it cannot access.
