from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import traceback
import zipfile
from typing import Dict, Iterable, List, Optional

from .artifact_io import rel_path as _rel, write_csv_artifact, write_json_artifact, write_text_artifact
from .parsers import (
    COMMON_ANIMS,
    parse_air,
    parse_code,
    read_text_safely,
    scan_project,
    write_text_safely,
    make_new_character,
)
from .air_tools import parse_air_with_lines, find_frame
from .move_wizard import MoveWizardSpec, append_move_to_project, build_move_package, find_character_file, normalize_spec
from .automation_bank import apply_beginner_pack, apply_preset
from .sff_codec import read_sff, sprite_lookup
from .snd_codec import read_snd
from .sff2_bridge import write_sff2_bridge_guide, write_sprmake2_bridge_project, create_sff2_source_pack_zip

VISUAL_FORGE_VERSION = "3.5.0"
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg", ".csv"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".snd"}
SKIP_BACKUP_PARTS = {"__pycache__", ".git", "exports", "backups", "visual_forge_backups"}


from .shared_utils import BaseResult, uniq as _uniq

@dataclass
class VisualForgeResult(BaseResult):
    title: str = "Visual Forge Result"


@dataclass
class BeginnerProjectSpec:
    name: str = "new_character"
    author: str = "MugenForge Creator"
    project_type: str = "character"  # character or stage starter metadata; stage creation remains template-based elsewhere.
    template: str = "Balanced Starter"
    archetype: str = "Balanced Arcade Fighter"
    life: int = 1000
    attack: int = 100
    defence: int = 100
    power_style: str = "classic"
    notes: str = ""

    @property
    def safe_name(self) -> str:
        return _safe_name(self.name)


@dataclass
class TimelineSelection:
    action_number: int
    frame_index: int
    ticks: int
    x: int
    y: int


@dataclass
class SoundCueSpec:
    state_no: int = 200
    frame: int = 2
    sound_group: int = 5
    sound_index: int = 0
    channel: int = 0
    label: str = "Visual Forge cue"


@dataclass
class MigrationSpec:
    source_root: Path
    destination_parent: Path
    new_name: str = ""
    copy_assets: bool = True
    write_guidance: bool = True


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(name or "")).strip("_") or "new_character"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")





def _vf_dir(root: Path) -> Path:
    out = Path(root) / "visual_forge"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _docs_dir(root: Path) -> Path:
    out = Path(root) / "docs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(root: Path, path: Path, text: str, result: Optional[VisualForgeResult] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, track_existing=True)


def _write_json(root: Path, path: Path, payload: object, result: Optional[VisualForgeResult] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, payload, result, root, changed, track_existing=True)


def backup_file(path: Path, root: Optional[Path] = None, reason: str = "visual_forge") -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    base = Path(root) if root else path.parent
    backup_root = base / "backups" / "visual_forge_file_backups"
    try:
        backup_root.mkdir(parents=True, exist_ok=True)
        rel = path.resolve().relative_to(base.resolve()) if root else Path(path.name)
        dst = backup_root / rel.with_name(rel.name + f".bak_{reason}_{_timestamp()}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
        return dst
    except Exception:
        dst = path.with_name(path.name + f".bak_{reason}_{_timestamp()}")
        shutil.copy2(path, dst)
        return dst


def log_error(root: Path, context: str, exc: BaseException | str) -> Path:
    root = Path(root)
    log = _vf_dir(root) / "error_log.txt"
    msg = str(exc)
    details = "" if isinstance(exc, str) else "\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {context}: {msg}{details}\n")
    return log


def _replace_or_add_kv(text: str, section: str, key: str, value: object) -> str:
    lines = text.splitlines()
    sec_re = re.compile(r"^\s*\[\s*" + re.escape(section) + r"\s*\]", re.I)
    any_sec_re = re.compile(r"^\s*\[.+\]")
    key_re = re.compile(r"^\s*" + re.escape(key) + r"\s*=", re.I)
    out: List[str] = []
    in_section = False
    section_seen = False
    key_done = False
    inserted = False
    for line in lines:
        if sec_re.match(line):
            in_section = True
            section_seen = True
            out.append(line)
            continue
        if in_section and any_sec_re.match(line):
            if not key_done:
                out.append(f"{key} = {value}")
                key_done = True
                inserted = True
            in_section = False
        if in_section and key_re.match(line):
            if not key_done:
                out.append(f"{key} = {value}")
                key_done = True
            continue
        out.append(line)
    if section_seen and in_section and not key_done:
        out.append(f"{key} = {value}")
        inserted = True
    if not section_seen:
        if out and out[-1].strip():
            out.append("")
        out.extend([f"[{section}]", f"{key} = {value}"])
        inserted = True
    return "\n".join(out).rstrip() + "\n"


