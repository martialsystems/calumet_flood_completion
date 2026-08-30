# Copyright (c) 2026 Martial Systems LLC
"""Stage A: live NLCD 2021 template and NFHL zone_class. No HAND, no P."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from calumetmap.align import require_live_template, template_fingerprint
from calumetmap.config import TEMPLATE_KIND_NLCD
from calumetmap.firm import (
    fetch_firm_pages,
    rasterize_firm,
    refuse_parent_gate_samples,
    require_gate_sample_mix,
    summarize_firm_rasters,
)
from calumetmap.huc import load_huc
from calumetmap.report import build_stage_a_report, write_report
from calumetmap.template import inspect_template

try:
    from calumetforge.gate import require_claims, require_huc, require_stage
except ImportError:  # pragma: no cover

    def require_claims(**kwargs):
        del kwargs

    def require_huc(**kwargs):
        del kwargs

    def require_stage(**kwargs):
        del kwargs


def run_stage_a(
    *,
    huc_path: Path,
    template_path: Path,
    interim_dir: Path,
    out_dir: Path,
    get_json=None,
    firm_features: list | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    require_claims()
    refuse_parent_gate_samples()
    require_gate_sample_mix()
    huc = load_huc(huc_path)
    require_huc(huc8=huc.huc8, parent_huc=False)
    template = inspect_template(template_path, kind=TEMPLATE_KIND_NLCD)
    require_live_template(template)
    require_stage(
        current_stage="0",
        target_stage="A",
        template_kind=TEMPLATE_KIND_NLCD,
        thread_id="stage_a",
    )
    interim_dir.mkdir(parents=True, exist_ok=True)
    sfha_path = interim_dir / "sfha.tif"
    zone_path = interim_dir / "zone_class.tif"
    firm_info = None
    if firm_features is None and sfha_path.is_file() and zone_path.is_file():
        try:
            firm_info = summarize_firm_rasters(template, sfha_path, zone_path)
        except GateError:
            firm_info = None
    if firm_info is None:
        if firm_features is None:
            if get_json is None:
                from calumetmap.fetch import default_get_json

                getter = default_get_json
            else:
                getter = get_json
            _wkid, firm_features = fetch_firm_pages(getter, huc=huc)
            del _wkid
        firm_info = rasterize_firm(
            firm_features,
            template,
            sfha_dest=sfha_path,
            zone_dest=zone_path,
        )
    extra_out = dict(extra or {})
    extra_out.setdefault("template_fingerprint", template_fingerprint(template))
    extra_out.setdefault("template_source", template.path.name)
    extra_out.setdefault("huc_source", huc_path.name)
    report = build_stage_a_report(huc, template, firm_info=firm_info, extra=extra_out)
    require_stage(
        current_stage="A",
        target_stage="A",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=bool(report.get("firm_unshaded_x_ok")),
        stage_a_report=True,
        thread_id="stage_a_complete",
    )
    write_report(out_dir, report)
    return report
