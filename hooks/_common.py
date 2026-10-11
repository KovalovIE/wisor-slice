"""Shared helpers for wisor-slice hooks. Python 3.9 compatible (macOS system python)."""
import datetime
import json
import os
import subprocess
import sys


def read_input():
    """Hook input JSON from stdin, or None when it is missing or malformed (then the hook stays out of the way)."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def project_root(data):
    return os.environ.get("CLAUDE_PROJECT_DIR") or (data or {}).get("cwd") or os.getcwd()


def is_wisor(root):
    """The plugin's rules only make sense inside the wisor monorepo; elsewhere every hook is a no-op."""
    return all(os.path.exists(os.path.join(root, p)) for p in ("CLAUDE.md", "apps/api", "apps/web"))


def changed_files(root):
    """Uncommitted changes as (status, path): status is 'added', 'modified' or 'deleted'."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "status", "--porcelain=v1", "-uall"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except Exception:
        return []
    changes = []
    for line in out.splitlines():
        code, path = line[:2], line[3:]
        if " -> " in path:  # rename: keep the new path
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if code == "??" or "A" in code:
            changes.append(("added", path))
        elif "D" in code:
            changes.append(("deleted", path))
        else:
            changes.append(("modified", path))
    return changes


def log_event(hook, decision, details):
    """Append to ${CLAUDE_PLUGIN_DATA}/hook-events.log — the evidence trail for CAPSTONE_LOG.md."""
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        return
    try:
        os.makedirs(data_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(data_dir, "hook-events.log"), "a", encoding="utf-8") as f:
            f.write("{}\t{}\t{}\t{}\n".format(stamp, hook, decision, details.replace("\n", " | ")))
    except Exception:
        pass
