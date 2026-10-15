---
name: {{WORKFLOW_NAME}}-run
description: Entry point for the {{WORKFLOW_NAME}} workflow. Updates workflow state, then asks what to do (next step, specific step, verify a step). Run manually.
disable-model-invocation: true
---

# {{WORKFLOW_NAME}} – run

Work from the user's project root. Never edit `state.json` by hand; use the script.

## 1. Update (script)
Run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/wf_state.py" status
```

It creates `{{WORKFLOW_NAME}}.config.yaml` in the project if missing (tell the user, and point them at it), then prints JSON. Report briefly:
- Steps: done / pending, and `next_step`.
- `new_commits` since the last sync (if any).
- Any step `issues` (output missing, watched files changed, recorded commit gone, requirement not done). These are possible regressions: say which steps and why.
- `tracking` output, if present.

Then record the sync:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/wf_state.py" sync
```

## 2. Ask the user what to do
Use one question with these options (omit those that don't apply):
- **Next step**: `next_step`.
- **Run a specific step**: ask which.
- **Verify a step**: ask which (default: a step with issues).
- **Roll back**: reset a step with issues (and dependents) after confirming.

## 3. Execute
- **Run a step**: invoke the skill `{{WORKFLOW_NAME}}:<step-id>` and follow it.
- **Verify a step**: read its output file and check it against that step's "Done when" without redoing the work. Report pass/fail. On pass with issues cleared, offer `done <step-id>`; on fail, offer a reset.
- **Roll back**: `python "${CLAUDE_PLUGIN_ROOT}/scripts/wf_state.py" reset <step-id> --cascade`

After any action, rerun section 1 and ask again. Stop when the user says so.
