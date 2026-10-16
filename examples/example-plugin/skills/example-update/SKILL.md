---
name: example-update
description: Example step 4 of 4. Updates req-tracker coverage for the passing test, opens the merge request and commits example.data (mock). Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# example-update (step 4 of 4: update trackers)

## Setup
Read `example.data/config.yaml` and `example.data/project-prompt.md` in the project root and follow the project prompt throughout.

Read `example.data/work/plan.md` and `example.data/work/result.json`. If either is missing, or `test_after` is not `passed`, stop and tell the user to run `example-execute` first. Check that the current branch is `result.branch` and its latest commit is `result.commit`.

## User gate
Before calling any tool, list the calls you will make (coverage updates, merge request) and ask the user to confirm. Do not continue on a "no".

## Operation
1. **Update req-tracker.** For each related requirement, as in the plan: `update_coverage` if a coverage record exists, otherwise `create_coverage`. Mock: acknowledged, no effect, so `req-tracker.json` stays unchanged until the next fetch.

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/req-tracker/server.py" update_coverage '{"id":"<coverage-id>","result":"passed","testcases":["<test-id>"]}'
python "${CLAUDE_PLUGIN_ROOT}/mcp/req-tracker/server.py" create_coverage '{"requirement_id":"<req-id>","result":"passed","testcases":["<test-id>"]}'
```

2. **Merge request** (mock, acknowledged, no effect):

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/dev-status/server.py" create_merge_request '{"title":"<title>","source_branch":"<branch>","target_branch":"dev","closes":[<iid>]}'
```

3. **Record and commit example.data.** The sequence is complete, so record the step and commit the `example.data` changes from steps 1 to 4 (the scratch folder `work/` is ignored). No push.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/example_data.py" record-step example-update
git add example.data
git commit -m "chore: record example run"
```

## Summary
Report in a few lines: the issue, requirements, test results (before and after), branch, commit hashes (fix and example.data), and the two acknowledgements (coverage, MR). The branch is ready for the user to push.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
