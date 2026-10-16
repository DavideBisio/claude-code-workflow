"""GitHub-backed `github-req-tracker`: requirements, coverage and specifications derived from
labeled GitHub issues (no separate tracker). Labels come from `git-dev.data/config.yaml`'s
`github.labels` (defaults: `req`, `test`, `dev`):

- `requirements` <- issues labeled `req`.
- `coverage`     <- issues labeled `test`; each one IS its own testcase. `requirement_id` is the
  first `#<number>` reference found in the issue's body (the req it covers). `result` is "passed"
  if closed, else "not_covered".
- `specifications` <- issues labeled `dev`, same linking. There is no GitHub concept of a
  specification; these are planned dev actions for a requirement, repurposed into this slot so the
  skills (which just display whatever is here) still surface them.
- `testplans` is always empty: no fourth label is defined for it.

Ids are GitHub issue numbers formatted as `"#<number>"`. Unlike the mock server, `create_*`/
`update_*` perform real actions (open/close/comment on real issues).

Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from ghcli import run, run_json, first_ref  # noqa: E402
from miniconfig import load as load_config, get as config_get  # noqa: E402
from mockmcp import run_tools  # noqa: E402

CONFIG = load_config("git-dev.data/config.yaml")
REPO = config_get(CONFIG, "github.repo")
LABELS = {k: config_get(CONFIG, f"github.labels.{k}", default) for k, default in
          (("requirement", "req"), ("test", "test"), ("dev", "dev"))}

FIELDS = "number,title,state,url,body"


def _by_label(label):
    return run_json(["issue", "list", "--label", label, "--state", "all", "--json", FIELDS,
                      "--limit", "200"], repo=REPO) or []


def _filtered(records, flt):
    return [r for r in records if all(r.get(k) == v for k, v in flt.items())]


def list_requirements(args):
    out = [{"id": f"#{r['number']}", "title": r["title"],
            "status": {"OPEN": "opened", "CLOSED": "closed"}.get(r["state"], r["state"].lower()),
            "specification_id": None, "url": r.get("url")}
           for r in _by_label(LABELS["requirement"])]
    return _filtered(out, args.get("filter") or {})


def list_coverage(args):
    out = []
    for r in _by_label(LABELS["test"]):
        req_id = first_ref(r.get("body", ""))
        out.append({"id": f"#{r['number']}", "requirement_id": req_id, "testcases": [f"#{r['number']}"],
                    "result": "passed" if r["state"] == "CLOSED" else "not_covered",
                    "title": r["title"], "url": r.get("url")})
    return _filtered(out, args.get("filter") or {})


def list_specifications(args):
    out = []
    for r in _by_label(LABELS["dev"]):
        req_id = first_ref(r.get("body", ""))
        out.append({"id": f"#{r['number']}", "requirement_id": req_id, "title": r["title"],
                    "state": {"OPEN": "opened", "CLOSED": "closed"}.get(r["state"], r["state"].lower()),
                    "url": r.get("url")})
    return _filtered(out, args.get("filter") or {})


def list_testplans(args):
    return []


def _get(lister, args):
    want = str(args.get("id", ""))
    for r in lister({}):
        if r["id"] == want or r["id"].lstrip("#") == want.lstrip("#"):
            return r
    return {"error": "not found", "id": args.get("id")}


def get_requirement(args):
    return _get(list_requirements, args)


def get_coverage(args):
    return _get(list_coverage, args)


def get_specification(args):
    return _get(list_specifications, args)


def create_coverage(args):
    req_id = str(args.get("requirement_id", "")).lstrip("#")
    title = args.get("title") or f"Test for #{req_id}"
    body = f"Refs #{req_id}\n\n" + args.get("body", "")
    try:
        url = run(["issue", "create", "--title", title, "--body", body,
                   "--label", LABELS["test"]], repo=REPO).strip()
        return {"ok": True, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_coverage(args):
    num = str(args.get("id", "")).lstrip("#")
    result = args.get("result")
    try:
        if result == "passed":
            run(["issue", "close", num, "--comment", f"Covered by {args.get('testcases', [])}"], repo=REPO)
        elif result in ("failed", "not_covered"):
            run(["issue", "reopen", num], repo=REPO)
            run(["issue", "comment", num, "--body", f"Result: {result}"], repo=REPO)
        return {"ok": True, "id": args.get("id"), "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


TOOLS = {
    "list_requirements": (f"List requirements (issues labeled `{LABELS['requirement']}`). Optional exact-match `filter`.", list_requirements),
    "get_requirement": ("Get one requirement by `id` (\"#<number>\").", get_requirement),
    "list_coverage": (f"List coverage records (issues labeled `{LABELS['test']}`). Optional exact-match `filter`.", list_coverage),
    "get_coverage": ("Get one coverage record by `id`.", get_coverage),
    "create_coverage": ("Open a real test issue for a requirement: `requirement_id`, optional `title`/`body`.", create_coverage),
    "update_coverage": ("Close (result=passed) or reopen+comment (result=failed/not_covered) a test issue by `id`.", update_coverage),
    "list_specifications": (f"List dev actions (issues labeled `{LABELS['dev']}`), repurposed into this slot. Optional exact-match `filter`.", list_specifications),
    "get_specification": ("Get one dev-action record by `id`.", get_specification),
    "list_testplans": ("Always empty: no label is defined for testplans.", list_testplans),
}

if __name__ == "__main__":
    run_tools("github-req-tracker", TOOLS)
