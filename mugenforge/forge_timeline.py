from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import html
import json
import math
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .air_tools import parse_air_with_lines, update_frame_clsn_text, normalize_box
from .artifact_io import (
    rel_path,
    timestamp as _timestamp,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .parsers import COMMON_ANIMS, parse_code, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file
from .palette_tools import read_act, write_act
try:  # optional in older packages during partial imports
    from .visual_forge import create_backup_snapshot
except Exception:  # pragma: no cover
    create_backup_snapshot = None  # type: ignore

FORGE_TIMELINE_VERSION = "4.5.0"
CODE_SUFFIXES = {".cmd", ".cns", ".st"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg", ".csv"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
PALETTE_SUFFIXES = {".act", ".pal"}
SKIP_PARTS = {"__pycache__", ".git", ".hg", ".svn", ".venv", "venv"}
GENERATED_PARTS = {"forge_timeline", "forge_polish", "forge_beyond", "visual_forge", "backups", "exports", "quality_lab", "rescue_lab"}


@dataclass
class ForgeTimelineResult:
    title: str = "Forge Timeline Result"
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def merge(self, other: object, label: Optional[str] = None) -> None:
        if not other:
            return
        prefix = f"{label}: " if label else ""
        for attr in ("created_files", "changed_files", "skipped_files", "warnings", "notes"):
            getattr(self, attr).extend(prefix + str(v) for v in (getattr(other, attr, []) or []))

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def add_note(self, message: str) -> None:
        self.notes.append(str(message))

    def to_text(self) -> str:
        lines = [self.title, "=" * max(12, len(self.title)), f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
        for label, values in (("Notes", self.notes), ("Created files/artifacts", self.created_files), ("Changed files", self.changed_files), ("Skipped", self.skipped_files), ("Warnings", self.warnings)):
            values = _uniq(values)
            if values:
                lines.append(label + ":")
                lines.extend(f"- {v}" for v in values)
                lines.append("")
        if len(lines) <= 4:
            lines.append("No changes made.")
        return "\n".join(lines).rstrip() + "\n"


def _uniq(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value or "")).strip("_") or "item"


def _rel(root: Path, path: Path | str | None) -> str:
    if path is None:
        return ""
    return rel_path(root, path)


def _out(root: Path, *parts: str) -> Path:
    p = Path(root) / "forge_timeline"
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_text(root: Path, path: Path, text: str, res: Optional[ForgeTimelineResult] = None) -> Path:
    return write_text_artifact(path, text, res, root, track_existing=True)


def _write_json(root: Path, path: Path, payload: object, res: Optional[ForgeTimelineResult] = None) -> Path:
    return write_json_artifact(path, payload, res, root, track_existing=True)


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[ForgeTimelineResult] = None) -> Path:
    return write_csv_artifact(path, rows, fields, res, root, track_existing=True)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _all_files(root: Path, include_generated: bool = True) -> List[Path]:
    root = Path(root)
    out: List[Path] = []
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts if path.is_relative_to(root) else path.parts
        if any(part in SKIP_PARTS for part in rel_parts):
            continue
        if not include_generated and any(part in GENERATED_PARTS for part in rel_parts):
            continue
        out.append(path)
    return out


def _code_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root, include_generated=False) if p.suffix.lower() in CODE_SUFFIXES]


def _image_files(root: Path, include_generated: bool = False) -> List[Path]:
    return [p for p in _all_files(root, include_generated=include_generated) if p.suffix.lower() in IMAGE_SUFFIXES]


def _palette_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root, include_generated=False) if p.suffix.lower() in PALETTE_SUFFIXES]


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {"root": root}
    for kind in ("def", "air", "cmd", "cns", "sff", "snd"):
        try:
            found = find_character_file(root, kind)
        except Exception:
            found = None
        if not found:
            hits = sorted(root.rglob(f"*.{kind}"), key=lambda p: str(p).lower())
            found = hits[0] if hits else None
        out[kind] = found
    return out


def _int(value: object, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "yes", "y", "true", "on", "apply", "enabled", "update", "add", "delete"}


def _backup_text_file(root: Path, path: Path, reason: str) -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        rel = path.resolve().relative_to(Path(root).resolve())
    except Exception:
        rel = Path(path.name)
    dst = Path(root) / "backups" / "forge_timeline_file_backups" / rel.with_name(rel.name + f".bak_{_safe_name(reason)}_{_timestamp()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def _read_air_actions(root: Path):
    files = _discover_files(root)
    air_path = files.get("air")
    if not air_path or not air_path.exists():
        return None, []
    return air_path, parse_air_with_lines(read_text_safely(air_path))


def _first_int_in(value: str, default: Optional[int] = None) -> Optional[int]:
    m = re.search(r"-?\d+", str(value or ""))
    return int(m.group(0)) if m else default


def _parse_int_pair(value: str) -> Tuple[Optional[int], Optional[int]]:
    nums = re.findall(r"-?\d+", str(value or ""))
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        return int(nums[0]), None
    return None, None


def _trigger_anim_elem(values: Dict[str, str]) -> Optional[int]:
    for key, value in values.items():
        if not key.lower().startswith("trigger"):
            continue
        text = str(value)
        m = re.search(r"AnimElem\s*(?:=|>=|<=|>|<)?\s*(-?\d+)", text, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"AnimElemNo\s*\([^\)]*\)\s*(?:=|>=|<=|>|<)\s*(-?\d+)", text, re.I)
        if m:
            return int(m.group(1))
    return None


def _state_records(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            anim = _first_int_in(state.values.get("anim", ""), None)
            rows.append({
                "file": _rel(root, path),
                "path": path,
                "line": state.line,
                "state": state.number,
                "anim": anim,
                "type": state.values.get("type", ""),
                "movetype": state.values.get("movetype", ""),
                "physics": state.values.get("physics", ""),
                "controller_count": len(state.controllers),
            })
    return rows


def _code_events(root: Path) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            anim = _first_int_in(state.values.get("anim", ""), state.number if state.number >= 0 else None)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).strip()
                low = stype.lower()
                elem = _trigger_anim_elem(ctrl.values)
                if elem is None and low in {"hitdef", "playsnd", "projectile", "helper", "explod", "velset", "posadd"}:
                    elem = 0
                if low not in {"hitdef", "playsnd", "projectile", "helper", "explod", "velset", "posadd", "changestate", "changeanim"}:
                    continue
                value = ctrl.values.get("value", "")
                detail = ""
                if low == "hitdef":
                    detail = f"damage={ctrl.values.get('damage', '')} attr={ctrl.values.get('attr', '')}"
                elif low == "playsnd":
                    detail = f"value={value} channel={ctrl.values.get('channel', '')}"
                elif low == "changestate":
                    detail = f"value={value}"
                elif low == "changeanim":
                    detail = f"value={value}"
                elif low == "projectile":
                    detail = f"projanim={ctrl.values.get('projanim', '')} damage={ctrl.values.get('damage', '')}"
                elif low == "helper":
                    detail = f"helpertype={ctrl.values.get('helpertype', '')} stateno={ctrl.values.get('stateno', '')}"
                elif low == "explod":
                    detail = f"anim={ctrl.values.get('anim', '')} id={ctrl.values.get('id', '')}"
                else:
                    detail = ", ".join(f"{k}={v}" for k, v in list(ctrl.values.items())[:4])
                events.append({
                    "file": _rel(root, path),
                    "path": path,
                    "line": ctrl.line,
                    "state": state.number,
                    "anim": anim,
                    "type": low,
                    "anim_elem": elem,
                    "detail": detail,
                    "values": dict(ctrl.values),
                })
    return events


def _events_by_anim(events: Sequence[Dict[str, object]]) -> Dict[int, List[Dict[str, object]]]:
    out: Dict[int, List[Dict[str, object]]] = {}
    for ev in events:
        anim = _int(ev.get("anim"), None)
        if anim is None:
            continue
        out.setdefault(anim, []).append(ev)
    return out


# ---------------------------------------------------------------------------
# Integrated move timeline
# ---------------------------------------------------------------------------


def build_integrated_move_timeline_model(root: Path, action_number: Optional[int] = None) -> ForgeTimelineResult:
    """Build a source-analysis timeline model with frame, CLSN, sound, HitDef and controller tracks.

    This is intentionally text/source based. It does not mutate SFF/SND binaries.
    """
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline v4.5 Integrated Move Timeline")
    out = _out(root, "move_timeline")
    air_path, actions = _read_air_actions(root)
    if not air_path:
        result.warnings.append("No AIR file found; timeline model could not be built.")
        return result
    if action_number is not None:
        actions = [a for a in actions if a.number == int(action_number)]
        if not actions:
            result.warnings.append(f"AIR action {action_number} was not found.")
    events = _code_events(root)
    ev_by_anim = _events_by_anim(events)
    states = _state_records(root)
    state_by_anim: Dict[int, List[Dict[str, object]]] = {}
    for st in states:
        anim = _int(st.get("anim"), None)
        if anim is not None:
            state_by_anim.setdefault(anim, []).append(st)

    action_payloads: List[Dict[str, object]] = []
    frame_rows: List[Dict[str, object]] = []
    total_frames = 0
    for action in actions:
        tick_cursor = 0
        action_events = ev_by_anim.get(action.number, [])
        action_states = state_by_anim.get(action.number, [])
        frames: List[Dict[str, object]] = []
        for frame in action.frames:
            clsn1 = [b for b in frame.clsn if b.kind.lower() == "clsn1"]
            clsn2 = [b for b in frame.clsn if b.kind.lower() == "clsn2"]
            elem = frame.frame_index + 1
            frame_events = [ev for ev in action_events if _int(ev.get("anim_elem"), -1) in {elem, 0, None}]
            sounds = [ev for ev in frame_events if ev.get("type") == "playsnd" and _int(ev.get("anim_elem"), 0) in {elem, 0}]
            hitdefs = [ev for ev in frame_events if ev.get("type") == "hitdef" and _int(ev.get("anim_elem"), 0) in {elem, 0}]
            controllers = [ev for ev in frame_events if ev.get("type") not in {"playsnd", "hitdef"} and _int(ev.get("anim_elem"), 0) in {elem, 0}]
            rec = {
                "action": action.number,
                "label": action.label or COMMON_ANIMS.get(action.number, ""),
                "frame_index": frame.frame_index,
                "anim_elem": elem,
                "group": frame.group,
                "image": frame.image,
                "x": frame.x,
                "y": frame.y,
                "ticks": frame.ticks,
                "flags": frame.flags,
                "tick_start": tick_cursor,
                "tick_end": tick_cursor + max(0, frame.ticks),
                "clsn1_count": len(clsn1),
                "clsn2_count": len(clsn2),
                "has_hitbox": bool(clsn1),
                "has_body": bool(clsn2),
                "sound_count": len(sounds),
                "hitdef_count": len(hitdefs),
                "controller_count": len(controllers),
                "events": [{k: v for k, v in ev.items() if k not in {"path", "values"}} for ev in frame_events],
            }
            frames.append(rec)
            frame_rows.append({k: v for k, v in rec.items() if k != "events"})
            tick_cursor += max(0, frame.ticks)
            total_frames += 1
        action_payloads.append({
            "action": action.number,
            "label": action.label or COMMON_ANIMS.get(action.number, ""),
            "line_index": action.line_index,
            "frame_count": len(action.frames),
            "total_ticks": tick_cursor,
            "states_using_anim": [{k: v for k, v in st.items() if k != "path"} for st in action_states],
            "events": [{k: v for k, v in ev.items() if k not in {"path", "values"}} for ev in action_events],
            "frames": frames,
        })
    payload = {
        "tool": "MugenForge Studio",
        "feature": "Forge Timeline v4.5 Integrated Move Timeline",
        "project": root.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source_air": _rel(root, air_path),
        "action_filter": action_number,
        "honest_scope": "Text/source-analysis timeline. Does not mutate SFF/SND binaries.",
        "action_count": len(action_payloads),
        "frame_count": total_frames,
        "actions": action_payloads,
    }
    _write_json(root, out / "integrated_move_timeline.json", payload, result)
    _write_csv(root, out / "integrated_move_timeline_frames.csv", frame_rows, [
        "action", "label", "frame_index", "anim_elem", "group", "image", "x", "y", "ticks", "flags", "tick_start", "tick_end", "clsn1_count", "clsn2_count", "has_hitbox", "has_body", "sound_count", "hitdef_count", "controller_count"
    ], result)
    html_text = _timeline_html(payload)
    _write_text(root, out / "integrated_move_timeline.html", html_text, result)
    try:
        png = _draw_integrated_timeline_png(root, payload, out / "integrated_move_timeline.png")
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"Timeline PNG preview could not be rendered: {exc}")
    result.notes.append(f"Built integrated timeline for {len(action_payloads)} AIR action(s), {total_frames} frame(s).")
    return result


