# Usage examples

All examples below are illustrative and use synthetic project descriptions. Production cleanup is disabled in this release candidate.

## Python project

For a repository with `pyproject.toml` and a local `.venv`, scan and review a plan:

```text
python -m hibernator scan --project /work/my-python-app
python -m hibernator plan --project /work/my-python-app
python -m hibernator restore --project /work/my-python-app --dry-run
```

The environment may be classified as regenerable when project evidence is present. Tracked files, local databases, `.env` files, uploads, model weights, and unknown contents remain protected or under review.

## React or Next.js project

For a React project with `package.json`, `package-lock.json`, and `node_modules`, Hibernator can identify the dependency directory for review and show `npm ci` as a restoration suggestion. A recognized `.next/cache` is considered only with Next.js evidence. Multiple lockfiles require a human package-manager choice.

```text
hibernator scan --project C:\work\portfolio-site
hibernator plan --project C:\work\portfolio-site --exclude node_modules
```

## Hackathon project

Repositories often contain generated dependencies next to downloaded datasets, demos, recordings, and local databases. Hibernator keeps unknown files visible for review and does not treat Git ignore rules as proof that content can be discarded.

```text
hibernator scan --project /work/hackathon-demo --format json
hibernator plan --project /work/hackathon-demo
```

## Portfolio codebase

Use a plan to inspect eligible paths and their reasons before taking any action. In this preview-only build, `apply` records the approval/refusal workflow but does not delete files, even after exact interactive confirmation.

```text
hibernator plan --project /work/portfolio
hibernator report --file /path/to/a/saved/report.json
hibernator restore --project /work/portfolio --dry-run
```
