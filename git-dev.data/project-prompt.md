# Project prompt

**Note on why this exists here:** this is `claude-code-workflow`, the plugin's own source repo —
not a separate target project. `git-dev.data/` was initialized here deliberately, to dogfood the
`workflow` plugin against itself rather than against an external project.

**Backends:** `config.yaml` sets `backends.version_control: github` and
`backends.req_tracker: github_labels` for this repo, so the tracker files are **real** data from
`DavideBisio/claude-code-workflow` on GitHub, not mock fixtures: `requirements` are issues labeled
`req`, `coverage` is issues labeled `test`, `specifications` (repurposed as planned dev actions)
is issues labeled `dev` — each `test`/`dev` issue links to its req via the first `#<number>`
reference in its body. `testplans` is always empty (no label defined for it). Treat every record
as a real, current issue/PR on this repo — `git-dev-update` will open real PRs and create/close
real issues, not acknowledgements. There are no `req`-labeled issues yet, so `git-dev-target` will
currently report "no opened issue" until one is filed.

Real project conventions: Python stdlib only (no third-party deps) under `workflow/`; the plugin
itself lives at `workflow/`, the marketplace manifest at `.claude-plugin/marketplace.json`. Tests:
`python -m unittest discover tests` and `python tests/e2e/run_e2e.py`, both run from `workflow/`.
