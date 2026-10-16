# example-plugin

Placeholder Claude Code plugin showing the workflow layout. Everything is a mock.

```
.claude-plugin/plugin.json   manifest
.mcp.json                    registers the two mock MCP servers
mcp/req-tracker/             mock Jama: requirements, coverage, specifications, testplans
mcp/dev-status/              mock GitLab: issues, merge requests, milestones
mcp/common/mockmcp.py        stdlib-only MCP stdio server + CLI used by both
skills/example-run/          orchestrator: rebase dev, fetch tracker data, ask what to do
skills/example-target/       step 1: pick the issue and requirements from the existing files
skills/example-plan/         step 2: plan test-first fix, commit, tracker updates
skills/example-execute/      step 3: branch, failing test, fix, passing test, commit
skills/example-update/       step 4: coverage update, MR, commit example.data
scripts/example_data.py      init / fetch / record-step for example.data/
assets/example.data/         template copied into the target project
tests/                       python -m unittest discover tests
tests/e2e/run_e2e.py        e2e: runs the skills through the claude CLI (spends tokens)
```

## Mock servers
Per resource: `list_<plural>` (optional exact-match `filter`), `get_<singular>` (`id`), `create_<singular>`, `update_<singular>`. Fetch returns sample data; create and update acknowledge (`"ok": true, "mock": true`) with no effect.

CLI (prints JSON): `python mcp/dev-status/server.py list_issues '{"filter":{"state":"opened"}}'`, also `tools` and `call TOOL [JSON]`.

## example.data/ (in the target project, committed)
`tracker/dev-status.json`, `tracker/req-tracker.json`, `state.json`, `config.yaml`, `project-prompt.md`. Created by `example-run`; the tracker files are overwritten on every fetch. `work/` is a gitignored scratch folder for step handoff. Every step asks the user before acting and ends with a summary.

## End-to-end test
`python tests/e2e/run_e2e.py` builds a throwaway project (bare origin, a bug matching issue 2 / REQ-2, an upstream commit to rebase onto), then calls `claude -p` once per skill (`run`, `target`, `plan`, `execute`, `update`) with gates pre-approved. Per phase it checks the goal (git and file state, tool calls, no push) and reports input, output and cache tokens, cost, turns and duration, Everything is kept under `tests/e2e/results/<timestamp>/` (gitignored) for review: `fixture/project` (the test project; its only remote is the local `fixture/origin.git`), `<phase>.md` (readable transcript: prompt, assistant text, tool calls and results), `<phase>.jsonl` (raw event stream) and `report.json`. Options: `--phases`, `--model`, `--budget` (USD per phase), `--claude PATH`, `--clean` (delete the fixture afterwards), `--dry-run`. It sends each skill's text inline, so it does not test skill auto-invocation.

## Not done
- Not yet loaded in Claude Code end to end.
- Tool input schemas are loose (`additionalProperties: true`).
- Status output of `example-run` is a placeholder.
