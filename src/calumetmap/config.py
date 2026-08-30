# Copyright (c) 2026 Martial Systems LLC
"""Locked Stage 0 constants. Little Calumet-Galien 04040001."""

from __future__ import annotations

from pathlib import Path

QUESTION = (
    "Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like "
    "the current FEMA SFHA given terrain and distance-to-water?"
)
HUC8 = "04040001"
HUC_NAME = "Little Calumet-Galien"
STATE_CODE = "IN"
VECTOR_CRS = 4269
TEMPLATE_CRS = 5070
TEMPLATE_RES_M = 30.0
TEMPLATE_KIND_FIXTURE = "fixture"
TEMPLATE_KIND_NLCD = "nlcd_2021"
PARENT_HUC8 = "05120201"

FIXTURE_WEST = 750_000.0
FIXTURE_NORTH = 2_170_000.0
FIXTURE_ROWS = 32
FIXTURE_COLS = 32

USER_AGENT = "MartialSystemsResearch/calumet_flood_completion (stage0)"
WBD_LAYER_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4"
WBD_MAX_ALLOWABLE_OFFSET_DEG = 0.0001
WBD_GEOMETRY_PRECISION = 6
# Whole HUC including IL/MI is about 1800 km2. Indiana slice is smaller.
EXPECTED_AREA_SQKM = (1200.0, 2500.0)

FIRM_LAYER_URL = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
)
FIRM_WHERE = "1=1"
FIRM_GATE_SAMPLES = (
    ("gary_downtown", -87.3370, 41.5934, "unshaded_x"),
    ("indiana_dunes", -87.0881, 41.6317, "unshaded_x"),
    ("crown_point_tillplain", -87.3653, 41.4169, "unshaded_x"),
)

INDY_PLANT_NAMES = (
    "THURSDAY POOLS",
    "FGF LLC",
    "ROYAL SPA CORP",
    "LINDE GAS & EQUIPMENT",
    "MAGNA POWERTRAIN EAST",
)
INDEX_GIST = "https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3"
MAPS_GIST = "https://gist.github.com/martialsystems/16584e78d079666f7e8994b4cc6158be"
UPPER_WHITE = "https://github.com/martialsystems/indiana_flood_completion"
P_DEFINITION = "P(sfha | hydro)"
REPO_ROOT = Path(__file__).resolve().parents[2]
