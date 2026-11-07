import json
import os
from argparse import Namespace
from datetime import date

import pytest

import rewind
import sync_codec_fixtures
import urlspec
from helpers import CLAUDE, FIXTURES, REPO, cli, report


def run_url(*args):
    done = cli("--claude-dir", CLAUDE, "--tz", "UTC", *args)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


# Each row is [key, value, new URLSearchParams([[key, value]]).toString()] from Node 25.
BROWSER_OUTPUT = [
    ["n", "Ana María", "n=Ana+Mar%C3%ADa"],
    ["t", "Code:42,Product:18", "t=Code%3A42%2CProduct%3A18"],
    ["pv", "Jan|from a|Oct|to b", "pv=Jan%7Cfrom+a%7COct%7Cto+b"],
    [
        "mo",
        "Jan|Asked how to exit vim.;Mar|Wrote a speech.",
        "mo=Jan%7CAsked+how+to+exit+vim.%3BMar%7CWrote+a+speech.",
    ],
    [
        "ro",
        "Ship it (again)! ~ 100% * ok_go-now. “done” …",
        "ro=Ship+it+%28again%29%21+%7E+100%25+*+ok_go-now.+%E2%80%9Cdone%E2%80%9D+%E2%80%A6",
    ],
    ["sr", "03-02..03-24", "sr=03-02..03-24"],
    ["lh", "03:47", "lh=03%3A47"],
    ["x", "日本語 é \U0001f600", "x=%E6%97%A5%E6%9C%AC%E8%AA%9E+%C3%A9+%F0%9F%98%80"],
    ["y", "a/b?c=d&e#f+g'h", "y=a%2Fb%3Fc%3Dd%26e%23f%2Bg%27h"],
]


@pytest.mark.parametrize("key,value,expected", BROWSER_OUTPUT)
def test_encoding_matches_url_search_params(key, value, expected):
    assert f"{key}={rewind.form_encode(value)}" == expected


def test_default_url_is_canonical():
    url = run_url()
    data = urlspec.decode(url)
    assert url.startswith(rewind.DEFAULT_SITE + "/r?v=1&p=claude-code&m=receipts&a=0&y=2026&")
    assert url.endswith("&src=skill")
    assert data["c"] == "4" and data["mg"] == "11" and data["t"] == "app:64,other:36"
    assert data["sr"] == "03-02..03-05" and data["bd"] == "06-20" and data["lh"] == "03:47"
    assert data["pc"] == "BDSP" and data["md"] == "opus-5.5,haiku-3.5"
    assert "n" not in data and "pn" not in data


def test_text_flags_reach_the_url():
    url = run_url(
        "--name",
        "Ana",
        "--roast",
        "You said thanks to a compiler.",
        "--compliment",
        "You ship.",
        "--moments",
        "Nope|Dropped.;Mar|Shipped the login.;June|Planned a move.",
        "--persona-name",
        "The Late Shipper",
    )
    data = urlspec.decode(url)
    assert data["n"] == "Ana"
    assert data["ro"] == "You said thanks to a compiler."
    assert data["co"] == "You ship."
    assert data["mo"] == "Mar|Shipped the login.;Jun|Planned a move."
    assert data["pn"] == "The Late Shipper"


def test_site_flag_sets_the_origin():
    assert run_url("--site", "https://example.test/").startswith("https://example.test/r?")
    assert run_url("--site", "example.test").startswith("https://example.test/r?")
    assert run_url("--site", "http://localhost:3000/x?y").startswith("http://localhost:3000/r?")
    assert run_url("--site", "").startswith(rewind.DEFAULT_SITE + "/r?")


def test_year_comes_from_since():
    assert "&y=2025&" in cli("--claude-dir", CLAUDE, "--since", "2025-01-01").stdout


@pytest.mark.parametrize(
    "raw,limit,expected",
    [
        ("  two   words ", 20, "two words"),
        ('"quoted"', 20, "quoted"),
        ("“curly”", 20, "curly"),
        ("trailing)", 20, "trailing"),
        ("trailing]", 20, "trailing"),
        ("(balanced)", 20, "(balanced)"),
        ('"A" and "B"', 20, '"A" and "B"'),
        ("\u00abguillemets\u00bb", 20, "guillemets"),
        ("null", 20, ""),
        ("N/A", 20, ""),
        ("zero\u200bwidth", 20, "zerowidth"),
        ("party \U0001f389 time", 20, "party time"),
        ("flag \U0001f1e6\U0001f1fa here", 20, "flag here"),
        ("tab\tand\nline", 20, "tab and line"),
        ("bell\x07", 20, "bell"),
        ("bad\udc80byte", 20, "badbyte"),
        ("<script>", 20, "<script>"),
        ("x" * 30, 10, "x" * 9 + "…"),
        (None, 10, ""),
    ],
)
def test_clean_text(raw, limit, expected):
    assert rewind.clean_text(raw, limit) == expected


