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
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file

RUNTIME_LAB_VERSION = "6.1.0"
TEXT_CODE_EXTS = {'.cmd', '.cns', '.st'}
EVIDENCE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.txt', '.log', '.csv', '.json', '.md'}
LOG_PATTERNS = [
    ('error', re.compile(r'\b(error|exception|traceback|crash|failed|fatal)\b', re.I)),
    ('warning', re.compile(r'\b(warn(?:ing)?|missing|not found|invalid|cannot|could not|unable)\b', re.I)),
    ('asset', re.compile(r'\b(sprite|anim|sound|snd|sff|palette|pal|stage)\b.*\b(missing|not found|invalid|failed)\b', re.I)),
    ('state', re.compile(r'\b(statedef|changestate|selfstate|state)\b.*\b(missing|invalid|not found|failed)\b', re.I)),
]


@dataclass
class RuntimeLabResult:
    title: str = 'Runtime Lab'
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

    def merge(self, other: 'RuntimeLabResult', label: Optional[str] = None) -> None:
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


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _runtime_dir(root: Path) -> Path:
    out = Path(root) / 'runtime_lab'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(root: Path, path: Path, text: str, result: Optional[RuntimeLabResult] = None, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed and changed:
        _backup_text(path)
    write_text_safely(path, text.rstrip() + '\n')
    if result is not None:
        (result.changed_files if existed or changed else result.created_files).append(_rel(root, path))
    return path


def _write_json(root: Path, path: Path, payload: object, result: Optional[RuntimeLabResult] = None, changed: bool = False) -> Path:
    return _write(root, path, json.dumps(payload, indent=2, ensure_ascii=False), result=result, changed=changed)


def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _backup_text(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    backup = path.with_name(path.name + f'.bak_runtime_{_timestamp()}')
    try:
        backup.write_text(read_text_safely(path), encoding='utf-8', errors='replace')
    except TypeError:
        backup.write_bytes(path.read_bytes())
    return backup


def _code_files(root: Path) -> List[Path]:
    skip = {'__pycache__', 'runtime_lab', 'binary_core', 'binary_mature_lab', 'forge_timeline', 'forge_polish', 'forge_beyond'}
    out: List[Path] = []
    for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()):
        if p.is_file() and p.suffix.lower() in TEXT_CODE_EXTS and not any(part in skip for part in p.parts):
            out.append(p)
    return out


def _main_def(root: Path) -> Optional[Path]:
    exact = Path(root) / f'{Path(root).name}.def'
    if exact.exists():
        return exact
    defs = sorted(Path(root).glob('*.def'), key=lambda p: p.name.lower())
    return defs[0] if defs else None


def _char_name(root: Path) -> str:
    dpath = _main_def(root)
    if dpath and dpath.exists():
        try:
            info = parse_def(read_text_safely(dpath)).get('info')
            if info:
                for key in ('name', 'displayname'):
                    val = info.values.get(key)
                    if val:
                        return val.strip().strip('"') or Path(root).name
        except Exception:
            pass
    return Path(root).name or 'character'


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    dpath = _main_def(root)
    if dpath:
        out['def'] = dpath
    refs: Dict[str, str] = {}
    if dpath and dpath.exists():
        try:
            files = parse_def(read_text_safely(dpath)).get('files')
            if files:
                refs = {k.lower(): v.strip().strip('"') for k, v in files.values.items()}
        except Exception:
            refs = {}
    for key, ext in [('anim', 'air'), ('cmd', 'cmd'), ('cns', 'cns'), ('sprite', 'sff'), ('sound', 'snd')]:
        path: Optional[Path] = None
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                path = p
        if path is None:
            try:
                path = find_character_file(root, ext)
            except Exception:
                path = None
        if path is None:
            exact = root / f'{root.name}.{ext}'
            if exact.exists():
                path = exact
        if path is None:
            hits = sorted(root.glob(f'*.{ext}'), key=lambda p: p.name.lower())
            path = hits[0] if hits else None
        out[ext] = path
    return out


def _read_runtime_config(root: Path) -> Dict[str, object]:
    cfg = _runtime_dir(root) / 'runtime_config.json'
    if cfg.exists():
        try:
            return json.loads(read_text_safely(cfg))
        except Exception:
            pass
    return _default_config(root)


def _default_config(root: Path) -> Dict[str, object]:
    char = _char_name(root)
    return {
        'schema': 'mugenforge.runtime_lab.config.v1',
        'tool': 'MugenForge Studio Runtime Lab',
        'engine_type': 'mugen_or_ikemen_go',
        'engine_executable': '',
        'engine_working_directory': '',
        'project_character_name': char,
        'default_opponent': 'kfm',
        'default_stage': 'stages/kfm.def',
        'log_paths': ['mugen.log', 'Ikemen.log', 'runtime_lab/logs'],
        'evidence_folder': 'runtime_lab/evidence',
        'notes': [
            'Set engine_executable before using generated launch scripts.',
            'Generated commands are editable harnesses. Always verify command-line flags with your target engine build.',
            'Runtime Lab does not simulate M.U.G.E.N; it organizes external engine tests and evidence.'
        ],
    }


def _csv_write(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, '') for k in fields})


