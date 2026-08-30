# Copyright (c) 2026 Martial Systems LLC
"""FEMA NFHL S_FLD_HAZ_AR: sfha band and zone_class on the live template.

Fetch is unfiltered (where=1=1) and clipped to this HUC. Unshaded X is
Zone X. Gate samples are Gary/Hammond and Crown Point, not Monument Circle.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.warp import transform as rio_transform
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape

from calumetmap.align import interior_mask, require_live_template, write_aligned
from calumetmap.codes import (
    ZONE_CLASS_NAME,
    ZONE_D,
    ZONE_FLOODWAY,
    ZONE_OTHER,
    ZONE_SFHA,
    ZONE_SHADED_X,
    ZONE_UNMAPPED,
    ZONE_UNSHADED_X,
    classify_firm_zone,
)
from calumetmap.config import (
    FIRM_EXPECTED_CRS,
    FIRM_GATE_SAMPLES,
    FIRM_GEOMETRY_PRECISION,
    FIRM_LAYER_URL,
    FIRM_LIVE_MIN_HEIGHT,
    FIRM_LIVE_MIN_WIDTH,
    FIRM_MAX_ALLOWABLE_OFFSET_DEG,
    FIRM_OUT_FIELDS,
    FIRM_PAGE_SIZE,
    FIRM_SOURCE,
    FIRM_WHERE,
    TEMPLATE_CRS,
    VECTOR_CRS,
)
from calumetmap.errors import CrsMissingError, FetchError, GateError
from calumetmap.fetch import GetJson, default_post_json, layer_wkid
from calumetmap.huc import HucLayer
from calumetmap.template import TemplateGrid

_PAINT_ORDER = (
    ZONE_UNMAPPED,
    ZONE_OTHER,
    ZONE_D,
    ZONE_UNSHADED_X,
    ZONE_SHADED_X,
    ZONE_SFHA,
    ZONE_FLOODWAY,
)
_PARENT_CIRCLE = (-86.1581, 39.7684)


def firm_attr(props: dict[str, Any] | None, key: str) -> object:
    if not props:
        return ""
    if key in props:
        return props[key]
    lower = {str(k).lower(): v for k, v in props.items()}
    return lower.get(key.lower(), "")


def refuse_parent_gate_samples(samples: tuple = FIRM_GATE_SAMPLES) -> None:
    for name, lon, lat, _expected in samples:
        if "monument" in str(name).lower():
            raise GateError("Monument Circle is not a Calumet gate sample")
        if abs(float(lon) - _PARENT_CIRCLE[0]) < 0.05 and abs(float(lat) - _PARENT_CIRCLE[1]) < 0.05:
            raise GateError("Upper White coordinates are not Calumet gate samples")


def require_gate_sample_mix(samples: tuple = FIRM_GATE_SAMPLES) -> None:
    classes = {row[3] for row in samples}
    if "unshaded_x" not in classes:
        raise GateError("FIRM gate samples need an unshaded_x cell in this basin")
    if "sfha" not in classes and "floodway" not in classes:
        raise GateError("FIRM gate samples need an SFHA cell in this basin")


def firm_query_url(*, offset: int, page_size: int = FIRM_PAGE_SIZE) -> str:
    if FIRM_WHERE.upper() != "1=1":
        raise GateError("FIRM where must be 1=1, got {0!r}".format(FIRM_WHERE))
    return (
        "{0}/query?where={1}&outFields={2}&orderByFields=OBJECTID"
        "&resultOffset={3}&resultRecordCount={4}"
        "&maxAllowableOffset={5}&geometryPrecision={6}"
        "&returnGeometry=true&outSR={7}&f=geojson"
    ).format(
        FIRM_LAYER_URL,
        quote(FIRM_WHERE),
        quote(FIRM_OUT_FIELDS),
        offset,
        page_size,
        FIRM_MAX_ALLOWABLE_OFFSET_DEG,
        FIRM_GEOMETRY_PRECISION,
        VECTOR_CRS,
    )


def assert_no_zone_filter(url: str) -> None:
    parsed = urlparse(url)
    where = (parse_qs(parsed.query).get("where") or ["1=1"])[0].upper().replace(" ", "")
    if "FLD_ZONE" in where or "SFHA_TF" in where:
        raise GateError("FIRM where filters zones: {0}".format(where))
    if where not in {"1=1", "1%3D1"}:
        raise GateError("FIRM where must be 1=1, got {0}".format(where))


def is_full_huc_template(template: TemplateGrid) -> bool:
    return template.width >= FIRM_LIVE_MIN_WIDTH and template.height >= FIRM_LIVE_MIN_HEIGHT


def _huc_envelope_tiles(
    huc: HucLayer, step: float = 0.25
) -> list[tuple[float, float, float, float]]:
    minx, miny, maxx, maxy = huc.geom.bounds
    tiles: list[tuple[float, float, float, float]] = []
    x = minx
    while x < maxx:
        x2 = min(x + step, maxx)
        y = miny
        while y < maxy:
            y2 = min(y + step, maxy)
            tiles.append((x, y, x2, y2))
            y = y2
        x = x2
    if not tiles:
        raise GateError("HUC envelope produced no FIRM tiles")
    return tiles


def firm_envelope_query_url(
    *,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    offset: int,
    page_size: int = FIRM_PAGE_SIZE,
) -> str:
    if FIRM_WHERE.upper() != "1=1":
        raise GateError("FIRM where must be 1=1, got {0!r}".format(FIRM_WHERE))
    geom = "{0},{1},{2},{3}".format(xmin, ymin, xmax, ymax)
    url = (
        "{0}/query?where={1}&geometry={2}&geometryType=esriGeometryEnvelope"
        "&inSR={3}&outSR={3}&spatialRel=esriSpatialRelIntersects"
        "&outFields={4}&orderByFields=OBJECTID&resultOffset={5}"
        "&resultRecordCount={6}&maxAllowableOffset={7}&geometryPrecision={8}"
        "&returnGeometry=true&f=geojson"
    ).format(
        FIRM_LAYER_URL,
        quote(FIRM_WHERE),
        quote(geom),
        VECTOR_CRS,
        quote(FIRM_OUT_FIELDS),
        offset,
        page_size,
        FIRM_MAX_ALLOWABLE_OFFSET_DEG,
        FIRM_GEOMETRY_PRECISION,
    )
    assert_no_zone_filter(url)
    return url


def _post_retry(poster, url: str, fields: dict[str, str], *, attempts: int = 3) -> dict:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return poster(url, fields)
        except FetchError as exc:
            last = exc
            time.sleep(min(2 ** i, 16))
    raise FetchError("FIRM POST failed after {0} attempts: {1}".format(attempts, last)) from last


def _page_exceeded(page: dict[str, Any]) -> bool:
    return bool(
        (page.get("properties") or {}).get("exceededTransferLimit")
        or page.get("exceededTransferLimit")
    )


def _feature_oid(feat: dict[str, Any]) -> object:
    props = feat.get("properties") or feat.get("attributes") or {}
    oid = firm_attr(props, "objectid")
    if oid in ("", None):
        return None
    return oid


def fetch_firm_pages(
    get_json: GetJson,
    *,
    huc: HucLayer | None = None,
    post_json=None,
    page_size: int = FIRM_PAGE_SIZE,
    pause_s: float = 0.1,
) -> tuple[int, list[dict[str, Any]]]:
    meta = get_json("{0}?f=pjson".format(FIRM_LAYER_URL))
    wkid = layer_wkid(meta)
    if wkid is None:
        raise CrsMissingError("FIRM MapServer has no spatialReference")
    if int(wkid) != FIRM_EXPECTED_CRS:
        raise GateError("FIRM wkid {0} != {1}".format(wkid, FIRM_EXPECTED_CRS))
    if huc is None:
        return wkid, _fetch_firm_get(get_json, page_size=page_size, pause_s=pause_s)
    poster = post_json or (
        lambda url, fields: default_post_json(url, fields, timeout=180)
    )
    features: list[dict[str, Any]] = []
    seen: set[object] = set()
    tiles = _huc_envelope_tiles(huc)
    live = post_json is None
    for tile_i, (xmin, ymin, xmax, ymax) in enumerate(tiles, start=1):
        offset = 0
        for _ in range(80):
            fields = {
                "where": FIRM_WHERE,
                "geometry": "{0},{1},{2},{3}".format(xmin, ymin, xmax, ymax),
                "geometryType": "esriGeometryEnvelope",
                "inSR": str(VECTOR_CRS),
                "outSR": str(VECTOR_CRS),
                "spatialRel": "esriSpatialRelIntersects",
                "returnGeometry": "true",
                "outFields": FIRM_OUT_FIELDS,
                "orderByFields": "OBJECTID",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
                "maxAllowableOffset": str(FIRM_MAX_ALLOWABLE_OFFSET_DEG),
                "geometryPrecision": str(FIRM_GEOMETRY_PRECISION),
                "f": "geojson",
            }
            try:
                page = _post_retry(poster, "{0}/query".format(FIRM_LAYER_URL), fields)
            except FetchError:
                get_url = firm_envelope_query_url(
                    xmin=xmin,
                    ymin=ymin,
                    xmax=xmax,
                    ymax=ymax,
                    offset=offset,
                    page_size=page_size,
                )
                page = None
                last_get: Exception | None = None
                for i in range(4):
                    try:
                        page = get_json(get_url)
                        last_get = None
                        break
                    except FetchError as exc:
                        last_get = exc
                        time.sleep(min(2 ** i, 16))
                if page is None:
                    raise FetchError("FIRM GET fallback failed: {0}".format(last_get)) from last_get
            if page.get("error"):
                raise FetchError("FIRM query error: {0}".format(page["error"]))
            batch = page.get("features") or []
            if not batch:
                break
            for feat in batch:
                oid = _feature_oid(feat)
                if oid is not None and oid in seen:
                    continue
                if oid is not None:
                    seen.add(oid)
                features.append(feat)
            if not _page_exceeded(page):
                break
            offset += len(batch)
            if pause_s:
                time.sleep(pause_s)
        else:
            raise GateError("FIRM pagination exceeded 80 pages on a tile")
        if live:
            print(
                "FIRM tile {0}/{1} features={2}".format(tile_i, len(tiles), len(features)),
                flush=True,
            )
    if not features:
        raise GateError("FIRM query returned no features")
    return wkid, features


def _fetch_firm_get(
    get_json: GetJson,
    *,
    page_size: int,
    pause_s: float,
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    offset = 0
    for _ in range(200):
        url = firm_query_url(offset=offset, page_size=page_size)
        assert_no_zone_filter(url)
        page = get_json(url)
        if page.get("error"):
            raise FetchError("FIRM query error: {0}".format(page["error"]))
        batch = page.get("features") or []
        if not batch:
            break
        features.extend(batch)
        exceeded = bool(
            (page.get("properties") or {}).get("exceededTransferLimit")
            or page.get("exceededTransferLimit")
        )
        if not exceeded:
            break
        offset += len(batch)
        if pause_s:
            time.sleep(pause_s)
    else:
        raise GateError("FIRM pagination exceeded 200 pages")
    if not features:
        raise GateError("FIRM query returned no features")
    return features


def _zone_counts(interior_zone: np.ndarray) -> dict[str, int]:
    return {
        ZONE_CLASS_NAME[int(k)]: int((interior_zone == k).sum())
        for k in sorted(np.unique(interior_zone))
        if int(k) in ZONE_CLASS_NAME
    }


def require_unshaded_majority(counts: dict[str, int]) -> None:
    ux = int(counts.get("unshaded_x") or 0)
    sf = int(counts.get("sfha") or 0)
    if ux <= sf:
        raise GateError(
            "unshaded_x={0} is not greater than sfha={1}; NFHL Zone X polygons missing".format(
                ux, sf
            )
        )


def sample_firm_gate_cells(template: TemplateGrid, zone_path: Path) -> list[dict[str, Any]]:
    require_live_template(template)
    refuse_parent_gate_samples()
    require_gate_sample_mix()
    samples: list[dict[str, Any]] = []
    with rasterio.open(zone_path) as src:
        arr = src.read(1)
        for name, lon, lat, expected in FIRM_GATE_SAMPLES:
            xs, ys = rio_transform(
                CRS.from_epsg(VECTOR_CRS),
                CRS.from_epsg(TEMPLATE_CRS),
                [lon],
                [lat],
            )
            row, col = src.index(xs[0], ys[0])
            if not (0 <= row < src.height and 0 <= col < src.width):
                raise GateError(
                    "FIRM gate sample {0} maps outside the template (row={1} col={2})".format(
                        name, row, col
                    )
                )
            code = int(arr[row, col])
            got = ZONE_CLASS_NAME.get(code, "code_{0}".format(code))
            samples.append(
                {
                    "name": name,
                    "lon": lon,
                    "lat": lat,
                    "row": int(row),
                    "col": int(col),
                    "zone_class": got,
                    "expected": expected,
                }
            )
    return samples


def require_firm_gate_samples(samples: list[dict[str, Any]]) -> None:
    bad = [s["name"] for s in samples if s.get("zone_class") != s.get("expected")]
    if bad:
        detail = ", ".join(
            "{0} got {1} expected {2}".format(
                s["name"], s.get("zone_class"), s.get("expected")
            )
            for s in samples
            if s["name"] in bad
        )
        raise GateError("FIRM gate samples mismatch: {0}".format(detail))


def _require_floodway_in_sfha(interior_zone: np.ndarray, interior_sfha: np.ndarray) -> None:
    floodway = interior_zone == ZONE_FLOODWAY
    if floodway.any() and not bool(np.all(interior_sfha[floodway] == 1)):
        raise GateError("floodway cells missing from sfha==1")


def summarize_firm_rasters(template: TemplateGrid, sfha_path: Path, zone_path: Path) -> dict:
    require_live_template(template)
    inside = interior_mask(template)
    with rasterio.open(sfha_path) as src:
        sfha = src.read(1)
    with rasterio.open(zone_path) as src:
        zone = src.read(1)
    interior_sfha = sfha[inside]
    interior_zone = zone[inside]
    _require_floodway_in_sfha(interior_zone, interior_sfha)
    counts = _zone_counts(interior_zone)
    out: dict[str, Any] = {
        "sfha_counts": {
            "0": int((interior_sfha == 0).sum()),
            "1": int((interior_sfha == 1).sum()),
        },
        "zone_class_counts": counts,
        "sfha_has_0_and_1": bool(0 in interior_sfha and 1 in interior_sfha),
        "from_existing_rasters": True,
        "firm_source": FIRM_SOURCE,
        "firm_where": FIRM_WHERE,
    }
    if is_full_huc_template(template):
        samples = sample_firm_gate_cells(template, zone_path)
        require_firm_gate_samples(samples)
        require_unshaded_majority(counts)
        out["gate_samples"] = samples
        out["firm_unshaded_x_ok"] = True
    else:
        out["firm_unshaded_x_ok"] = int(counts.get("unshaded_x") or 0) > 0
    return out


def rasterize_firm(
    features: list[dict[str, Any]],
    template: TemplateGrid,
    *,
    sfha_dest: Path,
    zone_dest: Path,
) -> dict:
    require_live_template(template)
    buckets: dict[int, list] = {code: [] for code in _PAINT_ORDER}
    n_empty = 0
    for feat in features:
        props = feat.get("properties") or feat.get("attributes") or {}
        geom_doc = feat.get("geometry")
        if not geom_doc:
            n_empty += 1
            continue
        geom = shape(geom_doc)
        if geom.is_empty:
            n_empty += 1
            continue
        geom5070 = shape(
            transform_geom(
                CRS.from_epsg(VECTOR_CRS),
                CRS.from_epsg(TEMPLATE_CRS),
                mapping(geom),
            )
        )
        code, _name = classify_firm_zone(
            firm_attr(props, "fld_zone"),
            firm_attr(props, "zone_subty"),
            firm_attr(props, "sfha_tf"),
        )
        buckets[code].append((mapping(geom5070), code))
    zone = np.full((template.height, template.width), ZONE_UNMAPPED, dtype=np.uint8)
    for code in _PAINT_ORDER:
        shapes = buckets[code]
        if not shapes:
            continue
        painted = rasterize(
            shapes,
            out_shape=(template.height, template.width),
            transform=template.transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        )
        zone = np.where(painted == code, painted, zone).astype(np.uint8)
    inside = interior_mask(template)
    sfha = np.where(
        np.isin(zone, (ZONE_SFHA, ZONE_FLOODWAY)),
        1,
        0,
    ).astype(np.uint8)
    zone = np.where(inside, zone, 255).astype(np.uint8)
    sfha = np.where(inside, sfha, 255).astype(np.uint8)
    interior_sfha = sfha[inside]
    interior_zone = zone[inside]
    if not (0 in interior_sfha and 1 in interior_sfha):
        raise GateError("sfha band missing 0 or 1 inside the HUC")
    _require_floodway_in_sfha(interior_zone, interior_sfha)
    write_aligned(sfha_dest, template, sfha, dtype="uint8", nodata=255)
    write_aligned(zone_dest, template, zone, dtype="uint8", nodata=255)
    counts = _zone_counts(interior_zone)
    out: dict[str, Any] = {
        "n_firm_features": len(features),
        "n_empty_geom": n_empty,
        "sfha_counts": {
            "0": int((interior_sfha == 0).sum()),
            "1": int((interior_sfha == 1).sum()),
        },
        "zone_class_counts": counts,
        "sfha_has_0_and_1": True,
        "firm_source": FIRM_SOURCE,
        "firm_where": FIRM_WHERE,
    }
    if is_full_huc_template(template):
        samples = sample_firm_gate_cells(template, zone_dest)
        require_firm_gate_samples(samples)
        require_unshaded_majority(counts)
        out["gate_samples"] = samples
        out["firm_unshaded_x_ok"] = True
    else:
        out["firm_unshaded_x_ok"] = int(counts.get("unshaded_x") or 0) > 0
    return out
