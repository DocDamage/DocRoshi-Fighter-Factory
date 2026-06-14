from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import csv
import json
import re
from typing import Dict, Iterable, List, Sequence, Tuple

from .parsers import read_text_safely, write_text_safely, parse_air, parse_code, parse_def, scan_project, COMMON_ANIMS
from .move_wizard import find_character_file
from .automation_bank import (
    ApplyResult,
    available_presets,
    apply_feature_ids_pack,
    auto_setup_project,
    beginner_project_status,
    kit_names,
    get_preset,
)
from .no_code_workflow import archetype_names, beginner_doctor_report, build_placeholder_sff_from_air, build_placeholder_snd


FF_PLUS_CORE_FEATURES: List[str] = [
    "required_action_library",
    "complete_gethit_library",
    "smart_cancel_system",
    "meter_gain_system",
    "combo_scaling_system",
    "juggle_limiter",
    "hit_pause_bank",
    "hitspark_router",
    "sound_router",
    "training_input_display",
    "training_damage_readout",
    "training_frame_data_readout",
    "ai_personality_router",
    "ai_range_router",
    "throw_tech_system",
    "perfect_guard_system",
    "burst_escape_system",
    "roman_cancel_system",
    "projectile_priority_bank",
    "assist_cooldown_system",
    "round_intro_outro_director",
    "character_bible_docs",
    "combo_recipe_docs",
    "balance_worksheet_docs",
    "test_plan_docs",
    "release_package_audit_docs",
]

FF_PLUS_VISUAL_FEATURES: List[str] = [
    "ffplus_air_template_bank",
    "sprite_axis_audit_docs",
    "step_dust_router",
    "landing_dust_router",
    "screen_shake_router",
    "camera_focus_router",
    "palfx_impact_bank",
    "afterimage_polish_bank",
    "color_palette_manager_docs",
    "readme_generator_docs",
]

FF_PLUS_SYSTEM_FEATURES: List[str] = [
    "chain_cancel_system",
    "jump_cancel_system",
    "dash_cancel_system",
    "super_cancel_system",
    "ex_meter_spender",
    "otg_limiter",
    "wall_bounce_system",
    "ground_bounce_system",
    "hitstun_tuning_bank",
    "guardstun_tuning_bank",
    "guard_spark_router",
    "voice_router",
    "training_hitbox_toggle",
    "training_dummy_guard_mode",
    "ai_combo_router",
    "ai_anti_air_router",
    "ai_escape_router",
    "parry_reward_system",
    "guard_break_meter",
    "stun_meter_system",
    "clash_system",
    "armor_system",
    "invuln_startup_bank",
    "projectile_reflect_router",
    "tag_assist_placeholder",
    "install_timer_hud",
    "boss_phase_router",
    "win_quote_bank",
    "move_unlock_flags",
    "accessibility_notes_docs",
    "credits_license_docs",
]

FF_PLUS_ALL_FEATURES: List[str] = list(dict.fromkeys(FF_PLUS_CORE_FEATURES + FF_PLUS_VISUAL_FEATURES + FF_PLUS_SYSTEM_FEATURES))


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup(path: Path) -> Path:
    return path.with_name(path.name + f".bak_{_timestamp()}")


