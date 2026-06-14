# MugenForge Maintenance Backlog after v7.5

Generated: 2026-06-14T00:15:01

## Immediate cleanup

- Continue consolidating module-backed tabs into role modes; `app.py` is now split into state, shell, tab-builder, and action modules.
- Extend the real test suite around controlled SFF/SND fixtures and risky backend workflows.
- Add sample projects with small permissive assets for repeatable visual/binary tests.
- Add a CI-friendly headless UI test using Xvfb where available.
- Consolidate duplicate workflow tabs into role modes: Beginner, Visual, Binary, Runtime, Release, Maintenance.

## Binary roadmap

- Expand SFF2 corpus validation with many real-world files and preserve hash-based support buckets.
- Document exact supported SFF2 encodings and table variants in one codec spec file.
- Add mutation rollback tests for axis, palette, sprite replacement, and SND replacement candidates.

## Runtime roadmap

- Add external-engine profile presets for common M.U.G.E.N/IKEMEN builds.
- Convert manual regression checklists into scenario files that Runtime/Evidence Core can execute or track.
- Add log pattern packs per engine family.

## UX roadmap

- Make Project Home the default cockpit and hide advanced labs behind mode toggles.
- Add a searchable command palette for actions instead of relying on dozens of tabs.
- Add guided fix buttons from dashboards into the relevant editors.

## Release engineering

- Create Windows portable builds after the Python package stabilizes.
- Add a package manifest with file hashes to every release ZIP.
- Keep handoff, changelog, release summary, and test results in sync before every artifact delivery.
