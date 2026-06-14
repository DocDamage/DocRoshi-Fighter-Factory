# MugenForge Studio v4.1 "Forge Polish" Release Summary

## Version

- App version: `4.1.0`
- App title: `MugenForge Studio 4.1 Forge Polish`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## Why this release exists

v4.0 added broad clean-room parity-plus workflows. v4.1 focuses on the next practical need: making those workflows safer, clearer, and more visual before users mutate project files. It adds one cockpit for validation, previews, beginner next steps, sound cue sheet insertion, state-flow graphing, template import, stage source-art preview, backup history, and report bundling.

## Built

### Version sync

- Package version, app title, Forge Polish, and Forge Beyond metadata are aligned to `4.1.0`.
- v4.0 Forge Beyond workflows remain intact; v4.1 adds the polish/stability layer on top.

### Forge Polish cockpit

- New `mugenforge/forge_polish.py` backend module.
- New **Forge Polish** UI tab.
- One-Click Polish Pass.
- Beginner dashboard with health score and actionable next steps.
- `forge_polish/FORGE_POLISH_START_HERE.md` and root `START_HERE_V4_1.md` starter guides.
- Reports bundle builder.
- Writes `forge_polish/FORGE_POLISH_START_HERE.md` and compatibility report aliases under `forge_polish/reports/`.
- Stable bundle copy at `forge_polish/reports_bundle/forge_polish_v4_1_bundle.zip`, plus timestamped export ZIPs under `exports/`.

### Sheet validation before apply

- Command sheet validation previews pending command/time/buffer edits and errors.
- AIR batch sheet validation previews pending frame edits and line-index risks.
- Validation reports are non-mutating.

### Sound cue sheet apply

- Exports `forge_polish/sheets/sound_cue_apply_sheet.csv`.
- Applies only rows with `action=add` and `enabled=yes`.
- Inserts `PlaySnd` controllers into text code with backups.
- Does not mutate SND binary banks.

### Sprite-backed timeline preview

- Generates timeline contact sheets from AIR actions.
- Uses loose source images where available.
- Uses supported SFF v1 sprite payload export where safe.
- Uses placeholders when no source sprite is available.
- Marks Clsn1 and Clsn2 presence visually.

### In-app state graph canvas

- Builds a StateDef/ChangeState canvas model.
- Draws graph nodes and edges inside the Forge Polish tab.
- Writes JSON, CSV, and HTML artifacts.

### Template/import polish

- Validates template/plugin data files.
- Imports data-only template packs from folder, ZIP, or individual file.
- Blocks executable/script-like files from auto-import.
- Does not auto-run downloaded plugins.

### Stage source-art preview

- Builds a static stage composition preview from source/background images.
- Adds estimated zoffset and rough camera/localcoord guide overlays.
- Documents that parallax, deltas, bounds, and BGCtrl timing still require engine testing.

### Backup history and restore

- Indexes backup/snapshot artifacts.
- Shows backup history in the UI.
- Restores individual backup files with a pre-restore guard copy when the target exists.
- Snapshot ZIP restore remains intentionally separate/manual.

## Honest limitations retained

- Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented.
- SFF2 workflows remain source-project/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation remains conservative.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Balance/frame-data/graph/dashboard reports are source-analysis aids, not engine-authoritative runtime telemetry.
- Template/plugin support remains data/metadata based and does not run arbitrary downloaded Python code.
