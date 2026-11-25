# Usage examples

## Mixed local Git project

```text
hibernator retire --project "/work/inactive-project" --output "/private/hibernator-results"
```

Create the private output directory separately. Read the Markdown report for exact paths, preservation evidence, recovery inputs and owner checklist. The JSON stores the bound local root for separate verification.

## Prioritize larger paths

```text
python -m hibernator retire --project "/work/inactive-project" --min-size-mib 64 --exclude apps/demo/node_modules --format json
```

An exclusion must match an eligible path in your actual project. The detailed report records filtered paths as preserved.

## Observe changes later

```text
hibernator verify --report "/private/hibernator-results/retirement-RUN_ID/retirement.json"
```

Verification observes the listed path entries and Git index/HEAD metadata. A missing observation establishes absence at that time. Recovery hints are for owner review. For independent suggestions, run `hibernator restore --project PATH --dry-run`.
