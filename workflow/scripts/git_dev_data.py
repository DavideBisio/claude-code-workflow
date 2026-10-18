"""Manage the `git-dev.data/` folder in the target project (run from the project root).

  git_dev_data.py init                create git-dev.data/ from the plugin template if missing
  git_dev_data.py fetch               write tracker/<version-control>.json and tracker/<req-tracker>.json
  git_dev_data.py record-step NAME    store today's date for step NAME in state.json
  git_dev_data.py provider KIND       print {name, command, tracker_file} for KIND (version_control | req_tracker)
  git_dev_data.py providers           print the valid backend choices for every KIND (built-in + custom)
  git_dev_data.py set-backend KIND VALUE   persist a backend choice in config.yaml's `backends:` block
  git_dev_data.py check-provider KIND      smoke-test the active KIND provider's `tools` output

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

# tracker kind -> (output filename, {config value under `backends.<kind>`: built-in provider dir})
BUILTIN = {
    "version_control": ("version-control.json", {"mock": "mock-version-control", "github": "github-version-control"}),
    "req_tracker": ("req-tracker.json", {"mock": "mock-req-tracker", "github_labels": "github-req-tracker"}),
}

# tracker kind -> required tool names (same set across every built-in provider of that kind)
REQUIRED_TOOLS = {
    "version_control": {"list_issues", "get_issue", "create_issue", "update_issue",
                         "list_merge_requests", "get_merge_request", "create_merge_request",
                         "list_milestones", "get_milestone"},
    "req_tracker": {"list_requirements", "get_requirement", "create_requirement",
                    "list_coverage", "get_coverage", "create_coverage", "update_coverage",
                    "list_specifications", "get_specification", "create_specification",
                    "list_testplans"},
}

# output key -> tool, shared by every provider of a kind (built-in or custom)
TOOLS_BY_KIND = {
    "version_control": {"issues": "list_issues", "merge_requests": "list_merge_requests", "milestones": "list_milestones"},
    "req_tracker": {"requirements": "list_requirements", "coverage": "list_coverage",
                    "specifications": "list_specifications", "testplans": "list_testplans"},
}


def provider(kind):
    """{"name", "command" (argv list), "tracker_file"} for tracker KIND, per `backends.<kind>` in
    config.yaml: a built-in (mock/github*) or a `providers.<name>` entry for anything else."""
    fname, choices = BUILTIN[kind]
    config = load_config(DATA / "config.yaml")
    backend = config_get(config, f"backends.{kind}", "mock")
    if backend in choices:
        server = choices[backend]
        return {"name": server, "command": [sys.executable, str(PLUGIN / "mcp" / server / "server.py")],
                "tracker_file": fname}
    custom = config_get(config, f"providers.{backend}")
    if not isinstance(custom, dict):
        sys.exit(f"unknown backends.{kind}: {backend!r}; choose from {list(choices)} or a providers.<name> entry")
    declared_kind = custom.get("kind")
    if declared_kind and declared_kind != kind:
        sys.exit(f"providers.{backend}.kind is {declared_kind!r}, but backends.{kind} expects a {kind!r} provider")
    command = [custom["command"]] if "args" not in custom else [custom["command"], custom["args"]]
    return {"name": backend, "command": command, "tracker_file": fname}


def list_providers():
    """Valid `backends.<kind>` values for every tracker KIND: built-ins plus any `providers.<name>`
    entry whose declared `kind` matches, so callers never hardcode them."""
    config = load_config(DATA / "config.yaml")
    custom = config_get(config, "providers") or {}
    out = {}
    for kind, (_, choices) in BUILTIN.items():
        names = list(choices)
        names += [name for name, spec in custom.items()
                  if isinstance(spec, dict) and spec.get("kind") == kind]
        out[kind] = names
    return out


def check_provider(kind):
    """Run the active KIND provider's `tools` and report which REQUIRED_TOOLS[kind] are missing."""
    info = provider(kind)
    res = subprocess.run([*info["command"], "tools"], capture_output=True, text=True, check=True)
    have = {t["name"] for t in json.loads(res.stdout)}
    missing = sorted(REQUIRED_TOOLS[kind] - have)
    return {"provider": info["name"], "missing": missing, "ok": not missing}


def set_backend(kind, value):
    """Persist `backends.<kind>: value` into config.yaml, editing only that block in place (or
    appending a new one) so any other content (comments, `test_command`, prose) is left alone."""
    if kind not in BUILTIN:
        sys.exit(f"unknown kind: {kind!r}; choose from {list(BUILTIN)}")
    _, choices = BUILTIN[kind]
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
    for kind in BUILTIN:
        info = provider(kind)
        doc = {}
        for key, tool in TOOLS_BY_KIND[kind].items():
            res = subprocess.run([*info["command"], tool], capture_output=True, text=True, check=True)
            doc[key] = json.loads(res.stdout)
        (DATA / "tracker" / info["tracker_file"]).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        out[info["tracker_file"]] = {k: len(v) for k, v in doc.items()}
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
        res = provider(argv[1])
    elif cmd == "providers" and len(argv) == 1:
        res = list_providers()
    elif cmd == "set-backend" and len(argv) == 3:
        res = set_backend(argv[1], argv[2])
    elif cmd == "check-provider" and len(argv) == 2:
        res = check_provider(argv[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
