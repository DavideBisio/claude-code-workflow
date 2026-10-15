"""Manage the `example.data/` folder in the target project (run from the project root).

  example_data.py init                create example.data/ from the plugin template if missing
  example_data.py fetch               write tracker/dev-status.json and tracker/req-tracker.json
  example_data.py record-step NAME    store today's date for step NAME in state.json

Prints JSON. Stdlib only.
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
DATA = Path("example.data")

# file -> (server, {key: tool})
TRACKERS = {
    "dev-status.json": ("dev-status", {"issues": "list_issues", "merge_requests": "list_merge_requests",
                                       "milestones": "list_milestones"}),
    "req-tracker.json": ("req-tracker", {"requirements": "list_requirements", "coverage": "list_coverage",
                                         "specifications": "list_specifications", "testplans": "list_testplans"}),
}


def init():
    if DATA.exists():
        return {"created": False, "path": str(DATA)}
    shutil.copytree(PLUGIN / "assets" / "example.data", DATA)
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
