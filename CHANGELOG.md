# Changelog

## v7.5.0 Continuity Core

### Added

- New **Operator Console** tab as the recommended front door for long sessions and broad projects.
- New `mugenforge/operator_console.py` backend with project-state inspection, phase scoring, dashboard, roadmap, next-chat handoff, decision log, release-readiness packet, and compact context bundle.
- New **Maintenance Core** tab.
- New `mugenforge/maintenance_core.py` backend with module/API catalog, UI tab inventory, release-lineage inventory, claim-risk audit, maintenance backlog, package-level smoke scripts, and next-chat handoff.
- New **Handoff Core** tab.
- Rebuilt `mugenforge/handoff_core.py` with context digest, package inventory, regression harness, next-chat prompt, development handoff, and handoff bundle.
- Package-level `tools/run_mugenforge_smoke.py`, `tools/package_release.py`, and `tools/print_latest_handoff.py`.
- Updated `MUGENFORGE_HANDOFF_v7_5.md`, `RELEASE_SUMMARY_v7_5.md`, and `TEST_RESULTS_v7_5.txt`.

### Changed

- App title changed to `MugenForge Studio 7.5 Continuity Core`.
- Default startup tab now selects **Operator Console** when available.
- The development direction is now consolidation and maintainability rather than adding another isolated capability layer.
- Handoff docs emphasize app.py modularization, real tests, UI consolidation, and corpus validation as the next priorities.

### Verified

- Module compilation.
- Import/version smoke.
- Handoff Core backend pass.
- Operator Console backend pass.
- Maintenance Core backend pass.
- Generated regression harness.
- Package-level smoke script.
- Tkinter UI smoke under Xvfb.
- ZIP packaging and extracted-package import smoke.

### Honest scope retained

- MugenForge does not bundle or replace M.U.G.E.N/IKEMEN.
- Static/source reports are evidence aids, not engine-authoritative certification.
- Binary mutation remains candidate/backup/verified-install first.
- Broad third-party SFF2/SND corpus validation remains the biggest proof step.
- v7.5 improves handoff, testing, and maintainability; it does not claim new arbitrary binary/runtime authority.

## v7.0.0 Authority Lab

### Added

- New **Authority Lab** release layer.
- New **Evidence Core** cockpit targeting the previous honest-limitation list directly.
- New **Closure Lab** cockpit with one-click limitation-closure workflows.
- Source-level offline runtime simulation for common M.U.G.E.N StateDef/AIR/controller sanity checks.
- Engine adapter/profile generation, validation, dry-run, external run, and captured stdout/stderr/result artifacts.
- SFF2/SND corpus validation workflows.
- Unknown SFF2/SND binary triage artifacts: hashes, magic bytes, entropy/signature scans, parser warnings, and review notes.
- Explicit binary mutation commit/install sheets with candidate verification, commit tokens, rollback snapshots, and restore workflow.
- Gameplay tuning sheet export/apply workflow for generated/scaffolded HitDefs and AIR timing.
- Report evidence contracts tying static reports to concrete runtime/corpus/evidence artifacts.
- New `mugenforge/evidence_core.py`, `mugenforge/closure_lab.py`, `mugenforge/gap_closer.py`, `mugenforge/authority_core.py`, and `mugenforge/authority_lab.py` workflows are present in the package.

### Changed

- App title changed to `MugenForge Studio 7.0 Authority Lab`.
- Release readiness now prioritizes evidence-backed gates rather than only static source checks.
- Binary mutation workflows now include explicit reviewed commits, hashes, backups, and rollback snapshots instead of only candidate generation.
- Generated gameplay code now has a playtest feedback/tuning loop.

### Verified

- Module compilation.
- Import/version smoke test.
- Closure Lab backend pass on generated project.
- Evidence Core backend pass on generated project.
- Gameplay tuning apply test.
- Engine adapter dry-run output generation.
- SFF2/SND corpus and unknown-binary triage generation.
- Tkinter UI smoke under Xvfb with Authority Lab, Evidence Core, Closure Lab, Gap Closer, Runtime Lab, and Authority Core tabs present.
- ZIP extraction/import verification.

