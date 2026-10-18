---
name: git-dev-run
description: Orchestrator for the git-dev workflow. Rebases the configured source branch, fetches version-control and requirement-tracker data, then asks what to do (run a step, reconfigure, show status), or chains the steps itself in opt-in auto mode. Run manually.
disable-model-invocation: true
---

# git-dev-run

Work from the project root. Helper script: `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py"`. Every provider (mock or github-backed) also has a JSON CLI (the MCP tools of the same names are equivalent).

## 0. Project data folder
`git-dev.data/` in the project root splits into durable, committed config and ephemeral,
gitignored data:
- **Committed**: `config.yaml` (skill custom config), `project-prompt.md` (project-specific prompt
  read by every step).
- **Gitignored (regenerated, never committed by any step)**: `tracker/version-control.json`
  (`issues`, `merge_requests`, `milestones`) and `tracker/req-tracker.json` (`requirements`,
  `coverage`, `specifications`, `testplans`) — the latest full tracker output, written by this
  step's fetch below, for picking which issue to target next. Each is produced by whichever
  provider `config.yaml`'s `backends.version_control` / `backends.req_tracker` names (defaults to
  the mock servers). Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" provider
  version_control` (or `req_tracker`) to see which is active. `state.json`: last run completion
  date per step. `work/handoff.json`: the scoped, schema-validated handoff between steps
  (`target`/`plan`/`result` sections), written and read only through `scripts/handoff_manager.py`
  — see that step's own skill for its shape.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" init
```

If it reports `created: true`, this is first-time setup: invoke the skill `workflow:git-dev-setup`
and follow it before anything else runs (it picks the trackers' backends and walks the user through
`project-prompt.md`'s placeholder sections). Do not inline those steps here.

## 1. Fetch git state and rebase
Resolve the branching strategy once, before touching git, so the rest of this step uses the
project's actual convention instead of a hardcoded one:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" prompt-section "Branching strategy"
```
Read `source_branch` and `target_branch` out of the returned text (e.g. a `source_branch: dev`
line); if `text` is `null` or either value isn't stated, default to `source_branch: dev`,
`target_branch: main` — today's convention. Use `<source_branch>`/`<target_branch>` for every git
command below in place of the literal `dev`/`main`.

Git comes first so the tree is clean before `git-dev.data/` is rewritten.

```bash
git branch --show-current
git status --short
```
- The expected branch is `<source_branch>`. If on another branch, say so and ask whether to continue; never switch branches without being asked.
- If the working tree is not clean, stop and ask; do not stash or discard anything.
- Otherwise bring `<source_branch>` up to the latest remote commit:

```bash
git fetch origin <source_branch>
git log --oneline HEAD..origin/<source_branch>
git rebase origin/<source_branch>
```

- Report the new commits (the `log` output above). If the rebase conflicts, stop, list the conflicting files and ask; use `git rebase --abort` only if the user says so.
- Do not run `git reset` or push.

### Check for drift against `<target_branch>` (fallback only)
`git-dev-update` targets `<target_branch>` for its merge request by default (see that skill) —
`<source_branch>` is only the branch-cut source, kept in sync *from* `<target_branch>` right after
each such PR merges, as the next action at the time, not something to catch later. This check is
only the fallback for when that sync got missed:

```bash
git fetch origin <target_branch>
git log --oneline <source_branch>..origin/<target_branch>
```
If `origin/<target_branch>` doesn't exist for this project, skip this check. Otherwise, if that log lists any commits, `<source_branch>` has drifted behind `<target_branch>`: tell the user plainly what's missing, then merge `origin/<target_branch>` into `<source_branch>` to close the gap (confirm before pushing). Every time this check finds drift — not just the first time — separately ask the user whether to open an issue tracking the recurring gap (e.g. via `git-dev-new-issue` if available); never open one without asking, and never skip asking just because a prior run already asked.

## 2. Fetch tracker updates
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" fetch
```

This overwrites both files in `git-dev.data/tracker/` (via whichever provider is configured;
gitignored, never committed). Read them and summarize only what matters: open issues and merge
requests, milestones, failed or uncovered requirements. If a `github`-backed provider errors (e.g.
`gh` not installed/authenticated), stop and report the error rather than falling back silently.

## 3. Check for opt-in auto mode
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" config auto.enabled false
```
Default is unset/`false` — behavior is unchanged, go straight to step 4. Auto mode chains at most
once per `git-dev-run` session: if a chain already ran in this session, skip this step and go to
step 4.

If it's `true`, this session chains the workflow automatically instead of asking what to do: say
once that auto mode is on, then fetch the gate list and the review toggle:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" config auto.gates ""
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" config auto.review false
```
Split `auto.gates` on commas into short step names (`target`, `plan`, `execute`, `review`,
`update`; a `git-dev-` prefixed name means the same step). Then decide each step's gate:
- **`auto.gates` empty**: every step is **gated** — it still pauses for its own confirmation; auto
  mode only changes who decides to *start* the next step.
- **`auto.gates` non-empty**: a step it names is **gated**; a step it leaves out is **ungated**.
- `git-dev-update` is always gated, whatever the list says (see its own skill).

The chain is `git-dev-target`, `git-dev-plan`, `git-dev-execute`, then `git-dev-review` only if
`auto.review` is `true`, then `git-dev-update`. Start from the first step whose predecessor has a
newer completion date in `state.json` (same selection rule as step 4's manual choice). For each
step, invoke the skill `workflow:<step>`, telling it that this run is in auto mode and whether it
is **gated** or **ungated** (its own "User gate" section acts on exactly that). Stop the chain if
any step reports a failure, a stop condition (e.g. no opened candidates), or asks a question only
a human can answer (e.g. a `blocked_by` ordering conflict in `git-dev-target`) — auto mode chains
the happy path, not past a step that's genuinely stuck. When the chain ends (success or stop), say
how it ended and go to step 4.

## 4. Ask the user what to do
One question, with these options:
- **Run a step**: ask which; the steps run in order, each asks for confirmation and ends with a summary: `git-dev-target` (1), `git-dev-plan` (2), `git-dev-execute` (3), `git-dev-review` (optional), `git-dev-update` (4). Suggest the first step whose predecessor has a newer completion date in `state.json`.
- **Reconfigure**: re-run setup (backend choice and/or the `project-prompt.md` sections) without treating it as first-time setup.
- **Return status**: show the workflow status.

## 5. Act on the choice
- **Run a step**: invoke the skill `workflow:<step>` and follow it.
- **Reconfigure**: invoke the skill `workflow:git-dev-setup` and follow it.
- **Return status**: report the git result from step 1, the tracker summary from step 2, and each step's last completion date from `git-dev.data/state.json` (`never` if absent).

After acting, go back to step 1 and ask again. Stop when the user says so.
