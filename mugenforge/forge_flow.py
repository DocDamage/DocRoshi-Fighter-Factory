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
import wave
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file
from .air_tools import parse_air_with_lines
from .palette_tools import read_act, write_act, build_act_from_image
from .visual_forge import create_backup_snapshot

FORGE_FLOW_VERSION = "4.5.0"
CODE_SUFFIXES = {".cmd", ".cns", ".st"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg", ".csv"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
AUDIO_SUFFIXES = {".wav"}
GENERATED_PARTS = {"forge_flow", "forge_polish", "forge_beyond", "visual_forge", "quality_lab", "exports", "backups", "__pycache__"}


from .shared_utils import (
    BaseResult,
    uniq,
    rel_path,
    timestamp,
    backup_file,
    write_text_artifact,
    write_json_artifact,
    write_csv_artifact,
    discover_project_files,
    get_code_files,
    get_all_files,
    parse_safe_int,
    is_truthy,
    sanitize_name,
)

@dataclass
class ForgeFlowResult(BaseResult):
    title: str = "Forge Flow Result"


def _uniq(values: Iterable[str]) -> List[str]:
    return uniq(values)


def _safe_name(value: object) -> str:
    return sanitize_name(value)


def _rel(root: Path, path: Path | str | None) -> str:
    if path is None:
        return ""
    return rel_path(root, path)


def _out(root: Path, *parts: str) -> Path:
    p = Path(root) / "forge_flow"
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_text(root: Path, path: Path, text: str, res: Optional[ForgeFlowResult] = None) -> Path:
    return write_text_artifact(path, text, res, root, track_existing=True)


def _write_json(root: Path, path: Path, payload: object, res: Optional[ForgeFlowResult] = None) -> Path:
    return write_json_artifact(path, payload, res, root, track_existing=True)


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[ForgeFlowResult] = None) -> Path:
    return write_csv_artifact(path, rows, fields, res, root, track_existing=True)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _all_files(root: Path, include_generated: bool = True) -> List[Path]:
    return get_all_files(root, include_generated)


def _code_files(root: Path) -> List[Path]:
    return get_code_files(root)


def _image_files(root: Path, include_generated: bool = False) -> List[Path]:
    return [p for p in get_all_files(root, include_generated) if p.suffix.lower() in IMAGE_SUFFIXES]


def _wav_files(root: Path, include_generated: bool = False) -> List[Path]:
    return [p for p in get_all_files(root, include_generated) if p.suffix.lower() == ".wav"]


def _act_files(root: Path) -> List[Path]:
    return [p for p in get_all_files(root, False) if p.suffix.lower() == ".act"]


def _truthy(value: object) -> bool:
    return is_truthy(value)


def _int(value: object, default: int = 0) -> int:
    parsed = parse_safe_int(value, default)
    return default if parsed is None else parsed


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    return discover_project_files(root)


