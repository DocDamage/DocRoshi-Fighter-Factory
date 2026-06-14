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
from typing import Dict, Iterable, List, Optional, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .automation_bank import ApplyResult, auto_setup_project, beginner_project_status, feature_bank_stats_text, make_placeholder_sprite_sheet
from .sff_codec import read_sff, sprite_lookup, build_sff_v1_from_manifest
from .snd_codec import make_placeholder_sound_bank, build_snd_from_manifest

FACTORY_PLUS_VERSION = "2.4.0"


from .shared_utils import BaseResult, uniq, rel_path, backup_file

@dataclass
class FactoryPlusResult(BaseResult):
    title: str = "Factory+ Result"

    def merge_apply(self, result: ApplyResult, prefix: str = "") -> None:
        p = (prefix + ": ") if prefix else ""
        self.changed_files += [p + item for item in result.changed_files]
        self.created_files += [p + item for item in result.created_files]
        self.skipped_files += [p + item for item in result.skipped_files]
        self.warnings += [p + item for item in result.warnings]


@dataclass
class CharacterFiles:
    root: Path
    def_path: Optional[Path] = None
    cmd_path: Optional[Path] = None
    cns_path: Optional[Path] = None
    air_path: Optional[Path] = None
    sff_path: Optional[Path] = None
    snd_path: Optional[Path] = None


def _backup(path: Path) -> Optional[Path]:
    return backup_file(path, "factory")


def _rel(root: Path, path: Path) -> str:
    return rel_path(root, path)


def _first(root: Path, suffix: str) -> Optional[Path]:
    files = sorted(root.glob(f"*{suffix}"), key=lambda p: p.name.lower())
    return files[0] if files else None


def discover_character_files(root: Path) -> CharacterFiles:
    root = Path(root)
    files = CharacterFiles(root=root)
    files.def_path = _first(root, ".def")
    refs: Dict[str, str] = {}
    if files.def_path and files.def_path.exists():
        try:
            sections = parse_def(read_text_safely(files.def_path))
            ref_section = sections.get("files")
            if ref_section:
                refs = {k.lower(): v.strip().strip('"') for k, v in ref_section.values.items()}
        except Exception:
            refs = {}

    def ref_path(key: str, fallback_ext: str) -> Optional[Path]:
        val = refs.get(key)
        if val:
            p = (root / val).resolve()
            if p.exists():
                return p
        return _first(root, fallback_ext)

    files.cmd_path = ref_path("cmd", ".cmd")
    # Elecbyte DEFs may use cns = main.cns and/or stcommon/st1/st2. Prefer cns, fall back to first .st.
    files.cns_path = ref_path("cns", ".cns") or _first(root, ".st")
    files.air_path = ref_path("anim", ".air")
    files.sff_path = ref_path("sprite", ".sff")
    files.snd_path = ref_path("sound", ".snd")
    return files


