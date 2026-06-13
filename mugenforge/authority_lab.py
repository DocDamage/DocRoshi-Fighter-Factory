from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _now,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .parsers import parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely, COMMON_ANIMS
from .move_wizard import find_character_file
from . import runtime_lab as rt_lab

AUTHORITY_LAB_VERSION = "7.0.0"
CODE_EXTS = {".cmd", ".cns", ".st"}
BINARY_EXTS = {".sff", ".snd"}
EVIDENCE_EXTS = {".txt", ".log", ".json", ".csv", ".md"}


@dataclass
class AuthorityLabResult:
    title: str = "Authority Lab"
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
        if other is None:
            return
        prefix = f"{label}: " if label else ""
        self.created_files.extend(prefix + str(x) for x in getattr(other, "created_files", []) or [])
        self.changed_files.extend(prefix + str(x) for x in getattr(other, "changed_files", []) or [])
        self.warnings.extend(prefix + str(x) for x in getattr(other, "warnings", []) or [])
        self.notes.extend(prefix + str(x) for x in getattr(other, "notes", []) or [])

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


def _auth_dir(root: Path) -> Path:
    out = Path(root) / "authority_lab"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, res: Optional[AuthorityLabResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, res, root, changed, track_existing=True, writer=write_text_safely)


def _write_json(path: Path, payload: object, res: Optional[AuthorityLabResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, payload, res, root, changed, track_existing=True)


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[AuthorityLabResult] = None, root: Optional[Path] = None) -> Path:
    return write_csv_artifact(path, rows, fields, res, root, track_existing=True)


def _read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _main_def(root: Path) -> Optional[Path]:
    exact = Path(root) / f"{Path(root).name}.def"
    if exact.exists():
        return exact
    hits = sorted(Path(root).glob("*.def"), key=lambda p: p.name.lower())
    return hits[0] if hits else None


def _def_refs(root: Path) -> Dict[str, str]:
    path = _main_def(root)
    if not path or not path.exists():
        return {}
    try:
        files = parse_def(read_text_safely(path)).get("files")
        if not files:
            return {}
        return {str(k).lower(): str(v).strip().strip('"') for k, v in files.values.items()}
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
    skip = {
        "__pycache__", "runtime_lab", "authority_lab", "binary_core", "binary_deep", "binary_maturity",
        "forge_timeline", "forge_polish", "forge_beyond", "visual_forge", "exports", "backups",
    }
    out: List[Path] = []
    for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()):
        if not p.is_file() or p.suffix.lower() not in CODE_EXTS:
            continue
        if any(part in skip or part.startswith(".") for part in p.parts):
            continue
        out.append(p)
    return out


def _all_state_defs(root: Path) -> Dict[int, List[str]]:
    defs: Dict[int, List[str]] = {}
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states:
            defs.setdefault(st.number, []).append(f"{_rel(root, p)}:{st.line}")
    return defs


