from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import math
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
from .sff_codec import read_sff, sprite_lookup, build_sff_v1_from_manifest
from .snd_codec import read_snd
from .automation_bank import auto_setup_project, beginner_project_status, make_placeholder_sprite_sheet, ApplyResult
from .no_code_director import write_no_code_dashboard, _auto_build_placeholder_sff, _auto_build_placeholder_snd
from .shared_utils import BaseResult, uniq, rel_path as _safe_rel, backup_file


@dataclass
class StudioPlusResult(BaseResult):
    title: str = "Studio Plus Result"


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup(path: Path) -> Optional[Path]:
    return backup_file(path, "studio_plus")


def _main_def(root: Path) -> Optional[Path]:
    exact = root / f"{root.name}.def"
    if exact.exists():
        return exact
    defs = sorted(root.glob("*.def"))
    return defs[0] if defs else None


def _def_file_paths(root: Path) -> Dict[str, Path]:
    root = Path(root)
    paths: Dict[str, Path] = {}
    dpath = _main_def(root)
    if dpath and dpath.exists():
        paths["def"] = dpath
        try:
            sections = parse_def(read_text_safely(dpath))
            files = sections.get("files")
            if files:
                for key, ext in [("anim", "air"), ("cmd", "cmd"), ("cns", "cns"), ("sprite", "sff"), ("sound", "snd")]:
                    ref = files.values.get(key)
                    if ref:
                        paths[ext] = (dpath.parent / ref.strip().strip('"')).resolve()
        except Exception:
            pass
    for ext in ("air", "cmd", "cns", "sff", "snd"):
        if ext not in paths or not paths[ext].exists():
            found = None
            if ext in {"air", "cmd", "cns"}:
                try:
                    found = find_character_file(root, ext)
                except Exception:
                    found = None
            if found is None:
                exact = root / f"{root.name}.{ext}"
                if exact.exists():
                    found = exact
                else:
                    matches = sorted(root.glob(f"*.{ext}"))
                    found = matches[0] if matches else None
            if found:
                paths[ext] = found
            else:
                paths.setdefault(ext, root / f"{root.name}.{ext}")
    return paths


def _feature_markers(root: Path) -> List[str]:
    markers: List[str] = []
    rx = re.compile(r"MugenForge Feature Bank ID:\s*([A-Za-z0-9_\-]+)")
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix.lower() not in {".cmd", ".cns", ".st", ".air", ".txt", ".md"}:
            continue
        try:
            markers += rx.findall(read_text_safely(p))
        except Exception:
            continue
    return sorted(uniq(markers))


def _action_numbers(air_path: Path) -> List[int]:
    if not air_path.exists():
        return []
    return [a.number for a in parse_air(read_text_safely(air_path))]


def _air_sprite_refs(air_path: Path) -> List[Tuple[int, int]]:
    if not air_path.exists():
        return []
    refs: List[Tuple[int, int]] = []
    seen = set()
    for action in parse_air(read_text_safely(air_path)):
        for frame in action.frames:
            if frame.group < 0 or frame.image < 0:
                continue
            key = (frame.group, frame.image)
            if key not in seen:
                seen.add(key)
                refs.append(key)
    return refs


def _state_numbers(paths: Dict[str, Path]) -> List[int]:
    nums: List[int] = []
    for key in ("cmd", "cns"):
        p = paths.get(key)
        if p and p.exists():
            nums.extend(st.number for st in parse_code(read_text_safely(p)).states)
    for p in sorted(paths.get("def", Path()).parent.glob("*.st")) if paths.get("def") else []:
        try:
            nums.extend(st.number for st in parse_code(read_text_safely(p)).states)
        except Exception:
            pass
    return sorted(set(nums))


