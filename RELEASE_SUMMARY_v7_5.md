# Release Summary — MugenForge Studio v7.5 Continuity Core

**Version:** `7.5.0`  
**Title:** `MugenForge Studio 7.5 Continuity Core`  
**Run command:** `python -m mugenforge.app`  
**Windows launcher:** `run_windows.bat`  
**Install dependencies:** `pip install -r requirements.txt`

v7.5 is a continuity, stabilization, and maintainability release. It preserves the v7.0 Evidence/Authority stack and adds a front-door operating layer for long projects and future development sessions.

## Main additions

```text
mugenforge/operator_console.py
mugenforge/maintenance_core.py
mugenforge/handoff_core.py
```

## New/updated UI tabs

```text
Operator Console
Maintenance Core
Handoff Core
```

### Operator Console

A new recommended starting point after opening a project. It writes dashboards, phase scoring, next-step guidance, decision logs, release-readiness packets, and compact context bundles.

Key outputs:

```text
operator_console/OPERATOR_START_HERE.md
operator_console/OPERATOR_DASHBOARD.md
operator_console/operator_project_state.json
operator_console/operator_phase_status.csv
operator_console/OPERATOR_ROADMAP.md
operator_console/NEXT_CHAT_HANDOFF.md
operator_console/release_readiness/RELEASE_READINESS_PACKET.md
```

### Maintenance Core

A package-level maintainer cockpit. It writes a module/API catalog, UI tab inventory, release lineage, honesty/claim-risk audit, backlog, smoke scripts, and handoff files.

Key outputs:

```text
maintenance_core/MAINTAINER_START_HERE.md
maintenance_core/module_catalog/module_api_catalog.html
maintenance_core/ui_inventory/ui_tab_inventory.md
maintenance_core/release_lineage/release_lineage.md
maintenance_core/honesty_claims/honesty_claims_audit.md
maintenance_core/maintenance_backlog.md
maintenance_core/HANDOFF_FOR_NEXT_CHAT.md
tools/run_mugenforge_smoke.py
tools/package_release.py
tools/print_latest_handoff.py
```

### Handoff Core

A continuity system for moving the project to another chat or maintainer. It writes a context digest, package inventory, regression harness, next-chat prompt, development handoff, and handoff bundle.

Key outputs:

```text
handoff_core/HANDOFF_CORE_START_HERE.md
handoff_core/digest/CONTEXT_DIGEST.md
handoff_core/inventory/PACKAGE_INVENTORY.md
handoff_core/handoff/NEXT_CHAT_PROMPT.md
handoff_core/handoff/CURRENT_STATE_HANDOFF.md
handoff_core/regression_harness/smoke_v7_5.py
MUGENFORGE_HANDOFF_v7_5.md
NEXT_CHAT_PROMPT_v7_5.md
```

## Why this release

The project has become broad: Visual Forge, Forge Timeline, Binary Core/Maturity, Runtime Lab, Evidence/Authority tools, no-code authoring, rescue tools, and release tooling. v7.5 makes that breadth safer to continue by adding inventories, smoke scripts, handoff prompts, and consolidation guidance.

## Honest scope

v7.5 improves continuity and maintainability. It does not remove the need for configured external engine testing, broad binary corpus validation, or real gameplay playtesting. Binary install/mutation remains candidate-first with backups and verification.
