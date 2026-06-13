from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Dict, Iterable, List, Optional, Sequence

from .parsers import parse_def, read_text_safely, write_text_safely, scan_project, COMMON_ANIMS
from .move_wizard import (
    MoveWizardSpec,
    MoveWizardPackage,
    build_move_package,
    find_character_file,
)


@dataclass
class FeaturePreset:
    feature_id: str
    name: str
    category: str
    difficulty: str
    description: str
    blocks: Sequence[str] = field(default_factory=lambda: ("cmd", "cns", "air"))
    beginner_notes: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)


@dataclass
class FeaturePackage:
    feature_id: str
    name: str
    cmd_block: str = ""
    cns_block: str = ""
    air_block: str = ""
    extra_files: Dict[str, str] = field(default_factory=dict)
    summary: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines: List[str] = []
        if self.changed_files:
            lines.append("Changed files:")
            lines += [f"- {item}" for item in self.changed_files]
        if self.created_files:
            lines.append("\nCreated files/folders:")
            lines += [f"- {item}" for item in self.created_files]
        if self.skipped_files:
            lines.append("\nSkipped:")
            lines += [f"- {item}" for item in self.skipped_files]
        if self.warnings:
            lines.append("\nWarnings:")
            lines += [f"- {item}" for item in self.warnings]
        return "\n".join(lines).strip() or "No changes made."


FEATURE_PRESETS: List[FeaturePreset] = [
    FeaturePreset("starter_basics", "Starter basics / required actions", "Setup", "Beginner", "Adds beginner-safe AIR placeholders for common required animations, plus basic CMD shortcuts and a clipboard/debug helper.", ("cmd", "cns", "air"), ("Use this first on a new character.", "It creates placeholders, not finished art."), ("setup", "air", "cmd")),
    FeaturePreset("common_commands", "Common command bank", "Setup", "Beginner", "Adds ready-to-use M.U.G.E.N command definitions for punch/kick buttons, quarter-circles, dragon-punch motions, dash, backdash, and taunt.", ("cmd",), ("Good when you want a reusable input library."), ("cmd", "inputs")),
    FeaturePreset("debug_overlay", "Training/debug overlay", "Tools", "Beginner", "Adds a State -2 DisplayToClipboard helper so creators can see animation, state, time, velocity, and ctrl values while testing.", ("cns",), ("Remove it before final release if you do not want debug text."), ("debug", "testing")),
    FeaturePreset("light_punch", "Light punch", "Normal Attacks", "Beginner", "Fast close-range punch with starter hitbox, sound, HitDef, CMD command, and AIR action.", ("cmd", "cns", "air"), tags=("attack", "normal")),
    FeaturePreset("medium_punch", "Medium punch", "Normal Attacks", "Beginner", "Balanced punch with more damage and a slightly wider active box.", ("cmd", "cns", "air"), tags=("attack", "normal")),
    FeaturePreset("heavy_punch", "Heavy punch", "Normal Attacks", "Beginner", "Slower stronger punch template with bigger hitbox and knockback.", ("cmd", "cns", "air"), tags=("attack", "normal")),
    FeaturePreset("light_kick", "Light kick", "Normal Attacks", "Beginner", "Fast standing kick template.", ("cmd", "cns", "air"), tags=("attack", "normal")),
    FeaturePreset("crouch_kick", "Crouch kick", "Normal Attacks", "Beginner", "Low crouching kick starter with lower hitbox placement.", ("cmd", "cns", "air"), tags=("attack", "low")),
    FeaturePreset("air_kick", "Air kick", "Normal Attacks", "Beginner", "Simple jumping kick starter. You may need to move it into your air control flow later.", ("cmd", "cns", "air"), tags=("attack", "air")),
    FeaturePreset("fireball", "Fireball projectile", "Special Moves", "Beginner", "Quarter-circle-forward projectile with startup animation, projectile controller, and placeholder projectile AIR action.", ("cmd", "cns", "air"), tags=("special", "projectile")),
    FeaturePreset("dragon_punch", "Dragon punch / uppercut", "Special Moves", "Intermediate", "Forward-down-downforward rising uppercut starter. Uses an attack state template and vertical-ish knockback.", ("cmd", "cns", "air"), tags=("special", "anti-air")),
    FeaturePreset("dash_forward", "Forward dash", "Movement", "Beginner", "Double-tap-forward movement state with AIR placeholders.", ("cmd", "cns", "air"), tags=("movement", "dash")),
    FeaturePreset("back_dash", "Back dash", "Movement", "Beginner", "Double-tap-back movement state with negative velocity.", ("cmd", "cns", "air"), tags=("movement", "dash")),
    FeaturePreset("taunt", "Taunt", "Personality", "Beginner", "Start-button taunt state with a safe non-attacking animation block.", ("cmd", "cns", "air"), tags=("taunt", "personality")),
    FeaturePreset("intro_pose", "Intro pose", "Round Flow", "Beginner", "Adds an intro animation action and a simple intro StateDef block you can wire into your character later.", ("cns", "air"), tags=("intro", "round")),
    FeaturePreset("win_pose", "Win pose", "Round Flow", "Beginner", "Adds a win-pose animation action and starter StateDef block.", ("cns", "air"), tags=("win", "round")),
    FeaturePreset("combo_three_hit", "Three-hit beginner combo", "Combos", "Beginner", "Adds light, medium, and heavy attack states with simple command chain windows. Good first combo pack.", ("cmd", "cns", "air"), ("Use this instead of adding each punch separately if you want them chained."), ("combo", "attack")),
    FeaturePreset("projectile_plus_super", "Projectile + super starter", "Special Moves", "Intermediate", "Adds a fireball and a stronger super projectile-style starter using separate states and animations.", ("cmd", "cns", "air"), tags=("special", "super", "projectile")),
]


def available_presets() -> List[FeaturePreset]:
    return list(FEATURE_PRESETS)


def get_preset(feature_id: str) -> FeaturePreset:
    for preset in FEATURE_PRESETS:
        if preset.feature_id == feature_id:
            return preset
    raise KeyError(feature_id)


def preset_display_list() -> List[str]:
    return [f"{p.category} :: {p.name}" for p in FEATURE_PRESETS]


def preset_by_display(display: str) -> FeaturePreset:
    for preset in FEATURE_PRESETS:
        if display == f"{preset.category} :: {preset.name}" or display == preset.name or display == preset.feature_id:
            return preset
    return FEATURE_PRESETS[0]


def _marker(feature_id: str) -> str:
    return f"; MugenForge Feature Bank ID: {feature_id}"


def _wrap(feature_id: str, title: str, block: str) -> str:
    if not block.strip():
        return ""
    return f"\n{_marker(feature_id)}\n; Feature: {title}\n{block.rstrip()}\n; End MugenForge Feature Bank ID: {feature_id}\n"


def _spec(
    move_name: str,
    command_name: str,
    command_input: str,
    state_no: int,
    anim_no: Optional[int] = None,
    sprite_group: Optional[int] = None,
    move_type: str = "attack",
    damage: int = 35,
    frame_count: int = 4,
    ticks: int = 4,
    hit_frame: int = 2,
    hit_box: tuple[int, int, int, int] = (18, -72, 58, -36),
    body_box: tuple[int, int, int, int] = (-18, -88, 18, 0),
    sound: tuple[int, int] = (5, 0),
    ground_velocity: tuple[float, float] = (-3.0, 0.0),
    air_velocity: tuple[float, float] = (-2.0, -4.0),
) -> MoveWizardSpec:
    return MoveWizardSpec(
        move_name=move_name,
        command_name=command_name,
        command_input=command_input,
        command_time=12,
        state_no=state_no,
        anim_no=anim_no if anim_no is not None else state_no,
        sprite_group=sprite_group if sprite_group is not None else (anim_no if anim_no is not None else state_no),
        start_image=0,
        frame_count=frame_count,
        ticks=ticks,
        hit_frame=hit_frame,
        damage=damage,
        hit_x1=hit_box[0], hit_y1=hit_box[1], hit_x2=hit_box[2], hit_y2=hit_box[3],
        body_x1=body_box[0], body_y1=body_box[1], body_x2=body_box[2], body_y2=body_box[3],
        sound_group=sound[0], sound_index=sound[1],
        ground_velocity_x=ground_velocity[0], ground_velocity_y=ground_velocity[1],
        air_velocity_x=air_velocity[0], air_velocity_y=air_velocity[1],
        move_type=move_type,
    )


def _pack_from_specs(feature_id: str, name: str, specs: Sequence[MoveWizardSpec], notes: Optional[List[str]] = None) -> FeaturePackage:
    cmd_parts: List[str] = []
    cns_parts: List[str] = []
    air_parts: List[str] = []
    summaries: List[str] = []
    for spec in specs:
        pkg = build_move_package(spec)
        cmd_parts.append(pkg.cmd_block)
        cns_parts.append(pkg.cns_block)
        air_parts.append(pkg.air_block)
        summaries.append(pkg.summary.strip())
    return FeaturePackage(
        feature_id=feature_id,
        name=name,
        cmd_block=_wrap(feature_id, name, "\n".join(cmd_parts)),
        cns_block=_wrap(feature_id, name, "\n".join(cns_parts)),
        air_block=_wrap(feature_id, name, "\n".join(air_parts)),
        summary=f"Feature Bank Package: {name}\n\n" + "\n\n".join(summaries),
        notes=notes or [],
    )


def _basic_air_actions() -> str:
    actions = [
        (0, "Standing idle", 4, (-18, -88, 18, 0)),
        (5, "Turn", 2, (-18, -88, 18, 0)),
        (10, "Stand to crouch", 2, (-18, -70, 18, 0)),
        (11, "Crouch to stand", 2, (-18, -80, 18, 0)),
        (12, "Crouching", 3, (-20, -55, 20, 0)),
        (20, "Walk forward", 6, (-18, -88, 18, 0)),
        (21, "Walk back", 6, (-18, -88, 18, 0)),
        (40, "Jump start", 3, (-18, -86, 18, 0)),
        (41, "Jump neutral", 4, (-18, -82, 18, 2)),
        (42, "Jump forward/back", 4, (-18, -82, 18, 2)),
        (47, "Jump land", 2, (-18, -72, 18, 0)),
        (100, "Run / dash forward", 5, (-18, -88, 18, 0)),
        (105, "Back dash", 5, (-18, -88, 18, 0)),
        (120, "Guard start", 2, (-22, -88, 22, 0)),
        (130, "Stand guard", 3, (-22, -88, 22, 0)),
        (140, "Crouch guard", 3, (-22, -58, 22, 0)),
        (150, "Air guard", 3, (-22, -82, 22, 2)),
        (5000, "Get hit high", 2, (-20, -88, 20, 0)),
        (5010, "Get hit low", 2, (-20, -88, 20, 0)),
        (5020, "Get hit crouch", 2, (-20, -58, 20, 0)),
        (5030, "Get hit air", 2, (-20, -82, 20, 2)),
        (5050, "Fall", 3, (-20, -82, 20, 2)),
        (5070, "Fall recovery", 3, (-20, -82, 20, 2)),
        (5100, "Lying down", 2, (-38, -18, 38, 2)),
        (5110, "Get up", 4, (-22, -72, 22, 0)),
        (5150, "Dead", 2, (-38, -18, 38, 2)),
    ]
    lines: List[str] = ["; MugenForge beginner placeholder actions", "; Replace group/image pairs with real sprites when ready."]
    for action_no, label, frames, body in actions:
        lines += ["", f"[Begin Action {action_no}] ; {label}"]
        for image in range(frames):
            lines.append("Clsn2: 1")
            lines.append(f"  Clsn2[0] = {body[0]},{body[1]},{body[2]},{body[3]}")
            lines.append(f"{action_no}, {image}, 0, 0, 6")
    return "\n".join(lines) + "\n"


def _common_command_bank() -> str:
    commands = [
        ("x", "x", 1), ("y", "y", 1), ("z", "z", 1),
        ("a", "a", 1), ("b", "b", 1), ("c", "c", 1), ("start", "s", 1),
        ("dash_forward", "F, F", 10), ("dash_back", "B, B", 10),
        ("qcf_x", "~D, DF, F, x", 18), ("qcf_y", "~D, DF, F, y", 18),
        ("qcf_z", "~D, DF, F, z", 18), ("qcb_x", "~D, DB, B, x", 18),
        ("dp_y", "~F, D, DF, y", 18), ("super_qcf2_x", "~D, DF, F, D, DF, F, x", 30),
        ("crouch_b", "D, b", 8), ("air_a", "a", 1),
    ]
    parts: List[str] = ["; MugenForge common input bank"]
    for name, command, time in commands:
        parts += ["", "[Command]", f"name = \"{name}\"", f"command = {command}", f"time = {time}", "buffer.time = 4"]
    return "\n".join(parts) + "\n"


def _debug_overlay_block() -> str:
    return '''; MugenForge beginner debug overlay
[State -2, MugenForge Debug Overlay]
type = DisplayToClipboard
trigger1 = 1
text = "state=%d anim=%d elem=%d time=%d ctrl=%d pos=(%d,%d) vel=(%f,%f)"
params = stateno, anim, animelemno(0), time, ctrl, pos x, pos y, vel x, vel y
ignorehitpause = 1

'''


def _simple_pose_state(state_no: int, anim_no: int, label: str, state_type: str = "S") -> str:
    return f'''; MugenForge {label} starter state
[Statedef {state_no}]
type = {state_type}
movetype = I
physics = S
anim = {anim_no}
ctrl = 0
sprpriority = 2

[State {state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''


def _simple_pose_air(anim_no: int, label: str, frames: int = 5) -> str:
    lines = [f"; MugenForge {label} animation", f"[Begin Action {anim_no}] ; {label}"]
    for idx in range(frames):
        lines.append("Clsn2: 1")
        lines.append("  Clsn2[0] = -18,-88,18,0")
        lines.append(f"{anim_no}, {idx}, 0, 0, 7")
    return "\n".join(lines) + "\n\n"


def build_feature_package(feature_id: str) -> FeaturePackage:
    preset = get_preset(feature_id)
    if feature_id == "starter_basics":
        return FeaturePackage(
            feature_id=feature_id,
            name=preset.name,
            cmd_block=_wrap(feature_id, preset.name, _common_command_bank()),
            cns_block=_wrap(feature_id, preset.name, _debug_overlay_block()),
            air_block=_wrap(feature_id, preset.name, _basic_air_actions()),
            extra_files={
                "MUGENFORGE_BEGINNER_GUIDE.md": beginner_guide_text(),
                "mugenforge_project.json": json.dumps(default_project_profile(), indent=2),
            },
            summary="Starter Basics installs common command definitions, beginner placeholder AIR actions, a debug overlay, and a project guide.",
            notes=list(preset.beginner_notes),
        )
    if feature_id == "common_commands":
        return FeaturePackage(feature_id, preset.name, cmd_block=_wrap(feature_id, preset.name, _common_command_bank()), summary="Common command bank only.")
    if feature_id == "debug_overlay":
        return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, _debug_overlay_block()), summary="Debug overlay block only.")

    single_specs: Dict[str, MoveWizardSpec] = {
        "light_punch": _spec("Light Punch", "light_punch", "x", 200, damage=25, frame_count=4, hit_frame=2, hit_box=(16, -70, 48, -42), sound=(5, 0)),
        "medium_punch": _spec("Medium Punch", "medium_punch", "y", 210, damage=45, frame_count=5, hit_frame=3, hit_box=(18, -74, 60, -38), sound=(5, 1)),
        "heavy_punch": _spec("Heavy Punch", "heavy_punch", "z", 220, damage=70, frame_count=7, hit_frame=4, hit_box=(20, -78, 72, -34), sound=(5, 2), ground_velocity=(-5, 0), air_velocity=(-3, -5)),
        "light_kick": _spec("Light Kick", "light_kick", "a", 230, damage=28, frame_count=4, hit_frame=2, hit_box=(20, -48, 60, -18), sound=(5, 0)),
        "crouch_kick": _spec("Crouch Kick", "crouch_kick", "D, b", 400, damage=32, frame_count=5, hit_frame=3, hit_box=(18, -32, 74, -8), body_box=(-20, -58, 20, 0), sound=(5, 1)),
        "air_kick": _spec("Air Kick", "air_kick", "a", 600, damage=38, frame_count=5, hit_frame=3, hit_box=(16, -62, 58, -22), body_box=(-18, -82, 18, 2), sound=(5, 1), ground_velocity=(-3, -1), air_velocity=(-2, -4)),
        "fireball": _spec("Fireball", "fireball", "~D, DF, F, x", 1000, move_type="projectile", damage=55, frame_count=6, hit_frame=4, hit_box=(22, -70, 62, -36), sound=(5, 3), ground_velocity=(-5, 0), air_velocity=(-3, -4)),
        "dragon_punch": _spec("Dragon Punch", "dragon_punch", "~F, D, DF, y", 1100, damage=80, frame_count=8, hit_frame=3, hit_box=(12, -92, 55, -26), sound=(5, 4), ground_velocity=(-3, -7), air_velocity=(-2, -8)),
        "dash_forward": _spec("Forward Dash", "dash_forward", "F, F", 100, move_type="movement", damage=0, frame_count=5, hit_frame=1, sound=(0, 0), ground_velocity=(4.5, 0)),
        "back_dash": _spec("Back Dash", "dash_back", "B, B", 105, move_type="movement", damage=0, frame_count=5, hit_frame=1, sound=(0, 0), ground_velocity=(-4.5, 0)),
    }
    if feature_id in single_specs:
        return _pack_from_specs(feature_id, preset.name, [single_specs[feature_id]], list(preset.beginner_notes))

    if feature_id == "taunt":
        cmd = '''[Command]
name = "taunt"
command = s
time = 1
buffer.time = 4

[State -1, Taunt]
type = ChangeState
value = 195
triggerall = command = "taunt"
triggerall = roundstate = 2
trigger1 = ctrl

'''
        cns = _simple_pose_state(195, 195, "Taunt")
        air = _simple_pose_air(195, "Taunt", frames=6)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a taunt command, state, and animation placeholder.")
    if feature_id == "intro_pose":
        return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, _simple_pose_state(190, 190, "Intro Pose")), air_block=_wrap(feature_id, preset.name, _simple_pose_air(190, "Intro Pose", 8)), summary="Adds intro pose starter blocks.")
    if feature_id == "win_pose":
        return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, _simple_pose_state(180, 180, "Win Pose")), air_block=_wrap(feature_id, preset.name, _simple_pose_air(180, "Win Pose", 8)), summary="Adds win pose starter blocks.")
    if feature_id == "combo_three_hit":
        specs = [
            _spec("Combo Light", "combo_light", "x", 300, damage=22, frame_count=4, hit_frame=2, hit_box=(16, -70, 48, -42), sound=(5, 0)),
            _spec("Combo Medium", "combo_medium", "y", 310, damage=38, frame_count=5, hit_frame=3, hit_box=(18, -74, 60, -38), sound=(5, 1)),
            _spec("Combo Heavy", "combo_heavy", "z", 320, damage=62, frame_count=7, hit_frame=4, hit_box=(20, -78, 72, -34), sound=(5, 2), ground_velocity=(-5, 0)),
        ]
        pkg = _pack_from_specs(feature_id, preset.name, specs, list(preset.beginner_notes))
        chain = '''; Extra chain windows for generated combo states.
; Paste these controllers inside matching states if you want tighter manual control.
[State 300, Chain to Medium]
type = ChangeState
trigger1 = command = "combo_medium"
trigger1 = AnimElem >= 3
value = 310

[State 310, Chain to Heavy]
type = ChangeState
trigger1 = command = "combo_heavy"
trigger1 = AnimElem >= 3
value = 320

'''
        pkg.cns_block += _wrap(feature_id + "_chain_notes", "Three-hit chain notes", chain)
        pkg.summary += "\n\nIncludes extra chain-window controllers for light -> medium -> heavy routing."
        return pkg
    if feature_id == "projectile_plus_super":
        specs = [
            _spec("Fireball", "fireball", "~D, DF, F, x", 1000, move_type="projectile", damage=55, frame_count=6, hit_frame=4, sound=(5, 3)),
            _spec("Super Fireball", "super_fireball", "~D, DF, F, D, DF, F, x", 3000, move_type="projectile", damage=150, frame_count=9, hit_frame=5, sound=(5, 6), ground_velocity=(-8, 0), air_velocity=(-4, -6)),
        ]
        return _pack_from_specs(feature_id, preset.name, specs, list(preset.beginner_notes))
    raise KeyError(feature_id)


def package_preview_text(package: FeaturePackage) -> str:
    lines = [package.summary or f"Feature package: {package.name}"]
    if package.notes:
        lines.append("\nBeginner notes:")
        lines += [f"- {note}" for note in package.notes]
    for label, block in (("CMD", package.cmd_block), ("CNS/ST", package.cns_block), ("AIR", package.air_block)):
        if block.strip():
            lines += ["\n" + "=" * 72, f"{label} BLOCK", "=" * 72, block.rstrip()]
    if package.extra_files:
        lines += ["\n" + "=" * 72, "EXTRA FILES", "=" * 72]
        for rel in package.extra_files:
            lines.append(f"- {rel}")
    return "\n".join(lines).strip() + "\n"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + f".bak_{_timestamp()}")


def _append_unique(path: Path, block: str, marker_id: str, result: ApplyResult) -> None:
    if not block.strip():
        return
    old = read_text_safely(path) if path.exists() else ""
    if _marker(marker_id) in old:
        result.skipped_files.append(f"{path.name}: already contains {marker_id}")
        return
    if path.exists():
        backup = _backup_path(path)
        backup.write_text(old, encoding="utf-8", errors="replace")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        result.created_files.append(path.name)
    glue = "" if old.endswith("\n") or not old else "\n"
    write_text_safely(path, old + glue + block)
    result.changed_files.append(f"{path.name}: appended {marker_id}")


def _fallback_file(root: Path, kind: str) -> Path:
    stem = root.name or "character"
    suffix = {"cmd": ".cmd", "cns": ".cns", "air": ".air"}[kind]
    return root / f"{stem}{suffix}"


def apply_feature_package(root: Path, package: FeaturePackage) -> ApplyResult:
    result = ApplyResult()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    targets = {
        "cmd": (find_character_file(root, "cmd") or _fallback_file(root, "cmd"), package.cmd_block),
        "cns": (find_character_file(root, "cns") or _fallback_file(root, "cns"), package.cns_block),
        "air": (find_character_file(root, "air") or _fallback_file(root, "air"), package.air_block),
    }
    for _kind, (path, block) in targets.items():
        _append_unique(path, block, package.feature_id, result)
    for rel, content in package.extra_files.items():
        target = root / rel
        if target.exists():
            result.skipped_files.append(f"{rel}: already exists")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel.lower().endswith(".json"):
            target.write_text(content, encoding="utf-8")
        else:
            write_text_safely(target, content)
        result.created_files.append(rel)
    return result


def apply_preset(root: Path, feature_id: str) -> ApplyResult:
    return apply_feature_package(root, build_feature_package(feature_id))


def apply_beginner_pack(root: Path) -> ApplyResult:
    ids = ["starter_basics", "light_punch", "medium_punch", "heavy_punch", "crouch_kick", "fireball", "dash_forward", "back_dash", "taunt"]
    combined = ApplyResult()
    for fid in ids:
        result = apply_preset(root, fid)
        combined.changed_files += result.changed_files
        combined.skipped_files += result.skipped_files
        combined.warnings += result.warnings
        combined.created_files += result.created_files
    return combined


def default_project_profile() -> Dict[str, object]:
    return {
        "tool": "MugenForge Studio",
        "profile_version": 1,
        "mode": "beginner",
        "recommended_workflow": [
            "1. Import/stage sprites from a sprite sheet.",
            "2. Build or replace SFF v1 from the manifest.",
            "3. Use Feature Bank to add moves without writing code.",
            "4. Use CLSN Editor to drag hitboxes until they feel right.",
            "5. Use Animation Player to preview timing.",
            "6. Validate, export audit, and package ZIP."
        ],
        "safe_defaults": {
            "write_backups": True,
            "append_code_instead_of_rewriting": True,
            "beginner_explanations": True,
        },
    }


def beginner_guide_text() -> str:
    return """# MugenForge Beginner Guide

This project has been prepared for a no-code workflow.

## Simple workflow

1. Put sprite sheets in `spritesheets/`.
2. Use **Sheet Import** to slice them.
3. Use **Build SFF v1** to make a sprite file.
4. Use **Feature Bank** to add moves without typing code.
5. Use **CLSN Editor** to move hitboxes visually.
6. Use **Animation Player** to check timing.
7. Use **Validate** and **Export Audit** before sharing.

## What the generated code does

M.U.G.E.N characters are usually split across these files:

- `.cmd` = player inputs and when moves are allowed.
- `.cns` / `.st` = move behavior and state logic.
- `.air` = animation frames and collision boxes.
- `.sff` = sprites.
- `.snd` = sounds.

Feature Bank writes the CMD/CNS/AIR parts for you and leaves art/sound replacement as the fun part.

## Safety

MugenForge appends generated code and writes backups before changing existing code files. If something breaks, restore the newest `.bak_YYYYMMDD_HHMMSS` copy.
"""


def _ensure_def_files_section(def_path: Path, references: Dict[str, str]) -> bool:
    text = read_text_safely(def_path) if def_path.exists() else ""
    changed = False
    if not text.strip():
        text = f"; Generated by MugenForge Studio\n[Info]\nname = \"{def_path.stem}\"\ndisplayname = \"{def_path.stem}\"\nversiondate = 06,13,2026\nmugenversion = 1.0\nauthor = \"MugenForge User\"\n\n[Files]\n"
        changed = True
    if not re.search(r"^\s*\[\s*Files\s*\]", text, flags=re.I | re.M):
        if not text.endswith("\n"):
            text += "\n"
        text += "\n[Files]\n"
        changed = True
    lines = text.splitlines()
    existing_keys = set()
    in_files = False
    for line in lines:
        sm = re.match(r"^\s*\[\s*([^\]]+)\s*\]", line)
        if sm:
            in_files = sm.group(1).strip().lower() == "files"
            continue
        if in_files:
            km = re.match(r"^\s*([^;#=]+?)\s*=", line)
            if km:
                existing_keys.add(km.group(1).strip().lower())
    missing_lines = []
    for key, value in references.items():
        if key.lower() not in existing_keys:
            missing_lines.append(f"{key} = {value}")
    if missing_lines:
        out_lines: List[str] = []
        inserted = False
        in_files = False
        for line in lines:
            sm = re.match(r"^\s*\[\s*([^\]]+)\s*\]", line)
            if sm:
                if in_files and not inserted:
                    out_lines.extend(missing_lines)
                    inserted = True
                in_files = sm.group(1).strip().lower() == "files"
            out_lines.append(line)
        if in_files and not inserted:
            out_lines.extend(missing_lines)
        text = "\n".join(out_lines) + "\n"
        changed = True
    if changed:
        if def_path.exists():
            _backup_path(def_path).write_text(read_text_safely(def_path), encoding="utf-8", errors="replace")
        write_text_safely(def_path, text)
    return changed


def auto_setup_project(root: Path) -> ApplyResult:
    result = ApplyResult()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stem = root.name or "character"
    folders = ["spritesheets", "staged_sprites", "sounds", "exports", "backups", "references"]
    for folder in folders:
        path = root / folder
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            result.created_files.append(folder + "/")
    defaults = {
        f"{stem}.cmd": "; MugenForge starter CMD\n\n",
        f"{stem}.cns": "; MugenForge starter CNS/ST\n\n[Statedef 0]\ntype = S\nphysics = S\nmovetype = I\nanim = 0\nctrl = 1\n\n",
        f"{stem}.air": _basic_air_actions(),
    }
    for rel, content in defaults.items():
        path = root / rel
        if not path.exists():
            write_text_safely(path, content)
            result.created_files.append(rel)
    def_path = root / f"{stem}.def"
    refs = {"cmd": f"{stem}.cmd", "cns": f"{stem}.cns", "anim": f"{stem}.air", "sprite": f"{stem}.sff", "sound": f"{stem}.snd"}
    if _ensure_def_files_section(def_path, refs):
        result.changed_files.append(def_path.name + ": ensured [Files] references")
    guide = root / "MUGENFORGE_BEGINNER_GUIDE.md"
    if not guide.exists():
        write_text_safely(guide, beginner_guide_text())
        result.created_files.append(guide.name)
    profile = root / "mugenforge_project.json"
    if not profile.exists():
        profile.write_text(json.dumps(default_project_profile(), indent=2), encoding="utf-8")
        result.created_files.append(profile.name)
    result.warnings.append("SFF and SND binary files are not auto-created here. Use Sheet Import/SFF Builder and Sounds/SND Builder when your art/audio is ready.")
    return result


def beginner_project_status(root: Path) -> str:
    audit = scan_project(root)
    lines = [f"Beginner project status: {root}", ""]
    if audit.missing_required:
        lines.append("Missing common file types:")
        lines += [f"- {ext}: use Auto Setup, Sheet Import/SFF Builder, or SND Builder" for ext in audit.missing_required]
    else:
        lines.append("All common character file types are present.")
    if audit.missing_references:
        lines.append("\nDEF references that point to missing files:")
        lines += [f"- {item}" for item in audit.missing_references]
    if audit.asset_issues:
        lines.append("\nAIR/SFF asset issues:")
        lines += [f"- {item}" for item in audit.asset_issues[:80]]
    if audit.code_issues:
        lines.append("\nCode issues MugenForge noticed:")
        lines += [f"- {item}" for item in audit.code_issues[:80]]
    if audit.warnings:
        lines.append("\nGeneral warnings:")
        lines += [f"- {item}" for item in audit.warnings[:80]]
    lines.append("\nRecommended next step:")
    if ".sff" in audit.missing_required:
        lines.append("- Import a sprite sheet and build an SFF v1, or point the DEF file at an existing SFF.")
    elif ".snd" in audit.missing_required:
        lines.append("- Add WAV files in Sounds tab and build an SND package.")
    elif audit.asset_issues:
        lines.append("- Open AIR/Animation Player and replace placeholder sprite IDs that do not exist in SFF.")
    elif audit.code_issues:
        lines.append("- Use Code Assistant/Feature Bank to inspect and auto-generate missing wiring.")
    else:
        lines.append("- Add personality: taunts, win poses, specials, sounds, and polish hitboxes.")
    return "\n".join(lines).strip() + "\n"


def export_code_bank_template(root: Path) -> Path:
    data = {
        "description": "Edit this file to plan your character without touching M.U.G.E.N code. MugenForge built-in Feature Bank uses internal presets; this file is for your notes/custom plan.",
        "planned_features": [p.feature_id for p in FEATURE_PRESETS],
        "button_map": {"x": "light punch", "y": "medium punch", "z": "heavy punch", "a": "light kick", "b": "medium kick", "c": "heavy kick", "s": "taunt/start"},
        "feature_notes": {p.feature_id: p.description for p in FEATURE_PRESETS},
    }
    out = Path(root) / "mugenforge_feature_bank_template.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out

# ---------------------------------------------------------------------------
# v2.1 expanded no-code creator bank
# ---------------------------------------------------------------------------

_EXTRA_FEATURE_PRESETS: List[FeaturePreset] = [
    FeaturePreset("medium_kick", "Medium kick", "Normal Attacks", "Beginner", "Balanced standing kick template with moderate damage and reach.", ("cmd", "cns", "air"), tags=("attack", "normal", "kick")),
    FeaturePreset("heavy_kick", "Heavy kick", "Normal Attacks", "Beginner", "Slow high-damage standing kick template with knockback.", ("cmd", "cns", "air"), tags=("attack", "normal", "kick")),
    FeaturePreset("crouch_punch", "Crouch punch", "Normal Attacks", "Beginner", "Low-profile crouching punch starter.", ("cmd", "cns", "air"), tags=("attack", "low")),
    FeaturePreset("sweep", "Sweep knockdown", "Normal Attacks", "Beginner", "Crouching sweep starter aimed at a low knockdown-style hitbox.", ("cmd", "cns", "air"), tags=("attack", "low", "knockdown")),
    FeaturePreset("launcher", "Launcher", "Normal Attacks", "Intermediate", "Uppercut-style normal that sends the opponent upward.", ("cmd", "cns", "air"), tags=("attack", "launcher")),
    FeaturePreset("air_punch", "Air punch", "Normal Attacks", "Beginner", "Simple jumping punch starter with air-friendly CLSN placement.", ("cmd", "cns", "air"), tags=("attack", "air")),
    FeaturePreset("slow_fireball", "Slow fireball", "Special Moves", "Beginner", "A slower projectile variant that gives the player time to move behind it.", ("cmd", "cns", "air"), tags=("projectile", "special")),
    FeaturePreset("slide_kick", "Slide kick", "Special Moves", "Beginner", "Forward-moving low attack template.", ("cmd", "cns", "air"), tags=("special", "low")),
    FeaturePreset("spin_kick", "Spin kick", "Special Moves", "Intermediate", "Multi-purpose special-kick starter with a wider hitbox.", ("cmd", "cns", "air"), tags=("special", "kick")),
    FeaturePreset("anti_air_kick", "Anti-air kick", "Special Moves", "Intermediate", "Rising kick anti-air starter.", ("cmd", "cns", "air"), tags=("special", "anti-air")),
    FeaturePreset("air_fireball", "Air fireball", "Special Moves", "Intermediate", "Air projectile starter. Tune triggers after testing your jump states.", ("cmd", "cns", "air"), tags=("special", "air", "projectile")),
    FeaturePreset("roll_forward", "Forward roll", "Movement", "Beginner", "Invulnerable-looking movement starter; tune NotHitBy duration after testing.", ("cmd", "cns", "air"), tags=("movement", "defense")),
    FeaturePreset("roll_back", "Back roll", "Movement", "Beginner", "Backward roll movement starter.", ("cmd", "cns", "air"), tags=("movement", "defense")),
    FeaturePreset("air_dash_forward", "Air dash forward", "Movement", "Intermediate", "Air movement starter for anime-style characters.", ("cmd", "cns", "air"), tags=("movement", "air")),
    FeaturePreset("teleport", "Teleport", "Movement", "Intermediate", "Quick repositioning starter with a PalFX/position shift skeleton.", ("cmd", "cns", "air"), tags=("movement", "special")),
    FeaturePreset("basic_throw", "Basic throw", "Grapple", "Intermediate", "Close-range throw starter with command wiring and simple throw state skeleton.", ("cmd", "cns", "air"), tags=("throw", "grapple")),
    FeaturePreset("command_grab", "Command grab", "Grapple", "Intermediate", "Motion-input grab starter for command-throw characters.", ("cmd", "cns", "air"), tags=("throw", "special")),
    FeaturePreset("counter_attack", "Counter attack", "Defense", "Intermediate", "Counter starter that uses a safe beginner skeleton with a delayed strike.", ("cmd", "cns", "air"), tags=("defense", "counter")),
    FeaturePreset("parry", "Parry", "Defense", "Intermediate", "Parry-style defensive state with NotHitBy and recovery timing placeholders.", ("cmd", "cns", "air"), tags=("defense", "parry")),
    FeaturePreset("pushblock", "Pushblock", "Defense", "Intermediate", "Guard-push starter block. You will still need to tune guard triggers for your game style.", ("cmd", "cns", "air"), tags=("defense", "guard")),
    FeaturePreset("guard_cancel", "Guard cancel attack", "Defense", "Intermediate", "Reversal-style starter attack intended to be triggered from guard states.", ("cmd", "cns", "air"), tags=("defense", "attack")),
    FeaturePreset("super_rush", "Super rush", "Supers", "Intermediate", "High-damage rushing super starter with meter check comments.", ("cmd", "cns", "air"), tags=("super", "rush")),
    FeaturePreset("super_uppercut", "Super uppercut", "Supers", "Intermediate", "Big anti-air super starter.", ("cmd", "cns", "air"), tags=("super", "anti-air")),
    FeaturePreset("power_install", "Power install mode", "Supers", "Advanced", "Temporary power-up skeleton with VarSet, PalFX, and timer notes.", ("cmd", "cns", "air"), tags=("super", "buff")),
    FeaturePreset("striker_assist", "Striker assist", "Helpers / FX", "Advanced", "Helper-based assist starter with separate helper StateDef skeleton.", ("cmd", "cns", "air"), tags=("helper", "assist")),
    FeaturePreset("trap_mine", "Trap mine", "Helpers / FX", "Advanced", "Stationary projectile/trap skeleton.", ("cmd", "cns", "air"), tags=("helper", "trap")),
    FeaturePreset("aura_fx", "Aura FX", "Helpers / FX", "Beginner", "One-button aura/explod visual-effect skeleton.", ("cmd", "cns", "air"), tags=("fx", "explod")),
    FeaturePreset("afterimage_dash", "Afterimage dash", "Helpers / FX", "Intermediate", "Dash starter with AfterImage effect controllers.", ("cmd", "cns", "air"), tags=("movement", "fx")),
    FeaturePreset("lose_pose", "Lose pose", "Round Flow", "Beginner", "Adds a lose-pose action/state placeholder.", ("cns", "air"), tags=("round", "pose")),
    FeaturePreset("simple_ai", "Simple AI helper", "Tools", "Intermediate", "Adds beginner-readable AI helper comments and sample CPU triggers for later tuning.", ("cmd", "cns"), tags=("ai", "tool")),
    FeaturePreset("input_debug", "Input debug display", "Tools", "Beginner", "Adds a DisplayToClipboard block focused on commands, states, animation, and control flags.", ("cns",), tags=("debug", "tool")),
]

_seen_feature_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _EXTRA_FEATURE_PRESETS:
    if _preset.feature_id not in _seen_feature_ids:
        FEATURE_PRESETS.append(_preset)
        _seen_feature_ids.add(_preset.feature_id)

_BASE_BUILD_FEATURE_PACKAGE = build_feature_package


def _movement_fx_state(state_no: int, anim_no: int, label: str, x_vel: float = 4.0, y_vel: float = 0.0, ticks: int = 16, nothit: bool = False, afterimage: bool = False) -> str:
    extras = []
    if nothit:
        extras.append(f'''[State {state_no}, Beginner-safe invuln window]