def _score_from_findings(findings: Dict[str, object]) -> Tuple[int, List[str]]:
    score = 100
    reasons: List[str] = []
    def ding(points: int, reason: str):
        nonlocal score
        if points <= 0:
            return
        score -= points
        reasons.append(f"-{points}: {reason}")

    missing_required = findings.get("missing_required", []) or []
    ding(min(35, 7 * len(missing_required)), f"missing common files: {', '.join(missing_required)}" if missing_required else "")
    missing_refs = findings.get("missing_references", []) or []
    ding(min(25, 5 * len(missing_refs)), f"DEF references missing files ({len(missing_refs)})" if missing_refs else "")
    missing_common = findings.get("missing_common_actions", []) or []
    ding(min(24, 2 * len(missing_common)), f"missing standard actions ({len(missing_common)})" if missing_common else "")
    missing_sprites = findings.get("missing_sprite_pairs", []) or []
    ding(min(25, len(missing_sprites)), f"AIR references sprites not in SFF ({len(missing_sprites)})" if missing_sprites else "")
    code_issues = findings.get("code_issues", []) or []
    ding(min(20, 2 * len(code_issues)), f"code warnings ({len(code_issues)})" if code_issues else "")
    if not findings.get("has_feature_markers"):
        ding(4, "no installed no-code Feature Bank markers found")
    if not findings.get("has_docs"):
        ding(3, "no beginner/release docs found")
    return max(0, min(100, score)), reasons


