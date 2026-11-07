import json
import os
from itertools import product

import pytest

import rewind
from helpers import FIXTURES, web_repo

TABLE = rewind.load_persona_table()
WEB = web_repo()
WEB_COPY = os.path.join(WEB, "src", "lib", "persona.json") if WEB else ""
WEB_PARITY = os.path.join(WEB, "tests", "fixtures", "persona-parity.json") if WEB else ""

with open(os.path.join(FIXTURES, "persona-parity.json"), encoding="utf-8") as handle:
    PARITY = json.load(handle)

ARGUMENTS = ["toolUsePerAssistantMessage", "nightShare", "typicalHour", "medianWords", "thanksPer100"]


def derive(inputs):
    """persona_code with the inputs of derivePersona in src/lib/persona.ts. A missing input is unknown."""
    return rewind.persona_code(TABLE, *(inputs.get(name) for name in ARGUMENTS))


def combinations():
    """Every combination of the axis cases in persona-parity.json, with the four letters it must give."""
    out = [({}, "")]
    for axis in PARITY["axes"]:
        out = [
            ({**inputs, **dict(zip(axis["inputs"], values))}, code + letter)
            for inputs, code in out
            for values, letter in axis["cases"]
        ]
    return out


def test_table_has_all_16_types():
    letters = ["".join(code) for code in product("BT", "DN", "SV", "PR")]
    assert sorted(TABLE["types"]) == sorted(letters)
    for entry in TABLE["types"].values():
        assert 0 < len(entry["name"]) <= rewind.MAX_PERSONA_NAME


@pytest.mark.skipif(not os.path.exists(WEB_COPY), reason="the web repo is private, so this runs only on a dev machine")
def test_table_matches_the_web_repo():
    with open(WEB_COPY, encoding="utf-8") as handle:
        assert json.load(handle) == TABLE


@pytest.mark.skipif(
    not os.path.exists(WEB_PARITY), reason="the web repo is private, so this runs only on a dev machine"
)
def test_parity_fixture_matches_the_web_repo():
    with open(WEB_PARITY, encoding="utf-8") as web, open(os.path.join(FIXTURES, "persona-parity.json")) as copy:
        assert web.read() == copy.read()


@pytest.mark.parametrize(
    "tools,night,hour,words,thanks,code",
    [
        (0.6, 25, 22, 40, 2, "BNVP"),
        (0.59, 24, 21, 39, 1.99, "TDSR"),
        (0.6, 0, 0, 0, 0, "BDSR"),
        (0, 25, 0, 0, 0, "TNSR"),
        (0, 0, 22, 0, 0, "TNSR"),
        (0, 0, 0, 40, 0, "TDVR"),
        (0, 0, 0, 0, 2, "TDSP"),
        (None, None, None, None, None, "TDSR"),
    ],
)
def test_thresholds_match_derive_persona(tools, night, hour, words, thanks, code):
    assert rewind.persona_code(TABLE, tools, night, hour, words, thanks) == code


def test_parity_axes_cover_both_letters_of_each_axis():
    assert len(PARITY["axes"]) == len(TABLE["axes"])
    for axis, table_axis in zip(PARITY["axes"], TABLE["axes"]):
        assert {letter for _, letter in axis["cases"]} == set(table_axis["pair"])


def test_parity_every_combination_gives_the_same_code_as_the_web():
    cases = combinations()
    expected_count = 1
    for axis in PARITY["axes"]:
        expected_count *= len(axis["cases"])
    assert len(cases) == expected_count
    wrong = [(inputs, code, derive(inputs)) for inputs, code in cases if derive(inputs) != code]
    assert wrong == []
    assert len({code for _, code in cases}) == 16


@pytest.mark.parametrize("case", PARITY["cases"], ids=lambda case: case["name"])
def test_parity_named_cases(case):
    assert derive(case["inputs"]) == case["code"]
    assert TABLE["types"][case["code"]]["name"] == case["personaName"]
