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


TARGET = {"issue": {"iid": 2}, "requirements": [], "coverage": [], "code_area": "app/"}
PLAN = {"branch": "fix/2-x", "test": "t", "fix": "f", "verification": "v",
        "commit_message": "m", "tracker_updates": []}
RESULT = {"branch": "fix/2-x", "commit": "abc", "test_id": "TC-4", "test_before": "failed",
          "test_after": "passed"}


def run(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd, input=stdin)


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


class StdinWrite(unittest.TestCase):
    def test_write_dash_reads_payload_from_stdin(self):
        target = {**TARGET, "issue": {"iid": 2, "title": "Don't crash on 'x' $(touch pwned) ü"}}
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(HANDOFF, "write", "target", "-", cwd=tmp, stdin=json.dumps(target, ensure_ascii=False))
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(json.loads(run(HANDOFF, "get", "target", cwd=tmp).stdout), target)
            self.assertFalse((Path(tmp) / "pwned").exists())

    def test_write_rejects_non_object_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(HANDOFF, "write", "target", "-", cwd=tmp,
                      stdin=json.dumps(["issue", "requirements", "coverage", "code_area"]))
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("JSON object", json.loads(res.stdout)["error"])


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


class PromptSection(unittest.TestCase):
    def test_extracts_section_body_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            prompt_path = Path(tmp) / "git-dev.data" / "project-prompt.md"
            prompt_path.write_text(
                "# Project prompt\n\n"
                "## Branching strategy\n"
                "- source_branch: dev\n"
                "- target_branch: main\n\n"
                "## Issue labels\n"
                "- todo\n", encoding="utf-8")
            out = json.loads(run(HANDOFF, "prompt-section", "branching strategy", cwd=tmp).stdout)
            self.assertEqual(out["heading"], "branching strategy")
            self.assertIn("source_branch: dev", out["text"])
            self.assertNotIn("Issue labels", out["text"])

    def test_missing_heading_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(HANDOFF, "prompt-section", "Nonexistent Section", cwd=tmp).stdout)
            self.assertIsNone(out["text"])

    def test_shipped_placeholder_sections_return_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            for heading in ("Issue labels", "Test commands", "Pre-PR checklist"):
                out = json.loads(run(HANDOFF, "prompt-section", heading, cwd=tmp).stdout)
                self.assertIsNone(out["text"], heading)

    def test_shipped_branching_values_are_used_without_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(HANDOFF, "prompt-section", "Branching strategy", cwd=tmp).stdout)
            self.assertIn("source_branch: dev", out["text"])
            self.assertNotIn("<!--", out["text"])

    def test_customized_line_next_to_placeholder_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "project-prompt.md").write_text(
                "## Test commands\n"
                "- python -m unittest\n"
                "- <e2e / integration test command, if any>\n"
                "<!-- Default if unchanged or missing: none assumed. -->\n", encoding="utf-8")
            out = json.loads(run(HANDOFF, "prompt-section", "Test commands", cwd=tmp).stdout)
            self.assertIn("python -m unittest", out["text"])
            self.assertNotIn("Default if", out["text"])


