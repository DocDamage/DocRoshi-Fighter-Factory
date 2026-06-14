# MugenForge Studio v4.0 Forge Beyond — Release Summary

## What was built

MugenForge Studio v4.0 adds a new **Forge Beyond** clean-room parity+ layer. It targets public Fighter Factory-style M.U.G.E.N authoring workflows while keeping MugenForge's own implementation, UI, reports, and data models.

Major additions:

- Forge Beyond tab in the Tkinter app.
- New backend module: `mugenforge/forge_beyond.py`.
- Clean-room capability matrix.
- Unified project index.
- Command editor sheet export/apply workflow.
- AIR batch sheet export/apply workflow.
- State graph HTML/CSV output.
- Variable usage map.
- Sprite/sound cross-reference report.
- Template/plugin foundation.
- Stage authoring pack.
- Source image editor helper.
- ZIP project import helper.
- Forge Beyond dashboard and reports bundle.
- Start-here documentation and updated handoff.

## Why it was built

The user requested the broad capabilities associated with a Fighter Factory-style workflow and wanted MugenForge to go beyond them. v4.0 does that as a clean-room implementation: it expands practical authoring coverage without copying proprietary code/assets and without overstating risky binary capabilities.

## Run/test commands

```bash
pip install -r requirements.txt
python -m mugenforge.app
```

Compile/test:

```bash
python -m compileall -q ./mugenforge
xvfb-run -a python - <<'PY'
from mugenforge.app import MugenForgeApp
app = MugenForgeApp()
print(app.title())
print('Forge Beyond' in [app.notebook.tab(t, 'text') for t in app.notebook.tabs()])
app.destroy()
PY
```

## Honest limitations retained

- Full mature arbitrary SFF v2 extraction/rebuild/mutation is not implemented.
- SFF2 work remains source-project/bridge based where practical.
- Generated gameplay code requires real M.U.G.E.N playtesting.
- Frame/balance/graph reports are source-analysis aids, not engine-authoritative telemetry.
- Plugin/template architecture remains metadata/data-first and does not auto-run untrusted community Python code.
