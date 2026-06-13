# MugenForge Maintenance Core

Generated: 2026-06-13T19:18:16
Maintenance Core version: 7.5.0
Package root: `/mnt/data/mugenforge_studio_v7_5`
Project root: `/mnt/data/mugenforge_studio_v7_5`

## Run commands

```bash
pip install -r requirements.txt
python -m mugenforge.app
python -m compileall -q mugenforge
python tools/run_mugenforge_smoke.py
```

## Current package snapshot

- Python modules: 49
- Latest v7 docs detected: MUGENFORGE_HANDOFF_v7_0.md, MUGENFORGE_HANDOFF_v7_5.md, RELEASE_SUMMARY_v7_0.md
- Project AIR actions: 0
- Project StateDefs: 0
- Project controllers: 0

## Maintenance order for the next developer

1. Run `tools/run_mugenforge_smoke.py` from the package root.
2. Open `maintenance_core/module_catalog.html` to understand backend modules.
3. Open `maintenance_core/ui_tab_inventory.md` before editing `app.py`.
4. Read `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md` and package-level `MUGENFORGE_HANDOFF_v7_5.md`.
5. Keep binary claims tied to verified parser/rebuild paths and runtime claims tied to external evidence.

## Generated maintenance files

- `module_catalog.csv/json/html` — modules, callables, classes, constants.
- `ui_tab_inventory.csv/md` — Tkinter tabs and builder methods.
- `release_lineage.md/json` — release-doc inventory.
- `honesty_claims_audit.csv/md` — claim-risk scan for docs/UI text.
- `maintenance_backlog.md` — practical next work.
- `HANDOFF_FOR_NEXT_CHAT.md` — compressed context handoff.
