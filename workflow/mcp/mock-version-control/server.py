"""Mock GitLab MCP server `mock-version-control`: issues, merge requests, milestones.

Fetch returns sample data; create/update acknowledge with no effect.
Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from mockmcp import run  # noqa: E402

RESOURCES = {
    "issue": ("issues", [
        {"id": 1, "iid": 1, "title": "Add login page", "state": "closed", "milestone_id": 1,
         "labels": ["feature"], "assignee": "alice", "requirements": ["REQ-1"],
         "blocks": [], "blocked_by": []},
        {"id": 2, "iid": 2, "title": "Fix crash on empty input", "state": "opened", "milestone_id": 1,
         "labels": ["bug"], "assignee": "bob", "requirements": ["REQ-2"],
         "blocks": [], "blocked_by": []},
        {"id": 3, "iid": 3, "title": "Document the API", "state": "opened", "milestone_id": 2,
         "labels": ["docs"], "assignee": None, "requirements": ["REQ-3"],
         "blocks": [], "blocked_by": []},
    ]),
    "merge_request": ("merge_requests", [
        {"id": 10, "iid": 1, "title": "Login page", "state": "merged", "source_branch": "feat/login",
         "target_branch": "dev", "pipeline": "passed", "closes": [1]},
        {"id": 11, "iid": 2, "title": "API docs draft", "state": "opened", "source_branch": "docs/api",
         "target_branch": "dev", "pipeline": "running", "closes": [3]},
    ]),
    "milestone": ("milestones", [
        {"id": 1, "title": "v0.1", "state": "open", "due_date": "2026-11-01"},
        {"id": 2, "title": "v0.2", "state": "open", "due_date": "2026-12-15"},
    ]),
}

if __name__ == "__main__":
    run("mock-version-control", RESOURCES)
