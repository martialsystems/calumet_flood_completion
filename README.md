# Calumet flood-map completion

Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage 0 pins that HUC and a 30 m EPSG:5070 template. Live WBD area is 1903.21 km² (states IL,IN,MI). Stage A clips NLCD 2021 impervious to this HUC and extracts FEMA NFHL layer 28 (`where=1=1`) onto that grid as `sfha` plus the full `zone_class` codebook. Unshaded X is Zone X. `P(sfha | hydro)` is the later map-completion score, not a 1-percent annual-chance product. Upper White `05120201` stays in its own tree. OFR 2008-1322 does not cover this HUC. HAND and `P` weights are a new train on this HUC, not a copy of Upper White.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

Parent (Upper White, frozen HUC): https://github.com/martialsystems/indiana_flood_completion

## Stage 0

Fixture HUC polygon plus a 32x32 30 m template. Live WBD fetch writes `data/raw/huc04040001.geojson`.

## Stage A

Live NLCD 2021 template (refuses the 32x32 fixture). NFHL `S_FLD_HAZ_AR` on layer 28. Gate samples: Gary downtown (unshaded X), Gary Little Calumet at Grant Street (SFHA), Crown Point till-plain (unshaded X). TRI overlay is optional and local. FIM-or-stop and industrial points wait on a FIRM raster plus a later P raster.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src:. python3 scripts/run_stage0.py --huc tests/fixtures/huc.geojson --out logs/stage0_fixture
.venv/bin/python -m pytest tests -q
PYTHONPATH=src:. python3 scripts/fetch_wbd.py data/raw
PYTHONPATH=src:. python3 scripts/run_stage_a.py --huc data/raw/huc04040001.geojson --out logs/stage_a
```

Do not use stock `/usr/bin/python3 -m pytest`. Empty WBD features stop (`fetch_wbd.py` exit 2). Stage A stops if the template looks like the fixture grid.

| File | Role |
|------|------|
| [METHODOLOGY.md](METHODOLOGY.md) | Locked contract |
| [AGENTS.md](AGENTS.md) | Agent rules |
| [CHECKLIST.md](CHECKLIST.md) | Operator list |
| `src/calumetmap/` | HUC load, NLCD template, NFHL zone_class, Stage 0/A reports |
| `calumetforge/` | GraphForge pin |

MIT. Martial Systems LLC.
