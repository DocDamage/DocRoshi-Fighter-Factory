# MugenForge Studio Handoff — v4.5 Timeline Core

## Current artifact

- Archive: `mugenforge_studio_v4_5.zip`
- App version: `4.5.0`
- Title: **MugenForge Studio 4.5 Timeline Core**
- Run command: `python -m mugenforge.app`
- Windows helper: `run_windows.bat`
- Dependency install: `pip install -r requirements.txt`

## Development direction

Continue building MugenForge as a clean-room Python/Tkinter M.U.G.E.N creator suite that is beginner-friendly, no-code-first, and honest about binary limits. The user should make creative decisions; the app should handle file wiring, starter code, reports, backups, validation, repair, asset handoff, and packaging.

## New v4.5 focus

v4.5 adds the **Forge Timeline** cockpit. It is the first major pass toward making the timeline the center of move authoring.

Key files:

```text
mugenforge/forge_timeline.py
mugenforge/app.py
README.md
CHANGELOG.md
RELEASE_SUMMARY_v4_5.md
TEST_RESULTS_v4_5.txt
```

## New v4.5 workflows

- Integrated move timeline: AIR frames + CLSN presence + source-code events.
- Move timeline edit sheet: AIR timing/offset edits plus PlaySnd insertion.
- CLSN track sheet: explicit per-frame Clsn1/Clsn2 editing.
- HitDef track sheet: common attack tuning fields.
- Editable StateDef graph: graph reports plus simple numeric retarget apply.
- Palette Studio: ACT grid and non-destructive ACT variant writer.
- Stage Live Preview: approximate source-art/camera/ground preview.
- One-Click Timeline Pass: dashboard, reports, sheets, previews, bundle.

## Important guardrails

- This is not Fighter Factory source code.
- Do not use, reference, copy, or claim VirtuallTek/Fighter Factory source code or assets.
- Keep all SFF/SND mutation conservative and honest.
- Full arbitrary mature SFF v2 binary editing/rebuilding is still not implemented.
- Generated gameplay code and analysis reports require real M.U.G.E.N playtesting.

## Suggested next milestones

### v4.6

- Make the Forge Timeline canvas more interactive inside Tkinter.
- Add selection syncing: click frame -> jump to AIR line / related HitDef / sound cue.
- Add sheet diff previews before applying edits.
- Add stronger validation for dynamic ChangeState expressions.
- Add palette preview on loose source sprites.

### v4.8

- Multi-track timeline editor with tracks for sprites, CLSN, HitDefs, sounds, velocities, helpers, projectiles, and Explods.
- Inline timeline operations: frame duplicate/delete/reorder where safe.
- Better undo browser and restore previews.
- Stage preview with BG element list and basic BGCtrl visualization.

### v5.0

- Begin serious native SFF v2 parser/rebuilder work only with a large compatibility test suite and corruption safeguards.
- Strengthen SND round-trip editing with waveform UI and many real-file tests.
