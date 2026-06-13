from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import ast
import csv
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file

MAINTENANCE_CORE_VERSION = "7.5.0"
TEXT_EXTS = {'.py', '.md', '.txt', '.csv', '.json', '.def', '.air', '.cmd', '.cns', '.st', '.ini', '.cfg', '.bat', '.sh'}
DOC_EXTS = {'.md', '.txt'}
SKIP_DIRS = {'__pycache__', '.git', '.mypy_cache', '.pytest_cache', 'backups', 'exports'}


@dataclass
class MaintenanceResult:
    title: str = 'Maintenance Core'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
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

    def merge(self, other: 'MaintenanceResult', label: Optional[str] = None) -> None:
        if not other:
            return
        prefix = f'{label}: ' if label else ''
        self.created_files += [prefix + x for x in other.created_files]
        self.changed_files += [prefix + x for x in other.changed_files]
        self.warnings += [prefix + x for x in other.warnings]
        self.notes += [prefix + x for x in other.notes]

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        if self.notes:
            lines += ['Notes:'] + [f'- {x}' for x in _unique(self.notes)] + ['']
        if self.changed_files:
            lines += ['Changed files:'] + [f'- {x}' for x in _unique(self.changed_files)] + ['']
        if self.created_files:
            lines += ['Created files/artifacts:'] + [f'- {x}' for x in _unique(self.created_files)] + ['']
        if self.warnings:
            lines += ['Warnings:'] + [f'- {x}' for x in _unique(self.warnings)] + ['']
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


def _unique(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _mc_dir(root: Path) -> Path:
    out = Path(root) / 'maintenance_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_safely(path, text.rstrip() + '\n')
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, '') for field in fields})
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path, *, suffixes: Optional[set[str]] = None, max_size: int = 5_000_000) -> Iterable[Path]:
    root = Path(root)
    if not root.exists():
        return []
    for p in sorted(root.rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS or part.startswith('.') for part in p.parts):
            continue
        if suffixes is not None and p.suffix.lower() not in suffixes:
            continue
        try:
            if p.stat().st_size > max_size:
                continue
        except Exception:
            continue
        yield p


def _module_files() -> List[Path]:
    return [p for p in _iter_files(_package_dir(), suffixes={'.py'}, max_size=2_000_000)]


def _safe_read(path: Path) -> str:
    try:
        return read_text_safely(path)
    except Exception:
        try:
            return path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return ''


def _parse_ast(path: Path) -> Optional[ast.Module]:
    try:
        return ast.parse(_safe_read(path), filename=str(path))
    except Exception:
        return None


