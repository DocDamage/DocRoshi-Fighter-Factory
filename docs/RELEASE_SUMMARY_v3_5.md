# MugenForge Studio v3.5 "Visual Forge" — Release Summary

## What was built

v3.5 adds a beginner-first Visual Forge layer on top of the v3.4 Rescue Bridge codebase. The goal is to make the app feel less like a raw file editor and more like a guided creative studio: users start from a Project Home, create/import projects through wizards, edit move timing and offsets visually, place sound cues through forms, and rely on central backups/logs for safer iteration.

The implementation is clean-room Python/Tkinter code. It does not use, reference, or emulate Fighter Factory / VirtuallTek source code, assets, or proprietary logic.

## Changelog grouped by requested priority items

### 1. Beginner Project Home + Wizard Mode

- Added **Project Home** tab, selected on startup.
- Added a guided new-project wizard with name, author, project type metadata, template, archetype, stats, and power style fields.
- Added Open Recent, Quick Start, tutorial text, home-doc generation, template install, SFF2 bridge pack, and backup buttons.
- Added backend `visual_forge.py` functions for Visual Forge project metadata and beginner dashboard files.

### 2. Real Visual Move-Timeline Editor

- Added **Visual Timeline** tab.
- Parses AIR frames and code controllers into a source-backed timeline model.
- Renders frame tiles with ticks, sprite group/image IDs, CLSN1/CLSN2 indicators, and event markers.
- Supports drag-to-preview timing changes and save-to-AIR tick mutation with backups.
- Exports `visual_forge/timeline_manifest.json` and `visual_forge/timeline_frames.csv`.

### 3. Sprite Offset / Axis Editor

- Added **Offset / Axis** tab.
- Supports click-and-drag AIR frame offset editing with coordinate display and snapping.
- Shows safe SFF axis reference metadata where the current SFF parser can inspect it.
- Does not claim arbitrary SFF2 binary axis mutation.

### 4. Sound Cue Editor

- Added **Sound Cue Editor** tab.
- Discovers StateDefs and inserts `PlaySnd` controllers at selected AnimElem frames with backups.
- Exports sound cue JSON/CSV manifests.

### 5. Move Composer 2.0

- Added **Move Composer 2.0** tab.
- Generates CMD/CNS/AIR move package previews from no-code fields.
- Writes move preview text and timeline seed JSON.
- Can append generated move blocks using the existing backup-safe Move Wizard path.

### 6. Existing Character Importer / Migration Wizard

- Added **Migration Wizard** tab.
- Copies existing character folders into new MugenForge project folders without modifying the original source.
- Writes migration reports and beginner migration guide docs.

### 7. Training / Debug Overlay Pack

- Added **Training Debug** tab.
- Installs the existing safe debug overlay preset.
- Writes Visual Forge training/debug docs and config.

### 8. Plugin / Template Architecture

- Added **Templates / Plugins** tab.
- Writes data-only no-code template and plugin manifest scaffolds.
- Keeps arbitrary third-party Python code execution disabled.

### 9. Improved SFF2 Bridge

- Added Visual Forge access to the SFF2 Bridge pack writer.
- Keeps SFF2 support source-based and honest: Sprmake2-ready source projects/guides only.

### 10. Central Backup / Undo / Error-Log System

- Added **Backups / Logs** tab.
- Added whole-project Visual Forge snapshot ZIPs.
- Added latest-snapshot restore with pre-restore guard snapshot.
- Added Visual Forge error log support.

## Updated run/test commands

Install dependency:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python -m mugenforge.app
```

Windows launcher:

```bat
run_windows.bat
```

Compile smoke test:

```bash
python -m compileall -q mugenforge
```

Backend smoke test example:

```bash
python - <<'PY'
from pathlib import Path
import tempfile
from mugenforge.visual_forge import create_visual_forge_project, BeginnerProjectSpec, build_visual_timeline_model
root = Path(tempfile.mkdtemp())
result = create_visual_forge_project(root, BeginnerProjectSpec(name='Smoke Hero'), install_pack=True)
project = root / 'Smoke_Hero'
print(result.to_text())
print(len(build_visual_timeline_model(project)['actions']))
PY
```

## Tests performed

- `python -m py_compile mugenforge/visual_forge.py` — passed.
- `python -m py_compile mugenforge/app.py` — passed.
- `python -m compileall -q mugenforge` — passed.
- Package import test — passed.
- App module import and title/version check — passed.
- Visual Forge backend project creation — passed.
- Timeline model generation — passed.
- AIR frame tick update with backup — passed.
- AIR offset update with backup — passed.
- Sound cue manifest export — passed.
- PlaySnd cue insertion with backup — passed.
- Move Composer 2.0 preview and append path — passed.
- Training/debug pack install — passed.
- Template/plugin scaffold generation — passed.
- Backup snapshot creation — passed.
- Migration wizard backend copy/report generation — passed.

GUI event-loop launch was not run in this headless container because Tkinter requires a display server. The app module imports successfully and the Tkinter code compiles.

## Honest limitations

- Full arbitrary mature SFF v2 extraction/rebuild is not implemented.
- SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- Mature existing-SFF/SND binary mutation remains conservative.
- Generated gameplay code is starter scaffolding and still needs real M.U.G.E.N playtesting and tuning.
- Visual Timeline and balance/frame-data reports are source-derived estimates, not engine-authoritative measurements.
- Plugin support is a data-only template/preset foundation, not a finished marketplace or arbitrary executable plugin system.
