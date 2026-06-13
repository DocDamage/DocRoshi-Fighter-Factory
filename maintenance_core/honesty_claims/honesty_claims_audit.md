# Honesty Claims Audit

Generated: 2026-06-13T19:18:19

This is a text scan, not a legal review. It flags statements that future developers should keep accurate.

- Rows: 2370
- High-risk rows: 352
- Medium-risk rows: 748

## Required truth rules for future releases

- Do not claim full arbitrary SFF2 support unless validated against a broad real-world corpus.
- Do not call static reports engine-authoritative unless backed by actual engine evidence.
- Keep candidate/backup-first wording for binary mutation unless direct install is proven safe.
- Do not auto-run untrusted community Python plugins without a genuine sandbox.

## First 100 flagged lines

- **info / honesty-negative** `CHANGELOG.md:14` — - Explicit binary mutation commit/install sheets with candidate verification, commit tokens, rollback snapshots, and restore workflow.
- **info / honesty-negative** `CHANGELOG.md:23` — - Binary mutation workflows now include explicit reviewed commits, hashes, backups, and rollback snapshots instead of only candidate generation.
- **medium / safety-claim** `CHANGELOG.md:26` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:40` — - MugenForge does not bundle M.U.G.E.N or IKEMEN.
- **medium / safety-claim** `CHANGELOG.md:44` — - Blind overwrites remain blocked; verified binary writes use backups and explicit opt-in sheets.
- **info / honesty-negative** `CHANGELOG.md:56` — - Optional State `-2` DisplayToClipboard/AppendToClipboard debug overlay installer with backup.
- **info / honesty-negative** `CHANGELOG.md:68` — - The recommended late-project loop is now: generate launcher/test plan, run the external engine, collect logs/evidence, parse logs, and regenerate readiness.
- **medium / safety-claim** `CHANGELOG.md:70` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:76` — - Debug overlay backup/append behavior.
- **high / engine-authority** `CHANGELOG.md:86` — - MugenForge does not emulate or simulate M.U.G.E.N/IKEMEN.
- **high / engine-authority** `CHANGELOG.md:88` — - Runtime readiness is an evidence aid, not engine-authoritative certification.
- **info / honesty-negative** `CHANGELOG.md:90` — - Binary SFF/SND mutation remains candidate/backup-first and avoids blind overwrites.
- **info / honesty-negative** `CHANGELOG.md:97` — - Decoded SFF2 export for PNG, raw indexed/truecolor, RLE8, RLE5, and LZ5 candidate paths.
- **info / honesty-negative** `CHANGELOG.md:98` — - Standard SFF2 candidate builder from source manifests.
- **info / honesty-negative** `CHANGELOG.md:112` — - Candidate SFF2/SND outputs still require target-engine testing.
- **info / honesty-negative** `CHANGELOG.md:122` — - SFF2 edit workspace export/apply for supported axis/source-image edits and rebuilt candidate copies.
- **medium / safety-claim** `CHANGELOG.md:134` — - Native SFF2 output is now a controlled table-backed writer path verified by MugenForge parser/export round trips, not the earlier private PNG-subset experiment.
- **medium / safety-claim** `CHANGELOG.md:137` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:145` — - SND slot patch sheet export and copied patch candidate apply.
- **medium / safety-claim** `CHANGELOG.md:152` — - v5.5 codec coverage is verified on controlled fixtures; broad real-world corpus validation remains necessary.
- **info / honesty-negative** `CHANGELOG.md:154` — - Binary mutation workflows write candidate copies/backups first; blind overwrite is intentionally avoided.
- **medium / safety-claim** `CHANGELOG.md:165` — - Supported SFF v1 payload extraction, conservative embedded PNG discovery, and MugenForge PNG-subset SFF2 payload extraction where records can be verified.
- **info / honesty-negative** `CHANGELOG.md:169` — - Rebuilt SND candidate generation from WAV payloads, leaving the current SND untouched until manually installed/tested.
- **medium / safety-claim** `CHANGELOG.md:179` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:189` — - SND bank sheet export and rebuilt-candidate apply.
- **high / binary-fullness** `CHANGELOG.md:196` — - Full arbitrary mature SFF v2 extraction/rebuild/mutation is still not implemented.
- **info / honesty-negative** `CHANGELOG.md:198` — - SFF axis apply creates patched copies; it does not blindly overwrite the original SFF.
- **info / honesty-negative** `CHANGELOG.md:200` — - SFF2 release rebuild remains source/Sprmake2 based; the experimental MugenForge PNG-subset copy is for pipeline testing only.
- **medium / safety-claim** `CHANGELOG.md:224` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:231` — - Move timeline sheet export and apply with AIR backup plus PlaySnd insertion.
- **info / honesty-negative** `CHANGELOG.md:232` — - CLSN track sheet export and apply with AIR backup.
- **info / honesty-negative** `CHANGELOG.md:233` — - HitDef track sheet export and apply with CNS backup.
- **high / binary-fullness** `CHANGELOG.md:243` — - Full mature arbitrary SFF v2 extraction/rebuild/mutation is still not implemented.
- **high / engine-authority** `CHANGELOG.md:246` — - Timeline, graph, palette, stage, frame-data, and dashboard reports are source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:247` — - Sound cue insertion edits source code only; it does not mutate SND binary banks.
- **info / honesty-negative** `CHANGELOG.md:248` — - Palette Studio writes ACT variants but does not patch SFF palette tables.
- **high / engine-authority** `CHANGELOG.md:249` — - Stage Live Preview is approximate and does not emulate M.U.G.E.N rendering, parallax, or BGCtrl timing authoritatively.
- **info / honesty-negative** `CHANGELOG.md:258` — - One-Click Polish Pass for dashboarding, sheet validation, sound cue sheet export, timeline preview, state graph artifacts, template validation, stage preview, backup history, and report bundling.
- **medium / plugin-execution** `CHANGELOG.md:264` — - Data-only template/plugin validation and import workflow.
- **info / honesty-negative** `CHANGELOG.md:266` — - Backup history browser, individual backup restore helper, and pre-restore guard copies.
- **medium / safety-claim** `CHANGELOG.md:275` — ### Verified
- **info / honesty-negative** `CHANGELOG.md:283` — - Editable sound cue sheet export/apply with backup creation.
- **info / honesty-negative** `CHANGELOG.md:288` — - Backup history indexing.
- **high / binary-fullness** `CHANGELOG.md:295` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **high / engine-authority** `CHANGELOG.md:299` — - Balance/frame-data/graph/dashboard reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:300` — - Plugin/template support remains data/metadata based and does not run arbitrary downloaded Python code.
- **medium / plugin-execution** `CHANGELOG.md:316` — - Metadata-only template/plugin foundation.
- **medium / safety-claim** `CHANGELOG.md:328` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:344` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **high / engine-authority** `CHANGELOG.md:348` — - Balance/frame-data/graph reports are estimates/source-analysis aids, not engine-authoritative runtime telemetry.
- **info / honesty-negative** `CHANGELOG.md:349` — - Plugin/template support remains metadata/preset based and does not run arbitrary downloaded Python code.
- **medium / safety-claim** `CHANGELOG.md:371` — - Added read-only SFF axis reference display where safe inspection is supported.
- **high / binary-fullness** `CHANGELOG.md:372` — - Kept SFF2 binary axis mutation honest: arbitrary SFF2 binary axis patching is not implemented.
- **medium / safety-claim** `CHANGELOG.md:377` — - Added StateDef discovery, PlaySnd cue insertion by AnimElem, and backup-safe code mutation.
- **medium / safety-claim** `CHANGELOG.md:384` — - Added optional append-to-project behavior using existing backup-safe Move Wizard paths.
- **medium / safety-claim** `CHANGELOG.md:395` — - Added one-click install for the existing safe debug overlay preset plus Visual Forge docs/config.
- **medium / plugin-execution** `CHANGELOG.md:397` — ### Plugin / Template Architecture
- **medium / plugin-execution** `CHANGELOG.md:400` — - Added data-only no-code template manifest and plugin manifest scaffolds.
- **medium / plugin-execution** `CHANGELOG.md:401` — - Explicitly kept arbitrary third-party Python plugin execution disabled.
- **high / binary-fullness** `CHANGELOG.md:406` — - Source-based Sprmake2 handoff remains the supported SFF2 path; full arbitrary SFF2 binary rebuilding is still not claimed.
- **info / honesty-negative** `CHANGELOG.md:408` — ### Central Backup / Undo / Error-Log System
- **medium / safety-claim** `CHANGELOG.md:421` — ### Verified
- **medium / plugin-execution** `CHANGELOG.md:432` — - Template/plugin scaffold generation.
- **info / honesty-negative** `CHANGELOG.md:433` — - Backup snapshot generation.
- **high / binary-fullness** `CHANGELOG.md:438` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **medium / safety-claim** `CHANGELOG.md:439` — - SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- **high / binary-fullness** `CHANGELOG.md:440` — - Mature existing-SFF/SND binary mutation remains conservative.
- **high / engine-authority** `CHANGELOG.md:442` — - Visual timeline and balance/frame reports are source-derived estimates, not engine-authoritative measurements.
- **info / honesty-negative** `CHANGELOG.md:451` — - Embedded PNG/PCX/WAV scanning from unsupported or packed projects.
- **medium / safety-claim** `CHANGELOG.md:468` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:481` — - Full mature arbitrary SFF v2 extraction/rebuild is not implemented.
- **medium / safety-claim** `CHANGELOG.md:482` — - SFF2 Bridge creates source projects for external Sprmake2 use; it is not byte-perfect SFF2 binary mutation.
- **medium / safety-claim** `CHANGELOG.md:512` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:524` — - Full mature SFF v2 extraction/rebuild is not implemented.
- **high / binary-fullness** `CHANGELOG.md:525` — - Mature existing-SFF/SND binary mutation remains conservative.
- **medium / safety-claim** `CHANGELOG.md:535` — ### Verified
- **high / binary-fullness** `CHANGELOG.md:578` — - Full mature SFF v2 extraction/rebuild is not implemented.
- **high / binary-fullness** `CHANGELOG.md:617` — - Full SFF v2 extraction/rebuild remains incomplete.
- **high / binary-fullness** `CHANGELOG.md:618` — - Mature existing-SFF/SND binary mutation remains conservative.
- **info / honesty-negative** `handoff_core/HANDOFF_CORE_START_HERE.md:13` — This system does not replace real tests or engine playtesting. It makes continuity safer and easier.
- **medium / safety-claim** `handoff_core/MUGENFORGE_DEVELOPMENT_HANDOFF_v7_5.md:29` — ## Safe run/test commands
- **medium / fighter-factory-reference** `handoff_core/NEXT_CHAT_PROMPT_v7_5.md:15` — - Clean-room only; do not use Fighter Factory / VirtualTek source code or assets.
- **info / honesty-negative** `handoff_core/NEXT_CHAT_PROMPT_v7_5.md:16` — - Keep binary mutation backup/candidate-first and refuse unsafe unknown layouts.
- **info / honesty-negative** `handoff_core/NEXT_CHAT_PROMPT_v7_5.md:17` — - External engine evidence is required for final runtime confidence.
- **high / engine-authority** `handoff_core/NEXT_CHAT_PROMPT_v7_5.md:18` — - Static/source simulation reports are preflight aids, not engine-authoritative results.
- **medium / fighter-factory-reference** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:14` — - Clean-room only. Do not use or claim Fighter Factory / VirtuallTek source, assets, or proprietary logic.
- **high / engine-authority** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:16` — - Do not claim static reports are engine-authoritative unless backed by external engine evidence.
- **medium / safety-claim** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:17` — - Do not blindly overwrite user binaries; preserve candidate/backup/verified install workflows.
- **medium / plugin-execution** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:18` — - Do not auto-run untrusted third-party Python plugins.
- **info / honesty-negative** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:34` — - v3.5 Visual Forge: beginner home, timeline, axis, sound cue, migration, backup logs.
- **info / honesty-negative** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:36` — - v4.1 Forge Polish: validation previews, sound cue apply, sprite-backed preview, backup history.
- **info / honesty-negative** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:38` — - v5.0 Binary Core: conservative SFF/SND binary inspection and candidate workflows.
- **info / honesty-negative** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:40` — - v6.1 Runtime Lab: external engine launchers, logs, evidence, readiness reports.
- **medium / safety-claim** `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md:41` — - v7.0 Evidence Core line: gap closure, authority/evidence labs, source runtime modeling, corpus validation, verified installs.
- **info / honesty-negative** `maintenance_core/honesty_claims/honesty_claims_audit.csv:2` — info,honesty-negative,CHANGELOG.md,14,"- Explicit binary mutation commit/install sheets with candidate verification, commit tokens, rollback snapshots, and restore workflow."
- **info / honesty-negative** `maintenance_core/honesty_claims/honesty_claims_audit.csv:3` — info,honesty-negative,CHANGELOG.md,23,"- Binary mutation workflows now include explicit reviewed commits, hashes, backups, and rollback snapshots instead of only candidate generation."
- **medium / safety-claim** `maintenance_core/honesty_claims/honesty_claims_audit.csv:4` — medium,safety-claim,CHANGELOG.md,26,### Verified
- **info / honesty-negative** `maintenance_core/honesty_claims/honesty_claims_audit.csv:5` — info,honesty-negative,CHANGELOG.md,40,- MugenForge does not bundle M.U.G.E.N or IKEMEN.
- **medium / safety-claim** `maintenance_core/honesty_claims/honesty_claims_audit.csv:6` — medium,safety-claim,CHANGELOG.md,44,- Blind overwrites remain blocked; verified binary writes use backups and explicit opt-in sheets.
- **info / honesty-negative** `maintenance_core/honesty_claims/honesty_claims_audit.csv:7` — info,honesty-negative,CHANGELOG.md,56,- Optional State `-2` DisplayToClipboard/AppendToClipboard debug overlay installer with backup.
