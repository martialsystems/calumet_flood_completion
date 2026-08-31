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

USER_AGENT = "MartialSystemsResearch/calumet_flood_completion (stageD)"
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

DEM_IMAGE_URL = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer/exportImage"
)
DEM_NODATA = -9999.0
DEM_TILE_PX = 2000

NHD_FLOWLINE_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6"
)
NHD_AREA_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/9"
)
NHD_WATERBODY_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12"
)
NHD_PAGE_SIZE = 2000
# StreamRiver plus Artificial Path through waterbodies (Little Calumet / Grand Calumet).
NHD_FLOWLINE_WHERE = "ftype IN (460,558)"
NHD_AREA_WHERE = "ftype=460"

DIST_NODATA = -1.0
HYDRO_NODATA = -9999.0
SLOPE_FLOOR_RAD = 0.001
HYDRO_BURN_M = 50.0
HYDRO_FILL_EPSILON_M = 1e-3
# Live NLCD 2021 template transform from Stage A @fc90f4d.
LOCKED_TRANSFORM_SHA256 = (
    "81748d4137cb2e161f4e875699d62a5b594a4141b5b6dc73eacd2af136d7e808"
)
STAGE_B_BANDS = (
    "slope",
    "twi",
    "hand",
    "dist_flowline",
    "dist_waterbody",
)
HAND_NODATA_RULE = "exclude_from_sample"
NORA_HAND_MARKERS = (
    "03351000",
    "NORI3",
    "white_river_stage_inundation",
    "nora_live",
)

WBD_HUC10_LAYER_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/5"
)
STAGE_C_FEATURES = (
    "slope",
    "twi",
    "hand",
    "dist_flowline",
    "dist_waterbody",
    "nlcd_impervious",
)
# New train for 04040001. Not Upper White XGB 200/4/0.08.
C_HGB_MAX_DEPTH = 3
C_HGB_MAX_ITER = 160
C_HGB_LEARNING_RATE = 0.05
C_HGB_MIN_SAMPLES_LEAF = 50
C_HGB_L2 = 1.0
C_HGB_MAX_BINS = 128
C_NON_SFHA_RATIO = 3.0
C_NEAR_STREAM_M = 300.0
C_RANDOM_SEED = 20260830
P_SFHA_NODATA = -1.0
P_SFHA_CALIBRATED_NAME = "p_sfha_calibrated.tif"
P_SFHA_RAW_NAME = "p_sfha.tif"
CAL_PR_AUC_MAX_SHIFT = 0.02

TRI_YEAR_CANDIDATES = (2023, 2022, 2021)
TRI_STATES = ("IN", "IL", "MI")
TRI_ENVIROFACTS = "https://data.epa.gov/efservice/MV_TRI_BASIC_DOWNLOAD"
D_BUFFER_RADIUS_CELLS = 4
D_HEADLINE_N = 5
D1_HEADER = "SFHA-like hydrology outside Zone A/AE"