### Remaining honest scope

- MugenForge does not bundle M.U.G.E.N or IKEMEN.
- Source-level runtime simulation is useful preflight analysis, not a full engine clone.
- Engine-backed confidence requires a user-configured local engine executable and captured run evidence.
- Unknown, corrupt, encrypted, or custom binary variants are fingerprinted and triaged rather than guessed.
- Blind overwrites remain blocked; verified binary writes use backups and explicit opt-in sheets.
- Gameplay feel and balance still require actual playtesting, now supported by structured tuning/evidence workflows.

## v6.1.0 Runtime Lab

### Added

- New **Runtime Lab** tab.
- New backend module `mugenforge/runtime_lab.py`.
- Runtime config writer: `runtime_lab/runtime_config.json`.
- Editable launch profile sheet: `runtime_lab/launch_profiles.csv`.
- Generated Windows and shell launcher scripts under `runtime_lab/launchers/`.
- Optional State `-2` DisplayToClipboard/AppendToClipboard debug overlay installer with backup.
- Runtime scenario matrix and manual test plan.
- Runtime log parser with CSV, JSON, and Markdown output.
- Runtime evidence index with file sizes, modified times, and SHA-256 hashes.
- Runtime regression checklist.
- Runtime readiness report and score.
- Runtime Lab evidence/report ZIP bundle.

### Changed

- App title changed to `MugenForge Studio 6.1 Runtime Lab`.
- The runtime workflow is now its own top-level cockpit instead of a small binary-maturity helper.
- The recommended late-project loop is now: generate launcher/test plan, run the external engine, collect logs/evidence, parse logs, and regenerate readiness.

### Verified

- Module compilation.
- Version/import smoke test.
- Runtime Lab backend smoke on a generated character.
- Generated launch profile and launcher artifacts.
- Debug overlay backup/append behavior.
- Runtime log parsing from a synthetic log.
- Evidence indexing.
- Runtime readiness report.
- Runtime Lab bundle generation.
- Tkinter UI smoke under Xvfb with exactly one Runtime Lab tab.
- ZIP extraction and import verification.

### Still limited

- MugenForge does not emulate or simulate M.U.G.E.N/IKEMEN.
- Generated launcher commands must be reviewed for the target engine/build.
- Runtime readiness is an evidence aid, not engine-authoritative certification.
- Generated gameplay code still requires real playtesting and tuning.
- Binary SFF/SND mutation remains candidate/backup-first and avoids blind overwrites.

## v5.5.0 Binary Maturity

### Added

- Common-table SFF2 parser for v2/v2.1-style sprite/palette tables.
- Decoded SFF2 export for PNG, raw indexed/truecolor, RLE8, RLE5, and LZ5 candidate paths.
- Standard SFF2 candidate builder from source manifests.
- Copied SFF1/SFF2 axis mutation workflow.
- Binary Maturity tab and runtime harness.
- Guarded SND same-or-smaller slot patch copies.
- Runtime evidence helper and log ingestion foundation.

### Changed

- Binary Core now routes key workflows through the v5.5 SFF2 parser/exporter.
- App title changed to `MugenForge Studio 5.5 Binary Maturity`.

### Still honest

- Unknown/corrupt/nonstandard SFF2 variants are refused or reported.
- Candidate SFF2/SND outputs still require target-engine testing.

## v5.5.0 Binary Maturity

### Added

- New **Binary Maturity** tab and backend module `mugenforge/binary_maturity.py`.
- New **Binary Deep** compatibility tab and backend module `mugenforge/binary_deep.py`.
- Standard/common-table SFF2 v2/v2.1 parsing and reporting in `mugenforge/sff_codec.py`.
- Decoded SFF2 export for direct PNG/PCX, zlib-wrapped PNG/PCX, raw indexed/RGB/RGBA, RLE8, and controlled RLE5/LZ5 paths, with raw-payload preservation for unusual variants.
- SFF2 edit workspace export/apply for supported axis/source-image edits and rebuilt candidate copies.
- Controlled table-backed native SFF2 writer from source or decoded-export manifests.
- SND slot patch sheets for same-size/smaller WAV replacement candidates in copied SND files.
- Runtime Test Harness / Runtime Validation Lab artifacts for collecting real engine evidence.
- Binary Maturity and Binary Deep report bundles.

