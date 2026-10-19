"""github-* provider parsing and real-action calls with `gh` stubbed out (no network), plus the
record-shape contract shared with the mock providers. Run: python -m unittest discover tests"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "mcp"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), MCP / name / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GH_REQ = load("github-req-tracker")
GH_VC = load("github-version-control")


def gh_issue(number, body="", state="OPEN", reason="", labels=()):
    return {"number": number, "title": f"Issue {number}", "state": state, "stateReason": reason,
            "labels": [{"name": l} for l in labels], "assignees": [], "milestone": None,
            "url": f"https://github.com/o/n/issues/{number}", "body": body}


class StubGh:
    """Replaces a server module's gh calls: `views` answers `gh issue view N`, `lists` answers
    list calls, and every `run` (a write) is recorded in `calls`."""

    def __init__(self, module, views=None, lists=(), create_url="https://github.com/o/n/issues/42"):
        self.module, self.views, self.lists, self.create_url = module, views or {}, list(lists), create_url
        self.calls = []

    def __enter__(self):
        self.saved = {n: getattr(self.module, n) for n in ("run", "run_json", "run_list")}
        self.module.run = self.run
        self.module.run_json = self.run_json
        self.module.run_list = lambda args, repo=None: self.lists
        return self

    def __exit__(self, *exc):
        for n, f in self.saved.items():
            setattr(self.module, n, f)

    def run(self, args, repo=None, input_=None):
        self.calls.append(args)
        return self.create_url + "\n" if args[:2] == ["issue", "create"] else ""

    def run_json(self, args, repo=None):
        return self.views[args[2]]


class ReqTrackerParsing(unittest.TestCase):
    def test_coverage_result_from_state_and_reason(self):
        recs = [gh_issue(1, "Refs #10", "CLOSED", "COMPLETED"), gh_issue(2, "Refs #10", "CLOSED", "NOT_PLANNED"),
                gh_issue(3, "Refs #10")]
        with StubGh(GH_REQ, lists=recs):
            out = GH_REQ.list_coverage({})
        self.assertEqual([c["result"] for c in out], ["passed", "not_covered", "not_covered"])

    def test_requirement_link_skips_every_blocking_ref(self):
        with StubGh(GH_REQ, lists=[gh_issue(1, "Blocked by #3, #4\n\nRefs #7")]):
            spec = GH_REQ.list_specifications({})[0]
        self.assertEqual(spec["requirement_id"], "#7")
        self.assertEqual(spec["blocked_by"], ["#3", "#4"])

    def test_get_checks_the_label_with_one_view(self):
        views = {"5": gh_issue(5, labels=["req"]), "6": gh_issue(6, labels=["bug"])}
        with StubGh(GH_REQ, views=views):
            self.assertEqual(GH_REQ.get_requirement({"id": "#5"})["id"], "#5")
            self.assertIn("error", GH_REQ.get_requirement({"id": "#6"}))


class ReqTrackerWrites(unittest.TestCase):
    def test_create_coverage_passed_closes_the_new_issue(self):
        with StubGh(GH_REQ) as gh:
            out = GH_REQ.create_coverage({"requirement_id": "#10", "result": "passed", "testcases": ["TC-1", "TC-2"]})
        self.assertTrue(out["ok"])
        self.assertEqual((out["id"], out["result"]), ("#42", "passed"))
        create, close = gh.calls
        self.assertIn("Testcases: TC-1, TC-2", create[create.index("--body") + 1])
        self.assertEqual(close[:3], ["issue", "close", "42"])
        self.assertIn("completed", close)
        self.assertEqual(close[close.index("--comment") + 1], "Covered by TC-1, TC-2")

    def test_create_coverage_rejects_unknown_result(self):
        with StubGh(GH_REQ) as gh:
            self.assertFalse(GH_REQ.create_coverage({"requirement_id": "#10", "result": "green"})["ok"])
        self.assertEqual(gh.calls, [])

    def test_update_coverage_rejects_unknown_result(self):
        with StubGh(GH_REQ) as gh:
            self.assertFalse(GH_REQ.update_coverage({"id": "#3", "result": "green"})["ok"])
        self.assertEqual(gh.calls, [])

    def test_update_passed_on_closed_issue_still_comments(self):
        with StubGh(GH_REQ, views={"3": {"state": "CLOSED", "stateReason": "COMPLETED"}}) as gh:
            self.assertTrue(GH_REQ.update_coverage({"id": "#3", "result": "passed", "testcases": ["TC-1"]})["ok"])
        self.assertEqual(gh.calls, [["issue", "comment", "3", "--body", "Covered by TC-1"]])

    def test_update_passed_on_not_planned_issue_reopens_then_closes_completed(self):
        with StubGh(GH_REQ, views={"3": {"state": "CLOSED", "stateReason": "NOT_PLANNED"}}) as gh:
            GH_REQ.update_coverage({"id": "#3", "result": "passed", "testcases": ["TC-1"]})
        self.assertEqual([c[:2] for c in gh.calls], [["issue", "reopen"], ["issue", "close"]])

    def test_update_failed_reopens_and_comments(self):
        with StubGh(GH_REQ, views={"3": {"state": "CLOSED", "stateReason": "COMPLETED"}}) as gh:
            GH_REQ.update_coverage({"id": "#3", "result": "failed"})
        self.assertEqual(gh.calls, [["issue", "reopen", "3"], ["issue", "comment", "3", "--body", "Result: failed"]])


class VersionControl(unittest.TestCase):
    def test_issue_requirement_link_skips_blocking_refs(self):
        issue = GH_VC._issue(gh_issue(2, "Blocked by #3, #4"))
        self.assertEqual(issue["requirements"], [])
        self.assertEqual(issue["blocked_by"], ["#3", "#4"])

    def test_merge_request_defaults_to_main(self):
        with StubGh(GH_VC) as gh:
            GH_VC.create_merge_request({"title": "t", "source_branch": "fix/1-x", "closes": [1]})
        args = gh.calls[0]
        self.assertEqual(args[args.index("--base") + 1], "main")

    def test_pipeline_rollup(self):
        self.assertEqual(GH_VC._pipeline([]), "unknown")
        self.assertEqual(GH_VC._pipeline([{"conclusion": "SUCCESS"}]), "passed")
        self.assertEqual(GH_VC._pipeline([{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}]), "failed")
        self.assertEqual(GH_VC._pipeline([{"state": "PENDING"}]), "running")


class McpExposure(unittest.TestCase):
    """The github-* servers are registered in every project; they must expose nothing unless the
    project selects them, and never their real-write tools."""

    def _served(self, server, config=None):
        with tempfile.TemporaryDirectory() as tmp:
            if config:
                (Path(tmp) / "git-dev.data").mkdir()
                (Path(tmp) / "git-dev.data" / "config.yaml").write_text(config, encoding="utf-8")
            msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            res = subprocess.run([sys.executable, str(MCP / server / "server.py")], capture_output=True,
                                 text=True, input=json.dumps(msg) + "\n", cwd=tmp)
            return {t["name"] for t in json.loads(res.stdout)["result"]["tools"]}

    def test_unselected_github_servers_expose_nothing(self):
        self.assertEqual(self._served("github-req-tracker"), set())
        self.assertEqual(self._served("github-version-control", "backends:\n  version_control: mock\n"), set())

    def test_selected_github_servers_expose_only_reads(self):
        for server, config in (("github-req-tracker", "backends:\n  req_tracker: github_labels\n"),
                               ("github-version-control", "backends:\n  version_control: github\n")):
            served = self._served(server, config)
            self.assertTrue(served, server)
            self.assertTrue(all(n.startswith(("list_", "get_")) for n in served), served)


def mock_records(server, tool):
    res = subprocess.run([sys.executable, str(MCP / server / "server.py"), tool], capture_output=True, text=True)
    return json.loads(res.stdout)


class SharedShape(unittest.TestCase):
    """Mock and github records carry the same keys (github adds only `url`), so a skill reading
    one backend's output reads the other's the same way."""

    def assertSameKeys(self, mock, github):
        self.assertEqual(set(mock) - {"url"}, set(github) - {"url"})

    def test_req_tracker_records(self):
        body = "Refs #1"
        self.assertSameKeys(mock_records("mock-req-tracker", "list_requirements")[0], GH_REQ._requirement(gh_issue(1, body)))
        self.assertSameKeys(mock_records("mock-req-tracker", "list_coverage")[0], GH_REQ._coverage(gh_issue(1, body)))
        self.assertSameKeys(mock_records("mock-req-tracker", "list_specifications")[0], GH_REQ._specification(gh_issue(1, body)))

    def test_version_control_records(self):
        self.assertSameKeys(mock_records("mock-version-control", "list_issues")[0], GH_VC._issue(gh_issue(1)))
        pr = {"number": 1, "title": "t", "state": "OPEN", "headRefName": "a", "baseRefName": "main",
              "closingIssuesReferences": [], "statusCheckRollup": [], "url": "u"}
        self.assertSameKeys(mock_records("mock-version-control", "list_merge_requests")[0], GH_VC._mr(pr))

    def test_state_vocabulary(self):
        for tool in ("list_requirements", "list_specifications"):
            self.assertLessEqual({r["state"] for r in mock_records("mock-req-tracker", tool)}, {"opened", "closed"})
        self.assertLessEqual({m["state"] for m in mock_records("mock-version-control", "list_milestones")},
                             {"open", "closed"})


if __name__ == "__main__":
    unittest.main()
