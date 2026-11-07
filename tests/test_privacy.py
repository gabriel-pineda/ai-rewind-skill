import ast
import json
import os

import pytest

from helpers import CLAUDE, CODEX, FIXTURES, REPO, SCRIPT, cli, report

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}
NETWORK = {
    "socket",
    "ssl",
    "http",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "telnetlib",
    "xmlrpc",
    "socketserver",
    "asyncio",
    "webbrowser",
    "subprocess",
}
BAD_CALLS = {"__import__", "exec", "eval", "compile"}


def tree():
    with open(SCRIPT, encoding="utf-8") as handle:
        return ast.parse(handle.read())


def test_no_network_imports():
    found = set()
    for node in ast.walk(tree()):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    assert not found & NETWORK


def test_script_source_is_ascii():
    """Invisible characters in a regex are easy to miss in a review."""
    with open(SCRIPT, "rb") as handle:
        assert handle.read().isascii()


def test_no_dynamic_code():
    for node in ast.walk(tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in BAD_CALLS
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert "importlib" not in ast.dump(node)


def texts(value):
    """Every string in a record, at any depth."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from texts(item)


def fixture_message_text(root):
    """Text from message content and the Codex payloads. Paths and ids stay out of the check."""
    for folder, _, names in os.walk(root):
        for name in names:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    yield from texts((record.get("message") or {}).get("content"))
                    payload = record.get("payload") or {}
                    yield from texts(payload.get("content"))
                    yield from texts(payload.get("message"))


def assert_no_leak(output, source):
    pieces = set()
    for text in source:
        for start in range(max(0, len(text) - 12)):
            pieces.add(text[start : start + 13])
    assert pieces
    leaks = [piece for piece in pieces if piece in output]
    assert leaks == []


@pytest.mark.parametrize("extra", [(), ("--json",), ("--json", "--anon")])
def test_output_never_holds_message_text(extra):
    done = cli("--claude-dir", CLAUDE, "--tz", "UTC", *extra)
    assert done.returncode == 0
    assert_no_leak(done.stdout + done.stderr, fixture_message_text(CLAUDE))


def test_codex_output_never_holds_message_text():
    done = cli("--platform", "codex", "--codex-dir", CODEX, "--tz", "UTC", "--json")
    assert done.returncode == 0
    assert_no_leak(done.stdout + done.stderr, fixture_message_text(CODEX))


def test_dry_run_output_has_no_message_text():
    done = cli("--claude-dir", CLAUDE, "--dry-run")
    assert_no_leak(done.stdout, fixture_message_text(CLAUDE))


def test_anon_removes_project_names_everywhere():
    data = report("--anon")
    text = json.dumps(data)
    assert '"app"' not in text and '"other"' not in text
    assert "t=Project+A%3A64%2CProject+B%3A36" in data["url"]
    assert [item["name"] for item in data["projects"]] == ["Project A", "Project B"]
    assert {item["topProject"] for item in data["months"]} == {"Project A", "Project B"}


def test_output_does_not_hold_the_log_paths():
    data = report()
    assert "/Users/" not in json.dumps(data)


def repo_files():
    for folder, subfolders, names in os.walk(REPO):
        subfolders[:] = [name for name in subfolders if name not in SKIP_DIRS]
        for name in names:
            yield os.path.join(folder, name)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def test_fixtures_use_only_the_demo_home():
    for folder, _, names in os.walk(FIXTURES):
        for name in names:
            body = read(os.path.join(folder, name))
            for piece in body.split("/Users/")[1:]:
                assert piece.startswith("demo"), name


def test_only_one_file_names_the_site():
    final_host = "ai-rewind" + ".com"
    live_host = "ai-rewind" + ".vercel.app"
    holders = [path for path in repo_files() if live_host in read(path)]
    assert holders == [SCRIPT]
    assert [path for path in repo_files() if final_host in read(path)] == []
