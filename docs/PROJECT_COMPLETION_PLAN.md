# MugenForge Project Completion Plan

## Goal

Make MugenForge Studio release-complete as a clean-room, no-code M.U.G.E.N character/stage editor with honest binary/runtime claims, repeatable validation, usable workflows, and reproducible release artifacts.

Completion is not just passing the current smoke tests. Completion requires evidence that the project is maintainable, testable, packaged, documented, and honest about what it can and cannot do.

## Current Baseline

- Branch: `codex/mugenforge-v75-continuity`
- Version line: `7.5.0`
- Current app entrypoint: `python -m mugenforge.app`
- Current `mugenforge/app.py` size: about 95 lines after refactor.
- Current validation baseline:
  - `python -m compileall -q mugenforge`
  - `python handoff_core/regression_harness/smoke_v7_5.py`
  - `python -m unittest discover -s tests -v`
- Major completed architecture work:
  - App state/actions/tabs split out of `app.py`.
  - `automation_bank` split into a package.
  - `sff_codec` split toward `mugenforge/sff/`.
  - Shared artifact/result utilities added.
  - Docs moved under `docs/`.
  - Maintenance/Handoff/Operator systems available.

## Definition of Complete

The project can be called complete when all of these are true:

1. The test suite gives meaningful coverage for parsers, SFF/SND codecs, move automation, artifact writes, and core UI wiring.
2. Binary support claims are backed by a controlled fixture set and a broader real-world corpus report with hashes and support buckets.
3. Runtime claims are backed by at least one configured external engine profile with scenario evidence logs.
4. The app has a coherent cockpit/command-palette workflow so users do not need to understand every tab.
5. Generated move automation is broad enough to create a playable starter moveset and common archetype kits without hand-coding.
6. Release packaging is reproducible and includes file manifests, checksums, test results, and handoff docs.
7. Documentation, changelog, release summary, and handoff artifacts are synchronized.
8. The repo has a clean commit, clean `git diff --check`, passing validation commands, and no stale generated claims.

## Phase 1 - Test Foundation

### Work

- Convert the existing smoke/unittest coverage into a formal pytest-compatible suite.
- Keep `unittest` compatibility if useful, but make pytest the main runner.
- Add fixtures for tiny clean-room projects:
  - Minimal DEF/CMD/CNS/AIR character.
  - Character with missing refs.
  - Character with starter SFF v1.
  - Character with starter SND.
  - Controlled SFF2 fixtures for supported and unsupported layouts.
- Add golden-file checks for generated artifacts where output stability matters.
- Add mutation rollback tests for:
  - AIR frame offset/tick edits.
  - HitDef tuning sheet apply.
  - SFF axis candidate generation.
  - SND candidate rebuild/patch flows.
  - Verified binary install/rollback sheets.

### Evidence

- `pytest -q` passes on Windows.
- Existing commands still pass:
  - `python -m compileall -q mugenforge`
  - `python handoff_core/regression_harness/smoke_v7_5.py`
  - `python -m unittest discover -s tests -v`
- Coverage report exists and identifies remaining risk areas.

### Done Criteria

- CI-friendly test command is documented in `README.md`.
- Test fixtures are small, clean-room, and committed.
- Tests cover public APIs preserved by the refactors.

## Phase 2 - Binary Corpus Proof

### Work

- Build a corpus harness folder structure:
  - `tests/fixtures/binary/sff_v1/`
  - `tests/fixtures/binary/sff_v2_supported/`
  - `tests/fixtures/binary/sff_v2_unsupported/`
  - `tests/fixtures/binary/snd_supported/`
  - `tests/fixtures/binary/snd_unsupported/`
- Create a corpus manifest with:
  - File path.
  - SHA-256.
  - Source/license note.
  - Expected support bucket.
  - Expected parser mode.
  - Expected warnings.
- Run corpus validation through Binary Core, Binary Deep, Binary Maturity, Evidence Core, Authority Core, and Closure Lab where relevant.
- Write a single codec support spec:
  - Supported SFF v1 layouts.
  - Supported SFF v2 table variants.
  - Supported image payload encodings.
  - Supported SND/WAV payload behavior.
  - Refusal/triage behavior for unknown/corrupt files.

### Evidence

- `docs/BINARY_CODEC_SUPPORT.md`
- `tests/fixtures/binary/corpus_manifest.json`
- Generated corpus report with pass/fail buckets and hashes.
- Tests assert expected parser behavior for each controlled fixture.

### Done Criteria

- Claims like “supported SFF2” point to exact table/encoding buckets.
- Unknown layouts fail safely with warnings, not silent mutation.
- Candidate/backup-first semantics remain intact.

## Phase 3 - Runtime Evidence

### Work

- Add external engine profile presets:
  - M.U.G.E.N 1.0 style profile.
  - M.U.G.E.N 1.1 style profile.
  - IKEMEN GO style profile.