def project_findings(root: Path) -> Dict[str, object]:
    root = Path(root)
    audit = scan_project(root)
    paths = _def_file_paths(root)
    actions = _action_numbers(paths.get("air", root / "missing.air"))
    missing_common = [f"{n} {COMMON_ANIMS[n]}" for n in COMMON_ANIMS if n not in set(actions)]
    refs = _air_sprite_refs(paths.get("air", root / "missing.air"))
    missing_sprite_pairs: List[str] = []
    unused_sprite_pairs: List[str] = []
    sff_variant = "none"
    sff_count = 0
    sff_supported = False
    if paths.get("sff") and paths["sff"].exists():
        try:
            info = read_sff(paths["sff"])
            sff_variant = info.variant
            sff_count = len(info.sprites)
            sff_supported = info.is_supported_for_extraction
            lookup = sprite_lookup(info)
            for pair in refs:
                if pair not in lookup:
                    missing_sprite_pairs.append(f"{pair[0]},{pair[1]}")
            used = set(refs)
            for spr in info.sprites[:2000]:
                if spr.key not in used:
                    unused_sprite_pairs.append(f"{spr.group},{spr.image}")
        except Exception as exc:
            missing_sprite_pairs.append(f"SFF scan failed: {exc}")
    elif refs:
        missing_sprite_pairs = [f"{g},{i}" for g, i in refs]
    snd_count = 0
    snd_variant = "none"
    if paths.get("snd") and paths["snd"].exists():
        try:
            snd_info = read_snd(paths["snd"])
            snd_count = len(snd_info.sounds)
            snd_variant = snd_info.variant
        except Exception:
            snd_variant = "unreadable"
    feature_ids = _feature_markers(root)
    docs = [p for p in root.glob("*.md") if p.name.upper().startswith(("README", "MOVE", "MUGENFORGE", "RELEASE", "TEST"))]
    code_issues: List[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix.lower() not in {".cmd", ".cns", ".st"}:
            continue
        try:
            scan = parse_code(read_text_safely(p))
            code_issues.extend([f"{p.name}: {i}" for i in scan.issues[:50]])
        except Exception as exc:
            code_issues.append(f"{p.name}: code scan failed: {exc}")
    duplicates = _duplicate_report(root, paths)
    findings: Dict[str, object] = {
        "root": str(root),
        "paths": {k: str(v) for k, v in paths.items()},
        "found_exts": audit.found_exts,
        "missing_required": audit.missing_required,
        "missing_references": audit.missing_references,
        "missing_common_actions": missing_common,
        "action_count": len(actions),
        "state_count": len(_state_numbers(paths)),
        "air_sprite_ref_count": len(refs),
        "missing_sprite_pairs": missing_sprite_pairs[:300],
        "unused_sprite_pairs": unused_sprite_pairs[:300],
        "sff_variant": sff_variant,
        "sff_sprite_count": sff_count,
        "sff_supported": sff_supported,
        "snd_variant": snd_variant,
        "snd_count": snd_count,
        "feature_ids": feature_ids,
        "has_feature_markers": bool(feature_ids),
        "has_docs": bool(docs),
        "docs": [str(p) for p in docs],
        "code_issues": code_issues,
        "duplicates": duplicates,
    }
    score, score_reasons = _score_from_findings(findings)
    findings["readiness_score"] = score
    findings["score_reasons"] = score_reasons
    return findings


def _duplicate_report(root: Path, paths: Dict[str, Path]) -> Dict[str, List[str]]:
    dup: Dict[str, List[str]] = {"commands": [], "states": [], "actions": []}
    command_locations: Dict[str, List[str]] = {}
    state_locations: Dict[int, List[str]] = {}
    action_locations: Dict[int, List[str]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        try:
            if p.suffix.lower() in {".cmd", ".cns", ".st"}:
                scan = parse_code(read_text_safely(p))
                for cmd in scan.commands:
                    command_locations.setdefault(cmd.name, []).append(f"{p.name}:line {cmd.line}")
                for st in scan.states:
                    state_locations.setdefault(st.number, []).append(f"{p.name}:line {st.line}")
            elif p.suffix.lower() == ".air":
                for action in parse_air(read_text_safely(p)):
                    action_locations.setdefault(action.number, []).append(p.name)
        except Exception:
            continue
    dup["commands"] = [f"{name}: " + ", ".join(locs) for name, locs in command_locations.items() if len(locs) > 1]
    dup["states"] = [f"{num}: " + ", ".join(locs) for num, locs in state_locations.items() if len(locs) > 1]
    dup["actions"] = [f"{num}: " + ", ".join(locs) for num, locs in action_locations.items() if len(locs) > 1]
    return dup


def studio_plus_report_text(root: Path) -> str:
    root = Path(root)
    f = project_findings(root)
    score = int(f["readiness_score"])
    paths = f.get("paths", {}) or {}
    lines = [
        "MugenForge Studio Plus Doctor",
        "=" * 72,
        f"Project: {root}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Readiness score: {score}/100",
        "",
        "Plain-English summary:",
    ]
    if score >= 90:
        lines.append("- The character folder looks release-ready from a static editor scan. Do a real engine test next.")
    elif score >= 70:
        lines.append("- The project is workable, but some missing assets or standard animations should be fixed before serious playtesting.")
    elif score >= 45:
        lines.append("- The project is prototype-level. Use Auto Fix / Build Missing Assets, then test animations and hitboxes.")
    else:
        lines.append("- The folder is not ready yet. Start with Auto Setup / Repair Project or One-Click Playable Prototype.")
    reasons = f.get("score_reasons", []) or []
    if reasons:
        lines += ["", "Why points were lost:"] + [f"- {r}" for r in reasons]
    lines += ["", "Core files:"]
    for k in ("def", "air", "cmd", "cns", "sff", "snd"):
        p = Path(str(paths.get(k, ""))) if paths.get(k) else None
        lines.append(f"- {k.upper():>3}: {_safe_rel(root, p) if p else 'not found'} {'OK' if p and p.exists() else 'MISSING'}")
    lines += [
        "",
        "Coverage:",
        f"- AIR actions: {f.get('action_count', 0)}",
        f"- StateDefs: {f.get('state_count', 0)}",
        f"- AIR sprite references: {f.get('air_sprite_ref_count', 0)}",
        f"- SFF sprites parsed: {f.get('sff_sprite_count', 0)} ({f.get('sff_variant', 'unknown')})",
        f"- SND sounds parsed: {f.get('snd_count', 0)} ({f.get('snd_variant', 'unknown')})",
        f"- Installed no-code features: {len(f.get('feature_ids', []) or [])}",
    ]
    missing_common = f.get("missing_common_actions", []) or []
    if missing_common:
        lines += ["", "Missing standard animations:"] + [f"- {x}" for x in missing_common[:60]]
    missing_sprites = f.get("missing_sprite_pairs", []) or []
    if missing_sprites:
        lines += ["", "AIR sprite refs missing in SFF:"] + [f"- {x}" for x in missing_sprites[:80]]
        if len(missing_sprites) > 80:
            lines.append(f"- ...and {len(missing_sprites) - 80} more")
    dup = f.get("duplicates", {}) or {}
    for key, title in (("commands", "Duplicate commands"), ("states", "Duplicate StateDefs"), ("actions", "Duplicate AIR actions")):
        values = dup.get(key, []) if isinstance(dup, dict) else []
        if values:
            lines += ["", title + ":"] + [f"- {v}" for v in values[:60]]
    issues = f.get("code_issues", []) or []
    if issues:
        lines += ["", "Code warnings:"] + [f"- {i}" for i in issues[:80]]
    feature_ids = f.get("feature_ids", []) or []
    if feature_ids:
        lines += ["", "Installed Feature Bank IDs:"] + [f"- {x}" for x in feature_ids[:120]]
    lines += [
        "",
        "Recommended next step:",
    ]
    if score < 45:
        lines.append("- Use Feature Bank > One-Click Playable Prototype, then reopen this report.")
    elif missing_sprites or missing_common:
        lines.append("- Use Studio Plus > Auto Fix / Build Missing Assets, then use Animation Player and CLSN Editor to tune the result.")
    elif issues:
        lines.append("- Open Code Assistant or Feature Bank and clean the warnings that affect your current moves.")
    else:
        lines.append("- Build a release ZIP, then test in M.U.G.E.N/IKEMEN and adjust feel, damage, and timing.")
    lines += ["", beginner_project_status(root)]
    return "\n".join(lines).rstrip() + "\n"


def write_studio_plus_report(root: Path) -> Path:
    out = Path(root) / "MUGENFORGE_STUDIO_PLUS_REPORT.md"
    out.write_text(studio_plus_report_text(root), encoding="utf-8")
    return out


def write_studio_plus_report_json(root: Path) -> Path:
    out = Path(root) / "mugenforge_studio_plus_report.json"
    out.write_text(json.dumps(project_findings(root), indent=2), encoding="utf-8")
    return out


def _common_action_block(action_no: int) -> str:
    label = COMMON_ANIMS.get(action_no, "placeholder action")
    if action_no in {10, 11, 12, 140, 5020}:
        body = (-20, -58, 20, 0)
        frames = 3
    elif action_no in {5100, 5150}:
        body = (-40, -18, 40, 2)
        frames = 2
    elif action_no in {5030, 5050, 5070, 150, 41, 42}:
        body = (-20, -82, 20, 2)
        frames = 3
    else:
        body = (-18, -88, 18, 0)
        frames = 3
    lines = ["", f"[Begin Action {action_no}] ; {label} - auto-created by Studio Plus"]
    for i in range(frames):
        lines += ["Clsn2: 1", f"  Clsn2[0] = {body[0]},{body[1]},{body[2]},{body[3]}", f"{action_no}, {i}, 0, 0, 6"]
    return "\n".join(lines) + "\n"


def append_missing_standard_air_actions(root: Path) -> StudioPlusResult:
    root = Path(root)
    paths = _def_file_paths(root)
    air_path = paths.get("air") or (root / f"{root.name}.air")
    result = StudioPlusResult("Append Missing Standard AIR Actions")
    if not air_path.exists():
        result.add_warning(f"AIR file not found: {air_path}")
        return result
    text = read_text_safely(air_path)
    existing = {a.number for a in parse_air(text)}
    missing = [n for n in COMMON_ANIMS if n not in existing]
    if not missing:
        result.add_skipped("All common M.U.G.E.N action numbers are already present.")
        return result
    _backup(air_path)
    append = "\n; === MugenForge Studio Plus: standard action placeholders ===\n" + "\n".join(_common_action_block(n) for n in missing)
    write_text_safely(air_path, text.rstrip() + "\n" + append)
    result.add_changed(root, air_path)
    result.add_note(f"Added {len(missing)} standard placeholder AIR actions. Replace their art later; they exist to keep the character testable.")
    return result


def auto_fix_project_plus(root: Path) -> StudioPlusResult:
    root = Path(root)
    result = StudioPlusResult("Studio Plus Auto Fix / Build Missing Assets")
    root.mkdir(parents=True, exist_ok=True)
    setup = auto_setup_project(root)
    result.merge(setup)
    try:
        dash = write_no_code_dashboard(root, None)
        result.merge(dash)
    except Exception as exc:
        result.add_warning(f"Could not write no-code dashboard/profile docs: {exc}")
    sub = append_missing_standard_air_actions(root)
    result.merge(sub)
    try:
        sheet_result = make_placeholder_sprite_sheet(root)
        result.merge(sheet_result)
        build_result = ApplyResult()
        _auto_build_placeholder_sff(root, build_result)
        result.merge(build_result)
        result.add_note("Created/staged placeholder sprite sheet and rebuilt starter SFF.")
    except Exception as exc:
        result.add_warning(f"Placeholder SFF rebuild skipped/failed: {exc}")
    try:
        snd_result = ApplyResult()
        _auto_build_placeholder_snd(root, snd_result)
        result.merge(snd_result)
        result.add_note("Rebuilt placeholder SND from silent WAV bank.")
    except Exception as exc:
        result.add_warning(f"Placeholder SND rebuild skipped/failed: {exc}")
    try:
        docs = write_beginner_docs(root)
        for doc in docs:
            if doc.exists():
                result.add_created(root, doc)
    except Exception as exc:
        result.add_warning(f"Could not write beginner docs: {exc}")
    try:
        result.add_created(root, write_studio_plus_report(root))
        result.add_created(root, write_studio_plus_report_json(root))
    except Exception as exc:
        result.add_warning(f"Could not write Studio Plus report: {exc}")
    return result


def write_beginner_docs(root: Path) -> List[Path]:
    root = Path(root)
    paths = _def_file_paths(root)
    cmd_path = paths.get("cmd")
    commands = []
    if cmd_path and cmd_path.exists():
        try:
            commands = parse_code(read_text_safely(cmd_path)).commands
        except Exception:
            commands = []
    move_list = root / "MOVE_LIST.md"
    lines = ["# Move List", "", "This file is generated from the current CMD file. Rename moves in the Feature Bank or Move Wizard when you are ready.", ""]
    if commands:
        lines += ["| Command name | Input | Time |", "|---|---:|---:|"]
        for cmd in commands:
            lines.append(f"| `{cmd.name}` | `{cmd.command}` | {cmd.time or ''} |")
    else:
        lines.append("No commands detected yet. Use Feature Bank or Move Wizard to add moves.")
    move_list.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    guide = root / "MUGENFORGE_CREATOR_GUIDE.md"
    guide.write_text("""# MugenForge Creator Guide

Beginner workflow:

1. Use **Feature Bank** to choose what your character can do.
2. Use **Studio Plus Doctor** to repair missing setup and placeholder assets.
3. Use **Animation Player** to watch every action.
4. Use **CLSN Editor** to drag hitboxes until they match the art.
5. Replace placeholder sprites and silent sounds with your real assets.
6. Build a release ZIP from Studio Plus when the project score is healthy.

Do not hand-edit CMD/CNS/AIR until you want to. The tool can write the starter code for you.
""", encoding="utf-8")
    test_plan = root / "MUGENFORGE_TEST_PLAN.md"
    test_plan.write_text("""# Test Plan

Use this after every major change.

- Open the character in M.U.G.E.N or IKEMEN.
- Confirm idle, walk, jump, guard, hit, fall, get-up, lose, intro, and win animations show something.
- Test every command in `MOVE_LIST.md`.
- Check that every attack has a visible active hitbox in Animation Player.
- Check that moves return to idle or another intended state.
- Tune damage, velocity, recovery, and pushback after the move feels good.
""", encoding="utf-8")
    return [move_list, guide, test_plan]


def make_project_snapshot(root: Path) -> Path:
    root = Path(root)
    out = root.parent / f"{root.name}_snapshot_{_now_tag()}.zip"
    skip_suffixes = (".bak", ".tmp")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                continue
            if "__pycache__" in p.parts:
                continue
            if any(p.name.endswith(s) for s in skip_suffixes):
                continue
            zf.write(p, p.relative_to(root.parent))
    return out


def build_release_zip_plus(root: Path) -> Path:
    root = Path(root)
    report = write_studio_plus_report(root)
    write_studio_plus_report_json(root)
    write_beginner_docs(root)
    out = root.parent / f"{root.name}_release_{_now_tag()}.zip"
    manifest = {
        "tool": "MugenForge Studio Plus",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project": root.name,
        "report": report.name,
        "findings": project_findings(root),
    }
    temp_manifest = root / "mugenforge_release_manifest.json"
    temp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_dir() or "__pycache__" in p.parts:
                continue
            if p.name.endswith((".bak", ".tmp")) or ".bak_" in p.name:
                continue
            zf.write(p, p.relative_to(root.parent))
    return out


def create_sff_contact_sheet(sff_path: Path, out_path: Path, max_sprites: int = 240, cell: int = 96) -> Path:
    try:
        from PIL import Image, ImageDraw  # type: ignore
        from io import BytesIO
    except Exception as exc:
        raise RuntimeError("Pillow is required for contact sheets. Install with: pip install Pillow") from exc
    sff_path = Path(sff_path)
    out_path = Path(out_path)
    info = read_sff(sff_path)
    sprites = [s for s in info.sprites if s.format_hint in {"pcx", "png"}][:max_sprites]
    if not sprites:
        raise ValueError("No supported PCX/PNG sprites were parsed from this SFF.")
    cols = max(1, min(8, int(math.sqrt(len(sprites))) + 1))
    rows = int(math.ceil(len(sprites) / cols))
    label_h = 18
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    data = sff_path.read_bytes()
    for idx, spr in enumerate(sprites):
        col = idx % cols
        row = idx // cols
        x0 = col * cell
        y0 = row * (cell + label_h)
        try:
            img = Image.open(BytesIO(data[spr.data_offset:spr.data_offset + spr.length])).convert("RGBA")
            img.thumbnail((cell - 8, cell - 8))
            px = x0 + (cell - img.width) // 2
            py = y0 + (cell - img.height) // 2
            bg = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            sheet.paste(bg, (px, py))
        except Exception:
            draw.rectangle((x0 + 8, y0 + 8, x0 + cell - 8, y0 + cell - 8), outline="black")
            draw.text((x0 + 12, y0 + 12), "decode?", fill="black")
        draw.rectangle((x0, y0, x0 + cell - 1, y0 + cell + label_h - 1), outline="gray")
        draw.text((x0 + 3, y0 + cell), f"{spr.group},{spr.image} ax {spr.x},{spr.y}", fill="black")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def export_action_gif(root: Path, action_no: int, out_path: Path, scale: int = 2, draw_clsn: bool = True) -> Path:
    try:
        from PIL import Image, ImageDraw  # type: ignore
        from io import BytesIO
    except Exception as exc:
        raise RuntimeError("Pillow is required for GIF export. Install with: pip install Pillow") from exc
    root = Path(root)
    paths = _def_file_paths(root)
    air_path = paths.get("air")
    sff_path = paths.get("sff")
    if not air_path or not air_path.exists():
        raise FileNotFoundError("AIR file not found.")
    actions = {a.number: a for a in parse_air(read_text_safely(air_path))}
    if action_no not in actions:
        raise KeyError(f"Action {action_no} not found in {air_path.name}.")
    lookup = {}
    data = b""
    if sff_path and sff_path.exists():
        info = read_sff(sff_path)
        lookup = sprite_lookup(info)
        data = sff_path.read_bytes()
    action = actions[action_no]
    frames: List[Image.Image] = []
    durations: List[int] = []
    canvas_w, canvas_h = 320 * scale, 260 * scale
    ox, oy = canvas_w // 2, int(canvas_h * 0.78)
    for frame in action.frames or []:
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(canvas)
        spr = lookup.get((frame.group, frame.image)) if lookup else None
        if spr and spr.format_hint in {"pcx", "png"}:
            try:
                img = Image.open(BytesIO(data[spr.data_offset:spr.data_offset + spr.length])).convert("RGBA")
                if scale != 1:
                    img = img.resize((max(1, img.width * scale), max(1, img.height * scale)))
                px = ox - int((spr.x - frame.x) * scale)
                py = oy - int((spr.y - frame.y) * scale)
                canvas.alpha_composite(img, (px, py))
            except Exception:
                draw.rectangle((ox - 32 * scale, oy - 96 * scale, ox + 32 * scale, oy), outline=(0, 0, 0, 255), width=2)
        else:
            draw.rectangle((ox - 32 * scale, oy - 96 * scale, ox + 32 * scale, oy), outline=(0, 0, 0, 255), width=2)
            draw.text((8, 8), f"{frame.group},{frame.image}", fill=(0, 0, 0, 255))
        if draw_clsn:
            for box in frame.clsn:
                color = (255, 0, 0, 255) if box.kind.lower() == "clsn1" else (0, 70, 255, 255)
                rect = (ox + box.x1 * scale, oy + box.y1 * scale, ox + box.x2 * scale, oy + box.y2 * scale)
                draw.rectangle(rect, outline=color, width=max(1, scale))
        draw.line((ox - 8, oy, ox + 8, oy), fill=(0, 0, 0, 255))
        draw.line((ox, oy - 8, ox, oy + 8), fill=(0, 0, 0, 255))
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE))
        durations.append(max(30, int(max(1, frame.ticks or 1) / 60 * 1000)))
    if not frames:
        raise ValueError(f"Action {action_no} has no frames.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
    return out_path


def batch_import_sprite_folder_to_sff(image_dir: Path, out_sff: Path, default_group: int = 9000, axis_x: int = 32, axis_y: int = 64, ticks: int = 5) -> Tuple[Path, Path]:
    image_dir = Path(image_dir)
    out_sff = Path(out_sff)
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)
    exts = {".png", ".pcx", ".bmp", ".gif"}
    images = [p for p in sorted(image_dir.iterdir()) if p.is_file() and p.suffix.lower() in exts]
    if not images:
        raise ValueError("No PNG/PCX/BMP/GIF images found in the selected folder.")
    records = []
    for idx, img in enumerate(images):
        group, image = _infer_group_image(img.name, default_group, idx)
        relname = img.name
        records.append({
            "index": idx,
            "group": group,
            "image": image,
            "axis": {"x": axis_x, "y": axis_y},
            "filename": relname,
            "source": str(img),
        })
    manifest = {
        "tool": "MugenForge Studio Plus",
        "mode": "batch_sprite_folder_import",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "note": "Filenames like g200_i0.png or 200_0.png keep their group/image IDs. Other files use the default group and sorted index.",
        "sprites": records,
        "suggested_air_ticks": ticks,
    }
    manifest_path = image_dir / "mugenforge_batch_sprite_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    build_sff_v1_from_manifest(manifest_path, out_sff)
    air_out = out_sff.with_suffix(".air_snippet.txt")
    by_group: Dict[int, List[dict]] = {}
    for rec in records:
        by_group.setdefault(int(rec["group"]), []).append(rec)
    lines = ["; AIR snippets generated by Studio Plus batch sprite import"]
    for group in sorted(by_group):
        lines += ["", f"[Begin Action {group}]"]
        for rec in sorted(by_group[group], key=lambda r: int(r["image"])):
            lines.append(f"{rec['group']}, {rec['image']}, 0, 0, {max(1, int(ticks))}")
    air_out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return manifest_path, air_out


