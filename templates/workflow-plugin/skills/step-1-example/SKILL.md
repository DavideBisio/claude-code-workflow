---
name: step-1-example
description: Step 1 of the {{WORKFLOW_NAME}} workflow – {{STEP_SUMMARY}}. Run manually.
disable-model-invocation: true
---

# Step 1: {{STEP_SUMMARY}}

## Setup
Read `{{WORKFLOW_NAME}}.config.yaml` in the project root (run `python "${CLAUDE_PLUGIN_ROOT}/scripts/wf_state.py" status` first if it doesn't exist). Use `state_dir` and `language`.

## Inputs
- Config keys: (list the keys this step uses)
- Files from earlier steps: none. If a required file is missing, stop and say which step to run first.

## Procedure
Put deterministic work in scripts, not prose. Companion scripts live in this skill's `scripts/` folder and run as:
`python "${CLAUDE_PLUGIN_ROOT}/skills/step-1-example/scripts/<name>.py"`

1. (action)
2. (action)
3. (check the result; fix and repeat if it fails)

## Behavior
- Ask before overwriting an existing output file.
- Don't guess missing data; list it as an open question.

## Output
Write `<state_dir>/01-example.md`.

## Done when
- The output file exists and matches the structure above.

Then mark it complete and give a 3-line summary:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/wf_state.py" done step-1-example
```