- Convert manual runtime checklists into scenario files:
  - Launch character.
  - Run basic movement.
  - Trigger generated normal.
  - Trigger generated special.
  - Trigger generated super.
  - Validate no missing asset/log crash markers.
- Add log pattern packs per engine family.
- Improve evidence capture:
  - stdout/stderr.
  - exit code.
  - scenario JSON.
  - log marker summary.
  - screenshot path if available.

### Evidence

- `runtime_lab/engine_profiles/*.json`
- Scenario files under a stable folder.
- Runtime/evidence reports generated from at least one real local engine configuration.

### Done Criteria

- Static reports are still labeled static.
- Runtime confidence is only claimed when actual engine evidence exists.
- Release readiness checks distinguish “not configured” from “failed”.

## Phase 4 - UX Consolidation

### Work

- Make Operator Console / Project Home the practical cockpit.
- Add a searchable command palette that can run common actions:
  - Create starter project.
  - Add move automation pack.
  - Validate project.
  - Generate release readiness.
  - Build handoff.
  - Run binary corpus validation.
  - Run runtime scenario.
- Keep advanced tabs available but hide them behind role modes.
- Turn dashboard findings into guided action buttons where possible.

### Evidence

- Command palette UI test or import/build test.
- Updated UI inventory.
- README screenshots or workflow docs.

### Done Criteria

- Beginner workflow can be completed from cockpit + guided actions.
- Advanced workflows remain discoverable without dominating first-run UI.

## Phase 5 - Move Automation Completeness

### Work

- Expand Feature Bank from individual move snippets into move automation packs:
  - Starter normals route.
  - Beginner cancel route.
  - Rushdown kit.
  - Zoner kit.
  - Grappler kit.
  - Anti-air/reversal kit.
  - Training macro/debug kit.
- Generate:
  - CMD commands.
  - CNS StateDefs.
  - AIR placeholder actions.
  - Cancel route notes.
  - Beginner docs explaining how to replace art/sounds and test the route.
- Add tests that ensure every new preset builds a non-empty package and routes through `apply_feature_package`.

### Evidence

- New automation presets in `mugenforge.automation_bank`.
- Tests for build/apply paths.
- Generated docs in package preview/extra files.

### Done Criteria

- A new user can install one move automation pack and get a playable starter route without writing code.
- Generated output is clearly marked as scaffolding requiring playtest/tuning.

## Phase 6 - Release Packaging

### Work

- Create a reproducible release packaging command.
- Include:
  - Source package.
  - Docs.
  - Test results.
  - File hash manifest.
  - Dependency list.
  - Handoff prompt.
- Add optional Windows portable packaging after tests stabilize.
- Ensure generated ZIP excludes caches, temp files, local secrets, and unsafe artifacts.

### Evidence

- Release ZIP.
- Manifest with SHA-256 hashes.
- Test results file from the same commit.
- Reproducible packaging notes.

### Done Criteria

- A maintainer can create the release from a clean checkout with one documented command.
- Package contents match the manifest.

## Phase 7 - Documentation and Final Audit

### Work

- Regenerate Maintenance Core after final changes.
- Update:
  - `README.md`
  - `CHANGELOG.md`
  - `docs/RELEASE_SUMMARY_v*.md`
  - `docs/MUGENFORGE_HANDOFF_v*.md`
  - `docs/TEST_RESULTS_v*.txt`
- Run honesty claims audit and resolve stale high-risk claims.
- Check all references to moved docs paths.
- Review generated backlog for stale completed items.

### Evidence

- Fresh maintenance outputs.
- Fresh handoff outputs.
- Clean `rg` scan for obsolete root-level doc paths.
- Clean `git diff --check`.

### Done Criteria

- The docs describe the current project, not historical gaps that have already been addressed.
- Known limitations are still explicit.

## Final Completion Gate

Run these from a clean checkout:

```bash
python -m compileall -q mugenforge
python handoff_core/regression_harness/smoke_v7_5.py
python -m unittest discover -s tests -v
pytest -q
python tools/run_mugenforge_smoke.py
python tools/package_release.py
```

Then verify:

- `git status -sb` is clean.
- Release ZIP exists.
- Manifest hashes match package contents.
- Test results are current.
- Handoff docs point to `docs/`.
- Corpus and runtime reports exist or the release notes explicitly say they are not included.

## Priority Order

1. Test foundation.
2. Move automation completeness.
3. Binary corpus proof.
4. Runtime evidence.
5. UX command palette/cockpit.
6. Release packaging.
7. Final docs/audit regeneration.

## Risks

- Broad binary support can become overclaimed without corpus evidence.
- Runtime reports can be mistaken for engine truth unless labels remain strict.
- UI breadth can hide useful workflows from beginners.
- Generated code can create playable scaffolds, but final gameplay quality still needs human playtesting.
- Portable builds should wait until tests and packaging are stable.
