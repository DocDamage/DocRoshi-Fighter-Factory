# Honesty Claims Audit

Generated: 2026-06-14T00:15:01

This is a text scan, not a legal review. It flags statements that future developers should keep accurate.

- Rows: 3576
- High-risk rows: 537
- Medium-risk rows: 1142

## Required truth rules for future releases

- Do not claim full arbitrary SFF2 support unless validated against a broad real-world corpus.
- Do not call static reports engine-authoritative unless backed by actual engine evidence.
- Keep candidate/backup-first wording for binary mutation unless direct install is proven safe.
- Do not auto-run untrusted community Python plugins without a genuine sandbox.

## First 100 flagged lines

- **medium / safety-claim** `CHANGELOG.md:23` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:37` — - MugenForge does not bundle or replace M.U.G.E.N/IKEMEN.
- **high / engine-authority** `CHANGELOG.md:38` — - Static/source reports are evidence aids, not engine-authoritative certification.
- **medium / safety-claim** `CHANGELOG.md:39` — - Binary mutation remains candidate/backup/verified-install first.
- **medium / plugin-execution** `CHANGELOG.md:40` — - Broad third-party SFF2/SND corpus validation remains the biggest proof step.
- **high / binary-fullness** `CHANGELOG.md:41` — - v7.5 improves handoff, testing, and maintainability; it does not claim new arbitrary binary/runtime authority.
- **info / honesty-negative** `CHANGELOG.md:54` — - Explicit binary mutation commit/install sheets with candidate verification, commit tokens, rollback snapshots, and restore workflow.
- **info / honesty-negative** `CHANGELOG.md:63` — - Binary mutation workflows now include explicit reviewed commits, hashes, backups, and rollback snapshots instead of only candidate generation.
- **medium / safety-claim** `CHANGELOG.md:66` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:80` — - MugenForge does not bundle M.U.G.E.N or IKEMEN.
- **medium / safety-claim** `CHANGELOG.md:84` — - Blind overwrites remain blocked; verified binary writes use backups and explicit opt-in sheets.
- **info / honesty-negative** `CHANGELOG.md:96` — - Optional State `-2` DisplayToClipboard/AppendToClipboard debug overlay installer with backup.
- **info / honesty-negative** `CHANGELOG.md:108` — - The recommended late-project loop is now: generate launcher/test plan, run the external engine, collect logs/evidence, parse logs, and regenerate readiness.
- **medium / safety-claim** `CHANGELOG.md:110` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:116` — - Debug overlay backup/append behavior.
- **high / engine-authority** `CHANGELOG.md:126` — - MugenForge does not emulate or simulate M.U.G.E.N/IKEMEN.
- **high / engine-authority** `CHANGELOG.md:128` — - Runtime readiness is an evidence aid, not engine-authoritative certification.
- **info / honesty-negative** `CHANGELOG.md:130` — - Binary SFF/SND mutation remains candidate/backup-first and avoids blind overwrites.
- **info / honesty-negative** `CHANGELOG.md:137` — - Decoded SFF2 export for PNG, raw indexed/truecolor, RLE8, RLE5, and LZ5 candidate paths.
- **info / honesty-negative** `CHANGELOG.md:138` — - Standard SFF2 candidate builder from source manifests.
- **info / honesty-negative** `CHANGELOG.md:152` — - Candidate SFF2/SND outputs still require target-engine testing.
- **info / honesty-negative** `CHANGELOG.md:162` — - SFF2 edit workspace export/apply for supported axis/source-image edits and rebuilt candidate copies.
- **medium / safety-claim** `CHANGELOG.md:174` — - Native SFF2 output is now a controlled table-backed writer path verified by MugenForge parser/export round trips, not the earlier private PNG-subset experiment.
- **medium / safety-claim** `CHANGELOG.md:177` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:185` — - SND slot patch sheet export and copied patch candidate apply.
- **medium / safety-claim** `CHANGELOG.md:192` — - v5.5 codec coverage is verified on controlled fixtures; broad real-world corpus validation remains necessary.
- **info / honesty-negative** `CHANGELOG.md:194` — - Binary mutation workflows write candidate copies/backups first; blind overwrite is intentionally avoided.
- **medium / safety-claim** `CHANGELOG.md:205` — - Supported SFF v1 payload extraction, conservative embedded PNG discovery, and MugenForge PNG-subset SFF2 payload extraction where records can be verified.
- **info / honesty-negative** `CHANGELOG.md:209` — - Rebuilt SND candidate generation from WAV payloads, leaving the current SND untouched until manually installed/tested.
- **medium / safety-claim** `CHANGELOG.md:219` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:229` — - SND bank sheet export and rebuilt-candidate apply.
- **high / binary-fullness** `CHANGELOG.md:236` — - Full arbitrary mature SFF v2 extraction/rebuild/mutation is still not implemented.
- **info / honesty-negative** `CHANGELOG.md:238` — - SFF axis apply creates patched copies; it does not blindly overwrite the original SFF.
- **info / honesty-negative** `CHANGELOG.md:240` — - SFF2 release rebuild remains source/Sprmake2 based; the experimental MugenForge PNG-subset copy is for pipeline testing only.
- **medium / safety-claim** `CHANGELOG.md:264` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:271` — - Move timeline sheet export and apply with AIR backup plus PlaySnd insertion.
- **info / honesty-negative** `CHANGELOG.md:272` — - CLSN track sheet export and apply with AIR backup.
- **info / honesty-negative** `CHANGELOG.md:273` — - HitDef track sheet export and apply with CNS backup.
- **high / binary-fullness** `CHANGELOG.md:283` — - Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented.
- **high / engine-authority** `CHANGELOG.md:286` — - Timeline, graph, palette, stage, frame-data, and dashboard reports are source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:287` — - Sound cue insertion edits source code only; it does not mutate SND binary banks.
- **info / honesty-negative** `CHANGELOG.md:288` — - Palette Studio writes ACT variants but does not patch SFF palette tables.
- **high / engine-authority** `CHANGELOG.md:289` — - Stage Live Preview is approximate and does not emulate M.U.G.E.N rendering, parallax, or BGCtrl timing authoritatively.
- **info / honesty-negative** `CHANGELOG.md:298` — - One-Click Polish Pass for dashboarding, sheet validation, sound cue sheet export, timeline preview, state graph artifacts, template validation, stage preview, backup history, and report bundling.
- **medium / plugin-execution** `CHANGELOG.md:304` — - Data-only template/plugin validation and import workflow.
- **info / honesty-negative** `CHANGELOG.md:306` — - Backup history browser, individual backup restore helper, and pre-restore guard copies.
- **medium / safety-claim** `CHANGELOG.md:315` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:323` — - Editable sound cue sheet export/apply with backup creation.
- **info / honesty-negative** `CHANGELOG.md:328` — - Backup history indexing.
- **high / binary-fullness** `CHANGELOG.md:335` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **high / engine-authority** `CHANGELOG.md:339` — - Balance/frame-data/graph/dashboard reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:340` — - Plugin/template support remains data/metadata based and does not run arbitrary downloaded Python code.
- **medium / plugin-execution** `CHANGELOG.md:356` — - Metadata-only template/plugin foundation.
- **medium / safety-claim** `CHANGELOG.md:368` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:384` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **high / engine-authority** `CHANGELOG.md:388` — - Balance/frame-data/graph reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:389` — - Plugin/template support remains metadata/preset based and does not run arbitrary downloaded Python code.
- **medium / safety-claim** `CHANGELOG.md:411` — - Added read-only SFF axis reference display where safe inspection is supported.
- **high / binary-fullness** `CHANGELOG.md:412` — - Kept SFF2 binary axis mutation honest: arbitrary SFF2 binary axis patching is not implemented.
- **medium / safety-claim** `CHANGELOG.md:417` — - Added StateDef discovery, PlaySnd cue insertion by AnimElem, and backup-safe code mutation.
- **medium / safety-claim** `CHANGELOG.md:424` — - Added optional append-to-project behavior using existing backup-safe Move Wizard paths.
- **medium / safety-claim** `CHANGELOG.md:435` — - Added one-click install for the existing safe debug overlay preset plus Visual Forge docs/config.
- **medium / plugin-execution** `CHANGELOG.md:437` — ### Plugin / Template Architecture
- **medium / plugin-execution** `CHANGELOG.md:440` — - Added data-only no-code template manifest and plugin manifest scaffolds.
- **medium / plugin-execution** `CHANGELOG.md:441` — - Explicitly kept arbitrary third-party Python plugin execution disabled.
- **high / binary-fullness** `CHANGELOG.md:446` — - Source-based Sprmake2 handoff remains the supported SFF2 path; full arbitrary SFF2 binary rebuilding is still not claimed.
- **info / honesty-negative** `CHANGELOG.md:448` — ### Central Backup / Undo / Error-Log System
- **medium / safety-claim** `CHANGELOG.md:461` — ### Verified
- **medium / plugin-execution** `CHANGELOG.md:472` — - Template/plugin scaffold generation.
- **info / honesty-negative** `CHANGELOG.md:473` — - Backup snapshot generation.
- **high / binary-fullness** `CHANGELOG.md:478` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **medium / safety-claim** `CHANGELOG.md:479` — - SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- **high / binary-fullness** `CHANGELOG.md:480` — - Mature existing-SFF/SND binary mutation remains conservative.
- **high / engine-authority** `CHANGELOG.md:482` — - Visual timeline and balance/frame reports are source-derived estimates, not engine-authoritative measurements.
- **info / honesty-negative** `CHANGELOG.md:491` — - Embedded PNG/PCX/WAV scanning from unsupported or packed projects.
- **medium / safety-claim** `CHANGELOG.md:508` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:521` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **medium / safety-claim** `CHANGELOG.md:522` — - SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- **medium / safety-claim** `CHANGELOG.md:552` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:564` — - Full mature SFF v2 extraction/rebuild is not implemented.
- **high / binary-fullness** `CHANGELOG.md:565` — - Mature existing-SFF/SND binary mutation remains conservative.
- **medium / safety-claim** `CHANGELOG.md:575` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:618` — - Full mature SFF v2 extraction/rebuild is not implemented.
- **high / binary-fullness** `CHANGELOG.md:657` — - Full SFF v2 extraction/rebuild remains incomplete.
- **high / binary-fullness** `CHANGELOG.md:658` — - Mature existing-SFF/SND binary mutation remains conservative.
- **medium / safety-claim** `docs/MUGENFORGE_HANDOFF_v3_5.md:29` — MugenForge Studio remains a clean-room Python/Tkinter M.U.G.E.N character/stage editor. The v3.5 focus is beginner onboarding and visual workflows: the user makes creative decisions while the tool writes safe scaffolds, guides, manifests, backups, reports, and source-based asset handoff files.
- **medium / plugin-execution** `docs/MUGENFORGE_HANDOFF_v3_5.md:40` — - Data-only plugin/template foundation.
- **info / honesty-negative** `docs/MUGENFORGE_HANDOFF_v3_5.md:42` — - Central backup, restore, and error-log tab.
- **medium / fighter-factory-reference** `docs/MUGENFORGE_HANDOFF_v3_5.md:46` — - Clean-room only. Do not use Fighter Factory / VirtuallTek source code or proprietary assets.
- **high / binary-fullness** `docs/MUGENFORGE_HANDOFF_v3_5.md:48` — - Full arbitrary mature SFF v2 binary extraction/rebuild is still not implemented.
- **high / binary-fullness** `docs/MUGENFORGE_HANDOFF_v3_5.md:49` — - SFF2 Bridge is a source project / Sprmake2 handoff workflow, not internal arbitrary SFF2 mutation.
- **high / engine-authority** `docs/MUGENFORGE_HANDOFF_v3_5.md:51` — - Balance and frame-data reports are estimates/source-derived, not engine-authoritative.
- **medium / safety-claim** `docs/MUGENFORGE_HANDOFF_v3_5.md:78` — - Replace placeholder timeline tile art with sprite-backed thumbnails where safe sprite extraction or source images are available.
- **medium / fighter-factory-reference** `docs/MUGENFORGE_HANDOFF_v4_0.md:32` — - Do not use or reference proprietary Fighter Factory / VirtuallTek source code or assets.
- **high / binary-fullness** `docs/MUGENFORGE_HANDOFF_v4_0.md:33` — - Do not claim arbitrary mature SFF v2 binary extraction/rebuild; it is still not implemented.
- **high / engine-authority** `docs/MUGENFORGE_HANDOFF_v4_0.md:37` — - Frame-data, graph, and balance reports are source-analysis aids and estimates, not engine-authoritative runtime telemetry.
- **medium / plugin-execution** `docs/MUGENFORGE_HANDOFF_v4_0.md:38` — - Plugin/template support is metadata/preset based; do not auto-run untrusted downloaded Python code.
- **medium / plugin-execution** `docs/MUGENFORGE_HANDOFF_v4_0.md:74` — - Template / Plugin Foundation
- **medium / plugin-execution** `docs/MUGENFORGE_HANDOFF_v4_0.md:121` — - Ran state graph, variable usage, sprite/sound cross-reference, template/plugin, stage authoring, image editor, archive import, and reports ZIP workflows.
- **medium / safety-claim** `docs/MUGENFORGE_HANDOFF_v4_0.md:122` — - Verified dashboard, unified index, capability matrix, state graph HTML, command sheet, AIR batch sheet, variable map, template manifest, and stage authoring pack outputs exist.
