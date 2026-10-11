"""Hook tests against a throwaway mini-wisor git repo. Run: python3 -m unittest discover -s tests -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")

BASELINE = {
    "CLAUDE.md": "# wisor\n",
    "apps/api/src/presentation/http/dto/category.dto.ts": "export interface CategoryResponse { id: string }\n",
    "apps/web/src/features/categorization/types.ts": "/** Mirrors presentation/http/dto/category.dto.ts */\n",
    "apps/web/src/features/categorization/api.ts": "export {};\n",
}


def write(root, rel, text="x\n"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def run_hook(name, payload, root, data_dir):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root, CLAUDE_PLUGIN_DATA=data_dir)
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS, name)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mini-wisor-")
        self.data_dir = tempfile.mkdtemp(prefix="plugin-data-")
        for rel, text in BASELINE.items():
            write(self.root, rel, text)
        git(self.root, "init", "-q")
        git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        git(self.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.data_dir, ignore_errors=True)


class DocsSyncTest(HookTestCase):
    def stop(self, **extra):
        return run_hook("docs-sync.py", dict({"hook_event_name": "Stop", "stop_hook_active": False}, **extra),
                        self.root, self.data_dir)

    def test_clean_tree_passes(self):
        self.assertIsNone(self.stop())

    def test_r1_new_shared_block_without_docs_blocks(self):
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertIn("R1", out["reason"])
        self.assertIn("http-error.ts", out["reason"])

    def test_r1_passes_when_claude_md_updated(self):
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        write(self.root, "CLAUDE.md", "- HttpError …\n")
        self.assertIsNone(self.stop())

    def test_r1_ignores_tests_and_repository_adapters(self):
        write(self.root, "apps/web/src/shared/lib/money.test.ts")
        write(self.root, "apps/api/src/infrastructure/persistence/pg-obligation.repository.ts")
        self.assertIsNone(self.stop())

    def test_r2_non_hook_file_in_hooks_dir_blocks(self):
        write(self.root, "apps/web/src/features/categorization/categories-page/hooks/budget.ts")
        out = self.stop()
        self.assertIn("R2", out["reason"])
        self.assertIn("budget.ts", out["reason"])

    def test_r2_documented_web_files_pass(self):
        page = "apps/web/src/features/budgeting/obligations-page/"
        for rel in ("index.tsx", "index.test.tsx", "styles.module.css", "helpers.ts", "helpers.test.ts",
                    "hooks/use-obligations-page.ts", "hooks/use-obligation-form.ts"):
            write(self.root, page + rel)
        write(self.root, "apps/web/src/features/budgeting/api.ts")
        self.assertIsNone(self.stop())

    def test_r2_api_layers(self):
        write(self.root, "apps/api/src/domain/budgeting/obligation.entity.ts")
        write(self.root, "apps/api/src/application/budgeting/ports/obligation-repository.port.ts")
        write(self.root, "apps/api/src/application/budgeting/create-obligation.use-case.ts")
        self.assertIsNone(self.stop())
        write(self.root, "apps/api/src/domain/budgeting/obligation-utils.ts")
        self.assertIn("obligation-utils.ts", self.stop()["reason"])

    def test_r3_dto_change_without_mirror_blocks(self):
        write(self.root, "apps/api/src/presentation/http/dto/category.dto.ts", "// new field\n")
        out = self.stop()
        self.assertIn("R3", out["reason"])
        self.assertIn("features/categorization/types.ts", out["reason"])

    def test_r3_passes_when_mirror_updated(self):
        write(self.root, "apps/api/src/presentation/http/dto/category.dto.ts", "// new field\n")
        write(self.root, "apps/web/src/features/categorization/types.ts", "// new field\n")
        self.assertIsNone(self.stop())

    def test_r3_new_dto_without_web_yet_passes(self):
        write(self.root, "apps/api/src/presentation/http/dto/obligation.dto.ts")
        self.assertIsNone(self.stop())

    def test_r3_still_applies_when_docs_touched(self):
        write(self.root, "apps/api/src/presentation/http/dto/category.dto.ts", "// new field\n")
        write(self.root, "CLAUDE.md", "edit\n")
        self.assertIn("R3", self.stop()["reason"])

    def test_second_stop_is_allowed(self):
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        self.assertIsNone(self.stop(stop_hook_active=True))

    def test_block_is_logged(self):
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        self.stop()
        with open(os.path.join(self.data_dir, "hook-events.log"), encoding="utf-8") as f:
            self.assertIn("docs-sync\tblock", f.read())

    def test_outside_wisor_is_noop(self):
        shutil.rmtree(os.path.join(self.root, "apps/web"))
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        self.assertIsNone(self.stop())


class DocsSyncF1ReplayTest(HookTestCase):
    """Moments from wisor's F1, where CLAUDE.md already had uncommitted edits from an earlier step."""

    UNRELATED_CLAUDE_MD_EDIT = "\n### Конвенції CRUD-ендпоінтів\n- PATCH: відсутнє поле не змінюється; `{}` → 400.\n"

    def stop(self):
        return run_hook("docs-sync.py", {"hook_event_name": "Stop", "stop_hook_active": False},
                        self.root, self.data_dir)

    def test_p5_http_error_blocks_although_claude_md_has_unrelated_edits(self):
        write(self.root, "CLAUDE.md", self.UNRELATED_CLAUDE_MD_EDIT)
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        out = self.stop()
        self.assertIn("R1", out["reason"])
        self.assertIn("http-error.ts", out["reason"])

    def test_p5_passes_once_claude_md_names_http_error(self):
        write(self.root, "CLAUDE.md", self.UNRELATED_CLAUDE_MD_EDIT + "- `HttpError` (presentation) → 400/404.\n")
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        self.assertIsNone(self.stop())

    def test_new_adr_naming_the_file_counts_as_documented(self):
        write(self.root, "docs/adr/0004-presentation-http-errors.md", "# ADR-0004\n`http-error.ts` maps …\n")
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        self.assertIsNone(self.stop())

    def test_p9_budget_blocks_although_claude_md_has_unrelated_edits(self):
        write(self.root, "CLAUDE.md", self.UNRELATED_CLAUDE_MD_EDIT + "- monthlyBudget is optional\n")
        write(self.root, "apps/web/src/features/categorization/categories-page/hooks/budget.ts")
        out = self.stop()
        self.assertIn("R2", out["reason"])
        self.assertIn("budget.ts", out["reason"])

    def test_only_unmentioned_files_are_reported(self):
        write(self.root, "CLAUDE.md", "- `HttpError` …\n")
        write(self.root, "apps/api/src/presentation/http/http-error.ts")
        write(self.root, "apps/web/src/shared/api/api-error.ts")
        reason = self.stop()["reason"]
        self.assertIn("api-error.ts", reason)
        self.assertNotIn("http-error.ts", reason)