def _int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _first_int(value: object, default: Optional[int] = None) -> Optional[int]:
    m = re.search(r"-?\d+", str(value or ""))
    return int(m.group(0)) if m else default


def create_visual_forge_project(parent: Path, spec: BeginnerProjectSpec, install_pack: bool = True) -> VisualForgeResult:
    """Create a beginner-friendly starter project and write Visual Forge metadata.

    The generated gameplay remains starter scaffolding. This function intentionally
    does not make SFF2 binary claims or mutate mature existing binary assets.
    """
    parent = Path(parent)
    result = VisualForgeResult("Beginner Project Wizard")
    char_dir = make_new_character(parent, spec.safe_name)
    result.add_created(parent, char_dir)

    def_path = find_character_file(char_dir, "def")
    if def_path and def_path.exists():
        text = read_text_safely(def_path)
        for key, value in (
            ("name", f'"{spec.safe_name}"'),
            ("displayname", f'"{spec.name.strip() or spec.safe_name}"'),
            ("author", f'"{spec.author.strip() or "MugenForge Creator"}"'),
        ):
            text = _replace_or_add_kv(text, "Info", key, value)
        backup_file(def_path, char_dir, "wizard")
        write_text_safely(def_path, text)
        result.add_changed(char_dir, def_path)

    cns = find_character_file(char_dir, "cns")
    if cns and cns.exists():
        text = read_text_safely(cns)
        for key, value in (("life", spec.life), ("attack", spec.attack), ("defence", spec.defence)):
            text = _replace_or_add_kv(text, "Data", key, int(value))
        backup_file(cns, char_dir, "wizard")
        write_text_safely(cns, text)
        result.add_changed(char_dir, cns)

    if install_pack:
        try:
            pack = apply_beginner_pack(char_dir)
            result.merge(pack, "Beginner Pack")
        except Exception as exc:
            result.warnings.append(f"Beginner Pack install failed: {exc}")
            log_error(char_dir, "Beginner Pack install", exc)

    result.merge(write_beginner_project_home(char_dir, spec), "Project Home")
    result.merge(install_template_architecture(char_dir), "Templates")
    result.notes.append("Created a no-code starter project with Visual Forge metadata, beginner guide, templates, and optional beginner move scaffolds.")
    result.notes.append("Gameplay code is starter scaffolding and still needs real M.U.G.E.N playtesting and tuning.")
    return result


