# Copyright (c) 2026 Martial Systems LLC
"""WBD HUC-8 fetch. Empty features stop."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from calumetmap.config import (
    HUC8,
    USER_AGENT,
    VECTOR_CRS,
    WBD_GEOMETRY_PRECISION,
    WBD_LAYER_URL,
    WBD_MAX_ALLOWABLE_OFFSET_DEG,
)
from calumetmap.errors import EmptyHucError, FetchError

GetJson = Callable[[str], dict[str, Any]]


def default_get_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=90) as resp:
        body = resp.read()
    if not body:
        raise FetchError("empty GET {0}".format(url))
    return json.loads(body.decode("utf-8"))


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
