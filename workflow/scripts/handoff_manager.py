"""Validated, scoped handoff between git-dev workflow steps (target -> plan -> execute -> update).

Replaces reading/writing raw tracker dumps and loose work/ files with one gitignored handoff file
(git-dev.data/work/handoff.json), written and read one section at a time:

  handoff_manager.py fetch --issue N      scope requirements/coverage/specifications to issue N
  handoff_manager.py get SECTION          print handoff.json[SECTION] ("scope"|"target"|"plan"|"result")
  handoff_manager.py write SECTION JSON   validate then store handoff.json[SECTION]
  handoff_manager.py provider KIND        print {name, command, tracker_file} for KIND (passthrough)
  handoff_manager.py record-step NAME     store today's date for step NAME in state.json (passthrough)

Prints JSON. Stdlib only.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import git_dev_data  # noqa: E402

DATA = git_dev_data.DATA
PLUGIN = git_dev_data.PLUGIN
HANDOFF = DATA / "work" / "handoff.json"

REQUIRED = {
    "target": ["issue", "requirements", "coverage", "code_area"],
    "plan": ["branch", "test", "fix", "verification", "commit_message", "tracker_updates"],
    "result": ["branch", "commit", "test_id", "test_before", "test_after"],
}


def _call(command, tool, args=None):
    res = subprocess.run([*command, tool, json.dumps(args or {})],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def _load():
    return json.loads(HANDOFF.read_text(encoding="utf-8")) if HANDOFF.exists() else {}


def _save(handoff):
    HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    HANDOFF.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")


def fetch(issue_id):
    """Scope requirements/coverage/specifications to one issue via each provider's exact-match
    `filter`, instead of the full tracker dump `git_dev_data.py fetch` writes."""
    vc_command = git_dev_data.provider("version_control")["command"]
    req_command = git_dev_data.provider("req_tracker")["command"]
    issue = _call(vc_command, "get_issue", {"id": issue_id})
    requirements, coverage, specifications = [], [], []
    for req_id in issue.get("requirements") or []:
        requirements.append(_call(req_command, "get_requirement", {"id": req_id}))
        coverage += _call(req_command, "list_coverage", {"filter": {"requirement_id": req_id}})
        specifications += _call(req_command, "list_specifications", {"filter": {"requirement_id": req_id}})
    scope = {"issue": issue, "requirements": requirements, "coverage": coverage, "specifications": specifications}
    handoff = _load()
    handoff["scope"] = scope
    _save(handoff)
    return scope


def get(section):
    handoff = _load()
    if section not in handoff:
        return {"error": f"'{section}' not set yet; run the step that produces it first"}
    return handoff[section]


def write(section, data):
    if section not in REQUIRED:
        sys.exit(f"unknown section: {section!r}; choose from {list(REQUIRED)}")
    missing = [k for k in REQUIRED[section] if k not in data]
    if missing:
        return {"ok": False, "error": f"missing required keys for '{section}': {missing}"}
    handoff = _load()
    handoff[section] = data
    _save(handoff)
    return {"ok": True, "section": section}


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "fetch" and len(argv) == 3 and argv[1] == "--issue":
        res = fetch(argv[2])
    elif cmd == "get" and len(argv) == 2:
        res = get(argv[1])
    elif cmd == "write" and len(argv) == 3:
        try:
            data = json.loads(argv[2])
        except json.JSONDecodeError as e:
            sys.exit(f"invalid JSON: {e}")
        res = write(argv[1], data)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)
    elif cmd == "provider" and len(argv) == 2:
        res = git_dev_data.provider(argv[1])
    elif cmd == "record-step" and len(argv) == 2:
        res = git_dev_data.record_step(argv[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
