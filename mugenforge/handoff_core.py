from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import ast
import csv
import hashlib
import json
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence

try:
    from . import __version__ as PACKAGE_VERSION
except Exception:  # pragma: no cover
    PACKAGE_VERSION = '7.5.0'

HANDOFF_CORE_VERSION = '7.5.0'
TEXT_EXTS = {'.py', '.md', '.txt', '.csv', '.json', '.bat', '.sh', '.ini', '.cfg', '.toml'}
SKIP_DIRS = {'__pycache__', '.git', '.hg', '.svn', '.pytest_cache', 'build', 'dist'}


@dataclass
class HandoffResult:
    title: str = 'Handoff Core Result'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, message: object) -> None:
        self.warnings.append(str(message))

    def add_note(self, message: object) -> None:
        self.notes.append(str(message))

    def merge(self, other: object, label: Optional[str] = None) -> None:
        if other is None:
            return
        prefix = f'{label}: ' if label else ''
        for attr in ('created_files', 'changed_files', 'skipped_files', 'warnings', 'notes'):
            vals = getattr(other, attr, []) or []
            getattr(self, attr).extend(prefix + str(v) for v in vals)

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        for label, values in [
            ('Notes', self.notes),
            ('Created files/artifacts', self.created_files),
            ('Changed files', self.changed_files),
            ('Skipped', self.skipped_files),
            ('Warnings', self.warnings),
        ]:
            uniq = _uniq(values)
            if uniq:
                lines.append(label + ':')
                lines.extend(f'- {x}' for x in uniq)
                lines.append('')
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


