# Hibernator hands-on preview test

This guide uses a **new synthetic Git project under your operating system's temporary directory**. Do not substitute a real project. The current preview cannot delete real project files; the final exact-approval check below must report `APPROVED_BUT_UNSUPPORTED` and leave the synthetic project's files untouched.

## 1. Verify installation

From the Hibernator checkout, run:

```text
hibernator doctor
hibernator --version
hibernator --help
```

If the command is not found but the package is installed in the active Python, use `python -m hibernator` in place of `hibernator` for the rest of the guide. Record the Python version and whether `doctor` found Git.

## 2. Create a disposable sample Git project

The project contains synthetic Node manifests, a generated-looking dependency, a fake local note, and a fake secret marker. These contents are not real credentials or personal data. The generated files are not removed by this guide.

### Windows PowerShell

```powershell
$sampleHome = Join-Path $env:TEMP ("hibernator-uat-" + [guid]::NewGuid().ToString("N"))
$sample = Join-Path $sampleHome "project"
$sentinel = Join-Path $sampleHome "outside-sentinel.txt"
$planPath = Join-Path $sampleHome "plan.json"
New-Item -ItemType Directory -Path "$sample\src", "$sample\node_modules\demo-package" -Force | Out-Null
Set-Content -Encoding ascii -NoNewline "$sample\package.json" '{"name":"hibernator-uat-sample","private":true,"scripts":{"test":"node src/app.js"}}'
Set-Content -Encoding ascii -NoNewline "$sample\package-lock.json" '{"name":"hibernator-uat-sample","lockfileVersion":3,"packages":{}}'
Set-Content -Encoding ascii -NoNewline "$sample\src\app.js" 'console.log("synthetic source");'
Set-Content -Encoding ascii -NoNewline "$sample\node_modules\demo-package\index.js" '// synthetic dependency'
Set-Content -Encoding ascii -NoNewline "$sample\.env.local" 'TOKEN=synthetic-placeholder'
Set-Content -Encoding ascii -NoNewline "$sample\local-notes.txt" 'synthetic untracked local note'
Set-Content -Encoding ascii -NoNewline $sentinel 'outside sentinel must remain unchanged'
git -C $sample init -q
git -C $sample config user.name "Hibernator UAT"
git -C $sample config user.email "hibernator-uat@example.invalid"
git -C $sample add package.json package-lock.json src/app.js
git -C $sample commit -qm "Create synthetic UAT project"
Get-FileHash "$sample\src\app.js", "$sample\.env.local", "$sample\local-notes.txt", $sentinel
git -C $sample status --short
```

### Linux or macOS shell

```sh
sample_home="$(mktemp -d "${TMPDIR:-/tmp}/hibernator-uat-XXXXXX")"
sample="$sample_home/project"
sentinel="$sample_home/outside-sentinel.txt"
plan_path="$sample_home/plan.json"
mkdir -p "$sample/src" "$sample/node_modules/demo-package"
printf '%s\n' '{"name":"hibernator-uat-sample","private":true,"scripts":{"test":"node src/app.js"}}' > "$sample/package.json"
printf '%s\n' '{"name":"hibernator-uat-sample","lockfileVersion":3,"packages":{}}' > "$sample/package-lock.json"
printf '%s\n' 'console.log("synthetic source");' > "$sample/src/app.js"
printf '%s\n' '// synthetic dependency' > "$sample/node_modules/demo-package/index.js"
printf '%s\n' 'TOKEN=synthetic-placeholder' > "$sample/.env.local"
printf '%s\n' 'synthetic untracked local note' > "$sample/local-notes.txt"
printf '%s\n' 'outside sentinel must remain unchanged' > "$sentinel"
git -C "$sample" init -q
git -C "$sample" config user.name "Hibernator UAT"
git -C "$sample" config user.email "hibernator-uat@example.invalid"
git -C "$sample" add package.json package-lock.json src/app.js
git -C "$sample" commit -qm "Create synthetic UAT project"
sha256sum "$sample/src/app.js" "$sample/.env.local" "$sample/local-notes.txt" "$sentinel"
git -C "$sample" status --short
```

Record the printed sample path and hashes. `package.json`, the lockfile, and source are committed. `node_modules/`, `.env.local`, and `local-notes.txt` are untracked synthetic content.

## 3. Scan and inspect classifications

Run:

```powershell
hibernator scan --project $sample
hibernator scan --project $sample --format json
```

```sh
hibernator scan --project "$sample"
hibernator scan --project "$sample" --format json
```

Expected: Node.js is detected; `node_modules` may be `REGENERABLE`; `src` and tracked manifests are preserved; `.env.local` is `KEEP`; and `local-notes.txt` remains visible as `REVIEW`. Read the exact reason and sizes. Logical bytes are file-length estimates, not promised reclaimed space.

