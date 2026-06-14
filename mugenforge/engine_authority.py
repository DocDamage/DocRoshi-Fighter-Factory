from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from hashlib import sha256
import csv
import html
import json
import re
import shutil
import struct
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import rel_path as _rel, write_csv_artifact, write_json_artifact, write_text_artifact
from .parsers import parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd

try:  # v5.5+ module
    from .sff2_codec import read_sff2, export_sff2_sprites, write_sff2_report
except Exception:  # pragma: no cover - keeps older package compatibility if module is absent
    read_sff2 = None  # type: ignore
    export_sff2_sprites = None  # type: ignore
    write_sff2_report = None  # type: ignore

ENGINE_AUTHORITY_VERSION = "7.0.0"
CODE_EXTS = {".cmd", ".cns", ".st"}
BINARY_EXTS = {".sff", ".snd"}
EVIDENCE_EXTS = {".txt", ".log", ".json", ".csv", ".md"}


from .shared_utils import (
    BaseResult,
    uniq,
    rel_path,
    timestamp,
    parse_first_int,
    get_code_files,
    discover_project_files,
)
from .artifact_io import sha256_file as _hash_file

ENGINE_AUTHORITY_VERSION = "7.0.0"
CODE_EXTS = {".cmd", ".cns", ".st"}
BINARY_EXTS = {".sff", ".snd"}
EVIDENCE_EXTS = {".txt", ".log", ".json", ".csv", ".md"}


@dataclass
class AuthorityResult(BaseResult):
    title: str = "Engine Authority"


_uniq = uniq
_now = timestamp
_rel = rel_path
_parse_int = parse_first_int


