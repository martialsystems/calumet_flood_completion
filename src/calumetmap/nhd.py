# Copyright (c) 2026 Martial Systems LLC
"""NHD flowlines and waterbodies on the Calumet template.

Flowlines keep StreamRiver (460) and Artificial Path (558). Named rivers
through lakes are often 558. Log ftypes. Distances are Euclidean; HAND is not.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from urllib.parse import quote

import numpy as np
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape

from calumetmap.align import require_live_template
from calumetmap.config import (
    NHD_AREA_URL,
    NHD_AREA_WHERE,
    NHD_FLOWLINE_URL,
    NHD_FLOWLINE_WHERE,
    NHD_PAGE_SIZE,
    NHD_WATERBODY_URL,
    TEMPLATE_CRS,
    VECTOR_CRS,
)
from calumetmap.errors import FetchError, GateError
from calumetmap.fetch import GetJson, default_post_json
from calumetmap.huc import HucLayer
from calumetmap.template import TemplateGrid


def _esri_polygon(geom) -> dict:
    simple = geom.simplify(0.005, preserve_topology=True)
    if simple.geom_type == "MultiPolygon":
        rings = [list(p.exterior.coords) for p in simple.geoms]
    else:
        rings = [list(simple.exterior.coords)]
    return {"rings": rings, "spatialReference": {"wkid": VECTOR_CRS}}


def _ftype(feat: dict) -> str:
    props = feat.get("properties") or feat.get("attributes") or {}
    for key in ("ftype", "FTYPE", "fcode", "FCODE"):
        if key in props and props[key] not in (None, ""):
            if key.lower() == "ftype" or key == "FTYPE":
                return str(props[key])
    return str(props.get("ftype") or props.get("FTYPE") or "")


def ftype_counts(features: list) -> dict[str, int]:
    return dict(Counter(_ftype(f) for f in features))


def nhd_flowline_query_url(*, xmin: float, ymin: float, xmax: float, ymax: float, offset: int) -> str:
    geom = "{0},{1},{2},{3}".format(xmin, ymin, xmax, ymax)
    return (
        "{0}/query?where={1}&geometry={2}&geometryType=esriGeometryEnvelope"
        "&inSR={3}&outSR={3}&spatialRel=esriSpatialRelIntersects"
        "&returnGeometry=true&outFields=objectid,ftype,fcode,gnis_name"
        "&resultOffset={4}&resultRecordCount={5}&f=geojson"
    ).format(
        NHD_FLOWLINE_URL,
        quote(NHD_FLOWLINE_WHERE),
        quote(geom),
        VECTOR_CRS,
        offset,
        NHD_PAGE_SIZE,
    )


def _post_pages(
    *,
    layer_url: str,
    where: str,
    huc: HucLayer,
    post_json,
    out_fields: str,
    empty_ok: bool,
    pause_s: float,
) -> list:
    features: list = []
    offset = 0
    geom = json.dumps(_esri_polygon(huc.geom))
    for _ in range(80):
        page = post_json(
            "{0}/query".format(layer_url),
            {
                "where": where,
                "geometry": geom,
                "geometryType": "esriGeometryPolygon",
                "inSR": str(VECTOR_CRS),
                "outSR": str(VECTOR_CRS),
                "spatialRel": "esriSpatialRelIntersects",
                "returnGeometry": "true",
                "outFields": out_fields,
                "resultOffset": str(offset),
                "resultRecordCount": str(NHD_PAGE_SIZE),
                "f": "geojson",
            },
        )
        if page.get("error"):
            raise FetchError("NHD query error: {0}".format(page["error"]))
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
        raise GateError("NHD pagination exceeded 80 pages")
    if not features and not empty_ok:
        raise GateError("NHD query returned no features: {0}".format(where))
    return features


def fetch_flowlines(
    huc: HucLayer,
    get_json: GetJson | None = None,
    *,
    post_json=None,
    pause_s: float = 0.05,
) -> list:
    if "460" not in NHD_FLOWLINE_WHERE or "558" not in NHD_FLOWLINE_WHERE:
        raise GateError("NHD flowline where must keep ftype 460 and 558")
    if get_json is not None:
        minx, miny, maxx, maxy = huc.geom.bounds
        page = get_json(
            nhd_flowline_query_url(xmin=minx, ymin=miny, xmax=maxx, ymax=maxy, offset=0)
        )
        batch = page.get("features") or []
        if not batch:
            raise GateError("NHD query returned no flowlines")
        return batch
    poster = post_json or default_post_json
    return _post_pages(
        layer_url=NHD_FLOWLINE_URL,
        where=NHD_FLOWLINE_WHERE,
        huc=huc,
        post_json=poster,
        out_fields="objectid,ftype,fcode,gnis_name",
        empty_ok=False,
        pause_s=pause_s,
    )


def fetch_nhd_polygons(
    huc: HucLayer,
    layer_url: str,
    *,
    where: str,
    get_json: GetJson | None = None,
    post_json=None,
    pause_s: float = 0.05,
    out_fields: str = "objectid,ftype,fcode,gnis_name",
    empty_ok: bool = False,
) -> list:
    if get_json is not None:
        minx, miny, maxx, maxy = huc.geom.bounds
        geom = "{0},{1},{2},{3}".format(minx, miny, maxx, maxy)
        page = get_json(
            "{0}/query?where={1}&geometry={2}&geometryType=esriGeometryEnvelope"
            "&inSR={3}&outSR={3}&spatialRel=esriSpatialRelIntersects"
            "&returnGeometry=true&outFields=objectid"
            "&resultOffset=0&resultRecordCount={4}&f=geojson".format(
                layer_url, quote(where), quote(geom), VECTOR_CRS, NHD_PAGE_SIZE
            )
        )
        batch = page.get("features") or []
        if not batch and not empty_ok:
            raise GateError("NHD polygon query returned no features: {0}".format(where))
        return batch
    poster = post_json or default_post_json
    return _post_pages(
        layer_url=layer_url,
        where=where,
        huc=huc,
        post_json=poster,
        out_fields=out_fields,
        empty_ok=empty_ok,
        pause_s=pause_s,
    )


def fetch_waterbodies(huc: HucLayer, get_json: GetJson | None = None, **kwargs) -> list:
    return fetch_nhd_polygons(
        huc, NHD_WATERBODY_URL, where="1=1", get_json=get_json, **kwargs
    )


def fetch_area_streamriver(huc: HucLayer, get_json: GetJson | None = None, **kwargs) -> list:
    return fetch_nhd_polygons(
        huc, NHD_AREA_URL, where=NHD_AREA_WHERE, get_json=get_json, empty_ok=True, **kwargs
    )


def features_to_mask(features: list, template: TemplateGrid) -> np.ndarray:
    require_live_template(template)
    shapes = []
    for feat in features:
        geom_doc = feat.get("geometry")
        if not geom_doc:
            continue
        geom = shape(geom_doc)
        if geom.is_empty:
            continue
        g5070 = shape(
            transform_geom(
                CRS.from_epsg(VECTOR_CRS),
                CRS.from_epsg(TEMPLATE_CRS),
                mapping(geom),
            )
        )
        shapes.append((mapping(g5070), 1))
    mask = np.zeros((template.height, template.width), dtype=np.uint8)
    if not shapes:
        return mask
    return rasterize(
        shapes,
        out_shape=(template.height, template.width),
        transform=template.transform,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
