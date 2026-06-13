from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import parse_air, parse_code, read_text_safely, write_text_safely, scan_project
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd

try:  # optional newer codec layer from Binary Maturity
    from . import sff2_codec
except Exception:  # pragma: no cover
    sff2_codec = None  # type: ignore

EVIDENCE_CORE_VERSION = '7.0.0'
TEXT_EXTS = {'.def', '.air', '.cmd', '.cns', '.st', '.txt', '.md', '.json', '.ini', '.cfg'}
BINARY_EXTS = {'.sff', '.snd'}
EVIDENCE_EXTS = {'.txt', '.log', '.json', '.csv', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.avi', '.mp4', '.mkv', '.zip'}
ERROR_PATTERNS = [
    re.compile(r'\b(error|fatal|exception|traceback|crash|failed|missing|unable to open|not found)\b', re.I),
    re.compile(r'\bassert(?:ion)?\b', re.I),
]
WARNING_PATTERNS = [
    re.compile(r'\b(warn(?:ing)?|deprecated|skipped|fallback|unsupported)\b', re.I),
]


@dataclass
class EvidenceCoreResult:
    title: str = 'Evidence Core Result'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def merge(self, other: object, label: Optional[str] = None) -> None:
        if other is None:
            return
        prefix = f'{label}: ' if label else ''
        for attr in ('created_files', 'changed_files', 'skipped_files', 'warnings', 'notes'):
            values = getattr(other, attr, []) or []
            getattr(self, attr).extend(prefix + str(v) for v in values)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def add_note(self, message: str) -> None:
        self.notes.append(str(message))

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
                lines.extend(f'- {v}' for v in uniq)
                lines.append('')
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


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


def _ec(root: Path, *parts: str) -> Path:
    out = Path(root) / 'evidence_core'
    for part in parts:
        out = out / part
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(root: Path, path: Path, text: str, result: Optional[EvidenceCoreResult] = None, *, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(text.rstrip() + '\n', encoding='utf-8')
    if result is not None:
        if changed or existed:
            result.add_changed(root, path)
        else:
            result.add_created(root, path)
    return path


def _write_json(root: Path, path: Path, payload: object, result: Optional[EvidenceCoreResult] = None, *, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if result is not None:
        if changed or existed:
            result.add_changed(root, path)
        else:
            result.add_created(root, path)
    return path


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], result: Optional[EvidenceCoreResult] = None, *, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, '') for k in fields})
    if result is not None:
        if changed or existed:
            result.add_changed(root, path)
        else:
            result.add_created(root, path)
    return path


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open('r', newline='', encoding='utf-8') as f:
        return [dict(r) for r in csv.DictReader(f)]


def _truthy(value: object) -> bool:
    return str(value or '').strip().lower() in {'1', 'yes', 'y', 'true', 'on', 'apply', 'enabled', 'pass', 'passed'}


def _now() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _safe_copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return dst