def test_clean_name_allows_only_name_characters():
    assert rewind.clean_name("  Mary-Jane O'Neil  ") == "Mary-Jane O'Neil"
    assert rewind.clean_name("Ana3 <b>") == "Ana b"
    assert rewind.clean_name("Zoë") == "Zoë"
    assert len(rewind.clean_name("Maximiliana Montgomery-Windsor")) == 24


def test_theme_name_removes_separators():
    assert rewind.theme_name("a:b,c;d|e") == "a-b-c-d-e"
    assert rewind.theme_name(":::") == "project"
    assert len(rewind.theme_name("a-very-long-project-folder-name")) == 18


def test_separators_inside_a_moment_stay():
    assert rewind.parse_moments("Mar|CI/CD; then Oct went|green;June|Done") == [
        ("Mar", "CI/CD; then Oct went|green"),
        ("Jun", "Done"),
    ]


def test_moments_stop_at_five():
    raw = ";".join(f"{month}|Line" for month in rewind.MONTHS)
    assert len(rewind.parse_moments(raw)) == 5


def fields(**extra):
    base = {"v": 1, "p": "claude-code", "m": "receipts", "a": 0, "y": 2026, "c": 1, "mg": 2, "src": "skill"}
    return {**base, **extra}


def test_short_query_is_unchanged():
    assert rewind.fit_query(fields(ro="Short")) == "v=1&p=claude-code&m=receipts&a=0&y=2026&c=1&mg=2&ro=Short&src=skill"


def test_query_stops_at_the_limit():
    moments = [(month, "あ" * 69) for month in rewind.MONTHS[:5]]
    query = rewind.fit_query(fields(mo=moments, ro="あ" * 140, co="あ" * 100, pn="あ" * 32))
    assert len(query) <= rewind.ENCODE_MAX


ELLIPSIS = "%E2%80%A6"


def test_truncation_shortens_every_moment_before_the_roast():
    moments = [(month, "m" * 70) for month in rewind.MONTHS[:5]]
    query = rewind.fit_query(fields(mo=moments, ro="r" * 140, co="c" * 100, pn="p" * 32), limit=650)
    assert len(query) <= 650
    assert "ro=" + "r" * 140 in query
    assert "co=" + "c" * 100 in query
    assert "pn=" + "p" * 32 in query
    assert query.count("%7C") == 5
    assert query.count(ELLIPSIS) == 5


def test_truncation_order_after_moments():
    query = rewind.fit_query(fields(mo=[("Jan", "m" * 70)], ro="r" * 140, co="c" * 100, pn="p" * 32), limit=295)
    assert len(query) <= 295
    assert "mo=Jan" in query
    assert "co=" + "c" * 100 in query
    assert "pn=" + "p" * 32 in query
    assert "r" * 100 not in query


def test_fields_drop_only_after_every_text_is_short():
    moments = [(month, "m" * 70) for month in rewind.MONTHS[:5]]
    query = rewind.fit_query(fields(mo=moments, ro="r" * 140, co="c" * 100, t=["app:60", "lib:40"]), limit=125)
    assert len(query) <= 125
    assert "mo=" not in query
    assert "t=app" in query


def test_last_resort_removes_themes_from_the_end():
    query = rewind.fit_query(fields(t=["aaaaaaaa:50", "bbbbbbbb:50"], pl="Ninja", md=["opus-5.5"]), limit=100)
    assert len(query) <= 100
    assert "aaaaaaaa" in query and "bbbbbbbb" not in query


def test_truncation_order_is_the_one_in_the_spec():
    assert rewind.TRUNCATE_ORDER == ("mo", "ro", "co", "pv", "pn")


def test_every_key_in_the_spec_order_is_known():
    assert rewind.CANONICAL_ORDER == urlspec.KEYS


