---
name: git-dev-execute
description: Workflow step 3 of 4. Executes the approved plan on a new branch (failing test, fix, passing test) and commits. Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# git-dev-execute (step 3 of 4: execute)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Read `git-dev.data/work/plan.md` and `git-dev.data/work/target.json`. If either is missing, stop and tell the user to run `git-dev-target` and `git-dev-plan` first.

Check git: the current branch must be `dev`, and the working tree must be clean except for changes under `git-dev.data/` (earlier steps record dates there). Otherwise stop and report; never stash or discard.

## User gate
Before changing anything, state what will happen (create the branch, write the test, change code, commit) and ask the user to confirm. Do not continue on a "no".

## Operation
1. `git switch -c <branch from the plan>`; the `git-dev.data/` changes come along.
2. **Test first (mock).** Write the test from the plan. Run it and confirm it fails. If it passes already, stop and report.
3. **Fix (mock).** Make the planned change.
4. **Test after the fix (mock).** It must pass. If it fails, go back to 3 (at most 3 tries), then stop and report.
5. **Commit** the fix and the test only (add them by path, not `git-dev.data/`), message as planned. Do not push.

## Output
Write `git-dev.data/work/result.json` (scratch folder, gitignored):
`{"branch": "...", "commit": "...", "test_id": "...", "test_before": "failed", "test_after": "passed"}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" record-step git-dev-execute
```

## Summary
Report in a few lines: branch, commit hash, files changed, test result before and after, and that the next step is `git-dev-update`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
