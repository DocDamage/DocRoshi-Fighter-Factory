# MugenForge Studio Handoff — v5.5 Binary Maturity

Continue from `mugenforge_studio_v5_5.zip`.

## Version

- App version: `5.5.0`
- Title: **MugenForge Studio 5.5 Binary Maturity**
- Run: `python -m mugenforge.app`
- Dependencies: `pip install -r requirements.txt`

## Main direction

v5.5 is the binary maturity pass. It closes much of the v5.0 gap list by adding common-table SFF2 parsing, decoded export for PNG/raw/RLE8/RLE5/LZ5 candidate paths, standard SFF2 candidate rebuilds, copied SFF axis mutation, guarded SND slot patch candidates, and runtime evidence scaffolding.

## Important boundaries

Do not claim every arbitrary SFF2 file in the wild is guaranteed. The parser handles common v2/v2.1 table layouts and refuses unknown/corrupt cases with reports. Candidate SFF2 builds and SND patches still need target-engine testing before release.
