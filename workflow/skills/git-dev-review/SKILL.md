---
name: git-dev-review
description: Optional step between git-dev-execute and git-dev-update. Reviews the fix commit's diff against the plan and the target's acceptance criteria, via a read-only reviewer agent. Not required — git-dev-update can run without it.
disable-model-invocation: false
---

# git-dev-review

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and
follow the project prompt throughout.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get target
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get plan
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" get result
```
If any returns an `error`, stop and tell the user to run the missing earlier step first.

## User gate
If `git-dev-run` invoked this step in auto mode and said it is **ungated** (see that skill's step 3
for how `auto.gates` decides this), skip this confirmation — state what you're about to do and
proceed directly. Otherwise: state that you're
about to compute the diff and dispatch it to the read-only reviewer agent, and ask the user to
confirm. Do not continue on a "no".

## Operation
1. Compute the diff yourself (the reviewer agent has no Bash): `git diff <plan.source_branch>...<result.commit>`
   (or `<plan.source_branch>..HEAD` if still on the result's branch).
2. Dispatch to the `workflow:reviewer` agent (via the Agent tool, `subagent_type: "workflow:reviewer"`),
   passing it the plan, the target (issue + requirements), and the diff text from step 1.
3. The agent returns `{"pass": true}` or `{"pass": false, "findings": [...]}`.

## Output
This step writes nothing to the handoff — it's advisory, not a required gate in the 4-step
sequence. Still record that it ran:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-review
```

## Summary
Report the agent's verdict. If `pass: false`, show the findings and ask the user whether to
address them (likely by going back to `git-dev-execute`) before moving on to `git-dev-update`, or
to proceed anyway. If `pass: true`, say the next step is `git-dev-update`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Never push or touch other branches; this step only reads.