def _csv_read(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return [dict(row) for row in csv.DictReader(f)]


def _commands(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        if path.suffix.lower() != '.cmd':
            continue
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for cmd in scan.commands:
            rows.append({'file': _rel(root, path), 'line': cmd.line, 'name': cmd.name, 'command': cmd.command, 'time': cmd.time or '', 'buffer_time': cmd.buffer_time or ''})
    return rows


def _states(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for st in scan.states:
            rows.append({'file': _rel(root, path), 'line': st.line, 'state': st.number, 'anim': st.values.get('anim', ''), 'type': st.values.get('type', ''), 'movetype': st.values.get('movetype', ''), 'controllers': len(st.controllers)})
    return rows


def _hitdefs(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for st in scan.states:
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype == 'hitdef':
                    rows.append({
                        'file': _rel(root, path), 'line': ctrl.line, 'state': st.number, 'anim': st.values.get('anim', st.number),
                        'damage': ctrl.values.get('damage', ''), 'attr': ctrl.values.get('attr', ''), 'trigger1': ctrl.values.get('trigger1', ''),
                        'hitsound': ctrl.values.get('hitsound', ''), 'guardsound': ctrl.values.get('guardsound', ''),
                    })
    return rows


def write_runtime_config_template(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Config Template')
    rd = _runtime_dir(root)
    cfg = rd / 'runtime_config.json'
    existed = cfg.exists()
    data = _read_runtime_config(root) if existed else _default_config(root)
    # Refresh project character name without clobbering user-specified engine path.
    data.setdefault('project_character_name', _char_name(root))
    data['project_character_name'] = str(data.get('project_character_name') or _char_name(root))
    _write_json(root, cfg, data, result=result, changed=existed)
    (rd / 'logs').mkdir(parents=True, exist_ok=True)
    (rd / 'evidence').mkdir(parents=True, exist_ok=True)
    result.add_created(root, rd / 'logs')
    result.add_created(root, rd / 'evidence')
    result.add_note('Edit runtime_lab/runtime_config.json to point at your M.U.G.E.N or IKEMEN executable before running generated launcher scripts.')
    return result


def export_runtime_launch_profiles(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Launch Profiles')
    rd = _runtime_dir(root)
    cfg = _read_runtime_config(root)
    char = str(cfg.get('project_character_name') or _char_name(root))
    opponent = str(cfg.get('default_opponent') or 'kfm')
    stage = str(cfg.get('default_stage') or 'stages/kfm.def')
    rows = [
        {'enabled': 'yes', 'profile_id': 'smoke_boot_p1_vs_kfm', 'engine_type': cfg.get('engine_type', 'mugen_or_ikemen_go'), 'p1': char, 'p2': opponent, 'stage': stage, 'p1_ai': 'no', 'p2_ai': 'yes', 'rounds': '1', 'log_file': 'runtime_lab/logs/smoke_boot_p1_vs_kfm.log', 'notes': 'Basic boot/load check.'},
        {'enabled': 'yes', 'profile_id': 'watch_ai_vs_ai', 'engine_type': cfg.get('engine_type', 'mugen_or_ikemen_go'), 'p1': char, 'p2': opponent, 'stage': stage, 'p1_ai': 'yes', 'p2_ai': 'yes', 'rounds': '1', 'log_file': 'runtime_lab/logs/watch_ai_vs_ai.log', 'notes': 'Hands-off crash and invalid-state watch.'},
        {'enabled': 'yes', 'profile_id': 'training_manual_control', 'engine_type': cfg.get('engine_type', 'mugen_or_ikemen_go'), 'p1': char, 'p2': opponent, 'stage': stage, 'p1_ai': 'no', 'p2_ai': 'no', 'rounds': '1', 'log_file': 'runtime_lab/logs/training_manual_control.log', 'notes': 'Manual checklist session; collect screenshots/video/logs.'},
    ]
    out = rd / 'launch_profiles.csv'
    _csv_write(out, rows, ['enabled', 'profile_id', 'engine_type', 'p1', 'p2', 'stage', 'p1_ai', 'p2_ai', 'rounds', 'log_file', 'notes'])
    result.add_created(root, out)
    result.add_note('Launch profiles are editable CSV rows consumed by Build Runtime Launch Scripts.')
    return result


def _shell_quote(value: object) -> str:
    s = str(value or '')
    return '"' + s.replace('"', '\\"') + '"'


def _bat_quote(value: object) -> str:
    s = str(value or '')
    return '"' + s.replace('"', '""') + '"'


def build_runtime_launch_scripts(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Launch Scripts')
    rd = _runtime_dir(root)
    cfg_res = write_runtime_config_template(root)
    profiles_path = rd / 'launch_profiles.csv'
    if not profiles_path.exists():
        export_runtime_launch_profiles(root)
    cfg = _read_runtime_config(root)
    profiles = _csv_read(profiles_path)
    out_dir = rd / 'launchers'
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = str(cfg.get('engine_executable') or '').strip()
    engine_placeholder = engine or 'EDIT_ME_ENGINE_PATH'
    engine_type = str(cfg.get('engine_type') or 'mugen_or_ikemen_go').lower()
    written = 0
    for row in profiles:
        if str(row.get('enabled', 'yes')).strip().lower() not in {'yes', 'y', '1', 'true'}:
            continue
        profile = re.sub(r'[^A-Za-z0-9_\-]+', '_', row.get('profile_id') or f'profile_{written+1}').strip('_') or f'profile_{written+1}'
        p1 = row.get('p1') or cfg.get('project_character_name') or _char_name(root)
        p2 = row.get('p2') or cfg.get('default_opponent') or 'kfm'
        stage = row.get('stage') or cfg.get('default_stage') or 'stages/kfm.def'
        log_file = row.get('log_file') or f'runtime_lab/logs/{profile}.log'
        # Command strings are intentionally visible/editable rather than hidden behind an executor.
        mugen_args = f'{_bat_quote(p1)} {_bat_quote(p2)} -s {_bat_quote(stage)} -log {_bat_quote(log_file)}'
        sh_args = f'{_shell_quote(p1)} {_shell_quote(p2)} -s {_shell_quote(stage)} -log {_shell_quote(log_file)}'
        if 'ikemen' in engine_type:
            mugen_args = f'-p1 {_bat_quote(p1)} -p2 {_bat_quote(p2)} -s {_bat_quote(stage)} -log {_bat_quote(log_file)}'
            sh_args = f'-p1 {_shell_quote(p1)} -p2 {_shell_quote(p2)} -s {_shell_quote(stage)} -log {_shell_quote(log_file)}'
        bat = out_dir / f'run_{profile}.bat'
        sh = out_dir / f'run_{profile}.sh'
        bat_text = f'''@echo off
REM MugenForge Runtime Lab profile: {profile}
REM Review this script before running. Command-line flags vary by engine/build.
set "ENGINE={engine_placeholder}"
if "%ENGINE%"=="EDIT_ME_ENGINE_PATH" (
  echo Edit runtime_lab\\runtime_config.json or this launcher and set ENGINE first.
  pause
  exit /b 1
)
"%ENGINE%" {mugen_args}
'''
        sh_text = f'''#!/usr/bin/env bash
# MugenForge Runtime Lab profile: {profile}
# Review this script before running. Command-line flags vary by engine/build.
ENGINE={_shell_quote(engine_placeholder)}
if [ "$ENGINE" = "EDIT_ME_ENGINE_PATH" ]; then
  echo "Edit runtime_lab/runtime_config.json or this launcher and set ENGINE first."
  exit 1
fi
"$ENGINE" {sh_args}
'''
        _write(root, bat, bat_text, result=result)
        _write(root, sh, sh_text, result=result)
        try:
            sh.chmod(sh.stat().st_mode | 0o111)
        except Exception:
            pass
        written += 1
    readme = rd / 'RUNTIME_LAUNCHERS_README.md'
    readme_text = f'''# Runtime Launchers

Generated scripts live in `runtime_lab/launchers/`.

## Before use

1. Edit `runtime_lab/runtime_config.json` and set `engine_executable`.
2. Verify the generated command-line flags against your engine build.
3. Run one launcher manually.
4. Put logs in `runtime_lab/logs/` and screenshots/video notes in `runtime_lab/evidence/`.
5. Use **Runtime Lab → Parse Runtime Logs** and **Runtime Lab → Runtime Readiness Report**.

## Engine type

Configured engine type: `{cfg.get('engine_type', 'mugen_or_ikemen_go')}`

Runtime Lab does not run the engine inside MugenForge. It creates transparent scripts, checklists, and evidence folders so failures are reproducible.
'''
    _write(root, readme, readme_text, result=result)
    if not engine:
        result.add_warning('No engine_executable is configured yet. Scripts were written with EDIT_ME_ENGINE_PATH placeholders.')
    result.add_note(f'Wrote launcher scripts for {written} enabled profiles.')
    result.merge(cfg_res, 'config')
    return result


def install_runtime_debug_overlay(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Debug Overlay Installer')
    target = find_character_file(root, 'cns') or find_character_file(root, 'st')
    if not target:
        cns = root / f'{root.name}.cns'
        cns.write_text('', encoding='utf-8')
        target = cns
        result.add_created(root, target)
    marker = '; MugenForge Runtime Lab ID: runtime_debug_overlay_v61'
    text = read_text_safely(target) if target.exists() else ''
    if marker in text:
        result.add_warning(f'{_rel(root, target)} already contains the Runtime Lab debug overlay marker. No duplicate block was inserted.')
        return result
    backup = _backup_text(target)
    block = f'''

{marker}
; Runtime Lab overlay. Remove before final release if you do not want debug text.
; This is an in-engine DisplayToClipboard helper, not an external debugger or simulator.
[State -2, MugenForge Runtime Snapshot]
type = DisplayToClipboard
trigger1 = 1
text = "rt state=%d anim=%d elem=%d time=%d ctrl=%d movetype=%d pos=(%f,%f) vel=(%f,%f) life=%d power=%d"
params = stateno, anim, animelemno(0), time, ctrl, movetype, pos x, pos y, vel x, vel y, life, power
ignorehitpause = 1

[State -2, MugenForge Runtime Snapshot Append]
type = AppendToClipboard
trigger1 = 1
text = " fps-check: animtime=%d hitpause=%d"
params = animtime, hitpause
ignorehitpause = 1
; End MugenForge Runtime Lab ID: runtime_debug_overlay_v61
'''
    write_text_safely(target, text.rstrip() + block + '\n')
    result.add_changed(root, target)
    if backup:
        result.add_note(f'Backup written: {_rel(root, backup)}')
    result.add_note('Installed State -2 DisplayToClipboard/AppendToClipboard helper for manual runtime observation.')
    return result


def write_runtime_test_plan(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Test Plan')
    rd = _runtime_dir(root)
    files = _discover_files(root)
    commands = _commands(root)
    states = _states(root)
    hitdefs = _hitdefs(root)
    scenarios: List[Dict[str, object]] = []
    def add(sid: str, category: str, steps: str, expected: str, state: object = '', anim: object = '', command: object = '', blocker: str = 'yes'):
        scenarios.append({'scenario_id': sid, 'category': category, 'state': state, 'anim': anim, 'command': command, 'steps': steps, 'expected_observation': expected, 'status': 'untested', 'blocker': blocker, 'evidence_path': '', 'notes': ''})
    add('boot_load_character', 'boot', 'Launch smoke_boot profile.', 'Character loads without engine crash, missing-file error, or broken palette.', blocker='yes')
    add('idle_control', 'control', 'Start round, wait, tap directions/buttons.', 'Idle, walk, crouch, jump, and basic buttons do not lock control unexpectedly.', blocker='yes')
    add('hit_reaction_smoke', 'defense', 'Let opponent hit P1 once standing, crouching, and airborne.', 'Get-hit/fall/recovery states play without invalid animation/state errors.', blocker='yes')
    add('sound_smoke', 'audio', 'Trigger at least one normal, special, hit, guard, and landing sound if available.', 'No missing sound warnings and no ear-damaging volume spikes.', blocker='no')
    for idx, cmd in enumerate(commands[:80], start=1):
        safe = re.sub(r'[^A-Za-z0-9_\-]+', '_', str(cmd.get('name') or idx)).strip('_') or f'cmd_{idx}'
        add(f'cmd_{idx:03d}_{safe}', 'command', f'Input `{cmd.get("command", "")}` for command `{cmd.get("name", "")}`.', 'Expected state/move triggers, then returns control or intended follow-up state.', command=cmd.get('name', ''), blocker='yes')
    for idx, hit in enumerate(hitdefs[:80], start=1):
        add(f'hitdef_{idx:03d}_state_{hit.get("state", "")}', 'hitdef', f'Trigger attack state `{hit.get("state", "")}` against standing guard and hit.', 'Hit connects/guards at intended frame, damage/pushback/sound match design notes.', state=hit.get('state', ''), anim=hit.get('anim', ''), blocker='yes')
    for row in states[:40]:
        if str(row.get('state')) in {'0', '-1', '-2', '-3'}:
            continue
        add(f'state_{row.get("state")}_smoke', 'state', f'Force or trigger StateDef `{row.get("state")}` if reachable.', 'State exits safely or loops intentionally without invalid ChangeState/ChangeAnim errors.', state=row.get('state'), anim=row.get('anim'), blocker='no')
    fields = ['scenario_id', 'category', 'state', 'anim', 'command', 'steps', 'expected_observation', 'status', 'blocker', 'evidence_path', 'notes']
    out_csv = rd / 'runtime_test_plan.csv'
    _csv_write(out_csv, scenarios, fields)
    result.add_created(root, out_csv)
    missing = [k for k in ('def', 'air', 'cmd', 'cns', 'sff', 'snd') if not files.get(k)]
    lines = [
        '# Runtime Test Plan', '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}',
        f'Character: `{_char_name(root)}`', '',
        'This plan is meant to be filled during real M.U.G.E.N/IKEMEN playtesting. Static source reports cannot prove runtime correctness.', '',
        f'- Scenarios generated: {len(scenarios)}',
        f'- Commands detected: {len(commands)}',
        f'- HitDefs detected: {len(hitdefs)}',
        f'- StateDefs detected: {len(states)}',
    ]
    if missing:
        lines += ['', '## Missing files detected before runtime testing', ''] + [f'- `{m}` file not found' for m in missing]
    lines += ['', '## Suggested loop', '', '1. Build launch scripts.', '2. Install debug overlay if desired.', '3. Run boot/control/hit/sound scenarios.', '4. Save logs/screenshots/video notes in `runtime_lab/evidence/`.', '5. Parse logs and regenerate readiness report.']
    out_md = rd / 'RUNTIME_TEST_PLAN.md'
    _write(root, out_md, '\n'.join(lines), result=result)
    result.add_note(f'Generated {len(scenarios)} runtime scenarios.')
    return result


def _candidate_log_paths(root: Path) -> List[Path]:
    cfg = _read_runtime_config(root)
    out: List[Path] = []
    for item in cfg.get('log_paths', []) if isinstance(cfg.get('log_paths', []), list) else []:
        p = Path(str(item))
        if not p.is_absolute():
            p = root / p
        if p.is_dir():
            out.extend(sorted([x for x in p.rglob('*') if x.is_file() and x.suffix.lower() in {'.log', '.txt'}], key=lambda x: str(x).lower()))
        elif p.exists() and p.is_file():
            out.append(p)
    # Conservative fallback scans only likely log locations.
    for folder in (root, root / 'runtime_lab' / 'logs', root / 'logs'):
        if folder.exists() and folder.is_dir():
            out.extend(sorted([x for x in folder.glob('*.log') if x.is_file()], key=lambda x: str(x).lower()))
    unique: List[Path] = []
    seen = set()
    for p in out:
        try:
            key = p.resolve()
        except Exception:
            key = p
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def parse_runtime_logs(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Log Parser')
    rd = _runtime_dir(root)
    rows: List[Dict[str, object]] = []
    summary: Dict[str, int] = {'logs_scanned': 0, 'error': 0, 'warning': 0, 'asset': 0, 'state': 0}
    logs = _candidate_log_paths(root)
    for path in logs:
        summary['logs_scanned'] += 1
        try:
            lines = read_text_safely(path).splitlines()
        except Exception as exc:
            rows.append({'file': _rel(root, path), 'line': 0, 'severity': 'error', 'category': 'read', 'text': f'Could not read log: {exc}'})
            summary['error'] += 1
            continue
        for lineno, line in enumerate(lines, start=1):
            text = line.strip()
            if not text:
                continue
            matched = []
            severity = ''
            for label, rx in LOG_PATTERNS:
                if rx.search(text):
                    matched.append(label)
                    if label in summary:
                        summary[label] += 1
                    if label == 'error':
                        severity = 'error'
                    elif not severity:
                        severity = 'warning'
            if matched:
                rows.append({'file': _rel(root, path), 'line': lineno, 'severity': severity or 'info', 'category': ','.join(matched), 'text': text[:500]})
    out_csv = rd / 'runtime_log_findings.csv'
    _csv_write(out_csv, rows, ['file', 'line', 'severity', 'category', 'text'])
    result.add_created(root, out_csv)
    out_json = rd / 'runtime_log_summary.json'
    _write_json(root, out_json, {'generated': datetime.now().isoformat(timespec='seconds'), 'summary': summary, 'logs': [_rel(root, p) for p in logs]}, result=result)
    md = rd / 'RUNTIME_LOG_REPORT.md'
    md_lines = ['# Runtime Log Report', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', '## Summary', '']
    for k, v in summary.items():
        md_lines.append(f'- {k}: {v}')
    if rows:
        md_lines += ['', '## Findings', '']
        for row in rows[:200]:
            md_lines.append(f'- `{row["file"]}:{row["line"]}` **{row["severity"]}** [{row["category"]}] {row["text"]}')
        if len(rows) > 200:
            md_lines.append(f'- ... {len(rows)-200} more findings in CSV')
    else:
        md_lines += ['', 'No error/warning-style lines were found in the configured logs.']
    _write(root, md, '\n'.join(md_lines), result=result)
    if not logs:
        result.add_warning('No runtime logs found yet. Put engine logs in runtime_lab/logs/ or configure log_paths in runtime_config.json.')
    else:
        result.add_note(f'Scanned {len(logs)} log file(s); findings: {len(rows)}.')
    return result


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 256), b''):
            h.update(chunk)
    return h.hexdigest()


def build_runtime_evidence_index(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Evidence Index')
    rd = _runtime_dir(root)
    evidence_dirs = [rd / 'evidence', rd / 'logs', root / 'release' / 'screenshots', root / 'screenshots']
    rows: List[Dict[str, object]] = []
    for folder in evidence_dirs:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            result.add_created(root, folder)
        for path in sorted(folder.rglob('*'), key=lambda p: str(p).lower()):
            if not path.is_file() or path.suffix.lower() not in EVIDENCE_EXTS:
                continue
            try:
                stat = path.stat()
                rows.append({'file': _rel(root, path), 'kind': path.suffix.lower().lstrip('.'), 'size_bytes': stat.st_size, 'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'), 'sha256': _sha256(path)})
            except Exception as exc:
                rows.append({'file': _rel(root, path), 'kind': path.suffix.lower().lstrip('.'), 'size_bytes': '', 'modified': '', 'sha256': f'ERROR: {exc}'})
    fields = ['file', 'kind', 'size_bytes', 'modified', 'sha256']
    out_csv = rd / 'runtime_evidence_index.csv'
    _csv_write(out_csv, rows, fields)
    result.add_created(root, out_csv)
    out_json = rd / 'runtime_evidence_index.json'
    _write_json(root, out_json, {'generated': datetime.now().isoformat(timespec='seconds'), 'count': len(rows), 'evidence': rows}, result=result)
    result.add_note(f'Indexed {len(rows)} evidence/log/screenshot files.')
    return result


def write_runtime_regression_checklist(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Regression Checklist')
    rd = _runtime_dir(root)
    plan = rd / 'runtime_test_plan.csv'
    if not plan.exists():
        write_runtime_test_plan(root)
    scenarios = _csv_read(plan)
    rows: List[Dict[str, object]] = []
    for row in scenarios:
        rows.append({
            'release': datetime.now().strftime('%Y-%m-%d'),
            'scenario_id': row.get('scenario_id', ''),
            'category': row.get('category', ''),
            'blocker': row.get('blocker', 'yes'),
            'last_known_status': row.get('status', 'untested'),
            'current_status': 'untested',
            'tester': '',
            'evidence_path': row.get('evidence_path', ''),
            'bug_id': '',
            'notes': row.get('notes', ''),
        })
    fields = ['release', 'scenario_id', 'category', 'blocker', 'last_known_status', 'current_status', 'tester', 'evidence_path', 'bug_id', 'notes']
    out = rd / 'runtime_regression_checklist.csv'
    _csv_write(out, rows, fields)
    result.add_created(root, out)
    md = rd / 'RUNTIME_REGRESSION_GUIDE.md'
    text = '''# Runtime Regression Guide

Use `runtime_regression_checklist.csv` before each public build.

Recommended gate:

- All blocker scenarios should be `pass` or have an explicit accepted-risk note.
- Any crash, missing required file, invalid StateDef, or invalid animation should block release.
- Add screenshot/video/log evidence for changed gameplay systems.
- Regenerate Runtime Readiness after parsing fresh logs.
'''
    _write(root, md, text, result=result)
    result.add_note(f'Regression checklist rows: {len(rows)}')
    return result


def write_runtime_readiness_report(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Readiness Report')
    rd = _runtime_dir(root)
    cfg = _read_runtime_config(root)
    files = _discover_files(root)
    deductions: List[Tuple[int, str]] = []
    notes: List[str] = []
    score = 100
    def ding(points: int, reason: str):
        nonlocal score
        if points <= 0:
            return
        score -= points
        deductions.append((points, reason))
    missing = [k for k in ('def', 'air', 'cmd', 'cns', 'sff', 'snd') if not files.get(k)]
    ding(min(35, 7 * len(missing)), f'Missing project file references: {", ".join(missing)}' if missing else '')
    engine_path = str(cfg.get('engine_executable') or '').strip()
    if not engine_path:
        ding(12, 'No engine_executable configured in runtime_config.json.')
    elif not Path(engine_path).exists():
        ding(6, f'Configured engine_executable does not exist on this system: {engine_path}')
    overlay_found = False
    for path in _code_files(root):
        try:
            if 'MugenForge Runtime Lab ID: runtime_debug_overlay_v61' in read_text_safely(path):
                overlay_found = True
                break
        except Exception:
            pass
    if not overlay_found:
        ding(6, 'Runtime debug overlay has not been installed.')
    air_path = files.get('air')
    if air_path and air_path.exists():
        try:
            existing = {a.number for a in parse_air(read_text_safely(air_path))}
            missing_common = [n for n in COMMON_ANIMS if n not in existing]
            ding(min(24, len(missing_common)), f'Missing common AIR actions: {len(missing_common)}')
        except Exception as exc:
            ding(15, f'AIR parse failed: {exc}')
    log_csv = rd / 'runtime_log_findings.csv'
    if log_csv.exists():
        rows = _csv_read(log_csv)
        err_count = sum(1 for r in rows if str(r.get('severity', '')).lower() == 'error')
        warn_count = sum(1 for r in rows if str(r.get('severity', '')).lower() == 'warning')
        ding(min(30, err_count * 10), f'Runtime log errors detected: {err_count}')
        ding(min(15, warn_count * 2), f'Runtime log warnings detected: {warn_count}')
        notes.append(f'Runtime log findings loaded from {_rel(root, log_csv)}.')
    else:
        ding(8, 'No parsed runtime log report exists yet.')
    evidence_csv = rd / 'runtime_evidence_index.csv'
    evidence_count = 0
    if evidence_csv.exists():
        evidence_count = len(_csv_read(evidence_csv))
    if evidence_count == 0:
        ding(8, 'No runtime evidence files indexed yet.')
    plan = rd / 'runtime_test_plan.csv'
    if plan.exists():
        scenarios = _csv_read(plan)
        blockers = [r for r in scenarios if str(r.get('blocker', 'yes')).lower() in {'yes', 'y', '1', 'true'}]
        passed = [r for r in blockers if str(r.get('status', '')).lower() == 'pass']
        if blockers and len(passed) < len(blockers):
            ding(min(20, len(blockers) - len(passed)), f'Blocker runtime scenarios not marked pass: {len(blockers)-len(passed)} of {len(blockers)}')
    else:
        ding(5, 'Runtime test plan has not been generated.')
    score = max(0, min(100, score))
    grade = 'release_candidate' if score >= 85 else 'needs_testing' if score >= 65 else 'not_ready'
    payload = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'score': score,
        'grade': grade,
        'deductions': [{'points': p, 'reason': r} for p, r in deductions if r],
        'notes': notes,
        'files': {k: _rel(root, v) if v else None for k, v in files.items() if k != 'root'},
        'evidence_count': evidence_count,
        'engine_executable_configured': bool(engine_path),
    }
    out_json = rd / 'runtime_readiness_report.json'
    _write_json(root, out_json, payload, result=result)
    md = rd / 'RUNTIME_READINESS_REPORT.md'
    lines = ['# Runtime Readiness Report', '', f'Generated: {payload["generated"]}', '', f'**Score:** {score}/100', f'**Grade:** `{grade}`', '', '## Deductions', '']
    if deductions:
        for points, reason in deductions:
            if reason:
                lines.append(f'- -{points}: {reason}')
    else:
        lines.append('- None')
    lines += ['', '## Important note', '', 'This score is a release aid. It is not engine-authoritative; real M.U.G.E.N/IKEMEN testing remains required.']
    _write(root, md, '\n'.join(lines), result=result)
    result.add_note(f'Runtime readiness score: {score}/100 ({grade}).')
    return result


def build_runtime_lab_bundle(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Lab Bundle')
    rd = _runtime_dir(root)
    if not rd.exists():
        write_runtime_config_template(root)
    out_dir = rd / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'runtime_lab_bundle_{_timestamp()}.zip'
    skip_parts = {'bundles', '__pycache__'}
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(rd.rglob('*'), key=lambda p: str(p).lower()):
            if not path.is_file():
                continue
            if any(part in skip_parts for part in path.parts):
                continue
            zf.write(path, path.relative_to(root))
    result.add_created(root, out)
    result.add_note('Bundle contains Runtime Lab configs, launchers, checklists, logs, reports, and evidence index files; it skips nested bundles.')
    return result


def run_runtime_lab_pass(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('One-Click Runtime Lab Pass')
    steps = [
        ('config', write_runtime_config_template),
        ('profiles', export_runtime_launch_profiles),
        ('launchers', build_runtime_launch_scripts),
        ('debug overlay', install_runtime_debug_overlay),
        ('test plan', write_runtime_test_plan),
        ('logs', parse_runtime_logs),
        ('evidence', build_runtime_evidence_index),
        ('regression', write_runtime_regression_checklist),
        ('readiness', write_runtime_readiness_report),
        ('bundle', build_runtime_lab_bundle),
    ]
    for label, fn in steps:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    start = _runtime_dir(root) / 'RUNTIME_LAB_START_HERE.md'
    text = f'''# Runtime Lab Start Here

Runtime Lab turns static MugenForge analysis into a real playtest loop.

## Next steps

1. Edit `runtime_lab/runtime_config.json` and set your engine executable.
2. Review scripts in `runtime_lab/launchers/` before running them.
3. Run the boot/control/hit/sound scenarios in `runtime_lab/runtime_test_plan.csv`.
4. Save logs in `runtime_lab/logs/` and screenshots/video notes in `runtime_lab/evidence/`.
5. Re-run Runtime Log Parser, Evidence Index, and Runtime Readiness Report.

## Honesty

MugenForge still does not simulate M.U.G.E.N/IKEMEN. Runtime Lab creates launchers, checklists, overlays, parsers, and evidence bundles so external engine testing is repeatable and auditable.

Generated: {datetime.now().isoformat(timespec='seconds')}
'''
    _write(root, start, text, result=result)
    return result

# v6.1 UI compatibility names. These wrappers keep the Runtime Lab tab readable
# while the backend uses more specific function names.
def write_runtime_lab_dashboard(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Lab Dashboard')
    result.merge(write_runtime_config_template(root), 'config')
    rd = _runtime_dir(root)
    files = _discover_files(root)
    plan_exists = (rd / 'runtime_test_plan.csv').exists()
    logs_exist = any((rd / 'logs').glob('*')) if (rd / 'logs').exists() else False
    readiness = rd / 'RUNTIME_READINESS_REPORT.md'
    lines = [
        '# Runtime Lab Dashboard', '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
        f'- Project: `{root.name}`',
        f'- DEF: `{_rel(root, files.get("def")) if files.get("def") else "missing"}`',
        f'- AIR: `{_rel(root, files.get("air")) if files.get("air") else "missing"}`',
        f'- CMD: `{_rel(root, files.get("cmd")) if files.get("cmd") else "missing"}`',
        f'- CNS/ST: `{_rel(root, files.get("cns")) if files.get("cns") else "missing"}`',
        f'- Runtime test plan exists: {"yes" if plan_exists else "no"}',
        f'- Logs/evidence exist: {"yes" if logs_exist else "no"}',
        f'- Readiness report exists: {"yes" if readiness.exists() else "no"}', '',
        '## Next actions', '',
        '1. Write Launch Profile and edit `runtime_lab/runtime_config.json` with your local engine path.',
        '2. Write Scenario Matrix / Runtime Test Plan.',
        '3. Run generated launch scripts or use your engine manually.',
        '4. Put logs in `runtime_lab/logs/` and screenshots/video notes in `runtime_lab/evidence/`.',
        '5. Parse Runtime Logs and regenerate Runtime Readiness.', '',
        'Runtime Lab does not emulate M.U.G.E.N/IKEMEN. It makes external engine testing repeatable and auditable.',
    ]
    _write(root, rd / 'RUNTIME_LAB_DASHBOARD.md', '\n'.join(lines), result=result)
    _write(root, rd / 'RUNTIME_LAB_START_HERE.md', '\n'.join(lines), result=result)
    return result


def write_engine_launch_profile(root: Path, engine_path: str | Path | None = None, **_kwargs) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Engine Launch Profile')
    cfg_res = write_runtime_config_template(root)
    cfg_path = _runtime_dir(root) / 'runtime_config.json'
    cfg = _read_runtime_config(root)
    if engine_path:
        cfg['engine_executable'] = str(engine_path)
        low = str(engine_path).lower()
        cfg['engine_type'] = 'ikemen_go' if 'ikemen' in low else 'mugen_or_ikemen_go'
        _write_json(root, cfg_path, cfg, result=result, changed=True)
    result.merge(cfg_res, 'config')
    result.merge(export_runtime_launch_profiles(root), 'profiles')
    result.merge(build_runtime_launch_scripts(root), 'launchers')
    return result


def write_runtime_scenario_matrix(root: Path) -> RuntimeLabResult:
    return write_runtime_test_plan(Path(root))


def write_runtime_telemetry_pack(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Telemetry Pack')
    rd = _runtime_dir(root) / 'telemetry'
    rd.mkdir(parents=True, exist_ok=True)
    snippet = '''; MugenForge Runtime Lab ID: runtime_debug_overlay_v61
; Debug-only Runtime Lab helper. Remove before public release if visible debug text is unwanted.
[State -2, MugenForge Runtime Snapshot]
type = DisplayToClipboard
trigger1 = 1
text = "rt state=%d anim=%d elem=%d time=%d ctrl=%d pos=(%f,%f) vel=(%f,%f) life=%d power=%d"
params = stateno, anim, animelemno(0), time, ctrl, pos x, pos y, vel x, vel y, life, power
ignorehitpause = 1

[State -2, MugenForge Runtime Snapshot Append]
type = AppendToClipboard
trigger1 = 1
text = " animtime=%d hitpause=%d"
params = animtime, hitpause
ignorehitpause = 1
; End MugenForge Runtime Lab ID: runtime_debug_overlay_v61
'''
    _write(root, rd / 'runtime_debug_overlay_snippet.cns', snippet, result=result)
    readme = '''# Runtime Telemetry Pack

This pack contains a debug-only `DisplayToClipboard` / `AppendToClipboard` helper. Use **Install Telemetry Helpers** to append it to your CNS/ST file with a backup, or copy it manually.

It is not an external debugger, memory inspector, or engine simulator. It only exposes useful runtime values during real playtesting.
'''
    _write(root, rd / 'RUNTIME_TELEMETRY_README.md', readme, result=result)
    return result


def install_runtime_telemetry_helpers(root: Path) -> RuntimeLabResult:
    return install_runtime_debug_overlay(Path(root))


def launch_engine_capture(root: Path, engine_path: str | Path | None = None, timeout_seconds: Optional[int] = None, extra_args: Optional[Sequence[str]] = None) -> RuntimeLabResult:
    import subprocess
    root = Path(root)
    result = RuntimeLabResult('Runtime Engine Launch/Capture')
    cfg = _read_runtime_config(root)
    engine = str(engine_path or cfg.get('engine_executable') or '').strip()
    rd = _runtime_dir(root)
    logs = rd / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    if not engine:
        result.add_warning('No engine executable configured. Use Write Launch Profile or edit runtime_lab/runtime_config.json first.')
        return result
    exe = Path(engine)
    if not exe.exists():
        result.add_warning(f'Engine executable does not exist on this machine: {engine}')
        return result
    timeout = int(timeout_seconds or cfg.get('timeout_seconds') or 25)
    args = [str(exe)] + [str(x) for x in (extra_args or cfg.get('arguments') or [])]
    tag = _timestamp()
    meta = {'generated': datetime.now().isoformat(timespec='seconds'), 'command': args, 'cwd': str(exe.parent), 'timeout_seconds': timeout}
    _write_json(root, logs / f'launch_capture_{tag}.json', meta, result=result)
    try:
        proc = subprocess.run(args, cwd=str(exe.parent), capture_output=True, text=True, timeout=timeout, check=False)
        _write(root, logs / f'launch_capture_{tag}_stdout.txt', proc.stdout or '', result=result)
        _write(root, logs / f'launch_capture_{tag}_stderr.txt', proc.stderr or '', result=result)
        _write_json(root, logs / f'launch_capture_{tag}_returncode.json', {'returncode': proc.returncode}, result=result)
        if proc.returncode != 0:
            result.add_warning(f'Engine returned non-zero code {proc.returncode}. Review captured logs.')
    except subprocess.TimeoutExpired as exc:
        _write(root, logs / f'launch_capture_{tag}_timeout_stdout.txt', (exc.stdout or '') if isinstance(exc.stdout, str) else str(exc.stdout or ''), result=result)
        _write(root, logs / f'launch_capture_{tag}_timeout_stderr.txt', (exc.stderr or '') if isinstance(exc.stderr, str) else str(exc.stderr or ''), result=result)
        result.add_warning(f'Engine capture timed out after {timeout} second(s). This can be normal for GUI engines; partial output was saved.')
    except Exception as exc:
        _write(root, logs / f'launch_capture_{tag}_exception.txt', repr(exc), result=result)
        result.add_warning(f'Could not launch/capture engine: {exc}')
    result.merge(parse_runtime_logs(root), 'log parser')
    return result


def write_runtime_evidence_report(root: Path) -> RuntimeLabResult:
    root = Path(root)
    result = RuntimeLabResult('Runtime Evidence / Readiness')
    result.merge(build_runtime_evidence_index(root), 'evidence index')
    result.merge(write_runtime_readiness_report(root), 'readiness')
    return result

# Compatibility alias for v7 Authority/Gap tools.
def write_runtime_config(root: Path) -> RuntimeLabResult:  # type: ignore[name-defined]
    return write_runtime_config_template(root)


# Compatibility aliases for v7 authority/gap modules.
def write_runtime_engine_profile(root: Path, engine_exe: str | Path | None = None, game_root: str | Path | None = None, default_stage: str = 'stages/training.def', **_kwargs) -> RuntimeLabResult:
    result = write_runtime_config_template(root)
    cfg_path = Path(root) / 'runtime_lab' / 'runtime_config.json'
    try:
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    except Exception:
        cfg = {}
    if engine_exe is not None:
        cfg['engine_executable'] = str(engine_exe)
    if game_root is not None:
        cfg['working_directory'] = str(game_root)
    cfg['default_stage'] = default_stage
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    result.changed_files.append(str(cfg_path))
    return result

def runtime_smoke_launch(root: Path, timeout_seconds: float | int = 0, dry_run: bool = True, **_kwargs) -> RuntimeLabResult:
    if dry_run:
        return launch_engine_capture(root, timeout_seconds=int(timeout_seconds or 0), extra_args=['--dry-run'])
    return launch_engine_capture(root, timeout_seconds=int(timeout_seconds or 8))

def ingest_runtime_logs(root: Path, folder: Path | None = None, **_kwargs) -> RuntimeLabResult:
    # Current parser scans the runtime_lab log locations. If a folder is provided, copy text logs into logs/.
    if folder:
        dst = Path(root) / 'runtime_lab' / 'logs'
        dst.mkdir(parents=True, exist_ok=True)
        for p in Path(folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in {'.txt', '.log', '.json', '.csv', '.md'}:
                try:
                    shutil.copy2(p, dst / p.name)
                except Exception:
                    pass
    return parse_runtime_logs(root)
