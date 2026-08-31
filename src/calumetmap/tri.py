# Copyright (c) 2026 Martial Systems LLC
"""TRI on-site releases clipped to Little Calumet-Galien. IL/IN/MI, not Indy."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Iterable

from shapely.geometry import Point

from calumetmap.config import (
    HUC8,
    INDY_PLANT_NAMES,
    TRI_ENVIROFACTS,
    TRI_STATES,
    TRI_YEAR_CANDIDATES,
)
from calumetmap.errors import FetchError, GateError
from calumetmap.fetch import GetBytes, default_get_bytes
from calumetmap.huc import HucLayer


def _col(row: dict, *needles: str) -> str:
    upper = {str(k).upper().strip(): k for k in row}
    for needle in needles:
        n = needle.upper().strip()
        if n in upper:
            val = row.get(upper[n])
            return "" if val is None else str(val).strip()
    return ""


def _float(text) -> float | None:
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    t = str(text or "").replace(",", "").strip()
    if not t or t.upper() in {"NA", "NONE", "NULL"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def refuse_indy_names(rows: Iterable[dict]) -> None:
    blob = " ".join(str(r.get("name") or "") for r in rows).upper()
    for plant in INDY_PLANT_NAMES:
        if plant.upper() in blob:
            raise GateError("Indy plant name in Calumet TRI: {0}".format(plant))


def parse_tri_1a(text: str, *, year: int) -> tuple[dict[str, dict], dict[str, int]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise GateError("TRI 1a csv has no header")
    by_fac: dict[str, dict] = {}
    n_rows = 0
    n_ok_state = 0
    n_dioxin = 0
    n_off = 0
    n_missing_xy = 0
    n_dropped_state = 0
    allowed = {s.upper() for s in TRI_STATES}
    for row in reader:
        n_rows += 1
        st = _col(row, "5. ST", "ST", "STATE").upper()
        if st and st not in allowed:
            n_dropped_state += 1
            continue
        n_ok_state += 1
        unit = _col(row, "UNIT OF MEASURE", "UNIT").upper()
        chem = _col(row, "CHEMICAL", "CHEMICAL NAME").upper()
        onsite = _float(_col(row, "ON-SITE RELEASE TOTAL", "ONSITE RELEASE TOTAL"))
        offsite = _float(_col(row, "OFF-SITE RELEASE TOTAL", "OFFSITE RELEASE TOTAL"))
        if offsite and offsite != 0.0:
            n_off += 1
        dioxin = "DIOXIN" in chem or unit in {"GRAMS", "G"}
        if dioxin:
            n_dioxin += 1
            lb = 0.0
        else:
            lb = onsite or 0.0
        lat = _float(_col(row, "LATITUDE", "LATITUDE83"))
        lon = _float(_col(row, "LONGITUDE", "LONGITUDE83"))
        if lat is None or lon is None:
            n_missing_xy += 1
            continue
        frs = _col(row, "FRS ID", "FRS_ID", "REGISTRY")
        trifd = _col(row, "TRIFD", "TRIFID", "TRI FACILITY ID")
        key = frs or trifd or "{0:.5f},{1:.5f}".format(lat, lon)
        name = _col(row, "FACILITY NAME", "PRIMARY_NAME")
        rec = by_fac.setdefault(
            key,
            {
                "key": key,
                "frs": frs,
                "trifd": trifd,
                "name": name,
                "lat": lat,
                "lon": lon,
                "state": st,
                "on_site_release_lb": 0.0,
                "n_chem": 0,
                "year": year,
            },
        )
        rec["on_site_release_lb"] += lb
        rec["n_chem"] += 1
    budget = {
        "n_1a_rows": n_rows,
        "n_1a_in_states": n_ok_state,
        "n_dropped_missing_xy": n_missing_xy,
        "n_dropped_other_state": n_dropped_state,
        "n_dioxin_rows_held_grams": n_dioxin,
        "n_excluded_off_site": n_off,
        "reporting_year": year,
        "states": list(TRI_STATES),
    }
    return by_fac, budget


def clip_to_huc(facilities: Iterable[dict], huc: HucLayer) -> tuple[list[dict], int]:
    kept: list[dict] = []
    n_out = 0
    for rec in facilities:
        pt = Point(rec["lon"], rec["lat"])
        if huc.geom.covers(pt) or huc.geom.intersects(pt):
            rec = dict(rec)
            rec["huc"] = huc.huc8
            kept.append(rec)
        else:
            n_out += 1
    refuse_indy_names(kept)
    return kept, n_out


def write_facilities_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "key",
        "frs",
        "trifd",
        "name",
        "lat",
        "lon",
        "state",
        "huc",
        "year",
        "on_site_release_lb",
        "n_chem",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def load_tri_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise GateError("TRI in-HUC csv missing: {0}".format(path))
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise GateError("TRI in-HUC csv is empty")
    out = []
    for rec in rows:
        out.append(
            {
                "key": rec.get("key") or "",
                "frs": rec.get("frs") or "",
                "trifd": rec.get("trifd") or "",
                "name": rec.get("name") or "",
                "lat": float(rec["lat"]),
                "lon": float(rec["lon"]),
                "state": rec.get("state") or "",
                "huc": rec.get("huc") or HUC8,
                "year": int(float(rec.get("year") or 0)),
                "on_site_release_lb": float(rec.get("on_site_release_lb") or 0.0),
                "n_chem": int(float(rec.get("n_chem") or 0)),
            }
        )
    refuse_indy_names(out)
    return out


def fetch_tri_envirofacts(
    *,
    year: int,
    get_bytes: GetBytes | None = None,
    page: int = 10000,
) -> list[dict]:
    getter = get_bytes or default_get_bytes
    rows: list[dict] = []
    for st in TRI_STATES:
        if get_bytes is None:
            print("TRI Envirofacts {0} {1}".format(st, year), flush=True)
        start = 1
        for _ in range(20):
            url = (
                "{0}/YEAR/{1}/ST/{2}/ROWS/{3}:{4}/JSON".format(
                    TRI_ENVIROFACTS, year, st, start, start + page - 1
                )
            )
            payload = getter(url)
            try:
                doc = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FetchError("TRI Envirofacts not JSON for {0} {1}".format(st, year)) from exc
            if not isinstance(doc, list) or not doc:
                break
            rows.extend(doc)
            if len(doc) < page:
                break
            start += page
    if not rows:
        raise GateError("TRI Envirofacts empty for {0} {1}".format(year, TRI_STATES))
    return rows


def parse_tri_json(rows: list[dict], *, year: int) -> tuple[dict[str, dict], dict[str, int]]:
    as_str = [{str(k): v for k, v in rec.items()} for rec in rows]
    if not as_str:
        raise GateError("TRI json empty")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(as_str[0].keys()))
    writer.writeheader()
    for rec in as_str:
        writer.writerow({k: "" if rec.get(k) is None else rec.get(k) for k in writer.fieldnames})
    return parse_tri_1a(buf.getvalue(), year=year)


def fetch_tri_in_huc(
    huc: HucLayer,
    dest_csv: Path,
    *,
    get_bytes: GetBytes | None = None,
    years: tuple[int, ...] = TRI_YEAR_CANDIDATES,
) -> tuple[list[dict], dict]:
    last: Exception | None = None
    for year in years:
        try:
            raw = fetch_tri_envirofacts(year=year, get_bytes=get_bytes)
            by_fac, budget = parse_tri_json(raw, year=year)
            kept, n_out = clip_to_huc(by_fac.values(), huc)
            budget["n_dropped_out_of_huc"] = n_out
            budget["n_tris_huc_year"] = len(kept)
            if not kept:
                last = GateError("TRI clip empty for {0}".format(year))
                continue
            write_facilities_csv(dest_csv, kept)
            return kept, budget
        except (GateError, FetchError, OSError, ValueError) as exc:
            last = exc
            continue
    raise GateError("TRI fetch failed: {0}".format(last))
