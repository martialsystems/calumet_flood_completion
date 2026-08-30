# Calumet flood-map completion

Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage 0 pins that HUC and a 30 m EPSG:5070 template. Live WBD area is 1903.21 km² (states IL,IN,MI). Stage A clips NLCD 2021 impervious to this HUC and extracts FEMA NFHL layer 28 (`where=1=1`) onto that grid as `sfha` plus the full `zone_class` codebook. Unshaded X is Zone X. Stage B builds slope (floor 0.001 rad), D8 HAND, and Euclidean distances on that same template from 3DEP and NHD. HAND follows D8 to the drained stream cell. `P(sfha | hydro)` is the later map-completion score, not a 1-percent annual-chance product. Train is Stage C. Upper White `05120201` stays in its own tree. OFR 2008-1322 does not cover this HUC.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

Parent (Upper White, frozen HUC): https://github.com/martialsystems/indiana_flood_completion

## Stage 0

Fixture HUC polygon plus a 32x32 30 m template. Live WBD fetch writes `data/raw/huc04040001.geojson`.

## Stage A

Live NLCD 2021 template (refuses the 32x32 fixture). NFHL `S_FLD_HAZ_AR` on layer 28. Gate samples: Gary downtown (unshaded X), Gary Little Calumet at Grant Street (SFHA), Crown Point till-plain (unshaded X).

## Stage B

3DEP on the Stage A template. NHD flowlines keep ftype 460 and 558. Slope floor, burn, fill, D8, TWI, HAND along flow, distance to flowline and waterbody. Fixture template refused. Nora HAND is not an input.

## Stage C

New train on the Stage B bands. Label is the SFHA band (floodway is already in `sfha==1`). Leave-one-HUC-10-out with a 1-pixel halo. PR-AUC vs prevalence and vs negated HAND. HistGradientBoosting on this HUC, not the Upper White XGB booster. Isotonic writes `p_sfha_calibrated.tif` and keeps `p_sfha.tif` (pooled OOF map if nested HUC-10 isotonic moves PR-AUC more than 0.02). HAND nodata stays nodata. Sampling P before that calibrated raster is refused. FIM-or-stop waits on a wet mask or this calibrated P. Industrial points wait on calibrated P.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src:. python3 scripts/run_stage0.py --huc tests/fixtures/huc.geojson --out logs/stage0_fixture
.venv/bin/python -m pytest tests -q
PYTHONPATH=src:. python3 scripts/fetch_wbd.py data/raw
PYTHONPATH=src:. python3 scripts/run_stage_a.py --huc data/raw/huc04040001.geojson --out logs/stage_a
PYTHONPATH=src:. python3 scripts/run_stage_b.py --huc data/raw/huc04040001.geojson --out logs/stage_b
PYTHONPATH=src:. python3 scripts/run_stage_c.py --huc data/raw/huc04040001.geojson --out logs/stage_c
```

Do not use stock `/usr/bin/python3 -m pytest`. Empty WBD features stop (`fetch_wbd.py` exit 2). Stage A and B stop if the template looks like the fixture grid.

| File | Role |
|------|------|
| [METHODOLOGY.md](METHODOLOGY.md) | Locked contract |
| [AGENTS.md](AGENTS.md) | Agent rules |
| [CHECKLIST.md](CHECKLIST.md) | Operator list |
| `src/calumetmap/` | HUC load, NLCD, NFHL, D8 HAND, HUC-10 CV, isotonic P |
| `calumetforge/` | GraphForge pin |

MIT. Martial Systems LLC.
