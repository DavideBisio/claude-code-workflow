# workflow

A collection of Claude Code workflows — multi-step processes made of gated skills, backed by
pluggable MCP-shaped providers (mock sample data by default; real `gh`-CLI-backed providers are
also available). Currently it bundles one workflow, `git-dev`.

## git-dev

A four-step dev workflow (target an issue, plan a test-first fix, execute it, update the tracker),
run through the `git-dev-run` orchestrator, plus three on-demand skills (`git-dev-new-issue`,
`git-dev-new-req`, `git-dev-new-test`) for creating tracker records outside that flow:

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
agents/executor.md                dispatched by git-dev-execute: branch, failing test, fix, passing test, commit
agents/reviewer.md                dispatched by git-dev-review: read-only diff-vs-plan review
agents/explorer.md                dispatched by git-dev-plan: read-only codebase exploration for a real fix
skills/git-dev-run/               orchestrator: rebase dev, fetch tracker data, ask what to do (or chain, in auto mode)
skills/git-dev-setup/             first-run (or on-demand reconfigure): pick backends, fill project-prompt.md
skills/git-dev-target/            step 1: pick the issue and requirements from the existing files
skills/git-dev-plan/              step 2: plan test-first fix, commit, tracker updates
skills/git-dev-execute/           step 3: dispatches to the executor agent; writes its result
skills/git-dev-review/            optional step: dispatches the diff to the reviewer agent
skills/git-dev-update/            step 4: coverage update, MR, commit git-dev.data
skills/git-dev-new-issue/         on-demand: create a version-control issue via the configured provider
skills/git-dev-new-req/           on-demand: create a requirement via the configured req_tracker provider
skills/git-dev-new-test/          on-demand: create a coverage/testcase record for a requirement
scripts/git_dev_data.py           init / fetch / record-step / provider / config for git-dev.data/
scripts/handoff_manager.py        scoped, schema-validated step handoff (target/plan/result) + prompt-section
assets/git-dev.data/              template copied into the target project
tests/                            python -m unittest discover tests
tests/e2e/harness.py              generic e2e engine: build fixture, invoke `claude -p`, verify, report
tests/e2e/testplan.py             this plugin's TestPlan (skills, fixture template, goal checks)
tests/e2e/fixtures/               fixture templates (plain file trees) for build_git_fixture
tests/e2e/run_e2e.py              e2e: runs a TestPlan's skills through the claude CLI (spends tokens)
```

### Agents (opt-in)
Three steps can dispatch part of their work to a read-scoped or execute-scoped subagent instead of
doing it inline in the main session: `git-dev-execute` → `workflow:executor` (branch/test/fix/
commit loop), `git-dev-plan` → `workflow:explorer` (read-only codebase lookup for the fix), and the
optional `git-dev-review` → `workflow:reviewer` (read-only diff review). This is not configurable
off — `git-dev-execute`/`git-dev-plan` always dispatch — but it is scoped narrowly: `git-dev-target`,
`git-dev-update`, and `git-dev-run` itself never do, since they either just read JSON or perform
real, hard-to-reverse side effects (a real push, a real PR/issue) that must stay in the main
session behind its own gate.

No agent here can push or create a real issue/PR — not because any tool is blocked from doing so
(a frontmatter `tools:`/`disallowedTools:` allowlist can't express "Bash minus `git push`", only
"no Bash at all"), but because of where the boundary actually sits: `git push`, `create_merge_request`
and `create_issue` only ever run inside `git-dev-update`/`git-dev-new-issue`, and neither of those
ever runs as a subagent under this design. `reviewer` and `explorer` are read-only by tool grant
(`Read, Grep, Glob`, no `Bash`/`Write`/`Edit`); `executor` does have `Bash`/`Write`/`Edit` (it needs
them to run tests and commit), so its "never pushes" is the same prose-level commitment the rest
of this plugin's skills already rely on, not a technically enforced one.

### Opt-in auto mode
`auto.enabled: true` in `config.yaml` makes `git-dev-run` chain `target → plan → execute → (review)
→ update` itself instead of asking after every step. `auto.gates` (comma-separated step names)
lists which steps still pause for their own confirmation; empty/unset means every step still
pauses, so turning auto mode on with no `gates` set changes only who decides to start the next
step, not whether that step still asks. `git-dev-update`'s gate is never skippable, in or out of
`auto.gates` — it's the one step with real side effects. Default is unset/`false`: unchanged from
today.

### Running multiple issues in parallel
Nothing here assumes a single global workspace: `git-dev.data/` lives in the project root, so
`git worktree add ../other-issue -b fix/26-x dev` plus its own `git_dev_data.py init` in that
worktree already gives you an independent `git-dev-run` session today, with no new code needed.
What isn't solved: two parallel runs racing on the *same* requirement's coverage record, or
creating overlapping issues — there's no cross-run lock. Worth building if that conflict actually
bites; not built speculatively ahead of a real case.

### Providers (backends)
Each tracker (`version_control`, `req_tracker`) is produced by a provider, selected per-project via
`backends.version_control` / `backends.req_tracker` in `git-dev.data/config.yaml` (defaults to
`mock` if unset — existing projects are unaffected). `scripts/git_dev_data.py provider <kind>`
prints `{name, command, tracker_file}` for whichever provider is active; skills run the printed
`command` array verbatim (never hardcode a path under `mcp/`), so the same skill text works for a
built-in or a custom provider.

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
    no spec concept — a specification with no linked requirement (`requirement_id: null`) is a
    valid standalone target, not an anomaly; `testplans` is always empty (no fourth label defined).
    See the commented example in `assets/git-dev.data/config.yaml`.
  - Issues, requirements and specifications also carry `blocks`/`blocked_by`: `#<number>` refs
    parsed from "Blocks #N"/"Blocked by #N" text in the body (`mcp/common/ghcli.py:blocking_refs`)
    — a text heuristic, not GitHub's native sub-issue relationship — used by `git-dev-target` to
    avoid picking a target out of order.

