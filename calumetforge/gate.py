# Copyright (c) 2026 Martial Systems LLC
"""Call sites for refuse laws."""

from __future__ import annotations

from typing import Any

from calumetforge._bootstrap import ensure_paths

ensure_paths()

from graphforge.product_law import require_law

from calumetforge.graphs.claim_bans import build_graph as build_claims
from calumetforge.graphs.huc_lock import build_graph as build_huc
from calumetforge.graphs.stage_gate import build_graph as build_stage


def require_huc(**flags: Any) -> None:
    thread_id = str(flags.pop("thread_id", "calumet_huc"))
    state = {"huc8": "04040001", "parent_huc": False}
    state.update(flags)
    require_law(
        build_huc(),
        state,
        allow_decisions=["allow"],
        law_id="calumet.huc_lock",
        thread_id=thread_id,
        raise_error=True,
    )


def require_stage(**flags: Any) -> None:
    thread_id = str(flags.pop("thread_id", "calumet_stage"))
    state = {
        "current_stage": "0",
        "target_stage": "0",
        "template_kind": "fixture",
        "firm_unshaded_x_ok": False,
        "stage_a_report": False,
        "stage_b_report": False,
    }
    state.update(flags)
    require_law(
        build_stage(),
        state,
        allow_decisions=["allow"],
        law_id="calumet.stage_gate",
        thread_id=thread_id,
        raise_error=True,
    )


def require_claims(**flags: Any) -> None:
    thread_id = str(flags.pop("thread_id", "calumet_claims"))
    state = {
        "p_as_100yr_exceedance": False,
        "emit_casualty_counts": False,
        "unmapped_risk": False,
        "indy_plants_copied": False,
        "ofr_2008_as_calumet": False,
    }
    state.update(flags)
    require_law(
        build_claims(),
        state,
        allow_decisions=["allow"],
        law_id="calumet.claim_bans",
        thread_id=thread_id,
        raise_error=True,
    )
