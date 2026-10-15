---
name: deploy-workflow
description: Deploys the workflow plugin template (templates/workflow-plugin) into a new, real workflow plugin folder. Use when creating a new workflow from this repo's template.
disable-model-invocation: true
argument-hint: <workflow-name> <target-dir>
---

# Deploy workflow template

Copies `templates/workflow-plugin/` to a new plugin folder and fills in the placeholders.

## Inputs
Ask for anything not given in the arguments:
- `WORKFLOW_NAME`: lowercase letters, digits, hyphens only; must not start with `claude-` or `anthropic-`.
- `WORKFLOW_DESCRIPTION`: one sentence.
- Target directory (default: `./<WORKFLOW_NAME>`).
- Step list: for each step, an id (`step-N-<slug>`) and a one-line `STEP_SUMMARY`. Default: keep the single example step.

## Template layout (what gets copied)
- `.claude-plugin/plugin.json`
- `workflow.json`: step graph (`id`, `output`, `requires`, `watch`). Plugin-level, not project-specific.
- `assets/{{WORKFLOW_NAME}}.config.yaml`: default project config. `wf_state.py` copies it into the user's project on first run; it is never read from the plugin at runtime.
- `scripts/wf_state.py`: state/status script shared by all skills.
- `skills/{{WORKFLOW_NAME}}-run/`: orchestrator.
- `skills/step-1-example/`: step template (optional `scripts/` inside a step for companion scripts).

## Procedure
1. Stop if the target directory exists and is not empty; ask what to do.
2. Copy `templates/workflow-plugin/` to the target (include dotfolders).
3. Replace `{{WORKFLOW_NAME}}`, `{{WORKFLOW_DESCRIPTION}}`, `{{STEP_SUMMARY}}` in file contents.
4. Rename paths containing `{{WORKFLOW_NAME}}` (the `-run` skill folder and the `assets/` config file).
5. Steps: rename `skills/step-1-example/` to the first real step id if given (update its `name`, heading, output filename, and the `step-1-example` strings inside its SKILL.md). For each further step, copy that folder to `skills/<step-id>/`, fix the same fields, and append the step to `workflow.json` (`requires` = previous step id, `output` = `NN-<slug>.md`).
6. Verify: no `{{` remains anywhere; every `workflow.json` step id has `skills/<id>/SKILL.md` whose `name` equals the id; `plugin.json` and `workflow.json` are valid JSON; `python -m py_compile scripts/wf_state.py` passes.
7. Report the created tree and the next action: fill in each step's Procedure and Behavior, move deterministic parts into scripts, and set `watch` paths in `workflow.json` for regression detection.

## Rules
- Never modify `templates/`.
- Don't commit or push in the target unless asked.
