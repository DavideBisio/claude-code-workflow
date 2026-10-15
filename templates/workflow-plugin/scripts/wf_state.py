#!/usr/bin/env python3
"""Deterministic state handling for the {{WORKFLOW_NAME}} workflow (stdlib only).

Run from the user's project root:
  wf_state.py status             # init config/state if needed, report completion + regressions (JSON)
  wf_state.py done STEP          # mark STEP complete (checks output + requirements)
  wf_state.py reset STEP [--cascade]   # mark STEP pending (and steps depending on it)
  wf_state.py sync               # record current git HEAD as the last synced commit

Step graph: plugin workflow.json. Project config: {{WORKFLOW_NAME}}.config.yaml.
State: <state_dir>/state.json.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NAME = "{{WORKFLOW_NAME}}"
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PROJECT = Path.cwd()
CONFIG = PROJECT / f"{NAME}.config.yaml"


def git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def flat_key(text, key, default=""):
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", text, re.M)
    if not m:
        return default
    return re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("\"'")


def ensure_config():
    if CONFIG.exists():
        return False
    shutil.copyfile(PLUGIN_ROOT / "assets" / f"{NAME}.config.yaml", CONFIG)
    return True


def load():
    created = ensure_config()
    cfg = CONFIG.read_text(encoding="utf-8")
    state_dir = PROJECT / flat_key(cfg, "state_dir", ".workflow")
    state_dir.mkdir(parents=True, exist_ok=True)
    steps = json.loads((PLUGIN_ROOT / "workflow.json").read_text(encoding="utf-8"))["steps"]
    sf = state_dir / "state.json"
    state = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {"last_sync_commit": None, "steps": {}}
    return created, cfg, state_dir, steps, state, sf


def save(sf, state):
    sf.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def step_by_id(steps, sid):
    for s in steps:
        if s["id"] == sid:
            return s
    sys.exit(f"unknown step: {sid} (known: {', '.join(s['id'] for s in steps)})")


def issues_for(step, rec, steps_state, state_dir, head):
    out = []
    if not (state_dir / step["output"]).exists():
        out.append("output_missing")
    for r in step.get("requires", []):
        if steps_state.get(r, {}).get("status") != "done":
            out.append(f"requires_not_done:{r}")
    commit = rec.get("commit")
    if commit and head:
        if git("cat-file", "-e", commit + "^{commit}") is None:
            out.append("recorded_commit_unreachable")
        elif step.get("watch"):
            changed = git("diff", "--name-only", commit, "--", *step["watch"])
            if changed:
                out.append("watched_files_changed:" + ",".join(changed.splitlines()[:10]))
    return out


def cmd_status():
    created, cfg, state_dir, steps, state, sf = load()
    head = git("rev-parse", "HEAD")
    last = state.get("last_sync_commit")
    new_commits = []
    if head and last and last != head and git("cat-file", "-e", last + "^{commit}") is not None:
        new_commits = (git("log", "--oneline", "-20", f"{last}..{head}") or "").splitlines()
    report_steps, nxt = [], None
    for s in steps:
        rec = state["steps"].get(s["id"], {})
        status = rec.get("status", "pending")
        iss = issues_for(s, rec, state["steps"], state_dir, head) if status == "done" else []
        report_steps.append({"id": s["id"], "status": status, "completed_at": rec.get("completed_at"),
                             "commit": rec.get("commit"), "issues": iss})
        ready = all(state["steps"].get(r, {}).get("status") == "done" for r in s.get("requires", []))
        if nxt is None and status != "done" and ready:
            nxt = s["id"]
    tracking = None
    cmd = flat_key(cfg, "tracking_sync_command")
    if cmd:
        try:
            r = subprocess.run(cmd, shell=True, cwd=PROJECT, capture_output=True, text=True, timeout=120)
            tracking = {"exit": r.returncode, "output": (r.stdout + r.stderr).strip()[-2000:]}
        except subprocess.TimeoutExpired:
            tracking = {"exit": None, "output": "timeout after 120s"}
    print(json.dumps({"workflow": NAME, "config_created": created, "config": str(CONFIG),
                      "state_dir": str(state_dir), "head": head, "last_sync_commit": last,
                      "new_commits": new_commits, "steps": report_steps, "next_step": nxt,
                      "tracking": tracking}, indent=2))


def cmd_done(sid):
    _, _, state_dir, steps, state, sf = load()
    step = step_by_id(steps, sid)
    if not (state_dir / step["output"]).exists():
        sys.exit(f"cannot mark done: output missing: {state_dir / step['output']}")
    for r in step.get("requires", []):
        if state["steps"].get(r, {}).get("status") != "done":
            sys.exit(f"cannot mark done: required step not done: {r}")
    state["steps"][sid] = {"status": "done", "commit": git("rev-parse", "HEAD"),
                           "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    save(sf, state)
    print(f"{sid}: done")


def cmd_reset(sid, cascade):
    _, _, _, steps, state, sf = load()
    step_by_id(steps, sid)
    todo, changed = {sid}, True
    while cascade and changed:
        changed = False
        for s in steps:
            if s["id"] not in todo and set(s.get("requires", [])) & todo:
                todo.add(s["id"])
                changed = True
    for t in sorted(todo):
        state["steps"][t] = {"status": "pending"}
    save(sf, state)
    print("reset: " + ", ".join(sorted(todo)))


def cmd_sync():
    _, _, _, _, state, sf = load()
    state["last_sync_commit"] = git("rev-parse", "HEAD")
    save(sf, state)
    print(f"synced at {state['last_sync_commit']}")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "status":
        cmd_status()
    elif cmd == "done" and len(rest) == 1:
        cmd_done(rest[0])
    elif cmd == "reset" and rest and rest[0] != "--cascade":
        cmd_reset(rest[0], "--cascade" in rest[1:])
    elif cmd == "sync":
        cmd_sync()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