def write_beginner_project_home(root: Path, spec: Optional[BeginnerProjectSpec] = None) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Visual Forge Home Files")
    spec = spec or BeginnerProjectSpec(name=root.name)
    profile = {
        "tool": "MugenForge Studio",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "project_name": spec.name,
        "safe_name": spec.safe_name,
        "author": spec.author,
        "project_type": spec.project_type,
        "template": spec.template,
        "archetype": spec.archetype,
        "stats": {"life": spec.life, "attack": spec.attack, "defence": spec.defence},
        "power_style": spec.power_style,
        "created_or_updated": datetime.now().isoformat(timespec="seconds"),
        "honest_limits": [
            "Visual Forge edits text assets and staged source manifests safely; it does not perform arbitrary mature SFF v2 binary rewriting.",
            "Generated CMD/CNS/AIR gameplay is starter scaffolding and requires engine testing.",
            "Frame data and balance reports are estimates, not engine-authoritative measurements.",
        ],
        "recommended_workflow": [
            "Open Project Home and run Quick Start.",
            "Use Move Composer 2.0 to scaffold a move.",
            "Use Visual Timeline to adjust frame timing and review hit/sound events.",
            "Use Sprite Offset / Axis Editor to align AIR frame offsets or staged manifest axes.",
            "Use Sound Cue Editor to place PlaySnd triggers.",
            "Use Training Debug Pack, Quality Lab, and release ZIP checks before sharing.",
        ],
    }
    _write_json(root, _vf_dir(root) / "project_home.json", profile, result)
    guide = f"""# Visual Forge Start Here

Project: **{spec.name or root.name}**
Author: **{spec.author}**
Template: **{spec.template}**
Archetype: **{spec.archetype}**

## Beginner workflow

1. Use **Move Composer 2.0** to scaffold moves without writing CMD/CNS/AIR by hand.
2. Use **Visual Timeline** to inspect frames, timing, hitbox presence, HitDef events, and sound cues.
3. Use **Sprite Offset / Axis Editor** to align frame offsets visually. Existing SFF binary axes are inspected; arbitrary SFF2 axis mutation is not claimed.
4. Use **Sound Cue Editor** to place `PlaySnd` triggers safely into a target state.
5. Use **Backups / Logs** before larger edits. Visual Forge writes central snapshots and file-level backups for its own mutating tools.
6. Use **Quality Lab** and **Run / Test** for playtesting. Generated code is only a starter.

## Honest limits

- Full arbitrary mature SFF v2 extraction/rebuild is still not implemented.
- SFF2 Bridge remains source-based: it writes Sprmake2-ready source projects and guides rather than silently patching SFF2 binaries.
- SFF/SND mutation remains conservative.
- Generated gameplay code, frame data, and balance outputs are not engine-authoritative and need testing.
"""
    _write_text(root, _docs_dir(root) / "VISUAL_FORGE_START_HERE.md", guide, result)
    dashboard = f"""# MugenForge Visual Forge Dashboard

## Current next actions

- [ ] Open **Visual Timeline** and inspect the first move animation.
- [ ] Align sprite offsets in **Sprite Offset / Axis Editor**.
- [ ] Add or verify sound cues in **Sound Cue Editor**.
- [ ] Create one central backup snapshot before major edits.
- [ ] Run a project audit and playtest in M.U.G.E.N.

## Creative decisions to make

- Character silhouette and movement feel.
- Move rhythm: startup, active frames, recovery.
- Hitbox shape and risk/reward.
- Sound placement and impact feedback.
- Balance after actual playtesting.

Generated: {datetime.now().isoformat(timespec='seconds')}
"""
    _write_text(root, _docs_dir(root) / "VISUAL_FORGE_DASHBOARD.md", dashboard, result)
    return result


def _code_files(root: Path) -> List[Path]:
    root = Path(root)
    files: List[Path] = []
    for pat in ("*.cmd", "*.cns", "*.st"):
        files.extend(sorted(root.rglob(pat), key=lambda p: str(p).lower()))
    return [p for p in files if p.is_file() and not any(part in SKIP_BACKUP_PARTS for part in p.parts)]


def _extract_anim_elem(values: Dict[str, str], default: int = 1) -> int:
    for key, value in values.items():
        if not key.lower().startswith("trigger"):
            continue
        m = re.search(r"AnimElem\s*(?:=|>=|<=|>|<)?\s*(-?\d+)", value, re.I)
        if m:
            return max(1, int(m.group(1)))
    return default


def _collect_code_events(root: Path) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            anim = _first_int(state.values.get("anim"), state.number)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).strip().lower()
                if stype not in {"hitdef", "playsnd", "projectile", "helper", "explod", "changestate"}:
                    continue
                frame = _extract_anim_elem(ctrl.values, 1)
                event: Dict[str, object] = {
                    "event_type": stype or "controller",
                    "state": state.number,
                    "anim": anim,
                    "frame": frame,
                    "source_file": _rel(root, path),
                    "line": ctrl.line,
                    "header": ctrl.header,
                }
                if stype == "playsnd":
                    event["value"] = ctrl.values.get("value", "")
                    event["channel"] = ctrl.values.get("channel", "")
                if stype in {"hitdef", "projectile"}:
                    event["damage"] = ctrl.values.get("damage", "")
                    event["attr"] = ctrl.values.get("attr", "")
                    event["hitsound"] = ctrl.values.get("hitsound", "")
                if stype == "changestate":
                    event["target_state"] = ctrl.values.get("value", "")
                events.append(event)
    return events


