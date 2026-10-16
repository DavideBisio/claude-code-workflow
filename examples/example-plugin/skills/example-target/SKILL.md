---
name: example-target
description: Example step 1 of 4. Reads the existing tracker files, picks the first opened issue, gathers its requirements and identifies the target. Asks for confirmation, then summarizes.
disable-model-invocation: false
---

# example-target (step 1 of 4: target)

## Setup
Read `example.data/config.yaml` and `example.data/project-prompt.md` in the project root and follow the project prompt throughout.

Work only from the existing files; do not fetch (that is `example-run`'s job). Source of truth is `example.data/tracker/req-tracker.json`; issues come from `example.data/tracker/dev-status.json`. If either is missing, stop and tell the user to run `example-run` first.

## Operation
1. Take the first issue with `state: opened` in `dev-status.json`. Its `requirements` field lists requirement ids; look them up in `req-tracker.json`, together with their `coverage` records, `specifications` and any `testplans` that mention their test cases.
2. Where the issue text and the requirements disagree, the requirements win; say so. If there is no opened issue, or it has no requirements, stop and report.
3. Identify the target: issue (iid, title), requirements (id, title, status), current coverage result and test cases per requirement, and the code area likely affected (mock: a one-line guess).

## User gate
Before writing anything, show the identified target and ask the user to confirm it or name a different issue. Do not continue on a "no".

## Output
Write the confirmed target to `example.data/work/target.json` (scratch folder, gitignored):
`{"issue": {...}, "requirements": [...], "coverage": [...], "code_area": "..."}`.

Record the step, with no commit:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/example_data.py" record-step example-target
```

## Summary
Report in a few lines: the issue, its requirements and their coverage state, conflicts or open questions, and that the next step is `example-plan`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Read-only on git; never push.
