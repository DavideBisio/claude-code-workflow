"""Generic e2e test harness: drive any Claude Code skill through the `claude` CLI on a throwaway
project and check the resulting state. Nothing in this module knows about any particular plugin
or skill — that lives in a TestPlan (see testplan.py for the example-plugin's). Stdlib only.

Milestones of a run:
  1. fixture  - build a throwaway project from a template, via the TestPlan's `build_project`
                hook. `build_git_fixture` below covers the common case: a template directory
                copied into a fresh git repo with a local bare origin, optionally with an
                upstream commit for the skill to rebase onto.
  2. invoke   - for each Phase, send the skill's own text to `claude -p` (stream-json), with
                confirmation gates pre-approved via an appended system prompt.
  3. collect  - parse the event stream into a transcript, the tool calls made and token/cost/turn
                metrics.
  4. verify   - run `general_checks` (apply to every phase: did the run error, did it use any
                tool at all, plus whichever opt-in git checks the Phase asks for — clean tree, no
                push, still on a given branch) followed by the Phase's own `checks`, which look at
                whatever that specific skill is supposed to have produced.
  5. report   - print a per-phase metrics table, write report.json, exit 1 if any goal was missed.
"""
import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SYSTEM = ("Automated test run, no human is present, so there will be no reply to any question. "
          "The user's answer to every confirmation gate is already given: YES, approved, go ahead. "
          "At a gate, print the gate text with 'Answer: yes (pre-approved)', then continue in the same turn "
          "and finish the whole skill, including its Output and Summary sections. "
          "Never end your turn with a question. Work only inside the current directory.")


# ---------- test plan ----------

@dataclass
class Phase:
    """One `claude -p` invocation: a skill, run to completion, then checked."""
    key: str                                           # --phases selector, e.g. "run"
    skill: str                                         # skill name: skills/<skill>/SKILL.md
    note: str = ""                                      # extra line appended to the pre-approval note
    checks: Callable = field(default=lambda ctx: [])    # skill-specific goal checks: Ctx -> [(name, ok)]
    expect_clean_tree: bool = False                     # opt into the generic "working tree clean" check
    expect_branch: str = None                           # opt into the generic "still on branch X" check
    expect_no_push: bool = False                        # opt into the generic "nothing pushed to origin" check


@dataclass
class TestPlan:
    """Everything specific to one plugin/skill-set; the rest of this module is generic."""
    name: str
    plugin_dir: Path
    build_project: Callable                             # root -> (project_path, ctx_extra: dict)
    phases: list
    system_prompt: str = SYSTEM
    ctx_factory: Callable = None                         # defaults to Ctx


# ---------- helpers ----------

def git(*args, cwd, check=True):
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and res.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr}")
    return res.stdout.strip()


def find_claude(explicit):
    for cand in (explicit, os.environ.get("CLAUDE_BIN"), shutil.which("claude")):
        if cand:
            return cand
    pattern = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code", "*", "*", "claude.exe")
    found = sorted(glob.glob(pattern))
    return found[-1] if found else None


