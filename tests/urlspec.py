"""A strict reader of the URL format in docs/URL-SPEC.md of the web repo.

The web codec is lenient. This reader is not: every value the script emits must be in the
canonical form, because a lenient decoder would hide a mistake.
"""

import re
from urllib.parse import parse_qsl, urlsplit

KEYS = "v p m a y n c mg d s sr bd bm lh th ns wu wa t ty so ar pc pn pv mo ex ro co rk pl tk md lf ff src".split()
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
INTEGER = re.compile(r"^\d+$")
NUMBER_KEYS = "c mg d s bm wu ty so".split()
# AI-side numbers. Scaled from the session-file window, they are an estimate: lo-hi or ~N.
APPROX_KEYS = "wa ar tk".split()
APPROX = re.compile(r"^(?:\d+|~\d+|(\d+)-(\d+))$")
DAY = re.compile(r"^2\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def split_url(url):
    parts = urlsplit(url)
    assert parts.scheme in ("http", "https")
    assert parts.path == "/r"
    return parts.query, parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)


def decode(url):
    query, pairs = split_url(url)
    keys = [key for key, _ in pairs]
    assert len(keys) == len(set(keys)), "duplicate key"
    assert set(keys) <= set(KEYS), "unknown key"
    assert keys == sorted(keys, key=KEYS.index), "keys are not in canonical order"
    data = dict(pairs)
    assert all(value != "" for value in data.values()), "empty value"
    assert data["v"] == "1"
    assert data["m"] == "receipts" and data["a"] == "0" and data["src"] == "skill"
    assert 2023 <= int(data["y"]) <= 2027
    assert "c" in data or "mg" in data
    for key in NUMBER_KEYS:
        if key in data:
            assert INTEGER.match(data[key]), key
    for key in APPROX_KEYS:
        if key in data:
            match = APPROX.match(data[key])
            assert match, key
            if match.group(1):
                assert int(match.group(1)) <= int(match.group(2)), key
    for key in ("lf", "ff"):
        if key in data:
            assert DAY.match(data[key]), key
    if "lf" in data and "ff" in data:
        assert data["lf"] < data["ff"]
    assert "ex" not in data, "the skill never writes examples"
    if "d" in data:
        assert int(data["d"]) <= 366
    if "s" in data:
        assert int(data["s"]) <= 366
    if "sr" in data:
        assert re.match(r"^\d\d-\d\d\.\.\d\d-\d\d$", data["sr"])
    if "bd" in data:
        assert re.match(r"^\d\d-\d\d$", data["bd"])
    if "lh" in data:
        assert re.match(r"^([01]\d|2[0-3]):[0-5]\d$", data["lh"])
    if "th" in data:
        assert 0 <= int(data["th"]) <= 23
    if "ns" in data:
        assert 0 <= int(data["ns"]) <= 100
    if "rk" in data:
        assert 1 <= int(data["rk"]) <= 100
    if "pc" in data:
        assert re.match(r"^[BT][DN][SV][PR]$", data["pc"])
    if "t" in data:
        items = data["t"].split(",")
        assert len(items) <= 5
        for item in items:
            name, _, percent = item.partition(":")
            assert name and len(name) <= 18 and INTEGER.match(percent)
    if "mo" in data:
        items = data["mo"].split(";")
        assert len(items) <= 5
        for item in items:
            month, _, text = item.partition("|")
            assert month in MONTHS and text and len(text) <= 70
    if "md" in data:
        assert len(data["md"].split(",")) <= 3
    for key, limit in (("n", 24), ("pn", 32), ("ro", 140), ("co", 100), ("pl", 24)):
        if key in data:
            assert len(data[key]) <= limit, key
    return data