def _timeline_html(payload: Dict[str, object]) -> str:
    rows: List[str] = []
    for action in payload.get("actions", []) or []:
        if not isinstance(action, dict):
            continue
        rows.append(f"<h2>Action {html.escape(str(action.get('action')))} {html.escape(str(action.get('label') or ''))}</h2>")
        rows.append("<table><tr><th>Frame</th><th>Sprite</th><th>Ticks</th><th>Offset</th><th>CLSN</th><th>Events</th></tr>")
        for fr in action.get("frames", []) or []:
            events = []
            if fr.get("hitdef_count"):
                events.append(f"HitDef x{fr.get('hitdef_count')}")
            if fr.get("sound_count"):
                events.append(f"Sound x{fr.get('sound_count')}")
            if fr.get("controller_count"):
                events.append(f"Controllers x{fr.get('controller_count')}")
            rows.append("<tr>" + "".join([
                f"<td>{fr.get('anim_elem')}</td>",
                f"<td>{fr.get('group')},{fr.get('image')}</td>",
                f"<td>{fr.get('ticks')}</td>",
                f"<td>{fr.get('x')},{fr.get('y')}</td>",
                f"<td>hit {fr.get('clsn1_count')} / body {fr.get('clsn2_count')}</td>",
                f"<td>{html.escape(', '.join(events) or '-')}</td>",
            ]) + "</tr>")
        rows.append("</table>")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Forge Timeline v4.5</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;}}table{{border-collapse:collapse;margin-bottom:24px;}}th,td{{border:1px solid #bbb;padding:4px 8px;font-size:13px;}}th{{background:#eee;}}.note{{background:#fff8d6;padding:10px;border:1px solid #dfc66a;}}</style>
</head><body>
<h1>Forge Timeline v4.5 Integrated Move Timeline</h1>
<p class="note">This is a text/source-analysis timeline. It can guide editing, but it is not engine-authoritative runtime telemetry and does not mutate SFF/SND binaries.</p>
<p>Project: <b>{html.escape(str(payload.get('project')))}</b><br>Generated: {html.escape(str(payload.get('generated')))}<br>Source AIR: {html.escape(str(payload.get('source_air')))}</p>
{''.join(rows)}
</body></html>"""


def _draw_integrated_timeline_png(root: Path, payload: Dict[str, object], out_path: Path) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for timeline PNG rendering. Install with: pip install Pillow") from exc
    actions = [a for a in payload.get("actions", []) or [] if isinstance(a, dict)]
    if not actions:
        actions = [{"action": "none", "label": "No actions", "frames": []}]
    row_h = 92
    left_w = 190
    top_h = 52
    scale = 9
    max_ticks = 60
    for action in actions:
        ticks = sum(max(1, int(fr.get("ticks", 1) or 1)) for fr in action.get("frames", []) or [])
        max_ticks = max(max_ticks, ticks)
    width = min(4200, max(900, left_w + max_ticks * scale + 80))
    height = max(260, top_h + len(actions) * row_h + 40)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 12)
        small = ImageFont.truetype("DejaVuSans.ttf", 10)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = small = bold = None
    draw.text((16, 14), "Forge Timeline v4.5 — Integrated Move Timeline", fill=(0, 0, 0), font=bold)
    draw.text((16, 32), "Tracks: sprite frames, CLSN, sound cues, HitDefs/controllers. Source-analysis only.", fill=(60, 60, 60), font=small)
    for row, action in enumerate(actions):
        y = top_h + row * row_h
        draw.rectangle([0, y, width, y + row_h - 1], outline=(210, 210, 210), fill=(250, 250, 250) if row % 2 else (255, 255, 255))
        label = f"Action {action.get('action')} {action.get('label') or ''}"[:28]
        draw.text((12, y + 12), label, fill=(0, 0, 0), font=bold)
        draw.text((12, y + 33), "CLSN / sound / HitDef", fill=(70, 70, 70), font=small)
        x = left_w
        for fr in action.get("frames", []) or []:
            ticks = max(1, int(fr.get("ticks", 1) or 1))
            w = max(20, ticks * scale)
            if x + w > width - 20:
                break
            base_fill = (236, 246, 255)
            if fr.get("hitdef_count"):
                base_fill = (255, 224, 224)
            elif fr.get("sound_count"):
                base_fill = (230, 242, 220)
            draw.rectangle([x, y + 10, x + w, y + 42], fill=base_fill, outline=(80, 120, 160))
            draw.text((x + 3, y + 13), f"{fr.get('anim_elem')}", fill=(0, 0, 0), font=small)
            draw.text((x + 3, y + 28), f"{fr.get('group')},{fr.get('image')}", fill=(0, 0, 0), font=small)
            # CLSN strip
            if fr.get("clsn2_count"):
                draw.rectangle([x, y + 50, x + w, y + 60], fill=(205, 230, 255), outline=(120, 160, 190))
            if fr.get("clsn1_count"):
                draw.rectangle([x, y + 63, x + w, y + 73], fill=(255, 205, 205), outline=(190, 120, 120))
            if fr.get("sound_count"):
                draw.ellipse([x + 3, y + 76, x + 13, y + 86], fill=(80, 150, 70))
            if fr.get("hitdef_count"):
                draw.polygon([(x + w - 14, y + 76), (x + w - 4, y + 76), (x + w - 9, y + 86)], fill=(190, 60, 60))
            x += w + 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def export_move_timeline_edit_sheet(root: Path, action_number: Optional[int] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Move Edit Sheet Export")
    # Ensure latest model exists and use its rows.
    result.merge(build_integrated_move_timeline_model(root, action_number), "model")
    model_path = root / "forge_timeline" / "move_timeline" / "integrated_move_timeline.json"
    if not model_path.exists():
        result.warnings.append("Timeline model was not available, so no edit sheet was written.")
        return result
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    rows: List[Dict[str, object]] = []
    for action in payload.get("actions", []) or []:
        for fr in action.get("frames", []) or []:
            rows.append({
                "apply": "no",
                "action": fr.get("action", action.get("action")),
                "frame_index": fr.get("frame_index"),
                "anim_elem": fr.get("anim_elem"),
                "group": fr.get("group"),
                "image": fr.get("image"),
                "x": fr.get("x"),
                "y": fr.get("y"),
                "ticks": fr.get("ticks"),
                "flags": fr.get("flags"),
                "new_group": "",
                "new_image": "",
                "new_x": "",
                "new_y": "",
                "new_ticks": "",
                "add_snd_group": "",
                "add_snd_sound": "",
                "add_snd_channel": "0",
                "add_snd_label": "",
                "notes": "Set apply=yes and fill only the new_* or add_snd_* fields you want changed.",
            })
    path = _out(root, "sheets") / "move_timeline_edit_sheet.csv"
    fields = ["apply", "action", "frame_index", "anim_elem", "group", "image", "x", "y", "ticks", "flags", "new_group", "new_image", "new_x", "new_y", "new_ticks", "add_snd_group", "add_snd_sound", "add_snd_channel", "add_snd_label", "notes"]
    _write_csv(root, path, rows, fields, result)
    result.notes.append("Edit frame timing/offsets in this sheet. Sound cue additions insert PlaySnd source text with backups.")
    return result


def _replace_air_frame_lines(text: str, updates: Dict[Tuple[int, int], Dict[str, object]]) -> Tuple[str, int, List[str]]:
    warnings: List[str] = []
    actions = parse_air_with_lines(text)
    frame_map = {(a.number, f.frame_index): f for a in actions for f in a.frames}
    lines = text.splitlines()
    changed = 0
    for key, upd in updates.items():
        frame = frame_map.get(key)
        if not frame:
            warnings.append(f"AIR frame not found for action={key[0]} frame_index={key[1]}")
            continue
        group = _int(upd.get("new_group"), frame.group)
        image = _int(upd.get("new_image"), frame.image)
        x = _int(upd.get("new_x"), frame.x)
        y = _int(upd.get("new_y"), frame.y)
        ticks = _int(upd.get("new_ticks"), frame.ticks)
        if group is None or image is None or x is None or y is None or ticks is None:
            warnings.append(f"Invalid AIR edit for action={key[0]} frame_index={key[1]}")
            continue
        ticks = max(1, ticks)
        flags = str(upd.get("new_flags") or frame.flags or "").strip()
        new_line = f"{group}, {image}, {x}, {y}, {ticks}" + (f", {flags}" if flags else "")
        if 0 <= frame.line_index < len(lines) and lines[frame.line_index].strip() != new_line.strip():
            lines[frame.line_index] = new_line
            changed += 1
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), changed, warnings


def _find_state_for_anim(root: Path, anim_no: int) -> Tuple[Optional[Path], Optional[int]]:
    # Prefer a StateDef that explicitly uses the animation.
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            anim = _first_int_in(state.values.get("anim", ""), None)
            if anim == int(anim_no):
                return path, state.number
    # Fall back to matching state number.
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            if state.number == int(anim_no):
                return path, state.number
    files = _discover_files(root)
    path = files.get("cns") or files.get("cmd")
    return path, int(anim_no) if path else None


def _insert_controller_into_state(text: str, state_no: int, block: str) -> Tuple[str, str]:
    lines = text.splitlines()
    state_re = re.compile(rf"^\s*\[\s*Statedef\s+{re.escape(str(int(state_no)))}\s*\]", re.I)
    any_state_re = re.compile(r"^\s*\[\s*Statedef\s+-?\d+\s*\]", re.I)
    ctrl_re = re.compile(r"^\s*\[\s*State\s+[^\]]+\]", re.I)
    start = None
    for i, line in enumerate(lines):
        if state_re.match(line):
            start = i
            break
    if start is None:
        # Append a tiny shell if the state is missing.
        add = f"\n[Statedef {state_no}]\ntype = S\nmovetype = I\nphysics = S\nanim = {state_no}\nctrl = 0\n\n{block.strip()}\n"
        return text.rstrip() + "\n" + add, "created_state_shell"
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if any_state_re.match(lines[i]):
            end = i
            break
    insert_at = end
    for i in range(start + 1, end):
        if ctrl_re.match(lines[i]):
            insert_at = i
            break
    new_lines = lines[:insert_at] + ["", block.strip(), ""] + lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""), "inserted"


def apply_move_timeline_edit_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Move Edit Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else root / "forge_timeline" / "sheets" / "move_timeline_edit_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"Move timeline edit sheet not found: {_rel(root, sheet)}")
        return result
    rows = _read_csv(sheet)
    enabled = [r for r in rows if _truthy(r.get("apply"))]
    if not enabled:
        result.skipped_files.append("No rows had apply=yes.")
        return result
    air_path, _actions = _read_air_actions(root)
    air_updates: Dict[Tuple[int, int], Dict[str, object]] = {}
    cue_rows: List[Dict[str, str]] = []
    for row in enabled:
        action = _int(row.get("action"), None)
        frame_index = _int(row.get("frame_index"), None)
        if action is None or frame_index is None:
            result.warnings.append(f"Skipped row with invalid action/frame_index: {row}")
            continue
        if any(str(row.get(key, "")).strip() for key in ("new_group", "new_image", "new_x", "new_y", "new_ticks")):
            air_updates[(action, frame_index)] = row
        if str(row.get("add_snd_group", "")).strip() or str(row.get("add_snd_sound", "")).strip():
            cue_rows.append(row)
    if air_updates:
        if not air_path or not air_path.exists():
            result.warnings.append("AIR edits were requested but no AIR file was found.")
        else:
            old = read_text_safely(air_path)
            new, count, warnings = _replace_air_frame_lines(old, air_updates)
            result.warnings.extend(warnings)
            if count:
                bak = _backup_text_file(root, air_path, "move_timeline_sheet")
                if bak:
                    result.notes.append(f"Backup written: {_rel(root, bak)}")
                write_text_safely(air_path, new)
                result.changed_files.append(_rel(root, air_path))
                result.notes.append(f"Updated {count} AIR frame line(s).")
            else:
                result.skipped_files.append("AIR frame edits produced no text changes.")
    # Insert PlaySnd rows, grouped by target file.
    file_texts: Dict[Path, str] = {}
    file_changed: Dict[Path, int] = {}
    for row in cue_rows:
        action = _int(row.get("action"), None)
        anim_elem = _int(row.get("anim_elem"), None)
        group = _int(row.get("add_snd_group"), None)
        sound = _int(row.get("add_snd_sound"), None)
        channel = _int(row.get("add_snd_channel"), 0) or 0
        if action is None or anim_elem is None or group is None or sound is None:
            result.warnings.append(f"Skipped incomplete sound cue row: {row}")
            continue
        code_path, state_no = _find_state_for_anim(root, action)
        if not code_path or state_no is None:
            result.warnings.append(f"No code file/state found for action {action}; sound cue skipped.")
            continue
        label = re.sub(r"[\r\n\[\]]+", " ", row.get("add_snd_label") or "Forge Timeline Sound Cue").strip()[:80] or "Forge Timeline Sound Cue"
        marker = f"; MugenForge Forge Timeline Sound Cue action={action} elem={anim_elem} value={group},{sound} channel={channel}"
        text = file_texts.get(code_path, read_text_safely(code_path) if code_path.exists() else "")
        if marker in text:
            result.skipped_files.append(f"{_rel(root, code_path)} already has sound cue marker for action {action} elem {anim_elem}.")
            continue
        block = f"""{marker}
[State {state_no}, {label}]
type = PlaySnd
trigger1 = AnimElem = {anim_elem}
value = {group}, {sound}
channel = {channel}
ignorehitpause = 1"""
        text, _status = _insert_controller_into_state(text, int(state_no), block)
        file_texts[code_path] = text
        file_changed[code_path] = file_changed.get(code_path, 0) + 1
    for path, text in file_texts.items():
        bak = _backup_text_file(root, path, "move_timeline_sound_cues")
        if bak:
            result.notes.append(f"Backup written: {_rel(root, bak)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_safely(path, text)
        result.changed_files.append(_rel(root, path))
        result.notes.append(f"Inserted {file_changed.get(path, 0)} PlaySnd cue(s) into {_rel(root, path)}.")
    return result


# ---------------------------------------------------------------------------
# CLSN and HitDef tracks
# ---------------------------------------------------------------------------


def export_clsn_track_sheet(root: Path, action_number: Optional[int] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline CLSN Track Sheet Export")
    air_path, actions = _read_air_actions(root)
    if not air_path:
        result.warnings.append("No AIR file found.")
        return result
    if action_number is not None:
        actions = [a for a in actions if a.number == int(action_number)]
    rows: List[Dict[str, object]] = []
    for action in actions:
        for frame in action.frames:
            if not frame.clsn:
                rows.append({
                    "apply": "no", "action": action.number, "frame_index": frame.frame_index, "anim_elem": frame.frame_index + 1,
                    "kind": "", "box_index": "", "x1": "", "y1": "", "x2": "", "y2": "",
                    "edit_action": "add", "new_kind": "Clsn2", "new_x1": -18, "new_y1": -88, "new_x2": 18, "new_y2": 0,
                    "notes": "No explicit boxes on this frame. Set apply=yes to add one."
                })
            for box in frame.clsn:
                rows.append({
                    "apply": "no", "action": action.number, "frame_index": frame.frame_index, "anim_elem": frame.frame_index + 1,
                    "kind": box.kind, "box_index": box.index, "x1": box.x1, "y1": box.y1, "x2": box.x2, "y2": box.y2,
                    "edit_action": "update", "new_kind": box.kind, "new_x1": box.x1, "new_y1": box.y1, "new_x2": box.x2, "new_y2": box.y2,
                    "notes": "Set apply=yes and edit new_* values, or set edit_action=delete."
                })
    fields = ["apply", "action", "frame_index", "anim_elem", "kind", "box_index", "x1", "y1", "x2", "y2", "edit_action", "new_kind", "new_x1", "new_y1", "new_x2", "new_y2", "notes"]
    _write_csv(root, _out(root, "sheets") / "clsn_track_sheet.csv", rows, fields, result)
    result.notes.append("CLSN sheet uses explicit per-frame boxes only. ClsnDefault blocks are preserved.")
    return result


def apply_clsn_track_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline CLSN Track Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else root / "forge_timeline" / "sheets" / "clsn_track_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"CLSN track sheet not found: {_rel(root, sheet)}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("apply"))]
    if not rows:
        result.skipped_files.append("No rows had apply=yes.")
        return result
    air_path, _ = _read_air_actions(root)
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    text = read_text_safely(air_path)
    grouped: Dict[Tuple[int, int], List[Dict[str, str]]] = {}
    for row in rows:
        action = _int(row.get("action"), None)
        frame = _int(row.get("frame_index"), None)
        if action is None or frame is None:
            result.warnings.append(f"Skipped row with invalid action/frame_index: {row}")
            continue
        grouped.setdefault((action, frame), []).append(row)
    changed_frames = 0
    warnings: List[str] = []
    for (action, frame_index), frame_rows in sorted(grouped.items(), reverse=True):
        actions = parse_air_with_lines(text)
        current = None
        for act in actions:
            if act.number == action:
                for fr in act.frames:
                    if fr.frame_index == frame_index:
                        current = fr
                        break
            if current:
                break
        if current is None:
            warnings.append(f"Frame not found for action={action} frame_index={frame_index}")
            continue
        boxes = list(current.clsn)
        for row in frame_rows:
            edit_action = str(row.get("edit_action") or "update").strip().lower()
            kind = str(row.get("kind") or row.get("new_kind") or "Clsn2")
            idx = _int(row.get("box_index"), None)
            if edit_action == "delete":
                boxes = [b for b in boxes if not (b.kind.lower() == kind.lower() and (idx is None or b.index == idx))]
                continue
            new_kind = row.get("new_kind") or kind or "Clsn2"
            x1 = _int(row.get("new_x1"), _int(row.get("x1"), -18)) or 0
            y1 = _int(row.get("new_y1"), _int(row.get("y1"), -88)) or 0
            x2 = _int(row.get("new_x2"), _int(row.get("x2"), 18)) or 0
            y2 = _int(row.get("new_y2"), _int(row.get("y2"), 0)) or 0
            box = normalize_box(str(new_kind), x1, y1, x2, y2)
            if edit_action == "add" or idx is None or str(row.get("kind") or "").strip() == "":
                boxes.append(box)
            else:
                replaced = False
                for i, existing in enumerate(boxes):
                    if existing.kind.lower() == kind.lower() and existing.index == idx:
                        boxes[i] = box
                        replaced = True
                        break
                if not replaced:
                    boxes.append(box)
        text, frame_warnings = update_frame_clsn_text(text, action, frame_index, boxes)
        warnings.extend(frame_warnings)
        changed_frames += 1
    if changed_frames:
        bak = _backup_text_file(root, air_path, "clsn_track_sheet")
        if bak:
            result.notes.append(f"Backup written: {_rel(root, bak)}")
        write_text_safely(air_path, text)
        result.changed_files.append(_rel(root, air_path))
        result.notes.append(f"Updated explicit CLSN on {changed_frames} frame(s).")
    result.warnings.extend(warnings)
    return result


def export_hitdef_track_sheet(root: Path) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline HitDef Track Sheet Export")
    rows: List[Dict[str, object]] = []
    states = {(_rel(root, st["path"]), int(st["state"])): st for st in _state_records(root) if st.get("path") is not None}
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception as exc:
            result.warnings.append(f"Could not parse {_rel(root, path)}: {exc}")
            continue
        for state in scan.states:
            anim = _first_int_in(state.values.get("anim", ""), state.number if state.number >= 0 else None)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype != "hitdef":
                    continue
                rows.append({
                    "apply": "no",
                    "file": _rel(root, path),
                    "controller_line": ctrl.line,
                    "state": state.number,
                    "anim": anim if anim is not None else "",
                    "anim_elem": _trigger_anim_elem(ctrl.values) or "",
                    "damage": ctrl.values.get("damage", ""),
                    "pausetime": ctrl.values.get("pausetime", ""),
                    "sparkno": ctrl.values.get("sparkno", ""),
                    "hitsound": ctrl.values.get("hitsound", ""),
                    "guardsound": ctrl.values.get("guardsound", ""),
                    "ground_velocity": ctrl.values.get("ground.velocity", ""),
                    "air_velocity": ctrl.values.get("air.velocity", ""),
                    "attr": ctrl.values.get("attr", ""),
                    "hitflag": ctrl.values.get("hitflag", ""),
                    "guardflag": ctrl.values.get("guardflag", ""),
                    "new_damage": "",
                    "new_pausetime": "",
                    "new_sparkno": "",
                    "new_hitsound": "",
                    "new_guardsound": "",
                    "new_ground_velocity": "",
                    "new_air_velocity": "",
                    "new_attr": "",
                    "new_hitflag": "",
                    "new_guardflag": "",
                    "notes": "Set apply=yes and fill only new_* fields you want changed. Backups are written first.",
                })
    fields = ["apply", "file", "controller_line", "state", "anim", "anim_elem", "damage", "pausetime", "sparkno", "hitsound", "guardsound", "ground_velocity", "air_velocity", "attr", "hitflag", "guardflag", "new_damage", "new_pausetime", "new_sparkno", "new_hitsound", "new_guardsound", "new_ground_velocity", "new_air_velocity", "new_attr", "new_hitflag", "new_guardflag", "notes"]
    _write_csv(root, _out(root, "sheets") / "hitdef_track_sheet.csv", rows, fields, result)
    result.notes.append(f"Exported {len(rows)} HitDef row(s).")
    return result


def _find_controller_block(lines: List[str], controller_line: int) -> Tuple[int, int]:
    start = max(0, int(controller_line) - 1)
    section_re = re.compile(r"^\s*\[[^\]]+\]")
    if start >= len(lines):
        return -1, -1
    # If line number drifted, search nearby for a [State ...] header.
    if not section_re.match(lines[start]):
        for i in range(max(0, start - 5), min(len(lines), start + 6)):
            if section_re.match(lines[i]) and re.match(r"^\s*\[\s*State\s+", lines[i], re.I):
                start = i
                break
    if not section_re.match(lines[start]):
        return -1, -1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if section_re.match(lines[i]):
            end = i
            break
    return start, end


def _replace_key_in_block(lines: List[str], start: int, end: int, key: str, value: str) -> bool:
    rx = re.compile(rf"^(\s*){re.escape(key)}(\s*=\s*).*$", re.I)
    for i in range(start + 1, end):
        if rx.match(lines[i]):
            lines[i] = f"{key} = {value}"
            return True
    lines.insert(end, f"{key} = {value}")
    return True


def apply_hitdef_track_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline HitDef Track Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else root / "forge_timeline" / "sheets" / "hitdef_track_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"HitDef track sheet not found: {_rel(root, sheet)}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("apply"))]
    if not rows:
        result.skipped_files.append("No rows had apply=yes.")
        return result
    by_file: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        rel = row.get("file") or ""
        path = (root / rel).resolve()
        if not path.exists():
            result.warnings.append(f"Code file not found for HitDef edit: {rel}")
            continue
        by_file.setdefault(path, []).append(row)
    key_map = {
        "new_damage": "damage",
        "new_pausetime": "pausetime",
        "new_sparkno": "sparkno",
        "new_hitsound": "hitsound",
        "new_guardsound": "guardsound",
        "new_ground_velocity": "ground.velocity",
        "new_air_velocity": "air.velocity",
        "new_attr": "attr",
        "new_hitflag": "hitflag",
        "new_guardflag": "guardflag",
    }
    for path, file_rows in by_file.items():
        lines = read_text_safely(path).splitlines()
        changed = 0
        # Descend by controller line so inserted keys do not affect earlier edits.
        for row in sorted(file_rows, key=lambda r: _int(r.get("controller_line"), 0) or 0, reverse=True):
            line = _int(row.get("controller_line"), None)
            if line is None:
                result.warnings.append(f"Skipped HitDef row without controller_line: {row}")
                continue
            start, end = _find_controller_block(lines, line)
            if start < 0:
                result.warnings.append(f"Could not find HitDef block around line {line} in {_rel(root, path)}")
                continue
            for new_key, real_key in key_map.items():
                value = str(row.get(new_key, "")).strip()
                if value:
                    _replace_key_in_block(lines, start, end, real_key, value)
                    changed += 1
        if changed:
            bak = _backup_text_file(root, path, "hitdef_track_sheet")
            if bak:
                result.notes.append(f"Backup written: {_rel(root, bak)}")
            write_text_safely(path, "\n".join(lines) + "\n")
            result.changed_files.append(_rel(root, path))
            result.notes.append(f"Updated {changed} HitDef field(s) in {_rel(root, path)}.")
    return result


# ---------------------------------------------------------------------------
# Editable StateDef graph
# ---------------------------------------------------------------------------


def build_editable_state_graph(root: Path) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Editable State Graph")
    out = _out(root, "state_graph_editor")
    nodes: Dict[int, Dict[str, object]] = {}
    edges: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception as exc:
            result.warnings.append(f"Could not parse {_rel(root, path)}: {exc}")
            continue
        for st in scan.states:
            nodes.setdefault(st.number, {
                "state": st.number,
                "label": f"State {st.number}",
                "files": [],
                "line": st.line,
                "anim": st.values.get("anim", ""),
                "type": st.values.get("type", ""),
                "movetype": st.values.get("movetype", ""),
                "physics": st.values.get("physics", ""),
                "controller_count": 0,
            })
            nodes[st.number]["files"].append(_rel(root, path))  # type: ignore[index]
            nodes[st.number]["controller_count"] = int(nodes[st.number].get("controller_count", 0)) + len(st.controllers)
            for ctrl in st.controllers:
                ctype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if ctype == "changestate":
                    val = ctrl.values.get("value", "")
                    target = int(val) if re.fullmatch(r"\s*-?\d+\s*", val or "") else None
                    edges.append({
                        "source": st.number,
                        "target": target,
                        "target_expr": val,
                        "kind": "ChangeState",
                        "file": _rel(root, path),
                        "controller_line": ctrl.line,
                        "trigger": "; ".join(v for k, v in ctrl.values.items() if k.startswith("trigger"))[:160],
                        "missing_target": target is not None and target not in nodes,
                    })
                elif ctype == "selfstate":
                    val = ctrl.values.get("value", "")
                    target = int(val) if re.fullmatch(r"\s*-?\d+\s*", val or "") else None
                    edges.append({
                        "source": st.number,
                        "target": target,
                        "target_expr": val,
                        "kind": "SelfState",
                        "file": _rel(root, path),
                        "controller_line": ctrl.line,
                        "trigger": "; ".join(v for k, v in ctrl.values.items() if k.startswith("trigger"))[:160],
                        "missing_target": target is not None and target not in nodes,
                    })
    # Refresh missing flags now all nodes are known.
    known = set(nodes)
    for e in edges:
        target = e.get("target")
        e["missing_target"] = target is not None and target not in known
    positioned = _layout_state_graph(list(nodes.values()), edges)
    payload = {
        "tool": "MugenForge Studio",
        "feature": "Forge Timeline v4.5 Editable State Graph",
        "project": root.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "honest_scope": "Graph is source-analysis and sheet-editable for simple numeric ChangeState/SelfState targets.",
        "nodes": positioned,
        "edges": edges,
        "missing_target_count": sum(1 for e in edges if e.get("missing_target")),
    }
    _write_json(root, out / "editable_state_graph.json", payload, result)
    _write_csv(root, out / "state_graph_nodes.csv", positioned, ["state", "label", "x", "y", "files", "line", "anim", "type", "movetype", "physics", "controller_count"], result)
    _write_csv(root, out / "state_graph_edges.csv", edges, ["source", "target", "target_expr", "kind", "file", "controller_line", "trigger", "missing_target"], result)
    sheet_rows = []
    for e in edges:
        sheet_rows.append({
            "apply": "no",
            "edit_action": "retarget",
            "file": e.get("file", ""),
            "controller_line": e.get("controller_line", ""),
            "source_state": e.get("source", ""),
            "current_target": e.get("target_expr", ""),
            "new_target": "",
            "notes": "For simple numeric ChangeState/SelfState values only. Set apply=yes and new_target to retarget.",
        })
    _write_csv(root, _out(root, "sheets") / "state_graph_edit_sheet.csv", sheet_rows, ["apply", "edit_action", "file", "controller_line", "source_state", "current_target", "new_target", "notes"], result)
    _write_text(root, out / "editable_state_graph.html", _state_graph_html(payload), result)
    try:
        png = _draw_state_graph_png(root, payload, out / "editable_state_graph.png")
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"State graph PNG could not be rendered: {exc}")
    result.notes.append(f"Graph contains {len(positioned)} node(s), {len(edges)} edge(s), {payload['missing_target_count']} missing numeric target(s).")
    return result


def _layout_state_graph(nodes: Sequence[Dict[str, object]], edges: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    rows: Dict[str, List[Dict[str, object]]] = {"negative": [], "common": [], "normal": [], "special": [], "super": [], "other": []}
    for node in sorted(nodes, key=lambda n: int(n.get("state", 0))):
        st = int(node.get("state", 0))
        if st < 0:
            rows["negative"].append(dict(node))
        elif st < 200:
            rows["common"].append(dict(node))
        elif st < 1000:
            rows["normal"].append(dict(node))
        elif st < 3000:
            rows["special"].append(dict(node))
        elif st < 6000:
            rows["super"].append(dict(node))
        else:
            rows["other"].append(dict(node))
    out: List[Dict[str, object]] = []
    y_lookup = {"negative": 40, "common": 160, "normal": 280, "special": 400, "super": 520, "other": 640}
    for bucket, items in rows.items():
        for i, node in enumerate(items):
            node["x"] = 40 + (i % 10) * 180
            node["y"] = y_lookup[bucket] + (i // 10) * 92
            if isinstance(node.get("files"), list):
                node["files"] = "; ".join(str(x) for x in node["files"])
            out.append(node)
    return out


def _state_graph_html(payload: Dict[str, object]) -> str:
    nodes = payload.get("nodes", []) or []
    edges = payload.get("edges", []) or []
    rows = ["<h2>Nodes</h2><table><tr><th>State</th><th>Anim</th><th>Type</th><th>Files</th></tr>"]
    for n in nodes:
        rows.append(f"<tr><td>{n.get('state')}</td><td>{html.escape(str(n.get('anim','')))}</td><td>{html.escape(str(n.get('type','')))}</td><td>{html.escape(str(n.get('files','')))}</td></tr>")
    rows.append("</table><h2>Edges</h2><table><tr><th>Source</th><th>Target</th><th>Kind</th><th>File</th><th>Line</th><th>Warning</th></tr>")
    for e in edges:
        warn = "missing target" if e.get("missing_target") else ""
        rows.append(f"<tr><td>{e.get('source')}</td><td>{html.escape(str(e.get('target_expr','')))}</td><td>{e.get('kind')}</td><td>{html.escape(str(e.get('file','')))}</td><td>{e.get('controller_line')}</td><td>{warn}</td></tr>")
    rows.append("</table>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Editable State Graph</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;}}table{{border-collapse:collapse;}}td,th{{border:1px solid #bbb;padding:4px 8px;font-size:13px;}}th{{background:#eee;}}.note{{background:#fff8d6;padding:10px;border:1px solid #dfc66a;}}</style></head><body>
<h1>Forge Timeline v4.5 Editable State Graph</h1><p class="note">Simple numeric ChangeState/SelfState targets can be retargeted through the CSV sheet. Dynamic expressions are reported but not rewritten automatically.</p>
<p>Project: <b>{html.escape(str(payload.get('project')))}</b>; generated {html.escape(str(payload.get('generated')))}</p>{''.join(rows)}</body></html>"""


def _draw_state_graph_png(root: Path, payload: Dict[str, object], out_path: Path) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for graph PNG rendering. Install with: pip install Pillow") from exc
    nodes = payload.get("nodes", []) or []
    edges = payload.get("edges", []) or []
    width = max(1100, 260 + max((_int(n.get("x"), 0) or 0 for n in nodes), default=0))
    height = max(760, 180 + max((_int(n.get("y"), 0) or 0 for n in nodes), default=0))
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 12)
    except Exception:
        font = bold = None
    draw.text((16, 12), "Forge Timeline v4.5 — Editable State Graph", fill=(0, 0, 0), font=bold)
    pos: Dict[int, Tuple[int, int]] = {}
    for n in nodes:
        st = _int(n.get("state"), 0) or 0
        x = _int(n.get("x"), 40) or 40
        y = _int(n.get("y"), 40) or 40
        pos[st] = (x, y)
    for e in edges:
        s = _int(e.get("source"), None)
        t = _int(e.get("target"), None)
        if s is None or t is None or s not in pos or t not in pos:
            continue
        x1, y1 = pos[s]
        x2, y2 = pos[t]
        draw.line([x1 + 70, y1 + 24, x2, y2 + 24], fill=(180, 90, 90) if e.get("missing_target") else (120, 120, 120), width=2)
    for n in nodes:
        st = _int(n.get("state"), 0) or 0
        x, y = pos.get(st, (40, 40))
        fill = (236, 246, 255)
        if st < 0:
            fill = (245, 245, 245)
        elif st >= 3000:
            fill = (255, 235, 220)
        draw.rectangle([x, y, x + 140, y + 54], fill=fill, outline=(60, 90, 120))
        draw.text((x + 6, y + 6), f"State {st}", fill=(0, 0, 0), font=bold)
        draw.text((x + 6, y + 24), f"anim {n.get('anim','')}", fill=(30, 30, 30), font=font)
        draw.text((x + 6, y + 38), str(n.get("movetype", ""))[:18], fill=(70, 70, 70), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def apply_state_graph_edit_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline State Graph Edit Apply")
    sheet = Path(sheet_path) if sheet_path else root / "forge_timeline" / "sheets" / "state_graph_edit_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"State graph edit sheet not found: {_rel(root, sheet)}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("apply"))]
    if not rows:
        result.skipped_files.append("No rows had apply=yes.")
        return result
    by_file: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        new_target = str(row.get("new_target", "")).strip()
        if not re.fullmatch(r"-?\d+", new_target):
            result.warnings.append(f"Skipped row with non-numeric new_target: {row}")
            continue
        path = (root / str(row.get("file", ""))).resolve()
        if not path.exists():
            result.warnings.append(f"Code file not found: {row.get('file')}")
            continue
        by_file.setdefault(path, []).append(row)
    for path, file_rows in by_file.items():
        lines = read_text_safely(path).splitlines()
        changes = 0
        for row in sorted(file_rows, key=lambda r: _int(r.get("controller_line"), 0) or 0, reverse=True):
            line = _int(row.get("controller_line"), None)
            new_target = str(row.get("new_target", "")).strip()
            if line is None:
                continue
            start, end = _find_controller_block(lines, line)
            if start < 0:
                result.warnings.append(f"Could not find controller block around line {line} in {_rel(root, path)}")
                continue
            _replace_key_in_block(lines, start, end, "value", new_target)
            changes += 1
        if changes:
            bak = _backup_text_file(root, path, "state_graph_edit_sheet")
            if bak:
                result.notes.append(f"Backup written: {_rel(root, bak)}")
            write_text_safely(path, "\n".join(lines) + "\n")
            result.changed_files.append(_rel(root, path))
            result.notes.append(f"Retargeted {changes} state graph edge(s) in {_rel(root, path)}.")
    return result