def _write_file(path: Path, text: str, result: ApplyResult, label: str | None = None, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not overwrite:
            result.skipped_files.append(f"{path.name}: already exists")
            return
        _backup(path).write_text(read_text_safely(path), encoding="utf-8", errors="replace")
        result.changed_files.append(label or f"{path.name}: updated")
    else:
        result.created_files.append(label or f"{path.name}: created")
    write_text_safely(path, text)


def _merge(into: ApplyResult, other: ApplyResult) -> ApplyResult:
    into.changed_files += other.changed_files
    into.created_files += other.created_files
    into.skipped_files += other.skipped_files
    into.warnings += other.warnings
    return into


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def ensure_ff_plus_workspace(root: Path) -> ApplyResult:
    root = Path(root)
    result = ApplyResult()
    folders = [
        "art/raw_sheets",
        "art/clean_slices",
        "art/reference",
        "audio/raw_wavs",
        "audio/voice",
        "docs",
        "docs/move_notes",
        "docs/reports",
        "release",
        "release/screenshots",
        "testing",
        "testing/combo_trials",
        "testing/bug_reports",
        "backups/manual",
        "presets",
        "presets/hitboxes",
        "presets/palettes",
    ]
    for rel in folders:
        path = root / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            result.created_files.append(rel + "/")
    workflow = f"""# MugenForge FF+ Workspace

This folder layout is for non-coders building a M.U.G.E.N character.

## Recommended beginner loop

1. Use **Feature Bank** or **FF+ Studio** to install systems and moves.
2. Replace placeholder sprites in `art/raw_sheets` or `staged_sprites`.
3. Use **Sheet Import** to build or rebuild SFF v1.
4. Use **Animation Player** to check motion.
5. Use **CLSN Editor** to drag hitboxes into place.
6. Use **FF+ Project Doctor** before packaging.

Generated at: {datetime.now().isoformat(timespec='seconds')}
"""
    _write_file(root / "docs" / "FF_PLUS_WORKFLOW.md", workflow, result)
    return result


def make_hitbox_preset_library(root: Path) -> Path:
    root = Path(root)
    data = {
        "schema": "mugenforge.hitbox_presets.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "note": "These are beginner-friendly starting points. Use CLSN Editor to tune visually.",
        "presets": [
            {"name": "standing_body", "kind": "Clsn2", "box": [-18, -88, 18, 0], "use": "basic standing body"},
            {"name": "crouching_body", "kind": "Clsn2", "box": [-22, -58, 22, 0], "use": "crouch body"},
            {"name": "air_body", "kind": "Clsn2", "box": [-18, -82, 18, 4], "use": "jump body"},
            {"name": "light_punch", "kind": "Clsn1", "box": [16, -70, 48, -42], "use": "quick hand hitbox"},
            {"name": "medium_punch", "kind": "Clsn1", "box": [18, -74, 60, -38], "use": "balanced hand hitbox"},
            {"name": "heavy_punch", "kind": "Clsn1", "box": [20, -78, 76, -34], "use": "slow far hand hitbox"},
            {"name": "low_kick", "kind": "Clsn1", "box": [18, -28, 82, -6], "use": "low poke / sweep"},
            {"name": "anti_air", "kind": "Clsn1", "box": [8, -102, 56, -22], "use": "uppercut / launcher"},
            {"name": "projectile_core", "kind": "Clsn1", "box": [20, -68, 64, -32], "use": "projectile active area"},
            {"name": "throw_range", "kind": "Clsn1", "box": [10, -76, 48, -20], "use": "throw detection starter"},
        ],
    }
    out = root / "presets" / "hitboxes" / "mugenforge_hitbox_presets.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def _main_files(root: Path) -> Dict[str, Path | None]:
    return {
        "def": find_character_file(root, "def"),
        "cmd": find_character_file(root, "cmd"),
        "cns": find_character_file(root, "cns"),
        "air": find_character_file(root, "air"),
        "sff": find_character_file(root, "sff"),
        "snd": find_character_file(root, "snd"),
    }


def _installed_feature_ids(root: Path) -> List[str]:
    ids: List[str] = []
    seen = set()
    marker = re.compile(r"MugenForge Feature Bank ID:\s*([A-Za-z0-9_\-]+)")
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".cmd", ".cns", ".st", ".air", ".txt", ".md"}:
            try:
                text = read_text_safely(path)
            except Exception:
                continue
            for match in marker.finditer(text):
                fid = match.group(1)
                if fid not in seen:
                    seen.add(fid)
                    ids.append(fid)
    return ids


