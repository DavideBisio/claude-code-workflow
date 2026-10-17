"""Tests for the validated, scoped step handoff. Run: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "git_dev_data.py"
HANDOFF = ROOT / "scripts" / "handoff_manager.py"
GITIGNORE_TEMPLATE = ROOT / "assets" / "git-dev.data" / ".gitignore"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=cwd)


class ScopedFetch(unittest.TestCase):
    def test_fetch_scopes_to_issue_not_full_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            scope = json.loads(run(HANDOFF, "fetch", "--issue", "2", cwd=tmp).stdout)
            self.assertEqual(scope["issue"]["iid"], 2)
            self.assertEqual([r["id"] for r in scope["requirements"]], ["REQ-2"])
            self.assertEqual([c["id"] for c in scope["coverage"]], ["COV-2"])
            # scoped to issue 2's requirement only, not the full 3-requirement / 3-coverage tracker
            full_req = json.loads(run(ROOT / "mcp" / "mock-req-tracker" / "server.py",
                                      "list_requirements", cwd=tmp).stdout)
            self.assertLess(len(scope["requirements"]), len(full_req))


class WriteValidation(unittest.TestCase):
    def test_write_rejects_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(HANDOFF, "write", "target", '{"issue": {}}', cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            out = json.loads(res.stdout)
            self.assertFalse(out["ok"])
            self.assertIn("requirements", out["error"])

    def test_write_accepts_complete_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            payload = {"issue": {"iid": 2}, "requirements": [], "coverage": [], "code_area": "app/"}
            res = run(HANDOFF, "write", "target", json.dumps(payload), cwd=tmp)
            self.assertEqual(res.returncode, 0)
            self.assertTrue(json.loads(res.stdout)["ok"])


class GetScoping(unittest.TestCase):
    def test_get_returns_only_that_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            payload = {"issue": {"iid": 2}, "requirements": [], "coverage": [], "code_area": "app/"}
            run(HANDOFF, "write", "target", json.dumps(payload), cwd=tmp)
            got = json.loads(run(HANDOFF, "get", "target", cwd=tmp).stdout)
            self.assertEqual(got, payload)
            missing = json.loads(run(HANDOFF, "get", "plan", cwd=tmp).stdout)
            self.assertIn("error", missing)


class GitignoreCoversEphemeralFiles(unittest.TestCase):
    def test_tracker_work_and_state_are_ignored(self):
        text = GITIGNORE_TEMPLATE.read_text(encoding="utf-8")
        for pattern in ("tracker/", "work/", "state.json"):
            self.assertIn(pattern, text)
        self.assertNotIn("config.yaml", text)
        self.assertNotIn("project-prompt.md", text)


if __name__ == "__main__":
    unittest.main()
