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

USER_AGENT = "MartialSystemsResearch/calumet_flood_completion (stageA)"
WBD_LAYER_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4"
WBD_MAX_ALLOWABLE_OFFSET_DEG = 0.0001
WBD_GEOMETRY_PRECISION = 6
# Live WBD MapServer/4 2026-08-30: 1903.21 km2, states IL,IN,MI.
WBD_LIVE_AREASQKM = 1903.21
EXPECTED_AREA_SQKM = (1200.0, 2500.0)

NLCD_WMS_URL = "https://www.mrlc.gov/geoserver/mrlc_download/wms"
NLCD_LAYER = "NLCD_2021_Impervious_L48"
NLCD_WMS_VERSION = "1.3.0"
NLCD_TILE_PX = 2000
NLCD_NODATA = 255
NLCD_YEAR = 2021

FIRM_LAYER_URL = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
)
FIRM_WHERE = "1=1"
FIRM_OUT_FIELDS = "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF,DFIRM_ID"
FIRM_MAX_ALLOWABLE_OFFSET_DEG = 0.0001
FIRM_GEOMETRY_PRECISION = 6
FIRM_PAGE_SIZE = 200
FIRM_EXPECTED_CRS = 4269
FIRM_SOURCE = "fema_nfhl_mapserver_28"
# lon, lat NAD83. Mix: a Gary/Hammond X cell and a known Little Calumet SFHA.
FIRM_GATE_SAMPLES = (
    ("gary_downtown", -87.3370, 41.5934, "unshaded_x"),
    ("gary_little_calumet", -87.3370, 41.5630, "sfha"),
    ("crown_point_tillplain", -87.3653, 41.4169, "unshaded_x"),
)
# Live NLCD clip of 04040001 is thousands of cells on a side. CI windows skip.
FIRM_LIVE_MIN_WIDTH = 1000
FIRM_LIVE_MIN_HEIGHT = 1000

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
