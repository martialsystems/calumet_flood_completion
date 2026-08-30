# Copyright (c) 2026 Martial Systems LLC
"""Refuse any HUC that is not 04040001. Upper White stays out."""

from __future__ import annotations

from typing import Any

from calumetforge.graphs._common import binary_graph


def _evaluate(state: dict[str, Any]) -> dict[str, Any]:
    v: list[str] = []
    if str(state.get("huc8") or "") != "04040001":
        v.append("huc8")
    if state.get("parent_huc"):
        v.append("parent_huc")
    return {"violations": v, "events": [{"node": "evaluate", "ok": not v}]}


def build_graph():
    return binary_graph(name="calumet.huc_lock", evaluate=_evaluate, extra=["huc8", "parent_huc"])