def skill_prompt(plugin_dir, skill, note=""):
    text = (plugin_dir / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    body = text.split("---", 2)[2].strip().replace("${CLAUDE_PLUGIN_ROOT}", plugin_dir.as_posix())
    return (f"Execute the following skill now, in the current project, from start to finish.\n\n{body}\n\n"
            f"Every confirmation gate is pre-approved (answer: yes). Do not stop at a gate. {note}\n")


def check_list(pairs):
    """pairs: [(name, callable)]. Returns [(name, ok)], folding an exception into the name."""
    out = []
    for name, fn in pairs:
        try:
            ok = bool(fn())
        except Exception as e:  # missing file, bad json, non-zero git...
            ok, name = False, f"{name} ({type(e).__name__}: {e})"
        out.append((name, ok))
    return out


# ---------- fixtures ----------

def build_git_fixture(root, template_dir, *, branch="main",
                       seed_identity=("Seed Dev", "seed@example.test"),
                       project_identity=("Test User", "user@example.test"),
                       post_init=None, diverge=None):
    """Generic `build_project`: copy a template directory (a plain file tree) into a fresh git
    repo with a local bare origin, then clone it out twice: `seed` (used to set things up further)
    and `project` (the one the skill under test actually runs in).

    - post_init(seed): optional hook for files the template can't hold statically (e.g. running
      the plugin's own setup script). Runs before the initial commit.
    - diverge(seed): optional hook that, once `project` has been cloned, edits `seed` further; the
      edit is committed and pushed so `project` ends up one commit behind origin (e.g. to exercise
      a skill's own rebase step). Commit message is fixed ("docs: update README") since the hook
      only edits files, not git.

    Returns (project_path, {"origin_dev": <rev-parse of `branch` at origin after setup>}).
    """
    origin, seed, project = root / "origin.git", root / "seed", root / "project"
    git("init", "-q", "--bare", "-b", branch, str(origin), cwd=root)
    git("clone", "-q", str(origin), str(seed), cwd=root)
    git("config", "user.name", seed_identity[0], cwd=seed)
    git("config", "user.email", seed_identity[1], cwd=seed)
    git("switch", "-q", "-c", branch, cwd=seed)
    shutil.copytree(template_dir, seed, dirs_exist_ok=True)
    if post_init:
        post_init(seed)
    git("add", "-A", cwd=seed)
    git("commit", "-q", "-m", "Initial project", cwd=seed)
    git("push", "-q", "-u", "origin", branch, cwd=seed)
    git("clone", "-q", "-b", branch, str(origin), str(project), cwd=root)
    git("config", "user.name", project_identity[0], cwd=project)
    git("config", "user.email", project_identity[1], cwd=project)
    if diverge:
        diverge(seed)
        git("commit", "-q", "-am", "docs: update README", cwd=seed)
        git("push", "-q", "origin", branch, cwd=seed)
    return project, {"origin_dev": git("rev-parse", branch, cwd=origin)}


# ---------- running claude ----------

def run_claude(claude, project, plugin_dir, phase, system_prompt, args):
    cmd = [claude, "-p", "--output-format", "stream-json", "--verbose",
           "--plugin-dir", str(plugin_dir), "--permission-mode", "acceptEdits",
           "--allowed-tools", "Bash,Read,Write,Edit,Glob,Grep",
           "--append-system-prompt", system_prompt, "--no-session-persistence",
           "--max-budget-usd", str(args.budget)]
    if args.model:
        cmd += ["--model", args.model]
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    started = datetime.datetime.now()
    prompt = skill_prompt(plugin_dir, phase.skill, phase.note)
    res = subprocess.run(cmd, cwd=project, input=prompt, capture_output=True, text=True,
                         env=env, encoding="utf-8")
    tools, final = [], {}
    for line in res.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for item in ev.get("message", {}).get("content", []):
                if item.get("type") == "tool_use":
                    tools.append({"name": item["name"], "input": item.get("input", {})})
        elif ev.get("type") == "result":
            final = ev
    usage = final.get("usage", {})
    return {
        "prompt": prompt,
        "raw": res.stdout,
        "exit_code": res.returncode,
        "error": bool(final.get("is_error")) or res.returncode != 0 or not final,
        "stderr": res.stderr[-500:],
        "result_text": final.get("result", ""),
        "tool_calls": tools,
        "metrics": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
            "cost_usd": final.get("total_cost_usd", 0.0),
            "turns": final.get("num_turns", 0),
            "duration_s": round(final.get("duration_ms", (datetime.datetime.now() - started).total_seconds() * 1000) / 1000, 1),
            "tool_calls": len(tools),
        },
    }


