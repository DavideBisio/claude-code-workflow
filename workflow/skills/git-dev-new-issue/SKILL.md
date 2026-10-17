---
name: git-dev-new-issue
description: Creates a new version-control issue (not labeled req/test/dev) via whichever version_control provider is configured. Asks for title/body/labels/assignee, confirms, then reports the result.
disable-model-invocation: false
---

# git-dev-new-issue

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Resolve the active provider — never hardcode `mock-version-control` vs `github-version-control`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" provider version_control
```

Use the printed `dir` value in place of `<version-control-provider>` below.

## Operation
1. Ask the user for: `title` (required), `body` (optional), `labels` (optional — do not use the tracker labels from `config.yaml`'s `github.labels`/defaults `req`/`test`/`dev`; those are managed by `git-dev-new-req` and `git-dev-new-test`), `assignee` (optional).
2. Show exactly what will be created.

## User gate
Before calling anything, state what will happen and ask the user to confirm. If `<version-control-provider>` is a `github-*` dir, say plainly that this opens a **real** GitHub issue on the real repo, not a mock acknowledgement. Do not continue on a "no".

## Create
```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/<version-control-provider>/server.py" create_issue '{"title":"<title>","body":"<body>","labels":["<label>"],"assignee":"<assignee>"}'
```
- Mock provider: returns `{"ok": true, "mock": true, ...}`, no effect.
- A `github-*` provider: returns `{"ok": true, "url": "..."}` for a real issue, or `{"ok": false, "error": "..."}`.

## Summary
Report in a few lines: the result (`ok`/error), the created issue's url (github) or acknowledgement (mock), and the title/labels/assignee used.

## Behavior
- Tool-agnostic: always resolve the provider via `git_dev_data.py provider version_control` first; never assume a specific backend or a return shape beyond `ok` (+ `url` or `error`).
- Don't guess missing required input (title) — ask.
- Never touches git; this skill only calls the version-control provider.