def _project_files(root: Path, suffixes: set[str]) -> List[Path]:
    root = Path(root)
    skip = {'__pycache__', '.git'}
    files: List[Path] = []
    for p in sorted(root.rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        if any(part in skip for part in p.parts):
            continue
        files.append(p)
    return files


def _discover_main_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    for key in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        try:
            found = find_character_file(root, key)
        except Exception:
            found = None
        if found and found.exists():
            out[key] = found
        else:
            matches = sorted(root.glob(f'*.{key}'), key=lambda p: p.name.lower())
            out[key] = matches[0] if matches else None
    if out.get('cns') is None:
        sts = sorted(root.glob('*.st'), key=lambda p: p.name.lower())
        out['cns'] = sts[0] if sts else None
    return out


# ---------------------------------------------------------------------------
# Dashboard and engine execution


def write_evidence_core_dashboard(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Dashboard')
    out = _ec(root)
    text = f"""# Evidence Core v{EVIDENCE_CORE_VERSION}

Evidence Core closes the practical Runtime Lab limitations with evidence-backed tooling:

- validate an external M.U.G.E.N/IKEMEN engine profile;
- run configured engine profiles from Python and capture stdout/stderr/result JSON;
- generate and score scenario sheets;
- ingest runtime logs, screenshots, replays, and packaged evidence;
- validate SFF/SND compatibility across a project or external corpus;
- create unknown-binary recovery workspaces for unsupported/corrupt files;
- install verified binary/text candidate files with SHA-256 backups and rollback manifests;
- export/apply playtest-driven HitDef tuning sheets.

This does not include an engine and does not pretend to emulate one. Runtime confidence now comes from actual external-engine evidence, not static reports alone.
"""
    _write_text(root, out / 'EVIDENCE_CORE_START_HERE.md', text, result)
    return result


def write_engine_profile_template(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Engine Profile Template')
    out = _ec(root, 'engine')
    files = _discover_main_files(root)
    char_name = root.name
    payload = {
        'tool': 'MugenForge Studio Evidence Core',
        'version': EVIDENCE_CORE_VERSION,
        'profile_version': 2,
        'engine_kind': 'custom',
        'engine_executable': '',
        'working_directory': '',
        'timeout_seconds': 60,
        'variables': {
            'character': char_name,
            'project_root': str(root),
            'main_def': str(files.get('def') or ''),
        },
        'launch_profiles': [
            {
                'name': 'boot_character_smoke',
                'enabled': True,
                'description': 'Launch the engine with the edited character when your engine supports command-line match launch.',
                'arguments': [],
                'expected_returncodes': [0],
                'log_globs': ['*.log', 'Logs/*.txt', 'logs/*.txt'],
            },
            {
                'name': 'custom_profile_1',
                'enabled': False,
                'description': 'Edit arguments for your local engine/build. Variables like {character} are expanded.',
                'arguments': ['{character}'],
                'expected_returncodes': [0],
                'log_globs': ['*.log', 'Logs/*.txt', 'logs/*.txt'],
            },
        ],
        'notes': [
            'Set engine_executable to your local mugen.exe, ikemen_go executable, or wrapper script.',
            'Set working_directory to the engine folder if blank cwd does not work.',
            'Use dry-run first; then run with an actual engine to create evidence.',
        ],
    }
    _write_json(root, out / 'engine_profile.json', payload, result)
    return result


def _load_engine_profile(root: Path, profile_path: Optional[Path] = None) -> Dict[str, object]:
    profile = Path(profile_path) if profile_path else _ec(root, 'engine') / 'engine_profile.json'
    if not profile.exists():
        write_engine_profile_template(root)
    return json.loads(profile.read_text(encoding='utf-8'))


def _expand_arg(arg: object, variables: Dict[str, object]) -> str:
    text = str(arg)
    for key, value in variables.items():
        text = text.replace('{' + key + '}', str(value))
    return text


def validate_engine_profile(root: Path, profile_path: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Engine Profile Validation')
    out = _ec(root, 'engine')
    profile = _load_engine_profile(root, profile_path)
    engine_text = str(profile.get('engine_executable') or '').strip()
    cwd_text = str(profile.get('working_directory') or '').strip()
    profiles = profile.get('launch_profiles') if isinstance(profile.get('launch_profiles'), list) else []
    findings: List[Dict[str, object]] = []
    ok = True
    if not engine_text:
        ok = False
        findings.append({'severity': 'blocker', 'field': 'engine_executable', 'message': 'engine_executable is blank.'})
    else:
        engine = Path(engine_text)
        if not engine.exists():
            ok = False
            findings.append({'severity': 'blocker', 'field': 'engine_executable', 'message': f'Engine executable does not exist: {engine}'})
        elif engine.is_dir():
            ok = False
            findings.append({'severity': 'blocker', 'field': 'engine_executable', 'message': f'Engine executable points to a directory: {engine}'})
        else:
            findings.append({'severity': 'ok', 'field': 'engine_executable', 'message': f'Found engine executable: {engine}'})
            if os.name != 'nt' and not os.access(engine, os.X_OK):
                findings.append({'severity': 'warning', 'field': 'engine_executable', 'message': 'Engine file is not marked executable on this platform.'})
    if cwd_text:
        cwd = Path(cwd_text)
        if not cwd.exists() or not cwd.is_dir():
            ok = False
            findings.append({'severity': 'blocker', 'field': 'working_directory', 'message': f'Working directory is not a folder: {cwd}'})
        else:
            findings.append({'severity': 'ok', 'field': 'working_directory', 'message': f'Working directory exists: {cwd}'})
    else:
        findings.append({'severity': 'warning', 'field': 'working_directory', 'message': 'working_directory is blank; Evidence Core will use the profile folder.'})
    enabled_profiles = [p for p in profiles if isinstance(p, dict) and _truthy(p.get('enabled'))]
    if not enabled_profiles:
        ok = False
        findings.append({'severity': 'blocker', 'field': 'launch_profiles', 'message': 'No launch profiles are enabled.'})
    for idx, p in enumerate(profiles):
        if not isinstance(p, dict):
            findings.append({'severity': 'warning', 'field': f'launch_profiles[{idx}]', 'message': 'Launch profile is not an object.'})
            continue
        args = p.get('arguments', [])
        if not isinstance(args, list):
            ok = False
            findings.append({'severity': 'blocker', 'field': f'launch_profiles[{idx}].arguments', 'message': 'arguments must be a list.'})
        else:
            findings.append({'severity': 'ok', 'field': f'launch_profiles[{idx}]', 'message': f'{p.get("name", idx)} has {len(args)} argument(s).'})
    report = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'valid_for_launch': ok,
        'profile': profile,
        'findings': findings,
    }
    _write_json(root, out / 'engine_profile_validation.json', report, result)
    md_lines = ['# Engine Profile Validation', '', f'Valid for launch: **{"yes" if ok else "no"}**', '']
    md_lines += ['## Findings'] + [f'- **{f["severity"]}** `{f["field"]}` — {f["message"]}' for f in findings]
    _write_text(root, out / 'ENGINE_PROFILE_VALIDATION.md', '\n'.join(md_lines), result)
    if ok:
        result.notes.append('Engine profile passed structural validation.')
    else:
        result.warnings.append('Engine profile is not ready for live launch. Fill engine_profile.json first.')
    return result


def run_engine_profile(root: Path, profile_path: Optional[Path] = None, profile_name: Optional[str] = None, *, dry_run: bool = False) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Engine Profile Run')
    out = _ec(root, 'runtime_runs')
    profile = _load_engine_profile(root, profile_path)
    variables = profile.get('variables') if isinstance(profile.get('variables'), dict) else {}
    variables = {str(k): v for k, v in variables.items()}
    variables.setdefault('character', root.name)
    variables.setdefault('project_root', str(root))
    engine = str(profile.get('engine_executable') or '').strip()
    profiles = [p for p in profile.get('launch_profiles', []) if isinstance(p, dict) and _truthy(p.get('enabled'))]
    if profile_name:
        profiles = [p for p in profiles if str(p.get('name')) == str(profile_name)]
    if not profiles:
        result.warnings.append('No enabled launch profile matched the request.')
        return result
    selected = profiles[0]
    args = [_expand_arg(a, variables) for a in selected.get('arguments', []) if isinstance(selected.get('arguments', []), list)]
    command = [engine] + args
    cwd = Path(str(profile.get('working_directory') or '') or (_ec(root, 'engine')))
    timeout = int(profile.get('timeout_seconds') or 60)
    tag = _now()
    run_dir = out / f'{tag}_{re.sub(r"[^A-Za-z0-9_\-]+", "_", str(selected.get("name", "profile")))}'
    run_dir.mkdir(parents=True, exist_ok=True)
    preview = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'dry_run': dry_run,
        'profile_name': selected.get('name', ''),
        'command': command,
        'cwd': str(cwd),
        'timeout_seconds': timeout,
    }
    _write_json(root, run_dir / 'runtime_command_preview.json', preview, result)
    if dry_run:
        result.notes.append('Dry-run only; command preview was written and no engine was launched.')
        return result
    if not engine or not Path(engine).exists():
        blocked = dict(preview)
        blocked['status'] = 'blocked'
        blocked['reason'] = 'engine_executable is missing or does not exist'
        _write_json(root, run_dir / 'runtime_result.json', blocked, result)
        result.warnings.append('Engine executable missing; live run blocked. Edit evidence_core/engine/engine_profile.json.')
        return result
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        stdout = proc.stdout or ''
        stderr = proc.stderr or ''
        (run_dir / 'stdout.txt').write_text(stdout, encoding='utf-8', errors='replace')
        (run_dir / 'stderr.txt').write_text(stderr, encoding='utf-8', errors='replace')
        expected = selected.get('expected_returncodes', [0])
        expected_codes = [int(x) for x in expected] if isinstance(expected, list) else [0]
        status = 'pass' if proc.returncode in expected_codes else 'fail'
        payload = dict(preview)
        payload.update({
            'status': status,
            'returncode': proc.returncode,
            'expected_returncodes': expected_codes,
            'stdout_file': _rel(root, run_dir / 'stdout.txt'),
            'stderr_file': _rel(root, run_dir / 'stderr.txt'),
        })
        _write_json(root, run_dir / 'runtime_result.json', payload, result)
        result.notes.append(f'Engine run finished with return code {proc.returncode} ({status}).')
    except subprocess.TimeoutExpired as exc:
        (run_dir / 'stdout.txt').write_text(str(exc.stdout or ''), encoding='utf-8', errors='replace')
        (run_dir / 'stderr.txt').write_text(str(exc.stderr or ''), encoding='utf-8', errors='replace')
        _write_json(root, run_dir / 'runtime_result.json', dict(preview, status='timeout', error='timeout'), result)
        result.warnings.append(f'Engine run timed out after {timeout} seconds.')
    except Exception as exc:
        _write_json(root, run_dir / 'runtime_result.json', dict(preview, status='error', error=str(exc)), result)
        result.warnings.append(f'Engine run failed: {exc}')
    return result


# ---------------------------------------------------------------------------
# Runtime scenarios, evidence, and release gate


def export_runtime_scenario_sheet(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Runtime Scenario Sheet')
    out = _ec(root, 'scenarios')
    rows: List[Dict[str, object]] = []
    seq = 1
    def add(category: str, target: object, expected: str, method: str = 'manual_playtest', notes: str = '') -> None:
        nonlocal seq
        rows.append({
            'enabled': 'yes',
            'scenario_id': f'EC-{seq:04d}',
            'category': category,
            'target': target,
            'method': method,
            'expected_result': expected,
            'status': '',
            'evidence_file': '',
            'observed_result': '',
            'notes': notes,
        })
        seq += 1
    add('boot', root.name, 'Character loads without engine error or missing asset log.', 'engine_launch')
    add('round_start', root.name, 'Round starts, character can idle, move, guard, jump, and return to neutral.', 'manual_playtest')
    files = _discover_main_files(root)
    air = files.get('air')
    if air and air.exists():
        for action in parse_air(read_text_safely(air))[:200]:
            if action.number in {0, 20, 21, 40, 41, 42, 47, 100, 105, 120, 130, 140, 150, 5000, 5010, 5020, 5030, 5050, 5100, 5110, 5150}:
                add('required_animation', action.number, f'Animation {action.number} displays correctly and does not reference blank/misaligned sprites.', 'manual_playtest')
    for path in _project_files(root, {'.cmd', '.cns', '.st'}):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for cmd in scan.commands[:300]:
            add('command', cmd.name, f'Input `{cmd.command}` triggers/behaves as expected if wired to a state.', 'manual_playtest', _rel(root, path))
        for st in scan.states[:300]:
            if any((ctrl.stype or ctrl.values.get('type', '')).lower() == 'hitdef' for ctrl in st.controllers):
                add('hitdef_state', st.number, f'State {st.number} hitboxes, damage, sounds, block behavior, and recovery are acceptable.', 'manual_playtest', _rel(root, path))
    fields = ['enabled','scenario_id','category','target','method','expected_result','status','evidence_file','observed_result','notes']
    _write_csv(root, out / 'runtime_scenario_sheet.csv', rows, fields, result)
    md = ['# Runtime Scenario Sheet', '', 'Edit `runtime_scenario_sheet.csv` after playtesting. Use `status=pass`, `fail`, `blocked`, or `needs_tuning`, and attach evidence file paths when available.', '', f'Scenarios generated: {len(rows)}']
    _write_text(root, out / 'RUNTIME_SCENARIO_GUIDE.md', '\n'.join(md), result)
    return result


def ingest_runtime_evidence(root: Path, evidence_folder: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Runtime Evidence Ingest')
    out = _ec(root, 'evidence')
    inbox = out / 'inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    marker = inbox / 'DROP_RUNTIME_LOGS_SCREENSHOTS_REPLAYS_HERE.txt'
    if not marker.exists():
        _write_text(root, marker, 'Drop runtime logs, screenshots, videos, replays, and manual notes here, then run Evidence Ingest again.', result)
    sources: List[Path] = [
        inbox,
        root / 'runtime_lab' / 'logs',
        root / 'runtime_lab' / 'evidence',
        root / 'runtime_lab' / 'runtime_logs',
        root / 'evidence_core' / 'runtime_runs',
        root / 'release' / 'screenshots',
        root / 'screenshots',
    ]
    if evidence_folder:
        sources.insert(0, Path(evidence_folder))
    archive = out / 'archive'
    archive.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    seen_hashes: set[str] = set()
    for src in sources:
        if not src.exists():
            continue
        for p in sorted(src.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file() or p.name.startswith('.'):
                continue
            if p.resolve() == marker.resolve():
                continue
            if p.suffix.lower() not in EVIDENCE_EXTS and p.name not in {'stdout.txt', 'stderr.txt', 'runtime_result.json'}:
                continue
            try:
                digest = _sha256(p)
            except Exception:
                continue
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            rel_name = re.sub(r'[^A-Za-z0-9_.\-]+', '_', f'{src.name}_{p.name}')
            dst = archive / rel_name
            suffix = 1
            while dst.exists() and _sha256(dst) != digest:
                dst = archive / f'{Path(rel_name).stem}_{suffix}{Path(rel_name).suffix}'
                suffix += 1
            _safe_copy(p, dst)
            rows.append({
                'file': _rel(root, dst),
                'source': str(p),
                'bytes': dst.stat().st_size,
                'sha256': digest,
                'modified': datetime.fromtimestamp(dst.stat().st_mtime).isoformat(timespec='seconds'),
                'kind': dst.suffix.lower().lstrip('.') or 'file',
            })
            result.add_created(root, dst)
    fields = ['file','source','bytes','sha256','modified','kind']
    _write_csv(root, out / 'runtime_evidence_index.csv', rows, fields, result, changed=True)
    _write_json(root, out / 'runtime_evidence_index.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'count': len(rows), 'evidence': rows}, result, changed=True)
    if rows:
        result.notes.append(f'Indexed {len(rows)} evidence file(s).')
    else:
        result.warnings.append('No runtime evidence files were found. Add logs/screenshots/replays to evidence_core/evidence/inbox/.')
    return result


def _runtime_result_files(root: Path) -> List[Path]:
    candidates = []
    for folder in [root / 'evidence_core' / 'runtime_runs', root / 'runtime_lab' / 'logs', root / 'runtime_lab']:
        if folder.exists():
            candidates.extend(sorted(folder.rglob('runtime_result*.json'), key=lambda p: str(p).lower()))
            candidates.extend(sorted(folder.rglob('*result*.json'), key=lambda p: str(p).lower()))
    return _uniq_paths(candidates)


def _uniq_paths(paths: Iterable[Path]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for p in paths:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key not in seen and p.is_file():
            seen.add(key)
            out.append(p)
    return out


def parse_runtime_logs_and_results(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Runtime Log/Result Parse')
    out = _ec(root, 'release_gate')
    rows: List[Dict[str, object]] = []
    result_files = _runtime_result_files(root)
    for p in result_files:
        try:
            payload = json.loads(p.read_text(encoding='utf-8', errors='replace'))
        except Exception as exc:
            rows.append({'file': _rel(root, p), 'kind': 'result_json', 'severity': 'warning', 'line': '', 'message': f'Could not read result JSON: {exc}'})
            continue
        status = str(payload.get('status', '') or '')
        rc = payload.get('returncode', '')
        if status in {'fail', 'error', 'timeout', 'blocked'} or (isinstance(rc, int) and rc != 0):
            rows.append({'file': _rel(root, p), 'kind': 'result_json', 'severity': 'error', 'line': '', 'message': f'runtime status={status or "unknown"} returncode={rc}'})
        else:
            rows.append({'file': _rel(root, p), 'kind': 'result_json', 'severity': 'ok', 'line': '', 'message': f'runtime status={status or "recorded"} returncode={rc}'})
    log_files = []
    for folder in [root / 'evidence_core' / 'runtime_runs', root / 'evidence_core' / 'evidence' / 'archive', root / 'runtime_lab' / 'logs', root / 'runtime_lab' / 'runtime_logs']:
        if folder.exists():
            log_files.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in {'.txt', '.log'})
    for p in _uniq_paths(log_files):
        try:
            lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
        except Exception:
            continue
        for line_no, line in enumerate(lines[:20000], 1):
            sev = None
            if any(rx.search(line) for rx in ERROR_PATTERNS):
                sev = 'error'
            elif any(rx.search(line) for rx in WARNING_PATTERNS):
                sev = 'warning'
            if sev:
                rows.append({'file': _rel(root, p), 'kind': 'text_log', 'severity': sev, 'line': line_no, 'message': line[:500]})
    fields = ['file','kind','severity','line','message']
    _write_csv(root, out / 'runtime_log_findings.csv', rows, fields, result, changed=True)
    summary = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'findings': len(rows),
        'errors': sum(1 for r in rows if r.get('severity') == 'error'),
        'warnings': sum(1 for r in rows if r.get('severity') == 'warning'),
        'runtime_results': len(result_files),
    }
    _write_json(root, out / 'runtime_log_summary.json', summary, result, changed=True)
    return result


def write_evidence_release_gate(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Release Gate')
    out = _ec(root, 'release_gate')
    parse_result = parse_runtime_logs_and_results(root)
    result.merge(parse_result, 'log parse')
    scenario_sheet = root / 'evidence_core' / 'scenarios' / 'runtime_scenario_sheet.csv'
    if not scenario_sheet.exists():
        export_runtime_scenario_sheet(root)
    scenarios = _read_csv(scenario_sheet)
    evidence_index = root / 'evidence_core' / 'evidence' / 'runtime_evidence_index.csv'
    if not evidence_index.exists():
        ingest_runtime_evidence(root)
    evidence_rows = _read_csv(evidence_index)
    findings = _read_csv(out / 'runtime_log_findings.csv')
    audit = scan_project(root)
    enabled = [r for r in scenarios if _truthy(r.get('enabled'))]
    pass_rows = [r for r in enabled if str(r.get('status', '')).strip().lower() in {'pass', 'passed', 'ok'}]
    fail_rows = [r for r in enabled if str(r.get('status', '')).strip().lower() in {'fail', 'failed', 'blocked', 'needs_tuning'}]
    result_files = _runtime_result_files(root)
    errors = [r for r in findings if r.get('severity') == 'error']
    warnings = [r for r in findings if r.get('severity') == 'warning']
    score = 100
    reasons: List[str] = []
    def ding(points: int, reason: str) -> None:
        nonlocal score
        if points <= 0:
            return
        score = max(0, score - points)
        reasons.append(f'-{points}: {reason}')
    if not result_files:
        ding(35, 'no actual engine runtime result JSON found')
    if not evidence_rows:
        ding(25, 'no runtime evidence files indexed')
    if enabled and not pass_rows:
        ding(20, 'no scenarios marked pass')
    if fail_rows:
        ding(min(30, 8 * len(fail_rows)), f'{len(fail_rows)} scenario(s) marked fail/blocked/needs_tuning')
    if errors:
        ding(min(35, 7 * len(errors)), f'{len(errors)} runtime/log error finding(s)')
    if warnings:
        ding(min(15, 3 * len(warnings)), f'{len(warnings)} runtime/log warning finding(s)')
    if audit.missing_required:
        ding(min(30, 6 * len(audit.missing_required)), f'missing required project files: {", ".join(audit.missing_required)}')
    status = 'pass' if score >= 85 and not errors and result_files and evidence_rows and not fail_rows else 'blocked'
    gate = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'version': EVIDENCE_CORE_VERSION,
        'status': status,
        'score': score,
        'reasons': reasons,
        'scenario_count': len(enabled),
        'scenario_passed': len(pass_rows),
        'scenario_blocked_or_failed': len(fail_rows),
        'runtime_result_files': [_rel(root, p) for p in result_files],
        'runtime_errors': len(errors),
        'runtime_warnings': len(warnings),
        'evidence_files': len(evidence_rows),
        'missing_required_files': audit.missing_required,
        'project_root': str(root),
    }
    _write_json(root, out / 'evidence_release_gate.json', gate, result, changed=True)
    md = [
        '# Evidence Release Gate', '',
        f'Status: **{status.upper()}**',
        f'Score: **{score}/100**', '',
        'This gate is based on actual external-engine result files and indexed evidence when available. Static reports alone are not enough to pass.', '',
        '## Counts',
        f'- Runtime result files: {len(result_files)}',
        f'- Evidence files: {len(evidence_rows)}',
        f'- Enabled scenarios: {len(enabled)}',
        f'- Passed scenarios: {len(pass_rows)}',
        f'- Failed/blocked/tuning scenarios: {len(fail_rows)}',
        f'- Runtime/log errors: {len(errors)}',
        f'- Runtime/log warnings: {len(warnings)}', '',
        '## Score reasons',
    ]
    md.extend(reasons or ['- No score deductions.'])
    _write_text(root, out / 'EVIDENCE_RELEASE_GATE.md', '\n'.join(md), result, changed=True)
    if status == 'pass':
        result.notes.append('Evidence release gate passed.')
    else:
        result.warnings.append('Evidence release gate is blocked until runtime evidence/scenario/log issues are resolved.')
    return result


# ---------------------------------------------------------------------------
# SFF/SND corpus validation and unknown binary recovery


def run_binary_corpus_validation(root: Path, corpus_folder: Optional[Path] = None, *, max_files: int = 250, max_export_per_sff: int = 5) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Binary Corpus Validation')
    base = Path(corpus_folder) if corpus_folder else root
    out = _ec(root, 'corpus_validation')
    export_base = out / 'sample_exports'
    export_base.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    files = [p for p in sorted(base.rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in BINARY_EXTS]
    if len(files) > max_files:
        result.warnings.append(f'Corpus has {len(files)} binary files; capped validation at {max_files}.')
    for p in files[:max_files]:
        rel = str(p.relative_to(base)) if base in p.parents or p.parent == base else str(p)
        row: Dict[str, object] = {'file': rel, 'absolute_path': str(p), 'kind': p.suffix.lower(), 'status': 'unknown', 'variant': '', 'records': 0, 'exports': 0, 'errors': '', 'warnings': ''}
        try:
            if p.suffix.lower() == '.sff':
                info = read_sff(p)
                row['variant'] = info.variant
                row['records'] = len(info.sprites)
                row['warnings'] = '; '.join(info.warnings[:8])
                if str(info.variant).startswith('sff2') or (info.version and (info.version[0] >= 2 or info.version[-1] == 2)):
                    if sff2_codec is None:
                        row['status'] = 'blocked'
                        row['errors'] = 'sff2_codec unavailable'
                    else:
                        s2 = sff2_codec.read_sff2(p)  # type: ignore[attr-defined]
                        row['variant'] = s2.parser_mode
                        row['records'] = len(s2.sprites)
                        row['warnings'] = '; '.join((s2.warnings or [])[:8])
                        sample_dir = export_base / re.sub(r'[^A-Za-z0-9_.\-]+', '_', p.stem)
                        outs, warns = sff2_codec.export_sff2_sprites(p, sample_dir, max_count=max_export_per_sff)  # type: ignore[attr-defined]
                        row['exports'] = len(outs)
                        row['warnings'] = '; '.join((s2.warnings + warns)[:12])
                        row['status'] = 'pass' if len(s2.sprites) == 0 or outs or not s2.can_export_any else 'warning'
                elif info.is_supported_for_extraction:
                    row['status'] = 'pass'
                else:
                    row['status'] = 'warning' if info.warnings else 'unknown'
            elif p.suffix.lower() == '.snd':
                snd = read_snd(p)
                row['variant'] = 'snd-signature' if snd.has_signature else 'snd-scanned'
                row['records'] = len(snd.sounds)
                row['warnings'] = '; '.join(snd.warnings[:8])
                row['status'] = 'pass' if snd.sounds else 'warning'
        except Exception as exc:
            row['status'] = 'fail'
            row['errors'] = str(exc)
        rows.append(row)
    fields = ['file','absolute_path','kind','status','variant','records','exports','errors','warnings']
    _write_csv(root, out / 'binary_corpus_validation.csv', rows, fields, result, changed=True)
    summary = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'source': str(base),
        'files_seen': len(files),
        'files_validated': len(rows),
        'pass': sum(1 for r in rows if r.get('status') == 'pass'),
        'warning': sum(1 for r in rows if r.get('status') == 'warning'),
        'fail': sum(1 for r in rows if r.get('status') == 'fail'),
    }
    _write_json(root, out / 'binary_corpus_validation.json', {'summary': summary, 'rows': rows}, result, changed=True)
    md = ['# Binary Corpus Validation', '', f'Source: `{base}`', '', '## Summary']
    md.extend(f'- {k}: {v}' for k, v in summary.items() if k != 'source')
    md += ['', 'This report lets the project build real-world compatibility evidence over time. A small smoke corpus is not a guarantee for every historical/custom variant.']
    _write_text(root, out / 'BINARY_CORPUS_VALIDATION.md', '\n'.join(md), result, changed=True)
    return result


def _find_png_segments(data: bytes) -> List[Tuple[int, int, str]]:
    out: List[Tuple[int, int, str]] = []
    sig = b'\x89PNG\r\n\x1a\n'
    pos = 0
    while True:
        start = data.find(sig, pos)
        if start < 0:
            break
        end_marker = data.find(b'IEND', start + 8)
        if end_marker >= 0 and end_marker + 8 <= len(data):
            end = end_marker + 8
            out.append((start, end - start, 'png'))
            pos = end
        else:
            out.append((start, 0, 'png_truncated'))
            pos = start + 8
    return out


def _find_wav_segments(data: bytes) -> List[Tuple[int, int, str]]:
    out: List[Tuple[int, int, str]] = []
    pos = 0
    while True:
        start = data.find(b'RIFF', pos)
        if start < 0:
            break
        if start + 12 <= len(data) and data[start + 8:start + 12] == b'WAVE':
            size = int.from_bytes(data[start + 4:start + 8], 'little') + 8
            if 12 <= size <= len(data) - start:
                out.append((start, size, 'wav'))
                pos = start + size
                continue
        pos = start + 4
    return out


def _find_pcx_segments(data: bytes) -> List[Tuple[int, int, str]]:
    # Conservative PCX carving: identify ZSoft 0x0A header and cut to before next known asset/header.
    out: List[Tuple[int, int, str]] = []
    positions = [m.start() for m in re.finditer(b'\x0A[\x00-\x05][\x01\x02\x03\x04\x05]', data)]
    for idx, start in enumerate(positions[:500]):
        candidates = [len(data)]
        for nxt in positions[idx + 1:idx + 2]:
            if nxt > start:
                candidates.append(nxt)
        for sig in (b'\x89PNG\r\n\x1a\n', b'RIFF'):
            nxt = data.find(sig, start + 16)
            if nxt > start:
                candidates.append(nxt)
        length = max(0, min(candidates) - start)
        if length >= 128:
            out.append((start, length, 'pcx_candidate'))
    return out


def write_unknown_binary_recovery_workspace(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Unknown Binary Recovery Workspace')
    out = _ec(root, 'unknown_binary_recovery')
    rows: List[Dict[str, object]] = []
    binaries = _project_files(root, BINARY_EXTS)
    for p in binaries:
        data = p.read_bytes()
        file_rows: List[Tuple[int, int, str]] = []
        file_rows.extend(_find_png_segments(data))
        file_rows.extend(_find_wav_segments(data))
        if p.suffix.lower() == '.sff':
            file_rows.extend(_find_pcx_segments(data))
        carved_dir = out / re.sub(r'[^A-Za-z0-9_.\-]+', '_', p.stem)
        header_path = carved_dir / 'header_first_256_bytes.hex.txt'
        _write_text(root, header_path, data[:256].hex(' ', 1), result)
        try:
            if p.suffix.lower() == '.sff':
                info = read_sff(p)
                warnings = '; '.join(info.warnings[:8])
                variant = info.variant
            else:
                snd = read_snd(p)
                warnings = '; '.join(snd.warnings[:8])
                variant = 'snd-signature' if snd.has_signature else 'snd-scanned'
        except Exception as exc:
            warnings = str(exc)
            variant = 'unreadable'
        for idx, (offset, length, kind) in enumerate(file_rows):
            suffix = {'png': '.png', 'png_truncated': '.bin', 'wav': '.wav', 'pcx_candidate': '.pcx'}.get(kind, '.bin')
            carve_path = carved_dir / f'{idx:04d}_offset_{offset:08X}_{kind}{suffix}'
            if length > 0:
                carve_path.parent.mkdir(parents=True, exist_ok=True)
                carve_path.write_bytes(data[offset:offset + length])
                result.add_created(root, carve_path)
            rows.append({
                'source_file': _rel(root, p),
                'variant': variant,
                'offset': offset,
                'length': length,
                'kind': kind,
                'carved_file': _rel(root, carve_path) if length > 0 else '',
                'warnings': warnings,
            })
        if not file_rows:
            rows.append({'source_file': _rel(root, p), 'variant': variant, 'offset': '', 'length': '', 'kind': 'no_embedded_assets_found', 'carved_file': '', 'warnings': warnings})
    fields = ['source_file','variant','offset','length','kind','carved_file','warnings']
    _write_csv(root, out / 'unknown_binary_recovery_index.csv', rows, fields, result, changed=True)
    md = ['# Unknown Binary Recovery Workspace', '', 'This workspace carves obvious embedded PNG/WAV/PCX-like payloads and writes header hex files for unsupported or corrupt binary review.', '', 'Encrypted or custom-compressed payloads cannot be decoded without their format/key, but they are now quarantined with repeatable evidence instead of silently ignored.', '', f'Files scanned: {len(binaries)}', f'Rows written: {len(rows)}']
    _write_text(root, out / 'UNKNOWN_BINARY_RECOVERY.md', '\n'.join(md), result, changed=True)
    return result


# ---------------------------------------------------------------------------
# Verified candidate install and rollback


def _candidate_folders(root: Path) -> List[Path]:
    names = ['binary_core', 'binary_deep', 'binary_maturity', 'codec_core', 'evidence_core', 'forge_timeline', 'runtime_lab']
    return [root / name for name in names if (root / name).exists()]


def _verify_candidate(path: Path) -> Tuple[str, str]:
    try:
        if path.suffix.lower() == '.sff':
            info = read_sff(path)
            if str(info.variant).startswith('sff2') or (info.version and (info.version[0] >= 2 or info.version[-1] == 2)):
                if sff2_codec is not None:
                    s2 = sff2_codec.read_sff2(path)  # type: ignore[attr-defined]
                    if s2.parser_mode.startswith('standard'):
                        return 'pass', f'sff2 {s2.parser_mode}; sprites={len(s2.sprites)} palettes={len(s2.palettes)} warnings={len(s2.warnings)}'
                return 'warning', f'sff2 metadata/legacy parser only; variant={info.variant}; warnings={len(info.warnings)}'
            if info.is_supported_for_extraction or info.sprites:
                return 'pass', f'{info.variant}; sprites={len(info.sprites)} warnings={len(info.warnings)}'
            return 'warning', f'{info.variant}; warnings={"; ".join(info.warnings[:3])}'
        if path.suffix.lower() == '.snd':
            snd = read_snd(path)
            if snd.sounds:
                return 'pass', f'sounds={len(snd.sounds)} signature={snd.has_signature} warnings={len(snd.warnings)}'
            return 'warning', f'no sounds found; signature={snd.has_signature}; warnings={"; ".join(snd.warnings[:3])}'
        if path.suffix.lower() in TEXT_EXTS:
            read_text_safely(path)
            return 'pass', 'text file is readable'
        return 'warning', 'no verifier for this file type'
    except Exception as exc:
        return 'fail', str(exc)


def export_candidate_install_sheet(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Candidate Install Sheet')
    out = _ec(root, 'verified_commits')
    files = _discover_main_files(root)
    target_by_ext = {
        '.sff': files.get('sff'),
        '.snd': files.get('snd'),
        '.air': files.get('air'),
        '.cmd': files.get('cmd'),
        '.cns': files.get('cns'),
        '.st': files.get('cns'),
    }
    rows: List[Dict[str, object]] = []
    seen: set[str] = set()
    for folder in _candidate_folders(root):
        for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in BINARY_EXTS | TEXT_EXTS:
                continue
            rel = _rel(root, p)
            if rel in seen or '/commit_backups/' in rel or '/archive/' in rel:
                continue
            seen.add(rel)
            name_l = p.name.lower() + ' ' + rel.lower()
            if not any(word in name_l for word in ['candidate', 'patched', 'rebuilt', 'build', 'workspace_copy', 'output']):
                continue
            status, detail = _verify_candidate(p)
            target = target_by_ext.get(p.suffix.lower())
            rows.append({
                'enabled': 'no',
                'candidate_file': rel,
                'target_file': _rel(root, target) if target else '',
                'candidate_sha256': _sha256(p),
                'verify_status': status,
                'verify_detail': detail,
                'install_mode': 'replace_with_backup',
                'notes': 'Set enabled=yes only after inspecting candidate and target. Apply writes SHA-256 backup and rollback manifest.',
            })
    fields = ['enabled','candidate_file','target_file','candidate_sha256','verify_status','verify_detail','install_mode','notes']
    _write_csv(root, out / 'candidate_install_sheet.csv', rows, fields, result, changed=True)
    if not rows:
        result.warnings.append('No generated candidate files were found yet.')
    return result


def apply_verified_candidate_install_sheet(root: Path, sheet_path: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Verified Candidate Install')
    sheet = Path(sheet_path) if sheet_path else root / 'evidence_core' / 'verified_commits' / 'candidate_install_sheet.csv'
    if not sheet.exists():
        result.warnings.append(f'Candidate install sheet not found: {_rel(root, sheet)}')
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get('enabled'))]
    if not rows:
        result.skipped_files.append('No rows had enabled=yes.')
        return result
    commit_dir = root / '.mugenforge' / 'verified_commits' / _now()
    backups = commit_dir / 'backups'
    backups.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, object] = {'generated': datetime.now().isoformat(timespec='seconds'), 'version': EVIDENCE_CORE_VERSION, 'entries': []}
    entries: List[Dict[str, object]] = []
    for row in rows:
        cand = (root / str(row.get('candidate_file', '')).strip()).resolve()
        target = (root / str(row.get('target_file', '')).strip()).resolve()
        if not cand.exists():
            result.warnings.append(f'Candidate missing: {row.get("candidate_file", "")}')
            continue
        if not str(target).startswith(str(root.resolve())):
            result.warnings.append(f'Target is outside project and was skipped: {target}')
            continue
        status, detail = _verify_candidate(cand)
        if status == 'fail':
            result.warnings.append(f'Candidate verifier failed for {_rel(root, cand)}: {detail}')
            continue
        before_sha = _sha256(target) if target.exists() else ''
        backup_rel = ''
        if target.exists():
            b = backups / _rel(root, target).replace('/', '__')
            _safe_copy(target, b)
            backup_rel = _rel(root, b)
            result.add_created(root, b)
        target.parent.mkdir(parents=True, exist_ok=True)
        _safe_copy(cand, target)
        after_sha = _sha256(target)
        entries.append({
            'candidate_file': _rel(root, cand),
            'target_file': _rel(root, target),
            'backup_file': backup_rel,
            'before_sha256': before_sha,
            'candidate_sha256': _sha256(cand),
            'after_sha256': after_sha,
            'verify_status': status,
            'verify_detail': detail,
        })
        result.add_changed(root, target)
    manifest['entries'] = entries
    _write_json(root, commit_dir / 'commit_manifest.json', manifest, result)
    _write_text(root, commit_dir / 'ROLLBACK_INSTRUCTIONS.md', '# Rollback\n\nUse Evidence Core → Rollback Latest Verified Commit, or manually copy files from `backups/` to their `target_file` paths listed in `commit_manifest.json`.', result)
    if entries:
        result.notes.append(f'Installed {len(entries)} verified candidate file(s).')
    return result


def rollback_last_verified_commit(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Rollback Latest Verified Commit')
    base = root / '.mugenforge' / 'verified_commits'
    manifests = sorted(base.glob('*/commit_manifest.json'), key=lambda p: str(p), reverse=True)
    if not manifests:
        result.warnings.append('No verified commit manifests found.')
        return result
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    restored = 0
    for entry in manifest.get('entries', []):
        if not isinstance(entry, dict):
            continue
        backup = str(entry.get('backup_file') or '')
        target = str(entry.get('target_file') or '')
        if not backup or not target:
            continue
        b = (root / backup).resolve()
        t = (root / target).resolve()
        if b.exists() and str(t).startswith(str(root.resolve())):
            _safe_copy(b, t)
            restored += 1
            result.add_changed(root, t)
    marker = manifest_path.parent / f'ROLLBACK_PERFORMED_{_now()}.json'
    _write_json(root, marker, {'generated': datetime.now().isoformat(timespec='seconds'), 'restored': restored, 'source_manifest': _rel(root, manifest_path)}, result)
    if restored:
        result.notes.append(f'Restored {restored} file(s) from latest verified commit backup.')
    else:
        result.warnings.append('No files were restored from the latest commit manifest.')
    return result


# ---------------------------------------------------------------------------
# Playtest-driven tuning


def _hitdef_rows(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _project_files(root, {'.cmd', '.cns', '.st'}):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            anim = state.values.get('anim', state.number)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype != 'hitdef':
                    continue
                rows.append({
                    'file': _rel(root, path),
                    'controller_line': ctrl.line,
                    'state': state.number,
                    'anim': anim,
                    'damage': ctrl.values.get('damage', ''),
                    'pausetime': ctrl.values.get('pausetime', ''),
                    'sparkno': ctrl.values.get('sparkno', ''),
                    'hitsound': ctrl.values.get('hitsound', ''),
                    'guardsound': ctrl.values.get('guardsound', ''),
                    'ground_velocity': ctrl.values.get('ground.velocity', ''),
                    'air_velocity': ctrl.values.get('air.velocity', ''),
                    'attr': ctrl.values.get('attr', ''),
                    'hitflag': ctrl.values.get('hitflag', ''),
                    'guardflag': ctrl.values.get('guardflag', ''),
                })
    return rows


def export_playtest_tuning_sheet(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Playtest Tuning Sheet')
    out = _ec(root, 'tuning')
    rows = []
    for row in _hitdef_rows(root):
        rows.append({
            'apply': 'no',
            **row,
            'observed_result': '',
            'evidence_file': '',
            'new_damage': '',
            'new_pausetime': '',
            'new_sparkno': '',
            'new_hitsound': '',
            'new_guardsound': '',
            'new_ground_velocity': '',
            'new_air_velocity': '',
            'new_attr': '',
            'new_hitflag': '',
            'new_guardflag': '',
            'notes': 'Fill observed_result/evidence_file after playtesting. Set apply=yes and fill only new_* fields to change.',
        })
    fields = ['apply','file','controller_line','state','anim','damage','pausetime','sparkno','hitsound','guardsound','ground_velocity','air_velocity','attr','hitflag','guardflag','observed_result','evidence_file','new_damage','new_pausetime','new_sparkno','new_hitsound','new_guardsound','new_ground_velocity','new_air_velocity','new_attr','new_hitflag','new_guardflag','notes']
    _write_csv(root, out / 'playtest_tuning_sheet.csv', rows, fields, result, changed=True)
    _write_text(root, out / 'PLAYTEST_TUNING_GUIDE.md', '# Playtest Tuning Sheet\n\nUse this after real engine testing. Record observed behavior and evidence, then set `apply=yes` only for fields you want MugenForge to patch with backups.', result, changed=True)
    return result


def apply_playtest_tuning_sheet(root: Path, sheet_path: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Playtest Tuning Apply')
    sheet = Path(sheet_path) if sheet_path else root / 'evidence_core' / 'tuning' / 'playtest_tuning_sheet.csv'
    if not sheet.exists():
        result.warnings.append(f'Playtest tuning sheet not found: {_rel(root, sheet)}')
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get('apply'))]
    if not rows:
        result.skipped_files.append('No rows had apply=yes.')
        return result
    # Reuse Forge Timeline's proven HitDef block writer by emitting its sheet format.
    try:
        from .forge_timeline import apply_hitdef_track_sheet
    except Exception as exc:
        result.warnings.append(f'Forge Timeline HitDef writer unavailable: {exc}')
        return result
    out = _ec(root, 'tuning') / 'evidence_hitdef_apply_sheet.csv'
    fields = ['apply','file','controller_line','state','anim','anim_elem','damage','pausetime','sparkno','hitsound','guardsound','ground_velocity','air_velocity','attr','hitflag','guardflag','new_damage','new_pausetime','new_sparkno','new_hitsound','new_guardsound','new_ground_velocity','new_air_velocity','new_attr','new_hitflag','new_guardflag','notes']
    ft_rows = []
    for r in rows:
        ft_rows.append({k: r.get(k, '') for k in fields})
        ft_rows[-1]['anim_elem'] = r.get('anim_elem', '')
    _write_csv(root, out, ft_rows, fields, result, changed=True)
    ft_result = apply_hitdef_track_sheet(root, out)
    result.merge(ft_result, 'HitDef writer')
    return result


# ---------------------------------------------------------------------------
# Bundle and one-click


def build_evidence_core_bundle(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Bundle')
    out_dir = _ec(root, 'bundles')
    bundle = out_dir / f'{root.name}_evidence_core_bundle_{_now()}.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as zf:
        for folder in [root / 'evidence_core', root / 'runtime_lab', root / '.mugenforge' / 'verified_commits']:
            if folder.exists():
                for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()):
                    if p.is_file() and p.resolve() != bundle.resolve():
                        zf.write(p, p.relative_to(root))
    result.add_created(root, bundle)
    return result


def run_evidence_core_pass(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('One-Click Evidence Core Pass')
    steps = [
        ('dashboard', write_evidence_core_dashboard),
        ('engine profile', write_engine_profile_template),
        ('engine validation', validate_engine_profile),
        ('runtime scenarios', export_runtime_scenario_sheet),
        ('evidence ingest', ingest_runtime_evidence),
        ('binary corpus', run_binary_corpus_validation),
        ('unknown binary recovery', write_unknown_binary_recovery_workspace),
        ('candidate install sheet', export_candidate_install_sheet),
        ('playtest tuning sheet', export_playtest_tuning_sheet),
        ('release gate', write_evidence_release_gate),
        ('bundle', build_evidence_core_bundle),
    ]
    for label, fn in steps:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.warnings.append(f'{label} failed: {exc}')
    return result

# ---------------------------------------------------------------------------
# UI compatibility aliases for the v7.0 app tab

def write_engine_profile(root: Path, engine_exe: Optional[Path] = None, game_root: Optional[Path] = None, default_stage: str = 'stages/kfm.def', opponent: str = 'kfm') -> EvidenceCoreResult:
    """Write a configured engine profile from UI fields."""
    root = Path(root)
    result = write_engine_profile_template(root)
    profile_path = _ec(root, 'engine') / 'engine_profile.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    if engine_exe:
        profile['engine_executable'] = str(engine_exe)
    if game_root:
        profile['working_directory'] = str(game_root)
    profile.setdefault('variables', {})
    if isinstance(profile['variables'], dict):
        profile['variables']['character'] = root.name
        profile['variables']['opponent'] = opponent
        profile['variables']['stage'] = default_stage
    for launch in profile.get('launch_profiles', []):
        if isinstance(launch, dict) and launch.get('name') == 'custom_profile_1':
            launch['enabled'] = True
            launch['arguments'] = ['{character}', '{opponent}', '{stage}']
            launch['description'] = 'Configured from the Evidence Core UI. Edit arguments for your engine if needed.'
    _write_json(root, profile_path, profile, result, changed=True)
    result.notes.append('Configured evidence_core/engine/engine_profile.json from UI inputs.')
    return result


def probe_engine_profile(root: Path) -> EvidenceCoreResult:
    """Validate and run a dry profile probe. This does not launch a match unless the profile arguments do so."""
    result = EvidenceCoreResult('Evidence Core Engine Probe')
    result.merge(validate_engine_profile(root), 'validation')
    result.merge(run_engine_profile(root, dry_run=True), 'command preview')
    return result


def build_engine_launch_matrix(root: Path) -> EvidenceCoreResult:
    return export_runtime_scenario_sheet(root)


def run_engine_validation(root: Path, *, dry_run: bool = False, timeout_seconds: Optional[float] = None) -> EvidenceCoreResult:
    if timeout_seconds is not None:
        profile_path = _ec(Path(root), 'engine') / 'engine_profile.json'
        profile = _load_engine_profile(Path(root))
        profile['timeout_seconds'] = int(timeout_seconds)
        profile_path.write_text(json.dumps(profile, indent=2) + '\n', encoding='utf-8')
    return run_engine_profile(root, dry_run=dry_run)


def write_evidence_authority_report(root: Path) -> EvidenceCoreResult:
    return write_evidence_release_gate(root)


def write_sff2_corpus_harness(root: Path, folder: Optional[Path] = None) -> EvidenceCoreResult:
    result = EvidenceCoreResult('Evidence Core SFF2 Corpus Harness')
    out = _ec(Path(root), 'corpus_validation')
    out.mkdir(parents=True, exist_ok=True)
    inbox = out / 'corpus_inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    if folder:
        pointer = out / 'external_corpus_folder.txt'
        _write_text(Path(root), pointer, str(folder), result, changed=True)
    guide = f"""# SFF2/SND Corpus Harness

Drop `.sff` and `.snd` files into:

`{_rel(Path(root), inbox)}`

Then run **Run SFF2 Corpus**. You may also choose an external folder from the UI.
"""
    _write_text(Path(root), out / 'SFF2_CORPUS_HARNESS.md', guide, result, changed=True)
    return result


def run_sff2_corpus_validation(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    pointer = _ec(root, 'corpus_validation') / 'external_corpus_folder.txt'
    folder = None
    if pointer.exists():
        text = pointer.read_text(encoding='utf-8').strip()
        if text:
            folder = Path(text)
    if folder is None:
        folder = _ec(root, 'corpus_validation') / 'corpus_inbox'
    if not folder.exists():
        folder = root
    return run_binary_corpus_validation(root, folder)


def export_verified_candidate_install_sheet(root: Path) -> EvidenceCoreResult:
    return export_candidate_install_sheet(root)


def export_runtime_tuning_sheet(root: Path) -> EvidenceCoreResult:
    return export_playtest_tuning_sheet(root)


def apply_runtime_tuning_sheet(root: Path) -> EvidenceCoreResult:
    return apply_playtest_tuning_sheet(root)


def write_playtest_closure_report(root: Path) -> EvidenceCoreResult:
    result = EvidenceCoreResult('Evidence Core Playtest Closure')
    result.merge(write_evidence_release_gate(root), 'release gate')
    out = _ec(Path(root), 'playtest_closure')
    gate_path = _ec(Path(root), 'release_gate') / 'evidence_release_gate.json'
    gate = json.loads(gate_path.read_text(encoding='utf-8')) if gate_path.exists() else {}
    text = [
        '# Playtest Closure Report',
        '',
        f'Status: **{str(gate.get("status", "unknown")).upper()}**',
        f'Score: **{gate.get("score", "")}/100**',
        '',
        'This report summarizes whether the project has enough external-engine evidence, scenario status, and clean logs to close the playtest loop.',
    ]
    reasons = gate.get('reasons') if isinstance(gate.get('reasons'), list) else []
    if reasons:
        text += ['', '## Open blockers'] + [f'- {r}' for r in reasons]
    _write_text(Path(root), out / 'PLAYTEST_CLOSURE_REPORT.md', '\n'.join(text), result, changed=True)
    return result

# ---------------------------------------------------------------------------
# Compatibility/public API used by the v7.0 Tkinter tab


def write_engine_profile(root: Path, *, engine_exe: Optional[Path] = None, game_root: Optional[Path] = None, default_stage: str = 'stages/training.def', opponent: str = 'kfm') -> EvidenceCoreResult:
    root = Path(root)
    result = write_engine_profile_template(root)
    profile_path = _ec(root, 'engine') / 'engine_profile.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    if engine_exe is not None:
        profile['engine_executable'] = str(Path(engine_exe))
    if game_root is not None:
        profile['working_directory'] = str(Path(game_root))
    variables = profile.setdefault('variables', {})
    if isinstance(variables, dict):
        variables['opponent'] = opponent
        variables['stage'] = default_stage
    profiles = profile.get('launch_profiles')
    if isinstance(profiles, list) and profiles:
        # Keep the first profile conservative and user-editable, but make the intent concrete.
        profiles[0]['arguments'] = ['{character}', '{opponent}', '{stage}']
        profiles[0]['description'] = 'Default evidence run. Edit arguments for the specific command-line syntax of your engine build.'
    _write_json(root, profile_path, profile, result, changed=True)
    result.notes.append('Engine profile configured. Run Probe/Validate before live launch.')
    return result


def probe_engine_profile(root: Path) -> EvidenceCoreResult:
    return validate_engine_profile(Path(root))


def build_engine_launch_matrix(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Engine Launch Matrix')
    profile = _load_engine_profile(root)
    variables = profile.get('variables') if isinstance(profile.get('variables'), dict) else {}
    variables = {str(k): v for k, v in variables.items()}
    engine = str(profile.get('engine_executable') or '').strip()
    rows: List[Dict[str, object]] = []
    for item in profile.get('launch_profiles', []) if isinstance(profile.get('launch_profiles'), list) else []:
        if not isinstance(item, dict):
            continue
        args = item.get('arguments', []) if isinstance(item.get('arguments', []), list) else []
        expanded = [_expand_arg(a, variables) for a in args]
        rows.append({
            'enabled': 'yes' if _truthy(item.get('enabled')) else 'no',
            'profile_name': item.get('name', ''),
            'description': item.get('description', ''),
            'engine': engine,
            'arguments': ' '.join(expanded),
            'command_preview': ' '.join([engine] + expanded).strip(),
            'expected_returncodes': ','.join(str(x) for x in (item.get('expected_returncodes', [0]) if isinstance(item.get('expected_returncodes', [0]), list) else [0])),
        })
    out = _ec(root, 'engine')
    fields = ['enabled','profile_name','description','engine','arguments','command_preview','expected_returncodes']
    _write_csv(root, out / 'engine_launch_matrix.csv', rows, fields, result, changed=True)
    _write_text(root, out / 'ENGINE_LAUNCH_MATRIX.md', '# Engine Launch Matrix\n\nReview `engine_launch_matrix.csv` before live validation. Dry-run writes previews; live run executes enabled profiles with captured logs.', result, changed=True)
    return result


def run_engine_validation(root: Path, *, dry_run: bool = True, timeout_seconds: float = 12.0) -> EvidenceCoreResult:
    root = Path(root)
    # Write requested timeout into profile without erasing other fields.
    profile_path = _ec(root, 'engine') / 'engine_profile.json'
    profile = _load_engine_profile(root, profile_path)
    profile['timeout_seconds'] = int(max(1, timeout_seconds))
    _write_json(root, profile_path, profile, None, changed=True)
    return run_engine_profile(root, profile_path, dry_run=dry_run)


def ingest_engine_evidence(root: Path, evidence_folder: Optional[Path] = None) -> EvidenceCoreResult:
    return ingest_runtime_evidence(Path(root), evidence_folder)


def write_evidence_authority_report(root: Path) -> EvidenceCoreResult:
    return write_evidence_release_gate(Path(root))


def write_sff2_corpus_harness(root: Path, corpus_folder: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core SFF2 Corpus Harness')
    out = _ec(root, 'sff2_corpus')
    inbox = out / 'corpus_inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    cfg = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'version': EVIDENCE_CORE_VERSION,
        'default_corpus_folder': str(corpus_folder or inbox),
        'max_files': 250,
        'max_export_per_sff': 5,
        'notes': ['Drop SFF/SFF2/SND files into corpus_inbox or choose an external corpus folder from the UI.'],
    }
    _write_json(root, out / 'sff2_corpus_harness.json', cfg, result, changed=True)
    _write_text(root, inbox / 'DROP_SFF_SND_CORPUS_FILES_HERE.txt', 'Drop SFF/SFF2/SND corpus files here, then run SFF2 Corpus Validation.', result)
    return result


def run_sff2_corpus_validation(root: Path, corpus_folder: Optional[Path] = None) -> EvidenceCoreResult:
    root = Path(root)
    if corpus_folder is None:
        inbox = root / 'evidence_core' / 'sff2_corpus' / 'corpus_inbox'
        corpus_folder = inbox if inbox.exists() and any(inbox.rglob('*')) else root
    return run_binary_corpus_validation(root, corpus_folder)


def export_verified_candidate_install_sheet(root: Path) -> EvidenceCoreResult:
    return export_candidate_install_sheet(Path(root))


def export_runtime_tuning_sheet(root: Path) -> EvidenceCoreResult:
    return export_playtest_tuning_sheet(Path(root))


def apply_runtime_tuning_sheet(root: Path, sheet_path: Optional[Path] = None) -> EvidenceCoreResult:
    return apply_playtest_tuning_sheet(Path(root), sheet_path)


def write_playtest_closure_report(root: Path) -> EvidenceCoreResult:
    root = Path(root)
    result = EvidenceCoreResult('Evidence Core Playtest Closure Report')
    gate = write_evidence_release_gate(root)
    result.merge(gate, 'release gate')
    tuning_sheet = root / 'evidence_core' / 'tuning' / 'playtest_tuning_sheet.csv'
    scenarios = root / 'evidence_core' / 'scenarios' / 'runtime_scenario_sheet.csv'
    tuning_rows = _read_csv(tuning_sheet)
    scenario_rows = _read_csv(scenarios)
    applied_or_ready = [r for r in tuning_rows if _truthy(r.get('apply')) or str(r.get('observed_result', '')).strip()]
    passed = [r for r in scenario_rows if str(r.get('status', '')).strip().lower() in {'pass', 'passed', 'ok'}]
    data = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'runtime_scenarios': len(scenario_rows),
        'runtime_scenarios_passed': len(passed),
        'tuning_rows_with_observations_or_apply': len(applied_or_ready),
        'release_gate': str(root / 'evidence_core' / 'release_gate' / 'EVIDENCE_RELEASE_GATE.md'),
    }
    out = _ec(root, 'playtest_closure')
    _write_json(root, out / 'playtest_closure_report.json', data, result, changed=True)
    md = ['# Playtest Closure Report', '', f'- Runtime scenarios: {len(scenario_rows)}', f'- Scenarios marked pass: {len(passed)}', f'- Tuning rows with observations/apply: {len(applied_or_ready)}', '', 'A project is considered playtest-closed only when the Evidence Release Gate passes and key scenarios have attached evidence.']
    _write_text(root, out / 'PLAYTEST_CLOSURE_REPORT.md', '\n'.join(md), result, changed=True)
    return result


def ingest_engine_evidence(root: Path, folder: Optional[Path] = None) -> EvidenceCoreResult:
    """UI compatibility alias for ingesting external engine evidence."""
    return ingest_runtime_evidence(root, folder)
