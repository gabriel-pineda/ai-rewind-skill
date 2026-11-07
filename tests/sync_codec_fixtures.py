#!/usr/bin/env python3
"""Copies the shared codec fixture from the web repo into tests/fixtures.

The web fixture holds only neutral sample names, so the copy is byte for byte.
Usage: python3 tests/sync_codec_fixtures.py /path/to/codec-fixtures.json
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "fixtures", "codec-fixtures.json")


def main():
    shutil.copyfile(sys.argv[1], TARGET)


if __name__ == "__main__":
    main()
