from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
from typing import Dict, List, Tuple, Optional, Iterable

TEXT_EXTS = {'.def', '.air', '.cmd', '.cns', '.st', '.txt', '.ini', '.cfg', '.json', '.md'}
IMAGE_EXTS = {'.png', '.gif', '.ppm', '.pgm'}
CHAR_REQUIRED_EXTS = ['.def', '.air', '.cmd', '.cns', '.sff', '.snd']

COMMON_ANIMS = {
    0: 'standing/idle', 5: 'turn', 10: 'stand to crouch', 11: 'crouch to stand',
    12: 'crouching', 20: 'walk forward', 21: 'walk back', 40: 'jump start',
    41: 'jump neutral', 42: 'jump forward/back', 47: 'jump land', 100: 'run/dash forward',
    105: 'run/dash back', 120: 'guard start', 130: 'stand guard', 140: 'crouch guard',
    150: 'air guard', 5000: 'hit high', 5010: 'hit low', 5020: 'hit crouch',
    5030: 'hit air', 5050: 'fall', 5070: 'fall recovery', 5100: 'lying down',
    5110: 'get up', 5150: 'dead'
}

@dataclass
class DefSection:
    name: str
    values: Dict[str, str] = field(default_factory=dict)
    raw_lines: List[str] = field(default_factory=list)

@dataclass
class AirClsnBox:
    kind: str
    x1: int
    y1: int
    x2: int
    y2: int

@dataclass
class AirFrame:
    group: int
    image: int
    x: int
    y: int
    ticks: int
    flags: str = ''
    clsn: List[AirClsnBox] = field(default_factory=list)

@dataclass
class AirAction:
    number: int
    frames: List[AirFrame] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)
    label: str = ''

@dataclass
class CmdCommand:
    name: str
    command: str
    time: Optional[int]
    buffer_time: Optional[int]
    line: int

@dataclass
class StateController:
    header: str
    stype: str
    line: int
    values: Dict[str, str] = field(default_factory=dict)

@dataclass
class StateDef:
    number: int
    line: int
    values: Dict[str, str] = field(default_factory=dict)
    controllers: List[StateController] = field(default_factory=list)

@dataclass
class CodeScan:
    commands: List[CmdCommand] = field(default_factory=list)
    states: List[StateDef] = field(default_factory=list)
    controllers: List[StateController] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

@dataclass
class ProjectAudit:
    root: Path
    found_exts: Dict[str, int]
    missing_required: List[str]
    text_files: List[Path]
    binary_files: List[Path]
    warnings: List[str]
    def_references: Dict[Path, Dict[str, str]] = field(default_factory=dict)
    missing_references: List[str] = field(default_factory=list)
    code_issues: List[str] = field(default_factory=list)
    asset_issues: List[str] = field(default_factory=list)


def read_text_safely(path: Path) -> str:
    for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode('latin-1', errors='replace')


