# Copyright (c) 2026 Martial Systems LLC
from pathlib import Path

from calumetmap.claims import scan_text
from calumetmap.config import HUC8, INDEX_GIST, INDY_PLANT_NAMES, PARENT_HUC8, QUESTION

REPO = Path(__file__).resolve().parents[1]


def test_readme_opens_with_the_question() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    body = "\n".join(text.splitlines()[1:]).lstrip()
    assert body.startswith(QUESTION)
    assert HUC8 in text
    assert PARENT_HUC8 in text
    assert "P(sfha | hydro)" in text
    assert "Stage 0" in text
    assert "Stage A" in text
    assert "Stage B" in text
    assert "Stage C" in text
    assert "1903.21" in text
    assert "04040001" in text
    assert "Monument Circle" not in text
    assert INDEX_GIST.split("/")[-1] in text
    assert ".github/blob/main/RESEARCH.md" not in text
    assert scan_text(text) == []
    assert "\u2014" not in text
    assert "What it is not" not in text
    for plant in INDY_PLANT_NAMES:
        assert plant not in text
    for name in ("METHODOLOGY.md", "AGENTS.md", "CHECKLIST.md"):
        other = (REPO / name).read_text(encoding="utf-8")
        assert scan_text(other) == []
        assert "\u2014" not in other
        assert "What it is not" not in other
        for plant in INDY_PLANT_NAMES:
            assert plant not in other
