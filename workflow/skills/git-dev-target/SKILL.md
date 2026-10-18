---
name: git-dev-target
description: Workflow step 1 of 4. Reads the existing tracker files, picks the next opened candidate (checking blocking order, including standalone dev specs and plain/todo issues), gathers its requirements and identifies the target. Asks for confirmation, then summarizes.
disable-model-invocation: false
---

# git-dev-target (step 1 of 4: target)

## Setup
Read `git-dev.data/config.yaml` and `git-dev.data/project-prompt.md` in the project root and follow the project prompt throughout.

Work only from the existing tracker files to pick *which* issue; do not fetch them yourself (that
is `git-dev-run`'s job). If the relevant tracker file (see Operation step 1) is missing, stop and
tell the user to run `git-dev-run` first.

If `backends.req_tracker` is `github_labels` (check `config.yaml`): there is no separate `issues`
vs `requirements` concept — the `req`- and `dev`-labeled issues themselves are candidates (see
Operation step 1). A `dev`-labeled issue (specification) with no linked `req`
(`requirement_id: null`) is a normal, valid target on its own — not every feature needs req-level
compliance, so don't treat the absence of a link as an anomaly requiring special confirmation.

Plain issues (no `req`/`test`/`dev` label — e.g. `todo`) are also valid candidates, and under
`github_labels` they don't disappear: the github-version-control provider's `list_issues`
excludes req/test/dev-labeled issues, so `version-control.json`'s opened issues are exactly these
standalone items, to combine with req-tracker's opened requirements/specifications (see Operation
step 1). The distinction that matters: `dev` means an action tied to a requirement (`req` label);
plain/`todo` means an action to take with no requirement tracking at all. Neither needs the other
to be a valid target.

## Operation
1. Build the candidate list of opened items:
   - `backends.req_tracker` is `github_labels`: every opened entry in
     `git-dev.data/tracker/req-tracker.json`'s `requirements` *and* `specifications`, combined with
     every opened issue in `git-dev.data/tracker/version-control.json` (these are disjoint sets —
     the provider excludes req/test/dev-labeled issues from the latter — so just union them).
   - otherwise: every opened issue in `git-dev.data/tracker/version-control.json`.
2. Order the candidates by issue number ascending (lowest first) by default — not by whatever
   order the tracker file happens to list them in (`gh issue list`'s default is newest-first,
   which is not a priority order). Then adjust for context before locking in a pick:
   - Each candidate (github backends only; mock sample data carries no such field, so skip this
     check there) has `blocks`/`blocked_by` lists of issue refs parsed from "Blocks #N"/"Blocked
     by #N" text in its body. If the lowest-numbered open candidate is `blocked_by` another
     still-open candidate, or another still-open candidate's `blocks` names it, don't silently
     proceed with the naive pick — tell the user which issue looks like it should go first and let
     them decide. This is a text heuristic over issue bodies, not an authoritative dependency
     graph, so treat it as a hint to surface, not a hard rule to enforce.
   - Read each candidate's body for signals beyond the `blocks`/`blocked_by` fields: explicit
     deferral ("not scheduled", "address later"), a stated dependency on another open issue even
     without the exact "Blocked by #N" phrasing, or a goal that overlaps/conflicts with another
     open candidate such that doing one first avoids rework on the other. Surface anything that
     would reorder the naive lowest-number pick, and say why, rather than applying the default
     silently.
3. Take the resulting candidate (lowest issue number by default, reordered per the context check
   above when applicable) as the target (its iid).
4. Scope the detail for that one issue only, instead of reading the full req-tracker dump:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" fetch --issue <iid>
```
This calls the req-tracker/version-control providers with an exact-match `filter`, returning just
that issue plus the requirements it references, their `coverage` records and `specifications` —
not every requirement in the tracker.
5. Where the issue text and the requirements disagree, the requirements win; say so. If there are
   no opened candidates, stop and report. A candidate with no linked requirement is a valid target
   on its own (see Setup) — don't stop or ask for special confirmation for that case alone.
6. Identify the target: issue (iid, title), requirements (id, title, status) if any, current
   coverage result and test cases per requirement, and the code area likely affected (mock: a
   one-line guess).

## User gate
If this run was invoked in auto mode with `git-dev-target` excluded from `auto.gates`, skip this
confirmation — state the identified target and proceed directly. Otherwise: before writing
anything, show the identified target and ask the user to confirm it or name a different issue. Do
not continue on a "no".

## Output
Write the confirmed target (validated against its required fields):
`{"issue": {...}, "requirements": [...], "coverage": [...], "code_area": "..."}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" write target '<json above>'
python "${CLAUDE_PLUGIN_ROOT}/scripts/handoff_manager.py" record-step git-dev-target
```

## Summary
Report in a few lines: the issue, its requirements and their coverage state, conflicts or open questions, and that the next step is `git-dev-plan`.

## Behavior
- Don't guess: list missing or conflicting data as open questions.
- Read-only on git; never push.