def _infer_group_image(name: str, default_group: int, idx: int) -> Tuple[int, int]:
    stem = Path(name).stem.lower()
    patterns = [
        r"g(-?\d+)[_\- ]*i(-?\d+)",
        r"g(-?\d+)[_\- ]*s(-?\d+)",
        r"(?:group)?(-?\d+)[_\- ]+(?:image|img|spr|sprite)?(-?\d+)$",
        r"^(-?\d+)[_\- ]+(-?\d+)$",
    ]
    for pat in patterns:
        m = re.search(pat, stem)
        if m:
            try:
                return int(m.group(1)), int(m.group(2))
            except Exception:
                pass
    return int(default_group), idx


def generate_air_from_sff_groups(root: Path, out_air: Optional[Path] = None, ticks: int = 5, append: bool = False) -> Path:
    root = Path(root)
    paths = _def_file_paths(root)
    sff = paths.get("sff")
    if not sff or not sff.exists():
        raise FileNotFoundError("SFF file not found.")
    info = read_sff(sff)
    if not info.sprites:
        raise ValueError("No sprites parsed from SFF.")
    by_group: Dict[int, List[Tuple[int, int]]] = {}
    for spr in info.sprites:
        by_group.setdefault(spr.group, []).append((spr.image, spr.index))
    lines = ["; Generated by MugenForge Studio Plus from SFF sprite groups", "; Review and rename action meanings after generation."]
    for group in sorted(by_group):
        unique_images = sorted({img for img, _ in by_group[group]})
        lines += ["", f"[Begin Action {group}] ; from SFF group {group}"]
        for img in unique_images:
            lines.append(f"{group}, {img}, 0, 0, {max(1, int(ticks))}")
    text = "\n".join(lines).rstrip() + "\n"
    if append:
        air = paths.get("air") or (root / f"{root.name}.air")
        if air.exists():
            _backup(air)
            old = read_text_safely(air)
            write_text_safely(air, old.rstrip() + "\n\n" + text)
            return air
    if out_air is None:
        out_air = root / "mugenforge_air_from_sff_groups.air"
    Path(out_air).write_text(text, encoding="utf-8")
    return Path(out_air)


