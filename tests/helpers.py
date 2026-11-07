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