def _backup_file(root: Path, path: Path, reason: str) -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        rel = path.resolve().relative_to(Path(root).resolve())
    except Exception:
        rel = Path(path.name)
    dst = Path(root) / "backups" / "forge_flow_file_backups" / rel.with_name(rel.name + f".bak_{_safe_name(reason)}_{timestamp()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def _set_text_state(text: str, section_re: re.Pattern[str], key: str, value: object) -> str:
    lines = text.splitlines()
    any_section_re = re.compile(r"^\s*\[[^\]]+\]")
    key_re = re.compile(r"^\s*" + re.escape(key) + r"\s*=", re.I)
    out: List[str] = []
    in_section = False
    section_seen = False
    key_done = False
    for line in lines:
        if section_re.match(line):
            in_section = True
            section_seen = True
            out.append(line)
            continue
        if in_section and any_section_re.match(line):
            if not key_done:
                out.append(f"{key} = {value}")
                key_done = True
            in_section = False
        if in_section and key_re.match(line):
            if not key_done:
                out.append(f"{key} = {value}")
                key_done = True
            continue
        out.append(line)
    if section_seen and in_section and not key_done:
        out.append(f"{key} = {value}")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Project mode dashboard
# ---------------------------------------------------------------------------


def _project_stats(root: Path) -> Dict[str, object]:
    audit = scan_project(root)
    files = _discover_files(root)
    actions = []
    if files.get("air") and files["air"] and files["air"].exists():
        try:
            actions = parse_air(read_text_safely(files["air"]))
        except Exception:
            actions = []
    commands = []
    states = []
    hitdefs = 0
    changestates = 0
    playsnds = 0
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
            commands.extend(scan.commands)
            states.extend(scan.states)
            for ctrl in scan.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype == "hitdef":
                    hitdefs += 1
                elif stype == "changestate":
                    changestates += 1
                elif stype == "playsnd":
                    playsnds += 1
        except Exception:
            pass
    action_nums = {a.number for a in actions}
    missing_common = [n for n in COMMON_ANIMS if n not in action_nums]
    score = 100
    score -= min(35, 7 * len(audit.missing_required))
    score -= min(25, 5 * len(audit.missing_references))
    score -= min(18, len(missing_common))
    if not commands:
        score -= 8
    if not states:
        score -= 8
    if not hitdefs:
        score -= 8
    if not _image_files(root):
        score -= 5
    score = max(0, min(100, score))
    return {
        "score": score,
        "missing_required": audit.missing_required,
        "missing_references": audit.missing_references,
        "warnings": audit.warnings,
        "actions": len(actions),
        "commands": len(commands),
        "states": len(states),
        "hitdefs": hitdefs,
        "changestates": changestates,
        "playsnds": playsnds,
        "images": len(_image_files(root)),
        "wavs": len(_wav_files(root)),
        "act_files": len(_act_files(root)),
        "missing_common_actions": missing_common,
    }


def write_flow_mode_dashboard(root: Path) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Forge Flow Mode Dashboard")
    stats = _project_stats(root)
    next_steps: List[str] = []
    if stats["missing_required"]:
        next_steps.append("Repair missing required files before deep editing.")
    if stats["missing_common_actions"]:
        next_steps.append("Use the AIR repair/common action tools before tuning animation flow.")
    if not stats["hitdefs"]:
        next_steps.append("Add at least one attack/HitDef via Move Composer or Feature Bank.")
    if not stats["images"]:
        next_steps.append("Add source sprites or extract supported SFF v1 sprites for richer timeline previews.")
    if not stats["act_files"]:
        next_steps.append("Create or import an ACT palette if you want Palette Studio previews.")
    next_steps.extend([
        "Use Move Flow Timeline as the main move-editing starting point.",
        "Validate and apply CSV edits in small batches; backups are written first.",
        "Use State Flow Sheet only for simple numeric ChangeState target repairs.",
        "Use Stage Flow Preview for source-art layout checks; engine rendering still requires M.U.G.E.N playtesting.",
    ])
    md_lines = [
        "# MugenForge v4.5 Forge Flow",
        "",
        f"Project: **{root.name}**",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Project health estimate: **{stats['score']} / 100**",
        "",
        "## Mode buttons to use next",
        "",
        "| Mode | Use it for | Main output |",
        "|---|---|---|",
        "| Move Designer | timing, frame order, sound cue placement, event visibility | `forge_flow/move_timeline/` |",
        "| State Flow | ChangeState target map and simple transition repairs | `forge_flow/state_flow/` |",
        "| Palette Studio | ACT grid, editable palette CSV, visual preview | `forge_flow/palette_studio/` |",
        "| Stage Flow | stage DEF parameter sheet and source-art preview | `forge_flow/stage_flow/` |",
        "| Sound Board | WAV waveform sheets for cue planning | `forge_flow/sound_board/` |",
        "| Release Review | bundled v4.5 artifacts | `forge_flow/forge_flow_bundle_*.zip` |",
        "",
        "## Next steps",
        "",
    ]
    md_lines += [f"- {step}" for step in next_steps]
    md_lines += [
        "",
        "## Honest notes",
        "",
        "- v4.5 improves visual source-driven workflows; it does not add arbitrary mature SFF v2 binary editing/rebuilding.",
        "- Timeline and state reports are source-analysis aids, not engine-authoritative runtime telemetry.",
        "- Apply tools write backups, but large migrations should still be versioned externally.",
    ]
    start = _out(root) / "FORGE_FLOW_START_HERE.md"
    _write_text(root, start, "\n".join(md_lines), result)
    html_rows = "".join(
        f"<tr><th>{html.escape(k.replace('_', ' ').title())}</th><td>{html.escape(str(v))}</td></tr>"
        for k, v in stats.items() if k not in {"missing_common_actions", "missing_references", "warnings"}
    )
    html_doc = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Forge Flow Dashboard</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;background:#f7f7f7;color:#222}}.card{{background:white;border:1px solid #ddd;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 2px 6px #0001}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #eee;padding:8px;text-align:left}}.score{{font-size:48px;font-weight:700}}li{{margin:.35rem 0}}</style></head>
<body><h1>MugenForge v4.5 Forge Flow</h1><div class='card'><div class='score'>{stats['score']} / 100</div><p>Project health estimate for <b>{html.escape(root.name)}</b>.</p></div>
<div class='card'><h2>Project snapshot</h2><table>{html_rows}</table></div>
<div class='card'><h2>Next steps</h2><ol>{''.join(f'<li>{html.escape(step)}</li>' for step in next_steps)}</ol></div>
<div class='card'><h2>Limits kept honest</h2><p>Reports and previews are source-analysis aids. Full arbitrary mature SFF v2 binary editing/rebuilding remains outside this release.</p></div>
</body></html>"""
    _write_text(root, _out(root) / "FLOW_MODE_DASHBOARD.html", html_doc, result)
    result.notes.append("Forge Flow dashboard written. Start at forge_flow/FORGE_FLOW_START_HERE.md.")
    return result


# ---------------------------------------------------------------------------
# Move Flow Timeline
# ---------------------------------------------------------------------------


def _anim_elem_from_values(values: Dict[str, str], default: int = 1) -> int:
    joined = "\n".join(str(v) for k, v in values.items() if k.startswith("trigger"))
    for pat in (
        r"AnimElem\s*=\s*(-?\d+)",
        r"AnimElemNo\s*\([^)]*\)\s*=\s*(-?\d+)",
        r"animelem\s*=\s*(-?\d+)",
    ):
        m = re.search(pat, joined, re.I)
        if m:
            return max(1, _int(m.group(1), default))
    if "time" in values and re.fullmatch(r"\s*\d+\s*", values.get("time", "")):
        return max(1, _int(values.get("time"), default))
    return default


def _parent_state_events(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            text = read_text_safely(path)
            scan = parse_code(text)
        except Exception:
            continue
        for state in scan.states:
            anim = _int(state.values.get("anim", state.number), state.number)
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype not in {"playsnd", "hitdef", "velset", "posadd", "changestate", "projectile", "helper", "explod", "changeanim"}:
                    continue
                frame = _anim_elem_from_values(ctrl.values, 1)
                data = {
                    "file": _rel(root, path),
                    "line": ctrl.line,
                    "state": state.number,
                    "anim": anim,
                    "frame": frame,
                    "type": stype,
                    "label": ctrl.header,
                    "value": ctrl.values.get("value", ""),
                    "damage": ctrl.values.get("damage", ""),
                    "attr": ctrl.values.get("attr", ""),
                    "channel": ctrl.values.get("channel", ""),
                    "x": ctrl.values.get("x", ""),
                    "y": ctrl.values.get("y", ""),
                    "projanim": ctrl.values.get("projanim", ""),
                    "helper_state": ctrl.values.get("stateno", ctrl.values.get("helpertype", "")),
                    "raw": dict(ctrl.values),
                }
                rows.append(data)
    return rows


def _sound_pair(value: object) -> Tuple[str, str]:
    nums = re.findall(r"-?\d+", str(value or ""))
    if len(nums) >= 2:
        return nums[0], nums[1]
    return "", ""


def build_move_flow_model(root: Path, action_number: Optional[int] = None) -> Dict[str, object]:
    root = Path(root)
    files = _discover_files(root)
    air_path = files.get("air")
    actions = []
    if air_path and air_path.exists():
        actions = parse_air(read_text_safely(air_path))
    events = _parent_state_events(root)
    by_anim_frame: Dict[Tuple[int, int], List[Dict[str, object]]] = {}
    for ev in events:
        by_anim_frame.setdefault((_int(ev.get("anim"), 0), _int(ev.get("frame"), 1)), []).append(ev)
    frames: List[Dict[str, object]] = []
    action_summaries: List[Dict[str, object]] = []
    selected_actions = [a for a in actions if action_number is None or a.number == int(action_number)]
    for action in selected_actions:
        ticks_total = sum(max(0, f.ticks) for f in action.frames)
        action_events = [ev for ev in events if _int(ev.get("anim"), -999999) == action.number]
        action_summaries.append({
            "action": action.number,
            "label": action.label or COMMON_ANIMS.get(action.number, ""),
            "frames": len(action.frames),
            "ticks": ticks_total,
            "events": len(action_events),
            "has_hitdef": any(ev.get("type") == "hitdef" for ev in action_events),
            "has_sound": any(ev.get("type") == "playsnd" for ev in action_events),
        })
        for idx, frame in enumerate(action.frames, start=1):
            fevents = by_anim_frame.get((action.number, idx), [])
            play = next((ev for ev in fevents if ev.get("type") == "playsnd"), {})
            hit = next((ev for ev in fevents if ev.get("type") == "hitdef"), {})
            sg, si = _sound_pair(play.get("value", ""))
            frames.append({
                "enabled": "no",
                "action": action.number,
                "action_label": action.label or COMMON_ANIMS.get(action.number, ""),
                "frame_index": idx,
                "sprite_group": frame.group,
                "sprite_image": frame.image,
                "offset_x": frame.x,
                "offset_y": frame.y,
                "ticks": frame.ticks,
                "flags": frame.flags,
                "clsn1_count": sum(1 for b in frame.clsn if b.kind.lower() == "clsn1"),
                "clsn2_count": sum(1 for b in frame.clsn if b.kind.lower() == "clsn2"),
                "event_types": ", ".join(sorted({str(ev.get("type", "")) for ev in fevents if ev.get("type")})),
                "sound_group": sg,
                "sound_index": si,
                "sound_channel": play.get("channel", ""),
                "add_playsnd": "no",
                "hitdef_damage": hit.get("damage", ""),
                "hitdef_attr": hit.get("attr", ""),
                "notes": "",
            })
    return {
        "tool": "MugenForge Studio",
        "version": FORGE_FLOW_VERSION,
        "mode": "move_flow_timeline",
        "project": root.name,
        "air_file": _rel(root, air_path) if air_path else "",
        "action_filter": action_number,
        "actions": action_summaries,
        "frames": frames,
        "events": events,
        "honest_limit": "This is a source-code/AIR timeline model. It is not engine-authoritative runtime telemetry.",
    }


def export_move_flow_sheet(root: Path, action_number: Optional[int] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Move Flow Sheet Export")
    model = build_move_flow_model(root, action_number)
    out = _out(root, "move_timeline")
    _write_json(root, out / "move_flow_model.json", model, result)
    fields = [
        "enabled", "action", "action_label", "frame_index", "sprite_group", "sprite_image",
        "offset_x", "offset_y", "ticks", "flags", "clsn1_count", "clsn2_count",
        "event_types", "sound_group", "sound_index", "sound_channel", "add_playsnd",
        "hitdef_damage", "hitdef_attr", "notes",
    ]
    _write_csv(root, out / "move_flow_editor_sheet.csv", model.get("frames", []), fields, result)
    result.notes.append("Edit enabled rows in move_flow_editor_sheet.csv. Applying supports AIR frame group/image/offset/ticks/flags edits and optional PlaySnd insertion.")
    return result


def _format_air_line(row: Dict[str, str], old_flags: str = "") -> str:
    g = _int(row.get("sprite_group"), 0)
    i = _int(row.get("sprite_image"), 0)
    x = _int(row.get("offset_x"), 0)
    y = _int(row.get("offset_y"), 0)
    ticks = max(1, _int(row.get("ticks"), 1))
    flags = str(row.get("flags", old_flags) or "").strip()
    base = f"{g}, {i}, {x}, {y}, {ticks}"
    return base + (f", {flags}" if flags else "")


def _find_state_targets_for_anim(root: Path, anim_no: int) -> List[Tuple[Path, int, int]]:
    targets: List[Tuple[Path, int, int]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for st in scan.states:
            if _int(st.values.get("anim", st.number), st.number) == int(anim_no) or st.number == int(anim_no):
                targets.append((path, st.number, st.line))
    return targets


def _insert_playsnd_block(text: str, state_no: int, frame: int, group: int, sound: int, channel: int, marker: str) -> Tuple[str, bool]:
    if marker in text:
        return text, False
    lines = text.splitlines()
    state_re = re.compile(r"^\s*\[\s*StateDef\s+" + re.escape(str(state_no)) + r"\s*\]", re.I)
    any_section_re = re.compile(r"^\s*\[[^\]]+\]")
    start = None
    insert_at = None
    for idx, line in enumerate(lines):
        if start is None and state_re.match(line):
            start = idx
            continue
        if start is not None and idx > start and any_section_re.match(line):
            insert_at = idx
            break
    if start is None:
        return text, False
    if insert_at is None:
        insert_at = len(lines)
    block = [
        "",
        f"; {marker}",
        f"[State {state_no}, Forge Flow PlaySnd frame {frame}]",
        "type = PlaySnd",
        f"trigger1 = AnimElem = {int(frame)}",
        f"value = {int(group)}, {int(sound)}",
        f"channel = {int(channel)}",
        "ignorehitpause = 1",
        "",
    ]
    lines[insert_at:insert_at] = block
    return "\n".join(lines).rstrip() + "\n", True


def apply_move_flow_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Move Flow Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else _out(root, "move_timeline") / "move_flow_editor_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"Move flow sheet not found: {sheet}")
        return result
    files = _discover_files(root)
    air_path = files.get("air")
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("enabled"))]
    if not rows:
        result.skipped_files.append("No enabled rows found. Set enabled=yes for rows you want to apply.")
        return result
    # AIR edits.
    if air_path and air_path.exists():
        text = read_text_safely(air_path)
        line_actions = parse_air_with_lines(text)
        lines = text.splitlines()
        by_key = {(a.number, f.frame_index + 1): f for a in line_actions for f in a.frames}
        changed = 0
        for row in rows:
            key = (_int(row.get("action"), 0), _int(row.get("frame_index"), 0))
            frame = by_key.get(key)
            if not frame:
                result.warnings.append(f"AIR frame not found for action/frame {key[0]}/{key[1]}")
                continue
            new_line = _format_air_line(row, getattr(frame, "flags", ""))
            if 0 <= frame.line_index < len(lines) and lines[frame.line_index].strip() != new_line.strip():
                lines[frame.line_index] = new_line
                changed += 1
        if changed:
            backup = _backup_file(root, air_path, "move_flow_air_apply")
            write_text_safely(air_path, "\n".join(lines).rstrip() + "\n")
            result.changed_files.append(_rel(root, air_path))
            if backup:
                result.notes.append(f"Backup written: {_rel(root, backup)}")
            result.notes.append(f"Updated {changed} AIR frame line(s).")
    else:
        result.warnings.append("No AIR file found; AIR frame edits were skipped.")
    # Optional PlaySnd insertion.
    changed_code: Dict[Path, str] = {}
    backups_done: set[Path] = set()
    inserted = 0
    for row in rows:
        if not _truthy(row.get("add_playsnd")):
            continue
        action = _int(row.get("action"), 0)
        frame = max(1, _int(row.get("frame_index"), 1))
        group = _int(row.get("sound_group"), 0)
        sound = _int(row.get("sound_index"), 0)
        channel = _int(row.get("sound_channel"), 0)
        targets = _find_state_targets_for_anim(root, action)
        if not targets:
            result.warnings.append(f"No StateDef found for action/anim {action}; PlaySnd insertion skipped for frame {frame}.")
            continue
        path, state_no, _line = targets[0]
        text = changed_code.get(path, read_text_safely(path))
        marker = f"MugenForge Forge Flow PlaySnd action={action} frame={frame} value={group},{sound}"
        text2, ok = _insert_playsnd_block(text, state_no, frame, group, sound, channel, marker)
        if ok:
            changed_code[path] = text2
            inserted += 1
    for path, text in changed_code.items():
        if path not in backups_done:
            backup = _backup_file(root, path, "move_flow_playsnd_apply")
            backups_done.add(path)
            if backup:
                result.notes.append(f"Backup written: {_rel(root, backup)}")
        write_text_safely(path, text)
        result.changed_files.append(_rel(root, path))
    if inserted:
        result.notes.append(f"Inserted {inserted} PlaySnd controller(s). Existing cue markers are not duplicated.")
    return result


def write_move_flow_timeline_pack(root: Path, action_number: Optional[int] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Move Flow Timeline Pack")
    result.merge(export_move_flow_sheet(root, action_number))
    model = build_move_flow_model(root, action_number)
    out = _out(root, "move_timeline")
    _write_json(root, out / "move_flow_model.json", model, result)
    # HTML timeline.
    frames = model.get("frames", [])
    action_groups: Dict[int, List[Dict[str, object]]] = {}
    for row in frames:
        action_groups.setdefault(_int(row.get("action"), 0), []).append(row)
    action_html: List[str] = []
    for action, rows in action_groups.items():
        cells: List[str] = []
        for row in rows:
            ticks = max(1, _int(row.get("ticks"), 1))
            width = max(42, min(180, ticks * 12))
            events = str(row.get("event_types", ""))
            css = "frame"
            if "hitdef" in events:
                css += " hit"
            if "playsnd" in events:
                css += " snd"
            cells.append(
                f"<div class='{css}' style='width:{width}px'><b>#{html.escape(str(row.get('frame_index')))}</b><br>"
                f"{html.escape(str(row.get('sprite_group')))}, {html.escape(str(row.get('sprite_image')))}<br>"
                f"ticks {ticks}<br><small>{html.escape(events)}</small></div>"
            )
        label = rows[0].get("action_label", "") if rows else ""
        action_html.append(f"<h2>Action {action} {html.escape(str(label))}</h2><div class='rail'>{''.join(cells)}</div>")
    html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Move Flow Timeline</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f7;color:#222}}.rail{{display:flex;align-items:stretch;gap:6px;overflow-x:auto;border:1px solid #ddd;background:white;padding:12px;border-radius:10px;margin-bottom:22px}}.frame{{border:1px solid #aaa;border-radius:8px;padding:8px;background:#fafafa;min-height:80px;font-size:12px;box-sizing:border-box}}.hit{{box-shadow:inset 0 -5px 0 #f3b1b1}}.snd{{outline:3px solid #b9d7ff}}small{{color:#555}}</style></head><body>
<h1>MugenForge v4.5 Move Flow Timeline</h1><p>Source-derived timeline. Width roughly follows AIR ticks. Red underline = HitDef event, blue outline = PlaySnd event.</p>{''.join(action_html) if action_html else '<p>No AIR frames found.</p>'}
</body></html>"""
    _write_text(root, out / "move_flow_timeline.html", html_doc, result)
    # PNG storyboard/contact sheet.
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        frame_w, frame_h = 150, 96
        actions = list(action_groups.items())[:20]
        max_cols = max([len(v) for _a, v in actions] + [1])
        width = max(900, min(2600, 180 + max_cols * (frame_w + 10) + 20))
        height = max(220, 60 + len(actions) * (frame_h + 44))
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 12)
            bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 13)
        except Exception:
            font = bold = None
        draw.text((18, 14), "MugenForge v4.5 Move Flow Timeline", fill=(0, 0, 0), font=bold)
        y = 54
        for action, rows in actions:
            draw.text((18, y + 28), f"Action {action}", fill=(0, 0, 0), font=bold)
            x = 150
            for row in rows[:max_cols]:
                events = str(row.get("event_types", ""))
                fill = (246, 246, 246)
                outline = (120, 120, 120)
                if "hitdef" in events:
                    fill = (255, 230, 230)
                elif "playsnd" in events:
                    fill = (230, 242, 255)
                draw.rounded_rectangle([x, y, x + frame_w, y + frame_h], radius=8, fill=fill, outline=outline)
                draw.text((x + 8, y + 8), f"F{row.get('frame_index')}  t={row.get('ticks')}", fill=(0, 0, 0), font=bold)
                draw.text((x + 8, y + 30), f"spr {row.get('sprite_group')},{row.get('sprite_image')}", fill=(0, 0, 0), font=font)
                draw.text((x + 8, y + 50), f"off {row.get('offset_x')},{row.get('offset_y')}", fill=(0, 0, 0), font=font)
                draw.text((x + 8, y + 70), events[:18], fill=(0, 0, 0), font=font)
                x += frame_w + 10
            y += frame_h + 44
        png = out / "move_flow_timeline.png"
        img.save(png)
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"PNG timeline storyboard skipped: {exc}")
    result.notes.append("Move Flow Timeline pack written with model JSON, editable CSV, HTML, and optional PNG storyboard.")
    return result