def _append_unique(path: Path, marker: str, block: str, result: FactoryPlusResult) -> bool:
    old = read_text_safely(path) if path.exists() else ""
    if marker in old:
        result.skipped_files.append(f"{path.name}: marker already installed ({marker})")
        return False
    if path.exists():
        b = _backup(path)
        if b:
            result.notes.append(f"Backup written: {b.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    glue = "" if not old or old.endswith("\n") else "\n"
    write_text_safely(path, old + glue + block.rstrip() + "\n")
    result.changed_files.append(path.name)
    return True


def _action_block(action_no: int, label: str, frames: int = 4, ticks: int = 6, group: Optional[int] = None) -> str:
    group = action_no if group is None else group
    # Conservative body box; users can drag it in the visual CLSN editor.
    if action_no in {12, 140, 5020}:
        body = (-22, -58, 22, 0)
    elif action_no in {5100, 5150}:
        body = (-44, -18, 44, 4)
    else:
        body = (-20, -88, 20, 0)
    lines = [f"; Factory+ auto-created missing action: {label}", f"[Begin Action {action_no}] ; {label}"]
    for i in range(max(1, frames)):
        lines.append("Clsn2: 1")
        lines.append(f"  Clsn2[0] = {body[0]},{body[1]},{body[2]},{body[3]}")
        lines.append(f"{group}, {i}, 0, 0, {max(1, ticks)}")
    return "\n".join(lines) + "\n"


def ensure_required_animations(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Required Animation Repair")
    files = discover_character_files(root)
    if not files.air_path:
        result.merge_apply(auto_setup_project(root), "auto setup")
        files = discover_character_files(root)
    if not files.air_path:
        result.warnings.append("No AIR file found or created.")
        return result
    text = read_text_safely(files.air_path) if files.air_path.exists() else ""
    existing = {a.number for a in parse_air(text)}
    required = [0, 5, 10, 11, 12, 20, 21, 40, 41, 42, 47, 100, 105, 120, 130, 140, 150, 5000, 5010, 5020, 5030, 5050, 5070, 5100, 5110, 5150]
    missing = [num for num in required if num not in existing]
    if not missing:
        result.skipped_files.append(f"{files.air_path.name}: all common required actions already exist")
        return result
    block_lines = ["", "; MugenForge Factory+ Required Animation Repair", "; These are safe placeholder actions. Replace art and adjust boxes visually.", ""]
    for num in missing:
        label = COMMON_ANIMS.get(num, f"action {num}")
        frames = 6 if num in {20, 21, 100, 105, 5110} else 3
        block_lines.append(_action_block(num, label, frames=frames, ticks=6))
    marker = "; MugenForge Factory+ Required Animation Repair"
    _append_unique(files.air_path, marker, "\n".join(block_lines), result)
    result.notes.append(f"Added {len(missing)} missing common AIR actions.")
    return result


def _air_sprite_pairs(root: Path) -> List[Tuple[int, int]]:
    files = discover_character_files(root)
    if not files.air_path or not files.air_path.exists():
        return []
    pairs: List[Tuple[int, int]] = []
    seen = set()
    for action in parse_air(read_text_safely(files.air_path)):
        for frame in action.frames:
            key = (frame.group, frame.image)
            if key not in seen:
                seen.add(key)
                pairs.append(key)
    return pairs


def rebuild_placeholder_sff_from_air(root: Path, out_name: Optional[str] = None) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Placeholder SFF From AIR")
    pairs = _air_sprite_pairs(root)
    if not pairs:
        result.warnings.append("No AIR sprite references found. Run Auto Setup/Feature Bank first.")
        return result
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        result.warnings.append(f"Pillow is required to generate placeholder SFF images: {exc}")
        return result
    staged = root / "factory_plus_staged_sprites"
    staged.mkdir(parents=True, exist_ok=True)
    records = []
    for idx, (group, image) in enumerate(pairs):
        img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        base = ((group * 41 + image * 17) % 180 + 45, (group * 29 + image * 31) % 180 + 45, (group * 11 + image * 53) % 180 + 45, 255)
        draw.rectangle((14, 18, 82, 90), outline=base, width=3)
        draw.ellipse((35, 8, 61, 34), outline=base, width=3)
        draw.line((48, 34, 48, 70), fill=base, width=3)
        draw.line((48, 44, 26, 60), fill=base, width=3)
        draw.line((48, 44, 70, 60), fill=base, width=3)
        draw.line((48, 70, 31, 90), fill=base, width=3)
        draw.line((48, 70, 65, 90), fill=base, width=3)
        draw.text((4, 4), f"{group},{image}", fill=base)
        filename = f"g{group:05d}_i{image:05d}.png"
        img.save(staged / filename)
        records.append({
            "index": idx,
            "group": group,
            "image": image,
            "source_rect": {"x": 0, "y": 0, "w": 96, "h": 96},
            "axis": {"x": 48, "y": 88},
            "filename": filename,
        })
    manifest = staged / "mugenforge_sprite_manifest.json"
    manifest.write_text(json.dumps({
        "tool": "MugenForge Studio Factory+",
        "mode": "air_reference_placeholder_staging",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "note": "Generated placeholder images for every unique AIR group/image reference.",
        "sprites": records,
    }, indent=2), encoding="utf-8")
    out = root / (out_name or f"{root.name}.sff")
    if out.exists():
        b = _backup(out)
        if b:
            result.notes.append(f"Backup written: {b.name}")
    build_sff_v1_from_manifest(manifest, out)
    result.created_files.append(_rel(root, manifest))
    result.changed_files.append(_rel(root, out))
    result.notes.append(f"Created {len(records)} placeholder sprites from AIR references.")
    return result


_IMAGE_NAME_PATTERNS = [
    re.compile(r"g(?P<g>-?\d+)[_\- ]?i(?P<i>-?\d+)", re.I),
    re.compile(r"group[_\- ]?(?P<g>-?\d+).*?(?:image|img|sprite)[_\- ]?(?P<i>-?\d+)", re.I),
    re.compile(r"(?P<g>-?\d+)[_\- ]+(?P<i>-?\d+)$"),
]


def _sprite_id_from_name(path: Path, fallback_index: int) -> Tuple[int, int]:
    stem = path.stem
    for pat in _IMAGE_NAME_PATTERNS:
        m = pat.search(stem)
        if m:
            try:
                return int(m.group("g")), int(m.group("i"))
            except Exception:
                pass
    return 9000, fallback_index


def bulk_import_sprite_folder(root: Path, source_folder: Path, *, append_air: bool = True, action_ticks: int = 5) -> FactoryPlusResult:
    """Import a folder of PNG/PCX images into a staged manifest, build an SFF v1, and optionally append AIR actions.

    The nicest filename formats are g200_i0.png, 200_0.png, or group200_image0.png.
    Images without group/image IDs are assigned to group 9000.
    """
    root = Path(root)
    source_folder = Path(source_folder)
    result = FactoryPlusResult("Factory+ Bulk Sprite Folder Import")
    if not source_folder.exists() or not source_folder.is_dir():
        result.warnings.append(f"Sprite source folder does not exist: {source_folder}")
        return result
    image_files = [p for p in sorted(source_folder.iterdir(), key=lambda p: p.name.lower()) if p.suffix.lower() in {".png", ".pcx", ".gif"}]
    if not image_files:
        result.warnings.append("No PNG/PCX/GIF files found in the selected folder.")
        return result
    staged = root / "factory_plus_bulk_import"
    staged.mkdir(parents=True, exist_ok=True)
    records = []
    for idx, src in enumerate(image_files):
        group, image = _sprite_id_from_name(src, idx)
        ext = ".png" if src.suffix.lower() not in {".pcx", ".gif"} else src.suffix.lower()
        filename = f"g{group:05d}_i{image:05d}{ext}"
        dst = staged / filename
        shutil.copy2(src, dst)
        records.append({
            "index": idx,
            "group": group,
            "image": image,
            "source_rect": {"x": 0, "y": 0, "w": 0, "h": 0},
            "axis": {"x": 48, "y": 88},
            "filename": filename,
            "source_file": str(src),
        })
    manifest = staged / "mugenforge_sprite_manifest.json"
    manifest.write_text(json.dumps({
        "tool": "MugenForge Studio Factory+",
        "mode": "bulk_folder_sprite_import",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source_folder": str(source_folder),
        "filename_help": "Use g200_i0.png, 200_0.png, or group200_image0.png to control group/image IDs.",
        "sprites": records,
    }, indent=2), encoding="utf-8")
    out = root / f"{root.name}.sff"
    if out.exists():
        b = _backup(out)
        if b:
            result.notes.append(f"Backup written: {b.name}")
    build_sff_v1_from_manifest(manifest, out)
    result.created_files.append(_rel(root, manifest))
    result.changed_files.append(_rel(root, out))
    result.notes.append(f"Imported {len(records)} image files into SFF v1.")

    if append_air:
        files = discover_character_files(root)
        if not files.air_path:
            result.merge_apply(auto_setup_project(root), "auto setup")
            files = discover_character_files(root)
        if files.air_path:
            groups: Dict[int, List[dict]] = {}
            for rec in records:
                groups.setdefault(int(rec["group"]), []).append(rec)
            existing_actions = set()
            if files.air_path.exists():
                existing_actions = {a.number for a in parse_air(read_text_safely(files.air_path))}
            blocks = ["", "; MugenForge Factory+ Bulk Import AIR actions", "; One action per imported sprite group.", ""]
            added = 0
            for group, recs in sorted(groups.items()):
                if group in existing_actions:
                    continue
                blocks.append(f"[Begin Action {group}] ; Factory+ bulk import")
                for rec in sorted(recs, key=lambda r: int(r["image"])):
                    blocks.append("Clsn2: 1")
                    blocks.append("  Clsn2[0] = -20,-88,20,0")
                    blocks.append(f"{rec['group']}, {rec['image']}, 0, 0, {max(1, action_ticks)}")
                blocks.append("")
                added += 1
            if added:
                marker = "; MugenForge Factory+ Bulk Import AIR actions"
                _append_unique(files.air_path, marker, "\n".join(blocks), result)
                result.notes.append(f"Added {added} AIR actions from imported sprite groups.")
            else:
                result.skipped_files.append("AIR append: imported groups already exist as actions")
    return result


def installed_feature_ids(root: Path) -> List[str]:
    ids = set()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".cmd", ".cns", ".st", ".air", ".txt", ".md"}:
            try:
                text = read_text_safely(path)
            except Exception:
                continue
            for m in re.finditer(r"MugenForge Feature Bank ID:\s*([A-Za-z0-9_\-]+)", text):
                ids.add(m.group(1))
    return sorted(ids)


def _all_code_text(root: Path) -> Tuple[str, List[Path]]:
    paths = [p for p in sorted(root.rglob("*"), key=lambda p: str(p).lower()) if p.is_file() and p.suffix.lower() in {".cmd", ".cns", ".st"}]
    chunks = []
    for p in paths:
        try:
            chunks.append(f"\n; ---- {p.name} ----\n" + read_text_safely(p))
        except Exception:
            pass
    return "\n".join(chunks), paths


def export_move_list(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Move List Export")
    text, paths = _all_code_text(root)
    scan = parse_code(text)
    command_by_name = {c.name: c for c in scan.commands}
    referenced_commands = set()
    state_by_command: Dict[str, str] = {}
    for m in re.finditer(r'command\s*=\s*["\']([^"\']+)["\']', text, re.I):
        referenced_commands.add(m.group(1))
    # Link a command to the closest following value = state inside the same small block.
    for m in re.finditer(r'triggerall\s*=\s*command\s*=\s*["\']([^"\']+)["\'][\s\S]{0,260}?\bvalue\s*=\s*(-?\d+)', text, re.I):
        state_by_command.setdefault(m.group(1), m.group(2))
    rows = []
    for name, cmd in sorted(command_by_name.items(), key=lambda kv: kv[0].lower()):
        rows.append({
            "name": name,
            "input": cmd.command,
            "time": cmd.time or "",
            "buffer": cmd.buffer_time or "",
            "state": state_by_command.get(name, ""),
            "referenced": "yes" if name in referenced_commands else "no",
        })
    installed = installed_feature_ids(root)
    out_md = root / "MUGENFORGE_MOVE_LIST.md"
    out_html = root / "MUGENFORGE_MOVE_LIST.html"
    lines = [f"# Move List: {root.name}", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", "## Commands", ""]
    if rows:
        lines.append("| Move / Command | Input | State | Time | Buffer | Used by code |")
        lines.append("|---|---|---:|---:|---:|---|")
        for r in rows:
            lines.append(f"| `{r['name']}` | `{r['input']}` | `{r['state']}` | `{r['time']}` | `{r['buffer']}` | {r['referenced']} |")
    else:
        lines.append("No `[Command]` blocks found yet.")
    lines += ["", "## Installed Feature Bank IDs", ""]
    lines += [f"- `{fid}`" for fid in installed] if installed else ["- None found"]
    lines += ["", "## Creator Notes", "", "Use this as a public movelist draft. Rename commands into plain move names when your character is closer to release."]
    write_text_safely(out_md, "\n".join(lines) + "\n")

    html_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r[k]))}</td>" for k in ["name", "input", "state", "time", "buffer", "referenced"]) + "</tr>"
        for r in rows
    )
    out_html.write_text(f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{html.escape(root.name)} Move List</title>
<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:32px auto;line-height:1.4}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px 8px}}th{{background:#eee}}code{{background:#f2f2f2;padding:1px 3px}}</style></head>
<body><h1>{html.escape(root.name)} Move List</h1><p>Generated {datetime.now().isoformat(timespec='seconds')}</p>
<table><thead><tr><th>Move / Command</th><th>Input</th><th>State</th><th>Time</th><th>Buffer</th><th>Used</th></tr></thead><tbody>{html_rows}</tbody></table>
<h2>Installed Feature Bank IDs</h2><ul>{''.join(f'<li><code>{html.escape(fid)}</code></li>' for fid in installed) or '<li>None found</li>'}</ul></body></html>""", encoding="utf-8")
    result.created_files += [_rel(root, out_md), _rel(root, out_html)]
    result.notes.append(f"Exported {len(rows)} command rows from {len(paths)} code files.")
    return result


def export_state_map(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ State Map Export")
    text, paths = _all_code_text(root)
    scan = parse_code(text)
    states = {s.number for s in scan.states}
    edges: List[Tuple[str, str, str]] = []
    current_state = None
    for line in text.splitlines():
        m_state = re.match(r"\s*\[\s*Statedef\s+(-?\d+)\s*\]", line, re.I)
        if m_state:
            current_state = m_state.group(1)
            continue
        m_value = re.match(r"\s*value\s*=\s*(-?\d+)\b", line, re.I)
        if current_state is not None and m_value:
            edges.append((current_state, m_value.group(1), "ChangeState/value"))
    dot = ["digraph mugenforge_state_map {", "  rankdir=LR;", "  node [shape=box, fontname=\"Arial\"];", f"  label=\"{root.name} State Map\";", "  labelloc=t;"]
    for s in sorted(states):
        dot.append(f"  s{s} [label=\"State {s}\"];")
    for src, dst, label in edges:
        dot.append(f"  s{src} -> s{dst} [label=\"{label}\"];")
    dot.append("}")
    out_dot = root / "MUGENFORGE_STATE_MAP.dot"
    write_text_safely(out_dot, "\n".join(dot) + "\n")
    out_md = root / "MUGENFORGE_STATE_MAP.md"
    lines = [f"# State Map: {root.name}", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", f"Code files scanned: {len(paths)}", f"StateDefs found: {len(states)}", f"Transitions/value lines found: {len(edges)}", "", "## Edges", ""]
    if edges:
        lines += [f"- `{src}` → `{dst}` ({label})" for src, dst, label in edges[:500]]
    else:
        lines.append("- No obvious state transitions found.")
    lines += ["", "## GraphViz", "", "Open `MUGENFORGE_STATE_MAP.dot` with a GraphViz viewer to see a visual state graph."]
    write_text_safely(out_md, "\n".join(lines) + "\n")
    result.created_files += [_rel(root, out_dot), _rel(root, out_md)]
    result.notes.append(f"Mapped {len(states)} states and {len(edges)} possible transitions.")
    return result


def export_balance_sheet(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Balance Sheet Export")
    text, _paths = _all_code_text(root)
    rows = []
    current_state = ""
    current_anim = ""
    for line in text.splitlines():
        m_state = re.match(r"\s*\[\s*Statedef\s+(-?\d+)\s*\]", line, re.I)
        if m_state:
            current_state = m_state.group(1)
            current_anim = ""
            continue
        m_anim = re.match(r"\s*anim\s*=\s*(-?\d+)\b", line, re.I)
        if m_anim and current_state and not current_anim:
            current_anim = m_anim.group(1)
            continue
        m_damage = re.match(r"\s*damage\s*=\s*([0-9]+)\s*(?:,\s*([0-9]+))?", line, re.I)
        if m_damage and current_state:
            dmg = int(m_damage.group(1))
            guard = int(m_damage.group(2) or 0)
            advice = "ok"
            if dmg >= 180:
                advice = "super-level damage; verify meter cost/startup/recovery"
            elif dmg >= 90:
                advice = "heavy/special damage; verify recovery and hitbox size"
            elif dmg <= 15:
                advice = "very low damage; check if this is intentional"
            rows.append([current_state, current_anim, dmg, guard, advice])
    out = root / "MUGENFORGE_BALANCE_SHEET.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["state", "anim", "damage", "guard_damage", "plain_english_review"])
        writer.writerows(rows)
    result.created_files.append(_rel(root, out))
    result.notes.append(f"Exported {len(rows)} HitDef damage rows.")
    return result


def deep_factory_doctor(root: Path) -> str:
    root = Path(root)
    audit = scan_project(root)
    files = discover_character_files(root)
    lines = [
        f"# Factory+ Doctor Report: {root.name}",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Project Health",
        "",
    ]
    if audit.missing_required:
        lines.append("Missing common file types: " + ", ".join(audit.missing_required))
    else:
        lines.append("Common character file types are present: DEF, AIR, CMD/CNS, SFF, SND.")
    if audit.missing_references:
        lines += ["", "### Missing DEF references"] + [f"- {m}" for m in audit.missing_references[:100]]
    if audit.asset_issues:
        lines += ["", "### AIR/SFF asset issues"] + [f"- {m}" for m in audit.asset_issues[:100]]

    lines += ["", "## File Routing", ""]
    for label, path in [("DEF", files.def_path), ("CMD", files.cmd_path), ("CNS/ST", files.cns_path), ("AIR", files.air_path), ("SFF", files.sff_path), ("SND", files.snd_path)]:
        lines.append(f"- {label}: `{_rel(root, path) if path else 'not found'}`")

    if files.air_path and files.air_path.exists():
        actions = parse_air(read_text_safely(files.air_path))
        frames = sum(len(a.frames) for a in actions)
        clsn1 = sum(1 for a in actions for f in a.frames for b in f.clsn if b.kind.lower() == "clsn1")
        clsn2 = sum(1 for a in actions for f in a.frames for b in f.clsn if b.kind.lower() == "clsn2")
        missing_actions = [n for n in COMMON_ANIMS if n not in {a.number for a in actions}]
        lines += ["", "## Animation / Hitbox Health", "", f"- AIR actions: {len(actions)}", f"- AIR frames: {frames}", f"- Attack boxes (Clsn1): {clsn1}", f"- Body boxes (Clsn2): {clsn2}"]
        if missing_actions:
            lines.append("- Missing common actions: " + ", ".join(str(n) for n in missing_actions[:30]))
        else:
            lines.append("- Common action coverage looks good.")
    else:
        lines += ["", "## Animation / Hitbox Health", "", "No AIR file found."]

    text, paths = _all_code_text(root)
    scan = parse_code(text)
    command_names = {c.name for c in scan.commands}
    refs = set(re.findall(r'command\s*=\s*["\']([^"\']+)["\']', text, flags=re.I))
    unreferenced = sorted(command_names - refs)
    missing_cmd_refs = sorted(refs - command_names)
    states = {s.number for s in scan.states}
    target_values = {int(v) for v in re.findall(r'\bvalue\s*=\s*(-?\d+)\b', text, flags=re.I) if v.lstrip("-").isdigit()}
    missing_state_targets = sorted(v for v in target_values if v not in states and v not in {0, 20, 40, 50, 52})
    lines += ["", "## Code Health", "", f"- Code files scanned: {len(paths)}", f"- Commands: {len(scan.commands)}", f"- StateDefs: {len(scan.states)}", f"- Controllers: {len(scan.controllers)}", f"- HitDefs: {sum(1 for c in scan.controllers if c.stype == 'hitdef')}", f"- ChangeStates: {sum(1 for c in scan.controllers if c.stype == 'changestate')}"]
    if missing_cmd_refs:
        lines.append("- Command references without definitions: " + ", ".join(missing_cmd_refs[:30]))
    if unreferenced:
        lines.append("- Defined commands not obviously used: " + ", ".join(unreferenced[:30]))
    if missing_state_targets:
        lines.append("- ChangeState/value targets without local StateDef: " + ", ".join(str(v) for v in missing_state_targets[:30]))

    installed = installed_feature_ids(root)
    lines += ["", "## No-Code Feature Bank", "", f"- Installed generated feature IDs detected: {len(installed)}"]
    lines += [f"  - `{fid}`" for fid in installed[:100]] if installed else ["  - None detected yet."]

    if files.sff_path and files.sff_path.exists():
        try:
            sff = read_sff(files.sff_path)
            lines += ["", "## Sprite File", "", f"- SFF variant: {sff.variant}", f"- Parsed sprites: {len(sff.sprites)}", f"- Header sprite count: {sff.sprite_count}"]
            if sff.warnings:
                lines += [f"- Warning: {w}" for w in sff.warnings[:20]]
            if files.air_path and files.air_path.exists() and sff.sprites:
                used = set(_air_sprite_pairs(root))
                available = set(sprite_lookup(sff).keys())
                missing = sorted(used - available)[:50]
                orphan = sorted(available - used)[:50]
                lines.append(f"- AIR sprite refs: {len(used)}")
                lines.append(f"- Missing AIR refs in SFF: {len(used - available)}")
                if missing:
                    lines += ["  - Missing examples:"] + [f"    - `{g},{i}`" for g, i in missing[:20]]
                lines.append(f"- SFF sprites not used by AIR yet: {len(available - used)}")
                if orphan:
                    lines += ["  - Unused examples:"] + [f"    - `{g},{i}`" for g, i in orphan[:20]]
        except Exception as exc:
            lines += ["", "## Sprite File", "", f"Could not inspect SFF: {exc}"]

    if files.snd_path and files.snd_path.exists():
        lines += ["", "## Sound File", "", f"- SND file: `{_rel(root, files.snd_path)}`", f"- Bytes: {files.snd_path.stat().st_size:,}"]

    lines += ["", "## Plain-English Next Step", ""]
    if audit.missing_required:
        lines.append("Run **Factory+ Smart Complete / Repair** first. It creates/repairs structure, common animations, placeholder SFF/SND, and beginner docs.")
    elif audit.asset_issues:
        lines.append("Run **Rebuild Placeholder SFF From AIR**, then use the Sprites/CLSN/Animation tabs to replace rough art and tune boxes.")
    elif missing_cmd_refs or missing_state_targets:
        lines.append("Run **Export State Map** and **Move List**, then install missing features from the Feature Bank or correct command/state numbers.")
    else:
        lines.append("The structure is healthy. Next: replace placeholder art/audio, tune hitboxes in the visual editor, then build a release package.")
    return "\n".join(lines).strip() + "\n"


def write_doctor_report(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Doctor Report")
    out = root / "MUGENFORGE_FACTORY_PLUS_DOCTOR.md"
    write_text_safely(out, deep_factory_doctor(root))
    result.created_files.append(_rel(root, out))
    return result


_FUNCTION_BANK: List[Dict[str, object]] = [
    {"category": "Animation", "name": "Create missing common AIR actions", "button": "Complete Missing AIR Actions", "what_it_writes": "AIR placeholder actions and CLSN2 boxes", "user_job": "Replace sprites and drag boxes."},
    {"category": "Sprites", "name": "Build placeholder SFF from AIR references", "button": "Rebuild Placeholder SFF From AIR", "what_it_writes": "PNG placeholders, manifest, SFF v1", "user_job": "Replace rough placeholder images later."},
    {"category": "Sprites", "name": "Bulk import named sprite images", "button": "Bulk Import Sprite Folder", "what_it_writes": "Staged manifest, SFF v1, optional AIR actions", "user_job": "Name images like g200_i0.png."},
    {"category": "Code", "name": "Generate no-code move/function code", "button": "Feature Bank / Move Wizard", "what_it_writes": "CMD commands, StateDefs, AIR blocks", "user_job": "Choose move type, damage, timing, and style."},
    {"category": "Diagnostics", "name": "Doctor report", "button": "Deep Doctor Report", "what_it_writes": "Markdown health report", "user_job": "Follow the next step line."},
    {"category": "Release", "name": "Build release package", "button": "Build Release ZIP", "what_it_writes": "Clean ZIP plus docs", "user_job": "Share/test the ZIP."},
]


def write_function_bank(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Function Bank")
    out_json = root / "MUGENFORGE_FACTORY_PLUS_FUNCTION_BANK.json"
    out_md = root / "MUGENFORGE_FACTORY_PLUS_FUNCTION_BANK.md"
    out_json.write_text(json.dumps({
        "tool": "MugenForge Studio Factory+",
        "version": FACTORY_PLUS_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "purpose": "A plain-English bank of no-code functions. The user chooses a function; MugenForge handles the CMD/CNS/AIR/SFF/SND wiring.",
        "functions": _FUNCTION_BANK,
    }, indent=2), encoding="utf-8")
    lines = ["# MugenForge Factory+ Function Bank", "", "This is the plain-English bank that turns creator choices into generated project work.", ""]
    for item in _FUNCTION_BANK:
        lines += [f"## {item['category']} — {item['name']}", "", f"App button: **{item['button']}**", "", f"MugenForge writes: {item['what_it_writes']}", "", f"User handles: {item['user_job']}", ""]
    lines += ["## Built-in Feature Bank Stats", "", "```", feature_bank_stats_text().strip(), "```", ""]
    write_text_safely(out_md, "\n".join(lines))
    result.created_files += [_rel(root, out_json), _rel(root, out_md)]
    return result


def write_start_here(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Start Here")
    out = root / "START_HERE_NO_CODE_CREATOR.md"
    text = f"""# Start Here: {root.name}

Generated: {datetime.now().isoformat(timespec='seconds')}

## The simple workflow

1. Open **Factory+** and run **Smart Complete / Repair**.
2. Open **Animation Player** and check whether the placeholder animations play.
3. Open **CLSN Editor** and drag hitboxes/body boxes onto the art.
4. Use **Feature Bank** for no-code moves, specials, defense tools, supers, FX, and AI helpers.
5. Replace placeholder sprites in `factory_plus_staged_sprites/` or import named sprites with **Bulk Import Sprite Folder**.
6. Replace silent WAVs in `sounds/` and rebuild SND.
7. Run **Deep Doctor Report**.
8. Run **Build Release ZIP**.

## Naming sprites for easy import

Use names like:

- `g200_i0.png`
- `g200_i1.png`
- `group1000_image0.png`
- `3000_0.png`

The first number is the sprite group/action. The second number is the image frame.

## What MugenForge handles

- Project files and DEF references.
- Required placeholder AIR actions.
- CMD/CNS/AIR code from no-code Feature Bank choices.
- Placeholder SFF/SND generation.
- Movelist docs, state maps, balance sheets, and release zips.

## What you handle

- Character concept.
- Sprite art style.
- Sound/voice choices.
- Hitbox feel.
- Move balance and personality.
"""
    write_text_safely(out, text)
    result.created_files.append(_rel(root, out))
    return result


def smart_complete_project(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Smart Complete / Repair")
    setup_result = auto_setup_project(root)
    setup_result.warnings = [w for w in setup_result.warnings if "SFF and SND binary files are not auto-created" not in w]
    result.merge_apply(setup_result, "auto setup")
    result.merge(ensure_required_animations(root), "required animations")
    result.merge(write_start_here(root), "start here")
    result.merge(write_function_bank(root), "function bank")
    # Build placeholders only if missing or if AIR refs are not covered.
    files = discover_character_files(root)
    if not files.sff_path or not files.sff_path.exists():
        result.merge(rebuild_placeholder_sff_from_air(root), "placeholder SFF")
    else:
        try:
            sff = read_sff(files.sff_path)
            missing = set(_air_sprite_pairs(root)) - set(sprite_lookup(sff).keys())
            if missing:
                result.merge(rebuild_placeholder_sff_from_air(root), "placeholder SFF")
            else:
                result.skipped_files.append("SFF: existing sprite file appears to cover AIR refs parsed by MugenForge")
        except Exception as exc:
            result.warnings.append(f"Existing SFF could not be inspected: {exc}")
    files = discover_character_files(root)
    if not files.snd_path or not files.snd_path.exists():
        try:
            manifest = make_placeholder_sound_bank(root / "sounds")
            snd_path = root / f"{root.name}.snd"
            if snd_path.exists():
                b = _backup(snd_path)
                if b:
                    result.notes.append(f"Backup written: {b.name}")
            build_snd_from_manifest(manifest, snd_path)
            result.created_files += [_rel(root, manifest), _rel(root, snd_path)]
        except Exception as exc:
            result.warnings.append(f"Could not create placeholder sound bank/SND: {exc}")
    else:
        result.skipped_files.append("SND: existing sound file found")
    result.merge(export_move_list(root), "move list")
    result.merge(export_state_map(root), "state map")
    result.merge(export_balance_sheet(root), "balance sheet")
    result.merge(write_doctor_report(root), "doctor")
    result.notes.append("Smart Complete does not replace finished art. It creates a safer scaffold and gives plain-English next steps.")
    return result


def build_release_zip(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Release ZIP")
    # Refresh docs before packaging.
    result.merge(write_doctor_report(root), "doctor")
    result.merge(export_move_list(root), "move list")
    exports = root / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    out = exports / f"{root.name}_factory_plus_release_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    skip_parts = {"__pycache__", ".git"}
    skip_suffixes = (".bak", ".tmp", ".pyc")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
            if path.is_dir():
                continue
            rel = path.relative_to(root)
            if any(part in skip_parts for part in rel.parts):
                continue
            name = str(rel).replace("\\", "/")
            lower = name.lower()
            if ".bak_" in lower or lower.endswith(skip_suffixes):
                continue
            if name.startswith("exports/") and path != out:
                continue
            z.write(path, arcname=f"{root.name}/{name}")
    result.created_files.append(_rel(root, out))
    result.notes.append("Release ZIP skips backups/temp files and refreshes Doctor + Move List first.")
    return result


# ---------------------------------------------------------------------------
# Compatibility and expanded Factory+ helpers used by newer UI panels.
# These wrappers keep the app stable while adding more Fighter-Factory-style
# workflows on top of the original Factory+ function names.
# ---------------------------------------------------------------------------

def project_doctor_report(root: Path) -> str:
    return deep_factory_doctor(Path(root))


def write_factory_doctor_report(root: Path) -> FactoryPlusResult:
    return write_doctor_report(Path(root))


def one_click_upgrade(root: Path) -> FactoryPlusResult:
    return smart_complete_project(Path(root))


def ensure_standard_air_actions(root: Path) -> FactoryPlusResult:
    return ensure_required_animations(Path(root))


def make_factory_plus_workspace(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Workspace")
    folders = [
        "exports", "exports/contact_sheets", "exports/animation_gifs", "exports/animation_frames",
        "docs", "docs/reports", "art/raw_sheets", "art/clean_slices", "audio/raw_wavs",
        "replacements", "presets/hitboxes", "presets/palettes", "release", "testing",
    ]
    for rel in folders:
        p = root / rel
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            result.created_files.append(rel + "/")
    result.merge(write_start_here(root), "start here")
    result.merge(write_function_bank(root), "function bank")
    return result


def asset_inventory(root: Path) -> Dict[str, object]:
    root = Path(root)
    files = discover_character_files(root)
    air_pairs = set(_air_sprite_pairs(root))
    sff_pairs: set[Tuple[int, int]] = set()
    warnings: List[str] = []
    if files.sff_path and files.sff_path.exists():
        try:
            info = read_sff(files.sff_path)
            sff_pairs = set(sprite_lookup(info).keys())
            warnings += list(info.warnings)
        except Exception as exc:
            warnings.append(f"SFF scan failed: {exc}")
    return {
        "root": str(root),
        "def": str(files.def_path) if files.def_path else "",
        "cmd": str(files.cmd_path) if files.cmd_path else "",
        "cns": str(files.cns_path) if files.cns_path else "",
        "air": str(files.air_path) if files.air_path else "",
        "sff": str(files.sff_path) if files.sff_path else "",
        "snd": str(files.snd_path) if files.snd_path else "",
        "air_sprite_pairs": sorted(air_pairs),
        "sff_sprite_pairs": sorted(sff_pairs),
        "missing_in_sff": sorted(air_pairs - sff_pairs),
        "unused_in_air": sorted(sff_pairs - air_pairs),
        "warnings": warnings,
    }


def export_asset_report(root: Path) -> Path:
    root = Path(root)
    out = root / "MUGENFORGE_FACTORY_PLUS_ASSET_REPORT.json"
    out.write_text(json.dumps(asset_inventory(root), indent=2), encoding="utf-8")
    return out


def rebuild_missing_placeholder_assets(root: Path) -> FactoryPlusResult:
    root = Path(root)
    result = FactoryPlusResult("Factory+ Placeholder Asset Rebuild")
    result.merge(rebuild_placeholder_sff_from_air(root), "SFF")
    try:
        manifest = make_placeholder_sound_bank(root / "sounds")
        snd = root / f"{root.name}.snd"
        if snd.exists():
            _backup(snd)
        build_snd_from_manifest(manifest, snd)
        result.created_files += [_rel(root, manifest), _rel(root, snd)]
    except Exception as exc:
        result.warnings.append(f"Placeholder SND failed: {exc}")
    try:
        result.created_files.append(_rel(root, export_asset_report(root)))
    except Exception as exc:
        result.warnings.append(f"Asset report failed: {exc}")
    return result


def _decode_sff_sprite_image(sff_path: Path, sprite):
    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
        data = sff_path.read_bytes()[sprite.data_offset:sprite.data_offset + sprite.length]
        return Image.open(BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def export_sprite_contact_sheet(root: Path, max_sprites: int = 240) -> Path:
    root = Path(root)
    files = discover_character_files(root)
    if not files.sff_path or not files.sff_path.exists():
        raise FileNotFoundError("No SFF file found for contact sheet export.")
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for contact sheet export. Install with: pip install Pillow") from exc
    info = read_sff(files.sff_path)
    sprites = [s for s in info.sprites if s.format_hint in {"pcx", "png"}][:max_sprites]
    if not sprites:
        raise ValueError("No extractable PCX/PNG sprites found in this SFF.")
    cell_w, cell_h = 118, 138
    cols = 8 if len(sprites) > 48 else 5
    rows = (len(sprites) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, spr in enumerate(sprites):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], outline=(190, 190, 190, 255))
        img = _decode_sff_sprite_image(files.sff_path, spr)
        if img is not None:
            scale = min((cell_w - 12) / max(1, img.width), (cell_h - 34) / max(1, img.height), 1.0)
            if scale < 1:
                img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
            sheet.alpha_composite(img, (x + (cell_w - img.width) // 2, y + 7))
        draw.text((x + 4, y + cell_h - 21), f"{spr.group},{spr.image}", fill=(0, 0, 0, 255))
    out_dir = root / "exports" / "contact_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{root.name}_sff_contact_sheet.png"
    sheet.convert("RGB").save(out)
    return out


def write_move_list_markdown(root: Path) -> Path:
    export_move_list(Path(root))
    return Path(root) / "MUGENFORGE_MOVE_LIST.md"


def write_move_list_html(root: Path) -> Path:
    md = write_move_list_markdown(root)
    body = ["<!doctype html><meta charset='utf-8'><title>MugenForge Move List</title><body>"]
    for line in read_text_safely(md).splitlines():
        esc = html.escape(line)
        if line.startswith("# "):
            body.append(f"<h1>{esc[2:]}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{esc[2:]}</li>")
        elif line.strip():
            body.append(f"<p>{esc}</p>")
    body.append("</body>")
    out = Path(root) / "MUGENFORGE_MOVE_LIST.html"
    out.write_text("\n".join(body), encoding="utf-8")
    return out


def export_state_graph(root: Path) -> Path:
    export_state_map(Path(root))
    return Path(root) / "MUGENFORGE_STATE_MAP.md"


def _find_action_block(text: str, action_no: int) -> Optional[Tuple[int, int, str]]:
    matches = list(re.finditer(r"^\s*\[\s*Begin\s+Action\s+(-?\d+)\s*\].*$", text, flags=re.I | re.M))
    for i, match in enumerate(matches):
        if int(match.group(1)) == int(action_no):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return start, end, text[start:end]
    return None


def _air_path_or_raise(path_or_root: Path) -> Path:
    p = Path(path_or_root)
    if p.suffix.lower() == ".air":
        return p
    files = discover_character_files(p)
    if files.air_path and files.air_path.exists():
        return files.air_path
    raise FileNotFoundError("No AIR file found.")


def duplicate_action(path_or_root: Path, source_action: int, target_action: int, sprite_group: Optional[int] = None) -> bool:
    air = _air_path_or_raise(path_or_root)
    text = read_text_safely(air)
    if _find_action_block(text, target_action):
        raise ValueError(f"Action {target_action} already exists.")
    found = _find_action_block(text, source_action)
    if not found:
        raise ValueError(f"Action {source_action} was not found.")
    block = found[2]
    block = re.sub(r"(\[\s*Begin\s+Action\s+)-?\d+(\s*\])", rf"\g<1>{target_action}\2", block, count=1, flags=re.I)
    if sprite_group is not None:
        block = re.sub(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*,", lambda m: f"{sprite_group}, {m.group(2)},", block, flags=re.M)
    _backup(air)
    write_text_safely(air, text.rstrip() + f"\n\n; Factory+ duplicated action {source_action} as {target_action}\n" + block.rstrip() + "\n")
    return True


def retime_action(path_or_root: Path, action_no: int, ticks: int) -> bool:
    air = _air_path_or_raise(path_or_root)
    text = read_text_safely(air)
    found = _find_action_block(text, action_no)
    if not found:
        raise ValueError(f"Action {action_no} was not found.")
    start, end, block = found
    def repl(m):
        parts = m.group(0).split(",")
        if len(parts) >= 5:
            parts[4] = f" {max(1, int(ticks))}"
        return ",".join(parts)
    new = re.sub(r"^\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+.*$", repl, block, flags=re.M)
    _backup(air)
    write_text_safely(air, text[:start] + new + text[end:])
    return True


def mirror_action_clsn(path_or_root: Path, action_no: int) -> bool:
    air = _air_path_or_raise(path_or_root)
    text = read_text_safely(air)
    found = _find_action_block(text, action_no)
    if not found:
        raise ValueError(f"Action {action_no} was not found.")
    start, end, block = found
    def repl(m):
        prefix = m.group(1)
        x1, y1, x2, y2 = [int(m.group(i)) for i in range(2, 6)]
        return f"{prefix}{-x2},{y1},{-x1},{y2}"
    new = re.sub(r"(Clsn[12]\[\s*\d+\s*\]\s*=\s*)(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)", repl, block, flags=re.I)
    _backup(air)
    write_text_safely(air, text[:start] + new + text[end:])
    return True


def auto_body_boxes_for_action(path_or_root: Path, action_no: int, box: Tuple[int, int, int, int] = (-20, -88, 20, 0)) -> bool:
    air = _air_path_or_raise(path_or_root)
    text = read_text_safely(air)
    found = _find_action_block(text, action_no)
    if not found:
        raise ValueError(f"Action {action_no} was not found.")
    start, end, block = found
    frame_re = re.compile(r"^\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+")
    out: List[str] = []
    for line in block.splitlines():
        if re.match(r"^\s*Clsn2\s*:\s*\d+", line, flags=re.I) or re.match(r"^\s*Clsn2\[", line, flags=re.I):
            continue
        if frame_re.match(line):
            out.append("Clsn2: 1")
            out.append(f"  Clsn2[0] = {box[0]},{box[1]},{box[2]},{box[3]}")
        out.append(line)
    _backup(air)
    write_text_safely(air, text[:start] + "\n".join(out).rstrip() + "\n" + text[end:])
    return True


def export_animation_gif(root: Path, action_no: int, out_path: Optional[Path] = None, zoom: int = 2) -> Path:
    root = Path(root)
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for GIF export. Install with: pip install Pillow") from exc
    files = discover_character_files(root)
    if not files.air_path or not files.air_path.exists():
        raise FileNotFoundError("No AIR file found.")
    action_map = {a.number: a for a in parse_air(read_text_safely(files.air_path))}
    action = action_map.get(int(action_no))
    if not action:
        raise ValueError(f"Action {action_no} not found.")
    lookup = {}
    if files.sff_path and files.sff_path.exists():
        try:
            lookup = sprite_lookup(read_sff(files.sff_path))
        except Exception:
            lookup = {}
    canvas_w, canvas_h = 320 * zoom, 240 * zoom
    origin = (canvas_w // 2, int(canvas_h * 0.72))
    rendered = []
    durations = []
    for idx, frame in enumerate(action.frames):
        im = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(im)
        draw.line([origin[0] - 150 * zoom, origin[1], origin[0] + 150 * zoom, origin[1]], fill=(220, 220, 220, 255))
        draw.line([origin[0], origin[1] - 110 * zoom, origin[0], origin[1] + 40 * zoom], fill=(220, 220, 220, 255))
        spr = lookup.get((frame.group, frame.image)) if lookup else None
        sprite_img = _decode_sff_sprite_image(files.sff_path, spr) if (files.sff_path and spr) else None
        if sprite_img:
            if zoom != 1:
                sprite_img = sprite_img.resize((max(1, sprite_img.width * zoom), max(1, sprite_img.height * zoom)))
            im.alpha_composite(sprite_img, (origin[0] + frame.x * zoom - spr.x * zoom, origin[1] + frame.y * zoom - spr.y * zoom))
        else:
            draw.rectangle([origin[0]-24*zoom, origin[1]-88*zoom, origin[0]+24*zoom, origin[1]], outline=(0,0,0,255), width=max(1, zoom))
            draw.text((8, 8), f"missing {frame.group},{frame.image}", fill=(0,0,0,255))
        for b in frame.clsn:
            color = (230, 0, 0, 255) if b.kind.lower() == "clsn1" else (0, 90, 255, 255)
            draw.rectangle([origin[0]+b.x1*zoom, origin[1]+b.y1*zoom, origin[0]+b.x2*zoom, origin[1]+b.y2*zoom], outline=color, width=max(1, zoom))
        draw.text((8, canvas_h - 20), f"Action {action_no} frame {idx} sprite {frame.group},{frame.image}", fill=(0,0,0,255))
        rendered.append(im.convert("P", palette=Image.ADAPTIVE))
        durations.append(max(33, int(1000 * max(1, frame.ticks) / 60)))
    if not rendered:
        raise ValueError("Action has no frames.")
    out_dir = root / "exports" / "animation_gifs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_path or (out_dir / f"action_{action_no}.gif")
    rendered[0].save(out, save_all=True, append_images=rendered[1:], duration=durations, loop=0, disposal=2)
    return out


def batch_export_animation_gifs(root: Path, limit: int = 80) -> List[Path]:
    root = Path(root)
    files = discover_character_files(root)
    if not files.air_path or not files.air_path.exists():
        raise FileNotFoundError("No AIR file found.")
    outs: List[Path] = []
    for action in parse_air(read_text_safely(files.air_path))[:limit]:
        try:
            outs.append(export_animation_gif(root, action.number))
        except Exception:
            continue
    if not outs:
        raise RuntimeError("No GIFs exported.")
    return outs


def batch_export_action_pngs(root: Path, action_no: int, zoom: int = 2) -> List[Path]:
    root = Path(root)
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError("Pillow is required for PNG frame export. Install with: pip install Pillow") from exc
    temp = export_animation_gif(root, action_no, root / "exports" / "animation_gifs" / f"action_{action_no}_temp.gif", zoom=zoom)
    out_dir = root / "exports" / "animation_frames" / f"action_{action_no}"
    out_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(temp)
    outputs: List[Path] = []
    for idx in range(getattr(image, "n_frames", 1)):
        image.seek(idx)
        out = out_dir / f"frame_{idx:03d}.png"
        image.convert("RGBA").save(out)
        outputs.append(out)
    try:
        temp.unlink()
    except Exception:
        pass
    return outputs