### Testing
Run from `workflow/` (this directory):
```
python -m unittest discover tests      # unit tests: mock servers + git_dev_data.py
python tests/e2e/run_e2e.py --dry-run  # e2e, no tokens: build the fixture, print prompts
python tests/e2e/run_e2e.py            # e2e, spends tokens: drive the skills through claude -p
```

### Provider contract
Every provider (mock, github-*, or a custom one) exposes the same shape per resource:
`list_<plural>` (optional exact-match `filter`), `get_<singular>` (`id`), plus whatever
`create_*`/`update_*` tools that resource supports. Mock providers' create/update acknowledge
(`"ok": true, "mock": true`) with no effect and ignore `filter`-less fetches; github-* providers'
create/update perform real `gh` actions.

CLI (prints JSON): `python mcp/mock-version-control/server.py list_issues '{"filter":{"state":"opened"}}'`, also `tools` and `call TOOL [JSON]`. Same for any other provider dir under `mcp/`.

Any command implementing this same convention (`tools` / `call TOOL [JSON]` / `TOOL [JSON]`,
printing JSON — see `mcp/common/mockmcp.py`'s `run_tools` for the reference harness) can be wired
in as a custom provider via a `providers:` entry in `git-dev.data/config.yaml` (see the commented
example there and **Providers (backends)** above), without forking this plugin. `scripts/
git_dev_data.py check-provider <kind>` smoke-tests that the active provider for `<kind>` exposes
every tool that kind needs. Making a custom provider *also* callable as a live MCP tool (not just
the CLI the skills use) requires separately adding it to the target project's own `.mcp.json`,
which Claude Code merges with this plugin's.

### git-dev.data/ (in the target project)
Durable and committed: `config.yaml`, `project-prompt.md`. Gitignored and regenerated, never
committed by any step: `tracker/version-control.json`, `tracker/req-tracker.json` (overwritten on
every `git-dev-run` fetch, used only to pick which issue to target next — see **Providers
(backends)** above), `state.json` (last run date per step), `work/handoff.json` (the scoped,
schema-validated handoff between steps, written and read one section at a time — `scope`/`target`/
`plan`/`result` — only through `scripts/handoff_manager.py`, never as raw tracker dumps). Created
by `git-dev-run`. Every step asks the user before acting and ends with a summary.

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
- Status output of `git-dev-run` just replays step 1/2's summaries and each step's last run date; no aggregate reporting (e.g. coverage trends over time).
- github-* providers don't auto-create the `req`/`test`/`dev` labels; `gh label create` them once per repo before use.
- `blocks`/`blocked_by` is a plain "Blocks #N"/"Blocked by #N" text match over the issue body, not GitHub's native sub-issue/blocked-by relationship; `git-dev-target` treats it as a hint to surface, not an authoritative dependency graph.
- `tests/e2e/testplan.py`'s goal checks still assert the pre-`handoff_manager.py` file shape (`work/target.json`, `work/plan.md`, `work/result.json`, a `git-dev.data` commit per step) and will fail as written; updating them is deferred to a follow-up issue by design (see issue #19's acceptance criteria).
- The e2e harness only exercises the mock providers; the github-* providers are only covered by unit tests of their no-`gh`-call surface (tool listing) plus manual checks against a real repo.
