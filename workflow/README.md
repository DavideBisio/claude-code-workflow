# workflow

A collection of Claude Code workflows — multi-step processes made of gated skills, backed by
pluggable MCP-shaped providers (mock sample data by default; real `gh`-CLI-backed providers are
also available). Currently it bundles one workflow, `git-dev`.

## git-dev

A four-step dev workflow (target an issue, plan a test-first fix, execute it, update the tracker):

```
.claude-plugin/plugin.json        manifest
.mcp.json                         registers all four provider MCP servers
mcp/mock-req-tracker/             mock Jama: requirements, coverage, specifications, testplans
mcp/mock-version-control/         mock GitLab: issues, merge requests, milestones
mcp/github-req-tracker/           real req-tracker backed by labeled GitHub issues (`gh` CLI)
mcp/github-version-control/       real GitHub issues/PRs/milestones (`gh` CLI)
mcp/common/mockmcp.py             stdlib-only MCP stdio server + CLI harness, shared by all providers
mcp/common/ghcli.py               thin `gh` subprocess wrapper used by the github-* providers
mcp/common/miniconfig.py          minimal nested key:value reader for config.yaml's `backends`/`github` keys
skills/git-dev-run/               orchestrator: rebase dev, fetch tracker data, ask what to do
skills/git-dev-target/            step 1: pick the issue and requirements from the existing files
skills/git-dev-plan/              step 2: plan test-first fix, commit, tracker updates
skills/git-dev-execute/           step 3: branch, failing test, fix, passing test, commit
skills/git-dev-update/            step 4: coverage update, MR, commit git-dev.data
scripts/git_dev_data.py           init / fetch / record-step / provider for git-dev.data/
assets/git-dev.data/              template copied into the target project
tests/                            python -m unittest discover tests
tests/e2e/harness.py              generic e2e engine: build fixture, invoke `claude -p`, verify, report
tests/e2e/testplan.py             this plugin's TestPlan (skills, fixture template, goal checks)
tests/e2e/fixtures/               fixture templates (plain file trees) for build_git_fixture
tests/e2e/run_e2e.py              e2e: runs a TestPlan's skills through the claude CLI (spends tokens)
```

### Providers (backends)
Each tracker (`version_control`, `req_tracker`) is produced by a provider, selected per-project via
`backends.version_control` / `backends.req_tracker` in `git-dev.data/config.yaml` (defaults to
`mock` if unset — existing projects are unaffected). `scripts/git_dev_data.py provider <kind>`
prints which provider dir is active.

- `mock` / `mock_labels`(n/a): static sample data, `create_*`/`update_*` acknowledge with no effect.
- `github` (version_control) / `github_labels` (req_tracker): shells out to the `gh` CLI (must be
  installed and authenticated) against the current directory's repo, or `github.repo` in
  `config.yaml` if set. **`create_*`/`update_*` here perform real actions** — opening a real PR,
  creating/closing/commenting on real issues — not mock acknowledgements.
  - `version_control`: issues (excluding ones labeled `req`/`test`/`dev` — those are the
    req-tracker), pull requests as `merge_requests`, milestones.
  - `req_tracker`: `requirements` <- issues labeled `req` (configurable: `github.labels.requirement`);
    `coverage` <- issues labeled `test` (`github.labels.test`), each one its own testcase, linked to
    its requirement via the first `#<number>` reference in the issue body; `specifications` <-
    issues labeled `dev` (`github.labels.dev`), repurposed as "planned dev actions" since GitHub has
    no spec concept; `testplans` is always empty (no fourth label defined). See the commented
    example in `assets/git-dev.data/config.yaml`.

### Testing
Run from `workflow/` (this directory):
```
python -m unittest discover tests      # unit tests: mock servers + git_dev_data.py
python tests/e2e/run_e2e.py --dry-run  # e2e, no tokens: build the fixture, print prompts
python tests/e2e/run_e2e.py            # e2e, spends tokens: drive the skills through claude -p
```

### Provider contract
Every provider (mock or github-*) exposes the same shape per resource: `list_<plural>`
(optional exact-match `filter`), `get_<singular>` (`id`), plus whatever `create_*`/`update_*`
tools that resource supports. Mock providers' create/update acknowledge (`"ok": true, "mock":
true`) with no effect and ignore `filter`-less fetches; github-* providers' create/update perform
real `gh` actions.

CLI (prints JSON): `python mcp/mock-version-control/server.py list_issues '{"filter":{"state":"opened"}}'`, also `tools` and `call TOOL [JSON]`. Same for any other provider dir under `mcp/`.

### git-dev.data/ (in the target project, committed)
`tracker/version-control.json`, `tracker/req-tracker.json`, `state.json`, `config.yaml`,
`project-prompt.md`. Created by `git-dev-run`; the tracker files are overwritten on every fetch,
regardless of which provider produced them (see **Providers (backends)** above). `work/` is a
gitignored scratch folder for step handoff. Every step asks the user before acting and ends with a
summary.

### End-to-end test
`harness.py` is a generic engine that drives any Claude Code skill through the `claude` CLI, in
five steps: build a throwaway project from a template, invoke `claude -p` with the skill's own text
(gates pre-approved), collect the transcript and metrics, verify the result, report. Verification
is layered — first the checks that apply to any skill (did it error, did it use a tool, plus
whichever opt-in git checks a phase asks for: clean tree, still on a branch, nothing pushed), then
that skill's own goal checks. `harness.py` has no knowledge of any particular plugin or workflow;
that lives in a `TestPlan` (skills, a fixture-building hook, per-phase checks).

`testplan.py` is the git-dev workflow's TestPlan: the `run`/`target`/`plan`/`execute`/`update`
workflow, built on a fixture (`fixtures/basic-python/`) with a bare origin, a bug matching issue
2 / REQ-2, and an upstream commit to rebase onto. `python tests/e2e/run_e2e.py` runs it by
default; point `--testplan PATH` at another module exposing `TESTPLAN = harness.TestPlan(...)` to
exercise a different workflow's skills with the same engine.

Everything is kept under `tests/e2e/results/<timestamp>/` (gitignored) for review: `fixture/project`
(the test project; its only remote is the local `fixture/origin.git`), `<phase>.md` (readable
transcript: prompt, assistant text, tool calls and results), `<phase>.jsonl` (raw event stream) and
`report.json` (per-phase checks and token/cost/turn/duration metrics). Options: `--testplan`,
`--phases`, `--model`, `--budget` (USD per phase), `--claude PATH`, `--clean` (delete the fixture
afterwards), `--dry-run`. It sends each skill's text inline, so it does not test skill
auto-invocation.

### Not done
- Exercised via the e2e CLI harness, not yet loaded and driven interactively inside Claude Code itself.
- Tool input schemas are loose (`additionalProperties: true`).
- Status output of `git-dev-run` is a placeholder.
- github-* providers don't auto-create the `req`/`test`/`dev` labels; `gh label create` them once per repo before use.
- The e2e harness only exercises the mock providers; the github-* providers are only covered by unit tests of their no-`gh`-call surface (tool listing) plus manual checks against a real repo.
