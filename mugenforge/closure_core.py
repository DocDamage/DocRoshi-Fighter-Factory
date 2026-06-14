from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Any

from .artifact_io import (
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _now,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .parsers import parse_air, parse_code, parse_def, read_text_safely, write_text_safely, scan_project
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd
from .binary_results import BinaryCoreResult, _uniq

try:  # v5.5+ standard SFF2 helpers. Keep the module importable if older packages reuse it.
    from .sff2_codec import read_sff2, export_sff2_sprites, write_sff2_report
except Exception:  # pragma: no cover - compatibility path
    read_sff2 = None  # type: ignore
    export_sff2_sprites = None  # type: ignore
    write_sff2_report = None  # type: ignore

CLOSURE_CORE_VERSION = "7.0.0"
CODE_EXTS = {'.cmd', '.cns', '.st'}
IMAGE_EXTS = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
AUDIO_EXTS = {'.wav', '.snd'}
BINARY_EXTS = {'.sff', '.snd'}


@dataclass
class ClosureResult(BinaryCoreResult):
    title: str = 'Closure Core Result'


@dataclass
class MicroState:
    number: int
    file: str
    line: int
    anim: int
    ctrl: int
    type: str = ''
    movetype: str = ''
    physics: str = ''
    velset: Tuple[float, float] = (0.0, 0.0)
    controllers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MicroScenario:
    scenario_id: str
    start_state: int
    command: str = ''
    max_ticks: int = 120
    notes: str = ''


# ---------------------------------------------------------------------------
# Shared helpers




def _closure_dir(root: Path) -> Path:
    out = Path(root) / 'closure_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(root: Path, path: Path, text: str, result: Optional[ClosureResult] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, track_existing=True)


def _write_json(root: Path, path: Path, data: object, result: Optional[ClosureResult] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, data, result, root, changed, track_existing=True)


def _csv_write(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> Path:
    return write_csv_artifact(path, rows, fields)


def _csv_read(path: Path) -> List[Dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open('r', encoding='utf-8-sig', newline='') as f:
        return [dict(row) for row in csv.DictReader(f)]


def _first_int(value: object, default: int = 0) -> int:
    m = re.search(r'-?\d+', str(value or ''))
    return int(m.group(0)) if m else default


def _first_float_pair(value: object, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
    nums = re.findall(r'-?\d+(?:\.\d+)?', str(value or ''))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), 0.0
    return default


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    for kind in ('def', 'cmd', 'cns', 'air', 'sff', 'snd'):
        try:
            out[kind] = find_character_file(root, kind)
        except Exception:
            out[kind] = None
    # Pick first recursively for packed legacy folders where files may be nested.
    for kind, pattern in [('sff', '*.sff'), ('snd', '*.snd'), ('air', '*.air')]:
        if not out.get(kind):
            hits = sorted(root.rglob(pattern), key=lambda p: str(p).lower())
            out[kind] = hits[0] if hits else None
    return out


def _code_files(root: Path) -> List[Path]:
    skip_parts = {'__pycache__', '.mugenforge', 'closure_core', 'runtime_lab', 'binary_core', 'binary_deep', 'binary_maturity'}
    return [
        p for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower())
        if p.is_file() and p.suffix.lower() in CODE_EXTS and not any(part in skip_parts for part in p.parts)
    ]


def _all_binary_files(root: Path) -> List[Path]:
    skip_parts = {'__pycache__', 'closure_core'}
    return [p for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in BINARY_EXTS and not any(part in skip_parts for part in p.parts)]


def _read_runtime_config(root: Path) -> Dict[str, object]:
    cfg = Path(root) / 'runtime_lab' / 'runtime_config.json'
    if cfg.exists():
        try:
            return json.loads(read_text_safely(cfg))
        except Exception:
            pass
    return {
        'engine_executable': '',
        'engine_working_directory': '',
        'engine_type': 'mugen_or_ikemen_go',
        'project_character_name': Path(root).name,
        'default_opponent': 'kfm',
        'default_stage': 'stages/kfm.def',
        'log_paths': ['runtime_lab/logs', 'mugen.log', 'Ikemen.log'],
    }


# ---------------------------------------------------------------------------
# Dashboard


def write_closure_dashboard(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Closure Core Dashboard')
    cd = _closure_dir(root)
    files = _discover_files(root)
    audit = scan_project(root)
    limitations = [
        ('Runtime behavior', 'Source-level micro-runtime plus external engine probe/evidence gate.'),
        ('Launcher review', 'Engine auto-probe scripts, profile report, command templates, and captured exit codes.'),
        ('Readiness authority', 'Readiness gate now separates static, simulated, and real external-engine evidence.'),
        ('SFF2 corpus breadth', 'Corpus validation harness scans project and testing/sff2_corpus files with parser/export results.'),
        ('Unknown binary layouts', 'Binary forensics maps signatures, offsets, entropy, and embedded recoverable payloads.'),
        ('Unsafe overwrites', 'Transactional publish sheets use hashes, backups, rollback manifests, and explicit enabled rows.'),
        ('Generated gameplay tuning', 'Gameplay tuning workbook connects commands, states, AIR timing, HitDefs, and test scenarios.'),
        ('Reports vs evidence', 'Evidence gate indexes logs/screenshots/videos/checklists and requires runtime artifacts for release confidence.'),
    ]
    lines = [
        '# MugenForge Closure Core Start Here',
        '',
        f'Version: `{CLOSURE_CORE_VERSION}`',
        f'Project: `{root.name}`',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}',
        '',
        'Closure Core is the gap-closing layer for the previous honest limitations list. It does not blindly claim universal behavior; it adds executable workflows, source-level simulation, corpus probes, forensic recovery, and explicit transactional publishing so each limitation has a concrete tool path.',
        '',
        '## Current project files',
    ]
    for key in ('def', 'cmd', 'cns', 'air', 'sff', 'snd'):
        p = files.get(key)
        lines.append(f'- {key.upper()}: `{_rel(root, p) if p else "missing"}`')
    lines += ['', '## Limitation closure map']
    lines.extend(f'- **{name}:** {desc}' for name, desc in limitations)
    lines += [
        '',
        '## Recommended order',
        '1. Run **Build Micro Runtime Model** and **Run Micro Runtime Scenarios** to catch obvious source-flow problems.',
        '2. Run **Engine Auto-Probe** after editing `runtime_lab/runtime_config.json` with your engine path.',
        '3. Run **SFF2 Corpus Validation** and **Binary Forensics** on imported projects.',
        '4. Use **Transactional Publish Sheet** for any candidate SFF/SND replacement.',
        '5. Use **Gameplay Tuning Workbook** and **Evidence Gate** before release packaging.',
        '',
        '## Static audit snapshot',
        f'- Missing required extensions: {", ".join(audit.missing_required) if audit.missing_required else "none detected"}',
        f'- Missing DEF references: {len(audit.missing_references)}',
        f'- Code issues: {len(audit.code_issues)}',
        f'- Asset issues: {len(audit.asset_issues)}',
    ]
    out = _write_text(root, cd / 'CLOSURE_CORE_START_HERE.md', '\n'.join(lines), result)
    _write_json(root, cd / 'closure_core_map.json', {'version': CLOSURE_CORE_VERSION, 'limitation_closure_map': [{'limitation': a, 'implemented_path': b} for a, b in limitations]}, result)
    result.add_note('Closure dashboard written. Run the focused tools next for runtime, binary, publish, and evidence workflows.')
    return result


# ---------------------------------------------------------------------------
# Source-level micro runtime


def _build_state_index(root: Path) -> Dict[int, MicroState]:
    states: Dict[int, MicroState] = {}
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        rel = _rel(root, path)
        for st in scan.states:
            anim = _first_int(st.values.get('anim', st.number), st.number)
            ctrl = _first_int(st.values.get('ctrl', 0), 0)
            velset = _first_float_pair(st.values.get('velset', '0,0'))
            mstate = MicroState(
                number=st.number,
                file=rel,
                line=st.line,
                anim=anim,
                ctrl=ctrl,
                type=str(st.values.get('type', '')),
                movetype=str(st.values.get('movetype', '')),
                physics=str(st.values.get('physics', '')),
                velset=velset,
            )
            for ctrlr in st.controllers:
                vals = dict(ctrlr.values)
                mstate.controllers.append({
                    'line': ctrlr.line,
                    'header': ctrlr.header,
                    'type': (ctrlr.stype or vals.get('type', '')).lower(),
                    'values': vals,
                })
            states[st.number] = mstate
    return states


def _build_air_index(root: Path) -> Dict[int, Dict[str, object]]:
    air = find_character_file(root, 'air')
    out: Dict[int, Dict[str, object]] = {}
    if not air or not air.exists():
        return out
    try:
        actions = parse_air(read_text_safely(air))
    except Exception:
        return out
    for action in actions:
        frames = []
        total = 0
        for idx, frame in enumerate(action.frames, start=1):
            ticks = max(1, int(frame.ticks))
            total += ticks
            frames.append({
                'elem': idx,
                'group': frame.group,
                'image': frame.image,
                'x': frame.x,
                'y': frame.y,
                'ticks': ticks,
                'clsn1_count': sum(1 for b in frame.clsn if b.kind.lower() == 'clsn1'),
                'clsn2_count': sum(1 for b in frame.clsn if b.kind.lower() == 'clsn2'),
            })
        out[action.number] = {'action': action.number, 'label': action.label, 'frames': frames, 'total_ticks': total}
    return out


def _anim_elem_at(action: Optional[Dict[str, object]], state_time: int) -> Tuple[int, int]:
    if not action:
        return 1, 0
    frames = action.get('frames') or []
    if not isinstance(frames, list) or not frames:
        return 1, 0
    total = int(action.get('total_ticks') or 0)
    if total <= 0:
        return 1, 0
    pos = min(max(0, int(state_time)), max(0, total - 1))
    acc = 0
    for fr in frames:
        ticks = max(1, int(fr.get('ticks', 1)))
        acc += ticks
        if pos < acc:
            return int(fr.get('elem', 1)), total - state_time
    return int(frames[-1].get('elem', len(frames))), total - state_time


def _compare(value: float, op: str, target: float) -> bool:
    if op == '=':
        return value == target
    if op == '!=':
        return value != target
    if op == '>=':
        return value >= target
    if op == '<=':
        return value <= target
    if op == '>':
        return value > target
    if op == '<':
        return value < target
    return False


def _eval_atom(expr: str, ctx: Dict[str, object], unknowns: List[str]) -> bool:
    e = str(expr or '').strip()
    if not e:
        return True
    low = e.lower().strip()
    if low in {'1', 'true'}:
        return True
    if low in {'0', 'false'}:
        return False
    # command = "x"
    m = re.search(r'command\s*=\s*["\']?([^"\';]+)["\']?', low, re.I)
    if m:
        return str(ctx.get('command', '')).lower() == m.group(1).strip().lower()
    m = re.search(r'time\s*(=|!=|>=|<=|>|<)\s*(-?\d+)', low)
    if m:
        return _compare(float(ctx.get('state_time', 0)), m.group(1), float(m.group(2)))
    m = re.search(r'animelem\s*(=|!=|>=|<=|>|<)\s*(-?\d+)', low)
    if m:
        return _compare(float(ctx.get('animelem', 1)), m.group(1), float(m.group(2)))
    m = re.search(r'animtime\s*(=|!=|>=|<=|>|<)\s*(-?\d+)', low)
    if m:
        return _compare(float(ctx.get('animtime', 0)), m.group(1), float(m.group(2)))
    m = re.search(r'anim\s*(=|!=|>=|<=|>|<)\s*(-?\d+)', low)
    if m:
        return _compare(float(ctx.get('anim', 0)), m.group(1), float(m.group(2)))
    if low == 'ctrl':
        return bool(ctx.get('ctrl'))
    if low.startswith('ctrl'):
        m = re.search(r'ctrl\s*(=|!=)\s*(-?\d+)', low)
        if m:
            return _compare(float(ctx.get('ctrl', 0)), m.group(1), float(m.group(2)))
    if 'roundstate' in low:
        # Treat normal fight roundstate as active in source-level scenarios.
        m = re.search(r'roundstate\s*(=|!=|>=|<=|>|<)\s*(-?\d+)', low)
        if m:
            return _compare(2.0, m.group(1), float(m.group(2)))
        return True
    # Common conjunctions in simple generated code. Evaluate each side if possible.
    if '&&' in low or ' and ' in low:
        parts = re.split(r'&&|\band\b', e, flags=re.I)
        return all(_eval_atom(p, ctx, unknowns) for p in parts)
    if '||' in low or ' or ' in low:
        parts = re.split(r'\|\||\bor\b', e, flags=re.I)
        return any(_eval_atom(p, ctx, unknowns) for p in parts)
    if low.startswith('numhelper') or low.startswith('numproj'):
        return False
    if low not in unknowns:
        unknowns.append(low)
    return False


def _controller_triggers_true(values: Dict[str, str], ctx: Dict[str, object], unknowns: List[str]) -> bool:
    triggerall = [v for k, v in values.items() if k.lower().startswith('triggerall')]
    triggers = [v for k, v in values.items() if re.fullmatch(r'trigger\d+', k.lower())]
    if triggerall and not all(_eval_atom(v, ctx, unknowns) for v in triggerall):
        return False
    if not triggers:
        return True
    return any(_eval_atom(v, ctx, unknowns) for v in triggers)


def _scenario_rows_from_project(root: Path, states: Dict[int, MicroState]) -> List[MicroScenario]:
    rows: List[MicroScenario] = []
    rows.append(MicroScenario('idle_boot_state_0', 0 if 0 in states else (min(states) if states else 0), '', 90, 'Default idle/boot state.'))
    seen = {rows[0].start_state}
    # Build command-derived scenarios from -1 ChangeStates.
    for st in states.values():
        if st.number != -1:
            continue
        for ctrl in st.controllers:
            vals = ctrl.get('values', {})
            if str(ctrl.get('type', '')).lower() not in {'changestate', 'selfstate'}:
                continue
            cmd = ''
            joined = ' '.join(str(v) for k, v in vals.items() if k.startswith('trigger'))
            cm = re.search(r'command\s*=\s*["\']([^"\']+)["\']', joined, re.I)
            if cm:
                cmd = cm.group(1)
            target = _first_int(vals.get('value', ''), 0)
            if target not in states:
                continue
            sid = f'command_{re.sub(r"[^A-Za-z0-9_]+", "_", cmd or str(target)).strip("_")}_{target}'
            rows.append(MicroScenario(sid, target, cmd, 150, f'Derived from State -1 ChangeState line {ctrl.get("line", "")}.'))
            seen.add(target)
    # Add first 40 playable non-negative states to catch generated states even if no command route exists.
    for num in sorted(n for n in states if n >= 0):
        if num in seen:
            continue
        rows.append(MicroScenario(f'state_{num}', num, '', 150, 'Direct state smoke simulation.'))
        seen.add(num)
        if len(rows) >= 40:
            break
    return rows


def _ensure_micro_scenario_sheet(root: Path, states: Dict[int, MicroState]) -> Path:
    out = _closure_dir(root) / 'micro_runtime' / 'micro_runtime_scenarios.csv'
    if out.exists():
        return out
    scenarios = _scenario_rows_from_project(root, states)
    _csv_write(out, [s.__dict__ for s in scenarios], ['scenario_id', 'start_state', 'command', 'max_ticks', 'notes'])
    return out


def build_micro_runtime_model(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Source-Level Micro Runtime Model')
    outdir = _closure_dir(root) / 'micro_runtime'
    states = _build_state_index(root)
    actions = _build_air_index(root)
    state_rows = []
    ctrl_rows = []
    for st in sorted(states.values(), key=lambda s: s.number):
        state_rows.append({
            'state': st.number, 'file': st.file, 'line': st.line, 'anim': st.anim, 'ctrl': st.ctrl,
            'type': st.type, 'movetype': st.movetype, 'physics': st.physics, 'velset_x': st.velset[0], 'velset_y': st.velset[1],
            'controllers': len(st.controllers), 'has_air_action': 'yes' if st.anim in actions else 'no',
        })
        for ctrl in st.controllers:
            vals = ctrl.get('values', {})
            ctrl_rows.append({
                'state': st.number, 'line': ctrl.get('line', ''), 'type': ctrl.get('type', ''), 'header': ctrl.get('header', ''),
                'value': vals.get('value', ''), 'trigger1': vals.get('trigger1', ''), 'triggerall': vals.get('triggerall', ''),
                'anim': vals.get('anim', ''), 'sound_value': vals.get('value', '') if str(ctrl.get('type', '')).lower() == 'playsnd' else '',
            })
    action_rows = []
    for action_no, action in sorted(actions.items()):
        action_rows.append({'action': action_no, 'label': action.get('label', ''), 'frames': len(action.get('frames') or []), 'total_ticks': action.get('total_ticks', 0)})
    model = {
        'tool': 'MugenForge Closure Core',
        'version': CLOSURE_CORE_VERSION,
        'project': str(root),
        'states': [s.__dict__ | {'controllers': s.controllers} for s in sorted(states.values(), key=lambda x: x.number)],
        'air_actions': actions,
        'capabilities': {
            'trigger_support': ['1', 'time comparisons', 'AnimElem comparisons', 'AnimTime comparisons', 'ctrl', 'command = "name"', 'roundstate'],
            'controller_support': ['ChangeState', 'SelfState', 'ChangeAnim', 'PlaySnd', 'HitDef', 'VelSet', 'VelAdd', 'PosAdd', 'CtrlSet', 'Helper/Projectile/Explod markers'],
            'scope': 'source-level deterministic approximation for generated/simple M.U.G.E.N code',
        },
    }
    _write_json(root, outdir / 'source_runtime_model.json', model, result)
    _csv_write(outdir / 'source_runtime_states.csv', state_rows, ['state','file','line','anim','ctrl','type','movetype','physics','velset_x','velset_y','controllers','has_air_action'])
    result.add_created(root, outdir / 'source_runtime_states.csv')
    _csv_write(outdir / 'source_runtime_controllers.csv', ctrl_rows, ['state','line','type','header','value','trigger1','triggerall','anim','sound_value'])
    result.add_created(root, outdir / 'source_runtime_controllers.csv')
    _csv_write(outdir / 'source_runtime_actions.csv', action_rows, ['action','label','frames','total_ticks'])
    result.add_created(root, outdir / 'source_runtime_actions.csv')
    _ensure_micro_scenario_sheet(root, states)
    result.add_created(root, outdir / 'micro_runtime_scenarios.csv')
    result.add_note(f'Model indexed {len(states)} states, {sum(len(s.controllers) for s in states.values())} controllers, and {len(actions)} AIR actions.')
    return result


def _load_micro_scenarios(root: Path, states: Dict[int, MicroState]) -> List[MicroScenario]:
    path = _ensure_micro_scenario_sheet(root, states)
    scenarios: List[MicroScenario] = []
    for row in _csv_read(path):
        if str(row.get('enabled', 'yes')).strip().lower() in {'no', 'false', '0'}:
            continue
        scenarios.append(MicroScenario(
            scenario_id=str(row.get('scenario_id') or f'scenario_{len(scenarios)+1}'),
            start_state=_first_int(row.get('start_state', 0), 0),
            command=str(row.get('command') or ''),
            max_ticks=max(1, min(3600, _first_int(row.get('max_ticks', 120), 120))),
            notes=str(row.get('notes') or ''),
        ))
    return scenarios or _scenario_rows_from_project(root, states)


def _simulate_one(scenario: MicroScenario, states: Dict[int, MicroState], actions: Dict[int, Dict[str, object]]) -> Tuple[List[Dict[str, object]], List[str]]:
    warnings: List[str] = []
    trace: List[Dict[str, object]] = []
    current_state = int(scenario.start_state)
    if current_state not in states:
        warnings.append(f'{scenario.scenario_id}: start state {current_state} does not exist.')
        return trace, warnings
    state_time = 0
    anim = states[current_state].anim
    ctrl = states[current_state].ctrl
    x = y = 0.0
    vx, vy = states[current_state].velset
    unknown_triggers: List[str] = []
    hitdef_seen = False
    transition_count = 0
    for global_tick in range(max(1, scenario.max_ticks)):
        st = states.get(current_state)
        if st is None:
            warnings.append(f'{scenario.scenario_id}: entered missing state {current_state} at tick {global_tick}.')
            break
        action = actions.get(anim)
        elem, animtime = _anim_elem_at(action, state_time)
        events: List[str] = []
        ctx = {
            'scenario': scenario.scenario_id,
            'command': scenario.command,
            'state': current_state,
            'state_time': state_time,
            'time': state_time,
            'anim': anim,
            'animelem': elem,
            'animtime': animtime,
            'ctrl': ctrl,
        }
        transitioned = False
        for ctrlr in st.controllers:
            ctype = str(ctrlr.get('type', '')).lower()
            vals = ctrlr.get('values', {})
            if not isinstance(vals, dict):
                continue
            if not _controller_triggers_true(vals, ctx, unknown_triggers):
                continue
            label = f'{ctype}@{ctrlr.get("line", "")}'
            if ctype in {'changestate', 'selfstate'}:
                target = _first_int(vals.get('value', ''), current_state)
                events.append(f'{label}: {current_state}->{target}')
                current_state = target
                transition_count += 1
                transitioned = True
                state_time = -1  # incremented to 0 below
                if current_state in states:
                    anim = states[current_state].anim
                    ctrl = states[current_state].ctrl
                    vx, vy = states[current_state].velset
                else:
                    warnings.append(f'{scenario.scenario_id}: ChangeState target {target} does not exist.')
                break
            if ctype == 'changeanim':
                anim = _first_int(vals.get('value', anim), anim)
                events.append(f'{label}: anim={anim}')
            elif ctype == 'playsnd':
                events.append(f'{label}: PlaySnd {vals.get("value", "") or vals.get("value0", "")}')
            elif ctype == 'hitdef':
                hitdef_seen = True
                events.append(f'{label}: HitDef damage={vals.get("damage", "")} attr={vals.get("attr", "")}')
            elif ctype == 'velset':
                vx, vy = _first_float_pair(vals.get('x', vals.get('value', vals.get('velset', '0,0'))), (vx, vy))
                if 'y' in vals and 'x' in vals:
                    vx = float(_first_float_pair(vals.get('x'), (vx, 0))[0])
                    vy = float(_first_float_pair(vals.get('y'), (vy, 0))[0])
                events.append(f'{label}: VelSet {vx:g},{vy:g}')
            elif ctype == 'veladd':
                ax, ay = _first_float_pair(vals.get('value', '0,0'))
                if 'x' in vals:
                    ax = _first_float_pair(vals.get('x'), (0, 0))[0]
                if 'y' in vals:
                    ay = _first_float_pair(vals.get('y'), (0, 0))[0]
                vx += ax
                vy += ay
                events.append(f'{label}: VelAdd {ax:g},{ay:g}')
            elif ctype == 'posadd':
                px, py = _first_float_pair(vals.get('value', '0,0'))
                if 'x' in vals:
                    px = _first_float_pair(vals.get('x'), (0, 0))[0]
                if 'y' in vals:
                    py = _first_float_pair(vals.get('y'), (0, 0))[0]
                x += px
                y += py
                events.append(f'{label}: PosAdd {px:g},{py:g}')
            elif ctype == 'ctrlset':
                ctrl = _first_int(vals.get('value', vals.get('ctrl', ctrl)), ctrl)
                events.append(f'{label}: CtrlSet {ctrl}')
            elif ctype in {'helper', 'projectile', 'explod', 'notbyhit', 'nothitby', 'hitoverride', 'assertspecial', 'palfx', 'afterimage', 'playsnd'}:
                events.append(f'{label}: marker')
        x += vx
        y += vy
        trace.append({
            'scenario_id': scenario.scenario_id,
            'tick': global_tick,
            'state': current_state,
            'state_time': max(0, state_time),
            'anim': anim,
            'animelem': elem,
            'animtime': animtime,
            'ctrl': ctrl,
            'x': round(x, 3),
            'y': round(y, 3),
            'vel_x': round(vx, 3),
            'vel_y': round(vy, 3),
            'events': '; '.join(events),
        })
        if transition_count > 40:
            warnings.append(f'{scenario.scenario_id}: stopped after 40 state transitions to avoid an infinite loop.')
            break
        state_time += 1
    if unknown_triggers:
        warnings.append(f'{scenario.scenario_id}: unsupported triggers skipped: ' + '; '.join(unknown_triggers[:20]))
    if scenario.start_state in states and states[scenario.start_state].movetype.upper() == 'A' and not hitdef_seen:
        warnings.append(f'{scenario.scenario_id}: attack-like start state had no triggered HitDef during this simplified simulation.')
    return trace, warnings


def run_micro_runtime_scenarios(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Micro Runtime Scenarios')
    outdir = _closure_dir(root) / 'micro_runtime'
    states = _build_state_index(root)
    actions = _build_air_index(root)
    if not states:
        result.add_warning('No StateDefs were found; micro-runtime simulation cannot run.')
        return result
    scenarios = _load_micro_scenarios(root, states)
    all_trace: List[Dict[str, object]] = []
    warnings: List[str] = []
    summary_rows: List[Dict[str, object]] = []
    for sc in scenarios:
        trace, warns = _simulate_one(sc, states, actions)
        all_trace.extend(trace)
        warnings.extend(warns)
        visited = sorted({int(r['state']) for r in trace}) if trace else []
        events = sum(1 for r in trace if str(r.get('events', '')).strip())
        summary_rows.append({'scenario_id': sc.scenario_id, 'start_state': sc.start_state, 'command': sc.command, 'ticks_recorded': len(trace), 'states_visited': ' '.join(str(v) for v in visited), 'event_rows': events, 'warnings': ' | '.join(w for w in warns if w.startswith(sc.scenario_id))})
    fields = ['scenario_id','tick','state','state_time','anim','animelem','animtime','ctrl','x','y','vel_x','vel_y','events']
    _csv_write(outdir / 'micro_runtime_trace.csv', all_trace, fields)
    result.add_created(root, outdir / 'micro_runtime_trace.csv')
    _csv_write(outdir / 'micro_runtime_summary.csv', summary_rows, ['scenario_id','start_state','command','ticks_recorded','states_visited','event_rows','warnings'])
    result.add_created(root, outdir / 'micro_runtime_summary.csv')
    report = [
        '# Source-Level Micro Runtime Report',
        '',
        f'Scenarios run: {len(scenarios)}',
        f'Trace rows: {len(all_trace)}',
        '',
        'This is a deterministic source-level runtime approximation. It executes common generated/simple StateDef flows, controller triggers, animation timing, PlaySnd, HitDef, and velocity/position operations. It is useful before external playtesting because it catches obvious dead states, missing ChangeState targets, non-triggered HitDefs, and animation timing issues.',
        '',
        '## Scenario summary',
    ]
    for row in summary_rows:
        report.append(f'- `{row["scenario_id"]}`: {row["ticks_recorded"]} ticks, states `{row["states_visited"] or "none"}`, event rows {row["event_rows"]}')
    if warnings:
        report += ['', '## Warnings'] + [f'- {w}' for w in _uniq(warnings)]
        for w in _uniq(warnings):
            result.add_warning(w)
    report += ['', '## Supported trigger/controller subset', '- triggers: command, ctrl, time, AnimElem, AnimTime, anim, roundstate, simple AND/OR', '- controllers: ChangeState/SelfState, ChangeAnim, PlaySnd, HitDef, VelSet/VelAdd/PosAdd/CtrlSet, plus marker events for common visual/helper controllers']
    _write_text(root, outdir / 'MICRO_RUNTIME_REPORT.md', '\n'.join(report), result)
    # Small HTML viewer for traces.
    rows_html = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(row.get(f, "")))}</td>' for f in fields) + '</tr>' for row in all_trace[:2000])
    table = '<table border="1" cellspacing="0" cellpadding="3"><thead><tr>' + ''.join(f'<th>{html.escape(f)}</th>' for f in fields) + '</tr></thead><tbody>' + rows_html + '</tbody></table>'
    _write_text(root, outdir / 'micro_runtime_trace.html', '<!doctype html><meta charset="utf-8"><title>Micro Runtime Trace</title><h1>Micro Runtime Trace</h1>' + table, result)
    result.add_note(f'Ran {len(scenarios)} source-level runtime scenarios.')
    return result


# ---------------------------------------------------------------------------
# Engine auto-probe and evidence gate


def write_engine_autoprobe(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Engine Auto-Probe')
    outdir = _closure_dir(root) / 'engine_probe'
    cfg = _read_runtime_config(root)
    exe = str(cfg.get('engine_executable') or '').strip().strip('"')
    cwd = str(cfg.get('engine_working_directory') or '').strip().strip('"')
    report: Dict[str, object] = {
        'tool': 'MugenForge Closure Core Engine Auto-Probe',
        'version': CLOSURE_CORE_VERSION,
        'engine_executable': exe,
        'engine_working_directory': cwd,
        'exists': False,
        'probe_attempts': [],
        'recommended_profile': 'manual',
        'usable': False,
    }
    attempts: List[Dict[str, object]] = []
    if exe and Path(exe).exists():
        report['exists'] = True
        work = cwd or str(Path(exe).parent)
        # Probes are intentionally short and non-destructive.
        for args in (['--help'], ['-h'], ['-version'], []):
            try:
                cp = subprocess.run([exe] + args, cwd=work if Path(work).exists() else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                blob = (cp.stdout or '') + '\n' + (cp.stderr or '')
                attempts.append({'args': args, 'returncode': cp.returncode, 'stdout_head': (cp.stdout or '')[:2000], 'stderr_head': (cp.stderr or '')[:2000]})
                low = blob.lower()
                if 'ikemen' in low:
                    report['recommended_profile'] = 'ikemen_go'
                    report['usable'] = True
                if 'm.u.g.e.n' in low or 'mugen' in low:
                    report['recommended_profile'] = 'mugen'
                    report['usable'] = True
                # Any clean quick exit is useful enough to mark the executable runnable.
                if cp.returncode in {0, 1}:
                    report['usable'] = True
                break
            except subprocess.TimeoutExpired as exc:
                attempts.append({'args': args, 'timeout': True, 'message': str(exc)})
            except Exception as exc:
                attempts.append({'args': args, 'error': str(exc)})
    elif exe:
        result.add_warning(f'Configured engine executable does not exist: {exe}')
    else:
        result.add_warning('runtime_lab/runtime_config.json does not contain engine_executable yet.')
    report['probe_attempts'] = attempts
    _write_json(root, outdir / 'engine_probe_report.json', report, result)
    lines = [
        '# Engine Auto-Probe Report',
        '',
        f'Configured executable: `{exe or "not set"}`',
        f'Executable exists: {"yes" if report["exists"] else "no"}',
        f'Recommended profile: `{report["recommended_profile"]}`',
        f'Runnable/usable according to probe: {"yes" if report["usable"] else "no"}',
        '',
        '## What this implements',
        'The previous launcher-review gap is now handled by a repeatable probe report. MugenForge checks that the configured executable exists, attempts short non-destructive version/help probes, fingerprints likely M.U.G.E.N/IKEMEN output, and records exit codes/stdout/stderr heads for review.',
        '',
        '## Probe attempts',
    ]
    if attempts:
        for a in attempts:
            lines.append(f'- args={a.get("args")}: returncode={a.get("returncode", "")}, timeout={a.get("timeout", "")}, error={a.get("error", "")}')
    else:
        lines.append('- No probe executed.')
    # Write a reusable Python probe runner so users can run it outside the GUI.
    probe_py = outdir / 'run_engine_probe.py'
    probe_py.parent.mkdir(parents=True, exist_ok=True)
    probe_py.write_text('''from pathlib import Path\nimport json, subprocess, sys\nroot = Path(__file__).resolve().parents[2]\ncfg = root / "runtime_lab" / "runtime_config.json"\nprint("Reading", cfg)\ndata = json.loads(cfg.read_text(encoding="utf-8"))\nexe = data.get("engine_executable", "")\nwork = data.get("engine_working_directory") or str(Path(exe).parent)\nfor args in (["--help"], ["-h"], ["-version"], []):\n    try:\n        print("PROBE", [exe] + args)\n        cp = subprocess.run([exe] + args, cwd=work, timeout=8, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)\n        print("returncode", cp.returncode)\n        print(cp.stdout[:2000])\n        print(cp.stderr[:2000])\n        break\n    except Exception as exc:\n        print("probe failed", args, exc)\n''', encoding='utf-8')
    result.add_created(root, probe_py)
    _write_text(root, outdir / 'ENGINE_PROBE_REPORT.md', '\n'.join(lines), result)
    result.add_note('Engine probe artifacts written. Configure runtime_lab/runtime_config.json and rerun to collect real engine fingerprints.')
    return result


def _collect_evidence_files(root: Path) -> List[Path]:
    cfg = _read_runtime_config(root)
    rels: List[str] = []
    for item in cfg.get('log_paths', []) if isinstance(cfg.get('log_paths'), list) else []:
        rels.append(str(item))
    rels.extend(['runtime_lab/evidence', 'runtime_lab/logs', 'release/screenshots', 'screenshots', 'closure_core/micro_runtime'])
    files: List[Path] = []
    for rel in rels:
        p = Path(rel)
        if not p.is_absolute():
            p = Path(root) / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(q for q in p.rglob('*') if q.is_file())
    return sorted(set(files), key=lambda p: str(p).lower())


def _scan_log_text(text: str) -> Tuple[int, int, List[str]]:
    errors = 0
    warnings = 0
    hits: List[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(token in low for token in ('error', 'exception', 'failed', 'missing', 'cannot open', 'assert', 'traceback')):
            errors += 1
            if len(hits) < 40:
                hits.append(f'line {idx}: {line[:240]}')
        elif any(token in low for token in ('warning', 'warn:', 'deprecated', 'not found')):
            warnings += 1
            if len(hits) < 40:
                hits.append(f'line {idx}: {line[:240]}')
    return errors, warnings, hits


def write_runtime_evidence_certification(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Runtime Evidence Gate')
    outdir = _closure_dir(root) / 'evidence_gate'
    files = _collect_evidence_files(root)
    rows: List[Dict[str, object]] = []
    error_count = 0
    warning_count = 0
    log_hits: List[str] = []
    for path in files:
        rel = _rel(root, path)
        kind = 'log' if path.suffix.lower() in {'.log', '.txt'} or 'log' in path.name.lower() else 'evidence'
        sha = _sha256(path) if path.exists() and path.is_file() else ''
        rows.append({'file': rel, 'kind': kind, 'size': path.stat().st_size, 'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'), 'sha256': sha})
        if kind == 'log':
            try:
                e, w, hits = _scan_log_text(read_text_safely(path))
                error_count += e
                warning_count += w
                log_hits.extend(f'{rel}: {h}' for h in hits)
            except Exception:
                pass
    _csv_write(outdir / 'runtime_evidence_gate_index.csv', rows, ['file','kind','size','modified','sha256'])
    result.add_created(root, outdir / 'runtime_evidence_gate_index.csv')
    micro_trace = Path(root) / 'closure_core' / 'micro_runtime' / 'micro_runtime_trace.csv'
    engine_probe = Path(root) / 'closure_core' / 'engine_probe' / 'engine_probe_report.json'
    probe_usable = False
    if engine_probe.exists():
        try:
            probe_usable = bool(json.loads(engine_probe.read_text(encoding='utf-8')).get('usable'))
        except Exception:
            pass
    score = 100
    reasons: List[str] = []
    def ding(points: int, reason: str):
        nonlocal score
        if points <= 0:
            return
        score -= points
        reasons.append(f'-{points}: {reason}')
    if not micro_trace.exists():
        ding(15, 'source-level micro-runtime trace has not been generated')
    if not probe_usable:
        ding(20, 'external engine executable has not been successfully probed')
    if not rows:
        ding(20, 'no runtime evidence/log files indexed')
    ding(min(30, error_count * 8), f'{error_count} error-like log findings')
    ding(min(15, warning_count * 2), f'{warning_count} warning-like log findings')
    score = max(0, min(100, score))
    gate = {
        'tool': 'MugenForge Closure Core Evidence Gate',
        'version': CLOSURE_CORE_VERSION,
        'score': score,
        'engine_probe_usable': probe_usable,
        'micro_runtime_trace_present': micro_trace.exists(),
        'evidence_files': len(rows),
        'log_errors': error_count,
        'log_warnings': warning_count,
        'score_reasons': reasons,
        'log_hits': log_hits[:100],
        'interpretation': 'evidence-backed readiness score; strongest when external engine logs and screenshots/videos are present',
    }
    _write_json(root, outdir / 'runtime_evidence_gate.json', gate, result)
    lines = [
        '# Runtime Evidence Gate',
        '',
        f'Score: **{score}/100**',
        f'Engine probe usable: {"yes" if probe_usable else "no"}',
        f'Micro-runtime trace present: {"yes" if micro_trace.exists() else "no"}',
        f'Evidence files indexed: {len(rows)}',
        f'Error-like log findings: {error_count}',
        f'Warning-like log findings: {warning_count}',
        '',
        'This gate separates static/source simulation from real engine evidence. A high score requires evidence files and clean logs, not just static reports.',
    ]
    if reasons:
        lines += ['', '## Score deductions'] + [f'- {r}' for r in reasons]
    if log_hits:
        lines += ['', '## Log findings'] + [f'- {html.escape(h)}' for h in log_hits[:80]]
    _write_text(root, outdir / 'RUNTIME_EVIDENCE_GATE.md', '\n'.join(lines), result)
    result.add_note(f'Evidence gate score: {score}/100.')
    return result


# ---------------------------------------------------------------------------
# SFF2 corpus and binary forensics


def _candidate_sff_files(root: Path) -> List[Path]:
    files: List[Path] = []
    main = find_character_file(root, 'sff')
    if main and main.exists():
        files.append(main)
    for base in [Path(root) / 'testing' / 'sff2_corpus', Path(root) / 'corpus' / 'sff2', Path(root) / 'assets']:
        if base.exists():
            files.extend(p for p in base.rglob('*.sff') if p.is_file())
    return sorted(set(files), key=lambda p: str(p).lower())


def write_sff2_corpus_validation(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('SFF2 Corpus Validation')
    outdir = _closure_dir(root) / 'sff2_corpus'
    rows: List[Dict[str, object]] = []
    warnings: List[str] = []
    for path in _candidate_sff_files(root):
        row: Dict[str, object] = {'file': _rel(root, path), 'size': path.stat().st_size, 'sha256': _sha256(path), 'read_sff_variant': '', 'sff2_parser_mode': '', 'sprite_count': 0, 'palette_count': 0, 'decode_exports': 0, 'status': 'unknown', 'warnings': ''}
        try:
            info = read_sff(path)
            row['read_sff_variant'] = info.variant
            row['sprite_count'] = len(info.sprites)
            warnings.extend(f'{_rel(root, path)}: {w}' for w in info.warnings)
        except Exception as exc:
            row['status'] = 'read_sff_error'
            row['warnings'] = str(exc)
            rows.append(row)
            continue
        if read_sff2 is not None:
            try:
                s2 = read_sff2(path)  # type: ignore[misc]
                row['sff2_parser_mode'] = s2.parser_mode
                row['sprite_count'] = len(s2.sprites)
                row['palette_count'] = len(s2.palettes)
                row['status'] = 'sff2_parsed' if s2.sprites else 'sff2_unrecognized_or_empty'
                exp_dir = outdir / 'exports' / re.sub(r'[^A-Za-z0-9_.-]+', '_', path.stem)
                if export_sff2_sprites is not None and s2.sprites:
                    outputs, warns = export_sff2_sprites(path, exp_dir, include_provisional=True)  # type: ignore[misc]
                    row['decode_exports'] = len(outputs)
                    warnings.extend(f'{_rel(root, path)}: {w}' for w in warns)
                if s2.warnings:
                    warnings.extend(f'{_rel(root, path)}: {w}' for w in s2.warnings)
            except Exception as exc:
                row['status'] = 'sff2_parser_error'
                row['warnings'] = str(exc)
        else:
            row['status'] = 'sff2_codec_module_missing'
        rows.append(row)
    if not rows:
        result.add_warning('No SFF files were found in the project or testing/sff2_corpus/.')
    fields = ['file','size','sha256','read_sff_variant','sff2_parser_mode','sprite_count','palette_count','decode_exports','status','warnings']
    _csv_write(outdir / 'sff2_corpus_validation.csv', rows, fields)
    result.add_created(root, outdir / 'sff2_corpus_validation.csv')
    _write_json(root, outdir / 'sff2_corpus_validation.json', {'rows': rows, 'warnings': _uniq(warnings)}, result)
    lines = [
        '# SFF2 Corpus Validation',
        '',
        f'Files scanned: {len(rows)}',
        '',
        'This harness turns the broad-corpus limitation into a repeatable test suite. Add real-world `.sff` files under `testing/sff2_corpus/` and rerun this pass; each file receives parser, table, decode/export, warning, and hash results.',
        '',
        '## Results',
    ]
    if rows:
        for r in rows:
            lines.append(f'- `{r["file"]}`: status={r["status"]}, variant={r["read_sff_variant"]}, parser={r["sff2_parser_mode"]}, sprites={r["sprite_count"]}, exports={r["decode_exports"]}')
    else:
        lines.append('- No SFF corpus files found yet.')
    if warnings:
        lines += ['', '## Warnings'] + [f'- {w}' for w in _uniq(warnings)[:200]]
        for w in _uniq(warnings)[:40]:
            result.add_warning(w)
    _write_text(root, outdir / 'SFF2_CORPUS_VALIDATION.md', '\n'.join(lines), result)
    result.add_note('SFF2 corpus validation written. Add more real-world files to testing/sff2_corpus to grow coverage.')
    return result


def _find_asset_markers(data: bytes) -> List[Dict[str, object]]:
    markers = [
        ('png', b'\x89PNG\r\n\x1a\n'),
        ('pcx', b'\x0A\x05'),
        ('riff_wave', b'RIFF'),
        ('zlib_78_9c', b'\x78\x9c'),
        ('zlib_78_da', b'\x78\xda'),
        ('elecbyte_spr', b'ElecbyteSpr\x00'),
        ('elecbyte_snd', b'ElecbyteSnd\x00'),
    ]
    hits: List[Dict[str, object]] = []
    for name, needle in markers:
        start = 0
        count = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            hits.append({'kind': name, 'offset': idx, 'hex_offset': f'0x{idx:X}', 'sample': data[idx:idx+32].hex(' ')})
            count += 1
            if count > 1000:
                break
            start = idx + 1
    return sorted(hits, key=lambda r: int(r['offset']))


def _entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = [0] * 256
    for b in chunk:
        counts[b] += 1
    total = len(chunk)
    ent = 0.0
    import math
    for c in counts:
        if c:
            p = c / total
            ent -= p * math.log2(p)
    return ent


def _write_entropy_map(path: Path, out_csv: Path, block_size: int = 4096) -> Path:
    data = path.read_bytes()
    rows = []
    for off in range(0, len(data), block_size):
        chunk = data[off:off+block_size]
        rows.append({'offset': off, 'hex_offset': f'0x{off:X}', 'size': len(chunk), 'entropy': round(_entropy(chunk), 4), 'ascii_hint': ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk[:40])})
    return _csv_write(out_csv, rows, ['offset','hex_offset','size','entropy','ascii_hint'])


def _extract_embedded_assets(path: Path, out_dir: Path) -> List[Path]:
    data = path.read_bytes()
    out: List[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    # PNG extraction by IEND marker.
    pos = 0
    idx = 0
    while True:
        start = data.find(b'\x89PNG\r\n\x1a\n', pos)
        if start < 0:
            break
        iend = data.find(b'IEND', start)
        if iend > start:
            end = min(len(data), iend + 8)
            dst = out_dir / f'{path.stem}_embedded_{idx:04d}_0x{start:X}.png'
            dst.write_bytes(data[start:end])
            out.append(dst)
            idx += 1
            pos = end
        else:
            pos = start + 8
    # WAV extraction by RIFF chunk length.
    pos = 0
    widx = 0
    while True:
        start = data.find(b'RIFF', pos)
        if start < 0:
            break
        if start + 12 <= len(data) and data[start+8:start+12] == b'WAVE':
            size = struct.unpack_from('<I', data, start + 4)[0] + 8
            if 12 <= size <= len(data) - start:
                dst = out_dir / f'{path.stem}_embedded_{widx:04d}_0x{start:X}.wav'
                dst.write_bytes(data[start:start+size])
                out.append(dst)
                widx += 1
                pos = start + size
                continue
        pos = start + 4
    return out


def write_binary_forensics_report(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Binary Forensics')
    outdir = _closure_dir(root) / 'binary_forensics'
    rows: List[Dict[str, object]] = []
    extracted: List[str] = []
    for path in _all_binary_files(root):
        data = path.read_bytes()
        hits = _find_asset_markers(data)
        sig_csv = outdir / f'{path.stem}_signature_map.csv'
        _csv_write(sig_csv, hits, ['kind','offset','hex_offset','sample'])
        result.add_created(root, sig_csv)
        ent_csv = outdir / f'{path.stem}_entropy_map.csv'
        _write_entropy_map(path, ent_csv)
        result.add_created(root, ent_csv)
        assets = _extract_embedded_assets(path, outdir / 'embedded_assets' / path.stem)
        extracted.extend(_rel(root, p) for p in assets)
        rows.append({'file': _rel(root, path), 'size': len(data), 'sha256': _sha256(path), 'signature_hits': len(hits), 'embedded_assets_extracted': len(assets), 'signature_csv': _rel(root, sig_csv), 'entropy_csv': _rel(root, ent_csv)})
    _csv_write(outdir / 'binary_forensics_index.csv', rows, ['file','size','sha256','signature_hits','embedded_assets_extracted','signature_csv','entropy_csv'])
    result.add_created(root, outdir / 'binary_forensics_index.csv')
    lines = [
        '# Binary Forensics Report',
        '',
        f'Files scanned: {len(rows)}',
        '',
        'This implements the unknown/corrupt/tool-specific binary review path. Instead of stopping at “manual review,” Closure Core maps signatures, entropy blocks, recoverable embedded PNG/WAV assets, and hashes so unsupported files can be triaged or salvaged systematically.',
        '',
        '## Files',
    ]
    if rows:
        for r in rows:
            lines.append(f'- `{r["file"]}`: signatures={r["signature_hits"]}, embedded_assets={r["embedded_assets_extracted"]}, sha256={str(r["sha256"])[:16]}…')
    else:
        lines.append('- No SFF/SND binary files found.')
    if extracted:
        lines += ['', '## Extracted embedded assets'] + [f'- `{p}`' for p in extracted[:200]]
    _write_text(root, outdir / 'BINARY_FORENSICS_REPORT.md', '\n'.join(lines), result)
    result.add_note(f'Binary forensics scanned {len(rows)} files and extracted {len(extracted)} embedded assets.')
    return result


# ---------------------------------------------------------------------------
# Transactional publishing


def _candidate_binary_outputs(root: Path) -> List[Path]:
    candidates: List[Path] = []
    bases = ['binary_core', 'binary_deep', 'binary_maturity', 'closure_core', 'creator_suite', 'quality_lab', 'rescue_lab']
    for base in bases:
        folder = Path(root) / base
        if not folder.exists():
            continue
        candidates.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in BINARY_EXTS)
    return sorted(set(candidates), key=lambda p: str(p).lower())


def export_transactional_publish_sheet(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Transactional Publish Sheet')
    outdir = _closure_dir(root) / 'transactions'
    files = _discover_files(root)
    rows: List[Dict[str, object]] = []
    for cand in _candidate_binary_outputs(root):
        target = ''
        if cand.suffix.lower() == '.sff' and files.get('sff'):
            target = _rel(root, files['sff'])
        elif cand.suffix.lower() == '.snd' and files.get('snd'):
            target = _rel(root, files['snd'])
        rows.append({
            'enabled': 'no',
            'candidate_rel': _rel(root, cand),
            'target_rel': target,
            'candidate_sha256': _sha256(cand),
            'candidate_size': cand.stat().st_size,
            'require_target_sha256': _sha256(root / target) if target and (root / target).exists() else '',
            'publish_note': 'Set enabled=yes only after verifying the candidate in Binary/Runtime Lab.',
        })
    if not rows:
        rows.append({'enabled': 'no', 'candidate_rel': '', 'target_rel': '', 'candidate_sha256': '', 'candidate_size': '', 'require_target_sha256': '', 'publish_note': 'No binary candidates found yet.'})
        result.add_warning('No candidate SFF/SND outputs were found under generated tool folders.')
    sheet = outdir / 'transactional_publish_sheet.csv'
    _csv_write(sheet, rows, ['enabled','candidate_rel','target_rel','candidate_sha256','candidate_size','require_target_sha256','publish_note'])
    result.add_created(root, sheet)
    guide = [
        '# Transactional Publish Guide',
        '',
        'This implements the old “candidate/backup-first” limitation as an explicit publish system. Generated binary candidates are not silently promoted. To publish one:',
        '',
        '1. Verify the candidate with Binary Core/Deep/Maturity and Runtime Lab.',
        '2. Open `transactional_publish_sheet.csv`.',
        '3. Set exactly the desired rows to `enabled=yes`.',
        '4. Keep or update `target_rel`.',
        '5. Run **Apply Transactional Publish Sheet**.',
        '',
        'Apply writes a backup, checks hashes, overwrites the target atomically, and records a rollback manifest.',
    ]
    _write_text(root, outdir / 'TRANSACTIONAL_PUBLISH_GUIDE.md', '\n'.join(guide), result)
    result.add_note('Transactional publish sheet exported.')
    return result


def apply_transactional_publish_sheet(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Apply Transactional Publish Sheet')
    outdir = _closure_dir(root) / 'transactions'
    sheet = outdir / 'transactional_publish_sheet.csv'
    if not sheet.exists():
        result.merge(export_transactional_publish_sheet(root))
    rows = _csv_read(sheet)
    log_rows: List[Dict[str, object]] = []
    changed = 0
    for row in rows:
        if str(row.get('enabled', '')).strip().lower() not in {'yes', 'y', '1', 'true'}:
            continue
        cand = Path(root) / str(row.get('candidate_rel', '')).strip()
        target = Path(root) / str(row.get('target_rel', '')).strip()
        if not cand.exists() or not cand.is_file():
            result.add_warning(f'Skipped missing candidate: {cand}')
            continue
        if not target.suffix.lower() in BINARY_EXTS:
            result.add_warning(f'Skipped target with unsupported extension: {target}')
            continue
        expected_cand_hash = str(row.get('candidate_sha256', '')).strip()
        cand_hash = _sha256(cand)
        if expected_cand_hash and cand_hash != expected_cand_hash:
            result.add_warning(f'Skipped {cand}: candidate hash changed since sheet export.')
            continue
        expected_target_hash = str(row.get('require_target_sha256', '')).strip()
        if expected_target_hash and target.exists() and _sha256(target) != expected_target_hash:
            result.add_warning(f'Skipped {target}: target hash changed since sheet export.')
            continue
        backup = None
        if target.exists():
            backup_dir = outdir / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f'{target.name}.bak_{_now()}'
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f'.tmp_publish_{_now()}')
        shutil.copy2(cand, tmp)
        os.replace(tmp, target)
        changed += 1
        result.add_changed(root, target)
        entry = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'candidate': _rel(root, cand),
            'target': _rel(root, target),
            'candidate_sha256': cand_hash,
            'new_target_sha256': _sha256(target),
            'backup': _rel(root, backup) if backup else '',
        }
        log_rows.append(entry)
        with (outdir / 'publish_log.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    if not changed:
        result.add_warning('No enabled rows were published. Set enabled=yes in transactional_publish_sheet.csv first.')
    else:
        rollback = outdir / f'rollback_manifest_{_now()}.json'
        _write_json(root, rollback, {'published': log_rows}, result)
        result.add_note(f'Published {changed} candidate binary file(s) with backups and rollback manifest.')
    return result


# ---------------------------------------------------------------------------
# Gameplay tuning workbook


def _hitdef_rows(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        rel = _rel(root, path)
        for st in scan.states:
            for ctrl in st.controllers:
                if (ctrl.stype or ctrl.values.get('type', '')).lower() != 'hitdef':
                    continue
                dmg = _first_int(ctrl.values.get('damage', '0'), 0)
                rows.append({
                    'file': rel,
                    'line': ctrl.line,
                    'state': st.number,
                    'anim': _first_int(st.values.get('anim', st.number), st.number),
                    'damage': dmg,
                    'pausetime': ctrl.values.get('pausetime', ''),
                    'sparkno': ctrl.values.get('sparkno', ''),
                    'hitsound': ctrl.values.get('hitsound', ''),
                    'guardsound': ctrl.values.get('guardsound', ''),
                    'ground.velocity': ctrl.values.get('ground.velocity', ''),
                    'air.velocity': ctrl.values.get('air.velocity', ''),
                    'attr': ctrl.values.get('attr', ''),
                    'hitflag': ctrl.values.get('hitflag', ''),
                    'guardflag': ctrl.values.get('guardflag', ''),
                    'trigger1': ctrl.values.get('trigger1', ''),
                })
    return rows


def _air_timing_by_action(root: Path) -> Dict[int, Dict[str, object]]:
    out: Dict[int, Dict[str, object]] = {}
    air = find_character_file(root, 'air')
    if not air or not air.exists():
        return out
    try:
        actions = parse_air(read_text_safely(air))
    except Exception:
        return out
    for action in actions:
        first_active = 0
        last_active = 0
        tick_pos = 0
        total = 0
        for idx, fr in enumerate(action.frames, start=1):
            ticks = max(1, int(fr.ticks))
            total += ticks
            if any(b.kind.lower() == 'clsn1' for b in fr.clsn):
                if not first_active:
                    first_active = tick_pos + 1
                last_active = tick_pos + ticks
            tick_pos += ticks
        startup = max(0, first_active - 1) if first_active else ''
        active = max(0, last_active - first_active + 1) if first_active else 0
        recovery = max(0, total - last_active) if first_active else ''
        out[action.number] = {'frames': len(action.frames), 'ticks': total, 'first_active_tick': first_active, 'last_active_tick': last_active, 'startup_ticks': startup, 'active_ticks': active, 'recovery_ticks': recovery}
    return out


def write_gameplay_tuning_workbook(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Gameplay Tuning Workbook')
    outdir = _closure_dir(root) / 'gameplay_tuning'
    timings = _air_timing_by_action(root)
    rows: List[Dict[str, object]] = []
    for hit in _hitdef_rows(root):
        anim = int(hit.get('anim') or 0)
        timing = timings.get(anim, {})
        damage = int(hit.get('damage') or 0)
        startup = timing.get('startup_ticks', '')
        recovery = timing.get('recovery_ticks', '')
        risk = ''
        try:
            st = int(startup) if startup != '' else 0
            rec = int(recovery) if recovery != '' else 0
            if damage >= 80 and rec < 10:
                risk = 'High damage with low estimated recovery; verify in engine.'
            elif st <= 2 and damage >= 50:
                risk = 'Fast high-damage attack; verify startup and punishability.'
            elif not timing:
                risk = 'No AIR timing found for this state anim.'
            else:
                risk = 'Normal static-risk estimate.'
        except Exception:
            risk = 'Static estimate unavailable.'
        row = dict(hit)
        row.update({
            'air_frames': timing.get('frames', ''),
            'air_ticks': timing.get('ticks', ''),
            'startup_ticks_est': timing.get('startup_ticks', ''),
            'active_ticks_est': timing.get('active_ticks', ''),
            'recovery_ticks_est': timing.get('recovery_ticks', ''),
            'runtime_test_required': 'yes',
            'suggested_test': f'Test State {hit.get("state")} / Anim {anim}: hit, block, whiff, counter-hit, sound, spark, recovery.',
            'risk_note': risk,
            'designer_notes': '',
        })
        rows.append(row)
    if not rows:
        result.add_warning('No HitDef controllers found for gameplay tuning workbook.')
    fields = ['file','line','state','anim','damage','pausetime','sparkno','hitsound','guardsound','ground.velocity','air.velocity','attr','hitflag','guardflag','trigger1','air_frames','air_ticks','startup_ticks_est','active_ticks_est','recovery_ticks_est','runtime_test_required','suggested_test','risk_note','designer_notes']
    _csv_write(outdir / 'gameplay_tuning_workbook.csv', rows, fields)
    result.add_created(root, outdir / 'gameplay_tuning_workbook.csv')
    lines = [
        '# Gameplay Tuning Workbook',
        '',
        f'HitDefs indexed: {len(rows)}',
        '',
        'This implements a no-code bridge between generated gameplay scaffolds and real tuning. The workbook connects HitDef values to AIR timing estimates, produces per-move test prompts, and marks every move for runtime verification.',
        '',
        'The estimates help prioritize testing; the external engine is still the authority for final feel.',
    ]
    if rows:
        lines += ['', '## High-priority rows']
        for r in rows[:40]:
            lines.append(f'- State {r["state"]} / Anim {r["anim"]}: damage {r["damage"]}, startup {r["startup_ticks_est"]}, active {r["active_ticks_est"]}, recovery {r["recovery_ticks_est"]}; {r["risk_note"]}')
    _write_text(root, outdir / 'GAMEPLAY_TUNING_WORKBOOK.md', '\n'.join(lines), result)
    result.add_note(f'Gameplay tuning workbook wrote {len(rows)} HitDef rows.')
    return result


# ---------------------------------------------------------------------------
# Bundle and one-click


def build_closure_core_bundle(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('Closure Core Bundle')
    cd = _closure_dir(root)
    if not cd.exists():
        result.add_warning('closure_core folder does not exist yet. Run other Closure Core tools first.')
        return result
    out = cd / f'closure_core_reports_{_now()}.zip'
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(cd.rglob('*'), key=lambda p: str(p).lower()):
            if path.is_file() and path != out:
                zf.write(path, path.relative_to(cd))
    result.add_created(root, out)
    result.add_note('Closure Core reports bundle created.')
    return result


def run_closure_core_pass(root: Path) -> ClosureResult:
    root = Path(root)
    result = ClosureResult('One-Click Closure Core Pass')
    for label, func in [
        ('dashboard', write_closure_dashboard),
        ('micro model', build_micro_runtime_model),
        ('micro scenarios', run_micro_runtime_scenarios),
        ('engine probe', write_engine_autoprobe),
        ('sff2 corpus', write_sff2_corpus_validation),
        ('binary forensics', write_binary_forensics_report),
        ('transaction sheet', export_transactional_publish_sheet),
        ('gameplay tuning', write_gameplay_tuning_workbook),
        ('evidence gate', write_runtime_evidence_certification),
        ('bundle', build_closure_core_bundle),
    ]:
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    start = _closure_dir(root) / 'CLOSURE_CORE_START_HERE.md'
    if start.exists():
        result.add_note('Open closure_core/CLOSURE_CORE_START_HERE.md first.')
    return result
