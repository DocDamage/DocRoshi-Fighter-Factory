# MugenForge Studio Handoff — v7.5 Maintenance Core

## Copy/paste prompt for the next chat

I am continuing **MugenForge Studio**, a clean-room Python/Tkinter M.U.G.E.N character/stage editor and no-code creator suite. Continue from the uploaded package **mugenforge_studio_v7_5.zip**. Do not start over. Unzip it, run smoke tests, inspect `MUGENFORGE_HANDOFF_v7_5.md`, then continue development.

Latest version: **7.5.0**  
Latest app title should be: **MugenForge Studio 7.5 Maintenance Core**  
Run command: `python -m mugenforge.app`  
Install: `pip install -r requirements.txt`

## Non-negotiable project rules

- Clean-room only. Do not use or claim Fighter Factory / VirtuallTek source, assets, or proprietary logic.
- Keep binary claims tied to implemented parser/writer paths and corpus evidence.
- Do not claim static reports are engine-authoritative unless backed by external engine evidence.
- Do not blindly overwrite user binaries; preserve candidate/backup/verified install workflows.
- Do not auto-run untrusted third-party Python plugins.

## Current architecture snapshot

- Package root: `/mnt/data/mugenforge_studio_v7_5`
- Python modules detected: 49
- Main UI file: `mugenforge/app.py`
- Maintenance module: `mugenforge/maintenance_core.py`
- Current project stats from smoke/handoff generation:
  - AIR actions: 0
  - StateDefs: 0
  - Controllers: 0

## Recent release line

- v3.4 Rescue Bridge: asset rescue and source-based SFF2 bridge.
- v3.5 Visual Forge: beginner home, timeline, axis, sound cue, migration, backup logs.
- v4.0 Forge Beyond: parity+ reports, sheets, state graph, project index.
- v4.1 Forge Polish: validation previews, sound cue apply, sprite-backed preview, backup history.
- v4.5 Timeline Core: integrated timeline, CLSN/HitDef sheets, palette/stage previews.
- v5.0 Binary Core: conservative SFF/SND binary inspection and candidate workflows.
- v5.5 Binary Maturity: deeper SFF2 decode/write candidates, SND patch candidates, runtime harness artifacts.
- v6.1 Runtime Lab: external engine launchers, logs, evidence, readiness reports.
- v7.0 Evidence Core line: gap closure, authority/evidence labs, source runtime modeling, corpus validation, verified installs.
- v7.5 Maintenance Core: handoff bundle, module catalog, UI inventory, claim audit, smoke scripts, maintenance backlog.

## What v7.5 added

- New `mugenforge/maintenance_core.py` backend.
- New **Maintenance Core** UI tab.
- One-click maintenance pass.
- Module/API catalog in CSV/JSON/HTML.
- UI tab inventory.
- Release lineage inventory.
- Honesty/claim-risk audit.
- Package-level tools:
  - `tools/run_mugenforge_smoke.py`
  - `tools/package_release.py`
  - `tools/print_latest_handoff.py`
- Package-level `MUGENFORGE_HANDOFF_v7_5.md`.
- Project-level `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md`.

## First commands to run

```bash
cd mugenforge_studio_v7_5
pip install -r requirements.txt
python -m compileall -q mugenforge
python tools/run_mugenforge_smoke.py
python -m mugenforge.app
```

## Most important next work

1. Refactor `app.py` into smaller tab/controller modules.
2. Turn smoke scripts into a real pytest suite with controlled SFF/SND fixtures.
3. Consolidate the many tabs into role-based modes and a command palette.
4. Build a broad SFF2/SND corpus validation set with support buckets and known hashes.
5. Add installer/portable builds only after regression tests stabilize.

## Files to read first

- `README.md`
- `CHANGELOG.md`
- `RELEASE_SUMMARY_v7_5.md`
- `TEST_RESULTS_v7_5.txt`
- `MUGENFORGE_HANDOFF_v7_5.md`
- `maintenance_core/MAINTAINER_START_HERE.md`
- `maintenance_core/module_catalog/module_api_catalog.html`
- `maintenance_core/ui_inventory/ui_tab_inventory.md`
- `maintenance_core/honesty_claims/honesty_claims_audit.md`