def build_visual_timeline_model(root: Path, action_number: Optional[int] = None) -> Dict[str, object]:
    root = Path(root)
    air_path = find_character_file(root, "air")
    if not air_path or not air_path.exists():
        return {"project": root.name, "air_file": None, "actions": [], "warnings": ["No AIR file found."]}
    actions = parse_air(read_text_safely(air_path))
    code_events = _collect_code_events(root)
    requested = [a for a in actions if action_number is None or a.number == int(action_number)]
    model_actions: List[Dict[str, object]] = []
    for action in requested:
        cursor = 0
        frames: List[Dict[str, object]] = []
        for idx, frame in enumerate(action.frames):
            ticks = max(1, int(frame.ticks))
            boxes = [
                {"kind": b.kind, "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}
                for b in frame.clsn
            ]
            clsn1 = sum(1 for b in frame.clsn if b.kind.lower() == "clsn1")
            clsn2 = sum(1 for b in frame.clsn if b.kind.lower() == "clsn2")
            frames.append({
                "index": idx,
                "elem": idx + 1,
                "group": frame.group,
                "image": frame.image,
                "offset_x": frame.x,
                "offset_y": frame.y,
                "ticks": ticks,
                "time_start_tick": cursor,
                "time_end_tick": cursor + ticks,
                "flags": frame.flags,
                "clsn1_count": clsn1,
                "clsn2_count": clsn2,
                "has_hitbox": clsn1 > 0,
                "has_bodybox": clsn2 > 0,
                "boxes": boxes,
            })
            cursor += ticks
        events = [e for e in code_events if _int(e.get("anim"), -999999) == action.number]
        model_actions.append({
            "action": action.number,
            "label": action.label or COMMON_ANIMS.get(action.number, ""),
            "frames": frames,
            "events": events,
            "total_ticks": cursor,
            "estimated_seconds_at_60fps": round(cursor / 60.0, 4),
        })
    return {
        "tool": "MugenForge Visual Forge",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "project": root.name,
        "air_file": _rel(root, air_path),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "actions": model_actions,
        "warnings": [],
    }


def write_visual_timeline_manifest(root: Path, action_number: Optional[int] = None) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Visual Move Timeline Manifest")
    model = build_visual_timeline_model(root, action_number)
    out = _vf_dir(root) / "timeline_manifest.json"
    _write_json(root, out, model, result)
    csv_path = _vf_dir(root) / "timeline_frames.csv"
    rows: List[Dict[str, object]] = []
    for action in model.get("actions", []):
        for frame in action.get("frames", []):
            rows.append({
                "action": action.get("action", ""),
                "label": action.get("label", ""),
                "frame_index": frame.get("index", ""),
                "elem": frame.get("elem", ""),
                "group": frame.get("group", ""),
                "image": frame.get("image", ""),
                "offset_x": frame.get("offset_x", ""),
                "offset_y": frame.get("offset_y", ""),
                "ticks": frame.get("ticks", ""),
                "clsn1_count": frame.get("clsn1_count", ""),
                "clsn2_count": frame.get("clsn2_count", ""),
            })
    fields = ["action", "label", "frame_index", "elem", "group", "image", "offset_x", "offset_y", "ticks", "clsn1_count", "clsn2_count"]
    write_csv_artifact(csv_path, rows, fields, result, root, track_existing=True)
    result.notes.append("Timeline manifest is source-derived from AIR and parsed code controllers. It is not an engine-authoritative frame-data capture.")
    return result


def _format_air_frame_line(frame, *, ticks: Optional[int] = None, offset_x: Optional[int] = None, offset_y: Optional[int] = None) -> str:
    x = frame.x if offset_x is None else int(offset_x)
    y = frame.y if offset_y is None else int(offset_y)
    t = frame.ticks if ticks is None else max(1, int(ticks))
    line = f"{frame.group}, {frame.image}, {x}, {y}, {t}"
    if frame.flags:
        line += f", {frame.flags}"
    return line


def update_air_frame_ticks(root: Path, action_number: int, frame_index: int, ticks: int) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Visual Timeline Tick Update")
    air_path = find_character_file(root, "air")
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    text = read_text_safely(air_path)
    actions = parse_air_with_lines(text)
    frame = find_frame(actions, int(action_number), int(frame_index))
    if frame is None:
        result.warnings.append(f"Action {action_number} frame {frame_index} not found.")
        return result
    lines = text.splitlines()
    backup = backup_file(air_path, root, "timeline_ticks")
    if backup:
        result.add_created(root, backup)
    lines[frame.line_index] = _format_air_frame_line(frame, ticks=max(1, int(ticks)))
    write_text_safely(air_path, "\n".join(lines).rstrip() + "\n")
    result.add_changed(root, air_path)
    result.notes.append(f"Updated Action {action_number} frame {frame_index + 1} to {max(1, int(ticks))} tick(s).")
    return result


def update_air_frame_offset(root: Path, action_number: int, frame_index: int, offset_x: int, offset_y: int) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Sprite Offset Update")
    air_path = find_character_file(root, "air")
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    text = read_text_safely(air_path)
    actions = parse_air_with_lines(text)
    frame = find_frame(actions, int(action_number), int(frame_index))
    if frame is None:
        result.warnings.append(f"Action {action_number} frame {frame_index} not found.")
        return result
    lines = text.splitlines()
    backup = backup_file(air_path, root, "offset")
    if backup:
        result.add_created(root, backup)
    lines[frame.line_index] = _format_air_frame_line(frame, offset_x=int(offset_x), offset_y=int(offset_y))
    write_text_safely(air_path, "\n".join(lines).rstrip() + "\n")
    result.add_changed(root, air_path)
    result.notes.append(f"Updated Action {action_number} frame {frame_index + 1} AIR offset to ({int(offset_x)}, {int(offset_y)}).")
    result.notes.append("This edits AIR frame offsets. It does not patch arbitrary SFF/SFF2 binary sprite-axis records.")
    return result


def build_sprite_offset_model(root: Path, action_number: Optional[int] = None) -> Dict[str, object]:
    model = build_visual_timeline_model(root, action_number)
    root = Path(root)
    sff_path = find_character_file(root, "sff")
    sff_axes: Dict[str, Dict[str, object]] = {}
    warnings: List[str] = []
    if sff_path and sff_path.exists():
        try:
            info = read_sff(sff_path)
            for sprite in info.sprites:
                sff_axes[f"{sprite.group},{sprite.image}"] = {"x": sprite.x, "y": sprite.y, "format": sprite.format_hint, "index": sprite.index}
            warnings.extend(info.warnings)
        except Exception as exc:
            warnings.append(f"SFF axis inspection failed: {exc}")
    model["sff_axis_reference"] = sff_axes
    model.setdefault("warnings", []).extend(warnings)
    model["axis_editor_note"] = "Visual Forge can edit AIR frame offsets and staged source manifest axes. It does not claim arbitrary SFF2 binary axis patching."
    return model


def write_sound_cue_manifest(root: Path) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Sound Cue Manifest")
    events = [e for e in _collect_code_events(root) if str(e.get("event_type", "")).lower() == "playsnd"]
    snd_path = find_character_file(root, "snd")
    sounds: List[Dict[str, object]] = []
    if snd_path and snd_path.exists():
        try:
            info = read_snd(snd_path)
            for s in info.sounds:
                sounds.append({"id": s.id_text, "group": s.group, "sound": s.sound, "bytes": s.length, "sample_rate": s.sample_rate})
            result.notes.extend(info.warnings[:5])
        except Exception as exc:
            result.warnings.append(f"SND scan failed: {exc}")
    payload = {
        "tool": "MugenForge Visual Forge",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "project": root.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "playsnd_events": events,
        "sound_bank": {"file": _rel(root, snd_path) if snd_path else None, "sounds": sounds},
        "note": "Cues are parsed from PlaySnd controllers. Timing is source-derived and should be verified in engine.",
    }
    _write_json(root, _vf_dir(root) / "sound_cue_manifest.json", payload, result)
    csv_path = _vf_dir(root) / "sound_cues.csv"
    fields = ["state", "anim", "frame", "value", "channel", "source_file", "line"]
    rows = [{field: event.get(field, "") for field in fields} for event in events]
    write_csv_artifact(csv_path, rows, fields, result, root, track_existing=True)
    return result


def add_sound_cue_controller(root: Path, cue: SoundCueSpec) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Sound Cue Insert")
    code_path = find_character_file(root, "cns")
    if not code_path or not code_path.exists():
        result.warnings.append("No CNS/ST target file found for sound cue insertion.")
        return result
    text = read_text_safely(code_path)
    state_re = re.compile(r"^\s*\[\s*Statedef\s+" + re.escape(str(int(cue.state_no))) + r"\s*\]", re.I | re.M)
    m = state_re.search(text)
    if not m:
        result.warnings.append(f"StateDef {cue.state_no} was not found in {code_path.name}. No cue was inserted.")
        return result
    next_state = re.search(r"^\s*\[\s*Statedef\s+-?\d+\s*\]", text[m.end():], re.I | re.M)
    insert_at = m.end() + next_state.start() if next_state else len(text)
    marker = f"; MugenForge Visual Forge Sound Cue: state={cue.state_no} frame={cue.frame} value={cue.sound_group},{cue.sound_index}"
    if marker in text:
        result.skipped_files.append("Cue marker already exists; no duplicate inserted.")
        return result
    block = f"""

{marker}
[State {int(cue.state_no)}, {cue.label or 'Visual Forge Sound Cue'}]
type = PlaySnd
trigger1 = AnimElem = {max(1, int(cue.frame))}
value = {int(cue.sound_group)}, {int(cue.sound_index)}
channel = {int(cue.channel)}
ignorehitpause = 1
"""
    backup = backup_file(code_path, root, "sound_cue")
    if backup:
        result.add_created(root, backup)
    new_text = text[:insert_at].rstrip() + block + "\n" + text[insert_at:].lstrip("\n")
    write_text_safely(code_path, new_text)
    result.add_changed(root, code_path)
    result.notes.append(f"Inserted PlaySnd cue in StateDef {cue.state_no} at AnimElem {max(1, int(cue.frame))}.")
    return result


def compose_move2(root: Path, spec: MoveWizardSpec, append: bool = False) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Move Composer 2.0")
    package = build_move_package(spec)
    preview_dir = _vf_dir(root) / "move_composer"
    preview = preview_dir / f"{_safe_name(spec.move_name)}_preview.txt"
    _write_text(root, preview, package.summary + "\n\n--- CMD ---\n" + package.cmd_block + "\n--- CNS/ST ---\n" + package.cns_block + "\n--- AIR ---\n" + package.air_block, result)
    if append:
        try:
            changes = append_move_to_project(root, package)
            result.changed_files.extend(changes)
            result.notes.append("Appended CMD/CNS/AIR blocks using the existing safe Move Wizard append path.")
        except Exception as exc:
            result.warnings.append(f"Append failed: {exc}")
            log_error(root, "Move Composer 2.0 append", exc)
    timeline_seed = {
        "move_name": spec.move_name,
        "state_no": spec.state_no,
        "anim_no": spec.anim_no,
        "frames": [
            {
                "elem": idx + 1,
                "group": spec.sprite_group,
                "image": spec.start_image + idx,
                "ticks": spec.ticks,
                "active": idx + 1 == spec.hit_frame and spec.move_type != "movement",
                "sound": (idx + 1 == spec.hit_frame),
            }
            for idx in range(max(1, int(spec.frame_count)))
        ],
        "note": "Generated preview timeline; append to project then use Visual Timeline for source-backed editing.",
    }
    _write_json(root, preview_dir / f"{_safe_name(spec.move_name)}_timeline_seed.json", timeline_seed, result)
    return result


def migrate_existing_character(spec: MigrationSpec) -> VisualForgeResult:
    source = Path(spec.source_root)
    dest_parent = Path(spec.destination_parent)
    name = _safe_name(spec.new_name or source.name)
    dest = dest_parent / name
    result = VisualForgeResult("Existing Character Import / Migration Wizard")
    if not source.exists() or not source.is_dir():
        result.warnings.append(f"Source folder does not exist: {source}")
        return result
    if dest.exists():
        result.warnings.append(f"Destination already exists: {dest}")
        return result
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "backups", "exports")
    shutil.copytree(source, dest, ignore=ignore)
    result.add_created(dest_parent, dest)
    audit = scan_project(dest)
    payload = {
        "tool": "MugenForge Visual Forge",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "source_root": str(source),
        "destination": str(dest),
        "copied_at": datetime.now().isoformat(timespec="seconds"),
        "missing_required": audit.missing_required,
        "warnings": audit.warnings,
        "missing_references": audit.missing_references,
        "code_issues": audit.code_issues[:100],
        "asset_issues": audit.asset_issues[:100],
        "honest_note": "This migration copies and profiles the project; it does not guarantee automatic repair of every legacy binary or gameplay behavior.",
    }
    _write_json(dest, _vf_dir(dest) / "migration_report.json", payload, result)
    guide = """# Migration Guide

This imported project was copied into MugenForge format without modifying the original source folder.

Recommended next steps:

1. Read `visual_forge/migration_report.json`.
2. Open the main DEF and verify `[Files]` references.
3. Use Rescue Lab if sprites/sounds are packed or unsupported.
4. Use Visual Timeline, CLSN Editor, and Quality Lab for source-driven cleanup.
5. Create a backup snapshot before repairs.

Honest limits: migration cannot guarantee full mature SFF2 extraction/rebuild or perfect gameplay conversion.
"""
    _write_text(dest, _docs_dir(dest) / "MIGRATION_GUIDE.md", guide, result)
    result.merge(write_beginner_project_home(dest, BeginnerProjectSpec(name=name, author="Imported Project", template="Legacy Import", archetype="Imported")), "Project Home")
    return result


