"""Generic e2e driver: run a TestPlan's skills through the `claude` CLI on a throwaway project.

  python tests/e2e/run_e2e.py [--testplan PATH] [--phases k1,k2,...] [--model M]
                              [--budget USD] [--claude PATH] [--clean] [--dry-run]

This script is generic over which skills it drives: see harness.py for what a run actually does
(fixture, invoke, collect, verify, report) and how a TestPlan plugs a specific plugin's skills,
fixture template and goal checks into that engine. By default this runs testplan.py, next to this
file — the workflow plugin's run/target/plan/execute/update workflow. Point --testplan at another
module exposing a module-level `TESTPLAN = harness.TestPlan(...)` to exercise a different
plugin's skills with the same engine, no changes to harness.py required.

It spends real tokens. Stdlib only. Exit code 1 if any goal check fails.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
DEFAULT_TESTPLAN = Path(__file__).resolve().parent / "testplan.py"


def load_testplan(path):
    spec = importlib.util.spec_from_file_location("testplan", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TESTPLAN


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--testplan", default=str(DEFAULT_TESTPLAN),
                     help="path to a module exposing TESTPLAN (default: testplan.py next to this file)")
    harness.add_common_args(ap)
    args = ap.parse_args()

    testplan_path = Path(args.testplan)
    if not testplan_path.is_file():
        sys.exit(f"testplan not found: {testplan_path}")
    testplan = load_testplan(testplan_path)

    sys.exit(harness.run(testplan, args, RESULTS))


if __name__ == "__main__":
    main()
