from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import csv
import json
from typing import Dict, List

from .automation_bank import (
    ApplyResult,
    FEATURE_PRESETS,
    KIT_PRESETS,
    apply_kit,
    auto_setup_project,
    beginner_project_status,
    export_code_bank_template,
    feature_bank_stats,
    feature_bank_stats_text,
    make_placeholder_sprite_sheet,
    _ensure_def_files_section,
)


@dataclass(frozen=True)
class ArchetypeProfile:
    name: str
    kit_name: str
    description: str
    suggested_buttons: Dict[str, str]
    creator_goals: List[str]
    tuning_notes: List[str]


ARCHETYPE_PROFILES: Dict[str, ArchetypeProfile] = {
    "Balanced Arcade Fighter": ArchetypeProfile(
        name="Balanced Arcade Fighter",
        kit_name="Balanced Arcade Fighter",
        description="A general-purpose shoto-style starting point: pokes, crouch tools, fireball, anti-air, dash, roll, and round-flow poses.",
        suggested_buttons={"x":"light punch", "y":"medium punch", "z":"heavy punch", "a":"light kick", "b":"medium kick", "c":"heavy kick", "s":"taunt"},
        creator_goals=["Make idle/walk/jump readable first.", "Replace normal attack sprites before specials.", "Tune hitboxes visually before changing damage."],
        tuning_notes=["Keep light attacks fast and low damage.", "Make fireball recovery long enough to be punishable.", "Dragon punch should be strong but risky."],
    ),
    "Rushdown Combo Fighter": ArchetypeProfile(
        name="Rushdown Combo Fighter",
        kit_name="Rushdown Combo Fighter",
        description="Fast pressure character with run, dash attack, target combo, auto-combo, launcher routes, rekka chain, and rush super.",
        suggested_buttons={"x":"combo starter", "y":"pressure normal", "z":"heavy ender", "a":"low/check", "b":"launcher", "c":"special/rekka", "s":"taunt/debug"},
        creator_goals=["Make forward movement feel good.", "Check that chain windows do not trap the player forever.", "Use Animation Player to verify combo rhythm."],
        tuning_notes=["Rushdown should win close range but work harder from full screen.", "Do not make every move plus/safe by default.", "Give big enders clear recovery."],
    ),
    "Projectile Zoner Fighter": ArchetypeProfile(
        name="Projectile Zoner Fighter",
        kit_name="Projectile Zoner Fighter",
        description="Screen-control starter with multiple projectile ideas, teleport/retreat options, reflect shield, and simple AI examples.",
        suggested_buttons={"x":"quick poke", "y":"fireball", "z":"beam/heavy projectile", "a":"low check", "b":"retreat", "c":"reflect/utility", "s":"taunt"},
        creator_goals=["Give projectiles distinct speeds and recovery.", "Make close-range normals weaker than a rushdown character.", "Use helpers sparingly until sprites are replaced."],
        tuning_notes=["Slow fireballs should create approach cover.", "Teleport needs recovery or it will become abusive.", "Reflect shield should be short and readable."],
    ),
    "Grappler Fighter": ArchetypeProfile(
        name="Grappler Fighter",
        kit_name="Grappler Fighter",
        description="Close-range heavy character with armor, throws, command grab, guard-break, and super grab starters.",
        suggested_buttons={"x":"short jab", "y":"throw/command normal", "z":"heavy strike", "a":"low", "b":"armor approach", "c":"command grab", "s":"taunt"},
        creator_goals=["Make walk/dash speed slower but satisfying.", "Give throws clear range and startup.", "Use hitboxes to make heavy attacks big but not instant."],
        tuning_notes=["Command grabs should lose to jump/backdash if too strong.", "Armor should have obvious recovery.", "Big damage needs clear commitment."],
    ),
    "Anime Air Mobility Fighter": ArchetypeProfile(
        name="Anime Air Mobility Fighter",
        kit_name="Anime Air Mobility Fighter",
        description="Air-focused starter with double jump, wall jump, air dash, dive kick, air fireball, and air-combo route pieces.",
        suggested_buttons={"x":"air jab", "y":"air chain", "z":"launcher", "a":"dive kick", "b":"air dash", "c":"air fireball", "s":"taunt"},
        creator_goals=["Get jump arcs and air dash readable first.", "Use CLSN Editor heavily on air attacks.", "Make landing recovery visible."],
        tuning_notes=["Air mobility should cost positioning or recovery.", "Cross-up hitboxes need careful tuning.", "Keep air projectiles slower than ground options."],
    ),
    "Boss / Flashy Character": ArchetypeProfile(
        name="Boss / Flashy Character",
        kit_name="Boss / Flashy Character",
        description="Big presentation starter with armor, teleport, helper/clone ideas, install, beam/cinematic supers, aura, dust, and spark placeholders.",
        suggested_buttons={"x":"heavy poke", "y":"helper", "z":"beam", "a":"armor", "b":"teleport", "c":"super", "s":"aura/taunt"},
        creator_goals=["Replace FX sprites early so placeholders do not hide timing problems.", "Keep boss moves readable despite being strong.", "Test against simple AI after every few changes."],
        tuning_notes=["Boss strength should come from spectacle and timing, not invisible hitboxes.", "Helpers need limits.", "SuperPause should not interrupt every minor action."],
    ),
}


