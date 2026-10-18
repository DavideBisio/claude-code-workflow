"""Validated, scoped handoff between git-dev workflow steps (target -> plan -> execute -> update).

Replaces reading/writing raw tracker dumps and loose work/ files with one gitignored handoff file
(git-dev.data/work/handoff.json), written and read one section at a time:

  handoff_manager.py fetch --issue N      scope requirements/coverage/specifications to issue N
  handoff_manager.py get SECTION          print handoff.json[SECTION] ("scope"|"target"|"plan"|"result")
  handoff_manager.py write SECTION JSON   validate then store handoff.json[SECTION]
  handoff_manager.py prompt-section HEADING   print {heading, text} for a "## HEADING" block in
                                               project-prompt.md (text is null if missing or still
                                               only the template's <placeholder> lines)
  handoff_manager.py provider KIND        print {name, command, tracker_file} for KIND (passthrough)
  handoff_manager.py record-step NAME     store today's date for step NAME in state.json (passthrough)

Prints JSON. Stdlib only.
"""
import json
import re
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

# section -> {key: type(s)}, checked only for keys present in the payload (required or optional).
# Kept narrow: just the keys later steps interpolate directly (e.g. into `git switch -c <branch>`
# or a commit message), where a wrong type would otherwise fail confusingly downstream.
TYPES = {
    "target": {"requirements": list, "coverage": list},
    "plan": {"branch": str, "source_branch": str, "target_branch": str, "commit_message": str,
             "tracker_updates": (list, dict)},
    "result": {"branch": str, "commit": str, "test_id": str, "test_before": str, "test_after": str},
}

# project-prompt.md template markup: `<!-- default note -->` comments, and `- <fill me in>` lines.
COMMENT = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER = re.compile(r"(?:[-*]\s*)?<[^>]*>")


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
    mismatched = [k for k, t in TYPES.get(section, {}).items() if k in data and not isinstance(data[k], t)]
    if mismatched:
        return {"ok": False, "error": f"wrong type for key(s) in '{section}': {mismatched}"}
    handoff = _load()
    handoff[section] = data
    _save(handoff)
    return {"ok": True, "section": section}


def prompt_section(heading):
    """{"heading", "text"} for the "## <heading>" block in project-prompt.md (case-insensitive
    heading match), text up to the next "## " heading or EOF, `<!-- -->` comments stripped.
    text=None if not found, empty, or only `<placeholder>` lines (the shipped template), so callers
    fall back to their own documented default."""
    path = DATA / "project-prompt.md"
    if not path.exists():
        return {"heading": heading, "text": None}
    lines = path.read_text(encoding="utf-8").splitlines()
    wanted = heading.strip().lower()
    start = next((i + 1 for i, l in enumerate(lines)
                  if l.startswith("## ") and l[3:].strip().lower() == wanted), None)
    if start is None:
        return {"heading": heading, "text": None}
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    body = COMMENT.sub("", "\n".join(lines[start:end])).strip()
    customized = any(l.strip() and not PLACEHOLDER.fullmatch(l.strip()) for l in body.splitlines())
    return {"heading": heading, "text": body if customized else None}


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
    elif cmd == "prompt-section" and len(argv) == 2:
        res = prompt_section(argv[1])
    elif cmd == "provider" and len(argv) == 2:
        res = git_dev_data.provider(argv[1])
    elif cmd == "record-step" and len(argv) == 2:
        res = git_dev_data.record_step(argv[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
