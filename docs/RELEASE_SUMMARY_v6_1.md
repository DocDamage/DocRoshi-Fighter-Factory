# MugenForge Studio v6.1 Runtime Lab — Release Summary

## Version

- Version: `6.1.0`
- Title: `MugenForge Studio 6.1 Runtime Lab`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## Why this release exists

v5.5 closed more of the binary gap, but the project still needed a serious way to turn static reports into actual engine-test evidence. v6.1 adds Runtime Lab: a dedicated cockpit for external engine launch profiles, debug overlays, test scenarios, log parsing, screenshot/log evidence indexing, regression checklists, readiness scoring, and shareable runtime bundles.

## Main new module

```text
mugenforge/runtime_lab.py
```

## Main modified files

```text
mugenforge/__init__.py
mugenforge/app.py
README.md
CHANGELOG.md
RELEASE_SUMMARY_v6_1.md
MUGENFORGE_HANDOFF_v6_1.md
TEST_RESULTS_v6_1.txt
```

## Major additions

### Runtime Lab UI

Added a new **Runtime Lab** tab with one-click and focused actions:

- One-Click Runtime Lab Pass
- Runtime Config Template
- Export Launch Profiles
- Build Launch Scripts
- Install Debug Overlay
- Runtime Test Plan
- Parse Runtime Logs
- Evidence Index
- Regression Checklist
- Readiness Report
- Bundle Runtime Lab

### External launch harnesses

Runtime Lab writes editable configs and scripts:

```text
runtime_lab/runtime_config.json
runtime_lab/launch_profiles.csv
runtime_lab/launchers/run_*.bat
runtime_lab/launchers/run_*.sh
runtime_lab/RUNTIME_LAUNCHERS_README.md
```

The generated scripts are transparent and do not hide command-line assumptions.

### Runtime debug overlay

The overlay installer appends a State `-2` DisplayToClipboard/AppendToClipboard helper with a backup first. It gives creators live values during manual engine testing.

### Runtime test and evidence workflow

Runtime Lab writes scenario/checklist/report artifacts:

```text
runtime_lab/runtime_test_plan.csv
runtime_lab/RUNTIME_TEST_PLAN.md
runtime_lab/runtime_log_findings.csv
runtime_lab/runtime_log_summary.json
runtime_lab/RUNTIME_LOG_REPORT.md
runtime_lab/runtime_evidence_index.csv
runtime_lab/runtime_evidence_index.json
runtime_lab/runtime_regression_checklist.csv
runtime_lab/RUNTIME_REGRESSION_GUIDE.md
runtime_lab/runtime_readiness_report.json
runtime_lab/RUNTIME_READINESS_REPORT.md
runtime_lab/bundles/runtime_lab_bundle_*.zip
```

## Honest limitations

- Runtime Lab does not run, emulate, or simulate M.U.G.E.N/IKEMEN internally.
- Launcher scripts must be reviewed and adjusted for the exact target engine/build.
- Readiness scoring is a release aid, not engine-authoritative certification.
- Generated gameplay code still requires real playtesting.
- Binary mutation remains backup/candidate-first and avoids blind overwrites.