def write_text_safely(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8', newline='')


def strip_inline_comment(value: str) -> str:
    for char in (';', '#'):
        if char in value:
            value = value.split(char, 1)[0]
    return value.strip()


def parse_def(text: str) -> Dict[str, DefSection]:
    sections: Dict[str, DefSection] = {}
    current: Optional[DefSection] = None
    section_re = re.compile(r'^\s*\[([^\]]+)\]\s*(?:[;#].*)?$')
    kv_re = re.compile(r'^\s*([^;#=]+?)\s*=\s*(.*?)\s*(?:[;#].*)?$')
    for line in text.splitlines():
        m = section_re.match(line)
        if m:
            name = m.group(1).strip()
            current = sections.setdefault(name.lower(), DefSection(name=name))
            current.raw_lines.append(line)
            continue
        if current is not None:
            current.raw_lines.append(line)
            kv = kv_re.match(line)
            if kv:
                current.values[kv.group(1).strip().lower()] = strip_inline_comment(kv.group(2))
    return sections


def parse_air(text: str) -> List[AirAction]:
    actions: List[AirAction] = []
    current: Optional[AirAction] = None
    pending_clsn: List[AirClsnBox] = []
    action_re = re.compile(r'^\s*\[\s*Begin\s+Action\s+(-?\d+)\s*\]\s*(?:[;#]\s*(.*))?$', re.IGNORECASE)
    frame_re = re.compile(r'^\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*(?:,\s*([^;#]+))?')
    clsn_re = re.compile(r'^\s*Clsn([12])\[\s*\d+\s*\]\s*=\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)', re.IGNORECASE)
    for line in text.splitlines():
        am = action_re.match(line)
        if am:
            current = AirAction(number=int(am.group(1)), label=(am.group(2) or COMMON_ANIMS.get(int(am.group(1)), '') or ''))
            current.raw_lines.append(line)
            actions.append(current)
            pending_clsn = []
            continue
        if current is not None:
            current.raw_lines.append(line)
            cm = clsn_re.match(line)
            if cm:
                pending_clsn.append(AirClsnBox(f'Clsn{cm.group(1)}', int(cm.group(2)), int(cm.group(3)), int(cm.group(4)), int(cm.group(5))))
                continue
            fm = frame_re.match(line)
            if fm:
                current.frames.append(AirFrame(
                    group=int(fm.group(1)), image=int(fm.group(2)), x=int(fm.group(3)),
                    y=int(fm.group(4)), ticks=int(fm.group(5)), flags=(fm.group(6) or '').strip(),
                    clsn=list(pending_clsn)
                ))
                pending_clsn = []
    return actions


def parse_code(text: str) -> CodeScan:
    scan = CodeScan()
    lines = text.splitlines()
    section_re = re.compile(r'^\s*\[\s*([^\]]+)\s*\]\s*(?:[;#].*)?$', re.I)
    kv_re = re.compile(r'^\s*([^;#=]+?)\s*=\s*(.*?)\s*(?:[;#].*)?$')
    current_cmd: Optional[Dict[str, str]] = None
    current_cmd_line = 0
    current_state: Optional[StateDef] = None
    current_ctrl: Optional[StateController] = None

    def finish_cmd():
        nonlocal current_cmd, current_cmd_line
        if current_cmd is not None:
            name = current_cmd.get('name', '').strip('"')
            command = current_cmd.get('command', '')
            def to_int(v: str | None) -> Optional[int]:
                try: return int(v) if v not in (None, '') else None
                except ValueError: return None
            if name:
                scan.commands.append(CmdCommand(name=name, command=command, time=to_int(current_cmd.get('time')), buffer_time=to_int(current_cmd.get('buffer.time') or current_cmd.get('buffer_time')), line=current_cmd_line))
            else:
                scan.issues.append(f'Line {current_cmd_line}: [Command] without a name.')
        current_cmd = None
        current_cmd_line = 0

    for idx, line in enumerate(lines, start=1):
        sm = section_re.match(line)
        if sm:
            title = sm.group(1).strip()
            low = title.lower()
            finish_cmd()
            current_ctrl = None
            if low == 'command':
                current_cmd = {}
                current_cmd_line = idx
                continue
            m_state = re.match(r'statedef\s+(-?\d+)', title, re.I)
            if m_state:
                current_state = StateDef(number=int(m_state.group(1)), line=idx)
                scan.states.append(current_state)
                continue
            m_ctrl = re.match(r'state\s+([^,]+)(?:,\s*(.*))?', title, re.I)
            if m_ctrl:
                current_ctrl = StateController(header=title, stype='', line=idx)
                scan.controllers.append(current_ctrl)
                if current_state is not None:
                    current_state.controllers.append(current_ctrl)
                continue
            continue
        kv = kv_re.match(line)
        if kv:
            key = kv.group(1).strip().lower()
            value = strip_inline_comment(kv.group(2))
            if current_cmd is not None:
                current_cmd[key] = value
            elif current_ctrl is not None:
                current_ctrl.values[key] = value
                if key == 'type':
                    current_ctrl.stype = value.lower()
            elif current_state is not None:
                current_state.values[key] = value
        lowline = line.lower()
        if 'todo' in lowline or 'placeholder' in lowline or 'fixme' in lowline:
            scan.issues.append(f'Line {idx}: TODO/FIXME/placeholder text detected.')
    finish_cmd()

    command_names = {c.name for c in scan.commands}
    for ctrl in scan.controllers:
        if ctrl.values.get('type', '').lower() == 'changestate':
            trigger_values = ' '.join(v.lower() for k, v in ctrl.values.items() if k.startswith('trigger'))
            if 'command' in trigger_values:
                found = False
                for name in command_names:
                    if f'"{name.lower()}"' in trigger_values or f"'{name.lower()}'" in trigger_values:
                        found = True
                        break
                if not found and command_names:
                    scan.issues.append(f'Line {ctrl.line}: ChangeState appears to reference command input, but no known [Command] name was matched.')
    return scan


def referenced_files_from_def(def_path: Path, sections: Dict[str, DefSection]) -> Dict[str, str]:
    files = sections.get('files')
    if not files:
        return {}
    refs: Dict[str, str] = {}
    for key, val in files.values.items():
        clean = val.strip().strip('"')
        if clean and not clean.startswith(';'):
            refs[key] = clean
    return refs


def resolve_reference(base: Path, ref: str) -> Path:
    ref = ref.replace('\\', '/')
    return (base / ref).resolve()


def scan_project(root: Path) -> ProjectAudit:
    found_exts: Dict[str, int] = {}
    text_files: List[Path] = []
    binary_files: List[Path] = []
    warnings: List[str] = []
    def_references: Dict[Path, Dict[str, str]] = {}
    missing_references: List[str] = []
    code_issues: List[str] = []
    asset_issues: List[str] = []

    for path in sorted(root.rglob('*')):
        if path.is_dir():
            continue
        ext = path.suffix.lower()
        found_exts[ext] = found_exts.get(ext, 0) + 1
        if ext in TEXT_EXTS:
            text_files.append(path)
            if ext == '.def':
                sections = parse_def(read_text_safely(path))
                refs = referenced_files_from_def(path, sections)
                def_references[path] = refs
                for key, ref in refs.items():
                    if ref and not resolve_reference(path.parent, ref).exists():
                        missing_references.append(f'{path.name} [{key}] -> {ref}')
                try:
                    anim_ref = refs.get('anim')
                    sprite_ref = refs.get('sprite')
                    if anim_ref and sprite_ref:
                        air_path = resolve_reference(path.parent, anim_ref)
                        sff_path = resolve_reference(path.parent, sprite_ref)
                        if air_path.exists() and sff_path.exists():
                            from .sff_codec import read_sff, sprite_lookup
                            actions = parse_air(read_text_safely(air_path))
                            lookup = sprite_lookup(read_sff(sff_path))
                            missing_pairs = []
                            for action in actions:
                                for frame in action.frames:
                                    if frame.group < 0 or frame.image < 0:
                                        continue
                                    if (frame.group, frame.image) not in lookup:
                                        pair = f'{frame.group},{frame.image}'
                                        if pair not in missing_pairs:
                                            missing_pairs.append(pair)
                                    if len(missing_pairs) >= 40:
                                        break
                                if len(missing_pairs) >= 40:
                                    break
                            if missing_pairs:
                                asset_issues.append(f'{air_path.name}: AIR references {len(missing_pairs)} sprite pair(s) not found in {sff_path.name}: ' + ', '.join(missing_pairs[:20]))
                except Exception as exc:
                    asset_issues.append(f'{path.name}: AIR/SFF cross-check failed: {exc}')
            elif ext in {'.cmd', '.cns', '.st'}:
                cs = parse_code(read_text_safely(path))
                for issue in cs.issues[:50]:
                    code_issues.append(f'{path.name}: {issue}')
        else:
            binary_files.append(path)
    missing = [ext for ext in CHAR_REQUIRED_EXTS if found_exts.get(ext, 0) == 0]
    if missing:
        warnings.append('Missing common character files by extension: ' + ', '.join(missing))
    if found_exts.get('.def', 0) > 1:
        warnings.append('Multiple .def files found. Confirm the main character DEF manually.')
    if found_exts.get('.air', 0) == 0:
        warnings.append('No AIR animation file detected.')
    if missing_references:
        warnings.append(f'{len(missing_references)} DEF file reference(s) point to missing files.')
    if code_issues:
        warnings.append(f'{len(code_issues)} code issue(s) detected in CMD/CNS/ST text.')
    if asset_issues:
        warnings.append(f'{len(asset_issues)} AIR/SFF asset issue(s) detected.')
    return ProjectAudit(root=root, found_exts=found_exts, missing_required=missing, text_files=text_files, binary_files=binary_files, warnings=warnings, def_references=def_references, missing_references=missing_references, code_issues=code_issues, asset_issues=asset_issues)


def summarize_sff(path: Path) -> str:
    try:
        from .sff_codec import summarize_sff_detailed
        return summarize_sff_detailed(path)
    except Exception as exc:
        data = path.read_bytes()[:2048]
        lines = [f'File: {path.name}', f'Size: {path.stat().st_size:,} bytes', f'SFF parser error: {exc}']
        if data:
            lines.append('First 16 bytes: ' + ' '.join(f'{b:02X}' for b in data[:16]))
        return '\n'.join(lines)


def summarize_snd(path: Path) -> str:
    try:
        from .snd_codec import summarize_snd_detailed
        return summarize_snd_detailed(path)
    except Exception as exc:
        data = path.read_bytes()
        lines = [f'File: {path.name}', f'Size: {path.stat().st_size:,} bytes', f'SND parser error: {exc}']
        if data[:12].startswith(b'ElecbyteSnd'):
            lines.append('Signature: ElecbyteSnd detected')
        wave_count = data.count(b'RIFF')
        lines.append(f'Embedded RIFF/WAVE markers found: {wave_count}')
        return '\n'.join(lines)


def summarize_act(path: Path) -> str:
    size = path.stat().st_size
    lines = [f'File: {path.name}', f'Size: {size:,} bytes']
    if size == 768:
        lines.append('Looks like a 256-color ACT palette: 256 RGB entries.')
    elif size == 769:
        lines.append('Looks like a 256-color ACT palette plus one extra byte.')
    elif size == 772:
        lines.append('Looks like a Photoshop ACT variant with count/transparent metadata.')
    else:
        lines.append('Non-standard ACT size. Palette loading may need special handling.')
    return '\n'.join(lines)


def summarize_binary(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == '.sff':
        return summarize_sff(path)
    if ext == '.snd':
        return summarize_snd(path)
    if ext == '.act':
        return summarize_act(path)
    return f'File: {path.name}\nSize: {path.stat().st_size:,} bytes\nBinary preview is not implemented for {ext} yet.'


def make_new_character(root: Path, name: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_\-]+', '_', name).strip('_') or 'new_character'
    char_dir = root / safe
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / f'{safe}.def').write_text(f'''[Info]\nname = "{safe}"\ndisplayname = "{safe}"\nversiondate = 06,12,2026\nmugenversion = 1.0\nauthor = "Doc"\n\n[Files]\nsprite = {safe}.sff\nsound = {safe}.snd\nanim = {safe}.air\ncmd = {safe}.cmd\ncns = {safe}.cns\n\n[Arcade]\nintro.storyboard = \nending.storyboard = \n''', encoding='utf-8')
    (char_dir / f'{safe}.air').write_text('[Begin Action 0] ; standing/idle\n0,0, 0,0, 5\n\n[Begin Action 20] ; walk forward\n0,0, 0,0, 4\n0,1, 0,0, 4\n0,2, 0,0, 4\n', encoding='utf-8')
    (char_dir / f'{safe}.cmd').write_text('''[Command]\nname = "x"\ncommand = x\ntime = 1\n\n[Command]\nname = "forward_x"\ncommand = F, x\ntime = 12\n\n[Statedef -1]\n\n[State -1, Light Attack]\ntype = ChangeState\nvalue = 200\ntriggerall = command = "x"\ntrigger1 = ctrl\n''', encoding='utf-8')
    (char_dir / f'{safe}.cns').write_text('''[Data]\nlife = 1000\nattack = 100\ndefence = 100\nfall.defence_up = 50\nliedown.time = 60\nairjuggle = 15\nsparkno = 2\nguard.sparkno = 40\nKO.echo = 0\nvolume = 0\nIntPersistIndex = 60\nFloatPersistIndex = 40\n\n[Size]\nxscale = 1\nyscale = 1\nground.back = 15\nground.front = 16\nair.back = 12\nair.front = 12\nheight = 60\nattack.dist = 160\nproj.attack.dist = 90\nproj.doscale = 0\nhead.pos = -5, -90\nmid.pos = -5, -60\nshadowoffset = 0\ndraw.offset = 0,0\n\n[Statedef 0]\ntype = S\nphysics = S\nanim = 0\nvelset = 0,0\nctrl = 1\n\n[Statedef 200]\ntype = S\nmovetype = A\nphysics = S\nanim = 200\nctrl = 0\n\n[State 200, HitDef]\ntype = HitDef\ntrigger1 = AnimElem = 2\nattr = S, NA\ndamage = 35, 5\npausetime = 8, 8\nsparkno = 2\nhitsound = 5, 0\nguardsound = 6, 0\nground.type = High\nground.slidetime = 8\nground.hittime = 12\nground.velocity = -3\nair.velocity = -2,-4\n\n[State 200, End]\ntype = ChangeState\ntrigger1 = AnimTime = 0\nvalue = 0\nctrl = 1\n''', encoding='utf-8')
    return char_dir
