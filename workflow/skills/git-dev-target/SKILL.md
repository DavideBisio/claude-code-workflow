---
name: git-dev-target
description: Workflow step 1 of 4. Reads the existing tracker files, picks the first opened issue, gathers its requirements and identifies the target. Asks for confirmation, then summarizes.
disable-model-invocation: false
---

# git-dev-target (step 1 of 4: target)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Work only from the existing tracker files to pick *which* issue; do not fetch them yourself (that
is `git-dev-run`'s job). The issue list comes from `git-dev.data/tracker/version-control.json`. If
it is missing, stop and tell the user to run `git-dev-run` first.

If `backends.req_tracker` is `github_labels` (check `config.yaml`): there is no separate `issues`
vs `requirements` concept — the requirement issues themselves are the target. Pick the first opened
requirement directly from `git-dev.data/tracker/req-tracker.json` instead of step 1 below.

## Operation
1. Take the first issue with `state: opened` in `version-control.json` (its iid).
2. Scope the detail for that one issue only, instead of reading the full req-tracker dump:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" fetch --issue <iid>
```
This calls the req-tracker/version-control providers with an exact-match `filter`, returning just
that issue plus the requirements it references, their `coverage` records and `specifications` —
not every requirement in the tracker.
3. Where the issue text and the requirements disagree, the requirements win; say so. If there is no
   opened issue, or it has no requirements, stop and report.
4. Identify the target: issue (iid, title), requirements (id, title, status), current coverage
   result and test cases per requirement, and the code area likely affected (mock: a one-line guess).

## User gate
Before writing anything, show the identified target and ask the user to confirm it or name a different issue. Do not continue on a "no".

## Output
Write the confirmed target (validated against its required fields):
`{"issue": {...}, "requirements": [...], "coverage": [...], "code_area": "..."}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" write target '<json above>'
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-target
```

## Summary
Report in a few lines: the issue, its requirements and their coverage state, conflicts or open questions, and that the next step is `git-dev-plan`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Read-only on git; never push.
