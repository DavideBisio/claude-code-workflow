"""Smoke tests for the mock servers and the data script. Run: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "mcp" / "mock-version-control" / "server.py"
REQ = ROOT / "mcp" / "mock-req-tracker" / "server.py"
DATA = ROOT / "scripts" / "git_dev_data.py"


def run(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, input=stdin)


class MockServers(unittest.TestCase):
    def test_list_with_filter(self):
        out = json.loads(run(DEV, "list_issues", '{"filter":{"state":"opened"}}').stdout)
        self.assertEqual([i["iid"] for i in out], [2, 3])

    def test_first_opened_issue_maps_to_failing_requirement(self):
        issue = json.loads(run(DEV, "list_issues", '{"filter":{"state":"opened"}}').stdout)[0]
        cov = json.loads(run(REQ, "list_coverage").stdout)
        by_req = {c["requirement_id"]: c for c in cov}
        self.assertEqual(by_req[issue["requirements"][0]]["result"], "failed")

    def test_create_and_update_are_acks(self):
        for server, tool in ((DEV, "create_merge_request"), (REQ, "update_coverage")):
            out = json.loads(run(server, tool, '{"id":"x"}').stdout)
            self.assertTrue(out["ok"] and out["mock"])

    def test_unknown_tool_fails(self):
        res = run(DEV, "nope")
        self.assertEqual(res.returncode, 1)
        self.assertIn("error", json.loads(res.stdout))

    def test_stdio_roundtrip(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "get_requirement", "arguments": {"id": "REQ-2"}}}]
        res = run(REQ, stdin="\n".join(json.dumps(m) for m in msgs) + "\n")
        replies = [json.loads(line) for line in res.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "mock-req-tracker")
        self.assertIn("update_coverage", [t["name"] for t in replies[1]["result"]["tools"]])
        self.assertIn("REQ-2", replies[2]["result"]["content"][0]["text"])


class DataScript(unittest.TestCase):
    def test_init_fetch_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(json.loads(run(DATA, "init", cwd=tmp).stdout)["created"])
            self.assertFalse(json.loads(run(DATA, "init", cwd=tmp).stdout)["created"])
            run(DATA, "fetch", cwd=tmp)
            dev = json.loads((Path(tmp) / "git-dev.data/tracker/mock-version-control.json").read_text())
            req = json.loads((Path(tmp) / "git-dev.data/tracker/mock-req-tracker.json").read_text())
            self.assertEqual(len(dev["issues"]), 3)
            self.assertEqual(len(req["requirements"]), 3)
            run(DATA, "record-step", "git-dev-target", cwd=tmp)
            state = json.loads((Path(tmp) / "git-dev.data/state.json").read_text())
            self.assertIn("git-dev-target", state)


if __name__ == "__main__":
    unittest.main()
