#!/usr/bin/env python3
# Copyright (c) 2026 Martial Systems LLC
"""Stage 0: HUC clip, 30 m template, claim scan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]

from calumetforge._bootstrap import ensure_paths  # noqa: E402

ensure_paths()

from calumetmap.config import TEMPLATE_KIND_FIXTURE  # noqa: E402
from calumetmap.stage0 import run_stage0  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc", type=Path, required=True)
    parser.add_argument("--template", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--huc-wkid", type=int, default=None)
    parser.add_argument("--template-kind", default=TEMPLATE_KIND_FIXTURE)
    args = parser.parse_args()
    report = run_stage0(
        huc_path=args.huc,
        out_dir=args.out,
        template_path=args.template,
        huc_wkid=args.huc_wkid,
        template_kind=args.template_kind,
    )
    print(
        "stage {0} gate={1} huc={2} template={3} {4}x{5}".format(
            report["stage"],
            report["gate"],
            report["huc8"],
            report["template_kind"],
            report["template_shape"][1],
            report["template_shape"][0],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
