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

from .artifact_io import (
    rel_path as _rel,
    timestamp as _timestamp,
    write_csv_artifact,
    write_json_artifact,
    write_text_artifact,
)
from .parsers import (
    COMMON_ANIMS,
    parse_air,
    parse_code,
    parse_def,
    read_text_safely,
    scan_project,
    write_text_safely,
)
from .move_wizard import find_character_file
from .sff_codec import read_sff
from .snd_codec import read_snd
from .visual_forge import create_backup_snapshot, install_template_architecture

FORGE_BEYOND_VERSION = "4.1.0"
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg", ".csv"}
CODE_SUFFIXES = {".cmd", ".cns", ".st"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".snd"}
SKIP_PARTS = {"__pycache__", ".git", ".hg", ".svn"}


@dataclass
class ForgeBeyondResult:
    title: str = "Forge Beyond Result"
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
            vals = getattr(other, attr, []) or []
            getattr(self, attr).extend(prefix + str(v) for v in vals)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def to_text(self) -> str:
        lines = [self.title, "=" * max(12, len(self.title)), f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
        for label, values in (
            ("Notes", self.notes),
            ("Created files/artifacts", self.created_files),
            ("Changed files", self.changed_files),
            ("Skipped", self.skipped_files),
            ("Warnings", self.warnings),
        ):
            if values:
                lines.append(label + ":")
                lines.extend(f"- {v}" for v in _uniq(values))
                lines.append("")
        if len(lines) <= 4:
            lines.append("No changes made.")
        return "\n".join(lines).rstrip() + "\n"


@dataclass
class ImageEditSpec:
    source_folder: Path
    output_folder: Optional[Path] = None
    trim_transparency: bool = True
    mirror_x: bool = False
    mirror_y: bool = False
    scale: float = 1.0
    force_canvas_w: int = 0
    force_canvas_h: int = 0
    output_format: str = "png"
    palette_colors: int = 0


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(name or "")).strip("_") or "project"


def _beyond_dir(root: Path) -> Path:
    out = Path(root) / "forge_beyond"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _docs_dir(root: Path) -> Path:
    out = Path(root) / "docs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _reports_dir(root: Path) -> Path:
    out = _beyond_dir(root) / "reports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _sheets_dir(root: Path) -> Path:
    out = _beyond_dir(root) / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _graphs_dir(root: Path) -> Path:
    out = _beyond_dir(root) / "graphs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(root: Path, path: Path, text: str, result: Optional[ForgeBeyondResult] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, track_existing=True)


def _write_json(root: Path, path: Path, payload: object, result: Optional[ForgeBeyondResult] = None, changed: bool = False) -> Path:
    return write_json_artifact(path, payload, result, root, changed, track_existing=True)


def _write_csv(root: Path, path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], result: Optional[ForgeBeyondResult] = None) -> Path:
    return write_csv_artifact(path, rows, fields, result, root, track_existing=True)


def _backup_text_file(path: Path, root: Path, label: str = "forge_beyond") -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    backup_dir = Path(root) / "backups" / "forge_beyond_sheet_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = path.resolve().relative_to(Path(root).resolve())
    except Exception:
        rel = Path(path.name)
    dst = backup_dir / rel.with_name(rel.name + f".bak_{label}_{_timestamp()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
    return dst


def _all_files(root: Path) -> List[Path]:
    return [p for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and not any(part in SKIP_PARTS for part in p.parts)]


def _code_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root) if p.suffix.lower() in CODE_SUFFIXES and not any(part in {"forge_beyond", "visual_forge", "backups"} for part in p.parts)]


def _image_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root) if p.suffix.lower() in IMAGE_SUFFIXES]


def _wav_files(root: Path) -> List[Path]:
    return [p for p in _all_files(root) if p.suffix.lower() == ".wav"]


def _first_int(value: object, default: int = 0) -> int:
    m = re.search(r"-?\d+", str(value or ""))
    return int(m.group(0)) if m else default


def _category_for_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".cmd", ".cns", ".st", ".def", ".air"}:
        return "mugen text/code"
    if ext == ".sff":
        return "sprite archive"
    if ext == ".snd":
        return "sound archive"
    if ext in IMAGE_SUFFIXES:
        return "source image/sprite"
    if ext in {".wav", ".ogg", ".mp3", ".flac"}:
        return "source audio"
    if ext in {".act", ".pal"}:
        return "palette"
    if ext in {".md", ".txt"}:
        return "documentation"
    if ext in {".json", ".csv", ".ini", ".cfg"}:
        return "metadata"
    return "other"


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {"root": root}
    def_path = root / f"{root.name}.def"
    if not def_path.exists():
        defs = sorted(root.glob("*.def"), key=lambda p: p.name.lower())
        def_path = defs[0] if defs else def_path
    out["def"] = def_path if def_path.exists() else None
    refs: Dict[str, str] = {}
    if out["def"]:
        try:
            files = parse_def(read_text_safely(out["def"])).get("files")
            if files:
                refs = {k.lower(): v.strip().strip('"') for k, v in files.values.items()}
        except Exception:
            refs = {}

    def by_ref(key: str, ext: str) -> Optional[Path]:
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                return p
        exact = root / f"{root.name}.{ext}"
        if exact.exists():
            return exact
        matches = sorted(root.glob(f"*.{ext}"), key=lambda p: p.name.lower())
        return matches[0] if matches else None

    out["cmd"] = by_ref("cmd", "cmd")
    out["cns"] = by_ref("cns", "cns") or by_ref("st", "st")
    out["air"] = by_ref("anim", "air")
    out["sff"] = by_ref("sprite", "sff")
    out["snd"] = by_ref("sound", "snd")
    return out


