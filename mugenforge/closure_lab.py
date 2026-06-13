from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Any

from .artifact_io import (
    backup_file,
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _now,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .parsers import parse_air, parse_code, parse_def, read_text_safely, write_text_safely, scan_project
from .move_wizard import find_character_file

CLOSURE_LAB_VERSION = "7.0.0"
CODE_EXTS = {".cmd", ".cns", ".st"}
BINARY_EXTS = {".sff", ".snd"}
EVIDENCE_EXTS = {".txt", ".log", ".json", ".csv", ".md"}


@dataclass
class ClosureLabResult:
    title: str = "Closure Lab"
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, message: object) -> None:
        self.warnings.append(str(message))

    def add_note(self, message: object) -> None:
        self.notes.append(str(message))

    def merge(self, other: object, label: Optional[str] = None) -> None:
        if other is None:
            return
        prefix = f"{label}: " if label else ""
        self.created_files += [prefix + str(x) for x in getattr(other, "created_files", []) or []]
        self.changed_files += [prefix + str(x) for x in getattr(other, "changed_files", []) or []]
        self.warnings += [prefix + str(x) for x in getattr(other, "warnings", []) or []]
        self.notes += [prefix + str(x) for x in getattr(other, "notes", []) or []]

    def to_text(self) -> str:
        lines = [self.title, "=" * max(12, len(self.title)), f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
        if self.notes:
            lines += ["Notes:"] + [f"- {x}" for x in _uniq(self.notes)] + [""]
        if self.changed_files:
            lines += ["Changed files:"] + [f"- {x}" for x in _uniq(self.changed_files)] + [""]
        if self.created_files:
            lines += ["Created files/artifacts:"] + [f"- {x}" for x in _uniq(self.created_files)] + [""]
        if self.warnings:
            lines += ["Warnings:"] + [f"- {x}" for x in _uniq(self.warnings)] + [""]
        if len(lines) <= 4:
            lines.append("No changes made.")
        return "\n".join(lines).rstrip() + "\n"


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _closure_dir(root: Path) -> Path:
    out = Path(root) / "closure_lab"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, res: Optional[ClosureLabResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, res, root, changed, track_existing=True, writer=write_text_safely)


def _write_json(path: Path, payload: object, res: Optional[ClosureLabResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, payload, res, root, changed, track_existing=True)


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[ClosureLabResult] = None, root: Optional[Path] = None) -> Path:
    return write_csv_artifact(path, rows, fields, res, root, track_existing=True)


def _read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _backup_file(path: Path, label: str = "closure") -> Optional[Path]:
    return backup_file(path, label)


def _main_def(root: Path) -> Optional[Path]:
    exact = Path(root) / f"{Path(root).name}.def"
    if exact.exists():
        return exact
    hits = sorted(Path(root).glob("*.def"), key=lambda p: p.name.lower())
    return hits[0] if hits else None


def _def_refs(root: Path) -> Dict[str, str]:
    dpath = _main_def(root)
    if not dpath or not dpath.exists():
        return {}
    try:
        sec = parse_def(read_text_safely(dpath)).get("files")
        if not sec:
            return {}
        return {str(k).lower(): str(v).strip().strip('"') for k, v in sec.values.items()}
    except Exception:
        return {}


def _project_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    refs = _def_refs(root)
    out: Dict[str, Optional[Path]] = {"root": root, "def": _main_def(root)}

    def by_ref(key: str, ext: str) -> Optional[Path]:
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                return p
        try:
            found = find_character_file(root, ext)
            if found and found.exists():
                return found
        except Exception:
            pass
        exact = root / f"{root.name}.{ext}"
        if exact.exists():
            return exact
        hits = sorted(root.glob(f"*.{ext}"), key=lambda p: p.name.lower())
        return hits[0] if hits else None

    out["cmd"] = by_ref("cmd", "cmd")
    out["cns"] = by_ref("cns", "cns")
    out["air"] = by_ref("anim", "air")
    out["sff"] = by_ref("sprite", "sff")
    out["snd"] = by_ref("sound", "snd")
    return out


def _code_files(root: Path) -> List[Path]:
    skip = {
        "__pycache__", "runtime_lab", "closure_lab", "binary_core", "binary_deep", "binary_maturity",
        "forge_timeline", "forge_polish", "forge_beyond", "visual_forge", "exports", "release",
    }
    out: List[Path] = []
    for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()):
        if not p.is_file() or p.suffix.lower() not in CODE_EXTS:
            continue
        if any(part in skip or part.startswith(".") for part in p.parts):
            continue
        out.append(p)
    return out


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        m = re.search(r"-?\d+", str(value or ""))
        return int(m.group(0)) if m else default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        m = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        return float(m.group(0)) if m else default


def _numbers(value: object) -> List[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))]


def _number_pair(value: object, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
    nums = _numbers(value)
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], default[1]
    return default


def _all_states(root: Path) -> Dict[int, Dict[str, object]]:
    states: Dict[int, Dict[str, object]] = {}
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states:
            states[st.number] = {"state": st, "file": p, "rel": _rel(root, p)}
    return states


