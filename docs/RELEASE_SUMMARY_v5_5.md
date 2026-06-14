# MugenForge Studio v5.5 — Binary Maturity

Version: `5.5.0`
Title: `MugenForge Studio 5.5 Binary Maturity`
Run command: `python -m mugenforge.app`
Windows launcher: `run_windows.bat`
Install dependencies: `pip install -r requirements.txt`

v5.5 directly addresses the remaining binary-gap list from v5.0. It keeps the clean-room scope while adding much deeper native SFF2/SND workflows, copied mutation candidates, standard-table rebuilds, and runtime evidence scaffolding.

## Built in v5.5

- Common-table SFF2 v2/v2.1 parser for 28-byte sprite tables and 16-byte palette tables.
- SFF2 decoded export for direct PNG payloads, raw indexed/truecolor payloads, RLE8, RLE5, and LZ5 paths supported by MugenForge/Sprmake2-style workflows.
- Direct and zlib-wrapped PNG/PCX recovery for transitional or rescue payloads.
- Standard SFF2 manifest-to-candidate builder with PNG32, raw8, RLE8, RLE5, and LZ5 source modes.
- SFF1/SFF2 copied axis patching through editable CSV sheets.
- Binary Maturity tab.
- Binary Deep companion tab.
- Guarded SND slot patching for same-or-smaller WAV replacement in copied SND files.
- SND rebuild candidate workflows retained.
- Runtime Validation Lab with config, launcher, log capture helper, and evidence indexing.
- Codec probe/smoke coverage for PNG32/raw8/RLE8/RLE5/LZ5 controlled SFF2 fixtures.

## New/updated modules

```text
mugenforge/sff_codec.py
mugenforge/binary_core.py
mugenforge/binary_deep.py
mugenforge/binary_maturity.py
mugenforge/codec_core.py
mugenforge/runtime_runner.py
mugenforge/app.py
mugenforge/__init__.py
```

## Remaining honest boundaries

- Unknown/corrupt/nonstandard SFF2 variants are still refused or reported rather than silently mutated.
- Native SFF2 rebuilds are candidate files and still require target-engine testing.
- SND slot patching is guarded: replacement WAVs must fit their original slot, or users should use the rebuild workflow.
- Generated gameplay code still requires real M.U.G.E.N/IKEMEN playtesting.
- Static reports are not engine-authoritative; runtime evidence is only engine-authoritative when captured from a configured external engine run.
