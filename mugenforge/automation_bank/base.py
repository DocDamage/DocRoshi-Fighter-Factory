from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Dict, Iterable, List, Optional, Sequence

from ..parsers import parse_def, read_text_safely, write_text_safely, scan_project, COMMON_ANIMS
from ..move_wizard import (
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


def available_presets() -> List[FeaturePreset]:
    from .presets import FEATURE_PRESETS
    return list(FEATURE_PRESETS)


def get_preset(feature_id: str) -> FeaturePreset:
    from .presets import FEATURE_PRESETS
    for preset in FEATURE_PRESETS:
        if preset.feature_id == feature_id:
            return preset
    raise KeyError(feature_id)


def preset_display_list() -> List[str]:
    from .presets import FEATURE_PRESETS
    return [f"{p.category} :: {p.name}" for p in FEATURE_PRESETS]


def preset_by_display(display: str) -> FeaturePreset:
    from .presets import FEATURE_PRESETS
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
    # Note: build_feature_package will be imported from package root
    from . import build_feature_package
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
    from .presets import FEATURE_PRESETS
    data = {
        "description": "Edit this file to plan your character without touching M.U.G.E.N code. MugenForge built-in Feature Bank uses internal presets; this file is for your notes/custom plan.",
        "planned_features": [p.feature_id for p in FEATURE_PRESETS],
        "button_map": {"x": "light punch", "y": "medium punch", "z": "heavy punch", "a": "light kick", "b": "medium kick", "c": "heavy kick", "s": "taunt/start"},
        "feature_notes": {p.feature_id: p.description for p in FEATURE_PRESETS},
    }
    out = Path(root) / "mugenforge_feature_bank_template.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def kit_names() -> List[str]:
    from .presets import KIT_PRESETS
    return list(KIT_PRESETS.keys())


def kit_preview_text(kit_name: str) -> str:
    from .presets import KIT_PRESETS
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
    from .presets import KIT_PRESETS
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
    result.created_files.append("spritesheets/" + out.name)
    result.created_files.append("spritesheets/" + plan_path.name)
    return result


def feature_bank_stats() -> Dict[str, object]:
    from .presets import FEATURE_PRESETS, KIT_PRESETS
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
