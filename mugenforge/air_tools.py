from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List, Optional, Tuple

@dataclass
class AirLineClsnBox:
    kind: str
    index: int
    x1: int
    y1: int
    x2: int
    y2: int
    line_index: int

@dataclass
class AirLineFrame:
    action_number: int
    frame_index: int
    group: int
    image: int
    x: int
    y: int
    ticks: int
    flags: str
    line_index: int
    clsn: List[AirLineClsnBox] = field(default_factory=list)

@dataclass
class AirLineAction:
    number: int
    label: str
    line_index: int
    frames: List[AirLineFrame] = field(default_factory=list)

ACTION_RE = re.compile(r'^\s*\[\s*Begin\s+Action\s+(-?\d+)\s*\]\s*(?:;\s*(.*))?$', re.I)
FRAME_RE = re.compile(r'^\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*(?:,\s*([^;]+))?')
CLSN_RE = re.compile(r'^\s*Clsn([12])\[\s*(\d+)\s*\]\s*=\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)', re.I)
CLSN_LINE_RE = re.compile(r'^\s*Clsn[12]\[\s*\d+\s*\]\s*=', re.I)


def parse_air_with_lines(text: str) -> List[AirLineAction]:
    actions: List[AirLineAction] = []
    current: Optional[AirLineAction] = None
    pending: List[AirLineClsnBox] = []
    for idx, line in enumerate(text.splitlines()):
        am = ACTION_RE.match(line)
        if am:
            current = AirLineAction(number=int(am.group(1)), label=am.group(2) or '', line_index=idx)
            actions.append(current)
            pending = []
            continue
        if current is None:
            continue
        cm = CLSN_RE.match(line)
        if cm:
            pending.append(AirLineClsnBox(
                kind=f'Clsn{cm.group(1)}', index=int(cm.group(2)),
                x1=int(cm.group(3)), y1=int(cm.group(4)), x2=int(cm.group(5)), y2=int(cm.group(6)),
                line_index=idx
            ))
            continue
        fm = FRAME_RE.match(line)
        if fm:
            flags = (fm.group(6) or '').strip()
            frame = AirLineFrame(
                action_number=current.number,
                frame_index=len(current.frames),
                group=int(fm.group(1)), image=int(fm.group(2)), x=int(fm.group(3)), y=int(fm.group(4)),
                ticks=int(fm.group(5)), flags=flags, line_index=idx, clsn=list(pending)
            )
            current.frames.append(frame)
            pending = []
    return actions


def find_frame(actions: List[AirLineAction], action_number: int, frame_index: int) -> Optional[AirLineFrame]:
    for action in actions:
        if action.number == action_number:
            if 0 <= frame_index < len(action.frames):
                return action.frames[frame_index]
            return None
    return None


def normalize_box(kind: str, x1: int, y1: int, x2: int, y2: int) -> AirLineClsnBox:
    kind = 'Clsn1' if str(kind).lower().endswith('1') else 'Clsn2'
    return AirLineClsnBox(kind=kind, index=0, x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2), line_index=-1)


def validate_boxes(boxes: List[AirLineClsnBox]) -> List[str]:
    issues: List[str] = []
    for i, b in enumerate(boxes):
        if b.x1 == b.x2 or b.y1 == b.y2:
            issues.append(f'Box {i} {b.kind}: zero-width or zero-height box.')
        if b.x1 > b.x2 or b.y1 > b.y2:
            issues.append(f'Box {i} {b.kind}: coordinates appear inverted; Fighter Factory-style boxes usually use x1,y1,x2,y2 ordering.')
        if max(abs(b.x1), abs(b.y1), abs(b.x2), abs(b.y2)) > 2000:
            issues.append(f'Box {i} {b.kind}: very large coordinate value; confirm this is intentional.')
    return issues


def update_frame_clsn_text(text: str, action_number: int, frame_index: int, boxes: List[AirLineClsnBox]) -> Tuple[str, List[str]]:
    """Replace per-frame Clsn1/Clsn2[] lines immediately attached to a frame.

    This intentionally does not rewrite ClsnDefault blocks. It only changes explicit per-frame CLSN
    lines that appear before a specific AIR frame line.
    """
    actions = parse_air_with_lines(text)
    frame = find_frame(actions, action_number, frame_index)
    if frame is None:
        raise ValueError(f'Action {action_number} frame {frame_index} was not found.')

    lines = text.splitlines()
    remove = {b.line_index for b in frame.clsn if 0 <= b.line_index < len(lines)}

    # Also remove contiguous Clsn lines directly above the frame if parser missed them because of spacing variants.
    scan = frame.line_index - 1
    while scan >= 0 and CLSN_LINE_RE.match(lines[scan]):
        remove.add(scan)
        scan -= 1

    ordered: List[str] = []
    counters = {'Clsn1': 0, 'Clsn2': 0}
    for box in boxes:
        kind = 'Clsn1' if box.kind.lower().endswith('1') else 'Clsn2'
        idx = counters[kind]
        counters[kind] += 1
        ordered.append(f'{kind}[{idx}] = {box.x1}, {box.y1}, {box.x2}, {box.y2}')

    new_lines: List[str] = []
    for idx, line in enumerate(lines):
        if idx == frame.line_index:
            new_lines.extend(ordered)
            new_lines.append(line)
        elif idx not in remove:
            new_lines.append(line)
    warnings = validate_boxes(boxes)
    if any('ClsnDefault' in lines[i] for i in range(max(0, frame.line_index - 6), frame.line_index)):
        warnings.append('Nearby ClsnDefault line detected. This editor changes explicit per-frame boxes only; defaults are preserved.')
    return '\n'.join(new_lines) + ('\n' if text.endswith('\n') else ''), warnings
