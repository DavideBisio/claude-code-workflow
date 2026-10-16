"""Manage the `git-dev.data/` folder in the target project (run from the project root).

  git_dev_data.py init                create git-dev.data/ from the plugin template if missing
  git_dev_data.py fetch               write tracker/<version-control>.json and tracker/<req-tracker>.json
  git_dev_data.py record-step NAME    store today's date for step NAME in state.json
  git_dev_data.py provider KIND       print the provider dir name for KIND (version_control | req_tracker)
  git_dev_data.py providers           print the valid backend choices for every KIND
  git_dev_data.py set-backend KIND VALUE   persist a backend choice in config.yaml's `backends:` block

Prints JSON. Stdlib only.
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "common"))
from miniconfig import load as load_config, get as config_get  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent
DATA = Path("git-dev.data")

# tracker kind -> (output filename, {config value under `backends.<kind>`: provider dir})
BACKENDS = {
    "version_control": ("version-control.json", {"mock": "mock-version-control", "github": "github-version-control"}),
    "req_tracker": ("req-tracker.json", {"mock": "mock-req-tracker", "github_labels": "github-req-tracker"}),
}

# provider dir -> {output key: tool}
TOOLS = {
    "mock-version-control": {"issues": "list_issues", "merge_requests": "list_merge_requests", "milestones": "list_milestones"},
    "github-version-control": {"issues": "list_issues", "merge_requests": "list_merge_requests", "milestones": "list_milestones"},
    "mock-req-tracker": {"requirements": "list_requirements", "coverage": "list_coverage",
                         "specifications": "list_specifications", "testplans": "list_testplans"},
    "github-req-tracker": {"requirements": "list_requirements", "coverage": "list_coverage",
                           "specifications": "list_specifications", "testplans": "list_testplans"},
}


def provider(kind):
    """(provider dir, output filename) for tracker KIND, per `backends.<kind>` in config.yaml."""
    fname, choices = BACKENDS[kind]
    backend = config_get(load_config(DATA / "config.yaml"), f"backends.{kind}", "mock")
    if backend not in choices:
        sys.exit(f"unknown backends.{kind}: {backend!r}; choose from {list(choices)}")
    return choices[backend], fname


def list_providers():
    """Valid `backends.<kind>` values for every tracker KIND, so callers never hardcode them."""
    return {kind: list(choices) for kind, (_, choices) in BACKENDS.items()}


def set_backend(kind, value):
    """Persist `backends.<kind>: value` into config.yaml, editing only that block in place (or
    appending a new one) so any other content (comments, `test_command`, prose) is left alone."""
    if kind not in BACKENDS:
        sys.exit(f"unknown kind: {kind!r}; choose from {list(BACKENDS)}")
    _, choices = BACKENDS[kind]
    if value not in choices:
        sys.exit(f"unknown backends.{kind}: {value!r}; choose from {list(choices)}")
    path = DATA / "config.yaml"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    start = next((i for i, l in enumerate(lines) if l.rstrip() == "backends:"), None)
    entry = f"  {kind}: {value}"
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["backends:", entry]
    else:
        end = start + 1
        while end < len(lines) and (lines[end].startswith("  ") or not lines[end].strip()):
            end += 1
        block = lines[start + 1:end]
        for i, l in enumerate(block):
            if l.strip().startswith(f"{kind}:"):
                block[i] = entry
                break
        else:
            block.append(entry)
        lines[start + 1:end] = block
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"backends": {kind: value}}


def init():
    if DATA.exists():
        return {"created": False, "path": str(DATA)}
    shutil.copytree(PLUGIN / "assets" / "git-dev.data", DATA)
    return {"created": True, "path": str(DATA), "note": "fill in config.yaml and project-prompt.md"}


def fetch():
    out = {}
    (DATA / "tracker").mkdir(parents=True, exist_ok=True)
    for kind in BACKENDS:
        server, fname = provider(kind)
        doc = {}
        for key, tool in TOOLS[server].items():
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
    elif cmd == "provider" and len(argv) == 2:
        server, fname = provider(argv[1])
        res = {"dir": server, "tracker_file": fname}
    elif cmd == "providers" and len(argv) == 1:
        res = list_providers()
    elif cmd == "set-backend" and len(argv) == 3:
        res = set_backend(argv[1], argv[2])
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
