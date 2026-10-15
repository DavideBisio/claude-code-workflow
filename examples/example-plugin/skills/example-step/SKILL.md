---
name: example-step
description: Example step. Takes the first opened issue, writes a failing test, solves the issue on a new branch, confirms the test passes, commits, updates req-tracker coverage and opens a merge request (mock).
disable-model-invocation: false
---

# example-step

## Setup
Read `example.data/config.yaml` and `example.data/project-prompt.md` in the project root and follow the project prompt throughout.

Source of truth is `example.data/tracker/req-tracker.json`. Issues come from `example.data/tracker/dev-status.json`. If either file is missing, stop and tell the user to run `example-run` first. The current branch must be `dev` with a clean tree; otherwise stop and report.

## Procedure
1. **Pick the issue.** Take the first issue with `state: opened` in `dev-status.json`. Its `requirements` field lists the requirement ids; look them up in `req-tracker.json`. Where the issue text and the requirements disagree, the requirements win; say so. If there is no opened issue, or it has no requirements, stop.
2. **New branch.** `git switch -c fix/<issue-iid>-<slug>` from `dev`.
3. **Develop the test first (mock).** Placeholder: write a test that checks the requirements' acceptance criteria. Run it before any fix and confirm it fails. If it passes already, stop and report.
4. **Solve the issue (mock).** Placeholder: make a small change that addresses the issue, e.g. add a note file.
5. **Run the test after the fix (mock).** It must pass. If it fails, go back to step 4 (at most 3 tries), then stop and report.
6. **Commit the fix.** One commit with the fix and the test; message references the issue (`Refs #<iid>`) and the requirement ids. Do not push.
7. **Update req-tracker for the passing test.** For each related requirement, find its record in `coverage` (`requirement_id`). Use `update_coverage` if it exists, otherwise `create_coverage` with `requirement_id`. Test ids are the existing `testcases` plus the new test (mock id, e.g. `TC-<next>`). Mock: acknowledged, no effect, so `req-tracker.json` stays unchanged until the next fetch.

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/req-tracker/server.py" update_coverage '{"id":"<coverage-id>","result":"passed","testcases":["<test-id>"]}'
python "${CLAUDE_PLUGIN_ROOT}/mcp/req-tracker/server.py" create_coverage '{"requirement_id":"<req-id>","result":"passed","testcases":["<test-id>"]}'
```

8. **Merge request.** Create it with the mock tool (acknowledged, no effect):

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/dev-status/server.py" create_merge_request '{"title":"<title>","source_branch":"<branch>","target_branch":"dev","closes":[<iid>]}'
```

9. **Record and commit example.data.** Record the completion date, then commit the `example.data` changes made by this step (no push):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/example_data.py" record-step example-step
git add example.data
git commit -m "chore: record example-step run"
```

Report the issue, requirements, test results (before and after), branch, commit hashes and the two acknowledgements (coverage, MR).

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
