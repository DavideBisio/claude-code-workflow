---
name: run
description: Run all steps of the {{WORKFLOW_NAME}} workflow in order. Run manually.
disable-model-invocation: true
---

# Run {{WORKFLOW_NAME}}

1. Read `workflow.config.yaml` at the plugin root.
2. For each entry in `steps`, in order, invoke that step's skill and follow it exactly.
3. After each step, confirm its `output` file exists in `workflow.state_dir`. If not, stop and report.
4. Stop at the first failure; never skip a step.
5. End with a one-line status per step.
