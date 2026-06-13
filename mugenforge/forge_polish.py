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

from .parsers import COMMON_ANIMS, parse_air, parse_code, read_text_safely, scan_project, write_text_safely
from .move_wizard import find_character_file
from .sff_codec import read_sff, export_sprite
from .visual_forge import create_backup_snapshot

FORGE_POLISH_VERSION = "4.1.0"
CODE_SUFFIXES = {".cmd", ".cns", ".st"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg", ".csv"}
SAFE_TEMPLATE_EXTS = TEXT_SUFFIXES | IMAGE_SUFFIXES | {".wav", ".ogg", ".mp3", ".flac", ".act", ".pal"}
BLOCKED_TEMPLATE_EXTS = {".py", ".pyc", ".pyd", ".dll", ".exe", ".bat", ".cmdline", ".sh", ".ps1", ".vbs", ".js", ".jar", ".scr"}
SKIP_PARTS = {"__pycache__", ".git", ".hg", ".svn", ".venv", "venv"}
GENERATED_PARTS = {"forge_polish", "polish_lab", "forge_beyond", "visual_forge", "backups", "exports", "quality_lab"}


@dataclass
class ForgePolishResult:
    title: str = "Forge Polish Result"
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


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _out(root: Path, *parts: str) -> Path:
    p = Path(root) / "forge_polish"
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_text(root: Path, path: Path, text: str, res: Optional[ForgePolishResult] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    if res is not None:
        (res.changed_files if existed else res.created_files).append(_rel(root, path))
    return path


def _write_json(root: Path, path: Path, payload: object, res: Optional[ForgePolishResult] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if res is not None:
        (res.changed_files if existed else res.created_files).append(_rel(root, path))
    return path


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], res: Optional[ForgePolishResult] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    if res is not None:
        (res.changed_files if existed else res.created_files).append(_rel(root, path))
    return path


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _all_files(root: Path, include_generated: bool = True) -> List[Path]:
    out: List[Path] = []
    for path in sorted(Path(root).rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if not include_generated and any(part in GENERATED_PARTS for part in path.relative_to(root).parts):
            continue
        out.append(path)
    return out


def _code_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root, include_generated=False) if p.suffix.lower() in CODE_SUFFIXES]


def _image_files(root: Path, include_generated: bool = False) -> List[Path]:
    return [p for p in _all_files(root, include_generated=include_generated) if p.suffix.lower() in IMAGE_SUFFIXES]


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


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "yes", "y", "true", "on", "apply", "enabled"}