def archetype_names() -> List[str]:
    return list(ARCHETYPE_PROFILES.keys())


def _profile(name: str | None) -> ArchetypeProfile:
    if name and name in ARCHETYPE_PROFILES:
        return ARCHETYPE_PROFILES[name]
    return ARCHETYPE_PROFILES["Balanced Arcade Fighter"]


def archetype_preview_text(name: str | None) -> str:
    profile = _profile(name)
    ids = KIT_PRESETS.get(profile.kit_name, [])
    lines = [f"Archetype: {profile.name}", "", profile.description, "", f"Installs kit: {profile.kit_name}", f"Features: {len(ids)}", ""]
    lines.append("Button map:")
    for button, use in profile.suggested_buttons.items():
        lines.append(f"- {button}: {use}")
    lines.append("\nCreator goals:")
    lines.extend(f"- {goal}" for goal in profile.creator_goals)
    lines.append("\nTuning notes:")
    lines.extend(f"- {note}" for note in profile.tuning_notes)
    lines.append("\nFeature IDs:")
    lines.extend(f"- {fid}" for fid in ids)
    return "\n".join(lines).strip() + "\n"


def _merge(target: ApplyResult, source: ApplyResult) -> None:
    target.changed_files += source.changed_files
    target.skipped_files += source.skipped_files
    target.warnings += source.warnings
    target.created_files += source.created_files


