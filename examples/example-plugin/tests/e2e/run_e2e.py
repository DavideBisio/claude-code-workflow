"""End-to-end test: run the example-plugin skills with the `claude` CLI on a throwaway project.

  python tests/e2e/run_e2e.py [--phases run,target,plan,execute,update] [--model M]
                              [--budget USD] [--claude PATH] [--clean] [--dry-run]

For each phase it calls `claude -p` (stream-json) with the skill text as the prompt, then checks the
resulting git/file state ("goal reached") and collects token usage, cost, turns and duration.
Everything lands in results/<timestamp>/ (gitignored): fixture/project (the test project, a git repo with
a local bare origin), <phase>.jsonl (raw event stream), <phase>.md (readable transcript), report.json.
It spends real tokens. Stdlib only. Exit code 1 if any goal check fails.

The skill text is sent inline (frontmatter stripped, ${CLAUDE_PLUGIN_ROOT} substituted), so the run
does not depend on skill auto-invocation; the plugin is still loaded with --plugin-dir for the MCP servers.
Confirmation gates are pre-approved through an appended system prompt.
"""
import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"

SKILLS = {"run": "example-run", "target": "example-target", "plan": "example-plan",
          "execute": "example-execute", "update": "example-update"}
PHASES = list(SKILLS)

PHASE_NOTE = {
    "run": "When step 3 asks what to do, answer 'Return status', give the status, then STOP (do not loop back).",
}
SYSTEM = ("Automated test run, no human is present, so there will be no reply to any question. "
          "The user's answer to every confirmation gate is already given: YES, approved, go ahead. "
          "At a gate, print the gate text with 'Answer: yes (pre-approved)', then continue in the same turn "
          "and finish the whole skill, including its Output and Summary sections. "
          "Never end your turn with a question. Work only inside the current directory.")


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


def skill_prompt(phase):
    text = (PLUGIN / "skills" / SKILLS[phase] / "SKILL.md").read_text(encoding="utf-8")
    body = text.split("---", 2)[2].strip().replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN.as_posix())
    note = PHASE_NOTE.get(phase, "")
    return (f"Execute the following skill now, in the current project, from start to finish.\n\n{body}\n\n"
            f"Every confirmation gate is pre-approved (answer: yes). Do not stop at a gate. {note}\n")


# ---------- fixture ----------

def build_project(root):
    """Target project with a bare origin, a filled example.data and a bug matching issue 2 / REQ-2."""
    origin, seed, project = root / "origin.git", root / "seed", root / "project"
    git("init", "-q", "--bare", "-b", "dev", str(origin), cwd=root)
    git("clone", "-q", str(origin), str(seed), cwd=root)
    for repo in (seed,):
        git("config", "user.name", "Seed Dev", cwd=repo)
        git("config", "user.email", "seed@example.test", cwd=repo)
    git("switch", "-q", "-c", "dev", cwd=seed)
    (seed / "app").mkdir()
    (seed / "app" / "__init__.py").write_text("")
    (seed / "app" / "parse.py").write_text(
        '"""Input parsing."""\n\n\ndef first_word(text):\n    return text.split()[0]\n')
    (seed / "tests").mkdir()
    (seed / "tests" / "__init__.py").write_text("")
    (seed / "tests" / "test_parse.py").write_text(
        "import unittest\nfrom app.parse import first_word\n\n\nclass ParseTest(unittest.TestCase):\n"
        "    def test_first_word(self):\n        self.assertEqual(first_word('hello world'), 'hello')\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n")
    (seed / "README.md").write_text("# demo\n")
    subprocess.run([sys.executable, str(PLUGIN / "scripts" / "example_data.py"), "init"],
                   cwd=seed, capture_output=True, check=True)
    (seed / "example.data" / "config.yaml").write_text("test_command: python -m unittest\n")
    (seed / "example.data" / "project-prompt.md").write_text(
        "Small Python project. Run tests with `python -m unittest` from the project root. "
        "Put tests in `tests/` (unittest), code in `app/`. Keep changes minimal.\n")
    git("add", "-A", cwd=seed)
    git("commit", "-q", "-m", "Initial project", cwd=seed)
    git("push", "-q", "-u", "origin", "dev", cwd=seed)
    git("clone", "-q", "-b", "dev", str(origin), str(project), cwd=root)
    git("config", "user.name", "Test User", cwd=project)
    git("config", "user.email", "user@example.test", cwd=project)
    # another developer pushes after the clone, so the rebase has work to do
    (seed / "README.md").write_text("# demo\n\nUpdated by another developer.\n")
    git("commit", "-q", "-am", "docs: update README", cwd=seed)
    git("push", "-q", "origin", "dev", cwd=seed)
    return project, git("rev-parse", "dev", cwd=origin)