def clone_air_action_variant(root: Path, source_action: int, new_action: int, tick_scale: float = 1.0, x_offset: int = 0, y_offset: int = 0) -> Path:
    root = Path(root)
    paths = _def_file_paths(root)
    air = paths.get("air")
    if not air or not air.exists():
        raise FileNotFoundError("AIR file not found.")
    actions = parse_air(read_text_safely(air))
    src = next((a for a in actions if a.number == int(source_action)), None)
    if not src:
        raise KeyError(f"Action {source_action} not found.")
    existing = {a.number for a in actions}
    if int(new_action) in existing:
        raise ValueError(f"Action {new_action} already exists.")
    lines = ["", f"[Begin Action {int(new_action)}] ; cloned from {int(source_action)} by Studio Plus"]
    for fr in src.frames:
        for b in fr.clsn:
            lines.append(f"{b.kind}: 1")
            lines.append(f"  {b.kind}[0] = {b.x1},{b.y1},{b.x2},{b.y2}")
        ticks = max(1, int(round(fr.ticks * float(tick_scale))))
        lines.append(f"{fr.group}, {fr.image}, {fr.x + int(x_offset)}, {fr.y + int(y_offset)}, {ticks}{', ' + fr.flags if fr.flags else ''}")
    _backup(air)
    write_text_safely(air, read_text_safely(air).rstrip() + "\n" + "\n".join(lines).rstrip() + "\n")
    return air


