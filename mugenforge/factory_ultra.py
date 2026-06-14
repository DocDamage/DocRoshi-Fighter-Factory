from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import json
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, read_text_safely, scan_project, write_text_safely
from .sff_codec import read_sff
from .snd_codec import read_snd
from .automation_bank import FEATURE_PRESETS, KIT_PRESETS, apply_kit, feature_bank_stats_text
from . import factory_max as fm

FACTORY_ULTRA_VERSION = "3.2.0"
CODE_SUFFIXES = {".cmd", ".cns", ".st"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg"}
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
ASSET_SUFFIXES = IMAGE_SUFFIXES | {".sff", ".snd", ".act", ".wav", ".ogg", ".mp3"}


from .shared_utils import (
    BaseResult,
    uniq,
    rel_path,
    backup_file,
    timestamp,
    write_text_artifact,
    write_json_artifact,
    discover_project_files,
    get_code_files,
    get_all_files,
    parse_safe_int,
    parse_damage_pair,
    scan_air_stats,
    scan_hitdefs,
    scan_commands,
    TEXT_SUFFIXES,
    IMAGE_SUFFIXES,
)

@dataclass
class UltraResult(BaseResult):
    title: str = "Factory Ultra Result"


# Backward-compatible alias for older annotations/import expectations.
MaxResult = UltraResult


def _now() -> str:
    return timestamp()


def _rel(root: Path, path: Path | str | None) -> str:
    if path is None:
        return "missing"
    return rel_path(root, path)


def _backup(path: Path) -> Optional[Path]:
    return backup_file(path, "ultra")


def _write(path: Path, text: str, result: Optional[UltraResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    existed = path.exists()
    if existed and changed:
        _backup(path)
    return write_text_artifact(path, text, result, root, changed, track_existing=True, writer=write_text_safely)


def _write_json(path: Path, payload: object, result: Optional[UltraResult] = None, root: Optional[Path] = None) -> Path:
    return write_json_artifact(path, payload, result, root, track_existing=True)


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    try:
        return fm._discover_files(Path(root))  # type: ignore[attr-defined]
    except Exception:
        return discover_project_files(root)


def _code_files(root: Path) -> List[Path]:
    return get_code_files(root)


def _text_files(root: Path) -> List[Path]:
    return [p for p in get_all_files(root) if p.suffix.lower() in TEXT_SUFFIXES]


def _images(root: Path) -> List[Path]:
    return [p for p in get_all_files(root) if p.suffix.lower() in IMAGE_SUFFIXES]


def _counts(root: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in get_all_files(root):
        ext = p.suffix.lower() or "[none]"
        counts[ext] = counts.get(ext, 0) + 1
    return counts


def _intish(value: object, default: Optional[int] = None) -> Optional[int]:
    return parse_safe_int(value, default)


def _damage_pair(value: str) -> Tuple[int, Optional[int]]:
    return parse_damage_pair(value)


def _air_stats(root: Path) -> Dict[int, Dict[str, int]]:
    return scan_air_stats(root)


def _hit_records(root: Path) -> List[Dict[str, object]]:
    return scan_hitdefs(root)


def _feature_hits(root: Path) -> List[str]:
    marker = re.compile(r"MugenForge Feature Bank ID:\s*([^\s]+)")
    ids: List[str] = []
    for path in _text_files(root):
        try:
            text = read_text_safely(path)
        except Exception:
            continue
        ids.extend(marker.findall(text))
    return sorted(set(ids))


def _cmd_commands(root: Path) -> List[Dict[str, object]]:
    return scan_commands(root)


def write_ultra_audit(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Audit / Doctor")
    audit = scan_project(root)
    files = _discover_files(root)
    air = _air_stats(root)
    hits = _hit_records(root)
    commands = _cmd_commands(root)
    states = []
    controllers = 0
    issues: List[str] = []
    for path in _code_files(root):
        scan = parse_code(read_text_safely(path))
        states.extend(scan.states)
        controllers += len(scan.controllers)
        issues.extend(f"{_rel(root, path)}: {issue}" for issue in scan.issues)
    sff_variant, sff_sprites, snd_sounds = "missing", 0, 0
    try:
        if files.get("sff") and files["sff"].exists():
            sff = read_sff(files["sff"])
            sff_variant = sff.variant
            sff_sprites = len(sff.sprites)
    except Exception as exc:
        result.warnings.append(f"SFF scan failed: {exc}")
    try:
        if files.get("snd") and files["snd"].exists():
            snd_sounds = len(read_snd(files["snd"]).sounds)
    except Exception as exc:
        result.warnings.append(f"SND scan failed: {exc}")
    missing_actions = [f"{num} {COMMON_ANIMS[num]}" for num in COMMON_ANIMS if num not in air]
    score = 100
    score -= min(30, len(audit.missing_required) * 6)
    score -= min(25, len(audit.missing_references) * 4)
    score -= min(18, len(missing_actions))
    score -= 10 if not hits else 0
    score -= 8 if not commands else 0
    score -= 8 if sff_sprites == 0 else 0
    score -= 5 if snd_sounds == 0 else 0
    score = max(0, score)
    payload = {
        "tool": "MugenForge Factory Ultra",
        "version": FACTORY_ULTRA_VERSION,
        "project": root.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "beginner_score": score,
        "files": {k: (_rel(root, v) if isinstance(v, Path) else None) for k, v in files.items() if k != "root"},
        "counts": {
            "commands": len(commands), "states": len(states), "controllers": controllers, "hitdefs": len(hits),
            "air_actions": len(air), "sff_variant": sff_variant, "sff_sprites": sff_sprites, "snd_sounds": snd_sounds,
            "feature_bank_markers": len(_feature_hits(root)),
        },
        "missing_required": audit.missing_required,
        "missing_references": audit.missing_references,
        "missing_common_actions": missing_actions,
        "code_issues": issues[:300],
    }
    _write_json(root / "MUGENFORGE_ULTRA_AUDIT.json", payload, result, root)
    lines = [f"# Factory Ultra Audit: {root.name}", "", f"Generated: {payload['generated']}", "", f"Beginner readiness score: **{score}/100**", "", "## Core files", ""]
    for k in ["def", "cmd", "cns", "air", "sff", "snd"]:
        lines.append(f"- {k.upper()}: `{payload['files'].get(k) or 'missing'}`")
    lines += ["", "## Counts", ""] + [f"- {k}: {v}" for k, v in payload["counts"].items()]
    if missing_actions:
        lines += ["", "## Missing common AIR actions", ""] + [f"- {x}" for x in missing_actions[:120]]
    if audit.missing_references:
        lines += ["", "## Missing DEF references", ""] + [f"- {x}" for x in audit.missing_references[:120]]
    if issues:
        lines += ["", "## Code issues / placeholders", ""] + [f"- {x}" for x in issues[:120]]
    lines += ["", "## Best next move", "", "Run **Factory Ultra → Beginner Task Board** or **Smart Next-Step Queue** and follow the highest-priority item first."]
    _write(root / "MUGENFORGE_ULTRA_AUDIT.md", "\n".join(lines).rstrip() + "\n", result, root)
    result.notes.append(f"Beginner readiness score: {score}/100")
    return result


def write_input_conflict_report(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Input Conflict Report")
    commands = _cmd_commands(root)
    by_name: Dict[str, List[dict]] = {}
    by_input: Dict[str, List[dict]] = {}
    for c in commands:
        by_name.setdefault(str(c["name"]).lower(), []).append(c)
        by_input.setdefault(str(c["norm"]), []).append(c)
    dup_names = {k: v for k, v in by_name.items() if len(v) > 1}
    dup_inputs = {k: v for k, v in by_input.items() if k and len(v) > 1}
    shadows = []
    for a in commands:
        for b in commands:
            if a is b:
                continue
            if a["norm"] and b["norm"] and a["norm"] != b["norm"] and len(str(a["norm"])) < len(str(b["norm"])) and str(a["norm"]) in str(b["norm"]):
                shadows.append({"short": a, "long": b})
    recommended = sorted(commands, key=lambda c: (-len(str(c["norm"])), str(c["name"]).lower()))
    _write_json(root / "MUGENFORGE_INPUT_CONFLICTS.json", {"commands": commands, "duplicate_names": dup_names, "duplicate_inputs": dup_inputs, "possible_shadows": shadows[:200], "recommended_order": recommended}, result, root)
    lines = [f"# Input Conflict Report: {root.name}", "", f"Commands found: **{len(commands)}**", ""]
    if dup_names:
        lines += ["## Duplicate command names", ""] + [f"- `{k}` appears {len(v)} times" for k, v in dup_names.items()]
    if dup_inputs:
        lines += ["", "## Duplicate input sequences", ""] + [f"- `{k}` is used by: " + ", ".join(str(x["name"]) for x in v) for k, v in dup_inputs.items()]
    if shadows:
        lines += ["", "## Possible input shadowing", "", "Longer/specific motions usually need to be above shorter/simple motions."] + [f"- `{x['short']['name']}` may shadow `{x['long']['name']}`" for x in shadows[:80]]
    lines += ["", "## Recommended command order", ""] + [f"- `{c['name']}` = `{c['command']}` ({c['file']}:{c['line']})" for c in recommended[:180]]
    _write(root / "MUGENFORGE_INPUT_CONFLICTS.md", "\n".join(lines).rstrip() + "\n", result, root)
    result.notes.append(f"Commands scanned: {len(commands)}")
    if dup_names or dup_inputs or shadows:
        result.warnings.append("Input conflicts or ordering risks detected.")
    return result


def write_balance_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Balance Lab")
    hits = _hit_records(root)
    air = _air_stats(root)
    csv_path = root / "MUGENFORGE_BALANCE_LAB.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "line", "state", "anim", "damage", "guard_damage", "air_frames", "air_ticks", "first_active", "last_active", "attr", "hitflag", "guardflag", "pausetime", "ground_velocity", "air_velocity", "sparkno", "notes"])
        for h in hits:
            a = air.get(int(h.get("anim") or h["state"]), {})
            notes = []
            if int(h["damage"]) >= 180: notes.append("very high damage")
            if int(h["damage"]) <= 10: notes.append("tiny damage")
            if not h.get("guardflag"): notes.append("no guardflag listed")
            w.writerow([h["file"], h["line"], h["state"], h.get("anim", ""), h["damage"], h.get("guard_damage") or "", a.get("frames", ""), a.get("ticks", ""), a.get("first_active", ""), a.get("last_active", ""), h.get("attr", ""), h.get("hitflag", ""), h.get("guardflag", ""), h.get("pausetime", ""), h.get("ground_velocity", ""), h.get("air_velocity", ""), h.get("sparkno", ""), "; ".join(notes)])
    result.created_files.append(_rel(root, csv_path))
    avg = round(sum(int(h["damage"]) for h in hits) / len(hits), 2) if hits else 0
    lines = [f"# Balance Lab: {root.name}", "", f"HitDefs found: **{len(hits)}**", f"Average listed damage: **{avg}**", ""]
    if hits:
        lines += ["## Highest damage moves", ""] + [f"- State `{h['state']}` anim `{h.get('anim')}` damage `{h['damage']}` — {h['file']}:{h['line']}" for h in sorted(hits, key=lambda x: int(x["damage"]), reverse=True)[:30]]
        lines += ["", "## Tuning rules", "", "- Fast normals should usually be lower damage than slow/heavy moves.", "- Projectiles need recovery or positioning risk.", "- Supers can be high damage, but should cost meter or have clear startup.", "- If a move is safe, fast, long-range, and high damage, it is doing too much."]
    else:
        lines.append("No HitDefs found yet. Use Feature Bank or Move Wizard first.")
    _write(root / "MUGENFORGE_BALANCE_LAB.md", "\n".join(lines).rstrip() + "\n", result, root)
    result.notes.append(f"HitDefs analyzed: {len(hits)}")
    return result


def generate_balance_lab(root: Path) -> UltraResult:
    return write_balance_lab(root)



def write_combo_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Combo Lab")
    hits = sorted(_hit_records(root), key=lambda h: (int(h["damage"]), int(h["state"])))
    commands = _cmd_commands(root)
    lines = [f"# Combo Lab: {root.name}", "", "No-code planning sheet. Pick routes here, then use Feature Bank or Move Wizard to add missing links.", ""]
    if hits:
        low = [h for h in hits if int(h["damage"]) <= 40]
        mid = [h for h in hits if 40 < int(h["damage"]) <= 85]
        high = [h for h in hits if int(h["damage"]) > 85]
        lines += ["## Auto-suggested route ideas", ""]
        if low and mid: lines.append(f"- Beginner confirm: state `{low[0]['state']}` → state `{mid[0]['state']}`")
        if low and mid and high: lines.append(f"- Three-step route: state `{low[0]['state']}` → `{mid[0]['state']}` → `{high[0]['state']}`")
        if mid and high: lines.append(f"- Punish route: state `{mid[-1]['state']}` → `{high[-1]['state']}`")
        lines += ["", "## Fast starters"] + [f"- State `{h['state']}` damage `{h['damage']}`" for h in low[:30]]
        lines += ["", "## Route pieces"] + [f"- State `{h['state']}` damage `{h['damage']}`" for h in mid[:30]]
        lines += ["", "## Finishers"] + [f"- State `{h['state']}` damage `{h['damage']}`" for h in high[:30]]
    else:
        lines.append("No HitDefs found. Install a starter kit or generate moves first.")
    if commands:
        lines += ["", "## Available commands", ""] + [f"- `{c['name']}` = `{c['command']}`" for c in commands[:180]]
    lines += ["", "## Beginner combo rules", "", "- One simple confirm.", "- One risky high-reward route.", "- One anti-air route.", "- No infinites unless this is explicitly a boss prototype."]
    _write(root / "MUGENFORGE_COMBO_LAB.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_combo_trial_builder(root: Path) -> UltraResult:
    return write_combo_lab(root)


def write_smart_next_steps(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Smart Next-Step Queue")
    audit = scan_project(root)
    files = _discover_files(root)
    air = _air_stats(root)
    hits = _hit_records(root)
    tasks: List[Tuple[str, str, str]] = []
    if audit.missing_required:
        tasks.append(("Critical", "Run Factory Ultra One-Click Upgrade", "Repairs starter files and creates scaffolding."))
    if audit.missing_references:
        tasks.append(("Critical", "Fix DEF [Files] references", "Missing references can stop the character from loading."))
    missing_common = [n for n in COMMON_ANIMS if n not in air]
    if missing_common:
        tasks.append(("High", "Complete common AIR actions", f"Missing {len(missing_common)} common actions."))
    if not hits:
        tasks.append(("High", "Add first playable attacks", "Use Feature Bank Beginner Pack, archetype kits, or Move Wizard."))
    if not files.get("sff") or not files["sff"].exists():
        tasks.append(("High", "Build starter SFF", "Use Sprite Lab or placeholder rebuild."))
    if not files.get("snd") or not files["snd"].exists():
        tasks.append(("Medium", "Build starter SND", "Use Sound AutoBank, then replace silent WAVs."))
    tasks += [
        ("Medium", "Open Animation Player", "Check timing before hitbox tuning."),
        ("Medium", "Open CLSN Editor", "Drag/resize boxes to match the art."),
        ("Medium", "Run Balance Lab", "Find overtuned/undertuned moves."),
        ("Low", "Build Ultra Release ZIP", "Share only after reports are clean."),
    ]
    _write_json(root / "MUGENFORGE_DO_THIS_NEXT.json", [{"priority": p, "title": t, "detail": d} for p, t, d in tasks], result, root)
    lines = [f"# Do This Next: {root.name}", "", "Plain-English queue for creators who do not want to code.", ""]
    for i, (priority, title, detail) in enumerate(tasks, 1):
        lines += [f"## {i}. {title} [{priority}]", "", detail, ""]
    _write(root / "MUGENFORGE_DO_THIS_NEXT.md", "\n".join(lines).rstrip() + "\n", result, root)
    result.notes.append(f"Tasks written: {len(tasks)}")
    return result


def generate_beginner_task_board(root: Path) -> UltraResult:
    return write_smart_next_steps(root)


def write_creator_home_dashboard(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Creator Home Dashboard")
    docs = sorted(root.glob("MUGENFORGE_*.md"), key=lambda p: p.name.lower())
    if (root / "docs").exists():
        docs += sorted((root / "docs").glob("*.md"), key=lambda p: p.name.lower())
    lines = [f"# Start Here: {root.name}", "", "Use this as the creator home screen.", "", "## Best beginner loop", "", "1. Run Factory Ultra One-Click Upgrade.", "2. Add features from Feature Bank / kits.", "3. Replace sprites and sounds.", "4. Use Animation Player and CLSN Editor.", "5. Run Audit, Balance Lab, Input Conflicts, Frame Data.", "6. Build Release ZIP.", "", "## Generated docs", ""]
    lines += [f"- [{p.name}]({_rel(root, p)})" for p in docs[:250]] or ["- No generated docs found yet."]
    _write(root / "START_HERE_MUGENFORGE.md", "\n".join(lines).rstrip() + "\n", result, root)
    links = "\n".join(f'<li><a href="{_rel(root, p)}">{p.name}</a></li>' for p in docs[:250]) or "<li>No generated docs found yet.</li>"
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>MugenForge Start Here</title><style>body{{font-family:Arial,sans-serif;max-width:960px;margin:32px auto;line-height:1.45}}li{{margin:4px 0}}</style></head><body><h1>MugenForge Start Here: {root.name}</h1><p>This dashboard is for non-coders. Use Factory Ultra first, then focus on sprites, sounds, timing, and hitboxes.</p><ol><li>One-Click Factory Ultra Upgrade</li><li>Feature Bank kits</li><li>Animation Player</li><li>CLSN Editor</li><li>Balance/Input/Frame reports</li><li>Ultra Release ZIP</li></ol><h2>Generated docs</h2><ul>{links}</ul></body></html>"
    (root / "START_HERE_MUGENFORGE.html").write_text(html, encoding="utf-8")
    result.created_files.append("START_HERE_MUGENFORGE.html")
    return result


def ultra_project_dashboard(root: Path) -> UltraResult:
    return write_creator_home_dashboard(root)


def write_beginner_command_center(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Beginner Command Center")
    result.merge(write_creator_home_dashboard(root), "dashboard")
    result.merge(write_smart_next_steps(root), "tasks")
    text = f"""# Beginner Command Center: {root.name}

Use this file when you are lost.

## Press these buttons first

1. Factory Ultra → One-Click Factory Ultra Upgrade
2. Factory Ultra → Beginner Task Board
3. Feature Bank → install a kit or preset
4. Animation Player → check timing
5. CLSN Editor → tune hitboxes
6. Factory Ultra → Build Ultra Release ZIP

## Rule

Do not hand-code unless you want to. Use the bank, reports, and visual tools first.
"""
    _write(root / "MUGENFORGE_BEGINNER_COMMAND_CENTER.md", text, result, root)
    return result


def write_no_code_function_map(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra No-Code Function Map")
    lines = [f"# No-Code Function Map: {root.name}", "", feature_bank_stats_text(), "", "## Kits", ""]
    for kit, ids in sorted(KIT_PRESETS.items()):
        lines.append(f"### {kit}")
        for fid in ids[:100]:
            name = next((p.name for p in FEATURE_PRESETS if p.feature_id == fid), fid)
            lines.append(f"- `{fid}` — {name}")
        lines.append("")
    lines += ["## Presets", ""]
    for p in FEATURE_PRESETS:
        lines.append(f"- **{p.category}** / `{p.feature_id}` — {p.name}: {p.description}")
    _write(root / "MUGENFORGE_NO_CODE_FUNCTION_MAP.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_no_code_feature_switchboard(root: Path) -> UltraResult:
    return write_no_code_function_map(root)


def write_no_code_recipe_bank(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra No-Code Recipe Bank")
    recipes = [
        ("Beginner balanced fighter", ["Starter Beginner Pack", "Ultra Beginner Moves Kit", "Ultra Beginner Safety Kit"]),
        ("Rushdown pressure", ["Rushdown Archetype Kit", "Ultra Advanced Combat Kit", "Ultra No-Code Production Kit"]),
        ("Projectile/zoner", ["Zoner Archetype Kit", "Ultra Beginner Moves Kit", "Ultra Release Polish Kit"]),
        ("Boss prototype", ["Ultra Boss and Training Kit", "Max AI and Training Kit"]),
    ]
    lines = [f"# No-Code Recipe Bank: {root.name}", "", "Pick a recipe, then install the listed kits from Feature Bank.", ""]
    for name, kits in recipes:
        lines += [f"## {name}", ""] + [f"- {k}" for k in kits] + [""]
    _write(root / "MUGENFORGE_NO_CODE_RECIPE_BANK.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_production_bible(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Production Bible")
    result.merge(write_creator_home_dashboard(root), "dashboard")
    result.merge(write_no_code_function_map(root), "function map")
    result.merge(write_smart_next_steps(root), "tasks")
    text = f"""# Production Bible: {root.name}

This file ties the creator-facing docs together.

## Start here

- `START_HERE_MUGENFORGE.md`
- `MUGENFORGE_DO_THIS_NEXT.md`
- `MUGENFORGE_NO_CODE_FUNCTION_MAP.md`
- `MUGENFORGE_BALANCE_LAB.md`
- `MUGENFORGE_INPUT_CONFLICTS.md`
- `MUGENFORGE_FRAME_DATA.md`

## Core rule

The tool handles code scaffolding. The creator handles taste: art, timing, feel, hitboxes, sounds, and balance decisions.
"""
    _write(root / "MUGENFORGE_PRODUCTION_BIBLE.md", text, result, root)
    return result


def write_generated_code_map(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Generated Code Map")
    rows = []
    marker_re = re.compile(r"MugenForge Feature Bank ID:\s*([^\s]+)")
    for path in _text_files(root):
        for i, line in enumerate(read_text_safely(path).splitlines(), 1):
            m = marker_re.search(line)
            if m:
                rows.append((_rel(root, path), i, m.group(1)))
    lines = [f"# Generated Code Map: {root.name}", "", "Marker-wrapped generated blocks found:", ""]
    lines += [f"- `{fid}` in `{file}` line {line}" for file, line, fid in rows] or ["- No generated markers found yet."]
    _write(root / "MUGENFORGE_GENERATED_CODE_MAP.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def build_asset_dependency_map(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Asset Dependency Map")
    files = _discover_files(root)
    refs: List[Tuple[str, str, str]] = []
    if files.get("def") and files["def"].exists():
        text = read_text_safely(files["def"])
        for k, v in re.findall(r"^\s*([^;#=]+?)\s*=\s*([^;#]+)$", text, re.M):
            clean = v.strip().strip('"')
            if Path(clean).suffix.lower() in {".air", ".cmd", ".cns", ".st", ".sff", ".snd", ".act"}:
                refs.append(("DEF", k.strip(), clean))
    if files.get("air") and files["air"].exists():
        seen = set()
        for action in parse_air(read_text_safely(files["air"])):
            for fr in action.frames:
                key = (fr.group, fr.image)
                if fr.group >= 0 and fr.image >= 0 and key not in seen:
                    refs.append(("AIR", f"action {action.number}", f"sprite {fr.group},{fr.image}"))
                    seen.add(key)
    lines = [f"# Asset Dependency Map: {root.name}", "", "## References", ""] + [f"- {src}: `{key}` → `{val}`" for src, key, val in refs[:600]]
    _write(root / "MUGENFORGE_ASSET_DEPENDENCY_MAP.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_clsn_audit(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra CLSN Audit")
    files = _discover_files(root)
    lines = [f"# CLSN Audit: {root.name}", ""]
    if files.get("air") and files["air"].exists():
        for action in parse_air(read_text_safely(files["air"])):
            frames = len(action.frames)
            atk = sum(1 for fr in action.frames if any(b.kind.lower() == "clsn1" for b in fr.clsn))
            body = sum(1 for fr in action.frames if any(b.kind.lower() == "clsn2" for b in fr.clsn))
            if frames and (atk or body < frames):
                lines.append(f"- Action `{action.number}`: frames={frames}, attack-box frames={atk}, body-box frames={body}")
    else:
        lines.append("No AIR file found.")
    _write(root / "MUGENFORGE_CLSN_AUDIT.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_controller_snippet_library(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Controller Snippet Library")
    text = """# Controller Snippet Library

Common M.U.G.E.N building blocks:

## ChangeState
Routes to another state.

## HitDef
Defines an attack hit.

## PlaySnd
Plays a sound from SND.

## Explod / Helper / Projectile
Creates visual effects, helpers, or projectiles.

Use Feature Bank and Code Assistant to insert these without typing from scratch.
"""
    _write(root / "MUGENFORGE_CONTROLLER_SNIPPET_LIBRARY.md", text, result, root)
    return result


def generate_cancel_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Cancel / State Flow Lab")
    text = """# Cancel / State Flow Lab

Use this sheet to design what can cancel into what without hand-coding first.

## Beginner rules

- Light normals can route to medium/heavy if the character needs simple chains.
- Specials should usually require hit/block confirm or commitment.
- EX/super cancels should cost resources.
- Whiff cancels are powerful; enable only when intentional.
"""
    _write(root / "MUGENFORGE_CANCEL_LAB.md", text, result, root)
    return result


def generate_asset_usage_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Asset Usage Lab")
    counts = _counts(root)
    lines = [f"# Asset Usage Lab: {root.name}", "", "## File counts", ""] + [f"- `{k}`: {v}" for k, v in sorted(counts.items())]
    lines += ["", "## Beginner note", "", "Use this to see whether your project is mostly placeholders, source art, code, or packed assets."]
    _write(root / "MUGENFORGE_ASSET_USAGE_LAB.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def generate_sprite_axis_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Sprite Axis Lab")
    files = _discover_files(root)
    lines = [f"# Sprite Axis Lab: {root.name}", "", "Axis consistency checklist:", "", "- Feet should stay planted across idle/walk/stand attacks.", "- Projectiles should spawn from a consistent hand/mouth/origin point.", "- Knockdown sprites need low body boxes and sensible origin placement.", ""]
    if files.get("sff") and files["sff"].exists():
        try:
            sff = read_sff(files["sff"])
            lines += [f"Parsed SFF variant: `{sff.variant}`", f"Parsed sprite records: `{len(sff.sprites)}`", ""]
            for sp in sff.sprites[:200]:
                lines.append(f"- Group `{sp.group}` image `{sp.image}` axis=({sp.x},{sp.y}) size={sp.length}")
        except Exception as exc:
            lines.append(f"SFF scan failed: {exc}")
    else:
        lines.append("No SFF found yet.")
    _write(root / "MUGENFORGE_SPRITE_AXIS_LAB.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def generate_ai_tuning_lab(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra AI Tuning Lab")
    hits = _hit_records(root)
    csv_path = root / "MUGENFORGE_AI_TUNING_LAB.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "anim", "range", "easy_weight", "normal_weight", "hard_weight", "notes"])
        for h in hits:
            dmg = int(h.get("damage", 0) or 0)
            rng = "far" if dmg >= 100 else "mid" if dmg >= 45 else "close"
            w.writerow([h.get("state"), h.get("anim"), rng, 1, 3, 5, "Tune after playtesting."])
    result.created_files.append(_rel(root, csv_path))
    lines = ["# Factory Ultra AI Tuning Lab", "", "Beginner-readable AI move weighting sheet. This does not force AI code; it gives you tuning notes.", "", "| State | Anim | Range | Easy | Normal | Hard |", "|---:|---:|---|---:|---:|---:|"]
    for h in hits[:300]:
        dmg = int(h.get("damage", 0) or 0)
        rng = "far" if dmg >= 100 else "mid" if dmg >= 45 else "close"
        lines.append(f"| {h.get('state')} | {h.get('anim')} | {rng} | 1 | 3 | 5 |")
    _write(root / "MUGENFORGE_AI_TUNING_LAB.md", "\n".join(lines).rstrip() + "\n", result, root)
    result.notes.append(f"AI tuning rows exported: {len(hits)}")
    return result


def generate_move_cards(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Move Cards")
    hits = _hit_records(root)
    cards = "".join(f"<section><h2>State {h['state']}</h2><p>Damage: {h['damage']}<br>Anim: {h.get('anim')}<br>Source: {h['file']}:{h['line']}</p></section>" for h in hits) or "<p>No HitDefs found yet.</p>"
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Move Cards</title><style>body{{font-family:Arial}}section{{border:1px solid #aaa;padding:12px;margin:10px;border-radius:8px}}</style></head><body><h1>Move Cards: {root.name}</h1>{cards}</body></html>"
    (root / "MUGENFORGE_MOVE_CARDS.html").write_text(html, encoding="utf-8")
    result.created_files.append("MUGENFORGE_MOVE_CARDS.html")
    return result


def generate_input_map_assistant(root: Path) -> UltraResult:
    return write_input_conflict_report(root)


def generate_release_readiness_report(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Release Readiness")
    result.merge(write_ultra_audit(root), "audit")
    result.merge(write_clsn_audit(root), "clsn")
    result.merge(write_input_conflict_report(root), "inputs")
    lines = [f"# Release Readiness: {root.name}", "", "Run this before sharing a build.", "", "- Audit generated.", "- CLSN audit generated.", "- Input conflict report generated.", "- Build Ultra Release ZIP after checking these files."]
    _write(root / "MUGENFORGE_RELEASE_READINESS.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def write_compatibility_matrix(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Compatibility Matrix")
    patterns = {
        "MUGEN 1.1 / zoom-like hints": r"\bzoom\b|stagefit|localcoord",
        "Palette logic": r"remappal|palno|palfx",
        "IKEMEN/addon hints": r"ikemen|zss|redirectid|map\(",
        "Heavy helper/projectile/explod usage": r"type\s*=\s*(helper|explod|proj|projectile)",
        "Debug display controllers": r"displaytoclipboard|appendtoclipboard",
    }
    hits = {k: [] for k in patterns}
    for path in _text_files(root):
        text = read_text_safely(path)
        for label, pat in patterns.items():
            if re.search(pat, text, re.I):
                hits[label].append(_rel(root, path))
    lines = [f"# Compatibility Matrix: {root.name}", "", "Heuristic scan only. Always test in the exact engine/version you plan to support.", ""]
    for label, vals in hits.items():
        lines += [f"## {label}", ""] + ([f"- `{v}`" for v in vals[:80]] if vals else ["- No obvious usage found."]) + [""]
    _write(root / "MUGENFORGE_COMPATIBILITY_MATRIX.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def create_sff_sprite_atlas(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra SFF Sprite Atlas")
    files = _discover_files(root)
    lines = [f"# SFF Sprite Atlas: {root.name}", ""]
    if files.get("sff") and files["sff"].exists():
        try:
            sff = read_sff(files["sff"])
            lines += [f"Variant: `{sff.variant}`", f"Sprites parsed: `{len(sff.sprites)}`", ""]
            lines += [f"- group `{sp.group}` image `{sp.image}` axis=({sp.x},{sp.y}) bytes={sp.length}" for sp in sff.sprites[:600]]
        except Exception as exc:
            lines.append(f"SFF scan failed: {exc}")
    else:
        lines.append("No SFF file found.")
    _write(root / "MUGENFORGE_SFF_SPRITE_ATLAS.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def create_action_strip_previews(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Action Strip Previews")
    files = _discover_files(root)
    lines = [f"# Action Strip Preview Plan: {root.name}", "", "Text-only action strip index. Use Animation Player for visual playback.", ""]
    if files.get("air") and files["air"].exists():
        for action in parse_air(read_text_safely(files["air"]))[:400]:
            refs = ", ".join(f"{fr.group},{fr.image}" for fr in action.frames[:18])
            ticks = sum(max(0, fr.ticks) for fr in action.frames)
            lines.append(f"- Action `{action.number}` frames={len(action.frames)} ticks={ticks} refs={refs}")
    else:
        lines.append("No AIR file found.")
    _write(root / "MUGENFORGE_ACTION_STRIP_PREVIEWS.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def create_snd_waveform_sheet(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra SND Waveform Sheet")
    files = _discover_files(root)
    rows = []
    if files.get("snd") and files["snd"].exists():
        try:
            info = read_snd(files["snd"])
            for idx, snd in enumerate(info.sounds):
                rows.append([getattr(snd, "group", 0), getattr(snd, "sound", 0), getattr(snd, "offset", getattr(snd, "riff_offset", 0)), getattr(snd, "length", 0), getattr(snd, "sample_rate", ""), getattr(snd, "channels", "")])
        except Exception as exc:
            result.warnings.append(f"SND scan failed: {exc}")
    csv_path = root / "MUGENFORGE_SND_WAVEFORM_SHEET.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "sound", "offset", "bytes", "sample_rate", "channels"])
        w.writerows(rows)
    result.created_files.append(_rel(root, csv_path))
    lines = [f"# SND Waveform Sheet: {root.name}", "", f"Sounds parsed: **{len(rows)}**", ""] + [f"- {r[0]},{r[1]} bytes={r[3]} rate={r[4]} channels={r[5]}" for r in rows[:200]]
    _write(root / "MUGENFORGE_SND_WAVEFORM_SHEET.md", "\n".join(lines).rstrip() + "\n", result, root)
    return result


def create_autosave_snapshot(root: Path) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Safety Snapshot")
    out_dir = root / "snapshots"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{root.name}_snapshot_{_now()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
            if path.is_dir():
                continue
            rel = path.relative_to(root)
            rel_s = str(rel).replace("\\", "/")
            if "__pycache__" in rel_s.lower() or ".git" in rel_s.lower() or rel_s.startswith("snapshots/"):
                continue
            z.write(path, arcname=f"{root.name}/{rel_s}")
    result.created_files.append(_rel(root, out))
    return result


def auto_tune_damage(root: Path, damage_scale: float = 1.0, max_damage: int = 180, min_damage: int = 1) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Auto-Tune Damage")
    scale = max(0.05, float(damage_scale))
    max_damage = max(1, int(max_damage))
    min_damage = max(0, int(min_damage))
    section_re = re.compile(r"^\s*\[\s*([^\]]+)\s*\]\s*(?:;.*)?$", re.I)
    dmg_re = re.compile(r"^(\s*damage\s*=\s*)(-?\d+)(\s*,\s*(-?\d+))?(.*)$", re.I)
    changed_total = 0
    for path in _code_files(root):
        old = read_text_safely(path)
        sections: List[List[str]] = []
        cur: List[str] = []
        for line in old.splitlines():
            if section_re.match(line) and cur:
                sections.append(cur)
                cur = [line]
            else:
                cur.append(line)
        if cur:
            sections.append(cur)
        changed = 0
        out_sections: List[str] = []
        for sec in sections:
            sec_text = "\n".join(sec)
            is_hitdef = bool(re.search(r"^\s*type\s*=\s*HitDef\b", sec_text, re.I | re.M))
            out: List[str] = []
            for line in sec:
                m = dmg_re.match(line)
                if is_hitdef and m:
                    primary = int(m.group(2))
                    secondary = int(m.group(4)) if m.group(4) is not None else None
                    new_primary = max(min_damage, min(max_damage, int(round(primary * scale))))
                    new_line = f"{m.group(1)}{new_primary}"
                    if secondary is not None:
                        new_line += f",{max(0, min(max_damage, int(round(secondary * scale))))}"
                    new_line += m.group(5)
                    if new_line != line:
                        line = new_line + " ; Factory Ultra tuned"
                        changed += 1
                out.append(line)
            out_sections.append("\n".join(out))
        new = "\n".join(out_sections).rstrip() + "\n"
        if changed and new != old:
            _backup(path)
            write_text_safely(path, new)
            result.changed_files.append(f"{_rel(root, path)}: tuned {changed} damage line(s)")
            changed_total += changed
    if not changed_total:
        result.skipped_files.append("No HitDef damage lines changed.")
    result.notes.append(f"Damage scale: {scale}; max clamp: {max_damage}; changed lines: {changed_total}")
    return result


def create_character_variant(root: Path, variant_name: str) -> UltraResult:
    root = Path(root)
    result = UltraResult("Factory Ultra Character Variant Clone")
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(variant_name)).strip("_") or f"{root.name}_variant"
    dest = root.parent / safe
    if dest.exists():
        dest = root.parent / f"{safe}_{_now()}"
    def ignore(_dir: str, names: Sequence[str]) -> set[str]:
        return {n for n in names if n == "__pycache__" or n.startswith(".") or ".bak_" in n or n.lower() in {"exports", "imports", "snapshots"}}
    shutil.copytree(root, dest, ignore=ignore)
    defs = sorted(dest.glob("*.def"), key=lambda p: p.name.lower())
    if defs:
        old_def = defs[0]
        new_def = dest / f"{safe}.def"
        if old_def.name != new_def.name:
            old_def.rename(new_def)
        text = read_text_safely(new_def)
        if not re.search(r"^\s*\[\s*Info\s*\]", text, re.I | re.M):
            text = f"[Info]\nname = \"{safe}\"\ndisplayname = \"{variant_name}\"\n\n" + text
        else:
            if re.search(r"^\s*name\s*=", text, re.I | re.M):
                text = re.sub(r"^(\s*name\s*=\s*).*$", rf"\1\"{safe}\"", text, count=1, flags=re.I | re.M)
            if re.search(r"^\s*displayname\s*=", text, re.I | re.M):
                text = re.sub(r"^(\s*displayname\s*=\s*).*$", rf"\1\"{variant_name}\"", text, count=1, flags=re.I | re.M)
        write_text_safely(new_def, text)
    _write(dest / "MUGENFORGE_VARIANT_NOTES.md", f"# Variant: {variant_name}\n\nCreated from `{root.name}` on {datetime.now().isoformat(timespec='seconds')}.\n", result, dest)
    result.created_files.append(str(dest))
    result.notes.append(f"Variant cloned to: {dest}")
    return result


def write_ultra_task_board(root: Path) -> UltraResult:
    return write_smart_next_steps(root)


# ---------------------------------------------------------------------------
# Final v3.0 stable overrides
# ---------------------------------------------------------------------------

def write_frame_data_report(root: Path) -> UltraResult:  # type: ignore[override]
    root = Path(root)
    result = UltraResult("Factory Ultra Frame Data Export")
    files = _discover_files(root)
    actions = []
    air = files.get("air")
    if air and air.exists():
        try:
            actions = parse_air(read_text_safely(air))
        except Exception as exc:
            result.warnings.append(f"AIR parse failed: {exc}")
    out_dir = root / "mugenforge_ultra"
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / "frame_data.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["action", "label", "frames", "ticks", "attack_box_frames", "body_box_frames", "seconds_at_60fps"])
        for action in actions:
            ticks = sum(max(0, int(fr.ticks)) for fr in action.frames)
            attack = sum(1 for fr in action.frames if any(str(b.kind).lower() == "clsn1" for b in fr.clsn))
            body = sum(1 for fr in action.frames if any(str(b.kind).lower() == "clsn2" for b in fr.clsn))
            w.writerow([action.number, getattr(action, "label", ""), len(action.frames), ticks, attack, body, round(ticks / 60, 3)])
    lines = ["# Factory Ultra Frame Data Export", "", "Rough timing export based on AIR ticks. Test in-game before finalizing feel.", "", f"CSV: `{_rel(root, csv_path)}`", "", "| Action | Frames | Ticks | Attack box frames | Body box frames |", "|---:|---:|---:|---:|---:|"]
    for action in actions[:500]:
        ticks = sum(max(0, int(fr.ticks)) for fr in action.frames)
        attack = sum(1 for fr in action.frames if any(str(b.kind).lower() == "clsn1" for b in fr.clsn))
        body = sum(1 for fr in action.frames if any(str(b.kind).lower() == "clsn2" for b in fr.clsn))
        lines.append(f"| {action.number} | {len(action.frames)} | {ticks} | {attack} | {body} |")
    _write(root / "MUGENFORGE_FRAME_DATA.md", "\n".join(lines).rstrip()+"\n", result, root)
    result.created_files.append(_rel(root, csv_path))
    result.notes.append(f"AIR actions exported: {len(actions)}")
    return result


def generate_frame_data_lab(root: Path) -> UltraResult:  # type: ignore[override]
    return write_frame_data_report(root)



def one_click_factory_ultra_upgrade(root: Path) -> UltraResult:  # type: ignore[override]
    root = Path(root)
    result = UltraResult("Factory Ultra One-Click No-Code Production Upgrade")
    try:
        result.merge(fm.one_click_factory_max_upgrade(root), "Factory Max")
    except Exception as exc:
        result.warnings.append(f"Factory Max base upgrade failed: {exc}")
    for kit in ["Ultra No-Code Production Kit", "Ultra Beginner Safety Kit", "Ultra Release Polish Kit", "Max Beginner Full Production Kit"]:
        try:
            result.merge(apply_kit(root, kit), f"kit {kit}")
        except Exception as exc:
            result.warnings.append(f"Could not apply kit {kit}: {exc}")
    for label, fn in [
        ("command center", write_beginner_command_center),
        ("smart next steps", write_smart_next_steps),
        ("function map", write_no_code_function_map),
        ("asset QA", generate_asset_usage_lab),
        ("frame data", generate_frame_data_lab),
        ("balance", generate_balance_lab),
        ("inputs", generate_input_map_assistant),
        ("CLSN", write_clsn_audit),
        ("readiness", generate_release_readiness_report),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.warnings.append(f"{label} failed: {exc}")
    result.notes.append("Factory Ultra turns the project into a guided creator suite: reports and scaffolds first, creative tuning second.")
    return result


def one_click_ultra_production_pass(root: Path) -> UltraResult:  # type: ignore[override]
    return one_click_factory_ultra_upgrade(root)

def _code_files_text(root: Path):
    for p in _code_files(Path(root)):
        text = read_text_safely(p)
        yield p, text, parse_code(text)

# --- v3.0.1 safety override: release zips should not recursively include old release zips. ---
def _factory_ultra_release_impl(root: Path) -> UltraResult:  # type: ignore[override]
    root = Path(root)
    result = UltraResult("Factory Ultra Release ZIP")
    for label, fn in [
        ("readiness", generate_release_readiness_report),
        ("command center", write_beginner_command_center),
        ("asset QA", generate_asset_usage_lab),
        ("balance", generate_balance_lab),
        ("frame data", generate_frame_data_lab),
        ("input map", generate_input_map_assistant),
    ]:
        try:
            result.merge(fn(root), label)
        except Exception as exc:
            result.warnings.append(f"{label} failed: {exc}")
    out_dir = root / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{root.name}_factory_ultra_release_{_now()}.zip"
    manifest = root / "MUGENFORGE_ULTRA_RELEASE_MANIFEST.json"
    manifest.write_text(json.dumps({"tool": "MugenForge Factory Ultra", "version": FACTORY_ULTRA_VERSION, "project": root.name, "generated": datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")

    def skip_file(p: Path) -> bool:
        rel_s = str(p.relative_to(root)).replace("\\", "/")
        low = rel_s.lower()
        if p == out:
            return True
        if "__pycache__" in low or ".git" in low or ".bak_" in low or low.endswith((".pyc", ".tmp")):
            return True
        if low.startswith("snapshots/"):
            return True
        # Never nest previous generated release ZIPs inside a release ZIP.
        if low.startswith("exports/") and low.endswith(".zip"):
            return True
        return False

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
            if p.is_dir() or skip_file(p):
                continue
            rel_s = str(p.relative_to(root)).replace("\\", "/")
            z.write(p, arcname=f"{root.name}/{rel_s}")
    result.created_files += [_rel(root, manifest), _rel(root, out)]
    result.notes.append("Factory Ultra release ZIP built without snapshots, backups, temp files, or nested release ZIPs.")
    return result


def build_ultra_release_zip(root: Path) -> UltraResult:  # type: ignore[override]
    return _factory_ultra_release_impl(root)


def build_factory_ultra_release_zip(root: Path) -> UltraResult:  # type: ignore[override]
    return _factory_ultra_release_impl(root)