### Changed

- App title changed to `MugenForge Studio 5.5 Binary Maturity`.
- Package version changed to `5.5.0`.
- The v5.0 SFF2 limitation is narrowed: common-table SFF2 files are no longer metadata-only for supported payloads.
- The v5.0 SND limitation is narrowed: copied direct patch candidates now exist for same-slot WAV payload replacements.
- Native SFF2 output is now a controlled table-backed writer path verified by MugenForge parser/export round trips, not the earlier private PNG-subset experiment.
- Generated gameplay scaffolding now has runtime validation artifacts for collecting actual test evidence.

### Verified

- Module compilation for all `mugenforge` modules.
- Import/version smoke test.
- Tkinter UI instantiation under Xvfb; Binary Core, Binary Deep, and Binary Maturity tabs appear.
- Controlled standard SFF2 build from PNG sources.
- Controlled standard SFF2 parse/decode/export.
- SFF2 maturity report and edit workspace export/apply.
- SND slot patch sheet export and copied patch candidate apply.
- Runtime Test Harness generation.
- One-Click Binary Maturity and Binary Deep passes on the controlled smoke project.

### Still limited / honest notes

- Unknown, corrupt, encrypted, or tool-specific SFF2 variants may still require manual review.
- v5.5 codec coverage is verified on controlled fixtures; broad real-world corpus validation remains necessary.
- Custom RLE/LZ variants can still export as raw `.bin` with warnings instead of decoded PNG.
- Binary mutation workflows write candidate copies/backups first; blind overwrite is intentionally avoided.
- SND direct WAV replacement is limited to slots where the replacement fits; larger changes use rebuilt candidates.
- Runtime reports and generated telemetry helpers still require real M.U.G.E.N/IKEMEN playtesting.

## v5.0.0 Binary Core

### Added

- New **Binary Core** tab and backend module `mugenforge/binary_core.py`.
- One-Click Binary Core Pass.
- Native SFF/SFF2 binary inspection report with table probes, payload-kind reporting, marker scans, and warnings.
- Supported SFF v1 payload extraction, conservative embedded PNG discovery, and MugenForge PNG-subset SFF2 payload extraction where records can be verified.
- SFF axis edit sheet with patched-copy apply workflow.
- SFF2 source rebuild pack workflow through Sprmake2 source projects.
- Editable SND bank sheet for keep/update/add/delete/reorder workflows.
- Rebuilt SND candidate generation from WAV payloads, leaving the current SND untouched until manually installed/tested.
- SND waveform board output.
- Binary roundtrip lab/report and Binary Core reports bundle.

### Changed

- App title changed to `MugenForge Studio 5.0 Binary Core`.
- Package version changed to `5.0.0`.
- The binary workflow now has a dedicated cockpit instead of being scattered across rescue/source-handoff tabs.

### Verified

- Module compilation for all `mugenforge` modules.
- Package import and version check.
- New character creation.
- Placeholder SFF/SND generation.
- Binary Core dashboard generation.
- SFF/SFF2 native inspection generation.
- Supported SFF payload extraction.
- SFF axis sheet export and patched-copy apply.
- SND bank sheet export and rebuilt-candidate apply.
- Binary roundtrip lab generation.
- One-Click Binary Core Pass.
- Tkinter UI instantiation under Xvfb; Binary Core tab appears.

### Still limited

- Full arbitrary mature SFF v2 extraction/rebuild/mutation is still not implemented.
- SFF2 custom bitmap encodings and unknown layouts are reported but not decoded or mutated.
- SFF axis apply creates patched copies; it does not blindly overwrite the original SFF.
- SND apply creates rebuilt candidates; final installation/testing remains explicit.
- SFF2 release rebuild remains source/Sprmake2 based; the experimental MugenForge PNG-subset copy is for pipeline testing only.
- Generated gameplay code is starter scaffolding and requires real M.U.G.E.N playtesting.

## v4.5.0 Timeline Core

### Added

