"""Mock Jama MCP server `mock-req-tracker`: requirements, coverage, specifications, test plans.

Fetch returns sample data; create/update acknowledge with no effect.
Also a CLI: `python server.py tools | call TOOL [JSON] | TOOL [JSON]` (prints JSON).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from mockmcp import run  # noqa: E402

RESOURCES = {
    "requirement": ("requirements", [
        {"id": "REQ-1", "title": "User can log in", "status": "approved", "specification_id": "SPEC-1"},
        {"id": "REQ-2", "title": "Empty input is rejected", "status": "approved", "specification_id": "SPEC-1"},
        {"id": "REQ-3", "title": "API is documented", "status": "draft", "specification_id": "SPEC-2"},
    ]),
    "coverage": ("coverage", [
        {"id": "COV-1", "requirement_id": "REQ-1", "testcases": ["TC-1"], "result": "passed"},
        {"id": "COV-2", "requirement_id": "REQ-2", "testcases": ["TC-2", "TC-3"], "result": "failed"},
        {"id": "COV-3", "requirement_id": "REQ-3", "testcases": [], "result": "not_covered"},
    ]),
    "specification": ("specifications", [
        {"id": "SPEC-1", "title": "Authentication and input handling", "version": "1.0"},
        {"id": "SPEC-2", "title": "Documentation", "version": "0.1"},
    ]),
    "testplan": ("testplans", [
        {"id": "TP-1", "title": "Release v0.1", "status": "in_progress", "testcases": ["TC-1", "TC-2", "TC-3"]},
    ]),
}

if __name__ == "__main__":
    run("mock-req-tracker", RESOURCES)
