# Copyright (c) 2026 Martial Systems LLC
import pytest

from calumetmap.claims import require_clean, scan_text
from calumetmap.errors import ClaimBanError


def test_question_is_clean() -> None:
    from calumetmap.config import QUESTION

    assert scan_text(QUESTION) == []


def test_p_as_100yr_and_indy_plants_fail() -> None:
    assert "p_as_100yr" in scan_text("this is a 100-year exceedance")
    assert "indy_plant_copy" in scan_text("THURSDAY POOLS overlay")
    with pytest.raises(ClaimBanError):
        require_clean("unmapped risk downtown Gary", source="t")