- New **Forge Timeline** tab and backend module `mugenforge/forge_timeline.py`.
- One-Click Timeline Pass for dashboarding, integrated timeline generation, edit-sheet exports, graph artifacts, palette studio outputs, stage preview outputs, and report bundling.
- Integrated move timeline model and visual PNG/HTML report that combines AIR frames, ticks, offsets, Clsn1/Clsn2 presence, PlaySnd cues, HitDefs, and other source events.
- Move timeline edit sheet apply workflow for AIR frame timing/offset edits and text-code PlaySnd cue insertion with backups.
- CLSN track sheet export/apply workflow for explicit per-frame hitbox/hurtbox editing.
- HitDef track sheet export/apply workflow for damage, pausetime, sparks, sounds, velocity, attr, hitflag, and guardflag fields.
- Editable StateDef graph artifacts with simple numeric ChangeState/SelfState retarget sheet and apply workflow.
- Palette Studio for ACT grid preview, editable palette CSV, and non-destructive ACT variant creation.
- Stage Live Preview with approximate camera/ground overlay and stage/source-image detection.
- Forge Timeline dashboard, start-here guide, and reports bundle ZIP.

### Changed

- App title changed to `MugenForge Studio 4.5 Timeline Core`.
- Package version changed to `4.5.0`.
- v4.1 Forge Polish remains intact and is now followed by a more unified visual/sheet-backed editing cockpit.

### Verified

- Module compilation for all `mugenforge` modules.
- Package import and version check.
- New character creation.
- Forge Timeline dashboard generation.
- Integrated move timeline JSON/CSV/HTML/PNG generation.
- Move timeline sheet export and apply with AIR backup plus PlaySnd insertion.
- CLSN track sheet export and apply with AIR backup.
- HitDef track sheet export and apply with CNS backup.
- Editable StateDef graph artifact generation and simple retarget apply.
- Palette Studio generation and ACT variant apply.
- Stage Live Preview generation.
- Forge Timeline reports bundle generation.
- One-Click Timeline Pass.
- Tkinter UI instantiation under Xvfb; Forge Timeline tab appears.

### Still limited

- Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented.
- SFF2 workflows remain source/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation remains conservative.
- Timeline, graph, palette, stage, frame-data, and dashboard reports are source-analysis aids, not engine-authoritative runtime telemetry.
- Sound cue insertion edits source code only; it does not mutate SND binary banks.
- Palette Studio writes ACT variants but does not patch SFF palette tables.
- Stage Live Preview is approximate and does not emulate M.U.G.E.N rendering, parallax, or BGCtrl timing authoritatively.
- Generated gameplay code is starter scaffolding and requires real playtesting.


## v4.1.0 Forge Polish

### Added

- New **Forge Polish** tab and backend module `mugenforge/forge_polish.py`.
- One-Click Polish Pass for dashboarding, sheet validation, sound cue sheet export, timeline preview, state graph artifacts, template validation, stage preview, backup history, and report bundling.
- Beginner dashboard with project health score, facts, and concrete next-step checklist.
- Pre-apply validation for Forge Beyond command and AIR batch sheets.
- Editable sound cue sheet export/apply workflow; applies only `action=add` and `enabled=yes` rows and writes backups before text-code changes.
- Sprite-backed timeline contact sheet using loose source images or supported SFF v1 sprite payload export, with Clsn1/Clsn2 visual indicators.
- In-app StateDef graph canvas plus JSON/CSV/HTML graph outputs.
- Data-only template/plugin validation and import workflow.
- Stage source-art preview with estimated zoffset and rough localcoord camera guide.
- Backup history browser, individual backup restore helper, and pre-restore guard copies.
- Forge Polish report bundle ZIP.

### Changed

- App title changed to `MugenForge Studio 4.1 Forge Polish`.
- Package version changed to `4.1.0`.
- v4.0 Forge Beyond remains intact and is now followed by a polish/stability cockpit.

### Verified

