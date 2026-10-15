# example-plugin

Placeholder Claude Code plugin showing the workflow layout. Everything is a mock.

```
.claude-plugin/plugin.json   manifest
.mcp.json                    registers the two mock MCP servers
mcp/req-tracker/             mock Jama: requirements, coverage, specifications, testplans
mcp/dev-status/              mock GitLab: issues, merge requests, milestones
mcp/common/mockmcp.py        stdlib-only MCP stdio server + CLI used by both
skills/example-run/          orchestrator: rebase dev, fetch tracker data, ask what to do
skills/example-step/         step: failing test, fix, passing test, commit, coverage, MR
scripts/example_data.py      init / fetch / record-step for example.data/
assets/example.data/         template copied into the target project
tests/                       python -m unittest discover tests
```

## Mock servers
Per resource: `list_<plural>` (optional exact-match `filter`), `get_<singular>` (`id`), `create_<singular>`, `update_<singular>`. Fetch returns sample data; create and update acknowledge (`"ok": true, "mock": true`) with no effect.

CLI (prints JSON): `python mcp/dev-status/server.py list_issues '{"filter":{"state":"opened"}}'`, also `tools` and `call TOOL [JSON]`.

## example.data/ (in the target project, committed)
`tracker/dev-status.json`, `tracker/req-tracker.json`, `state.json`, `config.yaml`, `project-prompt.md`. Created by `example-run`; the tracker files are overwritten on every fetch.

## Not done
- Not yet loaded in Claude Code end to end.
- Tool input schemas are loose (`additionalProperties: true`).
- Status output of `example-run` is a placeholder.
