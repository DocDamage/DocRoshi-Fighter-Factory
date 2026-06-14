from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
    sha256_file,
    timestamp as _now,
)
from .parsers import COMMON_ANIMS, parse_air, parse_code, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd
from .shared_utils import BaseResult, uniq, rel_path as _rel, get_code_files

OPERATOR_CONSOLE_VERSION = "7.5.0"
TEXT_EXTS = {'.def', '.air', '.cmd', '.cns', '.st', '.txt', '.md', '.json', '.ini', '.cfg', '.csv', '.log'}
SKIP_PARTS = {'__pycache__', '.git', '.hg', '.svn'}


@dataclass
class OperatorResult(BaseResult):
    title: str = 'Operator Console'


def _console_dir(root: Path) -> Path:
    out = Path(root) / 'operator_console'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(root: Path, path: Path, text: str, result: Optional[OperatorResult] = None, *, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, track_existing=True, writer=write_text_safely)


def _write_json(root: Path, path: Path, data: object, result: Optional[OperatorResult] = None) -> Path:
    return write_json_artifact(path, data, result, root, track_existing=True)


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], result: Optional[OperatorResult] = None) -> Path:
    return write_csv_artifact(path, rows, fields, result, root, track_existing=True)


def _file_sha256(path: Path) -> str:
    return sha256_file(path)


def _all_project_files(root: Path) -> List[Path]:
    return [
        p for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower())
        if p.is_file() and not any(part in SKIP_PARTS for part in p.parts)
    ]


def _safe_read(path: Path) -> str:
    try:
        return read_text_safely(path)
    except Exception:
        return ''


def _discover_main_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    for kind in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        try:
            out[kind] = find_character_file(root, kind)
        except Exception:
            out[kind] = None
    if out.get('def') is None:
        defs = sorted(root.glob('*.def'), key=lambda p: p.name.lower())
        out['def'] = defs[0] if defs else None
    if out.get('cns') is None:
        sts = sorted(root.rglob('*.st'), key=lambda p: str(p).lower())
        out['cns'] = sts[0] if sts else None
    return out


def _project_counts(root: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in _all_project_files(root):
        key = p.suffix.lower() or '[none]'
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))


def _code_files(root: Path) -> List[Path]:
    return get_code_files(root)


def _text_files(root: Path) -> List[Path]:
    return [p for p in _all_project_files(root) if p.suffix.lower() in TEXT_EXTS]


def _existing_report_dirs(root: Path) -> Dict[str, Dict[str, object]]:
    names = [
        'creator_hub', 'creator_os', 'creator_suite', 'quality_lab', 'rescue_lab', 'visual_forge', 'forge_beyond',
        'forge_polish', 'forge_timeline', 'binary_core', 'binary_deep', 'binary_maturity', 'runtime_lab',
        'closure_lab', 'gap_closer', 'authority_core', 'authority_lab', 'evidence_core', 'operator_console',
        'reports', 'docs', 'release', 'exports', 'testing', 'screenshots', 'staged_sprites', 'source_sprites',
    ]
    out: Dict[str, Dict[str, object]] = {}
    for name in names:
        path = root / name
        if not path.exists():
            continue
        files = [p for p in path.rglob('*') if p.is_file()]
        out[name] = {
            'path': str(path),
            'file_count': len(files),
            'total_bytes': sum(p.stat().st_size for p in files if p.exists()),
            'latest_mtime': max((p.stat().st_mtime for p in files if p.exists()), default=path.stat().st_mtime),
        }
    return out


