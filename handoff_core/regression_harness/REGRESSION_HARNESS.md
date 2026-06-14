# v7.5 Regression Harness

Run from the package root:

```bash
python handoff_core/regression_harness/smoke_v7_5.py
```

Optional UI smoke on Linux:

```bash
xvfb-run -a python - <<'PY'
from mugenforge.app import MugenForgeApp, APP_TITLE
app = MugenForgeApp()
tabs = [app.notebook.tab(t, 'text') for t in app.notebook.tabs()]
print(APP_TITLE)
print('Operator Console' in tabs)
print('Handoff Core' in tabs)
print(len(tabs))
app.destroy()
PY
```
