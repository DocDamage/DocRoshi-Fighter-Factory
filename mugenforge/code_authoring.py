from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile
from typing import Iterable, List, Set

from .parsers import TEXT_EXTS, read_text_safely, parse_code, parse_air

COMMAND_REF_RE = re.compile(r'command\s*=\s*["\']([^"\']+)["\']', re.I)

@dataclass
class CodeAuthoringReport:
    command_names: List[str]
    state_numbers: List[int]
    referenced_commands: List[str]
    missing_command_defs: List[str]
    unreferenced_commands: List[str]
    missing_state_targets: List[int]
    notes: List[str]


def command_template(name: str = 'x', command: str = 'x', time: int = 1, buffer_time: int | None = None) -> str:
    lines = ['[Command]', f'name = "{name}"', f'command = {command}', f'time = {int(time)}']
    if buffer_time is not None:
        lines.append(f'buffer.time = {int(buffer_time)}')
    return '\n'.join(lines) + '\n\n'


def negative_one_changestate_template(command_name: str = 'x', state_no: int = 200, label: str = 'Generated ChangeState') -> str:
    return f'''[State -1, {label}]
type = ChangeState
value = {int(state_no)}
triggerall = command = "{command_name}"
trigger1 = ctrl

'''


def attack_state_template(state_no: int = 200, anim_no: int | None = None, damage: int = 35, sound_group: int = 5, sound_index: int = 0) -> str:
    if anim_no is None:
        anim_no = state_no
    return f'''[Statedef {int(state_no)}]
type = S
movetype = A
physics = S
anim = {int(anim_no)}
ctrl = 0
velset = 0,0

[State {int(state_no)}, HitDef]
type = HitDef
trigger1 = AnimElem = 2
attr = S, NA
damage = {int(damage)}, 5
pausetime = 8, 8
sparkno = 2
hitsound = {int(sound_group)}, {int(sound_index)}
guardsound = 6, 0
ground.type = High
ground.slidetime = 8
ground.hittime = 12
ground.velocity = -3
air.velocity = -2,-4

[State {int(state_no)}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def projectile_state_template(state_no: int = 1000, anim_no: int | None = None, proj_anim: int | None = None, damage: int = 45) -> str:
    if anim_no is None:
        anim_no = state_no
    if proj_anim is None:
        proj_anim = state_no + 1
    return f'''[Statedef {int(state_no)}]
type = S
movetype = A
physics = S
anim = {int(anim_no)}
ctrl = 0

[State {int(state_no)}, Projectile]
type = Projectile
trigger1 = AnimElem = 3
projanim = {int(proj_anim)}
projhitanim = -1
projremanim = -1
projcancelanim = -1
velocity = 6,0
offset = 40,-50
attr = S, SP
damage = {int(damage)}, 5
pausetime = 4, 8
sparkno = 2
hitsound = 5, 0
guardsound = 6, 0
ground.velocity = -4
air.velocity = -2,-4

[State {int(state_no)}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def helper_explod_template(state_no: int = 1200, helper_id: int = 1200, helper_state: int = 1201, explod_anim: int = 1202) -> str:
    return f'''[State {int(state_no)}, Helper]
type = Helper
trigger1 = AnimElem = 2
helpertype = normal
name = "generated_helper"
ID = {int(helper_id)}
stateno = {int(helper_state)}
pos = 25,-45
postype = p1
ownpal = 1

[State {int(state_no)}, Explod]
type = Explod
trigger1 = AnimElem = 2
anim = {int(explod_anim)}
ID = {int(explod_anim)}
pos = 25,-45
postype = p1
bindtime = 1
removetime = -2
ownpal = 1

'''


def inspect_code_text(text: str) -> CodeAuthoringReport:
    scan = parse_code(text)
    command_names: Set[str] = {c.name for c in scan.commands}
    state_numbers: Set[int] = {s.number for s in scan.states}
    referenced_commands: Set[str] = set(COMMAND_REF_RE.findall(text))
    missing_command_defs = sorted(referenced_commands - command_names)
    unreferenced_commands = sorted(command_names - referenced_commands)
    missing_state_targets: Set[int] = set()
    for ctrl in scan.controllers:
        if ctrl.values.get('type', '').lower() == 'changestate':
            raw = ctrl.values.get('value', '')
            try:
                target = int(raw)
            except ValueError:
                continue
            # Negative common states and 0 are engine/common-state safe enough to ignore.
            if target > 0 and target not in state_numbers:
                missing_state_targets.add(target)
    notes: List[str] = []
    notes.extend(scan.issues)
    if not scan.commands and '[command]' in text.lower():
        notes.append('Command sections were detected but no named commands parsed.')
    if not scan.states and '[statedef' in text.lower():
        notes.append('StateDef sections were detected but no state numbers parsed.')
    return CodeAuthoringReport(
        command_names=sorted(command_names),
        state_numbers=sorted(state_numbers),
        referenced_commands=sorted(referenced_commands),
        missing_command_defs=missing_command_defs,
        unreferenced_commands=unreferenced_commands,
        missing_state_targets=sorted(missing_state_targets),
        notes=notes,
    )


def inspect_character_folder(root: Path) -> str:
    lines = [f'Code authoring scan: {root}', '']
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix.lower() in {'.cmd', '.cns', '.st'}:
            report = inspect_code_text(read_text_safely(path))
            rel = path.relative_to(root)
            lines.append(f'## {rel}')
            lines.append(f'- Commands: {len(report.command_names)}')
            lines.append(f'- StateDefs: {len(report.state_numbers)}')
            if report.missing_command_defs:
                lines.append('- Missing command definitions: ' + ', '.join(report.missing_command_defs))
            if report.unreferenced_commands:
                lines.append('- Defined but not referenced: ' + ', '.join(report.unreferenced_commands[:40]))
            if report.missing_state_targets:
                lines.append('- ChangeState targets without local StateDef: ' + ', '.join(map(str, report.missing_state_targets[:40])))
            if report.notes:
                lines.append('- Notes:')
                for note in report.notes[:30]:
                    lines.append(f'  - {note}')
            lines.append('')
    return '\n'.join(lines).strip() + '\n'


def package_character_zip(root: Path, out_zip: Path, include_backups: bool = False) -> int:
    skipped_names = {'__pycache__', '.git', '.svn', '.hg'}
    count = 0
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob('*')):
            if any(part in skipped_names for part in path.parts):
                continue
            if path.is_dir():
                continue
            if not include_backups and (path.suffix.lower() in {'.bak', '.tmp'} or path.name.endswith('~')):
                continue
            arc = Path(root.name) / path.relative_to(root)
            zf.write(path, arc.as_posix())
            count += 1
    return count
