# Copyright (c) 2026 Martial Systems LLC
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from calumetforge._bootstrap import ensure_paths

ensure_paths()

from graphforge.product_law import LawBlockedError

from calumetforge.gate import require_claims, require_huc, require_stage
from calumetforge.product_laws import laws


def test_laws() -> None:
    require_huc(huc8="04040001", thread_id="t.h.ok")
    with pytest.raises(LawBlockedError):
        require_huc(huc8="05120201", thread_id="t.h.white")
    with pytest.raises(LawBlockedError):
        require_huc(huc8="04040001", parent_huc=True, thread_id="t.h.parent")
    require_stage(current_stage="0", target_stage="0", template_kind="fixture", thread_id="t.s.ok")
    with pytest.raises(LawBlockedError):
        require_stage(current_stage="0", target_stage="C", thread_id="t.s.skip")
    with pytest.raises(LawBlockedError):
        require_stage(
            current_stage="0",
            target_stage="A",
            template_kind="fixture",
            thread_id="t.s.fix",
        )
    require_claims(thread_id="t.c.ok")
    with pytest.raises(LawBlockedError):
        require_claims(p_as_100yr_exceedance=True, thread_id="t.c.p")
    with pytest.raises(LawBlockedError):
        require_claims(indy_plants_copied=True, thread_id="t.c.indy")
    with pytest.raises(LawBlockedError):
        require_claims(ofr_2008_as_calumet=True, thread_id="t.c.ofr")
    assert {row["id"] for row in laws()} == {
        "calumet.huc_lock",
        "calumet.stage_gate",
        "calumet.claim_bans",
    }
