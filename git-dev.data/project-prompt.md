# Project prompt

**Note on why this exists here:** this is `claude-code-workflow`, the plugin's own source repo —
not a separate target project. `git-dev.data/` was initialized here deliberately, to dogfood the
`workflow` plugin against itself rather than against an external project. The mock servers' sample
data (issues, requirements, etc.) is unrelated to this repo's actual content; treat every
issue/requirement/coverage record as fictional test fixture data, not a real backlog for this repo.

Real project conventions: Python stdlib only (no third-party deps) under `workflow/`; the plugin
itself lives at `workflow/`, the marketplace manifest at `.claude-plugin/marketplace.json`. Tests:
`python -m unittest discover tests` and `python tests/e2e/run_e2e.py`, both run from `workflow/`.
