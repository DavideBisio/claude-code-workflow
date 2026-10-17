---
name: git-dev-update
description: Workflow step 4 of 4. Updates requirement-tracker coverage for the passing test, opens the merge request and commits git-dev.data (mock). Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# git-dev-update (step 4 of 4: update trackers)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get plan
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get result
```
If either returns an `error`, or `result.test_after` is not `passed`, stop and tell the user to run `git-dev-execute` first. Check that the current branch is `result.branch` and its latest commit is `result.commit`.

## User gate
Before calling any tool, list the calls you will make (coverage updates, merge request) and ask the user to confirm. Do not continue on a "no".

## Operation
First resolve which providers are active (prints the provider dir name, e.g. `mock-req-tracker` or `github-req-tracker`):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" provider req_tracker
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" provider version_control
```

Use the printed `dir` value in place of `<req-tracker-provider>` / `<version-control-provider>` below.

1. **Update the requirement tracker.** For each related requirement, as in the plan: `update_coverage` if a coverage record exists, otherwise `create_coverage`.
   - Mock provider: acknowledged, no effect; `req-tracker.json` stays unchanged until the next fetch.
   - A `github-*` provider: this is a **real** action — it opens or closes/comments on a real GitHub issue. Say so plainly in the user gate above, not just "update the tracker".

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/<req-tracker-provider>/server.py" update_coverage '{"id":"<coverage-id>","result":"passed","testcases":["<test-id>"]}'
python "${CLAUDE_PLUGIN_ROOT}/mcp/<req-tracker-provider>/server.py" create_coverage '{"requirement_id":"<req-id>","result":"passed","testcases":["<test-id>"]}'
```

2. **Merge request.**
   - Mock provider: acknowledged, no effect.
   - A `github-*` provider: opens a **real** pull request on the real repo. Say so plainly in the user gate above.

```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/<version-control-provider>/server.py" create_merge_request '{"title":"<title>","source_branch":"<branch>","target_branch":"dev","closes":[<iid>]}'
```

3. **Record the step.** The sequence is complete. `git-dev.data/` is entirely gitignored except `config.yaml`/`project-prompt.md`, neither of which this workflow touches, so there is nothing of its own to commit.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-update
```

## Summary
Report in a few lines: the issue, requirements, test results (before and after), branch, fix commit hash, and the two acknowledgements (coverage, MR). The branch is ready for the user to push.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
