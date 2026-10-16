"""Manage the `git-dev.data/` folder in the target project (run from the project root).

  git_dev_data.py init                create git-dev.data/ from the plugin template if missing
  git_dev_data.py fetch               write tracker/mock-version-control.json and tracker/mock-req-tracker.json
  git_dev_data.py record-step NAME    store today's date for step NAME in state.json

Prints JSON. Stdlib only.
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
DATA = Path("git-dev.data")

# file -> (server, {key: tool})
TRACKERS = {
    "mock-version-control.json": ("mock-version-control", {"issues": "list_issues", "merge_requests": "list_merge_requests",
                                       "milestones": "list_milestones"}),
    "mock-req-tracker.json": ("mock-req-tracker", {"requirements": "list_requirements", "coverage": "list_coverage",
                                         "specifications": "list_specifications", "testplans": "list_testplans"}),
}


def init():
    if DATA.exists():
        return {"created": False, "path": str(DATA)}
    shutil.copytree(PLUGIN / "assets" / "git-dev.data", DATA)
    return {"created": True, "path": str(DATA), "note": "fill in config.yaml and project-prompt.md"}


def fetch():
    out = {}
    (DATA / "tracker").mkdir(parents=True, exist_ok=True)
    for fname, (server, tools) in TRACKERS.items():
        doc = {}
        for key, tool in tools.items():
            res = subprocess.run([sys.executable, str(PLUGIN / "mcp" / server / "server.py"), tool],
                                 capture_output=True, text=True, check=True)
            doc[key] = json.loads(res.stdout)
        (DATA / "tracker" / fname).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        out[fname] = {k: len(v) for k, v in doc.items()}
    return out


def record_step(name):
    path = DATA / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state[name] = datetime.date.today().isoformat()
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "init":
        res = init()
    elif cmd == "fetch":
        res = fetch()
    elif cmd == "record-step" and len(argv) == 2:
        res = record_step(argv[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
