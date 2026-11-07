from datetime import date, datetime, timedelta, timezone

import pytest

import rewind
from helpers import CLAUDE, CODEX, HISTORY_ONLY, cli, report


def test_fixture_numbers_are_exact():
    stats = report()["stats"]
    assert stats == {
        "conversations": 4,  # S1, S2, S3, S5. S4 is out of range and S6 has no human.
        "messages": 11,  # Ten in S1 to S3, plus one new in S5. The resumed copies count once.
        "assistantMessages": 4,  # msg_001 spans three lines. Sidechain and synthetic stay out.
        "activeDays": 6,
        "streak": 4,
        "streakStart": "2026-03-02",
        "streakEnd": "2026-03-05",
        "busiestDay": "2026-06-20",
        "busiestDayMessages": 4,
        "latestClock": "03:47",
        "typicalHour": 14,
        "nightShare": 18,
        "wordsYou": 103,
        "wordsAi": 23,
        "thankYous": 3,
        "sorrys": 1,
        "absolutelyRight": 2,
        "greatQuestions": 1,
        "tokensOut": 110,  # 40 + 30 + 15 + 25: the highest value of each message.
        "models": ["opus-5.5", "haiku-3.5"],
        "toolUsePerAssistantMessage": 0.75,
        "medianWords": 6,
        "thanksPer100": 27.27,
        "persona": "BDSP",
        "personaName": "The Polite Shipper",
        "personaLine": "Ships by daylight, in few words, and still says thanks.",
        "rankPercent": 90,
        "power": "Rookie",
    }


def test_report_shape():
    data = report()
    assert list(data) == ["skill", "range", "stats", "seeds", "projects", "months", "url"]
    assert data["skill"] == rewind.VERSION
    assert data["range"]["firstDay"] == "2026-03-02"
    assert data["range"]["lastDay"] == "2026-06-21"
    assert data["projects"] == [{"name": "app", "share": 64}, {"name": "other", "share": 36}]
    assert data["months"][0] == {"month": "Mar", "messages": 6, "activeDays": 4, "topProject": "app"}


def test_three_numeric_seeds():
    seeds = report()["seeds"]
    assert seeds == [
        "Said thanks 3 times, 2 of them after 2 AM",
        "Top project took 64% of all messages",
        "4 messages on Jun 20",
    ]


def test_time_zone_moves_a_record_into_the_year():
    data = report("--tz", "Australia/Melbourne")
    assert data["stats"]["messages"] == 12
    assert data["stats"]["conversations"] == 5
    assert data["range"]["firstDay"] == "2026-01-01"


def test_date_range_limits_the_counts():
    stats = report("--since", "2026-06-01")["stats"]
    assert stats["messages"] == 5
    assert stats["conversations"] == 2
    stats = report("--until", "2026-03-04")["stats"]
    assert stats["messages"] == 4


def test_no_sessions_exits_with_2(tmp_path):
    done = cli("--claude-dir", str(tmp_path))
    assert done.returncode == 2
    assert done.stdout == ""
    assert "No sessions" in done.stderr
    assert cli("--claude-dir", CLAUDE, "--since", "2024-01-01", "--until", "2024-12-31").returncode == 2


def test_unknown_zone_exits_with_2():
    done = cli("--claude-dir", CLAUDE, "--tz", "Mars/Olympus")
    assert done.returncode == 2
    assert "time zone" in done.stderr


def test_history_fallback():
    done = cli("--claude-dir", HISTORY_ONLY, "--tz", "UTC")
    assert done.returncode == 0
    assert "c=2&mg=2" in done.stdout
    assert "&wa=" not in done.stdout and "&ar=" not in done.stdout and "&tk=" not in done.stdout


def test_codex_counts_each_prompt_once():
    done = cli("--platform", "codex", "--codex-dir", CODEX, "--tz", "UTC")
    assert done.returncode == 0
    for part in ("p=codex", "c=1&mg=1", "wa=8", "ty=1", "tk=77", "md=gpt-5.1-codex"):
        assert part in done.stdout


def day(n):
    return date(2026, 3, 1) + timedelta(days=n)


def test_longest_streak_takes_the_first_of_equal_runs():
    assert rewind.longest_streak([day(0), day(1), day(5), day(6)]) == (2, day(0), day(1))
    assert rewind.longest_streak([day(0)]) == (1, day(0), day(0))
    assert rewind.longest_streak([day(9), day(1), day(2), day(3)]) == (3, day(1), day(3))
    assert rewind.longest_streak([]) == (0, None, None)