- Module compilation for all `mugenforge` modules.
- Package import and version check.
- New character creation and beginner pack install.
- Forge Beyond command/AIR sheet export.
- Forge Polish dashboard generation.
- Command/AIR sheet validation preview.
- Editable sound cue sheet export/apply with backup creation.
- Sprite-backed timeline preview generation.
- State graph canvas model/artifact generation.
- Template architecture validation.
- Stage source-art preview generation.
- Backup history indexing.
- Forge Polish bundle generation.
- One-Click Polish Pass.
- Tkinter UI instantiation under Xvfb; Forge Polish tab appears.

### Still limited

- Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- SFF2 workflows remain source/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation remains conservative.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Balance/frame-data/graph/dashboard reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- Plugin/template support remains data/metadata based and does not run arbitrary downloaded Python code.


## v4.0.0 Forge Beyond

### Added

- New **Forge Beyond** tab and backend module `mugenforge/forge_beyond.py`.
- One-Click Parity+ Pass for project reports, sheets, graphs, templates, source-image outputs, and report ZIP bundles.
- Honest clean-room capability matrix for parity-style and beyond-editor workflows.
- Unified project index covering file inventory, commands, states, AIR frames, HitDefs, SFF metadata, and SND metadata.
- Command sheet export/apply workflow for no-code CMD command/time/buffer edits with backups.
- AIR batch sheet export/apply workflow for no-code group/image/x/y/ticks/flags edits with backups.
- State graph exports: HTML, DOT, JSON, and CSV.
- Variable usage map for `var(n)`, `fvar(n)`, and `sysvar(n)` references.
- Sprite/Sound cross-reference sheets for AIR sprite refs and PlaySnd cue refs.
- Metadata-only template/plugin foundation.
- Stage authoring pack with starter DEF and checklist.
- Conservative ZIP project import, source image batch editor, and Forge Beyond report bundle ZIP.
- ZIP project/archive import workflow.
- Source-image batch editor for trim, scale, format conversion, and manifests.

### Changed

- App title changed to `MugenForge Studio 4.0 Forge Beyond`.
- Package version changed to `4.0.0`.
- v3.5 Visual Forge remains intact and is now complemented by a parity-plus command center.

### Verified

- Module compilation for all `mugenforge` modules.
- Package import.
- New character creation.
- Beginner pack install.
- Forge Beyond One-Click Parity+ Pass.
- ZIP archive import.
- Source image editor smoke test.
- Command sheet export and unchanged apply.
- AIR batch sheet export and unchanged apply.
- State graph generation.
- Tkinter UI instantiation under Xvfb; Forge Beyond tab appears.

### Still limited

- Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- SFF2 workflows remain source/Sprmake2 handoff workflows.
- Existing SFF/SND binary mutation remains conservative.
- Generated gameplay code is starter scaffolding and requires real playtesting.
- Balance/frame-data/graph reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- Plugin/template support remains metadata/preset based and does not run arbitrary downloaded Python code.

## v3.5.0 Visual Forge

### Beginner Project Home + Wizard Mode

- Added a new **Project Home** tab selected on startup.
- Added a beginner new-project wizard for character name, author, project type metadata, template, archetype, basic stats, and power style.
- Added recent-project loading, Quick Start, tutorial text, and one-click home-doc generation.
- Added Visual Forge project metadata and beginner dashboard writers.

### Real Visual Move-Timeline Editor

- Added a new **Visual Timeline** tab.
- Added source-backed AIR frame timeline rendering with frame duration, sprite IDs, CLSN1/CLSN2 indicators, and parsed code-event markers.
- Added drag-to-preview timing changes and save-to-AIR tick updates with backups.
- Added JSON/CSV timeline manifest exports.

### Sprite Offset / Axis Editor

- Added a new **Offset / Axis** tab.
- Added drag-based AIR frame offset editing with live coordinate display and snapping.
- Added read-only SFF axis reference display where safe inspection is supported.
- Kept SFF2 binary axis mutation honest: arbitrary SFF2 binary axis patching is not implemented.

### Sound Cue Editor

- Added a new **Sound Cue Editor** tab.
- Added StateDef discovery, PlaySnd cue insertion by AnimElem, and backup-safe code mutation.
- Added sound cue JSON/CSV manifest export.

### Move Composer 2.0

