---
name: git-dev-setup
description: Dedicated setup skill for the git-dev workflow. Picks version-control/req-tracker backends on first run, and guides filling in project-prompt.md's Branching strategy, Issue labels, Test commands and Pre-PR checklist sections. Invoked by git-dev-run on first init or when the user asks to reconfigure.
disable-model-invocation: false
---

# git-dev-setup

## When this runs
Invoked by `git-dev-run` step 0 when `git_dev_data.py init` reports `created: true` (first-time
setup), or when the user asks to reconfigure from `git-dev-run`'s step 4 menu. Not meant to be run
standalone against a project with no `git-dev.data/` folder yet — `git-dev-run` creates it first.

## 1. Pick backends
Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" providers` to get the valid choices per
tracker kind (`version_control`, `req_tracker`). Never hardcode backend names; always ask the script.

Ask the user which choice to use for `version_control` and which for `req_tracker`. If no human is
present to ask (e.g. a pre-approved/automated run), default both to `mock` and say so.

Save each answer: `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" set-backend <kind> <value>`.

If the user picked anything other than the defaults, tell them to review the matching section in
`config.yaml` (e.g. `github:` for repo/label overrides) before the first real run. Advanced users
wiring in a third-party tracker instead of `mock`/`github*` can add a `providers:` block to
`config.yaml` (see the commented example there) and point `backends.<kind>` at its name; `python
"${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" check-provider <kind>` smoke-tests it before relying
on it.

## 2. Fill in project-prompt.md
`project-prompt.md` ships with four placeholder sections, each read by the rest of the workflow at
the exact point it's needed (via `handoff_manager.py prompt-section <heading>`), not just once at
Setup. Walk the user through each one, offering the shipped placeholder as a starting default they
can accept or edit, and write their answers back into `git-dev.data/project-prompt.md`:

- **Branching strategy** — source branch, target branch, and the branch-name pattern per kind of
  change (new feature / fix / other). Read by `git-dev-run` (rebase target) and `git-dev-plan`
  (branch name, source/target branch).
- **Issue labels** — the labels this tracker actually uses and what each means. Read by
  `git-dev-new-issue` before asking for labels.
- **Test commands** — how to run this project's tests (unit, and e2e/integration if any). Read by
  `git-dev-execute` before the test-first/test-after steps.
- **Pre-PR checklist** — anything that must land in the same commit/PR as a behavior change
  (version bump, changelog entry, etc.). Read by `git-dev-update`'s pre-PR gate check.

If the user is reconfiguring rather than doing first-time setup, show the current content of each
section before asking what to change, instead of starting from the blank placeholder.

A section left as its shipped `<placeholder>` lines (or deleted) is not an error —
`prompt-section` returns `null` for it, and every reader falls back to its default (`dev`/`main`,
`fix/<iid>-<slug>`, ask for the test command, no extra checklist). `Branching strategy` ships with
real values rather than placeholders, so accepting it as-is uses those values.

## Summary
Report in a few lines: which backends were set, and which of the four `project-prompt.md` sections
were filled in versus left as placeholders.

## Behavior
- Never invent backend names or label sets; always resolve them from the script output or ask the user.
- Don't skip a section because the user seems in a hurry — ask once per section; accepting the
  shipped placeholder is a valid answer.
