---
name: step-1-example
description: Step 1 of the {{WORKFLOW_NAME}} workflow – {{STEP_SUMMARY}}. Run manually.
disable-model-invocation: true
---

# Step 1: {{STEP_SUMMARY}}

## Setup
Read `workflow.config.yaml` at the plugin root (the parent of this `skills/` folder). Use `workflow.state_dir` and `workflow.language`.

## Inputs
- Config keys: (list the keys this step uses)
- Files from earlier steps: none. If a required file is missing, stop and say which step to run first.

## Procedure
1. (action)
2. (action)
3. (check the result; fix and repeat if it fails)

## Behavior
- Ask before overwriting an existing output file.
- Don't guess missing data; list it as an open question.

## Output
Write `<state_dir>/01-example.md`. Finish with a 3-line summary.

## Done when
- The output file exists and matches the structure above.