- Added a new no-code **Move Composer 2.0** tab.
- Added preview-file generation and timeline seed output.
- Added optional append-to-project behavior using existing backup-safe Move Wizard paths.

### Existing Character Importer / Migration Wizard

- Added a new **Migration Wizard** tab.
- Added legacy-character folder copying into a new MugenForge project folder without modifying the original.
- Added migration report and beginner migration guide writers.

### Training / Debug Overlay Pack

- Added a new **Training Debug** tab.
- Added one-click install for the existing safe debug overlay preset plus Visual Forge docs/config.

### Plugin / Template Architecture

- Added a new **Templates / Plugins** tab.
- Added data-only no-code template manifest and plugin manifest scaffolds.
- Explicitly kept arbitrary third-party Python plugin execution disabled.

### Improved SFF2 Bridge

- Added Visual Forge access to the honest SFF2 Bridge pack writer.
- Source-based Sprmake2 handoff remains the supported SFF2 path; full arbitrary SFF2 binary rebuilding is still not claimed.

### Central Backup / Undo / Error-Log System

- Added a new **Backups / Logs** tab.
- Added whole-project Visual Forge snapshot ZIP creation.
- Added latest-snapshot restore with pre-restore guard snapshot.
- Added Visual Forge error logging.

### Changed

- App title changed to `MugenForge Studio 3.5 Visual Forge`.
- Package version changed to `3.5.0`.
- README and release handoff now lead with beginner-facing Visual Forge workflows.

### Verified

- Package import.
- Module compilation with `python -m compileall -q mugenforge`.
- Visual Forge project wizard backend creation.
- Quick Start/home docs/template generation.
- Timeline model generation and AIR frame tick update.
- AIR offset update.
- Sound cue manifest export and PlaySnd insertion.
- Move Composer 2.0 preview and append path.
- Training debug pack install.
- Template/plugin scaffold generation.
- Backup snapshot generation.
- Migration wizard backend copy/report path.

### Still limited

- Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- Mature existing-SFF/SND binary mutation remains conservative.
- Generated gameplay code remains starter scaffolding and needs real engine playtesting.
- Visual timeline and balance/frame reports are source-derived estimates, not engine-authoritative measurements.


## v3.4.0 Rescue Bridge

### Added

- New **Rescue Lab** tab exposed in the UI.
- One-Click Rescue Lab Pass.
- Embedded PNG/PCX/WAV scanning from unsupported or packed projects.
- Recovery contact sheet generation.
- AIR-based recovery manifest builder.
- Recovered SFF v1 builder from salvageable sprites.
- Beginner rescue plan writer.
- New **SFF2 Bridge** tab.
- Sprmake2 source-project generator from normal sprite folders.
- Sprmake2 DEF/BAT/CSV/manifest writer.
- Optional external sprmake2.exe runner with confirmation.
- Supported SFF v1 export into an editable SFF2 source folder.
- SFF2 source-pack ZIP builder and beginner guide.

### Changed

- App title changed to `MugenForge Studio 3.4 Rescue Bridge`.
- The beginner workflow now includes asset rescue and source-based SFF2 handoff paths, reducing the need to edit packed binary files directly.

### Verified

- Package import.
- Module compilation.
- New character creation.
- Creator Suite AutoPilot.
- Creator Hub one-click pass.
- HitDef tuning sheet export/apply.
- Artist/sound handoff pack generation.
- SFF2 Bridge project/guide/source ZIP generation from test images.

### Still limited

- Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.

## v3.3.0 Creator Hub Ultra

### Added

- New **Creator Hub** production cockpit.
- One-Click Creator Hub Pass.
- Creator Dashboard export.
- Project Task Board export.
- Patch Macro Bank.
- Input Conflict Lab.
- Balance Autotune Plan.
- Combo Trial Pack.
- Controller Mapping Sheet.
- Asset Request Pack.
- No-Code Recipe Book.
- Release Website Scaffold.
- New `mugenforge/creator_hub.py` backend module.
- Creator Suite tab is now enabled in the UI.
- Creator Suite HitDef tuning sheet export/apply workflow.
- Creator Suite artist/sound handoff pack.
- Feature Bank expanded to 388 presets and 52 creator kits.