def _all_hitdefs(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states:
            for ctrl in st.controllers:
                if (ctrl.stype or ctrl.values.get("type", "")).strip().lower() == "hitdef":
                    rows.append({
                        "file": p,
                        "rel": _rel(root, p),
                        "line": ctrl.line,
                        "state": st.number,
                        "header": ctrl.header,
                        "values": dict(ctrl.values),
                    })
    return rows


def _load_air_actions(root: Path) -> Dict[int, object]:
    files = _project_files(root)
    air = files.get("air")
    if not air or not air.exists():
        return {}
    try:
        return {a.number: a for a in parse_air(read_text_safely(air))}
    except Exception:
        return {}


def _anim_element(action: object, anim_time: int) -> Tuple[int, Optional[object], int]:
    frames = list(getattr(action, "frames", []) or []) if action is not None else []
    if not frames:
        return 0, None, 0
    elapsed = 0
    for idx, frame in enumerate(frames, start=1):
        ticks = max(1, _safe_int(getattr(frame, "ticks", 1), 1))
        if anim_time < elapsed + ticks:
            return idx, frame, ticks
        elapsed += ticks
    return len(frames), frames[-1], max(1, _safe_int(getattr(frames[-1], "ticks", 1), 1))


def _anim_total_ticks(action: object) -> int:
    frames = list(getattr(action, "frames", []) or []) if action is not None else []
    return sum(max(1, _safe_int(getattr(frame, "ticks", 1), 1)) for frame in frames)


def _eval_trigger_expr(expr: object, ctx: Dict[str, object]) -> bool:
    s = str(expr or "").strip()
    if not s:
        return True
    low = s.lower().replace(" ", "")
    if low in {"1", "true"}:
        return True
    if low in {"0", "false"}:
        return False
    # Basic conjunction/disjunction support. M.U.G.E.N expression semantics are much richer;
    # this mini-runtime handles common generated-project patterns only.
    if "&&" in s:
        return all(_eval_trigger_expr(part, ctx) for part in s.split("&&"))
    if "||" in s:
        return any(_eval_trigger_expr(part, ctx) for part in s.split("||"))

    time_v = int(ctx.get("state_time", 0) or 0)
    elem = int(ctx.get("anim_elem", 0) or 0)
    anim_time_remaining = int(ctx.get("anim_time_remaining", 0) or 0)
    ctrl = bool(ctx.get("ctrl", False))
    commands = {str(x).lower() for x in ctx.get("commands", []) or []}

    if re.fullmatch(r"ctrl", low):
        return ctrl
    if "roundstate=2" in low:
        return True
    m = re.search(r'command\s*=\s*["\']?([^"\'\s]+)["\']?', s, re.I)
    if m:
        return m.group(1).lower() in commands
    m = re.search(r"\btime\s*(=|==|>=|<=|>|<)\s*(-?\d+)", s, re.I)
    if m:
        return _compare(time_v, m.group(1), int(m.group(2)))
    m = re.search(r"\banimtime\s*(=|==|>=|<=|>|<)\s*(-?\d+)", s, re.I)
    if m:
        return _compare(anim_time_remaining, m.group(1), int(m.group(2)))
    m = re.search(r"\banimelem\s*(=|==|>=|<=|>|<)?\s*(-?\d+)", s, re.I)
    if m:
        op = m.group(1) or "="
        return _compare(elem, op, int(m.group(2)))
    if "movecontact" in low or "movehit" in low or "p2" in low:
        # Cannot know opponent/contact offline; keep these false to avoid fake transitions.
        return False
    # Unknown expressions default false rather than hallucinating runtime behavior.
    return False


def _compare(left: int, op: str, right: int) -> bool:
    if op in {"=", "=="}:
        return left == right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    return False


def _controller_triggers_true(values: Dict[str, str], ctx: Dict[str, object]) -> bool:
    triggerall = [v for k, v in values.items() if k.startswith("triggerall")]
    if any(not _eval_trigger_expr(v, ctx) for v in triggerall):
        return False
    grouped: Dict[str, List[str]] = {}
    for k, v in values.items():
        if re.match(r"trigger\d+", k):
            n = re.findall(r"\d+", k)[0]
            grouped.setdefault(n, []).append(v)
    if not grouped:
        return True
    return any(all(_eval_trigger_expr(v, ctx) for v in exprs) for exprs in grouped.values())


def build_offline_runtime_simulation(root: Path, start_state: int = 0, max_ticks: int = 180, command_script: Optional[Sequence[Dict[str, object]]] = None) -> ClosureLabResult:
    """Build a deterministic, source-level mini-runtime trace for common M.U.G.E.N controllers.

    This is intentionally a subset simulator. It follows StateDefs, AIR timing, common
    VelSet/VelAdd/PosAdd, PlaySnd, HitDef, Projectile/Helper/Explod markers, and simple
    ChangeState/SelfState transitions. Unsupported trigger expressions are logged as
    ignored instead of guessed.
    """
    root = Path(root)
    result = ClosureLabResult("Offline Runtime Simulation")
    out = _closure_dir(root) / "offline_runtime"
    out.mkdir(parents=True, exist_ok=True)
    states = _all_states(root)
    actions = _load_air_actions(root)
    warnings: List[str] = []

    if not states:
        warnings.append("No StateDefs found; only a skeleton trace was produced.")
    if not actions:
        warnings.append("No AIR actions found; animation frame fields are blank.")

    commands_by_tick: Dict[int, List[str]] = {}
    for item in command_script or []:
        t = _safe_int(item.get("tick", item.get("time", 0)), 0)
        cmd = str(item.get("command", "")).strip()
        if cmd:
            commands_by_tick.setdefault(t, []).append(cmd)

    state_no = int(start_state)
    state_time = 0
    x = y = 0.0
    vx = vy = 0.0
    ctrl = True
    rows: List[Dict[str, object]] = []
    events: List[Dict[str, object]] = []
    unsupported: List[str] = []

    for tick in range(max(1, int(max_ticks))):
        st_rec = states.get(state_no)
        st = st_rec.get("state") if st_rec else None
        st_values = dict(getattr(st, "values", {}) or {}) if st else {}
        anim = _safe_int(st_values.get("anim", state_no), state_no)
        ctrl = bool(_safe_int(st_values.get("ctrl", int(ctrl)), int(ctrl)))
        action = actions.get(anim)
        elem, frame, _frame_ticks = _anim_element(action, state_time)
        total_ticks = _anim_total_ticks(action)
        animtime = state_time - total_ticks if total_ticks else 0
        current_commands = commands_by_tick.get(tick, [])
        ctx = {
            "tick": tick,
            "state": state_no,
            "state_time": state_time,
            "anim": anim,
            "anim_elem": elem,
            "anim_time_remaining": animtime,
            "ctrl": ctrl,
            "commands": current_commands,
        }
        tick_events: List[str] = []
        changed_state = False

        if st:
            for ctrl_obj in getattr(st, "controllers", []) or []:
                values = dict(getattr(ctrl_obj, "values", {}) or {})
                stype = (getattr(ctrl_obj, "stype", "") or values.get("type", "")).strip().lower()
                if not stype:
                    continue
                try:
                    active = _controller_triggers_true(values, ctx)
                except Exception as exc:
                    unsupported.append(f"{st_rec.get('rel')} line {getattr(ctrl_obj, 'line', '?')}: trigger eval failed: {exc}")
                    active = False
                if not active:
                    continue
                if stype == "velset":
                    if "x" in values or "y" in values:
                        if "x" in values:
                            vx = _safe_float(values.get("x"), vx)
                        if "y" in values:
                            vy = _safe_float(values.get("y"), vy)
                    else:
                        vx, vy = _number_pair(values.get("value", values.get("vel", "")), (vx, vy))
                    tick_events.append(f"VelSet({vx:g},{vy:g})")
                elif stype == "veladd":
                    ax, ay = _number_pair(values.get("value", ""), (0.0, 0.0))
                    if "x" in values:
                        ax = _safe_float(values.get("x"), 0.0)
                    if "y" in values:
                        ay = _safe_float(values.get("y"), 0.0)
                    vx += ax
                    vy += ay
                    tick_events.append(f"VelAdd({ax:g},{ay:g})")
                elif stype == "posadd":
                    px, py = _number_pair(values.get("value", ""), (0.0, 0.0))
                    if "x" in values:
                        px = _safe_float(values.get("x"), 0.0)
                    if "y" in values:
                        py = _safe_float(values.get("y"), 0.0)
                    x += px
                    y += py
                    tick_events.append(f"PosAdd({px:g},{py:g})")
                elif stype in {"changestate", "selfstate"}:
                    val = values.get("value", "")
                    if re.fullmatch(r"\s*-?\d+\s*", str(val or "")):
                        next_state = int(str(val).strip())
                        events.append({"tick": tick, "type": stype, "from_state": state_no, "to_state": next_state, "line": getattr(ctrl_obj, "line", "")})
                        tick_events.append(f"{stype}->{next_state}")
                        state_no = next_state
                        state_time = -1  # incremented to zero after row write
                        changed_state = True
                        break
                    unsupported.append(f"{st_rec.get('rel')} line {getattr(ctrl_obj, 'line', '?')}: dynamic ChangeState value not simulated: {val}")
                elif stype == "playsnd":
                    val = values.get("value", "")
                    tick_events.append(f"PlaySnd({val})")
                    events.append({"tick": tick, "type": "PlaySnd", "state": state_no, "value": val, "line": getattr(ctrl_obj, "line", "")})
                elif stype == "hitdef":
                    dmg = values.get("damage", "")
                    tick_events.append(f"HitDef({dmg})")
                    events.append({"tick": tick, "type": "HitDef", "state": state_no, "damage": dmg, "line": getattr(ctrl_obj, "line", "")})
                elif stype in {"projectile", "helper", "explod", "palfx", "envshake", "afterimage"}:
                    tick_events.append(stype)
                    events.append({"tick": tick, "type": stype, "state": state_no, "line": getattr(ctrl_obj, "line", "")})
                elif stype in {"statetypeset", "ctrlset"}:
                    if stype == "ctrlset" and "value" in values:
                        ctrl = bool(_safe_int(values.get("value"), int(ctrl)))
                    tick_events.append(stype)
                else:
                    # Keep unknown controllers visible without pretending to execute them.
                    pass

        group = image = offx = offy = ticks_v = ""
        if frame is not None:
            group = getattr(frame, "group", "")
            image = getattr(frame, "image", "")
            offx = getattr(frame, "x", "")
            offy = getattr(frame, "y", "")
            ticks_v = getattr(frame, "ticks", "")
        rows.append({
            "tick": tick,
            "state": state_no,
            "state_time": max(0, state_time),
            "anim": anim,
            "anim_elem": elem,
            "sprite_group": group,
            "sprite_image": image,
            "frame_offset_x": offx,
            "frame_offset_y": offy,
            "frame_ticks": ticks_v,
            "x": round(x, 4),
            "y": round(y, 4),
            "vel_x": round(vx, 4),
            "vel_y": round(vy, 4),
            "ctrl": int(ctrl),
            "commands": " | ".join(current_commands),
            "events": " | ".join(tick_events),
        })
        x += vx
        y += vy
        state_time += 1
        if changed_state and state_no not in states:
            warnings.append(f"Simulation entered undefined state {state_no} at tick {tick}.")

    fields = ["tick", "state", "state_time", "anim", "anim_elem", "sprite_group", "sprite_image", "frame_offset_x", "frame_offset_y", "frame_ticks", "x", "y", "vel_x", "vel_y", "ctrl", "commands", "events"]
    csv_path = _write_csv(out / "offline_runtime_trace.csv", rows, fields, result, root)
    model = {
        "tool": "MugenForge Closure Lab",
        "version": CLOSURE_LAB_VERSION,
        "mode": "source_level_mini_runtime",
        "start_state": start_state,
        "max_ticks": max_ticks,
        "capabilities": [
            "StateDef traversal",
            "AIR timing and sprite element lookup",
            "VelSet/VelAdd/PosAdd approximation",
            "simple ChangeState/SelfState transitions",
            "PlaySnd/HitDef/Projectile/Helper/Explod event markers",
            "simple trigger evaluation for time, AnimTime, AnimElem, command, ctrl, roundstate",
        ],
        "non_goals": [
            "Not a full M.U.G.E.N/IKEMEN clone",
            "Does not model opponent collision/contact or engine physics exactly",
            "Unsupported trigger expressions are reported rather than guessed",
        ],
        "warnings": warnings,
        "unsupported": unsupported[:500],
        "events": events,
        "rows": rows,
    }
    json_path = _write_json(out / "offline_runtime_trace.json", model, result, root)
    html_path = out / "offline_runtime_trace.html"
    html_rows = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(f, '')))}</td>" for f in fields) + "</tr>"
        for row in rows[:1000]
    )
    _write_text(html_path, f"""<!doctype html><meta charset='utf-8'><title>MugenForge Offline Runtime Trace</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}} table{{border-collapse:collapse;font-size:12px}}td,th{{border:1px solid #ccc;padding:3px 5px}} th{{background:#eee;position:sticky;top:0}}</style>
<h1>MugenForge Offline Runtime Trace</h1>
<p>This is a source-level mini-runtime for common controller patterns. Use the external engine harness for authoritative runtime evidence.</p>
<p>Rows: {len(rows)}. Events: {len(events)}. Warnings: {len(warnings)}. Unsupported expressions/controllers: {len(unsupported)}.</p>
<table><thead><tr>{''.join(f'<th>{html.escape(f)}</th>' for f in fields)}</tr></thead><tbody>{html_rows}</tbody></table>
""", result, root)
    if warnings:
        result.warnings += warnings
    if unsupported:
        result.add_note(f"Unsupported expressions/controllers recorded: {len(unsupported)}")
    result.add_note(f"Offline mini-runtime trace written: {_rel(root, csv_path)}")
    return result