# ---------------------------------------------------------------------------
# Palette studio
# ---------------------------------------------------------------------------


def _default_palette() -> List[Tuple[int, int, int]]:
    colors: List[Tuple[int, int, int]] = []
    for i in range(256):
        colors.append((i, i, i))
    return colors


def write_palette_studio(root: Path, palette_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Palette Studio")
    out = _out(root, "palette_studio")
    palette_files = _palette_files(root)
    if palette_path:
        palette_files = [Path(palette_path)]
    act_files = [p for p in palette_files if p.suffix.lower() == ".act" and p.exists()]
    if not act_files:
        starter = out / "starter_grayscale.act"
        write_act(starter, _default_palette())
        act_files = [starter]
        result.created_files.append(_rel(root, starter))
        result.warnings.append("No ACT palette found; created a starter grayscale ACT for editing.")
    rows: List[Dict[str, object]] = []
    first_info = None
    for pal in act_files:
        try:
            info = read_act(pal)
        except Exception as exc:
            result.warnings.append(f"Could not read palette {_rel(root, pal)}: {exc}")
            continue
        if first_info is None:
            first_info = info
        for idx, (r, g, b) in enumerate(info.colors[:256]):
            rows.append({
                "apply": "no",
                "source_palette": _rel(root, pal),
                "index": idx,
                "r": r, "g": g, "b": b,
                "hex": f"#{r:02X}{g:02X}{b:02X}",
                "new_r": "", "new_g": "", "new_b": "", "new_hex": "",
                "transparent": "yes" if idx == 0 else "no",
                "output_name": f"{Path(pal).stem}_forge_variant.act",
                "notes": "Set apply=yes on changed rows. Output is a new ACT file; source is not overwritten.",
            })
    fields = ["apply", "source_palette", "index", "r", "g", "b", "hex", "new_r", "new_g", "new_b", "new_hex", "transparent", "output_name", "notes"]
    _write_csv(root, _out(root, "sheets") / "palette_editor_sheet.csv", rows, fields, result)
    if first_info:
        try:
            grid = _draw_palette_grid(root, first_info.colors, out / "palette_grid.png", title=f"Palette: {_rel(root, first_info.path)}")
            result.add_created(root, grid)
        except Exception as exc:
            result.warnings.append(f"Palette grid PNG could not be rendered: {exc}")
    html_rows = [f"<tr><td>{row['index']}</td><td>{row['hex']}</td><td style='background:{row['hex']}'>&nbsp;</td></tr>" for row in rows[:256]]
    _write_text(root, out / "palette_studio.html", f"""<!doctype html><html><head><meta charset="utf-8"><title>Palette Studio</title><style>body{{font-family:Arial,sans-serif;margin:24px;}}table{{border-collapse:collapse;}}td,th{{border:1px solid #bbb;padding:4px 8px;}}</style></head><body><h1>Forge Timeline v4.5 Palette Studio</h1><p>ACT editing is sheet-backed and writes a new variant ACT. PAL variants are listed but not rewritten by this workflow.</p><table><tr><th>Index</th><th>Hex</th><th>Swatch</th></tr>{''.join(html_rows)}</table></body></html>""", result)
    result.notes.append(f"Palette sheet rows: {len(rows)}. Source palettes are not overwritten by apply.")
    return result


def _draw_palette_grid(root: Path, colors: Sequence[Tuple[int, int, int]], out_path: Path, title: str = "Palette") -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for palette grid rendering. Install with: pip install Pillow") from exc
    cell = 34
    cols = 16
    rows = 16
    top = 52
    img = Image.new("RGB", (cols * cell + 1, top + rows * cell + 1), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 9)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 12)
    except Exception:
        font = bold = None
    draw.text((8, 8), title[:80], fill=(0, 0, 0), font=bold)
    draw.text((8, 28), "Index 0 is commonly transparent; verify per character.", fill=(70, 70, 70), font=font)
    for idx, color in enumerate(list(colors)[:256]):
        x = (idx % cols) * cell
        y = top + (idx // cols) * cell
        draw.rectangle([x, y, x + cell, y + cell], fill=tuple(color), outline=(80, 80, 80))
        lum = (color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114)
        text_color = (0, 0, 0) if lum > 145 else (255, 255, 255)
        draw.text((x + 3, y + 3), str(idx), fill=text_color, font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _parse_hex(value: str) -> Optional[Tuple[int, int, int]]:
    value = str(value or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return None


def apply_palette_editor_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Palette Editor Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else root / "forge_timeline" / "sheets" / "palette_editor_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"Palette editor sheet not found: {_rel(root, sheet)}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("apply"))]
    if not rows:
        result.skipped_files.append("No rows had apply=yes.")
        return result
    by_source: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        by_source.setdefault(row.get("source_palette", ""), []).append(row)
    out = _out(root, "palette_studio", "variants")
    for source, source_rows in by_source.items():
        src = (root / source).resolve()
        if src.exists() and src.suffix.lower() == ".act":
            info = read_act(src)
            colors = list(info.colors)
        else:
            colors = _default_palette()
            result.warnings.append(f"Source ACT not found; used grayscale base for {source!r}.")
        raw_output = Path(source_rows[0].get("output_name") or (Path(source).stem + "_forge_variant.act")).name
        output_name = _safe_name(Path(raw_output).stem) + ".act"
        changes = 0
        for row in source_rows:
            idx = _int(row.get("index"), None)
            if idx is None or not (0 <= idx < 256):
                result.warnings.append(f"Skipped palette row with invalid index: {row}")
                continue
            rgb = _parse_hex(row.get("new_hex", ""))
            if rgb is None:
                r = _int(row.get("new_r"), None)
                g = _int(row.get("new_g"), None)
                b = _int(row.get("new_b"), None)
                if r is None or g is None or b is None:
                    continue
                rgb = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
            if colors[idx] != rgb:
                colors[idx] = rgb
                changes += 1
        dst = out / output_name
        write_act(dst, colors)
        result.created_files.append(_rel(root, dst))
        try:
            grid = _draw_palette_grid(root, colors, dst.with_suffix(".png"), title=f"Variant: {output_name}")
            result.created_files.append(_rel(root, grid))
        except Exception as exc:
            result.warnings.append(f"Variant grid could not be rendered: {exc}")
        result.notes.append(f"Wrote {output_name} with {changes} color change(s).")
    return result


# ---------------------------------------------------------------------------
# Stage live preview
# ---------------------------------------------------------------------------


def _parse_stage_def(path: Path) -> Dict[str, Dict[str, str]]:
    text = read_text_safely(path)
    sections: Dict[str, Dict[str, str]] = {}
    current = ""
    sec_re = re.compile(r"^\s*\[([^\]]+)\]")
    kv_re = re.compile(r"^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$")
    for line in text.splitlines():
        sm = sec_re.match(line)
        if sm:
            current = sm.group(1).strip().lower()
            sections.setdefault(current, {})
            continue
        km = kv_re.match(line)
        if km and current:
            sections[current][km.group(1).strip().lower()] = km.group(2).strip().strip('"')
    return sections


def _find_stage_def(root: Path) -> Optional[Path]:
    candidates = []
    for p in sorted(Path(root).rglob("*.def"), key=lambda x: str(x).lower()):
        try:
            text = read_text_safely(p)[:50000]
        except Exception:
            continue
        score = 0
        for marker in ("[Camera]", "[BGDef]", "[Bound]", "[StageInfo]", "[Scaling]"):
            if marker.lower() in text.lower():
                score += 1
        if score:
            candidates.append((score, p))
    if candidates:
        return sorted(candidates, key=lambda x: (-x[0], str(x[1]).lower()))[0][1]
    return None


def _find_stage_image(root: Path, stage_def: Optional[Path], sections: Dict[str, Dict[str, str]]) -> Optional[Path]:
    if stage_def:
        for sec, vals in sections.items():
            if sec.startswith("bg"):
                for key in ("spriteno", "filename", "file"):
                    ref = vals.get(key)
                    if ref:
                        p = (stage_def.parent / ref).resolve()
                        if p.exists() and p.suffix.lower() in IMAGE_SUFFIXES:
                            return p
        for folder in (stage_def.parent, stage_def.parent / "stages", stage_def.parent / "sprites", stage_def.parent / "images"):
            if folder.exists():
                imgs = [p for p in sorted(folder.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
                if imgs:
                    return imgs[0]
    imgs = _image_files(root, include_generated=False)
    return imgs[0] if imgs else None


def write_stage_live_preview(root: Path, stage_def_path: Optional[Path] = None, image_path: Optional[Path] = None) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Stage Live Preview")
    out = _out(root, "stage_live_preview")
    stage_def = Path(stage_def_path) if stage_def_path else _find_stage_def(root)
    sections: Dict[str, Dict[str, str]] = {}
    if stage_def and stage_def.exists():
        sections = _parse_stage_def(stage_def)
    else:
        result.warnings.append("No stage DEF detected. Preview will use a generic camera/bounds overlay.")
    image = Path(image_path) if image_path else _find_stage_image(root, stage_def, sections)
    camera = sections.get("camera", {})
    bound = sections.get("bound", {})
    stageinfo = sections.get("stageinfo", {})
    data = {
        "tool": "MugenForge Studio",
        "feature": "Forge Timeline v4.5 Stage Live Preview",
        "project": root.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "stage_def": _rel(root, stage_def) if stage_def else "",
        "source_image": _rel(root, image) if image else "",
        "camera": camera,
        "bound": bound,
        "stageinfo": stageinfo,
        "honest_scope": "Approximate stage/source-art preview. It does not emulate M.U.G.E.N rendering, parallax, or BGCtrl timing authoritatively.",
    }
    _write_json(root, out / "stage_live_preview_model.json", data, result)
    _write_text(root, out / "stage_live_preview.html", _stage_preview_html(data), result)
    try:
        png = _draw_stage_preview(root, data, image, out / "stage_live_preview.png")
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"Stage preview PNG could not be rendered: {exc}")
    result.notes.append("Stage preview is approximate and source-art based, not engine-authoritative.")
    return result


def _stage_preview_html(data: Dict[str, object]) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Stage Live Preview</title><style>body{{font-family:Arial,sans-serif;margin:24px;}}pre{{background:#f4f4f4;padding:12px;}}</style></head><body><h1>Forge Timeline v4.5 Stage Live Preview</h1><p>This is an approximate source-art preview, not a M.U.G.E.N renderer.</p><p>Stage DEF: {html.escape(str(data.get('stage_def')))}<br>Source image: {html.escape(str(data.get('source_image')))}</p><pre>{html.escape(json.dumps(data, indent=2, ensure_ascii=False))}</pre></body></html>"""


def _draw_stage_preview(root: Path, data: Dict[str, object], image_path: Optional[Path], out_path: Path) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for stage preview rendering. Install with: pip install Pillow") from exc
    canvas_w, canvas_h = 640, 480
    bg = Image.new("RGB", (canvas_w, canvas_h), (235, 238, 242))
    draw = ImageDraw.Draw(bg)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
        bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = bold = None
    if image_path and Path(image_path).exists():
        try:
            src = Image.open(image_path).convert("RGB")
            src.thumbnail((canvas_w, canvas_h))
            x = (canvas_w - src.width) // 2
            y = (canvas_h - src.height) // 2
            bg.paste(src, (x, y))
        except Exception:
            pass
    else:
        # horizon/floor placeholder
        draw.rectangle([0, 0, canvas_w, canvas_h // 2], fill=(220, 230, 240))
        draw.rectangle([0, canvas_h // 2, canvas_w, canvas_h], fill=(210, 205, 198))
        for x in range(0, canvas_w, 32):
            draw.line([x, canvas_h // 2, x - 80, canvas_h], fill=(190, 185, 178))
        for y in range(canvas_h // 2, canvas_h, 30):
            draw.line([0, y, canvas_w, y], fill=(190, 185, 178))
    camera = data.get("camera", {}) if isinstance(data.get("camera"), dict) else {}
    bound = data.get("bound", {}) if isinstance(data.get("bound"), dict) else {}
    # Approximate camera rectangle and ground axis.
    draw.rectangle([60, 50, canvas_w - 60, canvas_h - 80], outline=(255, 255, 0), width=3)
    draw.line([0, canvas_h - 110, canvas_w, canvas_h - 110], fill=(255, 80, 80), width=2)
    draw.text((16, 12), "Forge Timeline v4.5 — Approximate Stage Preview", fill=(0, 0, 0), font=bold)
    draw.text((16, 32), "Yellow: nominal camera / Red: ground axis. Not an engine renderer.", fill=(30, 30, 30), font=font)
    info = []
    for key in ("startx", "starty", "boundleft", "boundright", "boundhigh", "boundlow", "verticalfollow", "floortension"):
        if key in camera:
            info.append(f"{key}={camera[key]}")
        if key in bound:
            info.append(f"{key}={bound[key]}")
    draw.rectangle([8, canvas_h - 58, canvas_w - 8, canvas_h - 8], fill=(255, 255, 255), outline=(160, 160, 160))
    draw.text((14, canvas_h - 51), (" | ".join(info) or "No camera/bound data detected")[:110], fill=(0, 0, 0), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Dashboards/bundle/pass
# ---------------------------------------------------------------------------


def write_forge_timeline_dashboard(root: Path) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Dashboard")
    audit = scan_project(root)
    air_path, actions = _read_air_actions(root)
    events = _code_events(root)
    hitdefs = sum(1 for e in events if e.get("type") == "hitdef")
    sounds = sum(1 for e in events if e.get("type") == "playsnd")
    states = _state_records(root)
    palettes = _palette_files(root)
    score = 100
    score -= min(35, 7 * len(audit.missing_required))
    score -= min(20, 4 * len(audit.missing_references))
    if not actions:
        score -= 12
    if not states:
        score -= 12
    if not hitdefs:
        score -= 8
    if not sounds:
        score -= 3
    score = max(0, min(100, score))
    next_steps = []
    if not actions:
        next_steps.append("Create or import AIR actions before using timeline edits.")
    if not hitdefs:
        next_steps.append("Add or import at least one HitDef, then tune it through the HitDef track sheet.")
    next_steps.extend([
        "Use Move Timeline Edit Sheet for timing/offset changes and PlaySnd additions.",
        "Use CLSN Track Sheet for explicit per-frame hit/hurt boxes.",
        "Use HitDef Track Sheet for attack values, pushback, sparks, and sounds.",
        "Use Editable State Graph to find broken numeric ChangeState targets.",
        "Use Palette Studio to create ACT variants without overwriting source palettes.",
        "Use Stage Live Preview as an approximate layout aid only.",
    ])
    md = [
        "# Forge Timeline v4.5 Dashboard", "", f"Project: **{root.name}**", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", f"## Editor readiness score: {score}/100", "", "## Source counts", "", f"- AIR file: {_rel(root, air_path) if air_path else 'missing'}", f"- AIR actions: {len(actions)}", f"- StateDefs: {len(states)}", f"- Source events/controllers tracked: {len(events)}", f"- HitDefs: {hitdefs}", f"- PlaySnd controllers: {sounds}", f"- Palettes: {len(palettes)}", f"- Missing required file types: {', '.join(audit.missing_required) if audit.missing_required else 'none'}", "", "## Do next", "",
    ] + [f"- [ ] {step}" for step in next_steps] + ["", "## Honest limits", "", "- This release adds source/sheet-backed visual editing workflows. It still does not implement full arbitrary mature SFF v2 binary extraction/rebuild/mutation.", "- Timeline, graph, frame-data, palette, and stage previews are source-analysis aids; real M.U.G.E.N playtesting remains required.", "- SND/SFF binary mutation remains conservative; sound cues insert source PlaySnd controllers rather than patching SND binaries."]
    out = _out(root)
    _write_text(root, out / "FORGE_TIMELINE_DASHBOARD.md", "\n".join(md), result)
    html_text = "<br>".join(html.escape(line) for line in md)
    _write_text(root, out / "FORGE_TIMELINE_DASHBOARD.html", f"<!doctype html><html><head><meta charset='utf-8'><title>Forge Timeline Dashboard</title><style>body{{font-family:Arial,sans-serif;margin:24px;line-height:1.45;}}</style></head><body>{html_text}</body></html>", result)
    return result


def build_forge_timeline_bundle(root: Path) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline Reports Bundle")
    out_dir = root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{_safe_name(root.name)}_forge_timeline_v4_5_reports.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for base in (root / "forge_timeline", root / "docs"):
            if not base.exists():
                continue
            for path in sorted(base.rglob("*"), key=lambda p: str(p).lower()):
                if path.is_file():
                    zf.write(path, path.relative_to(root))
    result.created_files.append(_rel(root, zip_path))
    result.notes.append("Packaged Forge Timeline reports/sheets/previews only; this is not the playable character release ZIP.")
    return result


def run_forge_timeline_pass(root: Path) -> ForgeTimelineResult:
    root = Path(root)
    result = ForgeTimelineResult("Forge Timeline v4.5 One-Click Pass")
    if create_backup_snapshot is not None:
        try:
            result.merge(create_backup_snapshot(root, "forge_timeline_v4_5"), "snapshot")
        except Exception as exc:
            result.warnings.append(f"Snapshot skipped: {exc}")
    result.merge(write_forge_timeline_dashboard(root), "dashboard")
    result.merge(build_integrated_move_timeline_model(root), "timeline")
    result.merge(export_move_timeline_edit_sheet(root), "move_sheet")
    result.merge(export_clsn_track_sheet(root), "clsn_sheet")
    result.merge(export_hitdef_track_sheet(root), "hitdef_sheet")
    result.merge(build_editable_state_graph(root), "state_graph")
    result.merge(write_palette_studio(root), "palette")
    result.merge(write_stage_live_preview(root), "stage")
    start = """# Forge Timeline v4.5 Start Here

This release makes the editor feel more like a unified visual production surface while staying conservative about binary mutation.

Open these first:

1. `forge_timeline/FORGE_TIMELINE_DASHBOARD.md`
2. `forge_timeline/move_timeline/integrated_move_timeline.png`
3. `forge_timeline/sheets/move_timeline_edit_sheet.csv`
4. `forge_timeline/sheets/clsn_track_sheet.csv`
5. `forge_timeline/sheets/hitdef_track_sheet.csv`
6. `forge_timeline/state_graph_editor/editable_state_graph.png`
7. `forge_timeline/sheets/state_graph_edit_sheet.csv`
8. `forge_timeline/palette_studio/palette_grid.png`
9. `forge_timeline/stage_live_preview/stage_live_preview.png`

Safety workflow:

- Edit CSV rows.
- Set only intended rows to `apply=yes`.
- Apply from the Forge Timeline tab.
- Review backups under `backups/forge_timeline_file_backups/`.
- Playtest in M.U.G.E.N before trusting balance or timing.

Honest limit: this is source/sheet-backed editing, not full arbitrary mature SFF v2 binary editing/rebuilding.
"""
    _write_text(root, root / "forge_timeline" / "FORGE_TIMELINE_START_HERE.md", start, result)
    result.merge(build_forge_timeline_bundle(root), "bundle")
    return result