class WriteTypeValidation(unittest.TestCase):
    def test_write_rejects_wrong_type_for_known_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            payload = {"branch": "fix/1-x", "test": "t", "fix": "f", "verification": "v",
                       "commit_message": "m", "tracker_updates": "not-a-list-or-dict"}
            res = run(HANDOFF, "write", "plan", json.dumps(payload), cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            out = json.loads(res.stdout)
            self.assertFalse(out["ok"])
            self.assertIn("tracker_updates", out["error"])

    def test_write_accepts_correct_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            run(HANDOFF, "write", "target", json.dumps(TARGET), cwd=tmp)
            payload = {"branch": "fix/1-x", "test": "t", "fix": "f", "verification": "v",
                       "commit_message": "m", "tracker_updates": []}
            res = run(HANDOFF, "write", "plan", json.dumps(payload), cwd=tmp)
            self.assertEqual(res.returncode, 0)
            self.assertTrue(json.loads(res.stdout)["ok"])


class Staleness(unittest.TestCase):
    def test_new_target_clears_previous_plan_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            for section, payload in (("target", TARGET), ("plan", PLAN), ("result", RESULT)):
                self.assertEqual(run(HANDOFF, "write", section, json.dumps(payload), cwd=tmp).returncode, 0)
            new_target = {**TARGET, "issue": {"iid": 3}}
            run(HANDOFF, "write", "target", json.dumps(new_target), cwd=tmp)
            self.assertEqual(json.loads(run(HANDOFF, "get", "target", cwd=tmp).stdout), new_target)
            for section in ("plan", "result"):
                self.assertIn("error", json.loads(run(HANDOFF, "get", section, cwd=tmp).stdout), section)

    def test_new_plan_clears_previous_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            for section, payload in (("target", TARGET), ("plan", PLAN), ("result", RESULT), ("plan", PLAN)):
                run(HANDOFF, "write", section, json.dumps(payload), cwd=tmp)
            self.assertIn("error", json.loads(run(HANDOFF, "get", "result", cwd=tmp).stdout))

    def test_fetch_keeps_in_flight_target_plan_and_result(self):
        """fetch is git-dev-target's lookup, run before its gate: backing out (or starting it by
        mistake mid-cycle) must not discard the approved plan or the execute result."""
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            for section, payload in (("target", TARGET), ("plan", PLAN), ("result", RESULT)):
                run(HANDOFF, "write", section, json.dumps(payload), cwd=tmp)
            run(HANDOFF, "fetch", "--issue", "3", cwd=tmp)
            self.assertEqual(json.loads(run(HANDOFF, "get", "scope", cwd=tmp).stdout)["issue"]["iid"], 3)
            for section, payload in (("target", TARGET), ("plan", PLAN), ("result", RESULT)):
                self.assertEqual(json.loads(run(HANDOFF, "get", section, cwd=tmp).stdout), payload, section)

    def test_section_needs_its_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(HANDOFF, "write", "plan", json.dumps(PLAN), cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("target", json.loads(res.stdout)["error"])
            run(HANDOFF, "write", "target", json.dumps(TARGET), cwd=tmp)
            res = run(HANDOFF, "write", "result", json.dumps(RESULT), cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("plan", json.loads(res.stdout)["error"])


def _stub_provider(path, resources):
    """A provider script serving RESOURCES through the shared mock harness."""
    path.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'mcp' / 'common')!r})\n"
        "from mockmcp import run\n"
        f"run('stub', {resources!r})\n", encoding="utf-8")


class FetchScope(unittest.TestCase):
    def test_not_found_issue_is_an_error_not_a_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(HANDOFF, "fetch", "--issue", "99", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("error", json.loads(res.stdout))
            self.assertIn("error", json.loads(run(HANDOFF, "get", "scope", cwd=tmp).stdout))

    def test_requirement_issue_is_its_own_requirement_when_issue_backed(self):
        # Under github_labels a `req` issue is the requirement; its coverage hangs off its own id,
        # and a body ref (#1) that isn't a requirement is a warning, not a requirement entry.
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            vc, req = Path(tmp) / "vc.py", Path(tmp) / "req.py"
            _stub_provider(vc, {"issue": ("issues", [{"id": "#5", "iid": 5, "requirements": ["#1"]}])})
            _stub_provider(req, {
                "requirement": ("requirements", [{"id": "#5", "title": "R", "state": "opened"}]),
                "coverage": ("coverage", [{"id": "#9", "requirement_id": "#5"}]),
                "specification": ("specifications", [{"id": "#8", "requirement_id": "#5"}]),
            })
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  version_control: vc\n  req_tracker: rq\n"
                f"providers:\n  vc:\n    kind: version_control\n    command: {sys.executable}\n    args: {vc}\n"
                f"  rq:\n    kind: req_tracker\n    command: {sys.executable}\n    args: {req}\n"
                "    issue_backed: true\n", encoding="utf-8")
            res = run(HANDOFF, "fetch", "--issue", "#5", cwd=tmp)
            self.assertEqual(res.returncode, 0, res.stderr)
            scope = json.loads(res.stdout)
            self.assertEqual([r["id"] for r in scope["requirements"]], ["#5"])
            self.assertEqual([c["id"] for c in scope["coverage"]], ["#9"])
            self.assertEqual([s["id"] for s in scope["specifications"]], ["#8"])
            self.assertTrue(any("#1" in w for w in scope["warnings"]))

    def test_mock_scope_includes_linked_specification(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            scope = json.loads(run(HANDOFF, "fetch", "--issue", "2", cwd=tmp).stdout)
            self.assertEqual([s["id"] for s in scope["specifications"]], ["SPEC-2"])
            self.assertNotIn("warnings", scope)


class GitignoreCoversEphemeralFiles(unittest.TestCase):
    def test_tracker_work_and_state_are_ignored(self):
        text = GITIGNORE_TEMPLATE.read_text(encoding="utf-8")
        for pattern in ("tracker/", "work/", "state.json"):
            self.assertIn(pattern, text)
        self.assertNotIn("config.yaml", text)
        self.assertNotIn("project-prompt.md", text)


if __name__ == "__main__":
    unittest.main()
