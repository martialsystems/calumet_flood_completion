#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Stage B live hydrology on the Calumet NLCD template. No Nora HAND. No P."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402

ensure_paths()

from calumetmap.config import HUC8  # noqa: E402
from calumetmap.stage_b import run_stage_b  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--huc",
        type=Path,
        default=REPO / "data" / "raw" / "huc{0}.geojson".format(HUC8),
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=REPO / "data" / "interim" / "nlcd_impervious_2021_{0}.tif".format(HUC8),
    )
    parser.add_argument("--out", type=Path, default=REPO / "logs" / "stage_b")
    parser.add_argument(
        "--stage-a-report",
        type=Path,
        default=REPO / "logs" / "stage_a" / "stage_a_report.json",
    )
    parser.add_argument(
        "--interim",
        type=Path,
        default=REPO / "data" / "interim",
    )
    args = parser.parse_args()
    report = run_stage_b(
        huc_path=args.huc,
        template_path=args.template,
        interim_dir=args.interim,
        out_dir=args.out,
        stage_a_report_path=args.stage_a_report,
    )
    print(
        "stage {0} gate={1} n_interior={2} n_slope_floor={3} "
        "n_stream={4} n_hand_undef={5} ftypes={6} stage_c={7}".format(
            report["stage"],
            report["gate"],
            report.get("n_interior"),
            report.get("n_slope_floor"),
            report.get("n_stream_cells"),
            report.get("n_hand_undefined"),
            report.get("flowline_ftype_counts"),
            report.get("stage_c_started"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
