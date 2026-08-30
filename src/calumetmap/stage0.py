# Copyright (c) 2026 Martial Systems LLC
"""Production Stage 0 path: HUC, template, laws, report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from calumetmap.config import (
    FIXTURE_COLS,
    FIXTURE_ROWS,
    TEMPLATE_KIND_FIXTURE,
    TEMPLATE_KIND_NLCD,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.report import build_stage0_report, write_report
from calumetmap.template import inspect_template, sha256_file, write_fixture_template

try:
    from calumetforge.gate import require_claims, require_huc, require_stage
except ImportError:  # pragma: no cover

    def require_claims(**kwargs):
        del kwargs

    def require_huc(**kwargs):
        del kwargs

    def require_stage(**kwargs):
        del kwargs


def run_stage0(
    *,
    huc_path: Path,
    out_dir: Path,
    template_path: Path | None = None,
    huc_wkid: int | None = None,
    template_kind: str = TEMPLATE_KIND_FIXTURE,
    extra: dict[str, Any] | None = None,
) -> dict:
    require_claims()
    huc = load_huc(huc_path, wkid=huc_wkid)
    require_huc(huc8=huc.huc8, parent_huc=False)
    if template_kind not in {TEMPLATE_KIND_FIXTURE, TEMPLATE_KIND_NLCD}:
        template_kind = TEMPLATE_KIND_FIXTURE
    if template_path is None:
        if template_kind == TEMPLATE_KIND_NLCD:
            raise GateError("nlcd_2021 template path is required")
        template_path = out_dir / "template.tif"
        template = write_fixture_template(template_path)
        kind = TEMPLATE_KIND_FIXTURE
    else:
        kind = template_kind
        template = inspect_template(template_path, kind=kind)
        if kind == TEMPLATE_KIND_NLCD and (
            template.width <= FIXTURE_COLS and template.height <= FIXTURE_ROWS
        ):
            raise GateError("nlcd_2021 template looks like the fixture grid")
    require_stage(
        current_stage="0",
        target_stage="0",
        template_kind=kind,
        thread_id="stage0",
    )
    extra_out = dict(extra or {})
    extra_out.setdefault("template_sha256", sha256_file(template.path))
    report = build_stage0_report(
        huc,
        template,
        huc_source=huc_path.name,
        template_source=template.path.name,
        extra=extra_out,
    )
    write_report(out_dir, report)
    return report