def _backup_text_file(root: Path, path: Path, reason: str) -> Optional[Path]:
    if not path.exists():
        return None
    try:
        rel = path.resolve().relative_to(Path(root).resolve())
    except Exception:
        rel = Path(path.name)
    dst = root / "backups" / "forge_polish_file_backups" / rel.with_name(rel.name + f".bak_{_safe_name(reason)}_{_timestamp()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def write_beginner_next_steps_dashboard(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("v4.1 Beginner Dashboard")
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
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
            commands.extend(scan.commands)
            states.extend(scan.states)
            hitdefs += sum(1 for c in scan.controllers if (c.stype or c.values.get("type", "")).lower() == "hitdef")
        except Exception:
            pass
    counts: Dict[str, int] = {}
    for path in _all_files(root):
        ext = path.suffix.lower() or "[none]"
        counts[ext] = counts.get(ext, 0) + 1
    action_nums = {a.number for a in actions}
    missing_common = [n for n in COMMON_ANIMS if n not in action_nums]
    score = 100
    score -= min(35, 7 * len(audit.missing_required))
    score -= min(25, 5 * len(audit.missing_references))
    score -= min(20, len(missing_common))
    if not commands:
        score -= 8
    if not states:
        score -= 8
    if hitdefs == 0:
        score -= 8
    score = max(0, min(100, score))
    next_steps: List[str] = []
    if audit.missing_required:
        next_steps.append("Repair missing required file types/references from Project Home or Auto Setup.")
    if missing_common:
        next_steps.append("Install/repair common AIR actions before packaging.")
    if not commands:
        next_steps.append("Use Move Composer or beginner packs to add command definitions.")
    if hitdefs == 0:
        next_steps.append("Add at least one HitDef move and verify timing in the timeline/CLSN tools.")
    next_steps.extend([
        "Validate Forge Beyond command and AIR sheets before applying edits.",
        "Use the editable sound cue sheet for new PlaySnd timing; only enabled add rows apply.",
        "Review the sprite-backed timeline and StateDef graph before packaging.",
        "Create or review backups before any large migration or restore.",
        "Playtest in M.U.G.E.N; dashboards and graphs are source-analysis aids only.",
    ])
    md = [
        "# MugenForge v4.1 Beginner Dashboard", "", f"Project: **{root.name}**", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", f"## Health score: {score}/100", "", "## Project snapshot", "", f"- Commands: {len(commands)}", f"- StateDefs: {len(states)}", f"- HitDefs: {hitdefs}", f"- AIR actions: {len(actions)}", f"- Missing required file types: {', '.join(audit.missing_required) if audit.missing_required else 'none'}", f"- Missing common AIR actions: {len(missing_common)}", "", "## Do next", "",
    ] + [f"- [ ] {step}" for step in next_steps] + ["", "## Honest limits", "", "- Full arbitrary mature SFF v2 binary extraction/rebuild/mutation is still not implemented.", "- Reports are source-analysis aids, not engine-authoritative runtime telemetry."]
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    _write_text(root, docs / "BEGINNER_DASHBOARD_v4_1.md", "\n".join(md), result)
    cards = "".join(f"<li>{html.escape(step)}</li>" for step in next_steps)
    ext_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>" for k, v in sorted(counts.items()))
    html_text = f"<!doctype html><meta charset='utf-8'><title>MugenForge v4.1 Dashboard</title><style>body{{font-family:system-ui;margin:24px;max-width:980px}}.score{{font-size:42px;font-weight:700}}li{{margin:6px 0}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px}}</style><h1>MugenForge v4.1 Beginner Dashboard</h1><div class='score'>{score}/100</div><p>Commands: {len(commands)}. States: {len(states)}. HitDefs: {hitdefs}. AIR actions: {len(actions)}.</p><h2>Do next</h2><ol>{cards}</ol><h2>File counts</h2><table><tr><th>Ext</th><th>Count</th></tr>{ext_rows}</table><h2>Honest limits</h2><p>Full arbitrary mature SFF v2 editing/rebuilding is still not implemented. Playtest in engine before release.</p>"
    _write_text(root, _out(root) / "BEGINNER_DASHBOARD_v4_1.html", html_text, result)
    _write_json(root, _out(root) / "beginner_dashboard_v4_1.json", {"score": score, "commands": len(commands), "states": len(states), "hitdefs": hitdefs, "air_actions": len(actions), "missing_required": audit.missing_required, "missing_common_actions": missing_common, "next_steps": next_steps}, result)
    result.notes.append(f"Wrote v4.1 beginner dashboard with health score {score}/100.")
    return result


write_beginner_dashboard_41 = write_beginner_next_steps_dashboard


# ---------------------------------------------------------------------------
# Sheet validation
# ---------------------------------------------------------------------------


def _issue(severity: str, file: str, row: int, field: str, message: str) -> Dict[str, object]:
    return {"severity": severity, "file": file, "row": row, "field": field, "message": message}


def _issues_markdown(title: str, issues: Sequence[Dict[str, object]]) -> str:
    counts: Dict[str, int] = {}
    for issue in issues:
        sev = str(issue.get("severity", "info"))
        counts[sev] = counts.get(sev, 0) + 1
    lines = [f"# {title}", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", "## Summary", ""]
    if counts:
        lines.extend(f"- {key}: {counts[key]}" for key in sorted(counts))
    else:
        lines.append("- No issues found.")
    if issues:
        lines += ["", "## Details", ""]
        lines.extend(f"- **{i.get('severity')}** row {i.get('row')} `{i.get('file')}` `{i.get('field')}`: {i.get('message')}" for i in issues[:500])
    lines += ["", "No project files were modified by this validation report."]
    return "\n".join(lines)


def validate_command_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Command Sheet Validation Preview")
    sheet = Path(sheet_path) if sheet_path else root / "forge_beyond" / "sheets" / "command_editor_sheet.csv"
    out = _out(root, "sheet_validation")
    if not sheet.exists():
        result.warnings.append(f"Command sheet not found: {_rel(root, sheet)}")
        _write_text(root, out / "COMMAND_SHEET_VALIDATION.md", "# Command Sheet Validation\n\nCommand sheet not found. Export it from Forge Beyond first.", result)
        return result
    rows = _read_csv(sheet)
    issues: List[Dict[str, object]] = []
    previews: List[Dict[str, object]] = []
    for idx, row in enumerate(rows, start=2):
        rel = str(row.get("file", "")).strip()
        name = str(row.get("name", "")).strip()
        new_command = str(row.get("new_command", row.get("command", ""))).strip()
        new_time = str(row.get("new_time", row.get("time", ""))).strip()
        new_buffer = str(row.get("new_buffer_time", row.get("buffer_time", ""))).strip()
        if not rel:
            issues.append(_issue("error", rel, idx, "file", "Missing target file."))
        elif not (root / rel).exists() or (root / rel).suffix.lower() != ".cmd":
            issues.append(_issue("error", rel, idx, "file", "Target CMD file is missing."))
        if not name:
            issues.append(_issue("error", rel, idx, "name", "Missing command name."))
        if not new_command:
            issues.append(_issue("error", rel, idx, "new_command", "New command value is blank."))
        for field, value in (("new_time", new_time), ("new_buffer_time", new_buffer)):
            if value:
                try:
                    if int(value) < 0:
                        issues.append(_issue("error", rel, idx, field, "Must be >= 0."))
                except Exception:
                    issues.append(_issue("error", rel, idx, field, "Not an integer."))
        changed = []
        for old, new, label in ((row.get("command", ""), new_command, "command"), (row.get("time", ""), new_time, "time"), (row.get("buffer_time", ""), new_buffer, "buffer.time")):
            if str(new).strip() and str(old).strip() != str(new).strip():
                changed.append(f"{label}: {old} -> {new}")
        previews.append({"row": idx, "file": rel, "name": name, "changes": "; ".join(changed), "status": "error" if any(i.get("row") == idx and i.get("severity") == "error" for i in issues) else ("change" if changed else "no-op")})
    _write_csv(root, out / "command_sheet_validation.csv", issues, ["severity", "file", "row", "field", "message"], result)
    _write_csv(root, out / "command_sheet_preview.csv", previews, ["row", "file", "name", "changes", "status"], result)
    _write_text(root, out / "COMMAND_SHEET_VALIDATION.md", _issues_markdown("Command Sheet Validation", issues), result)
    if issues:
        result.warnings.append(f"Command sheet has {len(issues)} validation issue(s).")
    else:
        result.notes.append(f"Command sheet validated: {len(rows)} row(s), no blocking issues.")
    return result


def validate_air_batch_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("AIR Batch Sheet Validation Preview")
    sheet = Path(sheet_path) if sheet_path else root / "forge_beyond" / "sheets" / "air_batch_editor_sheet.csv"
    out = _out(root, "sheet_validation")
    if not sheet.exists():
        result.warnings.append(f"AIR batch sheet not found: {_rel(root, sheet)}")
        _write_text(root, out / "AIR_BATCH_SHEET_VALIDATION.md", "# AIR Batch Sheet Validation\n\nAIR batch sheet not found. Export it from Forge Beyond first.", result)
        return result
    rows = _read_csv(sheet)
    issues: List[Dict[str, object]] = []
    previews: List[Dict[str, object]] = []
    for idx, row in enumerate(rows, start=2):
        rel = str(row.get("file", "")).strip()
        path = root / rel if rel else None
        if not rel:
            issues.append(_issue("error", rel, idx, "file", "Missing target file."))
        elif not path or not path.exists() or path.suffix.lower() != ".air":
            issues.append(_issue("error", rel, idx, "file", "Target AIR file is missing."))
        line_index = _int(row.get("line_index"), None)
        if line_index is None or line_index < 0:
            issues.append(_issue("error", rel, idx, "line_index", "Line index is not a non-negative integer."))
        elif path and path.exists() and line_index >= len(read_text_safely(path).splitlines()):
            issues.append(_issue("error", rel, idx, "line_index", "Line index is beyond the current AIR file length."))
        for field, minimum in (("new_group", None), ("new_image", None), ("new_x", None), ("new_y", None), ("new_ticks", 1)):
            value = row.get(field, row.get(field.replace("new_", ""), ""))
            parsed = _int(value, None)
            if parsed is None:
                issues.append(_issue("error", rel, idx, field, "Not an integer."))
            elif minimum is not None and parsed < minimum:
                issues.append(_issue("error", rel, idx, field, f"Must be >= {minimum}."))
        changed = []
        for old_field, new_field in (("group", "new_group"), ("image", "new_image"), ("x", "new_x"), ("y", "new_y"), ("ticks", "new_ticks"), ("flags", "new_flags")):
            old = str(row.get(old_field, "")).strip()
            new = str(row.get(new_field, old)).strip()
            if new and new != old:
                changed.append(f"{old_field}: {old} -> {new}")
        previews.append({"row": idx, "file": rel, "action": row.get("action", ""), "frame_index": row.get("frame_index", ""), "changes": "; ".join(changed), "status": "error" if any(i.get("row") == idx and i.get("severity") == "error" for i in issues) else ("change" if changed else "no-op")})
    _write_csv(root, out / "air_batch_sheet_validation.csv", issues, ["severity", "file", "row", "field", "message"], result)
    _write_csv(root, out / "air_batch_sheet_preview.csv", previews, ["row", "file", "action", "frame_index", "changes", "status"], result)
    _write_text(root, out / "AIR_BATCH_SHEET_VALIDATION.md", _issues_markdown("AIR Batch Sheet Validation", issues), result)
    if issues:
        result.warnings.append(f"AIR batch sheet has {len(issues)} validation issue(s).")
    else:
        result.notes.append(f"AIR batch sheet validated: {len(rows)} row(s), no blocking issues.")
    return result


def validate_all_edit_sheets(root: Path) -> ForgePolishResult:
    result = ForgePolishResult("Forge Polish Sheet Validation")
    result.merge(validate_command_sheet(root), "command sheet")
    result.merge(validate_air_batch_sheet(root), "AIR batch sheet")
    return result


# ---------------------------------------------------------------------------
# Sound cue sheet export/apply
# ---------------------------------------------------------------------------


def _anim_elem(values: Dict[str, str]) -> int:
    for key, value in values.items():
        if key.lower().startswith("trigger"):
            m = re.search(r"AnimElem\s*=\s*(-?\d+)", value, re.I)
            if m:
                return int(m.group(1))
    return 1


def _sound_pair(value: object) -> Tuple[str, str]:
    nums = re.findall(r"-?\d+", str(value or ""))
    return (nums[0], nums[1]) if len(nums) >= 2 else ("", "")


def export_sound_cue_apply_sheet(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Editable Sound Cue Sheet")
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for state in scan.states:
            for ctrl in state.controllers:
                if (ctrl.stype or ctrl.values.get("type", "")).lower() == "playsnd":
                    group, sound = _sound_pair(ctrl.values.get("value", ""))
                    rows.append({"action": "keep", "enabled": "no", "target_file": _rel(root, path), "state": state.number, "frame": _anim_elem(ctrl.values), "sound_group": group, "sound_index": sound, "channel": ctrl.values.get("channel", ""), "label": ctrl.header, "note": f"Existing cue line {ctrl.line}; duplicate and set action=add enabled=yes to insert.", "source_file": _rel(root, path), "line": ctrl.line})
    default_target = _discover_files(root).get("cns") or _discover_files(root).get("cmd") or (root / f"{root.name}.cns")
    rows.append({"action": "add", "enabled": "no", "target_file": _rel(root, default_target), "state": 200, "frame": 2, "sound_group": 5, "sound_index": 0, "channel": 0, "label": "New sound cue", "note": "Set enabled=yes to apply this new cue.", "source_file": "", "line": ""})
    fields = ["action", "enabled", "target_file", "state", "frame", "sound_group", "sound_index", "channel", "label", "note", "source_file", "line"]
    out = _out(root, "sheets")
    _write_csv(root, out / "sound_cue_apply_sheet.csv", rows, fields, result)
    # Compatibility filename for earlier v4.1 UI experiments.
    _write_csv(root, out / "sound_cue_editor_sheet.csv", rows, fields, result)
    _write_text(root, _out(root, "sheet_validation") / "SOUND_CUE_SHEET_GUIDE.md", "# Editable Sound Cue Sheet\n\nOnly rows with `action=add` and `enabled=yes` are applied. Applying inserts text-code `PlaySnd` controllers with backups. This does not mutate SND binary banks.", result)
    result.notes.append(f"Exported {max(0, len(rows) - 1)} existing PlaySnd cue(s) plus one disabled add-template row.")
    return result


export_editable_sound_cue_sheet = export_sound_cue_apply_sheet


def _insert_playsnd(text: str, state_no: int, frame: int, group: int, sound: int, channel: int, label: str, marker: str) -> Tuple[str, str]:
    m = re.search(r"^\s*\[\s*Statedef\s+" + re.escape(str(state_no)) + r"\s*\]", text, re.I | re.M)
    if not m:
        return text, f"StateDef {state_no} not found"
    if marker in text:
        return text, "duplicate marker skipped"
    next_state = re.search(r"^\s*\[\s*Statedef\s+-?\d+\s*\]", text[m.end():], re.I | re.M)
    at = m.end() + next_state.start() if next_state else len(text)
    clean_label = re.sub(r"[\r\n\[\]]+", " ", label or "Forge Polish Sound Cue").strip()[:80] or "Forge Polish Sound Cue"
    block = f"""

{marker}
[State {state_no}, {clean_label}]
type = PlaySnd
trigger1 = AnimElem = {max(1, frame)}
value = {group}, {sound}
channel = {channel}
ignorehitpause = 1
"""
    return text[:at].rstrip() + block + "\n" + text[at:].lstrip("\n"), "inserted"


def apply_sound_cue_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Sound Cue Sheet Apply")
    sheet = Path(sheet_path) if sheet_path else _out(root, "sheets") / "sound_cue_apply_sheet.csv"
    if not sheet.exists():
        alt = _out(root, "sheets") / "sound_cue_editor_sheet.csv"
        sheet = alt if alt.exists() else sheet
    if not sheet.exists():
        result.warnings.append(f"Sound cue sheet not found: {_rel(root, sheet)}")
        return result
    rows = _read_csv(sheet)
    cache: Dict[Path, str] = {}
    backed_up: set[Path] = set()
    applied = 0
    skipped = 0
    for row_no, row in enumerate(rows, start=2):
        if str(row.get("action", "")).strip().lower() not in {"add", "insert", "append"} or not _truthy(row.get("enabled", "")):
            skipped += 1
            continue
        path = root / (row.get("target_file") or row.get("file") or "")
        state = _int(row.get("state", row.get("state_no")), None)
        frame = _int(row.get("frame", row.get("anim_elem")), None)
        group = _int(row.get("sound_group"), None)
        sound = _int(row.get("sound_index"), None)
        channel = _int(row.get("channel"), 0) or 0
        if not path.exists() or path.suffix.lower() not in CODE_SUFFIXES or None in (state, frame, group, sound):
            result.warnings.append(f"CSV row {row_no}: invalid target or integer fields")
            continue
        text = cache.get(path, read_text_safely(path))
        marker = f"; MugenForge Forge Polish Sound Cue: {sheet.name}:row{row_no} state={state} frame={frame} value={group},{sound} channel={channel}"
        new_text, status = _insert_playsnd(text, int(state), max(1, int(frame)), int(group), int(sound), int(channel), str(row.get("label", "Forge Polish Sound Cue")), marker)
        if status == "inserted":
            if path not in backed_up:
                backup = _backup_text_file(root, path, "sound_cue_sheet")
                if backup:
                    result.add_created(root, backup)
                backed_up.add(path)
            cache[path] = new_text
            applied += 1
        else:
            result.skipped_files.append(f"row {row_no}: {status}")
    for path, text in cache.items():
        write_text_safely(path, text)
        result.add_changed(root, path)
    result.notes.append(f"Applied {applied} sound cue insertion(s). Skipped {skipped} disabled/keep row(s).")
    return result


apply_snd_cue_sheet = apply_sound_cue_sheet


# ---------------------------------------------------------------------------
# Timeline preview and state graph
# ---------------------------------------------------------------------------


def _sprite_key_from_name(path: Path, fallback: int) -> Tuple[int, int]:
    stem = path.stem.lower()
    for pat in (r"g(?:roup)?[_\- ]?(?P<g>-?\d+)[_\- ]?i(?:mage|mg)?[_\- ]?(?P<i>-?\d+)", r"group[_\- ]?(?P<g>-?\d+)[_\- ]?(?:image|img|item)[_\- ]?(?P<i>-?\d+)", r"^(?P<g>-?\d+)[_\-., ](?P<i>-?\d+)$"):
        m = re.search(pat, stem)
        if m:
            return int(m.group("g")), int(m.group("i"))
    return 0, int(fallback)


def _sprite_source_lookup(root: Path, result: ForgePolishResult) -> Dict[Tuple[int, int], Path]:
    lookup: Dict[Tuple[int, int], Path] = {}
    for idx, path in enumerate(_image_files(root, include_generated=False)):
        lookup.setdefault(_sprite_key_from_name(path, idx), path)
    sff = _discover_files(root).get("sff")
    if sff and sff.exists():
        try:
            info = read_sff(sff)
            if info.is_supported_for_extraction:
                out = _out(root, "timeline_preview", "exported_sff_sprites")
                for spr in info.sprites[:2000]:
                    if spr.key not in lookup and spr.format_hint in {"png", "pcx"}:
                        try:
                            lookup[spr.key] = export_sprite(sff, spr, out)
                        except Exception:
                            pass
            elif info.warnings:
                result.warnings.extend(info.warnings[:3])
        except Exception as exc:
            result.warnings.append(f"SFF preview extraction skipped: {exc}")
    return lookup


def build_sprite_backed_timeline_preview(root: Path, action_number: Optional[int] = None, max_actions: int = 8) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Sprite-Backed Timeline Preview")
    air = _discover_files(root).get("air")
    if not air or not air.exists():
        result.warnings.append("No AIR file found.")
        return result
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        result.warnings.append(f"Pillow is required for timeline preview: {exc}")
        return result
    actions = parse_air(read_text_safely(air))
    if action_number is not None:
        actions = [a for a in actions if a.number == int(action_number)]
    else:
        actions = actions[:max_actions]
    if not actions:
        result.warnings.append("No matching AIR action found.")
        return result
    lookup = _sprite_source_lookup(root, result)
    out = _out(root, "timeline_preview")
    thumb_w, thumb_h, pad, label_h = 132, 132, 12, 58
    cols = max(1, min(24, max(len(a.frames) for a in actions)))
    sheet = Image.new("RGBA", (220 + cols * (thumb_w + pad) + pad, pad + len(actions) * (thumb_h + label_h + pad)), (248, 248, 248, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 10)
    except Exception:
        font = None
    manifest: List[Dict[str, object]] = []
    y = pad
    for action in actions:
        draw.text((pad, y + 8), f"Action {action.number}", fill=(0, 0, 0, 255), font=font)
        cursor = 0
        for idx, frame in enumerate(action.frames[:24]):
            x = 210 + idx * (thumb_w + pad)
            draw.rectangle([x, y, x + thumb_w, y + thumb_h], fill=(255, 255, 255, 255), outline=(170, 170, 170, 255))
            src = lookup.get((frame.group, frame.image))
            found = False
            if src and src.exists():
                try:
                    im = Image.open(src).convert("RGBA")
                    im.thumbnail((thumb_w - 14, thumb_h - 14))
                    sheet.alpha_composite(im, (x + (thumb_w - im.width) // 2, y + (thumb_h - im.height) // 2))
                    found = True
                except Exception:
                    found = False
            if not found:
                draw.line([x + 12, y + 12, x + thumb_w - 12, y + thumb_h - 12], fill=(185, 185, 185, 255), width=2)
                draw.line([x + thumb_w - 12, y + 12, x + 12, y + thumb_h - 12], fill=(185, 185, 185, 255), width=2)
                draw.text((x + 20, y + 55), "no source\nimage", fill=(80, 80, 80, 255), font=font)
            has_hit = any(b.kind.lower() == "clsn1" for b in frame.clsn)
            has_body = any(b.kind.lower() == "clsn2" for b in frame.clsn)
            if has_hit:
                draw.rectangle([x + 4, y + 4, x + thumb_w - 4, y + thumb_h - 4], outline=(210, 0, 0, 255), width=3)
            if has_body:
                draw.rectangle([x + 9, y + 9, x + thumb_w - 9, y + thumb_h - 9], outline=(0, 70, 210, 255), width=2)
            draw.text((x, y + thumb_h + 4), f"#{idx + 1} g{frame.group},i{frame.image}\n{frame.ticks} ticks off({frame.x},{frame.y})\nstart {cursor}", fill=(0, 0, 0, 255), font=font)
            manifest.append({"action": action.number, "frame": idx + 1, "group": frame.group, "image": frame.image, "ticks": frame.ticks, "offset_x": frame.x, "offset_y": frame.y, "start_tick": cursor, "source_image": _rel(root, src), "has_hitbox": has_hit, "has_hurtbox": has_body})
            cursor += max(1, int(frame.ticks))
        y += thumb_h + label_h + pad
    png = out / (f"timeline_action_{action_number}.png" if action_number is not None else "timeline_contact_sheet.png")
    sheet.convert("RGB").save(png)
    _write_csv(root, out / "sprite_backed_timeline_frames.csv", manifest, ["action", "frame", "group", "image", "ticks", "offset_x", "offset_y", "start_tick", "source_image", "has_hitbox", "has_hurtbox"], result)
    _write_json(root, out / "sprite_backed_timeline_manifest.json", {"air_file": _rel(root, air), "frames": manifest, "source_images_found": len(lookup)}, result)
    _write_text(root, out / "sprite_backed_timeline_preview.html", f"<!doctype html><meta charset='utf-8'><h1>Sprite-Backed Timeline Preview</h1><p>Red=Clsn1. Blue=Clsn2. Source preview only.</p><img src='{html.escape(png.name)}' style='max-width:100%;border:1px solid #999'>", result)
    result.add_created(root, png)
    result.notes.append(f"Created timeline preview for {len(actions)} AIR action(s).")
    return result


def make_state_graph_model(root: Path, max_nodes: int = 120) -> Dict[str, object]:
    root = Path(root)
    states: Dict[int, Dict[str, object]] = {}
    edges: List[Dict[str, object]] = []
    warnings: List[str] = []
    for path in _code_files(root):
        rel = _rel(root, path)
        try:
            scan = parse_code(read_text_safely(path))
        except Exception as exc:
            warnings.append(f"Could not parse {rel}: {exc}")
            continue
        for st in scan.states:
            states.setdefault(st.number, {"id": st.number, "state": st.number, "file": rel, "line": st.line, "type": st.values.get("type", ""), "movetype": st.values.get("movetype", ""), "physics": st.values.get("physics", ""), "anim": st.values.get("anim", ""), "controllers": len(st.controllers)})
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype == "changestate" and "value" in ctrl.values:
                    raw = str(ctrl.values.get("value", "")).strip()
                    numeric = bool(re.fullmatch(r"-?\d+", raw))
                    edges.append({"source": st.number, "target": int(raw) if numeric else raw, "target_raw": raw, "numeric_target": numeric, "missing": False, "file": rel, "line": ctrl.line, "controller": ctrl.header})
    for edge in edges:
        if edge["numeric_target"]:
            edge["missing"] = int(edge["target"]) not in states
    nodes = sorted(states.values(), key=lambda n: int(n["state"]))[:max_nodes]
    cols = max(1, math.ceil(math.sqrt(max(1, len(nodes)))))
    for idx, node in enumerate(nodes):
        sid = int(node["state"])
        node["x"] = 90 + (idx % cols) * 150
        node["y"] = 75 + (idx // cols) * 95
        node["incoming"] = sum(1 for edge in edges if edge.get("numeric_target") and int(edge.get("target", 999999)) == sid)
        node["outgoing"] = sum(1 for edge in edges if int(edge.get("source", 999999)) == sid)
        node["missing"] = any(edge.get("missing") and int(edge.get("source", 999999)) == sid for edge in edges)
    present = {int(n["state"]) for n in nodes}
    visible = [edge for edge in edges if edge.get("numeric_target") and int(edge.get("source", 999999)) in present and int(edge.get("target", 999999)) in present and not edge.get("missing")]
    width = max([int(n.get("x", 0)) for n in nodes] + [1200]) + 180
    height = max([int(n.get("y", 0)) for n in nodes] + [800]) + 140
    return {"generated": datetime.now().isoformat(timespec="seconds"), "project": root.name, "nodes": nodes, "states": nodes, "edges": edges, "visible_edges": visible, "warnings": warnings, "total_states": len(states), "total_edges": len(edges), "width": width, "height": height, "truncated": len(states) > len(nodes)}


build_state_graph_canvas_model = make_state_graph_model


def write_state_graph_canvas_pack(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("State Graph Canvas Pack")
    model = make_state_graph_model(root)
    missing = sum(1 for edge in model.get("edges", []) if edge.get("missing"))
    for out in (_out(root, "state_graph_canvas"), _out(root, "visual")):
        _write_json(root, out / "state_graph_canvas_model.json", model, result)
        _write_csv(root, out / "state_graph_nodes.csv", model["nodes"], ["id", "state", "file", "line", "type", "movetype", "physics", "anim", "controllers", "incoming", "outgoing", "missing", "x", "y"], result)
        _write_csv(root, out / "state_graph_edges.csv", model["edges"], ["source", "target_raw", "numeric_target", "missing", "file", "line", "controller"], result)
        rows = "".join(f"<tr><td>{n.get('id')}</td><td>{html.escape(str(n.get('anim', '')))}</td><td>{html.escape(str(n.get('file', '')))}</td><td>{n.get('incoming', 0)}</td><td>{n.get('outgoing', 0)}</td></tr>" for n in model["nodes"])
        _write_text(root, out / "state_graph_canvas.html", f"<!doctype html><meta charset='utf-8'><h1>State Graph Canvas</h1><p>States: {model['total_states']}. Edges: {model['total_edges']}. Missing numeric targets: {missing}.</p><table border='1' cellspacing='0' cellpadding='4'><tr><th>State</th><th>Anim</th><th>File</th><th>In</th><th>Out</th></tr>{rows}</table>", result)
    if missing:
        result.warnings.append(f"State graph contains {missing} missing numeric ChangeState target(s).")
    return result


write_state_graph_canvas_artifacts = write_state_graph_canvas_pack


# ---------------------------------------------------------------------------
# Templates, stage preview, backups
# ---------------------------------------------------------------------------


def validate_template_library(root: Path, source: Optional[Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Template / Plugin Data Validation")
    candidates: List[Path] = []
    if source:
        source = Path(source)
        if source.is_dir():
            candidates.extend(sorted(source.rglob("*.json"), key=lambda p: str(p).lower()))
        elif source.exists() and source.suffix.lower() == ".json":
            candidates.append(source)
    for folder in (root / "templates", root / "plugins", root / "visual_forge" / "templates", root / "forge_beyond" / "templates"):
        if folder.exists():
            candidates.extend(sorted(folder.rglob("*.json"), key=lambda p: str(p).lower()))
    rows: List[Dict[str, object]] = []
    issues: List[Dict[str, object]] = []
    seen: set[Path] = set()
    for index, path in enumerate(candidates, start=1):
        if path in seen:
            continue
        seen.add(path)
        rel = _rel(root, path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(_issue("error", rel, index, "json", f"Could not parse JSON: {exc}"))
            continue
        status = "ok"
        warning = ""
        if not isinstance(data, dict):
            status = "warning"
            warning = "Top-level JSON should be an object."
            keys = ""
        else:
            keys = ", ".join(sorted(str(k) for k in data.keys())[:40])
            text = json.dumps(data, ensure_ascii=False).lower()[:200000]
            for marker in ("subprocess", "os.system", "eval(", "exec(", "__import__"):
                if marker in text:
                    issues.append(_issue("warning", rel, index, "safety", f"Mentions potentially executable behavior: {marker}"))
            if "templates" in data and not isinstance(data.get("templates"), list):
                status = "error"
                warning = "templates must be a list"
            if "plugins" in data:
                for item in data.get("plugins") or []:
                    if isinstance(item, dict) and str(item.get("entry_type", "data-only")).lower() not in {"data-only", "declarative", "metadata"}:
                        issues.append(_issue("warning", rel, index, "plugin", "Executable plugin entry types are not auto-run."))
        rows.append({"file": rel, "status": status, "warning": warning, "keys": keys})
    out = _out(root, "template_validation")
    _write_csv(root, out / "template_plugin_inventory.csv", rows, ["file", "status", "warning", "keys"], result)
    _write_csv(root, out / "template_plugin_validation.csv", issues, ["severity", "file", "row", "field", "message"], result)
    _write_text(root, out / "TEMPLATE_PLUGIN_VALIDATION.md", _issues_markdown("Template / Plugin Validation", issues) + "\n\nData-only manifests are supported. Arbitrary third-party Python plugins are not auto-run.", result)
    if issues:
        result.warnings.append(f"Template validation produced {len(issues)} issue(s)/warning(s).")
    else:
        result.notes.append(f"Validated {len(rows)} template/plugin metadata file(s).")
    return result


validate_template_architecture = validate_template_library


def _safe_template_dest(dest: Path, name: str) -> Optional[Path]:
    rel = Path(str(name).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        return None
    suffix = rel.suffix.lower()
    if suffix in BLOCKED_TEMPLATE_EXTS:
        return None
    if suffix and suffix not in SAFE_TEMPLATE_EXTS:
        return None
    return dest / rel


def import_template_pack(root: Path, pack_path: Path) -> ForgePolishResult:
    root = Path(root)
    source = Path(pack_path)
    result = ForgePolishResult("Safe Template Pack Import")
    if not source.exists():
        result.warnings.append(f"Source not found: {source}")
        return result
    dest = root / "templates" / "imported" / _safe_name(source.stem)[:60]
    if dest.exists():
        dest = dest.with_name(dest.name + "_" + _timestamp())
    copied = 0
    skipped = 0
    if source.is_dir():
        for path in sorted(source.rglob("*"), key=lambda p: str(p).lower()):
            if not path.is_file():
                continue
            target = _safe_template_dest(dest, str(path.relative_to(source)))
            if not target:
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    elif source.suffix.lower() == ".zip":
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                target = _safe_template_dest(dest, member.filename)
                if not target:
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                copied += 1
    else:
        target = _safe_template_dest(dest, source.name)
        if not target:
            result.warnings.append("Template import supports safe data files/folders/ZIPs only.")
            return result
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied = 1
    _write_json(root, dest / "MUGENFORGE_IMPORT_RECORD.json", {"source": str(source), "copied_files": copied, "skipped_files": skipped, "note": "Data-only import; no executable code was run."}, result)
    result.add_created(root, dest)
    result.notes.append(f"Imported {copied} safe template file(s); skipped {skipped} unsafe/unsupported file(s).")
    result.merge(validate_template_library(root), "validation")
    return result


def _stage_image_candidates(root: Path, image_path: Optional[Path] = None) -> List[Path]:
    candidates: List[Path] = []
    if image_path:
        candidates.append(Path(image_path))
    for folder in (root / "stage_authoring" / "source_art", root / "stage_source", root / "source_stage", root / "backgrounds", root / "art" / "stage", root / "stages", root / "sprites", root / "source_sprites"):
        if folder.exists():
            candidates.extend(p for p in sorted(folder.rglob("*"), key=lambda p: str(p).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not candidates:
        candidates.extend(_image_files(root, include_generated=False))
    return [p for p in candidates if p.exists()]


def write_stage_source_art_preview(root: Path, image_path: Optional[Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Stage Source-Art Preview")
    out = _out(root, "stage_preview")
    candidates = _stage_image_candidates(root, image_path)
    if not candidates:
        _write_text(root, out / "STAGE_SOURCE_PREVIEW.md", "# Stage Source Preview\n\nNo stage/source image found. Place source art in `stage_authoring/source_art/`, `stage_source/`, or `art/stage/`.", result)
        result.warnings.append("No stage/source image found.")
        return result
    image = sorted(candidates, key=lambda p: (p.stat().st_size, p.name.lower()), reverse=True)[0]
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        with Image.open(image).convert("RGBA") as src:
            sw, sh = src.size
            scale = min(1.0, 960 / max(1, sw))
            preview = src.copy().resize((max(1, int(sw * scale)), max(1, int(sh * scale)))) if scale < 1 else src.copy()
        draw = ImageDraw.Draw(preview)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 13)
        except Exception:
            font = None
        w, h = preview.size
        z = int(h * 0.82)
        draw.rectangle([0, 0, w - 1, h - 1], outline=(30, 30, 30, 255), width=2)
        draw.line([0, z, w, z], fill=(230, 20, 20, 255), width=3)
        cw, ch = min(w, int(320 * scale)), min(h, int(240 * scale))
        draw.rectangle([(w - cw) // 2, max(0, z - ch), (w + cw) // 2, max(0, z - ch) + ch], outline=(20, 80, 220, 255), width=2)
        draw.text((10, 10), f"{image.name} source={sw}x{sh}", fill=(0, 0, 0, 255), font=font)
        png = out / "stage_source_preview.png"
        preview.convert("RGB").save(png)
    except Exception as exc:
        result.warnings.append(f"Stage preview render failed: {exc}")
        return result
    _write_json(root, out / "stage_preview_manifest.json", {"source_image": _rel(root, image), "source_width": sw, "source_height": sh, "preview": _rel(root, png), "note": "Source-art planning preview only; tune stage bounds/delta/parallax in-engine."}, result)
    _write_text(root, out / "stage_source_preview.html", "<!doctype html><meta charset='utf-8'><h1>Stage Source-Art Preview</h1><p>Red line=zoffset estimate. Blue box=rough localcoord camera guide. Source preview only.</p><img src='stage_source_preview.png' style='max-width:100%;border:1px solid #999'>", result)
    result.add_created(root, png)
    result.notes.append("Wrote stage source-art preview.")
    return result


def build_stage_source_preview(root: Path) -> ForgePolishResult:
    return write_stage_source_art_preview(root)


def list_backup_rows(root: Path) -> List[Dict[str, object]]:
    root = Path(root)
    rows: List[Dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        rel = str(rel_path).replace("\\", "/")
        low = rel.lower()
        is_backup = "backups" in rel_path.parts or ".bak" in path.name.lower() or (path.suffix.lower() == ".zip" and any(word in low for word in ("snapshot", "backup", "release")))
        if not is_backup:
            continue
        target = _guess_restore_target(rel)
        rows.append({"kind": "snapshot zip" if path.suffix.lower() == ".zip" else "file backup", "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"), "bytes": path.stat().st_size, "path": rel, "restore_hint": target})
    rows.sort(key=lambda row: str(row.get("modified", "")), reverse=True)
    return rows


def _guess_restore_target(backup_rel: str) -> str:
    rel = str(backup_rel).replace("\\", "/")
    parts = Path(rel).parts
    for marker in ("forge_polish_file_backups", "visual_forge_file_backups", "forge_beyond_sheet_backups", "forge_polish_restore_guards"):
        if marker in parts:
            tail = list(parts[parts.index(marker) + 1:])
            if tail:
                tail[-1] = re.sub(r"\.bak_[A-Za-z0-9_\-]+_\d{8}_\d{6}$", "", tail[-1])
                tail[-1] = re.sub(r"\.pre_restore_\d{8}_\d{6}$", "", tail[-1])
                return "/".join(tail)
    name = Path(rel).name
    name = re.sub(r"\.bak_[A-Za-z0-9_\-]+_\d{8}_\d{6}$", "", name)
    name = re.sub(r"\.bak_\d{8}_\d{6}$", "", name)
    return name


def write_backup_history(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Backup History Browser")
    rows = list_backup_rows(root)
    out = _out(root, "backup_history")
    _write_csv(root, out / "backup_history.csv", rows, ["modified", "kind", "bytes", "path", "restore_hint"], result)
    _write_json(root, out / "backup_history.json", rows, result)
    table = "".join(f"<tr><td>{html.escape(str(r.get('modified', '')))}</td><td>{html.escape(str(r.get('kind', '')))}</td><td>{r.get('bytes', '')}</td><td><code>{html.escape(str(r.get('path', '')))}</code></td><td><code>{html.escape(str(r.get('restore_hint', '')))}</code></td></tr>" for r in rows[:1000])
    _write_text(root, out / "backup_history.html", f"<!doctype html><meta charset='utf-8'><h1>Backup History</h1><p>Artifacts found: {len(rows)}</p><table border='1' cellspacing='0' cellpadding='4'><tr><th>Modified</th><th>Kind</th><th>Bytes</th><th>Path</th><th>Restore hint</th></tr>{table}</table>", result)
    _write_text(root, out / "BACKUP_HISTORY.md", f"# Backup History\n\nArtifacts found: {len(rows)}. Review restore hints before restoring. Forge Polish creates a pre-restore guard when restoring individual files from the UI.", result)
    result.notes.append(f"Indexed {len(rows)} backup/snapshot artifact(s).")
    return result


def restore_backup_file(root: Path, backup_rel: str | Path, target_rel: Optional[str | Path] = None) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Backup Restore")
    backup = Path(backup_rel)
    if not backup.is_absolute():
        backup = root / backup
    if not backup.exists() or not backup.is_file():
        result.warnings.append(f"Backup file not found: {backup}")
        return result
    if backup.suffix.lower() == ".zip":
        result.warnings.append("ZIP snapshot restore is intentionally not handled here; review and restore snapshots through the snapshot workflow.")
        return result
    target = Path(target_rel) if target_rel else Path(_guess_restore_target(_rel(root, backup)))
    if not target.is_absolute():
        target = root / target
    try:
        target.resolve().relative_to(root.resolve())
    except Exception:
        result.warnings.append("Refusing to restore outside the project root.")
        return result
    if target.exists():
        guard_dir = root / "backups" / "forge_polish_restore_guards"
        try:
            guard_dir = guard_dir / target.parent.relative_to(root)
        except Exception:
            pass
        guard_dir.mkdir(parents=True, exist_ok=True)
        guard = guard_dir / (target.name + f".pre_restore_{_timestamp()}")
        shutil.copy2(target, guard)
        result.add_created(root, guard)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
    result.add_changed(root, target)
    result.notes.append(f"Restored {_rel(root, backup)} to {_rel(root, target)}.")
    return result


# ---------------------------------------------------------------------------
# Bundle and one-click
# ---------------------------------------------------------------------------


def build_forge_polish_bundle(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Forge Polish Reports Bundle")
    out_dir = root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{_safe_name(root.name)}_forge_polish_v4_1_reports.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for base in (root / "forge_polish", root / "docs", root / "templates"):
            if not base.exists():
                continue
            for path in sorted(base.rglob("*"), key=lambda p: str(p).lower()):
                if path.is_file() and path != zip_path and path.suffix.lower() not in {".pyc", ".pyo"}:
                    zf.write(path, path.relative_to(root).as_posix())
        zf.writestr("FORGE_POLISH_BUNDLE_MANIFEST.json", json.dumps({"tool": "MugenForge Studio", "version": FORGE_POLISH_VERSION, "project": root.name, "created": datetime.now().isoformat(timespec="seconds"), "note": "Reports/docs/templates bundle only; gameplay files are not modified by bundling."}, indent=2))
    result.add_created(root, zip_path)
    result.notes.append("Packaged Forge Polish reports only; this is not the playable character release ZIP.")
    return result


def run_forge_polish_pass(root: Path) -> ForgePolishResult:
    root = Path(root)
    result = ForgePolishResult("Forge Polish v4.1 One-Click Pass")
    try:
        result.merge(create_backup_snapshot(root, "forge_polish_v4_1"), "snapshot")
    except Exception as exc:
        result.warnings.append(f"Snapshot failed: {exc}")
    # Export sheets if Forge Beyond is present. Validation remains non-mutating.
    try:
        from .forge_beyond import export_command_sheet, export_air_batch_sheet
        result.merge(export_command_sheet(root), "command sheet export")
        result.merge(export_air_batch_sheet(root), "AIR sheet export")
    except Exception as exc:
        result.warnings.append(f"Forge Beyond sheet export skipped: {exc}")
    for label, func in (("dashboard", write_beginner_next_steps_dashboard), ("command/AIR validation", validate_all_edit_sheets), ("sound cue sheet", export_sound_cue_apply_sheet), ("timeline preview", build_sprite_backed_timeline_preview), ("state graph", write_state_graph_canvas_pack), ("template validation", validate_template_library), ("stage preview", build_stage_source_preview), ("backup history", write_backup_history)):
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.warnings.append(f"{label} failed: {exc}")
    start = """# Forge Polish v4.1 Start Here

Open these first:

1. `forge_polish/BEGINNER_DASHBOARD_v4_1.html`
2. `forge_polish/sheet_validation/COMMAND_SHEET_VALIDATION.md`
3. `forge_polish/sheet_validation/AIR_BATCH_SHEET_VALIDATION.md`
4. `forge_polish/sheets/sound_cue_apply_sheet.csv`
5. `forge_polish/timeline_preview/timeline_contact_sheet.png`
6. `forge_polish/state_graph_canvas/state_graph_canvas.html`
7. `forge_polish/backup_history/backup_history.html`

v4.1 focuses on safer apply previews, visual preview consolidation, sound cue sheet insertion, and backup visibility. It does not add arbitrary mature SFF v2 binary editing/rebuilding.
"""
    _write_text(root, _out(root) / "FORGE_POLISH_START_HERE.md", start, result)
    try:
        result.merge(build_forge_polish_bundle(root), "bundle")
    except Exception as exc:
        result.warnings.append(f"Bundle failed: {exc}")
    result.notes.append("v4.1 focuses on validation previews, sound cue CSV apply, visual previews, graph canvas support, template safety, stage source-art planning, and backup visibility.")
    return result

# Backward-compatible alias for earlier v4.1 polish_lab imports.
list_backup_history = write_backup_history
