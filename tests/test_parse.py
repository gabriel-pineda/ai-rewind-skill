import os
import shutil
from datetime import date, timezone

import pytest

import make_fixtures
import rewind
from helpers import CLAUDE, CODEX, FIXTURES, HISTORY_ONLY, cli


def test_committed_fixtures_match_the_generator():
    for path, body in make_fixtures.rendered().items():
        with open(os.path.join(FIXTURES, path), encoding="utf-8") as handle:
            assert handle.read() == body, path


@pytest.mark.parametrize(
    "stamp,expected",
    [
        ("2026-03-14T10:11:12.345Z", (2026, 3, 14, 10, 11, 12)),
        ("2026-03-14T10:11:12Z", (2026, 3, 14, 10, 11, 12)),
        ("2026-03-14T10:11:12.123456789Z", (2026, 3, 14, 10, 11, 12)),
        ("2026-03-14T23:11:12+10:00", (2026, 3, 14, 13, 11, 12)),
        (1772442000000, (2026, 3, 2, 9, 0, 0)),
    ],
)
def test_parse_stamp(stamp, expected):
    moment = rewind.parse_stamp(stamp).astimezone(timezone.utc)
    assert moment.timetuple()[:6] == expected


@pytest.mark.parametrize("stamp", [None, "", "yesterday", "2026-13-40T00:00:00Z", True, {}])
def test_parse_stamp_rejects_bad_values(stamp):
    assert rewind.parse_stamp(stamp) is None


def test_sessions_are_top_level_only():
    files = rewind.claude_sessions(CLAUDE)
    assert len(files) == 6
    assert not any("subagents" in path for path in files)


def human(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


@pytest.mark.parametrize(
    "record",
    [
        human("Hello there"),
        human([{"type": "text", "text": "Hello there"}]),
        human("Hello there", origin={"kind": "human"}),
        human([{"type": "text", "text": "See this"}, {"type": "image"}]),
    ],
)
def test_human_records(record):
    assert rewind.human_text(record)


@pytest.mark.parametrize(
    "record",
    [
        human("x", isMeta=True),
        human("x", isSidechain=True),
        human("x", isCompactSummary=True),
        human("x", isVisibleInTranscriptOnly=True),
        human("x", origin={"kind": "task-notification"}),
        human("x", origin={"kind": "peer"}),
        human("x", origin={"kind": "auto-continuation"}),
        human([{"type": "tool_result", "content": "x"}]),
        human([{"type": "text", "text": "x"}, {"type": "tool_result", "content": "x"}]),
        human([{"type": "image"}]),
        human("<command-name>/foo</command-name>"),
        human("<local-command-stdout>x</local-command-stdout>"),
        human("<bash-input>ls</bash-input>"),
        human("  <system-reminder>x</system-reminder>"),
        human("[Request interrupted by user]"),
        human("This session is being continued from a previous conversation"),
        human(""),
        human(None),
        {"type": "user"},
    ],
)
def test_records_that_are_not_prompts(record):
    assert rewind.human_text(record) is None


def test_assistant_blocks_ignore_thinking_and_tool_input():
    blocks = [
        {"type": "thinking", "thinking": "secret"},
        {"type": "text", "text": "visible"},
        {"type": "tool_use", "input": {"x": "secret"}},
    ]
    assert rewind.assistant_blocks(blocks) == (["visible"], 1)


def test_broken_line_is_skipped(tmp_path):
    path = tmp_path / "a.jsonl"
    path.write_bytes(b'{"type":"user"\n[1,2]\n{"type":"assistant","a":1}\n')
    assert list(rewind.json_lines(str(path), claude_filter=True)) == [{"type": "assistant", "a": 1}]


def test_filter_keeps_lines_with_a_space_after_the_colon(tmp_path):
    path = tmp_path / "a.jsonl"
    path.write_bytes(b'{"type": "user", "a": 1}\n{"type": "attachment"}\n')
    assert list(rewind.json_lines(str(path), claude_filter=True)) == [{"type": "user", "a": 1}]


def test_filter_keeps_a_prompt_that_quotes_a_tool_result():
    done = rewind.USER_MARK in b'{"type":"user","message":{"content":"see \\"type\\":\\"tool_result\\""}}'
    assert done
    assert rewind.TOOL_RESULT_MARK not in b'{"type":"user","message":{"content":"see \\"type\\":\\"tool_result\\""}}'


def test_old_file_is_skipped_by_mtime(tmp_path):
    copy = tmp_path / "claude"
    shutil.copytree(CLAUDE, copy)
    old = copy / "projects" / "-Users-demo-other" / "bbbbbbbb-0000-4000-8000-000000000004.jsonl"
    stamp = 1700000000  # November 2023
    os.utime(old, (stamp, stamp))
    files, _ = rewind.find_files("claude-code", str(copy), date(2026, 1, 1))
    assert str(old) not in files
    assert len(files) == 5


def test_symbolic_link_is_not_followed(tmp_path):
    root = tmp_path / "claude" / "projects" / "-x"
    root.mkdir(parents=True)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n")
    (root / "link.jsonl").symlink_to(outside)
    assert rewind.claude_sessions(str(tmp_path / "claude")) == []


def test_dry_run_prints_only_paths_under_the_log_folder():
    done = cli("--claude-dir", CLAUDE, "--dry-run")
    assert done.returncode == 0
    lines = done.stdout.splitlines()
    assert len(lines) == 6
    for path in lines:
        assert path.startswith(CLAUDE + os.sep)
        assert os.path.isfile(path)
        assert "subagents" not in path


def test_codex_dry_run_lists_rollouts():
    done = cli("--platform", "codex", "--codex-dir", CODEX, "--dry-run")
    assert done.returncode == 0
    assert len(done.stdout.splitlines()) == 1


def test_dry_run_lists_history_when_there_are_no_project_logs():
    done = cli("--claude-dir", HISTORY_ONLY, "--dry-run")
    assert done.stdout.strip().endswith("history.jsonl")