## 4. Create, inspect, and stale a plan

Save the plan outside the project (in the temporary fixture's parent):

```powershell
hibernator plan --project $sample --output $planPath --format json
Get-Content $planPath
Set-Content -Encoding ascii -NoNewline "$sample\node_modules\demo-package\added-after-plan.js" 'synthetic new file'
hibernator apply --plan $planPath
$LASTEXITCODE
Test-Path "$sample\node_modules\demo-package\added-after-plan.js"
```

```sh
hibernator plan --project "$sample" --output "$plan_path" --format json
cat "$plan_path"
printf '%s\n' 'synthetic new file' > "$sample/node_modules/demo-package/added-after-plan.js"
hibernator apply --plan "$plan_path"
echo "$?"
test -f "$sample/node_modules/demo-package/added-after-plan.js" && echo "synthetic file remains"
```

Inspect the complete candidate list, target root, and digest in the output and the saved JSON file. Candidate selection should include only paths supported by the report; do not assume every generated-looking file appears.

Expected: apply rejects the stale plan (exit code `4`) and changes no files. The new synthetic file must still exist. Create a fresh plan before continuing.

## 5. Check text and JSON output and saved reports

```powershell
$scan = hibernator scan --project $sample --save-report --format json | ConvertFrom-Json
$scan.saved_report
hibernator report --file $scan.saved_report
hibernator report --file $scan.saved_report --format json
hibernator restore --project $sample --dry-run
hibernator restore --project $sample --dry-run --format json
```

```sh
scan_json="$(hibernator scan --project "$sample" --save-report --format json)"
report_path="$(printf '%s' "$scan_json" | python -c 'import json,sys; print(json.load(sys.stdin)["saved_report"])')"
printf 'Saved scan report: %s\n' "$report_path"
hibernator report --file "$report_path"
hibernator report --file "$report_path" --format json
hibernator restore --project "$sample" --dry-run
hibernator restore --project "$sample" --dry-run --format json
```

The restore preview should suggest the lockfile-matched Node install command. It must not run the package manager, access the network, or modify the sample project.

## 6. Verify exact approval is still refused

Create another fresh plan (`hibernator plan --project $sample --output $planPath` in PowerShell or `hibernator plan --project "$sample" --output "$plan_path"` in Unix) and run `hibernator apply --plan $planPath` from a real interactive terminal. Review the full printed root, candidates, and digest. Type the exact `DELETE <digest>` phrase only for this synthetic test fixture.

Expected: the report status is `APPROVED_BUT_UNSUPPORTED`, the process returns exit code `3`, and the CLI says no files were changed. This exact approval does **not** enable deletion. Load the returned report by its `report_id` with `hibernator report --id ID` if desired.

If you do not want to enter an approval phrase, cancel the prompt; a decline should be reported as `DECLINED`, exit code `5`, with no project changes.

## 7. Verify preservation

Repeat the hash command and `git status --short` shown in step 2. Compare them with the recorded values. Confirm all of the following:

- Tracked source and manifest hashes are unchanged.
- `.env.local`, `local-notes.txt`, and the post-plan synthetic file still exist with unchanged contents.
- The outside sentinel hash is unchanged.
- The Git working tree still shows the same untracked synthetic paths; no tracked source was modified.
- Scan and restore preview did not create files inside the sample project.
- The apply report says `APPROVED_BUT_UNSUPPORTED` or `DECLINED`, never `DELETED`.

After recording results, remove only the generated `hibernator-uat-*` fixture directory if you want to clean up the test. Confirm the exact temporary path first. Do not point a removal command at another project.

## 8. Record expected versus actual behavior

For every step, note the command, expected behavior, actual behavior, pass/fail, OS/Python/Git versions, and any exact skip or error message. Do not paste secrets or unrelated project paths into feedback.

### Feedback template

```text
Hibernator UAT feedback
OS / filesystem:
Python version:
Git version:
Hibernator version / commit:

Step and command:
Expected:
Actual:
Pass / fail:
Relevant output (redact local paths):

Usability (1–5) and notes:
Incorrect or surprising classifications:
Missing features:
Confusing messages:
Performance or scan duration:
Bugs and minimal synthetic reproduction:
Other feedback:
```

## Feedback checklist

- [ ] Installation and `doctor` worked.
- [ ] Scan explanations were understandable and conservative.
- [ ] The plan showed the expected root, digest, candidates, and estimates.
- [ ] A changed candidate invalidated its old plan.
- [ ] Text/JSON reports loaded as expected and did not expose an absolute root by default.
- [ ] Restore preview was useful and did not install anything.
- [ ] Exact approval was refused for production cleanup and all fixture files remained intact.
- [ ] I recorded confusing behavior, missing features, performance, and bugs above.
