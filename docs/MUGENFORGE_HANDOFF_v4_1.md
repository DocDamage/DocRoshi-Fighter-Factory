# MugenForge Studio Handoff — v4.1 Forge Polish

## Current artifact

- Archive: `mugenforge_studio_v4_1.zip`
- App version: `4.1.0`
- App title: **MugenForge Studio 4.1 Forge Polish**
- Main run command: `python -m mugenforge.app`
- Windows helper: `run_windows.bat`
- Dependency install: `pip install -r requirements.txt`

## What changed from v4.0

v4.1 adds a polish/stability cockpit on top of v4.0 Forge Beyond.

New backend module:

```text
mugenforge/forge_polish.py
```

Main UI integration:

```text
mugenforge/app.py
```

New UI tab:

```text
Forge Polish
```

## v4.1 feature focus

- Beginner dashboard and next steps.
- Command/AIR CSV validation before apply.
- Editable sound cue sheet export/apply.
- Sprite-backed AIR timeline contact sheet.
- In-app StateDef graph canvas.
- Data-only template/plugin validation/import.
- Stage source-art preview.
- Backup history browser.
- Individual backup restore with pre-restore guard copies.
- Forge Polish report bundle.

## Important guardrail to preserve

This is a clean-room M.U.G.E.N creator suite. Do not use or claim Fighter Factory / VirtuallTek source code, assets, or proprietary logic.

Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented. SFF2 work remains source-project/Sprmake2 handoff based. Do not soften this limitation unless a real native implementation and test corpus are added.

## Next likely work after v4.1

- Turn the timeline contact sheet into a truly interactive timeline with sprite thumbnails, sound lanes, hitbox lanes, and velocity lanes.
- Improve the state graph canvas with click-to-jump and simple visual transition editing.
- Add a real palette studio.
- Expand stage preview into live DEF/BGCtrl editing.
- Add stronger SND bank round-trip editing.
- Begin a real native SFF v2 parser/rebuilder only with conservative round-trip tests and honest failure modes.
