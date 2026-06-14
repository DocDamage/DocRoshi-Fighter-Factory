# MugenForge Studio v5.0 Binary Core — Release Summary

## Version

- App version: `5.0.0`
- Title: `MugenForge Studio 5.0 Binary Core`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## What was built

v5.0 adds the first dedicated binary-maturity layer on top of v4.5 Timeline Core:

- `mugenforge/binary_core.py`
- New **Binary Core** Tkinter tab
- Binary safety report with SHA-256 hashes
- Native SFF/SFF2 inspection reports
- Supported SFF v1 payload extraction and conservative embedded PNG discovery
- MugenForge PNG-subset SFF2 probe/extract/axis-copy support for files created by the v5.0 experimental subset builder
- SFF axis edit sheet and patched-copy workflow
- SFF2 source/Sprmake2 rebuild workspace workflow
- Experimental MugenForge PNG-subset SFF2-style copy builder for pipeline testing
- Editable SND bank sheet for keep/update/add/delete/reorder workflows
- Rebuilt SND candidate generation from WAV payloads
- SND waveform preview output
- Binary roundtrip lab/report
- Binary Core report bundle

## Why this release matters

Earlier releases made the editor beginner-friendly and visually productive. v5.0 starts closing the harder parity gap: binary asset handling. It separates inspection, extraction, patched copies, rebuilt candidates, and explicit install/test decisions so the app can improve binary workflows without making unsafe claims.

## Tests performed

- Module compilation for all `mugenforge` modules.
- Import/version smoke test.
- Backend Binary Core smoke test on a generated character with built SFF/SND assets.
- SFF axis patched-copy apply verified by creating a patched copy with updated axis values.
- SND rebuilt-candidate apply verified by reading the rebuilt SND.
- SFF2 PNG-subset smoke test verified inspection, payload export, axis sheet export, and patched-copy axis apply on the experimental subset format.
- Tkinter UI smoke test under Xvfb.

## Honest limitations

- Full arbitrary mature SFF v2 extraction/rebuild/mutation is still not implemented.
- Unknown SFF2 compression/layout decoding is not implemented.
- SFF2 release rebuild still uses source workspace handoff rather than arbitrary in-place binary mutation.
- The experimental MugenForge PNG-subset SFF2-style copy is a pipeline/testing format, not a full Sprmake2 replacement.
- SFF axis apply creates patched copies instead of overwriting originals.
- Default SND apply creates rebuilt candidates instead of overwriting originals.
- Generated gameplay scaffolds still require engine playtesting.
