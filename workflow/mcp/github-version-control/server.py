"""GitHub-backed `github-version-control`: issues, pull requests (as `merge_requests`),
milestones, via the `gh` CLI against the current directory's repo (override with
`github.repo` in `git-dev.data/config.yaml`).

Unlike the mock servers, `create_*`/`update_*` perform real actions on the real repo. `create_issue`
excludes the `req`/`test`/`dev` labels (that's the req-tracker's namespace); there is no
`create_milestone`/`update_milestone` yet. Ids are
GitHub issue/PR numbers formatted as `"#<number>"`, matching GitHub's own reference syntax, so
cross-links between issues (see github-req-tracker) use the same token everywhere.

Each issue also carries `blocks`/`blocked_by`: `#<number>` refs parsed from "Blocks #N"/"Blocked by
#N" text in its body (see `ghcli.blocking_refs`) — a text heuristic, not GitHub's native sub-issue
relationship, used by `git-dev-target` to avoid picking an issue out of order.

Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from ghcli import run, run_json, first_ref, blocking_refs  # noqa: E402
from miniconfig import load as load_config, get as config_get  # noqa: E402
from mockmcp import run_tools  # noqa: E402

CONFIG = load_config("git-dev.data/config.yaml")
REPO = config_get(CONFIG, "github.repo")

ISSUE_FIELDS = "number,title,state,labels,assignees,milestone,url,body"
PR_FIELDS = "number,title,state,headRefName,baseRefName,closingIssuesReferences,statusCheckRollup,url,body"
TRACKER_LABELS = {config_get(CONFIG, f"github.labels.{k}", default) for k, default in
                  (("requirement", "req"), ("test", "test"), ("dev", "dev"))}


def _state(raw):
    return {"OPEN": "opened", "CLOSED": "closed", "MERGED": "merged"}.get(raw, raw.lower())


def _issue(rec):
    labels = [l["name"] for l in rec.get("labels", [])]
    body = rec.get("body", "")
    blocks, blocked_by = blocking_refs(body)
    req_ref = first_ref(body, exclude=blocks + blocked_by)
    return {
        "id": f"#{rec['number']}", "iid": rec["number"], "title": rec["title"],
        "state": _state(rec["state"]), "milestone_id": (rec.get("milestone") or {}).get("number"),
        "labels": labels, "assignee": next((a["login"] for a in rec.get("assignees", [])), None),
        "requirements": [req_ref] if req_ref else [],
        "blocks": blocks, "blocked_by": blocked_by,
        "url": rec.get("url"),
    }


def _pipeline(rollup):
    if not rollup:
        return "unknown"
    states = {c.get("conclusion") or c.get("state") for c in rollup}
    if "FAILURE" in states or "ERROR" in states:
        return "failed"
    if states - {"SUCCESS"}:
        return "running"
    return "passed"


def _mr(rec):
    return {
        "id": f"#{rec['number']}", "iid": rec["number"], "title": rec["title"],
        "state": _state(rec["state"]), "source_branch": rec["headRefName"], "target_branch": rec["baseRefName"],
        "pipeline": _pipeline(rec.get("statusCheckRollup")),
        "closes": [r["number"] for r in rec.get("closingIssuesReferences", [])], "url": rec.get("url"),
    }


def list_issues(args):
    recs = run_json(["issue", "list", "--state", "all", "--json", ISSUE_FIELDS, "--limit", "200"], repo=REPO) or []
    recs = [r for r in recs if not TRACKER_LABELS & {l["name"] for l in r.get("labels", [])}]
    out = [_issue(r) for r in recs]
    flt = args.get("filter") or {}
    return [r for r in out if all(r.get(k) == v for k, v in flt.items())]


def get_issue(args):
    num = str(args.get("id", "")).lstrip("#")
    try:
        return _issue(run_json(["issue", "view", num, "--json", ISSUE_FIELDS], repo=REPO))
    except Exception as e:
        return {"error": str(e), "id": args.get("id")}


def create_issue(args):
    title, body = args.get("title", ""), args.get("body", "")
    labels = [l for l in (args.get("labels") or []) if l not in TRACKER_LABELS]
    gh_args = ["issue", "create", "--title", title, "--body", body]
    for l in labels:
        gh_args += ["--label", l]
    if args.get("assignee"):
        gh_args += ["--assignee", args["assignee"]]
    try:
        url = run(gh_args, repo=REPO).strip()
        return {"ok": True, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_issue(args):
    num = str(args.get("id", "")).lstrip("#")
    state = args.get("state")
    try:
        if state == "closed":
            run(["issue", "close", num], repo=REPO)
        elif state == "opened":
            run(["issue", "reopen", num], repo=REPO)
        if args.get("comment"):
            run(["issue", "comment", num, "--body", args["comment"]], repo=REPO)
        return {"ok": True, "id": args.get("id"), "state": state}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_merge_requests(args):
    recs = run_json(["pr", "list", "--state", "all", "--json", PR_FIELDS, "--limit", "200"], repo=REPO) or []
    out = [_mr(r) for r in recs]
    flt = args.get("filter") or {}
    return [r for r in out if all(r.get(k) == v for k, v in flt.items())]


def get_merge_request(args):
    num = str(args.get("id", "")).lstrip("#")
    try:
        return _mr(run_json(["pr", "view", num, "--json", PR_FIELDS], repo=REPO))
    except Exception as e:
        return {"error": str(e), "id": args.get("id")}


def create_merge_request(args):
    title, source, target = args.get("title", ""), args.get("source_branch"), args.get("target_branch", "dev")
    body_lines = [args.get("body", "")] + [f"Closes #{n}" for n in args.get("closes", [])]
    gh_args = ["pr", "create", "--title", title, "--base", target, "--body", "\n".join(filter(None, body_lines))]
    if source:
        gh_args += ["--head", source]
    try:
        url = run(gh_args, repo=REPO).strip()
        return {"ok": True, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_milestones(args):
    recs = run_json(["api", f"repos/{REPO or '{owner}/{repo}'}/milestones", "--paginate"], repo=None) or []
    out = [{"id": r["number"], "title": r["title"], "state": r["state"], "due_date": r.get("due_on")} for r in recs]
    flt = args.get("filter") or {}
    return [r for r in out if all(r.get(k) == v for k, v in flt.items())]


def get_milestone(args):
    try:
        r = run_json(["api", f"repos/{REPO or '{owner}/{repo}'}/milestones/{args.get('id')}"], repo=None)
        return {"id": r["number"], "title": r["title"], "state": r["state"], "due_date": r.get("due_on")}
    except Exception as e:
        return {"error": str(e), "id": args.get("id")}


TOOLS = {
    "list_issues": ("List issues (excludes req/test/dev-labeled ones; those are the req-tracker). Optional exact-match `filter`.", list_issues),
    "get_issue": ("Get one issue by `id` (\"#<number>\").", get_issue),
    "create_issue": ("Open a real issue: `title`, optional `body`, `labels` (req/test/dev excluded), `assignee`.", create_issue),
    "update_issue": ("Close/reopen (`state`=closed/opened) and/or comment on an issue by `id`.", update_issue),
    "list_merge_requests": ("List pull requests. Optional exact-match `filter`.", list_merge_requests),
    "get_merge_request": ("Get one pull request by `id` (\"#<number>\").", get_merge_request),
    "create_merge_request": ("Open a real pull request: `title`, `source_branch`, `target_branch`, optional `body`, `closes` (issue numbers).", create_merge_request),
    "list_milestones": ("List milestones. Optional exact-match `filter`.", list_milestones),
    "get_milestone": ("Get one milestone by `id`.", get_milestone),
}

if __name__ == "__main__":
    run_tools("github-version-control", TOOLS)
