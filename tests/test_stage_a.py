# Copyright (c) 2026 Martial Systems LLC

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calumetmap.config import HUC8, TEMPLATE_KIND_NLCD, WBD_LIVE_AREASQKM
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.stage0 import run_stage0
from calumetmap.stage_a import run_stage_a
from calumetmap.template import write_synthetic_nlcd

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def _features():
    huc = load_huc(HUC)
    minx, miny, maxx, maxy = huc.geom.bounds
    x = {
        "type": "Feature",
        "properties": {
            "fld_zone": "X",
            "sfha_tf": "F",
            "zone_subty": "AREA OF MINIMAL FLOOD HAZARD",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
            ],
        },
    }
    ae = {
        "type": "Feature",
        "properties": {"fld_zone": "AE", "sfha_tf": "T", "zone_subty": ""},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-87.35, 41.555],
                    [-87.32, 41.555],
                    [-87.32, 41.570],
                    [-87.35, 41.570],
                    [-87.35, 41.555],
                ]
            ],
        },
    }
    return x, ae


def test_stage_a_injected_firm(tmp_path: Path) -> None:
    huc = load_huc(HUC)
    tmpl = write_synthetic_nlcd(tmp_path / "nlcd.tif", huc)
    x, ae = _features()
    report = run_stage_a(
        huc_path=HUC,
        template_path=tmpl.path,
        interim_dir=tmp_path / "interim",
        out_dir=tmp_path / "out",
        firm_features=[x, ae],
    )
    assert report["stage"] == "A"
    assert report["gate"] == "pass"
    assert report["huc8"] == HUC8
    assert report["template_kind"] == TEMPLATE_KIND_NLCD
    assert report["wbd_live_areasqkm"] == WBD_LIVE_AREASQKM
    assert report["firm_unshaded_x_ok"] is True
    assert report["ofr_2008_covers_this_huc"] is False
    names = {s["name"]: s["zone_class"] for s in report["gate_samples"]}
    assert names["gary_downtown"] == "unshaded_x"
    assert names["gary_little_calumet"] == "sfha"
    assert (tmp_path / "out" / "stage_a_report.json").is_file()
    assert (tmp_path / "interim" / "zone_class.tif").is_file()
    assert (tmp_path / "interim" / "sfha.tif").is_file()


def test_stage_a_refuses_fixture_template(tmp_path: Path) -> None:
    out = tmp_path / "s0"
    run_stage0(huc_path=HUC, out_dir=out)
    with pytest.raises(GateError, match="fixture"):
        run_stage_a(
            huc_path=HUC,
            template_path=out / "template.tif",
            interim_dir=tmp_path / "interim",
            out_dir=tmp_path / "out",
            firm_features=[],
        )


def test_load_huc_requires_indiana_when_states_present(tmp_path: Path) -> None:
    bad = tmp_path / "no_in.geojson"
    bad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4269"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "huc8": HUC8,
                            "states": "IL,MI",
                            "areasqkm": 1903.21,
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-87.5, 41.7],
                                    [-86.8, 41.7],
                                    [-86.8, 41.4],
                                    [-87.5, 41.4],
                                    [-87.5, 41.7],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GateError, match="missing IN"):
        load_huc(bad)


def test_src_has_no_upper_white_hand_or_p_weights() -> None:
    src = Path(__file__).resolve().parents[1] / "src" / "calumetmap"
    names = {p.name for p in src.glob("*.py")}
    assert "calibrate.py" not in names
    blob = "\n".join(p.read_text(encoding="utf-8") for p in src.glob("*.py"))
    assert "p_sfha_calibrated" not in blob
