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

## Later stages

B: HAND along D8 on this HUC. New train. Do not copy Upper White HAND.

C: HUC-10 leave-one-out for `P(sfha | hydro)`. New weights. Do not copy Upper White `p_sfha` weights.

TRI overlay optional and local to 04040001. Do not copy the five Indy plant names. OFR 2008-1322 is an Upper White reach product: if no Calumet high-water mask fetches, log miss.

Two figures max after C. No Folium required in v1.

## Claims

Allowed: HUC 04040001; 30 m template; NFHL `zone_class` on this HUC; `P(sfha | hydro)` as map-completion (once C exists).

Scanner ids in `calumetmap.claims` stay in force: casualty_count, climate_attribution, tornado_count, population_at_risk, p_as_100yr, unmapped_risk, indy_plant_copy. OFR 2008-1322 is an Upper White reach product.