def install_training_debug_pack(root: Path) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Training / Debug Overlay Pack")
    try:
        debug = apply_preset(root, "debug_overlay")
        result.merge(debug, "Debug Overlay")
    except Exception as exc:
        result.warnings.append(f"Debug overlay install failed: {exc}")
        log_error(root, "Training debug overlay", exc)
    config = {
        "tool": "MugenForge Visual Forge",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "enabled_helpers": ["state", "anim", "animelem", "time", "ctrl", "position", "velocity"],
        "manual_helpers": [
            "Use Animation Player/CLSN Editor for visual hitbox inspection.",
            "Use M.U.G.E.N training matches for engine-authoritative frame behavior.",
        ],
        "remove_before_release": "Optional. Debug overlays are useful in testing but may be undesirable in public releases.",
    }
    _write_json(root, _vf_dir(root) / "training_debug_overlay_config.json", config, result)
    guide = """# Training / Debug Overlay Pack

This pack installs a beginner-safe `DisplayToClipboard` debug helper and writes a config file describing what to watch during testing.

The overlay is useful for checking state number, animation number, animation element, time, control state, position, and velocity while testing in M.U.G.E.N.

For hitbox visualization, use MugenForge's Animation Player / CLSN Editor and verify final behavior in the engine.
"""
    _write_text(root, _docs_dir(root) / "TRAINING_DEBUG_OVERLAY_PACK.md", guide, result)
    return result


