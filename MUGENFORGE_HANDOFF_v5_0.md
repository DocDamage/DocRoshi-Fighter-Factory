# MugenForge Studio Handoff — v5.0 Binary Core

Continue from `mugenforge_studio_v5_0.zip`.

## Run

```bash
python -m mugenforge.app
```

## New in v5.0

- Binary Core tab.
- `mugenforge/binary_core.py` backend.
- Binary safety report with SFF/SND SHA-256 hashes.
- Native SFF/SFF2 inspection under `binary_core/sff_inspection/`.
- Supported SFF v1 payload extraction, embedded PNG discovery, and MugenForge PNG-subset extraction for verified cases.
- SFF axis edit sheets and patched-copy apply.
- SFF2 source/Sprmake2 rebuild workspace workflow.
- Experimental MugenForge PNG-subset SFF2-style copy builder for pipeline testing.
- SND bank edit sheets and rebuilt candidates.
- SND waveform preview.
- Binary roundtrip reports and bundle.

## Guardrails

This remains clean-room. Do not use Fighter Factory / VirtualTek source code or assets. Keep SFF2 claims honest. Full arbitrary mature SFF2 binary extraction/rebuild/mutation is still not implemented.

## Suggested next release

v5.1 should deepen the Binary Core and editor feel by adding broader SFF2 fixture tests, more verified payload decoders only when format details are confirmed, a guided install/restore browser for rebuilt SND/SFF candidates, stronger visual binary diff views, and better integration between Binary Core outputs and the Forge Timeline editor.
