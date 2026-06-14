from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import html
import re
from typing import Dict, Iterable, List, Optional, Sequence

from .artifact_io import write_csv_artifact, write_json_artifact, write_text_artifact
from .parsers import parse_air, parse_code, read_text_safely, COMMON_ANIMS
from .move_wizard import find_character_file
from .quality_lab import build_reference_matrix, _matrix_score
from .automation_bank import available_presets, kit_names, kit_preview_text, feature_bank_stats_text
from .shared_utils import BaseResult, uniq, rel_path as _rel, get_code_files, parse_first_int

@dataclass
class CreatorHubResult(BaseResult):
    title: str = 'Creator Hub'


def _hub_dir(root: Path) -> Path:
    out = Path(root) / 'creator_hub'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(path: Path, text: str) -> Path:
    return write_text_artifact(path, text)


def _write_json(path: Path, data: object) -> Path:
    return write_json_artifact(path, data)


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> Path:
    return write_csv_artifact(path, rows, fields)


def _read_code_texts(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in get_code_files(root):
        try:
            out[_rel(root, path)] = read_text_safely(path)
        except Exception:
            pass
    return out


def _all_commands(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in sorted(Path(root).rglob('*.cmd')):
        if path.is_file() and not any(part.startswith('.') or part == '__pycache__' for part in path.parts):
            try:
                scan = parse_code(read_text_safely(path))
                for c in scan.commands:
                    rows.append({
                        'file': _rel(root, path), 'line': c.line, 'name': c.name,
                        'command': c.command, 'time': c.time or '', 'buffer_time': c.buffer_time or '',
                        'normalized': _normalize_input(c.command),
                    })
            except Exception:
                pass
    return rows


def _all_states(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in get_code_files(root):
        try:
            text = read_text_safely(path)
            scan = parse_code(text)
            for st in scan.states:
                rows.append({
                    'file': _rel(root, path), 'line': st.line, 'state': st.number,
                    'anim': st.values.get('anim', ''), 'ctrl': st.values.get('ctrl', ''), 'type': st.values.get('type', ''),
                    'controller_count': len(st.controllers),
                })
        except Exception:
            pass
    return rows


def _parse_hitdefs(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    block_re = re.compile(r'^\s*\[\s*State\s+[^\]]+\]\s*$(.*?)(?=^\s*\[|\Z)', re.I | re.M | re.S)
    kv_re = re.compile(r'^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$', re.M)
    for rel, text in _read_code_texts(root).items():
        for block in block_re.finditer(text):
            body = block.group(1)
            if not re.search(r'^\s*type\s*=\s*HitDef\b', body, re.I | re.M):
                continue
            data: Dict[str, str] = {}
            for kv in kv_re.finditer(body):
                data[kv.group(1).strip().lower()] = kv.group(2).strip()
            state_no = _nearest_state_before(text, block.start())
            damage = parse_first_int(data.get('damage', '0'))
            pausetime = data.get('pausetime', '')
            ground_velocity = data.get('ground.velocity', '')
            air_velocity = data.get('air.velocity', '')
            guard_velocity = data.get('guard.velocity', '')
            rows.append({
                'file': rel,
                'state': state_no if state_no is not None else '',
                'damage': damage,
                'attr': data.get('attr', ''),
                'hitflag': data.get('hitflag', ''),
                'guardflag': data.get('guardflag', ''),
                'pausetime': pausetime,
                'ground_velocity': ground_velocity,
                'air_velocity': air_velocity,
                'guard_velocity': guard_velocity,
                'sparkno': data.get('sparkno', ''),
                'hitsound': data.get('hitsound', ''),
                'guardsound': data.get('guardsound', ''),
                'recommendation': _damage_recommendation(damage, state_no, data),
            })
    return rows


def _nearest_state_before(text: str, offset: int) -> Optional[int]:
    prefix = text[:offset]
    found = None
    for m in re.finditer(r'^\s*\[\s*StateDef\s+(-?\d+)\s*\]', prefix, re.I | re.M):
        found = int(m.group(1))
    return found


def _normalize_input(command: str) -> str:
    s = str(command or '').lower().replace(' ', '')
    s = re.sub(r'[^a-z0-9,/$~+]', '', s)
    return s.replace('df', 'd/f').replace('db', 'd/b')


def _command_family(command: str) -> str:
    s = _normalize_input(command).replace('~', '').replace('$', '')
    s = re.sub(r',[abcxyzs][0-9]*$', ',BTN', s)
    return re.sub(r'\+[abcxyzs]$', '+BTN', s)


def _difficulty_for_input(command: str, time: object = '') -> str:
    s = _normalize_input(command)
    commas = s.count(',')
    pluses = s.count('+')
    try:
        t = int(time) if str(time).strip() else 15
    except Exception:
        t = 15
    score = commas + pluses + (1 if '~' in str(command) else 0) + (1 if '$' in str(command) else 0)
    if t and t < 8:
        score += 1
    if score <= 1:
        return 'easy'
    if score <= 3:
        return 'normal'
    if score <= 5:
        return 'advanced'
    return 'hard'


def _damage_recommendation(damage: int, state_no: Optional[int], data: Dict[str, str]) -> str:
    state_no = state_no or 0
    attr = data.get('attr', '').lower()
    if damage <= 0:
        return 'Set a real damage value. Placeholder/zero damage will feel broken unless intentional.'
    if state_no >= 3000 or 'ha' in attr or 'super' in attr:
        lo, hi = 180, 360
    elif state_no >= 1000 or 'sa' in attr:
        lo, hi = 55, 130
    elif state_no >= 600:
        lo, hi = 35, 95
    else:
        lo, hi = 18, 75
    if damage < lo:
        return f'Probably low for this move class. Try {lo}-{hi} unless this is a jab/setup.'
    if damage > hi:
        return f'Probably high for this move class. Try {lo}-{hi} unless this is a slow punish/super.'
    return f'Looks plausible. Typical range for this bucket: {lo}-{hi}.'


def _score_badge(score: int) -> str:
    if score >= 90:
        return 'release-candidate'
    if score >= 75:
        return 'playable-but-polish'
    if score >= 55:
        return 'prototype'
    return 'needs-repair'


def write_creator_dashboard(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    matrix = build_reference_matrix(root)
    score, reasons = _matrix_score(matrix)
    badge = _score_badge(score)
    feature_count = len(available_presets())
    kit_count = len(kit_names())
    links = [
        ('Project Task Board', 'CREATOR_TASK_BOARD.html'),
        ('Input Conflict Lab', 'INPUT_CONFLICT_LAB.html'),
        ('Balance Autotune Plan', 'BALANCE_AUTOTUNE_PLAN.md'),
        ('Combo Trial Pack', 'COMBO_TRIALS.md'),
        ('Asset Request Pack', 'ASSET_REQUEST_PACK.md'),
        ('No-Code Recipes', 'NO_CODE_RECIPES.md'),
        ('Release Website', 'release_site/index.html'),
    ]
    md = [
        '# MugenForge Creator Dashboard', '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
        f'Project readiness score: **{score}/100** — `{badge}`', '',
        f'No-code bank available in this build: **{feature_count} presets** and **{kit_count} kits**.', '',
        '## What to do next', '',
    ]
    if reasons:
        md += [f'- {r}' for r in reasons]
    else:
        md += ['- No major structural issues detected. Focus on art, sound, polish, and playtesting.']
    md += ['', '## Beginner workflow', '',
           '1. Open `CREATOR_TASK_BOARD.html` and clear the top red/yellow tasks first.',
           '2. Use the Feature Bank or kits for missing move/system code instead of hand-writing CMD/CNS blocks.',
           '3. Replace placeholder sprites/sounds through the Asset Swap Pack or Sprite Lab workflows.',
           '4. Run Quality Lab and Creator Hub again before packaging a release.', '',
           '## Generated companion files', '']
    md += [f'- [{label}]({href})' for label, href in links]
    md_path = _write(out / 'CREATOR_DASHBOARD.md', '\n'.join(md))

    cards = []
    cards.append(f'<div class="score {badge}"><b>{score}/100</b><span>{html.escape(badge)}</span></div>')
    summary_items = [
        ('Commands', str((matrix.get('commands') or {}).get('defined_count', 0))),
        ('StateDefs', str((matrix.get('states') or {}).get('statedef_count', 0))),
        ('AIR actions', str((matrix.get('animations') or {}).get('action_count', 0))),
        ('Sprite refs', str((matrix.get('animations') or {}).get('sprite_ref_count', 0))),
        ('Sounds', str((matrix.get('sounds') or {}).get('sound_count', 0))),
        ('HitDefs', str((matrix.get('hitdefs') or {}).get('count', 0))),
    ]
    cards.append('<div class="grid">' + ''.join(f'<div class="mini"><b>{html.escape(k)}</b><span>{html.escape(v)}</span></div>' for k, v in summary_items) + '</div>')
    cards.append('<h2>Next fixes</h2><ul>' + ''.join(f'<li>{html.escape(r)}</li>' for r in (reasons or ['No major structural issues detected.'])) + '</ul>')
    cards.append('<h2>Open tools</h2><div class="links">' + ''.join(f'<a href="{html.escape(h)}">{html.escape(l)}</a>' for l, h in links) + '</div>')
    html_text = f'''<!doctype html>
<html><head><meta charset="utf-8"><title>MugenForge Creator Dashboard</title>
<style>
body{{font-family:Arial,sans-serif;margin:24px;background:#f7f7fb;color:#20242a}}a{{color:#0b5cab}}.score{{display:inline-flex;gap:18px;align-items:baseline;border-radius:14px;padding:18px 22px;background:white;box-shadow:0 2px 10px #0001;margin-bottom:18px}}.score b{{font-size:42px}}.score span{{font-size:18px;text-transform:uppercase;letter-spacing:.08em}}.release-candidate{{border-left:10px solid #1a9f55}}.playable-but-polish{{border-left:10px solid #6f9f1a}}.prototype{{border-left:10px solid #c79b1b}}.needs-repair{{border-left:10px solid #b74040}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:12px 0 24px}}.mini{{background:white;border-radius:12px;padding:14px;box-shadow:0 1px 6px #0001}}.mini b{{display:block;color:#555}}.mini span{{font-size:28px}}.links{{display:flex;flex-wrap:wrap;gap:10px}}.links a{{background:white;border:1px solid #ddd;border-radius:10px;padding:10px 12px;text-decoration:none}}li{{margin:6px 0}}
</style></head><body><h1>MugenForge Creator Dashboard</h1><p>Generated {html.escape(datetime.now().isoformat(timespec='seconds'))}</p>{''.join(cards)}</body></html>'''
    html_path = _write(out / 'CREATOR_DASHBOARD.html', html_text)
    result = CreatorHubResult('Creator Dashboard written')
    result.add_created(_rel(root, md_path)); result.add_created(_rel(root, html_path))
    result.notes.append(f'Readiness score: {score}/100 ({badge}).')
    return result


def write_project_task_board(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    matrix = build_reference_matrix(root)
    tasks: List[Dict[str, str]] = []

    def add(priority: str, lane: str, title: str, why: str, action: str) -> None:
        tasks.append({'priority': priority, 'lane': lane, 'title': title, 'why': why, 'action': action})

    files = matrix.get('files', {}) or {}
    for ref in files.get('missing_def_references', []) or []:
        add('High', 'Project Setup', f'Missing DEF file reference: {ref}', 'M.U.G.E.N may fail to load the character.', 'Use Auto Setup/Repair or fix the DEF [Files] entry.')
    cmds = matrix.get('commands', {}) or {}
    for name in cmds.get('missing_definitions', []) or []:
        add('High', 'Inputs', f'Command used but not defined: {name}', 'A move may never activate.', 'Create the command in Feature Bank or Code Assistant.')
    for name in (cmds.get('duplicates', {}) or {}).keys():
        add('Medium', 'Inputs', f'Duplicate command definition: {name}', 'Duplicate inputs can create confusing behavior.', 'Merge or rename duplicate [Command] blocks.')
    states = matrix.get('states', {}) or {}
    for st in states.get('missing_targets', []) or []:
        add('High', 'Code Logic', f'Missing target StateDef {st}', 'A ChangeState can send the character to a missing state.', 'Use Move Wizard/Feature Bank to create the missing StateDef or correct the value.')
    anims = matrix.get('animations', {}) or {}
    for a in anims.get('missing_common_actions', [])[:60] or []:
        add('Medium', 'Animations', f'Missing common AIR action {a}', COMMON_ANIMS.get(int(a), 'Common animation action is not present.'), 'Use Factory+/Factory Max required action library or create placeholder action.')
    for a in anims.get('missing_changeanim_actions', [])[:60] or []:
        add('High', 'Animations', f'Code references missing AIR action {a}', 'ChangeAnim expects an animation that does not exist.', 'Create that AIR action or change the code to an existing animation.')
    sprites = matrix.get('sprites', {}) or {}
    for ref in sprites.get('missing_air_sprite_refs', [])[:100] or []:
        add('Medium', 'Sprites', f'Missing sprite used by AIR: {ref}', 'The animation frame may show blank/missing art.', 'Use Sprite Lab placeholder rebuild or import the sprite.')
    sounds = matrix.get('sounds', {}) or {}
    for ref in sounds.get('missing_playsnd_refs', [])[:100] or []:
        add('Low', 'Sounds', f'Missing PlaySnd cue: {ref}', 'A move may play no sound.', 'Use placeholder SND rebuild or import a WAV for the cue.')
    hits = matrix.get('hitdefs', {}) or {}
    for warn in hits.get('warnings', [])[:80] or []:
        add('Medium', 'Balance', warn, 'HitDef tuning can make the move feel broken or unfair.', 'Open Balance Autotune Plan and adjust values deliberately.')
    if not tasks:
        add('Low', 'Polish', 'No critical structural tasks found', 'The project looks structurally healthy.', 'Focus on sprites, animation timing, sounds, palettes, testing, and release notes.')

    csv_path = out / 'CREATOR_TASK_BOARD.csv'
    _write_csv(csv_path, tasks, ['priority', 'lane', 'title', 'why', 'action'])
    md = ['# Creator Task Board', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', '| Priority | Lane | Task | Why it matters | Suggested action |', '|---|---|---|---|---|']
    md += [f"| {t['priority']} | {t['lane']} | {t['title']} | {t['why']} | {t['action']} |" for t in tasks]
    md_path = _write(out / 'CREATOR_TASK_BOARD.md', '\n'.join(md))
    lanes: Dict[str, List[Dict[str, str]]] = {}
    for t in tasks:
        lanes.setdefault(t['lane'], []).append(t)
    columns = []
    for lane, items in sorted(lanes.items()):
        cards = ''.join(f"<div class='card {html.escape(i['priority']).lower()}'><b>{html.escape(i['priority'])}</b><h3>{html.escape(i['title'])}</h3><p>{html.escape(i['why'])}</p><small>{html.escape(i['action'])}</small></div>" for i in items)
        columns.append(f"<section><h2>{html.escape(lane)} <span>{len(items)}</span></h2>{cards}</section>")
    html_path = _write(out / 'CREATOR_TASK_BOARD.html', f'''<!doctype html><html><head><meta charset="utf-8"><title>Creator Task Board</title><style>body{{font-family:Arial,sans-serif;background:#f5f5f8;margin:20px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}section{{background:white;border-radius:14px;padding:12px;box-shadow:0 1px 8px #0001}}h2 span{{font-size:14px;color:#777}}.card{{border-left:8px solid #aaa;background:#fbfbfd;margin:10px 0;padding:10px;border-radius:10px}}.card.high{{border-color:#c0392b}}.card.medium{{border-color:#d69500}}.card.low{{border-color:#388e3c}}h3{{margin:.2em 0}}small{{color:#555}}</style></head><body><h1>MugenForge Creator Task Board</h1><p>Use this like a non-coder production board. Clear high-priority cards first.</p><main>{''.join(columns)}</main></body></html>''')
    result = CreatorHubResult('Creator Task Board written')
    for p in (csv_path, md_path, html_path): result.add_created(_rel(root, p))
    result.notes.append(f'Created {len(tasks)} task cards.')
    return result


def write_input_conflict_lab(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    rows = _all_commands(root)
    by_input: Dict[str, List[Dict[str, object]]] = {}
    by_family: Dict[str, List[Dict[str, object]]] = {}
    for r in rows:
        by_input.setdefault(str(r['normalized']), []).append(r)
        by_family.setdefault(_command_family(str(r['command'])), []).append(r)
    issues: List[Dict[str, str]] = []
    for key, group in by_input.items():
        if len(group) > 1:
            issues.append({'severity': 'High', 'type': 'Duplicate exact input', 'input': key, 'commands': ', '.join(str(g['name']) for g in group), 'fix': 'Rename or remove one command, or deliberately route duplicates with priority order.'})
    for key, group in by_family.items():
        if len(group) > 1 and not any(len(group) == len(by_input.get(str(g['normalized']), [])) for g in group):
            names = ', '.join(str(g['name']) for g in group)
            issues.append({'severity': 'Medium', 'type': 'Similar motion family', 'input': key, 'commands': names, 'fix': 'Check command times and order. Put stricter/super commands above broad simple commands.'})
    for r in rows:
        if not str(r.get('time', '')).strip():
            issues.append({'severity': 'Low', 'type': 'Missing command time', 'input': str(r['command']), 'commands': str(r['name']), 'fix': 'Add time = 10-20 for special motions; lower for strict inputs.'})
        if _difficulty_for_input(str(r['command']), r.get('time')) == 'hard':
            issues.append({'severity': 'Medium', 'type': 'Hard input', 'input': str(r['command']), 'commands': str(r['name']), 'fix': 'Consider a beginner-friendly alternate input or add buffering.'})
    csv_path = out / 'INPUT_CONFLICT_LAB.csv'
    command_rows = []
    for r in rows:
        rr = dict(r)
        rr['difficulty'] = _difficulty_for_input(str(r['command']), r.get('time'))
        command_rows.append(rr)
    _write_csv(csv_path, command_rows, ['file', 'line', 'name', 'command', 'time', 'buffer_time', 'normalized', 'difficulty'])
    issue_path = out / 'INPUT_CONFLICT_ISSUES.json'
    _write_json(issue_path, issues)
    md = ['# Input Conflict Lab', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', f'Commands scanned: **{len(rows)}**', f'Issues found: **{len(issues)}**', '', '## Issues', '']
    if issues:
        md += [f"- **{i['severity']}** — {i['type']} — `{i['input']}` — {i['commands']} — {i['fix']}" for i in issues]
    else:
        md.append('- No obvious input conflicts detected.')
    md += ['', '## Commands', '', '| Name | Input | Time | Difficulty | File |', '|---|---|---:|---|---|']
    for r in rows:
        md.append(f"| {r['name']} | `{r['command']}` | {r.get('time','')} | {_difficulty_for_input(str(r['command']), r.get('time'))} | {r['file']}:{r['line']} |")
    md_path = _write(out / 'INPUT_CONFLICT_LAB.md', '\n'.join(md))
    table = ''.join(f"<tr><td>{html.escape(str(r['name']))}</td><td><code>{html.escape(str(r['command']))}</code></td><td>{html.escape(str(r.get('time','')))}</td><td>{_difficulty_for_input(str(r['command']), r.get('time'))}</td><td>{html.escape(str(r['file']))}:{r['line']}</td></tr>" for r in rows)
    issue_cards = ''.join(f"<li><b>{html.escape(i['severity'])}</b> {html.escape(i['type'])}: <code>{html.escape(i['input'])}</code> — {html.escape(i['commands'])}<br><small>{html.escape(i['fix'])}</small></li>" for i in issues) or '<li>No obvious input conflicts detected.</li>'
    html_path = _write(out / 'INPUT_CONFLICT_LAB.html', f'''<!doctype html><html><head><meta charset="utf-8"><title>Input Conflict Lab</title><style>body{{font-family:Arial,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px}}th{{background:#eee}}li{{margin:8px 0}}</style></head><body><h1>Input Conflict Lab</h1><h2>Issues</h2><ul>{issue_cards}</ul><h2>Command Table</h2><table><tr><th>Name</th><th>Input</th><th>Time</th><th>Difficulty</th><th>Location</th></tr>{table}</table></body></html>''')
    result = CreatorHubResult('Input Conflict Lab written')
    for p in (csv_path, issue_path, md_path, html_path): result.add_created(_rel(root, p))
    result.notes.append(f'Scanned {len(rows)} command definitions and found {len(issues)} input concerns.')
    return result


def write_balance_autotune_plan(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    rows = _parse_hitdefs(root)
    csv_path = out / 'BALANCE_AUTOTUNE_PLAN.csv'
    fields = ['file', 'state', 'damage', 'attr', 'hitflag', 'guardflag', 'pausetime', 'ground_velocity', 'air_velocity', 'guard_velocity', 'sparkno', 'hitsound', 'guardsound', 'recommendation']
    _write_csv(csv_path, rows, fields)
    dmg_values = [int(r.get('damage') or 0) for r in rows]
    md = ['# Balance Autotune Plan', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
          'This is a safe plan, not a destructive auto-patch. It tells a non-coder which values to inspect first.', '']
    if dmg_values:
        md += [f'- HitDefs scanned: **{len(rows)}**', f'- Min damage: **{min(dmg_values)}**', f'- Max damage: **{max(dmg_values)}**', f'- Average damage: **{round(sum(dmg_values)/len(dmg_values), 1)}**', '']
    else:
        md.append('- No HitDefs found yet. Use Feature Bank or Move Wizard to add attacks.')
    md += ['## Move tuning rows', '', '| File | State | Damage | Attr | Pausetime | Recommendation |', '|---|---:|---:|---|---|---|']
    for r in rows:
        md.append(f"| {r.get('file','')} | {r.get('state','')} | {r.get('damage','')} | {r.get('attr','')} | {r.get('pausetime','')} | {r.get('recommendation','')} |")
    md += ['', '## Beginner tuning rules of thumb', '',
           '- Light normals should be quick, low damage, and safe-ish only if range is short.',
           '- Heavy normals can hit harder but need more startup/recovery or more whiff risk.',
           '- Specials should cost position, risk, meter, or recovery if they control big screen space.',
           '- Supers can be powerful, but the resource cost and startup/freeze must make sense.',
           '- Do not auto-raise every weak move. Weak moves may be combo starters, pokes, or utility tools.']
    md_path = _write(out / 'BALANCE_AUTOTUNE_PLAN.md', '\n'.join(md))
    js_path = _write_json(out / 'BALANCE_AUTOTUNE_PLAN.json', rows)
    result = CreatorHubResult('Balance Autotune Plan written')
    for p in (csv_path, md_path, js_path): result.add_created(_rel(root, p))
    result.notes.append(f'Scanned {len(rows)} HitDefs.')
    return result


def write_combo_trial_pack(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    commands = _all_commands(root)
    states = _all_states(root)
    command_names = [str(c['name']) for c in commands]
    low_normals = [n for n in command_names if any(k in n.lower() for k in ('light', 'jab', 'crouch', 'low'))]
    mids = [n for n in command_names if any(k in n.lower() for k in ('medium', 'kick', 'punch', 'sweep'))]
    specials = [n for n in command_names if any(k in n.lower() for k in ('fireball', 'upper', 'dragon', 'special', 'rekka', 'slide', 'dive'))]
    supers = [n for n in command_names if any(k in n.lower() for k in ('super', 'level', 'blast', 'beam', 'cinematic'))]
    trials: List[Dict[str, object]] = []
    def add(name: str, seq: Sequence[str], goal: str, difficulty: str) -> None:
        if seq:
            trials.append({'name': name, 'sequence': list(seq), 'goal': goal, 'difficulty': difficulty})
    add('First hit confirm', low_normals[:1] + mids[:1], 'Learn a simple normal-to-normal route.', 'Beginner')
    add('Normal into special', (low_normals[:1] or mids[:1]) + specials[:1], 'Learn to cancel or route into a special.', 'Beginner')
    add('Two-button confirm', low_normals[:1] + mids[:1] + specials[:1], 'Practice basic hit-confirm structure.', 'Beginner')
    add('Special into super idea', specials[:1] + supers[:1], 'Check if the character has a resource-spend route.', 'Intermediate')
    add('Full BnB draft', low_normals[:1] + mids[:1] + specials[:1] + supers[:1], 'A first bread-and-butter draft. Tune manually after playtesting.', 'Intermediate')
    if not trials and states:
        sample_states = [str(s['state']) for s in states[:5]]
        add('State smoke test', sample_states, 'Manually visit these states in debug/testing and confirm they animate safely.', 'Beginner')
    md = ['# Combo Trial Pack', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
          'These are generated practice/training ideas. They are not proof that the combo works in-engine yet.', '']
    if trials:
        for idx, t in enumerate(trials, start=1):
            md += [f"## Trial {idx}: {t['name']}", '', f"Difficulty: **{t['difficulty']}**", '', f"Goal: {t['goal']}", '', 'Sequence:', '']
            md += [f"{i}. `{step}`" for i, step in enumerate(t['sequence'], start=1)] + ['']
    else:
        md += ['No commands/states were found to build combo trials. Add moves through Feature Bank first.']
    md += ['## Suggested testing checklist', '',
           '- Does each hit connect at expected range?',
           '- Does the target recover too early or too late?',
           '- Does damage feel appropriate compared with meter/risk?',
           '- Is there a clear visual/sound cue for every important hit?',
           '- Does the route still work in the corner and midscreen?']
    md_path = _write(out / 'COMBO_TRIALS.md', '\n'.join(md))
    js_path = _write_json(out / 'COMBO_TRIALS.json', trials)
    csv_path = out / 'COMBO_TRIALS.csv'
    trial_rows = [
        {'name': t['name'], 'difficulty': t['difficulty'], 'goal': t['goal'], 'sequence': ' > '.join(t['sequence'])}
        for t in trials
    ]
    _write_csv(csv_path, trial_rows, ['name', 'difficulty', 'goal', 'sequence'])
    result = CreatorHubResult('Combo Trial Pack written')
    for p in (md_path, js_path, csv_path): result.add_created(_rel(root, p))
    result.notes.append(f'Generated {len(trials)} draft combo/training trials.')
    return result


def write_asset_request_pack(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    matrix = build_reference_matrix(root)
    actions = []
    air_path = find_character_file(root, 'air')
    if air_path and air_path.exists():
        actions = parse_air(read_text_safely(air_path))
    sprite_requests = []
    for a in actions:
        label = COMMON_ANIMS.get(a.number, a.label or '')
        refs = uniq(f'{fr.group},{fr.image}' for fr in a.frames)
        sprite_requests.append({'action': a.number, 'label': label, 'frames': len(a.frames), 'ticks': sum(max(0, f.ticks) for f in a.frames), 'sprite_refs': refs})
    sound_refs = []
    for rel, text in _read_code_texts(root).items():
        for m in re.finditer(r'PlaySnd\b.*?(?:\n.*?value\s*=\s*([^\n;]+))', text, re.I | re.S):
            sound_refs.append({'file': rel, 'value': m.group(1).strip()})
    sprite_csv = out / 'SPRITE_REQUESTS.csv'
    sprite_rows = [{**r, 'sprite_refs': '; '.join(r['sprite_refs'])} for r in sprite_requests]
    _write_csv(sprite_csv, sprite_rows, ['action', 'label', 'frames', 'ticks', 'sprite_refs'])
    sound_csv = out / 'SOUND_REQUESTS.csv'
    sound_rows = []
    for r in sound_refs:
        nums = re.findall(r'-?\d+', r['value'])
        suggested = f"sound_{nums[0]}_{nums[1]}.wav" if len(nums) >= 2 else 'sound_group_index.wav'
        sound_rows.append({'file': r['file'], 'value': r['value'], 'suggested_filename': suggested})
    _write_csv(sound_csv, sound_rows, ['file', 'value', 'suggested_filename'])
    md = ['# Asset Request Pack', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
          'Give this to an artist/sound designer or use it yourself as the replacement checklist.', '',
          '## Sprite/animation requests', '', '| AIR action | Label | Frames | Ticks | Sprite refs |', '|---:|---|---:|---:|---|']
    for r in sprite_requests:
        md.append(f"| {r['action']} | {r['label']} | {r['frames']} | {r['ticks']} | {'; '.join(r['sprite_refs'])} |")
    md += ['', '## Sound requests', '', '| Source file | PlaySnd value | Suggested WAV filename |', '|---|---|---|']
    for r in sound_refs:
        nums = re.findall(r'-?\d+', r['value'])
        suggested = f"sound_{nums[0]}_{nums[1]}.wav" if len(nums) >= 2 else 'sound_group_index.wav'
        md.append(f"| {r['file']} | `{r['value']}` | `{suggested}` |")
    md += ['', '## Missing reference notes', '']
    sprites = matrix.get('sprites', {}) or {}
    sounds = matrix.get('sounds', {}) or {}
    for ref in sprites.get('missing_air_sprite_refs', [])[:200] or []:
        md.append(f'- Missing sprite used by AIR: `{ref}`')
    for ref in sounds.get('missing_playsnd_refs', [])[:200] or []:
        md.append(f'- Missing PlaySnd reference: `{ref}`')
    md_path = _write(out / 'ASSET_REQUEST_PACK.md', '\n'.join(md))
    js_path = _write_json(out / 'ASSET_REQUEST_PACK.json', {'sprites': sprite_requests, 'sounds': sound_refs})
    result = CreatorHubResult('Asset Request Pack written')
    for p in (sprite_csv, sound_csv, md_path, js_path): result.add_created(_rel(root, p))
    result.notes.append(f'Generated {len(sprite_requests)} animation requests and {len(sound_refs)} sound requests.')
    return result


def write_no_code_recipe_book(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    presets = available_presets()
    kits = kit_names()
    categories: Dict[str, List[str]] = {}
    for p in presets:
        categories.setdefault(p.category, []).append(p.name)
    md = ['# No-Code Recipe Book', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
          feature_bank_stats_text(), '',
          'This file is the “bank of code” map for non-coders. Pick recipes/kits in the app; MugenForge writes the CMD/CNS/AIR blocks and backs up files.', '',
          '## Beginner routes', '',
          '### Make a playable first character', '',
          '1. Run Auto Setup / Repair Project.',
          '2. Install `Starter Beginner Pack` or `Balanced Full Character Kit`.',
          '3. Run Factory Max or Quality Lab one-click pass.',
          '4. Replace placeholder art/sounds through Sprite Lab/Sound workflows.', '',
          '### Make it feel more complete', '',
          '1. Add one movement kit, one defense kit, and one archetype kit.',
          '2. Run Input Conflict Lab.',
          '3. Run Balance Autotune Plan.',
          '4. Generate Combo Trials and test them in M.U.G.E.N.', '',
          '## Available kits', '']
    for kit in kits:
        md += [f'### {kit}', '', kit_preview_text(kit), '']
    md += ['## Presets by category', '']
    for cat, names in sorted(categories.items()):
        md += [f'### {cat}', ''] + [f'- {name}' for name in names] + ['']
    md_path = _write(out / 'NO_CODE_RECIPES.md', '\n'.join(md))
    js_path = _write_json(out / 'NO_CODE_RECIPE_INDEX.json', {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'preset_count': len(presets),
        'kit_count': len(kits),
        'kits': kits,
        'categories': categories,
    })
    result = CreatorHubResult('No-Code Recipe Book written')
    for p in (md_path, js_path): result.add_created(_rel(root, p))
    result.notes.append(f'Documented {len(presets)} presets and {len(kits)} kits.')
    return result


def write_controller_mapping_sheet(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    commands = _all_commands(root)
    groups = {'basic': [], 'movement': [], 'special': [], 'super': [], 'defense': [], 'other': []}
    for c in commands:
        name = str(c['name']).lower()
        bucket = 'other'
        if any(k in name for k in ('dash', 'jump', 'run', 'walk', 'roll', 'teleport')):
            bucket = 'movement'
        elif any(k in name for k in ('super', 'level', 'hyper', 'cinematic')):
            bucket = 'super'
        elif any(k in name for k in ('guard', 'parry', 'counter', 'burst', 'reflect', 'block')):
            bucket = 'defense'
        elif any(k in name for k in ('fireball', 'upper', 'special', 'rekka', 'projectile', 'dive')):
            bucket = 'special'
        elif any(k in name for k in ('punch', 'kick', 'light', 'medium', 'heavy', 'jab', 'sweep')):
            bucket = 'basic'
        groups[bucket].append(c)
    md = ['# Controller Mapping Sheet', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '',
          'Use this to make sure a beginner can understand the controls without reading CMD code.', '']
    for bucket, rows in groups.items():
        md += [f'## {bucket.title()}', '', '| Move/command | Input | Difficulty | Notes |', '|---|---|---|---|']
        if rows:
            for r in rows:
                md.append(f"| {r['name']} | `{r['command']}` | {_difficulty_for_input(str(r['command']), r.get('time'))} | time={r.get('time','')} buffer={r.get('buffer_time','')} |")
        else:
            md.append('| — | — | — | No commands detected in this bucket. |')
        md.append('')
    md_path = _write(out / 'CONTROLLER_MAPPING_SHEET.md', '\n'.join(md))
    csv_path = out / 'CONTROLLER_MAPPING_SHEET.csv'
    mapping_rows = []
    for bucket, rows in groups.items():
        for r in rows:
            mapping_rows.append({'bucket': bucket, 'name': r['name'], 'input': r['command'], 'difficulty': _difficulty_for_input(str(r['command']), r.get('time')), 'time': r.get('time',''), 'buffer_time': r.get('buffer_time',''), 'file': r.get('file','')})
    _write_csv(csv_path, mapping_rows, ['bucket', 'name', 'input', 'difficulty', 'time', 'buffer_time', 'file'])
    result = CreatorHubResult('Controller Mapping Sheet written')
    for p in (md_path, csv_path): result.add_created(_rel(root, p))
    result.notes.append(f'Mapped {len(commands)} commands into beginner-friendly buckets.')
    return result


def write_release_website(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root) / 'release_site'
    out.mkdir(parents=True, exist_ok=True)
    matrix = build_reference_matrix(root)
    score, reasons = _matrix_score(matrix)
    commands = _all_commands(root)
    hitdefs = _parse_hitdefs(root)
    command_cards = ''.join(f"<li><b>{html.escape(str(c['name']))}</b> — <code>{html.escape(str(c['command']))}</code></li>" for c in commands[:80]) or '<li>No commands documented yet.</li>'
    move_cards = ''.join(f"<tr><td>{html.escape(str(h.get('state','')))}</td><td>{html.escape(str(h.get('damage','')))}</td><td>{html.escape(str(h.get('attr','')))}</td><td>{html.escape(str(h.get('recommendation','')))}</td></tr>" for h in hitdefs[:120]) or '<tr><td colspan="4">No HitDefs detected yet.</td></tr>'
    issues = ''.join(f'<li>{html.escape(r)}</li>' for r in reasons) or '<li>No major structural issues detected.</li>'
    html_path = _write(out / 'index.html', f'''<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(root.name)} - MugenForge Release Page</title><style>body{{font-family:Arial,sans-serif;margin:0;background:#151821;color:#f2f2f2}}header{{padding:42px;background:linear-gradient(120deg,#22283a,#343c5a)}}section{{padding:24px;max-width:1100px;margin:auto}}code{{background:#0005;padding:2px 5px;border-radius:4px}}.score{{font-size:46px;font-weight:bold}}table{{border-collapse:collapse;width:100%;background:#fff;color:#222}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#eee}}.cards{{columns:2}}@media(max-width:800px){{.cards{{columns:1}}}}</style></head><body><header><h1>{html.escape(root.name)}</h1><p>Generated MugenForge release info page.</p><div class="score">{score}/100</div><p>Readiness: {html.escape(_score_badge(score))}</p></header><section><h2>Known release tasks</h2><ul>{issues}</ul></section><section><h2>Command list</h2><ul class="cards">{command_cards}</ul></section><section><h2>Move balance snapshot</h2><table><tr><th>State</th><th>Damage</th><th>Attr</th><th>Recommendation</th></tr>{move_cards}</table></section><section><h2>Creator notes</h2><p>Replace this text with screenshots, credits, installation notes, and gameplay description before release.</p></section></body></html>''')
    readme_path = _write(out / 'README_RELEASE_SITE.md', '# Release Website\n\nOpen `index.html` in a browser. Replace placeholder text with screenshots, credits, install notes, and a real move list before publishing.\n')
    result = CreatorHubResult('Release Website written')
    for p in (html_path, readme_path): result.add_created(_rel(root, p))
    result.notes.append('Created a local HTML release page scaffold.')
    return result


def write_patch_macro_bank(root: Path) -> CreatorHubResult:
    root = Path(root)
    out = _hub_dir(root)
    macros = [
        {'name': 'Add beginner debug overlay', 'safe': True, 'writes': ['CNS State -2 DisplayToClipboard'], 'user_choice': 'Enable only while testing.'},
        {'name': 'Add missing command', 'safe': True, 'writes': ['CMD [Command]', 'Statedef -1 route'], 'user_choice': 'Pick input and target state.'},
        {'name': 'Create attack move', 'safe': True, 'writes': ['CMD', 'CNS StateDef', 'AIR action', 'CLSN boxes'], 'user_choice': 'Move name, damage, frames, hitbox.'},
        {'name': 'Create projectile move', 'safe': True, 'writes': ['CMD', 'CNS Projectile controller', 'AIR action'], 'user_choice': 'Input, speed, damage, sprite group.'},
        {'name': 'Repair missing AIR action', 'safe': True, 'writes': ['AIR placeholder action'], 'user_choice': 'Animation number and frame count.'},
        {'name': 'Generate placeholder SFF', 'safe': True, 'writes': ['SFF v1 from AIR refs'], 'user_choice': 'Use placeholders until final art is ready.'},
        {'name': 'Build SND placeholder bank', 'safe': True, 'writes': ['WAV placeholders', 'SND bank'], 'user_choice': 'Replace WAVs later.'},
        {'name': 'Run release QA pass', 'safe': True, 'writes': ['reports only'], 'user_choice': 'Review high-priority cards.'},
    ]
    js_path = _write_json(out / 'PATCH_MACRO_BANK.json', macros)
    md = ['# Patch Macro Bank', '', 'This is the non-coder action library concept: each macro explains what the app will change behind the scenes.', '', '| Macro | Safe? | Writes | User handles |', '|---|---|---|---|']
    for m in macros:
        md.append(f"| {m['name']} | {m['safe']} | {', '.join(m['writes'])} | {m['user_choice']} |")
    md_path = _write(out / 'PATCH_MACRO_BANK.md', '\n'.join(md))
    result = CreatorHubResult('Patch Macro Bank written')
    for p in (js_path, md_path): result.add_created(_rel(root, p))
    result.notes.append('Documented safe high-level patch macros for non-coders.')
    return result


def run_creator_hub_pass(root: Path) -> CreatorHubResult:
    root = Path(root)
    result = CreatorHubResult('One-Click Creator Hub Pass')
    for label, func in [
        ('dashboard', write_creator_dashboard),
        ('task board', write_project_task_board),
        ('input lab', write_input_conflict_lab),
        ('balance plan', write_balance_autotune_plan),
        ('combo trials', write_combo_trial_pack),
        ('asset request pack', write_asset_request_pack),
        ('recipe book', write_no_code_recipe_book),
        ('controller map', write_controller_mapping_sheet),
        ('release website', write_release_website),
        ('patch macro bank', write_patch_macro_bank),
    ]:
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    result.notes.append('Creator Hub generated planning, QA, training, controls, asset handoff, and release-site files without touching core gameplay files.')
    return result
