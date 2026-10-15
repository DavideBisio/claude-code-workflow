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
- `WORKFLOW_NAME`: lowercase letters, digits, hyphens only.
- `WORKFLOW_DESCRIPTION`: one sentence.
- Target directory (default: `./<WORKFLOW_NAME>`).
- Step list: for each step, an id (`step-N-<slug>`) and a one-line `STEP_SUMMARY`. Default: keep the single example step.

## Procedure
1. Stop if the target directory exists and is not empty; ask what to do.
2. Copy `templates/workflow-plugin/` to the target.
3. Replace `{{WORKFLOW_NAME}}`, `{{WORKFLOW_DESCRIPTION}}`, `{{STEP_SUMMARY}}` in every file.
4. For each requested step beyond the first, copy `skills/step-1-example/` to `skills/<step-id>/`, fix its `name`, heading, and output filename, and add the step to `steps:` in `workflow.config.yaml` (with `requires` set to the previous step). Rename the example step if the user gave it a real id.
5. Verify: no `{{` remains; every `steps[].id` matches a `skills/<id>/SKILL.md` whose `name` equals the id; `plugin.json` is valid JSON.
6. Report the created tree and the next action: fill in each step's Procedure and Behavior sections.

## Rules
- Never modify `templates/`.
- Don't commit or push in the target unless asked.
