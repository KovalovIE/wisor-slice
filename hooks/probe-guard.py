#!/usr/bin/env python3
"""PreToolUse(Bash) hook: stop ad-hoc verification that runs outside the project's own toolchain.

From wisor's LOG.md (F1): 4 of 10 stuck moments were Claude checking its code with throwaway probes —
a tsx/node script in the scratchpad that could not resolve the repo's node_modules (ERR_MODULE_NOT_FOUND,
"Transform failed"), and `tsc` on a single file that ignored tsconfig (TS5112). Each cost a retry and
proved nothing the test suite wouldn't.

  B1  node / tsx / ts-node / bun / deno running a .js/.ts file from /tmp, $TMPDIR or the scratchpad
  B2  tsc given explicit .ts/.tsx files instead of a project
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import is_wisor, log_event, project_root, read_input  # noqa: E402

RUNNER = re.compile(r"(?:^|[\s;&|(])(?:npx\s+)?(?:node|tsx|ts-node|bun|deno)(?:\s|$)")
TSC_ON_FILES = re.compile(r"(?:^|[\s;&|(])(?:npx\s+)?tsc\b[^|;&]*?\s(?!-)[^\s|;&]+\.tsx?(?=\s|$)")
SCRIPT_EXT = r"\.(?:[cm]?[jt]s|tsx)\b"

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


def verdict(command, dirs):
    if RUNNER.search(command):
        temp_script = re.compile("(?:" + "|".join(re.escape(d) for d in dirs) + r")\S*" + SCRIPT_EXT)
        if temp_script.search(command):
            return "B1", PROBE_REASON
    if TSC_ON_FILES.search(command):
        return "B2", TSC_REASON
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
