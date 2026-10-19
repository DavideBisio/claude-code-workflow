"""Mock Jama MCP server `mock-req-tracker`: requirements, coverage, specifications, test plans.

Fetch returns sample data; create/update acknowledge with no effect. Record keys match
`github-req-tracker` (requirements/specifications carry `state: opened|closed`; specifications
link to their requirement via `requirement_id`), so skills see one shape whichever is configured.
Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from mockmcp import run  # noqa: E402

RESOURCES = {
    "requirement": ("requirements", [
        {"id": "REQ-1", "title": "User can log in", "state": "closed", "blocks": [], "blocked_by": []},
        {"id": "REQ-2", "title": "Empty input is rejected", "state": "opened", "blocks": [], "blocked_by": []},
        {"id": "REQ-3", "title": "API is documented", "state": "opened", "blocks": [], "blocked_by": []},
    ]),
    "coverage": ("coverage", [
        {"id": "COV-1", "requirement_id": "REQ-1", "testcases": ["TC-1"], "result": "passed",
         "title": "Login works"},
        {"id": "COV-2", "requirement_id": "REQ-2", "testcases": ["TC-2", "TC-3"], "result": "failed",
         "title": "Empty input rejected"},
        {"id": "COV-3", "requirement_id": "REQ-3", "testcases": [], "result": "not_covered",
         "title": "API docs exist"},
    ]),
    "specification": ("specifications", [
        {"id": "SPEC-1", "requirement_id": "REQ-1", "title": "Authentication", "state": "closed", "blocks": [], "blocked_by": []},
        {"id": "SPEC-2", "requirement_id": "REQ-2", "title": "Input handling", "state": "opened", "blocks": [], "blocked_by": []},
        {"id": "SPEC-3", "requirement_id": "REQ-3", "title": "Documentation", "state": "opened", "blocks": [], "blocked_by": []},
    ]),
    "testplan": ("testplans", [
        {"id": "TP-1", "title": "Release v0.1", "status": "in_progress", "testcases": ["TC-1", "TC-2", "TC-3"]},
    ]),
}

if __name__ == "__main__":
    run("mock-req-tracker", RESOURCES)
