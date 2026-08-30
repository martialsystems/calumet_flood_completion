#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetmap.errors import FetchError, GateError  # noqa: E402
from calumetmap.fetch import fetch_wbd  # noqa: E402


def main() -> int:
    dest_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "raw"
    try:
        dest = fetch_wbd(dest_dir)
    except (FetchError, GateError) as exc:
        print(exc)
        return 2
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