def write_engine_adapter_suite(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Engine Adapter Suite")
    out = _closure_dir(root) / "engine_adapters"
    out.mkdir(parents=True, exist_ok=True)
    files = _project_files(root)
    char_name = root.name
    default_stage = "stages/training.def"
    existing_cfg = out / "engine_adapter_config.json"
    cfg = _read_json(existing_cfg, {}) if existing_cfg.exists() else {}
    if not isinstance(cfg, dict):
        cfg = {}
    cfg = {
        "schema": "mugenforge.engine_adapter.v1",
        "engine_executable": cfg.get("engine_executable", ""),
        "engine_working_directory": cfg.get("engine_working_directory", ""),
        "target": cfg.get("target", "mugen_or_ikemen"),
        "character_name": cfg.get("character_name", char_name),
        "character_folder": str(root),
        "default_stage": cfg.get("default_stage", default_stage),
        "timeout_seconds": cfg.get("timeout_seconds", 20),
        "profiles": [
            {"name": "quick_boot", "args_template": ["-p1", "{character_name}", "-p2", "kfm", "-stage", "{default_stage}"]},
            {"name": "mirror_match", "args_template": ["-p1", "{character_name}", "-p2", "{character_name}", "-stage", "{default_stage}"]},
            {"name": "watch_mode_hint", "args_template": ["-p1", "{character_name}", "-p2", "kfm", "-stage", "{default_stage}", "-rounds", "1"]},
        ],
        "notes": [
            "Edit engine_executable and engine_working_directory before running non-dry scenarios.",
            "Different engines/builds expose different CLI switches; use the exact command preview files to adjust profiles.",
        ],
    }
    _write_json(existing_cfg, cfg, result, root, changed=True)

    runner = out / "engine_adapter_runner.py"
    runner_code = r'''from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json, subprocess, sys, shlex


def _expand(token: str, cfg: dict, profile: dict) -> str:
    data = dict(cfg)
    data.update(profile)
    return str(token).format(**data)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cfg_path = Path(argv[0]) if argv else Path(__file__).with_name('engine_adapter_config.json')
    profile_name = argv[1] if len(argv) > 1 else 'quick_boot'
    dry_run = '--run' not in argv
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    profiles = {p.get('name'): p for p in cfg.get('profiles', [])}
    profile = profiles.get(profile_name)
    if not profile:
        print(f'Unknown profile: {profile_name}', file=sys.stderr)
        return 2
    engine = str(cfg.get('engine_executable') or '').strip()
    if not engine:
        print('engine_executable is blank. Edit engine_adapter_config.json.', file=sys.stderr)
        return 2
    command = [engine] + [_expand(x, cfg, profile) for x in profile.get('args_template', [])]
    cwd = str(cfg.get('engine_working_directory') or Path(engine).parent or cfg_path.parent)
    timeout = int(cfg.get('timeout_seconds') or 20)
    logs = cfg_path.parent / 'sessions'
    logs.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime('%Y%m%d_%H%M%S')
    preview = {'profile': profile_name, 'dry_run': dry_run, 'command': command, 'cwd': cwd, 'timeout_seconds': timeout}
    (logs / f'{profile_name}_{tag}_command.json').write_text(json.dumps(preview, indent=2) + '\n', encoding='utf-8')
    print('COMMAND:', ' '.join(shlex.quote(x) for x in command))
    print('CWD:', cwd)
    if dry_run:
        print('Dry run only. Add --run to execute.')
        return 0
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        (logs / f'{profile_name}_{tag}_stdout.txt').write_text(proc.stdout or '', encoding='utf-8', errors='replace')
        (logs / f'{profile_name}_{tag}_stderr.txt').write_text(proc.stderr or '', encoding='utf-8', errors='replace')
        (logs / f'{profile_name}_{tag}_result.json').write_text(json.dumps({'returncode': proc.returncode, **preview}, indent=2) + '\n', encoding='utf-8')
        return int(proc.returncode)
    except subprocess.TimeoutExpired as exc:
        (logs / f'{profile_name}_{tag}_timeout.json').write_text(json.dumps({'error':'timeout', 'stdout': exc.stdout, 'stderr': exc.stderr, **preview}, indent=2) + '\n', encoding='utf-8', errors='replace')
        return 124
    except Exception as exc:
        (logs / f'{profile_name}_{tag}_error.json').write_text(json.dumps({'error': str(exc), **preview}, indent=2) + '\n', encoding='utf-8')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
'''
    _write_text(runner, runner_code, result, root, changed=True)

    commands: List[Dict[str, object]] = []
    for p in cfg.get("profiles", []):
        args = [str(x).format(**cfg, **p) for x in p.get("args_template", [])]
        command = [cfg.get("engine_executable", "<engine_executable>")] + args
        commands.append({"profile": p.get("name"), "command_preview": " ".join(str(x) for x in command), "working_directory": cfg.get("engine_working_directory", "")})
    _write_csv(out / "engine_command_previews.csv", commands, ["profile", "command_preview", "working_directory"], result, root)

    bat = out / "run_quick_boot.bat"
    sh = out / "run_quick_boot.sh"
    _write_text(bat, "@echo off\npython engine_adapter_runner.py engine_adapter_config.json quick_boot --run\npause\n", result, root, changed=True)
    _write_text(sh, "#!/usr/bin/env bash\npython3 engine_adapter_runner.py engine_adapter_config.json quick_boot --run\n", result, root, changed=True)
    try:
        sh.chmod(0o755)
    except Exception:
        pass

    validation = validate_engine_adapter_suite(root)
    result.merge(validation, "validation")
    result.add_note("Engine adapter suite writes executable command previews and runnable scripts; configure your local engine path to use them.")
    return result


def validate_engine_adapter_suite(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Engine Adapter Validation")
    out = _closure_dir(root) / "engine_adapters"
    cfg_path = out / "engine_adapter_config.json"
    cfg = _read_json(cfg_path, {})
    if not isinstance(cfg, dict):
        cfg = {}
    rows: List[Dict[str, object]] = []
    exe = Path(str(cfg.get("engine_executable") or "")) if cfg.get("engine_executable") else None
    cwd = Path(str(cfg.get("engine_working_directory") or "")) if cfg.get("engine_working_directory") else None
    rows.append({"check": "config_exists", "status": "pass" if cfg_path.exists() else "fail", "detail": _rel(root, cfg_path)})
    rows.append({"check": "engine_executable", "status": "pass" if exe and exe.exists() else "missing", "detail": str(exe or "blank")})
    rows.append({"check": "working_directory", "status": "pass" if cwd and cwd.exists() else ("missing" if cwd else "blank"), "detail": str(cwd or "blank")})
    rows.append({"check": "character_folder", "status": "pass" if Path(str(cfg.get("character_folder") or root)).exists() else "fail", "detail": str(cfg.get("character_folder") or root)})
    for p in cfg.get("profiles", []) if isinstance(cfg.get("profiles", []), list) else []:
        rows.append({"check": f"profile:{p.get('name')}", "status": "pass" if p.get("args_template") else "warn", "detail": " ".join(str(x) for x in p.get("args_template", []))})
    _write_csv(out / "engine_adapter_validation.csv", rows, ["check", "status", "detail"], result, root)
    _write_json(out / "engine_adapter_validation.json", {"checks": rows, "generated": datetime.now().isoformat(timespec="seconds")}, result, root)
    if not exe or not exe.exists():
        result.add_warning("engine_executable is not configured yet; dry-run command previews are still available.")
    return result


def run_engine_adapter_suite(root: Path, profile_name: str = "quick_boot", dry_run: bool = True, timeout_seconds: Optional[int] = None) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Engine Adapter Runner")
    out = _closure_dir(root) / "engine_adapters"
    cfg_path = out / "engine_adapter_config.json"
    if not cfg_path.exists():
        result.merge(write_engine_adapter_suite(root), "setup")
    cfg = _read_json(cfg_path, {})
    if not isinstance(cfg, dict):
        cfg = {}
    if timeout_seconds is not None:
        cfg["timeout_seconds"] = int(timeout_seconds)
        _write_json(cfg_path, cfg, None, root, changed=True)
    runner = out / "engine_adapter_runner.py"
    if not runner.exists():
        result.merge(write_engine_adapter_suite(root), "setup")
    cmd = [sys.executable, str(runner), str(cfg_path), str(profile_name)]
    if not dry_run:
        cmd.append("--run")
    sessions = out / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    tag = _now()
    try:
        proc = subprocess.run(cmd, cwd=str(out), capture_output=True, text=True, timeout=max(5, int(cfg.get("timeout_seconds") or 20) + 5))
        (sessions / f"mugenforge_adapter_{profile_name}_{tag}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8", errors="replace")
        (sessions / f"mugenforge_adapter_{profile_name}_{tag}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8", errors="replace")
        _write_json(sessions / f"mugenforge_adapter_{profile_name}_{tag}_result.json", {"returncode": proc.returncode, "dry_run": dry_run, "command": cmd}, result, root)
        if proc.returncode != 0 and not dry_run:
            result.add_warning(f"Engine adapter exited with return code {proc.returncode}.")
        else:
            result.add_note(f"Engine adapter {'dry-run' if dry_run else 'run'} completed with return code {proc.returncode}.")
    except Exception as exc:
        _write_json(sessions / f"mugenforge_adapter_{profile_name}_{tag}_error.json", {"error": str(exc), "dry_run": dry_run, "command": cmd}, result, root)
        result.add_warning(f"Engine adapter run failed: {exc}")
    return result


def build_sff2_corpus_validator(root: Path, corpus_dir: Optional[Path] = None) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("SFF2 Corpus Validator")
    out = _closure_dir(root) / "sff2_corpus"
    out.mkdir(parents=True, exist_ok=True)
    candidates: List[Path] = []
    project_sff = _project_files(root).get("sff")
    if project_sff and project_sff.exists():
        candidates.append(project_sff)
    corpus = Path(corpus_dir) if corpus_dir else out / "drop_sff_files_here"
    corpus.mkdir(parents=True, exist_ok=True)
    for p in sorted(corpus.rglob("*.sff"), key=lambda x: str(x).lower()):
        if p.is_file() and p not in candidates:
            candidates.append(p)

    rows: List[Dict[str, object]] = []
    db: Dict[str, object] = {"generated": datetime.now().isoformat(timespec="seconds"), "files": []}
    export_root = out / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    for idx, path in enumerate(candidates):
        sha = _sha256(path)
        row: Dict[str, object] = {
            "index": idx,
            "file": str(path),
            "relative": _rel(root, path),
            "size": path.stat().st_size if path.exists() else 0,
            "sha256": sha,
            "parser": "",
            "version": "",
            "sprites": 0,
            "palettes": 0,
            "exported": 0,
            "warnings": "",
            "status": "untested",
        }
        warnings: List[str] = []
        try:
            from .sff2_codec import read_sff2, export_sff2_sprites
            info = read_sff2(path, strict=False)
            row["parser"] = "sff2_codec"
            row["version"] = info.version_text
            row["sprites"] = len(info.sprites)
            row["palettes"] = len(info.palettes)
            row["warnings"] = " | ".join(info.warnings)
            exp_dir = export_root / f"{idx:04d}_{path.stem}"
            exported, exp_warnings = export_sff2_sprites(path, exp_dir, include_provisional=True, max_count=5000)
            row["exported"] = len(exported)
            warnings += list(info.warnings) + list(exp_warnings)
            row["status"] = "pass" if exported or info.sprites else "inspect"
            db["files"].append({"path": str(path), "sha256": sha, "sff2": info.to_dict(), "exported": [str(x) for x in exported], "warnings": warnings})
        except Exception as exc:
            try:
                from .sff_codec import read_sff
                info1 = read_sff(path)
                row["parser"] = "sff_codec"
                row["version"] = info1.version_text
                row["sprites"] = len(info1.sprites)
                row["warnings"] = " | ".join(info1.warnings + [str(exc)])
                row["status"] = "fallback" if info1.sprites else "fail"
                db["files"].append({"path": str(path), "sha256": sha, "fallback": {"version": info1.version_text, "sprites": len(info1.sprites), "warnings": info1.warnings}, "primary_error": str(exc)})
            except Exception as exc2:
                row["parser"] = "none"
                row["warnings"] = f"{exc}; fallback failed: {exc2}"
                row["status"] = "fail"
                db["files"].append({"path": str(path), "sha256": sha, "error": str(exc), "fallback_error": str(exc2)})
        rows.append(row)
    fields = ["index", "file", "relative", "size", "sha256", "parser", "version", "sprites", "palettes", "exported", "status", "warnings"]
    _write_csv(out / "sff2_corpus_results.csv", rows, fields, result, root)
    _write_json(out / "sff2_corpus_database.json", db, result, root)
    _write_text(out / "README_DROP_CORPUS_HERE.md", """# SFF2 Corpus Validator

Drop real-world `.sff` files into this folder or point the UI/function to a corpus directory, then run the validator again.

The validator records parser mode, sprite/palette counts, export count, warnings, and SHA-256 identifiers so compatibility can be expanded with real evidence instead of guesswork.
""", result, root)
    result.add_note(f"SFF files tested: {len(rows)}")
    if not rows:
        result.add_warning("No SFF files were found. Drop files into closure_lab/sff2_corpus/drop_sff_files_here and rerun.")
    return result


def write_sff2_unknown_triage(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Unknown SFF2 Triage")
    out = _closure_dir(root) / "sff2_triage"
    out.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    main = _project_files(root).get("sff")
    if main and main.exists():
        files.append(main)
    for p in sorted((_closure_dir(root) / "sff2_corpus" / "drop_sff_files_here").rglob("*.sff"), key=lambda x: str(x).lower()):
        if p not in files:
            files.append(p)
    rows: List[Dict[str, object]] = []
    for idx, path in enumerate(files):
        data = path.read_bytes() if path.exists() else b""
        entropy = _entropy(data[:min(len(data), 2_000_000)]) if data else 0.0
        sig = data[:12]
        magic_hits = _magic_hits(data)
        hexdump = _hexdump(data[:512])
        # Try reading header fields without trusting them.
        header_probe = _sff_header_probe(data)
        triage_path = out / f"{idx:04d}_{path.stem}_triage.txt"
        _write_text(triage_path, f"""SFF Triage: {path}
Generated: {datetime.now().isoformat(timespec='seconds')}
Size: {len(data)} bytes
SHA-256: {_sha256(path) if path.exists() else ''}
Signature bytes: {sig!r}
Entropy(first 2MB): {entropy:.4f}

Header probe:
{json.dumps(header_probe, indent=2)}

Magic hits:
{json.dumps(magic_hits, indent=2)}

First 512 bytes:
{hexdump}
""", result, root)
        rows.append({
            "file": str(path),
            "relative": _rel(root, path),
            "size": len(data),
            "sha256": _sha256(path) if path.exists() else "",
            "signature": sig.hex(),
            "entropy_first_2mb": f"{entropy:.4f}",
            "png_hits": len(magic_hits.get("png", [])),
            "pcx_hits": len(magic_hits.get("pcx", [])),
            "riff_hits": len(magic_hits.get("riff_wave", [])),
            "triage_file": _rel(root, triage_path),
        })
    _write_csv(out / "sff2_triage_index.csv", rows, ["file", "relative", "size", "sha256", "signature", "entropy_first_2mb", "png_hits", "pcx_hits", "riff_hits", "triage_file"], result, root)
    result.add_note(f"Triage files written for {len(rows)} SFF file(s).")
    return result


def export_direct_mutation_commit_sheet(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Direct Mutation Commit Sheet")
    out = _closure_dir(root) / "mutation_commit"
    out.mkdir(parents=True, exist_ok=True)
    files = _project_files(root)
    targets = {".sff": files.get("sff"), ".snd": files.get("snd")}
    search_dirs = [root / "binary_core", root / "binary_deep", root / "binary_maturity", root / "closure_lab" / "sff2_corpus" / "exports", root / "closure_lab" / "source_builds"]
    rows: List[Dict[str, object]] = []
    seen = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in BINARY_EXTS:
                continue
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            target = targets.get(p.suffix.lower())
            if target and target.exists() and p.resolve() == target.resolve():
                continue
            rows.append({
                "enabled": "no",
                "action": "review",
                "candidate_path": _rel(root, p),
                "target_path": _rel(root, target) if target else "",
                "candidate_size": p.stat().st_size,
                "candidate_sha256": _sha256(p),
                "confirm_phrase": "",
                "notes": "Set enabled=yes, action=commit, and confirm_phrase=I_UNDERSTAND_BACKUP_COMMIT to overwrite target with backup/rollback.",
            })
    sheet = out / "mutation_commit_sheet.csv"
    fields = ["enabled", "action", "candidate_path", "target_path", "candidate_size", "candidate_sha256", "confirm_phrase", "notes"]
    _write_csv(sheet, rows, fields, result, root)
    _write_text(out / "MUTATION_COMMIT_README.md", """# Direct Mutation Commit

This is the opt-in path for committing a vetted binary candidate over the live project SFF/SND.

Safety model:

1. Nothing commits unless `enabled=yes`, `action=commit`, and `confirm_phrase=I_UNDERSTAND_BACKUP_COMMIT` are set on a row.
2. MugenForge writes a snapshot ZIP containing the target file and manifest before copying.
3. A rollback manifest is written after each commit.
4. Use **Restore Last Mutation Snapshot** to restore the last committed target.

This replaces the old candidate-only workflow with a controlled commit/rollback system. It still avoids blind overwrites.
""", result, root)
    result.add_note(f"Candidate rows: {len(rows)}")
    if not rows:
        result.add_warning("No generated SFF/SND candidates were found to list.")
    return result


def apply_direct_mutation_commit_sheet(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Apply Direct Mutation Commit Sheet")
    out = _closure_dir(root) / "mutation_commit"
    sheet = out / "mutation_commit_sheet.csv"
    if not sheet.exists():
        result.merge(export_direct_mutation_commit_sheet(root), "export")
    if not sheet.exists():
        result.add_warning("Mutation commit sheet could not be created.")
        return result
    rows = list(csv.DictReader(sheet.open("r", encoding="utf-8", newline="")))
    commits: List[Dict[str, object]] = []
    snapshots = out / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    for idx, row in enumerate(rows):
        if str(row.get("enabled", "")).strip().lower() != "yes":
            continue
        if str(row.get("action", "")).strip().lower() != "commit":
            continue
        if str(row.get("confirm_phrase", "")).strip() != "I_UNDERSTAND_BACKUP_COMMIT":
            result.add_warning(f"Row {idx}: confirm_phrase missing; skipped.")
            continue
        cand = (root / str(row.get("candidate_path", ""))).resolve()
        target = (root / str(row.get("target_path", ""))).resolve()
        try:
            cand.relative_to(root.resolve())
            target.relative_to(root.resolve())
        except Exception:
            result.add_warning(f"Row {idx}: candidate/target must be inside project folder; skipped.")
            continue
        if not cand.exists() or not target.exists():
            result.add_warning(f"Row {idx}: candidate or target missing; skipped.")
            continue
        if cand.suffix.lower() != target.suffix.lower() or cand.suffix.lower() not in BINARY_EXTS:
            result.add_warning(f"Row {idx}: extension mismatch or unsupported binary type; skipped.")
            continue
        tag = _now()
        snap = snapshots / f"mutation_snapshot_{target.stem}_{tag}.zip"
        with zipfile.ZipFile(snap, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(target, f"before/{target.name}")
            z.write(cand, f"candidate/{cand.name}")
            z.writestr("manifest.json", json.dumps({
                "target": str(target),
                "candidate": str(cand),
                "target_sha256_before": _sha256(target),
                "candidate_sha256": _sha256(cand),
                "created": datetime.now().isoformat(timespec="seconds"),
            }, indent=2))
        shutil.copy2(cand, target)
        manifest = {
            "snapshot": str(snap),
            "target": str(target),
            "candidate": str(cand),
            "target_sha256_after": _sha256(target),
            "committed": datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(out / "last_mutation_rollback_manifest.json", manifest, result, root, changed=True)
        commits.append(manifest)
        result.add_changed(root, target)
        result.add_created(root, snap)
    _write_json(out / f"mutation_commit_log_{_now()}.json", {"commits": commits}, result, root)
    if not commits:
        result.add_warning("No rows were committed. Edit the sheet and set the explicit confirm phrase.")
    else:
        result.add_note(f"Committed {len(commits)} binary candidate(s) with rollback snapshots.")
    return result


def restore_last_mutation_snapshot(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Restore Last Mutation Snapshot")
    out = _closure_dir(root) / "mutation_commit"
    manifest_path = out / "last_mutation_rollback_manifest.json"
    manifest = _read_json(manifest_path, {})
    if not isinstance(manifest, dict) or not manifest.get("snapshot") or not manifest.get("target"):
        result.add_warning("No rollback manifest found.")
        return result
    snap = Path(str(manifest["snapshot"]))
    target = Path(str(manifest["target"]))
    if not snap.exists() or not target.exists():
        result.add_warning("Snapshot or target is missing.")
        return result
    _backup_file(target, "pre_restore")
    with zipfile.ZipFile(snap, "r") as z:
        before_names = [n for n in z.namelist() if n.startswith("before/") and not n.endswith("/")]
        if not before_names:
            result.add_warning("Snapshot does not contain a before/ file.")
            return result
        data = z.read(before_names[0])
    target.write_bytes(data)
    _write_json(out / f"restore_log_{_now()}.json", {"restored_target": str(target), "from_snapshot": str(snap), "sha256_after": _sha256(target)}, result, root)
    result.add_changed(root, target)
    result.add_note("Last mutation snapshot restored.")
    return result


def export_gameplay_tuning_sheet(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Gameplay Tuning Sheet")
    out = _closure_dir(root) / "gameplay_tuning"
    out.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    for idx, hit in enumerate(_all_hitdefs(root)):
        vals: Dict[str, str] = hit["values"]  # type: ignore[assignment]
        damage_first = _safe_int(vals.get("damage", 0), 0)
        if damage_first <= 0:
            suggested = 25
        elif damage_first > 180:
            suggested = 160
        else:
            suggested = damage_first
        rows.append({
            "enabled": "no",
            "row_id": idx,
            "file": hit["rel"],
            "line": hit["line"],
            "state": hit["state"],
            "current_damage": vals.get("damage", ""),
            "target_damage": suggested,
            "current_pausetime": vals.get("pausetime", ""),
            "target_pausetime": vals.get("pausetime", "8,8") or "8,8",
            "current_ground_velocity": vals.get("ground.velocity", ""),
            "target_ground_velocity": vals.get("ground.velocity", "-3,0") or "-3,0",
            "current_air_velocity": vals.get("air.velocity", ""),
            "target_air_velocity": vals.get("air.velocity", "-2,-4") or "-2,-4",
            "notes": "Set enabled=yes to apply target_* values. Use runtime evidence before final release.",
        })
    fields = ["enabled", "row_id", "file", "line", "state", "current_damage", "target_damage", "current_pausetime", "target_pausetime", "current_ground_velocity", "target_ground_velocity", "current_air_velocity", "target_air_velocity", "notes"]
    _write_csv(out / "gameplay_tuning_sheet.csv", rows, fields, result, root)
    _write_text(out / "GAMEPLAY_TUNING_GUIDE.md", """# Gameplay Tuning Sheet

This sheet closes the starter-scaffold gap by giving generated HitDefs an editable/applyable tuning loop.

Recommended loop:

1. Run Offline Runtime Simulation.
2. Run the external Engine Adapter smoke/scenario tests if your engine is configured.
3. Edit target values in `gameplay_tuning_sheet.csv`.
4. Set `enabled=yes` only on rows you want to apply.
5. Apply the sheet. Backups are written before source edits.
6. Re-test in the target engine.
""", result, root)
    result.add_note(f"HitDef rows exported: {len(rows)}")
    if not rows:
        result.add_warning("No HitDef controllers found.")
    return result


def apply_gameplay_tuning_sheet(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Apply Gameplay Tuning Sheet")
    sheet = _closure_dir(root) / "gameplay_tuning" / "gameplay_tuning_sheet.csv"
    if not sheet.exists():
        result.merge(export_gameplay_tuning_sheet(root), "export")
    if not sheet.exists():
        result.add_warning("Gameplay tuning sheet was not found.")
        return result
    rows = list(csv.DictReader(sheet.open("r", encoding="utf-8", newline="")))
    by_file: Dict[Path, List[Dict[str, str]]] = {}
    for row in rows:
        if str(row.get("enabled", "")).strip().lower() == "yes":
            by_file.setdefault((root / str(row.get("file", ""))).resolve(), []).append(row)
    changed = 0
    for path, edits in by_file.items():
        try:
            path.relative_to(root.resolve())
        except Exception:
            result.add_warning(f"Skipped out-of-project path: {path}")
            continue
        if not path.exists() or path.suffix.lower() not in CODE_EXTS:
            result.add_warning(f"Skipped missing/non-code path: {path}")
            continue
        lines = read_text_safely(path).splitlines()
        _backup_file(path, "gameplay_tuning")
        for row in sorted(edits, key=lambda r: _safe_int(r.get("line", 0), 0), reverse=True):
            line_no = max(1, _safe_int(row.get("line", 0), 0))
            start = max(0, line_no - 1)
            if start >= len(lines):
                continue
            end = start + 1
            while end < len(lines) and not re.match(r"^\s*\[", lines[end]):
                end += 1
            block = lines[start:end]
            replacements = {
                "damage": str(row.get("target_damage", "")).strip(),
                "pausetime": str(row.get("target_pausetime", "")).strip(),
                "ground.velocity": str(row.get("target_ground_velocity", "")).strip(),
                "air.velocity": str(row.get("target_air_velocity", "")).strip(),
            }
            block = _replace_block_kv(block, replacements)
            lines[start:end] = block
            changed += 1
        write_text_safely(path, "\n".join(lines).rstrip() + "\n")
        result.add_changed(root, path)
    if changed:
        result.add_note(f"Applied gameplay tuning to {changed} HitDef block(s).")
    else:
        result.add_warning("No enabled gameplay tuning rows were applied.")
    return result


def _replace_block_kv(block: List[str], replacements: Dict[str, str]) -> List[str]:
    out = list(block)
    present = {k: False for k in replacements}
    for i, line in enumerate(out):
        m = re.match(r"^(\s*)([^;=]+?)(\s*=\s*)(.*)$", line)
        if not m:
            continue
        key = m.group(2).strip().lower()
        if key in replacements and replacements[key] != "":
            out[i] = f"{m.group(1)}{m.group(2).strip()}{m.group(3)}{replacements[key]}"
            present[key] = True
    insert_at = len(out)
    for key, value in replacements.items():
        if value != "" and not present.get(key):
            out.insert(insert_at, f"{key} = {value}")
            insert_at += 1
    return out


def write_report_evidence_contract(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Report Evidence Contract")
    out = _closure_dir(root) / "evidence_contract"
    out.mkdir(parents=True, exist_ok=True)
    evidence_files: List[Path] = []
    for base in [root / "runtime_lab", root / "closure_lab" / "engine_adapters", root / "closure_lab" / "offline_runtime", root / "testing", root / "release"]:
        if base.exists():
            for p in sorted(base.rglob("*"), key=lambda x: str(x).lower()):
                if p.is_file() and p.suffix.lower() in EVIDENCE_EXTS:
                    evidence_files.append(p)
    rows: List[Dict[str, object]] = []
    for p in evidence_files:
        rows.append({"file": _rel(root, p), "size": p.stat().st_size, "sha256": _sha256(p), "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")})
    _write_csv(out / "runtime_evidence_index.csv", rows, ["file", "size", "sha256", "modified"], result, root)
    contract = {
        "tool": "MugenForge Closure Lab",
        "version": CLOSURE_LAB_VERSION,
        "reliability_levels": {
            "A_engine_evidence": "Produced by a configured external M.U.G.E.N/IKEMEN run and preserved as logs/results/evidence.",
            "B_mini_runtime": "Produced by MugenForge source-level mini-runtime for common controller patterns.",
            "C_static_analysis": "Produced by source/binary parser reports only.",
            "D_manual_note": "User-entered or imported notes that need review.",
        },
        "evidence_count": len(rows),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "policy": "Reports should state their evidence level. Release readiness should prefer A_engine_evidence when available.",
    }
    _write_json(out / "report_evidence_contract.json", contract, result, root)
    _write_text(out / "REPORT_EVIDENCE_CONTRACT.md", """# Report Evidence Contract

MugenForge now labels reports by evidence level instead of treating every static estimate as equally strong.

- **A_engine_evidence**: captured from a configured external M.U.G.E.N/IKEMEN run.
- **B_mini_runtime**: produced by Closure Lab's source-level mini-runtime.
- **C_static_analysis**: parser/report estimate only.
- **D_manual_note**: imported notes or checklist rows.

This does not remove the need for engine testing; it makes the difference visible and machine-readable.
""", result, root)
    result.add_note(f"Evidence files indexed: {len(rows)}")
    return result


def write_closure_dashboard(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Closure Lab Dashboard")
    out = _closure_dir(root)
    files = _project_files(root)
    audit = scan_project(root)
    checks = [
        ("external_engine_adapter", (out / "engine_adapters" / "engine_adapter_config.json").exists()),
        ("offline_mini_runtime", (out / "offline_runtime" / "offline_runtime_trace.json").exists()),
        ("sff2_corpus_database", (out / "sff2_corpus" / "sff2_corpus_database.json").exists()),
        ("mutation_commit_sheet", (out / "mutation_commit" / "mutation_commit_sheet.csv").exists()),
        ("gameplay_tuning_sheet", (out / "gameplay_tuning" / "gameplay_tuning_sheet.csv").exists()),
        ("report_evidence_contract", (out / "evidence_contract" / "report_evidence_contract.json").exists()),
    ]
    lines = [
        "# MugenForge Closure Lab",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Version: {CLOSURE_LAB_VERSION}",
        "",
        "Closure Lab targets the previous honest limitation list with concrete tools:",
        "",
        "| Gap | v7.0 closure tool | Status |",
        "|---|---|---|",
    ]
    status_map = {k: "ready" if v else "not yet generated" for k, v in checks}
    lines += [
        f"| No local runtime simulation | Offline source-level mini-runtime | {status_map['offline_mini_runtime']} |",
        f"| Engine scripts need review | Engine adapter config validation and exact command previews | {status_map['external_engine_adapter']} |",
        f"| Static readiness is not authoritative | Evidence contract and runtime-evidence index | {status_map['report_evidence_contract']} |",
        f"| SFF2 corpus coverage incomplete | Corpus validator database/harness | {status_map['sff2_corpus_database']} |",
        f"| Unknown/corrupt SFF2 manual review | Triage hexdumps/header/magic probes | {'ready' if (out/'sff2_triage'/'sff2_triage_index.csv').exists() else 'not yet generated'} |",
        f"| Candidate-only binary mutation | Opt-in commit/rollback sheet | {status_map['mutation_commit_sheet']} |",
        f"| Generated code needs tuning | Gameplay tuning sheet/apply workflow | {status_map['gameplay_tuning_sheet']} |",
        "",
        "## Project files",
        "",
    ]
    for key in ["def", "cmd", "cns", "air", "sff", "snd"]:
        lines.append(f"- {key.upper()}: {_rel(root, files.get(key)) if files.get(key) else 'missing'}")
    lines += ["", "## Project audit", "", f"- Missing required files: {', '.join(audit.missing_required) if audit.missing_required else 'none'}", f"- Missing DEF references: {len(audit.missing_references)}", f"- Code issues: {len(audit.code_issues)}", f"- Asset issues: {len(audit.asset_issues)}", ""]
    _write_text(out / "CLOSURE_LAB_START_HERE.md", "\n".join(lines), result, root, changed=True)
    _write_json(out / "closure_status.json", {"checks": [{"name": k, "generated": v} for k, v in checks], "version": CLOSURE_LAB_VERSION}, result, root, changed=True)
    return result


def build_closure_lab_bundle(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("Closure Lab Bundle")
    out = _closure_dir(root)
    bundle_dir = out / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bundle_dir / f"closure_lab_bundle_{_now()}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or p == zip_path:
                continue
            if "bundles" in p.parts and p.suffix.lower() == ".zip":
                continue
            z.write(p, p.relative_to(root))
    result.add_created(root, zip_path)
    result.add_note("Closure Lab bundle contains generated simulation, engine, corpus, mutation, tuning, and evidence artifacts.")
    return result


def run_closure_lab_pass(root: Path) -> ClosureLabResult:
    root = Path(root)
    result = ClosureLabResult("One-Click Closure Lab Pass")
    for label, fn in [
        ("dashboard", write_closure_dashboard),
        ("engine adapters", write_engine_adapter_suite),
        ("offline runtime", build_offline_runtime_simulation),
        ("sff2 corpus", build_sff2_corpus_validator),
        ("sff2 triage", write_sff2_unknown_triage),
        ("mutation sheet", export_direct_mutation_commit_sheet),
        ("gameplay tuning", export_gameplay_tuning_sheet),
        ("evidence contract", write_report_evidence_contract),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.add_warning(f"{label} failed: {exc}")
    try:
        result.merge(build_closure_lab_bundle(root), "bundle")
    except Exception as exc:
        result.add_warning(f"bundle failed: {exc}")
    try:
        result.merge(write_closure_dashboard(root), "dashboard refresh")
    except Exception:
        pass
    return result


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts: Dict[int, int] = {}
    for b in data:
        counts[b] = counts.get(b, 0) + 1
    total = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _magic_hits(data: bytes) -> Dict[str, List[int]]:
    hits: Dict[str, List[int]] = {"png": [], "pcx": [], "riff_wave": [], "elecbyte_spr": [], "elecbyte_snd": []}
    for name, sig in [("png", b"\x89PNG\r\n\x1a\n"), ("riff_wave", b"RIFF"), ("elecbyte_spr", b"ElecbyteSpr\x00"), ("elecbyte_snd", b"ElecbyteSnd\x00")]:
        pos = 0
        while True:
            idx = data.find(sig, pos)
            if idx < 0:
                break
            if name == "riff_wave" and idx + 12 <= len(data) and data[idx + 8:idx + 12] != b"WAVE":
                pos = idx + 4
                continue
            hits[name].append(idx)
            pos = idx + max(1, len(sig))
    # PCX sprites usually begin with 0x0A. Too common to list all, so keep sparse plausible offsets.
    pcx = []
    pos = 0
    while len(pcx) < 100:
        idx = data.find(b"\x0A", pos)
        if idx < 0:
            break
        if idx + 4 < len(data) and data[idx + 1] in {0, 2, 3, 5} and data[idx + 2] in {1, 8}:
            pcx.append(idx)
        pos = idx + 1
    hits["pcx"] = pcx
    return hits


def _hexdump(data: bytes, width: int = 16) -> str:
    lines: List[str] = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{off:08X}  {hexs:<{width*3}}  {asc}")
    return "\n".join(lines)


def _u32(data: bytes, off: int) -> Optional[int]:
    if off + 4 > len(data):
        return None
    return int.from_bytes(data[off:off + 4], "little", signed=False)


def _sff_header_probe(data: bytes) -> Dict[str, object]:
    return {
        "signature": data[:12].decode("latin-1", errors="replace") if len(data) >= 12 else "",
        "version_bytes": list(data[12:16]) if len(data) >= 16 else [],
        "u32_16": _u32(data, 16),
        "u32_20": _u32(data, 20),
        "u32_24": _u32(data, 24),
        "u32_28": _u32(data, 28),
        "u32_32": _u32(data, 32),
        "u32_36": _u32(data, 36),
        "u32_40": _u32(data, 40),
        "u32_44": _u32(data, 44),
        "u32_48": _u32(data, 48),
        "u32_52": _u32(data, 52),
        "u32_56": _u32(data, 56),
        "u32_60": _u32(data, 60),
        "u32_64": _u32(data, 64),
    }