class ProbeGuardTest(HookTestCase):
    def bash(self, command, **extra):
        payload = dict({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": command}}, **extra)
        return run_hook("probe-guard.py", payload, self.root, self.data_dir)

    def assert_denied(self, out, rule_text):
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn(rule_text, out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_b1_tsx_probe_in_tmp(self):
        self.assert_denied(self.bash("npx tsx /tmp/smoke/probe.ts"), "throwaway script")

    def test_b1_node_probe_in_scratchpad(self):
        scratch = "/private/var/claude/scratchpad"
        self.assert_denied(self.bash("cd apps/api && node {}/smoke.mjs".format(scratch), scratchpad_dir=scratch),
                           "throwaway script")

    def test_b2_tsc_on_single_file(self):
        self.assert_denied(self.bash("cd apps/api && npx tsc --noEmit src/domain/x.ts"), "single files")

    def test_allowed_commands(self):
        for command in (
            "make test-unit",
            "npx tsc --noEmit -p tsconfig.json",
            "node -e \"console.log(1)\"",
            "cat /tmp/notes.ts",
            "npm run migrate --workspace=apps/api -- up",
            "node scripts/migrate.ts",
            "npx vitest run test/unit",
        ):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))

    def test_non_bash_tool_is_ignored(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "/tmp/a.ts"}}
        self.assertIsNone(run_hook("probe-guard.py", payload, self.root, self.data_dir))

    def test_outside_wisor_is_noop(self):
        shutil.rmtree(os.path.join(self.root, "apps/web"))
        self.assertIsNone(self.bash("npx tsx /tmp/probe.ts"))

    def test_path_in_a_variable(self):
        self.assert_denied(self.bash('S="/tmp/x/scratch" && npx tsx ${S}/probe.ts'), "throwaway script")
        self.assert_denied(self.bash("export T=/tmp/a; B=$T/b; node $B/run.mjs"), "throwaway script")

    def test_b2_tsc_on_mts_and_cts(self):
        self.assert_denied(self.bash("npx tsc --noEmit src/a.mts"), "single files")
        self.assert_denied(self.bash("npx tsc --noEmit src/a.cts"), "single files")


class ProbeGuardF1ReplayTest(HookTestCase):
    """Verbatim Bash commands from wisor's F1 session (user name and session id replaced)."""

    FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "f1_probe_commands.json")

    def test_every_f1_command(self):
        with open(self.FIXTURES, encoding="utf-8") as f:
            cases = json.load(f)
        for case in cases:
            with self.subTest(step=case["step"]):
                payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                           "tool_input": {"command": case["command"]}}
                out = run_hook("probe-guard.py", payload, self.root, self.data_dir)
                if case["expect"] is None:
                    self.assertIsNone(out)
                else:
                    self.assertIsNotNone(out, "not blocked")
                    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
                    expected = "throwaway script" if case["expect"] == "B1" else "single files"
                    self.assertIn(expected, reason)


if __name__ == "__main__":
    unittest.main()
