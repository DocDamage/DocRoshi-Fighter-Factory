# MugenForge Studio v7.5 Continuity Core

MugenForge Studio is a clean-room Python/Tkinter M.U.G.E.N character/stage editor and no-code creator suite. It is **not** Fighter Factory source code and does not contain VirtuallTek/Fighter Factory assets, source, or proprietary logic.

v7.5 is a continuity and maintainability release. Earlier releases expanded Visual Forge, Forge Timeline, Binary Core/Maturity, Runtime Lab, Authority/Evidence tools, and guided no-code authoring. v7.5 adds a front-door operating layer for the next developer and for long projects: **Operator Console**, **Handoff Core**, and **Maintenance Core**.

## Run

```bash
pip install -r requirements.txt
python -m mugenforge.app
```

Windows helper:

```bat
run_windows.bat
```

## Playable assets

The public repo does not include the large third-party IKEMEN/MUGEN runtime
assets needed to play the assembled build. Those assets are published separately
as a private release:

- Private assets repo: https://github.com/DocDamage/DocRoshi-Fighter-Factory-Assets
- Current playable bundle: https://github.com/DocDamage/DocRoshi-Fighter-Factory-Assets/releases/tag/playable-assets-20260614-mbevo-swr
- Local bundle note: see `ASSETS.md`

Download both split `.7z` parts from the private release into one folder, then
extract the `.001` file with 7-Zip.

Smoke test:

```bash
python -m compileall -q mugenforge
python tools/run_mugenforge_smoke.py
```

## New in v7.5

### Operator Console

Operator Console is the recommended starting point after opening a project. It writes:

- `operator_console/OPERATOR_DASHBOARD.md`
- `operator_console/operator_project_state.json`
- `operator_console/operator_phase_status.csv`
- `operator_console/OPERATOR_ROADMAP.md`
- `operator_console/NEXT_CHAT_HANDOFF.md`
- `operator_console/release_readiness/RELEASE_READINESS_PACKET.md`
- `operator_console/operator_context_bundle_*.zip`

It scores the current project, highlights blockers, and tells the user which major area to use next: Forge Timeline, Binary Maturity, Runtime Lab, Authority Lab, Evidence Core, or release packaging.

### Handoff Core

Handoff Core generates compact continuity artifacts for future development sessions:

- `handoff_core/digest/CONTEXT_DIGEST.md`
- `handoff_core/inventory/PACKAGE_INVENTORY.md`
- `handoff_core/regression_harness/REGRESSION_HARNESS.md`
- `handoff_core/handoff/NEXT_CHAT_PROMPT.md`
- `handoff_core/handoff/CURRENT_STATE_HANDOFF.md`
- `handoff_core/bundles/mugenforge_handoff_core_v7_5_*.zip`

### Maintenance Core

Maintenance Core is for package-level maintainability. It writes:

- `maintenance_core/MAINTAINER_START_HERE.md`
- `maintenance_core/module_catalog/module_api_catalog.html`
- `maintenance_core/ui_inventory/ui_tab_inventory.md`
- `maintenance_core/release_lineage/release_lineage.md`
- `maintenance_core/honesty_claims/honesty_claims_audit.md`
- `maintenance_core/maintenance_backlog.md`
- `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md`
- `tools/run_mugenforge_smoke.py`
- `tools/package_release.py`
- `tools/print_latest_handoff.py`

## Recommended workflow now

1. Open/create a character folder.
2. Start in **Operator Console** and run **One-Click Operator Pass**.
3. Use the dashboard’s next action to move into Visual/Timeline/Binary/Runtime/Evidence tools.
4. Before ending a long session, run **Maintenance Core → One-Click Maintenance Pass** and **Handoff Core → One-Click Handoff Core Pass**.
5. Send the next developer `docs/MUGENFORGE_HANDOFF_v7_5.md` plus the generated handoff/operator/maintenance bundles.

## Honest scope retained

- MugenForge does not bundle M.U.G.E.N or IKEMEN.
- Static/source reports are evidence aids, not engine-authoritative certification.
- Runtime authority comes from configured external engine runs and imported logs/evidence.
- Binary workflows remain candidate/backup/verified-install first.
- Unknown, corrupt, encrypted, or custom binary data is triaged and preserved rather than guessed.
- SFF2/SND support has grown substantially, but broad real-world corpus validation is still the key remaining proof step.
- Generated gameplay code still requires real playtesting and tuning.
