# Hibernator hands-on preview test

Start with a **new synthetic Git project** in your temporary directory. Use only the generated project for the approval and staleness exercises. After that, Windows users can follow [step 9](#9-scan-a-real-repository-from-windows-powershell) to scan, plan, and preview restoration on an existing repository.

## 1. Verify installation

On Windows, open PowerShell and run these commands from a folder where you keep tools. Install [Python 3.10 or later](https://www.python.org/downloads/windows/) and [Git for Windows](https://git-scm.com/download/win) first if either version check fails. If you already have a current checkout, skip the clone and change to that checkout instead.

```powershell
git --version
py -3 --version
git clone https://github.com/YellankiKaushik/Hibernator-Skill.git
Set-Location Hibernator-Skill
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install .
if ($LASTEXITCODE -ne 0) { throw 'Hibernator installation failed.' }
$hibernatorPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
function hibernator { & $hibernatorPython -m hibernator @args }
```

If you have `python` on PATH but no `py` launcher, use `python --version` and `python -m venv .venv`. The function above keeps the installed command available in the current PowerShell window without requiring virtual environment activation. The install may download a build dependency. The preview commands below work offline.

On Linux or macOS, follow the [installation instructions](../README.md#installation) first. In the same terminal, verify the installed command:

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
[IO.File]::WriteAllText("$sample\package.json", '{"name":"hibernator-uat-sample","private":true,"scripts":{"test":"node src/app.js"}}')
[IO.File]::WriteAllText("$sample\package-lock.json", '{"name":"hibernator-uat-sample","lockfileVersion":3,"packages":{}}')
[IO.File]::WriteAllText("$sample\src\app.js", 'console.log("synthetic source");')
[IO.File]::WriteAllText("$sample\node_modules\demo-package\index.js", '// synthetic dependency')
[IO.File]::WriteAllText("$sample\.env.local", 'TOKEN=synthetic-placeholder')
[IO.File]::WriteAllText("$sample\local-notes.txt", 'synthetic untracked local note')
[IO.File]::WriteAllText($sentinel, 'outside sentinel must remain unchanged')
git -C $sample init -q
git -C $sample config user.name "Hibernator UAT"
git -C $sample config user.email "hibernator-uat@example.invalid"
git -C $sample add package.json package-lock.json src/app.js
git -C $sample commit -qm "Create synthetic UAT project"
Get-FileHash "$sample\src\app.js", "$sample\package.json", "$sample\package-lock.json",
    "$sample\node_modules\demo-package\index.js", "$sample\.env.local", "$sample\local-notes.txt", $sentinel
$sample
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
[IO.File]::WriteAllText("$sample\node_modules\demo-package\added-after-plan.js", 'synthetic new file')
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

Expected: apply rejects the stale plan (exit code `4`) and changes no files. The new synthetic file must still exist. Create a fresh plan before continuing. The file added in this step is an intentional change. Run `git status --short` again and use that output as the baseline for the remaining preservation checks.

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

## 9. Scan a real repository from Windows PowerShell

Run this after the disposable exercise. Choose an existing local Git repository that you own and leave editors, watchers, and other Git commands idle during the comparison. Use only the three preview commands shown here. Keep all output private because plans contain the exact project root and reports can still show relative file names.

Replace the example path with your own. Run these blocks in the PowerShell window where you installed the `hibernator` function. First resolve the repository root and prepare an evidence folder outside it:

```powershell
$projectPath = 'C:\work\My Project'
$target = git --no-optional-locks -C $projectPath rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw 'Choose an existing Git working tree.' }
$target = [IO.Path]::GetFullPath($target)
$evidenceName = 'hibernator-uat-' + [guid]::NewGuid().ToString('N')
$evidence = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA $evidenceName))
$targetPrefix = $target.TrimEnd('\', '/') + '\'
if ($evidence.Equals($target, [StringComparison]::OrdinalIgnoreCase) -or
    $evidence.StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose an evidence folder outside the repository.'
}
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop | Out-Null

function Get-HibernatorGitStatus {
    $lines = git --no-optional-locks -C $target status --porcelain=v1 --untracked-files=all
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git status.' }
    return ($lines -join [Environment]::NewLine)
}
$before = Get-HibernatorGitStatus
[IO.File]::WriteAllText((Join-Path $evidence 'git-before.txt'), [string]$before)
```

Next run the previews and save their JSON. The exit checks stop the walkthrough if a preview fails. A restore exit code of `3` means Hibernator could not offer supported restoration steps.

```powershell
hibernator scan --project $target --format json |
    Out-File -FilePath (Join-Path $evidence 'scan.json') -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw 'Review scan.json before continuing.' }

$planPath = Join-Path $evidence 'plan.json'
hibernator plan --project $target --output $planPath --format json |
    Out-File -FilePath (Join-Path $evidence 'plan-output.json') -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw 'Review plan-output.json before continuing.' }

hibernator restore --project $target --dry-run --format json |
    Out-File -FilePath (Join-Path $evidence 'restore.json') -Encoding UTF8
$restoreExit = $LASTEXITCODE
if ($restoreExit -ne 0 -and $restoreExit -ne 3) { throw 'Review restore.json.' }

$after = Get-HibernatorGitStatus
[IO.File]::WriteAllText((Join-Path $evidence 'git-after.txt'), [string]$after)
if ($before -ceq $after) {
    'Git status is identical before and after.'
} else {
    'Git status changed. Inspect both status files and check for concurrent activity.'
}
$evidence
```

An empty status file represents a clean working tree. Matching status shows that the reported tracked and untracked Git status stayed the same. It does not compare ignored file contents. The disposable fixture's hashes provide a separate content check for the files you selected.

Open `scan.json`, `plan.json`, and `restore.json` from the printed folder:

- `KEEP` means Hibernator classified the path for preservation. `REVIEW` means there is insufficient regeneration evidence or the path needs human interpretation. `BLOCKED` means a preservation or inspection rule prevented selection. `REGENERABLE` means a rule found sufficient evidence to propose the path as a candidate.
- In `plan.json`, check `root`, `candidates`, `review_items`, `estimated_logical_bytes`, and `digest`. A plan can validly have zero candidates. Logical bytes describe the candidate contents. Production deletion is disabled.
- In `restore.json`, read the suggested commands and warnings. Leave them as suggestions for this test. The dry run never invokes an installer.

Record your observations in a private `feedback.txt` in the same folder. Before sharing feedback, review it and remove local paths, private file names, and project details.
