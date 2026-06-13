# Handoff Core Start Here

Open these in order:

1. `handoff_core/digest/CONTEXT_DIGEST.md`
2. `handoff_core/handoff/NEXT_CHAT_PROMPT.md`
3. `handoff_core/handoff/CURRENT_STATE_HANDOFF.md`
4. `handoff_core/inventory/PACKAGE_INVENTORY.md`
5. `handoff_core/roadmap/ROADMAP_BACKLOG.md`
6. `handoff_core/scope/HONEST_SCOPE_LEDGER.md`
7. `handoff_core/regression_harness/REGRESSION_HARNESS.md`

Then run:

```bash
python -m compileall -q mugenforge
python handoff_core/regression_harness/smoke_v7_5.py
```