# ---------- running claude ----------

def run_claude(claude, project, phase, args):
    cmd = [claude, "-p", "--output-format", "stream-json", "--verbose",
           "--plugin-dir", str(PLUGIN), "--permission-mode", "acceptEdits",
           "--allowed-tools", "Bash,Read,Write,Edit,Glob,Grep",
           "--append-system-prompt", SYSTEM, "--no-session-persistence",
           "--max-budget-usd", str(args.budget)]
    if args.model:
        cmd += ["--model", args.model]
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    started = datetime.datetime.now()
    res = subprocess.run(cmd, cwd=project, input=skill_prompt(phase), capture_output=True, text=True,
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

    out = [f"# {phase} ({SKILLS[phase]})\n", "## Prompt\n", prompt, "\n## Conversation\n"]
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            out.append(f"```\n{line}\n```")
            continue
        kind = ev.get("type")
        content = ev.get("message", {}).get("content", [])
        if kind == "assistant":
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


# ---------- goal checks ----------

class Ctx:
    def __init__(self, project, origin_dev, tools):
        self.p, self.origin_dev, self.tools = project, origin_dev, tools
        self.origin = project.parent / "origin.git"

    def read_json(self, rel):
        return json.loads((self.p / rel).read_text(encoding="utf-8"))

    def commands(self):
        return [t["input"].get("command", "") for t in self.tools if t["name"] == "Bash"]

    def clean(self):
        return git("status", "--porcelain", cwd=self.p) == ""

    def not_pushed(self):
        branches = git("branch", "--list", cwd=self.origin).replace("*", "").split()
        return branches == ["dev"] and git("rev-parse", "dev", cwd=self.origin) == self.origin_dev


def checks_for(phase, c):
    out = []

    def add(name, fn):
        try:
            ok = bool(fn())
        except Exception as e:  # missing file, bad json...
            ok = False
            name = f"{name} ({type(e).__name__}: {e})"
        out.append((name, ok))

    if phase == "run":
        add("tracker data fetched", lambda: len(c.read_json("example.data/tracker/dev-status.json")["issues"]) == 3)
        add("dev rebased onto origin/dev", lambda: subprocess.run(
            ["git", "merge-base", "--is-ancestor", "origin/dev", "HEAD"], cwd=c.p).returncode == 0
            and "docs: update README" in git("log", "--format=%s", cwd=c.p))
        add("example.data committed", lambda: git("log", "-1", "--format=%s", cwd=c.p).startswith("chore"))
        add("clean tree, on dev", lambda: c.clean() and git("branch", "--show-current", cwd=c.p) == "dev")
        add("nothing pushed", c.not_pushed)
    elif phase == "target":
        t = lambda: c.read_json("example.data/work/target.json")
        add("target.json names issue 2", lambda: json.dumps(t()).count('"iid": 2') >= 1)
        add("target.json has REQ-2", lambda: "REQ-2" in json.dumps(t()))
        add("step date recorded", lambda: "example-target" in c.read_json("example.data/state.json"))
        add("still on dev, no new commit", lambda: git("branch", "--show-current", cwd=c.p) == "dev")
    elif phase == "plan":
        plan = lambda: (c.p / "example.data/work/plan.md").read_text(encoding="utf-8")
        add("plan.md names branch fix/2-", lambda: "fix/2-" in plan())
        add("plan.md covers REQ-2 and coverage", lambda: "REQ-2" in plan() and "coverage" in plan().lower())
        add("step date recorded", lambda: "example-plan" in c.read_json("example.data/state.json"))
        add("still on dev", lambda: git("branch", "--show-current", cwd=c.p) == "dev")
    elif phase == "execute":
        res = lambda: c.read_json("example.data/work/result.json")
        add("on branch fix/2-*", lambda: git("branch", "--show-current", cwd=c.p).startswith("fix/2-"))
        add("result.json: failed before, passed after",
            lambda: (res()["test_before"], res()["test_after"]) == ("failed", "passed"))
        add("fix commit ahead of dev with code and test", lambda: (
            git("rev-list", "--count", "dev..HEAD", cwd=c.p) != "0"
            and any(f.startswith("app/") for f in git("diff", "--name-only", "dev", "HEAD", cwd=c.p).split())
            and any(f.startswith("tests/") for f in git("diff", "--name-only", "dev", "HEAD", cwd=c.p).split())))
        add("commit message refs issue and REQ-2", lambda: all(
            s in git("log", "-1", "--format=%B", "HEAD", cwd=c.p) for s in ("#2", "REQ-2")))
        add("test suite passes", lambda: subprocess.run(
            [sys.executable, "-m", "unittest"], cwd=c.p, capture_output=True).returncode == 0)
        add("empty input rejected with ValueError, not IndexError", lambda: subprocess.run(
            [sys.executable, "-c",
             "from app.parse import first_word\n"
             "try:\n    first_word('')\nexcept ValueError:\n    raise SystemExit(0)\n"
             "except Exception:\n    raise SystemExit(2)\nraise SystemExit(3)"],
            cwd=c.p, capture_output=True).returncode == 0)
        add("nothing pushed", c.not_pushed)
    elif phase == "update":
        cmds = c.commands()
        add("coverage updated via req-tracker", lambda: any(
            ("update_coverage" in s or "create_coverage" in s) and "req-tracker" in s for s in cmds))
        add("merge request created via dev-status", lambda: any("create_merge_request" in s for s in cmds))
        add("all four steps recorded", lambda: {"example-target", "example-plan", "example-execute",
                                                "example-update"} <= set(c.read_json("example.data/state.json")))
        add("example.data committed", lambda: git("log", "-1", "--format=%s", cwd=c.p).startswith("chore"))
        add("clean tree", c.clean)
        add("nothing pushed", c.not_pushed)
    return out


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phases", default=",".join(PHASES))
    ap.add_argument("--model")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD per phase (default 2.0)")
    ap.add_argument("--claude", help="path to the claude binary (default: $CLAUDE_BIN, PATH, desktop app)")
    ap.add_argument("--clean", action="store_true", help="delete the fixture project afterwards (transcripts and report stay)")
    ap.add_argument("--dry-run", action="store_true", help="build the fixture, do not call claude")
    args = ap.parse_args()

    phases = args.phases.split(",")
    bad = [p for p in phases if p not in SKILLS]
    if bad:
        sys.exit(f"unknown phase: {bad}; choose from {PHASES}")
    claude = find_claude(args.claude)
    if not claude and not args.dry_run:
        sys.exit("claude CLI not found; pass --claude PATH or set CLAUDE_BIN")

    run_dir = RESULTS / f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
    root = run_dir / "fixture"
    root.mkdir(parents=True)
    project, origin_dev = build_project(root)
    print(f"run dir: {run_dir}\nclaude:  {claude}\n")
    report = {"started": datetime.datetime.now().isoformat(timespec="seconds"), "model": args.model,
              "project": str(project), "phases": []}
    failed = False
    try:
        for phase in phases:
            entry = {"phase": phase, "skill": SKILLS[phase]}
            if failed:
                entry["status"] = "skipped"
            elif args.dry_run:
                entry["status"] = "dry-run"
                print(f"[{phase}] prompt {len(skill_prompt(phase))} chars")
            else:
                print(f"[{phase}] running {SKILLS[phase]} ...", flush=True)
                run = run_claude(claude, project, phase, args)
                (run_dir / f"{phase}.jsonl").write_text(run["raw"], encoding="utf-8")
                (run_dir / f"{phase}.md").write_text(
                    render_transcript(phase, skill_prompt(phase), run["raw"]), encoding="utf-8")
                checks = checks_for(phase, Ctx(project, origin_dev, run["tool_calls"]))
                reached = all(ok for _, ok in checks) and not run["error"]
                entry.update(status="reached" if reached else "FAILED", metrics=run["metrics"],
                             checks=[{"name": n, "ok": ok} for n, ok in checks],
                             claude_error=run["error"], stderr=run["stderr"], final_text=run["result_text"][-600:],
                             tools=[t["input"].get("command", t["name"])[:160] for t in run["tool_calls"]])
                for n, ok in checks:
                    print(f"    {'ok  ' if ok else 'FAIL'} {n}")
                if run["error"]:
                    print(f"    FAIL claude run error (exit {run['exit_code']}): {run['stderr'] or run['result_text'][:200]}")
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
    sys.exit(0 if args.dry_run or report["goal_reached"] else 1)


if __name__ == "__main__":
    main()
