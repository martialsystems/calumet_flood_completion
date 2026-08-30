#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Stage C live train and isotonic P on 04040001. No Upper White boosters. No FIM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402

ensure_paths()

from calumetmap.config import HUC8  # noqa: E402
from calumetmap.stage_c import run_stage_c  # noqa: E402


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
    parser.add_argument("--out", type=Path, default=REPO / "logs" / "stage_c")
    parser.add_argument(
        "--stage-a-report",
        type=Path,
        default=REPO / "logs" / "stage_a" / "stage_a_report.json",
    )
    parser.add_argument(
        "--stage-b-report",
        type=Path,
        default=REPO / "logs" / "stage_b" / "stage_b_report.json",
    )
    parser.add_argument("--interim", type=Path, default=REPO / "data" / "interim")
    parser.add_argument("--raw", type=Path, default=REPO / "data" / "raw")
    args = parser.parse_args()
    report = run_stage_c(
        huc_path=args.huc,
        template_path=args.template,
        interim_dir=args.interim,
        out_dir=args.out,
        raw_dir=args.raw,
        stage_a_report_path=args.stage_a_report,
        stage_b_report_path=args.stage_b_report,
    )
    print(
        "stage {0} gate={1} pr_auc={2:.4f} base={3:.4f} hand={4:.4f} "
        "pr_auc_cal={5:.4f} n_huc10={6} calibrated={7}".format(
            report["stage"],
            report["gate"],
            report["pr_auc"],
            report["pr_auc_baseline"],
            report["hand_negated_pr_auc"],
            report["pr_auc_calibrated"],
            report["n_huc10"],
            report["probabilities_calibrated"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
