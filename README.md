# claude-code-workflow

A [Claude Code](https://claude.com/claude-code) plugin marketplace: step-by-step workflow plugins
(skills + mock MCP servers) that walk a repeatable process end to end, plus a generic harness for
testing them by actually driving the skills through the `claude` CLI.

```
.claude-plugin/marketplace.json   marketplace manifest (one entry per plugin below)
workflow/                         the workflow plugin (everything in it is mocked)
```

## Install

In a terminal's interactive `claude` REPL:
```
/plugin marketplace add DavideBisio/claude-code-workflow
/plugin install workflow@dev-workflows
```
`dev-workflows` is the marketplace name (from `marketplace.json`), not the repo name.

In the VS Code extension, `/plugin` isn't available; use `/plugins` (plural) instead to open the
"Manage plugins" panel, add the marketplace on the Marketplaces tab, then install `workflow` from
the Plugins tab.

Non-interactively, from any shell:
```
claude plugin marketplace add DavideBisio/claude-code-workflow
claude plugin install workflow@dev-workflows --scope user
```

From a local clone instead of GitHub: `/plugin marketplace add /path/to/claude-code-workflow` (or
`./claude-code-workflow`/`../claude-code-workflow` — a bare `owner/repo`-shaped path is always read
as a GitHub reference).

## workflow

A collection of workflows, each a set of gated skills backed by pluggable MCP-shaped providers. It
currently bundles one: `git-dev`, an orchestrator (`git-dev-run`) plus a four-step dev workflow
(target an issue, plan a test-first fix, execute it, update the tracker), with on-demand skills for
creating issues, requirements and tests outside that flow. Each of the two trackers it reads
(version control, requirements/coverage) is produced by a provider — mock sample data by default, or
a real `gh`-CLI-backed provider. See [workflow/README.md](workflow/README.md) for the layout, the
providers, and its end-to-end test harness.

## Prior art and what's different

This is not a new idea. Many Claude Code plugins already drive a gated, issue-to-PR workflow, and
several handle requirements traceability. A GitHub search (October 2026, a shallow survey, not a
code review) found, among others:

| Project | What it does |
|---|---|
| [workkit](https://github.com/itw-creative-works/workkit) | GitHub Issues as the single source of truth and labels as the pipeline, driven by an agent crew with guard hooks |
| [claude-software-factory](https://github.com/genai-jerry/claude-software-factory) | GitHub issues, sub-issues and labels as state, OpenSpec for content, 13 agent roles, human approval gates |
| [reqtrace-mcp](https://github.com/b4ked/reqtrace-mcp) | Traces code to requirements and requirements to tests (with per-test coverage), plus a read-only independent verifier and human sign-off |
| [plumbline](https://github.com/dr-zog/plumbline) | Enforces requirement-to-code links with code anchors; fails the build when a link breaks |
| [ai-workflow](https://github.com/masnun-siam/ai-workflow), [ticket-flow](https://github.com/alexanderop/ticket-flow), [change-workflow](https://github.com/cwoodard1121/change-workflow), [rk-skills](https://github.com/richkuo/rk-skills) | Issue to reviewed PR with human gates; no separate requirement or coverage records |
| spec-driven-development plugins ([specswarm](https://github.com/MartyBonacci/specswarm), [claude-plugin-sdd](https://github.com/joestump/claude-plugin-sdd), Spec Kit, BMAD) | Specs live as files in the repo, not in a tracker |

### What is different here
- **A requirements/coverage model on plain GitHub labels.** Requirements are `req` issues, coverage
  records are `test` issues linked to their requirement, and `dev` issues fill a "specifications"
  slot, so a Jama-style requirement tracker needs nothing beyond GitHub. The traceability tools
  above keep requirements in files or code; the issue-driven ones have no coverage layer.
- **Swappable providers behind one contract.** `mock` and `gh`-backed providers expose the same
  tools, chosen per project in `config.yaml`, so tests run without a network and another tracker
  could be added later.
- **Small, skills-first and gated per step.** Every step asks before acting by default and says
  plainly when an action is real. Opt-in auto mode can chain steps, but the step that pushes and
  opens the PR always asks. Subagents handle only the narrow execute/explore/review work, never a
  real push or PR. The heavier projects are agent-first.

### What is not different
Issue-driven, human-gated, test-first workflows are well covered elsewhere, and some of those
projects are more mature. This one is a lightweight option for requirement-to-test traceability on
GitHub issues, not a new category. A fuller comparison is tracked in the issue tracker.