def install_template_architecture(root: Path) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Plugin / Template Architecture")
    templates = root / "templates"
    plugins = root / "plugins"
    templates.mkdir(parents=True, exist_ok=True)
    plugins.mkdir(parents=True, exist_ok=True)
    result.add_created(root, templates)
    result.add_created(root, plugins)
    template_manifest = {
        "tool": "MugenForge Visual Forge",
        "visual_forge_version": VISUAL_FORGE_VERSION,
        "schema": "no-code-template-manifest-v1",
        "templates": [
            {"id": "balanced_starter", "name": "Balanced Starter", "kind": "character", "description": "Safe shoto-style starter with no-code move scaffolds."},
            {"id": "rushdown_starter", "name": "Rushdown Starter", "kind": "character", "description": "Fast pressure-oriented starter metadata."},
            {"id": "zoner_starter", "name": "Projectile Zoner Starter", "kind": "character", "description": "Projectile and spacing-oriented starter metadata."},
            {"id": "stage_basic", "name": "Basic Stage Template", "kind": "stage", "description": "Stage metadata scaffold; stage art/SFF still needs authoring."},
        ],
        "note": "These are MugenForge no-code presets. They are not Fighter Factory assets or code.",
    }
    _write_json(root, templates / "no_code_templates.json", template_manifest, result)
    plugin_manifest = {
        "schema": "mugenforge-plugin-manifest-v1",
        "plugins": [
            {
                "id": "example_recipe_plugin",
                "name": "Example Recipe Plugin",
                "enabled": False,
                "entry_type": "data-only",
                "description": "Community templates should start as data-only JSON presets. Arbitrary Python execution is not enabled by default.",
            }
        ],
        "security_note": "Plugin support is intentionally conservative. Data-only presets are supported; arbitrary executable plugins require explicit future design and review.",
    }
    _write_json(root, plugins / "plugin_manifest.json", plugin_manifest, result)
    readme = """# MugenForge Plugins

v3.5 introduces the foundation for templates and data-only community presets.

Current supported shape:

- JSON template manifests.
- Data-only move/project recipe metadata.
- No automatic execution of third-party Python code.

This is a foundation, not a finished plugin marketplace.
"""
    _write_text(root, plugins / "README.md", readme, result)
    return result


