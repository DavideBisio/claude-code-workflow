---
name: example-execute
description: Example step 3 of 4. Executes the approved plan on a new branch (failing test, fix, passing test) and commits. Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# example-execute (step 3 of 4: execute)

## Setup
Read `example.data/config.yaml` and `example.data/project-prompt.md` in the project root and follow the project prompt throughout.

Read `example.data/work/plan.md` and `example.data/work/target.json`. If either is missing, stop and tell the user to run `example-target` and `example-plan` first.

Check git: the current branch must be `dev`, and the working tree must be clean except for changes under `example.data/` (earlier steps record dates there). Otherwise stop and report; never stash or discard.

## User gate
Before changing anything, state what will happen (create the branch, write the test, change code, commit) and ask the user to confirm. Do not continue on a "no".

## Operation
1. `git switch -c <branch from the plan>`; the `example.data/` changes come along.
2. **Test first (mock).** Write the test from the plan. Run it and confirm it fails. If it passes already, stop and report.
3. **Fix (mock).** Make the planned change.
4. **Test after the fix (mock).** It must pass. If it fails, go back to 3 (at most 3 tries), then stop and report.
5. **Commit** the fix and the test only (add them by path, not `example.data/`), message as planned. Do not push.

## Output
Write `example.data/work/result.json` (scratch folder, gitignored):
`{"branch": "...", "commit": "...", "test_id": "...", "test_before": "failed", "test_after": "passed"}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/example_data.py" record-step example-execute
```

## Summary
Report in a few lines: branch, commit hash, files changed, test result before and after, and that the next step is `example-update`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
