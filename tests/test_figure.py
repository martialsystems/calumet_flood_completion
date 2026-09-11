# Copyright (c) 2026 Martial Systems LLC

from pathlib import Path

import pytest

from calumetmap.claims import scan_text
from calumetmap.config import INDY_PLANT_NAMES
from calumetmap.errors import GateError
from calumetmap.figure import (
    FIG1_NAME,
    FIG2_NAME,
    SCREEN_P,
    pmax_title,
    pr_auc_title,
    restamp_readme_figures,
    short_name,
    write_pmax_screen,
)

REPO = Path(__file__).resolve().parents[1]
STAGE_C = REPO / "logs" / "stage_c" / "stage_c_report.json"
STAGE_D = REPO / "logs" / "stage_d" / "stage_d_report.json"


def test_titles_are_clean() -> None:
    t1 = pr_auc_title(c=0.274, hand=0.220, prevalence=0.080)
    t2 = pmax_title()
    assert "beats HAND" in t1
    assert "Modest" in t1
    assert "Not a FIRM" in t1
    assert "0.50" in t2
    assert scan_text(t1) == []
    assert scan_text(t2) == []
    for plant in INDY_PLANT_NAMES:
        assert plant not in t1
        assert plant not in t2


def test_short_name_and_indy_refuse() -> None:
    assert short_name("HAMMOND GROUP INC- EXPANDERS 3100") == "Hammond Group"
    assert short_name("USS GARY WORKS") == "USS Gary"
    with pytest.raises(GateError, match="Indy plant"):
        short_name(INDY_PLANT_NAMES[0])


def test_restamp_writes_two_and_pmax_below_line(tmp_path: Path) -> None:
    paths = restamp_readme_figures(
        tmp_path, stage_c_path=STAGE_C, stage_d_path=STAGE_D
    )
    assert [p.name for p in paths] == [FIG1_NAME, FIG2_NAME]
    assert all(p.is_file() and p.stat().st_size > 0 for p in paths)
    import json

    rows = json.loads(STAGE_D.read_text(encoding="utf-8"))["d1_headline_rows"]
    pmax = [float(r["p_max"]) for r in rows]
    assert len(pmax) == 5
    assert all(v < SCREEN_P for v in pmax)
    assert max(pmax) < SCREEN_P
    names = [r["name"] for r in rows]
    assert names[0].upper().startswith("HAMMOND")
    assert "USS GARY" not in names[0].upper()


def test_pmax_figure_refuses_cleared_line(tmp_path: Path) -> None:
    rows = [
        {
            "name": "HAMMOND GROUP INC",
            "p_max": 0.51,
            "p_mean": 0.2,
        },
        {"name": "RESCO PRODUCTS INC", "p_max": 0.4, "p_mean": 0.1},
        {"name": "REWORLD OIL LLC", "p_max": 0.3, "p_mean": 0.1},
        {"name": "BEFESA ZINC US INC.", "p_max": 0.2, "p_mean": 0.1},
        {"name": "USS GARY WORKS", "p_max": 0.1, "p_mean": 0.05},
    ]
    with pytest.raises(GateError, match="0.50"):
        write_pmax_screen(tmp_path / FIG2_NAME, rows=rows)
