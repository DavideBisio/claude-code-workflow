"""Manage the `git-dev.data/` folder in the target project (run from the project root).

  git_dev_data.py init                create git-dev.data/ from the plugin template if missing
  git_dev_data.py fetch               write tracker/<version-control>.json and tracker/<req-tracker>.json
  git_dev_data.py record-step NAME    store the current timestamp for step NAME in state.json
  git_dev_data.py next-step [--review]     print {step}: the workflow step to run next, per state.json
  git_dev_data.py provider KIND       print {name, command, tracker_file, issue_backed} for KIND (version_control | req_tracker)
  git_dev_data.py providers           print the valid backend choices for every KIND (built-in + custom)
  git_dev_data.py set-backend KIND VALUE   persist a backend choice in config.yaml's `backends:` block
  git_dev_data.py check-provider KIND      smoke-test the active KIND provider's `tools` output
  git_dev_data.py call KIND TOOL      call TOOL on the active KIND provider with JSON args read from
                                      stdin (empty -> {}); print its JSON. Use a quoted heredoc: args
                                      carry user/tracker text, which must never pass through shell quoting
  git_dev_data.py config DOTTED [DEFAULT]  print {value} for a dotted config.yaml key (e.g. auto.enabled);
                                           true/false/yes/no/on/off (any case) print as JSON booleans

Prints JSON. Stdlib only.
"""
import datetime
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "common"))
from miniconfig import COMMENT, load as load_config, get as config_get  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent
DATA = Path("git-dev.data")

# tracker kind -> (output filename, {config value under `backends.<kind>`: built-in provider dir})
BUILTIN = {
    "version_control": ("version-control.json", {"mock": "mock-version-control", "github": "github-version-control"}),
    "req_tracker": ("req-tracker.json", {"mock": "mock-req-tracker", "github_labels": "github-req-tracker"}),
}

# Built-in backends whose req-tracker records are themselves version-control issues (so requirements
# and specifications are target candidates too). A custom provider opts in with `issue_backed: true`.
ISSUE_BACKED = {"github_labels"}

# Workflow steps in order; git-dev-review is optional (see next_step).
STEPS = ["git-dev-target", "git-dev-plan", "git-dev-execute", "git-dev-review", "git-dev-update"]

BOOLEANS = {"true": True, "yes": True, "on": True, "false": False, "no": False, "off": False}

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
    """{"name", "command" (argv list), "tracker_file", "issue_backed"} for tracker KIND, per
    `backends.<kind>` in config.yaml: a built-in (mock/github*) or a `providers.<name>` entry for
    anything else."""
    fname, choices = BUILTIN[kind]
    config = load_config(DATA / "config.yaml")
    backend = config_get(config, f"backends.{kind}", "mock")
    if backend in choices:
        server = choices[backend]
        return {"name": server, "command": [sys.executable, str(PLUGIN / "mcp" / server / "server.py")],
                "tracker_file": fname, "issue_backed": backend in ISSUE_BACKED}
    custom = config_get(config, f"providers.{backend}")
    if not isinstance(custom, dict):
        sys.exit(f"unknown backends.{kind}: {backend!r}; choose from {list(choices)} or a providers.<name> entry")
    declared_kind = custom.get("kind")
    if declared_kind and declared_kind != kind:
        sys.exit(f"providers.{backend}.kind is {declared_kind!r}, but backends.{kind} expects a {kind!r} provider")
    if not isinstance(custom.get("command"), str) or not custom["command"]:
        sys.exit(f"providers.{backend} has no `command`; set it to the executable that runs the provider")
    args = custom.get("args", [])
    args = [args] if isinstance(args, str) else list(args) if isinstance(args, list) else []
    return {"name": backend, "command": [custom["command"], *args], "tracker_file": fname,
            "issue_backed": _boolean(custom.get("issue_backed")) is True}


def _boolean(value):
    """true/false/yes/no/on/off (any case) as a bool; anything else unchanged."""
    return BOOLEANS.get(value.strip().lower(), value) if isinstance(value, str) else value


def call_provider(command, tool, args=None):
    """Run one provider tool via its CLI and return the parsed JSON. On failure, exit with the
    provider's own error (its `{"error"}` output or stderr, e.g. "gh auth login required") rather
    than a bare "returned non-zero exit status 1". Provider warnings on stderr are passed through."""
    cmd = [*command, tool] + ([json.dumps(args)] if args is not None else [])
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode:
        try:
            detail = json.loads(res.stdout).get("error")
        except (json.JSONDecodeError, AttributeError):
            detail = None
        detail = detail or res.stderr.strip() or res.stdout.strip() or "no output"
        sys.exit(f"provider call `{tool}` failed: {detail}")
    if res.stderr.strip():
        print(res.stderr.strip(), file=sys.stderr)
    return json.loads(res.stdout)


