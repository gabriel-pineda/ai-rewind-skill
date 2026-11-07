import json
import os
from datetime import date, datetime, timedelta, timezone

import pytest

import rewind
from helpers import CLAUDE, CODEX, FIXTURES, HISTORY_ONLY, cli, report, web_repo


def json_of(*args):
    done = cli(*args, "--json")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def persona(code):
    entry = rewind.load_persona_table()["types"][code]
    return {"persona": code, "personaName": entry["name"], "personaLine": entry["line"]}


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


# --- Exact numbers on the fixtures (Wave 3, T1) -------------------------------------------------------
# Every number below was worked out by hand from tests/make_fixtures.py, not copied from a run.
# The human prompts in UTC: S1 03-02 09:00 (9 words), 09:10 (4, thanks), 03-03 10:00 (9, fix),
# 03-04 23:30 (7, sorry); S2 03-05 02:15 (11, thank you), 03:47 (6, cheers, fixed); S3 06-20 14:00 (43),
# 14:05 (2), 14:10 (4), 15:00 (4); S5 06-21 08:00 (4). S4 is 2025-12-31 23:59 UTC (7 words).


SHARED_REPORT = os.path.join(FIXTURES, "skill-report-utc.json")


def test_full_report_matches_the_shared_fixture():
    """The web repo decodes this report's url and checks it against these stats (tests/unit/skill-url.test.ts)."""
    with open(SHARED_REPORT, encoding="utf-8") as handle:
        assert report("--site", "https://example.test") == json.load(handle)


@pytest.mark.skipif(not web_repo(), reason="the web repo is private, so this runs only on a dev machine")
def test_shared_report_copy_matches_the_web_repo():
    web_copy = os.path.join(web_repo(), "tests", "fixtures", "skill-report-utc.json")
    with open(web_copy, encoding="utf-8") as web, open(SHARED_REPORT, encoding="utf-8") as copy:
        assert web.read() == copy.read()


def test_default_url_is_exact():
    done = cli("--claude-dir", CLAUDE, "--tz", "UTC")
    assert done.returncode == 0
    assert done.stdout == (
        rewind.DEFAULT_SITE + "/r?v=1&p=claude-code&m=receipts&a=0&y=2026&c=4&mg=11&d=6&s=4&sr=03-02..03-05"
        "&bd=06-20&bm=4&lh=03%3A47&th=14&ns=18&wu=103&wa=23&t=app%3A64%2Cother%3A36&ty=3&so=1&ar=2&pc=BDSP"
        "&rk=90&pl=Rookie&tk=110&md=opus-5.5%2Chaiku-3.5&src=skill\n"
    )


def test_months_are_exact():
    assert report()["months"] == [
        {"month": "Mar", "messages": 6, "activeDays": 4, "topProject": "app"},
        {"month": "Jun", "messages": 5, "activeDays": 2, "topProject": "other"},
    ]


def test_melbourne_numbers_are_exact():
    """AEDT (+11) in January and March, AEST (+10) in June. S4 moves into 2026-01-01, S3 into 06-21 after midnight."""
    data = report("--tz", "Australia/Melbourne")
    assert data["stats"] == {
        "conversations": 5,  # S4 joins.
        "messages": 12,
        "assistantMessages": 4,
        "activeDays": 5,  # 01-01, 03-02, 03-03, 03-05, 06-21. 03-04 23:30 UTC is 03-05 10:30.
        "streak": 2,
        "streakStart": "2026-03-02",
        "streakEnd": "2026-03-03",
        "busiestDay": "2026-06-21",  # S3 (00:00 to 01:00) and S5 (18:00).
        "busiestDayMessages": 5,
        "latestClock": "01:00",  # 15:00 UTC on 06-20.
        "typicalHour": 0,  # 00:00, 00:05 and 00:10.
        "nightShare": 33,  # 4 of 12.
        "wordsYou": 110,  # 103 plus the 7 words of S4.
        "wordsAi": 23,
        "thankYous": 3,
        "sorrys": 1,
        "absolutelyRight": 2,
        "greatQuestions": 1,
        "tokensOut": 110,
        "models": ["opus-5.5", "haiku-3.5"],
        "toolUsePerAssistantMessage": 0.75,
        "medianWords": 6.5,  # 12 counts: the middle two are 6 and 7.
        "thanksPer100": 25.0,
        **persona("BNSP"),  # Night share 33 is at least 25.
        "rankPercent": 90,
        "power": "Rookie",
    }
    assert data["range"] == {
        "since": "2026-01-01",
        "until": "2026-12-31",
        "firstDay": "2026-01-01",
        "lastDay": "2026-06-21",
    }
    assert data["projects"] == [{"name": "app", "share": 58}, {"name": "other", "share": 42}]
    assert data["months"] == [
        {"month": "Jan", "messages": 1, "activeDays": 1, "topProject": "other"},
        {"month": "Mar", "messages": 6, "activeDays": 3, "topProject": "app"},
        {"month": "Jun", "messages": 5, "activeDays": 1, "topProject": "other"},
    ]
    # No thanks after 2 AM in Melbourne, so that seed gives way to the words seed.
    assert data["seeds"] == [
        "Top project took 58% of all messages",
        "5 messages on Jun 21",
        "opus-5.5 wrote 23 words; you wrote 110",
    ]


