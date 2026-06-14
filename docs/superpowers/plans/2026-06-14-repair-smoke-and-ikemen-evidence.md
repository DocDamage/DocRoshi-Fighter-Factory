# Repair Smoke And IKEMEN Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a compiling MugenForge Studio checkout, connect Evidence Core to the local IKEMEN checkout when possible, and refresh generated project state.

**Architecture:** Keep code changes narrow: add reusable safe filename helpers near the call sites that currently fail compilation, cover them with smoke tests, and use existing Operator/Maintenance/Handoff backends to regenerate artifacts. Evidence Core remains external-engine driven; this plan only writes/validates a profile if a local IKEMEN executable can be discovered.

**Tech Stack:** Python 3, unittest, compileall, Tkinter app modules, MugenForge Evidence Core/Operator/Maintenance/Handoff backends.

---

### Task 1: Regression Tests For Compile-Safe Names

**Files:**
- Modify: `tests/test_smoke_v7_5.py`
- Modify: `mugenforge/evidence_core.py`
- Modify: `mugenforge/ui_actions/visual_forge.py`

- [ ] **Step 1: Write failing tests**

Add tests that import the affected modules and assert their helper functions normalize unsafe names without using inline raw regexes in f-strings.

```python
    def test_safe_runtime_profile_name(self):
        from mugenforge.evidence_core import _safe_run_name

        self.assertEqual(_safe_run_name('boot character smoke'), 'boot_character_smoke')
        self.assertEqual(_safe_run_name('name/with:bad*chars'), 'name_with_bad_chars')
        self.assertEqual(_safe_run_name('***'), 'profile')

    def test_safe_move_preview_name(self):
        from mugenforge.ui_actions.visual_forge import _safe_preview_name

        self.assertEqual(_safe_preview_name('Hadoken EX'), 'Hadoken_EX')
        self.assertEqual(_safe_preview_name('move/with:bad*chars'), 'move_with_bad_chars')
        self.assertEqual(_safe_preview_name('***'), 'move')
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_smoke_v7_5.MugenForgeSmokeTests.test_safe_runtime_profile_name tests.test_smoke_v7_5.MugenForgeSmokeTests.test_safe_move_preview_name -v`

Expected: failure or import error because `mugenforge.evidence_core` and `mugenforge.ui_actions.visual_forge` currently do not compile.

- [ ] **Step 3: Implement helpers and replace inline f-string regexes**

In `mugenforge/evidence_core.py`, add:

```python
def _safe_run_name(value: object, default: str = 'profile') -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', str(value or '')).strip('_')
    return safe or default
```

Replace the failing run directory expression with:

```python
    run_name = _safe_run_name(selected.get('name', 'profile'))
    run_dir = out / f'{tag}_{run_name}'
```

In `mugenforge/ui_actions/visual_forge.py`, add:

```python
def _safe_preview_name(value: object, default: str = 'move') -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', str(value or '')).strip('_')
    return safe or default
```

Replace the failing preview path expression with:

```python
        preview_name = _safe_preview_name(spec.move_name)
        out = self.project_root / 'visual_forge' / 'move_composer' / f'{preview_name}_preview.txt'
```

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `python -m unittest tests.test_smoke_v7_5.MugenForgeSmokeTests.test_safe_runtime_profile_name tests.test_smoke_v7_5.MugenForgeSmokeTests.test_safe_move_preview_name -v`

Expected: both tests pass.

### Task 2: Full Smoke Verification

**Files:**
- No production file edits expected after Task 1.

- [ ] **Step 1: Run compileall**

Run: `python -m compileall -q mugenforge`

Expected: exit code 0.

- [ ] **Step 2: Run smoke script**

Run: `python tools/run_mugenforge_smoke.py`

Expected: prints `SMOKE_PASS`.

- [ ] **Step 3: Run unittest smoke suite**

Run: `python -m unittest tests.test_smoke_v7_5 -v`

Expected: tests pass, with Tk UI test skipped if no display is available.

### Task 3: IKEMEN Evidence Profile Discovery

**Files:**
- Generated/modify: `evidence_core/engine/engine_profile.json` if an IKEMEN executable exists locally.
- Generated/modify: `evidence_core/engine/engine_profile_validation.json`
- Generated/modify: `evidence_core/engine/ENGINE_PROFILE_VALIDATION.md`

- [ ] **Step 1: Locate IKEMEN checkout**

Run: search likely local locations under the user desktop/profile for `Ikemen-GO` directories and `Ikemen_GO.exe` or similar executable names.

Expected: either a usable executable path is found, or the final report names the search result and leaves engine profile setup as a user-action item.

- [ ] **Step 2: Configure profile when executable exists**

Use `mugenforge.evidence_core.configure_engine_profile(...)` if a local executable is found. Set `engine_kind` to `ikemen`, `engine_executable` to the executable, and `working_directory` to its parent folder.

- [ ] **Step 3: Validate profile**

Run `mugenforge.evidence_core.validate_engine_profile(Path('.'))`.

Expected: valid when executable exists; otherwise generated template remains blocked with a clear warning.

### Task 4: Refresh Operator, Maintenance, And Handoff Artifacts

**Files:**
- Generated/modify: `operator_console/*`
- Generated/modify: `maintenance_core/*`
- Generated/modify: `handoff_core/*`

- [ ] **Step 1: Run Operator Console pass**

Run existing backend function `run_operator_console_pass(Path('.'))`.

- [ ] **Step 2: Run Maintenance Core pass**

Run existing backend function `run_maintenance_core_pass(Path('.'))`.

- [ ] **Step 3: Run Handoff Core pass**

Run existing backend function `run_handoff_core_pass(Path('.'))`.

- [ ] **Step 4: Re-run verification**

Run compileall and smoke script again after generated artifact refresh.

Expected: exit code 0 for both commands.

### Task 5: Final State Report

**Files:**
- No file edits.

- [ ] **Step 1: Check git status**

Run: `git status --short`

- [ ] **Step 2: Summarize completed work**

Report syntax repair, tests, generated artifacts, IKEMEN profile status, and remaining product-scale items.

- [ ] **Step 3: Keep remaining work honest**

Do not claim completion for external-engine runs, corpus validation, installer packaging, or real character asset creation unless this pass actually completed them with evidence.
