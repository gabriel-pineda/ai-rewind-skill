"""Shared test helpers. No test here reads a real log folder."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "skills", "ai-wrapped", "scripts", "rewind.py")
FIXTURES = os.path.join(HERE, "fixtures")
CLAUDE = os.path.join(FIXTURES, "claude")
CODEX = os.path.join(FIXTURES, "codex")
HISTORY_ONLY = os.path.join(FIXTURES, "claude-history-only")


def web_repo():
    """The private web repo, for the checks that its shared files match ours. None when it is not here.

    AI_REWIND_WEB_DIR wins. Else the first ai-rewind folder next to this repo or next to a folder above it,
    so a clone in a scratch folder or a worktree still finds it.
    """
    configured = os.environ.get("AI_REWIND_WEB_DIR")
    if configured:
        return configured if os.path.isdir(configured) else None
    folder = REPO
    while os.path.dirname(folder) != folder:
        candidate = os.path.join(os.path.dirname(folder), "ai-rewind")
        if os.path.exists(os.path.join(candidate, "src", "lib", "persona.json")):
            return candidate
        folder = os.path.dirname(folder)
    return None


def cli(*args, home="/Users/demo", tz="UTC"):
    """Runs the script the way SKILL.md does. Returns the CompletedProcess."""
    env = {**os.environ, "HOME": home, "TZ": tz}
    command = [sys.executable, "-I", SCRIPT, *args]
    return subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)


def report(*args, **kwargs):
    """Runs on the Claude fixture with --json, and returns the parsed report."""
    done = cli("--claude-dir", CLAUDE, "--tz", "UTC", "--json", *args, **kwargs)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
