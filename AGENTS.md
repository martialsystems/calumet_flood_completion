# Agent notes: calumet_flood_completion

Public GitHub. MIT. Question: Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage 0 only in this commit. Do not expand to 05120201. Do not copy THURSDAY POOLS or the other four Indy plant names. Do not treat OFR 2008-1322 as this HUC. Do not start `calumet_fim_or_stop` or `nwi_industrial_points` here. Industrial points wait on a live P raster.

`calumetforge/` is the GraphForge pin: HUC lock, stage order, claim bans.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

## Verify

`python3 ~/agent_laws_verify_before_done/vbd_gate.py check --app-root . --claim-done`
