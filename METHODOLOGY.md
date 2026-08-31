# Methodology: Little Calumet-Galien map completion

Question: Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

## Geography lock

HUC-8 **04040001** Little Calumet-Galien. Deep River-Portage is HUC-12s inside this unit, not a second HUC-8. Expanding the HUC is a new stage. Upper White `05120201` is refused.

Vector: EPSG:4269 until a logged warp. Rasters: EPSG:5070, 30 m. Missing CRS: refuse.

Live HUC: USGS WBD MapServer layer 4, `huc8='04040001'`. Pinned live area: 1903.21 km². Incoming `areasqkm`, when present, must fall in 1200 to 2500 km². States must include IN; IL and MI may appear.

## What Stage 0 is

HUC polygon plus a 30 m 5070 template. Fixture template is a 32x32 CI grid. Live NLCD 2021 impervious is Stage A. Stage A refuses a fixture template.

`P(sfha | hydro)` is not produced at Stage 0.

## What Stage A is

Live NLCD 2021 impervious WMS mosaic, clipped to 04040001, 30 m EPSG:5070. NFHL MapServer layer 28, `where=1=1`, rasterized to `sfha` (0/1) and `zone_class` (unmapped, sfha, floodway, shaded_x, unshaded_x, D, other). Empty `ZONE_SUBTY` on FLD_ZONE X is unshaded X, not unmapped.

Gate samples in this basin: Gary downtown unshaded X; Gary Little Calumet at Grant Street SFHA; Crown Point till-plain unshaded X.

## What Stage B is

3DEP elevation on the Stage A NLCD 2021 template. NHD flowlines: ftype 460 StreamRiver and 558 Artificial Path (named rivers through lakes). Waterbodies and StreamRiver area polygons join the burn mask.

Slope in radians with floor 0.001 rad so TWI stays finite. Burn streams 50 m, priority-flood fill, D8, accumulation, TWI. HAND is height along the D8 path to the drained stream cell, using the unburned DEM. Distances to flowline and waterbody are Euclidean.

Undefined HAND stays nodata. It is not filled with zero. Nora HAND is not warped onto this grid.

## What Stage C is

Label: FEMA SFHA band on this template. Floodway cells are already `sfha==1`. Eligible cells have defined HAND; the 16,313 HAND nodata cells stay out of the sample and stay nodata in P.

Blocks: WBD HUC-10 polygons inside 04040001. Leave-one-HUC-10-out. Train drops a 1-pixel halo around the held-out unit.

Model: `HistGradientBoostingClassifier` fit on this HUC (max_depth 3, max_iter 160, learning_rate 0.05). Upper White XGB hyperparameters are not used.

Scores: PR-AUC vs SFHA prevalence (must beat) and vs negated HAND (logged). Isotonic writes `p_sfha_calibrated.tif` and leaves `p_sfha.tif` unchanged. Nested leave-one-HUC-10 isotonic is used when it moves PR-AUC by at most 0.02; otherwise a single increasing map is fit on the OOF scores so rank is preserved. Sampling P before that calibrated raster is refused.

TRI overlay optional and local to 04040001. OFR 2008-1322 is an Upper White reach product: if no Calumet high-water mask fetches, log miss.

Locked C (`3a5dcfd`): PR-AUC 0.274 vs HAND 0.220 vs prevalence 0.080.

## What Stage D is

TRI Form R on-site facilities whose coordinates fall in 04040001. States IL, IN, and MI are queried; Indiana must appear in the live clip. Dioxin rows are held in grams and add 0 lb. Off-site release totals are logged and not added to on-site pounds.

Each facility is scored on `p_sfha_calibrated.tif` in a 4-cell (120 m) window. p_max is the window maximum. p_mean is the window mean. D1 is unshaded X with a scored window. Headline: five D1 rows, sorted by p_max then on-site pounds. p_mean sits on the same row. The five Indy plant names are refused.

Raw `p_sfha.tif` stays on disk and is not the overlay. OFR 2008 is not used.

## Claims

Allowed: HUC 04040001; 30 m template; NFHL `zone_class`; D8 HAND; modest PR-AUC that beats HAND; `P(sfha | hydro)` after isotonic; five local TRI rows with p_max and p_mean.

Scanner ids in `calumetmap.claims` stay in force: casualty_count, climate_attribution, tornado_count, population_at_risk, p_as_100yr, unmapped_risk, indy_plant_copy. OFR 2008-1322 is an Upper White reach product.