def _callable_signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ''
    args: List[str] = []
    all_args = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(all_args) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(all_args, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += ': ' + _unparse(arg.annotation)
        if default is not None:
            text += '=' + _unparse(default)
        args.append(text)
    if node.args.vararg:
        args.append('*' + node.args.vararg.arg)
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += ': ' + _unparse(arg.annotation)
        if default is not None:
            text += '=' + _unparse(default)
        args.append(text)
    if node.args.kwarg:
        args.append('**' + node.args.kwarg.arg)
    out = f"{node.name}({', '.join(args)})"
    if node.returns is not None:
        out += ' -> ' + _unparse(node.returns)
    return out


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return '...'


def _project_stats(root: Path) -> Dict[str, object]:
    root = Path(root)
    stats: Dict[str, object] = {
        'root': str(root),
        'exists': root.exists(),
        'file_counts': {},
        'character_files': {},
        'air_actions': 0,
        'cmd_commands': 0,
        'states': 0,
        'controllers': 0,
        'scan_warnings': [],
    }
    if not root.exists():
        return stats
    counts: Dict[str, int] = {}
    for p in root.rglob('*'):
        if p.is_file() and not any(part.startswith('.') for part in p.parts):
            ext = p.suffix.lower() or '[none]'
            counts[ext] = counts.get(ext, 0) + 1
    stats['file_counts'] = dict(sorted(counts.items()))
    for kind in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        p = find_character_file(root, kind)
        stats['character_files'][kind] = _rel(root, p) if p else ''
    air = find_character_file(root, 'air')
    if air and air.exists():
        try:
            actions = parse_air(read_text_safely(air))
            stats['air_actions'] = len(actions)
        except Exception as exc:
            stats.setdefault('scan_warnings', []).append(f'AIR parse failed: {exc}')
    cmd = find_character_file(root, 'cmd')
    cns = find_character_file(root, 'cns')
    for p in [cmd, cns] + [x for x in sorted(root.glob('*.st')) if x not in {cmd, cns}]:
        if p and p.exists():
            try:
                scan = parse_code(read_text_safely(p))
                stats['cmd_commands'] = int(stats.get('cmd_commands', 0)) + len(scan.commands)
                stats['states'] = int(stats.get('states', 0)) + len(scan.states)
                stats['controllers'] = int(stats.get('controllers', 0)) + len(scan.controllers)
            except Exception as exc:
                stats.setdefault('scan_warnings', []).append(f'{p.name} parse failed: {exc}')
    try:
        audit = scan_project(root)
        stats['missing_required'] = list(getattr(audit, 'missing_required', []))
        stats['missing_references'] = list(getattr(audit, 'missing_references', []))
        stats['code_issues'] = list(getattr(audit, 'code_issues', []))[:50]
        stats['asset_issues'] = list(getattr(audit, 'asset_issues', []))[:50]
    except Exception as exc:
        stats.setdefault('scan_warnings', []).append(f'Project audit failed: {exc}')
    return stats


def write_maintainer_dashboard(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Maintenance Core Dashboard')
    out = _mc_dir(root)
    repo = _repo_root()
    stats = _project_stats(root)
    module_count = len(_module_files())
    latest_docs = sorted([p.name for p in repo.glob('*v7_*.md')])
    lines = [
        '# MugenForge Maintenance Core',
        '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}',
        f'Maintenance Core version: {MAINTENANCE_CORE_VERSION}',
        f'Package root: `{repo}`',
        f'Project root: `{root}`',
        '',
        '## Run commands',
        '',
        '```bash',
        'pip install -r requirements.txt',
        'python -m mugenforge.app',
        'python -m compileall -q mugenforge',
        'python tools/run_mugenforge_smoke.py',
        '```',
        '',
        '## Current package snapshot',
        '',
        f'- Python modules: {module_count}',
        f'- Latest v7 docs detected: {", ".join(latest_docs) if latest_docs else "none"}',
        f'- Project AIR actions: {stats.get("air_actions", 0)}',
        f'- Project StateDefs: {stats.get("states", 0)}',
        f'- Project controllers: {stats.get("controllers", 0)}',
        '',
        '## Maintenance order for the next developer',
        '',
        '1. Run `tools/run_mugenforge_smoke.py` from the package root.',
        '2. Open `maintenance_core/module_catalog.html` to understand backend modules.',
        '3. Open `maintenance_core/ui_tab_inventory.md` before editing `app.py`.',
        '4. Read `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md` and package-level `MUGENFORGE_HANDOFF_v7_5.md`.',
        '5. Keep binary claims tied to verified parser/rebuild paths and runtime claims tied to external evidence.',
        '',
        '## Generated maintenance files',
        '',
        '- `module_catalog.csv/json/html` — modules, callables, classes, constants.',
        '- `ui_tab_inventory.csv/md` — Tkinter tabs and builder methods.',
        '- `release_lineage.md/json` — release-doc inventory.',
        '- `honesty_claims_audit.csv/md` — claim-risk scan for docs/UI text.',
        '- `maintenance_backlog.md` — practical next work.',
        '- `HANDOFF_FOR_NEXT_CHAT.md` — compressed context handoff.',
    ]
    path = _write(out / 'MAINTAINER_START_HERE.md', '\n'.join(lines))
    _write_json(out / 'project_stats.json', stats)
    result.add_created(root, path)
    result.add_created(root, out / 'project_stats.json')
    result.add_note('Wrote maintainer dashboard and project stats.')
    return result


def write_module_api_catalog(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Module API Catalog')
    out = _mc_dir(root) / 'module_catalog'
    rows: List[Dict[str, object]] = []
    module_summaries: List[Dict[str, object]] = []
    for path in _module_files():
        rel = _rel(_repo_root(), path)
        text = _safe_read(path)
        tree = _parse_ast(path)
        line_count = text.count('\n') + 1 if text else 0
        functions = classes = dataclasses = 0
        imports: List[str] = []
        constants: List[str] = []
        if tree is None:
            rows.append({'module': rel, 'kind': 'parse_error', 'name': '', 'signature': '', 'line': '', 'doc': ''})
            continue
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    base = '.' * node.level + (node.module or '')
                    imports.append(base)
                else:
                    imports += [alias.name for alias in node.names]
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        constants.append(target.id)
                        rows.append({'module': rel, 'kind': 'constant', 'name': target.id, 'signature': target.id, 'line': node.lineno, 'doc': ''})
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id.isupper():
                constants.append(node.target.id)
                rows.append({'module': rel, 'kind': 'constant', 'name': node.target.id, 'signature': node.target.id, 'line': node.lineno, 'doc': ''})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
                rows.append({
                    'module': rel, 'kind': 'function', 'name': node.name,
                    'signature': _callable_signature(node), 'line': node.lineno,
                    'doc': (ast.get_docstring(node) or '').strip().split('\n')[0][:240],
                })
            if isinstance(node, ast.ClassDef):
                classes += 1
                is_dc = any((_unparse(dec).endswith('dataclass') or _unparse(dec) == 'dataclass') for dec in node.decorator_list)
                dataclasses += 1 if is_dc else 0
                rows.append({
                    'module': rel, 'kind': 'class' + ('/dataclass' if is_dc else ''), 'name': node.name,
                    'signature': node.name, 'line': node.lineno,
                    'doc': (ast.get_docstring(node) or '').strip().split('\n')[0][:240],
                })
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith('_'):
                        rows.append({
                            'module': rel, 'kind': 'method', 'name': f'{node.name}.{child.name}',
                            'signature': _callable_signature(child), 'line': child.lineno,
                            'doc': (ast.get_docstring(child) or '').strip().split('\n')[0][:240],
                        })
        module_summaries.append({
            'module': rel, 'lines': line_count, 'functions': functions, 'classes': classes,
            'dataclasses': dataclasses, 'constants': len(constants), 'imports': sorted(set(imports))[:30],
            'sha256': _sha256(path),
        })
    fields = ['module', 'kind', 'name', 'signature', 'line', 'doc']
    csv_path = _write_csv(out / 'module_api_catalog.csv', rows, fields)
    json_path = _write_json(out / 'module_api_catalog.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'modules': module_summaries, 'items': rows})
    html_rows = []
    for row in rows:
        html_rows.append('<tr>' + ''.join(f'<td>{html.escape(str(row.get(field, "")))}</td>' for field in fields) + '</tr>')
    html_path = _write(out / 'module_api_catalog.html', f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MugenForge Module API Catalog</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top}} th{{background:#eee;position:sticky;top:0}} code{{white-space:pre-wrap}}</style></head>
<body><h1>MugenForge Module API Catalog</h1><p>Generated {html.escape(datetime.now().isoformat(timespec='seconds'))}. Modules: {len(module_summaries)}. Items: {len(rows)}.</p>
<table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in fields)}</tr></thead><tbody>{''.join(html_rows)}</tbody></table></body></html>""")
    result.add_created(root, csv_path)
    result.add_created(root, json_path)
    result.add_created(root, html_path)
    result.add_note(f'Cataloged {len(module_summaries)} modules and {len(rows)} public-ish items.')
    return result


def write_ui_tab_inventory(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('UI Tab Inventory')
    app = _package_dir() / 'app.py'
    text = _safe_read(app)
    rows: List[Dict[str, object]] = []
    builder_re = re.compile(r'^\s+def\s+(_build_[A-Za-z0-9_]+_tab)\s*\(', re.M)
    add_re = re.compile(r'self\.notebook\.add\((?P<frame>[^,]+),\s*text\s*=\s*[\"\'](?P<text>[^\"\']+)[\"\']')
    call_re = re.compile(r'self\.(_build_[A-Za-z0-9_]+_tab)\s*\(\)')
    builders = [(m.group(1), text[:m.start()].count('\n') + 1) for m in builder_re.finditer(text)]
    adds = [(m.group('text'), m.group('frame').strip(), text[:m.start()].count('\n') + 1) for m in add_re.finditer(text)]
    calls = [(m.group(1), text[:m.start()].count('\n') + 1) for m in call_re.finditer(text)]
    for idx, (tab_text, frame, line) in enumerate(adds, 1):
        nearby_builder = ''
        preceding = [b for b in builders if b[1] <= line]
        if preceding:
            nearby_builder = preceding[-1][0]
        rows.append({'order': idx, 'tab': tab_text, 'frame_expr': frame, 'line': line, 'builder_guess': nearby_builder})
    out = _mc_dir(root) / 'ui_inventory'
    csv_path = _write_csv(out / 'ui_tab_inventory.csv', rows, ['order', 'tab', 'frame_expr', 'line', 'builder_guess'])
    md_lines = ['# UI Tab Inventory', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', f'Tabs detected: {len(rows)}', f'Tab builder methods detected: {len(builders)}', f'Build calls detected: {len(calls)}', '', '| # | Tab | app.py line | Builder guess |', '|---:|---|---:|---|']
    for row in rows:
        md_lines.append(f"| {row['order']} | {str(row['tab']).replace('|','/')} | {row['line']} | `{row['builder_guess']}` |")
    md_lines += ['', '## Build call order', '']
    for idx, (name, line) in enumerate(calls, 1):
        md_lines.append(f'{idx}. `{name}()` — app.py line {line}')
    md_path = _write(out / 'ui_tab_inventory.md', '\n'.join(md_lines))
    result.add_created(root, csv_path)
    result.add_created(root, md_path)
    result.add_note(f'Inventory wrote {len(rows)} tabs and {len(calls)} tab-build calls.')
    return result


def write_release_lineage(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Release Lineage')
    repo = _repo_root()
    docs = []
    for pat in ('RELEASE_SUMMARY_v*.md', 'MUGENFORGE_HANDOFF_v*.md', 'TEST_RESULTS_v*.txt'):
        docs.extend(sorted(repo.glob(pat), key=lambda p: p.name.lower()))
    docs += [repo / 'README.md', repo / 'CHANGELOG.md']
    rows: List[Dict[str, object]] = []
    version_re = re.compile(r'v(\d+(?:_\d+)+|\d+(?:\.\d+)+)', re.I)
    heading_re = re.compile(r'^#\s+(.+)$', re.M)
    for p in docs:
        if not p.exists():
            continue
        text = _safe_read(p)
        heading = ''
        hm = heading_re.search(text)
        if hm:
            heading = hm.group(1).strip()
        vm = version_re.search(p.name) or version_re.search(heading) or version_re.search(text[:1000])
        version = vm.group(1).replace('_', '.') if vm else ''
        rows.append({
            'file': p.name,
            'version_hint': version,
            'heading': heading,
            'bytes': p.stat().st_size,
            'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='seconds'),
            'sha256': _sha256(p),
        })
    out = _mc_dir(root) / 'release_lineage'
    _write_json(out / 'release_lineage.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'docs': rows})
    md = ['# Release Lineage', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', '| File | Version hint | Heading | Bytes |', '|---|---|---|---:|']
    for r in rows:
        md.append(f"| `{r['file']}` | {r['version_hint']} | {str(r['heading']).replace('|','/')} | {r['bytes']} |")
    md.append('')
    md.append('This inventory exists to reduce context loss between development sessions. Preserve older handoff files unless they are proven misleading.')
    md_path = _write(out / 'release_lineage.md', '\n'.join(md))
    result.add_created(root, out / 'release_lineage.json')
    result.add_created(root, md_path)
    result.add_note(f'Indexed {len(rows)} release/test/handoff docs.')
    return result


CLAIM_PATTERNS: List[Tuple[str, str, str]] = [
    ('binary-fullness', r'\b(full|arbitrary|complete|mature|all|any)\b.{0,80}\b(SFF|SFF2|SND|binary|mutation|rebuild|extract)', 'high'),
    ('engine-authority', r'\b(engine[- ]authoritative|simulate|emulate|runtime[- ]authoritative|certification)\b', 'high'),
    ('safety-claim', r'\b(safe|verified|guaranteed|lossless|byte[- ]perfect)\b', 'medium'),
    ('fighter-factory-reference', r'\b(Fighter Factory|VirtuallTek)\b', 'medium'),
    ('honesty-negative', r'\b(not implemented|does not|unsupported|experimental|candidate|backup|external engine|evidence aid|not.*authoritative)\b', 'info'),
    ('plugin-execution', r'\b(plugin|auto-run|execute|third-party|downloaded Python)\b', 'medium'),
]


def write_honesty_claims_audit(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Honesty Claims Audit')
    repo = _repo_root()
    files = list(_iter_files(repo, suffixes=TEXT_EXTS, max_size=1_500_000))
    rows: List[Dict[str, object]] = []
    for p in files:
        rel = _rel(repo, p)
        text = _safe_read(p)
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for claim_type, pattern, severity in CLAIM_PATTERNS:
                if re.search(pattern, line, re.I):
                    rows.append({
                        'severity': severity,
                        'claim_type': claim_type,
                        'file': rel,
                        'line': line_no,
                        'text': line.strip()[:500],
                    })
                    break
    high = sum(1 for r in rows if r['severity'] == 'high')
    medium = sum(1 for r in rows if r['severity'] == 'medium')
    out = _mc_dir(root) / 'honesty_claims'
    csv_path = _write_csv(out / 'honesty_claims_audit.csv', rows, ['severity', 'claim_type', 'file', 'line', 'text'])
    md = ['# Honesty Claims Audit', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', 'This is a text scan, not a legal review. It flags statements that future developers should keep accurate.', '', f'- Rows: {len(rows)}', f'- High-risk rows: {high}', f'- Medium-risk rows: {medium}', '', '## Required truth rules for future releases', '', '- Do not claim full arbitrary SFF2 support unless validated against a broad real-world corpus.', '- Do not call static reports engine-authoritative unless backed by actual engine evidence.', '- Keep candidate/backup-first wording for binary mutation unless direct install is proven safe.', '- Do not auto-run untrusted community Python plugins without a genuine sandbox.', '', '## First 100 flagged lines', '']
    for r in rows[:100]:
        md.append(f"- **{r['severity']} / {r['claim_type']}** `{r['file']}:{r['line']}` — {r['text']}")
    md_path = _write(out / 'honesty_claims_audit.md', '\n'.join(md))
    result.add_created(root, csv_path)
    result.add_created(root, md_path)
    if high:
        result.add_warning(f'{high} high-risk claim lines should be reviewed before public release text is finalized.')
    result.add_note(f'Flagged {len(rows)} claim-related lines across {len(files)} text files.')
    return result


def write_regression_test_scripts(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Regression Test Scripts')
    repo = _repo_root()
    tools = repo / 'tools'
    tools.mkdir(parents=True, exist_ok=True)
    smoke = r'''from __future__ import annotations

from pathlib import Path
import importlib
import json
import shutil
import subprocess
import sys
import tempfile

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def run(cmd: list[str]) -> None:
    print('RUN:', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, '-m', 'compileall', '-q', 'mugenforge'])
    import mugenforge
    from mugenforge.app import APP_TITLE
    print('VERSION', mugenforge.__version__)
    print('APP_TITLE', APP_TITLE)
    expected_modules = [
        'mugenforge.maintenance_core', 'mugenforge.handoff_core', 'mugenforge.operator_console', 'mugenforge.evidence_core', 'mugenforge.authority_core',
        'mugenforge.runtime_lab', 'mugenforge.binary_maturity', 'mugenforge.forge_timeline',
        'mugenforge.visual_forge', 'mugenforge.sff_codec', 'mugenforge.snd_codec',
    ]
    for name in expected_modules:
        importlib.import_module(name)
        print('IMPORT_OK', name)
    from mugenforge.parsers import make_new_character
    from mugenforge.maintenance_core import run_maintenance_core_pass
    with tempfile.TemporaryDirectory(prefix='mugenforge_smoke_') as td:
        project = make_new_character(Path(td), 'SmokeHero')
        result = run_maintenance_core_pass(project)
        print(result.to_text())
        assert (project / 'maintenance_core' / 'MAINTAINER_START_HERE.md').exists()
        assert (project / 'maintenance_core' / 'HANDOFF_FOR_NEXT_CHAT.md').exists()
    print('SMOKE_PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''
    package_script = r'''from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import zipfile

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
OUT = ROOT.parent / f'{ROOT.name}.zip'
SKIP_PARTS = {'__pycache__', '.git', '.pytest_cache', '.mypy_cache'}
SKIP_SUFFIXES = {'.pyc', '.pyo'}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def main() -> int:
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ROOT.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file() and not should_skip(p):
                zf.write(p, p.relative_to(ROOT.parent))
    print(f'Wrote {OUT}')
    print(f'Bytes {OUT.stat().st_size}')
    print(f'Generated {datetime.now().isoformat(timespec="seconds")}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''
    print_handoff = r'''from __future__ import annotations

from pathlib import Path

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
CANDIDATES = sorted(ROOT.glob('MUGENFORGE_HANDOFF_v*.md'), key=lambda p: p.name.lower())
if not CANDIDATES:
    raise SystemExit('No handoff file found.')
print(CANDIDATES[-1].read_text(encoding='utf-8', errors='replace'))
'''
    paths = [
        _write(tools / 'run_mugenforge_smoke.py', smoke),
        _write(tools / 'package_release.py', package_script),
        _write(tools / 'print_latest_handoff.py', print_handoff),
    ]
    out = _mc_dir(root) / 'scripts'
    out.mkdir(parents=True, exist_ok=True)
    for p in paths:
        shutil.copy2(p, out / p.name)
        result.add_created(root, out / p.name)
        result.add_changed(repo, p)
    readme = _write(out / 'README.md', '# Maintenance scripts\n\nThese are mirrored from the package-level `tools/` folder. Run them from the package root for release validation.\n\n```bash\npython tools/run_mugenforge_smoke.py\npython tools/package_release.py\npython tools/print_latest_handoff.py\n```\n')
    result.add_created(root, readme)
    result.add_note('Wrote package-level tools and mirrored them into the project maintenance folder.')
    return result


def write_maintenance_backlog(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Maintenance Backlog')
    lines = [
        '# MugenForge Maintenance Backlog after v7.5',
        '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}',
        '',
        '## Immediate cleanup',
        '',
        '- Continue consolidating module-backed tabs into role modes; `app.py` is now split into state, shell, tab-builder, and action modules.',
        '- Extend the real test suite around controlled SFF/SND fixtures and risky backend workflows.',
        '- Add sample projects with small permissive assets for repeatable visual/binary tests.',
        '- Add a CI-friendly headless UI test using Xvfb where available.',
        '- Consolidate duplicate workflow tabs into role modes: Beginner, Visual, Binary, Runtime, Release, Maintenance.',
        '',
        '## Binary roadmap',
        '',
        '- Expand SFF2 corpus validation with many real-world files and preserve hash-based support buckets.',
        '- Document exact supported SFF2 encodings and table variants in one codec spec file.',
        '- Add mutation rollback tests for axis, palette, sprite replacement, and SND replacement candidates.',
        '',
        '## Runtime roadmap',
        '',
        '- Add external-engine profile presets for common M.U.G.E.N/IKEMEN builds.',
        '- Convert manual regression checklists into scenario files that Runtime/Evidence Core can execute or track.',
        '- Add log pattern packs per engine family.',
        '',
        '## UX roadmap',
        '',
        '- Make Project Home the default cockpit and hide advanced labs behind mode toggles.',
        '- Add a searchable command palette for actions instead of relying on dozens of tabs.',
        '- Add guided fix buttons from dashboards into the relevant editors.',
        '',
        '## Release engineering',
        '',
        '- Create Windows portable builds after the Python package stabilizes.',
        '- Add a package manifest with file hashes to every release ZIP.',
        '- Keep handoff, changelog, release summary, and test results in sync before every artifact delivery.',
    ]
    path = _write(_mc_dir(root) / 'maintenance_backlog.md', '\n'.join(lines))
    result.add_created(root, path)
    return result


def write_handoff_for_next_chat(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Handoff Writer')
    repo = _repo_root()
    stats = _project_stats(root)
    module_count = len(_module_files())
    try:
        import mugenforge  # type: ignore
        version = getattr(mugenforge, '__version__', 'unknown')
    except Exception:
        version = 'unknown'
    handoff = f"""# MugenForge Studio Handoff — v7.5 Continuity Core

## Copy/paste prompt for the next chat

I am continuing **MugenForge Studio**, a clean-room Python/Tkinter M.U.G.E.N character/stage editor and no-code creator suite. Continue from the uploaded package **mugenforge_studio_v7_5.zip**. Do not start over. Unzip it, run smoke tests, inspect `MUGENFORGE_HANDOFF_v7_5.md`, then continue development.

Latest version: **{version}**  
Latest app title should be: **MugenForge Studio 7.5 Continuity Core**  
Run command: `python -m mugenforge.app`  
Install: `pip install -r requirements.txt`

## Non-negotiable project rules

- Clean-room only. Do not use or claim Fighter Factory / VirtuallTek source, assets, or proprietary logic.
- Keep binary claims tied to implemented parser/writer paths and corpus evidence.
- Do not claim static reports are engine-authoritative unless backed by external engine evidence.
- Do not blindly overwrite user binaries; preserve candidate/backup/verified install workflows.
- Do not auto-run untrusted third-party Python plugins.

## Current architecture snapshot

- Package root: `{repo}`
- Python modules detected: {module_count}
- Main UI file: `mugenforge/app.py`
- Maintenance module: `mugenforge/maintenance_core.py`
- Current project stats from smoke/handoff generation:
  - AIR actions: {stats.get('air_actions', 0)}
  - StateDefs: {stats.get('states', 0)}
  - Controllers: {stats.get('controllers', 0)}

## Recent release line

- v3.4 Rescue Bridge: asset rescue and source-based SFF2 bridge.
- v3.5 Visual Forge: beginner home, timeline, axis, sound cue, migration, backup logs.
- v4.0 Forge Beyond: parity+ reports, sheets, state graph, project index.
- v4.1 Forge Polish: validation previews, sound cue apply, sprite-backed preview, backup history.
- v4.5 Timeline Core: integrated timeline, CLSN/HitDef sheets, palette/stage previews.
- v5.0 Binary Core: conservative SFF/SND binary inspection and candidate workflows.
- v5.5 Binary Maturity: deeper SFF2 decode/write candidates, SND patch candidates, runtime harness artifacts.
- v6.1 Runtime Lab: external engine launchers, logs, evidence, readiness reports.
- v7.0 Evidence Core line: gap closure, authority/evidence labs, source runtime modeling, corpus validation, verified installs.
- v7.5 Continuity Core: Operator Console, Handoff Core, Maintenance Core, module/UI catalogs, claim audit, smoke scripts, release-readiness packet, and next-chat handoff bundle.

## What v7.5 added

- New `mugenforge/maintenance_core.py`, `mugenforge/handoff_core.py`, and `mugenforge/operator_console.py` backends.
- New **Maintenance Core**, **Handoff Core**, and **Operator Console** UI tabs.
- One-click maintenance pass.
- Module/API catalog in CSV/JSON/HTML.
- UI tab inventory.
- Release lineage inventory.
- Honesty/claim-risk audit.
- Package-level tools:
  - `tools/run_mugenforge_smoke.py`
  - `tools/package_release.py`
  - `tools/print_latest_handoff.py`
- Package-level `MUGENFORGE_HANDOFF_v7_5.md`.
- Project-level `maintenance_core/HANDOFF_FOR_NEXT_CHAT.md`.

## First commands to run

```bash
cd mugenforge_studio_v7_5
pip install -r requirements.txt
python -m compileall -q mugenforge
python tools/run_mugenforge_smoke.py
python -m mugenforge.app
```

## Most important next work

1. Refactor `app.py` into smaller tab/controller modules.
2. Turn smoke scripts into a real pytest suite with controlled SFF/SND fixtures.
3. Consolidate the many tabs into role-based modes and a command palette.
4. Build a broad SFF2/SND corpus validation set with support buckets and known hashes.
5. Add installer/portable builds only after regression tests stabilize.

## Files to read first

- `README.md`
- `CHANGELOG.md`
- `RELEASE_SUMMARY_v7_5.md`
- `TEST_RESULTS_v7_5.txt`
- `MUGENFORGE_HANDOFF_v7_5.md`
- `maintenance_core/MAINTAINER_START_HERE.md`
- `maintenance_core/module_catalog/module_api_catalog.html`
- `maintenance_core/ui_inventory/ui_tab_inventory.md`
- `maintenance_core/honesty_claims/honesty_claims_audit.md`
"""
    project_path = _write(_mc_dir(root) / 'HANDOFF_FOR_NEXT_CHAT.md', handoff)
    package_path = _write(repo / 'MUGENFORGE_HANDOFF_v7_5.md', handoff)
    result.add_created(root, project_path)
    result.add_changed(repo, package_path)
    result.add_note('Wrote project and package handoff files.')
    return result


def build_maintenance_bundle(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('Maintenance Bundle')
    out = _mc_dir(root)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_path = out / f'maintenance_core_bundle_{stamp}.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(out.parent))
        for name in ('README.md', 'CHANGELOG.md', 'MUGENFORGE_HANDOFF_v7_5.md', 'RELEASE_SUMMARY_v7_5.md', 'TEST_RESULTS_v7_5.txt'):
            p = _repo_root() / name
            if p.exists():
                zf.write(p, Path('package_docs') / p.name)
    manifest = {
        'bundle': str(zip_path),
        'bytes': zip_path.stat().st_size,
        'sha256': _sha256(zip_path),
        'generated': datetime.now().isoformat(timespec='seconds'),
    }
    _write_json(out / 'maintenance_core_bundle_manifest.json', manifest)
    result.add_created(root, zip_path)
    result.add_created(root, out / 'maintenance_core_bundle_manifest.json')
    return result


def run_maintenance_core_pass(root: Path) -> MaintenanceResult:
    root = Path(root)
    result = MaintenanceResult('One-Click Maintenance Core Pass')
    steps = [
        ('dashboard', write_maintainer_dashboard),
        ('module catalog', write_module_api_catalog),
        ('UI tab inventory', write_ui_tab_inventory),
        ('release lineage', write_release_lineage),
        ('honesty claims audit', write_honesty_claims_audit),
        ('regression scripts', write_regression_test_scripts),
        ('maintenance backlog', write_maintenance_backlog),
        ('handoff', write_handoff_for_next_chat),
    ]
    for label, fn in steps:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    try:
        result.merge(build_maintenance_bundle(root), 'bundle')
    except Exception as exc:
        result.add_warning(f'bundle failed: {exc}')
    result.add_note('Maintenance Core pass completed. Start with maintenance_core/MAINTAINER_START_HERE.md and MUGENFORGE_HANDOFF_v7_5.md.')
    return result
