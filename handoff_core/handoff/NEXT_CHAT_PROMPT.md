# Copy/paste prompt for next chat

I am continuing **MugenForge Studio v7.5 Continuity Core**, a clean-room Python/Tkinter M.U.G.E.N character/stage editor and no-code creator suite.

Please continue from the uploaded package `mugenforge_studio_v7_5.zip`. Unzip it, inspect the code, run smoke tests, and continue development from that exact package rather than starting over.

## Current version

- Package version: `7.5.0`
- App title: `MugenForge Studio 7.5 Continuity Core`
- Run command: `python -m mugenforge.app`
- Windows launcher: `run_windows.bat`
- Dependencies: `pip install -r requirements.txt`

## Start here

1. Read `MUGENFORGE_HANDOFF_v7_5.md`.
2. Read `handoff_core/HANDOFF_CORE_START_HERE.md`.
3. Run `python -m compileall -q mugenforge`.
4. Run `python handoff_core/regression_harness/smoke_v7_5.py`.
5. Open the UI; start from **Operator Console** and **Handoff Core**.

## Critical next work

- Continue consolidating module-backed tabs into role-based workspaces.
- Extend the real tests folder beyond smoke checks with focused SFF/SND fixtures.
- Run binary corpus validation on diverse real SFF/SND files.
- Consolidate the UI into role-based workspaces.
- Keep all feature claims honest and clean-room.
