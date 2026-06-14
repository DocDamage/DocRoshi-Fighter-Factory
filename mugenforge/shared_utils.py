from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    backup_file,
    rel_path,
    sha256_file,
    timestamp,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .binary_results import BinaryCoreResult
from .move_wizard import find_character_file
from .parsers import parse_air, parse_code, parse_def, read_text_safely, write_text_safely

CODE_SUFFIXES = {'.cmd', '.cns', '.st'}
IMAGE_SUFFIXES = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
TEXT_SUFFIXES = {'.def', '.air', '.cmd', '.cns', '.st', '.txt', '.md', '.json', '.ini', '.cfg', '.csv'}
SKIP_PARTS = {'__pycache__', '.git', '.hg', '.svn', '.venv', 'venv', '.mypy_cache', '.pytest_cache', 'backups', 'exports'}
GENERATED_PARTS = {
    'forge_polish',
    'polish_lab',
    'forge_beyond',
    'visual_forge',
    'backups',
    'exports',
    'quality_lab',
    'creator_os',
    'gap_closer',
    'runtime_lab',
    'binary_core',
    'binary_deep',
    'binary_maturity',
    'forge_timeline',
    'authority_core',
    'maintenance_core',
    'state_graph_canvas',
    'visual',
    'timeline_preview',
    'sheet_validation',
    'template_validation',
    'corpus_validation',
    'unknown_binary_triage',
    'verified_binary_install',
    'gameplay_tuning',
    'engine_runs',
    'engine_validation',
    'engine_contracts',
    'runtime_reconciliation',
}


@dataclass
class BaseResult(BinaryCoreResult):
    pass


def uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def sanitize_name(value: object) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', str(value or '')).strip('_') or 'item'


def parse_safe_int(value: object, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def parse_first_int(value: object, default: int = 0) -> int:
    m = re.search(r'-?\d+', str(value or ''))
    return int(m.group(0)) if m else default


def parse_numbers(value: object) -> List[float]:
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', str(value or ''))]


def parse_damage_pair(value: object) -> Tuple[int, Optional[int]]:
    nums = [int(n) for n in re.findall(r'-?\d+', str(value or ''))]
    if not nums:
        return 0, None
    return nums[0], nums[1] if len(nums) > 1 else None


def is_truthy(value: object) -> bool:
    return str(value or '').strip().lower() in {'1', 'yes', 'y', 'true', 'on', 'apply', 'enabled'}


def get_code_files(root: Path, skip_generated: bool = True) -> List[Path]:
    out: List[Path] = []
    for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS or part.startswith('.') for part in p.parts):
            continue
        if skip_generated and any(part in GENERATED_PARTS for part in p.relative_to(root).parts):
            continue
        if p.suffix.lower() in CODE_SUFFIXES:
            out.append(p)
    return out


def get_all_files(root: Path, include_generated: bool = True) -> List[Path]:
    out: List[Path] = []
    for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()):
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS or part.startswith('.') for part in p.parts):
            continue
        if not include_generated and any(part in GENERATED_PARTS for part in p.relative_to(root).parts):
            continue
        out.append(p)
    return out


def discover_project_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    exact_def = root / f'{root.name}.def'
    out['def'] = exact_def if exact_def.exists() else None
    if not out['def']:
        hits = sorted(root.glob('*.def'), key=lambda p: p.name.lower())
        out['def'] = hits[0] if hits else None

    refs: Dict[str, str] = {}
    dpath = out.get('def')
    if dpath and dpath.exists():
        try:
            sec = parse_def(read_text_safely(dpath)).get('files')
            if sec:
                refs = {k.lower(): str(v).strip().strip('"') for k, v in sec.values.items()}
        except Exception:
            refs = {}

    def by_ref(key: str, ext: str) -> Optional[Path]:
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                return p
        try:
            p2 = find_character_file(root, ext)
            if p2 and p2.exists():
                return p2
        except Exception:
            pass
        exact = root / f'{root.name}.{ext}'
        if exact.exists():
            return exact
        hits = sorted(root.glob(f'*.{ext}'), key=lambda p: p.name.lower())
        return hits[0] if hits else None

    out['cmd'] = by_ref('cmd', 'cmd')
    out['cns'] = by_ref('cns', 'cns') or by_ref('st', 'st')
    out['air'] = by_ref('anim', 'air')
    out['sff'] = by_ref('sprite', 'sff')
    out['snd'] = by_ref('sound', 'snd')
    return out


