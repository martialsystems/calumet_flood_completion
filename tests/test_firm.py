# Copyright (c) 2026 Martial Systems LLC

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio

from calumetmap.codes import ZONE_FLOODWAY, ZONE_SFHA, ZONE_UNSHADED_X
from calumetmap.config import FIRM_GATE_SAMPLES, FIRM_LAYER_URL, FIRM_WHERE
from calumetmap.errors import GateError
from calumetmap.firm import (
    assert_no_zone_filter,
    fetch_firm_pages,
    firm_attr,
    firm_envelope_query_url,
    firm_query_url,
    rasterize_firm,
    refuse_parent_gate_samples,
    require_gate_sample_mix,
    require_unshaded_majority,
)
from calumetmap.huc import load_huc
from calumetmap.template import write_synthetic_nlcd

HUC = Path(__file__).resolve().parent / "fixtures" / "huc.geojson"


def _huc_x_and_gary_ae():
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
    return huc, x, ae


def test_gate_samples_are_this_basin() -> None:
    names = [row[0] for row in FIRM_GATE_SAMPLES]
    classes = {row[3] for row in FIRM_GATE_SAMPLES}
    assert "gary_downtown" in names
    assert "gary_little_calumet" in names
    assert "unshaded_x" in classes
    assert "sfha" in classes
    refuse_parent_gate_samples()
    require_gate_sample_mix()
    with pytest.raises(GateError, match="Monument"):
        refuse_parent_gate_samples(
            (("monument_circle", -86.1581, 39.7684, "unshaded_x"),)
        )


def test_firm_zone_class_not_just_sfha(tmp_path: Path) -> None:
    huc, x, ae = _huc_x_and_gary_ae()
    tmpl = write_synthetic_nlcd(tmp_path / "nlcd.tif", huc)
    info = rasterize_firm(
        [ae, x],
        tmpl,
        sfha_dest=tmp_path / "sfha.tif",
        zone_dest=tmp_path / "zone.tif",
    )
    assert info["sfha_has_0_and_1"]
    assert info["sfha_counts"]["0"] > 0
    assert info["sfha_counts"]["1"] > 0
    assert info["zone_class_counts"].get("unshaded_x", 0) > 0
    assert info["zone_class_counts"].get("sfha", 0) > 0
    with rasterio.open(tmp_path / "zone.tif") as src:
        z = src.read(1)
    assert ZONE_UNSHADED_X in z
    assert ZONE_SFHA in z


def test_firm_query_is_nfhl_unfiltered() -> None:
    assert "NFHL/MapServer/28" in FIRM_LAYER_URL
    assert FIRM_WHERE == "1=1"
    url = firm_query_url(offset=0)
    q = parse_qs(urlparse(url).query)
    assert q["where"] == ["1=1"]
    assert_no_zone_filter(url)
    with pytest.raises(GateError, match="filters zones"):
        assert_no_zone_filter(
            FIRM_LAYER_URL + "/query?where=FLD_ZONE%3D%27AE%27&f=geojson"
        )


def test_firm_attr_case_insensitive() -> None:
    assert firm_attr({"FLD_ZONE": "X", "ZONE_SUBTY": ""}, "fld_zone") == "X"
    assert firm_attr({"fld_zone": "AE"}, "FLD_ZONE") == "AE"


def test_firm_floodway_cells_are_sfha(tmp_path: Path) -> None:
    huc, x, ae = _huc_x_and_gary_ae()
    tmpl = write_synthetic_nlcd(tmp_path / "nlcd.tif", huc)
    floodway = {
        "type": "Feature",
        "properties": {
            "FLD_ZONE": "AE",
            "SFHA_TF": "T",
            "ZONE_SUBTY": "FLOODWAY",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-87.35, 41.555],
                    [-87.345, 41.555],
                    [-87.345, 41.558],
                    [-87.35, 41.558],
                    [-87.35, 41.555],
                ]
            ],
        },
    }
    info = rasterize_firm(
        [ae, floodway, x],
        tmpl,
        sfha_dest=tmp_path / "sfha.tif",
        zone_dest=tmp_path / "zone.tif",
    )
    assert info["zone_class_counts"].get("floodway", 0) > 0
    with rasterio.open(tmp_path / "zone.tif") as src:
        z = src.read(1)
    with rasterio.open(tmp_path / "sfha.tif") as src:
        s = src.read(1)
    fw = z == ZONE_FLOODWAY
    assert fw.any()
    assert np.all(s[fw] == 1)


def test_empty_subtype_x_is_unshaded(tmp_path: Path) -> None:
    huc, _x, ae = _huc_x_and_gary_ae()
    tmpl = write_synthetic_nlcd(tmp_path / "nlcd.tif", huc)
    minx, miny, maxx, maxy = huc.geom.bounds
    x = {
        "type": "Feature",
        "properties": {"fld_zone": "X", "sfha_tf": "F", "zone_subty": ""},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
            ],
        },
    }
    info = rasterize_firm(
        [ae, x],
        tmpl,
        sfha_dest=tmp_path / "sfha.tif",
        zone_dest=tmp_path / "zone.tif",
    )
    assert info["zone_class_counts"].get("unshaded_x", 0) > 0


def test_require_unshaded_majority() -> None:
    require_unshaded_majority({"unshaded_x": 100, "sfha": 10})
    with pytest.raises(GateError, match="NFHL Zone X"):
        require_unshaded_majority({"unshaded_x": 10, "sfha": 100})


def test_fetch_firm_huc_tiles_unfiltered() -> None:
    huc = load_huc(HUC)
    posts: list[dict] = []

    def get_json(url: str) -> dict:
        if "query" not in url:
            return {"extent": {"spatialReference": {"wkid": 4269, "latestWkid": 4269}}}
        raise AssertionError("GET query not expected: {0}".format(url))

    def post_json(url: str, fields: dict) -> dict:
        posts.append(fields)
        assert fields["where"] == "1=1"
        assert "FLD_ZONE" not in fields["where"]
        assert fields["geometryType"] == "esriGeometryEnvelope"
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {
                        "OBJECTID": 1,
                        "FLD_ZONE": "X",
                        "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD",
                        "SFHA_TF": "F",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    },
                }
            ],
        }

    wkid, feats = fetch_firm_pages(get_json, huc=huc, post_json=post_json, pause_s=0)
    assert wkid == 4269
    assert len(feats) == 1
    assert posts
    env_url = firm_envelope_query_url(
        xmin=-87.5, ymin=41.5, xmax=-87.4, ymax=41.6, offset=0
    )
    assert_no_zone_filter(env_url)


def test_gate_samples_on_full_synthetic_huc(tmp_path: Path) -> None:
    huc, x, ae = _huc_x_and_gary_ae()
    tmpl = write_synthetic_nlcd(tmp_path / "nlcd.tif", huc)
    assert tmpl.width >= 1000
    info = rasterize_firm(
        [x, ae],
        tmpl,
        sfha_dest=tmp_path / "sfha.tif",
        zone_dest=tmp_path / "zone.tif",
    )
    names = {s["name"]: s["zone_class"] for s in info["gate_samples"]}
    assert names["gary_downtown"] == "unshaded_x"
    assert names["gary_little_calumet"] == "sfha"
    assert names["crown_point_tillplain"] == "unshaded_x"
    assert info["firm_unshaded_x_ok"] is True
