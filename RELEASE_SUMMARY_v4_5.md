# MugenForge Studio v4.5 Timeline Core — Release Summary

## Version

- Package: `mugenforge_studio_v4_5.zip`
- App version: `4.5.0`
- App title: `MugenForge Studio 4.5 Timeline Core`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## Why this release exists

v4.5 focuses on the next major usability gap: making MugenForge feel less like many separate tools and more like a unified visual production cockpit. The new Forge Timeline workflow brings frame timing, offsets, CLSN boxes, sound cues, HitDefs, state graph flow, palettes, and stage preview into one source/sheet-backed editing layer.

## Built

### Forge Timeline cockpit

- New `mugenforge/forge_timeline.py` backend module.
- New **Forge Timeline** tab in `mugenforge/app.py`.
- One-Click Timeline Pass.
- Dashboard, start-here guide, and report bundle ZIP.

### Integrated move timeline

- Builds `forge_timeline/move_timeline/integrated_move_timeline.json`.
- Builds `forge_timeline/move_timeline/integrated_move_timeline_frames.csv`.
- Builds `forge_timeline/move_timeline/integrated_move_timeline.html`.
- Builds `forge_timeline/move_timeline/integrated_move_timeline.png`.
- Combines AIR frame data with Clsn1/Clsn2 presence and source-code events such as PlaySnd, HitDef, Projectile, Helper, Explod, ChangeState, and ChangeAnim.

### Move timeline edit sheet

- Exports `forge_timeline/sheets/move_timeline_edit_sheet.csv`.
- Applies enabled rows for AIR frame group/image/x/y/ticks edits.
- Applies enabled sound cue rows by inserting source-code `PlaySnd` controllers.
- Writes backups before source edits.

### CLSN track sheet

- Exports `forge_timeline/sheets/clsn_track_sheet.csv`.
- Applies explicit per-frame Clsn1/Clsn2 add/update/delete edits.
- Preserves ClsnDefault blocks and writes AIR backups first.

### HitDef track sheet

- Exports `forge_timeline/sheets/hitdef_track_sheet.csv`.
- Applies common HitDef tuning fields: damage, pausetime, sparkno, hitsound, guardsound, ground.velocity, air.velocity, attr, hitflag, and guardflag.
- Writes code-file backups first.

### Editable StateDef graph

- Exports `forge_timeline/state_graph_editor/editable_state_graph.json`.
- Exports node/edge CSV files.
- Exports HTML and PNG graph previews.
- Exports `forge_timeline/sheets/state_graph_edit_sheet.csv`.
- Applies simple numeric ChangeState/SelfState retargets with backups.

### Palette Studio

- Exports `forge_timeline/sheets/palette_editor_sheet.csv`.
- Exports ACT grid preview PNG and HTML report.
- Applies enabled palette rows into new ACT variant files without overwriting source ACT files.

### Stage Live Preview

- Exports `forge_timeline/stage_live_preview/stage_live_preview_model.json`.
- Exports HTML and PNG approximate preview.
- Detects stage DEF/source image where possible and overlays camera/ground guides.

## Honest limitations retained

- Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented.
- SFF2 workflows remain source-project/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation remains conservative.
- Timeline and graph tools analyze and edit source text; they do not patch SFF/SND binary payloads.
- Sound cue additions insert source-code `PlaySnd` controllers and do not mutate SND banks.
- Palette Studio writes ACT variants but does not patch SFF palette tables.
- Stage Live Preview is approximate and does not emulate M.U.G.E.N rendering, parallax, or BGCtrl timing authoritatively.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Frame-data, balance, graph, dashboard, and preview reports are source-analysis aids, not engine-authoritative runtime telemetry.