def test_worst_case_fits():
    args = Namespace(
        platform="claude-code",
        since=date(2026, 1, 1),
        name="あ" * 40,
        persona_name="あ" * 40,
        moments=";".join(f"{month}|{chr(0x3042) * 90}" for month in rewind.MONTHS),
        roast="あ" * 300,
        compliment="あ" * 300,
    )
    stats = report()["stats"]
    projects = [{"name": rewind.theme_name("あ" * 40), "share": 20} for _ in range(5)]
    query = rewind.fit_query(rewind.build_fields(args, stats, projects))
    assert len(query) <= rewind.ENCODE_MAX
    urlspec.decode("https://example.test/r?" + query)


def stat_text(stat, approx_link):
    if not stat:
        return None
    if "lo" in stat:
        return f"{stat['lo']}-{stat['hi']}"
    return ("~" if stat["approx"] and not approx_link else "") + str(stat["value"])


def day_text(day):
    return f"{day['month']:02d}-{day['day']:02d}"


def fields_from_rewind_data(data):
    """Turns a RewindData from the shared fixture into the input of the Python encoder."""
    approx = data["approx"]
    pivot = data.get("pivot")
    span = data.get("streakRange")
    clock = data.get("latestClock")
    themes = data.get("themes") or []
    return {
        "v": 1,
        "p": data["platform"],
        "m": data["mode"],
        "a": 1 if approx else 0,
        "y": data["year"],
        "n": rewind.clean_name(data.get("name")),
        "c": stat_text(data.get("conversations"), approx),
        "mg": stat_text(data.get("messages"), approx),
        "d": stat_text(data.get("activeDays"), approx),
        "s": stat_text(data.get("streak"), approx),
        "sr": f"{day_text(span['start'])}..{day_text(span['end'])}" if span else None,
        "bd": day_text(data["busiestDay"]) if data.get("busiestDay") else None,
        "bm": stat_text(data.get("busiestDayMessages"), approx),
        "lh": f"{clock['h']:02d}:{clock['m']:02d}" if clock else None,
        "th": data.get("typicalHour"),
        "ns": data.get("nightShare"),
        "wu": stat_text(data.get("wordsYou"), approx),
        "wa": stat_text(data.get("wordsAi"), approx),
        "t": [f"{t['name']}:{t['percent']}" if "percent" in t else t["name"] for t in themes],
        "ty": stat_text(data.get("thankYous"), approx),
        "so": stat_text(data.get("sorrys"), approx),
        "ar": stat_text(data.get("absolutelyRight"), approx),
        "pc": data.get("persona"),
        "pn": rewind.clean_text(data.get("personaName"), rewind.MAX_PERSONA_NAME),
        "pv": "|".join((pivot["fromMonth"], pivot["from"], pivot["toMonth"], pivot["to"])) if pivot else None,
        "mo": [(item["month"], item["text"]) for item in data.get("moments") or []],
        "ro": rewind.clean_text(data.get("roast"), rewind.MAX_ROAST),
        "co": rewind.clean_text(data.get("compliment"), rewind.MAX_COMPLIMENT),
        "rk": data.get("rankPercent"),
        "pl": rewind.clean_text(data.get("power"), rewind.MAX_POWER),
        "tk": stat_text(data.get("tokensOut"), approx),
        "md": data.get("models") or [],
        "src": data["source"],
    }


FIXTURE_COPY = os.path.join(FIXTURES, "codec-fixtures.json")
WEB_FIXTURE = os.path.join(
    os.path.dirname(REPO), "ai-rewind", "src", "lib", "codec", "__fixtures__", "codec-fixtures.json"
)

with open(FIXTURE_COPY, encoding="utf-8") as handle:
    SHARED = json.load(handle)


@pytest.mark.parametrize("case", SHARED["encode"], ids=lambda case: case["name"])
def test_shared_fixture_encodes_to_the_same_bytes(case):
    assert rewind.fit_query(fields_from_rewind_data(case["data"])) == case["query"]


def test_shared_fixture_copy_holds_only_sample_names():
    with open(FIXTURE_COPY, encoding="utf-8") as handle:
        body = handle.read()
    for private, _ in sync_codec_fixtures.REPLACEMENTS:
        assert private not in body


@pytest.mark.skipif(not os.path.exists(WEB_FIXTURE), reason="the web repo is private, so this runs only on a dev box")
def test_shared_fixture_copy_matches_the_web_repo():
    with open(WEB_FIXTURE, encoding="utf-8") as handle:
        web = handle.read()
    with open(FIXTURE_COPY, encoding="utf-8") as handle:
        assert sync_codec_fixtures.public_copy(web) == handle.read()