def read_stdin():
    """All of stdin as UTF-8 text, whatever the console code page (cp1252 on Windows)."""
    return sys.stdin.buffer.read().decode("utf-8-sig")


def call(kind, tool):
    """One provider tool call with args from stdin, passed on as a single argv element (no shell)."""
    if kind not in BUILTIN:
        sys.exit(f"unknown kind: {kind!r}; choose from {list(BUILTIN)}")
    text = read_stdin().strip()
    try:
        args = json.loads(text) if text else {}
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON on stdin: {e}")
    return call_provider(provider(kind)["command"], tool, args)


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
    have = {t["name"] for t in call_provider(info["command"], "tools")}
    missing = sorted(REQUIRED_TOOLS[kind] - have)
    return {"provider": info["name"], "missing": missing, "ok": not missing}


def set_backend(kind, value):
    """Persist `backends.<kind>: value` into config.yaml, editing only that block in place (or
    appending a new one) so any other content (comments, other blocks such as `auto:`) is left alone."""
    if kind not in BUILTIN:
        sys.exit(f"unknown kind: {kind!r}; choose from {list(BUILTIN)}")
    choices = list_providers()[kind]
    if value not in choices:
        sys.exit(f"unknown backends.{kind}: {value!r}; choose from {choices}")
    path = DATA / "config.yaml"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    # Same comment rule as miniconfig, so `backends:  # note` is still recognized as the header
    # (otherwise a second `backends:` block would be appended and silently replace the first).
    start = next((i for i, l in enumerate(lines) if COMMENT.sub("", l).rstrip() == "backends:"), None)
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
            if COMMENT.sub("", l).strip().startswith(f"{kind}:"):
                block[i] = entry
                break
        else:
            block.append(entry)
        lines[start + 1:end] = block
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"backends": {kind: value}}


def config_value(dotted, default=None):
    """Any dotted key in config.yaml (not just backends.*/providers.*), e.g. `auto.enabled`.
    A bare `key:` with nothing under it parses as an empty block; treat it as unset."""
    config = load_config(DATA / "config.yaml")
    value = config_get(config, dotted, default)
    return _boolean(default if value == {} else value)


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
            doc[key] = call_provider(info["command"], tool)
        (DATA / "tracker" / info["tracker_file"]).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        out[info["tracker_file"]] = {k: len(v) for k, v in doc.items()}
    return out


def record_step(name):
    path = DATA / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # Full timestamp, not just the date: next_step compares steps run on the same day.
    state[name] = datetime.datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def next_step(review=False):
    """The step to run next: the first one in the chain that hasn't run since its predecessor did
    (or at all, once its predecessor has). git-dev-review is in the chain only with `review`; it
    is advisory, so update's predecessor is execute otherwise. All caught up -> git-dev-target.
    Older date-only entries still compare correctly against each other and sort before any
    timestamp of the same day."""
    path = DATA / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    chain = [s for s in STEPS if review or s != "git-dev-review"]
    for prev, step in itertools.pairwise(chain):
        if prev in state and (step not in state or state[step] < state[prev]):
            return {"step": step}
    return {"step": chain[0]}


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "init":
        res = init()
    elif cmd == "fetch":
        res = fetch()
    elif cmd == "record-step" and len(argv) == 2:
        res = record_step(argv[1])
    elif cmd == "next-step" and argv[1:] in ([], ["--review"]):
        res = next_step(review=argv[1:] == ["--review"])
    elif cmd == "provider" and len(argv) == 2:
        res = provider(argv[1])
    elif cmd == "providers" and len(argv) == 1:
        res = list_providers()
    elif cmd == "set-backend" and len(argv) == 3:
        res = set_backend(argv[1], argv[2])
    elif cmd == "call" and len(argv) == 3:
        res = call(argv[1], argv[2])
    elif cmd == "check-provider" and len(argv) == 2:
        res = check_provider(argv[1])
    elif cmd == "config" and len(argv) in (2, 3):
        res = {"value": config_value(argv[1], argv[2] if len(argv) == 3 else None)}
    else:
        sys.exit(__doc__)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
