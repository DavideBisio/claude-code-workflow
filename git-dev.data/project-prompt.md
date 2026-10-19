# Project-specific prompt

This project IS the `claude-code-workflow` plugin marketplace repo — the `git-dev` workflow being
run here is the same workflow this repo develops and ships (see `README.md` and
`workflow/README.md`). Treat this as dogfooding: changes typically land inside `workflow/`
(skills, mock/github MCP providers, `scripts/git_dev_data.py`, `tests/`).

## Conventions
- Source of truth for layout and concepts: `workflow/README.md` (providers, provider contract,
  `git-dev.data/` shape, e2e harness). Read it before assuming structure.
- Backends for this repo: `version_control = github`, `req_tracker = github_labels`, both backed by
  the real GitHub repo `DavideBisio/claude-code-workflow` via the `gh` CLI. **`create_*`/`update_*`
  calls here are real actions** (real issues/PRs/comments) — not mock acknowledgements.
- The `req`/`test`/`dev` labels already exist on the GitHub repo (confirmed via `gh label list`),
  so `github_labels` requirement tracking works without extra setup.
- Terminology: a GitHub issue labeled `req` is a "requirement"; labeled `test` is a "coverage"
  record/testcase (linked to its requirement via the first `#<number>` reference in its body);
  labeled `dev` is a "specification" (repurposed as a planned dev action, since GitHub has no
  native spec concept). `testplans` is always empty for this backend.
- Known gaps (see workflow/README.md "Not done"): status output of `git-dev-run` only replays each
  step's last summary and run date, with no aggregate reporting; github-* providers are covered by
  unit tests with `gh` stubbed out (parsing, the calls each write makes) plus manual checks against
  a real repo, but not exercised by the e2e harness (which only covers the mock providers).

## Branching strategy
- source_branch: dev
- target_branch: main
- branch_pattern: this repo has used both `feat/<iid>-<slug>` (new capability) and
  `fix/<iid>-<slug>` (bug fix/behavior change) historically; pick whichever matches the change.
- branching flow:
  1. feature branches are cut from `dev` (via `git-dev-plan`/`git-dev-execute`)
  2. `git-dev-update`'s merge request targets `main` directly, by default, for every PR — not just
     an occasional exception. `dev` is only the branch-cut source; it is never a PR target itself.
  3. right after such a PR merges into `main` — as the next action at the time, not lazily caught
     later — merge `main` back into `dev` so `dev` never falls behind (PR #8's provider fixes
     landed on `main` only and were missed by the next `dev`-branched feature until caught
     manually). `git-dev-run` step 1 also checks for this drift at the start of the next session as
     a fallback, but that is not the primary mechanism — don't rely on it.
  - This wasn't always the rule: PR #24 (issue #19) initially targeted `dev` as the then-documented
    default, which meant GitHub's `Closes #N` never fired on merge — closing keywords only resolve
    on a default-branch (`main`) merge. That left #19/#22/#23 open despite being fixed and merged,
    and is tracked as issue #25, fixed by making `main` the default target going forward.

## Issue labels
- `todo`: plain backlog item, no requirement tracking (see `git-dev-new-issue`).
- `req`: a requirement (see `git-dev-new-req`).
- `test`: a coverage record/testcase, linked to its requirement via the first `#<number>` reference
  in its body (see `git-dev-new-test`).
- `dev`: a specification — a planned dev action tied to a requirement, since GitHub has no native
  spec concept.

## Test commands
- Unit: `python -m unittest discover tests` (run from `workflow/`).
- e2e: `python tests/e2e/run_e2e.py` (run from `workflow/`; spends tokens — use `--dry-run` to avoid
  spending tokens when just checking wiring). **Not** part of `git-dev-execute`'s test-first/
  test-after loop: that loop uses the unit command only. Run e2e manually, and only when asked.

## Pre-PR checklist
- Version bump: treat this as a hard gate on *any* PR that adds a capability or changes behavior
  (new script, new skill operation, changed git-dev.data layout, etc.), regardless of target branch
  — not a reminder to remember separately, and not only for PRs to `main`. Checked twice already and
  still missed both times (PR #8 shipped without a bump despite the rule already existing; the #19
  PR to `dev` initially skipped it too since the rule was then scoped to "PRs to main" only):
  1. Bump `workflow/.claude-plugin/plugin.json`'s `version` inside the same PR/commit that ships the
     change, not as a separate follow-up commit afterward.
  2. Before opening *any* merge/pull request, re-check this section explicitly as a checklist (this
     is what `git-dev-update`'s "Pre-PR gate check" step fetches) rather than relying on having read
     this file once at the start of the run.
