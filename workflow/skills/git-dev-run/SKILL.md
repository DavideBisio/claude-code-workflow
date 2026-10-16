---
name: git-dev-run
description: Orchestrator for the git-dev workflow. Rebases dev, fetches version-control and requirement-tracker data, then asks what to do (run a step, show status). Run manually.
disable-model-invocation: true
---

# git-dev-run

Work from the project root. Helper script: `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py"`. Every provider (mock or github-backed) also has a JSON CLI (the MCP tools of the same names are equivalent).

## 0. Project data folder
All persistent files live in `git-dev.data/` in the project root and are **committed** (not gitignored):
- `tracker/version-control.json` (`issues`, `merge_requests`, `milestones`) and `tracker/req-tracker.json` (`requirements`, `coverage`, `specifications`, `testplans`): latest tracker output. Each is produced by whichever provider `config.yaml`'s `backends.version_control` / `backends.req_tracker` names (defaults to the mock servers; see the commented example in `config.yaml` for the `github` / `github_labels` options). Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" provider version_control` (or `req_tracker`) to see which is active.
- `state.json`: last run completion date per step.
- `work/`: scratch handoff between steps (`target.json`, `plan.md`, `result.json`); gitignored.
- `config.yaml`: skill custom config. `project-prompt.md`: project-specific prompt read by every step.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" init
```

If it reports `created: true`, this is first-time setup — pick a backend for each tracker before anything else runs:
1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" providers` to get the valid choices per tracker kind (`version_control`, `req_tracker`). Never hardcode backend names in this step; always ask the script.
2. Ask the user which choice to use for `version_control` and which for `req_tracker`. If no human is present to ask (e.g. a pre-approved/automated run), default both to `mock` and say so.
3. Save each answer: `python "${CLAUDE_PLUGIN_ROOT}/scripts/git_dev_data.py" set-backend <kind> <value>`.
4. Tell the user to fill in `project-prompt.md`, and — if they picked anything other than the defaults — to review the matching section in `config.yaml` (e.g. `github:` for repo/label overrides) before the first real run.

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

This overwrites both files in `git-dev.data/tracker/` (via whichever provider is configured). Read them and summarize only what matters: open issues and merge requests, milestones, failed or uncovered requirements. If a `github`-backed provider errors (e.g. `gh` not installed/authenticated), stop and report the error rather than falling back silently. If `git-dev.data/` changed, commit it (this path only, no push):

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
