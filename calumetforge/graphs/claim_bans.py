# Copyright (c) 2026 Martial Systems LLC
"""Refuse 100-year P, casualty language, and copied Indy plant names."""

from __future__ import annotations

from typing import Any

from calumetforge.graphs._common import binary_graph

_FLAGS = (
    "p_as_100yr_exceedance",
    "emit_casualty_counts",
    "unmapped_risk",
    "indy_plants_copied",
    "ofr_2008_as_calumet",
)


def _evaluate(state: dict[str, Any]) -> dict[str, Any]:
    v = [k for k in _FLAGS if state.get(k)]
    return {"violations": v, "events": [{"node": "evaluate", "ok": not v}]}


def build_graph():
    return binary_graph(name="calumet.claim_bans", evaluate=_evaluate, extra=list(_FLAGS))