### Changed

- App title changed to `MugenForge Studio 3.3 Creator Hub Ultra`.
- Recommended beginner workflow now starts with Creator Hub or Creator Suite, then moves into Animation Player / CLSN Editor / Sprite Lab.
- More of the raw code-writing workload is moved behind reports, CSVs, recipes, and one-click scaffolds.

### Verified

- Package import.
- Module compilation.
- New character creation.
- Creator Suite AutoPilot.
- Creator Hub one-click pass.
- HitDef tuning sheet export/apply.
- Artist/sound handoff pack generation.

### Still limited

- Full mature SFF v2 extraction/rebuild is not implemented.
- Mature existing-SFF/SND binary mutation remains conservative.
- Auto-generated gameplay remains starter scaffolding and still needs testing.

## v3.0.1 Creator OS

### Fixed

- Release ZIP builders now skip previous generated ZIP artifacts in `exports/`, avoiding recursive release packages.
- Creator OS release ZIP builder now skips snapshots, backups, temp files, bytecode, and nested release ZIPs.

### Verified

- Package import.
- New character creation.
- Creator OS one-click autopilot.
- Factory Ultra one-click production pass.
- Beginner command center generation.
- Factory Ultra and Creator OS release ZIP generation.

## v3.0.0 Creator OS

Added a top-level no-code Creator OS workflow on top of the existing Factory Ultra / Factory Max automation stack.

### Added

- New **Creator OS** tab.
- One-Click Creator OS Autopilot.
- Creator profile controls for archetype, complexity, and visual style.
- Character Blueprint writer.
- Project Wiki writer.
- Auto-Code Cookbook writer.
- Start-here guide for non-coders.
- Creator OS Release ZIP builder.
- Frame Data Sheet export button.
- Input Cheatsheet export button.
- Combo Routes builder button.
- Balance Report writer button.
- Asset Shopping List writer button.
- Release Quality Gate button.
- Beginner Lessons writer button.
- New `mugenforge/creator_os.py` backend module.
- Factory Ultra compatibility aliases for the Creator OS UI layer.
- Additional Feature Bank presets/kits for no-code production, safety, beginner moves, advanced combat, boss/training, and release polish.

### Changed

- Version bumped to 3.0.0.
- App title changed to `MugenForge Studio 3.0 Creator OS`.
- Recommended beginner workflow now starts from Creator OS.
- README rewritten for v3.0.

### Still limited

- Full mature SFF v2 extraction/rebuild is not implemented.
- Existing complex SFF/SND mutation remains conservative.
- Auto-generated gameplay code, reports, FX, and audio are starter assets and still require testing.


## v2.6.0 - Factory Ultra

Added a new no-code production HQ focused on making the tool more useful than a manual editor for beginners.

### Added

- New **Factory Ultra** tab.
- One-Click Ultra Production Pass.
- Safety Snapshot ZIP creation.
- Ultra Release ZIP builder.
- Ultra Dashboard writer.
- Beginner Task Board writer.
- Production Bible writer.
- No-Code Feature Switchboard writer.
- Release Readiness report.
- Frame Data Lab CSV/Markdown export.
- Balance Lab CSV/Markdown export.
- Cancel / State Flow Lab CSV/Markdown export.
- Asset Usage Lab JSON/Markdown export.
- Sprite Axis Lab CSV/Markdown export.
- AI Tuning Lab CSV/Markdown export.
- Move Cards HTML export.
- Input Map Assistant JSON/Markdown export.
- New backend module: `mugenforge/factory_ultra.py`.

### Changed

- App title updated to **MugenForge Studio 2.6 Factory Ultra**.
- Recommended beginner workflow now starts from Factory Ultra.
- Ultra one-click pass creates a snapshot before heavy automation.
- Ultra workflow reuses Factory Max/Feature Bank systems instead of duplicating them.

### Still limited

- Full SFF v2 extraction/rebuild remains incomplete.
- Mature existing-SFF/SND binary mutation remains conservative.
- Generated gameplay remains starter scaffolding and still needs creative testing/tuning.
- Balance and frame-data exports are helpful estimates, not official engine truth.
