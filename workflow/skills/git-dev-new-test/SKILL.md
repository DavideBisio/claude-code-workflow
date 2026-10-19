---
name: git-dev-new-test
description: Creates a new coverage/testcase record for an existing requirement via whichever req_tracker provider is configured. Asks for the target requirement and test title/body, confirms, then reports the result.
disable-model-invocation: false
---

# git-dev-new-test

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Resolve the active provider — never hardcode `mock-req-tracker` vs `github-req-tracker` vs a custom provider:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" provider req_tracker
```

This prints `{name, command, tracker_file}`; use `name` to tell a mock from a real tracker. Call the
provider's tools through `git_dev_data.py call req_tracker TOOL`, with the JSON args on stdin via a quoted
heredoc (`<<'GIT_DEV_JSON'`), never inside shell quotes: the args carry user-typed text, and a `'` in
a title would otherwise end the quoting and run the rest as a command.

## Operation
1. Ask the user for the target requirement id. Look it up to confirm it exists:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" call req_tracker get_requirement <<'GIT_DEV_JSON'
{"id":"<requirement-id>"}
GIT_DEV_JSON
   ```
   If it returns an `error`, stop and report; do not create a dangling coverage record.
2. Ask for the test `title` (optional — the provider defaults it) and `body` (optional).
3. Show exactly what will be created.

## User gate
Before calling anything, state what will happen and ask the user to confirm. If the resolved provider's `name` is `github-req-tracker` (or a custom provider backed by a real tracker), say plainly that this opens a **real** GitHub issue (labeled as coverage/testcase) on the real repo, not a mock acknowledgement. Do not continue on a "no".

## Create
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" call req_tracker create_coverage <<'GIT_DEV_JSON'
{"requirement_id":"<requirement-id>","title":"<title>","body":"<body>"}
GIT_DEV_JSON
```
- Mock provider: returns `{"ok": true, "mock": true, ...}`, no effect.
- `github-req-tracker`: returns `{"ok": true, "url": "..."}` for a real issue labeled as coverage, referencing the requirement in its body, or `{"ok": false, "error": "..."}`.

## Summary
Report in a few lines: the target requirement, the result (`ok`/error), and the created coverage record's url (github) or acknowledgement (mock).

## Behavior
- Tool-agnostic: always resolve the provider via `git_dev_data.py provider req_tracker` first; never assume a specific backend or a return shape beyond `ok` (+ `url` or `error`).
- Don't guess the requirement — verify it exists before creating coverage for it.
- Never touches git; this skill only calls the req-tracker provider.