type = NotHitBy
trigger1 = Time < {max(1, ticks - 4)}
value = SCA
''')
    if afterimage:
        extras.append(f'''[State {state_no}, AfterImage]
type = AfterImage
trigger1 = Time = 0
time = {ticks}
length = 8
palcontrast = 120,120,180
paladd = 20,20,40
palmul = .65,.65,.95
''')
    return f'''; MugenForge {label} movement state
[Statedef {state_no}]
type = S
movetype = I
physics = N
anim = {anim_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Velocity]
type = VelSet
trigger1 = Time = 0
x = {x_vel}
y = {y_vel}

{''.join(extras)}[State {state_no}, End]
type = ChangeState
trigger1 = Time >= {ticks}
value = 0
ctrl = 1

'''


def _state_minus_one(command_name: str, state_no: int, label: str, extra_trigger: str = "trigger1 = ctrl") -> str:
    return f'''[State -1, {label}]
type = ChangeState
value = {state_no}
triggerall = command = "{command_name}"
triggerall = roundstate = 2
{extra_trigger}

'''


def _command_block(command_name: str, command: str, time: int = 12, buffer: int = 4) -> str:
    return f'''[Command]
name = "{command_name}"
command = {command}
time = {time}
buffer.time = {buffer}

'''


def _teleport_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    cmd = _command_block("teleport", "D, D, z", 18) + _state_minus_one("teleport", 1250, "Teleport")
    cns = f'''; MugenForge teleport starter
[Statedef 1250]
type = S
movetype = I
physics = N
anim = 1250
ctrl = 0
sprpriority = 2

[State 1250, Flicker]
type = PalFX
trigger1 = Time = 0
time = 14
add = 80,80,120
mul = 180,180,255
sinadd = -80,-80,-120,4

[State 1250, Avoid hits during vanish]
type = NotHitBy
trigger1 = Time < 14
value = SCA

[State 1250, Reposition]
type = PosAdd
trigger1 = Time = 8
x = 80

[State 1250, End]
type = ChangeState
trigger1 = Time >= 18
value = 0
ctrl = 1

'''
    air = _simple_pose_air(1250, "Teleport", 4)
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a teleport starter. Tune distance, invulnerability, and FX after playtesting.")


def _defense_package(feature_id: str, preset: FeaturePreset, command_name: str, command: str, state_no: int, label: str, kind: str) -> FeaturePackage:
    cmd = _command_block(command_name, command, 8) + _state_minus_one(command_name, state_no, label)
    if kind == "parry":
        cns = f'''; MugenForge parry starter
[Statedef {state_no}]
type = S
movetype = I
physics = S
anim = {state_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Parry protection placeholder]
type = NotHitBy
trigger1 = Time < 8
value = SCA

[State {state_no}, Flash]
type = PalFX
trigger1 = Time = 0
time = 8
add = 80,120,255

[State {state_no}, End]
type = ChangeState
trigger1 = Time >= 14
value = 0
ctrl = 1

'''
    elif kind == "pushblock":
        cns = f'''; MugenForge pushblock starter
[Statedef {state_no}]
type = S
movetype = I
physics = S
anim = {state_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Push away opponent]
type = PlayerPush
trigger1 = Time < 10
value = 1

[State {state_no}, Safe recovery]
type = NotHitBy
trigger1 = Time < 6
value = SCA

[State {state_no}, End]
type = ChangeState
trigger1 = Time >= 16
value = 0
ctrl = 1

'''
    else:
        cns = _simple_pose_state(state_no, state_no, label)
    air = _simple_pose_air(state_no, label, 4)
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=f"Adds a {label.lower()} defensive starter. Tune triggers and hit behavior for your engine style.")


def _throw_package(feature_id: str, preset: FeaturePreset, command_name: str, command: str, state_no: int, label: str) -> FeaturePackage:
    cmd = _command_block(command_name, command, 10) + _state_minus_one(command_name, state_no, label, "trigger1 = ctrl\ntrigger1 = P2BodyDist X < 24")
    cns = f'''; MugenForge {label} starter
[Statedef {state_no}]
type = S
movetype = A
physics = S
anim = {state_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Throw attempt placeholder]
type = HitDef
trigger1 = AnimElem = 2
attr = S, NT
damage = 45, 0
animtype = Hard
guardflag =
hitflag = M-
priority = 7, Hit
pausetime = 8, 8
sparkno = -1
sparkxy = -10, -70
ground.type = High
ground.slidetime = 16
ground.hittime = 18
ground.velocity = -6, -3
fall = 1

[State {state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''
    air = _simple_pose_air(state_no, label, 5)
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=f"Adds a {label.lower()} starter with close-range command wiring and a throw-style HitDef.")


def _power_install_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    cmd = _command_block("power_install", "~D, DB, B, D, DB, B, z", 32) + _state_minus_one("power_install", 3300, "Power Install", "trigger1 = ctrl\ntrigger1 = power >= 1000")
    cns = '''; MugenForge power install starter
[Statedef 3300]
type = S
movetype = I
physics = S
anim = 3300
ctrl = 0
sprpriority = 2

[State 3300, Spend meter]
type = PowerAdd
trigger1 = Time = 0
value = -1000

[State 3300, Set install timer]
type = VarSet
trigger1 = Time = 0
v = 20
value = 600

[State 3300, Power-up flash]
type = PalFX
trigger1 = Time = 0
time = 60
add = 60,30,120
mul = 180,140,255
sinadd = 30,20,60,6

[State 3300, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

; Optional install timer upkeep. Move this into State -2/-3 after you understand your character flow.
[State -2, Power install timer note]
type = VarAdd
trigger1 = Var(20) > 0
v = 20
value = -1
ignorehitpause = 1

'''
    air = _simple_pose_air(3300, "Power Install", 8)
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a meter-spending power-install skeleton with timer variable and visual flash.")


def _helper_fx_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "striker":
        cmd = _command_block("striker_assist", "~D, DF, F, z", 20) + _state_minus_one("striker_assist", 2200, "Striker Assist", "trigger1 = ctrl\ntrigger1 = NumHelper(2201) = 0")
        cns = '''; MugenForge striker assist starter
[Statedef 2200]
type = S
movetype = I
physics = S
anim = 2200
ctrl = 0

[State 2200, Call striker]
type = Helper
trigger1 = Time = 2
helpertype = Normal
name = "MugenForge Striker"
ID = 2201
stateno = 2201
pos = 35,0
postype = p1
facing = 1
ownpal = 1

[State 2200, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

[Statedef 2201]
type = S
movetype = A
physics = N
anim = 2201
sprpriority = 4

[State 2201, Move]
type = VelSet
trigger1 = Time = 0
x = 5

[State 2201, Hit]
type = HitDef
trigger1 = Time = 8
attr = S, SA
damage = 60, 8
hitflag = MAF
guardflag = MA
priority = 4, Hit
pausetime = 6,8
ground.velocity = -5,0

[State 2201, Destroy]
type = DestroySelf
trigger1 = Time > 45

'''
        air = _simple_pose_air(2200, "Striker Call", 5) + _simple_pose_air(2201, "Striker Helper", 6)
        summary = "Adds a helper-based striker-assist skeleton. Replace helper sprites and tune helper behavior."
    elif kind == "trap":
        spec = _spec("Trap Mine", "trap_mine", "~D, DB, B, x", 2210, move_type="projectile", damage=65, frame_count=6, hit_frame=4, hit_box=(10, -28, 55, -4), sound=(5, 3), ground_velocity=(-2, 0))
        return _pack_from_specs(feature_id, preset.name, [spec], list(preset.beginner_notes))
    else:
        cmd = _command_block("aura_fx", "s", 1) + _state_minus_one("aura_fx", 2220, "Aura FX")
        cns = '''; MugenForge aura FX starter
[Statedef 2220]
type = S
movetype = I
physics = S
anim = 2220
ctrl = 0
sprpriority = 2

[State 2220, Aura explod placeholder]
type = Explod
trigger1 = Time = 0
anim = 2221
ID = 2221
pos = 0,-55
postype = p1
sprpriority = 6
ownpal = 1
removeongethit = 1

[State 2220, End]
type = ChangeState
trigger1 = Time >= 28
value = 0
ctrl = 1

'''
        air = _simple_pose_air(2220, "Aura Pose", 5) + _simple_pose_air(2221, "Aura FX", 6)
        summary = "Adds an aura/explod visual-effect skeleton. Replace action 2221 with real effect sprites."
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=summary)


def _tooling_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    if feature_id == "simple_ai":
        cns = '''; MugenForge simple AI helper starter
; This is intentionally conservative. It gives you safe examples rather than taking over your character.
[State -2, MugenForge AI movement idea]
type = ChangeState
triggerall = AILevel > 0
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2BodyDist X > 90
trigger1 = Random < 35
value = 100 ; forward dash from Feature Bank, if installed

[State -2, MugenForge AI fireball idea]
type = ChangeState
triggerall = AILevel > 0
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2BodyDist X > 120
trigger1 = Random < 25
value = 1000 ; fireball from Feature Bank, if installed

[State -2, MugenForge AI anti-air idea]
type = ChangeState
triggerall = AILevel > 0
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2StateType = A
trigger1 = P2BodyDist X < 70
trigger1 = Random < 50
value = 1100 ; dragon punch from Feature Bank, if installed

'''
        return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, cns), summary="Adds readable AI starter ideas for movement, fireball, and anti-air routing.")
    cns = '''; MugenForge input/state debug display
[State -2, Input Debug]
type = DisplayToClipboard
trigger1 = 1
text = "State=%d Anim=%d Time=%d Ctrl=%d MoveType=%s Pos=(%f,%f) Vel=(%f,%f)"
params = stateno, anim, time, ctrl, movetype, pos x, pos y, vel x, vel y
ignorehitpause = 1

[State -2, Input Debug append]
type = AppendToClipboard
trigger1 = 1
text = "\nPower=%d Life=%d P2DistX=%f AILevel=%d"
params = power, life, p2bodydist x, ailevel
ignorehitpause = 1

'''
    return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, cns), summary="Adds a debug clipboard overlay for testing state, animation, velocity, distance, and AILevel.")


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _EXTRA_FEATURE_PRESETS}:
        return _BASE_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    extra_specs: Dict[str, MoveWizardSpec] = {
        "medium_kick": _spec("Medium Kick", "medium_kick", "b", 240, damage=45, frame_count=5, hit_frame=3, hit_box=(22, -52, 72, -18), sound=(5, 1)),
        "heavy_kick": _spec("Heavy Kick", "heavy_kick", "c", 250, damage=78, frame_count=7, hit_frame=4, hit_box=(24, -62, 88, -16), sound=(5, 2), ground_velocity=(-6, 0), air_velocity=(-4, -5)),
        "crouch_punch": _spec("Crouch Punch", "crouch_punch", "D, x", 410, damage=24, frame_count=4, hit_frame=2, hit_box=(14, -48, 48, -20), body_box=(-20, -58, 20, 0), sound=(5, 0)),
        "sweep": _spec("Sweep", "sweep", "D, c", 420, damage=60, frame_count=7, hit_frame=4, hit_box=(20, -24, 92, -4), body_box=(-24, -58, 24, 0), sound=(5, 2), ground_velocity=(-7, -2), air_velocity=(-4, -4)),
        "launcher": _spec("Launcher", "launcher", "D, z", 430, damage=65, frame_count=7, hit_frame=3, hit_box=(12, -92, 56, -28), sound=(5, 4), ground_velocity=(-2, -8), air_velocity=(-2, -9)),
        "air_punch": _spec("Air Punch", "air_punch", "x", 610, damage=30, frame_count=5, hit_frame=3, hit_box=(14, -70, 52, -38), body_box=(-18, -80, 18, 4), sound=(5, 0), ground_velocity=(-3, -1), air_velocity=(-2, -4)),
        "slow_fireball": _spec("Slow Fireball", "slow_fireball", "~D, DF, F, y", 1010, move_type="projectile", damage=45, frame_count=7, hit_frame=5, hit_box=(20, -68, 62, -34), sound=(5, 3), ground_velocity=(-2, 0), air_velocity=(-1, -2)),
        "slide_kick": _spec("Slide Kick", "slide_kick", "~D, DF, F, a", 1200, damage=62, frame_count=8, hit_frame=4, hit_box=(18, -30, 86, -4), body_box=(-24, -46, 26, 0), sound=(5, 2), ground_velocity=(-6, 0), air_velocity=(-3, -3)),
        "spin_kick": _spec("Spin Kick", "spin_kick", "~D, DB, B, b", 1210, damage=75, frame_count=9, hit_frame=5, hit_box=(18, -70, 76, -16), sound=(5, 2), ground_velocity=(-5, 0), air_velocity=(-3, -5)),
        "anti_air_kick": _spec("Anti-air Kick", "anti_air_kick", "~F, D, DF, b", 1220, damage=85, frame_count=8, hit_frame=3, hit_box=(8, -100, 52, -22), sound=(5, 4), ground_velocity=(-3, -7), air_velocity=(-2, -8)),
        "air_fireball": _spec("Air Fireball", "air_fireball", "~D, DF, F, x", 1300, move_type="projectile", damage=50, frame_count=6, hit_frame=4, hit_box=(20, -62, 58, -30), body_box=(-18, -80, 18, 4), sound=(5, 3), ground_velocity=(-4, 2), air_velocity=(-2, 2)),
        "guard_cancel": _spec("Guard Cancel", "guard_cancel", "y+z", 1520, damage=70, frame_count=6, hit_frame=3, hit_box=(14, -82, 58, -30), sound=(5, 4), ground_velocity=(-5, -2), air_velocity=(-3, -5)),
        "counter_attack": _spec("Counter Attack", "counter_attack", "x+y", 1500, damage=70, frame_count=7, hit_frame=4, hit_box=(14, -78, 62, -32), sound=(5, 4), ground_velocity=(-5, 0), air_velocity=(-3, -5)),
        "super_rush": _spec("Super Rush", "super_rush", "~D, DF, F, D, DF, F, z", 3100, damage=180, frame_count=11, hit_frame=5, hit_box=(18, -84, 88, -24), sound=(5, 6), ground_velocity=(-9, 0), air_velocity=(-5, -7)),
        "super_uppercut": _spec("Super Uppercut", "super_uppercut", "~F, D, DF, F, D, DF, z", 3200, damage=210, frame_count=12, hit_frame=4, hit_box=(8, -110, 64, -20), sound=(5, 6), ground_velocity=(-4, -10), air_velocity=(-3, -11)),
    }
    if feature_id in extra_specs:
        return _pack_from_specs(feature_id, preset.name, [extra_specs[feature_id]], list(preset.beginner_notes))
    if feature_id == "roll_forward":
        cmd = _command_block("roll_forward", "F, F, x", 12) + _state_minus_one("roll_forward", 120, "Forward Roll")
        cns = _movement_fx_state(120, 120, "Forward Roll", 5.5, 0, 20, nothit=True)
        air = _simple_pose_air(120, "Forward Roll", 5)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a forward roll starter with a short NotHitBy window.")
    if feature_id == "roll_back":
        cmd = _command_block("roll_back", "B, B, x", 12) + _state_minus_one("roll_back", 121, "Back Roll")
        cns = _movement_fx_state(121, 121, "Back Roll", -5.0, 0, 20, nothit=True)
        air = _simple_pose_air(121, "Back Roll", 5)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a back roll starter with a short NotHitBy window.")
    if feature_id == "air_dash_forward":
        cmd = _command_block("air_dash_forward", "F, F", 10) + _state_minus_one("air_dash_forward", 140, "Air Dash Forward", "trigger1 = ctrl\ntrigger1 = statetype = A")
        cns = _movement_fx_state(140, 140, "Air Dash Forward", 6.0, -1.0, 15, afterimage=True).replace("type = S", "type = A", 1).replace("physics = N", "physics = N", 1)
        air = _simple_pose_air(140, "Air Dash Forward", 4)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds an air dash starter with afterimage effect.")
    if feature_id == "teleport":
        return _teleport_package(feature_id, preset)
    if feature_id == "basic_throw":
        return _throw_package(feature_id, preset, "basic_throw", "F, y", 800, "Basic Throw")
    if feature_id == "command_grab":
        return _throw_package(feature_id, preset, "command_grab", "~D, DB, B, y", 810, "Command Grab")
    if feature_id == "parry":
        return _defense_package(feature_id, preset, "parry", "z", 1510, "Parry", "parry")
    if feature_id == "pushblock":
        return _defense_package(feature_id, preset, "pushblock", "x+y", 1515, "Pushblock", "pushblock")
    if feature_id == "power_install":
        return _power_install_package(feature_id, preset)
    if feature_id == "striker_assist":
        return _helper_fx_package(feature_id, preset, "striker")
    if feature_id == "trap_mine":
        return _helper_fx_package(feature_id, preset, "trap")
    if feature_id == "aura_fx":
        return _helper_fx_package(feature_id, preset, "aura")
    if feature_id == "afterimage_dash":
        cmd = _command_block("afterimage_dash", "F, F, z", 12) + _state_minus_one("afterimage_dash", 126, "Afterimage Dash")
        cns = _movement_fx_state(126, 126, "Afterimage Dash", 6.5, 0, 18, afterimage=True)
        air = _simple_pose_air(126, "Afterimage Dash", 5)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a dash skeleton with AfterImage visual effect.")
    if feature_id == "lose_pose":
        return FeaturePackage(feature_id, preset.name, cns_block=_wrap(feature_id, preset.name, _simple_pose_state(170, 170, "Lose Pose")), air_block=_wrap(feature_id, preset.name, _simple_pose_air(170, "Lose Pose", 8)), summary="Adds lose pose starter blocks.")
    if feature_id in {"simple_ai", "input_debug"}:
        return _tooling_package(feature_id, preset)
    return _BASE_BUILD_FEATURE_PACKAGE(feature_id)


KIT_PRESETS: Dict[str, List[str]] = {
    "Starter Beginner Pack": ["starter_basics", "light_punch", "medium_punch", "heavy_punch", "crouch_kick", "fireball", "dash_forward", "back_dash", "taunt"],
    "Six Button Normals": ["light_punch", "medium_punch", "heavy_punch", "light_kick", "medium_kick", "heavy_kick", "crouch_punch", "crouch_kick", "sweep", "launcher", "air_punch", "air_kick"],
    "Movement Toolkit": ["dash_forward", "back_dash", "roll_forward", "roll_back", "air_dash_forward", "teleport", "afterimage_dash"],
    "Specials Toolkit": ["fireball", "slow_fireball", "dragon_punch", "slide_kick", "spin_kick", "anti_air_kick", "air_fireball", "trap_mine"],
    "Defense Toolkit": ["parry", "pushblock", "counter_attack", "guard_cancel", "roll_forward", "roll_back"],
    "Grapple Toolkit": ["basic_throw", "command_grab"],
    "Supers and FX Toolkit": ["projectile_plus_super", "super_rush", "super_uppercut", "power_install", "striker_assist", "aura_fx"],
    "Round Flow Toolkit": ["intro_pose", "win_pose", "lose_pose", "taunt"],
    "Creator Utility Toolkit": ["common_commands", "debug_overlay", "input_debug", "simple_ai"],
    "Full No-Code Creator Pack": [
        "starter_basics", "common_commands", "light_punch", "medium_punch", "heavy_punch", "light_kick", "medium_kick", "heavy_kick",
        "crouch_punch", "crouch_kick", "sweep", "launcher", "air_punch", "air_kick", "fireball", "slow_fireball", "dragon_punch",
        "slide_kick", "spin_kick", "anti_air_kick", "dash_forward", "back_dash", "roll_forward", "roll_back", "teleport",
        "basic_throw", "command_grab", "parry", "pushblock", "counter_attack", "guard_cancel", "projectile_plus_super", "super_rush",
        "power_install", "striker_assist", "aura_fx", "intro_pose", "win_pose", "lose_pose", "taunt", "debug_overlay", "input_debug", "simple_ai",
    ],
}


def kit_names() -> List[str]:
    return list(KIT_PRESETS.keys())


def kit_preview_text(kit_name: str) -> str:
    ids = KIT_PRESETS.get(kit_name, [])
    lines = [f"Creator Kit: {kit_name}", "", f"Features: {len(ids)}"]
    for fid in ids:
        try:
            preset = get_preset(fid)
            lines.append(f"- {preset.category}: {preset.name} [{fid}]")
        except Exception:
            lines.append(f"- {fid}")
    lines.append("\nInstall Kit writes the generated CMD/CNS/AIR blocks with backups and skips Feature Bank IDs that are already present.")
    return "\n".join(lines).strip() + "\n"


def apply_feature_ids_pack(root: Path, ids: Sequence[str]) -> ApplyResult:
    combined = ApplyResult()
    for fid in ids:
        result = apply_preset(root, fid)
        combined.changed_files += result.changed_files
        combined.skipped_files += result.skipped_files
        combined.warnings += result.warnings
        combined.created_files += result.created_files
    return combined


def apply_kit(root: Path, kit_name: str) -> ApplyResult:
    return apply_feature_ids_pack(root, KIT_PRESETS.get(kit_name, []))