# ---------------------------------------------------------------------------
# State Flow graph editing
# ---------------------------------------------------------------------------


def _change_state_rows(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            for ctrl in state.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype != "changestate":
                    continue
                val = ctrl.values.get("value", "")
                if not re.fullmatch(r"\s*-?\d+\s*", val or ""):
                    continue
                trig = "; ".join(f"{k}={v}" for k, v in ctrl.values.items() if k.startswith("trigger"))
                rows.append({
                    "enabled": "no",
                    "file": _rel(root, path),
                    "controller_line": ctrl.line,
                    "source_state": state.number,
                    "current_target": int(str(val).strip()),
                    "new_target": "",
                    "label": ctrl.header,
                    "triggers": trig,
                    "notes": "",
                })
    return rows


def export_state_flow_sheet(root: Path) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("State Flow Sheet Export")
    rows = _change_state_rows(root)
    fields = ["enabled", "file", "controller_line", "source_state", "current_target", "new_target", "label", "triggers", "notes"]
    out = _out(root, "state_flow")
    _write_csv(root, out / "state_transition_editor_sheet.csv", rows, fields, result)
    nodes = sorted({int(r["source_state"]) for r in rows} | {int(r["current_target"]) for r in rows})
    edges = [{"from": r["source_state"], "to": r["current_target"], "file": r["file"], "line": r["controller_line"]} for r in rows]
    _write_json(root, out / "state_flow_model.json", {"nodes": nodes, "edges": edges, "version": FORGE_FLOW_VERSION}, result)
    svg_edges = []
    width = 1200
    height = max(260, 120 + len(nodes) * 8)
    positions = {}
    radius = min(420, max(160, 40 + len(nodes) * 8))
    cx, cy = width // 2, height // 2
    for idx, node in enumerate(nodes):
        ang = 2 * math.pi * idx / max(1, len(nodes))
        positions[node] = (int(cx + math.cos(ang) * radius), int(cy + math.sin(ang) * radius))
    for e in edges[:250]:
        x1, y1 = positions.get(int(e["from"]), (cx, cy))
        x2, y2 = positions.get(int(e["to"]), (cx, cy))
        svg_edges.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#aaa' stroke-width='1'/>")
    svg_nodes = [f"<g><circle cx='{x}' cy='{y}' r='24' fill='white' stroke='#333'/><text x='{x}' y='{y+4}' text-anchor='middle' font-size='12'>{n}</text></g>" for n, (x, y) in positions.items()]
    html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>State Flow</title><style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px}}svg{{border:1px solid #ddd;background:#fbfbfb}}</style></head><body><h1>Forge Flow State Graph</h1><p>Edit <code>state_transition_editor_sheet.csv</code>; only rows with enabled=yes and numeric new_target are applied.</p><svg width='{width}' height='{height}'>{''.join(svg_edges)}{''.join(svg_nodes)}</svg></body></html>"""
    _write_text(root, out / "state_flow_graph.html", html_doc, result)
    result.notes.append("State transition sheet is for simple numeric ChangeState target edits only.")
    return result


def apply_state_flow_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("State Flow Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else _out(root, "state_flow") / "state_transition_editor_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"State flow sheet not found: {sheet}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("enabled"))]
    if not rows:
        result.skipped_files.append("No enabled rows found.")
        return result
    grouped: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        new_target = str(row.get("new_target", "")).strip()
        if not re.fullmatch(r"-?\d+", new_target):
            result.warnings.append(f"Row line {row.get('controller_line')}: new_target is not a simple integer; skipped.")
            continue
        path = root / str(row.get("file", ""))
        if not path.exists():
            result.warnings.append(f"File missing for state flow row: {row.get('file')}")
            continue
        grouped.setdefault(path, []).append(row)
    for path, file_rows in grouped.items():
        text = read_text_safely(path)
        lines = text.splitlines()
        changed = 0
        for row in file_rows:
            ctrl_line = _int(row.get("controller_line"), 0) - 1
            if not (0 <= ctrl_line < len(lines)):
                result.warnings.append(f"Controller line out of range in {_rel(root, path)}: {row.get('controller_line')}")
                continue
            end = len(lines)
            for i in range(ctrl_line + 1, len(lines)):
                if re.match(r"^\s*\[[^\]]+\]", lines[i]):
                    end = i
                    break
            replaced = False
            for i in range(ctrl_line + 1, end):
                if re.match(r"^\s*value\s*=", lines[i], re.I):
                    old = lines[i]
                    lines[i] = re.sub(r"^(\s*value\s*=\s*).*$", r"\g<1>" + str(row.get("new_target", "")).strip(), lines[i], flags=re.I)
                    if old != lines[i]:
                        changed += 1
                    replaced = True
                    break
            if not replaced:
                insert_at = min(end, ctrl_line + 1)
                lines.insert(insert_at, f"value = {str(row.get('new_target', '')).strip()}")
                changed += 1
        if changed:
            backup = _backup_file(root, path, "state_flow_apply")
            write_text_safely(path, "\n".join(lines).rstrip() + "\n")
            result.changed_files.append(_rel(root, path))
            if backup:
                result.notes.append(f"Backup written: {_rel(root, backup)}")
            result.notes.append(f"Updated {changed} ChangeState target(s) in {_rel(root, path)}.")
    return result


# ---------------------------------------------------------------------------
# Palette Studio
# ---------------------------------------------------------------------------


def _hex_to_rgb(value: str) -> Optional[Tuple[int, int, int]]:
    s = str(value or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", s):
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return None


def write_palette_studio(root: Path, palette_path: Optional[Path] = None, image_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Palette Studio")
    out = _out(root, "palette_studio")
    source = Path(palette_path) if palette_path else (_act_files(root)[0] if _act_files(root) else None)
    if source is None:
        images = _image_files(root)
        if images:
            try:
                source = out / "generated_from_first_image.act"
                info = build_act_from_image(images[0], source)
                result.notes.append(f"No ACT found; built starter ACT from {_rel(root, images[0])}.")
            except Exception as exc:
                result.warnings.append(f"No ACT file found and starter palette build failed: {exc}")
                return result
        else:
            result.warnings.append("No ACT palettes or source images found for Palette Studio.")
            return result
    try:
        info = read_act(source)
    except Exception as exc:
        result.warnings.append(f"Could not read ACT palette {source}: {exc}")
        return result
    rows = []
    for idx, (r, g, b) in enumerate(info.colors[:256]):
        rows.append({"index": idx, "r": r, "g": g, "b": b, "hex": f"#{r:02X}{g:02X}{b:02X}", "locked": "no", "notes": ""})
    _write_csv(root, out / "palette_editor_sheet.csv", rows, ["index", "r", "g", "b", "hex", "locked", "notes"], result)
    _write_json(root, out / "palette_source.json", {"source": _rel(root, source), "warnings": info.warnings, "colors": rows}, result)
    swatches = "".join(f"<div class='sw' title='{row['index']} {row['hex']}' style='background:{row['hex']}'><span>{row['index']}</span></div>" for row in rows)
    html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Palette Studio</title><style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f7}}.grid{{display:grid;grid-template-columns:repeat(16,36px);gap:4px;background:white;border:1px solid #ddd;padding:12px;width:max-content}}.sw{{width:36px;height:36px;border:1px solid #888;box-sizing:border-box;position:relative}}.sw span{{position:absolute;bottom:1px;right:2px;font-size:9px;color:white;text-shadow:0 1px 2px black}}</style></head><body><h1>Forge Flow Palette Studio</h1><p>Source: {html.escape(_rel(root, source))}</p><p>Edit <code>palette_editor_sheet.csv</code>, then apply it to create <code>forge_flow/palette_studio/edited_palette.act</code>.</p><div class='grid'>{swatches}</div></body></html>"""
    _write_text(root, out / "palette_grid.html", html_doc, result)
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        cell = 28
        img = Image.new("RGB", (16 * cell, 16 * cell + 34), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 8)
        except Exception:
            font = None
        for idx, (r, g, b) in enumerate(info.colors[:256]):
            x = (idx % 16) * cell
            y = (idx // 16) * cell
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(r, g, b), outline=(80, 80, 80))
            draw.text((x + 2, y + 17), str(idx), fill=(255, 255, 255), font=font)
        draw.text((4, 16 * cell + 8), f"Source: {_rel(root, source)}", fill=(0, 0, 0), font=font)
        png = out / "palette_grid.png"
        img.save(png)
        result.add_created(root, png)
        # Optional image preview: quantize/copy first image with palette.
        images = [Path(image_path)] if image_path else _image_files(root)
        if images:
            preview_src = images[0]
            try:
                src_img = Image.open(preview_src).convert("RGBA")
                src_img.thumbnail((360, 360))
                canvas = Image.new("RGB", (420, 430), "white")
                canvas.paste(src_img.convert("RGB"), (30, 30), src_img if src_img.mode == "RGBA" else None)
                draw2 = ImageDraw.Draw(canvas)
                draw2.text((30, 400), f"Preview source: {_rel(root, preview_src)}", fill=(0, 0, 0), font=font)
                prev = out / "palette_preview.png"
                canvas.save(prev)
                result.add_created(root, prev)
            except Exception as exc:
                result.warnings.append(f"Palette image preview skipped: {exc}")
    except Exception as exc:
        result.warnings.append(f"Palette PNG grid skipped: {exc}")
    result.notes.append("Palette Studio uses ACT files and source-image previews. It does not mutate SFF palettes directly.")
    return result


def apply_palette_sheet(root: Path, sheet_path: Optional[Path] = None, out_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Palette Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else _out(root, "palette_studio") / "palette_editor_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"Palette sheet not found: {sheet}")
        return result
    rows = _read_csv(sheet)
    colors = [(0, 0, 0)] * 256
    for row in rows:
        idx = _int(row.get("index"), -1)
        if not (0 <= idx < 256):
            continue
        rgb = _hex_to_rgb(row.get("hex", ""))
        if rgb is None:
            rgb = (_int(row.get("r"), 0), _int(row.get("g"), 0), _int(row.get("b"), 0))
        colors[idx] = tuple(max(0, min(255, int(v))) for v in rgb)  # type: ignore[assignment]
    out = Path(out_path) if out_path else _out(root, "palette_studio") / "edited_palette.act"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        backup = _backup_file(root, out, "palette_apply")
        if backup:
            result.notes.append(f"Backup written: {_rel(root, backup)}")
    write_act(out, colors)
    result.created_files.append(_rel(root, out))
    result.notes.append("Wrote edited ACT palette. Import/build steps remain separate; no packed SFF palette was mutated.")
    return result


# ---------------------------------------------------------------------------
# Stage Flow
# ---------------------------------------------------------------------------


def _stage_candidates(root: Path) -> List[Path]:
    defs = []
    for p in _all_files(root, include_generated=False):
        if p.suffix.lower() == ".def":
            try:
                text = read_text_safely(p).lower()
                if "[camera]" in text or "[bgdef]" in text or "[stageinfo]" in text:
                    defs.append(p)
            except Exception:
                pass
    return defs


def _def_value(sections: Dict[str, object], section: str, key: str, default: str = "") -> str:
    sec = sections.get(section.lower())
    vals = getattr(sec, "values", {}) if sec else {}
    return str(vals.get(key.lower(), default))


def write_stage_flow_preview(root: Path, stage_def: Optional[Path] = None, image_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Stage Flow Preview")
    out = _out(root, "stage_flow")
    stg = Path(stage_def) if stage_def else (_stage_candidates(root)[0] if _stage_candidates(root) else None)
    rows: List[Dict[str, object]] = []
    sections = {}
    if stg and stg.exists():
        try:
            sections = parse_def(read_text_safely(stg))
        except Exception as exc:
            result.warnings.append(f"Could not parse stage DEF {stg}: {exc}")
    params = [
        ("Camera", "boundleft"), ("Camera", "boundright"), ("Camera", "boundhigh"), ("Camera", "boundlow"),
        ("Camera", "verticalfollow"), ("Camera", "floortension"), ("PlayerInfo", "p1startx"), ("PlayerInfo", "p1starty"),
        ("PlayerInfo", "p2startx"), ("PlayerInfo", "p2starty"), ("StageInfo", "zoffset"), ("StageInfo", "localcoord"),
        ("Scaling", "topz"), ("Scaling", "botz"), ("Scaling", "topscale"), ("Scaling", "botscale"),
    ]
    for section, key in params:
        rows.append({"enabled": "no", "file": _rel(root, stg) if stg else "", "section": section, "key": key, "value": _def_value(sections, section, key), "new_value": "", "notes": ""})
    _write_csv(root, out / "stage_params_sheet.csv", rows, ["enabled", "file", "section", "key", "value", "new_value", "notes"], result)
    _write_json(root, out / "stage_flow_model.json", {"stage_def": _rel(root, stg) if stg else "", "params": rows, "version": FORGE_FLOW_VERSION}, result)
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        imgs = [Path(image_path)] if image_path else [p for p in _image_files(root) if any(word in p.name.lower() for word in ("stage", "bg", "background", "floor"))]
        canvas_w, canvas_h = 960, 540
        img = Image.new("RGB", (canvas_w, canvas_h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 13)
            bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
        except Exception:
            font = bold = None
        if imgs:
            try:
                bg = Image.open(imgs[0]).convert("RGB")
                bg.thumbnail((canvas_w, canvas_h))
                img.paste(bg, ((canvas_w - bg.width) // 2, (canvas_h - bg.height) // 2))
                result.notes.append(f"Stage preview used source image: {_rel(root, imgs[0])}")
            except Exception as exc:
                result.warnings.append(f"Stage source image could not be loaded: {exc}")
        zoffset = _int(_def_value(sections, "StageInfo", "zoffset", "440"), 440)
        localcoord = _def_value(sections, "StageInfo", "localcoord", "320,240")
        scale_x = canvas_w / 320.0
        scale_y = canvas_h / 240.0
        y = int(zoffset * scale_y / 2) if zoffset else canvas_h - 90
        y = max(60, min(canvas_h - 40, y))
        draw.line([(0, y), (canvas_w, y)], fill=(220, 20, 20), width=3)
        p1x = canvas_w // 2 + int(_int(_def_value(sections, "PlayerInfo", "p1startx", "-70"), -70) * scale_x / 2)
        p2x = canvas_w // 2 + int(_int(_def_value(sections, "PlayerInfo", "p2startx", "70"), 70) * scale_x / 2)
        for label, px, color in (("P1", p1x, (30, 70, 200)), ("P2", p2x, (200, 70, 30))):
            draw.ellipse([px - 18, y - 72, px + 18, y - 36], fill=color)
            draw.rectangle([px - 16, y - 36, px + 16, y], fill=color)
            draw.text((px - 12, y + 6), label, fill=(0, 0, 0), font=bold)
        draw.rectangle([12, 12, canvas_w - 12, canvas_h - 12], outline=(30, 30, 30), width=2)
        draw.text((24, 22), "Forge Flow Stage Preview", fill=(0, 0, 0), font=bold)
        draw.text((24, 44), f"Stage DEF: {_rel(root, stg) if stg else 'none detected'}", fill=(0, 0, 0), font=font)
        draw.text((24, 64), f"localcoord: {localcoord} | zoffset line shown in red", fill=(0, 0, 0), font=font)
        png = out / "stage_flow_preview.png"
        img.save(png)
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"Stage preview PNG skipped: {exc}")
    html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Stage Flow</title><style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px}}img{{max-width:100%;border:1px solid #ddd}}</style></head><body><h1>Forge Flow Stage Preview</h1><p>Edit <code>stage_params_sheet.csv</code>, then apply it for simple stage DEF key/value changes.</p><p>Preview is source-art/layout guidance only, not an engine-rendered stage.</p><img src='stage_flow_preview.png' alt='Stage preview'></body></html>"""
    _write_text(root, out / "stage_flow_preview.html", html_doc, result)
    return result


def apply_stage_params_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Stage Params Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else _out(root, "stage_flow") / "stage_params_sheet.csv"
    if not sheet.exists():
        result.warnings.append(f"Stage params sheet not found: {sheet}")
        return result
    rows = [r for r in _read_csv(sheet) if _truthy(r.get("enabled")) and str(r.get("new_value", "")).strip()]
    if not rows:
        result.skipped_files.append("No enabled rows with new_value found.")
        return result
    grouped: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        rel = row.get("file") or ""
        path = root / rel if rel else (_stage_candidates(root)[0] if _stage_candidates(root) else None)
        if not path or not path.exists():
            result.warnings.append(f"Stage DEF missing for row: {rel}")
            continue
        grouped.setdefault(path, []).append(row)
    for path, file_rows in grouped.items():
        text = read_text_safely(path)
        changed = 0
        for row in file_rows:
            section = str(row.get("section", "")).strip() or "StageInfo"
            key = str(row.get("key", "")).strip()
            new_value = str(row.get("new_value", "")).strip()
            if not key:
                continue
            sec_re = re.compile(r"^\s*\[\s*" + re.escape(section) + r"\s*\]", re.I)
            new_text = _set_text_state(text, sec_re, key, new_value)
            if new_text != text:
                text = new_text
                changed += 1
        if changed:
            backup = _backup_file(root, path, "stage_flow_apply")
            write_text_safely(path, text)
            result.changed_files.append(_rel(root, path))
            if backup:
                result.notes.append(f"Backup written: {_rel(root, backup)}")
            result.notes.append(f"Updated {changed} stage parameter(s) in {_rel(root, path)}.")
    return result


# ---------------------------------------------------------------------------
# Sound Board
# ---------------------------------------------------------------------------


def write_sound_waveform_board(root: Path) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Sound Waveform Board")
    out = _out(root, "sound_board")
    wavs = _wav_files(root)
    rows: List[Dict[str, object]] = []
    for idx, path in enumerate(wavs[:200]):
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                channels = wf.getnchannels()
                duration = frames / float(rate or 1)
                rows.append({"index": idx, "file": _rel(root, path), "duration_sec": f"{duration:.3f}", "rate": rate, "channels": channels, "cue_group": "", "cue_sound": "", "notes": ""})
        except Exception as exc:
            rows.append({"index": idx, "file": _rel(root, path), "duration_sec": "", "rate": "", "channels": "", "cue_group": "", "cue_sound": "", "notes": f"Unreadable WAV: {exc}"})
    _write_csv(root, out / "sound_waveform_index.csv", rows, ["index", "file", "duration_sec", "rate", "channels", "cue_group", "cue_sound", "notes"], result)
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        width = 1200
        row_h = 72
        height = max(160, 60 + min(len(wavs), 32) * row_h)
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 11)
            bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        except Exception:
            font = bold = None
        draw.text((18, 18), "Forge Flow Sound Waveform Board", fill=(0, 0, 0), font=bold)
        y = 54
        for row in rows[:32]:
            draw.rectangle([18, y, width - 18, y + row_h - 10], outline=(210, 210, 210), fill=(248, 248, 248))
            draw.text((28, y + 8), f"{row.get('index')}: {row.get('file')}", fill=(0, 0, 0), font=font)
            # Basic stylized waveform placeholder; do not decode huge samples here.
            try:
                dur = float(row.get("duration_sec") or 0)
            except Exception:
                dur = 0
            amp_w = min(820, max(20, int(80 + dur * 80)))
            base_x = 330
            base_y = y + 40
            for x in range(0, amp_w, 8):
                h = int(8 + 18 * abs(math.sin((x + int(row.get('index', 0)) * 17) / 21.0)))
                draw.line([(base_x + x, base_y - h), (base_x + x, base_y + h)], fill=(80, 80, 80))
            draw.text((base_x + amp_w + 18, y + 30), f"{row.get('duration_sec')}s {row.get('rate')}Hz", fill=(0, 0, 0), font=font)
            y += row_h
        png = out / "sound_waveform_board.png"
        img.save(png)
        result.add_created(root, png)
    except Exception as exc:
        result.warnings.append(f"Sound board PNG skipped: {exc}")
    html_rows = "".join(f"<tr><td>{r.get('index')}</td><td>{html.escape(str(r.get('file')))}</td><td>{r.get('duration_sec')}</td><td>{r.get('rate')}</td><td>{r.get('channels')}</td><td>{html.escape(str(r.get('notes')))}</td></tr>" for r in rows)
    html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Sound Board</title><style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px}}</style></head><body><h1>Forge Flow Sound Board</h1><p>Waveform board indexes loose WAV source files for cue planning. Packed SND rebuild/mutation remains conservative.</p><table><tr><th>#</th><th>File</th><th>Duration</th><th>Rate</th><th>Channels</th><th>Notes</th></tr>{html_rows}</table></body></html>"""
    _write_text(root, out / "sound_waveform_board.html", html_doc, result)
    if not wavs:
        result.warnings.append("No loose WAV files found. Export sounds or add source WAVs for waveform planning.")
    return result


# ---------------------------------------------------------------------------
# Bundle / one-click
# ---------------------------------------------------------------------------


def build_forge_flow_bundle(root: Path) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("Forge Flow Bundle")
    out = _out(root)
    zip_path = out / f"forge_flow_bundle_{timestamp()}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*"), key=lambda p: str(p).lower()):
            if not path.is_file() or path == zip_path:
                continue
            zf.write(path, path.relative_to(root))
    result.created_files.append(_rel(root, zip_path))
    result.notes.append("Forge Flow bundle contains v4.5 dashboards, sheets, previews, and reports only; it is not a release build of the character.")
    return result


def run_forge_flow_pass(root: Path) -> ForgeFlowResult:
    root = Path(root)
    result = ForgeFlowResult("One-Click Forge Flow Pass")
    result.merge(create_backup_snapshot(root, "forge_flow_v45"), "snapshot")
    result.merge(write_flow_mode_dashboard(root), "dashboard")
    result.merge(write_move_flow_timeline_pack(root), "move timeline")
    result.merge(export_state_flow_sheet(root), "state flow")
    result.merge(write_palette_studio(root), "palette studio")
    result.merge(write_stage_flow_preview(root), "stage flow")
    result.merge(write_sound_waveform_board(root), "sound board")
    result.merge(build_forge_flow_bundle(root), "bundle")
    result.notes.append("v4.5 Forge Flow pass complete. Start with forge_flow/FORGE_FLOW_START_HERE.md.")
    return result


# Backward-friendly alias names for likely UI/test references.
write_move_flow_pack = write_move_flow_timeline_pack
write_state_transition_sheet = export_state_flow_sheet
apply_state_transition_sheet = apply_state_flow_sheet
write_stage_preview = write_stage_flow_preview
