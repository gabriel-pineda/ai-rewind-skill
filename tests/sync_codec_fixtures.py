#!/usr/bin/env python3
"""Copies the shared codec fixture from the web repo into tests/fixtures.

The web fixture uses sample names that do not belong in this public repo, so the copy replaces them.
Usage: python3 tests/sync_codec_fixtures.py /path/to/codec-fixtures.json
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "fixtures", "codec-fixtures.json")
REPLACEMENTS = (("Gabriel", "Ana"), ("mission-control", "demo-app"), ("og-fox", "demo-lib"))


def public_copy(body):
    for private, public in REPLACEMENTS:
        body = body.replace(private, public)
    return body


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        body = handle.read()
    with open(TARGET, "w", encoding="utf-8") as handle:
        handle.write(public_copy(body))


if __name__ == "__main__":
    main()
