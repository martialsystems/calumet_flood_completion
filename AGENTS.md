# Agent notes: calumet_flood_completion

Public GitHub. MIT. Question: Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage A in this commit: live NLCD 2021 clip plus NFHL layer 28 `zone_class`. Do not expand to 05120201. Do not copy the five Indy plant names from Upper White. Do not treat OFR 2008-1322 as this HUC. Do not copy Upper White HAND or `p_sfha` weights. Do not start `calumet_fim_or_stop` or `nwi_industrial_points` here. Industrial points wait on a live P raster. Stage A refuses the 32x32 fixture as a live template.

`calumetforge/` is the GraphForge pin: HUC lock, stage order, claim bans.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

## Verify

`python3 ~/agent_laws_verify_before_done/vbd_gate.py check --app-root . --claim-done`