def _auth_dir(root: Path) -> Path:
    out = Path(root) / "engine_authority"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, res: Optional[AuthorityResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_text_artifact(
        path,
        text,
        res,
        root,
        changed,
        track_existing=True,
        writer=write_text_safely,
    )


def _write_json(path: Path, payload: object, res: Optional[AuthorityResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, payload, res, root, changed, track_existing=True)


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[AuthorityResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_csv_artifact(path, rows, fields, res, root, changed, track_existing=True)


def _read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _main_def(root: Path) -> Optional[Path]:
    return discover_project_files(root).get('def')


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
    return discover_project_files(root)


def _code_files(root: Path) -> List[Path]:
    return get_code_files(root)


def _all_air_actions(root: Path) -> Dict[int, object]:
    air = discover_project_files(root).get("air")
    if not air or not air.exists():
        return {}
    try:
        return {a.number: a for a in parse_air(read_text_safely(air))}
    except Exception:
        return {}



def _trigger_summary(values: Dict[str, str]) -> str:
    parts = []
    for key, value in sorted(values.items()):
        if key.lower().startswith("trigger"):
            parts.append(f"{key}={value}")
    return " ; ".join(parts)


def _anim_elem_from_trigger(text: str) -> Optional[int]:
    m = re.search(r"\bAnimElem\s*=\s*(-?\d+)", text, re.I)
    return int(m.group(1)) if m else None


def _time_from_trigger(text: str) -> Optional[int]:
    m = re.search(r"\bTime\s*=\s*(-?\d+)", text, re.I)
    return int(m.group(1)) if m else None


def _state_and_controller_rows(root: Path) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    states: List[Dict[str, object]] = []
    events: List[Dict[str, object]] = []
    commands: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        if path.suffix.lower() == ".cmd":
            for c in scan.commands:
                commands.append({
                    "file": _rel(root, path), "line": c.line, "name": c.name, "command": c.command,
                    "time": c.time if c.time is not None else "", "buffer_time": c.buffer_time if c.buffer_time is not None else "",
                })
        for st in scan.states:
            states.append({
                "file": _rel(root, path), "line": st.line, "state": st.number,
                "type": st.values.get("type", ""), "movetype": st.values.get("movetype", ""),
                "physics": st.values.get("physics", ""), "anim": st.values.get("anim", ""),
                "ctrl": st.values.get("ctrl", ""), "controller_count": len(st.controllers),
            })
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).strip()
                triggers = _trigger_summary(ctrl.values)
                events.append({
                    "file": _rel(root, path), "line": ctrl.line, "state": st.number,
                    "controller": stype, "header": ctrl.header,
                    "trigger_summary": triggers,
                    "anim_elem": _anim_elem_from_trigger(triggers) or "",
                    "time": _time_from_trigger(triggers) if _time_from_trigger(triggers) is not None else "",
                    "value": ctrl.values.get("value", ""),
                    "damage": ctrl.values.get("damage", ""),
                    "sound": ctrl.values.get("value", "") if stype.lower() == "playsnd" else "",
                    "target_state": ctrl.values.get("value", "") if stype.lower() in {"changestate", "selfstate"} else "",
                    "supported_mirror": "yes" if stype.lower() in {"hitdef", "playsnd", "changestate", "selfstate", "velset", "posset", "changeanim", "helper", "projectile", "explod", "assertspecial"} else "partial",
                })
    return states, events, commands


def build_supported_runtime_model(root: Path) -> AuthorityResult:
    """Build a source-level runtime mirror for common StateDef/AIR/controller timing.

    This is not a full M.U.G.E.N engine. It creates a deterministic model of supported
    source constructs so static reports can be compared against real runtime evidence.
    """
    root = Path(root)
    res = AuthorityResult("Supported Runtime Model")
    out = _auth_dir(root) / "supported_runtime_model"
    out.mkdir(parents=True, exist_ok=True)
    actions = _all_air_actions(root)
    states, events, commands = _state_and_controller_rows(root)

    action_rows: List[Dict[str, object]] = []
    for action_no, action in sorted(actions.items()):
        t = 0
        for idx, frame in enumerate(action.frames, start=1):
            clsn1 = sum(1 for b in frame.clsn if str(b.kind).lower() == "clsn1")
            clsn2 = sum(1 for b in frame.clsn if str(b.kind).lower() == "clsn2")
            action_rows.append({
                "action": action_no,
                "label": getattr(action, "label", ""),
                "frame": idx,
                "start_tick": t,
                "duration_ticks": frame.ticks,
                "end_tick": t + max(0, frame.ticks),
                "group": frame.group,
                "image": frame.image,
                "x": frame.x,
                "y": frame.y,
                "flags": frame.flags,
                "clsn1_boxes": clsn1,
                "clsn2_boxes": clsn2,
                "active": "yes" if clsn1 else "no",
                "body": "yes" if clsn2 else "no",
            })
            t += max(0, frame.ticks)

    state_timelines: List[Dict[str, object]] = []
    state_by_num = {int(s["state"]): s for s in states if str(s.get("state", "")).lstrip("-").isdigit()}
    for st in states:
        state_no = int(st["state"])
        anim_no = _parse_int(st.get("anim"), state_no)
        action = actions.get(anim_no)
        total_ticks = 0
        frame_count = 0
        if action:
            frame_count = len(action.frames)
            total_ticks = sum(max(0, f.ticks) for f in action.frames)
        st_events = [e for e in events if int(e.get("state", 999999)) == state_no]
        first_exit = ""
        targets = [e.get("target_state") for e in st_events if str(e.get("controller", "")).lower() in {"changestate", "selfstate"} and e.get("target_state")]
        if targets:
            first_exit = str(targets[0])
        state_timelines.append({
            "state": state_no,
            "anim": anim_no,
            "animation_found": "yes" if action else "no",
            "frames": frame_count,
            "estimated_ticks": total_ticks,
            "controller_events": len(st_events),
            "hitdefs": sum(1 for e in st_events if str(e.get("controller", "")).lower() == "hitdef"),
            "playsnd": sum(1 for e in st_events if str(e.get("controller", "")).lower() == "playsnd"),
            "projectiles": sum(1 for e in st_events if str(e.get("controller", "")).lower() == "projectile"),
            "helpers": sum(1 for e in st_events if str(e.get("controller", "")).lower() == "helper"),
            "first_exit_target": first_exit,
            "exit_target_defined": "yes" if (first_exit and _parse_int(first_exit, -999999) in state_by_num) else ("" if not first_exit else "no"),
        })

    _write_csv(out / "air_action_timeline.csv", action_rows, [
        "action", "label", "frame", "start_tick", "duration_ticks", "end_tick", "group", "image", "x", "y", "flags", "clsn1_boxes", "clsn2_boxes", "active", "body",
    ], res, root)
    _write_csv(out / "state_controller_events.csv", events, [
        "file", "line", "state", "controller", "header", "trigger_summary", "anim_elem", "time", "value", "damage", "sound", "target_state", "supported_mirror",
    ], res, root)
    _write_csv(out / "state_runtime_timelines.csv", state_timelines, [
        "state", "anim", "animation_found", "frames", "estimated_ticks", "controller_events", "hitdefs", "playsnd", "projectiles", "helpers", "first_exit_target", "exit_target_defined",
    ], res, root)
    _write_csv(out / "command_runtime_map.csv", commands, ["file", "line", "name", "command", "time", "buffer_time"], res, root)

    payload = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "model_scope": "supported source-level runtime mirror for common StateDef/AIR/controller timing; not a full engine emulator",
        "counts": {
            "actions": len(actions), "air_frames": len(action_rows), "states": len(states),
            "controller_events": len(events), "commands": len(commands),
        },
        "state_timelines": state_timelines,
        "warnings": [
            "Expressions, AI branches, helper recursion, physics, yacc-like trigger evaluation, engine bugs, and renderer differences require real engine evidence.",
            "Use Runtime Evidence Certification to reconcile this model with actual M.U.G.E.N/IKEMEN sessions.",
        ],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(out / "supported_runtime_model.json", payload, res, root)
    html_rows = "\n".join(
        f"<tr><td>{r['state']}</td><td>{r['anim']}</td><td>{r['animation_found']}</td><td>{r['frames']}</td><td>{r['estimated_ticks']}</td><td>{r['controller_events']}</td><td>{html.escape(str(r['first_exit_target']))}</td><td>{r['exit_target_defined']}</td></tr>"
        for r in state_timelines[:2000]
    )
    page = f"""<!doctype html><meta charset='utf-8'><title>Supported Runtime Model</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:4px 6px}}th{{background:#eee}}</style>
<h1>Supported Runtime Model</h1>
<p>This is a source-level mirror for common StateDef/AIR/controller timing. It is designed for comparison with real engine evidence.</p>
<p>Actions: {len(actions)} · States: {len(states)} · Controller events: {len(events)} · Commands: {len(commands)}</p>
<table><tr><th>State</th><th>Anim</th><th>Anim found</th><th>Frames</th><th>Ticks</th><th>Events</th><th>First exit</th><th>Exit defined</th></tr>{html_rows}</table>
"""
    _write_text(out / "supported_runtime_model.html", page, res, root)
    res.add_note("Built a deterministic source-level runtime mirror for common AIR/StateDef/controller constructs.")
    if any(r["exit_target_defined"] == "no" for r in state_timelines):
        res.add_warning("Some ChangeState/SelfState targets appear undefined; see state_runtime_timelines.csv.")
    return res


def write_external_engine_validator(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("External Engine Validator")
    out = _auth_dir(root) / "external_engine_validator"
    out.mkdir(parents=True, exist_ok=True)
    runtime_dir = Path(root) / "runtime_lab"
    cfg = _read_json(runtime_dir / "runtime_config.json", {})
    profile = _read_json(runtime_dir / "engine_profiles" / "engine_profile.json", {})
    exe = ""
    work = ""
    args: List[str] = []
    if isinstance(cfg, dict):
        exe = str(cfg.get("engine_executable") or cfg.get("executable") or "")
        work = str(cfg.get("working_directory") or "")
        args = [str(x) for x in (cfg.get("arguments") or [])] if isinstance(cfg.get("arguments"), list) else []
    if not exe and isinstance(profile, dict):
        engine = profile.get("engine") if isinstance(profile.get("engine"), dict) else {}
        exe = str(engine.get("executable") or "")
        work = str(engine.get("working_directory") or "")
    exe_path = Path(exe).expanduser() if exe else None
    work_path = Path(work).expanduser() if work else None
    checks = [
        {"check": "runtime_config_present", "status": "pass" if (runtime_dir / "runtime_config.json").exists() else "fail", "detail": str(runtime_dir / "runtime_config.json")},
        {"check": "engine_executable_configured", "status": "pass" if exe else "fail", "detail": exe},
        {"check": "engine_executable_exists", "status": "pass" if exe_path and exe_path.exists() else "fail", "detail": str(exe_path or "")},
        {"check": "working_directory_exists", "status": "pass" if (not work_path or work_path.exists()) else "fail", "detail": str(work_path or "")},
        {"check": "project_def_found", "status": "pass" if _main_def(root) else "fail", "detail": str(_main_def(root) or "")},
        {"check": "scenario_sheet_found", "status": "pass" if (runtime_dir / "scenario_suite" / "runtime_scenarios.csv").exists() else "warn", "detail": str(runtime_dir / "scenario_suite" / "runtime_scenarios.csv")},
    ]
    cmd = [exe] + args if exe else []
    payload = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "cmd": cmd,
        "working_directory": work,
        "checks": checks,
        "status": "ready-to-launch" if all(c["status"] == "pass" for c in checks[:5]) else "needs-configuration",
        "note": "This validates local launch configuration before running the external engine. It does not bundle or modify M.U.G.E.N/IKEMEN.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(out / "external_engine_validation.json", payload, res, root, changed=True)
    _write_csv(out / "external_engine_validation.csv", checks, ["check", "status", "detail"], res, root, changed=True)
    script_lines = [
        "# Runtime launch validation command", "", f"Status: **{payload['status']}**", "", "## Command", "", "```text", " ".join(cmd) if cmd else "[engine executable not configured]", "```", "", "## Checks", "",
    ]
    for c in checks:
        script_lines.append(f"- {c['status'].upper()}: {c['check']} — {c['detail']}")
    _write_text(out / "EXTERNAL_ENGINE_VALIDATION.md", "\n".join(script_lines), res, root, changed=True)
    res.add_note("Validated the configured external engine profile and wrote launch readiness artifacts.")
    if payload["status"] != "ready-to-launch":
        res.add_warning("External engine profile is not fully launch-ready; configure runtime_lab/runtime_config.json.")
    return res


def _find_evidence_files(root: Path) -> List[Path]:
    dirs = [
        Path(root) / "runtime_lab" / "evidence_inbox",
        Path(root) / "runtime_lab" / "evidence_reports",
        Path(root) / "runtime_lab" / "logs",
        Path(root) / "runtime_lab" / "logs_inbox",
        Path(root) / "runtime_lab" / "sessions",
        Path(root) / "release" / "screenshots",
        Path(root) / "testing",
    ]
    files: List[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_file() and p.suffix.lower() in EVIDENCE_EXTS:
                files.append(p)
    return files


def write_runtime_evidence_certificate(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Runtime Evidence Certificate")
    out = _auth_dir(root) / "runtime_evidence_certificate"
    out.mkdir(parents=True, exist_ok=True)
    scenario_path = root / "runtime_lab" / "scenario_suite" / "runtime_scenarios.csv"
    scenario_counts: Dict[str, int] = {}
    critical_failures = 0
    critical_blocked = 0
    if scenario_path.exists():
        try:
            with scenario_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    status = str(row.get("status") or "untested").strip().lower() or "untested"
                    scenario_counts[status] = scenario_counts.get(status, 0) + 1
                    priority = str(row.get("priority") or "").lower()
                    if priority == "critical" and status == "fail":
                        critical_failures += 1
                    if priority == "critical" and status == "blocked":
                        critical_blocked += 1
        except Exception as exc:
            res.add_warning(f"Could not read scenario status sheet: {exc}")
    evidence_files = _find_evidence_files(root)
    evidence_rows: List[Dict[str, object]] = []
    severity_counts: Dict[str, int] = {"fatal": 0, "error": 0, "warning": 0, "info": 0}
    patterns = [
        ("fatal", re.compile(r"\b(fatal|exception|traceback|segmentation|access violation)\b", re.I)),
        ("error", re.compile(r"\b(error|failed|missing|invalid|cannot open|not found)\b", re.I)),
        ("warning", re.compile(r"\b(warn|deprecated|fallback|unsupported)\b", re.I)),
        ("info", re.compile(r"\b(MFRT|state=|anim=|runtime|launch|screenshot|pass)\b", re.I)),
    ]
    for p in evidence_files:
        try:
            data = p.read_bytes()
            text = data[:250000].decode("utf-8", errors="replace")
            severities = []
            for sev, rx in patterns:
                hits = len(rx.findall(text))
                if hits:
                    severity_counts[sev] = severity_counts.get(sev, 0) + hits
                    severities.append(f"{sev}:{hits}")
            evidence_rows.append({
                "file": _rel(root, p),
                "bytes": len(data),
                "sha256": sha256(data).hexdigest(),
                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "markers": "; ".join(severities),
            })
        except Exception as exc:
            evidence_rows.append({"file": _rel(root, p), "bytes": "", "sha256": "", "modified": "", "markers": f"read error: {exc}"})
    total = sum(scenario_counts.values())
    passed = scenario_counts.get("pass", 0)
    failed = scenario_counts.get("fail", 0)
    blocked = scenario_counts.get("blocked", 0)
    tested = passed + failed + blocked + scenario_counts.get("skipped", 0)
    coverage = (tested / total) if total else 0.0
    evidence_ok = bool(evidence_rows)
    errors = severity_counts.get("fatal", 0) + severity_counts.get("error", 0)
    status = "certified-with-imported-engine-evidence"
    if not evidence_ok:
        status = "not-certified-no-evidence"
    elif total == 0:
        status = "not-certified-no-scenarios"
    elif critical_failures or critical_blocked or failed:
        status = "not-certified-runtime-failures"
    elif coverage < 0.5:
        status = "provisional-low-coverage"
    elif errors:
        status = "provisional-log-errors-present"
    payload = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "status": status,
        "scenario_counts": scenario_counts,
        "scenario_coverage": round(coverage, 4),
        "critical_failures": critical_failures,
        "critical_blocked": critical_blocked,
        "severity_counts": severity_counts,
        "evidence_file_count": len(evidence_rows),
        "evidence_files": evidence_rows,
        "note": "Certification is local/evidence-based. It means the configured evidence set passed MugenForge checks; it is not an official M.U.G.E.N/IKEMEN guarantee.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(out / "runtime_evidence_certificate.json", payload, res, root, changed=True)
    _write_csv(out / "runtime_evidence_index.csv", evidence_rows, ["file", "bytes", "sha256", "modified", "markers"], res, root, changed=True)
    md = [
        "# Runtime Evidence Certificate", "", f"Status: **{status}**", "",
        "This certificate is generated from local engine logs/evidence and scenario statuses. It is stronger than a static report, but it is still tied to the evidence that was imported.", "",
        "## Scenario counts", "",
    ]
    md += [f"- {k}: {v}" for k, v in sorted(scenario_counts.items())] or ["- No scenario sheet found."]
    md += ["", "## Evidence", "", f"- Evidence files indexed: {len(evidence_rows)}", f"- Severity markers: {severity_counts}", ""]
    md += ["## Next action", ""]
    if status.startswith("certified"):
        md.append("No blocking runtime issues were detected in the imported evidence set.")
    else:
        md.append("Add real engine evidence, mark scenarios pass/fail, and rerun this certificate.")
    _write_text(out / "RUNTIME_EVIDENCE_CERTIFICATE.md", "\n".join(md), res, root, changed=True)
    res.add_note(f"Runtime evidence status: {status}.")
    if not status.startswith("certified"):
        res.add_warning("Runtime certificate is not fully certified; see RUNTIME_EVIDENCE_CERTIFICATE.md.")
    return res


def write_binary_corpus_validator(root: Path, corpus_dir: Optional[Path] = None) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Binary Corpus Validator")
    out = _auth_dir(root) / "binary_corpus_validator"
    out.mkdir(parents=True, exist_ok=True)
    corpus = Path(corpus_dir) if corpus_dir else root / "binary_corpus"
    rows: List[Dict[str, object]] = []
    candidates: List[Path] = []
    if corpus.exists():
        candidates.extend(p for p in sorted(corpus.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in BINARY_EXTS)
    # Always include the active project binaries so the validator is useful before the user adds a corpus.
    for key in ("sff", "snd"):
        p = _project_files(root).get(key)
        if p and p.exists() and p not in candidates:
            candidates.append(p)
    for p in candidates:
        row: Dict[str, object] = {
            "file": _rel(root, p), "kind": p.suffix.lower(), "bytes": p.stat().st_size, "sha256": _hash_file(p),
            "parser": "", "status": "", "records": "", "warnings": "", "export_test": "not-run",
        }
        if p.suffix.lower() == ".sff":
            try:
                info = read_sff(p)
                row.update({"parser": info.variant, "status": "pass" if info.sprites or info.variant.startswith("sff2") else "warn", "records": len(info.sprites), "warnings": " | ".join(info.warnings[:8])})
                if read_sff2 is not None:
                    try:
                        s2 = read_sff2(p)  # type: ignore[misc]
                        if s2.sprites:
                            row["parser"] = f"{row['parser']}+sff2_codec"
                            row["records"] = len(s2.sprites)
                            export_dir = out / "exports" / p.stem
                            if export_sff2_sprites is not None:
                                exported, warns = export_sff2_sprites(p, export_dir, max_count=25)  # type: ignore[misc]
                                row["export_test"] = f"exported {len(exported)} preview sprites"
                                if warns:
                                    row["warnings"] = (str(row["warnings"]) + " | " + " | ".join(warns[:5])).strip(" |")
                    except Exception as exc:
                        row["warnings"] = (str(row["warnings"]) + f" | sff2 parse/export: {exc}").strip(" |")
            except Exception as exc:
                row.update({"parser": "sff", "status": "fail", "warnings": str(exc)})
        elif p.suffix.lower() == ".snd":
            try:
                info = read_snd(p)
                row.update({"parser": "snd", "status": "pass" if info.sounds else "warn", "records": len(info.sounds), "warnings": " | ".join(info.warnings[:8])})
            except Exception as exc:
                row.update({"parser": "snd", "status": "fail", "warnings": str(exc)})
        rows.append(row)
    _write_csv(out / "binary_corpus_validation.csv", rows, ["file", "kind", "bytes", "sha256", "parser", "status", "records", "warnings", "export_test"], res, root, changed=True)
    summary = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "corpus_dir": str(corpus),
        "files_tested": len(rows),
        "status_counts": {k: sum(1 for r in rows if r.get("status") == k) for k in sorted({str(r.get("status")) for r in rows})},
        "note": "This closes the validation workflow gap: add real-world SFF/SND files under binary_corpus/ and rerun to grow compatibility evidence.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(out / "binary_corpus_validation_summary.json", summary, res, root, changed=True)
    md = ["# Binary Corpus Validator", "", f"Files tested: **{len(rows)}**", "", f"Corpus folder: `{corpus}`", "", "Put third-party test files in `binary_corpus/` and rerun this tool to expand compatibility evidence.", "", "## Status counts", ""]
    for k, v in summary["status_counts"].items():
        md.append(f"- {k}: {v}")
    _write_text(out / "BINARY_CORPUS_VALIDATION.md", "\n".join(md), res, root, changed=True)
    if not corpus.exists() or not any(p for p in candidates if corpus in p.parents):
        res.add_warning("No external binary_corpus/ files were found; validator tested only active project binaries.")
    else:
        res.add_note(f"Validated {len(rows)} binary files across project/corpus inputs.")
    return res


def _find_png_spans(data: bytes) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    sig = b"\x89PNG\r\n\x1a\n"
    pos = 0
    while True:
        start = data.find(sig, pos)
        if start < 0:
            break
        iend = data.find(b"IEND", start + 8)
        if iend >= 0 and iend + 8 <= len(data):
            spans.append((start, iend + 8))
            pos = iend + 8
        else:
            spans.append((start, min(len(data), start + 32)))
            pos = start + 8
    return spans


def _find_pcx_offsets(data: bytes) -> List[int]:
    hits: List[int] = []
    for i in range(0, max(0, len(data) - 4)):
        if data[i] == 0x0A and data[i + 1] in {0, 2, 3, 5} and data[i + 2] == 1 and data[i + 3] in {1, 2, 4, 8}:
            hits.append(i)
            if len(hits) >= 5000:
                break
    return hits


def write_sff2_forensic_recovery(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("SFF2 Forensic Recovery")
    out = _auth_dir(root) / "sff2_forensic_recovery"
    out.mkdir(parents=True, exist_ok=True)
    sff = _project_files(root).get("sff")
    if not sff or not sff.exists():
        res.add_warning("No active SFF file found for forensic recovery.")
        return res
    data = sff.read_bytes()
    rows: List[Dict[str, object]] = []
    for start, end in _find_png_spans(data):
        rows.append({"kind": "embedded_png", "offset": start, "length": end - start, "confidence": "high", "note": "PNG signature/IEND span"})
    for off in _find_pcx_offsets(data):
        rows.append({"kind": "pcx_header_candidate", "offset": off, "length": "", "confidence": "medium", "note": "PCX-like header bytes"})
    for off in range(0, max(0, len(data) - 2)):
        if data[off] == 0x78 and data[off + 1] in {0x01, 0x5E, 0x9C, 0xDA}:
            rows.append({"kind": "zlib_candidate", "offset": off, "length": "", "confidence": "low", "note": "zlib-like header"})
            if sum(1 for r in rows if r["kind"] == "zlib_candidate") >= 200:
                break
    # Candidate table windows: look for repeated 28-byte rows with plausible group/image/width/height/data offsets.
    table_rows: List[Dict[str, object]] = []
    for base in range(16, min(len(data), 4096), 4):
        plausible = 0
        sample: List[str] = []
        for idx in range(0, 12):
            off = base + idx * 28
            if off + 28 > len(data):
                break
            try:
                g, i, w, h, ax, ay, link = struct.unpack_from("<HHHHhhH", data, off)
                rel = struct.unpack_from("<I", data, off + 16)[0]
                ln = struct.unpack_from("<I", data, off + 20)[0]
                fmt = data[off + 14]
                if 0 <= g <= 9999 and 0 <= i <= 9999 and 0 <= w <= 4096 and 0 <= h <= 4096 and fmt in {0, 1, 2, 3, 4, 10, 11, 12} and ln < len(data) and rel < len(data):
                    plausible += 1
                    sample.append(f"{g},{i} {w}x{h} fmt={fmt} rel={rel} len={ln}")
            except Exception:
                pass
        if plausible >= 4:
            table_rows.append({"candidate_table_offset": base, "plausible_rows": plausible, "sample": " | ".join(sample[:4])})
    _write_csv(out / "forensic_payload_candidates.csv", rows, ["kind", "offset", "length", "confidence", "note"], res, root, changed=True)
    _write_csv(out / "forensic_table_candidates.csv", table_rows, ["candidate_table_offset", "plausible_rows", "sample"], res, root, changed=True)
    # Export embedded PNGs directly for recovery review.
    export_dir = out / "carved_assets"
    export_dir.mkdir(parents=True, exist_ok=True)
    carved: List[Path] = []
    for idx, (start, end) in enumerate(_find_png_spans(data)[:1000]):
        p = export_dir / f"embedded_png_{idx:05d}_off{start:X}.png"
        p.write_bytes(data[start:end])
        carved.append(p)
    payload = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "source_sff": str(sff),
        "file_size": len(data),
        "payload_candidates": len(rows),
        "table_candidates": len(table_rows),
        "carved_pngs": len(carved),
        "note": "Forensic recovery reduces manual review by carving recognizable payloads and table candidates. Encrypted or custom-obfuscated data still needs a key/tool-specific decoder.",
    }
    _write_json(out / "sff2_forensic_recovery.json", payload, res, root, changed=True)
    md = ["# SFF2 Forensic Recovery", "", f"Source: `{sff}`", f"Payload candidates: **{len(rows)}**", f"Table candidates: **{len(table_rows)}**", f"Carved PNGs: **{len(carved)}**", "", "Use these artifacts when normal SFF2 parsing fails. This is safer than guessing binary writes."]
    _write_text(out / "SFF2_FORENSIC_RECOVERY.md", "\n".join(md), res, root, changed=True)
    res.add_note("Wrote SFF2 forensic payload/table candidate reports and carved recognizable PNG payloads.")
    if not rows and not table_rows:
        res.add_warning("No forensic candidates were found in the active SFF.")
    return res


def export_binary_promotion_sheet(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Binary Promotion Sheet")
    out = _auth_dir(root) / "binary_promotion"
    out.mkdir(parents=True, exist_ok=True)
    active = _project_files(root)
    candidates: List[Path] = []
    for base in [root / "binary_core", root / "binary_deep", root / "binary_maturity", root / "engine_authority"]:
        if base.exists():
            candidates.extend(p for p in sorted(base.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in BINARY_EXTS)
    rows: List[Dict[str, object]] = []
    seen = set()
    for p in candidates:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        kind = p.suffix.lower().lstrip(".")
        target = active.get(kind)
        rows.append({
            "enabled": "no",
            "candidate_file": _rel(root, p),
            "target_kind": kind,
            "target_file": _rel(root, target) if target else f"{root.name}.{kind}",
            "candidate_bytes": p.stat().st_size,
            "candidate_sha256": _hash_file(p),
            "validation_required": "yes",
            "notes": "Set enabled=yes only after reviewing parser reports and testing candidate in target engine.",
        })
    _write_csv(out / "binary_promotion_sheet.csv", rows, ["enabled", "candidate_file", "target_kind", "target_file", "candidate_bytes", "candidate_sha256", "validation_required", "notes"], res, root, changed=True)
    _write_text(out / "BINARY_PROMOTION_README.md", "# Binary Promotion\n\nThis sheet promotes reviewed SFF/SND candidates into the active project with backups and manifest logging. It avoids blind overwrites while providing a real apply path.\n", res, root, changed=True)
    res.add_note(f"Exported {len(rows)} candidate rows for guarded SFF/SND promotion.")
    if not rows:
        res.add_warning("No binary candidate files were found under binary_* or engine_authority outputs.")
    return res


def apply_verified_binary_promotions(root: Path, sheet_path: Optional[Path] = None) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Apply Verified Binary Promotions")
    sheet = Path(sheet_path) if sheet_path else _auth_dir(root) / "binary_promotion" / "binary_promotion_sheet.csv"
    if not sheet.exists():
        res.merge(export_binary_promotion_sheet(root), "sheet")
    if not sheet.exists():
        res.add_warning("Promotion sheet was not found or could not be created.")
        return res
    active = _project_files(root)
    applied: List[Dict[str, object]] = []
    with sheet.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("enabled", "")).strip().lower() not in {"yes", "true", "1", "apply"}:
                continue
            candidate = (root / str(row.get("candidate_file") or "")).resolve()
            kind = str(row.get("target_kind") or candidate.suffix.lower().lstrip(".")).lower().strip()
            if kind not in {"sff", "snd"}:
                res.add_warning(f"Skipped unsupported promotion kind: {kind}")
                continue
            if not candidate.exists():
                res.add_warning(f"Candidate does not exist: {candidate}")
                continue
            # Verify candidate parses before promotion.
            verify_status = ""
            try:
                if kind == "sff":
                    info = read_sff(candidate)
                    verify_status = f"sff parser={info.variant} sprites={len(info.sprites)} warnings={len(info.warnings)}"
                    if not (info.sprites or info.variant.startswith("sff2")):
                        res.add_warning(f"SFF candidate did not parse strongly; skipped: {candidate}")
                        continue
                else:
                    info = read_snd(candidate)
                    verify_status = f"snd sounds={len(info.sounds)} warnings={len(info.warnings)}"
                    if not info.sounds:
                        res.add_warning(f"SND candidate did not expose any sounds; skipped: {candidate}")
                        continue
            except Exception as exc:
                res.add_warning(f"Candidate verification failed for {candidate}: {exc}")
                continue
            target = active.get(kind)
            if not target:
                target = root / f"{root.name}.{kind}"
            backup = None
            if target.exists():
                backup = target.with_name(target.name + f".bak_engine_authority_{_now()}")
                shutil.copy2(target, backup)
                res.add_created(root, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, target)
            res.add_changed(root, target)
            applied.append({
                "candidate": _rel(root, candidate), "target": _rel(root, target), "backup": _rel(root, backup) if backup else "",
                "kind": kind, "candidate_sha256": _hash_file(candidate), "target_sha256": _hash_file(target), "verify_status": verify_status,
                "applied_at": datetime.now().isoformat(timespec="seconds"),
            })
    out = _auth_dir(root) / "binary_promotion"
    if applied:
        _write_csv(out / f"binary_promotion_apply_log_{_now()}.csv", applied, ["candidate", "target", "backup", "kind", "candidate_sha256", "target_sha256", "verify_status", "applied_at"], res, root)
        _write_json(out / "last_binary_promotion_apply.json", {"applied": applied}, res, root, changed=True)
        res.add_note(f"Promoted {len(applied)} verified binary candidate(s) with backups.")
    else:
        res.add_warning("No rows were enabled or no candidates passed verification.")
    return res


def write_gameplay_closure_pack(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Gameplay Closure Pack")
    out = _auth_dir(root) / "gameplay_closure"
    out.mkdir(parents=True, exist_ok=True)
    states, events, commands = _state_and_controller_rows(root)
    actions = _all_air_actions(root)
    problems: List[Dict[str, object]] = []
    state_nums = {int(s["state"]) for s in states if str(s.get("state", "")).lstrip("-").isdigit()}
    action_nums = set(actions.keys())
    for st in states:
        state_no = int(st["state"])
        anim_no = _parse_int(st.get("anim"), state_no)
        if anim_no not in action_nums:
            problems.append({"severity": "error", "kind": "missing_anim", "state": state_no, "detail": f"StateDef {state_no} references anim {anim_no}, which was not found in AIR.", "suggested_fix": "Create AIR action or update StateDef anim."})
    for e in events:
        controller = str(e.get("controller", "")).lower()
        if controller in {"changestate", "selfstate"} and str(e.get("target_state", "")).strip():
            val = str(e.get("target_state", "")).strip()
            if re.fullmatch(r"-?\d+", val) and int(val) not in state_nums:
                problems.append({"severity": "error", "kind": "missing_state_target", "state": e.get("state"), "detail": f"{controller} targets missing StateDef {val} at {e.get('file')}:{e.get('line')}", "suggested_fix": "Create target StateDef or retarget the transition."})
        if controller == "hitdef" and not e.get("damage"):
            problems.append({"severity": "warning", "kind": "hitdef_no_damage", "state": e.get("state"), "detail": f"HitDef has no damage field at {e.get('file')}:{e.get('line')}", "suggested_fix": "Add/tune damage via HitDef sheet."})
        if controller == "playsnd" and not e.get("sound"):
            problems.append({"severity": "warning", "kind": "playsnd_no_value", "state": e.get("state"), "detail": f"PlaySnd has no value field at {e.get('file')}:{e.get('line')}", "suggested_fix": "Assign group,sound in Sound Cue Editor."})
    # Command coverage: command names referenced in controllers should be defined in CMD.
    defined = {str(c.get("name")) for c in commands}
    for e in events:
        for cmd in re.findall(r'command\s*=\s*"([^"]+)"', str(e.get("trigger_summary", "")), flags=re.I):
            if cmd not in defined:
                problems.append({"severity": "warning", "kind": "missing_command_def", "state": e.get("state"), "detail": f"Controller references command '{cmd}' but no [Command] definition was found.", "suggested_fix": "Add command in CMD or retarget trigger."})
    _write_csv(out / "gameplay_closure_findings.csv", problems, ["severity", "kind", "state", "detail", "suggested_fix"], res, root, changed=True)
    patch_rows = []
    for idx, p in enumerate(problems, start=1):
        patch_rows.append({
            "enabled": "no", "finding_id": f"GCF-{idx:04d}", "kind": p.get("kind"), "state": p.get("state"),
            "safe_patch_available": "manual" if p.get("kind") in {"missing_anim", "missing_state_target", "missing_command_def"} else "sheet",
            "suggested_fix": p.get("suggested_fix"),
            "notes": p.get("detail"),
        })
    _write_csv(out / "gameplay_patch_plan.csv", patch_rows, ["enabled", "finding_id", "kind", "state", "safe_patch_available", "suggested_fix", "notes"], res, root, changed=True)
    payload = {
        "tool": "MugenForge Engine Authority",
        "version": ENGINE_AUTHORITY_VERSION,
        "findings": len(problems),
        "severity_counts": {k: sum(1 for p in problems if p.get("severity") == k) for k in sorted({str(p.get("severity")) for p in problems})},
        "note": "This narrows the starter-code gap by mapping source problems to explicit fixes and runtime scenarios. It still expects real playtesting for feel/balance.",
    }
    _write_json(out / "gameplay_closure_summary.json", payload, res, root, changed=True)
    md = ["# Gameplay Closure Pack", "", f"Findings: **{len(problems)}**", "", "This pack moves generated gameplay from loose starter scaffolding toward verified source/runtime tasks. Use the CSV patch plan plus Runtime Evidence Certificate before release.", ""]
    for p in problems[:80]:
        md.append(f"- **{p['severity']}** `{p['kind']}` state {p.get('state')}: {p['detail']}")
    if len(problems) > 80:
        md.append(f"- ... {len(problems)-80} more in CSV")
    _write_text(out / "GAMEPLAY_CLOSURE_PACK.md", "\n".join(md), res, root, changed=True)
    if problems:
        res.add_warning(f"Gameplay closure found {len(problems)} source issues/tasks.")
    else:
        res.add_note("No obvious source wiring problems were found by the gameplay closure scan.")
    return res


def write_static_runtime_reconciler(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Static/Runtime Reconciler")
    out = _auth_dir(root) / "static_runtime_reconciler"
    out.mkdir(parents=True, exist_ok=True)
    model_path = _auth_dir(root) / "supported_runtime_model" / "supported_runtime_model.json"
    if not model_path.exists():
        res.merge(build_supported_runtime_model(root), "model")
    model = _read_json(model_path, {})
    states = []
    if isinstance(model, dict) and isinstance(model.get("state_timelines"), list):
        states = [s for s in model["state_timelines"] if isinstance(s, dict)]
    evidence_files = _find_evidence_files(root)
    evidence_text = ""
    for p in evidence_files[:200]:
        try:
            evidence_text += "\n" + p.read_text(encoding="utf-8", errors="replace")[:200000]
        except Exception:
            pass
    rows: List[Dict[str, object]] = []
    for st in states:
        state_no = str(st.get("state"))
        anim_no = str(st.get("anim"))
        state_seen = bool(re.search(rf"\b(state|stateno)\s*=\s*{re.escape(state_no)}\b|\bstate\s+{re.escape(state_no)}\b", evidence_text, re.I))
        anim_seen = bool(re.search(rf"\b(anim)\s*=\s*{re.escape(anim_no)}\b|\banim\s+{re.escape(anim_no)}\b", evidence_text, re.I)) if anim_no else False
        rows.append({
            "state": state_no, "anim": anim_no, "model_ticks": st.get("estimated_ticks", ""),
            "state_seen_in_evidence": "yes" if state_seen else "no",
            "anim_seen_in_evidence": "yes" if anim_seen else "no",
            "reconciliation_status": "observed" if state_seen or anim_seen else "unobserved",
            "next_step": "Add runtime evidence for this state/anim" if not (state_seen or anim_seen) else "Review behavior/screenshots/logs",
        })
    _write_csv(out / "static_runtime_reconciliation.csv", rows, ["state", "anim", "model_ticks", "state_seen_in_evidence", "anim_seen_in_evidence", "reconciliation_status", "next_step"], res, root, changed=True)
    observed = sum(1 for r in rows if r["reconciliation_status"] == "observed")
    payload = {"tool": "MugenForge Engine Authority", "version": ENGINE_AUTHORITY_VERSION, "states_modeled": len(rows), "states_observed": observed, "evidence_files": len(evidence_files), "generated_at": datetime.now().isoformat(timespec="seconds")}
    _write_json(out / "static_runtime_reconciliation_summary.json", payload, res, root, changed=True)
    md = ["# Static / Runtime Reconciliation", "", f"Modeled states: **{len(rows)}**", f"Observed in evidence: **{observed}**", "", "This bridges static reports and runtime evidence. Add MFRT telemetry logs/screenshots/notes and rerun to improve coverage."]
    _write_text(out / "STATIC_RUNTIME_RECONCILIATION.md", "\n".join(md), res, root, changed=True)
    if not evidence_files:
        res.add_warning("No runtime evidence files were found; reconciliation marks states unobserved.")
    else:
        res.add_note(f"Reconciled {len(rows)} modeled states against {len(evidence_files)} evidence file(s).")
    return res


def write_gap_closure_dashboard(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Gap Closure Dashboard")
    out = _auth_dir(root)
    rows = [
        {"former_limitation": "MugenForge did not emulate/simulate runtime behavior", "v7_implementation": "Supported Runtime Model builds a deterministic source-level mirror for common AIR/StateDef/controller timing and reconciles it with real evidence.", "remaining_truth": "Not a full engine emulator; target engine evidence is still required for exact behavior."},
        {"former_limitation": "Runtime launcher scripts required manual review", "v7_implementation": "External Engine Validator checks configured executable, working directory, scenario sheet, and project DEF before launch.", "remaining_truth": "Engine command-line flags still vary, but bad local profiles are now caught before launch."},
        {"former_limitation": "Readiness scores were only evidence aids", "v7_implementation": "Runtime Evidence Certificate hashes evidence, reads scenario status, counts errors/fatals, and issues local certification statuses.", "remaining_truth": "Certification is local/evidence-based, not an official engine guarantee."},
        {"former_limitation": "SFF2 support needed broader corpus validation", "v7_implementation": "Binary Corpus Validator tests active and corpus SFF/SND files, attempts preview export, and records compatibility hashes.", "remaining_truth": "Coverage grows with the corpus supplied under binary_corpus/."},
        {"former_limitation": "Unknown/corrupt/tool-specific SFF2 layouts needed manual review", "v7_implementation": "SFF2 Forensic Recovery carves PNG/PCX/zlib candidates and detects plausible sprite-table windows.", "remaining_truth": "Encrypted/obfuscated files still require a key or tool-specific decoder."},
        {"former_limitation": "SFF/SND mutation was candidate-only", "v7_implementation": "Binary Promotion sheet applies verified candidates into active project files with backups and SHA-256 logs.", "remaining_truth": "Blind overwrite remains intentionally unavailable."},
        {"former_limitation": "Generated gameplay code remained starter scaffolding", "v7_implementation": "Gameplay Closure Pack maps missing anim/state/command/HitDef/sound issues to patch plans and runtime scenarios.", "remaining_truth": "Feel, balance, and matchup tuning still require real playtesting."},
        {"former_limitation": "Reports/previews were not runtime-authoritative", "v7_implementation": "Static/Runtime Reconciler compares modeled states/anims with imported runtime evidence.", "remaining_truth": "Reports become stronger as evidence coverage improves."},
    ]
    _write_csv(out / "gap_closure_matrix.csv", rows, ["former_limitation", "v7_implementation", "remaining_truth"], res, root, changed=True)
    md = ["# Engine Authority / Gap Closure Dashboard", "", f"Version: `{ENGINE_AUTHORITY_VERSION}`", "", "This release turns the honest limitations list into concrete workflows instead of hiding it.", "", "## Gap closure matrix", ""]
    for r in rows:
        md.append(f"### {r['former_limitation']}")
        md.append(f"- Implemented: {r['v7_implementation']}")
        md.append(f"- Remaining truth: {r['remaining_truth']}")
        md.append("")
    md += ["## Suggested order", "", "1. Supported Runtime Model", "2. External Engine Validator", "3. Runtime Evidence Certificate", "4. Static/Runtime Reconciler", "5. Binary Corpus Validator", "6. SFF2 Forensic Recovery", "7. Binary Promotion Sheet", "8. Gameplay Closure Pack", ""]
    _write_text(out / "ENGINE_AUTHORITY_START_HERE.md", "\n".join(md), res, root, changed=True)
    res.add_note("Wrote the v7 gap closure dashboard and matrix.")
    return res


def build_engine_authority_bundle(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("Engine Authority Bundle")
    out = _auth_dir(root)
    stamp = _now()
    zip_path = out / f"engine_authority_bundle_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(root))
    res.add_created(root, zip_path)
    res.add_note("Bundled Engine Authority reports and sheets.")
    return res


def run_engine_authority_pass(root: Path) -> AuthorityResult:
    root = Path(root)
    res = AuthorityResult("One-Click Engine Authority Pass")
    steps = [
        ("dashboard", write_gap_closure_dashboard),
        ("runtime model", build_supported_runtime_model),
        ("external engine validator", write_external_engine_validator),
        ("runtime evidence certificate", write_runtime_evidence_certificate),
        ("static/runtime reconciler", write_static_runtime_reconciler),
        ("binary corpus validator", write_binary_corpus_validator),
        ("sff2 forensic recovery", write_sff2_forensic_recovery),
        ("binary promotion sheet", export_binary_promotion_sheet),
        ("gameplay closure", write_gameplay_closure_pack),
    ]
    for label, fn in steps:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f"{label} failed: {exc}")
    try:
        res.merge(build_engine_authority_bundle(root), "bundle")
    except Exception as exc:
        res.add_warning(f"bundle failed: {exc}")
    return res