def render_transcript(phase, prompt, raw):
    """Readable markdown from the stream-json events: prompt, text, tool calls and results."""
    def clip(text, n=2000):
        text = text if isinstance(text, str) else json.dumps(text, indent=2)
        return text if len(text) <= n else text[:n] + f"\n... [{len(text) - n} more chars]"

    out = [f"# {phase.key} ({phase.skill})\n", "## Prompt\n", prompt, "\n## Conversation\n"]
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            out.append(f"```\n{line}\n```")
            continue
        kind = ev.get("type")
        msg = ev.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []
        if kind == "system" and isinstance(msg, str):
            out.append(f"*system:* {msg}\n")
        elif kind == "assistant":
            for item in content:
                if item.get("type") == "text":
                    out.append(f"**assistant:** {item['text']}\n")
                elif item.get("type") == "thinking" and item.get("thinking"):
                    out.append(f"*thinking:* {clip(item.get('thinking', ''), 800)}\n")
                elif item.get("type") == "tool_use":
                    out.append(f"**tool call `{item['name']}`**\n```json\n{clip(item.get('input', {}), 1500)}\n```\n")
        elif kind == "user" and isinstance(content, list):
            for item in content:
                if item.get("type") == "tool_result":
                    body = item.get("content", "")
                    if isinstance(body, list):
                        body = "\n".join(b.get("text", "") for b in body if isinstance(b, dict))
                    out.append(f"**tool result**\n```\n{clip(body)}\n```\n")
        elif kind == "result":
            out.append(f"## Result\n\n{ev.get('result', '')}\n\n"
                       f"cost ${ev.get('total_cost_usd', 0):.3f}, turns {ev.get('num_turns')}, "
                       f"error {ev.get('is_error')}\n")
    return "\n".join(out)


# ---------- checks ----------

class Ctx:
    """Helpers available to every check. A TestPlan can pass a subclass (via `ctx_factory`) that
    adds its own readers; whatever `build_project` returns as `ctx_extra` becomes attributes here
    (e.g. `origin_dev`, used by `not_pushed`)."""

    def __init__(self, project, tools, **extra):
        self.p, self.tools = project, tools
        self.origin = project.parent / "origin.git"
        for k, v in extra.items():
            setattr(self, k, v)

    def read_json(self, rel):
        return json.loads((self.p / rel).read_text(encoding="utf-8"))

    def commands(self):
        return [t["input"].get("command", "") for t in self.tools if t["name"] == "Bash"]

    def clean(self):
        return git("status", "--porcelain", cwd=self.p) == ""

    def branch(self):
        return git("branch", "--show-current", cwd=self.p)

    def not_pushed(self, branch="dev"):
        branches = git("branch", "--list", cwd=self.origin).replace("*", "").split()
        return branches == [branch] and git("rev-parse", branch, cwd=self.origin) == getattr(self, "origin_dev", None)


def general_checks(phase, run, ctx):
    """Checks that apply to any skill, regardless of what it does: did the CLI run complete, did
    it actually do anything — plus whichever opt-in git checks `phase` asked for."""
    pairs = [
        ("claude run completed without error", lambda: not run["error"]),
        ("skill used at least one tool", lambda: len(run["tool_calls"]) > 0),
    ]
    if phase.expect_clean_tree:
        pairs.append(("working tree clean", ctx.clean))
    if phase.expect_branch:
        pairs.append((f"still on branch {phase.expect_branch}", lambda: ctx.branch() == phase.expect_branch))
    if phase.expect_no_push:
        pairs.append(("nothing pushed to origin", lambda: ctx.not_pushed(phase.expect_branch or "dev")))
    return check_list(pairs)


# ---------- main ----------

def add_common_args(ap):
    ap.add_argument("--phases", default=None, help="comma-separated phase keys to run (default: all, in order)")
    ap.add_argument("--model")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD per phase (default 2.0)")
    ap.add_argument("--claude", help="path to the claude binary (default: $CLAUDE_BIN, PATH, desktop app)")
    ap.add_argument("--clean", action="store_true", help="delete the fixture project afterwards (transcripts and report stay)")
    ap.add_argument("--dry-run", action="store_true", help="build the fixture, do not call claude")


