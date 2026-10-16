---
name: git-dev-run
description: Orchestrator for the git-dev workflow. Rebases dev, fetches version-control and requirement-tracker data, then asks what to do (run a step, show status). Run manually.
disable-model-invocation: true
---

# git-dev-run

Work from the project root. Helper script: `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py"`. The mock servers also have a JSON CLI (the MCP tools of the same names are equivalent).

## 0. Project data folder
All persistent files live in `git-dev.data/` in the project root and are **committed** (not gitignored):
- `tracker/mock-version-control.json` (`issues`, `merge_requests`, `milestones`) and `tracker/mock-req-tracker.json` (`requirements`, `coverage`, `specifications`, `testplans`): latest tracker output.
- `state.json`: last run completion date per step.
- `work/`: scratch handoff between steps (`target.json`, `plan.md`, `result.json`); gitignored.
- `config.yaml`: skill custom config. `project-prompt.md`: project-specific prompt read by every step.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" init
```

If it reports `created: true`, tell the user to fill in `config.yaml` and `project-prompt.md`.

## 1. Fetch git state and rebase
Git comes first so the tree is clean before `git-dev.data/` is rewritten.

```bash
git branch --show-current
git status --short
```
- The expected branch is `dev`. If on another branch, say so and ask whether to continue; never switch branches without being asked.
- If the working tree is not clean, stop and ask; do not stash or discard anything.
- Otherwise bring `dev` up to the latest remote commit:

```bash
git fetch origin dev
git log --oneline HEAD..origin/dev
git rebase origin/dev
```

- Report the new commits (the `log` output above). If the rebase conflicts, stop, list the conflicting files and ask; use `git rebase --abort` only if the user says so.
- Do not run `git reset` or push.

## 2. Fetch tracker updates
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" fetch
```

This overwrites both files in `git-dev.data/tracker/`. Read them and summarize only what matters: open issues and merge requests, milestones, failed or uncovered requirements. If `git-dev.data/` changed, commit it (this path only, no push):

```bash
git add git-dev.data
git commit -m "chore: update git-dev.data tracker output"
```

## 3. Ask the user what to do
One question, with these options:
- **Run a step**: ask which; the steps run in order, each asks for confirmation and ends with a summary: `git-dev-target` (1), `git-dev-plan` (2), `git-dev-execute` (3), `git-dev-update` (4). Suggest the first step whose predecessor has a newer completion date in `state.json`.
- **Return status**: show the workflow status.

## 4. Act on the choice
- **Run a step**: invoke the skill `workflow:<step>` and follow it.
- **Return status**: report the git result from step 1, the tracker summary from step 2, and each step's last completion date from `git-dev.data/state.json` (`never` if absent).

After acting, go back to step 1 and ask again. Stop when the user says so.
