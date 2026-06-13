from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import json
import os
import re
import shutil
import subprocess
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    backup_file,
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _timestamp,
    write_csv_artifact,
    write_text_artifact,
)
from .parsers import COMMON_ANIMS, parse_air, parse_code, read_text_safely, write_text_safely
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd

try:  # SFF2 maturity helpers were introduced in the v5.5 line.
    from .sff_codec import parse_sff2_standard, export_sff2_decoded_images, build_sff2_standard_from_manifest
except Exception:  # pragma: no cover - older package compatibility
    parse_sff2_standard = None  # type: ignore[assignment]
    export_sff2_decoded_images = None  # type: ignore[assignment]
    build_sff2_standard_from_manifest = None  # type: ignore[assignment]

AUTHORITY_CORE_VERSION = '7.0.0'
TEXT_CODE_EXTS = {'.cmd', '.cns', '.st'}
BINARY_EXTS = {'.sff', '.snd'}
EVIDENCE_EXTS = {'.txt', '.log', '.json', '.csv', '.md', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
ERROR_RE = re.compile(r'\b(error|exception|traceback|crash|failed|fatal|assert|panic|segmentation)\b', re.I)
WARN_RE = re.compile(r'\b(warn(?:ing)?|missing|not found|invalid|cannot|could not|unable|unsupported)\b', re.I)
TELEMETRY_RE = re.compile(r'\b(?:MFTELEMETRY|MFRUNTIME|MFSTAT)\b\s*[:=]?\s*(.*)$', re.I)


@dataclass
class AuthorityCoreResult:
    title: str = 'Authority Core'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, msg: object) -> None:
        self.warnings.append(str(msg))

    def add_note(self, msg: object) -> None:
        self.notes.append(str(msg))

    def merge(self, other: 'AuthorityCoreResult', label: Optional[str] = None) -> None:
        if not other:
            return
        prefix = f'{label}: ' if label else ''
        self.created_files.extend(prefix + x for x in other.created_files)
        self.changed_files.extend(prefix + x for x in other.changed_files)
        self.warnings.extend(prefix + x for x in other.warnings)
        self.notes.extend(prefix + x for x in other.notes)

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        if self.notes:
            lines += ['Notes:'] + [f'- {x}' for x in _uniq(self.notes)] + ['']
        if self.changed_files:
            lines += ['Changed files:'] + [f'- {x}' for x in _uniq(self.changed_files)] + ['']
        if self.created_files:
            lines += ['Created files/artifacts:'] + [f'- {x}' for x in _uniq(self.created_files)] + ['']
        if self.warnings:
            lines += ['Warnings:'] + [f'- {x}' for x in _uniq(self.warnings)] + ['']
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


def _authority_dir(root: Path) -> Path:
    out = Path(root) / 'authority_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(root: Path, path: Path, text: str, result: Optional[AuthorityCoreResult] = None, changed: bool = False) -> Path:
    existed = path.exists()
    if existed and changed:
        _backup_file(path)
    return write_text_artifact(path, text, result, root, changed, track_existing=True, writer=write_text_safely)


def _write_json(root: Path, path: Path, payload: object, result: Optional[AuthorityCoreResult] = None, changed: bool = False) -> Path:
    return _write(root, path, json.dumps(payload, indent=2, ensure_ascii=False), result=result, changed=changed)


def _read_json(path: Path, default: object) -> object:
    try:
        return json.loads(read_text_safely(path))
    except Exception:
        return default