def run(testplan, args, results_dir):
    """Run `testplan` under `args` (see add_common_args), writing results under results_dir.
    Returns a process exit code (0 success, 1 a phase's goal was missed)."""
    all_keys = [p.key for p in testplan.phases]
    keys = args.phases.split(",") if args.phases else all_keys
    bad = [k for k in keys if k not in all_keys]
    if bad:
        sys.exit(f"unknown phase: {bad}; choose from {all_keys}")
    by_key = {p.key: p for p in testplan.phases}
    claude = find_claude(args.claude)
    if not claude and not args.dry_run:
        sys.exit("claude CLI not found; pass --claude PATH or set CLAUDE_BIN")

    run_dir = results_dir / f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
    root = run_dir / "fixture"
    root.mkdir(parents=True)
    project, ctx_extra = testplan.build_project(root)
    ctx_factory = testplan.ctx_factory or Ctx
    print(f"test plan: {testplan.name}\nrun dir:   {run_dir}\nclaude:    {claude}\n")
    report = {"started": datetime.datetime.now().isoformat(timespec="seconds"), "test_plan": testplan.name,
              "model": args.model, "project": str(project), "phases": []}
    failed = False
    try:
        for key in keys:
            phase = by_key[key]
            entry = {"phase": key, "skill": phase.skill}
            if failed:
                entry["status"] = "skipped"
            elif args.dry_run:
                entry["status"] = "dry-run"
                print(f"[{key}] prompt {len(skill_prompt(testplan.plugin_dir, phase.skill, phase.note))} chars")
            else:
                print(f"[{key}] running {phase.skill} ...", flush=True)
                res = run_claude(claude, project, testplan.plugin_dir, phase, testplan.system_prompt, args)
                (run_dir / f"{key}.jsonl").write_text(res["raw"], encoding="utf-8")
                (run_dir / f"{key}.md").write_text(render_transcript(phase, res["prompt"], res["raw"]), encoding="utf-8")
                ctx = ctx_factory(project, res["tool_calls"], **ctx_extra)
                checks = general_checks(phase, res, ctx) + phase.checks(ctx)
                reached = all(ok for _, ok in checks) and not res["error"]
                entry.update(status="reached" if reached else "FAILED", metrics=res["metrics"],
                             checks=[{"name": n, "ok": ok} for n, ok in checks],
                             claude_error=res["error"], stderr=res["stderr"], final_text=res["result_text"][-600:],
                             tools=[t["input"].get("command", t["name"])[:160] for t in res["tool_calls"]])
                for n, ok in checks:
                    print(f"    {'ok  ' if ok else 'FAIL'} {n}")
                if res["error"]:
                    print(f"    FAIL claude run error (exit {res['exit_code']}): {res['stderr'] or res['result_text'][:200]}")
                failed = not reached
            report["phases"].append(entry)
    finally:
        if args.clean:
            shutil.rmtree(root, ignore_errors=True)
            print("\nfixture deleted (--clean)")
        else:
            print(f"\nproject kept at {project}")

    ran = [p for p in report["phases"] if "metrics" in p]
    tot = {k: sum(p["metrics"][k] for p in ran) for k in
           ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens", "cost_usd", "turns", "duration_s")}
    report["total"] = tot
    report["goal_reached"] = bool(ran) and all(p["status"] == "reached" for p in report["phases"])

    if ran:
        print(f"\n{'phase':<9}{'goal':<9}{'in':>8}{'out':>8}{'cache_r':>10}{'cache_w':>9}{'turns':>6}{'sec':>7}{'usd':>8}")
        for p in report["phases"]:
            m = p.get("metrics")
            if m:
                print(f"{p['phase']:<9}{p['status']:<9}{m['input_tokens']:>8}{m['output_tokens']:>8}"
                      f"{m['cache_read_tokens']:>10}{m['cache_creation_tokens']:>9}{m['turns']:>6}"
                      f"{m['duration_s']:>7}{m['cost_usd']:>8.3f}")
            else:
                print(f"{p['phase']:<9}{p['status']}")
        print(f"{'total':<9}{'YES' if report['goal_reached'] else 'NO':<9}{tot['input_tokens']:>8}{tot['output_tokens']:>8}"
              f"{tot['cache_read_tokens']:>10}{tot['cache_creation_tokens']:>9}{tot['turns']:>6}"
              f"{tot['duration_s']:>7.1f}{tot['cost_usd']:>8.3f}")
        out = run_dir / "report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nreport: {out}")
    return 0 if args.dry_run or report["goal_reached"] else 1