def ff_plus_dashboard_report(root: Path) -> str:
    root = Path(root)
    audit = scan_project(root)
    files = _main_files(root)
    installed = _installed_feature_ids(root)
    score = 0
    max_score = 10
    if not audit.missing_required:
        score += 2
    if files.get("sff"):
        score += 1
    if files.get("snd"):
        score += 1
    if files.get("air"):
        try:
            actions = parse_air(read_text_safely(files["air"]))  # type: ignore[arg-type]
            if len(actions) >= 15:
                score += 1
            if any(any(frame.clsn for frame in action.frames) for action in actions):
                score += 1
        except Exception:
            actions = []
    else:
        actions = []
    if len(installed) >= 10:
        score += 1
    if not audit.missing_references:
        score += 1
    if not audit.asset_issues:
        score += 1
    if (root / "docs" / "MUGENFORGE_MOVELIST.md").exists() or (root / "MOVELIST_AUTOGENERATED.md").exists():
        score += 1

    lines = [
        "MugenForge FF+ Project Doctor",
        "=" * 76,
        f"Project: {root}",
        f"Readiness score: {score}/{max_score}",
        "",
        "Main files:",
    ]
    for key, path in files.items():
        lines.append(f"- {key.upper()}: {_relative(root, path) if path else 'not found'}")
    lines += ["", "Detected file types:"]
    for ext, count in sorted(audit.found_exts.items()):
        lines.append(f"- {ext or '[none]'}: {count}")
    lines += ["", f"Installed no-code features: {len(installed)}"]
    if installed:
        lines += [f"- {fid}" for fid in installed[:80]]
        if len(installed) > 80:
            lines.append(f"- ... plus {len(installed) - 80} more")
    if actions:
        lines += ["", f"AIR actions: {len(actions)}"]
        action_numbers = [a.number for a in actions]
        common_present = [n for n in sorted(COMMON_ANIMS) if n in action_numbers]
        missing_common = [n for n in sorted(COMMON_ANIMS) if n not in action_numbers]
        lines.append("Common actions present: " + (", ".join(map(str, common_present[:40])) if common_present else "none"))
        lines.append("Common actions missing: " + (", ".join(map(str, missing_common[:40])) if missing_common else "none"))
    if audit.missing_required:
        lines += ["", "Missing required/common files:"] + [f"- {item}" for item in audit.missing_required]
    if audit.missing_references:
        lines += ["", "Broken DEF references:"] + [f"- {item}" for item in audit.missing_references[:100]]
    if audit.asset_issues:
        lines += ["", "AIR/SFF asset issues:"] + [f"- {item}" for item in audit.asset_issues[:100]]
    if audit.code_issues:
        lines += ["", "Code warnings:"] + [f"- {item}" for item in audit.code_issues[:100]]
    lines += ["", "Plain-English next step:"]
    if audit.missing_required:
        lines.append("- Run FF+ One-Click Upgrade, then rebuild placeholder SFF/SND assets.")
    elif audit.asset_issues:
        lines.append("- Open Animation Player, find missing sprite refs, then rebuild/replace SFF sprites.")
    elif len(installed) < 10:
        lines.append("- Install an archetype kit or FF+ Authoring Pack so the tool writes the code bank for you.")
    else:
        lines.append("- Replace placeholder art/sounds and tune CLSN boxes visually.")
    lines += ["", "", "Feature Bank status:", f"- Available presets: {len(available_presets())}", f"- Available kits: {len(kit_names())}", f"- Available archetypes: {len(archetype_names())}"]
    return "\n".join(lines).strip() + "\n"


