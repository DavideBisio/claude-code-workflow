---
name: git-dev-update
description: Workflow step 4 of 4. Updates requirement-tracker coverage for the passing test, pushes the branch (github-* only) and opens the merge request. Asks for confirmation first, then summarizes.
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

## Pre-PR gate check
Before the user gate below, fetch the checklist and check each item off explicitly — don't rely on
having read `project-prompt.md` once at Setup:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" prompt-section "Pre-PR checklist"
```
If `text` is `null`, there's nothing project-specific to check beyond the merge request itself. If
a listed requirement isn't met, say so and ask the user whether to complete it (e.g. make the
commit that bumps a version file) before opening the merge request, rather than opening it first
and fixing it after.

## User gate
This gate is never skipped, even in auto mode and even if `git-dev-run` calls this step
**ungated** or `update` is left out of `auto.gates` — its actions (tracker writes, a real push, a real PR) are exactly the kind of
hard-to-reverse, real-world side effects a human must confirm regardless of how the rest of the
run is configured.

Before calling any tool, list the calls you will make (coverage updates, merge request, and — for
a `github-*` version-control provider — pushing the branch, since a real PR cannot exist without
the branch on the remote) and ask the user to confirm. Do not continue on a "no".

## Operation
First resolve which providers are active (prints `{name, command, tracker_file}`; `name` is e.g. `mock-req-tracker` or `github-req-tracker`, or a custom provider's name from `providers:` in `config.yaml`):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" provider req_tracker
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" provider version_control
```

Run the printed `command` array verbatim, followed by `TOOL '<json>'`, in place of `<req-tracker-provider-command>` / `<version-control-provider-command>` below.

1. **Update the requirement tracker.** For each related requirement, as in the plan: `update_coverage` if a coverage record exists, otherwise `create_coverage`.
   - Mock provider: acknowledged, no effect; `req-tracker.json` stays unchanged until the next fetch.
   - A `github-*` provider: this is a **real** action — it opens or closes/comments on a real GitHub issue. Say so plainly in the user gate above, not just "update the tracker".

```bash
<req-tracker-provider-command> update_coverage '{"id":"<coverage-id>","result":"passed","testcases":["<test-id>"]}'
<req-tracker-provider-command> create_coverage '{"requirement_id":"<req-id>","result":"passed","testcases":["<test-id>"]}'
```

2. **Merge request, targeting `plan.target_branch`.** The branch was cut from `plan.source_branch`
   (see `git-dev-plan`/`git-dev-execute`; both default to `dev` if the plan predates these fields),
   but the PR itself targets `plan.target_branch` (default `main`), not the source branch — the
   source branch is only the branch-cut source, kept in sync *from* the target branch after each
   merge, not something PRs land on directly. Targeting the source branch here means GitHub's
   `Closes #N` keyword never fires, since it only auto-closes on a default-branch merge — found the
   hard way in issue #25.
   - Mock provider: acknowledged, no effect.
   - A `github-*` provider: this needs the branch on the remote first, which this workflow has not
     done before now (`git-dev-execute` never pushes). Push it — `git push -u origin <branch>` —
     only after the user gate above has covered this push explicitly, then open the **real** pull
     request on the real repo.

```bash
git push -u origin <branch>
<version-control-provider-command> create_merge_request '{"title":"<title>","source_branch":"<branch>","target_branch":"<plan.target_branch>","closes":[<iid>]}'
```

3. **Record the step.** The sequence is complete. `git-dev.data/` is entirely gitignored except `config.yaml`/`project-prompt.md`, neither of which this workflow touches, so there is nothing of its own to commit.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-update
```

## Summary
Report in a few lines: the issue, requirements, test results (before and after), branch, fix commit
hash, and the two acknowledgements (coverage, MR). Remind the user: once this PR merges into
`plan.target_branch`, merge it back into `plan.source_branch` right away, as the next action, not
something to catch later — `git-dev-run`'s drift check is only the fallback for when that step gets
missed.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never touch other branches. The only push this workflow ever makes is the one above, for a
  `github-*` provider's real merge request, and only after the user gate covers it explicitly.
