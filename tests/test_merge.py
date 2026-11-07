"""history.jsonl and the session files together: exact human numbers, estimated AI numbers, honest coverage.

The merge fixture has session files for 8 and 9 Oct only, like a machine where Claude Code deleted the older
ones. history.jsonl has prompts from March to November. See tests/make_fixtures.py.
"""

import json
import os

import rewind
import urlspec
from helpers import CLAUDE, cli

MERGE = os.path.join(CLAUDE, "merge")


def merged(*args):
    done = cli("--claude-dir", MERGE, "--tz", "UTC", "--json", *args)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_coverage_block():
    assert merged()["coverage"] == {
        "promptsFrom": "2026-03-09",
        "promptsTo": "2026-11-01",
        "fullLogsFrom": "2026-10-08",
        "fullLogsTo": "2026-10-09",
        "transcriptFiles": 2,
        "historyFile": True,
        "historyLines": 13,  # 16 lines: one is from 2025, one is /clear, one is a ! shell line.
        "merged": 9,
        "duplicates": 4,  # Three W1 prompts (0 s, +3 s, -4 s) and one W2 prompt (+1 s).
        "mergedInWindow": 2,  # X1 (another project) and the W2 line 6 s off: both are new prompts.
        "windowMessages": 5,
        "estimated": {
            "wordsAi": {"value": 48, "lo": 41, "hi": 55, "window": 17},
            "absolutelyRight": {"value": 3, "lo": 3, "hi": 3, "window": 1},
            "greatQuestions": {"value": 0, "lo": 0, "hi": 0, "window": 0},
            "tokensOut": {"value": 280, "lo": 238, "hi": 322, "window": 100},
        },
    }


def test_human_numbers_are_exact_for_the_full_range():
    stats = merged()["stats"]
    # H1 to H6, W1, W2 and X1. X1 shares a second with a W1 prompt, but it is another session.
    assert stats["conversations"] == 9
    assert stats["messages"] == 14  # 5 from the session files and 9 that only history.jsonl holds.
    assert stats["activeDays"] == 8  # 03-09, 03-10, 06-01, 06-02, 06-03, 10-08, 10-09, 11-01.
    assert (stats["streak"], stats["streakStart"], stats["streakEnd"]) == (3, "2026-06-01", "2026-06-03")
    assert (stats["busiestDay"], stats["busiestDayMessages"]) == ("2026-10-08", 4)
    assert stats["latestClock"] == "02:30"
    assert stats["nightShare"] == 7  # 1 of 14.
    assert (stats["thankYous"], stats["sorrys"]) == (1, 1)  # Both are in history.jsonl only.
    assert stats["wordsYou"] == 74


def test_ai_numbers_are_scaled_from_the_window():
    stats = merged()["stats"]
    assert stats["assistantMessages"] == 5  # The window. Not scaled.
    assert stats["wordsAi"] == 48  # 17 words in 5 window prompts, times 14 prompts.
    assert stats["absolutelyRight"] == 3
    assert stats["tokensOut"] == 280
    assert stats["toolUsePerAssistantMessage"] == 0.2  # A ratio from the window, so no scaling.
    assert stats["models"] == ["opus-5.5"]


def test_url_marks_estimates_and_dates():
    data = merged()
    decoded = urlspec.decode(data["url"])
    assert decoded["wa"] == "41-55"
    assert decoded["ar"] == "~3"
    assert decoded["tk"] == "238-322"
    assert decoded["lf"] == "2026-03-09"
    assert decoded["ff"] == "2026-10-08"
    assert (decoded["c"], decoded["mg"], decoded["d"], decoded["s"]) == ("9", "14", "8", "3")
    assert data["url"].endswith("&md=opus-5.5&lf=2026-03-09&ff=2026-10-08&src=skill")


def test_seed_says_about_for_an_estimate():
    assert "opus-5.5 wrote about 48 words; you wrote 74" in merged()["seeds"]


def test_same_start_day_adds_no_dates():
    """From 8 Oct the session files hold every prompt but two. Those two still make the AI side an estimate."""
    data = merged("--since", "2026-10-08", "--until", "2026-10-09")
    assert data["stats"]["messages"] == 7
    assert data["coverage"]["merged"] == 2
    assert data["coverage"]["promptsFrom"] == data["coverage"]["fullLogsFrom"] == "2026-10-08"
    assert "lf" not in urlspec.decode(data["url"])  # Same start day, so the dates add nothing.


