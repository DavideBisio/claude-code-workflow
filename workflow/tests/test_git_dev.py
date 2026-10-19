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
                          encoding="utf-8", cwd=cwd, input=stdin)


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

    def test_stdio_is_utf8_whatever_the_console_code_page(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "create_requirement", "arguments": {"title": "Á — ü"}}}
        res = subprocess.run([sys.executable, str(REQ)], capture_output=True,
                             input=(json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        reply = json.loads(res.stdout.decode("utf-8"))
        self.assertIn("Á — ü", json.loads(reply["result"]["content"][0]["text"])["data"]["title"])


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
                                   "tracker_file": "version-control.json", "issue_backed": False})

    def test_provider_honors_config_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: github_labels\n", encoding="utf-8")
            out = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out, {"name": "github-req-tracker",
                                   "command": [sys.executable, str(GH_REQ)],
                                   "tracker_file": "req-tracker.json", "issue_backed": True})

    def test_provider_resolves_custom_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: req_tracker\n"
                f"    command: {sys.executable}\n    args: {REQ}\n", encoding="utf-8")
            out = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out, {"name": "my_custom", "command": [sys.executable, str(REQ)],
                                   "tracker_file": "req-tracker.json", "issue_backed": False})
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

    def test_set_backend_accepts_custom_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            config = Path(tmp) / "git-dev.data" / "config.yaml"
            config.write_text("providers:\n  my_jira:\n    kind: req_tracker\n"
                              f"    command: {sys.executable}\n    args: {REQ}\n", encoding="utf-8")
            res = run(DATA, "set-backend", "req_tracker", "my_jira", cwd=tmp)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)["name"], "my_jira")
            # a custom provider of the other kind is still rejected
            self.assertNotEqual(run(DATA, "set-backend", "version_control", "my_jira", cwd=tmp).returncode, 0)

    def test_set_backend_finds_header_with_trailing_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            config = Path(tmp) / "git-dev.data" / "config.yaml"
            config.write_text("backends:  # chosen at setup\n  version_control: github\n", encoding="utf-8")
            run(DATA, "set-backend", "req_tracker", "github_labels", cwd=tmp)
            text = config.read_text(encoding="utf-8")
            self.assertEqual(text.count("backends:"), 1)
            cfg = miniconfig.load(config)
            self.assertEqual(cfg["backends"], {"version_control": "github", "req_tracker": "github_labels"})

    def test_custom_provider_args_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: req_tracker\n"
                f"    command: {sys.executable}\n    args:\n      - -I\n      - {REQ}\n", encoding="utf-8")
            out = json.loads(run(DATA, "provider", "req_tracker", cwd=tmp).stdout)
            self.assertEqual(out["command"], [sys.executable, "-I", str(REQ)])

    def test_custom_provider_without_command_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  req_tracker: my_custom\n"
                "providers:\n  my_custom:\n    kind: req_tracker\n", encoding="utf-8")
            res = run(DATA, "provider", "req_tracker", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("command", res.stderr)
            self.assertNotIn("Traceback", res.stderr)

    def test_provider_error_reaches_the_caller(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            failing = Path(tmp) / "failing.py"
            failing.write_text("import json, sys\n"
                               "print(json.dumps({'error': 'gh auth login required'}))\n"
                               "sys.exit(1)\n", encoding="utf-8")
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "backends:\n  version_control: broken\n"
                "providers:\n  broken:\n    kind: version_control\n"
                f"    command: {sys.executable}\n    args: {failing}\n", encoding="utf-8")
            res = run(DATA, "fetch", cwd=tmp)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("gh auth login required", res.stderr)
            self.assertNotIn("Traceback", res.stderr)


class ProviderCall(unittest.TestCase):
    def test_call_reads_args_from_stdin_untouched_by_the_shell(self):
        title = "Don't crash on 'quotes' $(touch pwned) and ünïcode"
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(DATA, "call", "version_control", "create_issue", cwd=tmp,
                      stdin=json.dumps({"title": title}, ensure_ascii=False))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout)["data"]["title"], title)
            self.assertFalse((Path(tmp) / "pwned").exists())

    def test_call_with_empty_stdin_means_no_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            res = run(DATA, "call", "req_tracker", "list_requirements", cwd=tmp, stdin="")
            self.assertEqual(len(json.loads(res.stdout)), 3)

    def test_call_rejects_bad_json_and_unknown_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            self.assertNotEqual(run(DATA, "call", "req_tracker", "list_requirements", cwd=tmp,
                                    stdin="{nope").returncode, 0)
            self.assertNotEqual(run(DATA, "call", "nope", "list_issues", cwd=tmp, stdin="").returncode, 0)


