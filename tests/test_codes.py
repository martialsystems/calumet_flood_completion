# Copyright (c) 2026 Martial Systems LLC

from calumetmap.codes import classify_firm_zone


def test_classify_sfha_and_floodway() -> None:
    assert classify_firm_zone("AE", "", "T") == (1, "sfha")
    assert classify_firm_zone("AE", "FLOODWAY", "T")[1] == "floodway"


def test_classify_zone_x_shaded_and_unshaded() -> None:
    assert classify_firm_zone("X", "AREA OF MINIMAL FLOOD HAZARD", "F")[1] == "unshaded_x"
    assert classify_firm_zone("X", "", "F")[1] == "unshaded_x"
    assert classify_firm_zone("X", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD", "F")[1] == "shaded_x"


def test_classify_unmapped_d_other() -> None:
    assert classify_firm_zone("OPEN WATER", "", "F")[1] == "unmapped"
    assert classify_firm_zone("AREA NOT INCLUDED", "", "F")[1] == "unmapped"
    assert classify_firm_zone("D", "", "F")[1] == "D"
    assert classify_firm_zone("ZZ", "LEVEE", "F")[1] == "other"
