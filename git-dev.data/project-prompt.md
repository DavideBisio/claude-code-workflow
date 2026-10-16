# Project-specific prompt

This project IS the `claude-code-workflow` plugin marketplace repo — the `git-dev` workflow being
run here is the same workflow this repo develops and ships (see `README.md` and
`workflow/README.md`). Treat this as dogfooding: changes typically land inside `workflow/`
(skills, mock/github MCP providers, `scripts/git_dev_data.py`, `tests/`).

## Conventions
- Source of truth for layout and concepts: `workflow/README.md` (providers, provider contract,
  `git-dev.data/` shape, e2e harness). Read it before assuming structure.
- Tests: `python -m unittest discover tests` (unit) and `python tests/e2e/run_e2e.py` (e2e, spends
  tokens; use `--dry-run` to avoid spending tokens when just checking wiring). Run both from
  `workflow/`.
- Backends for this repo: `version_control = github`, `req_tracker = github_labels`, both backed by
  the real GitHub repo `DavideBisio/claude-code-workflow` via the `gh` CLI. **`create_*`/`update_*`
  calls here are real actions** (real issues/PRs/comments) — not mock acknowledgements.
- The `req`/`test`/`dev` labels already exist on the GitHub repo (confirmed via `gh label list`),
  so `github_labels` requirement tracking works without extra setup.
- Terminology: a GitHub issue labeled `req` is a "requirement"; labeled `test` is a "coverage"
  record/testcase (linked to its requirement via the first `#<number>` reference in its body);
  labeled `dev` is a "specification" (repurposed as a planned dev action, since GitHub has no
  native spec concept). `testplans` is always empty for this backend.
- Known gaps (see workflow/README.md "Not done"): status output of `git-dev-run` is a placeholder;
  github-* providers are only unit-tested on their no-`gh`-call surface, not exercised by the e2e
  harness (which only covers the mock providers).
