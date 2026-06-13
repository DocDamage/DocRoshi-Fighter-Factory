from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import parse_air, parse_code, parse_def, read_text_safely, write_text_safely, scan_project
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd

GAP_CLOSER_VERSION = "7.0.0"
CODE_EXTS = {".cmd", ".cns", ".st"}
BINARY_EXTS = {".sff", ".snd"}
EVIDENCE_EXTS = {".txt", ".log", ".json", ".csv", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


@dataclass
class GapCloserResult:
    title: str = "Gap Closer"
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, msg: object) -> None:
        self.warnings.append(str(msg))

    def add_note(self, msg: object) -> None:
        self.notes.append(str(msg))

    def merge(self, other: object, label: Optional[str] = None) -> None:
        if not other:
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


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _gap_dir(root: Path) -> Path:
    out = Path(root) / "gap_closer"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, res: Optional[GapCloserResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed and changed:
        _backup_file(path)
    write_text_safely(path, text.rstrip() + "\n")
    if res is not None:
        (res.add_changed if existed or changed else res.add_created)(root or path.parent, path)
    return path


def _write_json(path: Path, payload: object, res: Optional[GapCloserResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed and changed:
        _backup_file(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if res is not None:
        (res.add_changed if existed or changed else res.add_created)(root or path.parent, path)
    return path


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[GapCloserResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for row in rows:
            w.writerow({field: row.get(field, "") for field in fields})
    if res is not None:
        (res.add_changed if existed else res.add_created)(root or path.parent, path)
    return path


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _backup_file(path: Path) -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak_gap_{_now()}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _main_def(root: Path) -> Optional[Path]:
    root = Path(root)
    exact = root / f"{root.name}.def"
    if exact.exists():
        return exact
    hits = sorted(root.glob("*.def"), key=lambda p: p.name.lower())
    return hits[0] if hits else None


def _project_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {"root": root, "def": _main_def(root)}
    refs: Dict[str, str] = {}
    dpath = out.get("def")
    if dpath and dpath.exists():
        try:
            sec = parse_def(read_text_safely(dpath)).get("files")
            if sec:
                refs = {k.lower(): str(v).strip().strip('"') for k, v in sec.values.items()}
        except Exception:
            refs = {}

    def by_ref(key: str, ext: str) -> Optional[Path]:
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                return p
        try:
            p2 = find_character_file(root, ext)
            if p2 and p2.exists():
                return p2
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
    skip = {"__pycache__", "gap_closer", "runtime_lab", "binary_core", "binary_deep", "binary_maturity", "forge_timeline", "forge_polish", "forge_beyond", "visual_forge"}
    out: List[Path] = []
    for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()):
        if p.is_file() and p.suffix.lower() in CODE_EXTS and not any(part in skip or part.startswith(".") for part in p.parts):
            out.append(p)
    return out


def _char_name(root: Path) -> str:
    dpath = _main_def(root)
    if dpath and dpath.exists():
        try:
            info = parse_def(read_text_safely(dpath)).get("info")
            if info:
                return (info.values.get("displayname") or info.values.get("name") or Path(root).name).strip().strip('"')
        except Exception:
            pass
    return Path(root).name or "character"


def _first_int(value: object, default: int = 0) -> int:
    m = re.search(r"-?\d+", str(value or ""))
    return int(m.group(0)) if m else default


def _numbers(value: object) -> List[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))]


def write_gap_closer_dashboard(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Gap Closer Dashboard")
    base = _gap_dir(root)
    status = _limitation_status(root)
    lines = [
        "# Gap Closer Start Here",
        "",
        f"Project: `{root.name}`",
        f"MugenForge gap closer version: `{GAP_CLOSER_VERSION}`",
        "",
        "This panel targets the previous honest-limitation list with concrete tools: engine-profile probing, lightweight source-runtime modeling, engine-backed scenario sessions, SFF/SND corpus validation, binary triage, guarded binary commits, and generated-code tuning sheets.",
        "",
        "## Previous limitation closure map",
        "",
        "| Previous limitation | v7.0 implementation | Current status |",
        "|---|---|---|",
    ]
    for row in status:
        lines.append(f"| {row['limitation']} | {row['implementation']} | {row['status']} |")
    lines += [
        "",
        "## Recommended order",
        "",
        "1. Configure or probe an engine profile if you have a local engine executable.",
        "2. Run the Source Runtime Model to catch source-level logic and timing issues before booting the engine.",
        "3. Export and run scenario sessions; copy engine logs/screenshots into `gap_closer/engine_sessions/` or `runtime_lab/logs_inbox/`.",
        "4. Run the SFF2 Corpus Lab on your real character archive folder.",
        "5. Use Binary Triage for unknown/corrupt files.",
        "6. Commit binary candidates only after hash/backup verification.",
        "7. Apply generated-code tuning only from enabled CSV rows.",
    ]
    _write_text(base / "GAP_CLOSER_START_HERE.md", "\n".join(lines), res, root)
    _write_json(base / "limitation_closure_status.json", status, res, root)
    res.add_note("Gap closure dashboard written.")
    return res


def _limitation_status(root: Path) -> List[Dict[str, str]]:
    return [
        {
            "limitation": "No M.U.G.E.N/IKEMEN runtime simulation.",
            "implementation": "Source Runtime Model builds a lightweight StateDef/AIR/CMD timing simulator and Engine Scenario Sessions run the real external engine when configured.",
            "status": "Partially closed: real engine evidence is supported; exact full engine emulation is still not claimed.",
        },
        {
            "limitation": "Launcher scripts must be reviewed for the target engine/build.",
            "implementation": "Engine Profile Probe records executable hash, help/version output, working directory, selected profile, and exact commands before launch.",
            "status": "Improved: commands are validated/probed and reproducibly logged.",
        },
        {
            "limitation": "Runtime readiness scores are evidence aids, not engine-authoritative.",
            "implementation": "Engine-backed Readiness Gate upgrades status only when scenario sessions include real engine return codes/log evidence.",
            "status": "Improved: score can be evidence-backed when the external engine runs.",
        },
        {
            "limitation": "Full arbitrary historical/custom SFF2 variants need broader corpus validation.",
            "implementation": "SFF/SND Corpus Lab recursively validates user-supplied corpora and builds support matrices, decode/export results, and failure buckets.",
            "status": "Tooling added: coverage grows as users run real corpora.",
        },
        {
            "limitation": "Unknown/corrupt/encrypted/tool-specific SFF2 layouts may need manual review.",
            "implementation": "Unknown Binary Triage classifies headers, entropy, payload signatures, first bytes, likely causes, and next action.",
            "status": "Reduced: manual review is guided by structured diagnostics.",
        },
        {
            "limitation": "SFF/SND mutation remains candidate/backup-first and avoids blind overwrite.",
            "implementation": "Guarded Binary Commit can write candidate files into project slots only with SHA-256 verification and automatic backups.",
            "status": "Closed safely: direct commit exists, but not blind overwrite.",
        },
        {
            "limitation": "Generated gameplay code requires real playtesting and tuning.",
            "implementation": "Generated Code Tuning Lab exports/apply sheets for HitDef damage/pause/velocity and links each row to runtime scenarios.",
            "status": "Improved: tuning is guided and repeatable; creative feel still needs playtesting.",
        },
        {
            "limitation": "Reports/graphs/previews/static frame-data are not substitutes for engine testing.",
            "implementation": "Engine-backed Evidence Gate separates static findings from real engine logs/session return codes and evidence hashes.",
            "status": "Improved: reports now show whether claims are static-only or backed by engine evidence.",
        },
    ]


def probe_engine_profile(root: Path, engine_exe: Optional[Path | str] = None, game_root: Optional[Path | str] = None, timeout_seconds: float = 6.0) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Engine Profile Probe")
    base = _gap_dir(root) / "engine_profile"
    base.mkdir(parents=True, exist_ok=True)
    engine_path = Path(engine_exe).expanduser() if engine_exe else None
    if engine_path is None:
        # Try existing runtime_lab profiles/configs before leaving blank.
        for rel in ("runtime_lab/runtime_engine_profile.json", "runtime_lab/runtime_config.json", "runtime_lab/engine_profile.json"):
            p = root / rel
            if p.exists():
                try:
                    data = json.loads(read_text_safely(p))
                    cand = data.get("engine_executable") or data.get("engine") or data.get("path")
                    if cand:
                        engine_path = Path(str(cand)).expanduser()
                        break
                except Exception:
                    pass
    exists = bool(engine_path and engine_path.exists())
    kind = _guess_engine_kind(engine_path.name if engine_path else "")
    profile: Dict[str, object] = {
        "schema": "mugenforge.gap_closer.engine_profile.v1",
        "version": GAP_CLOSER_VERSION,
        "project_root": str(root),
        "character": _char_name(root),
        "engine_executable": str(engine_path) if engine_path else "",
        "engine_exists": exists,
        "engine_kind_guess": kind,
        "engine_sha256": _sha256(engine_path) if exists and engine_path and engine_path.is_file() else "",
        "game_root": str(Path(game_root).expanduser()) if game_root else (str(engine_path.parent) if exists and engine_path else ""),
        "probe_timestamp": datetime.now().isoformat(timespec="seconds"),
        "probe_attempts": [],
        "recommended_profiles": _recommended_profile_templates(kind),
    }
    attempts: List[Dict[str, object]] = []
    if exists and engine_path:
        for args in (["--version"], ["-version"], ["--help"], ["-h"]):
            attempts.append(_probe_command(engine_path, args, Path(str(profile["game_root"])) if profile.get("game_root") else engine_path.parent, timeout_seconds))
        res.add_note("Engine executable exists; probe commands completed or were safely captured.")
    else:
        res.add_warning("No engine executable was found. Profile template was written with blank engine path.")
    profile["probe_attempts"] = attempts
    _write_json(base / "engine_profile_probe.json", profile, res, root)
    lines = [
        "# Engine Profile Probe",
        "",
        f"Engine: `{profile['engine_executable'] or 'not configured'}`",
        f"Exists: `{exists}`",
        f"Kind guess: `{kind}`",
        f"SHA-256: `{profile['engine_sha256'] or 'not available'}`",
        "",
        "## Probe attempts",
    ]
    if not attempts:
        lines.append("No probe was run because no executable is configured.")
    for a in attempts:
        lines += [
            "",
            f"### `{a.get('display_command', '')}`",
            f"Return code: `{a.get('returncode', '')}`",
            f"Timed out: `{a.get('timeout', False)}`",
            f"Stdout excerpt: `{str(a.get('stdout_excerpt', '')).replace('`', '')[:240]}`",
            f"Stderr excerpt: `{str(a.get('stderr_excerpt', '')).replace('`', '')[:240]}`",
        ]
    lines += [
        "",
        "## How this closes the launcher gap",
        "MugenForge now records the exact engine path, guessed engine family, executable hash, working directory, and probe evidence before building/running commands. This reduces manual script review and makes engine sessions reproducible.",
    ]
    _write_text(base / "ENGINE_PROFILE_PROBE.md", "\n".join(lines), res, root)
    return res


def _guess_engine_kind(name: str) -> str:
    s = name.lower()
    if "ikemen" in s:
        return "ikemen_go"
    if "mugen" in s:
        return "mugen"
    if not s:
        return "not_configured"
    return "unknown_engine"


def _recommended_profile_templates(kind: str) -> List[Dict[str, object]]:
    common = [
        {"name": "boot_only", "description": "Launch engine with no special arguments; capture stdout/stderr.", "args": []},
        {"name": "quick_vs", "description": "Creator must adapt args for target engine if needed.", "args": []},
    ]
    if kind == "ikemen_go":
        common.append({"name": "ikemen_training_hint", "description": "Ikemen GO builds vary; use select.def/test mode settings when CLI flags differ.", "args": []})
    if kind == "mugen":
        common.append({"name": "mugen_classic_hint", "description": "Classic M.U.G.E.N CLI support varies; generated launchers are evidence-capture wrappers.", "args": []})
    return common


def _probe_command(engine: Path, args: Sequence[str], cwd: Path, timeout_seconds: float) -> Dict[str, object]:
    cmd = [str(engine)] + list(args)
    out: Dict[str, object] = {"command": cmd, "display_command": " ".join(cmd), "cwd": str(cwd), "returncode": "", "timeout": False, "stdout_excerpt": "", "stderr_excerpt": ""}
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=max(1.0, float(timeout_seconds)))
        out.update({
            "returncode": proc.returncode,
            "stdout_excerpt": (proc.stdout or "")[:1200],
            "stderr_excerpt": (proc.stderr or "")[:1200],
        })
    except subprocess.TimeoutExpired as exc:
        out.update({"timeout": True, "stdout_excerpt": str(exc.stdout or "")[:1200], "stderr_excerpt": str(exc.stderr or "")[:1200]})
    except Exception as exc:
        out.update({"error": str(exc)})
    return out


def build_source_runtime_model(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Source Runtime Model")
    base = _gap_dir(root) / "source_runtime_model"
    base.mkdir(parents=True, exist_ok=True)
    files = _project_files(root)
    actions = []
    action_by_no: Dict[int, object] = {}
    air_path = files.get("air")
    if air_path and air_path.exists():
        try:
            actions = parse_air(read_text_safely(air_path))
            action_by_no = {a.number: a for a in actions}
        except Exception as exc:
            res.add_warning(f"AIR parse failed: {exc}")
    states: List[Dict[str, object]] = []
    commands: List[Dict[str, object]] = []
    controllers: List[Dict[str, object]] = []
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception as exc:
            res.add_warning(f"Code parse failed for {_rel(root, p)}: {exc}")
            continue
        for c in scan.commands:
            commands.append({"file": _rel(root, p), "line": c.line, "name": c.name, "command": c.command, "time": c.time or "", "buffer_time": c.buffer_time or ""})
        for st in scan.states:
            anim = _first_int(st.values.get("anim", st.number), st.number)
            action = action_by_no.get(anim)
            total_ticks = 0
            frames: List[Dict[str, object]] = []
            active_frames: List[int] = []
            body_frames: List[int] = []
            if action:
                for idx, fr in enumerate(action.frames, 1):
                    ticks = max(0, int(getattr(fr, "ticks", 0)))
                    total_ticks += ticks
                    clsn1 = sum(1 for b in getattr(fr, "clsn", []) if getattr(b, "kind", "").lower() == "clsn1")
                    clsn2 = sum(1 for b in getattr(fr, "clsn", []) if getattr(b, "kind", "").lower() == "clsn2")
                    if clsn1:
                        active_frames.append(idx)
                    if clsn2:
                        body_frames.append(idx)
                    frames.append({"frame": idx, "sprite": f"{fr.group},{fr.image}", "ticks": ticks, "offset": [fr.x, fr.y], "clsn1": clsn1, "clsn2": clsn2})
            hitdefs = [ctrl for ctrl in st.controllers if (ctrl.stype or ctrl.values.get("type", "")).lower() == "hitdef"]
            playsnds = [ctrl for ctrl in st.controllers if (ctrl.stype or ctrl.values.get("type", "")).lower() == "playsnd"]
            changestates = [ctrl for ctrl in st.controllers if (ctrl.stype or ctrl.values.get("type", "")).lower() in {"changestate", "selfstate"}]
            state_rec = {
                "file": _rel(root, p),
                "line": st.line,
                "state": st.number,
                "anim": anim,
                "has_action": bool(action),
                "frame_count": len(frames),
                "total_ticks": total_ticks,
                "estimated_seconds_at_60fps": round(total_ticks / 60.0, 4),
                "first_active_frame": active_frames[0] if active_frames else "",
                "last_active_frame": active_frames[-1] if active_frames else "",
                "active_frame_count": len(active_frames),
                "body_frame_count": len(body_frames),
                "movetype": st.values.get("movetype", ""),
                "physics": st.values.get("physics", ""),
                "ctrl": st.values.get("ctrl", ""),
                "hitdef_count": len(hitdefs),
                "playsnd_count": len(playsnds),
                "changestate_count": len(changestates),
                "estimated_risk": _runtime_risk(st, total_ticks, active_frames, hitdefs, changestates, action is not None),
            }
            states.append(state_rec)
            for ctrl in st.controllers:
                ctype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if ctype in {"hitdef", "playsnd", "changestate", "selfstate", "velset", "veladd", "projectile", "helper", "explod"}:
                    controllers.append({
                        "file": _rel(root, p),
                        "line": ctrl.line,
                        "state": st.number,
                        "type": ctype,
                        "trigger1": ctrl.values.get("trigger1", ""),
                        "value": ctrl.values.get("value", ctrl.values.get("damage", ctrl.values.get("velocity", ""))),
                    })
    traces = _build_static_traces(states, controllers)
    model = {
        "schema": "mugenforge.gap_closer.source_runtime_model.v1",
        "version": GAP_CLOSER_VERSION,
        "project": str(root),
        "character": _char_name(root),
        "air_actions": len(actions),
        "commands": commands,
        "states": states,
        "notable_controllers": controllers,
        "static_traces": traces,
        "disclaimer": "This is a lightweight source-runtime model for preflight checks. It does not replace real M.U.G.E.N/IKEMEN execution.",
    }
    _write_json(base / "source_runtime_model.json", model, res, root)
    _write_csv(base / "state_runtime_estimates.csv", states, ["file", "line", "state", "anim", "has_action", "frame_count", "total_ticks", "estimated_seconds_at_60fps", "first_active_frame", "last_active_frame", "active_frame_count", "body_frame_count", "movetype", "physics", "ctrl", "hitdef_count", "playsnd_count", "changestate_count", "estimated_risk"], res, root)
    _write_csv(base / "controller_timeline_events.csv", controllers, ["file", "line", "state", "type", "trigger1", "value"], res, root)
    _write_csv(base / "static_simulation_trace.csv", traces, ["scenario", "step", "state", "event", "detail", "risk"], res, root)
    lines = ["# Source Runtime Model", "", "This adds a lightweight runtime-style pass over source files. It estimates state duration, active windows, sound events, HitDefs, ChangeStates, and common risks before launching the external engine.", "", "## Summary", "", f"Commands: {len(commands)}", f"States: {len(states)}", f"AIR actions: {len(actions)}", f"Static traces: {len(traces)}", "", "## Highest-risk states", ""]
    for st in sorted(states, key=lambda r: str(r.get("estimated_risk", "")), reverse=True)[:20]:
        if st.get("estimated_risk"):
            lines.append(f"- State {st['state']} / anim {st['anim']}: {st['estimated_risk']}")
    lines += ["", "## Engine relation", "This model narrows the no-simulation gap but does not claim cycle-perfect engine behavior. Pair it with Engine Scenario Sessions for real evidence."]
    _write_text(base / "SOURCE_RUNTIME_MODEL.md", "\n".join(lines), res, root)
    res.add_note(f"Modeled {len(states)} StateDefs and {len(actions)} AIR actions.")
    return res


def _runtime_risk(st: object, total_ticks: int, active_frames: List[int], hitdefs: Sequence[object], changestates: Sequence[object], has_action: bool) -> str:
    risks: List[str] = []
    movetype = str(getattr(st, "values", {}).get("movetype", "")).upper()
    if not has_action:
        risks.append("missing AIR action for anim")
    if total_ticks == 0 and has_action:
        risks.append("zero estimated duration")
    if movetype == "A" and hitdefs and not active_frames:
        risks.append("HitDef attack has no Clsn1 active frames")
    if movetype == "A" and active_frames and not hitdefs:
        risks.append("Clsn1 active boxes but no HitDef detected")
    if not changestates and total_ticks > 0 and _first_int(getattr(st, "number", 0), 0) >= 0:
        risks.append("no obvious ChangeState/SelfState exit")
    return "; ".join(risks)


def _build_static_traces(states: Sequence[Dict[str, object]], controllers: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    ctrl_by_state: Dict[int, List[Dict[str, object]]] = {}
    for c in controllers:
        try:
            ctrl_by_state.setdefault(int(c.get("state", 0)), []).append(c)
        except Exception:
            pass
    for st in states[:300]:
        state = int(st.get("state", 0) or 0)
        scenario = f"state_{state}"
        out.append({"scenario": scenario, "step": 0, "state": state, "event": "enter_state", "detail": f"anim={st.get('anim')} ticks={st.get('total_ticks')}", "risk": st.get("estimated_risk", "")})
        for i, c in enumerate(ctrl_by_state.get(state, [])[:20], 1):
            out.append({"scenario": scenario, "step": i, "state": state, "event": c.get("type", "controller"), "detail": f"trigger1={c.get('trigger1','')} value={c.get('value','')}", "risk": ""})
        out.append({"scenario": scenario, "step": 99, "state": state, "event": "estimated_exit", "detail": f"after {st.get('total_ticks')} ticks unless controller interrupts", "risk": st.get("estimated_risk", "")})
    return out


def build_engine_scenario_sessions(root: Path, dry_run: bool = True, timeout_seconds: float = 12.0) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Engine Scenario Sessions")
    base = _gap_dir(root) / "engine_sessions"
    base.mkdir(parents=True, exist_ok=True)
    profile_path = _gap_dir(root) / "engine_profile" / "engine_profile_probe.json"
    profile = json.loads(read_text_safely(profile_path)) if profile_path.exists() else {}
    engine = str(profile.get("engine_executable", "")).strip()
    game_root = str(profile.get("game_root", "")).strip() or str(Path(engine).parent if engine else root)
    sheet = base / "engine_scenario_sheet.csv"
    scenarios = _scenario_rows(root)
    _write_csv(sheet, scenarios, ["enabled", "scenario_id", "kind", "state", "command", "expected", "engine_args", "notes"], res, root)
    session_rows: List[Dict[str, object]] = []
    for sc in scenarios:
        if str(sc.get("enabled", "yes")).lower() not in {"yes", "1", "true"}:
            continue
        command = [engine] + [x for x in str(sc.get("engine_args", "")).split(" ") if x]
        rec: Dict[str, object] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "scenario_id": sc.get("scenario_id", ""),
            "dry_run": dry_run,
            "engine": engine,
            "cwd": game_root,
            "command": " ".join(command) if engine else "",
            "returncode": "",
            "status": "not_configured" if not engine else ("dry_run" if dry_run else "pending"),
            "stdout_file": "",
            "stderr_file": "",
            "notes": "",
        }
        if not engine:
            rec["notes"] = "Configure engine profile before live runs."
        elif dry_run:
            rec["notes"] = "Dry run only; exact command recorded."
        else:
            tag = f"{_now()}_{sc.get('scenario_id','scenario')}"
            try:
                proc = subprocess.run(command, cwd=game_root or None, capture_output=True, text=True, timeout=max(1.0, timeout_seconds))
                stdout_path = base / f"stdout_{tag}.txt"
                stderr_path = base / f"stderr_{tag}.txt"
                stdout_path.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
                stderr_path.write_text(proc.stderr or "", encoding="utf-8", errors="replace")
                rec.update({"returncode": proc.returncode, "status": "pass" if proc.returncode == 0 else "fail", "stdout_file": _rel(root, stdout_path), "stderr_file": _rel(root, stderr_path)})
                res.add_created(root, stdout_path)
                res.add_created(root, stderr_path)
            except subprocess.TimeoutExpired as exc:
                rec.update({"returncode": 124, "status": "timeout", "notes": str(exc)[:400]})
            except Exception as exc:
                rec.update({"returncode": 1, "status": "error", "notes": str(exc)[:400]})
        session_rows.append(rec)
    _write_csv(base / "engine_session_results.csv", session_rows, ["timestamp", "scenario_id", "dry_run", "engine", "cwd", "command", "returncode", "status", "stdout_file", "stderr_file", "notes"], res, root)
    _write_json(base / "engine_session_summary.json", {"engine_configured": bool(engine), "dry_run": dry_run, "scenario_count": len(session_rows), "pass_count": sum(1 for r in session_rows if r.get("status") == "pass"), "results": session_rows}, res, root)
    lines = ["# Engine Scenario Sessions", "", f"Dry run: `{dry_run}`", f"Engine configured: `{bool(engine)}`", f"Scenarios: `{len(session_rows)}`", "", "These sessions close the static-report gap only when they contain real engine return codes/logs. Dry-run rows are useful command previews but are not runtime evidence."]
    _write_text(base / "ENGINE_SCENARIO_SESSIONS.md", "\n".join(lines), res, root)
    return res


def _scenario_rows(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = [
        {"enabled": "yes", "scenario_id": "boot_engine", "kind": "boot", "state": "", "command": "", "expected": "engine starts and exits/continues without fatal error", "engine_args": "", "notes": "Baseline smoke."},
        {"enabled": "yes", "scenario_id": "load_character", "kind": "load", "state": "", "command": "", "expected": "character loads with no missing file errors", "engine_args": "", "notes": "Arguments vary by engine; edit as needed."},
    ]
    files = _project_files(root)
    if files.get("cmd") and files["cmd"] and files["cmd"].exists():
        try:
            for c in parse_code(read_text_safely(files["cmd"])).commands[:40]:
                rows.append({"enabled": "yes", "scenario_id": f"command_{_slug(c.name)}", "kind": "command", "state": "", "command": c.name, "expected": "command can be performed in match", "engine_args": "", "notes": c.command})
        except Exception:
            pass
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states[:60]:
            if int(st.number) >= 0:
                rows.append({"enabled": "yes", "scenario_id": f"state_{st.number}", "kind": "state", "state": st.number, "command": "", "expected": "state can be reached/exits cleanly", "engine_args": "", "notes": f"{_rel(root, p)} line {st.line}"})
    return rows[:250]


def _slug(s: object) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(s)).strip("_") or "item"


def build_engine_backed_readiness_gate(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Engine-Backed Readiness Gate")
    base = _gap_dir(root) / "readiness_gate"
    base.mkdir(parents=True, exist_ok=True)
    model_path = _gap_dir(root) / "source_runtime_model" / "state_runtime_estimates.csv"
    session_path = _gap_dir(root) / "engine_sessions" / "engine_session_results.csv"
    evidence_files = _evidence_files(root)
    model_rows = _read_csv(model_path)
    session_rows = _read_csv(session_path)
    source_risks = [r for r in model_rows if str(r.get("estimated_risk", "")).strip()]
    real_sessions = [r for r in session_rows if str(r.get("dry_run", "")).lower() in {"false", "0", "no"}]
    failing_sessions = [r for r in real_sessions if str(r.get("status", "")).lower() not in {"pass", "ok", "0"}]
    score = 100
    reasons: List[str] = []

    def ding(n: int, reason: str) -> None:
        nonlocal score
        if n > 0:
            score -= n
            reasons.append(f"-{n}: {reason}")

    audit = scan_project(root)
    ding(min(35, 7 * len(audit.missing_required)), f"missing required files: {', '.join(audit.missing_required)}" if audit.missing_required else "")
    ding(min(30, 3 * len(source_risks)), f"source runtime model risks: {len(source_risks)}" if source_risks else "")
    if not real_sessions:
        ding(25, "no live engine session evidence")
    else:
        ding(min(50, 12 * len(failing_sessions)), f"failing engine sessions: {len(failing_sessions)}" if failing_sessions else "")
    if not evidence_files:
        ding(8, "no external evidence files indexed")
    score = max(0, min(100, score))
    evidence_status = "engine_backed" if real_sessions and not failing_sessions else ("engine_evidence_with_failures" if real_sessions else "static_only")
    report = {
        "schema": "mugenforge.gap_closer.readiness_gate.v1",
        "score": score,
        "evidence_status": evidence_status,
        "source_risk_count": len(source_risks),
        "live_engine_session_count": len(real_sessions),
        "failing_engine_session_count": len(failing_sessions),
        "evidence_file_count": len(evidence_files),
        "reasons": reasons,
        "generated": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(base / "engine_backed_readiness_gate.json", report, res, root)
    lines = [
        "# Engine-Backed Readiness Gate",
        "",
        f"Score: **{score}/100**",
        f"Evidence status: **{evidence_status}**",
        "",
        "## Why this differs from older static readiness",
        "This gate clearly separates static/source-only checks from live engine evidence. A project is marked `engine_backed` only when live scenario rows exist and do not report failures.",
        "",
        "## Score reasons",
    ]
    lines += [f"- {x}" for x in reasons] if reasons else ["- No deductions."]
    _write_text(base / "ENGINE_BACKED_READINESS_GATE.md", "\n".join(lines), res, root)
    return res


def _evidence_files(root: Path) -> List[Path]:
    roots = [Path(root) / "gap_closer" / "engine_sessions", Path(root) / "runtime_lab", Path(root) / "testing", Path(root) / "release" / "screenshots"]
    out: List[Path] = []
    for d in roots:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_file() and p.suffix.lower() in EVIDENCE_EXTS:
                out.append(p)
    return out


def build_sff_snd_corpus_lab(root: Path, corpus_dir: Optional[Path | str] = None, export_supported: bool = False) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("SFF/SND Corpus Validation Lab")
    base = _gap_dir(root) / "corpus_lab"
    base.mkdir(parents=True, exist_ok=True)
    scan_roots = [root]
    if corpus_dir:
        c = Path(corpus_dir).expanduser()
        if c.exists():
            scan_roots.append(c)
        else:
            res.add_warning(f"Corpus folder does not exist: {c}")
    rows: List[Dict[str, object]] = []
    for sr in scan_roots:
        for p in sorted(Path(sr).rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in BINARY_EXTS:
                continue
            if "gap_closer" in p.parts and p.suffix.lower() in BINARY_EXTS:
                continue
            rows.append(_validate_binary_file(root, p, base, export_supported=export_supported))
    fields = ["file", "kind", "size", "sha256", "signature", "variant", "record_count", "supported_export", "decode_status", "warnings", "exception"]
    _write_csv(base / "sff_snd_corpus_matrix.csv", rows, fields, res, root)
    summary: Dict[str, object] = {
        "total_files": len(rows),
        "sff_files": sum(1 for r in rows if r.get("kind") == "sff"),
        "snd_files": sum(1 for r in rows if r.get("kind") == "snd"),
        "supported_export_count": sum(1 for r in rows if str(r.get("supported_export", "")).lower() == "yes"),
        "warning_count": sum(1 for r in rows if r.get("warnings")),
        "exception_count": sum(1 for r in rows if r.get("exception")),
    }
    _write_json(base / "sff_snd_corpus_summary.json", summary, res, root)
    lines = ["# SFF/SND Corpus Validation Lab", "", f"Files scanned: {len(rows)}", f"SFF files: {summary['sff_files']}", f"SND files: {summary['snd_files']}", f"Files with supported export/read paths: {summary['supported_export_count']}", f"Files with warnings: {summary['warning_count']}", f"Files with exceptions: {summary['exception_count']}", "", "Run this against a real archive of legacy/custom characters to grow confidence beyond controlled fixtures."]
    _write_text(base / "SFF_SND_CORPUS_LAB.md", "\n".join(lines), res, root)
    return res


def _validate_binary_file(root: Path, path: Path, base: Path, export_supported: bool = False) -> Dict[str, object]:
    row: Dict[str, object] = {
        "file": _rel(root, path),
        "kind": path.suffix.lower().lstrip("."),
        "size": path.stat().st_size if path.exists() else 0,
        "sha256": _sha256(path),
        "signature": "",
        "variant": "",
        "record_count": "",
        "supported_export": "no",
        "decode_status": "not_attempted",
        "warnings": "",
        "exception": "",
    }
    try:
        head = path.read_bytes()[:16]
        row["signature"] = head.hex(" ")
        if path.suffix.lower() == ".sff":
            info = read_sff(path)
            row["variant"] = getattr(info, "variant", "")
            row["record_count"] = len(getattr(info, "sprites", []) or []) or getattr(info, "sprite_count", "")
            row["warnings"] = " | ".join(getattr(info, "warnings", []) or [])
            row["supported_export"] = "yes" if getattr(info, "is_supported_for_extraction", False) or getattr(info, "sprites", []) else "no"
            row["decode_status"] = "parsed" if row["record_count"] else "metadata_only"
        elif path.suffix.lower() == ".snd":
            info = read_snd(path)
            row["variant"] = "snd-signature" if getattr(info, "has_signature", False) else "snd-scan"
            row["record_count"] = len(getattr(info, "sounds", []) or [])
            row["warnings"] = " | ".join(getattr(info, "warnings", []) or [])
            row["supported_export"] = "yes" if len(getattr(info, "sounds", []) or []) else "no"
            row["decode_status"] = "parsed" if row["record_count"] else "metadata_only"
    except Exception as exc:
        row["exception"] = str(exc)
        row["decode_status"] = "exception"
    return row


def write_unknown_binary_triage(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Unknown Binary Triage")
    base = _gap_dir(root) / "unknown_binary_triage"
    base.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()):
        if not p.is_file() or p.suffix.lower() not in BINARY_EXTS:
            continue
        if "gap_closer" in p.parts:
            continue
        rows.append(_triage_binary(root, p, base))
    fields = ["file", "kind", "size", "sha256", "signature_class", "entropy", "payload_signatures", "triage_status", "next_action", "first_64_bytes_hex"]
    _write_csv(base / "unknown_binary_triage.csv", rows, fields, res, root)
    _write_json(base / "unknown_binary_triage.json", rows, res, root)
    lines = ["# Unknown Binary Triage", "", "This report reduces manual review by classifying binary signatures, entropy, embedded payload hints, and recommended next action.", "", f"Files triaged: {len(rows)}", ""]
    for row in rows[:100]:
        lines.append(f"- `{row['file']}` — {row['triage_status']} — {row['next_action']}")
    _write_text(base / "UNKNOWN_BINARY_TRIAGE.md", "\n".join(lines), res, root)
    return res


def _triage_binary(root: Path, path: Path, base: Path) -> Dict[str, object]:
    data = path.read_bytes()
    sig = _signature_class(data, path.suffix.lower())
    entropy = _entropy(data[:1024 * 1024])
    payloads = []
    for name, marker in [("png", b"\x89PNG\r\n\x1a\n"), ("pcx", b"\x0A"), ("wav", b"RIFF"), ("zlib", b"\x78")]:
        if marker in data[: min(len(data), 1024 * 1024)]:
            payloads.append(name)
    if sig in {"sff", "snd"}:
        status = "known_container"
        action = "Use Binary Maturity / Corpus Lab for parse/export/mutation candidates."
    elif entropy > 7.7:
        status = "high_entropy_unknown"
        action = "Likely compressed/encrypted/custom payload; preserve original and review manually."
    elif payloads:
        status = "embedded_assets_detected"
        action = "Use Rescue Lab or Corpus Lab to extract/recover embedded payloads."
    else:
        status = "unknown_layout"
        action = "Keep raw backup; inspect with hex view/spec notes before mutation."
    return {
        "file": _rel(root, path),
        "kind": path.suffix.lower().lstrip("."),
        "size": len(data),
        "sha256": _sha256(path),
        "signature_class": sig,
        "entropy": round(entropy, 4),
        "payload_signatures": ",".join(sorted(set(payloads))),
        "triage_status": status,
        "next_action": action,
        "first_64_bytes_hex": data[:64].hex(" "),
    }


def _signature_class(data: bytes, suffix: str) -> str:
    if data.startswith(b"ElecbyteSpr\x00"):
        return "sff"
    if data.startswith(b"ElecbyteSnd\x00"):
        return "snd"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\x0A"):
        return "pcx_or_binary_0A"
    return f"unknown_{suffix.lstrip('.') or 'bin'}"


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    total = float(len(data))
    ent = 0.0
    for c in counts:
        if c:
            p = c / total
            ent -= p * math.log(p, 2)
    return ent


def export_binary_commit_sheet(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Guarded Binary Commit Sheet")
    base = _gap_dir(root) / "guarded_binary_commit"
    base.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    for label, rels in [("sff", ["binary_maturity/sff2_workspace/rebuilt", "binary_core/sff/builds", "binary_deep/sff2_native_builds"]), ("snd", ["binary_maturity/snd_slot_patch", "binary_core/snd/builds", "binary_deep/snd_patch"] )]:
        for rel in rels:
            d = root / rel
            if not d.exists():
                continue
            for p in sorted(d.rglob(f"*.{label}"), key=lambda x: str(x).lower()):
                target = _project_files(root).get(label)
                rows.append({
                    "enabled": "no",
                    "commit_token": "",
                    "kind": label,
                    "candidate_path": _rel(root, p),
                    "candidate_sha256": _sha256(p),
                    "target_path": _rel(root, target) if target else f"{root.name}.{label}",
                    "expected_target_sha256": _sha256(target) if target and target.exists() else "",
                    "backup_before_commit": "yes",
                    "notes": "Set enabled=yes and commit_token=COMMIT to write candidate into target slot.",
                })
    _write_csv(base / "guarded_binary_commit_sheet.csv", rows, ["enabled", "commit_token", "kind", "candidate_path", "candidate_sha256", "target_path", "expected_target_sha256", "backup_before_commit", "notes"], res, root)
    _write_text(base / "GUARDED_BINARY_COMMIT.md", "# Guarded Binary Commit\n\nEdit `guarded_binary_commit_sheet.csv`. Only rows with `enabled=yes` and `commit_token=COMMIT` are applied. The target SHA-256 must match unless the expected field is blank. A backup is written before commit.\n", res, root)
    return res


def apply_binary_commit_sheet(root: Path, sheet_path: Optional[Path | str] = None) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Apply Guarded Binary Commit Sheet")
    base = _gap_dir(root) / "guarded_binary_commit"
    sheet = Path(sheet_path) if sheet_path else base / "guarded_binary_commit_sheet.csv"
    rows = _read_csv(sheet)
    applied: List[Dict[str, object]] = []
    for row in rows:
        if str(row.get("enabled", "")).strip().lower() not in {"yes", "1", "true"}:
            continue
        if str(row.get("commit_token", "")).strip() != "COMMIT":
            res.add_warning(f"Skipped {row.get('candidate_path')}: commit_token must be COMMIT.")
            continue
        candidate = (root / str(row.get("candidate_path", ""))).resolve()
        target = (root / str(row.get("target_path", ""))).resolve()
        if not candidate.exists():
            res.add_warning(f"Candidate not found: {candidate}")
            continue
        expected_candidate = str(row.get("candidate_sha256", "")).strip()
        actual_candidate = _sha256(candidate)
        if expected_candidate and expected_candidate != actual_candidate:
            res.add_warning(f"Candidate hash mismatch for {candidate.name}; skipped.")
            continue
        if target.exists():
            expected_target = str(row.get("expected_target_sha256", "")).strip()
            actual_target = _sha256(target)
            if expected_target and expected_target != actual_target:
                res.add_warning(f"Target hash mismatch for {target.name}; skipped to avoid overwriting unexpected changes.")
                continue
            backup = _backup_file(target)
            if backup:
                res.add_created(root, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target)
        res.add_changed(root, target)
        applied.append({"candidate": _rel(root, candidate), "target": _rel(root, target), "target_sha256_after": _sha256(target)})
    _write_json(base / "guarded_binary_commit_applied.json", applied, res, root)
    if not applied:
        res.add_note("No binary commit rows were applied. Enable rows and use commit_token=COMMIT.")
    return res


def export_generated_code_tuning_lab(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Generated Code Tuning Lab")
    base = _gap_dir(root) / "generated_code_tuning"
    base.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    for p in _code_files(root):
        try:
            text = read_text_safely(p)
            scan = parse_code(text)
        except Exception:
            continue
        for st in scan.states:
            anim = _first_int(st.values.get("anim", st.number), st.number)
            for ctrl in st.controllers:
                ctype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if ctype != "hitdef":
                    continue
                damage = ctrl.values.get("damage", "")
                dmg_nums = _numbers(damage)
                dmg = int(dmg_nums[0]) if dmg_nums else 0
                rec = _recommend_hitdef_tuning(st.number, anim, dmg, ctrl.values)
                rows.append({
                    "enabled": "no",
                    "file": _rel(root, p),
                    "state": st.number,
                    "controller_line": ctrl.line,
                    "current_damage": damage,
                    "recommended_damage": rec["damage"],
                    "current_pausetime": ctrl.values.get("pausetime", ""),
                    "recommended_pausetime": rec["pausetime"],
                    "current_ground_velocity": ctrl.values.get("ground.velocity", ""),
                    "recommended_ground_velocity": rec["ground_velocity"],
                    "current_air_velocity": ctrl.values.get("air.velocity", ""),
                    "recommended_air_velocity": rec["air_velocity"],
                    "reason": rec["reason"],
                })
    fields = ["enabled", "file", "state", "controller_line", "current_damage", "recommended_damage", "current_pausetime", "recommended_pausetime", "current_ground_velocity", "recommended_ground_velocity", "current_air_velocity", "recommended_air_velocity", "reason"]
    _write_csv(base / "generated_code_tuning_sheet.csv", rows, fields, res, root)
    lines = ["# Generated Code Tuning Lab", "", f"HitDefs found: {len(rows)}", "", "Edit `generated_code_tuning_sheet.csv` and set `enabled=yes` for rows you want to apply. This creates backups and only updates common HitDef fields inside the selected controller block."]
    _write_text(base / "GENERATED_CODE_TUNING_LAB.md", "\n".join(lines), res, root)
    return res


def _recommend_hitdef_tuning(state: int, anim: int, damage: int, values: Dict[str, str]) -> Dict[str, object]:
    reason = []
    recommended_damage = damage
    if damage <= 0:
        recommended_damage = 30
        reason.append("zero/blank damage")
    elif damage > 150 and state < 3000:
        recommended_damage = 95
        reason.append("normal/special damage appears high")
    elif damage < 15 and 200 <= state < 1000:
        recommended_damage = 25
        reason.append("normal damage appears very low")
    pausetime = values.get("pausetime", "") or ("8,8" if recommended_damage < 80 else "10,12")
    gv = values.get("ground.velocity", "") or ("-3,0" if recommended_damage < 60 else "-5,0")
    av = values.get("air.velocity", "") or ("-2,-4" if recommended_damage < 60 else "-3,-6")
    if not reason:
        reason.append("baseline check")
    return {"damage": f"{recommended_damage}, {max(0, recommended_damage // 8)}", "pausetime": pausetime, "ground_velocity": gv, "air_velocity": av, "reason": "; ".join(reason)}


def apply_generated_code_tuning_sheet(root: Path, sheet_path: Optional[Path | str] = None) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Apply Generated Code Tuning Sheet")
    base = _gap_dir(root) / "generated_code_tuning"
    sheet = Path(sheet_path) if sheet_path else base / "generated_code_tuning_sheet.csv"
    rows = [r for r in _read_csv(sheet) if str(r.get("enabled", "")).strip().lower() in {"yes", "1", "true"}]
    if not rows:
        res.add_note("No tuning rows enabled.")
        return res
    by_file: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        by_file.setdefault(str(row.get("file", "")), []).append(row)
    for rel, file_rows in by_file.items():
        path = (root / rel).resolve()
        if not path.exists():
            res.add_warning(f"File not found: {rel}")
            continue
        text = read_text_safely(path)
        new_text = _apply_hitdef_rows_to_text(text, file_rows)
        if new_text != text:
            _backup_file(path)
            write_text_safely(path, new_text)
            res.add_changed(root, path)
        else:
            res.add_warning(f"No changes applied to {rel}; controller lines may have shifted.")
    return res


def _apply_hitdef_rows_to_text(text: str, rows: Sequence[Dict[str, str]]) -> str:
    lines = text.splitlines()
    for row in sorted(rows, key=lambda r: _first_int(r.get("controller_line"), 0), reverse=True):
        line_no = max(1, _first_int(row.get("controller_line"), 0))
        idx = line_no - 1
        if idx < 0 or idx >= len(lines):
            continue
        # Find the controller block from its header line to before next bracketed section.
        start = idx
        while start > 0 and not re.match(r"^\s*\[", lines[start]):
            start -= 1
        end = start + 1
        while end < len(lines) and not re.match(r"^\s*\[", lines[end]):
            end += 1
        block = lines[start:end]
        if not any(re.match(r"^\s*type\s*=\s*HitDef\b", x, re.I) for x in block):
            continue
        replacements = {
            "damage": row.get("recommended_damage", ""),
            "pausetime": row.get("recommended_pausetime", ""),
            "ground.velocity": row.get("recommended_ground_velocity", ""),
            "air.velocity": row.get("recommended_air_velocity", ""),
        }
        present = set()
        for j, line in enumerate(block):
            m = re.match(r"^(\s*)([^;=]+?)(\s*=\s*)(.*?)(\s*(?:;.*)?)$", line)
            if not m:
                continue
            key = m.group(2).strip().lower()
            for wanted, val in replacements.items():
                if key == wanted.lower() and str(val).strip():
                    block[j] = f"{m.group(1)}{m.group(2).strip()}{m.group(3)}{val}{m.group(5)}"
                    present.add(wanted)
        insert_at = len(block)
        for wanted, val in replacements.items():
            if wanted not in present and str(val).strip():
                block.insert(insert_at, f"{wanted} = {val}")
                insert_at += 1
        lines[start:end] = block
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def build_gap_closer_bundle(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("Gap Closer Bundle")
    base = _gap_dir(root)
    out = base / f"gap_closer_bundle_{_now()}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        if base.exists():
            for p in sorted(base.rglob("*"), key=lambda x: str(x).lower()):
                if p.is_file() and p != out:
                    zf.write(p, p.relative_to(root))
    res.add_created(root, out)
    return res


def run_gap_closer_pass(root: Path) -> GapCloserResult:
    root = Path(root)
    res = GapCloserResult("One-Click Gap Closer Pass")
    for label, func in [
        ("dashboard", write_gap_closer_dashboard),
        ("engine probe", probe_engine_profile),
        ("source runtime model", build_source_runtime_model),
        ("engine scenario dry run", lambda r: build_engine_scenario_sessions(r, dry_run=True)),
        ("readiness gate", build_engine_backed_readiness_gate),
        ("corpus lab", build_sff_snd_corpus_lab),
        ("unknown binary triage", write_unknown_binary_triage),
        ("binary commit sheet", export_binary_commit_sheet),
        ("generated code tuning", export_generated_code_tuning_lab),
    ]:
        try:
            res.merge(func(root), label)
        except Exception as exc:
            res.add_warning(f"{label} failed: {exc}")
    try:
        res.merge(build_gap_closer_bundle(root), "bundle")
    except Exception as exc:
        res.add_warning(f"bundle failed: {exc}")
    return res
