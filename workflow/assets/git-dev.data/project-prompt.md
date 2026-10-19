# PLACEHOLDER: project-specific prompt

Read by every step before it starts. Describe project conventions, terminology and constraints here.

The four sections below are read individually, at the exact point each is needed, via
`handoff_manager.py prompt-section "<heading>"` — not just once at Setup. A section that is
deleted, or still holds only its `<placeholder>` lines, is treated as unset: every reader falls
back to the default noted under it. `Branching strategy` ships with real values, which are used
as written until you change them.

## Branching strategy
- source_branch: dev
- target_branch: main
- branch_pattern:
  - new feature: `feat/<iid>-<slug>`
  - fix to an existing feature: `fix/<iid>-<slug>`
  - else: `docs/<iid>-<slug>` or `chore/<iid>-<slug>`
- branching flow:
  1. always start from source_branch
  2. work on feat/fix/docs/chore branches cut from source_branch
  3. PR back to target_branch once work is done
  4. merge target_branch back into source_branch after the PR merges
<!-- Default if this section is missing: source_branch=dev, target_branch=main, branch_pattern=fix/<iid>-<slug>. -->

## Issue labels
- <list your tracker's labels and what each means, e.g. todo, dev, req, test>
<!-- Default if unchanged or missing: no special label handling beyond what each provider already assumes. -->

## Test commands
- <unit test command>
- <e2e / integration test command, if any>
<!-- Default if unchanged or missing: none assumed; git-dev-execute asks rather than guessing. -->

## Pre-PR checklist
- <anything that must land in the same commit/PR as a behavior change, e.g. a version bump or changelog entry>
<!-- Default if unchanged or missing: no extra checklist items beyond the merge request itself. -->