def _commands_from_project(root: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        if path.suffix.lower() != ".cmd":
            continue
        try:
            scan = parse_code(read_text_safely(path))
        except Exception:
            continue
        for c in scan.commands:
            rows.append({
                "file": _rel(root, path),
                "line": c.line,
                "name": c.name,
                "command": c.command,
                "time": c.time if c.time is not None else "",
                "buffer_time": c.buffer_time if c.buffer_time is not None else "",
                "new_command": c.command,
                "new_time": c.time if c.time is not None else "",
                "new_buffer_time": c.buffer_time if c.buffer_time is not None else "",
                "note": "edit new_* columns only",
            })
    return rows


def _state_controller_rows(root: Path) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    states: List[Dict[str, object]] = []
    controllers: List[Dict[str, object]] = []
    hitdefs: List[Dict[str, object]] = []
    for path in _code_files(root):
        rel = _rel(root, path)
        try:
            scan = parse_code(read_text_safely(path))
        except Exception as exc:
            controllers.append({"file": rel, "line": 0, "state": "", "type": "parse-error", "detail": str(exc)})
            continue
        for st in scan.states:
            states.append({"file": rel, "line": st.line, "state": st.number, "type": st.values.get("type", ""), "movetype": st.values.get("movetype", ""), "physics": st.values.get("physics", ""), "anim": st.values.get("anim", ""), "controllers": len(st.controllers)})
            for ctrl in st.controllers:
                ctype = (ctrl.stype or ctrl.values.get("type", "")).strip()
                detail = ", ".join(f"{k}={v}" for k, v in list(ctrl.values.items())[:10])
                controllers.append({"file": rel, "line": ctrl.line, "state": st.number, "type": ctype, "detail": detail})
                if ctype.lower() == "hitdef":
                    hitdefs.append({
                        "file": rel,
                        "line": ctrl.line,
                        "state": st.number,
                        "anim": st.values.get("anim", ""),
                        "damage": ctrl.values.get("damage", ""),
                        "attr": ctrl.values.get("attr", ""),
                        "hitflag": ctrl.values.get("hitflag", ""),
                        "guardflag": ctrl.values.get("guardflag", ""),
                        "pausetime": ctrl.values.get("pausetime", ""),
                        "hitsound": ctrl.values.get("hitsound", ""),
                        "guardsound": ctrl.values.get("guardsound", ""),
                    })
    return states, controllers, hitdefs


def import_archive_project(archive_path: Path, destination_parent: Path, new_name: Optional[str] = None) -> ForgeBeyondResult:
    result = ForgeBeyondResult("Forge Beyond ZIP Import")
    archive_path = Path(archive_path)
    destination_parent = Path(destination_parent)
    if not archive_path.exists():
        result.warnings.append(f"Archive not found: {archive_path}")
        return result
    if archive_path.suffix.lower() != ".zip":
        result.warnings.append("Only ZIP import is implemented without extra dependencies.")
        return result
    safe = _safe_name(new_name or archive_path.stem)
    dest = destination_parent / safe
    if dest.exists():
        dest = destination_parent / f"{safe}_{_timestamp()}"
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.infolist():
            target = dest / member.filename
            if not target.resolve().is_relative_to(dest.resolve()):
                result.warnings.append(f"Skipped unsafe path in archive: {member.filename}")
                continue
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    result.add_created(dest, dest)
    write_project_organizer_manifest(dest)
    result.notes.append(f"Imported ZIP into {dest}")
    return result


def run_source_image_editor(spec: ImageEditSpec) -> ForgeBeyondResult:
    source = Path(spec.source_folder)
    result = ForgeBeyondResult("Forge Beyond Source Image Editor")
    if not source.exists():
        result.warnings.append(f"Source folder not found: {source}")
        return result
    output = Path(spec.output_folder) if spec.output_folder else source / "forge_beyond_edited"
    output.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageOps  # type: ignore
    except Exception as exc:
        result.warnings.append(f"Pillow is required for image editing: {exc}")
        return result
    rows: List[Dict[str, object]] = []
    for img_path in [p for p in sorted(source.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]:
        try:
            img = Image.open(img_path).convert("RGBA")
            original = img.size
            if spec.trim_transparency:
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
            if spec.mirror_x:
                img = ImageOps.mirror(img)
            if spec.mirror_y:
                img = ImageOps.flip(img)
            scale = float(spec.scale or 1.0)
            if scale > 0 and abs(scale - 1.0) > 0.001:
                img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
            if spec.force_canvas_w > 0 or spec.force_canvas_h > 0:
                cw = max(spec.force_canvas_w, img.width)
                ch = max(spec.force_canvas_h, img.height)
                canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
                canvas.alpha_composite(img, ((cw - img.width) // 2, ch - img.height))
                img = canvas
            fmt = str(spec.output_format or "png").lower().strip(".")
            if fmt not in {"png", "pcx", "bmp"}:
                fmt = "png"
            out_path = output / (img_path.stem + "." + fmt)
            save_img = img
            if spec.palette_colors and spec.palette_colors > 0:
                save_img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=max(2, min(256, int(spec.palette_colors))))
            save_img.save(out_path)
            result.add_created(source, out_path)
            rows.append({"source": str(img_path), "output": str(out_path), "original_w": original[0], "original_h": original[1], "new_w": img.width, "new_h": img.height})
        except Exception as exc:
            result.warnings.append(f"{img_path.name}: {exc}")
    _write_csv(source, output / "image_edit_manifest.csv", rows, ["source", "output", "original_w", "original_h", "new_w", "new_h"], result)
    result.notes.append(f"Edited {len(rows)} image(s) into {output}")
    return result


def write_capability_matrix(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Capability Matrix")
    rows = [
        {"capability": "Project/module workspace", "coverage": "Open/create character folders; stage helpers; many workflow tabs", "status": "Implemented", "honest_notes": "Beginner Home, Creator Hub, Visual Forge, Forge Beyond"},
        {"capability": "Project organizer", "coverage": "File tree, organizer manifests, dependency maps, archive import", "status": "Implemented", "honest_notes": "Clean-room organizer model"},
        {"capability": "Text/code editor", "coverage": "DEF/AIR/CMD/CNS/ST text editing, Code Map, generated snippets", "status": "Implemented", "honest_notes": "Static source editing, not runtime interpreter"},
        {"capability": "Parser/syntax intelligence", "coverage": "DEF, AIR, CMD/CNS/ST commands/controllers, HitDefs, ChangeStates", "status": "Implemented", "honest_notes": "Practical static parser, not engine-perfect"},
        {"capability": "Sprite/SFF viewer", "coverage": "SFF v1 inspection/extract/rebuild from manifests, atlas/contact sheets", "status": "Implemented for supported formats", "honest_notes": "SFF2 remains source bridge/metadata only"},
        {"capability": "Sprite image editor", "coverage": "Source-image trim, resize, mirror, quantize, canvas pad, batch conversion", "status": "Implemented source-based", "honest_notes": "Does not mutate arbitrary SFF2 binaries in place"},
        {"capability": "Palette tools", "coverage": "ACT read/write, image-derived palettes, palette variants", "status": "Implemented", "honest_notes": "Palette accuracy depends on source assets"},
        {"capability": "AIR animation editor", "coverage": "Timeline, animation player, timing manifests, CLSN overlays", "status": "Implemented", "honest_notes": "Playback is an editor preview; playtest in engine"},
        {"capability": "CLSN editor", "coverage": "Visual add/update/delete Clsn1 and Clsn2 with backups", "status": "Implemented", "honest_notes": "Line-aware AIR rewrite remains conservative"},
        {"capability": "Offset/axis tools", "coverage": "AIR offset editing and source axis manifests", "status": "Implemented", "honest_notes": "SFF2 axis mutation is not claimed"},
        {"capability": "Sound/SND tools", "coverage": "SND scan/extract where RIFF payloads are found, WAV manifests, cue editor", "status": "Conservative support", "honest_notes": "Packed/nonstandard SND files may be partial"},
        {"capability": "Move creation", "coverage": "Move Wizard, Move Composer 2.0, presets, kits, starter CMD/CNS/AIR", "status": "Implemented as scaffolding", "honest_notes": "Generated gameplay requires playtesting/tuning"},
        {"capability": "Command spreadsheet editing", "coverage": "Export/apply command/time/buffer CSV edits with backups", "status": "Implemented", "honest_notes": "Only explicit sheet fields are mutated"},
        {"capability": "AIR batch spreadsheet editing", "coverage": "Export/apply group/image/x/y/ticks/flags CSV edits with backups", "status": "Implemented", "honest_notes": "Complements visual timeline; not a renderer"},
        {"capability": "State graph navigation", "coverage": "ChangeState graph CSV/DOT/JSON/HTML outputs", "status": "Implemented", "honest_notes": "Static graph, not runtime trace"},
        {"capability": "Variable usage map", "coverage": "var/fvar/sysvar reference CSVs", "status": "Implemented", "honest_notes": "Helps avoid collisions; does not evaluate expressions"},
        {"capability": "Stage/BG authoring", "coverage": "Stage scanner, stage authoring pack, starter templates", "status": "Implemented as source workflow", "honest_notes": "Not a pixel-perfect camera/parallax simulator"},
        {"capability": "Debug/training helpers", "coverage": "DisplayToClipboard overlay, debugger bridge pack, run/test launcher", "status": "Implemented", "honest_notes": "No memory debugger/data breakpoints"},
        {"capability": "Migration/rescue", "coverage": "Legacy import guidance, rescue scans, source-based recovery packs", "status": "Implemented", "honest_notes": "Destructive binary patching avoided"},
        {"capability": "Plugins/templates", "coverage": "Safe JSON/data manifests, macro packs, no-code template foundation", "status": "Implemented foundation", "honest_notes": "Does not auto-run arbitrary downloaded Python"},
        {"capability": "Full arbitrary SFF2 rebuild/edit", "coverage": "Source-pack bridge via external tools", "status": "Not implemented", "honest_notes": "Explicit limitation retained"},
    ]
    md = [
        "# Forge Beyond Capability Matrix",
        "",
        "This matrix is a clean-room feature implementation ledger. It does not use or reproduce proprietary Fighter Factory/VirtualTek code, assets, or private logic.",
        "",
        "| Capability class | MugenForge v4.0 clean-room coverage | Status | Honest notes |",
        "|---|---|---|---|",
    ]
    for row in rows:
        md.append(f"| {row['capability']} | {row['coverage']} | {row['status']} | {row['honest_notes']} |")
    md += [
        "",
        "## Beyond-first direction",
        "",
        "MugenForge goes beyond a raw asset/code editor by turning production work into beginner-safe, no-code passes: dashboards, task boards, tuning sheets, move composers, migration reports, backup snapshots, release checks, artist/sound handoff packs, and source-based SFF2 projects.",
        "",
        "## Honest limits retained",
        "",
        "- No proprietary Fighter Factory/VirtualTek source, assets, or private implementation logic are used.",
        "- Full arbitrary mature SFF v2 extraction/rebuild/editing is still not implemented.",
        "- Binary mutation remains conservative and source-based when formats are risky.",
        "- Frame data, balance, animation, and debug reports are creator aids, not engine-authoritative truth.",
    ]
    text = "\n".join(md)
    _write_text(root, _docs_dir(root) / "FORGE_BEYOND_CAPABILITY_MATRIX.md", text, result)
    _write_text(root, _reports_dir(root) / "CAPABILITY_MATRIX.md", text, result)
    _write_text(root, _beyond_dir(root) / "capability_matrix.md", text, result)
    _write_json(root, _beyond_dir(root) / "capability_matrix.json", rows, result)
    _write_csv(root, _reports_dir(root) / "capability_matrix.csv", rows, ["capability", "coverage", "status", "honest_notes"], result)
    result.notes.append("Wrote honest clean-room parity/beyond matrix in docs and forge_beyond/reports.")
    return result


def write_project_organizer_manifest(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Project Organizer")
    files: List[Dict[str, object]] = []
    extension_counts: Dict[str, int] = {}
    for p in _all_files(root):
        ext = p.suffix.lower() or "[none]"
        extension_counts[ext] = extension_counts.get(ext, 0) + 1
        files.append({"path": _rel(root, p), "ext": ext, "bytes": p.stat().st_size, "category": _category_for_file(p)})
    refs: Dict[str, Dict[str, str]] = {}
    for d in sorted(root.rglob("*.def"), key=lambda p: str(p).lower()):
        try:
            sec = parse_def(read_text_safely(d)).get("files")
            if sec:
                refs[_rel(root, d)] = dict(sec.values)
        except Exception:
            continue
    payload = {"generated": datetime.now().isoformat(timespec="seconds"), "root": str(root), "extension_counts": extension_counts, "def_references": refs, "files": files}
    out_dir = _beyond_dir(root) / "organizer"
    _write_json(root, out_dir / "project_organizer_manifest.json", payload, result)
    _write_csv(root, out_dir / "project_files.csv", files, ["path", "ext", "bytes", "category"], result)
    md = ["# Forge Beyond Project Organizer", "", "Generated file map and DEF reference map.", "", "## File counts", ""]
    for ext, count in sorted(extension_counts.items()):
        md.append(f"- `{ext}`: {count}")
    _write_text(root, _docs_dir(root) / "FORGE_BEYOND_PROJECT_ORGANIZER.md", "\n".join(md), result)
    result.notes.append(f"Indexed {len(files)} project files across {len(extension_counts)} extension buckets.")
    return result


def write_codesense_report(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond CodeSense")
    commands = _commands_from_project(root)
    states, controllers, hitdefs = _state_controller_rows(root)
    out = _beyond_dir(root) / "codesense"
    _write_csv(root, out / "commands.csv", commands, ["file", "line", "name", "command", "time", "buffer_time", "new_command", "new_time", "new_buffer_time", "note"], result)
    _write_csv(root, out / "states.csv", states, ["file", "line", "state", "type", "movetype", "physics", "anim", "controllers"], result)
    _write_csv(root, out / "controllers.csv", controllers, ["file", "line", "state", "type", "detail"], result)
    _write_csv(root, out / "hitdefs.csv", hitdefs, ["file", "line", "state", "anim", "damage", "attr", "hitflag", "guardflag", "pausetime", "hitsound", "guardsound"], result)
    html_rows = "\n".join(f"<tr><td>{html.escape(str(r.get('state','')))}</td><td>{html.escape(str(r.get('type','')))}</td><td>{html.escape(str(r.get('file','')))}</td><td>{html.escape(str(r.get('line','')))}</td></tr>" for r in states[:500])
    page = f"<!doctype html><meta charset='utf-8'><title>Forge Beyond CodeSense</title><h1>CodeSense</h1><p>Commands: {len(commands)}. States: {len(states)}. Controllers: {len(controllers)}. HitDefs: {len(hitdefs)}.</p><table border='1' cellspacing='0' cellpadding='4'><tr><th>State</th><th>Type</th><th>File</th><th>Line</th></tr>{html_rows}</table>"
    _write_text(root, out / "codesense_index.html", page, result)
    result.notes.append("CodeSense CSV/HTML reports written.")
    return result


def write_asset_deep_audit(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Asset Deep Audit")
    rows: List[Dict[str, object]] = []
    for p in _image_files(root):
        rec = {"file": _rel(root, p), "kind": "image", "bytes": p.stat().st_size, "width": "", "height": "", "mode": "", "note": ""}
        try:
            from PIL import Image  # type: ignore
            with Image.open(p) as im:
                rec.update({"width": im.width, "height": im.height, "mode": im.mode})
        except Exception as exc:
            rec["note"] = str(exc)
        rows.append(rec)
    files = _discover_files(root)
    if files.get("sff") and files["sff"].exists():
        try:
            info = read_sff(files["sff"])
            rows.append({"file": _rel(root, files["sff"]), "kind": "sff", "bytes": files["sff"].stat().st_size, "width": "", "height": "", "mode": info.variant, "note": "; ".join(info.warnings)})
            for spr in info.sprites[:20000]:
                rows.append({"file": _rel(root, files["sff"]), "kind": "sff sprite", "bytes": spr.length, "width": "", "height": "", "mode": spr.format_hint, "note": f"{spr.group},{spr.image} axis=({spr.x},{spr.y}) offset=0x{spr.data_offset:X}"})
        except Exception as exc:
            result.warnings.append(f"SFF audit failed: {exc}")
    if files.get("snd") and files["snd"].exists():
        try:
            info = read_snd(files["snd"])
            rows.append({"file": _rel(root, files["snd"]), "kind": "snd", "bytes": files["snd"].stat().st_size, "width": "", "height": "", "mode": info.version_text, "note": "; ".join(info.warnings)})
            for snd in info.sounds:
                rows.append({"file": _rel(root, files["snd"]), "kind": "snd sound", "bytes": snd.length, "width": snd.channels or "", "height": snd.sample_rate or "", "mode": snd.id_text, "note": "; ".join(snd.warnings)})
        except Exception as exc:
            result.warnings.append(f"SND audit failed: {exc}")
    out = _beyond_dir(root) / "asset_deep_audit"
    _write_csv(root, out / "asset_deep_audit.csv", rows, ["file", "kind", "bytes", "width", "height", "mode", "note"], result)
    result.notes.append(f"Wrote deep asset rows: {len(rows)}.")
    return result


def write_unified_project_index(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Unified Project Index")
    out = _beyond_dir(root)
    result.merge(write_codesense_report(root), "codesense")
    result.merge(write_project_organizer_manifest(root), "organizer")
    result.merge(write_asset_deep_audit(root), "asset audit")
    commands = _commands_from_project(root)
    states, controllers, _hitdefs = _state_controller_rows(root)
    image_count = len(_image_files(root))
    wav_count = len(_wav_files(root))
    links = [
        ("Capability Matrix", "reports/CAPABILITY_MATRIX.md"),
        ("Project Organizer", "organizer/project_organizer_manifest.json"),
        ("CodeSense HTML", "codesense/codesense_index.html"),
        ("Asset Deep Audit", "asset_deep_audit/asset_deep_audit.csv"),
        ("Command Sheet", "sheets/command_editor_sheet.csv"),
        ("AIR Batch Sheet", "sheets/air_batch_editor_sheet.csv"),
        ("State Graph", "graphs/state_graph.html"),
        ("Variable Usage Map", "maps/variable_usage.csv"),
        ("Sprite/Sound Cross Ref", "cross_reference/sprite_sound_cross_reference.md"),
        ("Template Foundation", "templates/README.md"),
        ("Stage Authoring Pack", "stage_authoring/STAGE_AUTHORING_PACK.md"),
    ]
    cards = "\n".join(f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>' for label, href in links)
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Forge Beyond Unified Project Index</title>
<style>body{{font-family:system-ui,Segoe UI,sans-serif;margin:24px;}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;}} .card{{border:1px solid #ccc;border-radius:8px;padding:12px;background:#fafafa;}} code{{background:#eee;padding:2px 4px;}}</style>
</head><body>
<h1>Forge Beyond Unified Project Index</h1>
<p>Project: <code>{html.escape(str(root))}</code></p>
<div class="grid">
<div class="card"><h2>Code</h2><p>Commands: {len(commands)}<br>States: {len(states)}<br>Controllers: {len(controllers)}</p></div>
<div class="card"><h2>Assets</h2><p>Images: {image_count}<br>WAV files: {wav_count}</p></div>
<div class="card"><h2>Scope</h2><p>Clean-room workflows. SFF2 binary rebuild remains source-based/honest.</p></div>
</div>
<h2>Generated reports</h2><ul>{cards}</ul>
</body></html>"""
    _write_text(root, out / "UNIFIED_PROJECT_INDEX.html", page, result)
    md = ["# Forge Beyond Unified Project Index", "", "Open `UNIFIED_PROJECT_INDEX.html` for linked generated reports.", "", f"- Commands: {len(commands)}", f"- States: {len(states)}", f"- Controllers: {len(controllers)}", f"- Source images: {image_count}", f"- WAV files: {wav_count}"]
    md_text = "\n".join(md)
    _write_text(root, out / "UNIFIED_PROJECT_INDEX.md", md_text, result)
    _write_text(root, _reports_dir(root) / "UNIFIED_PROJECT_INDEX.md", md_text, result)
    dashboard = ["# Forge Beyond Dashboard", "", "Start here after running the parity+ pass.", "", "- Open `UNIFIED_PROJECT_INDEX.html` for a linked cockpit.", "- Open `reports/CAPABILITY_MATRIX.md` for capability coverage and honest limits.", "- Edit `sheets/command_editor_sheet.csv` or `sheets/air_batch_editor_sheet.csv` only after making/keeping backups."]
    _write_text(root, out / "FORGE_BEYOND_DASHBOARD.md", "\n".join(dashboard), result)
    result.notes.append("Unified index links major Forge Beyond outputs in one place.")
    return result


def export_command_sheet(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Command Sheet Export")
    rows = _commands_from_project(root)
    out = _sheets_dir(root) / "command_editor_sheet.csv"
    _write_csv(root, out, rows, ["file", "line", "name", "command", "time", "buffer_time", "new_command", "new_time", "new_buffer_time", "note"], result)
    result.notes.append(f"Exported {len(rows)} command rows. Edit only new_command/new_time/new_buffer_time, then apply with backups.")
    return result


def _replace_command_block(block: str, row: Dict[str, str]) -> str:
    def sub_or_add(text: str, key: str, value: str) -> str:
        if value is None or str(value).strip() == "":
            return text
        pat = re.compile(r"(^\s*" + re.escape(key) + r"\s*=\s*)(.*?)(\s*(?:;.*)?$)", re.I | re.M)
        if pat.search(text):
            return pat.sub(lambda m: m.group(1) + str(value).strip() + m.group(3), text, count=1)
        return text.rstrip() + f"\n{key} = {str(value).strip()}\n"
    block = sub_or_add(block, "command", row.get("new_command", ""))
    block = sub_or_add(block, "time", row.get("new_time", ""))
    if str(row.get("new_buffer_time", "")).strip():
        block = sub_or_add(block, "buffer.time", str(row.get("new_buffer_time", "")).strip())
    return block


def apply_command_sheet(root: Path, sheet_path: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Command Sheet Apply")
    sheet_path = Path(sheet_path)
    if not sheet_path.exists():
        result.warnings.append(f"Sheet not found: {sheet_path}")
        return result
    rows: List[Dict[str, str]] = []
    with sheet_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_file: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        file_rel = (row.get("file") or "").strip()
        name = (row.get("name") or "").strip()
        if file_rel and name:
            by_file.setdefault(file_rel, []).append(row)
    cmd_section_re = re.compile(r"(^\s*\[\s*Command\s*\]\s*$.*?)(?=^\s*\[|\Z)", re.I | re.M | re.S)
    name_re = re.compile(r"^\s*name\s*=\s*\"?([^\"\n;]+)\"?", re.I | re.M)
    changed = 0
    for rel, file_rows in by_file.items():
        path = root / rel
        if not path.exists() or path.suffix.lower() != ".cmd":
            result.warnings.append(f"Skipped missing/non-CMD file: {rel}")
            continue
        text = read_text_safely(path)
        wanted = {str(row.get("name", "")).strip(): row for row in file_rows}
        def repl(match):
            nonlocal changed
            block = match.group(1)
            nm = name_re.search(block)
            if not nm:
                return block
            row = wanted.get(nm.group(1).strip())
            if not row:
                return block
            new_block = _replace_command_block(block, row)
            if new_block != block:
                changed += 1
            return new_block
        new_text = cmd_section_re.sub(repl, text)
        if new_text != text:
            _backup_text_file(path, root, "command_sheet")
            write_text_safely(path, new_text)
            result.add_changed(root, path)
        else:
            result.skipped_files.append(f"{rel}: no command changes detected")
    result.notes.append(f"Applied command sheet changes to {changed} command block(s).")
    return result


def export_air_batch_sheet(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond AIR Batch Sheet Export")
    out = _sheets_dir(root) / "air_batch_editor_sheet.csv"
    air = find_character_file(root, "air")
    rows: List[Dict[str, object]] = []
    if air and air.exists():
        try:
            from .air_tools import parse_air_with_lines
            actions = parse_air_with_lines(read_text_safely(air))
            for action in actions:
                for frame in action.frames:
                    rows.append({"file": _rel(root, air), "line_index": frame.line_index, "action": frame.action_number, "frame_index": frame.frame_index, "group": frame.group, "image": frame.image, "x": frame.x, "y": frame.y, "ticks": frame.ticks, "flags": frame.flags, "new_group": frame.group, "new_image": frame.image, "new_x": frame.x, "new_y": frame.y, "new_ticks": frame.ticks, "new_flags": frame.flags, "note": "edit new_* columns only"})
        except Exception as exc:
            result.warnings.append(f"AIR sheet export failed: {exc}")
    else:
        result.warnings.append("No AIR file found.")
    _write_csv(root, out, rows, ["file", "line_index", "action", "frame_index", "group", "image", "x", "y", "ticks", "flags", "new_group", "new_image", "new_x", "new_y", "new_ticks", "new_flags", "note"], result)
    result.notes.append(f"Exported {len(rows)} AIR frame rows. Edit only new_* columns, then apply with backups.")
    return result


def _intish(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def apply_air_batch_sheet(root: Path, sheet_path: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond AIR Batch Sheet Apply")
    sheet_path = Path(sheet_path)
    if not sheet_path.exists():
        result.warnings.append(f"Sheet not found: {sheet_path}")
        return result
    with sheet_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_file: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        rel = (row.get("file") or "").strip()
        if rel:
            by_file.setdefault(rel, []).append(row)
    changed_lines = 0
    for rel, file_rows in by_file.items():
        path = root / rel
        if not path.exists() or path.suffix.lower() != ".air":
            result.warnings.append(f"Skipped missing/non-AIR file: {rel}")
            continue
        lines = read_text_safely(path).splitlines()
        changed = False
        for row in file_rows:
            idx = _intish(row.get("line_index"), -1)
            if idx < 0 or idx >= len(lines):
                continue
            group = _intish(row.get("new_group") or row.get("group"), _intish(row.get("group"), 0))
            image = _intish(row.get("new_image") or row.get("image"), _intish(row.get("image"), 0))
            x = _intish(row.get("new_x") or row.get("x"), _intish(row.get("x"), 0))
            y = _intish(row.get("new_y") or row.get("y"), _intish(row.get("y"), 0))
            ticks = _intish(row.get("new_ticks") or row.get("ticks"), _intish(row.get("ticks"), 1))
            flags = str(row.get("new_flags") or row.get("flags") or "").strip()
            new_line = f"{group}, {image}, {x}, {y}, {ticks}" + (f", {flags}" if flags else "")
            if lines[idx].strip() != new_line.strip():
                lines[idx] = new_line
                changed = True
                changed_lines += 1
        if changed:
            _backup_text_file(path, root, "air_batch_sheet")
            write_text_safely(path, "\n".join(lines).rstrip() + "\n")
            result.add_changed(root, path)
        else:
            result.skipped_files.append(f"{rel}: no AIR frame changes detected")
    result.notes.append(f"Applied AIR batch changes to {changed_lines} frame line(s).")
    return result


def write_state_graph(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond State Graph")
    out_dir = _graphs_dir(root)
    edges: List[Dict[str, object]] = []
    states = set()
    for path in _code_files(root):
        rel = _rel(root, path)
        try:
            scan = parse_code(read_text_safely(path))
        except Exception as exc:
            result.warnings.append(f"Could not parse {rel}: {exc}")
            continue
        for st in scan.states:
            states.add(st.number)
            for ctrl in st.controllers:
                stype = (ctrl.stype or ctrl.values.get("type", "")).lower()
                if stype == "changestate" and "value" in ctrl.values:
                    edges.append({"source": st.number, "target": ctrl.values.get("value", ""), "file": rel, "line": ctrl.line, "controller": ctrl.header})
    _write_csv(root, out_dir / "state_graph_edges.csv", edges, ["source", "target", "file", "line", "controller"], result)
    dot = ["digraph mugen_states {", "  rankdir=LR;", "  node [shape=box];"]
    for st in sorted(states):
        dot.append(f"  s{st} [label=\"State {st}\"];")
    for edge in edges:
        target = str(edge.get("target", "")).strip()
        if re.fullmatch(r"-?\d+", target):
            dot.append(f"  s{edge['source']} -> s{target} [label=\"line {edge['line']}\"];")
    dot.append("}")
    _write_text(root, out_dir / "state_graph.dot", "\n".join(dot), result)
    _write_json(root, out_dir / "state_graph.json", {"states": sorted(states), "edges": edges}, result)
    rows = "\n".join(f"<tr><td>{html.escape(str(e['source']))}</td><td>{html.escape(str(e['target']))}</td><td>{html.escape(str(e['file']))}</td><td>{html.escape(str(e['line']))}</td><td>{html.escape(str(e['controller']))}</td></tr>" for e in edges[:1000])
    page = f"<!doctype html><meta charset='utf-8'><title>Forge Beyond State Graph</title><h1>Forge Beyond State Graph</h1><p>States: {len(states)}. ChangeState edges: {len(edges)}.</p><table border='1' cellspacing='0' cellpadding='4'><tr><th>Source</th><th>Target</th><th>File</th><th>Line</th><th>Controller</th></tr>{rows}</table>"
    _write_text(root, out_dir / "state_graph.html", page, result)
    result.notes.append("State graph exports written: CSV, DOT, JSON, and HTML.")
    return result


def write_variable_usage_map(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Variable Usage Map")
    rows: List[Dict[str, object]] = []
    rx = re.compile(r"\b(f?var|sysvar|sysfvar)\s*\(\s*(-?\d+)\s*\)", re.I)
    for path in _code_files(root):
        try:
            for lineno, line in enumerate(read_text_safely(path).splitlines(), start=1):
                for m in rx.finditer(line):
                    rows.append({"file": _rel(root, path), "line": lineno, "kind": m.group(1).lower(), "index": m.group(2), "text": line.strip()[:220]})
        except Exception:
            continue
    out = _beyond_dir(root) / "maps"
    _write_csv(root, out / "variable_usage.csv", rows, ["file", "line", "kind", "index", "text"], result)
    _write_text(root, out / "VARIABLE_USAGE_MAP.md", f"# Forge Beyond Variable Usage Map\n\nRows: {len(rows)}\n\nUse this to find var/fvar/sysvar collisions before adding new systems.", result)
    result.notes.append(f"Mapped {len(rows)} variable references.")
    return result


def write_sprite_sound_cross_reference(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Sprite/Sound Cross Reference")
    out = _beyond_dir(root) / "cross_reference"
    air_refs: List[Dict[str, object]] = []
    sprite_pairs = set()
    air = find_character_file(root, "air")
    if air and air.exists():
        try:
            for action in parse_air(read_text_safely(air)):
                for frame in action.frames:
                    if frame.group >= 0 and frame.image >= 0:
                        sprite_pairs.add((frame.group, frame.image))
                        air_refs.append({"action": action.number, "group": frame.group, "image": frame.image, "x": frame.x, "y": frame.y, "ticks": frame.ticks})
        except Exception as exc:
            result.warnings.append(f"AIR sprite ref parse failed: {exc}")
    sff_keys = set()
    files = _discover_files(root)
    if files.get("sff") and files["sff"].exists():
        try:
            info = read_sff(files["sff"])
            sff_keys = {spr.key for spr in info.sprites}
            if info.variant.startswith("sff2"):
                result.warnings.append("SFF v2/non-v1 detected: cross-reference uses metadata only where available.")
        except Exception as exc:
            result.warnings.append(f"SFF read failed: {exc}")
    missing = sorted(sprite_pairs - sff_keys) if sff_keys else sorted(sprite_pairs)
    sound_rows: List[Dict[str, object]] = []
    sound_ref_re = re.compile(r"(?:value|hitsound|guardsound)\s*=\s*(-?\d+)\s*,\s*(-?\d+)", re.I)
    for path in _code_files(root):
        try:
            for lineno, line in enumerate(read_text_safely(path).splitlines(), start=1):
                for m in sound_ref_re.finditer(line):
                    sound_rows.append({"file": _rel(root, path), "line": lineno, "group": m.group(1), "sound": m.group(2), "text": line.strip()[:220]})
        except Exception:
            continue
    _write_csv(root, out / "air_sprite_refs.csv", air_refs, ["action", "group", "image", "x", "y", "ticks"], result)
    _write_csv(root, out / "sound_refs.csv", sound_rows, ["file", "line", "group", "sound", "text"], result)
    _write_csv(root, out / "missing_sprite_refs.csv", [{"group": g, "image": i} for g, i in missing], ["group", "image"], result)
    md = ["# Forge Beyond Sprite/Sound Cross Reference", "", f"AIR sprite references: {len(air_refs)}", f"Unique AIR sprite pairs: {len(sprite_pairs)}", f"SFF indexed pairs: {len(sff_keys)}", f"Missing sprite references: {len(missing)}", f"Sound references in code: {len(sound_rows)}", "", "This is an editor-side cross-reference. SFF2/non-v1 files may expose metadata only."]
    _write_text(root, out / "sprite_sound_cross_reference.md", "\n".join(md), result)
    if missing:
        result.warnings.append(f"AIR references {len(missing)} sprite pairs not found in indexed SFF metadata/source.")
    result.notes.append("Cross-reference CSV/Markdown files written.")
    return result


def install_safe_macro_pack(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Safe Macro Pack")
    out = _beyond_dir(root) / "safe_macros"
    macros = {
        "schema": "mugenforge.forge_beyond.safe_macros.v1",
        "execution_model": "data-only",
        "macros": [
            {"id": "generate_index", "label": "Generate project index", "description": "Writes reports; does not mutate gameplay files."},
            {"id": "export_command_sheet", "label": "Export command sheet", "description": "Creates editable CSV."},
            {"id": "export_air_sheet", "label": "Export AIR batch sheet", "description": "Creates editable CSV."},
        ],
    }
    _write_json(root, out / "safe_macro_pack.json", macros, result)
    _write_text(root, out / "README.md", "# Forge Beyond Safe Macro Pack\n\nData-only macros. MugenForge does not auto-run arbitrary downloaded code.", result)
    return result


def write_template_plugin_foundation(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Template / Plugin Foundation")
    try:
        result.merge(install_template_architecture(root), "Visual Forge templates")
    except Exception as exc:
        result.warnings.append(f"Visual Forge template foundation failed: {exc}")
    result.merge(install_safe_macro_pack(root), "safe macros")
    out = _beyond_dir(root) / "templates"
    manifest = {"schema": "mugenforge.forge_beyond.templates.v1", "version": FORGE_BEYOND_VERSION, "execution_model": "declarative-first", "safe_policy": ["Preview generated changes before applying.", "Back up files before mutation.", "Do not auto-run arbitrary downloaded Python code.", "Keep SFF2 rebuild work source-based unless a real implementation is added."], "template_types": ["move", "system", "stage", "sound-cue", "palette", "release-check"]}
    _write_json(root, out / "forge_beyond_template_manifest.json", manifest, result)
    _write_text(root, out / "README.md", "# Forge Beyond Template / Plugin Foundation\n\nDeclarative templates and macros for no-code expansion. Arbitrary downloaded Python plugins are not auto-executed.", result)
    result.notes.append("Template/plugin foundation installed with metadata-first safety rules.")
    return result


def write_stage_authoring_pack(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Stage Authoring Pack")
    out = _beyond_dir(root) / "stage_authoring"
    starter_name = _safe_name(Path(root).name + "_stage")
    def_text = f"""; Forge Beyond starter stage source
[Info]
name = "{starter_name}"
displayname = "{starter_name}"
author = "MugenForge Creator"

[Camera]
startx = 0
starty = 0
boundleft = -320
boundright = 320
boundhigh = -240
boundlow = 0
verticalfollow = .2
floortension = 60
tension = 50

[PlayerInfo]
p1startx = -70
p1starty = 0
p1facing = 1
p2startx = 70
p2starty = 0
p2facing = -1

[StageInfo]
zoffset = 210
autoturn = 1
resetBG = 1
localcoord = 320,240

[Shadow]
intensity = 96
color = 0,0,0
yscale = .4

[Music]
bgmusic =
bgvolume = 0

[BGDef]
spr = stage_source.sff
debugbg = 0

[BG 0]
type = normal
spriteno = 0,0
start = 0,0
delta = 1,1
mask = 0
"""
    _write_text(root, out / f"{starter_name}.def", def_text, result)
    _write_text(root, out / "STAGE_AUTHORING_PACK.md", "# Stage Authoring Pack\n\n- Replace placeholder art with clean source images.\n- Verify zoffset against character feet/axis.\n- Tune camera bounds in-engine.\n- Keep source images and manifests outside packed binaries.\n", result)
    (out / "source_images").mkdir(parents=True, exist_ok=True)
    result.add_created(root, out / "source_images")
    result.notes.append("Stage authoring pack created.")
    return result


def write_animation_interpolation_report(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Animation Timing Audit")
    rows: List[Dict[str, object]] = []
    air = find_character_file(root, "air")
    if air and air.exists():
        for action in parse_air(read_text_safely(air)):
            total = sum(max(0, f.ticks) for f in action.frames)
            rows.append({"action": action.number, "frames": len(action.frames), "ticks": total, "avg_ticks": round(total / len(action.frames), 2) if action.frames else 0, "label": action.label})
    out = _beyond_dir(root) / "animation"
    _write_csv(root, out / "animation_timing_audit.csv", rows, ["action", "frames", "ticks", "avg_ticks", "label"], result)
    return result


def write_debugger_bridge_pack(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Debugger Bridge Pack")
    out = _beyond_dir(root) / "debugger_bridge"
    guide = "# Debugger Bridge Pack\n\nUse Training Debug overlays, Run/Test helper, and M.U.G.E.N logs to verify behavior. This pack is not a memory debugger.\n"
    _write_text(root, out / "DEBUGGER_BRIDGE_PACK.md", guide, result)
    return result


def write_sound_waveform_board(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Sound Board")
    rows: List[Dict[str, object]] = []
    for p in _wav_files(root):
        rows.append({"file": _rel(root, p), "bytes": p.stat().st_size, "note": "WAV indexed; waveform rendering available in existing Creator/Ultra tools where Pillow/wave support exists."})
    out = _beyond_dir(root) / "sound_board"
    _write_csv(root, out / "sound_board.csv", rows, ["file", "bytes", "note"], result)
    return result


def build_forge_beyond_release_bundle(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Reports Bundle")
    base = _beyond_dir(root)
    if not base.exists():
        result.merge(run_forge_beyond_pass(root), "generate first")
    zip_path = base / f"{_safe_name(root.name)}_forge_beyond_reports_{_timestamp()}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(base.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(root))
    result.add_created(root, zip_path)
    result.notes.append("Packaged Forge Beyond reports, sheets, graphs, and template metadata. This is not the playable character release ZIP.")
    return result


def run_forge_beyond_pass(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond One-Click Parity+ Pass")
    try:
        result.merge(create_backup_snapshot(root), "backup snapshot")
    except Exception as exc:
        result.warnings.append(f"Snapshot failed: {exc}")
    for label, fn in [
        ("capability matrix", write_capability_matrix),
        ("unified project index", write_unified_project_index),
        ("command sheet", export_command_sheet),
        ("air batch sheet", export_air_batch_sheet),
        ("state graph", write_state_graph),
        ("variable usage map", write_variable_usage_map),
        ("sprite/sound cross reference", write_sprite_sound_cross_reference),
        ("template/plugin foundation", write_template_plugin_foundation),
        ("stage authoring pack", write_stage_authoring_pack),
        ("animation timing audit", write_animation_interpolation_report),
        ("sound board", write_sound_waveform_board),
        ("debugger bridge", write_debugger_bridge_pack),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.warnings.append(f"{label} failed: {exc}")
    dashboard = [
        "# Forge Beyond Dashboard",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Start here",
        "",
        "1. Open `UNIFIED_PROJECT_INDEX.html`.",
        "2. Review `reports/CAPABILITY_MATRIX.md` for ready/partial capabilities.",
        "3. Edit command/AIR batch CSVs only after making a backup.",
        "4. Use sprite/sound cross-reference to resolve missing assets.",
        "5. Use stage authoring and template folders for source-first expansion.",
        "",
        "## Honest limits retained",
        "",
        "- Full arbitrary mature SFF v2 extraction/rebuild is not implemented.",
        "- SFF2 work remains source-project/bridge based.",
        "- Generated gameplay must be playtested in-engine.",
        "- Frame/balance reports are estimates, not engine-authoritative.",
        "- Third-party plugin execution remains disabled by default.",
    ]
    _write_text(root, _beyond_dir(root) / "FORGE_BEYOND_DASHBOARD.md", "\n".join(dashboard), result)
    result.notes.append("Forge Beyond v4.0 parity+ pass completed with clean-room workflows and honest capability limits.")
    return result

# Public v4.0 compatibility helpers appended by package builder.
def capability_rows() -> List[Dict[str, object]]:
    return [
        {"area": "Project shell", "status": "implemented", "where": "Project Home / Wizard / file tree"},
        {"area": "Code editor", "status": "implemented + v4 sheets", "where": "Editor / Code Map / CodeSense / command sheet"},
        {"area": "AIR animation", "status": "implemented", "where": "AIR Timeline / Animation Player / AIR batch sheet"},
        {"area": "CLSN", "status": "implemented", "where": "CLSN Editor"},
        {"area": "SFF/SND", "status": "conservative", "where": "Sprite/Sound browsers, source bridge, cross refs"},
        {"area": "Stage/BG", "status": "source-authoring pack", "where": "Forge Beyond Stage Authoring Pack"},
        {"area": "Templates/plugins", "status": "data-first foundation", "where": "Forge Beyond Template / Plugin Foundation"},
        {"area": "Release/reporting", "status": "implemented", "where": "Forge Beyond Reports Bundle"},
    ]


def write_forge_beyond_start_here(root: Path) -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Start Here")
    text = """# Forge Beyond Start Here

Run **Forge Beyond → One-Click Parity+ Pass**, then inspect:

1. `forge_beyond/FORGE_BEYOND_DASHBOARD.md`
2. `forge_beyond/reports/CAPABILITY_MATRIX.md`
3. `forge_beyond/reports/UNIFIED_PROJECT_INDEX.md`
4. `forge_beyond/sheets/command_editor_sheet.csv`
5. `forge_beyond/sheets/air_batch_editor_sheet.csv`
6. `forge_beyond/graphs/state_graph.html`

Honest boundaries remain: no proprietary source/assets, no arbitrary mature SFF2 binary rewrite claim, and gameplay scaffolds require M.U.G.E.N playtesting.
"""
    _write_text(root, Path(root) / "docs" / "FORGE_BEYOND_START_HERE.md", text, result)
    return result


def create_beyond_snapshot(root: Path, label: str = "manual") -> ForgeBeyondResult:
    root = Path(root)
    result = ForgeBeyondResult("Forge Beyond Snapshot")
    try:
        result.merge(create_backup_snapshot(root), "visual forge snapshot")
    except Exception as exc:
        result.warnings.append(f"Visual Forge snapshot failed: {exc}")
    return result


def build_forge_beyond_release_zip(root: Path) -> ForgeBeyondResult:
    return build_forge_beyond_release_bundle(root)
