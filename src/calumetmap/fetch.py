# Copyright (c) 2026 Martial Systems LLC
"""WBD HUC-8 fetch and MRLC NLCD 2021 WMS. Empty features stop."""

from __future__ import annotations

import json
import math
import time
from http.client import IncompleteRead
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from calumetmap.config import (
    HUC8,
    NLCD_LAYER,
    NLCD_TILE_PX,
    NLCD_WMS_URL,
    NLCD_WMS_VERSION,
    TEMPLATE_CRS,
    TEMPLATE_RES_M,
    USER_AGENT,
    VECTOR_CRS,
    WBD_GEOMETRY_PRECISION,
    WBD_LAYER_URL,
    WBD_MAX_ALLOWABLE_OFFSET_DEG,
)
from calumetmap.errors import EmptyHucError, FetchError, GateError

GetJson = Callable[[str], dict[str, Any]]
GetBytes = Callable[[str], bytes]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, IncompleteRead):
        return True
    if isinstance(exc, HTTPError):
        return int(getattr(exc, "code", 0) or 0) >= 500
    return isinstance(exc, (URLError, TimeoutError, ConnectionResetError, ConnectionError))


def _request(url: str, *, timeout: int, attempts: int = 6) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last: BaseException | None = None
    for i in range(attempts):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionResetError,
            ConnectionError,
            IncompleteRead,
        ) as exc:
            last = exc
            if not _is_retryable(exc) or i == attempts - 1:
                raise FetchError("GET failed: {0}: {1}".format(url, exc)) from exc
            time.sleep(min(2 ** i, 16))
    raise FetchError("GET failed: {0}: {1}".format(url, last)) from last


def default_get_json(url: str, *, timeout: int = 90) -> dict[str, Any]:
    raw = _request(url, timeout=timeout)
    if not raw:
        raise FetchError("empty GET {0}".format(url))
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError("not JSON: {0}".format(url)) from exc
    if not isinstance(doc, dict):
        raise FetchError("JSON object required: {0}".format(url))
    return doc


def default_get_bytes(url: str, *, timeout: int = 120) -> bytes:
    return _request(url, timeout=timeout)


def default_post_json(
    url: str,
    fields: dict[str, str],
    *,
    timeout: int = 180,
    attempts: int = 6,
) -> dict[str, Any]:
    body = urlencode(fields).encode("utf-8")
    last: BaseException | None = None
    raw = b""
    for i in range(attempts):
        req = Request(
            url,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            break
        except (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionResetError,
            ConnectionError,
            IncompleteRead,
        ) as exc:
            last = exc
            if not _is_retryable(exc) or i == attempts - 1:
                raise FetchError("POST failed: {0}: {1}".format(url, exc)) from exc
            time.sleep(min(2 ** i, 16))
    else:
        raise FetchError("POST failed: {0}: {1}".format(url, last)) from last
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError("POST not JSON: {0}".format(url)) from exc
    if not isinstance(doc, dict):
        raise FetchError("POST JSON object required: {0}".format(url))
    return doc


def layer_wkid(meta: dict[str, Any]) -> int | None:
    extent = meta.get("extent") or {}
    sr = (
        extent.get("spatialReference")
        or meta.get("sourceSpatialReference")
        or meta.get("spatialReference")
        or {}
    )
    wkid = sr.get("latestWkid") or sr.get("wkid")
    try:
        return int(wkid) if wkid is not None else None
    except (TypeError, ValueError):
        return None


def wbd_query_url(*, huc8: str = HUC8, out_sr: int = VECTOR_CRS) -> str:
    where = "huc8='{0}'".format(huc8)
    return (
        "{0}/query?where={1}&outFields=huc8,name,states,areasqkm"
        "&returnGeometry=true&outSR={2}&maxAllowableOffset={3}"
        "&geometryPrecision={4}&f=geojson"
    ).format(
        WBD_LAYER_URL,
        quote(where),
        out_sr,
        WBD_MAX_ALLOWABLE_OFFSET_DEG,
        WBD_GEOMETRY_PRECISION,
    )


def fetch_wbd_doc(get_json: GetJson, *, huc8: str = HUC8) -> tuple[int, dict[str, Any]]:
    meta = get_json("{0}?f=pjson".format(WBD_LAYER_URL))
    if meta.get("error"):
        raise FetchError("WBD layer error: {0}".format(meta["error"]))
    doc = get_json(wbd_query_url(huc8=huc8))
    if doc.get("error"):
        raise FetchError("WBD query error: {0}".format(doc["error"]))
    features = doc.get("features") or []
    if not features:
        raise EmptyHucError("WBD query returned no features for {0}".format(huc8))
    props = features[0].get("properties") or {}
    got = str(props.get("huc8") or props.get("HUC8") or "")
    if got != huc8:
        raise EmptyHucError("WBD huc8={0!r} != {1!r}".format(got, huc8))
    doc.setdefault(
        "crs",
        {"type": "name", "properties": {"name": "EPSG:{0}".format(VECTOR_CRS), "wkid": VECTOR_CRS}},
    )
    return VECTOR_CRS, doc


def fetch_wbd(raw_dir, *, get_json: GetJson | None = None, huc8: str = HUC8):
    from pathlib import Path

    getter = get_json or default_get_json
    wkid, doc = fetch_wbd_doc(getter, huc8=huc8)
    dest = Path(raw_dir) / "huc{0}.geojson".format(huc8)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc), encoding="utf-8")
    return dest