def write_visual_sff2_bridge_pack(root: Path, image_folder: Optional[Path] = None) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Improved SFF2 Bridge Pack")
    try:
        guide = write_sff2_bridge_guide(root)
        result.add_created(root, guide)
    except Exception as exc:
        result.warnings.append(f"SFF2 guide failed: {exc}")
        log_error(root, "SFF2 guide", exc)
    if image_folder and Path(image_folder).exists():
        try:
            bridge = write_sprmake2_bridge_project(root, Path(image_folder))
            result.merge(bridge, "Sprmake2 Source Project")
        except Exception as exc:
            result.warnings.append(f"Sprmake2 source project failed: {exc}")
            log_error(root, "Sprmake2 source project", exc)
    result.notes.append("SFF2 Bridge remains source-based and honest: it prepares Sprmake2 source files and does not patch arbitrary mature SFF2 binaries.")
    return result


def create_backup_snapshot(root: Path, label: str = "manual") -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Central Backup Snapshot")
    backup_root = root / "backups" / "visual_forge_snapshots"
    backup_root.mkdir(parents=True, exist_ok=True)
    safe_label = _safe_name(label)[:40]
    out = backup_root / f"{root.name}_{safe_label}_{_timestamp()}.zip"
    manifest: List[Dict[str, object]] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
            if path.is_dir():
                continue
            rel = path.relative_to(root)
            parts = set(rel.parts)
            if parts & {"__pycache__", ".git"}:
                continue
            if rel.parts[:2] == ("backups", "visual_forge_snapshots"):
                continue
            if path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            zf.write(path, rel.as_posix())
            manifest.append({"path": rel.as_posix(), "bytes": path.stat().st_size})
        zf.writestr("VISUAL_FORGE_SNAPSHOT_MANIFEST.json", json.dumps({
            "tool": "MugenForge Visual Forge",
            "version": VISUAL_FORGE_VERSION,
            "project": root.name,
            "label": label,
            "created": datetime.now().isoformat(timespec="seconds"),
            "files": manifest,
        }, indent=2))
    result.add_created(root, out)
    result.notes.append(f"Snapshot contains {len(manifest)} file(s).")
    return result


