# Agent notes: calumet_flood_completion

Public GitHub. MIT. Question: Which 30 m cells in Little Calumet-Galien (HUC-8 04040001) look like the current FEMA SFHA given terrain and distance-to-water?

Stage C in this commit: new train on Stage B bands, HUC-10 block CV, halo, PR-AUC vs prevalence and vs HAND, then isotonic. Do not copy Upper White boosters or `p_sfha` weights. Do not warp Nora HAND. Do not expand to 05120201. Do not copy the five Indy plant names from Upper White. Do not treat OFR 2008-1322 as this HUC. Do not sample P before `p_sfha_calibrated.tif`. Do not start `calumet_fim_or_stop` or `nwi_industrial_points` here. FIM waits on a wet mask or calibrated P. Industrial points wait on calibrated P. Fixture 32x32 is refused.

`calumetforge/` is the GraphForge pin: HUC lock, stage order, claim bans.

Research index: https://gist.github.com/martialsystems/66b896b0a4a0b8cba2b478aef64312f3

## Verify

`python3 ~/agent_laws_verify_before_done/vbd_gate.py check --app-root . --claim-done`
