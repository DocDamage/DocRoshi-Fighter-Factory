# MugenForge Studio Handoff — v6.1 Runtime Lab

Continue development from `mugenforge_studio_v6_1.zip`.

## Current version

- App version: `6.1.0`
- App title: **MugenForge Studio 6.1 Runtime Lab**
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Install dependencies: `pip install -r requirements.txt`

## Development direction

The current focus is closing the runtime feedback gap. MugenForge now has a top-level **Runtime Lab** that creates configs, launch scripts, test plans, debug overlays, log parsers, evidence indexes, regression checklists, readiness reports, and bundles around actual external engine tests.

## New backend

```text
mugenforge/runtime_lab.py
```

## New UI tab

```text
Runtime Lab
```

## Runtime Lab output folder

```text
runtime_lab/
```

Important outputs:

```text
runtime_lab/runtime_config.json
runtime_lab/launch_profiles.csv
runtime_lab/launchers/
runtime_lab/runtime_test_plan.csv
runtime_lab/runtime_log_findings.csv
runtime_lab/runtime_evidence_index.csv
runtime_lab/runtime_regression_checklist.csv
runtime_lab/runtime_readiness_report.json
runtime_lab/RUNTIME_LAB_START_HERE.md
runtime_lab/bundles/
```

## Guardrails to preserve

- Clean-room only. Do not use or claim Fighter Factory / VirtuallTek source code or proprietary assets.
- Runtime Lab must remain honest: it organizes external testing but does not emulate the engine.
- Generated launch scripts must remain editable and transparent.
- Runtime readiness must be described as an evidence aid, not a guarantee.
- Binary edits must remain backup/candidate-first.
- Generated gameplay code still requires actual engine playtesting.

## Suggested next release

A logical next release would be **v6.5 Runtime Capture**:

- Optional safe engine-launch execution inside MugenForge with user confirmation.
- Better per-profile stdout/stderr capture.
- Screenshot/video folder watch.
- Runtime test plan status editor in the UI.
- Evidence attachment browser.
- Diff readiness between two test runs.
- Import logs from common engine folders.
