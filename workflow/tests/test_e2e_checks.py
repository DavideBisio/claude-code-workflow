"""Unit tests for tests/e2e/testplan.py's check functions against the handoff-manager's unified
git-dev.data/work/handoff.json shape, without spinning up `claude` or a real git fixture.
Run: python -m unittest discover tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "e2e"))
import testplan  # noqa: E402


def make_ctx(tmp, handoff, state=None):
    p = Path(tmp)
    (p / "git-dev.data" / "work").mkdir(parents=True)
    (p / "git-dev.data" / "work" / "handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
    (p / "git-dev.data" / "state.json").write_text(json.dumps(state or {}), encoding="utf-8")
    return testplan.WorkflowCtx(p, [])


class TargetChecks(unittest.TestCase):
    def test_passes_against_handoff_json_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp, {"target": {"issue": {"iid": 2}, "requirements": [{"id": "REQ-2"}],
                                             "coverage": [], "code_area": "app/"}},
                           state={"git-dev-target": "2026-10-18"})
            results = testplan.checks_target(ctx)
            self.assertTrue(all(ok for _, ok in results), results)


class PlanChecks(unittest.TestCase):
    def test_passes_against_handoff_json_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp, {"plan": {"branch": "fix/2-empty-input", "test": "REQ-2",
                                           "fix": "...", "verification": "...",
                                           "commit_message": "...",
                                           "tracker_updates": {"coverage": "REQ-2"}}},
                           state={"git-dev-plan": "2026-10-18"})
            results = testplan.checks_plan(ctx)
            self.assertTrue(all(ok for _, ok in results), results)


class ExecuteChecksResultSection(unittest.TestCase):
    def test_result_read_from_handoff_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp, {"result": {"branch": "fix/2-empty-input", "commit": "abc123",
                                             "test_id": "TC-2", "test_before": "failed",
                                             "test_after": "passed"}})
            self.assertEqual(ctx.handoff("result")["test_before"], "failed")
            self.assertEqual(ctx.handoff("result")["test_after"], "passed")


if __name__ == "__main__":
    unittest.main()
