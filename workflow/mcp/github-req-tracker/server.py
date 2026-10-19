"""GitHub-backed `github-req-tracker`: requirements, coverage and specifications derived from
labeled GitHub issues (no separate tracker). Labels come from `git-dev.data/config.yaml`'s
`github.labels` (defaults: `req`, `test`, `dev`):

- `requirements` <- issues labeled `req`.
- `coverage`     <- issues labeled `test`; each one IS its own testcase. `requirement_id` is the
  first `#<number>` reference found in the issue's body (the req it covers). `result` is "passed"
  if closed as completed, else "not_covered" (open, or closed as not planned).
- `specifications` <- issues labeled `dev`, same linking. There is no GitHub concept of a
  specification; these are planned dev actions, repurposed into this slot so the skills (which just
  display whatever is here) still surface them. `requirement_id` is `None` when the body has no
  `#<number>` reference — a standalone dev action with no linked requirement is a valid target on
  its own, not an anomaly (not every feature needs req-level compliance).
- `testplans` is always empty: no fourth label is defined for it.
- `requirements`/`specifications` also carry `blocks`/`blocked_by`: `#<number>` refs parsed from
  "Blocks #N"/"Blocked by #N" text in the body (see `ghcli.blocking_refs`) — a text heuristic, not
  GitHub's native sub-issue relationship, used by `git-dev-target` to avoid picking a target out of
  order.

Record shapes match `mock-req-tracker` (same keys, `state` is `opened`/`closed`, specifications
link to their requirement via `requirement_id`); `tests/test_providers.py` checks that.

Ids are GitHub issue numbers formatted as `"#<number>"`. Unlike the mock server, `create_*`/
`update_*` perform real actions (open/close/comment on real issues). `create_requirement` and
`create_specification` open `req`-/`dev`-labeled issues directly; only coverage has an `update_*`
(close/reopen a test issue) since requirements and specifications have no result to flip here.
As a live MCP server it exposes only the read tools, and only when `backends.req_tracker` is
`github_labels` (see `ghcli.mcp_served`).

Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from ghcli import run, run_json, run_list, first_ref, blocking_refs, mcp_served  # noqa: E402
from miniconfig import load as load_config, get as config_get  # noqa: E402
from mockmcp import run_tools  # noqa: E402

CONFIG = load_config("git-dev.data/config.yaml")
REPO = config_get(CONFIG, "github.repo")
LABELS = {k: config_get(CONFIG, f"github.labels.{k}", default) for k, default in
          (("requirement", "req"), ("test", "test"), ("dev", "dev"))}
RESULTS = ("passed", "failed", "not_covered")

FIELDS = "number,title,state,stateReason,labels,url,body"


def _state(raw):
    return {"OPEN": "opened", "CLOSED": "closed"}.get(raw, raw.lower())


def _requirement(r):
    blocks, blocked_by = blocking_refs(r.get("body", ""))
    return {"id": f"#{r['number']}", "title": r["title"], "state": _state(r["state"]),
            "blocks": blocks, "blocked_by": blocked_by, "url": r.get("url")}


def _coverage(r):
    body = r.get("body", "")
    blocks, blocked_by = blocking_refs(body)
    passed = r["state"] == "CLOSED" and r.get("stateReason") != "NOT_PLANNED"
    return {"id": f"#{r['number']}", "requirement_id": first_ref(body, exclude=blocks + blocked_by),
            "testcases": [f"#{r['number']}"], "result": "passed" if passed else "not_covered",
            "title": r["title"], "url": r.get("url")}


def _specification(r):
    body = r.get("body", "")
    blocks, blocked_by = blocking_refs(body)
    return {"id": f"#{r['number']}", "requirement_id": first_ref(body, exclude=blocks + blocked_by),
            "title": r["title"], "state": _state(r["state"]),
            "blocks": blocks, "blocked_by": blocked_by, "url": r.get("url")}


# resource -> (label key, record mapper)
KINDS = {"requirement": ("requirement", _requirement), "coverage": ("test", _coverage),
         "specification": ("dev", _specification)}


def _list(kind, args):
    label, mapper = KINDS[kind]
    recs = run_list(["issue", "list", "--label", LABELS[label], "--state", "all", "--json", FIELDS], repo=REPO)
    out = [mapper(r) for r in recs]
    flt = args.get("filter") or {}
    return [r for r in out if all(r.get(k) == v for k, v in flt.items())]


def _get(kind, args):
    """One `gh issue view` instead of re-listing every issue of that label."""
    label, mapper = KINDS[kind]
    num = str(args.get("id", "")).lstrip("#")
    try:
        r = run_json(["issue", "view", num, "--json", FIELDS], repo=REPO)
    except Exception as e:
        return {"error": str(e), "id": args.get("id")}
    if LABELS[label] not in {l["name"] for l in r.get("labels", [])}:
        return {"error": f"#{num} is not labeled `{LABELS[label]}` (not a {kind})", "id": args.get("id")}
    return mapper(r)


def _number(url):
    """Issue number from the URL `gh issue create` prints (".../issues/<n>")."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def _create(label, title, body):
    try:
        url = run(["issue", "create", "--title", title, "--body", body, "--label", label], repo=REPO).strip()
        return {"ok": True, "id": f"#{_number(url)}", "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _covered_by(testcases):
    return f"Covered by {', '.join(testcases)}" if testcases else "Result: passed"


def list_requirements(args):
    return _list("requirement", args)


def get_requirement(args):
    return _get("requirement", args)


def create_requirement(args):
    return _create(LABELS["requirement"], args.get("title") or "Untitled requirement", args.get("body", ""))


def list_coverage(args):
    return _list("coverage", args)


def get_coverage(args):
    return _get("coverage", args)


def create_coverage(args):
    """Open a test issue for `requirement_id`. With `result: "passed"` it is closed right away (a
    closed test issue is what reads back as `passed`), so new coverage doesn't show as uncovered."""
    result = args.get("result")
    if result is not None and result not in RESULTS:
        return {"ok": False, "error": f"unknown result {result!r}; expected one of {list(RESULTS)}"}
    req_id = str(args.get("requirement_id", "")).lstrip("#")
    testcases = args.get("testcases") or []
    title = args.get("title") or f"Test for #{req_id}"
    body = f"Refs #{req_id}\n\n" + (f"Testcases: {', '.join(testcases)}\n\n" if testcases else "") + args.get("body", "")
    out = _create(LABELS["test"], title, body)
    if not out["ok"] or result is None:
        return out
    num = out["id"].lstrip("#")
    try:
        if result == "passed":
            run(["issue", "close", num, "--reason", "completed", "--comment", _covered_by(testcases)], repo=REPO)
        else:
            run(["issue", "comment", num, "--body", f"Result: {result}"], repo=REPO)
    except Exception as e:
        return {**out, "ok": False, "error": f"created {out['url']} but could not record result: {e}"}
    return {**out, "result": result}


def update_coverage(args):
    num = str(args.get("id", "")).lstrip("#")
    result = args.get("result")
    if result not in RESULTS:
        return {"ok": False, "error": f"unknown result {result!r}; expected one of {list(RESULTS)}"}
    testcases = args.get("testcases") or []
    try:
        cur = run_json(["issue", "view", num, "--json", "state,stateReason"], repo=REPO)
        closed = cur["state"] == "CLOSED"
        if result == "passed":
            if closed and cur.get("stateReason") != "NOT_PLANNED":
                run(["issue", "comment", num, "--body", _covered_by(testcases)], repo=REPO)
            else:
                if closed:  # closed as not planned: reopen so it can be closed as completed
                    run(["issue", "reopen", num], repo=REPO)
                run(["issue", "close", num, "--reason", "completed", "--comment", _covered_by(testcases)], repo=REPO)
        else:
            if closed:
                run(["issue", "reopen", num], repo=REPO)
            suffix = f" ({', '.join(testcases)})" if testcases else ""
            run(["issue", "comment", num, "--body", f"Result: {result}{suffix}"], repo=REPO)
        return {"ok": True, "id": args.get("id"), "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_specifications(args):
    return _list("specification", args)


def get_specification(args):
    return _get("specification", args)


def create_specification(args):
    req_id = str(args.get("requirement_id", "")).lstrip("#")
    title = args.get("title") or (f"Dev action for #{req_id}" if req_id else "Untitled dev action")
    body = (f"Refs #{req_id}\n\n" if req_id else "") + args.get("body", "")
    return _create(LABELS["dev"], title, body)


def list_testplans(args):
    return []


TOOLS = {
    "list_requirements": (f"List requirements (issues labeled `{LABELS['requirement']}`). Optional exact-match `filter`.", list_requirements),
    "get_requirement": ("Get one requirement by `id` (\"#<number>\").", get_requirement),
    "create_requirement": (f"Open a real requirement issue labeled `{LABELS['requirement']}`: optional `title`/`body`.", create_requirement),
    "list_coverage": (f"List coverage records (issues labeled `{LABELS['test']}`). Optional exact-match `filter`.", list_coverage),
    "get_coverage": ("Get one coverage record by `id`.", get_coverage),
    "create_coverage": ("Open a real test issue for a requirement: `requirement_id`, optional `title`/`body`/`testcases`, and `result` (passed closes it as completed).", create_coverage),
    "update_coverage": ("Close as completed (result=passed) or reopen+comment (result=failed/not_covered) a test issue by `id`, with optional `testcases`.", update_coverage),
    "list_specifications": (f"List dev actions (issues labeled `{LABELS['dev']}`), repurposed into this slot. Optional exact-match `filter`.", list_specifications),
    "get_specification": ("Get one dev-action record by `id`.", get_specification),
    "create_specification": (f"Open a real dev-action issue labeled `{LABELS['dev']}`: optional `requirement_id`, `title`/`body`.", create_specification),
    "list_testplans": ("Always empty: no label is defined for testplans.", list_testplans),
}

if __name__ == "__main__":
    run_tools("github-req-tracker", TOOLS,
              served=mcp_served(TOOLS, config_get(CONFIG, "backends.req_tracker") == "github_labels"))
