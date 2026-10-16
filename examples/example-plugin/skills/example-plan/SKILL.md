---
name: example-plan
description: Example step 2 of 4. Plans the execution for the confirmed target (test first, fix, commit, tracker updates). Asks for approval, then summarizes.
disable-model-invocation: false
---

# example-plan (step 2 of 4: plan)

## Setup
Read `example.data/config.yaml` and `example.data/project-prompt.md` in the project root and follow the project prompt throughout.

Read `example.data/work/target.json`. If it is missing, stop and tell the user to run `example-target` first.

## Operation
Draft a plan; change nothing in the repository yet.
1. **Branch**: `fix/<issue-iid>-<slug>`, created from `dev`.
2. **Test first (mock)**: what the test checks (the requirements' acceptance criteria), where it goes, its test id (mock, e.g. `TC-<next>`). It must fail before the fix.
3. **Fix (mock)**: the intended change, kept small.
4. **Verification**: the test must pass after the fix (at most 3 tries).
5. **Commit**: one commit with fix and test, message referencing `Refs #<iid>` and the requirement ids. No push.
6. **Tracker updates** (for `example-update`): per requirement, `update_coverage` if a coverage record exists, otherwise `create_coverage`, with the test ids; plus the merge request title, source branch and target `dev`.
7. Risks and open questions.

## User gate
Show the plan and ask the user to approve it, edit it, or stop. Do not continue on a "no".

## Output
Write the approved plan to `example.data/work/plan.md` (scratch folder, gitignored).

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/example_data.py" record-step example-plan
```

## Summary
Report in a few lines: branch name, test, intended fix, tracker updates planned, and that the next step is `example-execute`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- No repository changes, no push.