def test_typical_hour_tie_goes_to_the_later_hour():
    assert rewind.typical_hour({9: 3, 14: 3, 2: 1}) == 14


def test_latest_clock_treats_early_hours_as_late():
    tally = rewind.Tally(date(2026, 1, 1), date(2026, 12, 31), timezone.utc, rewind.ProjectNames("/h"))
    for hour, minute in ((23, 59), (1, 5), (5, 59), (6, 0), (22, 0)):
        tally.add_human(datetime(2026, 2, 1, hour, minute, tzinfo=timezone.utc), "hello", "s", "/x")
    assert tally.latest == (29, 59)


def test_active_minutes_ignores_long_gaps():
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    times = [start, start + timedelta(minutes=30), start + timedelta(minutes=31), start + timedelta(hours=5)]
    assert rewind.active_minutes(times) == 31


@pytest.mark.parametrize(
    "text,hits",
    [
        ("thanks a lot", True),
        ("Thank you!", True),
        ("thx", True),
        ("ty", True),
        ("Cheers mate", True),
        ("much appreciated", True),
        ("you legend", True),
        ("thankless job", False),
        ("party time", False),
    ],
)
def test_thanks_pattern(text, hits):
    assert rewind.found(rewind.THANKS_RE, rewind.THANKS_HINTS, text, text.lower()) is hits
    assert bool(rewind.THANKS_RE.search(text)) is hits


@pytest.mark.parametrize(
    "pattern,hints,text",
    [
        (rewind.THANKS_RE, rewind.THANKS_HINTS, "THANK YOU"),
        (rewind.THANKS_RE, rewind.THANKS_HINTS, "(TY)"),
        (rewind.SORRY_RE, rewind.SORRY_HINTS, "SORRY"),
        (rewind.SORRY_RE, rewind.SORRY_HINTS, "My Bad"),
        (rewind.SORRY_RE, rewind.SORRY_HINTS, "Apologies"),
        (rewind.FIX_RE, rewind.FIX_HINTS, "FIXED it"),
        (rewind.GREAT_RE, rewind.GREAT_HINTS, "Great Question"),
    ],
)
def test_hints_never_hide_a_match(pattern, hints, text):
    assert rewind.found(pattern, hints, text, text.lower())


@pytest.mark.parametrize(
    "text,hits",
    [
        ("You're absolutely right", True),
        ("you’re completely right!", True),
        ("Youre totally right", True),
        ("You're exactly right", True),
        ("You're right", False),
    ],
)
def test_absolutely_right_pattern(text, hits):
    assert rewind.found(rewind.RIGHT_RE, rewind.RIGHT_HINTS, text, text.lower()) is hits


@pytest.mark.parametrize(
    "model,short",
    [
        ("claude-opus-5-5-20261001", "opus-5.5"),
        ("claude-opus-5-5", "opus-5.5"),
        ("claude-opus-5-5[1m]", "opus-5.5"),
        ("claude-3-5-sonnet-20241022", "sonnet-3.5"),
        ("claude-sonnet-4", "sonnet-4"),
        ("gpt-5.1-codex", "gpt-5.1-codex"),
    ],
)
def test_short_model(model, short):
    assert rewind.short_model(model) == short


def test_rank_curve_and_power_tiers():
    assert rewind.rank_percent(500) == 1
    assert rewind.rank_percent(41) == 10
    assert rewind.rank_percent(0.5) == 90
    assert rewind.power_title(0) == "Rookie"
    assert rewind.power_title(5000) == "Sage Mode"
    assert rewind.power_title(99999) == "God Mode"


def test_project_names():
    names = rewind.ProjectNames("/Users/demo")
    assert names.name("/Users/demo/app/src/deep") == "app"
    assert names.name("/Users/demo/Documents/other/sub") == "other"
    assert names.name("/Users/demo/Documents/other/.claude/worktrees/wt-1") == "other"
    assert names.name("/Users/demo") == "home"
    assert names.name("/tmp/abc123") == "scratch"
    assert names.name("/private/tmp/abc123") == "scratch"
    assert names.name("/srv/www/site") == "site"
    assert names.name(None) == "misc"


def test_git_root_wins(tmp_path):
    repo = tmp_path / "code" / "my-repo"
    (repo / "pkg" / "sub").mkdir(parents=True)
    (repo / ".git").mkdir()
    names = rewind.ProjectNames(str(tmp_path))
    assert names.name(str(repo / "pkg" / "sub")) == "my-repo"


def test_home_folder_name_never_shows_when_home_is_a_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    assert rewind.ProjectNames(str(tmp_path)).name(str(tmp_path)) == "home"
