# MugenForge Studio Handoff — v4.0 Forge Beyond

## Latest artifact

- Archive: `mugenforge_studio_v4_0.zip`
- App version: `4.0.0`
- Title: **MugenForge Studio 4.0 Forge Beyond**
- Run command:

```bash
python -m mugenforge.app
```

- Windows helper:

```bat
run_windows.bat
```

- Install dependencies:

```bash
pip install -r requirements.txt
```

## Development direction

MugenForge Studio remains a clean-room Python/Tkinter M.U.G.E.N character/stage editor. v4.0 adds a **Forge Beyond** command center focused on clean-room classic-editor parity workflows plus beginner-first systems that go beyond raw editor tools.

## Non-negotiable honesty

- Do not use or reference proprietary Fighter Factory / VirtuallTek source code or assets.
- Do not claim arbitrary mature SFF v2 binary extraction/rebuild; it is still not implemented.
- SFF2 workflows are source-project/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation is conservative.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Frame-data, graph, and balance reports are source-analysis aids and estimates, not engine-authoritative runtime telemetry.
- Plugin/template support is metadata/preset based; do not auto-run untrusted downloaded Python code.

## New v4.0 backend

```text
mugenforge/forge_beyond.py
```

Major functions:

- `run_forge_beyond_pass(root)`
- `write_capability_matrix(root)`
- `write_unified_project_index(root)`
- `export_command_sheet(root)` / `apply_command_sheet(root, sheet_path)`
- `export_air_batch_sheet(root)` / `apply_air_batch_sheet(root, sheet_path)`
- `write_state_graph(root)`
- `write_variable_usage_map(root)`
- `write_sprite_sound_cross_reference(root)`
- `write_template_plugin_foundation(root)`
- `write_stage_authoring_pack(root)`
- `build_forge_beyond_release_bundle(root)`
- `run_source_image_editor(ImageEditSpec(...))`
- `import_archive_project(archive_path, destination_parent, new_name)`

## New v4.0 UI

`mugenforge/app.py` adds a new **Forge Beyond** tab with buttons for:

- One-Click Parity+ Pass
- Capability Matrix
- Unified Project Index
- State Graph HTML
- Variable Usage Map
- Sprite/Sound Cross Ref
- Export/Apply Command Sheet
- Export/Apply AIR Batch Sheet
- Template / Plugin Foundation
- Stage Authoring Pack
- Import ZIP Project
- Source Image Editor
- Build Reports ZIP

Project Home remains selected at startup.

## Main Forge Beyond outputs

```text
forge_beyond/FORGE_BEYOND_DASHBOARD.md
forge_beyond/reports/CAPABILITY_MATRIX.md
forge_beyond/reports/UNIFIED_PROJECT_INDEX.md
forge_beyond/sheets/command_editor_sheet.csv
forge_beyond/sheets/air_batch_editor_sheet.csv
forge_beyond/graphs/state_graph.html
forge_beyond/graphs/state_graph.json
forge_beyond/maps/VARIABLE_USAGE_MAP.md
forge_beyond/maps/variable_usage.csv
forge_beyond/cross_reference/sprite_sound_cross_reference.md
forge_beyond/templates/forge_beyond_template_manifest.json
forge_beyond/stage_authoring/STAGE_AUTHORING_PACK.md
```

## Tests performed for v4.0

```bash
python -m compileall -q mugenforge
```

```bash
python - <<'PY'
import mugenforge
from mugenforge.app import APP_TITLE
from mugenforge.forge_beyond import FORGE_BEYOND_VERSION
print(mugenforge.__version__)
print(APP_TITLE)
print(FORGE_BEYOND_VERSION)
PY
```

Backend smoke test:

- Created a new demo character with `make_new_character`.
- Ran `run_forge_beyond_pass`.
- Exported and applied unchanged command and AIR batch sheets.
- Ran state graph, variable usage, sprite/sound cross-reference, template/plugin, stage authoring, image editor, archive import, and reports ZIP workflows.
- Verified dashboard, unified index, capability matrix, state graph HTML, command sheet, AIR batch sheet, variable map, template manifest, and stage authoring pack outputs exist.

Tkinter smoke test under Xvfb:

- Instantiated `MugenForgeApp`.
- Verified title is `MugenForge Studio 4.0 Forge Beyond`.
- Verified the app has 38 tabs.
- Verified **Project Home** is selected at startup.
- Verified **Forge Beyond** tab exists.

## Recommended next work

- Add per-row validation previews before applying CSV sheet changes.
- Add a richer graph canvas inside the UI instead of HTML export only.
- Add SND cue sheet apply support.
- Add safer template validation and import UI.
- Add stage source-art preview workflow.
- Continue improving Visual Timeline drag/drop and sprite-backed previews.
