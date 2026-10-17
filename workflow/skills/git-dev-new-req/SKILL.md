---
name: git-dev-new-req
description: Creates a new requirement via whichever req_tracker provider is configured. Asks for title/description, confirms, then reports the result.
disable-model-invocation: false
---

# git-dev-new-req

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Resolve the active provider — never hardcode `mock-req-tracker` vs `github-req-tracker`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" provider req_tracker
```

Use the printed `dir` value in place of `<req-tracker-provider>` below.

## Operation
1. Ask the user for: `title` (required), `body`/description (optional).
2. Show exactly what will be created.

## User gate
Before calling anything, state what will happen and ask the user to confirm. If `<req-tracker-provider>` is `github-req-tracker`, say plainly that this opens a **real** GitHub issue (labeled as a requirement) on the real repo, not a mock acknowledgement. Do not continue on a "no".

## Create
```bash
python "${CLAUDE_PLUGIN_ROOT}/mcp/<req-tracker-provider>/server.py" create_requirement '{"title":"<title>","body":"<body>"}'
```
- Mock provider: returns `{"ok": true, "mock": true, ...}`, no effect.
- `github-req-tracker`: returns `{"ok": true, "url": "..."}` for a real issue labeled as a requirement, or `{"ok": false, "error": "..."}`.

## Summary
Report in a few lines: the result (`ok`/error) and the created requirement's url (github) or acknowledgement (mock), with the title used.

## Behavior
- Tool-agnostic: always resolve the provider via `git_dev_data.py provider req_tracker` first; never assume a specific backend or a return shape beyond `ok` (+ `url` or `error`).
- Don't guess missing required input (title) — ask.
- Never touches git; this skill only calls the req-tracker provider.
