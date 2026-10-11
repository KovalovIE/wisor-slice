#!/usr/bin/env python3
"""Stop hook: don't let Claude finish a turn when code changed but the doc that describes it did not.

Every rule comes from a `REPEAT docs` line in wisor's LOG.md (F1), where the user had to ask
"sync the docs" by hand:

  R1  new shared building block (e.g. presentation/http/http-error.ts) → CLAUDE.md or an ADR
  R2  file outside the documented slice structure (e.g. hooks/budget.ts that isn't a hook) → CLAUDE.md
  R3  a backend DTO changed but its web mirror features/*/types.ts did not (CLAUDE.md «apps/web»)

R1/R2 count a file as documented only when text *added* to CLAUDE.md, ARCHITECTURE.md or docs/adr/
in the uncommitted changes names that file (`http-error.ts`, `http-error` or `HttpError`). "Some doc
changed" is not enough: skills don't commit between steps, so an unrelated CLAUDE.md edit from an
earlier step would otherwise silence the hook for the rest of the feature (that is how F1's P5 slipped).

Blocks once per stop: when Claude Code is already continuing because of this hook
(`stop_hook_active`), it lets the turn end, so a "no doc change needed" answer is possible.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import changed_files, is_wisor, log_event, project_root, read_input  # noqa: E402

SHARED_BUILDING_BLOCK = [
    r"^apps/api/src/domain/shared/",
    r"^apps/api/src/application/shared/",
    r"^apps/api/src/presentation/http/[^/]+\.ts$",
    r"^apps/api/src/presentation/http/middleware/",
    r"^apps/api/src/infrastructure/persistence/(?!.*\.repository\.ts$)",
    r"^apps/web/src/shared/",
]

# Documented places for slice files (CLAUDE.md «Конвенції», «apps/web»). Anything else new needs a doc line.
SLICE_DIRS_AND_ALLOWED = [
    (r"^apps/api/src/domain/(?!shared/)[^/]+/", r"[^/]+\.(entity|value-object|error)\.ts$"),
    (r"^apps/api/src/application/(?!shared/)[^/]+/", r"([^/]+\.use-case\.ts|ports/[^/]+\.port\.ts)$"),
    (r"^apps/api/src/presentation/http/controllers/", r"[^/]+\.controller\.ts$"),
    (r"^apps/api/src/presentation/http/dto/", r"[^/]+\.dto\.ts$"),
    (r"^apps/api/src/presentation/http/routes/", r"[^/]+\.routes\.ts$"),
    (
        r"^apps/web/src/features/[^/]+/",
        r"(api\.ts|types\.ts|[^/]+/(index\.tsx|index\.test\.tsx|styles\.module\.css|helpers(\.test)?\.ts"
        r"|hooks/use-[^/]+?(\.test)?\.ts))$",
    ),
]

DTO = re.compile(r"^apps/api/src/presentation/http/dto/([^/]+\.dto\.ts)$")
TEST_FILE = re.compile(r"\.test\.tsx?$")


def is_doc(path):
    return path in ("CLAUDE.md", "ARCHITECTURE.md") or path.startswith("docs/adr/")


def added_doc_text(root, changes):
    """Lines added to docs in the uncommitted changes: '+' lines of modified docs, whole new docs."""
    modified = [p for s, p in changes if s == "modified" and is_doc(p)]
    new = [p for s, p in changes if s == "added" and is_doc(p)]
    chunks = []
    if modified:
        try:
            diff = subprocess.run(
                ["git", "-C", root, "diff", "-U0", "HEAD", "--"] + modified,
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
            chunks += [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
        except Exception:
            pass
    for p in new:
        try:
            with open(os.path.join(root, p), encoding="utf-8") as f:
                chunks.append(f.read())
        except OSError:
            continue
    return "\n".join(chunks)


def mention_tokens(path):
    """Names a doc may use for a file: `http-error.ts`, `http-error`, `HttpError`. A one-word stem
    (`budget.ts`) needs the file name itself — the bare word is too common to count."""
    base = os.path.basename(path)
    parts = base.split(".")[0].split("-")
    tokens = [base]
    if len(parts) > 1:
        tokens += ["-".join(parts), "".join(p.capitalize() for p in parts)]
    return tokens


def is_documented(path, doc_text):
    return any(
        re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", doc_text) for token in mention_tokens(path)
    )


def check_shared_blocks(added):
    return [
        "R1 new shared building block `{}` — describe it in CLAUDE.md (or an ADR) so the next slice reuses "
        "it instead of re-inventing it.".format(p)
        for p in added
        if not TEST_FILE.search(p) and any(re.search(rx, p) for rx in SHARED_BUILDING_BLOCK)
    ]


def check_slice_structure(added):
    problems = []
    for p in added:
        for dir_rx, allowed_rx in SLICE_DIRS_AND_ALLOWED:
            m = re.match(dir_rx, p)
            if m and not re.fullmatch(allowed_rx, p[m.end():]):
                problems.append(
                    "R2 `{}` is outside the documented slice structure — move it to a documented place, or add "
                    "the new pattern to CLAUDE.md.".format(p)
                )
                break
    return problems


def web_mirrors(root, dto_name):
    features = os.path.join(root, "apps/web/src/features")
    mirrors = []
    if not os.path.isdir(features):
        return mirrors
    for feature in sorted(os.listdir(features)):
        rel = "apps/web/src/features/{}/types.ts".format(feature)
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                if dto_name in f.read():
                    mirrors.append(rel)
        except OSError:
            continue
    return mirrors


def check_dto_mirrors(root, modified, changed):
    problems = []
    for p in modified:
        m = DTO.match(p)
        if not m:
            continue
        mirrors = web_mirrors(root, m.group(1))
        if mirrors and not any(x in changed for x in mirrors):
            problems.append(
                "R3 `{}` changed but its web mirror {} did not (CLAUDE.md «apps/web»: update in the same "
                "change). If the request/response shape is unchanged, say so and finish.".format(
                    p, ", ".join("`{}`".format(x) for x in mirrors)
                )
            )
    return problems


def main():
    data = read_input()
    if data is None or data.get("stop_hook_active"):
        return 0
    root = project_root(data)
    if not is_wisor(root):
        return 0

    changes = changed_files(root)
    changed = {p for _, p in changes}
    modified = [p for s, p in changes if s == "modified"]
    doc_text = added_doc_text(root, changes)
    undocumented = [p for s, p in changes if s == "added" and not is_doc(p) and not is_documented(p, doc_text)]

    problems = check_shared_blocks(undocumented) + check_slice_structure(undocumented)
    problems += check_dto_mirrors(root, modified, changed)
    if not problems:
        return 0

    reason = "wisor-slice docs-sync: code changed but its docs did not.\n- " + "\n- ".join(problems)
    log_event("docs-sync", "block", reason)
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
