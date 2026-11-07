"""Text cleaning parity with the web codec.

tests/fixtures/text-cleaning.json comes from the web repo (tests/unit/text-cleaning-parity.test.ts), where each
row is checked against tidyText and cleanName. Here the same rows run through clean_text and clean_name, so the
text the skill puts in a link is the text the web decoder shows.
"""

import json
import os

import pytest

import rewind
from helpers import FIXTURES, web_repo

with open(os.path.join(FIXTURES, "text-cleaning.json"), encoding="utf-8") as handle:
    SHARED = json.load(handle)

WEB = web_repo()
WEB_COPY = os.path.join(WEB, "tests", "fixtures", "text-cleaning.json") if WEB else ""


def test_fixture_has_rows():
    assert len(SHARED["rows"]) > 300


def test_clean_text_matches_tidy_text():
    wrong = [row for row in SHARED["rows"] if rewind.clean_text(row["raw"], SHARED["max"]) != row["text"]]
    assert wrong == []


def test_clean_name_matches_clean_name():
    wrong = [row for row in SHARED["rows"] if rewind.clean_name(row["raw"]) != row["name"]]
    assert wrong == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("%E6%97%A5%E6%9C%AC", "日本"),
        ("%2541", "A"),
        ("100% sure", "100% sure"),
        ("%7C%2", "|%2"),
        ("a%E6%41", "a%E6A"),
        ("bom﻿inside", "bom inside"),
        ("unit\x1fseparator", "unitseparator"),
        ("next\x85line", "nextline"),
    ],
)
def test_percent_and_space_steps(raw, expected):
    assert rewind.clean_text(raw, 40) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("-%7C", ""),
        ("- ' -", ""),
        ("“null", ""),
        ("'a'%2", "a"),
        ("Abcdefghijklmnopqrstuvwxyzabc", "Abcdefghijklmnopqrstuvwx"),
        ("Maximiliana Montgomery-Windsor", "Maximiliana Montgomery-W"),
    ],
)
def test_name_rules(raw, expected):
    assert rewind.clean_name(raw) == expected


@pytest.mark.skipif(not os.path.exists(WEB_COPY), reason="the web repo is private, so this runs only on a dev machine")
def test_fixture_copy_matches_the_web_repo():
    with open(WEB_COPY, encoding="utf-8") as web, open(os.path.join(FIXTURES, "text-cleaning.json")) as copy:
        assert web.read() == copy.read()