def generate_action_catalog(root: Path) -> Path:
    root = Path(root)
    air_path = find_character_file(root, "air")
    if not air_path or not air_path.exists():
        raise FileNotFoundError("No AIR file found. Run Auto Setup or open a character with an AIR file first.")
    actions = parse_air(read_text_safely(air_path))
    out_dir = root / "docs" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "MUGENFORGE_ACTION_CATALOG.csv"
    md_path = out_dir / "MUGENFORGE_ACTION_CATALOG.md"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["action", "label", "frames", "ticks", "clsn1_boxes", "clsn2_boxes", "sprite_refs"])
        for action in actions:
            ticks = sum(max(0, frame.ticks) for frame in action.frames)
            c1 = sum(1 for frame in action.frames for box in frame.clsn if box.kind.lower() == "clsn1")
            c2 = sum(1 for frame in action.frames for box in frame.clsn if box.kind.lower() == "clsn2")
            refs = sorted({f"{frame.group},{frame.image}" for frame in action.frames if frame.group >= 0 and frame.image >= 0})
            writer.writerow([action.number, action.label or COMMON_ANIMS.get(action.number, ""), len(action.frames), ticks, c1, c2, " ".join(refs[:80])])
    lines = ["# MugenForge Action Catalog", "", f"Source: `{_relative(root, air_path)}`", "", "| Action | Label | Frames | Ticks | CLSN1 | CLSN2 |", "|---:|---|---:|---:|---:|---:|"]
    for action in actions:
        ticks = sum(max(0, frame.ticks) for frame in action.frames)
        c1 = sum(1 for frame in action.frames for box in frame.clsn if box.kind.lower() == "clsn1")
        c2 = sum(1 for frame in action.frames for box in frame.clsn if box.kind.lower() == "clsn2")
        label = action.label or COMMON_ANIMS.get(action.number, "")
        lines.append(f"| {action.number} | {label} | {len(action.frames)} | {ticks} | {c1} | {c2} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def generate_asset_index(root: Path) -> Path:
    root = Path(root)
    audit = scan_project(root)
    files = _main_files(root)
    out_dir = root / "docs" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "mugenforge.asset_index.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "main_files": {k: (_relative(root, v) if v else None) for k, v in files.items()},
        "found_exts": audit.found_exts,
        "missing_required": audit.missing_required,
        "missing_references": audit.missing_references,
        "asset_issues": audit.asset_issues,
        "text_files": [_relative(root, p) for p in audit.text_files],
        "binary_files": [_relative(root, p) for p in audit.binary_files],
    }
    json_path = out_dir / "MUGENFORGE_ASSET_INDEX.json"
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md_path = out_dir / "MUGENFORGE_ASSET_INDEX.md"
    lines = ["# MugenForge Asset Index", "", f"Generated: {data['created_at']}", "", "## Main files"]
    for k, v in data["main_files"].items():
        lines.append(f"- **{k.upper()}**: {v or 'not found'}")
    lines += ["", "## File types"]
    for ext, count in sorted(audit.found_exts.items()):
        lines.append(f"- `{ext or '[none]'}`: {count}")
    if audit.missing_references:
        lines += ["", "## Missing DEF references"] + [f"- {item}" for item in audit.missing_references]
    if audit.asset_issues:
        lines += ["", "## AIR/SFF issues"] + [f"- {item}" for item in audit.asset_issues]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def generate_move_list(root: Path) -> Path:
    root = Path(root)
    cmd_path = find_character_file(root, "cmd")
    cns_path = find_character_file(root, "cns")
    commands = []
    states = []
    if cmd_path and cmd_path.exists():
        scan = parse_code(read_text_safely(cmd_path))
        commands = scan.commands
    if cns_path and cns_path.exists():
        scan_cns = parse_code(read_text_safely(cns_path))
        states = scan_cns.states
    installed = _installed_feature_ids(root)
    out = root / "docs" / "MUGENFORGE_MOVELIST.md"
    lines = ["# Move List", "", "Generated by MugenForge FF+.", "", "## Controls / Commands"]
    if commands:
        lines += ["", "| Name | Input | Time | Buffer |", "|---|---|---:|---:|"]
        for cmd in commands:
            lines.append(f"| `{cmd.name}` | `{cmd.command}` | {cmd.time or ''} | {cmd.buffer_time or ''} |")
    else:
        lines.append("No commands detected yet.")
    lines += ["", "## States"]
    if states:
        for st in states[:200]:
            anim = st.values.get("anim", "")
            movetype = st.values.get("movetype", "")
            lines.append(f"- State `{st.number}` — anim `{anim}` — movetype `{movetype}`")
    else:
        lines.append("No StateDefs detected yet.")
    lines += ["", "## Installed no-code features"]
    if installed:
        for fid in installed:
            try:
                preset = get_preset(fid)
                lines.append(f"- **{preset.name}** (`{fid}`): {preset.description}")
            except Exception:
                lines.append(f"- `{fid}`")
    else:
        lines.append("No Feature Bank markers detected yet.")
    lines += ["", "## Creator notes", "- Replace placeholder names with public-facing move names.", "- Test each move in-game and update this list before release."]
    _write_file(out, "\n".join(lines) + "\n", ApplyResult())
    return out


