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
- PRs to `main`: feature branches are cut from `dev` and PR'd directly to `main`, not through
  `git-dev-update`'s own default target (`dev`). Treat these two as a hard gate on that PR, not a
  reminder to remember separately — checked once already and still missed (PR #8 shipped without a
  bump despite the rule already existing):
  1. Bump `workflow/.claude-plugin/plugin.json`'s `version` inside the same PR that merges to
     `main`, not as a separate follow-up commit afterward.
  2. Right after that PR merges into `main` — as the last step of that unit of work, not lazily
     caught later — merge `main` back into `dev` so `dev` never falls behind (PR #8's provider fixes
     landed on `main` only and were missed by the next `dev`-branched feature until caught
     manually). `git-dev-run` step 1 also checks for this drift at the start of the next session as
     a fallback, but that is not the primary mechanism — don't rely on it.