def _write_text_if_changed(path: Path, text: str, result: ApplyResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
    if old == text:
        result.skipped_files.append(f"{path.name}: already current")
        return
    path.write_text(text, encoding="utf-8")
    if old is None:
        result.created_files.append(path.name)
    else:
        result.changed_files.append(path.name)


def _write_csv(path: Path, headers: List[str], rows: List[List[str]], result: ApplyResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    if existed:
        result.changed_files.append(path.name)
    else:
        result.created_files.append(path.name)


def _dashboard_text(root: Path, profile: ArchetypeProfile) -> str:
    stats = feature_bank_stats()
    return f"""# MugenForge No-Code Creator Dashboard

Project: `{root.name}`
Archetype: **{profile.name}**
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## What this project is set up to do

{profile.description}

## Your job vs. MugenForge's job

Your job is the fun part:

- Draw or replace sprites.
- Pick sounds and voice clips.
- Move hitboxes visually in the CLSN Editor.
- Adjust timing, speed, and damage after playtesting.

MugenForge handles the boring wiring:

- CMD input blocks.
- StateDef routing.
- HitDef starter logic.
- AIR placeholder actions.
- Backups before generated code is appended.

## Suggested button map

""" + "\n".join(f"- `{k}` = {v}" for k, v in profile.suggested_buttons.items()) + f"""

## Immediate next steps

1. Open **Animation Player** and check that generated actions exist.
2. Open **CLSN Editor** and drag hitboxes until attacks line up with your art.
3. Replace placeholder sprites in `spritesheets/` or `staged_sprites/`.
4. Replace placeholder WAV files in `sounds/`.
5. Use **Validate** and **Export Audit** before packaging.

## Tuning notes

""" + "\n".join(f"- {note}" for note in profile.tuning_notes) + f"""

## Feature bank size

- No-code presets: {stats['total_presets']}
- Creator kits: {stats['total_kits']}

Use `MUGENFORGE_MOVE_TUNING.csv`, `MUGENFORGE_SPRITE_TODO.csv`, and `MUGENFORGE_SOUND_TODO.csv` as checklists while building.
"""


def _sprite_rows(profile: ArchetypeProfile) -> List[List[str]]:
    base = [
        ["0", "idle", "standing idle", "required", "replace placeholder"],
        ["20", "walk forward", "movement", "required", "make feet readable"],
        ["40", "jump start", "movement", "required", "short anticipation"],
        ["200", "light punch", "normal", "high", "fast, small hitbox"],
        ["210", "medium punch", "normal", "high", "balanced reach"],
        ["220", "heavy punch", "normal", "high", "clear windup"],
        ["230", "light kick", "normal", "high", "simple standing kick"],
        ["240", "medium kick", "normal", "medium", "good reach"],
        ["250", "heavy kick", "normal", "medium", "strong recovery"],
        ["1000", "fireball", "special", "medium", "startup/recovery"],
        ["1100", "uppercut", "special", "medium", "anti-air silhouette"],
        ["3000+", "super", "super", "later", "replace after basics feel good"],
    ]
    if "Air" in profile.name or "Anime" in profile.name:
        base += [["140", "air dash", "movement", "high", "clear direction"], ["640", "air combo", "attack", "medium", "tune cross-up boxes"]]
    if "Zoner" in profile.name:
        base += [["1320", "boomerang", "helper", "medium", "projectile art"], ["1330", "homing orb", "helper", "later", "small readable orb"]]
    if "Grappler" in profile.name:
        base += [["800", "throw", "grapple", "high", "grab reach must be visible"], ["3520", "super grab", "super", "later", "big tell before grab"]]
    return base


def _move_rows(profile: ArchetypeProfile) -> List[List[str]]:
    ids = KIT_PRESETS.get(profile.kit_name, [])
    rows: List[List[str]] = []
    for fid in ids:
        preset = next((p for p in FEATURE_PRESETS if p.feature_id == fid), None)
        if not preset:
            continue
        rows.append([fid, preset.name, preset.category, preset.difficulty, "not tested", "sprites/hitboxes/timing/damage"])
    return rows


def write_no_code_dashboard(root: Path, archetype_name: str | None = None) -> ApplyResult:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    result = ApplyResult()
    profile = _profile(archetype_name)

    _write_text_if_changed(root / "NO_CODE_CREATOR_DASHBOARD.md", _dashboard_text(root, profile), result)
    blueprint = {
        "tool": "MugenForge Studio",
        "profile_version": 2,
        "archetype": profile.name,
        "kit_name": profile.kit_name,
        "button_map": profile.suggested_buttons,
        "creator_goals": profile.creator_goals,
        "tuning_notes": profile.tuning_notes,
        "feature_bank": feature_bank_stats(),
        "installed_feature_plan": KIT_PRESETS.get(profile.kit_name, []),
    }
    _write_text_if_changed(root / "MUGENFORGE_CHARACTER_BLUEPRINT.json", json.dumps(blueprint, indent=2), result)
    _write_text_if_changed(root / "MUGENFORGE_BUTTON_MAP.json", json.dumps(profile.suggested_buttons, indent=2), result)
    _write_text_if_changed(root / "MUGENFORGE_FEATURE_BANK_STATS.txt", feature_bank_stats_text(), result)

    bank_export = {
        "feature_presets": [p.__dict__ for p in FEATURE_PRESETS],
        "creator_kits": KIT_PRESETS,
        "archetypes": {name: prof.__dict__ for name, prof in ARCHETYPE_PROFILES.items()},
    }
    _write_text_if_changed(root / "mugenforge_no_code_bank.json", json.dumps(bank_export, indent=2), result)

    _write_csv(root / "MUGENFORGE_MOVE_TUNING.csv", ["feature_id", "name", "category", "difficulty", "status", "what_to_tune"], _move_rows(profile), result)
    _write_csv(root / "MUGENFORGE_SPRITE_TODO.csv", ["action_or_group", "name", "type", "priority", "notes"], _sprite_rows(profile), result)
    _write_csv(root / "MUGENFORGE_SOUND_TODO.csv", ["group_sound", "use", "priority", "notes"], [
        ["5,0", "light hit", "high", "replace silent placeholder"],
        ["5,1", "medium hit", "high", "replace silent placeholder"],
        ["5,2", "heavy hit", "high", "replace silent placeholder"],
        ["5,3", "special/projectile", "medium", "replace silent placeholder"],
        ["5,4", "uppercut/reversal", "medium", "replace silent placeholder"],
        ["5,6", "super", "later", "replace silent placeholder"],
        ["6,0", "guard", "medium", "replace silent placeholder"],
        ["7,0+", "voice callouts", "optional", "use Voice Callout Hooks preset"],
    ], result)
    try:
        export_code_bank_template(root)
        result.created_files.append("mugenforge_feature_bank_template.json")
    except Exception as exc:
        result.warnings.append(f"Could not write feature-bank template: {exc}")
    return result


def _auto_build_placeholder_sff(root: Path, result: ApplyResult) -> None:
    try:
        from .spritesheet_tools import compute_grid_slices, export_grid_slices, write_manifest
        from .sff_codec import build_sff_v1_from_manifest
        sheet = root / "spritesheets" / "mugenforge_placeholder_sheet.png"
        if not sheet.exists():
            result.warnings.append("Placeholder sheet does not exist, so SFF was not built.")
            return
        slices = compute_grid_slices(sheet, 96, 96, 8, 6, group=0, start_image=0, axis_x=48, axis_y=88)
        staged_dir = root / "staged_sprites"
        export_grid_slices(sheet, slices, staged_dir, trim_empty=False)
        manifest = write_manifest(sheet, slices, staged_dir / "mugenforge_sprite_manifest.json")
        sff_path = root / f"{root.name}.sff"
        build_sff_v1_from_manifest(manifest, sff_path)
        result.created_files += ["staged_sprites/mugenforge_sprite_manifest.json", f"{root.name}.sff"]
    except Exception as exc:
        result.warnings.append(f"Could not auto-build placeholder SFF. Pillow may be missing. Details: {exc}")


def _auto_build_placeholder_snd(root: Path, result: ApplyResult) -> None:
    try:
        from .snd_codec import make_placeholder_sound_bank, build_snd_from_manifest
        manifest = make_placeholder_sound_bank(root / "sounds")
        snd_path = root / f"{root.name}.snd"
        build_snd_from_manifest(manifest, snd_path)
        result.created_files += ["sounds/mugenforge_snd_manifest.json", f"{root.name}.snd"]
    except Exception as exc:
        result.warnings.append(f"Could not auto-build placeholder SND: {exc}")


def one_click_playable_skeleton(root: Path, archetype_name: str | None = None) -> ApplyResult:
    """Create the most complete beginner project MugenForge can safely generate.

    The result is not finished art/gameplay. It is a playable-ish scaffold: DEF/CMD/CNS/AIR,
    placeholder sprite sheet, staged SFF v1 when Pillow is available, placeholder SND, selected
    archetype kit, and no-code planning docs.
    """
    root = Path(root)
    profile = _profile(archetype_name)
    result = ApplyResult()
    _merge(result, auto_setup_project(root))
    result.warnings = [w for w in result.warnings if 'SFF and SND binary files are not auto-created here' not in w]
    _merge(result, write_no_code_dashboard(root, profile.name))
    _merge(result, apply_kit(root, profile.kit_name))
    _merge(result, make_placeholder_sprite_sheet(root))
    _auto_build_placeholder_sff(root, result)
    _auto_build_placeholder_snd(root, result)
    def_path = root / f"{root.name}.def"
    if _ensure_def_files_section(def_path, {"cmd": f"{root.name}.cmd", "cns": f"{root.name}.cns", "anim": f"{root.name}.air", "sprite": f"{root.name}.sff", "sound": f"{root.name}.snd"}):
        result.changed_files.append(def_path.name + ": checked binary references")
    quickstart = f"""# One-Click Skeleton Quickstart

Archetype: {profile.name}

MugenForge created the most complete starter scaffold it can safely generate. It is still placeholder-heavy.

## Open these tabs next

1. **Animation Player**: preview actions and timing.
2. **CLSN Editor**: drag hitboxes over the generated sprites.
3. **Feature Bank**: add/remove features or install more kits.
4. **Palettes**: generate ACT palettes once your art is real.
5. **Validate / Export Audit**: check missing references.

## Replace next

- `spritesheets/mugenforge_placeholder_sheet.png`
- files in `staged_sprites/`
- WAV files in `sounds/`

## Current status

{beginner_project_status(root)}
"""
    _write_text_if_changed(root / "ONE_CLICK_SKELETON_QUICKSTART.md", quickstart, result)
    result.warnings.append("This is a scaffold, not a finished character. The generated code is intentionally beginner-readable and should be tuned by testing animations, hitboxes, and damage.")
    return result


def no_code_director_summary(root: Path, archetype_name: str | None = None) -> str:
    profile = _profile(archetype_name)
    return archetype_preview_text(profile.name) + "\n" + feature_bank_stats_text() + "\n" + beginner_project_status(root)