def _csv_write(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    write_csv_artifact(path, rows, fields)


def _csv_read(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return [dict(row) for row in csv.DictReader(f)]


def _backup_file(path: Path) -> Optional[Path]:
    return backup_file(path, 'authority')


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    for ext in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        found = None
        try:
            found = find_character_file(root, ext)
        except Exception:
            found = None
        if found is None:
            exact = root / f'{root.name}.{ext}'
            if exact.exists():
                found = exact
        if found is None:
            hits = sorted(root.glob(f'*.{ext}'), key=lambda p: p.name.lower())
            found = hits[0] if hits else None
        out[ext] = found
    return out


def _code_files(root: Path) -> List[Path]:
    skip = {'__pycache__', '.mugenforge', 'authority_core', 'runtime_lab', 'binary_core', 'binary_deep', 'binary_maturity', 'forge_timeline', 'forge_polish', 'forge_beyond'}
    out: List[Path] = []
    for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()):
        if p.is_file() and p.suffix.lower() in TEXT_CODE_EXTS and not any(part in skip for part in p.parts):
            out.append(p)
    return out


def _first_int(value: object, default: int = 0) -> int:
    m = re.search(r'-?\d+', str(value or ''))
    return int(m.group(0)) if m else int(default)


def _project_char_name(root: Path) -> str:
    dpath = _discover_files(root).get('def')
    if dpath and dpath.exists():
        try:
            text = read_text_safely(dpath)
            m = re.search(r'^\s*name\s*=\s*"?([^";\n]+)', text, re.I | re.M)
            if m:
                return m.group(1).strip() or Path(root).name
        except Exception:
            pass
    return Path(root).name or 'character'


def _default_engine_config(root: Path) -> Dict[str, object]:
    char = _project_char_name(root)
    return {
        'schema': 'mugenforge.authority_core.engine_config.v1',
        'tool': 'MugenForge Studio Authority Core',
        'version': AUTHORITY_CORE_VERSION,
        'engine_profile': 'custom',
        'engine_executable': '',
        'working_directory': '',
        'timeout_seconds': 30,
        'character_name': char,
        'opponent_name': 'kfm',
        'stage': 'stages/kfm.def',
        'arguments': [],
        'auto_run_enabled': False,
        'binary_corpus_folder': '',
        'notes': [
            'Authority Core can run a configured local engine executable and capture stdout/stderr/result JSON.',
            'Leave auto_run_enabled false for one-click passes if you do not want external processes launched.',
            'For engines with custom CLI behavior, set arguments manually. Tokens {p1}, {p2}, {stage}, {log} are expanded.'
        ],
    }


def _engine_config_path(root: Path) -> Path:
    return _authority_dir(root) / 'engine_config.json'


def _read_engine_config(root: Path) -> Dict[str, object]:
    path = _engine_config_path(root)
    if path.exists():
        data = _read_json(path, {})
        if isinstance(data, dict):
            base = _default_engine_config(root)
            base.update(data)
            return base
    # Import useful Runtime Lab config if present.
    rt_cfg = Path(root) / 'runtime_lab' / 'runtime_config.json'
    base = _default_engine_config(root)
    if rt_cfg.exists():
        data = _read_json(rt_cfg, {})
        if isinstance(data, dict):
            base['engine_executable'] = data.get('engine_executable', base['engine_executable'])
            base['working_directory'] = data.get('engine_working_directory', data.get('working_directory', base['working_directory']))
            base['timeout_seconds'] = data.get('timeout_seconds', base['timeout_seconds'])
            base['arguments'] = data.get('arguments', base['arguments'])
    return base


def write_authority_dashboard(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Authority Core Dashboard')
    out = _authority_dir(root)
    cfg = _read_engine_config(root)
    cfg_path = _engine_config_path(root)
    if not cfg_path.exists():
        _write_json(root, cfg_path, cfg, result=result)
    text = f'''# Authority Core v{AUTHORITY_CORE_VERSION}

Authority Core turns the remaining honest limitations into executable validation workflows.

## What it adds

- External engine scenario runner with captured stdout/stderr/result JSON.
- Engine configuration validation and command expansion.
- Runtime evidence parser and runtime/static reconciliation reports.
- SFF/SND corpus validation over a user-provided folder.
- Unknown/corrupt binary triage records.
- Verified binary candidate install workflow with hashes, backups, and parser checks.
- Gameplay tuning feedback sheets that apply measured adjustments back into source text.
- Authority score that distinguishes static-only reports from engine-backed evidence.

## Important boundary

MugenForge cannot magically validate an engine or corpus that is not present on this machine. When you provide an engine executable and/or corpus folder in `authority_core/engine_config.json`, Authority Core runs those workflows and records exact evidence.

Generated: {datetime.now().isoformat(timespec='seconds')}
'''
    _write(root, out / 'AUTHORITY_CORE_START_HERE.md', text, result=result)
    return result


def write_engine_contract_profiles(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Engine Contract Profiles')
    out = _authority_dir(root) / 'engine_contracts'
    contracts = {
        'schema': 'mugenforge.authority_core.engine_contracts.v1',
        'profiles': [
            {
                'profile_id': 'custom',
                'description': 'Use explicit arguments from engine_config.json. Tokens are expanded before launch.',
                'argument_template': []
            },
            {
                'profile_id': 'mugen_classic_guess',
                'description': 'Common M.U.G.E.N-style positional launch guess. Verify against your engine build.',
                'argument_template': ['{p1}', '{p2}', '-s', '{stage}', '-log', '{log}']
            },
            {
                'profile_id': 'ikemen_go_guess',
                'description': 'Common IKEMEN GO-style launch guess. Verify against your build.',
                'argument_template': ['-p1', '{p1}', '-p2', '{p2}', '-s', '{stage}', '-log', '{log}']
            },
            {
                'profile_id': 'no_args_smoke',
                'description': 'Launch only the executable. Useful for fake-engine smoke tests and engines that read select.def.',
                'argument_template': []
            },
        ]
    }
    _write_json(root, out / 'engine_contract_profiles.json', contracts, result=result)
    rows = []
    for p in contracts['profiles']:
        rows.append({'profile_id': p['profile_id'], 'description': p['description'], 'argument_template': ' '.join(p['argument_template'])})
    _csv_write(out / 'engine_contract_profiles.csv', rows, ['profile_id', 'description', 'argument_template'])
    result.add_created(root, out / 'engine_contract_profiles.csv')
    cfg_path = _engine_config_path(root)
    if not cfg_path.exists():
        _write_json(root, cfg_path, _default_engine_config(root), result=result)
    result.add_note('Engine contract profiles were written. Use custom arguments for exact target-engine behavior.')
    return result


def validate_engine_configuration(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Engine Configuration Validation')
    out = _authority_dir(root) / 'engine_validation'
    cfg = _read_engine_config(root)
    findings: List[Dict[str, object]] = []
    def add(level: str, item: str, detail: str):
        findings.append({'level': level, 'item': item, 'detail': detail})
        if level.lower() in {'error', 'warning'}:
            result.add_warning(f'{item}: {detail}')
        else:
            result.add_note(f'{item}: {detail}')
    exe = str(cfg.get('engine_executable') or '').strip()
    if not exe:
        add('warning', 'engine_executable', 'blank; external runtime scenarios cannot be launched yet.')
    elif not Path(exe).exists():
        add('error', 'engine_executable', f'configured path does not exist: {exe}')
    else:
        add('ok', 'engine_executable', f'found: {exe}')
    cwd = str(cfg.get('working_directory') or '').strip()
    if cwd and not Path(cwd).exists():
        add('warning', 'working_directory', f'configured working directory does not exist: {cwd}')
    elif cwd:
        add('ok', 'working_directory', f'found: {cwd}')
    else:
        add('info', 'working_directory', 'blank; engine executable folder or project root will be used.')
    profile_ids = {'custom', 'mugen_classic_guess', 'ikemen_go_guess', 'no_args_smoke'}
    prof = str(cfg.get('engine_profile') or 'custom')
    if prof not in profile_ids:
        add('warning', 'engine_profile', f'unknown profile {prof}; custom arguments will be used.')
    else:
        add('ok', 'engine_profile', prof)
    files = _discover_files(root)
    for key in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        p = files.get(key)
        add('ok' if p and p.exists() else 'warning', f'project_{key}', _rel(root, p) if p else 'not found')
    _csv_write(out / 'engine_validation_findings.csv', findings, ['level', 'item', 'detail'])
    result.add_created(root, out / 'engine_validation_findings.csv')
    _write_json(root, out / 'engine_validation_findings.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'findings': findings}, result=result)
    return result


def _contract_args(profile: str) -> List[str]:
    if profile == 'mugen_classic_guess':
        return ['{p1}', '{p2}', '-s', '{stage}', '-log', '{log}']
    if profile == 'ikemen_go_guess':
        return ['-p1', '{p1}', '-p2', '{p2}', '-s', '{stage}', '-log', '{log}']
    return []


def _expand_args(args: Sequence[object], cfg: Dict[str, object], log_path: Path) -> List[str]:
    mapping = {
        'p1': str(cfg.get('character_name') or _project_char_name(log_path.parent)),
        'p2': str(cfg.get('opponent_name') or 'kfm'),
        'stage': str(cfg.get('stage') or 'stages/kfm.def'),
        'log': str(log_path),
    }
    out: List[str] = []
    for arg in args:
        s = str(arg)
        for key, val in mapping.items():
            s = s.replace('{' + key + '}', val)
        out.append(s)
    return out


def build_engine_command(root: Path, scenario_id: str = 'smoke') -> Tuple[List[str], Path, Dict[str, object]]:
    root = Path(root)
    cfg = _read_engine_config(root)
    exe = str(cfg.get('engine_executable') or '').strip()
    out_dir = _authority_dir(root) / 'engine_runs'
    log_path = out_dir / f'{scenario_id}_{_timestamp()}.engine.log'
    explicit_args = cfg.get('arguments') or []
    if not isinstance(explicit_args, list):
        explicit_args = []
    profile = str(cfg.get('engine_profile') or 'custom')
    template = explicit_args if explicit_args else _contract_args(profile)
    cmd = [exe] + _expand_args(template, cfg, log_path) if exe else []
    return cmd, log_path, cfg


def run_authoritative_engine_scenario(root: Path, scenario_id: str = 'smoke', timeout_seconds: Optional[float] = None, dry_run: bool = False) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Authoritative Engine Scenario')
    out_dir = _authority_dir(root) / 'engine_runs'
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd, log_path, cfg = build_engine_command(root, scenario_id=scenario_id)
    cwd_raw = str(cfg.get('working_directory') or '').strip()
    if not cwd_raw and cmd:
        try:
            cwd_raw = str(Path(cmd[0]).parent)
        except Exception:
            cwd_raw = str(root)
    cwd = cwd_raw or str(root)
    timeout = float(timeout_seconds if timeout_seconds is not None else cfg.get('timeout_seconds') or 30)
    tag = _timestamp()
    preview = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'scenario_id': scenario_id,
        'dry_run': bool(dry_run),
        'command': cmd,
        'working_directory': cwd,
        'timeout_seconds': timeout,
        'intended_log_path': str(log_path),
    }
    _write_json(root, out_dir / f'{scenario_id}_{tag}_command.json', preview, result=result)
    if dry_run:
        result.add_note('Dry-run command generated; no external engine process was launched.')
        if not cmd:
            result.add_warning('No command was built because engine_executable is blank.')
        return result
    if not cmd:
        result.add_warning('No engine_executable configured; external scenario not launched.')
        return result
    if not Path(cmd[0]).exists():
        result.add_warning(f'Engine executable does not exist: {cmd[0]}')
        return result
    try:
        proc = subprocess.run(cmd, cwd=cwd if Path(cwd).exists() else str(root), capture_output=True, text=True, timeout=max(1.0, timeout))
        stdout_path = out_dir / f'{scenario_id}_{tag}_stdout.txt'
        stderr_path = out_dir / f'{scenario_id}_{tag}_stderr.txt'
        stdout_path.write_text(proc.stdout or '', encoding='utf-8', errors='replace')
        stderr_path.write_text(proc.stderr or '', encoding='utf-8', errors='replace')
        result.add_created(root, stdout_path)
        result.add_created(root, stderr_path)
        payload = dict(preview, returncode=proc.returncode, stdout_file=_rel(root, stdout_path), stderr_file=_rel(root, stderr_path), status='pass' if proc.returncode == 0 else 'fail')
        result_path = out_dir / f'{scenario_id}_{tag}_result.json'
        _write_json(root, result_path, payload, result=result)
        if proc.returncode == 0:
            result.add_note('External engine process exited with code 0. This run is captured as runtime evidence.')
        else:
            result.add_warning(f'External engine process exited with code {proc.returncode}.')
    except subprocess.TimeoutExpired as exc:
        timeout_path = out_dir / f'{scenario_id}_{tag}_timeout.json'
        _write_json(root, timeout_path, dict(preview, status='timeout', stdout=exc.stdout or '', stderr=exc.stderr or ''), result=result)
        result.add_warning(f'External engine process timed out after {timeout} seconds.')
    except Exception as exc:
        error_path = out_dir / f'{scenario_id}_{tag}_error.json'
        _write_json(root, error_path, dict(preview, status='error', error=str(exc)), result=result)
        result.add_warning(f'External engine process failed: {exc}')
    return result


def parse_engine_run_results(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Engine Run Result Parser')
    out_dir = _authority_dir(root) / 'engine_runs'
    report_dir = _authority_dir(root) / 'engine_run_reports'
    rows: List[Dict[str, object]] = []
    if out_dir.exists():
        for p in sorted(out_dir.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file():
                continue
            if p.suffix.lower() in {'.txt', '.log'} or p.name.endswith('_stdout.txt') or p.name.endswith('_stderr.txt'):
                try:
                    text = read_text_safely(p)
                except Exception:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    sev = ''
                    if ERROR_RE.search(line):
                        sev = 'error'
                    elif WARN_RE.search(line):
                        sev = 'warning'
                    if sev:
                        rows.append({'file': _rel(root, p), 'line': lineno, 'severity': sev, 'message': line[:500]})
            elif p.name.endswith('_result.json') or p.name.endswith('_timeout.json') or p.name.endswith('_error.json'):
                data = _read_json(p, {})
                if isinstance(data, dict):
                    status = data.get('status') or ('pass' if data.get('returncode') == 0 else 'fail')
                    rows.append({'file': _rel(root, p), 'line': '', 'severity': 'run_status', 'message': f'{status}; returncode={data.get("returncode", "")} scenario={data.get("scenario_id", "")}'})
    fields = ['file', 'line', 'severity', 'message']
    _csv_write(report_dir / 'engine_run_findings.csv', rows, fields)
    result.add_created(root, report_dir / 'engine_run_findings.csv')
    summary = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'finding_count': len(rows),
        'errors': sum(1 for r in rows if r.get('severity') == 'error'),
        'warnings': sum(1 for r in rows if r.get('severity') == 'warning'),
        'run_status_rows': sum(1 for r in rows if r.get('severity') == 'run_status'),
    }
    _write_json(root, report_dir / 'engine_run_summary.json', summary, result=result)
    result.add_note(f'Parsed {len(rows)} engine-run finding/status rows.')
    return result


def _telemetry_rows(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for folder in [_authority_dir(root) / 'engine_runs', Path(root) / 'runtime_lab', _authority_dir(root) / 'evidence']:
        if not folder.exists():
            continue
        for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in {'.txt', '.log', '.md'}:
                continue
            try:
                lines = read_text_safely(p).splitlines()
            except Exception:
                continue
            for lineno, line in enumerate(lines, 1):
                m = TELEMETRY_RE.search(line)
                if not m:
                    continue
                payload = m.group(1).strip()
                row: Dict[str, object] = {'file': _rel(root, p), 'line': lineno, 'raw': payload}
                for key, val in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s,;]+)', payload):
                    row[key.lower()] = val
                rows.append(row)
    return rows


def write_runtime_reconciliation_report(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Runtime Reconciliation Report')
    out_dir = _authority_dir(root) / 'runtime_reconciliation'
    static_rows: List[Dict[str, object]] = []
    files = _discover_files(root)
    air = files.get('air')
    if air and air.exists():
        try:
            for action in parse_air(read_text_safely(air)):
                static_rows.append({'kind': 'air_action', 'id': action.number, 'frames': len(action.frames), 'ticks': sum(max(0, f.ticks) for f in action.frames), 'source': _rel(root, air)})
        except Exception as exc:
            result.add_warning(f'AIR parse failed during reconciliation: {exc}')
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for st in scan.states:
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype == 'hitdef':
                    static_rows.append({'kind': 'hitdef', 'id': st.number, 'frames': '', 'ticks': '', 'source': f'{_rel(root, path)}:{ctrl.line}', 'damage': ctrl.values.get('damage', ''), 'trigger1': ctrl.values.get('trigger1', '')})
    telemetry = _telemetry_rows(root)
    _csv_write(out_dir / 'static_timing_and_hitdefs.csv', static_rows, sorted({k for row in static_rows for k in row.keys()} or {'kind'}))
    result.add_created(root, out_dir / 'static_timing_and_hitdefs.csv')
    _csv_write(out_dir / 'runtime_telemetry_rows.csv', telemetry, sorted({k for row in telemetry for k in row.keys()} or {'file'}))
    result.add_created(root, out_dir / 'runtime_telemetry_rows.csv')
    summary = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'static_rows': len(static_rows),
        'telemetry_rows': len(telemetry),
        'runtime_anchored': bool(telemetry),
        'note': 'Rows become runtime-anchored when logs contain MFTELEMETRY/MFRUNTIME/MFSTAT helper output.'
    }
    _write_json(root, out_dir / 'runtime_reconciliation_summary.json', summary, result=result)
    md = ['# Runtime Reconciliation Report', '', f'Static source rows: {len(static_rows)}', f'Runtime telemetry rows: {len(telemetry)}', '']
    if telemetry:
        md.append('Runtime telemetry was found, so static estimates can be compared against captured engine evidence.')
    else:
        md.append('No MugenForge telemetry markers were found yet. Install/run the runtime overlay or import engine logs containing MFTELEMETRY/MFRUNTIME/MFSTAT lines.')
    _write(root, out_dir / 'RUNTIME_RECONCILIATION_REPORT.md', '\n'.join(md), result=result)
    return result


def _corpus_root(root: Path, corpus_folder: Optional[Path | str] = None) -> Path:
    if corpus_folder:
        return Path(corpus_folder)
    cfg = _read_engine_config(root)
    val = str(cfg.get('binary_corpus_folder') or '').strip()
    if val:
        return Path(val)
    return Path(root)


def write_sff_snd_corpus_validation_suite(root: Path, corpus_folder: Optional[Path | str] = None) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('SFF/SND Corpus Validation Suite')
    corpus = _corpus_root(root, corpus_folder)
    out_dir = _authority_dir(root) / 'corpus_validation'
    rows: List[Dict[str, object]] = []
    if not corpus.exists():
        result.add_warning(f'Corpus folder does not exist: {corpus}')
    else:
        for p in sorted(corpus.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in BINARY_EXTS:
                continue
            row: Dict[str, object] = {
                'file': str(p), 'relative': _rel(corpus, p), 'kind': p.suffix.lower().lstrip('.'),
                'bytes': p.stat().st_size, 'sha256': _sha256(p), 'status': 'unknown', 'variant': '', 'records': '', 'warnings': '', 'decodable': '',
            }
            if p.suffix.lower() == '.sff':
                try:
                    info = read_sff(p)
                    row.update(status='parsed', variant=info.variant, records=len(info.sprites), warnings=' | '.join(info.warnings[:8]))
                    if parse_sff2_standard is not None:
                        try:
                            s2 = parse_sff2_standard(p)  # type: ignore[misc]
                            row.update(status='sff2_standard_parsed', variant='sff2-standard', records=len(s2.sprites), decodable=getattr(s2, 'decodable_count', ''))
                        except Exception:
                            pass
                except Exception as exc:
                    row.update(status='parse_failed', warnings=str(exc))
            elif p.suffix.lower() == '.snd':
                try:
                    info = read_snd(p)
                    row.update(status='parsed', variant='ElecbyteSnd' if info.has_signature else 'riff-scan', records=len(info.sounds), warnings=' | '.join(info.warnings[:8]))
                except Exception as exc:
                    row.update(status='parse_failed', warnings=str(exc))
            rows.append(row)
    fields = ['file', 'relative', 'kind', 'bytes', 'sha256', 'status', 'variant', 'records', 'decodable', 'warnings']
    _csv_write(out_dir / 'sff_snd_corpus_validation.csv', rows, fields)
    result.add_created(root, out_dir / 'sff_snd_corpus_validation.csv')
    summary = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'corpus_folder': str(corpus),
        'files_scanned': len(rows),
        'sff_files': sum(1 for r in rows if r.get('kind') == 'sff'),
        'snd_files': sum(1 for r in rows if r.get('kind') == 'snd'),
        'parse_failed': sum(1 for r in rows if r.get('status') == 'parse_failed'),
        'standard_sff2': sum(1 for r in rows if r.get('status') == 'sff2_standard_parsed'),
    }
    _write_json(root, out_dir / 'sff_snd_corpus_validation_summary.json', summary, result=result)
    result.add_note(f'Corpus validation scanned {len(rows)} SFF/SND file(s).')
    return result


def triage_unknown_binary_layouts(root: Path, corpus_folder: Optional[Path | str] = None) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Unknown Binary Layout Triage')
    corpus = _corpus_root(root, corpus_folder)
    out_dir = _authority_dir(root) / 'unknown_binary_triage'
    validation_csv = _authority_dir(root) / 'corpus_validation' / 'sff_snd_corpus_validation.csv'
    if not validation_csv.exists():
        write_sff_snd_corpus_validation_suite(root, corpus)
    rows = []
    for row in _csv_read(validation_csv):
        status = str(row.get('status', '')).lower()
        warnings = str(row.get('warnings', '')).lower()
        if status in {'parse_failed', 'unknown'} or 'unsupported' in warnings or 'invalid' in warnings:
            p = Path(row.get('file', ''))
            head = ''
            tail = ''
            if p.exists():
                data = p.read_bytes()
                head = data[:64].hex(' ')
                tail = data[-64:].hex(' ') if data else ''
            rows.append({
                'file': row.get('file', ''), 'kind': row.get('kind', ''), 'status': row.get('status', ''),
                'bytes': row.get('bytes', ''), 'sha256': row.get('sha256', ''), 'header64_hex': head,
                'tail64_hex': tail, 'recommended_action': 'manual review or external codec sample needed',
                'warnings': row.get('warnings', ''),
            })
    fields = ['file', 'kind', 'status', 'bytes', 'sha256', 'header64_hex', 'tail64_hex', 'recommended_action', 'warnings']
    _csv_write(out_dir / 'unknown_binary_triage.csv', rows, fields)
    result.add_created(root, out_dir / 'unknown_binary_triage.csv')
    _write_json(root, out_dir / 'unknown_binary_triage.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'count': len(rows), 'items': rows}, result=result)
    result.add_note(f'Triage rows: {len(rows)}.')
    return result


def export_binary_install_sheet(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Verified Binary Install Sheet')
    out_dir = _authority_dir(root) / 'verified_binary_install'
    files = _discover_files(root)
    candidates: List[Path] = []
    for folder in [root / 'binary_core', root / 'binary_deep', root / 'binary_maturity', root / 'codec_core', root / 'authority_core']:
        if not folder.exists():
            continue
        for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file() and p.suffix.lower() in BINARY_EXTS and '.bak_' not in p.name:
                candidates.append(p)
    rows: List[Dict[str, object]] = []
    for idx, cand in enumerate(candidates):
        kind = cand.suffix.lower().lstrip('.')
        target = files.get(kind)
        status = 'pending'
        verify = ''
        try:
            if kind == 'sff':
                info = read_sff(cand)
                verify = f'{info.variant}; sprites={len(info.sprites)}; warnings={len(info.warnings)}'
                status = 'verified' if info.variant != 'unknown' else 'needs_review'
            else:
                info = read_snd(cand)
                verify = f'sounds={len(info.sounds)}; warnings={len(info.warnings)}'
                status = 'verified' if info.sounds or info.has_signature else 'needs_review'
        except Exception as exc:
            status = 'failed'
            verify = str(exc)
        rows.append({
            'enabled': 'no', 'row_id': idx + 1, 'kind': kind, 'candidate_path': str(cand),
            'candidate_sha256': _sha256(cand), 'target_path': str(target or (root / f'{root.name}.{kind}')),
            'verification_status': status, 'verification_detail': verify,
            'install_mode': 'backup_then_replace', 'notes': 'Set enabled=yes only after verifying this candidate in your target engine.'
        })
    fields = ['enabled', 'row_id', 'kind', 'candidate_path', 'candidate_sha256', 'target_path', 'verification_status', 'verification_detail', 'install_mode', 'notes']
    _csv_write(out_dir / 'verified_binary_install_sheet.csv', rows, fields)
    result.add_created(root, out_dir / 'verified_binary_install_sheet.csv')
    result.add_note(f'Install sheet rows: {len(rows)}. Nothing is installed until enabled=yes.')
    return result


def install_verified_binary_candidates(root: Path, sheet_path: Optional[Path | str] = None) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Verified Binary Candidate Installer')
    out_dir = _authority_dir(root) / 'verified_binary_install'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'verified_binary_install_sheet.csv'
    if not sheet.exists():
        export_binary_install_sheet(root)
    rows = _csv_read(sheet)
    installed: List[Dict[str, object]] = []
    for row in rows:
        if str(row.get('enabled', 'no')).strip().lower() not in {'yes', 'y', '1', 'true'}:
            continue
        cand = Path(row.get('candidate_path', ''))
        target = Path(row.get('target_path', ''))
        expected_hash = str(row.get('candidate_sha256', '')).strip()
        if not cand.exists():
            result.add_warning(f'Candidate missing: {cand}')
            continue
        actual_hash = _sha256(cand)
        if expected_hash and actual_hash != expected_hash:
            result.add_warning(f'Hash mismatch for {cand}; expected {expected_hash}, got {actual_hash}.')
            continue
        kind = str(row.get('kind', cand.suffix.lower().lstrip('.'))).lower()
        try:
            if kind == 'sff':
                read_sff(cand)
            elif kind == 'snd':
                read_snd(cand)
            else:
                result.add_warning(f'Unsupported install kind: {kind}')
                continue
        except Exception as exc:
            result.add_warning(f'Verification failed for {cand}: {exc}')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = _backup_file(target) if target.exists() else None
        shutil.copy2(cand, target)
        result.add_changed(root, target)
        installed.append({'candidate': str(cand), 'target': str(target), 'candidate_sha256': actual_hash, 'backup': str(backup or '')})
    _write_json(root, out_dir / 'verified_binary_install_log.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'installed': installed}, result=result, changed=True)
    result.add_note(f'Installed {len(installed)} verified candidate(s).')
    return result


def _hitdef_locations(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            text = read_text_safely(path)
            scan = parse_code(text)
        except Exception:
            continue
        for st in scan.states:
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype == 'hitdef':
                    rows.append({'file': _rel(root, path), 'state': st.number, 'line': ctrl.line, 'damage': ctrl.values.get('damage', ''), 'attr': ctrl.values.get('attr', ''), 'trigger1': ctrl.values.get('trigger1', '')})
    return rows


def write_gameplay_tuning_feedback_sheet(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Gameplay Tuning Feedback Sheet')
    out_dir = _authority_dir(root) / 'gameplay_tuning'
    rows: List[Dict[str, object]] = []
    for idx, hit in enumerate(_hitdef_locations(root), start=1):
        rows.append({
            'enabled': 'no', 'row_id': idx, 'kind': 'hitdef_damage', 'file': hit['file'], 'state': hit['state'],
            'line': hit['line'], 'current_value': hit['damage'], 'new_value': '', 'evidence_path': '',
            'tester_note': 'Enter measured/tuned damage as e.g. 45,5 then set enabled=yes.'
        })
    air = _discover_files(root).get('air')
    if air and air.exists():
        try:
            for action in parse_air(read_text_safely(air)):
                rows.append({
                    'enabled': 'no', 'row_id': len(rows) + 1, 'kind': 'air_action_ticks_scale', 'file': _rel(root, air),
                    'state': action.number, 'line': '', 'current_value': sum(max(0, f.ticks) for f in action.frames),
                    'new_value': '', 'evidence_path': '', 'tester_note': 'Enter scale like 0.90 or 1.10 to retime all positive ticks in this action.'
                })
        except Exception as exc:
            result.add_warning(f'AIR parse failed: {exc}')
    fields = ['enabled', 'row_id', 'kind', 'file', 'state', 'line', 'current_value', 'new_value', 'evidence_path', 'tester_note']
    _csv_write(out_dir / 'gameplay_tuning_feedback_sheet.csv', rows, fields)
    result.add_created(root, out_dir / 'gameplay_tuning_feedback_sheet.csv')
    result.add_note(f'Gameplay tuning rows: {len(rows)}.')
    return result


def _replace_hitdef_damage(text: str, target_line: int, new_value: str) -> Tuple[str, bool]:
    lines = text.splitlines()
    idx = max(0, int(target_line) - 1)
    # Search near the parsed controller line for a damage assignment before the next block header.
    for j in range(idx, min(len(lines), idx + 80)):
        if j > idx and re.match(r'^\s*\[', lines[j]):
            break
        if re.match(r'^\s*damage\s*=', lines[j], re.I):
            prefix = re.match(r'^(\s*damage\s*=\s*)', lines[j], re.I).group(1)  # type: ignore[union-attr]
            comment = ''
            if ';' in lines[j]:
                comment = ' ;' + lines[j].split(';', 1)[1]
            lines[j] = prefix + str(new_value).strip() + comment
            return '\n'.join(lines) + ('\n' if text.endswith('\n') else ''), True
    return text, False


def _scale_air_action_ticks(text: str, action_no: int, scale: float) -> Tuple[str, bool]:
    lines = text.splitlines()
    in_action = False
    changed = False
    action_re = re.compile(r'^\s*\[\s*Begin\s+Action\s+(-?\d+)\s*\]', re.I)
    frame_re = re.compile(r'^(\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*)(-?\d+)(.*)$')
    for i, line in enumerate(lines):
        am = action_re.match(line)
        if am:
            in_action = int(am.group(1)) == int(action_no)
            continue
        if in_action and line.lstrip().startswith('['):
            in_action = False
        if not in_action:
            continue
        fm = frame_re.match(line)
        if fm:
            old = int(fm.group(2))
            if old > 0:
                new = max(1, int(round(old * scale)))
                if new != old:
                    lines[i] = fm.group(1) + str(new) + fm.group(3)
                    changed = True
    return '\n'.join(lines) + ('\n' if text.endswith('\n') else ''), changed


def apply_gameplay_tuning_feedback_sheet(root: Path, sheet_path: Optional[Path | str] = None) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Gameplay Tuning Feedback Apply')
    out_dir = _authority_dir(root) / 'gameplay_tuning'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'gameplay_tuning_feedback_sheet.csv'
    if not sheet.exists():
        write_gameplay_tuning_feedback_sheet(root)
    rows = _csv_read(sheet)
    grouped_changes: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        if str(row.get('enabled', 'no')).strip().lower() not in {'yes', 'y', '1', 'true'}:
            continue
        rel = row.get('file', '')
        if not rel:
            continue
        grouped_changes.setdefault((root / rel).resolve(), []).append(row)
    applied: List[Dict[str, object]] = []
    for path, changes in grouped_changes.items():
        if not path.exists():
            result.add_warning(f'Tuning target not found: {path}')
            continue
        text = read_text_safely(path)
        original = text
        for row in changes:
            kind = str(row.get('kind', '')).lower()
            new_value = str(row.get('new_value', '')).strip()
            if not new_value:
                continue
            if kind == 'hitdef_damage':
                text, ok = _replace_hitdef_damage(text, _first_int(row.get('line'), 0), new_value)
                applied.append({'file': _rel(root, path), 'kind': kind, 'ok': ok, 'new_value': new_value})
            elif kind == 'air_action_ticks_scale':
                try:
                    scale = float(new_value)
                except Exception:
                    result.add_warning(f'Invalid AIR tick scale {new_value!r} for row {row.get("row_id")}.')
                    continue
                text, ok = _scale_air_action_ticks(text, _first_int(row.get('state'), 0), scale)
                applied.append({'file': _rel(root, path), 'kind': kind, 'ok': ok, 'new_value': new_value})
        if text != original:
            _backup_file(path)
            write_text_safely(path, text)
            result.add_changed(root, path)
    _write_json(root, out_dir / 'gameplay_tuning_apply_log.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'applied': applied}, result=result, changed=True)
    result.add_note(f'Applied {sum(1 for x in applied if x.get("ok"))} gameplay tuning change(s).')
    return result


def write_authority_score(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Authority Score')
    out_dir = _authority_dir(root) / 'authority_score'
    score = 100
    deductions: List[Dict[str, object]] = []
    upgrades: List[str] = []
    def ding(points: int, reason: str):
        nonlocal score
        if points > 0 and reason:
            score -= points
            deductions.append({'points': points, 'reason': reason})
    files = _discover_files(root)
    missing = [k for k in ('def', 'air', 'cmd', 'cns', 'sff', 'snd') if not files.get(k)]
    ding(min(35, len(missing) * 7), f'Missing project files: {", ".join(missing)}' if missing else '')
    run_summary = _authority_dir(root) / 'engine_run_reports' / 'engine_run_summary.json'
    engine_runs = {}
    if run_summary.exists():
        data = _read_json(run_summary, {})
        if isinstance(data, dict):
            engine_runs = data
            ding(min(40, int(data.get('errors', 0) or 0) * 10), f'Engine-run errors detected: {data.get("errors", 0)}')
            ding(min(15, int(data.get('warnings', 0) or 0) * 3), f'Engine-run warnings detected: {data.get("warnings", 0)}')
            if int(data.get('run_status_rows', 0) or 0) > 0:
                upgrades.append('engine_run_evidence_present')
    else:
        ding(15, 'No parsed engine-run evidence yet.')
    recon = _authority_dir(root) / 'runtime_reconciliation' / 'runtime_reconciliation_summary.json'
    if recon.exists():
        data = _read_json(recon, {})
        if isinstance(data, dict) and data.get('runtime_anchored'):
            upgrades.append('runtime_telemetry_present')
        else:
            ding(5, 'No runtime telemetry rows found in reconciliation report.')
    else:
        ding(5, 'Runtime reconciliation report has not been generated.')
    corpus = _authority_dir(root) / 'corpus_validation' / 'sff_snd_corpus_validation_summary.json'
    if corpus.exists():
        data = _read_json(corpus, {})
        if isinstance(data, dict):
            fails = int(data.get('parse_failed', 0) or 0)
            ding(min(20, fails * 4), f'Corpus parse failures: {fails}')
            if int(data.get('files_scanned', 0) or 0) > 1:
                upgrades.append('binary_corpus_validation_present')
    else:
        ding(5, 'Binary corpus validation has not been generated.')
    score = max(0, min(100, score))
    evidence_backed = 'engine_run_evidence_present' in upgrades
    verdict = 'engine_backed_release_candidate' if score >= 90 and evidence_backed else 'static_plus_evidence_candidate' if score >= 80 else 'needs_runtime_evidence' if score >= 60 else 'not_ready'
    payload = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'score': score,
        'verdict': verdict,
        'evidence_backed': evidence_backed,
        'deductions': deductions,
        'upgrades': upgrades,
        'engine_run_summary': engine_runs,
    }
    _write_json(root, out_dir / 'authority_score.json', payload, result=result)
    lines = ['# Authority Score', '', f'Generated: {payload["generated"]}', '', f'Score: **{score}/100**', f'Verdict: `{verdict}`', '', '## Evidence status', '']
    lines.append(f'- External engine evidence present: {"yes" if evidence_backed else "no"}')
    lines.append(f'- Runtime telemetry present: {"yes" if "runtime_telemetry_present" in upgrades else "no"}')
    lines.append(f'- Binary corpus validation present: {"yes" if "binary_corpus_validation_present" in upgrades else "no"}')
    lines += ['', '## Deductions', '']
    if deductions:
        lines += [f'- -{d["points"]}: {d["reason"]}' for d in deductions]
    else:
        lines.append('- None')
    lines += ['', '## Meaning', '', 'An `engine_backed_release_candidate` verdict requires captured local engine run evidence. Static-only reports cannot receive that verdict.']
    _write(root, out_dir / 'AUTHORITY_SCORE.md', '\n'.join(lines), result=result)
    result.add_note(f'Authority score: {score}/100 ({verdict}).')
    return result


def build_authority_core_bundle(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('Authority Core Bundle')
    base = _authority_dir(root)
    out_dir = base / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_authority_core_bundle_{_timestamp()}.zip'
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for folder in [base, root / 'runtime_lab', root / 'binary_core', root / 'binary_deep', root / 'binary_maturity']:
            if not folder.exists():
                continue
            for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()):
                if p.is_file() and p != out and 'bundles' not in p.parts:
                    zf.write(p, p.relative_to(root))
    result.add_created(root, out)
    return result


def run_authority_core_pass(root: Path) -> AuthorityCoreResult:
    root = Path(root)
    result = AuthorityCoreResult('One-Click Authority Core Pass')
    steps = [
        ('dashboard', write_authority_dashboard),
        ('engine contracts', write_engine_contract_profiles),
        ('engine validation', validate_engine_configuration),
        ('engine run parser', parse_engine_run_results),
        ('runtime reconciliation', write_runtime_reconciliation_report),
        ('corpus validation', write_sff_snd_corpus_validation_suite),
        ('unknown triage', triage_unknown_binary_layouts),
        ('binary install sheet', export_binary_install_sheet),
        ('gameplay tuning sheet', write_gameplay_tuning_feedback_sheet),
        ('authority score', write_authority_score),
        ('bundle', build_authority_core_bundle),
    ]
    for label, fn in steps:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    cfg = _read_engine_config(root)
    if bool(cfg.get('auto_run_enabled')):
        try:
            result.merge(run_authoritative_engine_scenario(root, dry_run=False), 'external engine auto-run')
            result.merge(parse_engine_run_results(root), 'engine run parser after auto-run')
            result.merge(write_authority_score(root), 'authority score after auto-run')
        except Exception as exc:
            result.add_warning(f'external engine auto-run failed: {exc}')
    else:
        result.add_note('auto_run_enabled is false; one-click pass did not launch an external process.')
    return result
