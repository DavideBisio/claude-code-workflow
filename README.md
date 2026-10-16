# claude-code-workflow

A [Claude Code](https://claude.com/claude-code) plugin marketplace: step-by-step workflow plugins
(skills + mock MCP servers) that walk a repeatable process end to end, plus a generic harness for
testing them by actually driving the skills through the `claude` CLI.

```
.claude-plugin/marketplace.json   marketplace manifest (one entry per plugin below)
workflow/                         the workflow plugin (everything in it is mocked)
```

## Install

```
/plugin marketplace add DavideBisio/claude-code-workflow
/plugin install workflow@dev-workflows
```

(or, from a local clone: `/plugin marketplace add /path/to/claude-code-workflow`)

## workflow

A collection of workflows, each a set of gated skills (and, where useful, mock MCP servers). It
currently bundles one: `git-dev`, a four-step dev workflow (target an issue, plan a test-first fix,
execute it, update the tracker) backed by two mock MCP servers standing in for a version-control
system and a requirements/coverage tracker. See [workflow/README.md](workflow/README.md) for the
layout, the mock servers, and its end-to-end test harness.
