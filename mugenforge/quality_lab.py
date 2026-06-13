from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from io import BytesIO
import csv
import html
import json
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, write_text_safely
from .move_wizard import find_character_file
from .sff_codec import read_sff, export_all_sprites, sprite_lookup
from .snd_codec import read_snd, export_all_sounds

TEXT_EXTS = {'.def', '.air', '.cmd', '.cns', '.st', '.txt', '.md', '.json', '.ini', '.cfg'}
IMAGE_EXTS = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}


@dataclass
class QualityLabResult:
    title: str = 'Quality Lab'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, path: Path | str) -> None:
        self.created_files.append(str(path))

    def add_changed(self, path: Path | str) -> None:
        self.changed_files.append(str(path))

    def add_warning(self, msg: str) -> None:
        self.warnings.append(str(msg))

    def merge(self, other: 'QualityLabResult', label: Optional[str] = None) -> None:
        if not other:
            return
        prefix = f'{label}: ' if label else ''
        self.created_files += [prefix + x for x in other.created_files]
        self.changed_files += [prefix + x for x in other.changed_files]
        self.warnings += [prefix + x for x in other.warnings]
        self.notes += [prefix + x for x in other.notes]

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        if self.changed_files:
            lines += ['Changed files:'] + [f'- {x}' for x in _uniq(self.changed_files)] + ['']
        if self.created_files:
            lines += ['Created files/artifacts:'] + [f'- {x}' for x in _uniq(self.created_files)] + ['']
        if self.warnings:
            lines += ['Warnings:'] + [f'- {x}' for x in _uniq(self.warnings)] + ['']
        if self.notes:
            lines += ['Notes:'] + [f'- {x}' for x in _uniq(self.notes)] + ['']
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out


