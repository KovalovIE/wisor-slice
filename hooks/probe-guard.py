#!/usr/bin/env python3
"""PreToolUse(Bash) hook: stop ad-hoc verification that runs outside the project's own toolchain.

From wisor's F1 session: Claude checked its code with 8 throwaway probes — tsx scripts in the scratchpad
and `tsc` on single .mts files. 3 of them failed outright (ERR_MODULE_NOT_FOUND, "Transform failed",
TS5112 — stuck moments #3, #4, #6 in LOG.md); none left a check behind that the test suite keeps running.
tests/fixtures/f1_probe_commands.json holds those commands verbatim.

  B1  node / tsx / ts-node / bun / deno running a .js/.ts file from /tmp, $TMPDIR or the scratchpad
  B2  tsc given explicit .ts/.tsx/.mts/.cts files instead of a project

Claude usually puts the scratch path in a variable first (`S=<scratchpad> && npx tsx $S/x.ts`), so
assignments made in the same command are expanded before matching.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import is_wisor, log_event, project_root, read_input  # noqa: E402

RUNNER = re.compile(r"(?:^|[\s;&|(])(?:npx\s+)?(?:node|tsx|ts-node|bun|deno)(?:\s|$)")
TSC_ON_FILES = re.compile(r"(?:^|[\s;&|(])(?:npx\s+)?tsc\b[^|;&\n]*?\s(?!-)[^\s|;&]+\.[cm]?tsx?(?=[\s;&|]|$)")
SCRIPT_EXT = r"\.(?:[cm]?[jt]s|tsx)\b"
ASSIGNMENT = re.compile(
    r"(?:^|[\s;&|(])(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=((?:\"[^\"]*\"|'[^']*'|[^\s;&|()<>\"'])+)"
)

PROBE_REASON = (
    "wisor-slice probe-guard: don't verify code with a throwaway script outside the repo — it can't resolve the "
    "repo's node_modules or tsconfig (F1: ERR_MODULE_NOT_FOUND, 'Transform failed'). Put the check in a real "
    "test next to the code (apps/api/test/unit/... or *.test.ts(x) in apps/web) and run `make test-unit` / "
    "`make test-web`. The test then stays as a regression check."
)
TSC_REASON = (
    "wisor-slice probe-guard: `tsc` on single files ignores tsconfig (F1: TS5112). Type-check the project: "
    "`make lint-api` / `npm run typecheck --workspace=apps/web`."
)


def temp_dirs(data):
    dirs = ["/tmp/", "/private/tmp/", "/var/folders/"]
    for extra in (os.environ.get("TMPDIR"), (data or {}).get("scratchpad_dir")):
        if extra:
            dirs.append(extra.rstrip("/") + "/")
    return dirs


def substitute(text, variables):
    for name, value in variables.items():
        text = re.sub(r"\$\{" + name + r"\}|\$" + name + r"(?![A-Za-z0-9_])", lambda _m, v=value: v, text)
    return text


def expand_variables(command):
    """Replace $VAR / ${VAR} with values assigned earlier in the same command (in order, so B=$A/x works)."""
    variables = {}
    for m in ASSIGNMENT.finditer(command):
        variables[m.group(1)] = substitute(m.group(2).replace('"', "").replace("'", ""), variables)
    return substitute(command, variables)


def verdict(command, dirs):
    command = expand_variables(command)
    # B2 first: it is the more specific rule, and tsc flags like `--types node` would otherwise match RUNNER.
    if TSC_ON_FILES.search(command):
        return "B2", TSC_REASON
    if RUNNER.search(command):
        temp_script = re.compile("(?:" + "|".join(re.escape(d) for d in dirs) + r")\S*" + SCRIPT_EXT)
        if temp_script.search(command):
            return "B1", PROBE_REASON
    return None, None


def main():
    data = read_input()
    if data is None or data.get("tool_name") != "Bash":
        return 0
    if not is_wisor(project_root(data)):
        return 0

    command = (data.get("tool_input") or {}).get("command", "")
    rule, reason = verdict(command, temp_dirs(data))
    if not rule:
        return 0

    log_event("probe-guard", "deny", "{} {}".format(rule, command[:200]))
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