class NextStep(unittest.TestCase):
    def _next(self, state, *flags):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "state.json").write_text(json.dumps(state), encoding="utf-8")
            return json.loads(run(DATA, "next-step", *flags, cwd=tmp).stdout)["step"]

    def test_record_step_stores_a_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            state = json.loads(run(DATA, "record-step", "git-dev-target", cwd=tmp).stdout)
            self.assertRegex(state["git-dev-target"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")

    def test_fresh_state_starts_at_target(self):
        self.assertEqual(self._next({}), "git-dev-target")

    def test_second_issue_on_the_same_day(self):
        # A full run finished in the morning; a new target was picked the same afternoon.
        state = {"git-dev-target": "2026-10-19T14:00:00", "git-dev-plan": "2026-10-19T09:10:00",
                 "git-dev-execute": "2026-10-19T09:20:00", "git-dev-update": "2026-10-19T09:30:00"}
        self.assertEqual(self._next(state), "git-dev-plan")

    def test_completed_run_goes_back_to_target(self):
        state = {"git-dev-target": "2026-10-19T09:00:00", "git-dev-plan": "2026-10-19T09:10:00",
                 "git-dev-execute": "2026-10-19T09:20:00", "git-dev-update": "2026-10-19T09:30:00"}
        self.assertEqual(self._next(state), "git-dev-target")

    def test_review_only_counts_when_asked(self):
        state = {"git-dev-target": "2026-10-19T09:00:00", "git-dev-plan": "2026-10-19T09:10:00",
                 "git-dev-execute": "2026-10-19T09:20:00"}
        self.assertEqual(self._next(state), "git-dev-update")
        self.assertEqual(self._next(state, "--review"), "git-dev-review")
        reviewed = {**state, "git-dev-review": "2026-10-19T09:25:00"}
        self.assertEqual(self._next(reviewed, "--review"), "git-dev-update")


class SkillStructure(unittest.TestCase):
    def test_setup_skill_extracted_from_run(self):
        setup_skill = ROOT / "skills" / "git-dev-setup" / "SKILL.md"
        run_skill = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(setup_skill.exists())
        self.assertNotIn("pick a backend for each tracker before anything else runs", run_skill)
        self.assertIn("git-dev-setup", run_skill)

    def test_code_fences_are_balanced_and_closed_bare(self):
        """A closing fence with trailing text (``` For each) is not a fence: the rest of the skill
        would render as code."""
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            open_ = False
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("```"):
                    if open_:
                        self.assertEqual(line.strip(), "```", f"{path.parent.name}:{n}")
                    open_ = not open_
            self.assertFalse(open_, f"{path.parent.name}: unclosed fence")

    def test_no_json_in_shell_quotes(self):
        """JSON carrying tracker/user text goes through a quoted heredoc, never '<json>' on the
        command line, where a `'` in a title ends the quoting and runs the rest as a command."""
        import re
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"'\{|'<json", text), path.parent.name)
            self.assertNotIn("provider-command>", text, path.parent.name)

    def test_update_opens_pr_before_marking_coverage_and_returns_to_source(self):
        text = (ROOT / "skills" / "git-dev-update" / "SKILL.md").read_text(encoding="utf-8")
        op = text[text.index("## Operation"):]
        self.assertLess(op.index("create_merge_request"), op.index("update_coverage"))
        self.assertLess(op.index("update_coverage"), op.index("git switch <plan.source_branch>"))

    def test_run_rebases_only_the_source_branch(self):
        text = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("skip the rebase", text)
        self.assertIn("only when the current branch is <source_branch>", text)


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

    @staticmethod
    def _gate(skill):
        text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        return text.split("## User gate", 1)[1].split("\n## ", 1)[0]

    def test_skippable_gates_act_on_the_ungated_flag(self):
        for skill in ("git-dev-target", "git-dev-plan", "git-dev-execute", "git-dev-review"):
            self.assertIn("**ungated**", self._gate(skill), skill)

    def test_update_gate_is_never_skipped(self):
        gate = self._gate("git-dev-update")
        self.assertIn("never skipped", gate)
        self.assertNotIn("skip this confirmation", gate)

    def test_execute_stays_gated_with_real_providers(self):
        run_skill = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`git-dev-execute` is always gated when either provider is real", run_skill)
        self.assertIn("mock-", self._gate("git-dev-execute"))

    def test_run_selects_steps_through_next_step(self):
        run_skill = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("git_dev_data.py\" next-step", run_skill)
        self.assertNotIn("newer completion date", run_skill)

    def test_untrusted_tracker_text_is_called_out(self):
        for path in (ROOT / "skills" / "git-dev-target" / "SKILL.md", ROOT / "skills" / "git-dev-plan" / "SKILL.md",
                     ROOT / "skills" / "git-dev-execute" / "SKILL.md", *(ROOT / "agents").glob("*.md")):
            self.assertIn("untrusted", path.read_text(encoding="utf-8"), path.name)

    def test_run_skill_never_pushes(self):
        run_skill = (ROOT / "skills" / "git-dev-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("confirm before pushing", run_skill)
        self.assertIn("Never push the result", run_skill)

    def test_config_reads_auto_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "auto:\n  enabled: true\n  gates: plan,update\n", encoding="utf-8")
            out = json.loads(run(DATA, "config", "auto.enabled", cwd=tmp).stdout)
            self.assertEqual(out, {"value": True})
            out2 = json.loads(run(DATA, "config", "auto.gates", cwd=tmp).stdout)
            self.assertEqual(out2, {"value": "plan,update"})

    def test_config_returns_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            out = json.loads(run(DATA, "config", "auto.enabled", "false", cwd=tmp).stdout)
            self.assertEqual(out, {"value": False})

    def test_config_treats_empty_block_as_unset(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(DATA, "init", cwd=tmp)
            (Path(tmp) / "git-dev.data" / "config.yaml").write_text(
                "auto:\n  enabled: true\n  gates:\n", encoding="utf-8")
            out = json.loads(run(DATA, "config", "auto.gates", "", cwd=tmp).stdout)
            self.assertEqual(out, {"value": ""})

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

    def test_quotes_inline_hash_and_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "github:\n"
                "  repo: \"owner/name\"  # quoted\n"
                "  note: 'a#b'\n"
                "  url: http://x/#frag\n"
                "providers:\n"
                "  p:\n"
                "    args:\n"
                "      - one\n"
                "      - \"two words\"\n", encoding="utf-8")
            cfg = miniconfig.load(path)
            self.assertEqual(cfg["github"], {"repo": "owner/name", "note": "a#b", "url": "http://x/#frag"})
            self.assertEqual(cfg["providers"]["p"]["args"], ["one", "two words"])


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

    def test_multi_ref_lists_stay_with_their_keyword(self):
        for body, blocks, blocked_by in (
                ("Blocked by #3, #4", [], ["#3", "#4"]),
                ("Blocks #7 and #8", ["#7", "#8"], []),
                ("Blocks #1 & #2. Blocked by #3/#4, then see #9", ["#1", "#2"], ["#3", "#4"])):
            got = ghcli.blocking_refs(body)
            self.assertEqual(got, (blocks, blocked_by), body)
            # none of the keyword's refs leaks into the requirement link
            ref = ghcli.first_ref(body, exclude=got[0] + got[1])
            self.assertEqual(ref, "#9" if "#9" in body else None, body)


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
