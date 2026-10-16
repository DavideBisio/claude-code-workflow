---
name: git-dev-target
description: Workflow step 1 of 4. Reads the existing tracker files, picks the first opened issue, gathers its requirements and identifies the target. Asks for confirmation, then summarizes.
disable-model-invocation: false
---

# git-dev-target (step 1 of 4: target)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Work only from the existing files; do not fetch (that is `git-dev-run`'s job). Source of truth is `git-dev.data/tracker/req-tracker.json`; issues come from `git-dev.data/tracker/version-control.json`. If either is missing, stop and tell the user to run `git-dev-run` first.

If `backends.req_tracker` is `github_labels` (check `config.yaml`): there is no separate `issues` vs `requirements` concept — the requirement issues themselves are the target. Pick the first opened requirement directly from `req-tracker.json` instead of step 1 below, and treat its own linked `coverage`/`specifications` entries as the lookup in step 1.

## Operation
1. Take the first issue with `state: opened` in `version-control.json`. Its `requirements` field lists requirement ids; look them up in `req-tracker.json`, together with their `coverage` records, `specifications` and any `testplans` that mention their test cases.
2. Where the issue text and the requirements disagree, the requirements win; say so. If there is no opened issue, or it has no requirements, stop and report.
3. Identify the target: issue (iid, title), requirements (id, title, status), current coverage result and test cases per requirement, and the code area likely affected (mock: a one-line guess).

## User gate
Before writing anything, show the identified target and ask the user to confirm it or name a different issue. Do not continue on a "no".

## Output
Write the confirmed target to `git-dev.data/work/target.json` (scratch folder, gitignored):
`{"issue": {...}, "requirements": [...], "coverage": [...], "code_area": "..."}`.

Record the step, with no commit:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" record-step git-dev-target
```

## Summary
Report in a few lines: the issue, its requirements and their coverage state, conflicts or open questions, and that the next step is `git-dev-plan`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Read-only on git; never push.
