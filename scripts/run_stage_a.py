#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Stage A live path: NLCD 2021 template plus NFHL layer 28. No HAND, no P."""

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
from calumetmap.errors import GateError  # noqa: E402
from calumetmap.fetch import default_get_bytes, fetch_wbd  # noqa: E402
from calumetmap.huc import load_huc  # noqa: E402
from calumetmap.stage_a import run_stage_a  # noqa: E402
from calumetmap.template import inspect_template, write_nlcd_template  # noqa: E402


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
    parser.add_argument("--out", type=Path, default=REPO / "logs" / "stage_a")
    parser.add_argument(
        "--interim",
        type=Path,
        default=REPO / "data" / "interim",
    )
    args = parser.parse_args()
    if not args.huc.is_file():
        fetch_wbd(args.huc.parent)
    if not args.template.is_file():
        huc = load_huc(args.huc)
        write_nlcd_template(args.template, huc, get_bytes=default_get_bytes)
    template = inspect_template(args.template, kind=TEMPLATE_KIND_NLCD)
    require_live_template(template)
    report = run_stage_a(
        huc_path=args.huc,
        template_path=args.template,
        interim_dir=args.interim,
        out_dir=args.out,
    )
    zc = report.get("zone_class_counts") or {}
    samples = report.get("gate_samples") or []
    print(
        "stage {0} gate={1} template={2}x{3} unshaded_x={4} sfha={5} samples={6}".format(
            report["stage"],
            report["gate"],
            report["template_shape"][1],
            report["template_shape"][0],
            zc.get("unshaded_x"),
            zc.get("sfha"),
            [s.get("name") + "=" + s.get("zone_class", "?") for s in samples],
        )
    )
    if not report.get("firm_unshaded_x_ok"):
        raise GateError("Stage A FIRM unshaded X gate failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
