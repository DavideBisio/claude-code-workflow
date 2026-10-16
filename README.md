# claude-code-workflow

Step-by-step workflows for [Claude Code](https://claude.com/claude-code): plugins (skills + mock
MCP servers) that walk a repeatable process end to end, plus a generic harness for testing them by
actually driving the skills through the `claude` CLI.

```
examples/example-plugin/   placeholder plugin demonstrating the layout (everything in it is mocked)
```

## example-plugin

A four-step dev workflow (target an issue, plan a test-first fix, execute it, update the tracker),
each step a gated skill backed by two mock MCP servers standing in for an issue tracker and a
requirements/coverage tracker. See [examples/example-plugin/README.md](examples/example-plugin/README.md)
for the layout, the mock servers, and its end-to-end test harness.