def _all_change_targets(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states:
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype not in {"changestate", "selfstate"}:
                    continue
                value = str(ctrl.values.get("value", "")).strip()
                if re.fullmatch(r"-?\d+", value):
                    rows.append({
                        "file": _rel(root, p), "line": ctrl.line, "state": st.number,
                        "controller": stype, "target": int(value),
                        "trigger1": ctrl.values.get("trigger1", ""),
                        "trigger2": ctrl.values.get("trigger2", ""),
                    })
                else:
                    rows.append({
                        "file": _rel(root, p), "line": ctrl.line, "state": st.number,
                        "controller": stype, "target": value,
                        "trigger1": ctrl.values.get("trigger1", ""),
                        "trigger2": ctrl.values.get("trigger2", ""),
                    })
    return rows


def _air_actions(root: Path):
    air = _project_files(root).get("air")
    if not air or not air.exists():
        return []
    try:
        return parse_air(read_text_safely(air))
    except Exception:
        return []


def _anim_duration(actions_by_no: Dict[int, object], anim_no: int) -> int:
    action = actions_by_no.get(int(anim_no))
    if not action:
        return 0
    total = 0
    for fr in getattr(action, "frames", []) or []:
        ticks = int(getattr(fr, "ticks", 1) or 1)
        if ticks >= 0:
            total += ticks
        else:
            total += 1
    return total


def _first_int(value: object, default: int = 0) -> int:
    m = re.search(r"-?\d+", str(value or ""))
    return int(m.group(0)) if m else default


def _evidence_files(root: Path) -> List[Path]:
    dirs = [
        Path(root) / "runtime_lab" / "logs",
        Path(root) / "runtime_lab" / "logs_inbox",
        Path(root) / "runtime_lab" / "evidence_inbox",
        Path(root) / "runtime_lab" / "sessions",
        Path(root) / "authority_lab" / "engine",
        Path(root) / "authority_lab" / "release_gate",
        Path(root) / "testing",
        Path(root) / "release" / "screenshots",
        Path(root) / "screenshots",
    ]
    files: List[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_file() and p.suffix.lower() in EVIDENCE_EXTS:
                files.append(p)
    return files


# ---------------------------------------------------------------------------
# Dashboard and limitation closure map


def write_authority_dashboard(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Authority Lab Dashboard")
    out = _auth_dir(root)
    rows = [
        {
            "previous_limitation": "Editor-side reports were not engine-authoritative.",
            "v7_feature": "Evidence Authority Gate combines runtime logs, engine probe results, scenarios, evidence hashes, source simulation, and binary corpus status.",
            "status": "implemented as evidence-backed gate when runtime evidence exists",
        },
        {
            "previous_limitation": "Runtime launch scripts required manual review.",
            "v7_feature": "Engine Profile Verifier checks executable path, working directory, arguments, and optional subprocess probe output.",
            "status": "implemented",
        },
        {
            "previous_limitation": "MugenForge did not simulate runtime behavior.",
            "v7_feature": "Source Runtime Simulator follows common StateDef/AIR timing/ChangeState paths to catch loops and missing references.",
            "status": "implemented as source simulator, not engine replacement",
        },
        {
            "previous_limitation": "SFF2 support needed broader corpus validation.",
            "v7_feature": "SFF2 Corpus Validator scans project/corpus folders, fingerprints variants, decodes supported records, and reports compatibility by file/format.",
            "status": "implemented infrastructure; corpus coverage depends on files supplied",
        },
        {
            "previous_limitation": "Unknown/corrupt/tool-specific SFF2 layouts needed manual review.",
            "v7_feature": "Unknown SFF2 fingerprinting records header dwords, signatures, entropy, embedded PNG/PCX/zlib hints, and parser reason.",
            "status": "implemented triage, not magic recovery for encrypted/corrupt bytes",
        },
        {
            "previous_limitation": "Binary mutation was candidate/backup-first only.",
            "v7_feature": "Verified Binary Commit Sheet promotes chosen candidate SFF/SND files to live DEF-referenced files after SHA verification and automatic backup.",
            "status": "implemented deliberate commit; blind overwrite still blocked",
        },
        {
            "previous_limitation": "Generated gameplay code needed real playtesting/tuning.",
            "v7_feature": "Gameplay Tuning Workbench exports move/HitDef/command/scenario sheets tied to runtime evidence and source simulation findings.",
            "status": "implemented workflow; real playtesting remains required for feel",
        },
    ]
    _write_csv(out / "limitation_closure_map.csv", rows, ["previous_limitation", "v7_feature", "status"], res, root)
    md = [
        "# Authority Lab v7.0",
        "",
        "Authority Lab turns the previous honest-limitations list into concrete workflows:",
        "",
    ]
    for row in rows:
        md += [f"## {row['previous_limitation']}", "", f"**Implemented:** {row['v7_feature']}", "", f"**Status:** {row['status']}", ""]
    md += [
        "## Remaining truth",
        "",
        "No editor can make subjective move feel, balance, or player-fun decisions without playtesting. Authority Lab narrows the technical gaps by collecting evidence, verifying external engine setup, and making risky binary changes deliberate and reversible.",
    ]
    _write_text(out / "AUTHORITY_START_HERE.md", "\n".join(md), res, root)
    res.add_note("Mapped the honest limitations to v7 concrete workflows.")
    return res


# ---------------------------------------------------------------------------
# Engine profile verification and optional probe


def verify_engine_profile(root: Path, *, run_probe: bool = False, timeout_seconds: float = 5.0) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Engine Profile Verification")
    out = _auth_dir(root) / "engine"
    out.mkdir(parents=True, exist_ok=True)
    runtime_cfg = root / "runtime_lab" / "runtime_config.json"
    if not runtime_cfg.exists():
        res.merge(rt_lab.write_runtime_config(root), "runtime config")
    cfg = _read_json(runtime_cfg, {})
    if not isinstance(cfg, dict):
        cfg = {}
        res.add_warning("runtime_lab/runtime_config.json is not a JSON object.")
    exe_raw = str(cfg.get("engine_executable") or "").strip()
    cwd_raw = str(cfg.get("working_directory") or "").strip()
    args = [str(x) for x in (cfg.get("arguments") or [])]
    exe = Path(exe_raw) if exe_raw else None
    cwd = Path(cwd_raw) if cwd_raw else (exe.parent if exe else Path(""))
    checks = {
        "config_exists": runtime_cfg.exists(),
        "engine_executable_set": bool(exe_raw),
        "engine_executable_exists": bool(exe and exe.exists()),
        "engine_executable_is_file": bool(exe and exe.exists() and exe.is_file()),
        "working_directory_exists": bool(cwd_raw and cwd.exists()) if cwd_raw else bool(exe and exe.parent.exists()),
        "project_def_exists": bool(_project_files(root).get("def")),
        "arguments_count": len(args),
    }
    probe: Dict[str, object] = {"attempted": False}
    if run_probe:
        if not checks["engine_executable_is_file"]:
            res.add_warning("Probe requested, but engine executable is missing or not a file.")
        else:
            probe["attempted"] = True
            tag = _now()
            command = [str(exe)] + args
            try:
                proc = subprocess.run(command, cwd=str(cwd if cwd and cwd.exists() else exe.parent), capture_output=True, text=True, timeout=float(timeout_seconds))
                stdout = out / f"engine_probe_stdout_{tag}.txt"
                stderr = out / f"engine_probe_stderr_{tag}.txt"
                stdout.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
                stderr.write_text(proc.stderr or "", encoding="utf-8", errors="replace")
                res.add_created(root, stdout)
                res.add_created(root, stderr)
                probe.update({
                    "returncode": proc.returncode,
                    "timeout_seconds": timeout_seconds,
                    "command": command,
                    "cwd": str(cwd),
                    "stdout_file": _rel(root, stdout),
                    "stderr_file": _rel(root, stderr),
                })
            except subprocess.TimeoutExpired as exc:
                probe.update({"returncode": 124, "timeout": True, "timeout_seconds": timeout_seconds, "command": command, "cwd": str(cwd)})
                res.add_warning(f"Engine probe timed out after {timeout_seconds} seconds.")
            except Exception as exc:
                probe.update({"error": str(exc), "command": command, "cwd": str(cwd)})
                res.add_warning(f"Engine probe failed: {exc}")
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "runtime_config": _rel(root, runtime_cfg),
        "engine_executable": exe_raw,
        "working_directory": cwd_raw,
        "arguments": args,
        "checks": checks,
        "probe": probe,
    }
    _write_json(out / "engine_profile_verification.json", payload, res, root, changed=True)
    verdict = "PASS" if all(bool(v) for k, v in checks.items() if k not in {"arguments_count"}) else "NEEDS_CONFIG"
    if run_probe and probe.get("attempted") and probe.get("returncode") not in {0, None}:
        verdict = "PROBE_NONZERO_OR_TIMEOUT"
    lines = [
        "# Engine Profile Verification",
        "",
        f"Verdict: **{verdict}**",
        "",
        "## Checks",
        "",
    ]
    for k, v in checks.items():
        lines.append(f"- {k}: `{v}`")
    lines += ["", "## Probe", "", f"- attempted: `{probe.get('attempted', False)}`"]
    if probe.get("attempted"):
        lines.append(f"- returncode: `{probe.get('returncode', '')}`")
        lines.append(f"- command: `{probe.get('command', '')}`")
    lines += [
        "",
        "This verifies local engine configuration and optional startup behavior. It does not certify engine-specific command-line semantics for every build.",
    ]
    _write_text(out / "ENGINE_PROFILE_VERIFICATION.md", "\n".join(lines), res, root, changed=True)
    res.add_note(f"Engine profile verification verdict: {verdict}")
    return res


# ---------------------------------------------------------------------------
# Source runtime simulation / source-level sanity runner


def build_source_runtime_simulation(root: Path, *, max_steps_per_state: int = 180) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Source Runtime Simulation")
    out = _auth_dir(root) / "source_runtime_sim"
    out.mkdir(parents=True, exist_ok=True)
    actions = _air_actions(root)
    actions_by_no = {int(a.number): a for a in actions}
    state_defs = _all_state_defs(root)
    targets = _all_change_targets(root)
    rows: List[Dict[str, object]] = []
    issue_rows: List[Dict[str, object]] = []
    graph_edges: List[Dict[str, object]] = []
    for target in targets:
        src = int(target["state"]) if isinstance(target.get("state"), int) else _first_int(target.get("state"), 0)
        dst = target.get("target")
        if isinstance(dst, int):
            graph_edges.append({"source": src, "target": dst, "controller": target.get("controller", ""), "trigger": target.get("trigger1", "")})
            if dst not in state_defs and dst not in {0, 11, 20, 40, 50, 52, 5050, 5100, 5110, 5150}:
                issue_rows.append({"severity": "warning", "kind": "missing_state_target", "state": src, "detail": f"{target.get('controller')} targets undefined StateDef {dst}", "file": target.get("file", ""), "line": target.get("line", "")})
    # State summaries and simple execution expectations.
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception as exc:
            issue_rows.append({"severity": "error", "kind": "parse", "state": "", "detail": str(exc), "file": _rel(root, p), "line": ""})
            continue
        for st in scan.states:
            anim = _first_int(st.values.get("anim", st.number), st.number)
            duration = _anim_duration(actions_by_no, anim)
            has_end = any(
                (ctrl.stype or ctrl.values.get("type", "")).lower() in {"changestate", "selfstate", "destroyself"}
                for ctrl in st.controllers
            )
            has_hitdef = any((ctrl.stype or ctrl.values.get("type", "")).lower() == "hitdef" for ctrl in st.controllers)
            has_playsnd = any((ctrl.stype or ctrl.values.get("type", "")).lower() == "playsnd" for ctrl in st.controllers)
            if anim and anim not in actions_by_no:
                issue_rows.append({"severity": "warning", "kind": "missing_anim", "state": st.number, "detail": f"StateDef {st.number} references missing AIR action {anim}", "file": _rel(root, p), "line": st.line})
            if duration == 0 and anim:
                issue_rows.append({"severity": "info", "kind": "zero_anim_duration", "state": st.number, "detail": f"No known duration for anim {anim}", "file": _rel(root, p), "line": st.line})
            if not has_end and st.number >= 0 and st.values.get("movetype", "").upper() in {"A", "I", "H"}:
                issue_rows.append({"severity": "warning", "kind": "no_obvious_exit", "state": st.number, "detail": "No ChangeState/SelfState/DestroySelf controller detected; verify this state can end.", "file": _rel(root, p), "line": st.line})
            steps = min(max_steps_per_state, max(1, duration or 1))
            rows.append({
                "state": st.number,
                "file": _rel(root, p),
                "line": st.line,
                "anim": anim,
                "anim_ticks": duration,
                "simulated_ticks": steps,
                "controller_count": len(st.controllers),
                "has_hitdef": "yes" if has_hitdef else "no",
                "has_playsnd": "yes" if has_playsnd else "no",
                "has_exit_controller": "yes" if has_end else "no",
                "type": st.values.get("type", ""),
                "movetype": st.values.get("movetype", ""),
                "physics": st.values.get("physics", ""),
            })
    # Loop hints from graph: simple self-loops and two-node cycles.
    edges_by_src: Dict[int, List[int]] = {}
    for e in graph_edges:
        edges_by_src.setdefault(int(e["source"]), []).append(int(e["target"]))
        if int(e["source"]) == int(e["target"]):
            issue_rows.append({"severity": "info", "kind": "self_loop", "state": e["source"], "detail": f"State {e['source']} ChangeState/SelfState targets itself; verify triggers are intentional.", "file": "", "line": ""})
    for a, dsts in edges_by_src.items():
        for b in dsts:
            if a != b and a in edges_by_src.get(b, []):
                issue_rows.append({"severity": "info", "kind": "two_state_cycle", "state": a, "detail": f"State {a} and {b} can target each other; verify loop is intentional.", "file": "", "line": ""})
    _write_csv(out / "source_runtime_state_summary.csv", rows, ["state", "file", "line", "anim", "anim_ticks", "simulated_ticks", "controller_count", "has_hitdef", "has_playsnd", "has_exit_controller", "type", "movetype", "physics"], res, root)
    _write_csv(out / "source_runtime_edges.csv", graph_edges, ["source", "target", "controller", "trigger"], res, root)
    _write_csv(out / "source_runtime_findings.csv", issue_rows, ["severity", "kind", "state", "detail", "file", "line"], res, root)
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "states": rows,
        "edges": graph_edges,
        "findings": issue_rows,
        "scope": "source-level AIR/CNS/CMD sanity simulation; not an engine emulator",
    }
    _write_json(out / "source_runtime_simulation.json", payload, res, root, changed=True)
    html_path = out / "source_runtime_simulation.html"
    html_rows = "\n".join(f"<tr><td>{html.escape(str(r.get('severity','')))}</td><td>{html.escape(str(r.get('kind','')))}</td><td>{html.escape(str(r.get('state','')))}</td><td>{html.escape(str(r.get('detail','')))}</td></tr>" for r in issue_rows[:1000])
    _write_text(html_path, f"""<!doctype html><meta charset='utf-8'><title>MugenForge Source Runtime Simulation</title>
<h1>Source Runtime Simulation</h1>
<p>This is a source-level sanity runner for StateDef/AIR timing/ChangeState relationships. It is not a M.U.G.E.N/IKEMEN emulator.</p>
<p>States scanned: {len(rows)}. Findings: {len(issue_rows)}. Edges: {len(graph_edges)}.</p>
<table border='1' cellspacing='0' cellpadding='4'><tr><th>Severity</th><th>Kind</th><th>State</th><th>Detail</th></tr>{html_rows}</table>
""", res, root, changed=True)
    if issue_rows:
        res.add_note(f"Source runtime simulation created {len(issue_rows)} finding(s).")
    return res


# ---------------------------------------------------------------------------
# SFF2 corpus validation and unknown fingerprinting


def _byte_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    total = len(data)
    entropy = 0.0
    for c in counts:
        if c:
            p = c / total
            entropy -= p * math.log2(p)
    return entropy


def _fingerprint_sff(path: Path) -> Dict[str, object]:
    data = path.read_bytes()
    head = data[:96]
    dwords = []
    for off in range(0, min(len(data), 96), 4):
        if off + 4 <= len(data):
            try:
                dwords.append(int.from_bytes(data[off:off+4], "little", signed=False))
            except Exception:
                pass
    sample = data[: min(len(data), 8192)]
    return {
        "file": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "signature": data[:12].hex(),
        "version_bytes": list(data[12:16]) if len(data) >= 16 else [],
        "header_hex": head.hex(),
        "header_dwords_le": dwords,
        "has_png_signature": data.find(b"\x89PNG\r\n\x1a\n") >= 0,
        "has_pcx_signature": data.find(b"\x0A") >= 0,
        "has_zlib_hint": any(data.find(bytes([b, x])) >= 0 for b in (0x78,) for x in (0x01, 0x5E, 0x9C, 0xDA)),
        "entropy_8k": round(_byte_entropy(sample), 4),
    }


def validate_sff2_corpus(root: Path, corpus_folder: Optional[Path] = None, *, export_decode_samples: bool = True, max_files: int = 500) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("SFF2 Corpus Validation")
    out = _auth_dir(root) / "sff2_corpus"
    out.mkdir(parents=True, exist_ok=True)
    folders: List[Path] = []
    if corpus_folder:
        folders.append(Path(corpus_folder))
    folders += [root, out / "corpus_inbox", root / "test_corpus" / "sff2"]
    files: List[Path] = []
    seen = set()
    for folder in folders:
        if not folder.exists():
            continue
        for p in sorted(folder.rglob("*.sff"), key=lambda x: str(x).lower()):
            if p.resolve() in seen:
                continue
            if "authority_lab" in p.parts and p.name.startswith("candidate_"):
                continue
            seen.add(p.resolve())
            files.append(p)
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    rows: List[Dict[str, object]] = []
    fingerprints: List[Dict[str, object]] = []
    fmt_counts: Dict[str, int] = {}
    try:
        from .sff2_codec import read_sff2, export_sff2_decoded_images
    except Exception as exc:
        read_sff2 = None  # type: ignore[assignment]
        export_sff2_decoded_images = None  # type: ignore[assignment]
        res.add_warning(f"sff2_codec unavailable: {exc}")
    for p in files:
        fp = _fingerprint_sff(p)
        fingerprints.append({**fp, "file": _rel(root, p)})
        status = "unread"
        parser_mode = ""
        sprite_count = 0
        palette_count = 0
        decoded_count = 0
        warnings = ""
        formats = ""
        if read_sff2 is not None:
            try:
                info = read_sff2(p)
                status = "parsed" if info.sprites else "metadata_or_unrecognized"
                parser_mode = info.parser_mode
                sprite_count = len(info.sprites)
                palette_count = len(info.palettes)
                fcounts: Dict[str, int] = {}
                for spr in info.sprites:
                    fcounts[spr.format_name] = fcounts.get(spr.format_name, 0) + 1
                    fmt_counts[spr.format_name] = fmt_counts.get(spr.format_name, 0) + 1
                formats = "; ".join(f"{k}:{v}" for k, v in sorted(fcounts.items()))
                warnings = "; ".join(info.warnings[:12])
                if export_decode_samples and info.sprites and export_sff2_decoded_images is not None:
                    sample_dir = out / "decoded_samples" / re.sub(r"[^A-Za-z0-9_.-]+", "_", p.stem)[:80]
                    try:
                        exported = export_sff2_decoded_images(p, sample_dir, include_raw_payloads=True)
                        decoded_count = len(exported)
                        for ep in exported[:100]:
                            res.add_created(root, ep)
                    except Exception as exc:
                        warnings = (warnings + "; " if warnings else "") + f"decode export failed: {exc}"
            except Exception as exc:
                status = "parse_error"
                warnings = str(exc)
        rows.append({
            "file": _rel(root, p),
            "bytes": p.stat().st_size,
            "sha256": fp["sha256"],
            "status": status,
            "parser_mode": parser_mode,
            "sprite_count": sprite_count,
            "palette_count": palette_count,
            "formats": formats,
            "decoded_export_count": decoded_count,
            "entropy_8k": fp["entropy_8k"],
            "has_png_signature": fp["has_png_signature"],
            "has_pcx_signature": fp["has_pcx_signature"],
            "has_zlib_hint": fp["has_zlib_hint"],
            "warnings": warnings,
        })
    fields = ["file", "bytes", "sha256", "status", "parser_mode", "sprite_count", "palette_count", "formats", "decoded_export_count", "entropy_8k", "has_png_signature", "has_pcx_signature", "has_zlib_hint", "warnings"]
    _write_csv(out / "sff2_corpus_validation.csv", rows, fields, res, root)
    _write_json(out / "sff2_unknown_fingerprints.json", fingerprints, res, root, changed=True)
    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "files_scanned": len(rows),
        "status_counts": {k: sum(1 for r in rows if r["status"] == k) for k in sorted({str(r["status"]) for r in rows})},
        "format_counts": fmt_counts,
        "folders": [str(f) for f in folders],
    }
    _write_json(out / "sff2_corpus_summary.json", summary, res, root, changed=True)
    lines = [
        "# SFF2 Corpus Validation",
        "",
        f"Files scanned: **{len(rows)}**",
        "",
        "## Status counts",
        "",
    ]
    for k, v in summary["status_counts"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Format counts", ""]
    for k, v in sorted(fmt_counts.items()):
        lines.append(f"- {k}: {v}")
    lines += ["", "Unknown/corrupt/tool-specific files are fingerprinted instead of guessed. Add more files to `authority_lab/sff2_corpus/corpus_inbox/` to expand coverage."]
    _write_text(out / "SFF2_CORPUS_VALIDATION.md", "\n".join(lines), res, root, changed=True)
    if not rows:
        res.add_warning("No .sff files found for corpus validation. Add files to authority_lab/sff2_corpus/corpus_inbox/ or pass a corpus folder.")
    else:
        res.add_note(f"Validated {len(rows)} SFF file(s); decoded samples where supported.")
    return res


# ---------------------------------------------------------------------------
# Verified binary commit workflows


def _candidate_binary_files(root: Path) -> List[Path]:
    search_dirs = [
        Path(root) / "binary_core", Path(root) / "binary_deep", Path(root) / "binary_maturity",
        Path(root) / "authority_lab", Path(root) / "forge_timeline", Path(root) / "visual_forge",
    ]
    live = {p.resolve() for p in _project_files(root).values() if isinstance(p, Path) and p.exists()}
    out: List[Path] = []
    seen = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in BINARY_EXTS:
                continue
            if p.resolve() in live or p.resolve() in seen:
                continue
            if any(part in {"backups", "bundles"} for part in p.parts):
                continue
            seen.add(p.resolve())
            out.append(p)
    return out


def export_verified_binary_commit_sheet(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Verified Binary Commit Sheet")
    out = _auth_dir(root) / "binary_commit"
    out.mkdir(parents=True, exist_ok=True)
    files = _project_files(root)
    rows: List[Dict[str, object]] = []
    for cand in _candidate_binary_files(root):
        kind = cand.suffix.lower().lstrip(".")
        live = files.get(kind)
        rows.append({
            "enabled": "no",
            "kind": kind,
            "candidate_path": _rel(root, cand),
            "candidate_sha256": _sha256(cand),
            "candidate_bytes": cand.stat().st_size,
            "live_path": _rel(root, live) if live else "",
            "live_sha256": _sha256(live) if live and live.exists() else "",
            "install_mode": "replace_live_with_backup",
            "notes": "Set enabled=yes only after testing this candidate in your target engine.",
        })
    fields = ["enabled", "kind", "candidate_path", "candidate_sha256", "candidate_bytes", "live_path", "live_sha256", "install_mode", "notes"]
    sheet = out / "verified_binary_commit_sheet.csv"
    _write_csv(sheet, rows, fields, res, root)
    _write_text(out / "BINARY_COMMIT_README.md", "\n".join([
        "# Verified Binary Commit Sheet",
        "",
        "This sheet promotes a tested candidate `.sff` or `.snd` into the live DEF-referenced file with a backup and SHA-256 verification.",
        "",
        "1. Test the candidate in your target engine.",
        "2. Open `verified_binary_commit_sheet.csv`.",
        "3. Set `enabled=yes` for the exact candidate to promote.",
        "4. Do not edit the SHA fields unless you intentionally regenerated the sheet.",
        "5. Apply the sheet in Authority Lab.",
        "",
        "Blind overwrites are intentionally blocked. The app verifies the candidate hash before copying and writes a backup of the live file first.",
    ]), res, root, changed=True)
    res.add_note(f"Exported {len(rows)} candidate row(s).")
    return res


def apply_verified_binary_commit_sheet(root: Path, sheet_path: Optional[Path] = None) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Apply Verified Binary Commit Sheet")
    out = _auth_dir(root) / "binary_commit"
    sheet = Path(sheet_path) if sheet_path else out / "verified_binary_commit_sheet.csv"
    if not sheet.exists():
        res.merge(export_verified_binary_commit_sheet(root), "sheet")
    if not sheet.exists():
        res.add_warning("Verified binary commit sheet not found.")
        return res
    commit_log: List[Dict[str, object]] = []
    with sheet.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("enabled", "")).strip().lower() not in {"yes", "true", "1", "y"}:
                continue
            kind = str(row.get("kind", "")).strip().lower()
            if kind not in {"sff", "snd"}:
                res.add_warning(f"Skipping unsupported kind: {kind}")
                continue
            cand = (root / str(row.get("candidate_path", "")).strip()).resolve()
            live_rel = str(row.get("live_path", "")).strip()
            live = (root / live_rel).resolve() if live_rel else (_project_files(root).get(kind) or Path(""))
            if not cand.exists():
                res.add_warning(f"Candidate does not exist: {cand}")
                continue
            expected = str(row.get("candidate_sha256", "")).strip().lower()
            actual = _sha256(cand).lower()
            if expected and expected != actual:
                res.add_warning(f"Candidate SHA mismatch for {cand.name}; expected {expected}, got {actual}. Row skipped.")
                continue
            if not live or not Path(live).exists():
                res.add_warning(f"Live {kind.upper()} target missing; row skipped: {live}")
                continue
            backup_dir = out / "live_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"{Path(live).name}.bak_authority_{_now()}"
            shutil.copy2(live, backup)
            shutil.copy2(cand, live)
            res.add_created(root, backup)
            res.add_changed(root, live)
            commit_log.append({
                "time": datetime.now().isoformat(timespec="seconds"),
                "kind": kind,
                "candidate": _rel(root, cand),
                "candidate_sha256": actual,
                "live": _rel(root, live),
                "backup": _rel(root, backup),
                "new_live_sha256": _sha256(live),
            })
    log_path = out / "verified_binary_commit_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        for item in commit_log:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    if commit_log:
        res.add_changed(root, log_path)
        res.add_note(f"Promoted {len(commit_log)} verified binary candidate(s) into live files.")
    else:
        res.add_note("No rows were enabled or applied.")
    return res


# ---------------------------------------------------------------------------
# Generated gameplay tuning workbench


def write_gameplay_tuning_workbench(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Gameplay Tuning Workbench")
    out = _auth_dir(root) / "gameplay_tuning"
    out.mkdir(parents=True, exist_ok=True)
    hit_rows: List[Dict[str, object]] = []
    command_rows: List[Dict[str, object]] = []
    state_rows: List[Dict[str, object]] = []
    for p in _code_files(root):
        try:
            scan = parse_code(read_text_safely(p))
        except Exception as exc:
            res.add_warning(f"Could not parse {p}: {exc}")
            continue
        for c in scan.commands:
            command_rows.append({"file": _rel(root, p), "line": c.line, "name": c.name, "command": c.command, "time": c.time or "", "buffer_time": c.buffer_time or "", "test_status": "todo", "notes": ""})
        for st in scan.states:
            state_rows.append({"file": _rel(root, p), "line": st.line, "state": st.number, "type": st.values.get("type", ""), "movetype": st.values.get("movetype", ""), "physics": st.values.get("physics", ""), "anim": st.values.get("anim", ""), "test_status": "todo", "feel_notes": ""})
            for ctrl in st.controllers:
                if (ctrl.stype or ctrl.values.get("type", "")).lower() == "hitdef":
                    hit_rows.append({
                        "file": _rel(root, p), "line": ctrl.line, "state": st.number, "anim": st.values.get("anim", st.number),
                        "damage": ctrl.values.get("damage", ""), "pausetime": ctrl.values.get("pausetime", ""),
                        "sparkno": ctrl.values.get("sparkno", ""), "hitsound": ctrl.values.get("hitsound", ""),
                        "ground.velocity": ctrl.values.get("ground.velocity", ""), "air.velocity": ctrl.values.get("air.velocity", ""),
                        "hitflag": ctrl.values.get("hitflag", ""), "guardflag": ctrl.values.get("guardflag", ""),
                        "runtime_observed": "", "tuning_decision": "keep", "notes": "",
                    })
    scenario_rows: List[Dict[str, object]] = []
    for idx, row in enumerate(hit_rows, 1):
        scenario_rows.append({
            "scenario_id": f"hitdef_{idx:03d}", "state": row["state"], "purpose": f"Verify hit behavior/damage for State {row['state']}",
            "expected": f"Damage {row.get('damage','')} / pausetime {row.get('pausetime','')} / velocity {row.get('ground.velocity','')}",
            "status": "todo", "runtime_log_ref": "", "notes": "",
        })
    for idx, row in enumerate(command_rows[:100], 1):
        scenario_rows.append({
            "scenario_id": f"command_{idx:03d}", "state": "", "purpose": f"Verify command input {row['name']}",
            "expected": row.get("command", ""), "status": "todo", "runtime_log_ref": "", "notes": "",
        })
    _write_csv(out / "hitdef_runtime_tuning_sheet.csv", hit_rows, ["file", "line", "state", "anim", "damage", "pausetime", "sparkno", "hitsound", "ground.velocity", "air.velocity", "hitflag", "guardflag", "runtime_observed", "tuning_decision", "notes"], res, root)
    _write_csv(out / "command_runtime_test_sheet.csv", command_rows, ["file", "line", "name", "command", "time", "buffer_time", "test_status", "notes"], res, root)
    _write_csv(out / "state_runtime_test_sheet.csv", state_rows, ["file", "line", "state", "type", "movetype", "physics", "anim", "test_status", "feel_notes"], res, root)
    _write_csv(out / "runtime_scenario_evidence_sheet.csv", scenario_rows, ["scenario_id", "state", "purpose", "expected", "status", "runtime_log_ref", "notes"], res, root)
    _write_text(out / "GAMEPLAY_TUNING_WORKBENCH.md", "\n".join([
        "# Gameplay Tuning Workbench",
        "",
        "This workbench does not pretend generated gameplay code is finished. It turns generated scaffolding into testable tuning sheets.",
        "",
        f"- HitDef rows: {len(hit_rows)}",
        f"- Command rows: {len(command_rows)}",
        f"- State rows: {len(state_rows)}",
        f"- Runtime scenarios: {len(scenario_rows)}",
        "",
        "Use the sheets to record actual engine observations, then apply tuning in Forge Timeline / Creator Suite / HitDef tuning tools.",
    ]), res, root, changed=True)
    res.add_note("Generated runtime-linked tuning sheets for commands, states, HitDefs, and scenarios.")
    return res


# ---------------------------------------------------------------------------
# Evidence authority gate


def write_evidence_authority_gate(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Evidence Authority Gate")
    out = _auth_dir(root) / "release_gate"
    out.mkdir(parents=True, exist_ok=True)
    evidence = _evidence_files(root)
    engine_report = _read_json(_auth_dir(root) / "engine" / "engine_profile_verification.json", {})
    sim_report = _read_json(_auth_dir(root) / "source_runtime_sim" / "source_runtime_simulation.json", {})
    corpus_summary = _read_json(_auth_dir(root) / "sff2_corpus" / "sff2_corpus_summary.json", {})
    readiness = _read_json(root / "runtime_lab" / "readiness" / "runtime_readiness_report.json", {})
    if not readiness:
        # Some Runtime Lab builds write under runtime_lab root.
        readiness = _read_json(root / "runtime_lab" / "runtime_readiness_report.json", {})
    evidence_rows: List[Dict[str, object]] = []
    for p in evidence:
        evidence_rows.append({
            "file": _rel(root, p), "bytes": p.stat().st_size, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"), "sha256": _sha256(p)
        })
    _write_csv(out / "authority_evidence_index.csv", evidence_rows, ["file", "bytes", "modified", "sha256"], res, root)
    score = 100
    blockers: List[str] = []
    warnings: List[str] = []
    def ding(points: int, msg: str, blocker: bool = False) -> None:
        nonlocal score
        score = max(0, score - points)
        (blockers if blocker else warnings).append(msg)
    checks = engine_report.get("checks", {}) if isinstance(engine_report, dict) else {}
    probe = engine_report.get("probe", {}) if isinstance(engine_report, dict) else {}
    if not engine_report:
        ding(20, "Engine profile verification has not been generated.", True)
    elif not checks.get("engine_executable_exists"):
        ding(25, "Configured engine executable is missing.", True)
    if probe.get("attempted") and probe.get("returncode") not in {0, None}:
        ding(10, f"Engine probe returned {probe.get('returncode')}.")
    elif not probe.get("attempted"):
        ding(8, "Engine probe has not been run; evidence is configuration-only.")
    findings = sim_report.get("findings", []) if isinstance(sim_report, dict) else []
    sim_errors = [x for x in findings if isinstance(x, dict) and str(x.get("severity", "")).lower() == "error"]
    sim_warnings = [x for x in findings if isinstance(x, dict) and str(x.get("severity", "")).lower() == "warning"]
    if not sim_report:
        ding(10, "Source runtime simulation has not been generated.")
    if sim_errors:
        ding(min(30, 10 * len(sim_errors)), f"Source runtime simulation has {len(sim_errors)} error finding(s).", True)
    if sim_warnings:
        ding(min(20, 2 * len(sim_warnings)), f"Source runtime simulation has {len(sim_warnings)} warning finding(s).")
    if not corpus_summary:
        ding(8, "SFF2 corpus validation has not been generated.")
    elif int(corpus_summary.get("files_scanned", 0) or 0) == 0:
        ding(8, "SFF2 corpus validation scanned no files.")
    if len(evidence_rows) == 0:
        ding(20, "No runtime/log/evidence files were indexed.", True)
    elif len(evidence_rows) < 3:
        ding(8, "Only a small amount of runtime evidence was indexed.")
    audit = scan_project(root)
    if audit.missing_required:
        ding(min(25, 5 * len(audit.missing_required)), f"Missing required project file types: {', '.join(audit.missing_required)}", True)
    status = "BLOCKED" if blockers else ("READY_WITH_EVIDENCE" if score >= 85 else "NEEDS_REVIEW")
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "score": score,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "engine_verification": engine_report,
        "source_runtime_finding_count": len(findings),
        "sff2_corpus_summary": corpus_summary,
        "runtime_readiness": readiness,
        "evidence_count": len(evidence_rows),
    }
    _write_json(out / "authority_gate_report.json", payload, res, root, changed=True)
    lines = [
        "# Authority Gate Report",
        "",
        f"Status: **{status}**",
        f"Score: **{score}/100**",
        "",
        "## Blockers",
        "",
    ]
    lines += [f"- {b}" for b in blockers] or ["- None"]
    lines += ["", "## Warnings", ""]
    lines += [f"- {w}" for w in warnings] or ["- None"]
    lines += [
        "", "## Evidence", "", f"Indexed files: {len(evidence_rows)}", "",
        "Authority Gate is evidence-backed when it includes real external engine logs/probe output. Without real engine evidence, it remains a strong preflight check rather than runtime certification.",
    ]
    _write_text(out / "AUTHORITY_GATE_REPORT.md", "\n".join(lines), res, root, changed=True)
    res.add_note(f"Authority gate status: {status} ({score}/100).")
    return res


# ---------------------------------------------------------------------------
# Bundle and one-click pass


def build_authority_bundle(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("Authority Lab Bundle")
    base = _auth_dir(root)
    out_dir = base / "bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{root.name}_authority_lab_bundle_{_now()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in [base, root / "runtime_lab", root / "binary_core", root / "binary_deep", root / "binary_maturity"]:
            if not folder.exists():
                continue
            for p in sorted(folder.rglob("*"), key=lambda x: str(x).lower()):
                if p.is_file() and p != out and not p.name.endswith(".pyc"):
                    try:
                        zf.write(p, p.relative_to(root))
                    except Exception:
                        pass
    res.add_created(root, out)
    return res


def run_authority_lab_pass(root: Path) -> AuthorityLabResult:
    root = Path(root)
    res = AuthorityLabResult("One-Click Authority Lab Pass")
    steps = [
        ("dashboard", write_authority_dashboard),
        ("runtime config", lambda r: rt_lab.write_runtime_config(r)),
        ("engine verification", lambda r: verify_engine_profile(r, run_probe=False)),
        ("source runtime simulation", build_source_runtime_simulation),
        ("sff2 corpus validation", validate_sff2_corpus),
        ("binary commit sheet", export_verified_binary_commit_sheet),
        ("gameplay tuning", write_gameplay_tuning_workbench),
        ("runtime readiness", lambda r: rt_lab.write_runtime_readiness_report(r)),
        ("runtime log ingest", lambda r: rt_lab.parse_runtime_logs(r)),
        ("authority gate", write_evidence_authority_gate),
        ("bundle", build_authority_bundle),
    ]
    for label, fn in steps:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f"{label} failed: {exc}")
    return res
