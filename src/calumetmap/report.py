# Copyright (c) 2026 Martial Systems LLC
"""Stage 0 report. Pixel-grid bootstrap. Claim-scanned."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from calumetmap.claims import require_clean, scan_obj
from calumetmap.config import HUC8, HUC_NAME, P_DEFINITION, STATE_CODE, TEMPLATE_CRS, TEMPLATE_RES_M
from calumetmap.errors import GateError
from calumetmap.huc import HucLayer
from calumetmap.template import TemplateGrid


def build_stage0_report(
    huc: HucLayer,
    template: TemplateGrid,
    *,
    huc_source: str,
    template_source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if huc.huc8 != HUC8:
        raise GateError("HUC {0!r} != {1!r}".format(huc.huc8, HUC8))
    if template.crs != TEMPLATE_CRS:
        raise GateError("template CRS {0} != {1}".format(template.crs, TEMPLATE_CRS))
    report: dict[str, Any] = {
        "stage": "0",
        "state": STATE_CODE,
        "huc8": HUC8,
        "huc_name": huc.name or HUC_NAME,
        "unit": "pixel",
        "p_definition": P_DEFINITION,
        "vector_crs": huc.crs,
        "template_crs": template.crs,
        "template_res_m": TEMPLATE_RES_M,
        "template_kind": template.kind,
        "template_shape": [template.height, template.width],
        "huc_source": huc_source,
        "template_source": template_source,
        "n_huc_features": huc.n_features,
        "huc_states": huc.states,
        "huc_areasqkm": huc.areasqkm,
        "ofr_2008_covers_this_huc": False,
        "indy_plants_copied": False,
        "claim_bans": [
            "casualty_count",
            "climate_attribution",
            "tornado_count",
            "population_at_risk",
            "p_as_100yr",
            "unmapped_risk",
            "indy_plant_copy",
        ],
        "gate": "pass",
    }
    if extra:
        report.update(extra)
    require_clean(json.dumps(report, default=str), source="stage0_report")
    hits = scan_obj(report)
    if hits:
        raise GateError("report claim scan {0}".format(hits))
    return report


def write_report(out_dir: Path, report: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "stage0_report.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return path
