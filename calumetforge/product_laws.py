# Copyright (c) 2026 Martial Systems LLC
"""Refuse laws. Verify-before-done is the finish gate."""

from __future__ import annotations

from typing import Any


def laws() -> list[dict[str, Any]]:
    from calumetforge.graphs.claim_bans import build_graph as claim_bans
    from calumetforge.graphs.huc_lock import build_graph as huc_lock
    from calumetforge.graphs.stage_gate import build_graph as stage_gate

    return [
        {
            "id": "calumet.huc_lock",
            "build": huc_lock,
            "state": {"huc8": "04040001", "parent_huc": False},
            "allow_decisions": ["allow"],
        },
        {
            "id": "calumet.stage_gate",
            "build": stage_gate,
            "state": {
                "current_stage": "0",
                "target_stage": "0",
                "template_kind": "fixture",
            },
            "allow_decisions": ["allow"],
        },
        {
            "id": "calumet.claim_bans",
            "build": claim_bans,
            "state": {
                "p_as_100yr_exceedance": False,
                "emit_casualty_counts": False,
                "unmapped_risk": False,
                "indy_plants_copied": False,
                "ofr_2008_as_calumet": False,
            },
            "allow_decisions": ["allow"],
        },
    ]