def make_stage_template(parent: Path, name: str = "new_stage") -> Path:
    parent = Path(parent)
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "new_stage"
    stage_dir = parent / safe
    stage_dir.mkdir(parents=True, exist_ok=True)
    def_path = stage_dir / f"{safe}.def"
    if def_path.exists():
        _backup(def_path)
    def_path.write_text(f"""; MugenForge Studio Plus stage template
; Replace the placeholder values and add real sprites/backgrounds later.

[Info]
name = "{safe}"
displayname = "{safe}"
author = "MugenForge"

[Camera]
startx = 0
starty = 0
boundleft = -320
boundright = 320
boundhigh = -240
boundlow = 0
verticalfollow = .2
floortension = 60

[PlayerInfo]
p1startx = -70
p1starty = 0
p1facing = 1
p2startx = 70
p2starty = 0
p2facing = -1
leftbound = -1000
rightbound = 1000

[Bound]
screenleft = 15
screenright = 15

[StageInfo]
zoffset = 220
autoturn = 1
resetBG = 1

[Shadow]
intensity = 128
color = 0,0,0
yscale = .4

[Reflection]
intensity = 0

[Music]
bgmusic =
bgmvolume = 100

[BGdef]
spr = {safe}.sff
debugbg = 1

[BG 0]
type = normal
spriteno = 0,0
start = 0,0
delta = 1,1
mask = 0
""", encoding="utf-8")
    readme = stage_dir / "README_STAGE.md"
    readme.write_text("""# Stage Template

This is a starter M.U.G.E.N stage DEF. Add a real SFF background later, then tune camera bounds and zoffset.
""", encoding="utf-8")
    return stage_dir