def restore_latest_snapshot(root: Path) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Restore Latest Visual Forge Snapshot")
    backup_root = root / "backups" / "visual_forge_snapshots"
    zips = sorted(backup_root.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if backup_root.exists() else []
    if not zips:
        result.warnings.append("No Visual Forge snapshot ZIPs were found.")
        return result
    latest = zips[0]
    guard = create_backup_snapshot(root, "pre_restore_guard")
    result.merge(guard, "Pre-restore guard")
    with zipfile.ZipFile(latest, "r") as zf:
        for member in zf.namelist():
            if member == "VISUAL_FORGE_SNAPSHOT_MANIFEST.json" or member.startswith("../") or Path(member).is_absolute():
                continue
            target = root / member
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    result.notes.append(f"Restored latest snapshot: {latest.name}")
    result.warnings.append("Restore overwrites files from the snapshot. A pre-restore guard snapshot was created first.")
    return result


def quick_start_pass(root: Path) -> VisualForgeResult:
    root = Path(root)
    result = VisualForgeResult("Visual Forge Quick Start")
    result.merge(write_beginner_project_home(root, BeginnerProjectSpec(name=root.name)), "Home")
    result.merge(install_template_architecture(root), "Templates")
    result.merge(write_visual_timeline_manifest(root), "Timeline")
    result.merge(write_sound_cue_manifest(root), "Sound Cues")
    result.notes.append("Quick Start writes source-derived helper files and does not alter existing gameplay code except through explicitly selected tools.")
    return result
