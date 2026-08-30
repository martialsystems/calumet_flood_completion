# Calumet flood-map completion

Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage 0 pins that HUC and a 30 m EPSG:5070 template. `P(sfha | hydro)` is the later map-completion score, not a 1-percent annual-chance product. Upper White `05120201` stays in its own tree. OFR 2008-1322 does not cover this HUC.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

Parent (Upper White, frozen HUC): https://github.com/martialsystems/indiana_flood_completion

## Stage 0

Fixture HUC polygon plus a 32x32 30 m template. Live WBD fetch writes `data/raw/huc04040001.geojson`. Stage A (new FIRM extract, NLCD template) is next. TRI overlay is optional and local. No Indy plant table.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src:. python3 scripts/run_stage0.py --huc tests/fixtures/huc.geojson --out logs/stage0_fixture
.venv/bin/python -m pytest tests -q
PYTHONPATH=src:. python3 scripts/fetch_wbd.py data/raw
```

Do not use stock `/usr/bin/python3 -m pytest`. Empty WBD features stop (`fetch_wbd.py` exit 2).

| File | Role |
|------|------|
| [METHODOLOGY.md](METHODOLOGY.md) | Locked contract |
| [AGENTS.md](AGENTS.md) | Agent rules |
| [CHECKLIST.md](CHECKLIST.md) | Operator list |
| `src/calumetmap/` | HUC load, 30 m template, Stage 0 report |
| `calumetforge/` | GraphForge pin |

MIT. Martial Systems LLC.
