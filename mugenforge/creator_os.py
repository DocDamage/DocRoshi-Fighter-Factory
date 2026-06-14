from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import html
import json
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, write_text_safely
from .move_wizard import find_character_file
from .shared_utils import (
    BaseResult,
    uniq,
    rel_path,
    timestamp,
    backup_file,
    parse_first_int,
    get_code_files,
    scan_hitdefs,
    scan_commands,
    scan_air_stats,
    scan_state_anim_map,
)

CREATOR_OS_VERSION = "3.2.0"


@dataclass
class CreatorOSResult(BaseResult):
    title: str = "Creator OS"


_uniq = uniq
_rel = rel_path
_timestamp = timestamp
_backup = backup_file
_first_int = parse_first_int


def _creator_dir(root: Path) -> Path:
    out = Path(root) / "creator_os"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _code_files(root: Path) -> List[Path]:
    return get_code_files(root)


def _read_code(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in get_code_files(root):
        try:
            out[_rel(root, path)] = read_text_safely(path)
        except Exception:
            pass
    return out


def _command_defs(root: Path) -> Dict[str, Dict[str, object]]:
    out = {}
    for cmd in scan_commands(root):
        name = str(cmd['name']).strip()
        if name:
            out[name] = {
                "file": cmd['file'],
                "command": cmd['command'],
                "time": cmd['time'],
                "buffer.time": cmd['buffer_time']
            }
    return out


def _air_action_numbers(root: Path) -> Dict[int, object]:
    path = find_character_file(root, "air")
    if not path or not path.exists():
        return {}
    try:
        return {a.number: a for a in parse_air(read_text_safely(path))}
    except Exception:
        return {}


def _hitdef_blocks(root: Path) -> List[Dict[str, object]]:
    rows = []
    for hd in scan_hitdefs(root):
        rows.append({
            "file": hd['file'],
            "state": hd['state'],
            "header": hd['label'],
            "damage": hd['damage'],
            "attr": hd['attr'],
            "hitflag": hd['hitflag'],
            "guardflag": hd['guardflag'],
            "pausetime": hd['pausetime'],
            "sparkno": hd['sparkno'],
            "hitsound": hd['hitsound'],
            "guardsound": hd['guardsound'],
            "ground_velocity": hd['ground_velocity'],
            "air_velocity": hd['air_velocity'],
        })
    return rows


def _estimate_state_anim_map(root: Path) -> Dict[int, int]:
    return scan_state_anim_map(root)


def _air_total_ticks(root: Path) -> Dict[int, int]:
    return {num: stats['ticks'] for num, stats in scan_air_stats(root).items()}


def _state_defs_targets_anims(root: Path) -> Tuple[Dict[int, List[str]], Dict[int, List[str]], Dict[int, List[str]]]:
    defs: Dict[int, List[str]] = {}
    targets: Dict[int, List[str]] = {}
    anims: Dict[int, List[str]] = {}
    for rel, text in _read_code(root).items():
        scan = parse_code(text)
        for st in scan.states:
            defs.setdefault(st.number, []).append(rel)
            if "anim" in st.values:
                anims.setdefault(_first_int(st.values.get("anim")), []).append(f"{rel}:StateDef {st.number}")
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype == "changestate" and "value" in ctrl.values:
                    val = ctrl.values.get("value", "")
                    if re.fullmatch(r"\s*-?\d+\s*", val):
                        targets.setdefault(int(val), []).append(f"{rel}:StateDef {st.number}")
                if stype == "changeanim" and "value" in ctrl.values:
                    val = ctrl.values.get("value", "")
                    if re.fullmatch(r"\s*-?\d+\s*", val):
                        anims.setdefault(int(val), []).append(f"{rel}:StateDef {st.number}")
    return defs, targets, anims


def _system_score(root: Path) -> Dict[str, object]:
    root = Path(root)
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    air = _air_action_numbers(root)
    commands = _command_defs(root)
    missing_states = sorted([t for t in targets if t >= 0 and t not in defs])
    missing_anims = sorted([a for a in anim_refs if a >= 0 and a not in air])
    has_def = bool(find_character_file(root, "def"))
    has_cmd = bool(find_character_file(root, "cmd"))
    has_cns = bool(find_character_file(root, "cns"))
    has_air = bool(find_character_file(root, "air"))
    has_sff = bool(find_character_file(root, "sff"))
    has_snd = bool(find_character_file(root, "snd"))
    score = 0
    checks = {
        "DEF present": has_def,
        "CMD present": has_cmd,
        "CNS/ST present": has_cns,
        "AIR present": has_air,
        "SFF present": has_sff,
        "SND present": has_snd,
        "At least one command": bool(commands),
        "At least one StateDef": bool(defs),
        "At least one AIR action": bool(air),
        "No missing ChangeState targets": not missing_states,
        "No missing AIR actions referenced by code": not missing_anims,
    }
    for ok in checks.values():
        score += 9 if ok else 0
    return {
        "score": min(100, score),
        "checks": checks,
        "missing_states": missing_states,
        "missing_anims": missing_anims,
        "commands": commands,
        "statedefs": sorted(defs),
        "targets": sorted(targets),
        "air_actions": sorted(air),
    }


def creator_os_status_report(root: Path) -> str:
    root = Path(root)
    data = _system_score(root)
    lines = [f"Creator OS Status: {root.name}", "=" * (19 + len(root.name)), "", f"Readiness score: {data['score']}/100", ""]
    lines.append("Core checks:")
    checks: Dict[str, bool] = data["checks"]  # type: ignore[assignment]
    for label, ok in checks.items():
        lines.append(f"- {'OK' if ok else 'NEEDS WORK'}: {label}")
    if data["missing_states"]:
        lines += ["", "Missing StateDefs that code tries to ChangeState into:"] + [f"- {x}" for x in data["missing_states"][:80]]
    if data["missing_anims"]:
        lines += ["", "Missing AIR actions referenced by code:"] + [f"- {x}" for x in data["missing_anims"][:80]]
    lines += ["", "Detected totals:", f"- Commands: {len(data['commands'])}", f"- StateDefs: {len(data['statedefs'])}", f"- AIR actions: {len(data['air_actions'])}"]
    lines += ["", "Recommended next action:"]
    if data["missing_states"]:
        lines.append("- Run Auto-Fix Missing StateDefs. It appends safe fallback states with backups.")
    elif data["missing_anims"]:
        lines.append("- Run Auto-Create Missing AIR Actions. It adds visible placeholder actions with body CLSN.")
    elif int(data["score"]) < 75:
        lines.append("- Run Creator OS One-Click Pass, then open the generated dashboard.")
    else:
        lines.append("- Tune feel: use Frame Data Sheet, Combo Routes, Balance Presets, Animation Player, and CLSN Editor.")
    return "\n".join(lines).rstrip() + "\n"


def write_creator_os_dashboard(root: Path) -> Path:
    root = Path(root)
    outdir = _creator_dir(root)
    status = _system_score(root)
    hits = _hitdef_blocks(root)
    commands = status["commands"]
    rows = []
    for name, info in sorted(commands.items()):
        rows.append(f"| `{name}` | `{info.get('command','')}` | `{info.get('file','')}` |")
    if not rows:
        rows.append("| _None yet_ |  |  |")
    body = f"""# MugenForge Creator OS Dashboard

Project: `{root.name}`
Generated: {datetime.now().isoformat(timespec='seconds')}
Creator OS version: {CREATOR_OS_VERSION}

## Plain-English status

{creator_os_status_report(root)}

## What to do next

1. Fix blockers first: missing StateDefs, missing AIR actions, missing SFF/SND files.
2. Pick no-code features from the Feature Bank or edit `creator_os/function_bank/*.json` as planning cards.
3. Use `FRAME_DATA_SHEET.csv` and `MOVE_TUNING_BOARD.csv` to tune timing, damage, pushback, and hit feel.
4. Use Animation Player and CLSN Editor for the fun part: making the move look and feel right.
5. Run Quality Lab and build a release ZIP only after placeholders are replaced.

## Command map

| Command name | Input | File |
|---|---:|---|
{chr(10).join(rows)}

## HitDef summary

Detected HitDefs: **{len(hits)}**

See:

- `FRAME_DATA_SHEET.csv`
- `MOVE_TUNING_BOARD.csv`
- `COMBO_ROUTES.json`
- `INPUT_MAPPER.json`
- `function_bank/`
- `PROJECT_WEB_PREVIEW.html`
"""
    return _write(outdir / "CREATOR_OS_DASHBOARD.md", body)


_FUNCTION_BANK = [
    {
        "id": "normal_attack_starter",
        "name": "Normal Attack Starter",
        "category": "Attacks",
        "plain_english": "Use this when you need a new punch/kick with startup, active frames, recovery, HitDef, sound, and AIR placeholder frames.",
        "user_controls": ["move name", "button", "state number", "damage", "reach", "startup", "recovery", "sound cue"],
        "outputs": ["CMD command", "Statedef -1 ChangeState", "CNS StateDef", "AIR action", "default Clsn1/Clsn2"],
    },
    {
        "id": "projectile_starter",
        "name": "Projectile Starter",
        "category": "Specials",
        "plain_english": "Creates a motion special and a projectile helper/controller starter. The user tunes speed, damage, hit angle, sprite, and sound.",
        "user_controls": ["input motion", "state number", "projectile speed", "projectile art group", "damage", "hit sound"],
        "outputs": ["CMD", "CNS", "AIR projectile action", "sound placeholders"],
    },
    {
        "id": "combo_cancel_router",
        "name": "Combo Cancel Router",
        "category": "Combat Systems",
        "plain_english": "Adds safe ChangeState links between moves so a beginner can build chains without writing triggers manually.",
        "user_controls": ["from state", "to state", "command", "cancel window", "hit/guard requirement"],
        "outputs": ["CNS combo cancel controllers"],
    },
    {
        "id": "air_action_autofill",
        "name": "AIR Action Autofill",
        "category": "Animation",
        "plain_english": "Creates missing AIR actions for states that reference animations that do not exist yet.",
        "user_controls": ["body box", "frame count", "ticks", "sprite group"],
        "outputs": ["AIR placeholder action blocks"],
    },
    {
        "id": "balance_preset",
        "name": "Balance Preset",
        "category": "Tuning",
        "plain_english": "Scales HitDef damage across code files with backups. Useful when a prototype hits too hard or too weak.",
        "user_controls": ["preset", "damage multiplier", "damage cap"],
        "outputs": ["patched CNS/ST/CMD code with backups", "balance report"],
    },
    {
        "id": "input_mapper",
        "name": "Input Mapper",
        "category": "Inputs",
        "plain_english": "Writes an editable JSON list of commands; applying it rewrites command inputs for the user.",
        "user_controls": ["command name", "new input", "time", "buffer time"],
        "outputs": ["patched CMD with backups"],
    },
    {
        "id": "release_web_preview",
        "name": "Release Web Preview",
        "category": "Publishing",
        "plain_english": "Creates a local HTML page showing project status, commands, moves, and beginner release notes.",
        "user_controls": ["none"],
        "outputs": ["PROJECT_WEB_PREVIEW.html"],
    },
]


def write_function_bank(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Function Bank")
    outdir = _creator_dir(root) / "function_bank"
    outdir.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Creator OS Function Bank", "", "These JSON cards are a no-code planning bank. They describe what the tool can generate or repair for a beginner without asking them to hand-code CMD/CNS/AIR blocks.", ""]
    for item in _FUNCTION_BANK:
        path = outdir / f"{item['id']}.json"
        path.write_text(json.dumps(item, indent=2), encoding="utf-8")
        result.add_created(path)
        index_lines.append(f"- **{item['name']}** (`{item['id']}`): {item['plain_english']}")
    index = _write(outdir / "FUNCTION_BANK_INDEX.md", "\n".join(index_lines))
    result.add_created(index)
    return result


def write_frame_data_sheet(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Frame Data Sheet")
    outdir = _creator_dir(root)
    state_anim = _estimate_state_anim_map(root)
    ticks = _air_total_ticks(root)
    hitdefs = _hitdef_blocks(root)
    hit_by_state: Dict[int, List[Dict[str, object]]] = {}
    for hd in hitdefs:
        st = hd.get("state")
        if isinstance(st, int):
            hit_by_state.setdefault(st, []).append(hd)
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    rows: List[Dict[str, object]] = []
    for st in sorted(defs):
        anim = state_anim.get(st, st if st in ticks else 0)
        total = ticks.get(anim, 0)
        damage = sum(int(h.get("damage", 0) or 0) for h in hit_by_state.get(st, []))
        has_hitdef = "yes" if hit_by_state.get(st) else "no"
        category = "system"
        if damage > 0:
            category = "attack"
        elif st in {0, 10, 11, 12, 20, 21, 40, 41, 42, 47, 100, 105}:
            category = "movement/basic"
        elif 5000 <= st <= 5999:
            category = "get-hit/system"
        note = "Tune by feel."
        if has_hitdef == "yes" and total:
            note = "Check startup/active/recovery in Animation Player."
        elif has_hitdef == "yes":
            note = "HitDef exists but AIR timing is unknown/missing."
        rows.append({"state": st, "anim": anim, "category": category, "total_air_ticks": total, "hitdefs": len(hit_by_state.get(st, [])), "damage_total": damage, "defined_in": "; ".join(defs.get(st, [])), "notes": note})
    csv_path = outdir / "FRAME_DATA_SHEET.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["state", "anim", "category", "total_air_ticks", "hitdefs", "damage_total", "defined_in", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    md_lines = ["# Frame Data Sheet", "", "This is an approximate no-code tuning sheet. It reads StateDefs, Anim references, AIR action ticks, and HitDefs.", "", "| State | Anim | Category | AIR ticks | HitDefs | Damage | Notes |", "|---:|---:|---|---:|---:|---:|---|"]
    for row in rows:
        md_lines.append(f"| {row['state']} | {row['anim']} | {row['category']} | {row['total_air_ticks']} | {row['hitdefs']} | {row['damage_total']} | {row['notes']} |")
    md_path = _write(outdir / "FRAME_DATA_SHEET.md", "\n".join(md_lines))
    result.add_created(csv_path)
    result.add_created(md_path)
    return result


def write_move_tuning_board(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Move Tuning Board")
    outdir = _creator_dir(root)
    hitdefs = _hitdef_blocks(root)
    state_anim = _estimate_state_anim_map(root)
    ticks = _air_total_ticks(root)
    rows: List[Dict[str, object]] = []
    for hd in hitdefs:
        st = int(hd.get("state") or 0)
        anim = state_anim.get(st, st)
        damage = int(hd.get("damage") or 0)
        tier = "light"
        if damage >= 90:
            tier = "super/heavy"
        elif damage >= 55:
            tier = "heavy"
        elif damage >= 30:
            tier = "medium"
        suggestion = "OK starter range"
        if damage <= 0:
            suggestion = "No damage parsed; inspect HitDef."
        elif damage > 150:
            suggestion = "Very high; boss/super only."
        elif damage < 15:
            suggestion = "Very low; chip/utility only."
        rows.append({
            "state": st, "anim": anim, "tier_guess": tier, "damage": damage,
            "air_ticks": ticks.get(anim, 0), "pausetime": hd.get("pausetime", ""),
            "ground_velocity": hd.get("ground_velocity", ""), "air_velocity": hd.get("air_velocity", ""),
            "suggestion": suggestion,
        })
    csv_path = outdir / "MOVE_TUNING_BOARD.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["state", "anim", "tier_guess", "damage", "air_ticks", "pausetime", "ground_velocity", "air_velocity", "suggestion"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    md_lines = ["# Move Tuning Board", "", "Use this when a move feels wrong but you do not want to dig through code first.", "", "| State | Tier | Damage | AIR ticks | Pushback | Suggestion |", "|---:|---|---:|---:|---|---|"]
    for row in rows:
        md_lines.append(f"| {row['state']} | {row['tier_guess']} | {row['damage']} | {row['air_ticks']} | `{row['ground_velocity']}` | {row['suggestion']} |")
    if not rows:
        md_lines.append("| _No HitDefs detected yet_ | | | | | Add moves from Feature Bank or Move Wizard. |")
    md_path = _write(outdir / "MOVE_TUNING_BOARD.md", "\n".join(md_lines))
    result.add_created(csv_path)
    result.add_created(md_path)
    return result


def write_input_mapper_template(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Input Mapper Template")
    commands = _command_defs(root)
    data = {
        "instructions": "Edit new_command/time/buffer_time, then use Apply Input Mapper. Command names must match existing [Command] name values.",
        "commands": [
            {"name": name, "current_command": info.get("command", ""), "new_command": info.get("command", ""), "time": info.get("time", ""), "buffer_time": info.get("buffer.time", ""), "file": info.get("file", "")}
            for name, info in sorted(commands.items())
        ],
        "examples": {"quarter_circle_forward_x": "~D, DF, F, x", "dragon_punch_y": "~F, D, DF, y", "dash_forward": "F, F"},
    }
    path = _creator_dir(root) / "INPUT_MAPPER.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result.add_created(path)
    if not commands:
        result.add_warning("No [Command] definitions found yet. Add Feature Bank commands or run project setup first.")
    return result


def _replace_command_block(block: str, new_command: Optional[str], new_time: Optional[str], new_buffer: Optional[str]) -> str:
    def sub_or_append(text: str, key: str, value: str) -> str:
        if value is None or str(value).strip() == "":
            return text
        pattern = re.compile(rf"(^\s*{re.escape(key)}\s*=\s*)(.*?)(\s*(?:;.*)?$)", re.I | re.M)
        if pattern.search(text):
            return pattern.sub(lambda m: f"{m.group(1)}{value}{m.group(3)}", text, count=1)
        return text.rstrip() + f"\n{key} = {value}\n"
    out = block
    if new_command is not None:
        out = sub_or_append(out, "command", str(new_command))
    if new_time is not None:
        out = sub_or_append(out, "time", str(new_time))
    if new_buffer is not None:
        out = sub_or_append(out, "buffer.time", str(new_buffer))
    return out


def apply_input_mapper(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Apply Input Mapper")
    mapper = _creator_dir(root) / "INPUT_MAPPER.json"
    if not mapper.exists():
        result.add_warning("INPUT_MAPPER.json not found. Run Write Input Mapper Template first.")
        return result
    data = json.loads(mapper.read_text(encoding="utf-8"))
    desired: Dict[str, Dict[str, str]] = {}
    for item in data.get("commands", []):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        desired[name] = {
            "new_command": str(item.get("new_command", "")).strip(),
            "time": str(item.get("time", "")).strip(),
            "buffer_time": str(item.get("buffer_time", "")).strip(),
        }
    if not desired:
        result.add_warning("INPUT_MAPPER.json has no commands to apply.")
        return result
    cmd_section_re = re.compile(r"(^\s*\[\s*Command\s*\]\s*$.*?)(?=^\s*\[|\Z)", re.I | re.M | re.S)
    name_re = re.compile(r"^\s*name\s*=\s*\"?([^\"\n;]+)\"?", re.I | re.M)
    changed_any = False
    for path in sorted(Path(root).rglob("*.cmd")):
        if not path.is_file():
            continue
        old = read_text_safely(path)
        changed = False
        def repl(match: re.Match) -> str:
            nonlocal changed
            block = match.group(1)
            nm = name_re.search(block)
            if not nm:
                return block
            name = nm.group(1).strip()
            if name not in desired:
                return block
            spec = desired[name]
            new = _replace_command_block(block, spec.get("new_command"), spec.get("time"), spec.get("buffer_time"))
            if new != block:
                changed = True
            return new
        new_text = cmd_section_re.sub(repl, old)
        if changed and new_text != old:
            b = _backup(path)
            write_text_safely(path, new_text)
            result.add_changed(f"{_rel(root, path)} updated from INPUT_MAPPER.json")
            if b:
                result.add_created(b)
            changed_any = True
    if not changed_any:
        result.add_note("No command changes were needed or no matching command names were found.")
    return result


def write_combo_routes_template(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Combo Routes Template")
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    commands = _command_defs(root)
    attack_states = []
    for hd in _hitdef_blocks(root):
        st = hd.get("state")
        if isinstance(st, int) and st not in attack_states:
            attack_states.append(st)
    attack_states = sorted(attack_states)
    command_names = sorted(commands)[:20]
    routes = []
    for i in range(len(attack_states) - 1):
        routes.append({
            "label": f"Route {i+1}",
            "from_state": attack_states[i],
            "to_state": attack_states[i + 1],
            "command": command_names[min(i + 1, len(command_names) - 1)] if command_names else "change_me",
            "start_time": 3,
            "end_time": 18,
            "requires_hit_or_guard": True,
            "enabled": True,
        })
    if not routes:
        routes = [{"label": "Example light-to-medium", "from_state": 200, "to_state": 210, "command": "medium_punch", "start_time": 3, "end_time": 18, "requires_hit_or_guard": True, "enabled": False}]
    data = {
        "instructions": "Edit routes, set enabled true, then use Apply Combo Routes. This appends beginner-safe ChangeState cancel controllers with backups.",
        "routes": routes,
    }
    path = _creator_dir(root) / "COMBO_ROUTES.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result.add_created(path)
    return result


def apply_combo_routes(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Apply Combo Routes")
    route_path = _creator_dir(root) / "COMBO_ROUTES.json"
    if not route_path.exists():
        result.add_warning("COMBO_ROUTES.json not found. Run Write Combo Routes Template first.")
        return result
    data = json.loads(route_path.read_text(encoding="utf-8"))
    routes = [r for r in data.get("routes", []) if r.get("enabled")]
    if not routes:
        result.add_warning("No enabled combo routes found in COMBO_ROUTES.json.")
        return result
    cns = find_character_file(root, "cns")
    if not cns:
        result.add_warning("No CNS/ST target file found.")
        return result
    old = read_text_safely(cns)
    marker = "; MugenForge Creator OS Combo Routes"
    blocks = ["", marker, f"; Generated: {datetime.now().isoformat(timespec='seconds')}", "; Edit COMBO_ROUTES.json and reapply if you need different links.", ""]
    for r in routes:
        try:
            from_state = int(r.get("from_state"))
            to_state = int(r.get("to_state"))
        except Exception:
            result.add_warning(f"Skipped invalid route: {r}")
            continue
        command = str(r.get("command", "")).strip() or "change_me"
        start = _first_int(r.get("start_time"), 1)
        end = _first_int(r.get("end_time"), 999)
        label = str(r.get("label", f"{from_state} to {to_state}"))
        contact = "MoveContact" if r.get("requires_hit_or_guard", True) else "1"
        blocks.append(f"[State {from_state}, Creator OS combo route - {label}]")
        blocks.append("type = ChangeState")
        blocks.append(f"triggerall = command = \"{command}\"")
        blocks.append(f"triggerall = Time >= {start}")
        blocks.append(f"triggerall = Time <= {end}")
        blocks.append(f"trigger1 = {contact}")
        blocks.append(f"value = {to_state}")
        blocks.append("ctrl = 0")
        blocks.append("")
    block_text = "\n".join(blocks).rstrip() + "\n"
    if marker in old:
        result.add_warning("Combo route marker already exists. To avoid stacking duplicates, remove the old generated block manually or use a fresh CNS copy.")
        return result
    b = _backup(cns)
    write_text_safely(cns, old.rstrip() + "\n\n" + block_text)
    result.add_changed(f"{_rel(root, cns)} appended combo route controllers")
    if b:
        result.add_created(b)
    return result


def _safe_state_stub(state_no: int) -> str:
    return f"""; Creator OS auto-generated fallback. Replace with a real move/state later.
[Statedef {state_no}]
type = S
movetype = I
physics = S
anim = 0
ctrl = 0
sprpriority = 2

[State {state_no}, Label]
type = DisplayToClipboard
trigger1 = Time = 0
text = "Creator OS placeholder StateDef {state_no}: replace this with real behavior"
ignorehitpause = 1

[State {state_no}, Return to idle]
type = ChangeState
trigger1 = Time >= 1
value = 0
ctrl = 1
"""


def auto_fix_missing_statedefs(root: Path, limit: int = 80) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Auto-Fix Missing StateDefs")
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    missing = [x for x in sorted(targets) if x >= 0 and x not in defs]
    if not missing:
        result.add_note("No missing ChangeState target StateDefs detected.")
        return result
    cns = find_character_file(root, "cns")
    if not cns:
        result.add_warning("No CNS/ST target file found.")
        return result
    missing = missing[:max(1, limit)]
    old = read_text_safely(cns)
    marker = "; MugenForge Creator OS Missing StateDef Repair"
    block = "\n\n" + marker + f"\n; Generated: {datetime.now().isoformat(timespec='seconds')}\n" + "\n".join(_safe_state_stub(n) for n in missing)
    b = _backup(cns)
    write_text_safely(cns, old.rstrip() + block + "\n")
    result.add_changed(f"{_rel(root, cns)} appended {len(missing)} safe placeholder StateDefs")
    if b:
        result.add_created(b)
    result.add_note("These placeholders prevent broken ChangeState targets from being invisible. Replace them with real movement/attack logic when ready.")
    return result


def _air_placeholder(action_no: int, frames: int = 4, ticks: int = 6) -> str:
    label = COMMON_ANIMS.get(action_no, "Creator OS placeholder")
    lines = [f"[Begin Action {action_no}] ; {label}"]
    for i in range(max(1, frames)):
        lines.append("Clsn2: 1")
        lines.append("  Clsn2[0] = -18,-82,18,0")
        lines.append(f"{action_no}, {i}, 0, 0, {max(1, ticks)}")
    return "\n".join(lines) + "\n"


def auto_create_missing_air_actions(root: Path, limit: int = 160) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Auto-Create Missing AIR Actions")
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    air_actions = _air_action_numbers(root)
    missing = [a for a in sorted(anim_refs) if a >= 0 and a not in air_actions]
    if not missing:
        result.add_note("No missing AIR actions referenced by code were detected.")
        return result
    air = find_character_file(root, "air")
    if not air:
        result.add_warning("No AIR target file found.")
        return result
    missing = missing[:max(1, limit)]
    old = read_text_safely(air)
    marker = "; MugenForge Creator OS Missing AIR Repair"
    block = "\n\n" + marker + f"\n; Generated: {datetime.now().isoformat(timespec='seconds')}\n" + "\n".join(_air_placeholder(n) for n in missing)
    b = _backup(air)
    write_text_safely(air, old.rstrip() + block + "\n")
    result.add_changed(f"{_rel(root, air)} appended {len(missing)} placeholder AIR actions")
    if b:
        result.add_created(b)
    result.add_note("These are visual placeholders with basic body boxes. Replace frame sprite IDs/art later.")
    return result


_BALANCE_PRESETS = {
    "Training Low Damage": {"factor": 0.50, "cap": 80, "note": "Good for debugging long combos without ending rounds too fast."},
    "Beginner Safe": {"factor": 0.85, "cap": 120, "note": "Safer prototype values while testing feel."},
    "Arcade Standard": {"factor": 1.00, "cap": 160, "note": "Normalizes extreme values but mostly keeps damage unchanged."},
    "Boss Prototype": {"factor": 1.25, "cap": 240, "note": "Raises damage for boss/prototype testing."},
}


def balance_preset_names() -> List[str]:
    return list(_BALANCE_PRESETS)


def apply_balance_preset(root: Path, preset_name: str) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult(f"Creator OS Balance Preset: {preset_name}")
    preset = _BALANCE_PRESETS.get(preset_name) or _BALANCE_PRESETS["Beginner Safe"]
    factor = float(preset["factor"])
    cap = int(preset["cap"])
    block_re = re.compile(r"(^\s*\[\s*State\s+[^\]]+\]\s*$.*?)(?=^\s*\[|\Z)", re.I | re.M | re.S)
    type_hitdef_re = re.compile(r"^\s*type\s*=\s*HitDef\b", re.I | re.M)
    damage_re = re.compile(r"(^\s*damage\s*=\s*)(-?\d+)(.*?$)", re.I | re.M)
    total_changes = 0
    for path in _code_files(root):
        old = read_text_safely(path)
        changed = False
        def repl_block(match: re.Match) -> str:
            nonlocal changed, total_changes
            block = match.group(1)
            if not type_hitdef_re.search(block):
                return block
            def repl_damage(dm: re.Match) -> str:
                nonlocal changed, total_changes
                old_val = int(dm.group(2))
                new_val = max(0, min(cap, int(round(old_val * factor))))
                if new_val != old_val:
                    changed = True
                    total_changes += 1
                return f"{dm.group(1)}{new_val}{dm.group(3)}"
            return damage_re.sub(repl_damage, block, count=1)
        new_text = block_re.sub(repl_block, old)
        if changed and new_text != old:
            b = _backup(path)
            write_text_safely(path, new_text)
            result.add_changed(f"{_rel(root, path)} scaled HitDef damage values")
            if b:
                result.add_created(b)
    result.add_note(str(preset.get("note", "")))
    result.add_note(f"Changed {total_changes} HitDef damage value(s).")
    if total_changes == 0:
        result.add_warning("No HitDef damage values were changed.")
    write_move_tuning_board(root)
    return result


def write_project_web_preview(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Project Web Preview")
    outdir = _creator_dir(root)
    status = creator_os_status_report(root)
    commands = _command_defs(root)
    hitdefs = _hitdef_blocks(root)
    frame_rows = []
    state_anim = _estimate_state_anim_map(root)
    ticks = _air_total_ticks(root)
    defs, targets, anim_refs = _state_defs_targets_anims(root)
    for st in sorted(defs):
        anim = state_anim.get(st, st)
        frame_rows.append((st, anim, ticks.get(anim, 0)))
    cmd_html = "".join(f"<tr><td>{html.escape(k)}</td><td><code>{html.escape(str(v.get('command','')))}</code></td><td>{html.escape(str(v.get('file','')))}</td></tr>" for k, v in sorted(commands.items())) or "<tr><td colspan='3'>No commands found yet.</td></tr>"
    hit_html = "".join(f"<tr><td>{h.get('state','')}</td><td>{h.get('damage','')}</td><td>{html.escape(str(h.get('attr','')))}</td><td><code>{html.escape(str(h.get('ground_velocity','')))}</code></td></tr>" for h in hitdefs) or "<tr><td colspan='4'>No HitDefs found yet.</td></tr>"
    frame_html = "".join(f"<tr><td>{st}</td><td>{an}</td><td>{tk}</td></tr>" for st, an, tk in frame_rows[:400]) or "<tr><td colspan='3'>No StateDefs found yet.</td></tr>"
    doc = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{html.escape(root.name)} Creator OS Preview</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;line-height:1.4}}table{{border-collapse:collapse;width:100%;margin:12px 0}}th,td{{border:1px solid #ccc;padding:6px 8px;text-align:left}}code,pre{{background:#f5f5f5;padding:2px 4px}}section{{margin-bottom:28px}}.score{{font-size:22px;font-weight:bold}}</style></head>
<body><h1>{html.escape(root.name)} — Creator OS Preview</h1>
<p>Generated {datetime.now().isoformat(timespec='seconds')} by MugenForge Creator OS {CREATOR_OS_VERSION}.</p>
<section><h2>Status</h2><pre>{html.escape(status)}</pre></section>
<section><h2>Commands</h2><table><tr><th>Name</th><th>Input</th><th>File</th></tr>{cmd_html}</table></section>
<section><h2>HitDefs</h2><table><tr><th>State</th><th>Damage</th><th>Attr</th><th>Ground velocity</th></tr>{hit_html}</table></section>
<section><h2>State / Animation Timing</h2><table><tr><th>State</th><th>Anim</th><th>AIR ticks</th></tr>{frame_html}</table></section>
<section><h2>Beginner release notes</h2><ul><li>Replace placeholder sprites/sounds before release.</li><li>Run Quality Lab and fix missing references.</li><li>Use the Animation Player and CLSN Editor to tune feel.</li><li>Package only after testing in M.U.G.E.N.</li></ul></section>
</body></html>"""
    path = outdir / "PROJECT_WEB_PREVIEW.html"
    path.write_text(doc, encoding="utf-8")
    result.add_created(path)
    return result


def create_creator_restore_point(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS Restore Point")
    outdir = _creator_dir(root) / "restore_points"
    outdir.mkdir(parents=True, exist_ok=True)
    zip_path = outdir / f"{root.name}_creatoros_restore_{_timestamp()}.zip"
    skip_suffixes = (".bak", ".tmp")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path == zip_path or not path.is_file():
                continue
            if any(part == "__pycache__" for part in path.parts):
                continue
            if path.suffix.lower() in skip_suffixes:
                continue
            try:
                zf.write(path, path.relative_to(root))
            except Exception:
                pass
    result.add_created(zip_path)
    result.add_note("Restore points are ordinary ZIP files. Extract manually if you need to roll back.")
    return result


def write_beginner_autopilot_plan(root: Path) -> Path:
    status = _system_score(root)
    steps = []
    if status["missing_states"]:
        steps.append("Run Auto-Fix Missing StateDefs.")
    if status["missing_anims"]:
        steps.append("Run Auto-Create Missing AIR Actions.")
    if not status["commands"]:
        steps.append("Install a Feature Bank kit or use Move Wizard to add commands/moves.")
    steps += [
        "Open Animation Player and check whether motion reads clearly.",
        "Open CLSN Editor and adjust body/attack boxes by dragging handles.",
        "Use Move Tuning Board to adjust damage/pushback.",
        "Use Input Mapper if commands feel awkward.",
        "Run Quality Lab, replace placeholders, then build a release ZIP.",
    ]
    body = "# Beginner Autopilot Plan\n\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps)) + "\n"
    return _write(_creator_dir(root) / "BEGINNER_AUTOPILOT_PLAN.md", body)


def one_click_creator_os_pass(root: Path) -> CreatorOSResult:
    root = Path(root)
    result = CreatorOSResult("Creator OS One-Click Pass")
    _creator_dir(root)
    for func, label in [
        (write_function_bank, "function bank"),
        (write_frame_data_sheet, "frame data"),
        (write_move_tuning_board, "move tuning"),
        (write_input_mapper_template, "input mapper"),
        (write_combo_routes_template, "combo routes"),
        (write_project_web_preview, "web preview"),
    ]:
        try:
            sub = func(root)
            result.merge(sub, label)
        except Exception as exc:
            result.add_warning(f"{label} failed: {exc}")
    try:
        dash = write_creator_os_dashboard(root)
        result.add_created(dash)
    except Exception as exc:
        result.add_warning(f"dashboard failed: {exc}")
    try:
        plan = write_beginner_autopilot_plan(root)
        result.add_created(plan)
    except Exception as exc:
        result.add_warning(f"autopilot plan failed: {exc}")
    try:
        restore = create_creator_restore_point(root)
        result.merge(restore, "restore point")
    except Exception as exc:
        result.add_warning(f"restore point failed: {exc}")
    result.add_note("This pass writes dashboards/templates/reports and a restore ZIP. Use the separate repair/apply buttons when you want generated code changes.")
    return result

# ---------------------------------------------------------------------------
# Compatibility wrappers for the older Creator OS UI route used by app.py.
# The current Creator OS engine above is richer; these keep old button names
# working while routing into the newer no-code reports and autopilot files.
# ---------------------------------------------------------------------------

def _co_result(title: str, paths: Sequence[Path] = (), notes: Sequence[str] = ()) -> CreatorOSResult:
    r = CreatorOSResult(title)
    for p in paths:
        r.add_created(str(p))
    for n in notes:
        r.add_note(n)
    return r


def creator_os_one_click(root: Path, archetype: str = "Balanced Starter", complexity: str = "Beginner", visual_style: str = "Arcade") -> CreatorOSResult:
    return one_click_creator_os_pass(Path(root))


def write_character_blueprint(root: Path, archetype: str = "Balanced Starter", complexity: str = "Beginner", visual_style: str = "Arcade") -> CreatorOSResult:
    root = Path(root)
    out = _creator_dir(root) / "CHARACTER_BLUEPRINT.md"
    text = f"""# Character Blueprint: {root.name}

Generated: {datetime.now().isoformat(timespec='seconds')}

## Profile
- Archetype: {archetype}
- Complexity: {complexity}
- Visual style: {visual_style}

## Creator choices
- Silhouette
- Main colors
- Movement feel
- Signature normal
- Signature special
- Super move fantasy
- Voice/sound identity

## MugenForge automation
- Use Feature Bank and Creator Suite to write starter CMD/CNS/AIR.
- Use Sprite Lab and Image Factory for assets.
- Use Animation Player and CLSN Editor for timing/hitboxes.
- Use Quality Lab / Factory Ultra before release.
"""
    _write(out, text)
    return _co_result("Creator OS Character Blueprint", [out], ["Blueprint written for no-code planning."])


def export_frame_data_sheet(root: Path) -> CreatorOSResult:
    return write_frame_data_sheet(Path(root))


def export_input_cheatsheet(root: Path) -> CreatorOSResult:
    return write_input_mapper_template(Path(root))


def write_combo_routes(root: Path) -> CreatorOSResult:
    return write_combo_routes_template(Path(root))


def write_balance_report(root: Path) -> CreatorOSResult:
    return write_move_tuning_board(Path(root))


def write_release_quality_gate(root: Path) -> CreatorOSResult:
    root = Path(root)
    out = _creator_dir(root) / "RELEASE_QUALITY_GATE.md"
    score = _system_score(root)
    checks = [
        "All required files exist",
        "Commands resolve to states",
        "ChangeAnim references have AIR actions",
        "AIR sprite refs have SFF sprites or placeholder plan",
        "SND refs have WAV/SND replacements or placeholder plan",
        "Hitboxes reviewed in Animation Player/CLSN Editor",
        "Credits/license notes written",
        "Clean release ZIP built",
    ]
    text = [f"# Release Quality Gate: {root.name}", "", f"Readiness score: **{score.get('score', 0)} / 100**", "", "## Manual gate"] + [f"- [ ] {x}" for x in checks]
    _write(out, "\n".join(text) + "\n")
    return _co_result("Creator OS Quality Gate", [out], ["Quality gate checklist written."])


def write_asset_shopping_list(root: Path) -> CreatorOSResult:
    root = Path(root)
    out = _creator_dir(root) / "ASSET_SHOPPING_LIST.md"
    defs, targets, anims = _state_defs_targets_anims(root)
    actions = _air_action_numbers(root)
    missing_anims = sorted(a for a in anims if a not in actions and a >= 0)
    text = [f"# Asset Shopping List: {root.name}", "", "## Animation/action needs"]
    text += [f"- AIR action `{a}` referenced by {', '.join(anims[a][:3])}" for a in missing_anims[:200]] or ["- No missing ChangeAnim/AIR action refs detected."]
    text += ["", "## Standard replacement categories", "- Idle/walk/jump sprites", "- Attacks/specials/supers", "- Hit/get-up/guard sprites", "- Hitsparks/FX", "- Voice and hit sounds", "- Palettes"]
    _write(out, "\n".join(text) + "\n")
    return _co_result("Creator OS Asset Shopping List", [out], [f"Listed {len(missing_anims)} missing animation refs."])


def write_beginner_lessons(root: Path) -> CreatorOSResult:
    root = Path(root)
    out = _creator_dir(root) / "BEGINNER_LESSONS.md"
    text = """# Beginner Lessons

1. Open the character folder.
2. Run Creator OS Autopilot.
3. Replace placeholder art with Sprite Lab or Sheet Import.
4. Use Animation Player to feel the timing.
5. Use CLSN Editor to drag hitboxes.
6. Use HitDef Tuning Sheet to change damage/pushback without hand-editing code.
7. Run Quality Lab and Factory Ultra before release.
"""
    _write(out, text)
    return _co_result("Creator OS Beginner Lessons", [out])


def write_project_wiki(root: Path) -> CreatorOSResult:
    root = Path(root)
    dashboard = write_creator_os_dashboard(root)
    preview = write_project_web_preview(root)
    return _co_result("Creator OS Project Wiki", [dashboard, preview], ["Dashboard and web preview written."])


def write_autocode_cookbook(root: Path) -> CreatorOSResult:
    return write_function_bank(Path(root))


def build_creator_os_release_zip(root: Path) -> CreatorOSResult:
    root = Path(root)
    out = root.parent / f"{root.name}_creator_os_release_{_timestamp()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix.lower() == ".pyc":
                continue
            zf.write(p, arcname=str(p.relative_to(root)).replace("\\", "/"))
    return _co_result("Creator OS Release ZIP", [out], ["Release ZIP includes current project files and generated Creator OS docs."])