def inspect_project_state(root: Path) -> Dict[str, object]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    files = _discover_main_files(root)
    counts = _project_counts(root)
    try:
        audit = scan_project(root)
    except Exception:
        audit = None

    air_actions: List[int] = []
    missing_common_actions: List[str] = []
    air_frame_count = 0
    air_path = files.get('air')
    if air_path and air_path.exists():
        try:
            actions = parse_air(read_text_safely(air_path))
            air_actions = sorted(a.number for a in actions)
            air_frame_count = sum(len(a.frames) for a in actions)
            existing = set(air_actions)
            missing_common_actions = [f'{num} {COMMON_ANIMS[num]}' for num in COMMON_ANIMS if num not in existing]
        except Exception as exc:
            missing_common_actions = [f'AIR parse failed: {exc}']

    state_numbers: List[int] = []
    command_names: List[str] = []
    hitdef_count = 0
    changestate_targets: List[int] = []
    code_issues: List[str] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
            command_names.extend(c.name for c in scan.commands if c.name)
            state_numbers.extend(st.number for st in scan.states)
            code_issues.extend(scan.issues or [])
            for st in scan.states:
                for ctrl in st.controllers:
                    stype = (ctrl.stype or ctrl.values.get('type', '')).lower()
                    if stype == 'hitdef':
                        hitdef_count += 1
                    if stype in {'changestate', 'selfstate'}:
                        val = ctrl.values.get('value', '')
                        if re.fullmatch(r'\s*-?\d+\s*', val or ''):
                            changestate_targets.append(int(str(val).strip()))
        except Exception as exc:
            code_issues.append(f'{_rel(root, path)} parse failed: {exc}')
    state_numbers = sorted(set(state_numbers))
    command_names = sorted(set(command_names))
    missing_state_targets = sorted({n for n in changestate_targets if n not in set(state_numbers) and n >= 0})

    sff_summary: Dict[str, object] = {'present': False}
    sff_path = files.get('sff')
    if sff_path and sff_path.exists():
        try:
            info = read_sff(sff_path)
            sff_summary = {
                'present': True,
                'path': _rel(root, sff_path),
                'version': getattr(info, 'version_text', ''),
                'variant': getattr(info, 'variant', ''),
                'sprite_count': getattr(info, 'sprite_count', len(getattr(info, 'sprites', []) or [])),
                'parsed_sprite_records': len(getattr(info, 'sprites', []) or []),
                'supported_for_extraction': bool(getattr(info, 'is_supported_for_extraction', False)),
                'warnings': list(getattr(info, 'warnings', []) or [])[:20],
            }
        except Exception as exc:
            sff_summary = {'present': True, 'path': _rel(root, sff_path), 'warnings': [f'SFF read failed: {exc}']}

    snd_summary: Dict[str, object] = {'present': False}
    snd_path = files.get('snd')
    if snd_path and snd_path.exists():
        try:
            info = read_snd(snd_path)
            snd_summary = {
                'present': True,
                'path': _rel(root, snd_path),
                'version': getattr(info, 'version_text', ''),
                'sound_count': len(getattr(info, 'sounds', []) or []),
                'declared_count': getattr(info, 'declared_count', None),
                'warnings': list(getattr(info, 'warnings', []) or [])[:20],
            }
        except Exception as exc:
            snd_summary = {'present': True, 'path': _rel(root, snd_path), 'warnings': [f'SND read failed: {exc}']}

    missing_required = []
    if audit is not None:
        missing_required = list(getattr(audit, 'missing_required', []) or [])
    else:
        for ext in ('.def', '.air', '.cmd', '.cns', '.sff', '.snd'):
            if not counts.get(ext):
                missing_required.append(ext)

    report_dirs = _existing_report_dirs(root)
    recent_reports = []
    for name, data in report_dirs.items():
        recent_reports.append({
            'name': name,
            'file_count': data['file_count'],
            'total_bytes': data['total_bytes'],
            'latest_mtime': datetime.fromtimestamp(float(data['latest_mtime'])).isoformat(timespec='seconds'),
        })
    recent_reports.sort(key=lambda row: row['latest_mtime'], reverse=True)

    blocker_count = len(missing_required) + len(missing_state_targets) + max(0, len(missing_common_actions) - 8)
    coverage_score = 100
    coverage_score -= min(35, len(missing_required) * 8)
    coverage_score -= min(25, len(missing_state_targets) * 5)
    coverage_score -= min(20, len(missing_common_actions) // 2)
    if not sff_summary.get('present'):
        coverage_score -= 8
    if not snd_summary.get('present'):
        coverage_score -= 5
    if 'runtime_lab' not in report_dirs and 'evidence_core' not in report_dirs:
        coverage_score -= 8
    coverage_score = max(0, min(100, int(coverage_score)))

    return {
        'tool': 'MugenForge Studio',
        'operator_console_version': OPERATOR_CONSOLE_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'project_root': str(root),
        'project_name': root.name,
        'main_files': {k: (_rel(root, v) if isinstance(v, Path) and v.exists() else '') for k, v in files.items() if k != 'root'},
        'file_counts_by_extension': counts,
        'missing_required': missing_required,
        'air': {'action_count': len(air_actions), 'frame_count': air_frame_count, 'actions': air_actions[:300], 'missing_common_actions': missing_common_actions},
        'code': {
            'command_count': len(command_names),
            'commands': command_names[:300],
            'state_count': len(state_numbers),
            'states': state_numbers[:500],
            'hitdef_count': hitdef_count,
            'missing_state_targets': missing_state_targets[:300],
            'issues': code_issues[:200],
        },
        'sff': sff_summary,
        'snd': snd_summary,
        'report_dirs': report_dirs,
        'recent_report_dirs': recent_reports[:30],
        'blocker_count': blocker_count,
        'operator_score': coverage_score,
    }


def _phase_status(state: Dict[str, object]) -> List[Dict[str, object]]:
    missing_required = list(state.get('missing_required', []) or [])
    air = state.get('air', {}) if isinstance(state.get('air'), dict) else {}
    code = state.get('code', {}) if isinstance(state.get('code'), dict) else {}
    sff = state.get('sff', {}) if isinstance(state.get('sff'), dict) else {}
    snd = state.get('snd', {}) if isinstance(state.get('snd'), dict) else {}
    dirs = state.get('report_dirs', {}) if isinstance(state.get('report_dirs'), dict) else {}
    rows: List[Dict[str, object]] = []

    def add(phase: str, status: str, reason: str, next_action: str) -> None:
        rows.append({'phase': phase, 'status': status, 'reason': reason, 'next_action': next_action})

    add('Project skeleton', 'pass' if not any(ext in missing_required for ext in ('.def', '.air', '.cmd', '.cns')) else 'needs work',
        'DEF/AIR/CMD/CNS are present.' if not any(ext in missing_required for ext in ('.def', '.air', '.cmd', '.cns')) else f'Missing: {", ".join(missing_required)}',
        'Run Project Home / Beginner Wizard or Auto Setup if base files are missing.')
    add('Animation coverage', 'pass' if len(air.get('missing_common_actions', []) or []) <= 6 else 'needs work',
        f"{air.get('action_count', 0)} AIR actions, {len(air.get('missing_common_actions', []) or [])} common actions missing.",
        'Use Factory+ Required Animation Repair or Visual Timeline to fill/replace placeholder actions.')
    add('Move logic', 'pass' if int(code.get('hitdef_count', 0) or 0) > 0 else 'needs work',
        f"{code.get('state_count', 0)} StateDefs, {code.get('command_count', 0)} commands, {code.get('hitdef_count', 0)} HitDefs.",
        'Use Move Composer 2.0 / Forge Timeline to author and tune moves.')
    add('State routing', 'pass' if not code.get('missing_state_targets') else 'needs work',
        'No missing numeric ChangeState/SelfState targets found.' if not code.get('missing_state_targets') else f"Missing targets: {len(code.get('missing_state_targets') or [])}",
        'Use State Graph / Authority Lab to inspect and retarget broken transitions.')
    add('Sprites / SFF', 'pass' if sff.get('present') else 'needs work',
        f"SFF present: {sff.get('path', '')}; variant={sff.get('variant', '')}; records={sff.get('parsed_sprite_records', 0)}" if sff.get('present') else 'No SFF file detected.',
        'Use Binary Maturity for existing SFF2, or Sheet Import / SFF2 Bridge for source images.')
    add('Sounds / SND', 'pass' if snd.get('present') else 'needs work',
        f"SND present: {snd.get('path', '')}; sounds={snd.get('sound_count', 0)}" if snd.get('present') else 'No SND file detected.',
        'Use Sound Cue Editor, Binary Core SND sheets, or source WAV rebuild workflow.')
    add('Runtime evidence', 'pass' if ('runtime_lab' in dirs or 'evidence_core' in dirs) else 'not started',
        'Runtime/evidence artifacts exist.' if ('runtime_lab' in dirs or 'evidence_core' in dirs) else 'No runtime/evidence artifacts found yet.',
        'Run Runtime Lab or Evidence Core with your local M.U.G.E.N/IKEMEN executable.')
    add('Release packaging', 'pass' if ('release' in dirs or 'exports' in dirs) else 'not started',
        'Release/export artifacts exist.' if ('release' in dirs or 'exports' in dirs) else 'No release/export artifacts found yet.',
        'Run Release ZIP / Evidence Bundle / Operator Context Bundle near ship time.')
    return rows


def _markdown_table(rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> List[str]:
    if not rows:
        return []
    lines = ['| ' + ' | '.join(fields) + ' |', '| ' + ' | '.join('---' for _ in fields) + ' |']
    for row in rows:
        vals = []
        for field in fields:
            val = str(row.get(field, '')).replace('\n', ' ').replace('|', '\\|')
            vals.append(val)
        lines.append('| ' + ' | '.join(vals) + ' |')
    return lines


def write_operator_dashboard(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Operator Console Dashboard')
    state = inspect_project_state(root)
    out = _console_dir(root)
    _write_json(root, out / 'operator_project_state.json', state, result)
    phase_rows = _phase_status(state)
    _write_csv(root, out / 'operator_phase_status.csv', phase_rows, ['phase', 'status', 'reason', 'next_action'], result)

    lines = [
        '# MugenForge Operator Dashboard',
        '',
        f"Project: `{state.get('project_name', '')}`",
        f"Generated: `{state.get('generated_at', '')}`",
        f"Operator score: **{state.get('operator_score', 0)}/100**",
        f"Blocker count: **{state.get('blocker_count', 0)}**",
        '',
        '## Current project files',
        '',
    ]
    main_files = state.get('main_files', {}) if isinstance(state.get('main_files'), dict) else {}
    for key in ('def', 'air', 'cmd', 'cns', 'sff', 'snd'):
        lines.append(f"- `{key}`: `{main_files.get(key, '') or 'missing'}`")
    lines += ['', '## Phase status', ''] + _markdown_table(phase_rows, ['phase', 'status', 'reason', 'next_action'])

    air = state.get('air', {}) if isinstance(state.get('air'), dict) else {}
    code = state.get('code', {}) if isinstance(state.get('code'), dict) else {}
    lines += [
        '', '## Counts', '',
        f"- AIR actions: {air.get('action_count', 0)}",
        f"- AIR frames: {air.get('frame_count', 0)}",
        f"- Commands: {code.get('command_count', 0)}",
        f"- StateDefs: {code.get('state_count', 0)}",
        f"- HitDefs: {code.get('hitdef_count', 0)}",
        '', '## Recommended next buttons', '',
        '1. **Operator Console → One-Click Operator Pass** to refresh this dashboard and handoff bundle.',
        '2. **Forge Timeline → One-Click Timeline Pass** when tuning moves, CLSN, HitDefs, palettes, and stage preview.',
        '3. **Binary Maturity / Evidence Core** for SFF/SND candidate validation and runtime-backed promotion.',
        '4. **Runtime Lab / Authority Lab** before release to collect external-engine evidence.',
    ]
    missing_common = air.get('missing_common_actions', []) or []
    if missing_common:
        lines += ['', '## Missing common AIR actions', ''] + [f'- {x}' for x in missing_common[:80]]
    missing_targets = code.get('missing_state_targets', []) or []
    if missing_targets:
        lines += ['', '## Missing numeric state targets', ''] + [f'- {x}' for x in missing_targets[:120]]
    recent = state.get('recent_report_dirs', []) or []
    if recent:
        lines += ['', '## Recent generated workspaces', ''] + _markdown_table(recent[:20], ['name', 'file_count', 'latest_mtime'])
    lines += [
        '', '## Honest scope', '',
        '- Operator Console consolidates project state and next steps. It does not replace engine testing.',
        '- Binary and runtime tools remain candidate/backup/evidence first. Review generated sheets before applying edits.',
    ]
    _write(root, out / 'OPERATOR_DASHBOARD.md', '\n'.join(lines), result)
    result.add_note('Dashboard, JSON state, and phase CSV were refreshed.')
    return result


def write_next_chat_handoff(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Next Chat Handoff')
    state = inspect_project_state(root)
    out = _console_dir(root)
    phase_rows = _phase_status(state)
    prompt = f"""You are continuing development/testing for a MugenForge project using **MugenForge Studio v{OPERATOR_CONSOLE_VERSION} Operator Console**.

Project folder to open:

```text
{root}
```

Run the app with:

```bash
python -m mugenforge.app
```

Start in **Operator Console**. First open `operator_console/OPERATOR_DASHBOARD.md`, then refresh **One-Click Operator Pass**. Use the phase table below to decide whether to work in Forge Timeline, Binary Maturity, Runtime Lab, Authority Lab, or Evidence Core.

Current state summary:

- Operator score: {state.get('operator_score', 0)}/100
- Blocker count: {state.get('blocker_count', 0)}
- AIR actions: {(state.get('air') or {}).get('action_count', 0) if isinstance(state.get('air'), dict) else 0}
- StateDefs: {(state.get('code') or {}).get('state_count', 0) if isinstance(state.get('code'), dict) else 0}
- Commands: {(state.get('code') or {}).get('command_count', 0) if isinstance(state.get('code'), dict) else 0}
- HitDefs: {(state.get('code') or {}).get('hitdef_count', 0) if isinstance(state.get('code'), dict) else 0}
- SFF: {((state.get('sff') or {}).get('path', 'missing') if isinstance(state.get('sff'), dict) else 'missing')}
- SND: {((state.get('snd') or {}).get('path', 'missing') if isinstance(state.get('snd'), dict) else 'missing')}

Phase table:

"""
    prompt += '\n'.join(_markdown_table(phase_rows, ['phase', 'status', 'reason', 'next_action']))
    prompt += """

Clean-room guardrails:

- Do not use or copy Fighter Factory / VirtualTek source, assets, or proprietary logic.
- Keep binary work honest; unsupported/corrupt/custom binaries should be triaged and preserved, not guessed.
- Candidate builds and mutation flows should write backups and verification reports before install.
- Runtime authority comes from the user-configured external M.U.G.E.N/IKEMEN executable and collected evidence.

Suggested next release direction:

1. Keep improving Operator Console as the front door so beginners do not have to understand all historical tabs.
2. Add real project corpus tests for SFF2/SND variants and keep unsupported cases visible.
3. Continue turning sheet/report workflows into direct visual canvas workflows, especially timeline, graph, palettes, and stage.
4. Build installer/distribution polish only after the evidence/corpus loop is stable.
"""
    _write(root, out / 'NEXT_CHAT_HANDOFF.md', prompt, result)
    _write(root, out / 'RESUME_PROMPT.txt', prompt, result)
    result.add_note('Next-chat prompt and handoff were written for context handoff.')
    return result


def write_operator_roadmap(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Operator Roadmap')
    state = inspect_project_state(root)
    out = _console_dir(root)
    phase_rows = _phase_status(state)
    tasks: List[Dict[str, object]] = []

    priority = 1
    for row in phase_rows:
        if row['status'] != 'pass':
            tasks.append({
                'priority': priority,
                'area': row['phase'],
                'status': row['status'],
                'task': row['next_action'],
                'why': row['reason'],
            })
            priority += 1
    evergreen = [
        ('Corpus validation', 'Expand real-world SFF2/SND test corpus and record supported/unsupported buckets.'),
        ('Visual timeline depth', 'Collapse move timing, CLSN, HitDef, sounds, helpers, projectiles, and velocity into one primary timeline surface.'),
        ('Stage maturity', 'Convert stage preview/report workflow into direct BG element and camera/bounds canvas editing.'),
        ('Installer polish', 'Add Windows packaging only after binary/runtime evidence loops are reliable.'),
        ('Docs/tutorials', 'Write beginner tutorials around Operator Console instead of individual historical tabs.'),
    ]
    for area, task in evergreen:
        tasks.append({'priority': priority, 'area': area, 'status': 'backlog', 'task': task, 'why': 'Long-term product maturity'})
        priority += 1
    _write_csv(root, out / 'operator_roadmap.csv', tasks, ['priority', 'area', 'status', 'task', 'why'], result)
    lines = ['# MugenForge Operator Roadmap', '', 'This roadmap is generated from the current project state plus the standing product backlog.', '']
    lines += _markdown_table(tasks, ['priority', 'area', 'status', 'task', 'why'])
    _write(root, out / 'OPERATOR_ROADMAP.md', '\n'.join(lines), result)
    result.add_note('Roadmap was generated from current phase status.')
    return result


def write_decision_log_template(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Decision Log Template')
    out = _console_dir(root)
    path = out / 'DECISION_LOG.md'
    if path.exists():
        result.skipped_files.append(_rel(root, path) + ' already exists; not overwritten.')
        return result
    text = f"""# MugenForge Decision Log

Use this file to preserve intent between long development sessions.

## {datetime.now().date()} — Operator Console baseline

Decision: Continue from MugenForge Studio v{OPERATOR_CONSOLE_VERSION} and use Operator Console as the front door.

Reason: The app has many powerful tabs. The next maturity step is consolidation, not adding more isolated panels.

Consequences:

- Run Operator Console first after opening a project.
- Treat generated dashboards and handoffs as the source of truth for what to do next.
- Keep binary edits candidate/backup/evidence-first.
- Keep final runtime authority tied to external M.U.G.E.N/IKEMEN evidence.
"""
    _write(root, path, text, result)
    return result


def build_operator_context_bundle(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Operator Context Bundle')
    out = _console_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    write_operator_dashboard(root)
    write_next_chat_handoff(root)
    write_operator_roadmap(root)

    bundle_path = out / f'operator_context_bundle_{_now()}.zip'
    manifest_rows: List[Dict[str, object]] = []
    include_roots = [
        root / 'operator_console', root / 'runtime_lab', root / 'evidence_core', root / 'authority_lab',
        root / 'authority_core', root / 'closure_lab', root / 'gap_closer', root / 'binary_maturity',
        root / 'binary_core', root / 'forge_timeline', root / 'forge_polish', root / 'forge_beyond',
        root / 'visual_forge', root / 'quality_lab', root / 'creator_hub', root / 'creator_suite',
        root / 'docs', root / 'reports', root / 'testing', root / 'release',
    ]
    main_files = _discover_main_files(root)
    include_files: List[Path] = []
    for key in ('def', 'air', 'cmd', 'cns'):
        p = main_files.get(key)
        if p and p.exists():
            include_files.append(p)
    for p in _text_files(root):
        if p.name.upper().startswith(('README', 'CHANGELOG')) or p.name in {'MUGENFORGE_BEGINNER_GUIDE.md', 'MUGENFORGE_CHARACTER_BLUEPRINT.json'}:
            include_files.append(p)
    for base in include_roots:
        if not base.exists():
            continue
        for p in sorted(base.rglob('*'), key=lambda x: str(x).lower()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            include_files.append(p)
    unique_files: List[Path] = []
    seen = set()
    for p in include_files:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen or rp == bundle_path.resolve():
            continue
        seen.add(rp)
        unique_files.append(p)

    with zipfile.ZipFile(bundle_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in unique_files:
            try:
                rel = _rel(root, p)
                zf.write(p, rel)
                stat = p.stat()
                manifest_rows.append({
                    'path': rel,
                    'bytes': stat.st_size,
                    'sha256': _file_sha256(p),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                })
            except Exception as exc:
                result.add_warning(f'Could not bundle {p}: {exc}')
        manifest_text = json.dumps({
            'tool': 'MugenForge Studio',
            'operator_console_version': OPERATOR_CONSOLE_VERSION,
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'project_root': str(root),
            'files': manifest_rows,
        }, indent=2, ensure_ascii=False)
        zf.writestr('operator_context_manifest.json', manifest_text)
    _write_csv(root, out / 'operator_context_manifest.csv', manifest_rows, ['path', 'bytes', 'sha256', 'modified'], result)
    result.add_created(root, bundle_path)
    result.add_note(f'Context bundle contains {len(manifest_rows)} text/report/source files; large binaries are intentionally excluded.')
    return result


def write_release_readiness_packet(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('Operator Release Readiness Packet')
    state = inspect_project_state(root)
    out = _console_dir(root) / 'release_readiness'
    out.mkdir(parents=True, exist_ok=True)
    phases = _phase_status(state)
    blockers = [row for row in phases if row['status'] == 'needs work']
    warnings = [row for row in phases if row['status'] == 'not started']
    packet = {
        'tool': 'MugenForge Studio',
        'operator_console_version': OPERATOR_CONSOLE_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'project': state.get('project_name'),
        'operator_score': state.get('operator_score'),
        'release_recommendation': 'hold' if blockers else ('evidence-needed' if warnings else 'candidate'),
        'blockers': blockers,
        'warnings': warnings,
        'phase_status': phases,
        'honest_scope': [
            'This readiness packet is a management gate, not a M.U.G.E.N/IKEMEN emulator.',
            'Ship decisions should include external-engine logs/screenshots/videos where possible.',
            'Binary candidate installs should be verified with hashes and rollback manifests.',
        ],
    }
    _write_json(root, out / 'release_readiness_packet.json', packet, result)
    lines = [
        '# Operator Release Readiness Packet', '',
        f"Project: `{state.get('project_name')}`",
        f"Generated: `{packet['generated_at']}`",
        f"Recommendation: **{packet['release_recommendation']}**",
        f"Operator score: **{packet['operator_score']}/100**",
        '', '## Blockers', '',
    ]
    if blockers:
        lines += _markdown_table(blockers, ['phase', 'status', 'reason', 'next_action'])
    else:
        lines.append('No blocking phase failures detected by Operator Console.')
    lines += ['', '## Evidence still recommended', '']
    if warnings:
        lines += _markdown_table(warnings, ['phase', 'status', 'reason', 'next_action'])
    else:
        lines.append('No not-started evidence phases detected.')
    lines += ['', '## Full phase table', ''] + _markdown_table(phases, ['phase', 'status', 'reason', 'next_action'])
    _write(root, out / 'RELEASE_READINESS_PACKET.md', '\n'.join(lines), result)
    result.add_note(f"Release recommendation: {packet['release_recommendation']}")
    return result


def run_operator_console_pass(root: Path) -> OperatorResult:
    root = Path(root)
    result = OperatorResult('One-Click Operator Console Pass')
    for label, fn in [
        ('dashboard', write_operator_dashboard),
        ('handoff', write_next_chat_handoff),
        ('roadmap', write_operator_roadmap),
        ('decision log', write_decision_log_template),
        ('release readiness', write_release_readiness_packet),
        ('context bundle', build_operator_context_bundle),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    start = _console_dir(root) / 'OPERATOR_START_HERE.md'
    text = f"""# Operator Start Here

Generated by MugenForge Studio v{OPERATOR_CONSOLE_VERSION} Operator Console.

Open these files in order:

1. `operator_console/OPERATOR_DASHBOARD.md`
2. `operator_console/OPERATOR_ROADMAP.md`
3. `operator_console/release_readiness/RELEASE_READINESS_PACKET.md`
4. `operator_console/NEXT_CHAT_HANDOFF.md`
5. Latest `operator_console/operator_context_bundle_*.zip` when moving to another chat or machine.

Recommended app order:

1. Operator Console
2. Forge Timeline
3. Binary Maturity / Evidence Core
4. Runtime Lab / Authority Lab
5. Release packaging

Honest scope: Operator Console makes project state easier to resume and audit. It does not make static analysis engine-authoritative.
"""
    _write(root, start, text, result)
    return result