def _safe_stem(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', str(name)).strip('_') or 'item'


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def _ql_dir(root: Path) -> Path:
    out = Path(root) / 'quality_lab'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')
    return path


def _code_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for pat in ('*.cmd', '*.cns', '*.st'):
        files.extend(sorted(Path(root).rglob(pat)))
    return [p for p in files if p.is_file() and not any(part == '__pycache__' for part in p.parts)]


def _read_code(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in _code_files(root):
        try:
            out[_rel(root, path)] = read_text_safely(path)
        except Exception:
            pass
    return out


def _parse_numeric_pair(value: str) -> Tuple[float, float]:
    nums = re.findall(r'-?\d+(?:\.\d+)?', str(value))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), 0.0
    return 0.0, 0.0


def _first_int(value: str, default: int = 0) -> int:
    m = re.search(r'-?\d+', str(value or ''))
    return int(m.group(0)) if m else default


def _command_defs_and_uses(texts: Dict[str, str]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    defined: Dict[str, List[str]] = {}
    used: Dict[str, List[str]] = {}
    cmd_section_re = re.compile(r'\[\s*Command\s*\](.*?)(?=^\s*\[|\Z)', re.I | re.M | re.S)
    name_re = re.compile(r'^\s*name\s*=\s*"?([^"\n;]+)"?', re.I | re.M)
    use_re = re.compile(r'command\s*=\s*"([^"]+)"', re.I)
    for rel, text in texts.items():
        for block in cmd_section_re.finditer(text):
            nm = name_re.search(block.group(1))
            if nm:
                defined.setdefault(nm.group(1).strip(), []).append(rel)
        for use in use_re.finditer(text):
            used.setdefault(use.group(1).strip(), []).append(rel)
    return defined, used


def _state_defs_targets_and_anims(texts: Dict[str, str]) -> Tuple[Dict[int, List[str]], Dict[int, List[str]], Dict[int, List[str]]]:
    defs: Dict[int, List[str]] = {}
    targets: Dict[int, List[str]] = {}
    anim_refs: Dict[int, List[str]] = {}
    for rel, text in texts.items():
        scan = parse_code(text)
        for st in scan.states:
            defs.setdefault(st.number, []).append(rel)
            if 'anim' in st.values:
                anim_refs.setdefault(_first_int(st.values.get('anim', '')), []).append(f'{rel}:StateDef {st.number}')
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                if stype == 'changestate' and 'value' in ctrl.values:
                    val = ctrl.values.get('value', '')
                    if re.fullmatch(r'-?\d+', val.strip()):
                        targets.setdefault(int(val), []).append(f'{rel}:StateDef {st.number}')
                if stype == 'changeanim' and 'value' in ctrl.values:
                    val = ctrl.values.get('value', '')
                    if re.fullmatch(r'-?\d+', val.strip()):
                        anim_refs.setdefault(int(val), []).append(f'{rel}:StateDef {st.number}')
    return defs, targets, anim_refs


def _hitdef_rows(texts: Dict[str, str]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    block_re = re.compile(r'^\s*\[\s*State\s+[^\]]+\]\s*$(.*?)(?=^\s*\[|\Z)', re.I | re.M | re.S)
    kv_re = re.compile(r'^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$', re.M)
    for rel, text in texts.items():
        for block in block_re.finditer(text):
            body = block.group(1)
            if not re.search(r'^\s*type\s*=\s*HitDef\b', body, re.I | re.M):
                continue
            data: Dict[str, str] = {}
            for kv in kv_re.finditer(body):
                data[kv.group(1).strip().lower()] = kv.group(2).strip()
            rows.append({
                'file': rel,
                'damage': _first_int(data.get('damage', '0')),
                'attr': data.get('attr', ''),
                'hitflag': data.get('hitflag', ''),
                'guardflag': data.get('guardflag', ''),
                'pausetime': data.get('pausetime', ''),
                'ground_velocity': data.get('ground.velocity', ''),
                'air_velocity': data.get('air.velocity', ''),
                'raw': data,
            })
    return rows


def _playsnd_refs(texts: Dict[str, str]) -> List[Dict[str, object]]:
    refs: List[Dict[str, object]] = []
    block_re = re.compile(r'^\s*\[\s*State\s+[^\]]+\]\s*$(.*?)(?=^\s*\[|\Z)', re.I | re.M | re.S)
    kv_re = re.compile(r'^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$', re.M)
    for rel, text in texts.items():
        for block in block_re.finditer(text):
            body = block.group(1)
            if not re.search(r'^\s*type\s*=\s*PlaySnd\b', body, re.I | re.M):
                continue
            data: Dict[str, str] = {}
            for kv in kv_re.finditer(body):
                data[kv.group(1).strip().lower()] = kv.group(2).strip()
            value = data.get('value', '')
            nums = re.findall(r'-?\d+', value)
            refs.append({'file': rel, 'value': value, 'group': int(nums[0]) if nums else None, 'sound': int(nums[1]) if len(nums) >= 2 else None})
    return refs


def _def_file_references(root: Path) -> Tuple[Dict[str, str], List[str]]:
    def_path = find_character_file(root, 'def')
    refs: Dict[str, str] = {}
    missing: List[str] = []
    if not def_path or not def_path.exists():
        return refs, ['No DEF file detected.']
    sections = parse_def(read_text_safely(def_path))
    files = sections.get('files')
    if not files:
        return refs, ['DEF has no [Files] section.']
    for k, raw in files.values.items():
        if not raw:
            continue
        target = (def_path.parent / raw.strip().strip('"')).resolve()
        refs[k] = raw
        if not target.exists():
            missing.append(f'{k} = {raw}')
    return refs, missing


def build_reference_matrix(root: Path) -> Dict[str, object]:
    root = Path(root)
    texts = _read_code(root)
    all_code = '\n'.join(texts.values())
    cmd_defs, cmd_uses = _command_defs_and_uses(texts)
    statedefs, targets, anim_refs = _state_defs_targets_and_anims(texts)
    def_refs, missing_def_refs = _def_file_references(root)
    air_path = find_character_file(root, 'air')
    actions = parse_air(read_text_safely(air_path)) if air_path and air_path.exists() else []
    air_action_ids = {a.number for a in actions}
    air_sprite_refs = sorted({(f.group, f.image) for a in actions for f in a.frames})
    missing_anim_refs = sorted(n for n in anim_refs if n not in air_action_ids and n >= 0)
    sff_path = find_character_file(root, 'sff')
    sff_keys: set[Tuple[int, int]] = set()
    sff_variant = 'none'
    sff_warnings: List[str] = []
    if sff_path and sff_path.exists():
        try:
            sff = read_sff(sff_path)
            sff_keys = {s.key for s in sff.sprites}
            sff_variant = sff.variant
            sff_warnings = list(sff.warnings)
        except Exception as exc:
            sff_warnings = [f'SFF read failed: {exc}']
    missing_sprites = [pair for pair in air_sprite_refs if sff_keys and pair not in sff_keys]
    snd_path = find_character_file(root, 'snd')
    snd_ids: set[Tuple[int, int]] = set()
    snd_warnings: List[str] = []
    if snd_path and snd_path.exists():
        try:
            snd = read_snd(snd_path)
            snd_ids = {(s.group, s.sound) for s in snd.sounds if s.group is not None and s.sound is not None}
            snd_warnings = list(snd.warnings)
        except Exception as exc:
            snd_warnings = [f'SND read failed: {exc}']
    sound_refs = _playsnd_refs(texts)
    missing_sounds = [r for r in sound_refs if r.get('group') is not None and r.get('sound') is not None and snd_ids and (int(r['group']), int(r['sound'])) not in snd_ids]
    hitdefs = _hitdef_rows(texts)
    balance_warnings: List[str] = []
    for idx, row in enumerate(hitdefs, start=1):
        dmg = int(row.get('damage') or 0)
        if dmg <= 0:
            balance_warnings.append(f'HitDef #{idx} in {row["file"]}: damage missing/zero.')
        if dmg > 180:
            balance_warnings.append(f'HitDef #{idx} in {row["file"]}: high damage {dmg}.')
        if not row.get('hitflag'):
            balance_warnings.append(f'HitDef #{idx} in {row["file"]}: hitflag missing.')
        if not row.get('guardflag'):
            balance_warnings.append(f'HitDef #{idx} in {row["file"]}: guardflag missing.')
        if row.get('pausetime'):
            p1, p2 = _parse_numeric_pair(str(row['pausetime']))
            if max(p1, p2) > 24:
                balance_warnings.append(f'HitDef #{idx} in {row["file"]}: heavy pausetime {row["pausetime"]}.')
    missing_commands = sorted(k for k in cmd_uses if k not in cmd_defs and not k.startswith('hold'))
    duplicate_commands = {k: v for k, v in cmd_defs.items() if len(v) > 1}
    duplicate_states = {str(k): v for k, v in statedefs.items() if len(v) > 1}
    safe_builtin_targets = {0, 10, 11, 12, 20, 21, 40, 41, 42, 47, 50, 51, 52, 100, 105, 120, 130, 140, 150}
    missing_targets = sorted(n for n in targets if n not in statedefs and n not in safe_builtin_targets)
    return {
        'root': str(root),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'files': {
            'def_references': def_refs,
            'missing_def_references': missing_def_refs,
            'code_files': sorted(texts),
        },
        'commands': {
            'defined_count': len(cmd_defs),
            'used_count': sum(len(v) for v in cmd_uses.values()),
            'missing_definitions': missing_commands,
            'duplicates': duplicate_commands,
        },
        'states': {
            'statedef_count': len(statedefs),
            'changestate_target_count': len(targets),
            'missing_targets': missing_targets,
            'duplicate_statedefs': duplicate_states,
        },
        'animations': {
            'air_file': _rel(root, air_path) if air_path else '',
            'action_count': len(actions),
            'frame_count': sum(len(a.frames) for a in actions),
            'sprite_ref_count': len(air_sprite_refs),
            'missing_common_actions': [n for n in COMMON_ANIMS if actions and n not in air_action_ids],
            'missing_changeanim_actions': missing_anim_refs,
        },
        'sprites': {
            'sff_file': _rel(root, sff_path) if sff_path else '',
            'sff_variant': sff_variant,
            'sprite_count': len(sff_keys),
            'missing_air_sprite_refs': [f'{g},{i}' for g, i in missing_sprites[:1000]],
            'warnings': sff_warnings,
        },
        'sounds': {
            'snd_file': _rel(root, snd_path) if snd_path else '',
            'sound_count': len(snd_ids),
            'playsnd_ref_count': len(sound_refs),
            'missing_playsnd_refs': [f'{r.get("group")},{r.get("sound")} in {r.get("file")}' for r in missing_sounds[:1000]],
            'warnings': snd_warnings,
        },
        'hitdefs': {
            'count': len(hitdefs),
            'damage_values': [int(r.get('damage') or 0) for r in hitdefs],
            'warnings': balance_warnings,
        },
    }


def _matrix_score(matrix: Dict[str, object]) -> Tuple[int, List[str]]:
    score = 100
    reasons: List[str] = []
    def penalize(count: int, points: int, label: str) -> None:
        nonlocal score
        if count:
            loss = min(points, count * max(1, points // 8))
            score -= loss
            reasons.append(f'-{loss}: {label} ({count})')
    files = matrix.get('files', {}) or {}
    cmds = matrix.get('commands', {}) or {}
    states = matrix.get('states', {}) or {}
    anims = matrix.get('animations', {}) or {}
    sprites = matrix.get('sprites', {}) or {}
    sounds = matrix.get('sounds', {}) or {}
    hits = matrix.get('hitdefs', {}) or {}
    penalize(len(files.get('missing_def_references', []) or []), 18, 'missing DEF file references')
    penalize(len(cmds.get('missing_definitions', []) or []), 18, 'commands used but not defined')
    penalize(len(states.get('missing_targets', []) or []), 18, 'ChangeState targets without StateDefs')
    penalize(len(anims.get('missing_changeanim_actions', []) or []), 14, 'ChangeAnim values without AIR actions')
    penalize(len(sprites.get('missing_air_sprite_refs', []) or []), 16, 'AIR frames without SFF sprites')
    penalize(len(sounds.get('missing_playsnd_refs', []) or []), 10, 'PlaySnd refs missing from SND')
    penalize(len(hits.get('warnings', []) or []), 16, 'HitDef warnings')
    return max(0, min(100, score)), reasons


def write_advanced_audit(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab advanced audit written')
    matrix = build_reference_matrix(root)
    score, reasons = _matrix_score(matrix)
    outdir = _ql_dir(root)
    json_path = outdir / 'advanced_reference_matrix.json'
    json_path.write_text(json.dumps(matrix, indent=2), encoding='utf-8')
    result.add_created(_rel(root, json_path))
    lines = [
        '# Quality Lab Advanced Project Audit', '',
        f'Project: `{root.name}`',
        f'Generated: {matrix.get("generated_at")}', '',
        f'## Readiness score: {score}/100', '',
    ]
    if reasons:
        lines += ['Score deductions:'] + reasons + ['']
    else:
        lines += ['No major wiring deductions detected.', '']
    def sec(title: str, items: Sequence[str], ok: str) -> None:
        lines.extend([f'## {title}', ''])
        if items:
            lines.extend(f'- {item}' for item in items[:500])
        else:
            lines.append(f'- {ok}')
        lines.append('')
    sec('Missing DEF file references', matrix['files']['missing_def_references'], 'No missing DEF references detected.')
    sec('Missing command definitions', matrix['commands']['missing_definitions'], 'No missing commands detected.')
    sec('Duplicate command definitions', [f'{k}: {", ".join(v)}' for k, v in (matrix['commands']['duplicates'] or {}).items()], 'No duplicate commands detected.')
    sec('Missing ChangeState targets', [str(x) for x in matrix['states']['missing_targets']], 'No missing state targets detected.')
    sec('Missing ChangeAnim AIR actions', [str(x) for x in matrix['animations']['missing_changeanim_actions']], 'No missing ChangeAnim actions detected.')
    sec('Missing AIR sprite refs in SFF', matrix['sprites']['missing_air_sprite_refs'], 'No missing AIR/SFF sprite refs detected, or no SFF parsed.')
    sec('Missing PlaySnd refs in SND', matrix['sounds']['missing_playsnd_refs'], 'No missing PlaySnd refs detected, or SND has no IDs to compare.')
    sec('HitDef warnings', matrix['hitdefs']['warnings'], 'No obvious HitDef warnings detected.')
    lines += ['## Plain-English next step', '']
    if score < 70:
        lines.append('Fix red-wire issues first: missing commands, missing states, missing actions, and missing assets will break testing before balance matters.')
    elif score < 90:
        lines.append('Project is close enough for playtesting. Use the timing, hitbox, and sound reports next.')
    else:
        lines.append('Project wiring looks healthy. Focus on animation quality, hitbox feel, sound timing, and final packaging.')
    md_path = _write(outdir / 'ADVANCED_PROJECT_AUDIT.md', '\n'.join(lines))
    result.add_created(_rel(root, md_path))
    result.notes.append(f'Readiness score: {score}/100')
    return result


def write_searchable_html_index(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab searchable HTML index written')
    matrix = build_reference_matrix(root)
    texts = _read_code(root)
    air_path = find_character_file(root, 'air')
    actions = parse_air(read_text_safely(air_path)) if air_path and air_path.exists() else []
    hitdefs = _hitdef_rows(texts)
    sff_path = find_character_file(root, 'sff')
    sff_rows = []
    if sff_path and sff_path.exists():
        try:
            info = read_sff(sff_path)
            sff_rows = [{'index': s.index, 'group': s.group, 'image': s.image, 'axis': f'{s.x},{s.y}', 'format': s.format_hint, 'bytes': s.length} for s in info.sprites[:2000]]
        except Exception:
            pass
    snd_path = find_character_file(root, 'snd')
    snd_rows = []
    if snd_path and snd_path.exists():
        try:
            info = read_snd(snd_path)
            snd_rows = [{'index': s.index, 'id': s.id_text, 'sample_rate': s.sample_rate or '', 'bits': s.bits_per_sample or '', 'bytes': s.length} for s in info.sounds[:2000]]
        except Exception:
            pass
    css = 'body{font-family:Arial,sans-serif;margin:20px;line-height:1.4} input{font-size:16px;padding:8px;width:100%;max-width:900px} table{border-collapse:collapse;width:100%;margin:12px 0} th,td{border:1px solid #ccc;padding:5px;text-align:left;font-size:13px} th{background:#eee} .warn{background:#fff1d6}.bad{background:#ffdede}.ok{background:#eaffea} code{background:#eee;padding:2px 4px}'
    js = """
function q(){let s=document.getElementById('search').value.toLowerCase();document.querySelectorAll('tr[data-search]').forEach(r=>{r.style.display=r.dataset.search.includes(s)?'':'none'});}
"""
    def table(title: str, rows: List[Dict[str, object]], cols: Sequence[str]) -> str:
        out = [f'<h2>{html.escape(title)}</h2>', '<table>', '<tr>' + ''.join(f'<th>{html.escape(c)}</th>' for c in cols) + '</tr>']
        for row in rows:
            text = ' '.join(str(row.get(c, '')) for c in cols).lower()
            out.append(f'<tr data-search="{html.escape(text, quote=True)}">' + ''.join(f'<td>{html.escape(str(row.get(c, "")))}</td>' for c in cols) + '</tr>')
        out.append('</table>')
        return '\n'.join(out)
    cmd_rows = []
    for rel, text in texts.items():
        scan = parse_code(text)
        for c in scan.commands:
            cmd_rows.append({'file': rel, 'line': c.line, 'name': c.name, 'command': c.command, 'time': c.time or '', 'buffer': c.buffer_time or ''})
    state_rows = []
    for rel, text in texts.items():
        scan = parse_code(text)
        for st in scan.states:
            state_rows.append({'file': rel, 'line': st.line, 'state': st.number, 'anim': st.values.get('anim',''), 'type': st.values.get('type',''), 'controllers': len(st.controllers)})
    action_rows = [{'action': a.number, 'label': a.label or COMMON_ANIMS.get(a.number,''), 'frames': len(a.frames), 'ticks': sum(max(0, f.ticks) for f in a.frames), 'sprites': ', '.join(_uniq([f'{f.group},{f.image}' for f in a.frames])[:10])} for a in actions]
    hit_rows = [{k: (v if k != 'raw' else '') for k, v in row.items()} for row in hitdefs]
    score, _ = _matrix_score(matrix)
    html_text = f"""<!doctype html><html><head><meta charset='utf-8'><title>MugenForge Quality Index - {html.escape(root.name)}</title><style>{css}</style><script>{js}</script></head><body>
<h1>MugenForge Quality Lab Index</h1>
<p>Project: <code>{html.escape(str(root))}</code></p>
<p>Readiness score from current audit: <strong>{score}/100</strong></p>
<input id='search' onkeyup='q()' placeholder='Search commands, states, animations, sprites, sounds, files...'>
{table('Commands', cmd_rows, ['file','line','name','command','time','buffer'])}
{table('States', state_rows, ['file','line','state','anim','type','controllers'])}
{table('AIR Actions', action_rows, ['action','label','frames','ticks','sprites'])}
{table('HitDefs', hit_rows, ['file','damage','attr','hitflag','guardflag','pausetime','ground_velocity','air_velocity'])}
{table('SFF Sprites', sff_rows, ['index','group','image','axis','format','bytes'])}
{table('SND Sounds', snd_rows, ['index','id','sample_rate','bits','bytes'])}
</body></html>"""
    out = _write(_ql_dir(root) / 'PROJECT_INDEX.html', html_text)
    result.add_created(_rel(root, out))
    result.notes.append('Open PROJECT_INDEX.html in a browser and use the search box to find commands/states/sprites/sounds quickly.')
    return result


def write_move_cards(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab move cards written')
    texts = _read_code(root)
    rows: List[Dict[str, object]] = []
    for rel, text in texts.items():
        scan = parse_code(text)
        for st in scan.states:
            hitdefs = [c for c in st.controllers if (c.stype or c.values.get('type','')).lower() == 'hitdef']
            playsnds = [c for c in st.controllers if (c.stype or c.values.get('type','')).lower() == 'playsnd']
            changestates = [c for c in st.controllers if (c.stype or c.values.get('type','')).lower() == 'changestate']
            if not hitdefs and int(st.number) < 180:
                continue
            row = {
                'file': rel,
                'state': st.number,
                'anim': st.values.get('anim', ''),
                'movetype': st.values.get('movetype', ''),
                'statetype': st.values.get('type', ''),
                'physics': st.values.get('physics', ''),
                'hitdefs': len(hitdefs),
                'damage': '; '.join(h.values.get('damage','') for h in hitdefs),
                'hitflag': '; '.join(h.values.get('hitflag','') for h in hitdefs),
                'guardflag': '; '.join(h.values.get('guardflag','') for h in hitdefs),
                'sounds': '; '.join(p.values.get('value','') for p in playsnds),
                'exits': '; '.join(c.values.get('value','') for c in changestates[-3:]),
            }
            rows.append(row)
    outdir = _ql_dir(root)
    csv_path = outdir / 'MOVE_CARDS.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        cols = ['file','state','anim','movetype','statetype','physics','hitdefs','damage','hitflag','guardflag','sounds','exits']
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader(); writer.writerows(rows)
    result.add_created(_rel(root, csv_path))
    lines = ['# Quality Lab Move Cards', '', 'Use this as a plain-English move editing checklist.', '']
    if not rows:
        lines.append('No attack-like StateDefs detected yet.')
    for row in rows[:500]:
        lines += [f'## State {row["state"]}', '', f'- File: `{row["file"]}`', f'- Anim: `{row["anim"]}`', f'- MoveType: `{row["movetype"]}` / StateType: `{row["statetype"]}` / Physics: `{row["physics"]}`', f'- HitDefs: `{row["hitdefs"]}`', f'- Damage: `{row["damage"]}`', f'- Hit/Guard flags: `{row["hitflag"]}` / `{row["guardflag"]}`', f'- Sounds: `{row["sounds"]}`', f'- Exit ChangeState values: `{row["exits"]}`', '']
    md_path = _write(outdir / 'MOVE_CARDS.md', '\n'.join(lines))
    result.add_created(_rel(root, md_path))
    result.notes.append(f'Move cards generated for {len(rows)} states.')
    return result


def _decode_sprite_image(sff_path: Path, sprite) -> Optional[Tuple[object, int, int]]:
    try:
        from PIL import Image
    except Exception:
        return None
    if sprite.format_hint not in {'pcx', 'png'} or sprite.length <= 0:
        return None
    data = sff_path.read_bytes()[sprite.data_offset:sprite.data_offset + sprite.length]
    try:
        img = Image.open(BytesIO(data)).convert('RGBA')
        return img, img.width, img.height
    except Exception:
        return None


def _alpha_bbox(img) -> Optional[Tuple[int, int, int, int]]:
    # Prefer true alpha. If every pixel is opaque, treat the top-left color as background.
    alpha = img.getchannel('A')
    bbox = alpha.getbbox()
    if bbox and bbox != (0, 0, img.width, img.height):
        l, t, r, b = bbox
        return l, t, r - 1, b - 1
    try:
        bg = img.getpixel((0, 0))[:3]
        pix = img.load()
        xs: List[int] = []
        ys: List[int] = []
        for y in range(img.height):
            for x in range(img.width):
                rgba = pix[x, y]
                if rgba[3] > 0 and rgba[:3] != bg:
                    xs.append(x); ys.append(y)
        if xs and ys:
            return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        pass
    return bbox and (bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1)


def build_alpha_clsn_suggestions(root: Path, *, padding: int = 2) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab alpha CLSN suggestions written')
    sff_path = find_character_file(root, 'sff')
    air_path = find_character_file(root, 'air')
    if not sff_path or not sff_path.exists():
        raise FileNotFoundError('No SFF file found for alpha CLSN suggestions.')
    if not air_path or not air_path.exists():
        raise FileNotFoundError('No AIR file found for alpha CLSN suggestions.')
    info = read_sff(sff_path)
    lookup = sprite_lookup(info)
    actions = parse_air(read_text_safely(air_path))
    outdir = _ql_dir(root) / 'auto_clsn'
    outdir.mkdir(parents=True, exist_ok=True)
    sprite_bboxes: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}
    for key, spr in lookup.items():
        dec = _decode_sprite_image(sff_path, spr)
        if not dec:
            continue
        img, _, _ = dec
        bbox = _alpha_bbox(img)
        if bbox:
            sprite_bboxes[key] = bbox
    suggestions: List[Dict[str, object]] = []
    air_lines = ['; Quality Lab auto-generated Clsn2 suggestions from sprite visible pixels.', '; Review in the CLSN Editor before replacing hand-tuned boxes.', '']
    for action in actions:
        if not action.frames:
            continue
        air_lines += [f'[Begin Action {action.number}] ; {action.label or COMMON_ANIMS.get(action.number, "")}'.rstrip()]
        for frame_index, frame in enumerate(action.frames):
            spr = lookup.get((frame.group, frame.image))
            bbox = sprite_bboxes.get((frame.group, frame.image))
            if spr and bbox:
                l, t, r, b = bbox
                x1 = l - spr.x + frame.x - int(padding)
                y1 = t - spr.y + frame.y - int(padding)
                x2 = r - spr.x + frame.x + int(padding)
                y2 = b - spr.y + frame.y + int(padding)
                # Avoid absurd full-screen boxes from odd palettes.
                if x2 > x1 and y2 > y1 and (x2 - x1) <= 500 and (y2 - y1) <= 500:
                    suggestions.append({'action': action.number, 'frame_index': frame_index, 'sprite': f'{frame.group},{frame.image}', 'clsn2': [x1, y1, x2, y2], 'ticks': frame.ticks})
                    air_lines += ['Clsn2: 1', f'Clsn2[0] = {x1},{y1},{x2},{y2}']
                else:
                    result.add_warning(f'Skipped suspicious bbox for action {action.number} sprite {frame.group},{frame.image}.')
            else:
                result.add_warning(f'No decodable sprite/bbox for action {action.number} frame {frame_index} sprite {frame.group},{frame.image}.')
            air_lines.append(f'{frame.group}, {frame.image}, {frame.x}, {frame.y}, {frame.ticks}' + (f', {frame.flags}' if frame.flags else ''))
        air_lines.append('')
    json_path = outdir / 'alpha_clsn_suggestions.json'
    json_path.write_text(json.dumps({'created_at': datetime.now().isoformat(timespec='seconds'), 'source_sff': str(sff_path), 'source_air': str(air_path), 'suggestions': suggestions}, indent=2), encoding='utf-8')
    result.add_created(_rel(root, json_path))
    air_out = _write(outdir / 'alpha_clsn_suggested_actions.air', '\n'.join(air_lines))
    result.add_created(_rel(root, air_out))
    result.notes.append(f'Generated {len(suggestions)} frame-level Clsn2 suggestions from supported sprites.')
    return result


def write_alpha_clsn_air_copy(root: Path, *, padding: int = 2) -> QualityLabResult:
    root = Path(root)
    result = build_alpha_clsn_suggestions(root, padding=padding)
    src = _ql_dir(root) / 'auto_clsn' / 'alpha_clsn_suggested_actions.air'
    if src.exists():
        out = root / f'{root.name}_alpha_body_clsn_copy.air'
        out.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        result.add_created(_rel(root, out))
        result.notes.append('Created a separate AIR copy with generated body CLSN. Original AIR was not overwritten.')
    return result


def write_animation_timing_sheet(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab animation timing sheet written')
    air_path = find_character_file(root, 'air')
    if not air_path or not air_path.exists():
        raise FileNotFoundError('No AIR file found.')
    actions = parse_air(read_text_safely(air_path))
    outdir = _ql_dir(root)
    csv_path = outdir / 'ANIMATION_TIMING.csv'
    rows: List[Dict[str, object]] = []
    for a in actions:
        ticks = sum(max(0, f.ticks) for f in a.frames)
        seconds = ticks / 60.0
        flag = ''
        if not a.frames:
            flag = 'empty'
        elif ticks <= 6:
            flag = 'very fast'
        elif ticks >= 120:
            flag = 'very long'
        rows.append({'action': a.number, 'label': a.label or COMMON_ANIMS.get(a.number, ''), 'frames': len(a.frames), 'ticks': ticks, 'seconds_at_60fps': f'{seconds:.3f}', 'note': flag})
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        cols = ['action','label','frames','ticks','seconds_at_60fps','note']
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)
    result.add_created(_rel(root, csv_path))
    lines = ['# Quality Lab Animation Timing Sheet', '', '| Action | Label | Frames | Ticks | Seconds | Note |', '|---:|---|---:|---:|---:|---|']
    for row in rows:
        lines.append(f'| {row["action"]} | {row["label"]} | {row["frames"]} | {row["ticks"]} | {row["seconds_at_60fps"]} | {row["note"]} |')
    md = _write(outdir / 'ANIMATION_TIMING.md', '\n'.join(lines))
    result.add_created(_rel(root, md))
    return result


def create_asset_swap_pack(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab asset swap pack created')
    outdir = _ql_dir(root) / 'asset_swap_pack'
    if outdir.exists():
        shutil.rmtree(outdir)
    sprites_dir = outdir / 'sprites'
    sounds_dir = outdir / 'sounds'
    outdir.mkdir(parents=True, exist_ok=True)
    sff_path = find_character_file(root, 'sff')
    sprite_exports: List[str] = []
    if sff_path and sff_path.exists():
        try:
            for p in export_all_sprites(sff_path, sprites_dir):
                sprite_exports.append(_rel(outdir, p))
        except Exception as exc:
            result.add_warning(f'Sprite export failed: {exc}')
    else:
        result.add_warning('No SFF found for sprite export.')
    snd_path = find_character_file(root, 'snd')
    sound_exports: List[str] = []
    if snd_path and snd_path.exists():
        try:
            for p in export_all_sounds(snd_path, sounds_dir):
                sound_exports.append(_rel(outdir, p))
        except Exception as exc:
            result.add_warning(f'Sound export failed: {exc}')
    else:
        result.add_warning('No SND found for sound export.')
    manifest = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'source_project': str(root),
        'source_sff': str(sff_path) if sff_path else '',
        'source_snd': str(snd_path) if snd_path else '',
        'sprites': sprite_exports,
        'sounds': sound_exports,
        'next_step': 'Replace exported art/audio, then use MugenForge SFF/SND builders or replacement-manifest tools to rebuild.',
    }
    manifest_path = outdir / 'asset_swap_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    readme = _write(outdir / 'README_ASSET_SWAP.md', f'''# Asset Swap Pack

This folder lets a non-coder replace art and sound files outside the raw M.U.G.E.N formats.

## What was exported

- Sprites: {len(sprite_exports)}
- Sounds: {len(sound_exports)}

## Beginner workflow

1. Edit or replace files in `sprites/` and `sounds/`.
2. Keep filenames stable when possible.
3. Return to MugenForge.
4. Use Sprites/SND build or replacement workflows to rebuild the packed assets.
5. Run Quality Lab audit again.
''')
    result.add_created(_rel(root, manifest_path))
    result.add_created(_rel(root, readme))
    result.add_created(_rel(root, outdir))
    result.notes.append(f'Exported {len(sprite_exports)} sprites and {len(sound_exports)} sounds where supported.')
    return result


def create_backup_restore_bundle(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab backup/restore bundle created')
    outdir = _ql_dir(root) / 'backups'
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = outdir / f'{root.name}_backup_restore_{stamp}.zip'
    skip_parts = {'__pycache__'}
    skip_ext = {'.pyc', '.tmp'}
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        restore = f'''# Restore Instructions\n\nBackup generated: {datetime.now().isoformat(timespec="seconds")}\nProject: {root}\n\nTo restore, extract this ZIP next to the original character folder. It contains a full snapshot of the folder at backup time.\n'''
        zf.writestr(f'{root.name}/RESTORE_INSTRUCTIONS.md', restore)
        for p in root.rglob('*'):
            if not p.is_file():
                continue
            if p == out or any(part in skip_parts for part in p.parts) or p.suffix.lower() in skip_ext:
                continue
            zf.write(p, Path(root.name) / p.relative_to(root))
    result.add_created(_rel(root, out))
    result.notes.append('Use this before risky generated-code or asset passes.')
    return result


def write_beginner_fix_plan(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='Quality Lab beginner fix plan written')
    matrix = build_reference_matrix(root)
    score, reasons = _matrix_score(matrix)
    tasks: List[Tuple[str, str]] = []
    if matrix['files']['missing_def_references']:
        tasks.append(('1', 'Open DEF references or run Smart Complete/Repair to restore missing files.'))
    if matrix['commands']['missing_definitions']:
        tasks.append(('2', 'Use Feature Bank/Recipe Bank to reinstall missing command presets.'))
    if matrix['states']['missing_targets']:
        tasks.append(('3', 'Use Code Map/Move Wizard to add or reroute missing StateDefs.'))
    if matrix['animations']['missing_changeanim_actions'] or matrix['animations']['missing_common_actions']:
        tasks.append(('4', 'Use Factory+ Complete Missing AIR Actions, then preview in Animation Player.'))
    if matrix['sprites']['missing_air_sprite_refs']:
        tasks.append(('5', 'Use Factory+ placeholder SFF rebuild or Smart Sprite Mapper to satisfy missing AIR sprites.'))
    if matrix['sounds']['missing_playsnd_refs']:
        tasks.append(('6', 'Use Sounds tab placeholder bank or SND builder to satisfy missing PlaySnd references.'))
    if matrix['hitdefs']['warnings']:
        tasks.append(('7', 'Open Move Cards and tune HitDef damage, flags, pausetime, and velocity.'))
    if not tasks:
        tasks.append(('OK', 'No major beginner-blocking issue detected. Replace placeholder assets and playtest feel.'))
    lines = ['# What Should I Fix Next?', '', f'Readiness score: **{score}/100**', '']
    if reasons:
        lines += ['## Why the score changed', ''] + reasons + ['']
    lines += ['## Ordered beginner tasks', '']
    for n, task in tasks:
        lines.append(f'{n}. {task}')
    lines += ['', '## Safe rule', '', 'Make a Quality Lab backup before generated-code passes or asset rebuilds.']
    out = _write(_ql_dir(root) / 'WHAT_TO_FIX_NEXT.md', '\n'.join(lines))
    result.add_created(_rel(root, out))
    result.notes.append(f'Fix plan score: {score}/100')
    return result


def run_quality_lab_pass(root: Path) -> QualityLabResult:
    root = Path(root)
    result = QualityLabResult(title='One-Click Quality Lab Pass finished')
    for label, func in [
        ('backup', create_backup_restore_bundle),
        ('advanced audit', write_advanced_audit),
        ('html index', write_searchable_html_index),
        ('move cards', write_move_cards),
        ('animation timing', write_animation_timing_sheet),
        ('alpha clsn suggestions', build_alpha_clsn_suggestions),
        ('asset swap pack', create_asset_swap_pack),
        ('fix plan', write_beginner_fix_plan),
    ]:
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    result.notes.append('Quality Lab does not overwrite the main AIR during the one-click pass; it writes suggestions/copies so beginners can review before replacing tuned data.')
    return result
