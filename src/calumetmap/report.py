# Copyright (c) 2026 Martial Systems LLC
"""Stage 0 report. Pixel-grid bootstrap. Claim-scanned."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from calumetmap.claims import require_clean, scan_obj
from calumetmap.config import (
    HUC8,
    HUC_NAME,
    P_DEFINITION,
    STATE_CODE,
    TEMPLATE_CRS,
    TEMPLATE_RES_M,
    WBD_LIVE_AREASQKM,
)
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
        "wbd_live_areasqkm": WBD_LIVE_AREASQKM,
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
    stage = str(report.get("stage") or "0").lower()
    names = {
        "0": "stage0_report.json",
        "a": "stage_a_report.json",
        "b": "stage_b_report.json",
        "c": "stage_c_report.json",
    }
    name = names.get(stage, "stage0_report.json")
    path = out_dir / name
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def build_stage_a_report(
    huc: HucLayer,
    template: TemplateGrid,
    *,
    firm_info: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if huc.huc8 != HUC8:
        raise GateError("HUC {0!r} != {1!r}".format(huc.huc8, HUC8))
    if template.kind != "nlcd_2021":
        raise GateError("Stage A template_kind must be nlcd_2021")
    if huc.states and STATE_CODE not in huc.states.upper():
        raise GateError("HUC states={0!r} missing {1}".format(huc.states, STATE_CODE))
    report: dict[str, Any] = {
        "stage": "A",
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
        "n_huc_features": huc.n_features,
        "huc_states": huc.states,
        "huc_areasqkm": huc.areasqkm,
        "wbd_live_areasqkm": WBD_LIVE_AREASQKM,
        "firm": firm_info,
        "firm_source": firm_info.get("firm_source"),
        "firm_where": firm_info.get("firm_where"),
        "firm_unshaded_x_ok": bool(firm_info.get("firm_unshaded_x_ok")),
        "gate_samples": firm_info.get("gate_samples") or [],
        "zone_class_counts": firm_info.get("zone_class_counts") or {},
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
    require_clean(json.dumps(report, default=str), source="stage_a_report")
    hits = scan_obj(report)
    if hits:
        raise GateError("report claim scan {0}".format(hits))
    return report


def build_stage_b_report(
    huc: HucLayer,
    template: TemplateGrid,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if huc.huc8 != HUC8:
        raise GateError("HUC {0!r} != {1!r}".format(huc.huc8, HUC8))
    if template.kind != "nlcd_2021":
        raise GateError("Stage B template_kind must be nlcd_2021")
    report: dict[str, Any] = {
        "stage": "B",
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
        "huc_states": huc.states,
        "huc_areasqkm": huc.areasqkm,
        "wbd_live_areasqkm": WBD_LIVE_AREASQKM,
        "ofr_2008_covers_this_huc": False,
        "indy_plants_copied": False,
        "nora_hand_copied": False,
        "stage_c_started": False,
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
    require_clean(json.dumps(report, default=str), source="stage_b_report")
    hits = scan_obj(report)
    if hits:
        raise GateError("report claim scan {0}".format(hits))
    return report


def build_stage_c_report(
    huc: HucLayer,
    template: TemplateGrid,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if huc.huc8 != HUC8:
        raise GateError("HUC {0!r} != {1!r}".format(huc.huc8, HUC8))
    if template.kind != "nlcd_2021":
        raise GateError("Stage C template_kind must be nlcd_2021")
    report: dict[str, Any] = {
        "stage": "C",
        "state": STATE_CODE,
        "huc8": HUC8,
        "huc_name": huc.name or HUC_NAME,
        "unit": "pixel",
        "p_definition": P_DEFINITION,
        "colorbar": P_DEFINITION,
        "vector_crs": huc.crs,
        "template_crs": template.crs,
        "template_res_m": TEMPLATE_RES_M,
        "template_kind": template.kind,
        "template_shape": [template.height, template.width],
        "huc_states": huc.states,
        "huc_areasqkm": huc.areasqkm,
        "wbd_live_areasqkm": WBD_LIVE_AREASQKM,
        "ofr_2008_covers_this_huc": False,
        "indy_plants_copied": False,
        "nora_hand_copied": False,
        "fim_started": False,
        "industrial_points_started": False,
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
    require_clean(json.dumps(report, default=str), source="stage_c_report")
    hits = scan_obj(report)
    if hits:
        raise GateError("report claim scan {0}".format(hits))
    return report
