from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .parsers import parse_def, read_text_safely, write_text_safely


@dataclass
class MoveWizardSpec:
    move_name: str = 'Light Punch'
    command_name: str = 'light_punch'
    command_input: str = 'x'
    command_time: int = 12
    state_no: int = 200
    anim_no: int = 200
    sprite_group: int = 200
    start_image: int = 0
    frame_count: int = 4
    ticks: int = 4
    hit_frame: int = 2
    damage: int = 35
    hit_x1: int = 18
    hit_y1: int = -72
    hit_x2: int = 58
    hit_y2: int = -36
    body_x1: int = -18
    body_y1: int = -88
    body_x2: int = 18
    body_y2: int = 0
    sound_group: int = 5
    sound_index: int = 0
    sparkno: int = 2
    guard_sparkno: int = 40
    ground_velocity_x: float = -3.0
    ground_velocity_y: float = 0.0
    air_velocity_x: float = -2.0
    air_velocity_y: float = -4.0
    move_type: str = 'attack'  # attack, projectile, movement


@dataclass
class MoveWizardPackage:
    cmd_block: str
    cns_block: str
    air_block: str
    summary: str


def _safe_int(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def normalize_spec(**kwargs) -> MoveWizardSpec:
    base = MoveWizardSpec()
    data = base.__dict__.copy()
    for key, value in kwargs.items():
        if key not in data:
            continue
        if isinstance(data[key], int):
            data[key] = _safe_int(value, data[key])
        elif isinstance(data[key], float):
            try:
                data[key] = float(str(value).strip())
            except Exception:
                pass
        else:
            data[key] = str(value).strip() or data[key]
    data['frame_count'] = max(1, int(data['frame_count']))
    data['hit_frame'] = max(1, min(int(data['hit_frame']), int(data['frame_count'])))
    data['ticks'] = max(1, int(data['ticks']))
    return MoveWizardSpec(**data)


def command_block(spec: MoveWizardSpec) -> str:
    return f'''; MugenForge Move Wizard: {spec.move_name}
[Command]
name = "{spec.command_name}"
command = {spec.command_input}
time = {spec.command_time}
buffer.time = 4

[State -1, {spec.move_name}]
type = ChangeState
value = {spec.state_no}
triggerall = command = "{spec.command_name}"
triggerall = roundstate = 2
trigger1 = ctrl

'''


def attack_state_block(spec: MoveWizardSpec) -> str:
    return f'''; MugenForge Move Wizard: {spec.move_name}
[Statedef {spec.state_no}]
type = S
movetype = A
physics = S
anim = {spec.anim_no}
ctrl = 0
velset = 0,0
sprpriority = 2

[State {spec.state_no}, PlaySnd]
type = PlaySnd
trigger1 = AnimElem = {spec.hit_frame}
value = {spec.sound_group}, {spec.sound_index}
channel = 0

[State {spec.state_no}, HitDef]
type = HitDef
trigger1 = AnimElem = {spec.hit_frame}
attr = S, NA
hitflag = MAF
guardflag = MA
animtype = Light
air.animtype = Back
damage = {spec.damage}, 5
pausetime = 8, 8
sparkno = {spec.sparkno}
guardsparkno = {spec.guard_sparkno}
hitsound = {spec.sound_group}, {spec.sound_index}
guardsound = 6, 0
ground.type = High
ground.slidetime = 8
ground.hittime = 12
ground.velocity = {spec.ground_velocity_x:g}, {spec.ground_velocity_y:g}
air.velocity = {spec.air_velocity_x:g}, {spec.air_velocity_y:g}

[State {spec.state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def projectile_state_block(spec: MoveWizardSpec) -> str:
    proj_anim = spec.anim_no + 1
    return f'''; MugenForge Move Wizard: {spec.move_name}
[Statedef {spec.state_no}]
type = S
movetype = A
physics = S
anim = {spec.anim_no}
ctrl = 0
velset = 0,0

[State {spec.state_no}, PlaySnd]
type = PlaySnd
trigger1 = AnimElem = {spec.hit_frame}
value = {spec.sound_group}, {spec.sound_index}
channel = 0

[State {spec.state_no}, Projectile]
type = Projectile
trigger1 = AnimElem = {spec.hit_frame}
projanim = {proj_anim}
projhitanim = -1
projremanim = -1
velocity = 6,0
offset = 45,-55
attr = S, SP
hitflag = MAF
guardflag = MA
damage = {spec.damage}, 5
pausetime = 4, 8
sparkno = {spec.sparkno}
guardsparkno = {spec.guard_sparkno}
hitsound = {spec.sound_group}, {spec.sound_index}
guardsound = 6, 0
ground.velocity = {spec.ground_velocity_x:g}, {spec.ground_velocity_y:g}
air.velocity = {spec.air_velocity_x:g}, {spec.air_velocity_y:g}

[State {spec.state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def movement_state_block(spec: MoveWizardSpec) -> str:
    return f'''; MugenForge Move Wizard: {spec.move_name}
[Statedef {spec.state_no}]
type = S
movetype = I
physics = S
anim = {spec.anim_no}
ctrl = 0

[State {spec.state_no}, Step Velocity]
type = VelSet
trigger1 = Time = 0
x = {spec.ground_velocity_x:g}
y = {spec.ground_velocity_y:g}

[State {spec.state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def air_block(spec: MoveWizardSpec) -> str:
    lines = [f'; MugenForge Move Wizard: {spec.move_name}', f'[Begin Action {spec.anim_no}]']
    for idx in range(spec.frame_count):
        frame_no = spec.start_image + idx
        elem = idx + 1
        # Body box on every frame.
        lines.append('Clsn2: 1')
        lines.append(f'  Clsn2[0] = {spec.body_x1},{spec.body_y1},{spec.body_x2},{spec.body_y2}')
        # Hitbox only on the selected active frame.
        if elem == spec.hit_frame and spec.move_type != 'movement':
            lines.append('Clsn1: 1')
            lines.append(f'  Clsn1[0] = {spec.hit_x1},{spec.hit_y1},{spec.hit_x2},{spec.hit_y2}')
        lines.append(f'{spec.sprite_group}, {frame_no}, 0, 0, {spec.ticks}')
    return '\n'.join(lines) + '\n\n'


def build_move_package(spec: MoveWizardSpec) -> MoveWizardPackage:
    if spec.move_type == 'projectile':
        cns = projectile_state_block(spec)
    elif spec.move_type == 'movement':
        cns = movement_state_block(spec)
    else:
        cns = attack_state_block(spec)
    cmd = command_block(spec)
    air = air_block(spec)
    summary = f'''Move Wizard Package: {spec.move_name}

Command: {spec.command_name} = {spec.command_input}
StateDef: {spec.state_no}
Animation: {spec.anim_no}
Sprite range: group {spec.sprite_group}, images {spec.start_image}-{spec.start_image + spec.frame_count - 1}
Frames: {spec.frame_count} at {spec.ticks} ticks each
Active frame: {spec.hit_frame}
Damage: {spec.damage}
Sound: {spec.sound_group}, {spec.sound_index}
Move type: {spec.move_type}

Generated blocks:
- CMD command + Statedef -1 ChangeState wiring
- CNS/ST StateDef logic
- AIR animation action with Clsn2 body boxes and optional Clsn1 attack box
'''
    return MoveWizardPackage(cmd_block=cmd, cns_block=cns, air_block=air, summary=summary)


def find_def_file(root: Path) -> Optional[Path]:
    defs = sorted(root.glob('*.def'))
    return defs[0] if defs else None


def find_character_file(root: Path, kind: str) -> Optional[Path]:
    """Find a main character file by kind. Supported kinds: def, cmd, cns, air, sff, snd."""
    kind = kind.lower().lstrip('.')
    if kind == 'def':
        return find_def_file(root)
    def_path = find_def_file(root)
    if def_path:
        sections = parse_def(read_text_safely(def_path))
        files = sections.get('files')
        if files:
            key_map = {
                'cmd': ['cmd', 'command'],
                'cns': ['cns', 'st', 'common'],
                'air': ['anim', 'air'],
                'sff': ['sprite', 'sff'],
                'snd': ['sound', 'snd'],
            }
            keys = key_map.get(kind, [kind])
            for k, v in files.values.items():
                lk = k.lower()
                if any(token == lk or token in lk for token in keys):
                    candidate = (def_path.parent / v.strip().strip('"')).resolve()
                    if candidate.exists() and candidate.is_file():
                        if kind != 'cns' or candidate.suffix.lower() in {'.cns', '.st'}:
                            return candidate
    patterns = {'cmd': '*.cmd', 'cns': '*.cns', 'air': '*.air', 'sff': '*.sff', 'snd': '*.snd'}
    if kind not in patterns:
        return None
    matches = sorted(root.glob(patterns[kind]))
    if not matches and kind == 'cns':
        matches = sorted(root.glob('*.st'))
    return matches[0] if matches else None


def append_block(path: Path, block: str, make_backup: bool = True) -> None:
    old = read_text_safely(path)
    if make_backup:
        backup = path.with_suffix(path.suffix + '.bak')
        backup.write_text(old, encoding='utf-8', errors='replace')
    glue = '' if old.endswith('\n') else '\n'
    write_text_safely(path, old + glue + '\n' + block)


def append_move_to_project(root: Path, package: MoveWizardPackage) -> list[str]:
    results: list[str] = []
    targets = {
        'cmd': (find_character_file(root, 'cmd'), package.cmd_block),
        'cns': (find_character_file(root, 'cns'), package.cns_block),
        'air': (find_character_file(root, 'air'), package.air_block),
    }
    for kind, (path, block) in targets.items():
        if not path:
            results.append(f'{kind.upper()}: no target file found')
            continue
        append_block(path, block, make_backup=True)
        results.append(f'{kind.upper()}: appended to {path.name} and wrote {path.name}.bak')
    return results
