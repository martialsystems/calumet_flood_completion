# Methodology: Little Calumet-Galien map completion

Question: Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

## Geography lock

HUC-8 **04040001** Little Calumet-Galien. Deep River-Portage is HUC-12s inside this unit, not a second HUC-8. Expanding the HUC is a new stage. Upper White `05120201` is refused.

Vector: EPSG:4269 until a logged warp. Rasters: EPSG:5070, 30 m. Missing CRS: refuse.

Live HUC: USGS WBD MapServer layer 4, `huc8='04040001'`. Area, when present, must fall in 1200 to 2500 km².

## What Stage 0 is

HUC polygon plus a 30 m 5070 template. Fixture template is a 32x32 CI grid. Live NLCD 2021 impervious is Stage A. Stage A refuses a fixture template.

`P(sfha | hydro)` is not produced at Stage 0.

## Later stages (not this commit)

A: new NFHL `S_FLD_HAZ_AR` extract, `where=1=1`, `sfha` and `zone_class` codebook. Gate samples: Gary downtown, Indiana Dunes, Crown Point till-plain. Not Monument Circle.

B: HAND along D8, not Euclidean nearest stream.

C: HUC-10 leave-one-out for `P(sfha | hydro)`.

TRI overlay optional and local to 04040001. Do not copy the five Indy plant names. OFR 2008-1322 is an Upper White reach product: if no Calumet high-water mask fetches, log miss.

Two figures max after C. No Folium required in v1.

## Claims

Allowed: HUC 04040001; 30 m template; `P(sfha | hydro)` as map-completion (once C exists).

Banned: treating P as a 1-percent annual-chance number; unmapped risk; casualty language; Indy plant names; OFR 2008 as a Calumet inundation mask.
