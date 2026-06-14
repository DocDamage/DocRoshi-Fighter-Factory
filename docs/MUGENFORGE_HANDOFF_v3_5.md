# MugenForge Studio Handoff — v3.5 Visual Forge

Latest artifact: `mugenforge_studio_v3_5.zip`

App version: `3.5.0`

App title: **MugenForge Studio 3.5 Visual Forge**

Run command:

```bash
python -m mugenforge.app
```

Windows helper:

```bat
run_windows.bat
```

Install dependency:

```bash
pip install -r requirements.txt
```

## Development direction

MugenForge Studio remains a clean-room Python/Tkinter M.U.G.E.N character/stage editor. The v3.5 focus is beginner onboarding and visual workflows: the user makes creative decisions while the tool writes safe scaffolds, guides, manifests, backups, reports, and source-based asset handoff files.

## Major v3.5 additions

- Project Home + Wizard Mode.
- Source-backed Visual Timeline editor.
- AIR sprite offset/axis alignment editor.
- Sound Cue Editor.
- Move Composer 2.0.
- Legacy character Migration Wizard.
- Training Debug pack UI.
- Data-only plugin/template foundation.
- Improved SFF2 Bridge access while preserving honest source-based limitations.
- Central backup, restore, and error-log tab.

## Important guardrails

- Clean-room only. Do not use Fighter Factory / VirtuallTek source code or proprietary assets.
- Keep binary editing conservative and honest.
- Full arbitrary mature SFF v2 binary extraction/rebuild is still not implemented.
- SFF2 Bridge is a source project / Sprmake2 handoff workflow, not internal arbitrary SFF2 mutation.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Balance and frame-data reports are estimates/source-derived, not engine-authoritative.

## Key new module

`mugenforge/visual_forge.py` contains the new backend layer for:

- `create_visual_forge_project`
- `write_beginner_project_home`
- `quick_start_pass`
- `build_visual_timeline_model`
- `write_visual_timeline_manifest`
- `update_air_frame_ticks`
- `build_sprite_offset_model`
- `update_air_frame_offset`
- `write_sound_cue_manifest`
- `add_sound_cue_controller`
- `compose_move2`
- `migrate_existing_character`
- `install_training_debug_pack`
- `install_template_architecture`
- `write_visual_sff2_bridge_pack`
- `create_backup_snapshot`
- `restore_latest_snapshot`
- `log_error`

## Recommended next work

- Replace placeholder timeline tile art with sprite-backed thumbnails where safe sprite extraction or source images are available.
- Add richer undo granularity for individual edits, not only snapshot restore.
- Expand stage-specific Project Home wizard fields.
- Add data-only template import/export UI.
- Add more automated validation for inserted PlaySnd cues and Move Composer conflict detection.