def test_since_june_numbers_are_exact():
    data = report("--since", "2026-06-01")
    assert data["stats"] == {
        "conversations": 2,  # S3 and S5.
        "messages": 5,
        "assistantMessages": 1,  # msg_004 only.
        "activeDays": 2,
        "streak": 2,
        "streakStart": "2026-06-20",
        "streakEnd": "2026-06-21",
        "busiestDay": "2026-06-20",
        "busiestDayMessages": 4,
        "latestClock": "15:00",
        "typicalHour": 14,
        "nightShare": 0,
        "wordsYou": 57,  # 43 + 2 + 4 + 4 + 4.
        "wordsAi": 4,
        "thankYous": 0,
        "sorrys": 0,
        "absolutelyRight": 0,
        "greatQuestions": 1,
        "tokensOut": 25,
        "models": ["haiku-3.5"],
        "toolUsePerAssistantMessage": 0.0,
        "medianWords": 4,
        "thanksPer100": 0.0,
        **persona("TDSR"),
        "rankPercent": 90,
        "power": "Rookie",
    }
    assert data["projects"] == [{"name": "other", "share": 80}, {"name": "app", "share": 20}]
    assert data["seeds"] == [
        "Top project took 80% of all messages",
        "4 messages on Jun 20",
        "haiku-3.5 wrote 4 words; you wrote 57",
    ]
    assert "&ty=0&so=0&ar=0&" in data["url"]


def test_codex_numbers_are_exact():
    data = json_of("--platform", "codex", "--codex-dir", CODEX, "--tz", "UTC")
    assert data["stats"] == {
        "conversations": 1,
        "messages": 1,  # The response_item and the event_msg of one prompt count once.
        "assistantMessages": 1,
        "activeDays": 1,
        "streak": 1,
        "streakStart": "2026-04-10",
        "streakEnd": "2026-04-10",
        "busiestDay": "2026-04-10",
        "busiestDayMessages": 1,
        "latestClock": "01:00",
        "typicalHour": 1,
        "nightShare": 100,
        "wordsYou": 7,
        "wordsAi": 8,
        "thankYous": 1,
        "sorrys": 0,
        "absolutelyRight": 0,  # "You're right" without "absolutely".
        "greatQuestions": 0,
        "tokensOut": 77,
        "models": ["gpt-5.1-codex"],
        "toolUsePerAssistantMessage": 1.0,  # One function_call.
        "medianWords": 7,
        "thanksPer100": 100.0,
        **persona("BNSP"),
        "rankPercent": 90,
        "power": "Rookie",
    }
    assert data["projects"] == [{"name": "app", "share": 100}]
    assert data["seeds"] == [
        "Top project took 100% of all messages",
        "1 message on Apr 10",
        "gpt-5.1-codex wrote 8 words; you wrote 7",
    ]
    assert data["url"] == (
        rewind.DEFAULT_SITE + "/r?v=1&p=codex&m=receipts&a=0&y=2026&c=1&mg=1&d=1&s=1&sr=04-10..04-10&bd=04-10"
        "&bm=1&lh=01%3A00&th=1&ns=100&wu=7&wa=8&t=app%3A100&ty=1&so=0&ar=0&pc=BNSP&rk=90&pl=Rookie&tk=77"
        "&md=gpt-5.1-codex&src=skill"
    )


def test_history_only_numbers_are_exact():
    """history.jsonl has prompts only: no assistant numbers, and /clear is not a prompt."""
    data = json_of("--claude-dir", HISTORY_ONLY, "--tz", "UTC")
    assert data["stats"] == {
        "conversations": 2,
        "messages": 2,
        "assistantMessages": 0,
        "activeDays": 2,
        "streak": 2,
        "streakStart": "2026-03-02",
        "streakEnd": "2026-03-03",
        "busiestDay": "2026-03-02",
        "busiestDayMessages": 1,
        "latestClock": "09:00",
        "typicalHour": 9,
        "nightShare": 0,
        "wordsYou": 7,
        "wordsAi": 0,
        "thankYous": 1,
        "sorrys": 0,
        "absolutelyRight": 0,
        "greatQuestions": 0,
        "tokensOut": 0,
        "models": [],
        "toolUsePerAssistantMessage": 0,
        "medianWords": 3.5,
        "thanksPer100": 50.0,
        **persona("TDSP"),
        "rankPercent": 90,
        "power": "Rookie",
    }
    assert data["seeds"] == ["Top project took 100% of all messages", "1 message on Mar 2", "Said thanks 1 time"]
    assert data["url"] == (
        rewind.DEFAULT_SITE + "/r?v=1&p=claude-code&m=receipts&a=0&y=2026&c=2&mg=2&d=2&s=2&sr=03-02..03-03"
        "&bd=03-02&bm=1&lh=09%3A00&th=9&ns=0&wu=7&t=app%3A100&ty=1&so=0&pc=TDSP&rk=90&pl=Rookie&src=skill"
    )


def test_anon_changes_only_the_project_names():
    plain, anon = report(), report("--anon")
    assert anon["stats"] == plain["stats"]
    assert anon["seeds"] == plain["seeds"]
    assert anon["projects"] == [{"name": "Project A", "share": 64}, {"name": "Project B", "share": 36}]
    assert anon["url"] == plain["url"].replace("t=app%3A64%2Cother%3A36", "t=Project+A%3A64%2CProject+B%3A36")


@pytest.mark.parametrize(
    "count,word,text",
    [(0, "time", "0 times"), (1, "time", "1 time"), (2, "message", "2 messages"), (1, "word", "1 word")],
)
def test_seed_plurals(count, word, text):
    assert rewind.plural(count, word) == text
