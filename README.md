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
