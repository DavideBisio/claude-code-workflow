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
tests/e2e/harness.py         generic e2e engine: build fixture, invoke `claude -p`, verify, report
tests/e2e/testplan.py        this plugin's TestPlan (skills, fixture template, goal checks)
tests/e2e/fixtures/          fixture templates (plain file trees) for build_git_fixture
tests/e2e/run_e2e.py         e2e: runs a TestPlan's skills through the claude CLI (spends tokens)
```

## Mock servers
Per resource: `list_<plural>` (optional exact-match `filter`), `get_<singular>` (`id`), `create_<singular>`, `update_<singular>`. Fetch returns sample data; create and update acknowledge (`"ok": true, "mock": true`) with no effect.

CLI (prints JSON): `python mcp/dev-status/server.py list_issues '{"filter":{"state":"opened"}}'`, also `tools` and `call TOOL [JSON]`.

## example.data/ (in the target project, committed)
`tracker/dev-status.json`, `tracker/req-tracker.json`, `state.json`, `config.yaml`, `project-prompt.md`. Created by `example-run`; the tracker files are overwritten on every fetch. `work/` is a gitignored scratch folder for step handoff. Every step asks the user before acting and ends with a summary.

## End-to-end test
`harness.py` is a generic engine that drives any Claude Code skill through the `claude` CLI, in
five steps: build a throwaway project from a template, invoke `claude -p` with the skill's own text
(gates pre-approved), collect the transcript and metrics, verify the result, report. Verification
is layered — first the checks that apply to any skill (did it error, did it use a tool, plus
whichever opt-in git checks a phase asks for: clean tree, still on a branch, nothing pushed), then
that skill's own goal checks. `harness.py` has no knowledge of any particular plugin; that lives in
a `TestPlan` (skills, a fixture-building hook, per-phase checks).

`testplan.py` is this plugin's TestPlan: the `run`/`target`/`plan`/`execute`/`update` workflow,
built on a fixture (`fixtures/basic-python/`) with a bare origin, a bug matching issue 2 / REQ-2,
and an upstream commit to rebase onto. `python tests/e2e/run_e2e.py` runs it by default; point
`--testplan PATH` at another module exposing `TESTPLAN = harness.TestPlan(...)` to exercise a
different plugin's skills with the same engine.

Everything is kept under `tests/e2e/results/<timestamp>/` (gitignored) for review: `fixture/project`
(the test project; its only remote is the local `fixture/origin.git`), `<phase>.md` (readable
transcript: prompt, assistant text, tool calls and results), `<phase>.jsonl` (raw event stream) and
`report.json` (per-phase checks and token/cost/turn/duration metrics). Options: `--testplan`,
`--phases`, `--model`, `--budget` (USD per phase), `--claude PATH`, `--clean` (delete the fixture
afterwards), `--dry-run`. It sends each skill's text inline, so it does not test skill
auto-invocation.

## Not done
- Exercised via the e2e CLI harness, not yet loaded and driven interactively inside Claude Code itself.
- Tool input schemas are loose (`additionalProperties: true`).
- Status output of `example-run` is a placeholder.