HandoffCoreResult = HandoffResult


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _out(root: Path, *parts: str) -> Path:
    path = Path(root) / 'handoff_core'
    for part in parts:
        path = path / part
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(root: Path, path: Path, text: str, result: Optional[HandoffResult] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(text.rstrip() + '\n', encoding='utf-8')
    if result is not None:
        if existed:
            result.add_changed(root, path)
        else:
            result.add_created(root, path)
    return path


def _write_json(root: Path, path: Path, data: object, result: Optional[HandoffResult] = None) -> Path:
    return _write(root, path, json.dumps(data, indent=2, ensure_ascii=False), result)


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], result: Optional[HandoffResult] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for row in rows:
            w.writerow({field: row.get(field, '') for field in fields})
    if result is not None:
        if existed:
            result.add_changed(root, path)
        else:
            result.add_created(root, path)
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> List[Path]:
    files: List[Path] = []
    root = Path(root)
    for p in sorted(root.rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_EXTS or p.name.lower() in {'requirements.txt', 'run_windows.bat'}:
            files.append(p)
    return files


def _module_summary(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding='utf-8', errors='replace')
    row: Dict[str, object] = {
        'module': path.name,
        'path': str(path),
        'bytes': path.stat().st_size,
        'lines': len(text.splitlines()),
        'classes': 0,
        'functions': 0,
        'constants': '',
        'syntax_error': '',
        'sha256': _sha256(path),
    }
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        row['syntax_error'] = f'{exc.msg} at line {exc.lineno}'
        return row
    classes: List[str] = []
    funcs: List[str] = []
    constants: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
    row.update({
        'module': path.stem,
        'classes': len(classes),
        'functions': len(funcs),
        'class_names': ', '.join(classes[:20]),
        'function_names': ', '.join(funcs[:30]),
        'constants': ', '.join(constants[:30]),
    })
    return row


def _find_app_title(root: Path) -> str:
    app = root / 'mugenforge' / 'app.py'
    if not app.exists():
        return ''
    m = re.search(r"APP_TITLE\s*=\s*['\"]([^'\"]+)['\"]", app.read_text(encoding='utf-8', errors='replace'))
    return m.group(1) if m else ''


def _tab_names(root: Path) -> List[str]:
    app = root / 'mugenforge' / 'app.py'
    if not app.exists():
        return []
    text = app.read_text(encoding='utf-8', errors='replace')
    return re.findall(r"notebook\.add\([^\n]+text\s*=\s*['\"]([^'\"]+)['\"]", text)


def _project_summary(root: Path) -> Dict[str, object]:
    root = Path(root)
    counts: Dict[str, int] = {}
    if not root.exists():
        return {'root': str(root), 'exists': False}
    for p in root.rglob('*'):
        if p.is_file():
            counts[p.suffix.lower() or '[none]'] = counts.get(p.suffix.lower() or '[none]', 0) + 1
    core: Dict[str, List[str]] = {}
    for ext in ['.def', '.air', '.cmd', '.cns', '.st', '.sff', '.snd']:
        core[ext] = [_rel(root, p) for p in sorted(root.rglob(f'*{ext}'))[:30]]
    return {'root': str(root), 'exists': True, 'extension_counts': dict(sorted(counts.items())), 'core_files': core}


def _is_package_root(root: Path) -> bool:
    return (root / 'mugenforge' / 'app.py').exists()


def _package_root_for(root: Path) -> Path:
    root = Path(root)
    if _is_package_root(root):
        return root
    return Path(__file__).resolve().parents[1]


def collect_package_inventory(root: Path) -> Dict[str, object]:
    package_root = _package_root_for(root)
    module_rows: List[Dict[str, object]] = []
    text_rows: List[Dict[str, object]] = []
    for p in _iter_files(package_root):
        rel = _rel(package_root, p)
        if p.suffix.lower() == '.py':
            row = _module_summary(p)
            row['path'] = rel
            module_rows.append(row)
        else:
            text_rows.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': _sha256(p)})
    tabs = _tab_names(package_root)
    return {
        'tool': 'MugenForge Studio',
        'package_version': PACKAGE_VERSION,
        'handoff_core_version': HANDOFF_CORE_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'package_root': str(package_root),
        'app_title': _find_app_title(package_root),
        'tabs': tabs,
        'tab_count': len(tabs),
        'module_count': len(module_rows),
        'total_python_lines': sum(int(row.get('lines') or 0) for row in module_rows),
        'modules': module_rows,
        'text_artifacts': text_rows,
        'handoff_target_summary': _project_summary(root),
    }


def write_package_inventory(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Package Inventory')
    inv = collect_package_inventory(root)
    out = _out(root, 'inventory')
    _write_json(root, out / 'package_inventory.json', inv, result)
    fields = ['path', 'bytes', 'lines', 'classes', 'functions', 'syntax_error', 'class_names', 'function_names', 'constants', 'sha256']
    _write_csv(root, out / 'package_modules.csv', inv['modules'], fields, result)
    lines = [
        '# MugenForge Package Inventory', '',
        f'Generated: {inv["generated_at"]}',
        f'Package version: {inv["package_version"]}',
        f'App title: {inv["app_title"]}',
        f'Modules: {inv["module_count"]}',
        f'Tabs detected in app.py: {inv["tab_count"]}',
        f'Total Python lines: {inv["total_python_lines"]}',
        '', '## Largest modules', '',
    ]
    for row in sorted(inv['modules'], key=lambda r: int(r.get('lines') or 0), reverse=True)[:25]:
        lines.append(f'- `{row["path"]}` — {row["lines"]} lines, {row["functions"]} functions, {row["classes"]} classes')
    lines += ['', '## Tabs', ''] + [f'- {tab}' for tab in inv['tabs']]
    _write(root, out / 'PACKAGE_INVENTORY.md', '\n'.join(lines), result)
    return result


def write_context_digest(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Context Digest')
    inv = collect_package_inventory(root)
    out = _out(root, 'digest')
    digest = {
        'generated_at': inv['generated_at'],
        'package_version': inv['package_version'],
        'handoff_core_version': inv['handoff_core_version'],
        'app_title': inv['app_title'],
        'module_count': inv['module_count'],
        'tab_count': inv['tab_count'],
        'total_python_lines': inv['total_python_lines'],
        'handoff_target_summary': inv['handoff_target_summary'],
        'resume_order': [
            'Read handoff_core/HANDOFF_CORE_START_HERE.md',
            'Read MUGENFORGE_HANDOFF_v7_5.md and RELEASE_SUMMARY_v7_5.md',
            'Run python -m compileall -q mugenforge',
            'Run python handoff_core/regression_harness/smoke_v7_5.py',
            'Open the UI and start in Operator Console, then Handoff Core',
        ],
    }
    _write_json(root, out / 'context_digest.json', digest, result)
    lines = [
        '# Handoff Context Digest', '',
        f'Generated: {digest["generated_at"]}',
        f'Package: {digest["package_version"]} — {digest["app_title"]}',
        f'Modules: {digest["module_count"]}',
        f'Tabs: {digest["tab_count"]}',
        f'Total Python lines: {digest["total_python_lines"]}',
        '', '## Resume order', '',
    ]
    lines.extend(f'{idx}. {item}' for idx, item in enumerate(digest['resume_order'], 1))
    lines += ['', '## Handoff target summary', '', '```json', json.dumps(digest['handoff_target_summary'], indent=2), '```']
    _write(root, out / 'CONTEXT_DIGEST.md', '\n'.join(lines), result)
    return result


def _roadmap_rows() -> List[Dict[str, object]]:
    return [
        {'priority': 'P0', 'area': 'Architecture', 'item': 'Split app.py into tab/controller modules', 'status': 'next', 'notes': 'Largest stability/maintainability gap after feature expansion.'},
        {'priority': 'P0', 'area': 'Tests', 'item': 'Turn smoke harness into real pytest-style suite', 'status': 'next', 'notes': 'Keep compile/import/UI/backend smoke coverage before refactors.'},
        {'priority': 'P1', 'area': 'Binary', 'item': 'Run SFF2/SND corpus validation on broad real-world samples', 'status': 'framework ready', 'notes': 'Document exact supported variants; preserve unknown layouts.'},
        {'priority': 'P1', 'area': 'UX', 'item': 'Collapse 40+ tabs into role-based workspaces', 'status': 'design needed', 'notes': 'Beginner, Animator, Binary, Runtime, Release, Maintainer.'},
        {'priority': 'P1', 'area': 'Timeline', 'item': 'Convert sheet-backed edits to direct visual timeline/canvas editing', 'status': 'partial', 'notes': 'Forge Timeline is the target center of move editing.'},
        {'priority': 'P2', 'area': 'Docs', 'item': 'Create tutorial sample projects and guided lessons', 'status': 'not started', 'notes': 'Needed for non-coder onboarding.'},
        {'priority': 'P2', 'area': 'Packaging', 'item': 'Windows app bundle/installer', 'status': 'not started', 'notes': 'Do after tests and architecture split.'},
    ]


def write_roadmap_backlog(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Roadmap Backlog')
    out = _out(root, 'roadmap')
    rows = _roadmap_rows()
    _write_csv(root, out / 'roadmap_backlog.csv', rows, ['priority', 'area', 'item', 'status', 'notes'], result)
    lines = ['# MugenForge v7.5 Roadmap Backlog', '', 'Recommended continuation order after this handoff.', '']
    for row in rows:
        lines += [f'## {row["priority"]} — {row["area"]}: {row["item"]}', '', f'Status: **{row["status"]}**', '', str(row['notes']), '']
    _write(root, out / 'ROADMAP_BACKLOG.md', '\n'.join(lines), result)
    return result


def write_honest_scope_ledger(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Honest Scope Ledger')
    out = _out(root, 'scope')
    rows = [
        {'claim_area': 'Clean-room status', 'safe_claim': 'MugenForge is a clean-room Python/Tkinter M.U.G.E.N creator suite.', 'do_not_claim': 'Do not claim Fighter Factory / VirtuallTek source reuse.'},
        {'claim_area': 'SFF2', 'safe_claim': 'Common SFF2 workflows include parser/export/candidate build/triage paths.', 'do_not_claim': 'Do not claim perfect arbitrary custom/encrypted/historical SFF2 support without corpus evidence.'},
        {'claim_area': 'SND', 'safe_claim': 'SND workflows include WAV extraction/rebuild and guarded candidate patching when metadata is reliable.', 'do_not_claim': 'Do not claim blind in-place mutation of arbitrary legacy SND files.'},
        {'claim_area': 'Runtime', 'safe_claim': 'Runtime/Evidence/Authority tools can configure local engine runs, parse logs, and index evidence.', 'do_not_claim': 'Do not claim bundled or emulated M.U.G.E.N/IKEMEN authority.'},
        {'claim_area': 'Gameplay', 'safe_claim': 'Generated code is scaffolded and tunable through sheets and evidence loops.', 'do_not_claim': 'Do not claim generated moves are balanced/final without playtesting.'},
    ]
    _write_json(root, out / 'honest_scope_ledger.json', rows, result)
    lines = ['# Honest Scope Ledger', '', 'Use this before changing UI copy, README text, or release notes.', '']
    for row in rows:
        lines += [f'## {row["claim_area"]}', '', f'- Safe claim: {row["safe_claim"]}', f'- Do not claim: {row["do_not_claim"]}', '']
    _write(root, out / 'HONEST_SCOPE_LEDGER.md', '\n'.join(lines), result)
    return result


def write_next_chat_prompt(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Next Chat Prompt')
    out = _out(root, 'handoff')
    inv = collect_package_inventory(root)
    prompt = f'''# Copy/paste prompt for next chat

I am continuing **MugenForge Studio v7.5 Continuity Core**, a clean-room Python/Tkinter M.U.G.E.N character/stage editor and no-code creator suite.

Please continue from the uploaded package `mugenforge_studio_v7_5.zip`. Unzip it, inspect the code, run smoke tests, and continue development from that exact package rather than starting over.

## Current version

- Package version: `{PACKAGE_VERSION}`
- App title: `{inv.get('app_title')}`
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

- Split `mugenforge/app.py` into tab/controller modules.
- Move generated smoke checks into a real tests folder.
- Run binary corpus validation on diverse real SFF/SND files.
- Consolidate the UI into role-based workspaces.
- Keep all feature claims honest and clean-room.
'''
    _write(root, out / 'NEXT_CHAT_PROMPT.md', prompt, result)
    _write(root, root / 'NEXT_CHAT_PROMPT_v7_5.md', prompt, result)
    return result


def write_development_handoff(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Development Handoff')
    out = _out(root, 'handoff')
    inv = collect_package_inventory(root)
    text = f'''# MugenForge Studio Handoff — v7.5 Continuity Core

## Artifact

- Archive: `mugenforge_studio_v7_5.zip`
- Version: `{PACKAGE_VERSION}`
- Title: `{inv.get('app_title')}`
- Run: `python -m mugenforge.app`
- Install: `pip install -r requirements.txt`

## What v7.5 added

v7.5 is a stabilization/continuity pass. It adds **Operator Console** and **Handoff Core** so future work starts from generated dashboards, inventories, handoff prompts, release-readiness packets, and smoke-test harnesses instead of from memory.

## Major capability stack

- v3.x: creator hub, rescue workflows, SFF2 source bridge.
- v4.x: visual forge, forge beyond/polish/timeline.
- v5.x: binary core/deep/maturity for SFF/SND inspection, candidate builds, and guarded mutation.
- v6.x: runtime lab for launch profiles, logs, evidence, readiness.
- v7.x: closure/evidence/authority layers for simulation, engine-backed gates, corpus validation, verified candidate promotion.
- v7.5: continuity, handoff, inventory, roadmap, scope ledger, smoke harness, context bundles.

## Handoff target summary

```json
{json.dumps(inv.get('handoff_target_summary'), indent=2)}
```

## Next maintainer priorities

1. Refactor `mugenforge/app.py` into module-backed tab classes.
2. Preserve compile/import/UI smoke tests before each refactor.
3. Expand binary corpus validation and document unsupported variants.
4. Turn Forge Timeline sheet workflows into direct visual editing surfaces.
5. Package tutorials/sample projects after architecture stabilizes.
'''
    _write(root, out / 'CURRENT_STATE_HANDOFF.md', text, result)
    _write(root, root / 'MUGENFORGE_HANDOFF_v7_5.md', text, result)
    return result


def write_regression_harness(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Regression Harness')
    out = _out(root, 'regression_harness')
    script = '''#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import compileall
import importlib
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print('MugenForge smoke root:', ROOT)
ok = compileall.compile_dir(str(ROOT / 'mugenforge'), quiet=1)
print('compileall:', 'PASS' if ok else 'FAIL')
if not ok:
    raise SystemExit(1)

import mugenforge
from mugenforge.app import APP_TITLE
print('version:', mugenforge.__version__)
print('title:', APP_TITLE)

for name in [
    'mugenforge.handoff_core', 'mugenforge.operator_console', 'mugenforge.evidence_core',
    'mugenforge.authority_core', 'mugenforge.runtime_lab', 'mugenforge.binary_maturity',
    'mugenforge.forge_timeline',
]:
    importlib.import_module(name)
    print('import:', name, 'PASS')

from mugenforge.parsers import make_new_character
from mugenforge.handoff_core import write_context_digest, write_package_inventory, write_regression_harness
from mugenforge.operator_console import write_operator_dashboard, write_next_chat_handoff, write_operator_roadmap
with tempfile.TemporaryDirectory(prefix='mf_v75_smoke_') as tmp:
    char = make_new_character(Path(tmp), 'SmokeHero')
    results = [
        write_context_digest(char),
        write_package_inventory(char),
        write_regression_harness(char),
        write_operator_dashboard(char),
        write_next_chat_handoff(char),
        write_operator_roadmap(char),
    ]
    print('backend warnings:', sum(len(r.warnings) for r in results))

print('SMOKE_TEST_PASS')
'''
    script_path = out / 'smoke_v7_5.py'
    _write(root, script_path, script, result)
    md = '''# v7.5 Regression Harness

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
'''
    _write(root, out / 'REGRESSION_HARNESS.md', md, result)
    return result


def build_handoff_bundle(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('Handoff Core — Bundle')
    for label, fn in [
        ('context digest', write_context_digest),
        ('package inventory', write_package_inventory),
        ('roadmap', write_roadmap_backlog),
        ('scope ledger', write_honest_scope_ledger),
        ('next prompt', write_next_chat_prompt),
        ('development handoff', write_development_handoff),
        ('regression harness', write_regression_harness),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    out = _out(root, 'bundles')
    bundle = out / f'mugenforge_handoff_core_v7_5_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    manifest: List[Dict[str, object]] = []
    include_files: List[Path] = []
    for base in [root / 'handoff_core']:
        if base.exists():
            for p in sorted(base.rglob('*'), key=lambda x: str(x).lower()):
                if p.is_file() and p.suffix.lower() in TEXT_EXTS and p != bundle:
                    include_files.append(p)
    for name in ['README.md', 'CHANGELOG.md', 'MUGENFORGE_HANDOFF_v7_5.md', 'RELEASE_SUMMARY_v7_5.md', 'TEST_RESULTS_v7_5.txt', 'NEXT_CHAT_PROMPT_v7_5.md', 'requirements.txt', 'run_windows.bat']:
        p = root / name
        if p.exists():
            include_files.append(p)
    seen = set()
    with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in include_files:
            rp = p.resolve()
            if rp in seen or rp == bundle.resolve():
                continue
            seen.add(rp)
            rel = _rel(root, p)
            zf.write(p, rel)
            manifest.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': _sha256(p)})
        zf.writestr('handoff_bundle_manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    result.add_created(root, bundle)
    result.add_note(f'Bundled {len(manifest)} handoff files.')
    return result


def run_handoff_core_pass(root: Path) -> HandoffResult:
    root = Path(root)
    result = HandoffResult('One-Click Handoff Core Pass')
    for label, fn in [
        ('context digest', write_context_digest),
        ('package inventory', write_package_inventory),
        ('roadmap', write_roadmap_backlog),
        ('scope ledger', write_honest_scope_ledger),
        ('next prompt', write_next_chat_prompt),
        ('development handoff', write_development_handoff),
        ('regression harness', write_regression_harness),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    start = _out(root) / 'HANDOFF_CORE_START_HERE.md'
    text = '''# Handoff Core Start Here

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
'''
    _write(root, start, text, result)
    try:
        result.merge(build_handoff_bundle(root), 'handoff bundle')
    except Exception as exc:
        result.add_warning(f'handoff bundle failed: {exc}')
    return result
