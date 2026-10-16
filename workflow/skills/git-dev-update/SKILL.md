---
name: git-dev-update
description: Workflow step 4 of 4. Updates requirement-tracker coverage for the passing test, opens the merge request and commits git-dev.data (mock). Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# git-dev-update (step 4 of 4: update trackers)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Read `git-dev.data/work/plan.md` and `git-dev.data/work/result.json`. If either is missing, or `test_after` is not `passed`, stop and tell the user to run `git-dev-execute` first. Check that the current branch is `result.branch` and its latest commit is `result.commit`.

## User gate
Before calling any tool, list the calls you will make (coverage updates, merge request) and ask the user to confirm. Do not continue on a "no".

## Operation
1. **Update the requirement tracker.** For each related requirement, as in the plan: `update_coverage` if a coverage record exists, otherwise `create_coverage`. Mock: acknowledged, no effect, so `mock-req-tracker.json` stays unchanged until the next fetch.

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/mock-req-tracker/server.py" update_coverage '{"id":"<coverage-id>","result":"passed","testcases":["<test-id>"]}'
python "${CLAUDE_PLUGIN_ROOT}/mcp/mock-req-tracker/server.py" create_coverage '{"requirement_id":"<req-id>","result":"passed","testcases":["<test-id>"]}'
```

2. **Merge request** (mock, acknowledged, no effect):

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/mock-version-control/server.py" create_merge_request '{"title":"<title>","source_branch":"<branch>","target_branch":"dev","closes":[<iid>]}'
```

3. **Record and commit git-dev.data.** The sequence is complete, so record the step and commit the `git-dev.data` changes from steps 1 to 4 (the scratch folder `work/` is ignored). No push.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" record-step git-dev-update
git add git-dev.data
git commit -m "chore: record git-dev run"
```

## Summary
Report in a few lines: the issue, requirements, test results (before and after), branch, commit hashes (fix and git-dev.data), and the two acknowledgements (coverage, MR). The branch is ready for the user to push.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