def get_character_name(root: Path) -> str:
    files = discover_project_files(root)
    dpath = files.get('def')
    if dpath and dpath.exists():
        try:
            info = parse_def(read_text_safely(dpath)).get('info')
            if info:
                name = info.values.get('displayname') or info.values.get('name')
                if name:
                    return str(name).strip().strip('"')
        except Exception:
            pass
    return Path(root).name or 'character'


def scan_hitdefs(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in get_code_files(root):
        try:
            text = read_text_safely(path)
            scan = parse_code(text)
        except Exception:
            continue
        for state in scan.states:
            anim = parse_safe_int(state.values.get('anim'), state.number)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype != 'hitdef':
                    continue
                dmg, gdmg = parse_damage_pair(ctrl.values.get('damage', '0'))

                # Approximate anim element (AnimElem = X) from triggers
                anim_elem = 1
                for val in ctrl.values.values():
                    m = re.search(r'AnimElem\s*=\s*(-?\d+)', str(val), re.I)
                    if m:
                        anim_elem = int(m.group(1))
                        break

                rows.append({
                    'file': rel_path(root, path),
                    'line': ctrl.line,
                    'state': state.number,
                    'anim': anim,
                    'damage': dmg,
                    'guard_damage': gdmg,
                    'attr': ctrl.values.get('attr', ''),
                    'hitflag': ctrl.values.get('hitflag', ''),
                    'guardflag': ctrl.values.get('guardflag', ''),
                    'pausetime': ctrl.values.get('pausetime', ''),
                    'sparkno': ctrl.values.get('sparkno', ''),
                    'hitsound': ctrl.values.get('hitsound', ''),
                    'guardsound': ctrl.values.get('guardsound', ''),
                    'ground_velocity': ctrl.values.get('ground.velocity', ctrl.values.get('ground.velocity.x', '')),
                    'air_velocity': ctrl.values.get('air.velocity', ctrl.values.get('air.velocity.x', '')),
                    'frame': anim_elem,
                    'label': ctrl.header or '',
                    'trigger1': ctrl.values.get('trigger1', ''),
                })
    return rows


def scan_commands(root: Path) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for path in sorted(Path(root).rglob('*.cmd'), key=lambda x: str(x).lower()):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            text = read_text_safely(path)
            scan = parse_code(text)
            for c in scan.commands:
                out.append({
                    'file': rel_path(root, path),
                    'line': c.line,
                    'name': c.name,
                    'command': c.command,
                    'norm': re.sub(r'\s+', '', c.command.lower()),
                    'time': c.time,
                    'buffer_time': c.buffer_time,
                })
        except Exception:
            continue
    return out


def scan_air_stats(root: Path) -> Dict[int, Dict[str, int]]:
    files = discover_project_files(root)
    air = files.get('air')
    out: Dict[int, Dict[str, int]] = {}
    if not air or not air.exists():
        return out
    try:
        actions = parse_air(read_text_safely(air))
        for action in actions:
            active = [i for i, frame in enumerate(action.frames, 1) if any(b.kind.lower() == 'clsn1' for b in frame.clsn)]
            body = [i for i, frame in enumerate(action.frames, 1) if any(b.kind.lower() == 'clsn2' for b in frame.clsn)]
            out[action.number] = {
                'frames': len(action.frames),
                'ticks': sum(max(0, frame.ticks) for frame in action.frames),
                'first_active': active[0] if active else 0,
                'last_active': active[-1] if active else 0,
                'active_frames': len(active),
                'body_frames': len(body),
            }
    except Exception:
        pass
    return out


def scan_state_anim_map(root: Path) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for path in get_code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
            for st in scan.states:
                if 'anim' in st.values:
                    out[st.number] = parse_first_int(st.values.get('anim'), st.number)
        except Exception:
            continue
    return out


def handle_ui_errors(context: str, return_on_error: object = None):
    def decorator(func):
        import functools
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                try:
                    from tkinter import messagebox
                    messagebox.showerror(f'{context} failed', str(exc))
                except Exception:
                    pass
                if hasattr(self, 'project_root') and self.project_root:
                    try:
                        from .visual_forge import log_error
                        log_error(self.project_root, context, exc)
                    except Exception:
                        pass
                return return_on_error
        return wrapper
    return decorator
