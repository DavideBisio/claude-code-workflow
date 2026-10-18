---
name: git-dev-execute
description: Workflow step 3 of 4. Executes the approved plan on a new branch (failing test, fix, passing test) and commits. Asks for confirmation first, then summarizes.
disable-model-invocation: false
---

# git-dev-execute (step 3 of 4: execute)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get target
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get plan
```
If either returns an `error`, stop and tell the user to run `git-dev-target` and `git-dev-plan` first.

Check git: the current branch must be `plan.source_branch` (default `dev` if the plan predates this
field), and the working tree must be clean. Otherwise stop and report; never stash or discard.

Resolve the test command once, before running anything:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" prompt-section "Test commands"
```
If `text` is not `null`, use the command(s) it names for steps 2 and 4 below. If it is `null`, ask
the user for the test command rather than guessing.

## User gate
If this run was invoked in auto mode with `git-dev-execute` excluded from `auto.gates`, skip this
confirmation — state what you're about to do and proceed directly. Otherwise: before changing
anything, state what will happen (dispatch to the executor agent: create the branch, write the
test, change code, commit) and ask the user to confirm. Do not continue on a "no".

## Operation
Dispatch the whole test-first/fix/test-after/commit loop to the `workflow:executor` agent (via the
Agent tool, `subagent_type: "workflow:executor"`), rather than doing it inline in this session —
this is the heaviest, most context-hungry step, and the agent's own file keeps it from re-asking
for confirmation or re-discovering what's already been resolved. Give it:
- the branch name, `source_branch`, and `target_branch` from the plan
- the test spec and fix spec from the plan
- the resolved test command from Setup (or, if that was `null`, whatever you asked the user for)

The agent creates the branch, writes the failing test, confirms it fails, makes the fix, confirms
the test passes (retrying the fix at most 3 times), and commits the fix and test only (not
`git-dev.data/`) with the plan's commit message. It does not push. If the agent reports it
couldn't get the test to pass after 3 tries, or that the test passed before any fix, stop and
report that — don't retry the whole dispatch yourself.

## Output
Validate the agent's report has the required keys, then write it (you write the handoff, not the
agent): `{"branch", "commit", "test_id", "test_before", "test_after"}`, e.g.
`{"branch": "...", "commit": "...", "test_id": "...", "test_before": "failed", "test_after": "passed"}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" write result '<json above>'
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-execute
```

## Summary
Report in a few lines: branch, commit hash, files changed, test result before and after, and that the next step is `git-dev-update`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches.
