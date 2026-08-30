#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Live NLCD 2021 impervious clip to HUC 04040001. Refuses the fixture grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402

ensure_paths()

from calumetmap.align import require_live_template  # noqa: E402
from calumetmap.config import HUC8, TEMPLATE_KIND_NLCD  # noqa: E402
from calumetmap.fetch import default_get_bytes  # noqa: E402
from calumetmap.huc import load_huc  # noqa: E402
from calumetmap.template import write_nlcd_template  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--huc",
        type=Path,
        default=REPO / "data" / "raw" / "huc{0}.geojson".format(HUC8),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO / "data" / "interim" / "nlcd_impervious_2021_{0}.tif".format(HUC8),
    )
    args = parser.parse_args()
    huc = load_huc(args.huc)
    grid = write_nlcd_template(args.out, huc, get_bytes=default_get_bytes)
    require_live_template(grid)
    print(
        "nlcd {0} {1}x{2} kind={3}".format(
            grid.path, grid.width, grid.height, TEMPLATE_KIND_NLCD
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