def snap_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    *,
    res: float = TEMPLATE_RES_M,
    pad_px: int = 1,
) -> tuple[float, float, float, float, int, int]:
    west = math.floor(minx / res) * res - pad_px * res
    south = math.floor(miny / res) * res - pad_px * res
    east = math.ceil(maxx / res) * res + pad_px * res
    north = math.ceil(maxy / res) * res + pad_px * res
    width = int(round((east - west) / res))
    height = int(round((north - south) / res))
    if width < 2 or height < 2:
        raise GateError("snapped NLCD window too small: {0}x{1}".format(width, height))
    return west, south, east, north, width, height


def iter_tiles(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    res: float = TEMPLATE_RES_M,
    tile_px: int = NLCD_TILE_PX,
) -> Iterable[tuple[float, float, float, float, int, int]]:
    width = int(round((east - west) / res))
    height = int(round((north - south) / res))
    for row0 in range(0, height, tile_px):
        h = min(tile_px, height - row0)
        for col0 in range(0, width, tile_px):
            w = min(tile_px, width - col0)
            tw = west + col0 * res
            tn = north - row0 * res
            te = tw + w * res
            ts = tn - h * res
            yield tw, ts, te, tn, w, h


def nlcd_wms_url(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    width: int,
    height: int,
    layer: str = NLCD_LAYER,
    crs: int = TEMPLATE_CRS,
) -> str:
    params = {
        "SERVICE": "WMS",
        "VERSION": NLCD_WMS_VERSION,
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "CRS": "EPSG:{0}".format(crs),
        "BBOX": "{0},{1},{2},{3}".format(west, south, east, north),
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/geotiff",
        "STYLES": "",
    }
    return "{0}?{1}".format(NLCD_WMS_URL, urlencode(params))


def _require_geotiff(payload: bytes, *, url: str) -> bytes:
    if payload[:4] in (b"II*\x00", b"MM\x00*") or payload[:4] == b"\x49\x49\x2a\x00":
        return payload
    head = payload[:200].lstrip()
    if head.startswith(b"<") or b"ServiceException" in payload[:400]:
        raise FetchError("NLCD WMS exception: {0}: {1!r}".format(url, payload[:300]))
    raise FetchError("NLCD WMS did not return GeoTIFF: {0}".format(url))


def fetch_nlcd_tile_bytes(
    get_bytes: GetBytes,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    width: int,
    height: int,
) -> bytes:
    url = nlcd_wms_url(
        west=west, south=south, east=east, north=north, width=width, height=height
    )
    return _require_geotiff(get_bytes(url), url=url)
