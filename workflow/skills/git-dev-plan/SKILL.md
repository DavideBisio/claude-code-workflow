---
name: git-dev-plan
description: Workflow step 2 of 4. Plans the execution for the confirmed target (test first, fix, commit, tracker updates). Asks for approval, then summarizes.
disable-model-invocation: false
---

# git-dev-plan (step 2 of 4: plan)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get target
```
If this returns an `error`, stop and tell the user to run `git-dev-target` first.

## Operation
Draft a plan; change nothing in the repository yet.
1. **Branch**: resolve the branching strategy once, here — later steps (`git-dev-execute`,
   `git-dev-update`) read `source_branch`/`target_branch` from this plan rather than re-resolving it:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" prompt-section "Branching strategy"
   ```
   Read `source_branch`, `target_branch`, and the branch-pattern-by-change-type out of the returned
   text; if `text` is `null` or a value isn't stated, default to `source_branch: dev`,
   `target_branch: main`, pattern `fix/<iid>-<slug>` — today's convention. Pick the prefix that
   matches this change (`feat`/`fix`/`docs`/`chore`, or whatever the text names) and produce the
   branch name, created from `source_branch`.
2. **Test first (mock)**: what the test checks (the requirements' acceptance criteria), where it goes, its test id (mock, e.g. `TC-<next>`). It must fail before the fix.
3. **Fix (mock)**: the intended change, kept small.
4. **Verification**: the test must pass after the fix (at most 3 tries).
5. **Commit**: one commit with fix and test, message referencing `Refs #<iid>` and the requirement ids. No push.
6. **Tracker updates** (for `git-dev-update`): per requirement, `update_coverage` if a coverage record exists, otherwise `create_coverage`, with the test ids; plus the merge request title and `target_branch` from step 1 (the branch itself is cut from `source_branch`; the PR targets `target_branch` directly — see `git-dev-update`).
7. Risks and open questions.

## User gate
Show the plan and ask the user to approve it, edit it, or stop. Do not continue on a "no".

## Output
Write the approved plan as JSON (required keys: `branch`, `test`, `fix`, `verification`,
`commit_message`, `tracker_updates`; also include `source_branch`/`target_branch` from step 1 so
`git-dev-execute`/`git-dev-update` don't need to re-resolve them; put risks/open questions under an
optional `risks` key):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" write plan '<json above>'
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-plan
```
A rejected write prints which required keys are missing; fix the payload and write again.

## Summary
Report in a few lines: branch name, test, intended fix, tracker updates planned, and that the next step is `git-dev-execute`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- No repository changes, no push.
