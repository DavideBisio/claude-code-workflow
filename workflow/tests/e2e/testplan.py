"""Test plan for workflow: the run/target/plan/execute/update workflow, plugged into the
generic engine in harness.py. Fixture: a throwaway Python project (tests/e2e/fixtures/basic-python/)
with a bare origin and an upstream README commit for git-dev-run to rebase onto, plus a bug
matching issue 2 / REQ-2 in the mock tracker data for the rest of the workflow to fix.

Only this file (and the fixture template) is specific to workflow; harness.py has no
knowledge of its skills, data files or mock servers. A different plugin gets the same engine by
writing its own `testplan.py`-shaped module and pointing `run_e2e.py --testplan` at it.
"""
import json
import subprocess
import sys
from pathlib import Path

from harness import Ctx, Phase, TestPlan, build_git_fixture, check_list, git

PLUGIN = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "fixtures" / "basic-python"


# ---------- fixture ----------

def post_init(seed):
    """Create git-dev.data/ via the plugin's own script, then fill in the two files a real user
    would edit by hand before running git-dev-run for the first time."""
    subprocess.run([sys.executable, str(PLUGIN / "scripts" / "git_dev_data.py"), "init"],
                   cwd=seed, capture_output=True, check=True)
    (seed / "git-dev.data" / "config.yaml").write_text(
        "test_command: python -m unittest\n", encoding="utf-8")
    (seed / "git-dev.data" / "project-prompt.md").write_text(
        "Small Python project. Run tests with `python -m unittest` from the project root. "
        "Put tests in `tests/` (unittest), code in `app/`. Keep changes minimal.\n", encoding="utf-8")


def diverge(seed):
    """Another developer pushes a README change after `project` is cloned, so git-dev-run's own
    rebase step (section 1 of its SKILL.md) has work to do."""
    (seed / "README.md").write_text("# demo\n\nUpdated by another developer.\n", encoding="utf-8")


def build_project(root):
    return build_git_fixture(root, TEMPLATE, branch="dev", post_init=post_init, diverge=diverge)


# ---------- goal checks ----------
# Git-level checks shared across phases (clean tree, still on dev, nothing pushed) are declared
# as Phase flags below and covered by harness.general_checks; everything here is specific to what
# that one skill is supposed to have produced.

class WorkflowCtx(Ctx):
    pass


def checks_run(c):
    return check_list([
        ("tracker data fetched", lambda: len(c.read_json("git-dev.data/tracker/version-control.json")["issues"]) == 3),
        ("dev rebased onto origin/dev", lambda: subprocess.run(
            ["git", "merge-base", "--is-ancestor", "origin/dev", "HEAD"], cwd=c.p,
            capture_output=True).returncode == 0
            and "docs: update README" in git("log", "--format=%s", cwd=c.p)),
        ("git-dev.data committed", lambda: git("log", "-1", "--format=%s", cwd=c.p).startswith("chore")),
    ])


def checks_target(c):
    t = lambda: c.read_json("git-dev.data/work/target.json")
    return check_list([
        ("target.json names issue 2", lambda: json.dumps(t()).count('"iid": 2') >= 1),
        ("target.json has REQ-2", lambda: "REQ-2" in json.dumps(t())),
        ("step date recorded", lambda: "git-dev-target" in c.read_json("git-dev.data/state.json")),
    ])


def checks_plan(c):
    plan = lambda: (c.p / "git-dev.data/work/plan.md").read_text(encoding="utf-8")
    return check_list([
        ("plan.md names branch fix/2-", lambda: "fix/2-" in plan()),
        ("plan.md covers REQ-2 and coverage", lambda: "REQ-2" in plan() and "coverage" in plan().lower()),
        ("step date recorded", lambda: "git-dev-plan" in c.read_json("git-dev.data/state.json")),
    ])


def checks_execute(c):
    res = lambda: c.read_json("git-dev.data/work/result.json")
    return check_list([
        ("on branch fix/2-*", lambda: c.branch().startswith("fix/2-")),
        ("result.json: failed before, passed after",
            lambda: (res()["test_before"], res()["test_after"]) == ("failed", "passed")),
        ("fix commit ahead of dev with code and test", lambda: (
            git("rev-list", "--count", "dev..HEAD", cwd=c.p) != "0"
            and any(f.startswith("app/") for f in git("diff", "--name-only", "dev", "HEAD", cwd=c.p).split())
            and any(f.startswith("tests/") for f in git("diff", "--name-only", "dev", "HEAD", cwd=c.p).split()))),
        ("commit message refs issue and REQ-2", lambda: all(
            s in git("log", "-1", "--format=%B", "HEAD", cwd=c.p) for s in ("#2", "REQ-2"))),
        ("test suite passes", lambda: subprocess.run(
            [sys.executable, "-m", "unittest"], cwd=c.p, capture_output=True).returncode == 0),
        ("empty input rejected with ValueError, not IndexError", lambda: subprocess.run(
            [sys.executable, "-c",
             "from app.parse import first_word\n"
             "try:\n    first_word('')\nexcept ValueError:\n    raise SystemExit(0)\n"
             "except Exception:\n    raise SystemExit(2)\nraise SystemExit(3)"],
            cwd=c.p, capture_output=True).returncode == 0),
    ])


def checks_update(c):
    cmds = c.commands()
    return check_list([
        ("coverage updated via mock-req-tracker", lambda: any(
            ("update_coverage" in s or "create_coverage" in s) and "mock-req-tracker" in s for s in cmds)),
        ("merge request created via mock-version-control", lambda: any("create_merge_request" in s for s in cmds)),
        ("all four steps recorded", lambda: {"git-dev-target", "git-dev-plan", "git-dev-execute",
                                             "git-dev-update"} <= set(c.read_json("git-dev.data/state.json"))),
        ("git-dev.data committed", lambda: git("log", "-1", "--format=%s", cwd=c.p).startswith("chore")),
    ])


TESTPLAN = TestPlan(
    name="workflow",
    plugin_dir=PLUGIN,
    build_project=build_project,
    ctx_factory=WorkflowCtx,
    phases=[
        Phase("run", "git-dev-run", checks=checks_run, expect_clean_tree=True, expect_branch="dev", expect_no_push=True,
              note="When step 3 asks what to do, answer 'Return status', give the status, then STOP (do not loop back)."),
        Phase("target", "git-dev-target", checks=checks_target, expect_branch="dev"),
        Phase("plan", "git-dev-plan", checks=checks_plan, expect_branch="dev"),
        Phase("execute", "git-dev-execute", checks=checks_execute, expect_no_push=True),
        Phase("update", "git-dev-update", checks=checks_update, expect_clean_tree=True, expect_no_push=True),
    ],
)