def write_smart_code_bank(root: Path) -> Path:
    root = Path(root)
    out_dir = root / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "mugenforge.smart_code_bank.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "how_to_use": "Pick features/kits/archetypes in MugenForge. The app writes CMD/CNS/AIR code with backups; you handle names, art, sound, and hitbox tuning.",
        "feature_count": len(available_presets()),
        "features": [
            {
                "id": p.feature_id,
                "name": p.name,
                "category": p.category,
                "difficulty": p.difficulty,
                "description": p.description,
                "tags": list(p.tags),
            }
            for p in available_presets()
        ],
        "kits": kit_names(),
        "archetypes": archetype_names(),
        "recommended_no_code_paths": {
            "first_character": ["One-Click Playable Prototype", "FF+ One-Click Upgrade", "Animation Player", "CLSN Editor", "Package ZIP"],
            "better_hitboxes": ["Action Catalog", "Hitbox Presets", "CLSN Editor", "Animation Player"],
            "more_moves": ["Feature Bank", "Move Wizard", "Smart Code Bank"],
            "release_ready": ["Project Doctor", "Asset Index", "Move List", "Release Checklist"],
        },
    }
    out = out_dir / "MUGENFORGE_SMART_CODE_BANK.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = out_dir / "MUGENFORGE_SMART_CODE_BANK.md"
    lines = ["# MugenForge Smart Code Bank", "", f"Available presets: **{len(available_presets())}**", "", "The user should not need to write M.U.G.E.N code by hand. Pick a feature, kit, or archetype; MugenForge writes the blocks with backups.", "", "## Categories"]
    cats: Dict[str, int] = {}
    for p in available_presets():
        cats[p.category] = cats.get(p.category, 0) + 1
    for cat, count in sorted(cats.items()):
        lines.append(f"- {cat}: {count}")
    lines += ["", "## Recommended path", "1. Create/open a project.", "2. Run One-Click Playable Prototype.", "3. Run FF+ One-Click Upgrade.", "4. Replace art/sound.", "5. Tune hitboxes visually.", "6. Run Project Doctor and Package ZIP."]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def generate_release_checklist(root: Path) -> Path:
    root = Path(root)
    report = ff_plus_dashboard_report(root)
    out = root / "docs" / "MUGENFORGE_RELEASE_CHECKLIST.md"
    lines = [
        "# Release Checklist",
        "",
        "## Must pass before sharing",
        "- [ ] Character loads in M.U.G.E.N without errors.",
        "- [ ] Every command in the move list works.",
        "- [ ] Every AIR action used by code has visible sprites.",
        "- [ ] Every attack has intentional Clsn1 and Clsn2 boxes.",
        "- [ ] Sounds are no longer silent placeholders unless intentional.",
        "- [ ] Palettes are checked in-game.",
        "- [ ] Debug overlays are disabled or intentionally kept.",
        "- [ ] README, credits, and permissions are included.",
        "- [ ] ZIP package contains only release files, not temp/backups.",
        "",
        "## Current project doctor snapshot",
        "```text",
        report.rstrip(),
        "```",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def install_required_actions_library(root: Path) -> ApplyResult:
    return apply_feature_ids_pack(Path(root), ["required_action_library", "complete_gethit_library", "ffplus_air_template_bank"])


def install_smart_cancel_suite(root: Path) -> ApplyResult:
    return apply_feature_ids_pack(Path(root), ["smart_cancel_system", "chain_cancel_system", "jump_cancel_system", "dash_cancel_system", "super_cancel_system", "roman_cancel_system"])


def install_training_suite(root: Path) -> ApplyResult:
    return apply_feature_ids_pack(Path(root), ["training_input_display", "training_damage_readout", "training_frame_data_readout", "training_hitbox_toggle", "training_dummy_guard_mode"])


def install_ff_plus_authoring_pack(root: Path) -> ApplyResult:
    root = Path(root)
    result = ApplyResult()
    _merge(result, auto_setup_project(root))
    _merge(result, ensure_ff_plus_workspace(root))
    _merge(result, apply_feature_ids_pack(root, FF_PLUS_CORE_FEATURES + FF_PLUS_VISUAL_FEATURES))
    try:
        hitbox_path = make_hitbox_preset_library(root)
        result.created_files.append(_relative(root, hitbox_path))
    except Exception as exc:
        result.warnings.append(f"Hitbox preset library failed: {exc}")
    for maker in (write_smart_code_bank, generate_action_catalog, generate_asset_index, generate_move_list, generate_release_checklist):
        try:
            out = maker(root)
            result.created_files.append(_relative(root, out))
        except Exception as exc:
            result.warnings.append(f"{maker.__name__} failed: {exc}")
    return result


def one_click_fighter_factory_plus_pass(root: Path) -> ApplyResult:
    root = Path(root)
    result = install_ff_plus_authoring_pack(root)
    # Add deeper system skeletons only after the core pack; these are more advanced but still no-code.
    _merge(result, apply_feature_ids_pack(root, FF_PLUS_SYSTEM_FEATURES))
    try:
        sff = build_placeholder_sff_from_air(root)
        result.changed_files.append(_relative(root, sff))
    except Exception as exc:
        result.warnings.append(f"Placeholder SFF rebuild skipped: {exc}")
    try:
        snd = build_placeholder_snd(root)
        result.changed_files.append(_relative(root, snd))
    except Exception as exc:
        result.warnings.append(f"Placeholder SND rebuild skipped: {exc}")
    try:
        report_path = root / "docs" / "reports" / "MUGENFORGE_FF_PLUS_DOCTOR.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(ff_plus_dashboard_report(root), encoding="utf-8")
        result.created_files.append(_relative(root, report_path))
    except Exception as exc:
        result.warnings.append(f"Final doctor report failed: {exc}")
    return result


def ff_plus_summary_after_result(root: Path, result: ApplyResult) -> str:
    return result.to_text() + "\n\n" + ff_plus_dashboard_report(root) + "\n" + beginner_project_status(root) + "\n" + beginner_doctor_report(root)
