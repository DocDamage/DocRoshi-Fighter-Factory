# MugenForge Studio v7.0 Authority Lab — Release Summary

## Version

- Version: `7.0.0`
- Title: `MugenForge Studio 7.0 Authority Lab`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## Why this release exists

The previous honest limitations were real gaps: runtime simulation, engine-profile certainty, SFF/SND corpus coverage, unknown binary triage, candidate-only binary mutation, generated-code tuning, and report authority. v7.0 turns those gaps into executable workflows with visible outputs, evidence folders, CSV sheets, commit tokens, parser checks, backups, and rollback records.

## Main additions

- Authority Lab release layer.
- Evidence Core cockpit.
- Closure Lab cockpit.
- Gap Closer cockpit retained.
- Authority Core cockpit retained.
- Offline source-runtime simulation.
- External-engine adapter validation, dry-run, live-run evidence capture, stdout/stderr/result JSON, and command records.
- SFF/SND corpus validation and unknown-binary triage.
- Verified binary commit/install workflows with hashes, commit tokens, backups, and rollback.
- Gameplay tuning sheets and apply workflows for playtest-measured source changes.
- Evidence contracts and authority scores that distinguish static-only reports from engine-backed evidence.

## Key files

```text
mugenforge/evidence_core.py
mugenforge/closure_lab.py
mugenforge/gap_closer.py
mugenforge/authority_core.py
mugenforge/authority_lab.py
mugenforge/app.py
mugenforge/runtime_lab.py
```

## Implemented against the previous limitation list

### Runtime behavior

Added source-level mini-runtime tools that create CSV/JSON/HTML traces from StateDefs and AIR timing. These follow common triggers and controllers such as Time, AnimTime, AnimElem, command, ctrl, VelSet, VelAdd, PosAdd, ChangeState, SelfState, PlaySnd, HitDef, Projectile, Helper, and Explod.

### Engine scripts and external evidence

Added validated engine adapters with editable config, exact command previews, dry-run execution, live subprocess execution, stdout/stderr/result JSON capture, and profile validation.

### Readiness confidence

Added report evidence contracts and authority/evidence gates so findings can be labeled as engine evidence, mini-runtime evidence, static analysis, or manual notes.

### SFF2/SND corpus validation

Added corpus scanning and compatibility database generation for project and user-supplied files, including parser mode, sprite/palette/sound counts, export attempt counts, warnings, and SHA-256 IDs.

### Unknown binary layouts

Added unknown binary triage files with header probes, entropy, magic scans, embedded PNG/PCX/WAVE clues, hexdumps, and review notes.

### SFF/SND mutation

Added explicit commit/install sheets that promote generated SFF/SND candidates into live project files only with enabled rows and confirmation/commit tokens. Backup snapshots and rollback manifests are written first.

### Generated gameplay tuning

Added gameplay tuning sheet export/apply workflows for generated/common HitDefs and AIR timing.

### Reports/previews

Added evidence indexing and machine-readable evidence contracts so static parser reports are not treated with the same confidence as engine-backed results.

## Updated honest scope

- MugenForge does not bundle M.U.G.E.N or IKEMEN.
- The offline mini-runtime is a source-level simulator for common controller patterns, not a byte-identical clone of every engine behavior.
- External-engine authority requires the user to configure and run their local engine.
- Unknown/corrupt/encrypted/custom binary layouts are fingerprinted and triaged rather than guessed.
- Direct binary installation is supported only through explicit commit/rollback snapshots.
- Subjective gameplay feel and final balance still require real playtesting.
