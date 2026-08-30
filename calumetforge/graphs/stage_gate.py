# Copyright (c) 2026 Martial Systems LLC
"""Refuse stage skips. Stage A refuses a fixture template. No OFR 2008 D gate."""

from __future__ import annotations

from typing import Any

from calumetforge.graphs._common import binary_graph

_ORDER = ("0", "A", "B", "C")


def _rank(stage: Any) -> int:
    key = str(stage or "0")
    try:
        return _ORDER.index(key)
    except ValueError:
        return -1


def _evaluate(state: dict[str, Any]) -> dict[str, Any]:
    v: list[str] = []
    current = str(state.get("current_stage") or "0")
    target = str(state.get("target_stage") or "0")
    cr, tr = _rank(current), _rank(target)
    if cr < 0 or tr < 0:
        v.append("unknown_stage")
    if tr > cr + 1:
        v.append("stage_skip")
    kind = str(state.get("template_kind") or "")
    if tr >= _rank("A") and kind != "nlcd_2021":
        v.append("advance_on_fixture_template")
    if tr >= _rank("B"):
        if not bool(state.get("firm_unshaded_x_ok")):
            v.append("advance_without_firm_unshaded_x")
        if not bool(state.get("stage_a_report")):
            v.append("advance_without_stage_a")
    if tr >= _rank("C"):
        if not bool(state.get("stage_a_report")):
            v.append("stage_c_without_a")
        if not bool(state.get("stage_b_report")):
            v.append("stage_c_without_b")
    return {"violations": v, "events": [{"node": "evaluate", "ok": not v}]}


def build_graph():
    return binary_graph(
        name="calumet.stage_gate",
        evaluate=_evaluate,
        extra=[
            "current_stage",
            "target_stage",
            "template_kind",
            "firm_unshaded_x_ok",
            "stage_a_report",
            "stage_b_report",
        ],
    )
