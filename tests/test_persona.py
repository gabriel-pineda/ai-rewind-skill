import json
import os
from itertools import product

import pytest

import rewind
from helpers import REPO

TABLE = rewind.load_persona_table()
WEB_COPY = os.path.join(os.path.dirname(REPO), "ai-rewind", "src", "lib", "persona.json")


def test_table_has_all_16_types():
    letters = ["".join(code) for code in product("BT", "DN", "SV", "PR")]
    assert sorted(TABLE["types"]) == sorted(letters)
    for entry in TABLE["types"].values():
        assert 0 < len(entry["name"]) <= rewind.MAX_PERSONA_NAME


@pytest.mark.skipif(not os.path.exists(WEB_COPY), reason="the web repo is private, so this runs only on a dev machine")
def test_table_matches_the_web_repo():
    with open(WEB_COPY, encoding="utf-8") as handle:
        assert json.load(handle) == TABLE


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
