#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Stage D: TRI on calibrated P. Top five by window-max. No Indy names. No FIM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402

ensure_paths()

from calumetmap.config import HUC8  # noqa: E402
from calumetmap.stage_d import run_stage_d  # noqa: E402


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
    parser.add_argument("--out", type=Path, default=REPO / "logs" / "stage_d")
    parser.add_argument(
        "--stage-c-report",
        type=Path,
        default=REPO / "logs" / "stage_c" / "stage_c_report.json",
    )
    parser.add_argument("--interim", type=Path, default=REPO / "data" / "interim")
    parser.add_argument("--tri-csv", type=Path, default=None)
    args = parser.parse_args()
    report = run_stage_d(
        huc_path=args.huc,
        template_path=args.template,
        interim_dir=args.interim,
        out_dir=args.out,
        stage_c_report_path=args.stage_c_report,
        tri_csv=args.tri_csv,
    )
    names = [r["name"] for r in report.get("d1_headline_rows") or []]
    print(
        "stage {0} gate={1} n_tris={2} d1={3} headline={4} p_source={5}".format(
            report["stage"],
            report["gate"],
            report["n_tris_huc_year"],
            report["d1_n_unshaded_x"],
            names,
            report["p_source"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
