"""Smoke tests for the mock servers and the data script. Run: python -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "mcp" / "mock-version-control" / "server.py"
REQ = ROOT / "mcp" / "mock-req-tracker" / "server.py"
GH_DEV = ROOT / "mcp" / "github-version-control" / "server.py"
GH_REQ = ROOT / "mcp" / "github-req-tracker" / "server.py"
DATA = ROOT / "scripts" / "git_dev_data.py"
sys.path.insert(0, str(ROOT / "mcp" / "common"))
import miniconfig  # noqa: E402
import ghcli  # noqa: E402


def run(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, input=stdin)


class MockServers(unittest.TestCase):
    def test_list_with_filter(self):
        out = json.loads(run(DEV, "list_issues", '{"filter":{"state":"opened"}}').stdout)
        self.assertEqual([i["iid"] for i in out], [2, 3])

    def test_first_opened_issue_maps_to_failing_requirement(self):
        issue = json.loads(run(DEV, "list_issues", '{"filter":{"state":"opened"}}').stdout)[0]
        cov = json.loads(run(REQ, "list_coverage").stdout)
        by_req = {c["requirement_id"]: c for c in cov}
        self.assertEqual(by_req[issue["requirements"][0]]["result"], "failed")

    def test_create_and_update_are_acks(self):
        for server, tool in ((DEV, "create_merge_request"), (REQ, "update_coverage")):
            out = json.loads(run(server, tool, '{"id":"x"}').stdout)
            self.assertTrue(out["ok"] and out["mock"])

    def test_unknown_tool_fails(self):
        res = run(DEV, "nope")
        self.assertEqual(res.returncode, 1)
        self.assertIn("error", json.loads(res.stdout))

    def test_stdio_roundtrip(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "get_requirement", "arguments": {"id": "REQ-2"}}}]
        res = run(REQ, stdin="\n".join(json.dumps(m) for m in msgs) + "\n")
        replies = [json.loads(line) for line in res.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "mock-req-tracker")
        self.assertIn("update_coverage", [t["name"] for t in replies[1]["result"]["tools"]])
        self.assertIn("REQ-2", replies[2]["result"]["content"][0]["text"])


class DataScript(unittest.TestCase):
    def test_init_fetch_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(json.loads(run(DATA, "init", cwd=tmp).stdout)["created"])
            self.assertFalse(json.loads(run(DATA, "init", cwd=tmp).stdout)["created"])
            run(DATA, "fetch", cwd=tmp)
            dev = json.loads((Path(tmp) / "git-dev.data/tracker/version-control.json").read_text())
            req = json.loads((Path(tmp) / "git-dev.data/tracker/req-tracker.json").read_text())
            self.assertEqual(len(dev["issues"]), 3)
            self.assertEqual(len(req["requirements"]), 3)
            run(DATA, "record-step", "git-dev-target", cwd=tmp)
            state = json.loads((Path(tmp) / "git-dev.data/state.json").read_text())
            self.assertIn("git-dev-target", state)

    def test_provider_defaults_to_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(DATA, "provider", "version_control", cwd=tmp).stdout)
            self.assertEqual(out, {"name": "mock-version-control",
                                   "command": [sys.executable, str(DEV)],
                                   "tracker_file": "version-control.json"})

    def test_provider_honors_config_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: github_labels\n", encoding="utf-8")
            out = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out, {"name": "github-req-tracker",
                                   "command": [sys.executable, str(GH_REQ)],
                                   "tracker_file": "req-tracker.json"})

    def test_provider_resolves_custom_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: req_tracker\n"
                f"    command: {sys.executable}\n    args: {REQ}\n", encoding="utf-8")
            out = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out, {"name": "my_custom", "command": [sys.executable, str(REQ)],
                                   "tracker_file": "req-tracker.json"})
            tools_res = subprocess.run([*out["command"], "tools"], capture_output=True, text=True, cwd=tmp)
            tools = json.loads(tools_res.stdout)
            self.assertIn("list_requirements", {t["name"] for t in tools})

    def test_provider_kind_mismatch_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: version_control\n"
                f"    command: {sys.executable}\n    args: {REQ}\n", encoding="utf-8")
            res = run(DATA, "provider", "req_tracker", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("my_custom", res.stderr)

    def test_check_provider_reports_missing_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(DATA, "check-provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out, {"provider": "mock-req-tracker", "missing": [], "ok": True})

            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: req_tracker\n"
                f"    command: {sys.executable}\n    args: {DEV}\n", encoding="utf-8")
            out = json.loads(run(DATA, "check-provider", "req_tracker", cwd=tmp).stdout)
            self.assertFalse(out["ok"])
            self.assertIn("list_requirements", out["missing"])

    def test_unknown_backend_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: not_a_backend\n", encoding="utf-8")
            res = run(DATA, "provider", "req_tracker", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)

    def test_providers_lists_choices_without_hardcoding(self):
        out = json.loads(run(DATA, "providers").stdout)
        self.assertEqual(out, {"version_control": ["mock", "github"], "req_tracker": ["mock", "github_labels"]})

    def test_providers_lists_custom_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "providers:\n  my_custom:\n    kind: req_tracker\n"
                f"    command: {sys.executable}\n    args: {REQ}\n", encoding="utf-8")
            out = json.loads(run(DATA, "providers", cwd=tmp).stdout)
            self.assertIn("my_custom", out["req_tracker"])
            self.assertNotIn("my_custom", out["version_control"])

    def test_set_backend_appends_block_and_preserves_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            config = Path(tmp) / "git-dev.data" / "config.yaml"
            before = config.read_text(encoding="utf-8")
            out = json.loads(run(DATA, "set-backend", "req_tracker", "github_labels", cwd=tmp).stdout)
            self.assertEqual(out, {"backends": {"req_tracker": "github_labels"}})
            after = config.read_text(encoding="utf-8")
            self.assertTrue(after.startswith(before.rstrip("\n")))
            self.assertIn("backends:\n  req_tracker: github_labels", after)
            fetched = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(fetched["name"], "github-req-tracker")

    def test_set_backend_updates_existing_key_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            run(DATA, "set-backend", "version_control", "github", cwd=tmp)
            run(DATA, "set-backend", "req_tracker", "github_labels", cwd=tmp)
            run(DATA, "set-backend", "version_control", "mock", cwd=tmp)
            lines = (Path(tmp) / "git-dev.data" / "config.yaml").read_text(encoding="utf-8").splitlines()
            self.assertEqual([l for l in lines if l == "  version_control: mock"], ["  version_control: mock"])
            self.assertIn("  req_tracker: github_labels", lines)

    def test_set_backend_rejects_unknown_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(DATA, "set-backend", "version_control", "gitlab", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)


class SkillStructure(unittest.TestCase):
    def test_setup_skill_extracted_from_run(self):
        setup_skill = ROOT / "skills" / "git-dev-setup" / "SKILL.md"
        run_skill = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(setup_skill.exists())
        self.assertNotIn("pick a backend for each tracker before anything else runs", run_skill)
        self.assertIn("git-dev-setup", run_skill)


def _frontmatter_tools(path):
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("tools:"):
            return {t.strip() for t in line.split(":", 1)[1].split(",")}
    return set()


class AgentDefinitions(unittest.TestCase):
    def test_executor_can_edit_and_run_commands(self):
        tools = _frontmatter_tools(ROOT / "agents" / "executor.md")
        self.assertEqual(tools, {"Read", "Write", "Edit", "Bash", "Grep", "Glob"})

    def test_reviewer_is_read_only(self):
        tools = _frontmatter_tools(ROOT / "agents" / "reviewer.md")
        self.assertEqual(tools, {"Read", "Grep", "Glob"})

    def test_explorer_is_read_only(self):
        tools = _frontmatter_tools(ROOT / "agents" / "explorer.md")
        self.assertEqual(tools, {"Read", "Grep", "Glob"})


class SubagentWiring(unittest.TestCase):
    def test_review_skill_exists_and_dispatches_to_reviewer_agent(self):
        text = (ROOT / "skills" / "git-dev-review" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("workflow:reviewer", text)

    def test_execute_dispatches_to_executor_agent(self):
        text = (ROOT / "skills" / "git-dev-execute" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("workflow:executor", text)

    def test_plan_dispatches_to_explorer_agent(self):
        text = (ROOT / "skills" / "git-dev-plan" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("workflow:explorer", text)


class AutoMode(unittest.TestCase):
    def test_run_chains_steps_when_auto_enabled(self):
        text = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("auto.enabled", text)

    def test_each_gated_step_can_skip_its_gate_in_auto_mode(self):
        for skill in ("git-dev-target", "git-dev-plan", "git-dev-execute", "git-dev-update", "git-dev-review"):
            text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("auto mode", text.lower())

    def test_config_reads_auto_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "auto:\n  enabled: true\n  gates: plan,update\n", encoding="utf-8")
            out = json.loads(run(DATA, "config", "auto.enabled", cwd=tmp).stdout)
            self.assertEqual(out, {"value": "true"})
            out2 = json.loads(run(DATA, "config", "auto.gates", cwd=tmp).stdout)
            self.assertEqual(out2, {"value": "plan,update"})

    def test_config_returns_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(DATA, "config", "auto.enabled", "false", cwd=tmp).stdout)
            self.assertEqual(out, {"value": "false"})

    def test_config_returns_null_when_missing_and_no_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(DATA, "config", "auto.enabled", cwd=tmp).stdout)
            self.assertIsNone(out["value"])


class MiniConfig(unittest.TestCase):
    def test_nested_keys_and_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "# a comment\n"
                "backends:\n"
                "  version_control: github\n"
                "github:\n"
                "  repo: owner/name\n"
                "  labels:\n"
                "    requirement: req\n", encoding="utf-8")
            cfg = miniconfig.load(path)
            self.assertEqual(miniconfig.get(cfg, "backends.version_control"), "github")
            self.assertEqual(miniconfig.get(cfg, "github.labels.requirement"), "req")
            self.assertIsNone(miniconfig.get(cfg, "github.labels.missing"))
            self.assertEqual(miniconfig.get(cfg, "github.labels.missing", "req"), "req")

    def test_missing_file_is_empty(self):
        self.assertEqual(miniconfig.load(Path("does/not/exist.yaml")), {})


class GhCli(unittest.TestCase):
    def test_blocks_and_blocked_by_refs(self):
        blocks, blocked_by = ghcli.blocking_refs(
            "Blocks #18, it's a prerequisite for subagents. Blocked by #5 for now.")
        self.assertEqual(blocks, ["#18"])
        self.assertEqual(blocked_by, ["#5"])

    def test_no_refs_returns_empty_lists(self):
        self.assertEqual(ghcli.blocking_refs(""), ([], []))
        self.assertEqual(ghcli.blocking_refs(None), ([], []))

    def test_blocked_by_not_also_matched_as_blocks(self):
        blocks, blocked_by = ghcli.blocking_refs("Blocked by #7")
        self.assertEqual(blocks, [])
        self.assertEqual(blocked_by, ["#7"])

    def test_first_ref_skips_excluded_numbers(self):
        self.assertEqual(
            ghcli.first_ref("Blocks #18, it's a prerequisite. See also #20.", exclude=["#18"]), "#20")

    def test_first_ref_default_behavior_unchanged(self):
        self.assertEqual(ghcli.first_ref("Refs #5 and #6"), "#5")


class GithubProviders(unittest.TestCase):
    """Only the no-`gh`-call surface: tool listings and the CLI error paths. Anything that shells
    out to `gh` is exercised manually against a real repo, not in CI."""

    def test_tools_listed(self):
        dev_tools = {t["name"] for t in json.loads(run(GH_DEV, "tools").stdout)}
        req_tools = {t["name"] for t in json.loads(run(GH_REQ, "tools").stdout)}
        self.assertEqual(dev_tools, {"list_issues", "get_issue", "create_issue", "update_issue",
                                     "list_merge_requests", "get_merge_request",
                                     "create_merge_request", "list_milestones", "get_milestone"})
        self.assertEqual(req_tools, {"list_requirements", "get_requirement", "create_requirement",
                                     "list_coverage", "get_coverage",
                                     "create_coverage", "update_coverage", "list_specifications",
                                     "get_specification", "create_specification", "list_testplans"})

    def test_unknown_tool_fails(self):
        res = run(GH_DEV, "nope")
        self.assertEqual(res.returncode, 1)
        self.assertIn("error", json.loads(res.stdout))


if __name__ == "__main__":
    unittest.main()