def make_placeholder_sprite_sheet(root: Path) -> ApplyResult:
    result = ApplyResult()
    root = Path(root)
    spritesheets = root / "spritesheets"
    spritesheets.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        result.warnings.append(f"Pillow is required to generate placeholder sprite sheets: {exc}")
        return result
    cell_w, cell_h = 96, 96
    cols, rows = 8, 6
    img = Image.new("RGBA", (cell_w * cols, cell_h * rows), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    labels = [
        "idle", "turn", "crouch", "walk", "jump", "land", "lp", "mp",
        "hp", "lk", "mk", "hk", "c.lp", "c.lk", "sweep", "launch",
        "air p", "air k", "dash", "back", "roll", "tele", "fire", "dp",
        "slide", "spin", "throw", "grab", "parry", "guard", "super", "install",
        "assist", "aura", "intro", "win", "lose", "taunt", "hit", "ko",
        "fx1", "fx2", "proj", "mine", "spark", "dust", "blank", "blank",
    ]
    for idx, label in enumerate(labels[:cols * rows]):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        base = ((idx * 37) % 180 + 40, (idx * 59) % 180 + 40, (idx * 83) % 180 + 40, 255)
        draw.rectangle([x + 12, y + 18, x + 84, y + 90], outline=base, width=3)
        draw.ellipse([x + 34, y + 8, x + 62, y + 36], outline=base, width=3)
        draw.line([x + 48, y + 36, x + 48, y + 72], fill=base, width=3)
        draw.line([x + 48, y + 46, x + 24, y + 58], fill=base, width=3)
        draw.line([x + 48, y + 46, x + 72, y + 58], fill=base, width=3)
        draw.text((x + 4, y + 4), label, fill=base)
    out = spritesheets / "mugenforge_placeholder_sheet.png"
    img.save(out)
    plan = {
        "sheet": str(out.name),
        "cell_width": cell_w,
        "cell_height": cell_h,
        "columns": cols,
        "rows": rows,
        "axis_x": 48,
        "axis_y": 88,
        "recommended_next_step": "Open Sheet Import, choose this PNG, set cell 96x96, columns 8, rows 6, axis 48/88, then export slices/build SFF.",
        "labels": labels[:cols * rows],
    }
    plan_path = spritesheets / "mugenforge_placeholder_sheet_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    result.created_files += [str(out.relative_to(root)), str(plan_path.relative_to(root))]
    return result


# ---------------------------------------------------------------------------
# v2.2 expanded no-code bank: more presets, archetype kits, creator utility
# ---------------------------------------------------------------------------

_V22_EXTRA_FEATURE_PRESETS: List[FeaturePreset] = [
    FeaturePreset("overhead_attack", "Overhead attack", "Normal Attacks", "Beginner", "A standing overhead starter for opening up crouch-blocking opponents.", ("cmd", "cns", "air"), tags=("attack", "overhead")),
    FeaturePreset("close_heavy", "Close heavy strike", "Normal Attacks", "Beginner", "A short-range high-impact normal with more hitstop/knockback feel.", ("cmd", "cns", "air"), tags=("attack", "normal")),
    FeaturePreset("forward_punch", "Forward + punch command normal", "Normal Attacks", "Beginner", "A simple command normal wired to F+x.", ("cmd", "cns", "air"), tags=("attack", "command-normal")),
    FeaturePreset("forward_kick", "Forward + kick command normal", "Normal Attacks", "Beginner", "A simple command normal wired to F+a.", ("cmd", "cns", "air"), tags=("attack", "command-normal")),
    FeaturePreset("hop_kick", "Hop kick", "Normal Attacks", "Beginner", "A small-hop kicking attack starter.", ("cmd", "cns", "air"), tags=("attack", "air")),
    FeaturePreset("crossup_kick", "Cross-up kick", "Normal Attacks", "Intermediate", "A jumping/cross-up style kick starter with body and hitbox placement ready for visual tuning.", ("cmd", "cns", "air"), tags=("attack", "air")),
    FeaturePreset("dash_attack", "Dash attack", "Movement", "Beginner", "A forward-moving attack state for characters who need a simple advancing strike.", ("cmd", "cns", "air"), tags=("movement", "attack")),
    FeaturePreset("run_forward", "Run forward", "Movement", "Beginner", "Hold-forward-style run starter with a simple movement state.", ("cmd", "cns", "air"), tags=("movement", "run")),
    FeaturePreset("run_stop", "Run stop / brake", "Movement", "Beginner", "A braking animation/state to return from a run smoothly.", ("cmd", "cns", "air"), tags=("movement", "run")),
    FeaturePreset("short_hop", "Short hop", "Movement", "Intermediate", "A short hop state for King of Fighters-style movement.", ("cmd", "cns", "air"), tags=("movement", "jump")),
    FeaturePreset("double_jump", "Double jump skeleton", "Movement", "Intermediate", "Adds a readable double-jump skeleton using a variable gate. Tune it against your jump states.", ("cmd", "cns", "air"), tags=("movement", "air")),
    FeaturePreset("wall_jump", "Wall jump skeleton", "Movement", "Intermediate", "A wall-jump starter with comments for tuning wall distance triggers.", ("cmd", "cns", "air"), tags=("movement", "air")),
    FeaturePreset("quick_rise", "Quick rise / tech get-up", "Defense", "Intermediate", "A recovery option starter that can be wired into your get-up flow.", ("cmd", "cns", "air"), tags=("defense", "recovery")),
    FeaturePreset("air_recovery", "Air recovery", "Defense", "Intermediate", "Air tech/recovery starter state for faster character feel.", ("cmd", "cns", "air"), tags=("defense", "air")),
    FeaturePreset("guard_break", "Guard break attack", "Defense", "Intermediate", "A heavy guard-break style strike skeleton. Tune guard behavior to match your game rules.", ("cmd", "cns", "air"), tags=("attack", "guard")),
    FeaturePreset("armor_tackle", "Armored tackle", "Special Moves", "Intermediate", "A forward special with temporary hit protection and a heavy body hitbox.", ("cmd", "cns", "air"), tags=("armor", "special")),
    FeaturePreset("invincible_reversal", "Invincible reversal", "Special Moves", "Intermediate", "Wake-up/reversal style starter with a short NotHitBy window.", ("cmd", "cns", "air"), tags=("reversal", "special")),
    FeaturePreset("rekka_chain", "Three-step rekka chain", "Special Moves", "Intermediate", "Generates three chained special states with beginner-readable chain windows.", ("cmd", "cns", "air"), tags=("special", "combo")),
    FeaturePreset("charge_fireball", "Charge fireball", "Special Moves", "Intermediate", "Back-charge-forward projectile starter.", ("cmd", "cns", "air"), tags=("charge", "projectile")),
    FeaturePreset("flash_kick", "Flash kick", "Special Moves", "Intermediate", "Down-charge-up anti-air kick starter.", ("cmd", "cns", "air"), tags=("charge", "anti-air")),
    FeaturePreset("power_wave", "Ground power wave", "Special Moves", "Beginner", "A ground-hugging projectile starter.", ("cmd", "cns", "air"), tags=("projectile", "special")),
    FeaturePreset("beam_projectile", "Beam projectile", "Special Moves", "Intermediate", "A beam-style projectile skeleton with a longer horizontal hitbox.", ("cmd", "cns", "air"), tags=("projectile", "beam")),
    FeaturePreset("boomerang_projectile", "Boomerang projectile", "Special Moves", "Advanced", "A two-phase projectile/helper-style skeleton for returning projectile ideas.", ("cmd", "cns", "air"), tags=("projectile", "helper")),
    FeaturePreset("homing_orb", "Homing orb helper", "Helpers / FX", "Advanced", "A helper-based homing-orb skeleton with simple turn-toward-opponent logic.", ("cmd", "cns", "air"), tags=("helper", "projectile")),
    FeaturePreset("reflect_shield", "Reflect shield", "Defense", "Advanced", "A defensive helper/shield skeleton for projectile-reflect concepts.", ("cmd", "cns", "air"), tags=("defense", "helper")),
    FeaturePreset("dive_kick", "Dive kick", "Special Moves", "Intermediate", "Air-only downward special kick starter.", ("cmd", "cns", "air"), tags=("air", "special")),
    FeaturePreset("ground_bounce", "Ground-bounce strike", "Special Moves", "Intermediate", "A heavier attack tuned with upward/downward hit velocity for bounce-style testing.", ("cmd", "cns", "air"), tags=("attack", "bounce")),
    FeaturePreset("wall_bounce", "Wall-bounce strike", "Special Moves", "Intermediate", "A strong side-launching hit skeleton for wall-bounce style routes.", ("cmd", "cns", "air"), tags=("attack", "bounce")),
    FeaturePreset("target_combo", "Target combo", "Combos", "Beginner", "A three-button target combo skeleton with state chaining notes included.", ("cmd", "cns", "air"), tags=("combo", "attack")),
    FeaturePreset("auto_combo", "Beginner auto-combo", "Combos", "Beginner", "A simple repeated-button auto-combo starter for non-coders.", ("cmd", "cns", "air"), tags=("combo", "beginner")),
    FeaturePreset("air_combo_starter", "Air combo starter", "Combos", "Intermediate", "Jumping starter plus air follow-up skeleton for air-combo characters.", ("cmd", "cns", "air"), tags=("combo", "air")),
    FeaturePreset("launcher_air_route", "Launcher into air route", "Combos", "Intermediate", "Launcher plus air punch/kick package with notes for tuning juggle flow.", ("cmd", "cns", "air"), tags=("combo", "launcher")),
    FeaturePreset("meter_charge", "Meter charge", "Supers / Meter", "Beginner", "Hold-button meter charge state with safe beginner limits.", ("cmd", "cns", "air"), tags=("meter", "utility")),
    FeaturePreset("small_heal", "Small heal", "Supers / Meter", "Intermediate", "A meter-spending small heal skeleton for custom characters.", ("cmd", "cns", "air"), tags=("meter", "utility")),
    FeaturePreset("super_beam", "Super beam", "Supers / Meter", "Intermediate", "A meter-spending beam super skeleton with SuperPause and projectile hitbox.", ("cmd", "cns", "air"), tags=("super", "beam")),
    FeaturePreset("cinematic_super", "Cinematic super skeleton", "Supers / Meter", "Advanced", "A staged super skeleton with SuperPause, camera/fx comments, and a big hit.", ("cmd", "cns", "air"), tags=("super", "cinematic")),
    FeaturePreset("command_super_grab", "Command super grab", "Supers / Meter", "Advanced", "A meter-spending close-range super grab starter.", ("cmd", "cns", "air"), tags=("super", "grapple")),
    FeaturePreset("install_dash_cancel", "Install dash cancel", "Supers / Meter", "Advanced", "A dash-cancel skeleton gated by the power-install variable from the Power Install preset.", ("cmd", "cns", "air"), tags=("install", "movement")),
    FeaturePreset("stance_switch", "Stance switch", "Stance / Modes", "Intermediate", "A simple mode toggle using Var(21), with comments for mode-specific move edits.", ("cmd", "cns", "air"), tags=("stance", "mode")),
    FeaturePreset("stance_special", "Stance-only special", "Stance / Modes", "Intermediate", "A special move gated by Var(21), intended to pair with Stance Switch.", ("cmd", "cns", "air"), tags=("stance", "special")),
    FeaturePreset("summon_clone", "Clone summon", "Helpers / FX", "Advanced", "A helper clone skeleton that moves forward and attacks before destroying itself.", ("cmd", "cns", "air"), tags=("helper", "clone")),
    FeaturePreset("dust_fx", "Dust step FX", "Helpers / FX", "Beginner", "Adds a reusable dust Explod skeleton for dashes/runs/landings.", ("cmd", "cns", "air"), tags=("fx", "explod")),
    FeaturePreset("hit_spark_fx", "Custom hit spark FX", "Helpers / FX", "Beginner", "Adds placeholder hit spark AIR actions and notes for replacing default sparks.", ("cns", "air"), tags=("fx", "spark")),
    FeaturePreset("voice_callouts", "Voice callout hooks", "Tools", "Beginner", "Adds commented PlaySnd hooks for intro, taunt, special, super, win, and lose callouts.", ("cns",), tags=("sound", "voice")),
    FeaturePreset("training_shortcuts", "Training shortcuts", "Tools", "Beginner", "Adds optional debug/testing commands for quickly jumping to common states while developing.", ("cmd", "cns"), tags=("debug", "testing")),
    FeaturePreset("ai_level_scaler", "AI level scaler", "Tools", "Intermediate", "Adds beginner-readable AI routing separated by AILevel tiers.", ("cns",), tags=("ai", "tool")),
    FeaturePreset("round_state_helper", "Round-state helper", "Round Flow", "Beginner", "Adds readable State -2 examples for intro/win/lose/roundstate checks.", ("cns",), tags=("round", "tool")),
    FeaturePreset("dizzy_pose", "Dizzy / stun pose", "Round Flow", "Beginner", "Adds a dizzy/stun pose state and AIR placeholder.", ("cns", "air"), tags=("pose", "round")),
    FeaturePreset("perfect_win_pose", "Perfect win pose", "Round Flow", "Beginner", "Adds a separate perfect-win pose skeleton.", ("cns", "air"), tags=("pose", "round")),
    FeaturePreset("time_over_pose", "Time-over pose", "Round Flow", "Beginner", "Adds a time-over pose skeleton for custom round flow.", ("cns", "air"), tags=("pose", "round")),
]

_v22_seen_feature_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _V22_EXTRA_FEATURE_PRESETS:
    if _preset.feature_id not in _v22_seen_feature_ids:
        FEATURE_PRESETS.append(_preset)
        _v22_seen_feature_ids.add(_preset.feature_id)

_BASE_BUILD_FEATURE_PACKAGE_V22 = build_feature_package


def _attack_with_custom_state(feature_id: str, preset: FeaturePreset, spec: MoveWizardSpec, extra_cns: str = "") -> FeaturePackage:
    pkg = _pack_from_specs(feature_id, preset.name, [spec], list(preset.beginner_notes))
    if extra_cns.strip():
        pkg.cns_block += _wrap(feature_id + "_extra_logic", preset.name + " extra logic", extra_cns)
    return pkg


def _charge_or_utility_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "meter_charge":
        cmd = _command_block("meter_charge", "/s", 1, 1) + _state_minus_one("meter_charge", 3400, "Meter Charge")
        cns = '''; MugenForge meter charge starter
[Statedef 3400]
type = S
movetype = I
physics = S
anim = 3400
ctrl = 0
sprpriority = 2

[State 3400, Add power while held]
type = PowerAdd
trigger1 = command = "meter_charge"
trigger1 = power < 3000
value = 8

[State 3400, Charge FX]
type = PalFX
trigger1 = Time % 12 = 0
time = 8
add = 30,30,70

[State 3400, Release]
type = ChangeState
trigger1 = command != "meter_charge"
trigger2 = power >= 3000
value = 0
ctrl = 1

'''
        air = _simple_pose_air(3400, "Meter Charge", 6)
        summary = "Adds a hold-button meter charge starter. Tune power gain and max meter for your game."
    elif kind == "small_heal":
        cmd = _command_block("small_heal", "~D, DB, B, c", 20) + _state_minus_one("small_heal", 3410, "Small Heal", "trigger1 = ctrl\ntrigger1 = power >= 500")
        cns = '''; MugenForge small heal starter
[Statedef 3410]
type = S
movetype = I
physics = S
anim = 3410
ctrl = 0
sprpriority = 2

[State 3410, Spend meter]
type = PowerAdd
trigger1 = Time = 0
value = -500

[State 3410, Heal]
type = LifeAdd
trigger1 = Time = 18
value = 80
kill = 0
absolute = 0

[State 3410, Heal FX]
type = PalFX
trigger1 = Time = 18
time = 24
add = 40,100,40

[State 3410, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''
        air = _simple_pose_air(3410, "Small Heal", 8)
        summary = "Adds a meter-spending heal skeleton."
    else:
        cmd = _command_block("voice_callout", "s", 1) + "; Add these PlaySnd hooks into matching states after replacing placeholder sounds.\n"
        cns = '''; MugenForge voice callout hook bank
; These are safe examples. Move/copy the PlaySnd controllers into your actual intro/taunt/special/super/win/lose states.
[State 190, Voice intro example]
type = PlaySnd
trigger1 = Time = 0
value = 7,0
channel = 3
persistent = 0

[State 195, Voice taunt example]
type = PlaySnd
trigger1 = Time = 0
value = 7,1
channel = 3
persistent = 0

[State 1000, Voice special example]
type = PlaySnd
trigger1 = Time = 0
value = 7,2
channel = 3
persistent = 0

[State 3000, Voice super example]
type = PlaySnd
trigger1 = Time = 0
value = 7,3
channel = 3
persistent = 0

'''
        air = ""
        summary = "Adds commented voice-callout PlaySnd hooks. Replace sound group 7 with your voice bank."
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=summary)


def _rekka_chain_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    specs = [
        _spec("Rekka 1", "rekka_1", "~D, DF, F, x", 1230, damage=42, frame_count=6, hit_frame=3, hit_box=(20, -70, 68, -32), sound=(5, 1), ground_velocity=(-3, 0)),
        _spec("Rekka 2", "rekka_2", "~D, DF, F, x", 1231, damage=48, frame_count=6, hit_frame=3, hit_box=(20, -66, 76, -24), sound=(5, 2), ground_velocity=(-4, 0)),
        _spec("Rekka 3", "rekka_3", "~D, DF, F, x", 1232, damage=62, frame_count=7, hit_frame=4, hit_box=(22, -76, 86, -20), sound=(5, 2), ground_velocity=(-6, -2)),
    ]
    pkg = _pack_from_specs(feature_id, preset.name, specs, list(preset.beginner_notes))
    chain = '''; MugenForge rekka chain windows. Paste inside the matching states for tighter control if needed.
[State 1230, Chain to Rekka 2]
type = ChangeState
trigger1 = command = "rekka_2"
trigger1 = AnimElem >= 4
value = 1231

[State 1231, Chain to Rekka 3]
type = ChangeState
trigger1 = command = "rekka_3"
trigger1 = AnimElem >= 4
value = 1232

'''
    pkg.cns_block += _wrap(feature_id + "_chain_windows", "Rekka chain windows", chain)
    pkg.summary += "\n\nAdds three rekka states plus chain-window notes."
    return pkg


def _helper_projectile_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "boomerang":
        cmd_name, cmd_input, state_no, helper_no, label = "boomerang_projectile", "~D, DB, B, x", 1320, 1321, "Boomerang Projectile"
        helper_logic = '''[State 1321, Move out]
type = VelSet
trigger1 = Time < 24
x = 5

[State 1321, Return]
type = VelSet
trigger1 = Time >= 24
x = -5

[State 1321, Face owner-ish]
type = Turn
trigger1 = Time = 24

[State 1321, Hit]
type = HitDef
trigger1 = Time = 4
trigger2 = Time = 28
attr = S, SP
damage = 45,5
hitflag = MAF
guardflag = MA
priority = 4, Hit
ground.velocity = -4,0

[State 1321, Destroy]
type = DestroySelf
trigger1 = Time > 52
'''
    elif kind == "homing":
        cmd_name, cmd_input, state_no, helper_no, label = "homing_orb", "~D, DF, F, c", 1330, 1331, "Homing Orb"
        helper_logic = '''[State 1331, Track X]
type = VelSet
trigger1 = 1
x = ifelse(P2Dist X > 0, 3.5, -3.5)
y = ifelse(P2Dist Y > -40, -1.5, 1.5)

[State 1331, Hit]
type = HitDef
trigger1 = Time = 8
attr = S, SP
damage = 55,5
hitflag = MAF
guardflag = MA
priority = 4, Hit
ground.velocity = -4,-2

[State 1331, Destroy]
type = DestroySelf
trigger1 = Time > 90
'''
    elif kind == "reflect":
        cmd_name, cmd_input, state_no, helper_no, label = "reflect_shield", "~D, DB, B, z", 1540, 1541, "Reflect Shield"
        helper_logic = '''[State 1541, Shield hitbox placeholder]
type = HitOverride
trigger1 = Time < 28
attr = SCA, AP, SP, HP
stateno = 1542
slot = 0
time = 1

[State 1541, Destroy]
type = DestroySelf
trigger1 = Time > 30

[Statedef 1542]
type = S
movetype = I
physics = N
anim = 1541

[State 1542, Reflect flash]
type = PalFX
trigger1 = Time = 0
time = 8
add = 80,120,255

[State 1542, Return]
type = ChangeState
trigger1 = Time > 8
value = 1541
'''
    else:
        cmd_name, cmd_input, state_no, helper_no, label = "summon_clone", "~D, D, z", 2230, 2231, "Clone Summon"
        helper_logic = '''[State 2231, Run]
type = VelSet
trigger1 = Time = 0
x = 4.5

[State 2231, Clone hit]
type = HitDef
trigger1 = Time = 10
attr = S, SA
damage = 70,8
hitflag = MAF
guardflag = MA
priority = 4, Hit
ground.velocity = -5,0

[State 2231, Destroy]
type = DestroySelf
trigger1 = Time > 50
'''
    cmd = _command_block(cmd_name, cmd_input, 20) + _state_minus_one(cmd_name, state_no, label, "trigger1 = ctrl\ntrigger1 = NumHelper(%d) = 0" % helper_no)
    cns = f'''; MugenForge {label} helper starter
[Statedef {state_no}]
type = S
movetype = I
physics = S
anim = {state_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Spawn helper]
type = Helper
trigger1 = Time = 4
helpertype = Normal
name = "MugenForge {label}"
ID = {helper_no}
stateno = {helper_no}
pos = 40,-50
postype = p1
facing = 1
ownpal = 1

[State {state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

[Statedef {helper_no}]
type = S
movetype = A
physics = N
anim = {helper_no}
sprpriority = 5

{helper_logic}

'''
    air = _simple_pose_air(state_no, label, 5) + _simple_pose_air(helper_no, label + " Helper", 6)
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=f"Adds a {label.lower()} helper skeleton. Replace helper sprites and tune behavior.")


def _super_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "super_beam":
        cmd_name, command, state_no, anim_no, dmg, label = "super_beam", "~D, DF, F, D, DF, F, y", 3500, 3500, 190, "Super Beam"
        cns_extra = '''[State 3500, Spend meter]
type = PowerAdd
trigger1 = Time = 0
value = -1000

[State 3500, Super pause]
type = SuperPause
trigger1 = Time = 0
time = 32
movetime = 32
poweradd = 0

'''
    elif kind == "cinematic":
        cmd_name, command, state_no, anim_no, dmg, label = "cinematic_super", "~D, DF, F, D, DB, B, z", 3510, 3510, 260, "Cinematic Super"
        cns_extra = '''[State 3510, Spend meter]
type = PowerAdd
trigger1 = Time = 0
value = -2000

[State 3510, Super pause]
type = SuperPause
trigger1 = Time = 0
time = 45
movetime = 45
poweradd = 0

[State 3510, Dramatic flash]
type = PalFX
trigger1 = Time = 0
time = 45
add = 90,90,140
sinadd = -60,-60,-100,5

'''
    else:
        cmd_name, command, state_no, anim_no, dmg, label = "command_super_grab", "~D, DB, B, D, DB, B, y", 3520, 3520, 220, "Command Super Grab"
        cmd = _command_block(cmd_name, command, 32) + _state_minus_one(cmd_name, state_no, label, "trigger1 = ctrl\ntrigger1 = power >= 1000\ntrigger1 = P2BodyDist X < 28")
        cns = f'''; MugenForge {label} starter
[Statedef {state_no}]
type = S
movetype = A
physics = S
anim = {anim_no}
ctrl = 0
sprpriority = 2

[State {state_no}, Spend meter]
type = PowerAdd
trigger1 = Time = 0
value = -1000

[State {state_no}, Super pause]
type = SuperPause
trigger1 = Time = 0
time = 28
movetime = 28
poweradd = 0

[State {state_no}, Throw hit]
type = HitDef
trigger1 = AnimElem = 3
attr = S, HT
damage = {dmg}, 0
guardflag =
hitflag = M-
priority = 7, Hit
pausetime = 10, 12
ground.velocity = -7, -5
fall = 1

[State {state_no}, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

'''
        air = _simple_pose_air(anim_no, label, 9)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=f"Adds a meter-spending {label.lower()} skeleton.")
    spec = _spec(label, cmd_name, command, state_no, anim_no=anim_no, move_type="projectile", damage=dmg, frame_count=10, ticks=4, hit_frame=5, hit_box=(20, -86, 160, -28), sound=(5, 6), ground_velocity=(-8, -2), air_velocity=(-5, -6))
    pkg = _pack_from_specs(feature_id, preset.name, [spec], list(preset.beginner_notes))
    pkg.cns_block += _wrap(feature_id + "_super_logic", label + " meter/superpause", cns_extra)
    pkg.summary += "\n\nIncludes meter-spend and SuperPause logic as a separate marked block."
    return pkg


def _stance_or_ai_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "stance_switch":
        cmd = _command_block("stance_switch", "D, D, x", 16) + _state_minus_one("stance_switch", 3600, "Stance Switch")
        cns = '''; MugenForge stance switch starter
[Statedef 3600]
type = S
movetype = I
physics = S
anim = 3600
ctrl = 0
sprpriority = 2

[State 3600, Toggle stance variable]
type = VarSet
trigger1 = Time = 0
v = 21
value = ifelse(Var(21) = 0, 1, 0)

[State 3600, Stance flash]
type = PalFX
trigger1 = Time = 0
time = 18
add = 40,40,120

[State 3600, End]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

; MugenForge note: Use triggerall = Var(21) = 1 to gate stance-only moves.
'''
        air = _simple_pose_air(3600, "Stance Switch", 6)
        summary = "Adds a Var(21)-based stance toggle."
    elif kind == "ai_level_scaler":
        cmd = ""
        cns = '''; MugenForge AI level scaler examples
[State -2, Easy AI poke]
type = ChangeState
triggerall = AILevel > 0
triggerall = AILevel <= 3
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2BodyDist X < 60
trigger1 = Random < 20
value = 200

[State -2, Medium AI projectile]
type = ChangeState
triggerall = AILevel >= 4
triggerall = AILevel <= 6
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2BodyDist X > 100
trigger1 = Random < 35
value = 1000

[State -2, Hard AI anti-air]
type = ChangeState
triggerall = AILevel >= 7
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = P2StateType = A
trigger1 = P2BodyDist X < 85
trigger1 = Random < 70
value = 1100

'''
        air = ""
        summary = "Adds AILevel-tier examples that beginners can read and tune."
    elif kind == "training_shortcuts":
        cmd = '''; MugenForge training shortcut commands. Remove before release if unwanted.
[Command]
name = "debug_idle"
command = /x
time = 1
buffer.time = 1

[Command]
name = "debug_fireball"
command = /y
time = 1
buffer.time = 1

[Command]
name = "debug_super"
command = /z
time = 1
buffer.time = 1

'''
        cns = '''; MugenForge training shortcut router. Remove before release if unwanted.
[State -2, Debug idle]
type = ChangeState
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = command = "debug_idle"
value = 0

[State -2, Debug fireball]
type = ChangeState
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = command = "debug_fireball"
value = 1000

[State -2, Debug super]
type = ChangeState
triggerall = roundstate = 2
triggerall = ctrl
trigger1 = command = "debug_super"
value = 3000

'''
        air = ""
        summary = "Adds optional debug shortcuts for testing states quickly. Remove before release."
    else:
        cmd = ""
        cns = '''; MugenForge round-state helper examples
[State -2, Round flow note]
type = DisplayToClipboard
trigger1 = 0 ; set to 1 while debugging round flow
text = "RoundState=%d Win=%d Lose=%d Time=%d"
params = roundstate, win, lose, time
ignorehitpause = 1

; Common RoundState meanings: 0 pre-intro/loading, 1 intro, 2 fighting, 3 round over, 4 win screen/end.
; Use this as a readable note bank while wiring intro/win/lose logic.
'''
        air = ""
        summary = "Adds readable round-state notes and an optional debug DisplayToClipboard block."
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=summary)


def _fx_or_pose_package(feature_id: str, preset: FeaturePreset, kind: str) -> FeaturePackage:
    if kind == "dust":
        cmd = _command_block("dust_fx_test", "s", 1) + _state_minus_one("dust_fx_test", 2240, "Dust FX Test")
        cns = '''; MugenForge dust FX starter
[Statedef 2240]
type = S
movetype = I
physics = S
anim = 2240
ctrl = 0

[State 2240, Dust Explod]
type = Explod
trigger1 = Time = 0
anim = 2241
ID = 2241
pos = 0,0
postype = p1
sprpriority = 1
ownpal = 1
removeongethit = 1

[State 2240, End]
type = ChangeState
trigger1 = Time > 16
value = 0
ctrl = 1

'''
        air = _simple_pose_air(2240, "Dust Test Pose", 3) + _simple_pose_air(2241, "Dust FX", 5)
        summary = "Adds a reusable dust Explod skeleton."
    elif kind == "spark":
        cmd = ""
        cns = '''; MugenForge custom hit spark notes
; Replace sparkno/guardsparkno in your HitDefs after you create matching AIR actions.
; Example: sparkno = S2250, guardsparkno = S2251 depending on the engine/version/style you target.
'''
        air = _simple_pose_air(2250, "Custom Hit Spark", 5) + _simple_pose_air(2251, "Custom Guard Spark", 5)
        summary = "Adds placeholder AIR actions and notes for custom hit/guard sparks."
    else:
        mapping = {
            "dizzy": (5300, "Dizzy Pose", 8),
            "perfect": (181, "Perfect Win Pose", 8),
            "timeover": (182, "Time Over Pose", 8),
        }
        state_no, label, frames = mapping[kind]
        cmd = ""
        cns = _simple_pose_state(state_no, state_no, label)
        air = _simple_pose_air(state_no, label, frames)
        summary = f"Adds {label.lower()} starter blocks."
    return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary=summary)


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _V22_EXTRA_FEATURE_PRESETS}:
        return _BASE_BUILD_FEATURE_PACKAGE_V22(feature_id)
    preset = get_preset(feature_id)
    extra_specs: Dict[str, MoveWizardSpec] = {
        "overhead_attack": _spec("Overhead Attack", "overhead_attack", "F, y", 440, damage=52, frame_count=6, hit_frame=4, hit_box=(18, -84, 64, -40), sound=(5, 1), ground_velocity=(-4, 0)),
        "close_heavy": _spec("Close Heavy", "close_heavy", "z", 260, damage=90, frame_count=8, hit_frame=4, hit_box=(12, -80, 54, -28), sound=(5, 2), ground_velocity=(-7, 0), air_velocity=(-4, -6)),
        "forward_punch": _spec("Forward Punch", "forward_punch", "F, x", 270, damage=42, frame_count=5, hit_frame=3, hit_box=(20, -74, 70, -34), sound=(5, 1)),
        "forward_kick": _spec("Forward Kick", "forward_kick", "F, a", 280, damage=48, frame_count=6, hit_frame=3, hit_box=(22, -60, 78, -16), sound=(5, 1)),
        "hop_kick": _spec("Hop Kick", "hop_kick", "UF, b", 620, damage=44, frame_count=6, hit_frame=3, hit_box=(16, -64, 62, -18), body_box=(-18, -84, 18, 4), sound=(5, 1), ground_velocity=(-4, -2), air_velocity=(-2, -5)),
        "crossup_kick": _spec("Cross-up Kick", "crossup_kick", "b", 630, damage=46, frame_count=6, hit_frame=3, hit_box=(-54, -64, 22, -18), body_box=(-18, -82, 18, 4), sound=(5, 1), ground_velocity=(-3, -2), air_velocity=(-2, -4)),
        "dash_attack": _spec("Dash Attack", "dash_attack", "F, F, y", 145, damage=65, frame_count=7, hit_frame=4, hit_box=(20, -72, 86, -26), sound=(5, 2), ground_velocity=(-6, 0), air_velocity=(-3, -5)),
        "short_hop": _spec("Short Hop", "short_hop", "D, U", 142, move_type="movement", damage=0, frame_count=4, hit_frame=1, body_box=(-18, -82, 18, 4), sound=(0, 0), ground_velocity=(1.2, -5.0)),
        "quick_rise": _spec("Quick Rise", "quick_rise", "x", 5205, move_type="movement", damage=0, frame_count=5, hit_frame=1, sound=(0, 0), ground_velocity=(0, 0)),
        "air_recovery": _spec("Air Recovery", "air_recovery", "x", 5210, move_type="movement", damage=0, frame_count=5, hit_frame=1, sound=(0, 0), ground_velocity=(0, -4)),
        "guard_break": _spec("Guard Break", "guard_break", "F, z", 450, damage=95, frame_count=9, hit_frame=5, hit_box=(18, -86, 76, -26), sound=(5, 2), ground_velocity=(-8, -2), air_velocity=(-5, -6)),
        "invincible_reversal": _spec("Invincible Reversal", "invincible_reversal", "~D, DF, F, c", 1240, damage=88, frame_count=8, hit_frame=3, hit_box=(10, -96, 56, -20), sound=(5, 4), ground_velocity=(-4, -6), air_velocity=(-3, -8)),
        "charge_fireball": _spec("Charge Fireball", "charge_fireball", "~60$B, F, x", 1020, move_type="projectile", damage=60, frame_count=7, hit_frame=5, hit_box=(24, -70, 70, -34), sound=(5, 3), ground_velocity=(-5, 0)),
        "flash_kick": _spec("Flash Kick", "flash_kick", "~60$D, U, b", 1235, damage=95, frame_count=8, hit_frame=3, hit_box=(8, -108, 58, -20), sound=(5, 4), ground_velocity=(-4, -8), air_velocity=(-3, -9)),
        "power_wave": _spec("Power Wave", "power_wave", "~D, DF, F, a", 1030, move_type="projectile", damage=55, frame_count=7, hit_frame=5, hit_box=(18, -38, 86, -6), sound=(5, 3), ground_velocity=(-4, 0)),
        "beam_projectile": _spec("Beam Projectile", "beam_projectile", "~D, DF, F, z", 1040, move_type="projectile", damage=70, frame_count=8, hit_frame=4, hit_box=(20, -82, 150, -28), sound=(5, 3), ground_velocity=(-5, 0)),
        "dive_kick": _spec("Dive Kick", "dive_kick", "D, b", 1310, damage=62, frame_count=6, hit_frame=3, hit_box=(12, -36, 62, 8), body_box=(-18, -80, 18, 8), sound=(5, 2), ground_velocity=(-4, 4), air_velocity=(-3, 5)),
        "ground_bounce": _spec("Ground Bounce Strike", "ground_bounce", "D, y", 460, damage=85, frame_count=8, hit_frame=4, hit_box=(16, -80, 70, -24), sound=(5, 2), ground_velocity=(-2, -7), air_velocity=(-2, 8)),
        "wall_bounce": _spec("Wall Bounce Strike", "wall_bounce", "B, z", 470, damage=88, frame_count=8, hit_frame=4, hit_box=(18, -78, 86, -24), sound=(5, 2), ground_velocity=(-10, -2), air_velocity=(-8, -3)),
        "stance_special": _spec("Stance Special", "stance_special", "~D, DF, F, b", 3610, damage=80, frame_count=8, hit_frame=4, hit_box=(18, -76, 82, -24), sound=(5, 4), ground_velocity=(-5, -2), air_velocity=(-3, -5)),
        "install_dash_cancel": _spec("Install Dash Cancel", "install_dash_cancel", "F, F, a", 3310, move_type="movement", damage=0, frame_count=4, hit_frame=1, sound=(0, 0), ground_velocity=(7.0, 0)),
    }
    if feature_id in extra_specs:
        pkg = _pack_from_specs(feature_id, preset.name, [extra_specs[feature_id]], list(preset.beginner_notes))
        if feature_id == "invincible_reversal":
            extra = '''; Add this controller inside State 1240 for a short invulnerable startup.
[State 1240, Startup invulnerability]
type = NotHitBy
trigger1 = Time < 5
value = SCA
'''
            pkg.cns_block += _wrap(feature_id + "_startup_invuln", "Invincible Reversal startup", extra)
        if feature_id == "stance_special":
            gate = '''; MugenForge note: Add this triggerall to the generated Stance Special -1 route if you only want it in stance mode.
; triggerall = Var(21) = 1
'''
            pkg.cns_block += _wrap(feature_id + "_stance_gate_note", "Stance-only gate note", gate)
        if feature_id == "install_dash_cancel":
            gate = '''; MugenForge note: This move expects Power Install to use Var(20) as an install timer.
; Add triggerall = Var(20) > 0 to the generated -1 route after testing.
'''
            pkg.cns_block += _wrap(feature_id + "_install_gate_note", "Install cancel gate note", gate)
        return pkg
    if feature_id == "armor_tackle":
        spec = _spec("Armored Tackle", "armor_tackle", "~D, DF, F, c", 1245, damage=90, frame_count=8, hit_frame=4, hit_box=(18, -76, 90, -22), sound=(5, 4), ground_velocity=(-7, 0), air_velocity=(-4, -5))
        extra = '''; Add this controller inside State 1245 for one-hit armor behavior while testing.
[State 1245, Armor window]
type = NotHitBy
trigger1 = Time < 8
value = SCA
'''
        return _attack_with_custom_state(feature_id, preset, spec, extra)
    if feature_id == "run_forward":
        cmd = _command_block("run_forward", "F, F", 10) + _state_minus_one("run_forward", 130, "Run Forward")
        cns = _movement_fx_state(130, 130, "Run Forward", 5.0, 0, 24, afterimage=False)
        air = _simple_pose_air(130, "Run Forward", 6)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a run-forward starter. Tune to hold-forward/run-stop logic after testing.")
    if feature_id == "run_stop":
        cmd = _command_block("run_stop", "B", 1) + _state_minus_one("run_stop", 131, "Run Stop")
        cns = _movement_fx_state(131, 131, "Run Stop", 0.0, 0, 10)
        air = _simple_pose_air(131, "Run Stop", 3)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a run-stop/brake starter.")
    if feature_id == "double_jump":
        cmd = _command_block("double_jump", "U", 8) + _state_minus_one("double_jump", 143, "Double Jump", "trigger1 = ctrl\ntrigger1 = statetype = A\ntrigger1 = Var(22) = 0")
        cns = _movement_fx_state(143, 143, "Double Jump", 1.0, -7.0, 18).replace("[State 143, Velocity]", "[State 143, Mark double jump used]\ntype = VarSet\ntrigger1 = Time = 0\nv = 22\nvalue = 1\n\n[State 143, Velocity]")
        cns += '''; Put this reset idea into your landing/standing flow after testing.
[State -2, Reset double jump when grounded]
type = VarSet
trigger1 = statetype != A
v = 22
value = 0
ignorehitpause = 1

'''
        air = _simple_pose_air(143, "Double Jump", 4)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a Var(22)-gated double-jump skeleton.")
    if feature_id == "wall_jump":
        cmd = _command_block("wall_jump", "U", 8) + _state_minus_one("wall_jump", 144, "Wall Jump", "trigger1 = ctrl\ntrigger1 = statetype = A\ntrigger1 = BackEdgeBodyDist < 18 || FrontEdgeBodyDist < 18")
        cns = _movement_fx_state(144, 144, "Wall Jump", -5.0, -7.0, 18)
        air = _simple_pose_air(144, "Wall Jump", 4)
        return FeaturePackage(feature_id, preset.name, _wrap(feature_id, preset.name, cmd), _wrap(feature_id, preset.name, cns), _wrap(feature_id, preset.name, air), summary="Adds a wall-jump starter. Tune edge-distance triggers for your stage rules.")
    if feature_id == "rekka_chain":
        return _rekka_chain_package(feature_id, preset)
    if feature_id == "target_combo":
        specs = [
            _spec("Target 1", "target_1", "x", 480, damage=26, frame_count=4, hit_frame=2, hit_box=(16, -70, 48, -38), sound=(5, 0)),
            _spec("Target 2", "target_2", "y", 481, damage=42, frame_count=5, hit_frame=3, hit_box=(18, -74, 60, -30), sound=(5, 1)),
            _spec("Target 3", "target_3", "z", 482, damage=66, frame_count=7, hit_frame=4, hit_box=(22, -82, 82, -22), sound=(5, 2)),
        ]
        pkg = _pack_from_specs(feature_id, preset.name, specs)
        pkg.cns_block += _wrap(feature_id + "_chain", "Target combo chain notes", '''[State 480, Target chain 2]
type = ChangeState
trigger1 = command = "target_2"
trigger1 = AnimElem >= 3
value = 481

[State 481, Target chain 3]
type = ChangeState
trigger1 = command = "target_3"
trigger1 = AnimElem >= 3
value = 482

''')
        return pkg
    if feature_id == "auto_combo":
        specs = [
            _spec("Auto Combo 1", "auto_combo", "x", 490, damage=22, frame_count=4, hit_frame=2, hit_box=(16, -70, 48, -38), sound=(5, 0)),
            _spec("Auto Combo 2", "auto_combo", "x", 491, damage=36, frame_count=5, hit_frame=3, hit_box=(18, -74, 60, -30), sound=(5, 1)),
            _spec("Auto Combo Ender", "auto_combo", "x", 492, damage=60, frame_count=7, hit_frame=4, hit_box=(22, -82, 82, -22), sound=(5, 2)),
        ]
        pkg = _pack_from_specs(feature_id, preset.name, specs)
        pkg.cns_block += _wrap(feature_id + "_repeat_button_chain", "Auto-combo chain notes", '''; For an auto-combo, route repeated x presses through these states.
[State 490, Auto chain 2]
type = ChangeState
trigger1 = command = "auto_combo"
trigger1 = AnimElem >= 3
value = 491

[State 491, Auto chain 3]
type = ChangeState
trigger1 = command = "auto_combo"
trigger1 = AnimElem >= 3
value = 492

''')
        return pkg
    if feature_id == "air_combo_starter":
        specs = [
            _spec("Air Combo Starter", "air_combo_start", "x", 640, damage=34, frame_count=5, hit_frame=3, hit_box=(16, -70, 58, -30), body_box=(-18, -82, 18, 4), sound=(5, 0), ground_velocity=(-3, -2), air_velocity=(-2, -4)),
            _spec("Air Combo Ender", "air_combo_end", "y", 641, damage=58, frame_count=6, hit_frame=3, hit_box=(18, -72, 70, -20), body_box=(-18, -82, 18, 4), sound=(5, 1), ground_velocity=(-5, 2), air_velocity=(-3, 5)),
        ]
        return _pack_from_specs(feature_id, preset.name, specs)
    if feature_id == "launcher_air_route":
        specs = [
            _spec("Route Launcher", "route_launcher", "D, z", 650, damage=62, frame_count=7, hit_frame=3, hit_box=(12, -96, 56, -24), sound=(5, 4), ground_velocity=(-2, -9), air_velocity=(-2, -10)),
            _spec("Route Air Hit", "route_air_hit", "x", 651, damage=34, frame_count=5, hit_frame=3, hit_box=(16, -70, 58, -30), body_box=(-18, -82, 18, 4), sound=(5, 0)),
            _spec("Route Air Ender", "route_air_ender", "y", 652, damage=65, frame_count=6, hit_frame=3, hit_box=(18, -72, 70, -20), body_box=(-18, -82, 18, 4), sound=(5, 2), air_velocity=(-4, 6)),
        ]
        return _pack_from_specs(feature_id, preset.name, specs)
    if feature_id in {"boomerang_projectile", "homing_orb", "reflect_shield", "summon_clone"}:
        return _helper_projectile_package(feature_id, preset, {"boomerang_projectile":"boomerang", "homing_orb":"homing", "reflect_shield":"reflect", "summon_clone":"clone"}[feature_id])
    if feature_id in {"meter_charge", "small_heal", "voice_callouts"}:
        return _charge_or_utility_package(feature_id, preset, feature_id)
    if feature_id in {"super_beam", "cinematic_super", "command_super_grab"}:
        return _super_package(feature_id, preset, {"super_beam":"super_beam", "cinematic_super":"cinematic", "command_super_grab":"grab"}[feature_id])
    if feature_id in {"stance_switch", "ai_level_scaler", "training_shortcuts", "round_state_helper"}:
        return _stance_or_ai_package(feature_id, preset, feature_id)
    if feature_id in {"dust_fx", "hit_spark_fx", "dizzy_pose", "perfect_win_pose", "time_over_pose"}:
        return _fx_or_pose_package(feature_id, preset, {"dust_fx":"dust", "hit_spark_fx":"spark", "dizzy_pose":"dizzy", "perfect_win_pose":"perfect", "time_over_pose":"timeover"}[feature_id])
    return _BASE_BUILD_FEATURE_PACKAGE_V22(feature_id)


KIT_PRESETS.update({
    "Balanced Arcade Fighter": ["starter_basics", "common_commands", "light_punch", "medium_punch", "heavy_punch", "light_kick", "medium_kick", "heavy_kick", "crouch_punch", "crouch_kick", "sweep", "overhead_attack", "launcher", "fireball", "dragon_punch", "dash_forward", "back_dash", "roll_forward", "taunt", "intro_pose", "win_pose", "lose_pose"],
    "Rushdown Combo Fighter": ["starter_basics", "common_commands", "light_punch", "medium_punch", "heavy_punch", "dash_forward", "run_forward", "run_stop", "dash_attack", "overhead_attack", "target_combo", "auto_combo", "launcher_air_route", "rekka_chain", "slide_kick", "afterimage_dash", "super_rush", "input_debug"],
    "Projectile Zoner Fighter": ["starter_basics", "common_commands", "light_punch", "medium_punch", "crouch_kick", "fireball", "slow_fireball", "charge_fireball", "power_wave", "beam_projectile", "boomerang_projectile", "homing_orb", "reflect_shield", "teleport", "roll_back", "super_beam", "simple_ai"],
    "Grappler Fighter": ["starter_basics", "common_commands", "light_punch", "heavy_punch", "forward_punch", "armor_tackle", "dash_forward", "roll_forward", "basic_throw", "command_grab", "command_super_grab", "guard_break", "counter_attack", "taunt", "simple_ai"],
    "Anime Air Mobility Fighter": ["starter_basics", "common_commands", "air_punch", "air_kick", "air_fireball", "air_dash_forward", "double_jump", "wall_jump", "dive_kick", "crossup_kick", "air_combo_starter", "launcher_air_route", "afterimage_dash", "super_uppercut", "aura_fx"],
    "Boss / Flashy Character": ["starter_basics", "common_commands", "heavy_punch", "heavy_kick", "guard_break", "armor_tackle", "teleport", "homing_orb", "summon_clone", "striker_assist", "power_install", "super_beam", "cinematic_super", "aura_fx", "dust_fx", "hit_spark_fx"],
    "Recovery and Defense Toolkit": ["quick_rise", "air_recovery", "parry", "pushblock", "guard_cancel", "reflect_shield", "counter_attack", "roll_forward", "roll_back"],
    "FX and Presentation Toolkit": ["dust_fx", "hit_spark_fx", "aura_fx", "afterimage_dash", "voice_callouts", "intro_pose", "win_pose", "perfect_win_pose", "lose_pose", "time_over_pose", "dizzy_pose"],
    "No-Code Debug and AI Toolkit": ["debug_overlay", "input_debug", "training_shortcuts", "simple_ai", "ai_level_scaler", "round_state_helper"],
})

KIT_PRESETS["Full No-Code Creator Pack"] = list(dict.fromkeys(KIT_PRESETS.get("Full No-Code Creator Pack", []) + [
    "overhead_attack", "close_heavy", "forward_punch", "forward_kick", "hop_kick", "crossup_kick", "dash_attack", "run_forward", "run_stop", "short_hop", "double_jump", "wall_jump", "quick_rise", "air_recovery", "guard_break", "armor_tackle", "invincible_reversal", "rekka_chain", "charge_fireball", "flash_kick", "power_wave", "beam_projectile", "boomerang_projectile", "homing_orb", "reflect_shield", "dive_kick", "ground_bounce", "wall_bounce", "target_combo", "auto_combo", "air_combo_starter", "launcher_air_route", "meter_charge", "small_heal", "super_beam", "cinematic_super", "command_super_grab", "install_dash_cancel", "stance_switch", "stance_special", "summon_clone", "dust_fx", "hit_spark_fx", "voice_callouts", "training_shortcuts", "ai_level_scaler", "round_state_helper", "dizzy_pose", "perfect_win_pose", "time_over_pose",
]))


def feature_bank_stats() -> Dict[str, object]:
    categories: Dict[str, int] = {}
    difficulties: Dict[str, int] = {}
    for preset in FEATURE_PRESETS:
        categories[preset.category] = categories.get(preset.category, 0) + 1
        difficulties[preset.difficulty] = difficulties.get(preset.difficulty, 0) + 1
    return {
        "total_presets": len(FEATURE_PRESETS),
        "total_kits": len(KIT_PRESETS),
        "categories": categories,
        "difficulties": difficulties,
    }


def feature_bank_stats_text() -> str:
    stats = feature_bank_stats()
    lines = ["MugenForge Feature Bank Stats", "", f"Total no-code presets: {stats['total_presets']}", f"Total creator kits: {stats['total_kits']}", "", "Categories:"]
    for key, value in sorted(stats["categories"].items()):
        lines.append(f"- {key}: {value}")
    lines.append("\nDifficulties:")
    for key, value in sorted(stats["difficulties"].items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"

# ---------------------------------------------------------------------------
# v2.3 Fighter Factory+ no-code systems and polish bank
# ---------------------------------------------------------------------------

_V23_FEATURE_PRESETS: List[FeaturePreset] = [
    FeaturePreset("required_action_library", "Required action library", "FF+ Setup", "Beginner", "Adds a broad starter AIR library for common M.U.G.E.N required actions so beginners do not have to remember action numbers.", ("air",), tags=("setup", "air", "required")),
    FeaturePreset("complete_gethit_library", "Complete get-hit placeholder library", "FF+ Setup", "Beginner", "Adds safer placeholder get-hit, fall, recovery, lie-down, and dead actions.", ("air",), tags=("setup", "air", "gethit")),
    FeaturePreset("ffplus_air_template_bank", "FF+ animation template bank", "FF+ Visual", "Beginner", "Adds extra AIR actions for effects, projectiles, intros, win poses, and utility placeholders.", ("air",), tags=("air", "visual")),
    FeaturePreset("smart_cancel_system", "Smart cancel variable system", "FF+ Combat Systems", "Intermediate", "Adds beginner-readable cancel-window variables and examples for normals, specials, supers, and recovery control.", ("cns",), tags=("cancel", "system")),
    FeaturePreset("chain_cancel_system", "Chain cancel system", "FF+ Combat Systems", "Intermediate", "Adds light-to-medium-to-heavy chain-cancel skeleton logic.", ("cns",), tags=("cancel", "combo")),
    FeaturePreset("jump_cancel_system", "Jump cancel system", "FF+ Combat Systems", "Intermediate", "Adds jump-cancel starter variables and example triggers.", ("cns",), tags=("cancel", "jump")),
    FeaturePreset("dash_cancel_system", "Dash cancel system", "FF+ Combat Systems", "Intermediate", "Adds dash-cancel starter variables and example triggers.", ("cns",), tags=("cancel", "dash")),
    FeaturePreset("super_cancel_system", "Super cancel system", "FF+ Combat Systems", "Intermediate", "Adds meter-aware super-cancel starter logic.", ("cns",), tags=("cancel", "super")),
    FeaturePreset("ex_meter_spender", "EX meter spender", "FF+ Combat Systems", "Beginner", "Adds a reusable meter-spend snippet for EX move templates.", ("cns",), tags=("meter", "ex")),
    FeaturePreset("meter_gain_system", "Meter gain system", "FF+ Combat Systems", "Beginner", "Adds readable PowerAdd examples for attacks, blocks, whiffs, and movement rewards.", ("cns",), tags=("meter", "power")),
    FeaturePreset("combo_scaling_system", "Combo damage scaling system", "FF+ Combat Systems", "Advanced", "Adds a Var-based combo-scaling skeleton with beginner notes.", ("cns",), tags=("combo", "balance")),
    FeaturePreset("juggle_limiter", "Juggle limiter", "FF+ Combat Systems", "Intermediate", "Adds a simple juggle-count variable skeleton to help prevent infinite air combos.", ("cns",), tags=("combo", "juggle")),
    FeaturePreset("otg_limiter", "OTG limiter", "FF+ Combat Systems", "Intermediate", "Adds a starter variable for limiting off-the-ground hits.", ("cns",), tags=("combo", "otg")),
    FeaturePreset("wall_bounce_system", "Wall bounce system", "FF+ Combat Systems", "Advanced", "Adds wall-bounce starter state notes and variables.", ("cns", "air"), tags=("combo", "bounce")),
    FeaturePreset("ground_bounce_system", "Ground bounce system", "FF+ Combat Systems", "Advanced", "Adds ground-bounce starter state notes and variables.", ("cns", "air"), tags=("combo", "bounce")),
    FeaturePreset("hitstun_tuning_bank", "Hitstun tuning bank", "FF+ Balance", "Beginner", "Adds commented HitDef timing examples for light, medium, heavy, launcher, and super attacks.", ("cns",), tags=("balance", "hitdef")),
    FeaturePreset("guardstun_tuning_bank", "Guardstun tuning bank", "FF+ Balance", "Beginner", "Adds commented guard timing examples for safe and unsafe moves.", ("cns",), tags=("balance", "guard")),
    FeaturePreset("hit_pause_bank", "Hit pause / freeze bank", "FF+ Polish", "Beginner", "Adds reusable pausetime templates for different impact strengths.", ("cns",), tags=("polish", "hitpause")),
    FeaturePreset("hitspark_router", "Hitspark router", "FF+ Polish", "Beginner", "Adds a clean note bank for standardizing spark IDs across moves.", ("cns", "air"), tags=("polish", "sparks")),
    FeaturePreset("guard_spark_router", "Guard spark router", "FF+ Polish", "Beginner", "Adds guard-spark standardization notes and effect placeholders.", ("cns", "air"), tags=("polish", "sparks")),
    FeaturePreset("sound_router", "Sound event router", "FF+ Audio", "Beginner", "Adds standard PlaySnd event examples for attacks, specials, jumps, landings, hits, and supers.", ("cns",), tags=("audio", "sounds")),
    FeaturePreset("voice_router", "Voice event router", "FF+ Audio", "Beginner", "Adds separate voice-bank PlaySnd examples so voices stay organized.", ("cns",), tags=("audio", "voice")),
    FeaturePreset("step_dust_router", "Step dust FX router", "FF+ Visual", "Beginner", "Adds a reusable Explod placeholder for walk/run dust.", ("cns", "air"), tags=("fx", "dust")),
    FeaturePreset("landing_dust_router", "Landing dust FX router", "FF+ Visual", "Beginner", "Adds a reusable Explod placeholder for jump landing dust.", ("cns", "air"), tags=("fx", "dust")),
    FeaturePreset("screen_shake_router", "Screen shake router", "FF+ Visual", "Beginner", "Adds standardized EnvShake examples for impacts, landings, throws, and supers.", ("cns",), tags=("fx", "shake")),
    FeaturePreset("camera_focus_router", "Camera focus router", "FF+ Visual", "Intermediate", "Adds PosFreeze/ScreenBound examples for cinematic move starters.", ("cns",), tags=("fx", "camera")),
    FeaturePreset("palfx_impact_bank", "PalFX impact bank", "FF+ Visual", "Beginner", "Adds PalFX templates for flash, armor, parry, super, and hit-confirm polish.", ("cns",), tags=("fx", "palfx")),
    FeaturePreset("afterimage_polish_bank", "Afterimage polish bank", "FF+ Visual", "Beginner", "Adds AfterImage examples for dashes, teleports, supers, and installs.", ("cns",), tags=("fx", "afterimage")),
    FeaturePreset("training_hitbox_toggle", "Training hitbox toggle", "FF+ Training", "Intermediate", "Adds debug display logic for hitbox/CLSN review mode notes.", ("cns",), tags=("training", "debug")),
    FeaturePreset("training_input_display", "Training input display", "FF+ Training", "Beginner", "Adds an input/state clipboard overlay for testing command recognition.", ("cns",), tags=("training", "debug")),
    FeaturePreset("training_damage_readout", "Training damage readout", "FF+ Training", "Beginner", "Adds a Power/Life/HitCount style readout skeleton for testing damage feel.", ("cns",), tags=("training", "damage")),
    FeaturePreset("training_frame_data_readout", "Training frame data readout", "FF+ Training", "Intermediate", "Adds a readable frame-data clipboard skeleton for state/time/anim debugging.", ("cns",), tags=("training", "framedata")),
    FeaturePreset("training_dummy_guard_mode", "Training dummy guard mode notes", "FF+ Training", "Advanced", "Adds a safe commented starter for guard-mode testing hooks.", ("cns",), tags=("training", "guard")),
    FeaturePreset("ai_personality_router", "AI personality router", "FF+ AI", "Intermediate", "Adds variables for rushdown, zoner, grappler, and boss AI behavior routing.", ("cns",), tags=("ai", "router")),
    FeaturePreset("ai_range_router", "AI range router", "FF+ AI", "Intermediate", "Adds distance-aware CPU routing examples.", ("cns",), tags=("ai", "range")),
    FeaturePreset("ai_combo_router", "AI combo router", "FF+ AI", "Advanced", "Adds CPU combo-follow-up examples tied to state/time/distance.", ("cns",), tags=("ai", "combo")),
    FeaturePreset("ai_anti_air_router", "AI anti-air router", "FF+ AI", "Intermediate", "Adds CPU anti-air examples using P2StateType and distance.", ("cns",), tags=("ai", "anti-air")),
    FeaturePreset("ai_escape_router", "AI escape router", "FF+ AI", "Intermediate", "Adds CPU escape/defensive movement examples.", ("cns",), tags=("ai", "defense")),
    FeaturePreset("throw_tech_system", "Throw tech system", "FF+ Defense", "Advanced", "Adds a throw-break skeleton and beginner notes.", ("cmd", "cns", "air"), tags=("throw", "defense")),
    FeaturePreset("parry_reward_system", "Parry reward system", "FF+ Defense", "Advanced", "Adds parry reward variable and feedback snippets.", ("cns",), tags=("parry", "defense")),
    FeaturePreset("perfect_guard_system", "Perfect guard system", "FF+ Defense", "Advanced", "Adds perfect-guard timing notes and skeleton variables.", ("cns",), tags=("guard", "defense")),
    FeaturePreset("guard_break_meter", "Guard break meter", "FF+ Defense", "Advanced", "Adds a guard-crush variable skeleton.", ("cns",), tags=("guard", "meter")),
    FeaturePreset("stun_meter_system", "Stun meter system", "FF+ Defense", "Advanced", "Adds a stun/dizzy variable skeleton.", ("cns", "air"), tags=("stun", "dizzy")),
    FeaturePreset("burst_escape_system", "Burst escape system", "FF+ Defense", "Advanced", "Adds a burst escape command/state starter.", ("cmd", "cns", "air"), tags=("burst", "defense")),
    FeaturePreset("roman_cancel_system", "Roman/spark cancel system", "FF+ Combat Systems", "Advanced", "Adds a meter-spending cancel skeleton inspired by modern cancel mechanics.", ("cmd", "cns", "air"), tags=("cancel", "meter")),
    FeaturePreset("clash_system", "Attack clash system", "FF+ Combat Systems", "Advanced", "Adds clash-detection notes and state placeholders.", ("cns", "air"), tags=("clash", "combat")),
    FeaturePreset("armor_system", "Armor / super armor system", "FF+ Defense", "Advanced", "Adds reusable armor-window NotHitBy/HitOverride examples.", ("cns",), tags=("armor", "defense")),
    FeaturePreset("invuln_startup_bank", "Invulnerability startup bank", "FF+ Defense", "Beginner", "Adds NotHitBy examples for reversals, rolls, and teleports.", ("cns",), tags=("invuln", "defense")),
    FeaturePreset("projectile_priority_bank", "Projectile priority bank", "FF+ Projectiles", "Intermediate", "Adds projectile priority/velocity/damage tuning examples.", ("cns",), tags=("projectile", "balance")),
    FeaturePreset("projectile_reflect_router", "Projectile reflect router", "FF+ Projectiles", "Advanced", "Adds reflect/absorb hook notes for projectile-heavy characters.", ("cns",), tags=("projectile", "reflect")),
    FeaturePreset("assist_cooldown_system", "Assist cooldown system", "FF+ Helpers", "Advanced", "Adds variables for striker/helper cooldowns.", ("cns",), tags=("helper", "assist")),
    FeaturePreset("tag_assist_placeholder", "Tag / assist placeholder", "FF+ Helpers", "Advanced", "Adds placeholder states for assist entry/exit routing.", ("cmd", "cns", "air"), tags=("helper", "tag")),
    FeaturePreset("install_timer_hud", "Install timer HUD debug", "FF+ Supers", "Advanced", "Adds timer-variable and clipboard feedback for install supers.", ("cns",), tags=("super", "install")),
    FeaturePreset("boss_phase_router", "Boss phase router", "FF+ AI", "Advanced", "Adds life-threshold phase variables for boss prototypes.", ("cns",), tags=("boss", "ai")),
    FeaturePreset("round_intro_outro_director", "Round intro/outro director", "FF+ Round Flow", "Beginner", "Adds intro, win, lose, and quote routing notes.", ("cns", "air"), tags=("round", "pose")),
    FeaturePreset("win_quote_bank", "Win quote bank", "FF+ Round Flow", "Beginner", "Writes a starter win quote/documentation bank.", tuple(), tags=("round", "docs")),
    FeaturePreset("move_unlock_flags", "Move unlock flag notes", "FF+ Tools", "Advanced", "Adds commented variables for unlockable/boss-only move prototypes.", ("cns",), tags=("tools", "vars")),
    FeaturePreset("color_palette_manager_docs", "Palette manager docs", "FF+ Docs", "Beginner", "Writes a beginner guide for ACT files, palette order, and color separation planning.", tuple(), tags=("palette", "docs")),
    FeaturePreset("sprite_axis_audit_docs", "Sprite axis audit docs", "FF+ Docs", "Beginner", "Writes a worksheet for checking sprite axes, feet placement, and visual jitter.", tuple(), tags=("sprite", "docs")),
    FeaturePreset("release_package_audit_docs", "Release package audit docs", "FF+ Docs", "Beginner", "Writes a release checklist focused on what beginners forget.", tuple(), tags=("release", "docs")),
    FeaturePreset("character_bible_docs", "Character bible docs", "FF+ Docs", "Beginner", "Writes a character bible template for style, moves, animation needs, and balance notes.", tuple(), tags=("docs", "planning")),
    FeaturePreset("combo_recipe_docs", "Combo recipe docs", "FF+ Docs", "Beginner", "Writes a combo recipe worksheet for beginner playtesting.", tuple(), tags=("docs", "combo")),
    FeaturePreset("balance_worksheet_docs", "Balance worksheet docs", "FF+ Docs", "Beginner", "Writes a tuning worksheet for damage, speed, recovery, and meter.", tuple(), tags=("docs", "balance")),
    FeaturePreset("test_plan_docs", "Testing plan docs", "FF+ Docs", "Beginner", "Writes a plain-language test plan for loading, commands, hitboxes, sounds, palettes, and release packaging.", tuple(), tags=("docs", "testing")),
    FeaturePreset("accessibility_notes_docs", "Accessibility notes docs", "FF+ Docs", "Beginner", "Writes notes for readable commands, visual clarity, and sound/flash restraint.", tuple(), tags=("docs", "accessibility")),
    FeaturePreset("readme_generator_docs", "README generator docs", "FF+ Docs", "Beginner", "Writes a release README starter that beginners can edit.", tuple(), tags=("docs", "readme")),
    FeaturePreset("credits_license_docs", "Credits/license docs", "FF+ Docs", "Beginner", "Writes a credits and permissions template.", tuple(), tags=("docs", "credits")),
]

_seen_feature_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _V23_FEATURE_PRESETS:
    if _preset.feature_id not in _seen_feature_ids:
        FEATURE_PRESETS.append(_preset)
        _seen_feature_ids.add(_preset.feature_id)

_V22_BUILD_FEATURE_PACKAGE = build_feature_package


def _v23_doc_text(title: str, feature_id: str) -> str:
    return f"""# {title}

Generated by MugenForge Studio FF+.

This file exists so the creator can make decisions without editing M.U.G.E.N code by hand.

## What to fill in

- What should this feature look/sound like?
- Which animation action numbers does it use?
- Which sound group/index does it use?
- Is the move safe, unsafe, armored, projectile-based, or throw-based?
- What should be checked in Animation Player and CLSN Editor?

## Beginner rule

Do the fun part here: naming, feel, visuals, sound, timing notes. Let Feature Bank / Move Wizard write the raw CMD, CNS, and AIR blocks.

Feature Bank ID: `{feature_id}`
"""


def _v23_docs_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    filename = {
        "color_palette_manager_docs": "docs/PALETTE_MANAGER_GUIDE.md",
        "sprite_axis_audit_docs": "docs/SPRITE_AXIS_AUDIT.md",
        "release_package_audit_docs": "docs/RELEASE_PACKAGE_AUDIT.md",
        "character_bible_docs": "docs/CHARACTER_BIBLE.md",
        "combo_recipe_docs": "testing/combo_trials/COMBO_RECIPES.md",
        "balance_worksheet_docs": "docs/BALANCE_WORKSHEET.md",
        "test_plan_docs": "testing/TEST_PLAN.md",
        "accessibility_notes_docs": "docs/ACCESSIBILITY_NOTES.md",
        "readme_generator_docs": "README_RELEASE_TEMPLATE.md",
        "credits_license_docs": "CREDITS_AND_PERMISSIONS.md",
        "win_quote_bank": "docs/WIN_QUOTES.md",
    }.get(feature_id, f"docs/{feature_id.upper()}.md")
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        extra_files={filename: _v23_doc_text(preset.name, feature_id)},
        summary=f"Writes {preset.name} planning/documentation file. No code editing required.",
        notes=["This is a planning/doc preset, not a combat code block."],
    )


def _v23_required_air(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    if feature_id == "required_action_library":
        action_ids = [0, 5, 10, 11, 12, 20, 21, 40, 41, 42, 47, 100, 105, 120, 130, 140, 150, 170, 180, 190, 195]
        air = "".join(_simple_pose_air(n, COMMON_ANIMS.get(n, f"Action {n}"), 4 if n < 5000 else 5) for n in action_ids)
        summary = "Adds beginner-safe placeholders for many common required/round-flow actions. Replace art later."
    elif feature_id == "complete_gethit_library":
        action_ids = [5000, 5010, 5020, 5030, 5050, 5060, 5070, 5080, 5100, 5110, 5150]
        air = "".join(_simple_pose_air(n, COMMON_ANIMS.get(n, f"Get-hit {n}"), 5) for n in action_ids)
        summary = "Adds placeholder get-hit/fall/recovery/dead action library."
    else:
        action_ids = [7000, 7001, 7010, 7011, 7020, 7021, 7030, 7040, 7050, 7060, 7070, 7080]
        labels = ["Small Hitspark", "Big Hitspark", "Guard Spark", "Super Spark", "Dust Puff", "Landing Dust", "Slash FX", "Aura Loop", "Projectile Core", "Throw FX", "Cancel Spark", "Clash Spark"]
        air = "".join(_simple_pose_air(n, label, 4) for n, label in zip(action_ids, labels))
        summary = "Adds visual template actions for sparks, dust, projectile, aura, throw, cancel, and clash effects."
    return FeaturePackage(feature_id, preset.name, air_block=_wrap(feature_id, preset.name, air), summary=summary)


def _v23_state2_block(feature_id: str, title: str, var_no: int, lines: str) -> str:
    return f"""; MugenForge FF+ {title}
; This block is intentionally readable and conservative.
; Tune it after in-game testing.
[State -2, FF+ {title} init]
type = VarSet
trigger1 = RoundState < 2
v = {var_no}
value = 0
ignorehitpause = 1

{lines.rstrip()}

"""


def _v23_system_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    title = preset.name
    var_seed = 50 + (sum(ord(ch) for ch in feature_id) % 45)
    cmd = ""
    air = ""
    notes: List[str] = ["Generated as a beginner-readable system skeleton. It is safe to install, but final tuning still needs in-game testing."]

    if feature_id in {"throw_tech_system", "burst_escape_system", "roman_cancel_system", "tag_assist_placeholder"}:
        command = {
            "throw_tech_system": "x+y",
            "burst_escape_system": "x+y+z",
            "roman_cancel_system": "y+z",
            "tag_assist_placeholder": "a+b",
        }[feature_id]
        state_no = {
            "throw_tech_system": 6400,
            "burst_escape_system": 6410,
            "roman_cancel_system": 6420,
            "tag_assist_placeholder": 6430,
        }[feature_id]
        cmd = _command_block(feature_id, command, 8) + _state_minus_one(feature_id, state_no, title)
        cns = f"""; MugenForge FF+ {title}
[Statedef {state_no}]
type = S
movetype = I
physics = S
anim = {state_no}
ctrl = 0
sprpriority = 5

[State {state_no}, spend/read variables]
type = VarAdd
trigger1 = Time = 0
v = {var_seed}
value = 1

[State {state_no}, visual feedback]
type = PalFX
trigger1 = Time = 0
time = 12
add = 60,60,90
mul = 220,220,255

[State {state_no}, end]
type = ChangeState
trigger1 = Time >= 18
value = 0
ctrl = 1

"""
        air = _simple_pose_air(state_no, title, 5)
        return FeaturePackage(feature_id, title, _wrap(feature_id, title, cmd), _wrap(feature_id, title, cns), _wrap(feature_id, title, air), summary=f"Adds no-code starter command/state for {title}.", notes=notes)

    if feature_id in {"wall_bounce_system", "ground_bounce_system", "stun_meter_system", "clash_system", "round_intro_outro_director"}:
        state_no = {
            "wall_bounce_system": 6500,
            "ground_bounce_system": 6510,
            "stun_meter_system": 6520,
            "clash_system": 6530,
            "round_intro_outro_director": 6540,
        }[feature_id]
        cns = f"""; MugenForge FF+ {title}
; Use this as a named destination/state idea. Wire specific moves into it after testing.
[Statedef {state_no}]
type = S
movetype = I
physics = N
anim = {state_no}
ctrl = 0
sprpriority = 4

[State {state_no}, freeze/control]
type = VelSet
trigger1 = Time = 0
x = 0
y = 0

[State {state_no}, feedback]
type = EnvShake
trigger1 = Time = 0
time = 10
freq = 90
ampl = -3
ignorehitpause = 1

[State {state_no}, end]
type = ChangeState
trigger1 = Time >= 20
value = 0
ctrl = 1

"""
        air = _simple_pose_air(state_no, title, 5)
        return FeaturePackage(feature_id, title, cns_block=_wrap(feature_id, title, cns), air_block=_wrap(feature_id, title, air), summary=f"Adds placeholder state/action for {title}.", notes=notes)

    special_lines = {
        "smart_cancel_system": """[State -2, FF+ mark cancel window while attacking]\ntype = VarSet\ntriggerall = MoveType = A\ntrigger1 = AnimElemNo(0) >= 2\nv = 50\nvalue = 1\nignorehitpause = 1\n\n[State -2, FF+ clear cancel window]\ntype = VarSet\ntrigger1 = MoveType != A\nv = 50\nvalue = 0\nignorehitpause = 1""",
        "chain_cancel_system": """[State -2, FF+ chain route note]\ntype = DisplayToClipboard\ntrigger1 = Var(50) = 1\ntext = \"Chain window open: light -> medium -> heavy\"\nignorehitpause = 1""",
        "jump_cancel_system": """[State -2, FF+ jump cancel marker]\ntype = VarSet\ntrigger1 = MoveHit\ntrigger1 = StateType != A\nv = 51\nvalue = 1\nignorehitpause = 1""",
        "dash_cancel_system": """[State -2, FF+ dash cancel marker]\ntype = VarSet\ntrigger1 = MoveContact\ntrigger1 = Power >= 250\nv = 52\nvalue = 1\nignorehitpause = 1""",
        "super_cancel_system": """[State -2, FF+ super cancel marker]\ntype = VarSet\ntrigger1 = MoveContact\ntrigger1 = Power >= 1000\nv = 53\nvalue = 1\nignorehitpause = 1""",
        "ex_meter_spender": """[State -2, FF+ EX meter note]\ntype = DisplayToClipboard\ntrigger1 = Power >= 500\ntrigger1 = 0 ; change to your EX move trigger\ntext = \"EX ready: spend 500 power in the move state\"\nignorehitpause = 1""",
        "meter_gain_system": """[State -2, FF+ tiny meter reward example]\ntype = PowerAdd\ntrigger1 = MoveContact\ntrigger1 = Time % 12 = 0\nvalue = 5\nignorehitpause = 1""",
        "combo_scaling_system": """[State -2, FF+ combo scaling variable]\ntype = VarSet\ntrigger1 = NumEnemy > 0\ntrigger1 = P2MoveType = H\nv = 54\nvalue = HitCount\nignorehitpause = 1""",
        "juggle_limiter": """[State -2, FF+ juggle count idea]\ntype = VarAdd\ntrigger1 = MoveHit\ntrigger1 = P2StateType = A\nv = 55\nvalue = 1\nignorehitpause = 1""",
        "otg_limiter": """[State -2, FF+ OTG count idea]\ntype = VarAdd\ntrigger1 = MoveHit\ntrigger1 = P2StateType = L\nv = 56\nvalue = 1\nignorehitpause = 1""",
        "hit_pause_bank": """; HitDef pausetime examples:\n; light pausetime = 4,6\n; medium pausetime = 6,8\n; heavy pausetime = 9,12\n; super pausetime = 12,18\n[State -2, FF+ hitpause note]\ntype = Null\ntrigger1 = 1""",
        "hitstun_tuning_bank": """; HitDef hittime examples:\n; light ground.hittime = 10\n; medium ground.hittime = 14\n; heavy ground.hittime = 18\n; launcher air.hittime = 24\n[State -2, FF+ hitstun note]\ntype = Null\ntrigger1 = 1""",
        "guardstun_tuning_bank": """; HitDef guardtime examples:\n; unsafe light guard.hittime = 8\n; safe special guard.hittime = 16\n; plus-frame super guard.hittime = 24\n[State -2, FF+ guardstun note]\ntype = Null\ntrigger1 = 1""",
        "training_input_display": """[State -2, FF+ input display]\ntype = DisplayToClipboard\ntrigger1 = 1\ntext = \"cmd/debug state=%d anim=%d time=%d ctrl=%d power=%d\"\nparams = stateno, anim, time, ctrl, power\nignorehitpause = 1""",
        "training_damage_readout": """[State -2, FF+ damage readout]\ntype = AppendToClipboard\ntrigger1 = 1\ntext = \"\\nlife=%d p2life=%d hitcount=%d\"\nparams = life, enemynear,life, hitcount\nignorehitpause = 1""",
        "training_frame_data_readout": """[State -2, FF+ frame data readout]\ntype = AppendToClipboard\ntrigger1 = 1\ntext = \"\\nframe data: stateno=%d time=%d animelem=%d movetype=%s\"\nparams = stateno, time, animelemno(0), movetype\nignorehitpause = 1""",
        "training_hitbox_toggle": """[State -2, FF+ CLSN note]\ntype = DisplayToClipboard\ntrigger1 = 0 ; set to 1 while tuning CLSN in-game\ntext = \"Use MugenForge CLSN Editor for visual hitbox edits, then save AIR with backup.\"\nignorehitpause = 1""",
        "training_dummy_guard_mode": """[State -2, FF+ training dummy guard notes]\ntype = Null\ntrigger1 = 1\n; Add engine-specific dummy behavior here if your M.U.G.E.N build supports it.""",
        "ai_personality_router": """[State -2, FF+ AI personality]\ntype = VarSet\ntrigger1 = AILevel > 0\ntrigger1 = RoundState = 2\nv = 60\nvalue = 1 ; 1=rushdown, 2=zoner, 3=grappler, 4=boss\nignorehitpause = 1""",
        "ai_range_router": """[State -2, FF+ AI range idea]\ntype = ChangeState\ntriggerall = AILevel > 0\ntriggerall = ctrl\ntrigger1 = P2BodyDist X > 120\ntrigger1 = Random < 20\nvalue = 1000""",
        "ai_combo_router": """[State -2, FF+ AI combo follow-up idea]\ntype = ChangeState\ntriggerall = AILevel > 0\ntrigger1 = MoveHit\ntrigger1 = Random < 35\nvalue = 210""",
        "ai_anti_air_router": """[State -2, FF+ AI anti-air idea]\ntype = ChangeState\ntriggerall = AILevel > 0\ntriggerall = ctrl\ntrigger1 = P2StateType = A\ntrigger1 = P2BodyDist X < 70\nvalue = 1100""",
        "ai_escape_router": """[State -2, FF+ AI escape idea]\ntype = ChangeState\ntriggerall = AILevel > 0\ntriggerall = ctrl\ntrigger1 = P2BodyDist X < 30\ntrigger1 = Random < 25\nvalue = 105""",
        "parry_reward_system": """[State -2, FF+ parry reward idea]\ntype = PowerAdd\ntrigger1 = Var(61) = 1\nvalue = 100\nignorehitpause = 1""",
        "perfect_guard_system": """[State -2, FF+ perfect guard marker]\ntype = VarSet\ntrigger1 = StateType != A\ntrigger1 = MoveType = H\ntrigger1 = Time < 4\nv = 62\nvalue = 1\nignorehitpause = 1""",
        "guard_break_meter": """[State -2, FF+ guard meter idea]\ntype = VarAdd\ntrigger1 = MoveType = H\ntrigger1 = StateType != A\nv = 63\nvalue = 1\nignorehitpause = 1""",
        "armor_system": """[State -2, FF+ armor window example]\ntype = NotHitBy\ntrigger1 = Var(64) > 0\nvalue = SCA\nignorehitpause = 1""",
        "invuln_startup_bank": """; Copy into a state that needs invulnerable startup.\n[State -2, FF+ invuln startup note]\ntype = NotHitBy\ntrigger1 = 0 ; change to Time < N inside target state\nvalue = SCA\nignorehitpause = 1""",
        "projectile_priority_bank": """; Projectile tuning examples:\n; projpriority = 1 light, 3 medium, 5 super\n; velocity should match recovery so zoners are fair.\n[State -2, FF+ projectile priority note]\ntype = Null\ntrigger1 = 1""",
        "projectile_reflect_router": """[State -2, FF+ reflect hook note]\ntype = Null\ntrigger1 = 1\n; Wire reflect/absorb moves here after testing ReversalDef behavior.""",
        "assist_cooldown_system": """[State -2, FF+ assist cooldown]\ntype = VarAdd\ntrigger1 = Var(70) > 0\nv = 70\nvalue = -1\nignorehitpause = 1""",
        "install_timer_hud": """[State -2, FF+ install timer HUD]\ntype = AppendToClipboard\ntrigger1 = Var(71) > 0\ntext = \"\\nInstall timer=%d\"\nparams = Var(71)\nignorehitpause = 1""",
        "boss_phase_router": """[State -2, FF+ boss phase]\ntype = VarSet\ntrigger1 = Life < LifeMax / 2\nv = 72\nvalue = 2\nignorehitpause = 1""",
        "move_unlock_flags": """[State -2, FF+ move unlock flags]\ntype = VarSet\ntrigger1 = RoundNo >= 1\nv = 73\nvalue = 1\nignorehitpause = 1""",
        "screen_shake_router": """[State -2, FF+ screen shake example]\ntype = EnvShake\ntrigger1 = 0 ; copy this into big-impact states\ntime = 12\nfreq = 90\nampl = -4\nignorehitpause = 1""",
        "camera_focus_router": """[State -2, FF+ cinematic camera note]\ntype = ScreenBound\ntrigger1 = 0 ; copy into cinematic states\nvalue = 0\nmovecamera = 0,0\nignorehitpause = 1""",
        "palfx_impact_bank": """[State -2, FF+ PalFX impact example]\ntype = PalFX\ntrigger1 = 0 ; copy into impact states\ntime = 8\nadd = 80,80,80\nmul = 256,256,256\nignorehitpause = 1""",
        "afterimage_polish_bank": """[State -2, FF+ AfterImage example]\ntype = AfterImage\ntrigger1 = 0 ; copy into dash/super states\ntime = 16\nlength = 8\npalcontrast = 140,140,220\nignorehitpause = 1""",
        "sound_router": """[State -2, FF+ sound router notes]\ntype = Null\ntrigger1 = 1\n; Suggested groups: 0 system, 5 attacks, 6 specials, 7 supers, 10 voice.""",
        "voice_router": """[State -2, FF+ voice router notes]\ntype = Null\ntrigger1 = 1\n; Use PlaySnd group 10 for voice so it stays separate from hits and movement.""",
    }
    if feature_id in {"hitspark_router", "guard_spark_router", "step_dust_router", "landing_dust_router"}:
        action_map = {
            "hitspark_router": (7000, "Hitspark Router", "sparkxy = -10,-60"),
            "guard_spark_router": (7010, "Guard Spark Router", "sparkxy = -8,-58"),
            "step_dust_router": (7020, "Step Dust Router", "pos = 0,0"),
            "landing_dust_router": (7021, "Landing Dust Router", "pos = 0,0"),
        }
        anim_no, label, pos_line = action_map[feature_id]
        cns = f"""; MugenForge FF+ {label}
[State -2, {label} note]
type = Null
trigger1 = 1
; Copy this Explod into the states that need it.
; type = Explod
; anim = {anim_no}
; {pos_line}
; postype = p1
; sprpriority = 5
; ownpal = 1
"""
        air = _simple_pose_air(anim_no, label, 4)
        return FeaturePackage(feature_id, title, cns_block=_wrap(feature_id, title, cns), air_block=_wrap(feature_id, title, air), summary=f"Adds {label} placeholder action and routing notes.", notes=notes)
    lines = special_lines.get(feature_id)
    if lines is None:
        lines = f"""[State -2, FF+ {title} note]\ntype = Null\ntrigger1 = 1\n; Starter hook for {title}. Use this as the central code bank location."""
    cns = _v23_state2_block(feature_id, title, var_seed, lines)
    return FeaturePackage(feature_id, title, cns_block=_wrap(feature_id, title, cns), summary=f"Adds FF+ no-code system skeleton: {title}.", notes=notes)


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _V23_FEATURE_PRESETS}:
        return _V22_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id in {"required_action_library", "complete_gethit_library", "ffplus_air_template_bank"}:
        return _v23_required_air(feature_id, preset)
    if feature_id.endswith("_docs") or feature_id in {"win_quote_bank"}:
        return _v23_docs_package(feature_id, preset)
    return _v23_system_package(feature_id, preset)


KIT_PRESETS.update({
    "FF+ Fighter Factory-Style Essentials": [
        "required_action_library", "complete_gethit_library", "ffplus_air_template_bank", "smart_cancel_system",
        "meter_gain_system", "combo_scaling_system", "juggle_limiter", "hit_pause_bank", "hitspark_router",
        "sound_router", "training_input_display", "training_frame_data_readout", "character_bible_docs",
        "combo_recipe_docs", "balance_worksheet_docs", "test_plan_docs", "release_package_audit_docs",
    ],
    "FF+ Visual Polish Kit": [
        "hitspark_router", "guard_spark_router", "step_dust_router", "landing_dust_router", "screen_shake_router",
        "camera_focus_router", "palfx_impact_bank", "afterimage_polish_bank", "sprite_axis_audit_docs",
        "color_palette_manager_docs",
    ],
    "FF+ Combat Systems Kit": [
        "smart_cancel_system", "chain_cancel_system", "jump_cancel_system", "dash_cancel_system", "super_cancel_system",
        "roman_cancel_system", "ex_meter_spender", "combo_scaling_system", "juggle_limiter", "otg_limiter",
        "wall_bounce_system", "ground_bounce_system", "hitstun_tuning_bank", "guardstun_tuning_bank",
    ],
    "FF+ Training and Debug Kit": [
        "training_input_display", "training_damage_readout", "training_frame_data_readout", "training_hitbox_toggle",
        "training_dummy_guard_mode", "input_debug", "debug_overlay",
    ],
    "FF+ AI and Boss Kit": [
        "ai_personality_router", "ai_range_router", "ai_combo_router", "ai_anti_air_router", "ai_escape_router",
        "boss_phase_router", "simple_ai",
    ],
})

KIT_PRESETS["Full No-Code Creator Pack"] = list(dict.fromkeys(KIT_PRESETS.get("Full No-Code Creator Pack", []) + KIT_PRESETS["FF+ Fighter Factory-Style Essentials"] + KIT_PRESETS["FF+ Visual Polish Kit"]))

# ---------------------------------------------------------------------------
# v2.5 Factory Max / Better-than-FF no-code expansion
# ---------------------------------------------------------------------------

_V25_FEATURE_PRESETS: List[FeaturePreset] = [
    # Fighter Factory-style editor parity docs/tools
    FeaturePreset("max_sprite_organizer_docs", "Sprite organizer workflow", "Factory Max Editor Parity", "Beginner", "Plain-English sprite organizer workflow for group/image naming, axis notes, collision-safe imports, and contact sheets.", ("docs",), tags=("sprites", "organizer", "docs")),
    FeaturePreset("max_image_editor_macros_docs", "Image editor macro bank", "Factory Max Editor Parity", "Beginner", "Documents one-click image macros: trim, pad, transparency key, mirror, outline, shadow, scale, and palette reduction.", ("docs",), tags=("image", "editor", "docs")),
    FeaturePreset("max_offset_viewer_docs", "Offset viewer / axis checklist", "Factory Max Editor Parity", "Beginner", "Axis checklist to keep feet, projectiles, sparks, and throw points lined up.", ("docs",), tags=("axis", "offset", "docs")),
    FeaturePreset("max_throw_creator_docs", "Throw creator checklist", "Factory Max Editor Parity", "Intermediate", "No-code throw planning sheet for attacker/victim states, bind timing, release timing, and safety checks.", ("docs",), tags=("throw", "docs")),
    FeaturePreset("max_bg_stage_editor_docs", "BG/stage editor checklist", "Factory Max Editor Parity", "Beginner", "Stage and background checklist for bounds, zoffset, deltas, parallax notes, and release tests.", ("docs",), tags=("stage", "docs")),
    FeaturePreset("max_storyboard_editor_docs", "Storyboard editor checklist", "Factory Max Editor Parity", "Beginner", "Intro/ending storyboard planning sheet with scene timing and asset list.", ("docs",), tags=("storyboard", "docs")),
    FeaturePreset("max_autocomplete_bank_docs", "Auto-completion bank docs", "Factory Max Editor Parity", "Beginner", "Offline syntax/snippet bank explaining common controllers and triggers.", ("docs",), tags=("codesense", "docs")),
    FeaturePreset("max_import_resolver_docs", "Project import resolver", "Factory Max Editor Parity", "Intermediate", "Safe import/collision-resolution checklist for borrowing assets from your own projects without overwriting current files.", ("docs",), tags=("import", "docs")),
    FeaturePreset("max_palette_link_audit_docs", "Palette link audit", "Factory Max Editor Parity", "Intermediate", "Palette audit guide for SFF v1/v2 shared palettes, ACT files, transparency index, and alt palettes.", ("docs",), tags=("palette", "docs")),
    FeaturePreset("max_onion_skin_docs", "Onion-skin animation notes", "Factory Max Editor Parity", "Beginner", "Animation timing sheet for onion-skin review, anticipation, active frames, recovery, and smear frames.", ("docs",), tags=("animation", "docs")),
    FeaturePreset("max_frame_interpolation_docs", "Frame interpolation checklist", "Factory Max Editor Parity", "Intermediate", "Planning sheet for frame interpolation/fake in-betweens and timing variations.", ("docs",), tags=("animation", "docs")),
    FeaturePreset("max_sound_viewer_docs", "Sound viewer / cue bank", "Factory Max Editor Parity", "Beginner", "Sound cue and group/index planning sheet so users can replace silent placeholders without coding.", ("docs",), tags=("sound", "docs")),
    FeaturePreset("max_code_history_safety_docs", "Edit history / backup safety", "Factory Max Editor Parity", "Beginner", "Backup/restore workflow for generated code blocks, binary assets, and release packaging.", ("docs",), tags=("safety", "docs")),
    FeaturePreset("max_debugger_docs", "Debugger test loop guide", "Factory Max Editor Parity", "Beginner", "Plain-English test loop guide for launch, debug overlay, frame data readouts, and quick test steps.", ("docs",), tags=("debug", "docs")),

    # No-code combat lab systems
    FeaturePreset("max_universal_chain_router", "Universal chain router", "Factory Max Combat Lab", "Intermediate", "State -2 chain-router skeleton for light/medium/heavy normal routing.", ("cns",), tags=("chain", "system")),
    FeaturePreset("max_air_chain_router", "Air chain router", "Factory Max Combat Lab", "Intermediate", "State -2 air-chain routing notes for anime-style jump chains.", ("cns",), tags=("air", "chain")),
    FeaturePreset("max_cancel_window_hud", "Cancel-window HUD", "Factory Max Combat Lab", "Intermediate", "Debug overlay showing cancel window variables and current state/time.", ("cns",), tags=("debug", "cancel")),
    FeaturePreset("max_meter_rules_router", "Meter rules router", "Factory Max Combat Lab", "Intermediate", "Central meter gain/spend skeleton for specials, EX, supers, and install timers.", ("cns",), tags=("meter", "system")),
    FeaturePreset("max_ex_move_router", "EX move router", "Factory Max Combat Lab", "Intermediate", "EX move spend/refund skeleton and helper comments.", ("cns",), tags=("ex", "meter")),
    FeaturePreset("max_super_freeze_router", "Super-freeze router", "Factory Max Combat Lab", "Intermediate", "SuperPause/screen-freeze starter hook for cinematic supers.", ("cns", "air"), tags=("super", "cinematic")),
    FeaturePreset("max_round_director_router", "Round director", "Factory Max Combat Lab", "Intermediate", "Round-start/round-end routing skeleton for intros, win poses, lose poses, and boss phases.", ("cns",), tags=("round", "system")),
    FeaturePreset("max_proration_router", "Damage proration router", "Factory Max Combat Lab", "Advanced", "Beginner-readable combo scaling and damage-proration skeleton.", ("cns",), tags=("balance", "combo")),
    FeaturePreset("max_pushback_router", "Pushback tuning router", "Factory Max Combat Lab", "Intermediate", "Central notes for pushback/vel tuning and safe/unsafe move review.", ("cns",), tags=("balance", "pushback")),
    FeaturePreset("max_corner_escape_router", "Corner escape router", "Factory Max Combat Lab", "Intermediate", "Skeleton for corner escape, roll, burst, or guard cancel logic.", ("cns",), tags=("defense", "corner")),
    FeaturePreset("max_throw_tech_router", "Throw-tech router", "Factory Max Combat Lab", "Advanced", "Throw-tech planning skeleton with command/window notes.", ("cmd", "cns"), tags=("throw", "defense")),
    FeaturePreset("max_guard_crush_router", "Guard-crush router", "Factory Max Combat Lab", "Advanced", "Guard meter/crush skeleton with variables and reset notes.", ("cns",), tags=("guard", "system")),
    FeaturePreset("max_airdash_rules_router", "Air-dash rules router", "Factory Max Combat Lab", "Intermediate", "Variable-based air-dash count/cooldown/reset skeleton.", ("cns",), tags=("movement", "air")),
    FeaturePreset("max_wallbounce_router", "Wall-bounce router", "Factory Max Combat Lab", "Advanced", "Wall-bounce limiter/tuning skeleton.", ("cns",), tags=("combo", "wallbounce")),
    FeaturePreset("max_groundbounce_router", "Ground-bounce router", "Factory Max Combat Lab", "Advanced", "Ground-bounce limiter/tuning skeleton.", ("cns",), tags=("combo", "groundbounce")),
    FeaturePreset("max_otg_rules_router", "OTG rules router", "Factory Max Combat Lab", "Advanced", "OTG counter/rule skeleton.", ("cns",), tags=("combo", "otg")),
    FeaturePreset("max_projectile_ecosystem_router", "Projectile ecosystem router", "Factory Max Combat Lab", "Advanced", "Projectile durability/reflect/absorb planning skeleton.", ("cns",), tags=("projectile", "system")),
    FeaturePreset("max_assist_rules_router", "Assist rules router", "Factory Max Combat Lab", "Advanced", "Assist cooldown, call, and screen-presence skeleton.", ("cmd", "cns"), tags=("assist", "helper")),
    FeaturePreset("max_tag_rules_router", "Tag/assist prototype router", "Factory Max Combat Lab", "Advanced", "Experimental tag-system planning skeleton for full-game creators.", ("cns",), tags=("tag", "system")),

    # No-code move additions
    FeaturePreset("max_target_combo", "Target combo starter", "Factory Max Moves", "Beginner", "Two-button target combo starter with command/state/AIR scaffolding.", ("cmd", "cns", "air"), tags=("combo", "normal")),
    FeaturePreset("max_chain_uppercut", "Chain uppercut", "Factory Max Moves", "Intermediate", "Combo-route uppercut starter with vertical hitbox.", ("cmd", "cns", "air"), tags=("launcher", "normal")),
    FeaturePreset("max_rekka_finish_low", "Rekka finish low", "Factory Max Moves", "Intermediate", "Low rekka finisher starter.", ("cmd", "cns", "air"), tags=("rekka", "low")),
    FeaturePreset("max_rekka_finish_overhead", "Rekka finish overhead", "Factory Max Moves", "Intermediate", "Overhead rekka finisher starter.", ("cmd", "cns", "air"), tags=("rekka", "overhead")),
    FeaturePreset("max_flame_uppercut", "Flame uppercut", "Factory Max Moves", "Intermediate", "Flashy anti-air special starter.", ("cmd", "cns", "air"), tags=("special", "anti-air")),
    FeaturePreset("max_ice_projectile", "Ice projectile", "Factory Max Moves", "Intermediate", "Slower control projectile starter.", ("cmd", "cns", "air"), tags=("projectile", "special")),
    FeaturePreset("max_lightning_dash", "Lightning dash", "Factory Max Moves", "Intermediate", "Fast movement attack starter with FX notes.", ("cmd", "cns", "air"), tags=("movement", "special")),
    FeaturePreset("max_ground_pound", "Ground pound", "Factory Max Moves", "Intermediate", "Short-range quake-style attack starter.", ("cmd", "cns", "air"), tags=("special", "ground")),
    FeaturePreset("max_command_counter", "Command counter", "Factory Max Moves", "Advanced", "Command-input counter attack starter.", ("cmd", "cns", "air"), tags=("counter", "defense")),
    FeaturePreset("max_air_special_dive", "Air special dive", "Factory Max Moves", "Intermediate", "Air dive special starter.", ("cmd", "cns", "air"), tags=("air", "special")),
    FeaturePreset("max_ex_uppercut", "EX uppercut", "Factory Max Moves", "Intermediate", "Metered uppercut starter with spend notes.", ("cmd", "cns", "air"), tags=("ex", "special")),
    FeaturePreset("max_ex_fireball", "EX fireball", "Factory Max Moves", "Intermediate", "Metered projectile starter with stronger hitbox and speed notes.", ("cmd", "cns", "air"), tags=("ex", "projectile")),
    FeaturePreset("max_level2_super", "Level 2 super starter", "Factory Max Moves", "Intermediate", "Mid-cost super starter.", ("cmd", "cns", "air"), tags=("super", "meter")),
    FeaturePreset("max_cinematic_finisher", "Cinematic finisher starter", "Factory Max Moves", "Advanced", "Large super/finisher starter with camera/freeze notes.", ("cmd", "cns", "air"), tags=("super", "cinematic")),
    FeaturePreset("max_boss_desperation", "Boss desperation move", "Factory Max Moves", "Advanced", "Boss-style desperation attack starter gated by life/power comments.", ("cmd", "cns", "air"), tags=("boss", "super")),

    # AI and test lab
    FeaturePreset("max_ai_easy_profile", "AI easy profile", "Factory Max AI", "Beginner", "Gentle CPU behavior router.", ("cns",), tags=("ai", "easy")),
    FeaturePreset("max_ai_normal_profile", "AI normal profile", "Factory Max AI", "Intermediate", "Balanced CPU behavior router.", ("cns",), tags=("ai", "normal")),
    FeaturePreset("max_ai_hard_profile", "AI hard profile", "Factory Max AI", "Advanced", "Aggressive CPU behavior router.", ("cns",), tags=("ai", "hard")),
    FeaturePreset("max_ai_boss_profile", "AI boss profile", "Factory Max AI", "Advanced", "Boss-phase CPU behavior router.", ("cns",), tags=("ai", "boss")),
    FeaturePreset("max_training_dummy_profile", "Training dummy profile", "Factory Max Testing", "Beginner", "Training-dummy behavior notes and debug hooks.", ("cns",), tags=("training", "debug")),
    FeaturePreset("max_hitbox_debug_profile", "Hitbox debug profile", "Factory Max Testing", "Beginner", "Debug profile for checking state/time/animation/hitbox workflow.", ("cns",), tags=("hitbox", "debug")),
    FeaturePreset("max_frame_data_export_docs", "Frame-data export guide", "Factory Max Testing", "Beginner", "Frame-data review sheet for startup/active/recovery testing.", ("docs",), tags=("framedata", "docs")),
    FeaturePreset("max_combo_trial_docs", "Combo trial builder guide", "Factory Max Testing", "Beginner", "Combo trial planning guide for documenting routes.", ("docs",), tags=("combo", "docs")),
    FeaturePreset("max_release_qa_docs", "Release QA checklist", "Factory Max Testing", "Beginner", "Final quality checklist before packaging or sharing.", ("docs",), tags=("release", "docs")),
    FeaturePreset("max_accessibility_docs", "Accessibility checklist", "Factory Max Testing", "Beginner", "Checklist for readable effects, sane flashing, and control clarity.", ("docs",), tags=("accessibility", "docs")),
]

_v25_seen_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _V25_FEATURE_PRESETS:
    if _preset.feature_id not in _v25_seen_ids:
        FEATURE_PRESETS.append(_preset)
        _v25_seen_ids.add(_preset.feature_id)

_V24_BUILD_FEATURE_PACKAGE = build_feature_package

_V25_DOC_IDS = {p.feature_id for p in _V25_FEATURE_PRESETS if "docs" in p.blocks}
_V25_SYSTEM_IDS = {p.feature_id for p in _V25_FEATURE_PRESETS if p.feature_id.startswith("max_") and p.feature_id not in _V25_DOC_IDS}


def _v25_doc_text(fid: str, title: str) -> str:
    return f"""# {title}

Generated by MugenForge Studio Factory Max.

## Goal

This page exists so a beginner can make the creative decision while MugenForge handles the ugly routing/code in the app.

## What to decide

- What should this feature look like?
- Which sprites/sounds should represent it?
- Is it fast, slow, safe, risky, flashy, simple, or boss-level?
- What should the player feel when using it?

## What MugenForge can handle

- CMD/CNS/AIR scaffolding from Feature Bank presets.
- Placeholder sprites/sounds.
- AIR action repair.
- SFF/SND starter rebuilds.
- Project reports, state maps, move lists, and release ZIPs.

## Manual fun part

- Replace placeholder art.
- Drag hitboxes in the CLSN editor.
- Test the move in-game.
- Adjust timing/damage until it feels right.

## Related feature id

`{fid}`
"""


def _v25_docs_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", feature_id).upper()
    rel = f"docs/FACTORY_MAX_{safe}.md"
    text = _v25_doc_text(feature_id, preset.name)
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        extra_files={rel: text},
        summary=f"Writes a beginner-friendly Factory Max guide: {preset.name}.",
        notes=["No M.U.G.E.N code is required for this documentation helper."],
    )


def _v25_system_block(feature_id: str, title: str) -> str:
    var_seed = abs(sum(ord(c) for c in feature_id)) % 80
    var_a = 80 + (var_seed % 20)
    return f"""; MugenForge Factory Max system scaffold: {title}
; Feature id: {feature_id}
; This is intentionally readable and centralized so non-coders can toggle/tune the feature later.
[State -2, Factory Max {title} enable flag]
type = VarSet
trigger1 = RoundState = 2
v = {var_a}
value = Var({var_a})
ignorehitpause = 1

[State -2, Factory Max {title} debug note]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while tuning {title}
text = "\\nFactory Max: {title} var{var_a}=%d"
params = Var({var_a})
ignorehitpause = 1

; Beginner tuning notes:
; - Keep this as a router/hook, then use Move Wizard or Feature Bank to add actual moves.
; - Do not delete the marker comments around this block unless you want MugenForge to reinstall it.
"""


def _v25_cmd_hook(feature_id: str, title: str) -> str:
    cmd_name = feature_id.replace("max_", "")[:28]
    return f"""[Command]
name = "{cmd_name}"
command = x+y
time = 12
buffer.time = 4

; Factory Max optional command hook for {title}.
; Wire this to a custom StateDef only after testing.
"""


def _v25_system_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    cmd = _v25_cmd_hook(feature_id, preset.name) if "cmd" in preset.blocks else ""
    cns = _v25_system_block(feature_id, preset.name) if "cns" in preset.blocks else ""
    air = _simple_pose_air(8900 + (abs(sum(ord(c) for c in feature_id)) % 700), preset.name, 5) if "air" in preset.blocks else ""
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        cmd_block=_wrap(feature_id, preset.name, cmd),
        cns_block=_wrap(feature_id, preset.name, cns),
        air_block=_wrap(feature_id, preset.name, air),
        summary=f"Adds Factory Max no-code scaffold: {preset.name}.",
        notes=["This is a safe starter hook. Use the visual editors/reports to tune it instead of hand-coding from scratch."],
    )


_V25_MOVE_SPECS: Dict[str, MoveWizardSpec] = {
    "max_target_combo": _spec("Target Combo", "max_target_combo", "x, y", 1260, damage=45, frame_count=6, hit_frame=3, hit_box=(18, -76, 68, -34), sound=(5, 1), ground_velocity=(-4, 0)),
    "max_chain_uppercut": _spec("Chain Uppercut", "max_chain_uppercut", "F, y", 1265, damage=70, frame_count=7, hit_frame=3, hit_box=(10, -100, 58, -22), sound=(5, 2), ground_velocity=(-3, -6), air_velocity=(-3, -8)),
    "max_rekka_finish_low": _spec("Rekka Finish Low", "max_rekka_low", "~D, DF, F, a", 1270, damage=65, frame_count=7, hit_frame=4, hit_box=(18, -36, 84, -8), body_box=(-20, -70, 20, 0), sound=(5, 2), ground_velocity=(-6, 0)),
    "max_rekka_finish_overhead": _spec("Rekka Finish Overhead", "max_rekka_overhead", "~D, DF, F, b", 1271, damage=72, frame_count=8, hit_frame=5, hit_box=(18, -92, 78, -42), sound=(5, 2), ground_velocity=(-5, 0)),
    "max_flame_uppercut": _spec("Flame Uppercut", "max_flame_uppercut", "~F, D, DF, z", 1280, damage=95, frame_count=8, hit_frame=3, hit_box=(8, -108, 60, -18), sound=(5, 4), ground_velocity=(-4, -8), air_velocity=(-4, -9)),
    "max_ice_projectile": _spec("Ice Projectile", "max_ice_projectile", "~D, DF, F, y", 1285, move_type="projectile", damage=60, frame_count=7, hit_frame=4, hit_box=(24, -70, 78, -34), sound=(5, 3), ground_velocity=(-4, 0)),
    "max_lightning_dash": _spec("Lightning Dash", "max_lightning_dash", "F, F, z", 1290, damage=80, frame_count=7, hit_frame=3, hit_box=(18, -76, 100, -22), sound=(5, 4), ground_velocity=(-7, 0)),
    "max_ground_pound": _spec("Ground Pound", "max_ground_pound", "D, D, z", 1295, damage=85, frame_count=9, hit_frame=5, hit_box=(-36, -26, 86, 4), sound=(5, 5), ground_velocity=(-4, -2)),
    "max_command_counter": _spec("Command Counter", "max_command_counter", "B, DB, D, x", 1300, damage=75, frame_count=8, hit_frame=5, hit_box=(14, -84, 64, -28), sound=(5, 4), ground_velocity=(-5, 0)),
    "max_air_special_dive": _spec("Air Special Dive", "max_air_dive", "D, DF, F, a", 1305, damage=70, frame_count=7, hit_frame=3, hit_box=(14, -64, 70, -8), body_box=(-18, -82, 18, 4), sound=(5, 3), ground_velocity=(-4, -3), air_velocity=(-3, 6)),
    "max_ex_uppercut": _spec("EX Uppercut", "max_ex_uppercut", "~F, D, DF, c", 1310, damage=115, frame_count=9, hit_frame=3, hit_box=(8, -112, 70, -18), sound=(5, 6), ground_velocity=(-5, -9), air_velocity=(-4, -10)),
    "max_ex_fireball": _spec("EX Fireball", "max_ex_fireball", "~D, DF, F, z", 1315, move_type="projectile", damage=85, frame_count=8, hit_frame=4, hit_box=(22, -76, 94, -30), sound=(5, 6), ground_velocity=(-6, 0)),
    "max_level2_super": _spec("Level 2 Super", "max_level2_super", "~D, DF, F, D, DF, F, y", 3200, move_type="projectile", damage=210, frame_count=12, hit_frame=6, hit_box=(20, -86, 160, -20), sound=(5, 6), ground_velocity=(-8, 0)),
    "max_cinematic_finisher": _spec("Cinematic Finisher", "max_cinematic_finisher", "~D, DB, B, D, DB, B, z", 3300, damage=260, frame_count=14, hit_frame=7, hit_box=(10, -100, 110, -10), sound=(5, 7), ground_velocity=(-9, -4), air_velocity=(-6, -8)),
    "max_boss_desperation": _spec("Boss Desperation", "max_boss_desperation", "~D, DF, F, D, DF, F, c", 3400, move_type="projectile", damage=320, frame_count=16, hit_frame=8, hit_box=(0, -120, 220, 0), sound=(5, 7), ground_velocity=(-10, -4)),
}


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _V25_FEATURE_PRESETS}:
        return _V24_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id in _V25_DOC_IDS:
        return _v25_docs_package(feature_id, preset)
    if feature_id in _V25_MOVE_SPECS:
        pkg = _pack_from_specs(feature_id, preset.name, [_V25_MOVE_SPECS[feature_id]], list(preset.beginner_notes))
        if feature_id.startswith("max_ex_"):
            pkg.notes.append("EX starter: add meter spend/tuning after testing. The Max Meter Rules Router can centralize that logic.")
        if feature_id in {"max_level2_super", "max_cinematic_finisher", "max_boss_desperation"}:
            pkg.cns_block += _wrap(feature_id + "_super_notes", preset.name + " super pause notes", "[State -2, Factory Max super tuning note]\ntype = Null\ntrigger1 = 1\n; Copy SuperPause/EnvShake/PalFX into the generated state after testing timing.\n")
        return pkg
    return _v25_system_package(feature_id, preset)


KIT_PRESETS.update({
    "Max Visual Editor Parity Kit": [
        "max_sprite_organizer_docs", "max_image_editor_macros_docs", "max_offset_viewer_docs", "max_palette_link_audit_docs",
        "max_onion_skin_docs", "max_frame_interpolation_docs", "max_sound_viewer_docs", "max_autocomplete_bank_docs",
        "max_code_history_safety_docs", "max_debugger_docs",
    ],
    "Max No-Code Combat Lab Kit": [
        "max_universal_chain_router", "max_air_chain_router", "max_cancel_window_hud", "max_meter_rules_router",
        "max_ex_move_router", "max_super_freeze_router", "max_proration_router", "max_throw_tech_router",
        "max_guard_crush_router", "max_airdash_rules_router", "max_wallbounce_router", "max_groundbounce_router",
        "max_otg_rules_router", "max_projectile_ecosystem_router", "max_assist_rules_router",
    ],
    "Max Move Expansion Kit": [
        "max_target_combo", "max_chain_uppercut", "max_rekka_finish_low", "max_rekka_finish_overhead", "max_flame_uppercut",
        "max_ice_projectile", "max_lightning_dash", "max_ground_pound", "max_command_counter", "max_air_special_dive",
        "max_ex_uppercut", "max_ex_fireball", "max_level2_super",
    ],
    "Max AI and Training Kit": [
        "max_ai_easy_profile", "max_ai_normal_profile", "max_ai_hard_profile", "max_ai_boss_profile",
        "max_training_dummy_profile", "max_hitbox_debug_profile", "max_frame_data_export_docs", "max_combo_trial_docs",
    ],
    "Max Stage Storyboard Kit": [
        "max_bg_stage_editor_docs", "max_storyboard_editor_docs", "max_import_resolver_docs", "max_release_qa_docs", "max_accessibility_docs",
    ],
})
KIT_PRESETS["Max Beginner Full Production Kit"] = list(dict.fromkeys(
    KIT_PRESETS.get("FF+ Fighter Factory-Style Essentials", []) +
    KIT_PRESETS.get("FF+ Visual Polish Kit", []) +
    KIT_PRESETS["Max Visual Editor Parity Kit"] +
    KIT_PRESETS["Max No-Code Combat Lab Kit"] +
    KIT_PRESETS["Max AI and Training Kit"] +
    ["max_release_qa_docs", "max_accessibility_docs"]
))
KIT_PRESETS["Full No-Code Creator Pack"] = list(dict.fromkeys(
    KIT_PRESETS.get("Full No-Code Creator Pack", []) + KIT_PRESETS["Max Beginner Full Production Kit"]
))

# v2.6 Factory Ultra / Creator Pilot no-code expansion
_V25_BUILD_FEATURE_PACKAGE = build_feature_package

_V26_FEATURE_PRESETS: List[FeaturePreset] = [
    # Creator-pilot documentation helpers
    FeaturePreset("ultra_creator_cockpit_docs", "Creator cockpit guide", "Factory Ultra Guides", "Beginner", "Explains the cockpit dashboard, next-click workflow, and what the creator should handle versus what the tool handles.", ("docs",), tags=("cockpit", "docs")),
    FeaturePreset("ultra_task_board_docs", "Guided task board guide", "Factory Ultra Guides", "Beginner", "Explains the task board workflow for finishing a character without reading code.", ("docs",), tags=("tasks", "docs")),
    FeaturePreset("ultra_asset_qa_docs", "Asset QA guide", "Factory Ultra Guides", "Beginner", "Plain-English guide for checking sprite dimensions, transparency, AIR/SFF refs, WAV quality, and placeholder status.", ("docs",), tags=("assets", "qa")),
    FeaturePreset("ultra_balance_lab_docs", "Balance lab tuning guide", "Factory Ultra Guides", "Beginner", "Explains damage, hitstun, guardstun, pause, pushback, and power tuning without code jargon.", ("docs",), tags=("balance", "docs")),
    FeaturePreset("ultra_release_matrix_docs", "Release readiness guide", "Factory Ultra Guides", "Beginner", "Explains the release-readiness matrix and final packaging flow.", ("docs",), tags=("release", "docs")),
    FeaturePreset("ultra_lesson_mode_docs", "Lesson mode designer", "Factory Ultra Guides", "Beginner", "Creates a plan for tutorials, trials, and beginner-friendly move lessons.", ("docs",), tags=("tutorial", "docs")),
    FeaturePreset("ultra_snapshot_docs", "Snapshot safety workflow", "Factory Ultra Guides", "Beginner", "Teaches safe snapshot/backup habits before using generated code or batch edits.", ("docs",), tags=("backup", "safety")),
    FeaturePreset("ultra_sound_identity_docs", "Sound identity checklist", "Factory Ultra Guides", "Beginner", "Helps the creator choose impact, movement, voice, and UI sound families.", ("docs",), tags=("sound", "docs")),
    FeaturePreset("ultra_fx_identity_docs", "FX identity checklist", "Factory Ultra Guides", "Beginner", "Helps the creator choose spark, aura, projectile, smoke, and super-flash style rules.", ("docs",), tags=("fx", "docs")),
    FeaturePreset("ultra_accessibility_fx_docs", "Readable effects checklist", "Factory Ultra Guides", "Beginner", "Checklist for readable FX, reasonable flashing, contrast, and silhouettes.", ("docs",), tags=("accessibility", "fx")),

    # Beginner system routers / hidden code helpers
    FeaturePreset("ultra_input_buffer_router", "Input buffer router", "Factory Ultra Systems", "Intermediate", "Central readable skeleton for command buffers and input leniency tuning.", ("cmd", "cns"), tags=("input", "system")),
    FeaturePreset("ultra_easy_combo_router", "Easy combo router", "Factory Ultra Systems", "Beginner", "Starter one-button/easy-route combo skeleton for beginner-accessible characters.", ("cmd", "cns"), tags=("combo", "beginner")),
    FeaturePreset("ultra_autocombo_router", "Auto-combo router", "Factory Ultra Systems", "Intermediate", "Simple auto-combo routing skeleton with clear tuning variables.", ("cmd", "cns"), tags=("autocombo", "system")),
    FeaturePreset("ultra_move_cooldown_router", "Move cooldown router", "Factory Ultra Systems", "Intermediate", "Central cooldown skeleton for specials, assists, evasive actions, and boss moves.", ("cns",), tags=("cooldown", "system")),
    FeaturePreset("ultra_whiff_punish_router", "Whiff-punish teaching helper", "Factory Ultra Systems", "Intermediate", "Training helper skeleton that can display notes when big moves miss.", ("cns",), tags=("training", "whiff")),
    FeaturePreset("ultra_hitconfirm_helper", "Hit-confirm trainer helper", "Factory Ultra Systems", "Beginner", "Clipboard/debug helper for teaching which moves are confirmable.", ("cns",), tags=("training", "hitconfirm")),
    FeaturePreset("ultra_random_color_intro", "Random color intro hook", "Factory Ultra Systems", "Beginner", "Intro/palette personality hook skeleton with safe comments.", ("cns", "air"), tags=("intro", "palette")),
    FeaturePreset("ultra_dynamic_difficulty_router", "Dynamic difficulty router", "Factory Ultra Systems", "Advanced", "Optional CPU/boss difficulty variable router with readable tuning notes.", ("cns",), tags=("ai", "difficulty")),
    FeaturePreset("ultra_boss_phase_2_router", "Boss phase-two router", "Factory Ultra Systems", "Advanced", "Boss phase trigger skeleton based on life/round state.", ("cns", "air"), tags=("boss", "system")),
    FeaturePreset("ultra_camera_shake_router", "Camera shake rules", "Factory Ultra Systems", "Intermediate", "Central EnvShake style rules for heavy hits, landings, and supers.", ("cns",), tags=("camera", "fx")),
    FeaturePreset("ultra_hitstop_router", "Hitstop timing router", "Factory Ultra Systems", "Intermediate", "Central notes/router for attack freeze feel and pausetime consistency.", ("cns",), tags=("hitstop", "balance")),
    FeaturePreset("ultra_assist_safety_router", "Assist safety rules", "Factory Ultra Systems", "Advanced", "Safety/cooldown notes for helper/assist moves.", ("cns",), tags=("assist", "safety")),
    FeaturePreset("ultra_round_tutorial_router", "Round tutorial router", "Factory Ultra Systems", "Beginner", "Optional training-round text/display scaffold for teaching the character.", ("cns",), tags=("tutorial", "training")),
    FeaturePreset("ultra_quality_flags_router", "Quality flags router", "Factory Ultra Systems", "Beginner", "Central variables for placeholder flags, test flags, debug flags, and release flags.", ("cns",), tags=("qa", "flags")),

    # Move starters
    FeaturePreset("ultra_auto_combo_1", "Auto-combo route A", "Factory Ultra Moves", "Beginner", "Beginner-friendly auto-combo starter move with CMD/CNS/AIR scaffolding.", ("cmd", "cns", "air"), tags=("combo", "beginner")),
    FeaturePreset("ultra_auto_combo_2", "Auto-combo route B", "Factory Ultra Moves", "Beginner", "Second auto-combo route starter for alternate button feel.", ("cmd", "cns", "air"), tags=("combo", "beginner")),
    FeaturePreset("ultra_safe_special", "Safe special starter", "Factory Ultra Moves", "Intermediate", "Lower-risk special move starter with modest damage and pushback.", ("cmd", "cns", "air"), tags=("special", "safe")),
    FeaturePreset("ultra_risky_reversal", "Risky reversal starter", "Factory Ultra Moves", "Intermediate", "High-risk wakeup/reversal-style starter with clear balancing notes.", ("cmd", "cns", "air"), tags=("reversal", "special")),
    FeaturePreset("ultra_meter_burn_combo", "Meter-burn combo starter", "Factory Ultra Moves", "Intermediate", "Metered extension starter to teach EX/combo routes.", ("cmd", "cns", "air"), tags=("meter", "combo")),
    FeaturePreset("ultra_screen_control_special", "Screen-control special", "Factory Ultra Moves", "Intermediate", "Space-control projectile/trap-style starter.", ("cmd", "cns", "air"), tags=("projectile", "space")),
    FeaturePreset("ultra_air_route_starter", "Air-route starter", "Factory Ultra Moves", "Intermediate", "Air combo starter with vertical hit placement.", ("cmd", "cns", "air"), tags=("air", "combo")),
    FeaturePreset("ultra_corner_carry", "Corner-carry starter", "Factory Ultra Moves", "Intermediate", "Horizontal knockback/carry starter for combo routing.", ("cmd", "cns", "air"), tags=("corner", "combo")),
    FeaturePreset("ultra_guard_breaker", "Guard-breaker starter", "Factory Ultra Moves", "Advanced", "Slow guard-pressure starter with strong warning comments.", ("cmd", "cns", "air"), tags=("guard", "pressure")),
    FeaturePreset("ultra_throw_bait", "Throw-bait feint", "Factory Ultra Moves", "Intermediate", "Non-hit feint/step starter for mix-up personality.", ("cmd", "cns", "air"), tags=("feint", "mixup")),
]

_v26_seen_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _V26_FEATURE_PRESETS:
    if _preset.feature_id not in _v26_seen_ids:
        FEATURE_PRESETS.append(_preset)
        _v26_seen_ids.add(_preset.feature_id)

_V26_DOC_IDS = {p.feature_id for p in _V26_FEATURE_PRESETS if "docs" in p.blocks}


def _v26_doc_text(fid: str, title: str) -> str:
    return f"""# {title}

Generated by MugenForge Studio Factory Ultra.

## Purpose

This guide is for creators who do not want to hand-code M.U.G.E.N files. Use it as a decision sheet: pick the creative answer, then let MugenForge generate or repair the code/assets behind the scenes.

## Creator choices

- What should the player feel?
- What should the move/effect/sound communicate?
- Is it beginner-friendly, flashy, technical, defensive, boss-like, or goofy?
- What placeholder should be replaced first?

## Tool-handled work

- CMD/CNS/AIR scaffolding.
- Placeholder sprite and sound banks.
- Asset QA reports.
- Balance CSVs.
- Release readiness reports.
- Backup snapshots before risky edits.

## Related Feature Bank ID

`{fid}`
"""


def _v26_docs_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", feature_id).upper()
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        extra_files={f"docs/FACTORY_ULTRA_{safe}.md": _v26_doc_text(feature_id, preset.name)},
        summary=f"Writes a Factory Ultra beginner guide: {preset.name}.",
        notes=["Documentation-only preset. No coding required."],
    )


def _v26_system_block(feature_id: str, title: str) -> str:
    seed = abs(sum(ord(c) for c in feature_id))
    var_a = 100 + (seed % 40)
    var_b = 140 + (seed % 40)
    return f"""; MugenForge Factory Ultra system scaffold: {title}
; Feature id: {feature_id}
; This block is intentionally centralized and readable so a non-coder can turn it on/off later.
[State -2, Ultra {title} flag]
type = VarSet
trigger1 = RoundState = 2
v = {var_a}
value = Var({var_a})
ignorehitpause = 1

[State -2, Ultra {title} timer]
type = VarAdd
trigger1 = Var({var_b}) > 0
v = {var_b}
value = -1
ignorehitpause = 1

[State -2, Ultra {title} debug]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while tuning {title}
text = "\\nUltra {title}: flag=%d timer=%d"
params = Var({var_a}), Var({var_b})
ignorehitpause = 1

; Beginner tuning notes:
; - The Feature Bank installed the hook. You still choose sprites, sounds, timing, and feel.
; - Use Factory Ultra reports before release.
"""


def _v26_cmd_hook(feature_id: str, title: str) -> str:
    cmd_name = feature_id.replace("ultra_", "u_")[:28]
    return f"""[Command]
name = "{cmd_name}"
command = x+y
buffer.time = 4
time = 12

; Optional Factory Ultra command hook for {title}.
"""


def _v26_system_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    cmd = _v26_cmd_hook(feature_id, preset.name) if "cmd" in preset.blocks else ""
    cns = _v26_system_block(feature_id, preset.name) if "cns" in preset.blocks else ""
    air = _simple_pose_air(9400 + (abs(sum(ord(c) for c in feature_id)) % 500), preset.name, 5) if "air" in preset.blocks else ""
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        cmd_block=_wrap(feature_id, preset.name, cmd),
        cns_block=_wrap(feature_id, preset.name, cns),
        air_block=_wrap(feature_id, preset.name, air),
        summary=f"Adds Factory Ultra no-code hook: {preset.name}.",
        notes=["Safe starter hook. Use the Creator Cockpit, Task Board, and reports to tune without hand-coding."],
    )


_V26_MOVE_SPECS: Dict[str, MoveWizardSpec] = {
    "ultra_auto_combo_1": _spec("Auto Combo Route A", "ultra_auto_a", "x", 4100, damage=42, frame_count=6, hit_frame=3, hit_box=(18, -76, 72, -34), sound=(5, 1), ground_velocity=(-3, 0)),
    "ultra_auto_combo_2": _spec("Auto Combo Route B", "ultra_auto_b", "y", 4110, damage=58, frame_count=7, hit_frame=4, hit_box=(20, -84, 84, -26), sound=(5, 2), ground_velocity=(-4, -2), air_velocity=(-3, -5)),
    "ultra_safe_special": _spec("Safe Special", "ultra_safe_special", "~D, DF, F, x", 4120, damage=52, frame_count=7, hit_frame=4, hit_box=(20, -72, 92, -30), sound=(5, 3), ground_velocity=(-2, 0)),
    "ultra_risky_reversal": _spec("Risky Reversal", "ultra_reversal", "~F, D, DF, x", 4130, damage=88, frame_count=8, hit_frame=3, hit_box=(4, -108, 64, -14), sound=(5, 4), ground_velocity=(-5, -8), air_velocity=(-4, -9)),
    "ultra_meter_burn_combo": _spec("Meter Burn Combo", "ultra_meter_burn", "~D, DF, F, y+z", 4140, damage=105, frame_count=9, hit_frame=5, hit_box=(18, -88, 112, -20), sound=(5, 6), ground_velocity=(-6, -3)),
    "ultra_screen_control_special": _spec("Screen Control Special", "ultra_screen_ctrl", "~D, DB, B, y", 4150, move_type="projectile", damage=62, frame_count=8, hit_frame=5, hit_box=(24, -66, 120, -22), sound=(5, 3), ground_velocity=(-3, 0)),
    "ultra_air_route_starter": _spec("Air Route Starter", "ultra_air_route", "D, DF, F, x", 4160, damage=68, frame_count=7, hit_frame=3, hit_box=(8, -80, 66, -8), body_box=(-18, -82, 18, 4), sound=(5, 2), ground_velocity=(-3, -5), air_velocity=(-3, -7)),
    "ultra_corner_carry": _spec("Corner Carry", "ultra_corner_carry", "~D, DF, F, z", 4170, damage=76, frame_count=8, hit_frame=4, hit_box=(14, -76, 110, -18), sound=(5, 2), ground_velocity=(-8, 0), air_velocity=(-6, -3)),
    "ultra_guard_breaker": _spec("Guard Breaker", "ultra_guard_break", "~D, DB, B, z", 4180, damage=92, frame_count=10, hit_frame=7, hit_box=(16, -96, 96, -18), sound=(5, 5), ground_velocity=(-5, 0)),
    "ultra_throw_bait": _spec("Throw Bait Feint", "ultra_throw_bait", "F, x+y", 4190, move_type="movement", damage=0, frame_count=6, hit_frame=0, hit_box=(0, 0, 0, 0), sound=(6, 0), ground_velocity=(0, 0)),
}


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _V26_FEATURE_PRESETS}:
        return _V25_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id in _V26_DOC_IDS:
        return _v26_docs_package(feature_id, preset)
    if feature_id in _V26_MOVE_SPECS:
        pkg = _pack_from_specs(feature_id, preset.name, [_V26_MOVE_SPECS[feature_id]], list(preset.beginner_notes))
        if feature_id in {"ultra_meter_burn_combo", "ultra_guard_breaker", "ultra_risky_reversal"}:
            pkg.notes.append("This starter is intentionally strong/risky. Run Balance Lab after installing it.")
        return pkg
    return _v26_system_package(feature_id, preset)


KIT_PRESETS.update({
    "Ultra No-Code Production Kit": [
        "ultra_creator_cockpit_docs", "ultra_task_board_docs", "ultra_asset_qa_docs", "ultra_balance_lab_docs",
        "ultra_input_buffer_router", "ultra_quality_flags_router", "ultra_hitconfirm_helper", "ultra_round_tutorial_router",
    ],
    "Ultra Beginner Safety Kit": [
        "ultra_snapshot_docs", "ultra_release_matrix_docs", "ultra_accessibility_fx_docs", "ultra_sound_identity_docs", "ultra_fx_identity_docs",
        "ultra_quality_flags_router", "ultra_hitstop_router",
    ],
    "Ultra Beginner Moves Kit": [
        "ultra_auto_combo_1", "ultra_auto_combo_2", "ultra_safe_special", "ultra_screen_control_special", "ultra_throw_bait",
    ],
    "Ultra Advanced Combat Kit": [
        "ultra_autocombo_router", "ultra_move_cooldown_router", "ultra_risky_reversal", "ultra_meter_burn_combo",
        "ultra_air_route_starter", "ultra_corner_carry", "ultra_guard_breaker", "ultra_assist_safety_router",
    ],
    "Ultra Boss and Training Kit": [
        "ultra_dynamic_difficulty_router", "ultra_boss_phase_2_router", "ultra_whiff_punish_router", "ultra_hitconfirm_helper",
        "ultra_lesson_mode_docs", "ultra_camera_shake_router",
    ],
    "Ultra Release Polish Kit": [
        "ultra_release_matrix_docs", "ultra_asset_qa_docs", "ultra_balance_lab_docs", "ultra_sound_identity_docs", "ultra_fx_identity_docs",
        "ultra_accessibility_fx_docs", "ultra_camera_shake_router", "ultra_hitstop_router",
    ],
})

KIT_PRESETS["Full No-Code Creator Pack"] = list(dict.fromkeys(
    KIT_PRESETS.get("Full No-Code Creator Pack", []) +
    KIT_PRESETS["Ultra No-Code Production Kit"] +
    KIT_PRESETS["Ultra Beginner Safety Kit"] +
    KIT_PRESETS["Ultra Beginner Moves Kit"]
))

# ---------------------------------------------------------------------------
# v2.6 Creator AutoPilot feature bank expansion
# ---------------------------------------------------------------------------

_V26_FEATURE_PRESETS: List[FeaturePreset] = [
    # Creator AutoPilot documentation helpers
    FeaturePreset("v26_character_dna_docs", "Character DNA worksheet", "Creator AutoPilot Docs", "Beginner", "No-code character identity worksheet covering archetype, buttons, meter, personality, and priorities.", ("docs",), tags=("autopilot", "docs")),
    FeaturePreset("v26_creator_dashboard_docs", "Creator dashboard guide", "Creator AutoPilot Docs", "Beginner", "Explains the dashboard/report workflow for non-coders.", ("docs",), tags=("dashboard", "docs")),
    FeaturePreset("v26_time_machine_docs", "Time Machine snapshot guide", "Creator AutoPilot Docs", "Beginner", "Teaches the snapshot-before-big-edits safety workflow.", ("docs",), tags=("backup", "docs")),
    FeaturePreset("v26_asset_library_docs", "Asset Library guide", "Creator AutoPilot Docs", "Beginner", "Guides sprite/sound/palette organization without manual code edits.", ("docs",), tags=("assets", "docs")),
    FeaturePreset("v26_move_lab_docs", "Move Lab / frame sheet guide", "Creator AutoPilot Docs", "Beginner", "Plain-English guide to reading startup/active/recovery-style timing from generated reports.", ("docs",), tags=("moves", "docs")),
    FeaturePreset("v26_combo_tree_docs", "Combo Tree guide", "Creator AutoPilot Docs", "Beginner", "Explains the state-flow graph and how to spot broken transitions.", ("docs",), tags=("combo", "docs")),
    FeaturePreset("v26_art_task_board_docs", "Art Task Board guide", "Creator AutoPilot Docs", "Beginner", "Turns AIR sprite references into an artist-friendly to-do list.", ("docs",), tags=("art", "docs")),
    FeaturePreset("v26_beginner_tuning_docs", "Beginner tuning guide", "Creator AutoPilot Docs", "Beginner", "Explains safe damage/speed/hit-pause/pushback tuning knobs.", ("docs",), tags=("tuning", "docs")),
    FeaturePreset("v26_training_pack_docs", "Training pack guide", "Creator AutoPilot Docs", "Beginner", "Guide for combo trials, button notes, and repeatable test scripts.", ("docs",), tags=("training", "docs")),
    FeaturePreset("v26_final_qa_docs", "Final QA guide", "Creator AutoPilot Docs", "Beginner", "Release checklist covering files, testing, credits, and packaging.", ("docs",), tags=("qa", "docs")),
    FeaturePreset("v26_accessible_creator_docs", "Accessible creator workflow", "Creator AutoPilot Docs", "Beginner", "Design notes for readable FX, control clarity, and avoiding over-flashy visuals.", ("docs",), tags=("accessibility", "docs")),
    FeaturePreset("v26_no_code_pipeline_docs", "No-code pipeline overview", "Creator AutoPilot Docs", "Beginner", "End-to-end workflow: recipe → kits → placeholders → animation → hitboxes → test → release.", ("docs",), tags=("pipeline", "docs")),

    # Project-wide no-code system hooks
    FeaturePreset("v26_tuning_panel_router", "Beginner tuning panel router", "Creator AutoPilot Systems", "Beginner", "Central starter VarSet/clipboard hook for future no-code tuning panels.", ("cns",), tags=("tuning", "system")),
    FeaturePreset("v26_damage_knob_router", "Damage knob router", "Creator AutoPilot Systems", "Intermediate", "Central damage-scale variable hook for generated move families.", ("cns",), tags=("damage", "tuning")),
    FeaturePreset("v26_hitpause_knob_router", "Hit-pause knob router", "Creator AutoPilot Systems", "Intermediate", "Hit-pause/guard-pause variable hook for generated attacks.", ("cns",), tags=("hitpause", "tuning")),
    FeaturePreset("v26_pushback_knob_router", "Pushback knob router", "Creator AutoPilot Systems", "Intermediate", "Pushback tuning variable hook for generated HitDefs.", ("cns",), tags=("pushback", "tuning")),
    FeaturePreset("v26_input_buffer_router", "Input buffer helper router", "Creator AutoPilot Systems", "Intermediate", "Readable command-buffer notes and debug hook for command tuning.", ("cmd", "cns"), tags=("input", "system")),
    FeaturePreset("v26_auto_combo_assist_router", "Auto-combo assist router", "Creator AutoPilot Systems", "Intermediate", "Safe starter hook for optional simplified combo routes.", ("cmd", "cns"), tags=("combo", "assist")),
    FeaturePreset("v26_beginner_cancel_helper", "Beginner cancel helper", "Creator AutoPilot Systems", "Intermediate", "Starter hook for turning cancel rules into a centralized readable section.", ("cns",), tags=("cancel", "system")),
    FeaturePreset("v26_state_safety_net", "State safety net", "Creator AutoPilot Systems", "Beginner", "Debug/readability scaffold to help catch states that never return to control.", ("cns",), tags=("safety", "debug")),
    FeaturePreset("v26_auto_return_idle_guard", "Auto return-to-idle guard", "Creator AutoPilot Systems", "Beginner", "Readable Null hook reminding generated states to return to idle safely.", ("cns",), tags=("safety", "states")),
    FeaturePreset("v26_round_start_director", "Round start director", "Creator AutoPilot Systems", "Intermediate", "Round-start personality hook for intros, power settings, and visual state.", ("cns", "air"), tags=("round", "system")),
    FeaturePreset("v26_meter_display_hook", "Meter display hook", "Creator AutoPilot Systems", "Intermediate", "Clipboard/debug hook for power/meter testing.", ("cns",), tags=("meter", "debug")),
    FeaturePreset("v26_combo_counter_hook", "Combo counter review hook", "Creator AutoPilot Systems", "Intermediate", "Debug hook for checking combo/hit timing during testing.", ("cns",), tags=("combo", "debug")),
    FeaturePreset("v26_hitbox_review_overlay", "Hitbox review overlay hook", "Creator AutoPilot Systems", "Beginner", "Clipboard reminders for hitbox review workflow.", ("cns",), tags=("hitbox", "debug")),
    FeaturePreset("v26_training_todo_clipboard", "Training TODO clipboard", "Creator AutoPilot Systems", "Beginner", "Optional clipboard checklist while testing in-engine.", ("cns",), tags=("training", "debug")),
    FeaturePreset("v26_asset_missing_warning", "Missing asset warning hook", "Creator AutoPilot Systems", "Beginner", "Debug/readability hook for reminding creators to check Art Task Board and missing refs.", ("cns",), tags=("assets", "debug")),
    FeaturePreset("v26_palette_style_router", "Palette style router", "Creator AutoPilot Systems", "Beginner", "Palette/FX style hook and notes for colorway variants.", ("cns", "air"), tags=("palette", "style")),
    FeaturePreset("v26_sound_call_router", "Sound call router", "Creator AutoPilot Systems", "Beginner", "Central sound-cue routing notes for generated moves.", ("cns",), tags=("sound", "system")),
    FeaturePreset("v26_ai_style_director", "AI style director", "Creator AutoPilot Systems", "Intermediate", "AI personality hook with beginner-readable difficulty notes.", ("cns",), tags=("ai", "system")),
    FeaturePreset("v26_accessibility_fx_limiter", "Accessibility FX limiter", "Creator AutoPilot Systems", "Beginner", "Readable hook for limiting screen shake/flashing while testing.", ("cns",), tags=("accessibility", "fx")),

    # AutoPilot move/system starters
    FeaturePreset("v26_assisted_light_chain", "Assisted light chain", "Creator AutoPilot Moves", "Beginner", "Simple low-risk chain starter for beginners who want one-button flow testing.", ("cmd", "cns", "air"), tags=("combo", "beginner")),
    FeaturePreset("v26_assisted_launch_chain", "Assisted launcher chain", "Creator AutoPilot Moves", "Intermediate", "Chain starter that routes to a launcher-style attack.", ("cmd", "cns", "air"), tags=("combo", "launcher")),
    FeaturePreset("v26_simple_punish_button", "Simple punish button", "Creator AutoPilot Moves", "Beginner", "One reliable punish attack with readable damage/timing notes.", ("cmd", "cns", "air"), tags=("attack", "punish")),
    FeaturePreset("v26_beginner_anti_air", "Beginner anti-air", "Creator AutoPilot Moves", "Beginner", "Easy anti-air starter with big vertical box for early testing.", ("cmd", "cns", "air"), tags=("anti-air", "attack")),
    FeaturePreset("v26_safe_fireball", "Safe test fireball", "Creator AutoPilot Moves", "Beginner", "Projectile starter tuned for learning spacing rather than final balance.", ("cmd", "cns", "air"), tags=("projectile", "beginner")),
    FeaturePreset("v26_escape_special", "Escape special", "Creator AutoPilot Moves", "Intermediate", "Movement special starter for defensive or evasive characters.", ("cmd", "cns", "air"), tags=("movement", "defense")),
    FeaturePreset("v26_showoff_taunt", "Showoff taunt", "Creator AutoPilot Moves", "Beginner", "Personality taunt with a longer animation placeholder.", ("cmd", "cns", "air"), tags=("taunt", "personality")),
    FeaturePreset("v26_training_super", "Training super", "Creator AutoPilot Moves", "Intermediate", "Simple super starter designed for hitbox/timing practice.", ("cmd", "cns", "air"), tags=("super", "training")),
    FeaturePreset("v26_boss_phase_attack", "Boss phase attack", "Creator AutoPilot Moves", "Advanced", "Boss-style large attack scaffold with phase notes.", ("cmd", "cns", "air"), tags=("boss", "attack")),
    FeaturePreset("v26_signature_finisher", "Signature finisher", "Creator AutoPilot Moves", "Advanced", "Big character-defining finisher scaffold for late polish.", ("cmd", "cns", "air"), tags=("finisher", "super")),
]

_v26_seen_ids = {p.feature_id for p in FEATURE_PRESETS}
for _preset in _V26_FEATURE_PRESETS:
    if _preset.feature_id not in _v26_seen_ids:
        FEATURE_PRESETS.append(_preset)
        _v26_seen_ids.add(_preset.feature_id)

_V26_BUILD_FEATURE_PACKAGE = build_feature_package
_V26_DOC_IDS = {p.feature_id for p in _V26_FEATURE_PRESETS if "docs" in p.blocks}
_V26_MOVE_IDS = {p.feature_id for p in _V26_FEATURE_PRESETS if p.category == "Creator AutoPilot Moves"}


def _v26_doc_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", feature_id).upper()
    rel = f"docs/CREATOR_AUTOPILOT_{safe}.md"
    text = f"""# {preset.name}

Generated by MugenForge Studio Creator AutoPilot.

## What this is

{preset.description}

## No-code workflow

1. Pick the creative direction.
2. Let MugenForge generate safe starter scaffolding and reports.
3. Replace placeholder art and sound.
4. Use Animation Player and CLSN Editor for timing/hitboxes.
5. Test in M.U.G.E.N and run Final QA.

## Creator choices

- Visual style
- Sound/voice style
- Animation timing
- Hitbox feel
- Balance and personality

## Related feature id

`{feature_id}`
"""
    return FeaturePackage(feature_id=feature_id, name=preset.name, extra_files={rel: text}, summary=f"Writes Creator AutoPilot guide: {preset.name}.", notes=["Documentation helper; no hand coding required."])


def _v26_system_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    seed = abs(sum(ord(c) for c in feature_id))
    var_no = 40 + (seed % 19)
    cmd_name = feature_id.replace("v26_", "")[:28]
    cmd = ""
    if "cmd" in preset.blocks:
        cmd = f"""[Command]
name = "{cmd_name}"
command = x+y
// Change this command later in the Code Assistant if needed.
time = 12
buffer.time = 4
""".replace("//", ";")
    cns = ""
    if "cns" in preset.blocks:
        cns = f"""; Creator AutoPilot system hook: {preset.name}
; Feature id: {feature_id}
[State -2, Creator AutoPilot {preset.name} flag]
type = VarSet
trigger1 = RoundState >= 0
v = {var_no}
value = Var({var_no})
ignorehitpause = 1

[State -2, Creator AutoPilot {preset.name} note]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while tuning this helper
text = "\\nCreator AutoPilot: {preset.name} var{var_no}=%d"
params = Var({var_no})
ignorehitpause = 1

; Beginner note: this is a central hook/router. Use the Creator AutoPilot tab, Move Wizard, and Feature Bank to add real moves around it.
"""
    air = _simple_pose_air(9300 + (seed % 600), preset.name, 5) if "air" in preset.blocks else ""
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        cmd_block=_wrap(feature_id, preset.name, cmd),
        cns_block=_wrap(feature_id, preset.name, cns),
        air_block=_wrap(feature_id, preset.name, air),
        summary=f"Adds Creator AutoPilot scaffold: {preset.name}.",
        notes=["Designed as no-code routing/scaffolding, not a finished balance solution."],
    )


_V26_MOVE_SPECS: Dict[str, MoveWizardSpec] = {
    "v26_assisted_light_chain": _spec("Assisted Light Chain", "v26_light_chain", "x, x", 1420, damage=32, frame_count=5, hit_frame=2, hit_box=(15, -70, 55, -35), sound=(5, 0), ground_velocity=(-3, 0)),
    "v26_assisted_launch_chain": _spec("Assisted Launch Chain", "v26_launch_chain", "x, y", 1425, damage=62, frame_count=7, hit_frame=3, hit_box=(8, -104, 62, -20), sound=(5, 2), ground_velocity=(-3, -6), air_velocity=(-3, -8)),
    "v26_simple_punish_button": _spec("Simple Punish Button", "v26_punish", "z", 1430, damage=78, frame_count=8, hit_frame=4, hit_box=(18, -80, 82, -28), sound=(5, 2), ground_velocity=(-6, 0)),
    "v26_beginner_anti_air": _spec("Beginner Anti Air", "v26_anti_air", "y", 1435, damage=68, frame_count=7, hit_frame=3, hit_box=(4, -112, 58, -24), sound=(5, 2), ground_velocity=(-2, -5), air_velocity=(-2, -7)),
    "v26_safe_fireball": _spec("Safe Test Fireball", "v26_safe_fireball", "~D, DF, F, x", 1440, move_type="projectile", damage=48, frame_count=7, hit_frame=4, hit_box=(22, -72, 80, -32), sound=(5, 3), ground_velocity=(-3, 0)),
    "v26_escape_special": _spec("Escape Special", "v26_escape", "B, D, DB, a", 1445, damage=38, frame_count=8, hit_frame=5, hit_box=(12, -70, 58, -26), sound=(5, 4), ground_velocity=(-2, 0)),
    "v26_showoff_taunt": _spec("Showoff Taunt", "v26_showoff", "s", 1450, move_type="movement", damage=0, frame_count=9, hit_frame=99, hit_box=(0, 0, 0, 0), sound=(5, 0), ground_velocity=(0, 0)),
    "v26_training_super": _spec("Training Super", "v26_training_super", "~D, DF, F, D, DF, F, x", 3500, damage=190, frame_count=12, hit_frame=6, hit_box=(16, -90, 140, -16), sound=(5, 6), ground_velocity=(-7, -3)),
    "v26_boss_phase_attack": _spec("Boss Phase Attack", "v26_boss_phase", "~D, DB, B, D, DF, F, z", 3600, move_type="projectile", damage=230, frame_count=14, hit_frame=7, hit_box=(-20, -120, 210, 0), sound=(5, 7), ground_velocity=(-8, -4)),
    "v26_signature_finisher": _spec("Signature Finisher", "v26_finisher", "~D, DF, F, D, DB, B, c", 3700, damage=260, frame_count=15, hit_frame=8, hit_box=(8, -112, 160, -10), sound=(5, 7), ground_velocity=(-9, -5)),
}


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in {p.feature_id for p in _V26_FEATURE_PRESETS}:
        return _V26_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id in _V26_DOC_IDS:
        return _v26_doc_package(feature_id, preset)
    if feature_id in _V26_MOVE_SPECS:
        pkg = _pack_from_specs(feature_id, preset.name, [_V26_MOVE_SPECS[feature_id]], list(preset.beginner_notes))
        pkg.notes.append("Creator AutoPilot move: use Move Lab, Animation Player, and CLSN Editor after installing.")
        return pkg
    return _v26_system_package(feature_id, preset)


KIT_PRESETS.update({
    "Creator AutoPilot Docs Kit": [
        "v26_character_dna_docs", "v26_creator_dashboard_docs", "v26_time_machine_docs", "v26_asset_library_docs",
        "v26_move_lab_docs", "v26_combo_tree_docs", "v26_art_task_board_docs", "v26_beginner_tuning_docs",
        "v26_training_pack_docs", "v26_final_qa_docs", "v26_no_code_pipeline_docs",
    ],
    "Creator AutoPilot Systems Kit": [
        "v26_tuning_panel_router", "v26_damage_knob_router", "v26_hitpause_knob_router", "v26_pushback_knob_router",
        "v26_input_buffer_router", "v26_auto_combo_assist_router", "v26_beginner_cancel_helper", "v26_state_safety_net",
        "v26_auto_return_idle_guard", "v26_meter_display_hook", "v26_combo_counter_hook", "v26_hitbox_review_overlay",
        "v26_training_todo_clipboard", "v26_asset_missing_warning", "v26_palette_style_router", "v26_sound_call_router",
    ],
    "Creator AutoPilot Starter Moves Kit": [
        "v26_assisted_light_chain", "v26_assisted_launch_chain", "v26_simple_punish_button", "v26_beginner_anti_air",
        "v26_safe_fireball", "v26_escape_special", "v26_showoff_taunt", "v26_training_super",
    ],
    "Creator AutoPilot Boss/Advanced Kit": [
        "v26_boss_phase_attack", "v26_signature_finisher", "v26_ai_style_director", "v26_accessibility_fx_limiter", "v26_round_start_director",
    ],
})
KIT_PRESETS["Creator AutoPilot Full Kit"] = list(dict.fromkeys(
    KIT_PRESETS["Creator AutoPilot Docs Kit"] +
    KIT_PRESETS["Creator AutoPilot Systems Kit"] +
    KIT_PRESETS["Creator AutoPilot Starter Moves Kit"]
))
KIT_PRESETS["Full No-Code Creator Pack"] = list(dict.fromkeys(
    KIT_PRESETS.get("Full No-Code Creator Pack", []) + KIT_PRESETS["Creator AutoPilot Full Kit"]
))

# ---------------------------------------------------------------------------
# v2.6 Factory Ultra compatibility patch
# ---------------------------------------------------------------------------
_FINAL_V26_PREV_BUILD_FEATURE_PACKAGE = build_feature_package


def _factory_ultra_compat_doc(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", feature_id).upper()
    text = f"""# {preset.name}

Generated by MugenForge Studio Factory Ultra.

## Purpose

{preset.description}

## Beginner workflow

- Make the creative decision first.
- Let MugenForge generate code, reports, and placeholder assets.
- Replace placeholder art/sound.
- Use Animation Player and CLSN Editor for visual tuning.
- Run Factory Ultra reports before release.

Feature ID: `{feature_id}`
"""
    return FeaturePackage(feature_id=feature_id, name=preset.name, extra_files={f"docs/FACTORY_ULTRA_{safe}.md": text}, summary=f"Writes Factory Ultra guide: {preset.name}.", notes=["No-code documentation helper."])


def _factory_ultra_compat_system(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    seed = abs(sum(ord(c) for c in feature_id))
    var_no = 100 + (seed % 40)
    cmd = ""
    if "cmd" in preset.blocks:
        cmd_name = feature_id[:28]
        cmd = f"""[Command]
name = "{cmd_name}"
command = x+y
time = 12
buffer.time = 4
"""
    cns = ""
    if "cns" in preset.blocks:
        cns = f"""; Factory Ultra no-code system hook: {preset.name}
; Feature id: {feature_id}
[State -2, Factory Ultra {preset.name} flag]
type = VarSet
trigger1 = RoundState >= 0
v = {var_no}
value = Var({var_no})
ignorehitpause = 1

[State -2, Factory Ultra {preset.name} debug]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while tuning this feature
text = "\\nFactory Ultra: {preset.name} var{var_no}=%d"
params = Var({var_no})
ignorehitpause = 1
"""
    air = _simple_pose_air(9600 + (seed % 300), preset.name, 5) if "air" in preset.blocks else ""
    return FeaturePackage(feature_id=feature_id, name=preset.name, cmd_block=_wrap(feature_id, preset.name, cmd), cns_block=_wrap(feature_id, preset.name, cns), air_block=_wrap(feature_id, preset.name, air), summary=f"Adds Factory Ultra no-code scaffold: {preset.name}.", notes=["Safe starter hook; use visual reports to tune."])


def _factory_ultra_compat_move(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    seed = abs(sum(ord(c) for c in feature_id))
    state_no = 4300 + (seed % 1200)
    name = preset.name
    lname = (preset.name + " " + feature_id).lower()
    command = "x"
    if "fireball" in lname or "orb" in lname or "projectile" in lname: command = "~D, DF, F, x"
    elif "super" in lname or "finisher" in lname: command = "~D, DF, F, D, DF, F, z"
    elif "dash" in lname or "carry" in lname: command = "F, F, y"
    elif "anti" in lname or "launcher" in lname: command = "D, y"
    elif "guard" in lname or "breaker" in lname: command = "F, z"
    damage = 35 + (seed % 80)
    if "super" in lname or "finisher" in lname or "boss" in lname: damage += 120
    move_type = "projectile" if any(w in lname for w in ["fireball", "orb", "projectile", "screen control"]) else "attack"
    spec = _spec(name, feature_id[:28], command, state_no, damage=damage, frame_count=6 + (seed % 6), hit_frame=2 + (seed % 4), hit_box=(16, -84, 70 + (seed % 50), -18), sound=(5, seed % 8), ground_velocity=(-(3 + seed % 6), 0), air_velocity=(-3, -(4 + seed % 5)), move_type=move_type)
    pkg = _pack_from_specs(feature_id, preset.name, [spec], list(preset.beginner_notes))
    pkg.notes.append("Factory Ultra generated fallback move scaffold. Tune timing/hitboxes visually after install.")
    return pkg


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id.startswith("ultra_"):
        try:
            preset = get_preset(feature_id)
            if "docs" in preset.blocks:
                return _factory_ultra_compat_doc(feature_id, preset)
            if {"cmd", "cns", "air"}.intersection(set(preset.blocks)) == {"cmd", "cns", "air"} or ("cmd" in preset.blocks and "air" in preset.blocks):
                return _factory_ultra_compat_move(feature_id, preset)
            return _factory_ultra_compat_system(feature_id, preset)
        except Exception:
            pass
    return _FINAL_V26_PREV_BUILD_FEATURE_PACKAGE(feature_id)


# ---------------------------------------------------------------------------
# v3.1 Quality Lab no-code bank additions
# ---------------------------------------------------------------------------

_QUALITY_LAB_PRESETS: List[FeaturePreset] = [
    FeaturePreset('ql_advanced_project_audit_docs', 'Quality Lab advanced audit guide', 'Quality Lab', 'Beginner', 'Writes a non-coder guide explaining the advanced reference matrix: DEF, CMD, CNS, AIR, SFF, SND, HitDef, and next-step scoring.', ('docs',), tags=('quality', 'audit', 'beginner')),
    FeaturePreset('ql_searchable_index_docs', 'Searchable project index guide', 'Quality Lab', 'Beginner', 'Adds a guide for using the generated browser-based project index to find states, commands, sprites, sounds, and HitDefs.', ('docs',), tags=('quality', 'index')),
    FeaturePreset('ql_beginner_fix_plan_docs', 'What-to-fix-next guide', 'Quality Lab', 'Beginner', 'Adds a plain-English repair-order checklist so a beginner knows whether to fix files, commands, states, sprites, sounds, or balance first.', ('docs',), tags=('quality', 'planning')),
    FeaturePreset('ql_asset_swap_workflow_docs', 'Asset swap workflow guide', 'Quality Lab', 'Beginner', 'Adds a guide for replacing exported sprites/sounds without touching raw packed files by hand.', ('docs',), tags=('assets', 'beginner')),
    FeaturePreset('ql_alpha_clsn_workflow_docs', 'Alpha CLSN workflow guide', 'Quality Lab', 'Beginner', 'Explains how to use auto-generated body hitbox suggestions from visible sprite pixels, then review them in the CLSN Editor.', ('docs',), tags=('hitbox', 'clsn')),
    FeaturePreset('ql_move_cards_docs', 'Move cards tuning guide', 'Quality Lab', 'Beginner', 'Adds a guide for tuning generated moves from state cards: damage, hitflags, guardflags, sounds, exits, and animation links.', ('docs',), tags=('moves', 'tuning')),
    FeaturePreset('ql_animation_timing_docs', 'Animation timing guide', 'Quality Lab', 'Beginner', 'Adds a guide for reading AIR timing sheets and spotting actions that are too fast, too long, or empty.', ('docs',), tags=('animation', 'timing')),
    FeaturePreset('ql_backup_restore_docs', 'Backup / restore safety guide', 'Quality Lab', 'Beginner', 'Adds a safety guide for creating restore bundles before big no-code passes.', ('docs',), tags=('backup', 'safety')),
    FeaturePreset('ql_release_gate_docs', 'Release readiness gate guide', 'Quality Lab', 'Beginner', 'Adds a release gate checklist for audit score, missing refs, placeholders, move list, credits, and playtest notes.', ('docs',), tags=('release', 'qa')),
    FeaturePreset('ql_frame_tags_docs', 'Startup / active / recovery frame-tag guide', 'Quality Lab', 'Intermediate', 'Adds notes for labeling move frames so creators can balance attacks without reading raw CNS logic first.', ('docs',), tags=('frames', 'balance')),
    FeaturePreset('ql_sprite_axis_docs', 'Sprite axis alignment guide', 'Quality Lab', 'Beginner', 'Adds a guide for keeping feet/origin stable across sprites so animations do not jitter.', ('docs',), tags=('sprite', 'axis')),
    FeaturePreset('ql_sound_cue_docs', 'Sound cue audit guide', 'Quality Lab', 'Beginner', 'Adds a guide for mapping PlaySnd values to actual SND IDs and replacing silent placeholder WAVs.', ('docs',), tags=('sound', 'snd')),
    FeaturePreset('ql_palette_safety_docs', 'Palette swap safety guide', 'Quality Lab', 'Beginner', 'Adds a guide for palette variants, ACT files, palette sharing, and avoiding accidental color breakage.', ('docs',), tags=('palette', 'act')),
    FeaturePreset('ql_engine_test_loop_docs', 'In-engine test loop guide', 'Quality Lab', 'Beginner', 'Adds a quick loop for M.U.G.E.N launch, reproduce, edit, rebuild, retest, and package.', ('docs',), tags=('testing', 'mugen')),
    FeaturePreset('ql_controller_input_docs', 'Controller input cheat sheet', 'Quality Lab', 'Beginner', 'Adds a simple input mapping checklist for non-coders adding commands through the bank.', ('docs',), tags=('cmd', 'inputs')),
    FeaturePreset('ql_balance_budget_docs', 'Beginner balance budget guide', 'Quality Lab', 'Beginner', 'Adds suggested damage, stun, velocity, and meter ranges for starter characters.', ('docs',), tags=('balance', 'hitdef')),
    FeaturePreset('ql_accessibility_pack_docs', 'Accessibility polish checklist', 'Quality Lab', 'Beginner', 'Adds notes for readable flashes, reduced screen shake, sound separation, and player-facing documentation.', ('docs',), tags=('accessibility', 'polish')),
    FeaturePreset('ql_stage_camera_docs', 'Stage camera tuning checklist', 'Quality Lab', 'Intermediate', 'Adds stage/background tuning notes for zoffset, bounds, deltas, and image source tracking.', ('docs',), tags=('stage', 'camera')),
    FeaturePreset('ql_project_handoff_docs', 'Project handoff pack guide', 'Quality Lab', 'Beginner', 'Adds a guide for handing a character to another creator with docs, asset swap pack, reports, and backups.', ('docs',), tags=('handoff', 'docs')),
    FeaturePreset('ql_ff_parity_migration_docs', 'Fighter Factory migration checklist', 'Quality Lab', 'Beginner', 'Adds a workflow checklist for creators coming from Fighter Factory-style tools into MugenForge no-code workflows.', ('docs',), tags=('migration', 'workflow')),
    FeaturePreset('ql_hitbox_debug_overlay', 'Hitbox debug overlay notes', 'Quality Lab Systems', 'Beginner', 'Adds a State -2 debug clipboard hook that reminds creators what action/state/frame they are checking while reviewing hitboxes.', ('cns',), tags=('debug', 'clsn')),
    FeaturePreset('ql_balance_debug_overlay', 'Balance debug overlay notes', 'Quality Lab Systems', 'Beginner', 'Adds a State -2 debug hook showing life, power, hitcount, state, anim, and time for rough balance testing.', ('cns',), tags=('debug', 'balance')),
    FeaturePreset('ql_sound_debug_overlay', 'Sound cue debug notes', 'Quality Lab Systems', 'Beginner', 'Adds a State -2 clipboard note block for tracking planned sound groups while testing.', ('cns',), tags=('sound', 'debug')),
    FeaturePreset('ql_training_toggle_bank', 'Training toggle variable bank', 'Quality Lab Systems', 'Intermediate', 'Adds a readable variable-bank skeleton for toggling debug, hitbox, damage, AI, and dummy-test helpers.', ('cns',), tags=('training', 'debug')),
    FeaturePreset('ql_ai_test_router', 'AI smoke-test router', 'Quality Lab Systems', 'Intermediate', 'Adds a conservative AI smoke-test router that randomly chooses safe existing-ish states when AILevel is active.', ('cns',), tags=('ai', 'testing')),
    FeaturePreset('ql_placeholder_cleanup_docs', 'Placeholder cleanup guide', 'Quality Lab', 'Beginner', 'Adds a checklist to remove/rewrite placeholders before a public release.', ('docs',), tags=('release', 'placeholder')),
    FeaturePreset('ql_combo_trial_docs', 'Combo trial authoring guide', 'Quality Lab', 'Beginner', 'Adds a beginner-friendly combo trial planning worksheet.', ('docs',), tags=('combo', 'training')),
    FeaturePreset('ql_hitdef_recipe_docs', 'HitDef recipe cards', 'Quality Lab', 'Beginner', 'Adds readable HitDef recipes for light, medium, heavy, launcher, projectile, throw-like, and super hits.', ('docs',), tags=('hitdef', 'recipe')),
    FeaturePreset('ql_sprite_naming_docs', 'Smart sprite naming guide', 'Quality Lab', 'Beginner', 'Adds filename examples that the Smart Sprite Mapper can infer automatically.', ('docs',), tags=('sprites', 'naming')),
    FeaturePreset('ql_sound_naming_docs', 'Smart sound naming guide', 'Quality Lab', 'Beginner', 'Adds filename examples for WAV IDs such as 5_0.wav, sound_5_0.wav, and g5_s0.wav.', ('docs',), tags=('sounds', 'naming')),
    FeaturePreset('ql_credits_license_docs', 'Credits/license release guide', 'Quality Lab', 'Beginner', 'Adds a release-safe credits, permission, and source-art checklist.', ('docs',), tags=('license', 'credits')),
    FeaturePreset('ql_rc_smoke_test_docs', 'Release candidate smoke-test guide', 'Quality Lab', 'Beginner', 'Adds a short QA script for checking select.def entry, arcade launch, moves, hits, blocks, sounds, and no missing sprites.', ('docs',), tags=('release', 'qa')),
    FeaturePreset('ql_no_code_guardrails_docs', 'No-code guardrails guide', 'Quality Lab', 'Beginner', 'Adds reminders about what the tool can automate and what still needs taste: timing, feel, readability, and playtesting.', ('docs',), tags=('beginner', 'workflow')),
    FeaturePreset('ql_asset_manifest_docs', 'Asset manifest guide', 'Quality Lab', 'Beginner', 'Adds documentation for tracking sources, replacements, IDs, axes, palettes, and staged files.', ('docs',), tags=('assets', 'manifest')),
    FeaturePreset('ql_state_cleanup_docs', 'State cleanup guide', 'Quality Lab', 'Intermediate', 'Adds a checklist for duplicate states, missing exits, Ctrl handling, physics choices, and ChangeState fallbacks.', ('docs',), tags=('states', 'cleanup')),
    FeaturePreset('ql_command_cleanup_docs', 'Command cleanup guide', 'Quality Lab', 'Beginner', 'Adds a checklist for duplicate commands, time/buffer settings, and command naming.', ('docs',), tags=('commands', 'cleanup')),
]

for _preset in _QUALITY_LAB_PRESETS:
    if _preset.feature_id not in {p.feature_id for p in FEATURE_PRESETS}:
        FEATURE_PRESETS.append(_preset)

_QUALITY_BASE_BUILD_FEATURE_PACKAGE = build_feature_package
_QUALITY_IDS = {p.feature_id for p in _QUALITY_LAB_PRESETS}


def _quality_doc(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    title = preset.name
    stem = re.sub(r'[^A-Za-z0-9_\-]+', '_', title).strip('_').upper()
    body = f"""# {title}

Feature Bank ID: `{feature_id}`

## What this does

{preset.description}

## Beginner workflow

1. Run the matching Quality Lab button when available.
2. Read the generated Markdown/CSV/HTML output before changing raw code.
3. Fix project-breaking issues first: missing files, missing commands, missing StateDefs, missing AIR actions, missing sprites, and missing sounds.
4. Tune fun/feel second: timing, hitboxes, damage, pushback, sound timing, and visual readability.
5. Make a backup before generated-code or asset rebuild passes.

## Where to look in MugenForge

- Quality Lab tab for audits, move cards, timing sheets, asset swap packs, auto-CLSN suggestions, backups, and beginner fix plans.
- Feature Bank for one-click code scaffolding.
- Factory Max for broader project setup and release packaging.
- CLSN Editor and Animation Player for frame-by-frame feel.

## Notes

This is a guide/checklist preset. It intentionally writes docs instead of silently mutating gameplay code.
"""
    return FeaturePackage(
        feature_id=feature_id,
        name=title,
        extra_files={f'quality_lab/feature_guides/{stem}.md': body},
        summary=f'Writes Quality Lab guide: {title}.',
        notes=['Safe for beginners: this preset writes documentation/checklists only.']
    )


def _quality_system(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    title = preset.name
    if feature_id == 'ql_hitbox_debug_overlay':
        cns = """; Quality Lab hitbox review overlay
[State -2, Quality Lab hitbox review]
type = DisplayToClipboard
trigger1 = 1
text = "QL hitbox check | state=%d anim=%d elem=%d time=%d ctrl=%d"
params = stateno, anim, animelemno(0), time, ctrl
ignorehitpause = 1
"""
    elif feature_id == 'ql_balance_debug_overlay':
        cns = """; Quality Lab balance review overlay
[State -2, Quality Lab balance review]
type = DisplayToClipboard
trigger1 = 1
text = "QL balance | life=%d power=%d p2life=%d hitcount=%d state=%d anim=%d time=%d"
params = life, power, enemynear,life, hitcount, stateno, anim, time
ignorehitpause = 1
"""
    elif feature_id == 'ql_sound_debug_overlay':
        cns = """; Quality Lab sound cue note overlay
[State -2, Quality Lab sound cue note]
type = AppendToClipboard
trigger1 = 1
text = "\nSound groups idea: 0 system | 5 attacks | 6 specials | 7 supers | 10 voice"
ignorehitpause = 1
"""
    elif feature_id == 'ql_training_toggle_bank':
        cns = """; Quality Lab training/debug variable bank
[State -2, Quality Lab debug toggles init]
type = VarSet
trigger1 = RoundState < 2
v = 80
value = 1 ; debug overlay enabled
ignorehitpause = 1

[State -2, Quality Lab helper mode labels]
type = AppendToClipboard
trigger1 = Var(80) = 1
text = "\nQL toggles: v80 debug | v81 hitbox | v82 damage | v83 dummy | v84 AI smoke"
ignorehitpause = 1
"""
    else:
        cns = """; Quality Lab AI smoke-test router
[State -2, Quality Lab AI smoke test]
type = ChangeState
triggerall = AILevel > 0
triggerall = ctrl
triggerall = RoundState = 2
trigger1 = P2BodyDist X > 120
trigger1 = Random < 18
value = 1000

[State -2, Quality Lab AI close-range smoke test]
type = ChangeState
triggerall = AILevel > 0
triggerall = ctrl
triggerall = RoundState = 2
trigger1 = P2BodyDist X <= 60
trigger1 = Random < 18
value = 200
"""
    return FeaturePackage(feature_id=feature_id, name=title, cns_block=_wrap(feature_id, title, cns), summary=f'Adds Quality Lab system helper: {title}.', notes=['Use during testing, then disable or remove before final release if you do not want debug clipboard output.'])


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in _QUALITY_IDS:
        return _QUALITY_BASE_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id.endswith('_docs') or feature_id in {
        'ql_advanced_project_audit_docs', 'ql_searchable_index_docs', 'ql_beginner_fix_plan_docs',
        'ql_asset_swap_workflow_docs', 'ql_alpha_clsn_workflow_docs', 'ql_move_cards_docs',
        'ql_animation_timing_docs', 'ql_backup_restore_docs', 'ql_release_gate_docs',
        'ql_frame_tags_docs', 'ql_sprite_axis_docs', 'ql_sound_cue_docs', 'ql_palette_safety_docs',
        'ql_engine_test_loop_docs', 'ql_controller_input_docs', 'ql_balance_budget_docs',
        'ql_accessibility_pack_docs', 'ql_stage_camera_docs', 'ql_project_handoff_docs',
        'ql_ff_parity_migration_docs'
    }:
        return _quality_doc(feature_id, preset)
    return _quality_system(feature_id, preset)

KIT_PRESETS.update({
    'Quality Lab Beginner Safety Kit': [
        'ql_backup_restore_docs', 'ql_beginner_fix_plan_docs', 'ql_advanced_project_audit_docs',
        'ql_searchable_index_docs', 'ql_release_gate_docs', 'ql_no_code_guardrails_docs',
    ],
    'Quality Lab Asset Polish Kit': [
        'ql_asset_swap_workflow_docs', 'ql_alpha_clsn_workflow_docs', 'ql_sprite_axis_docs',
        'ql_palette_safety_docs', 'ql_sound_cue_docs', 'ql_asset_manifest_docs',
    ],
    'Quality Lab Gameplay Tuning Kit': [
        'ql_move_cards_docs', 'ql_animation_timing_docs', 'ql_frame_tags_docs', 'ql_balance_budget_docs',
        'ql_hitdef_recipe_docs', 'ql_hitbox_debug_overlay', 'ql_balance_debug_overlay',
    ],
    'Quality Lab Release QA Kit': [
        'ql_rc_smoke_test_docs', 'ql_release_gate_docs', 'ql_placeholder_cleanup_docs',
        'ql_credits_license_docs', 'ql_project_handoff_docs', 'ql_engine_test_loop_docs',
    ],
})

KIT_PRESETS['Full No-Code Creator Pack'] = list(dict.fromkeys(
    KIT_PRESETS.get('Full No-Code Creator Pack', [])
    + KIT_PRESETS['Quality Lab Beginner Safety Kit']
    + KIT_PRESETS['Quality Lab Asset Polish Kit']
    + KIT_PRESETS['Quality Lab Gameplay Tuning Kit']
))



# ---------------------------------------------------------------------------
# v3.2 Rescue Lab / Factory Complete no-code bank additions
# ---------------------------------------------------------------------------
_RESCUE_LAB_PRESETS: List[FeaturePreset] = [
    FeaturePreset('rescue_embedded_scan_docs', 'Embedded asset scanner guide', 'Rescue Lab', 'Beginner', 'Explains how to scan unsupported SFF/SND/binary files for embedded PNG, PCX, and WAV payloads without writing code.', ('docs',), tags=('rescue', 'assets', 'sff', 'snd')),
    FeaturePreset('rescue_contact_sheet_docs', 'Recovery contact sheet guide', 'Rescue Lab', 'Beginner', 'Explains how to review extracted sprite candidates visually before rebuilding a starter SFF.', ('docs',), tags=('rescue', 'sprites')),
    FeaturePreset('rescue_air_mapping_docs', 'AIR reference mapping guide', 'Rescue Lab', 'Beginner', 'Explains how recovered images can be mapped to AIR group/image IDs so non-coders can continue with Animation Player and CLSN Editor.', ('docs',), tags=('rescue', 'air')),
    FeaturePreset('rescue_sff_rebuild_docs', 'Recovered SFF v1 rebuild guide', 'Rescue Lab', 'Beginner', 'Explains the safe difference between rebuilding a fresh starter SFF v1 and byte-perfect SFF v2 editing.', ('docs',), tags=('rescue', 'sff')),
    FeaturePreset('rescue_audio_recovery_docs', 'Recovered sound bank guide', 'Rescue Lab', 'Beginner', 'Explains how to identify recovered WAV files and turn them into a usable sound manifest/cue sheet.', ('docs',), tags=('rescue', 'sound')),
    FeaturePreset('rescue_source_art_handoff_docs', 'Source art handoff checklist', 'Rescue Lab', 'Beginner', 'Creates a checklist for replacing recovered assets with clean source art, credits, and naming conventions.', ('docs',), tags=('rescue', 'handoff')),
    FeaturePreset('rescue_migration_plan_docs', 'Old character migration plan', 'Rescue Lab', 'Beginner', 'Creates a beginner migration plan for moving an older/unknown character into a clean MugenForge workflow.', ('docs',), tags=('migration', 'beginner')),
    FeaturePreset('factory_complete_route_docs', 'Factory Complete beginner route', 'Factory Complete', 'Beginner', 'Writes a recommended order for beginners: Creator OS, Factory Ultra, Quality Lab, Rescue Lab, then release packaging.', ('docs',), tags=('workflow', 'beginner')),
    FeaturePreset('factory_complete_safety_docs', 'Factory Complete safety rules', 'Factory Complete', 'Beginner', 'Writes simple backup, restore, and generated-code safety rules for non-coders.', ('docs',), tags=('safety', 'backup')),
    FeaturePreset('factory_complete_asset_policy_docs', 'Asset source and permission policy', 'Factory Complete', 'Beginner', 'Creates a plain-English checklist for source art, sound permission, credits, and placeholder cleanup.', ('docs',), tags=('credits', 'release')),
    FeaturePreset('factory_complete_beginner_debug_hook', 'Beginner debug hook', 'Factory Complete Systems', 'Beginner', 'Adds a safe clipboard overlay that points the creator to the current state/action/frame while testing.', ('cns',), tags=('debug', 'testing')),
    FeaturePreset('factory_complete_asset_missing_hook', 'Asset missing reminder hook', 'Factory Complete Systems', 'Beginner', 'Adds a visible in-engine reminder that placeholder sprites/sounds must be replaced before public release.', ('cns',), tags=('placeholder', 'release')),
    FeaturePreset('factory_complete_tuning_knobs_hook', 'Tuning knob variable bank', 'Factory Complete Systems', 'Intermediate', 'Adds readable variable placeholders for damage, pushback, hitpause, AI, FX intensity, and accessibility toggles.', ('cns',), tags=('tuning', 'variables')),
]

for _preset in _RESCUE_LAB_PRESETS:
    if _preset.feature_id not in {p.feature_id for p in FEATURE_PRESETS}:
        FEATURE_PRESETS.append(_preset)

_RESCUE_BASE_BUILD_FEATURE_PACKAGE = build_feature_package
_RESCUE_IDS = {p.feature_id for p in _RESCUE_LAB_PRESETS}


def _rescue_doc_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    stem = re.sub(r'[^A-Za-z0-9_\-]+', '_', preset.name).strip('_').upper()
    body = f"""# {preset.name}

Feature Bank ID: `{feature_id}`

## What this is for

{preset.description}

## No-code workflow

1. Make a backup or restore bundle before heavy edits.
2. Use Creator OS / Factory Ultra for broad setup.
3. Use Quality Lab to find what is broken.
4. Use Rescue Lab only when packed assets or unsupported binaries block progress.
5. Replace placeholder/recovered art and sound with clean source assets before release.

## Where this lives in MugenForge

- **Rescue Lab** for embedded PNG/PCX/WAV scanning, recovery manifests, contact sheets, and recovered SFF v1 builds.
- **Quality Lab** for plain-English fix plans and audits.
- **Animation Player / CLSN Editor** for visual tuning after assets are recovered.
- **Factory Ultra / Creator OS** for beginner-facing production routes.

## Important limitation

Recovery tools are practical creator helpers. They do not claim byte-perfect SFF v2 mutation or ownership/permission over recovered assets.
"""
    return FeaturePackage(feature_id=feature_id, name=preset.name, extra_files={f'docs/RESCUE_LAB_{stem}.md': body}, summary=f'Writes Rescue/Factory Complete guide: {preset.name}.', notes=['Documentation-only preset; safe for beginners.'])


def _rescue_system_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    if feature_id == 'factory_complete_beginner_debug_hook':
        cns = """; Factory Complete beginner debug hook
[State -2, Factory Complete current context]
type = DisplayToClipboard
trigger1 = 1
text = "Factory Complete | state=%d anim=%d elem=%d time=%d ctrl=%d power=%d"
params = stateno, anim, animelemno(0), time, ctrl, power
ignorehitpause = 1
"""
    elif feature_id == 'factory_complete_asset_missing_hook':
        cns = """; Factory Complete placeholder asset reminder
[State -2, Factory Complete placeholder reminder]
type = AppendToClipboard
trigger1 = RoundState = 2
trigger1 = Time % 120 = 0
text = "\nReminder: run Quality Lab/Rescue Lab and replace placeholder sprites/sounds before release."
ignorehitpause = 1
"""
    else:
        cns = """; Factory Complete creator tuning knobs
[State -2, Factory Complete tuning defaults]
type = VarSet
trigger1 = RoundState < 2
v = 90
value = 100 ; damage percent helper
ignorehitpause = 1

[State -2, Factory Complete tuning notes]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while tuning
text = "\nTuning vars: v90 damage%, v91 pushback%, v92 hitpause%, v93 FX intensity, v94 accessibility mode"
ignorehitpause = 1
"""
    return FeaturePackage(feature_id=feature_id, name=preset.name, cns_block=_wrap(feature_id, preset.name, cns), summary=f'Adds Factory Complete helper: {preset.name}.', notes=['Testing/helper scaffold. Disable debug output before final release if desired.'])


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in _RESCUE_IDS:
        return _RESCUE_BASE_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if 'docs' in preset.blocks:
        return _rescue_doc_package(feature_id, preset)
    return _rescue_system_package(feature_id, preset)

KIT_PRESETS.update({
    'Rescue Lab Beginner Recovery Kit': [
        'rescue_embedded_scan_docs', 'rescue_contact_sheet_docs', 'rescue_air_mapping_docs',
        'rescue_sff_rebuild_docs', 'rescue_audio_recovery_docs', 'rescue_source_art_handoff_docs',
        'rescue_migration_plan_docs',
    ],
    'Factory Complete Beginner Safety Kit': [
        'factory_complete_route_docs', 'factory_complete_safety_docs', 'factory_complete_asset_policy_docs',
        'factory_complete_beginner_debug_hook', 'factory_complete_asset_missing_hook', 'factory_complete_tuning_knobs_hook',
    ],
})
KIT_PRESETS['Full No-Code Creator Pack'] = list(dict.fromkeys(
    KIT_PRESETS.get('Full No-Code Creator Pack', [])
    + KIT_PRESETS['Rescue Lab Beginner Recovery Kit']
    + KIT_PRESETS['Factory Complete Beginner Safety Kit']
))

# ---------------------------------------------------------------------------
# v3.2 Creator Hub expansion: more no-code, beginner-facing presets.
# These are intentionally safe defaults. Many write docs/checklists; selected
# debug helpers write conservative State -2 clipboard systems with Feature IDs.
# ---------------------------------------------------------------------------

_CREATOR_HUB_PRESETS = [
    ('ch_creator_dashboard_docs', 'Creator dashboard guide', 'Creator Hub', 'Beginner', 'Explains the dashboard, task board, and non-coder workflow.'),
    ('ch_task_board_docs', 'Kanban task board guide', 'Creator Hub', 'Beginner', 'Shows how to use high/medium/low cards as a production plan.'),
    ('ch_input_conflict_docs', 'Input conflict guide', 'Creator Hub', 'Beginner', 'Plain-English command overlap and input priority guide.'),
    ('ch_balance_autotune_docs', 'Balance autotune guide', 'Creator Hub', 'Beginner', 'Damage, hit-pause, velocity, guardflag, and risk/reward tuning guide.'),
    ('ch_combo_trial_docs', 'Combo trial authoring guide', 'Creator Hub', 'Beginner', 'How to turn generated combo trials into actual practice missions.'),
    ('ch_asset_request_docs', 'Asset request handoff guide', 'Creator Hub', 'Beginner', 'How to hand sprite/sound request CSV files to an artist or sound designer.'),
    ('ch_controller_map_docs', 'Controller map guide', 'Creator Hub', 'Beginner', 'How to write a player-facing move list from CMD commands.'),
    ('ch_release_website_docs', 'Release website guide', 'Creator Hub', 'Beginner', 'Checklist for screenshots, install notes, credits, and release pages.'),
    ('ch_patch_macro_docs', 'Patch macro bank guide', 'Creator Hub', 'Beginner', 'Explains how no-code macros map to CMD/CNS/AIR edits behind the scenes.'),
    ('ch_artist_brief_docs', 'Artist brief template', 'Production', 'Beginner', 'Writes a template for commissioning or organizing character art.'),
    ('ch_sound_brief_docs', 'Sound brief template', 'Production', 'Beginner', 'Writes a template for attack, voice, hit, guard, UI, and round-flow sound requests.'),
    ('ch_voice_script_docs', 'Voice script template', 'Production', 'Beginner', 'Writes a character voice script bank for intros, attacks, hurts, wins, and losses.'),
    ('ch_palette_plan_docs', 'Palette/costume plan', 'Production', 'Beginner', 'Plan palette variants, costume naming, and accessibility-safe color contrast.'),
    ('ch_stage_match_docs', 'Stage match plan', 'Production', 'Beginner', 'Plan a matching stage, music, camera feel, and background story.'),
    ('ch_move_identity_docs', 'Move identity worksheet', 'Design', 'Beginner', 'Define what each move is for: poke, anti-air, punish, mixup, mobility, or resource spend.'),
    ('ch_archetype_mix_docs', 'Archetype mixer worksheet', 'Design', 'Beginner', 'Blend rushdown, zoner, grappler, boss, anime, and footsies ideas without code.'),
    ('ch_risk_reward_docs', 'Risk/reward worksheet', 'Design', 'Beginner', 'Avoid overpowered moves by tying reward to startup, range, recovery, meter, or spacing.'),
    ('ch_meter_economy_docs', 'Meter economy worksheet', 'Design', 'Intermediate', 'Plan meter gain, EX costs, supers, installs, and comeback tools.'),
    ('ch_neutral_game_docs', 'Neutral game worksheet', 'Design', 'Beginner', 'Plan pokes, whiff punish tools, anti-air, movement, and projectile answers.'),
    ('ch_defense_flow_docs', 'Defense flow worksheet', 'Design', 'Beginner', 'Plan guard, parry, pushblock, roll, burst, counter, and escape options.'),
    ('ch_ai_personality_docs', 'AI personality worksheet', 'AI', 'Beginner', 'Plan easy/normal/hard/boss AI personality in plain English before code.'),
    ('ch_boss_phase_docs', 'Boss phase worksheet', 'AI', 'Intermediate', 'Plan boss phases, desperation, pattern tells, and fairness.'),
    ('ch_training_mode_docs', 'Training mode checklist', 'Testing', 'Beginner', 'Checklist for damage display, input display, dummy behavior, and hitbox review.'),
    ('ch_accessibility_docs', 'Accessibility checklist', 'Release', 'Beginner', 'Readability, flashing effects, palette contrast, input difficulty, and documentation checklist.'),
    ('ch_readme_install_docs', 'Install README template', 'Release', 'Beginner', 'Writes beginner-friendly install/update/uninstall instructions.'),
    ('ch_credits_license_docs', 'Credits/license template', 'Release', 'Beginner', 'Tracks borrowed assets, original assets, AI-assisted material, and permissions.'),
    ('ch_update_log_docs', 'Update log template', 'Release', 'Beginner', 'Simple changelog template for balancing updates and bug fixes.'),
    ('ch_playtest_form_docs', 'Playtest feedback form', 'Testing', 'Beginner', 'Questions testers can answer without knowing M.U.G.E.N code.'),
    ('ch_bug_report_form_docs', 'Bug report form', 'Testing', 'Beginner', 'Standard bug report format with state, animation, input, position, and reproducible steps.'),
    ('ch_release_gate_docs', 'Release gate checklist', 'Release', 'Beginner', 'Final no-placeholder, no-missing-reference, credits, zip, and smoke-test checklist.'),
    ('ch_auto_meter_overlay', 'Creator Hub meter/debug overlay', 'Testing Helpers', 'Beginner', 'Adds a clipboard overlay for life/power/state/animation review.'),
    ('ch_input_echo_overlay', 'Creator Hub input echo overlay', 'Testing Helpers', 'Beginner', 'Adds a simple current command/state clipboard hint for testing.'),
    ('ch_combo_review_overlay', 'Creator Hub combo review overlay', 'Testing Helpers', 'Beginner', 'Adds hitcount/damage review text to the clipboard.'),
    ('ch_position_review_overlay', 'Creator Hub spacing review overlay', 'Testing Helpers', 'Beginner', 'Adds distance/velocity review text to the clipboard.'),
    ('ch_ai_smoke_router', 'Creator Hub AI smoke router', 'Testing Helpers', 'Intermediate', 'Adds very conservative AI smoke-test routing for checking if moves can activate.'),
    ('ch_round_flow_overlay', 'Creator Hub round flow overlay', 'Testing Helpers', 'Beginner', 'Adds roundstate/status debug notes for intros/wins/losses testing.'),
    ('ch_art_gap_overlay', 'Creator Hub art gap reminder', 'Testing Helpers', 'Beginner', 'Adds placeholder-art reminder text while testing.'),
    ('ch_sound_gap_overlay', 'Creator Hub sound gap reminder', 'Testing Helpers', 'Beginner', 'Adds sound-cue reminder text while testing.'),
    ('ch_balance_lab_overlay', 'Creator Hub balance lab overlay', 'Testing Helpers', 'Beginner', 'Adds a compact balance review overlay for playtest sessions.'),
    ('ch_release_candidate_overlay', 'Creator Hub release-candidate overlay', 'Testing Helpers', 'Beginner', 'Adds final QA clipboard hints for release-candidate testing.'),
]

_CREATOR_HUB_IDS = {item[0] for item in _CREATOR_HUB_PRESETS}
for _fid, _name, _cat, _diff, _desc in _CREATOR_HUB_PRESETS:
    if _fid not in {p.feature_id for p in FEATURE_PRESETS}:
        FEATURE_PRESETS.append(FeaturePreset(_fid, _name, _cat, _diff, _desc, ('cns',) if _fid.endswith('_overlay') or _fid.endswith('_router') else ('docs',), tags=('creator-hub', 'no-code')))

_CREATOR_HUB_PREV_BUILD_FEATURE_PACKAGE = build_feature_package  # type: ignore[name-defined]


def _creator_hub_doc(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    stem = re.sub(r'[^A-Za-z0-9_\-]+', '_', feature_id).strip('_')
    body = f"""# {preset.name}

Category: {preset.category}  
Difficulty: {preset.difficulty}

{preset.description}

## No-code purpose

This preset is part of the Creator Hub bank. It is designed for users who do not want to hand-edit CMD/CNS/AIR files. Use it as a worksheet, checklist, or production guide while the app handles the repetitive code/report generation.

## Recommended workflow

1. Run One-Click Creator Hub Pass.
2. Open the dashboard/task board it creates.
3. Use Feature Bank/Move Wizard for move code.
4. Use Sprite Lab/Sound tools for assets.
5. Run Quality Lab before packaging.

## Safety note

This doc preset writes files only. It does not mutate gameplay code.
"""
    return FeaturePackage(feature_id=feature_id, name=preset.name, extra_files={f'creator_hub/feature_guides/{stem}.md': body}, summary=f'Writes Creator Hub guide: {preset.name}.', notes=['Safe documentation preset.'])


def _creator_hub_system(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    if feature_id == 'ch_auto_meter_overlay':
        cns = '''; Creator Hub meter/debug overlay
[State -2, Creator Hub meter overlay]
type = DisplayToClipboard
trigger1 = 1
text = "CH meter | life=%d power=%d state=%d anim=%d time=%d ctrl=%d"
params = life, power, stateno, anim, time, ctrl
ignorehitpause = 1
'''
    elif feature_id == 'ch_input_echo_overlay':
        cns = '''; Creator Hub input echo overlay
[State -2, Creator Hub input echo]
type = AppendToClipboard
trigger1 = 1
text = "\nCH input/state test: state=%d anim=%d elem=%d"
params = stateno, anim, animelemno(0)
ignorehitpause = 1
'''
    elif feature_id == 'ch_combo_review_overlay':
        cns = '''; Creator Hub combo review overlay
[State -2, Creator Hub combo review]
type = AppendToClipboard
trigger1 = MoveHit || MoveGuarded || NumTarget
text = "\nCH combo: hitcount=%d power=%d targetdist=%d"
params = hitcount, power, P2BodyDist X
ignorehitpause = 1
'''
    elif feature_id == 'ch_position_review_overlay':
        cns = '''; Creator Hub spacing review overlay
[State -2, Creator Hub spacing]
type = AppendToClipboard
trigger1 = 1
text = "\nCH spacing: p2dist=%d vel=(%d,%d) pos=(%d,%d)"
params = P2BodyDist X, Vel X, Vel Y, Pos X, Pos Y
ignorehitpause = 1
'''
    elif feature_id == 'ch_ai_smoke_router':
        cns = '''; Creator Hub AI smoke-test router
[State -2, Creator Hub AI far smoke]
type = ChangeState
triggerall = AILevel > 0
triggerall = RoundState = 2
triggerall = ctrl
trigger1 = P2BodyDist X > 120
trigger1 = Random < 12
value = 1000

[State -2, Creator Hub AI close smoke]
type = ChangeState
triggerall = AILevel > 0
triggerall = RoundState = 2
triggerall = ctrl
trigger1 = P2BodyDist X <= 70
trigger1 = Random < 12
value = 200
'''
    elif feature_id == 'ch_round_flow_overlay':
        cns = '''; Creator Hub round flow overlay
[State -2, Creator Hub round flow]
type = AppendToClipboard
trigger1 = 1
text = "\nCH round: roundstate=%d alive=%d win=%d lose=%d"
params = RoundState, Alive, Win, Lose
ignorehitpause = 1
'''
    elif feature_id == 'ch_art_gap_overlay':
        cns = '''; Creator Hub art gap reminder
[State -2, Creator Hub art note]
type = AppendToClipboard
trigger1 = Time % 120 = 0
text = "\nCH art QA: check placeholders, axes, CLSN, and missing AIR sprites."
ignorehitpause = 1
'''
    elif feature_id == 'ch_sound_gap_overlay':
        cns = '''; Creator Hub sound gap reminder
[State -2, Creator Hub sound note]
type = AppendToClipboard
trigger1 = Time % 120 = 0
text = "\nCH sound QA: confirm attack, guard, voice, landing, jump, and super cues."
ignorehitpause = 1
'''
    elif feature_id == 'ch_balance_lab_overlay':
        cns = '''; Creator Hub balance lab overlay
[State -2, Creator Hub balance lab]
type = AppendToClipboard
trigger1 = 1
text = "\nCH balance: life=%d p2life=%d power=%d hitcount=%d damage-check manually"
params = life, enemynear,life, power, hitcount
ignorehitpause = 1
'''
    else:
        cns = '''; Creator Hub release-candidate overlay
[State -2, Creator Hub release QA]
type = AppendToClipboard
trigger1 = Time % 180 = 0
text = "\nCH release QA: no placeholders, no missing refs, docs/credits ready, zip smoke-tested."
ignorehitpause = 1
'''
    return FeaturePackage(feature_id=feature_id, name=preset.name, cns_block=_wrap(feature_id, preset.name, cns), summary=f'Adds Creator Hub testing helper: {preset.name}.', notes=['Use during testing; remove before final release if you do not want clipboard debug text.'])


def build_feature_package(feature_id: str) -> FeaturePackage:  # type: ignore[override]
    if feature_id not in _CREATOR_HUB_IDS:
        return _CREATOR_HUB_PREV_BUILD_FEATURE_PACKAGE(feature_id)
    preset = get_preset(feature_id)
    if feature_id.endswith('_overlay') or feature_id.endswith('_router'):
        return _creator_hub_system(feature_id, preset)
    return _creator_hub_doc(feature_id, preset)


KIT_PRESETS.update({
    'Creator Hub Beginner Command Center Kit': [
        'ch_creator_dashboard_docs', 'ch_task_board_docs', 'ch_patch_macro_docs', 'ch_no_code_recipe_docs' if False else 'ch_controller_map_docs',
        'ch_input_conflict_docs', 'ch_balance_autotune_docs', 'ch_combo_trial_docs',
    ],
    'Creator Hub Production Handoff Kit': [
        'ch_asset_request_docs', 'ch_artist_brief_docs', 'ch_sound_brief_docs', 'ch_voice_script_docs',
        'ch_palette_plan_docs', 'ch_stage_match_docs', 'ch_credits_license_docs',
    ],
    'Creator Hub Playtest Kit': [
        'ch_training_mode_docs', 'ch_playtest_form_docs', 'ch_bug_report_form_docs',
        'ch_auto_meter_overlay', 'ch_input_echo_overlay', 'ch_combo_review_overlay', 'ch_position_review_overlay',
    ],
    'Creator Hub Release Kit': [
        'ch_release_website_docs', 'ch_readme_install_docs', 'ch_update_log_docs', 'ch_release_gate_docs',
        'ch_accessibility_docs', 'ch_release_candidate_overlay',
    ],
    'Creator Hub Design Bible Kit': [
        'ch_move_identity_docs', 'ch_archetype_mix_docs', 'ch_risk_reward_docs', 'ch_meter_economy_docs',
        'ch_neutral_game_docs', 'ch_defense_flow_docs', 'ch_ai_personality_docs', 'ch_boss_phase_docs',
    ],
})

KIT_PRESETS['Full No-Code Creator Pack'] = list(dict.fromkeys(
    KIT_PRESETS.get('Full No-Code Creator Pack', [])
    + KIT_PRESETS['Creator Hub Beginner Command Center Kit']
    + KIT_PRESETS['Creator Hub Production Handoff Kit']
    + KIT_PRESETS['Creator Hub Playtest Kit']
    + KIT_PRESETS['Creator Hub Release Kit']
))