def test_no_history_means_no_estimate():
    data = json.loads(cli("--claude-dir", CLAUDE, "--tz", "UTC", "--json").stdout)
    assert data["coverage"]["estimated"] == {}
    assert data["coverage"]["historyFile"] is False
    decoded = urlspec.decode(data["url"])
    assert decoded["wa"] == "23" and "lf" not in decoded and "ff" not in decoded


def test_history_without_display_is_skipped_with_a_note(tmp_path):
    projects = tmp_path / "projects" / "-Users-demo-app"
    projects.mkdir(parents=True)
    source = os.path.join(MERGE, "projects", "-Users-demo-app")
    for name in os.listdir(source):
        with open(os.path.join(source, name), encoding="utf-8") as handle:
            (projects / name).write_text(handle.read(), encoding="utf-8")
    (tmp_path / "history.jsonl").write_text(
        '{"timestamp": 1772442000000, "project": "/Users/demo/app"}\n', encoding="utf-8"
    )
    done = cli("--claude-dir", str(tmp_path), "--tz", "UTC", "--json")
    assert done.returncode == 0
    assert "older Claude Code" in done.stderr
    data = json.loads(done.stdout)
    assert data["coverage"]["merged"] == 0 and data["stats"]["messages"] == 5
    assert data["coverage"]["estimated"] == {}


def test_dedupe_window_is_five_seconds():
    tally = rewind.Tally(rewind.parse_day("2026-01-01"), rewind.parse_day("2026-12-31"), None, None)
    moment = rewind.parse_stamp("2026-10-08T10:00:00Z")
    tally.note_prompt("s", moment)
    for offset, known in ((-5, True), (5, True), (-6, False), (6, False)):
        later = rewind.parse_stamp(1000 * (moment.timestamp() + offset))
        assert tally.known_prompt("s", later) is known, offset
    assert tally.known_prompt("other", moment) is False


def test_dry_run_lists_history_with_the_session_files():
    done = cli("--claude-dir", MERGE, "--dry-run")
    lines = done.stdout.splitlines()
    assert len(lines) == 3 and lines[-1].endswith("history.jsonl")


def test_output_never_holds_history_text():
    with open(os.path.join(MERGE, "history.jsonl"), encoding="utf-8") as handle:
        prompts = [json.loads(line)["display"] for line in handle]
    for extra in ((), ("--json",), ("--json", "--anon")):
        done = cli("--claude-dir", MERGE, "--tz", "UTC", *extra)
        output = done.stdout + done.stderr
        for text in prompts:
            for start in range(max(0, len(text) - 12)):
                assert text[start : start + 13] not in output


def test_web_midpoint_of_each_range_is_the_estimate():
    """The web codec shows round((lo + hi) / 2). It must equal the value that --json prints."""
    for key, estimate in merged()["coverage"]["estimated"].items():
        assert int((estimate["lo"] + estimate["hi"]) / 2 + 0.5) == estimate["value"], key
    for value in range(0, 500):
        tally_value = rewind.round_half_up(value)
        spread = rewind.round_half_up(tally_value * rewind.ESTIMATE_SPREAD)
        assert int(((tally_value - spread) + (tally_value + spread)) / 2 + 0.5) == tally_value


def test_resumed_session_prompt_counts_once():
    """A resumed session copies a prompt into a new file under a new sessionId. The old file is gone, so the
    history line (old sessionId) matches by project folder and time only."""
    from datetime import date, datetime, timezone

    tally = rewind.Tally(date(2026, 1, 1), date(2026, 12, 31), timezone.utc, rewind.ProjectNames("/nonexistent"))
    moment = datetime(2026, 10, 8, 10, 0, 0, tzinfo=timezone.utc)
    tally.note_prompt("new-session", moment, "/work/app")
    assert tally.known_prompt("old-session", moment, "/work/app")
    assert not tally.known_prompt("old-session", moment, "/work/notes")
    later = datetime(2026, 10, 8, 10, 0, 6, tzinfo=timezone.utc)
    assert not tally.known_prompt("old-session", later, "/work/app")
