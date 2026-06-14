from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .base import (
    FeaturePackage,
    FeaturePreset,
    MoveWizardSpec,
    _pack_from_specs,
    _spec,
    _wrap,
    get_preset,
)


def _route_doc(name: str, steps: Sequence[str], notes: Sequence[str]) -> str:
    lines = [
        f"# {name}",
        "",
        "This automation pack writes playable starter scaffolding. Replace placeholder art/sounds and tune timings in-engine before release.",
        "",
        "## Suggested route",
    ]
    lines += [f"{idx}. `{step}`" for idx, step in enumerate(steps, start=1)]
    if notes:
        lines += ["", "## Tuning notes"] + [f"- {note}" for note in notes]
    return "\n".join(lines).rstrip() + "\n"


def _cancel_system(feature_id: str, routes: Sequence[tuple[int, str, int, int]]) -> str:
    lines: List[str] = [
        "; MugenForge move automation cancel route helpers",
        "; These controllers are conservative starter routes. Tune AnimElem windows after playtesting.",
    ]
    for state_no, command_name, next_state, earliest_elem in routes:
        lines += [
            "",
            f"[State {state_no}, MugenForge cancel to {next_state}]",
            "type = ChangeState",
            f"trigger1 = command = \"{command_name}\"",
            f"trigger1 = AnimElem >= {earliest_elem}",
            f"value = {next_state}",
        ]
    return _wrap(feature_id + "_cancel_routes", "Cancel Route Helpers", "\n".join(lines) + "\n")


def _docs_file(feature_id: str, preset: FeaturePreset, steps: Sequence[str], notes: Sequence[str]) -> Dict[str, str]:
    safe = feature_id.replace("/", "_")
    return {f"docs/move_automation/{safe}.md": _route_doc(preset.name, steps, notes)}


def _pack(
    feature_id: str,
    specs: Sequence[MoveWizardSpec],
    steps: Sequence[str],
    notes: Sequence[str],
    cancels: Sequence[tuple[int, str, int, int]] = (),
) -> FeaturePackage:
    preset = get_preset(feature_id)
    package = _pack_from_specs(feature_id, preset.name, specs, list(preset.beginner_notes))
    if cancels:
        package.cns_block += _cancel_system(feature_id, cancels)
    package.extra_files.update(_docs_file(feature_id, preset, steps, notes))
    package.summary += "\n\nMove automation pack includes a beginner route guide and conservative cancel/tuning notes."
    return package


MOVE_AUTOMATION_SPECS: Dict[str, Sequence[MoveWizardSpec]] = {
    "auto_starter_normals_route": [
        _spec("Auto Jab", "auto_jab", "x", 260, damage=22, frame_count=4, hit_frame=2, hit_box=(14, -68, 48, -42), sound=(5, 0)),
        _spec("Auto Mid Kick", "auto_mid_kick", "b", 270, damage=42, frame_count=5, hit_frame=3, hit_box=(22, -54, 74, -18), sound=(5, 1)),
        _spec("Auto Sweep", "auto_sweep", "D, c", 280, damage=58, frame_count=7, hit_frame=4, hit_box=(20, -24, 92, -4), body_box=(-24, -58, 24, 0), sound=(5, 2), ground_velocity=(-7, -2), air_velocity=(-4, -4)),
    ],
    "auto_beginner_cancel_route": [
        _spec("Route Jab", "route_jab", "x", 360, damage=20, frame_count=4, hit_frame=2, hit_box=(14, -68, 48, -42), sound=(5, 0)),
        _spec("Route Medium", "route_medium", "y", 370, damage=38, frame_count=5, hit_frame=3, hit_box=(18, -74, 60, -38), sound=(5, 1)),
        _spec("Route Launcher", "route_launcher", "D, z", 380, damage=62, frame_count=7, hit_frame=3, hit_box=(12, -92, 56, -28), sound=(5, 4), ground_velocity=(-2, -8), air_velocity=(-2, -9)),
        _spec("Route Fireball Ender", "route_fireball", "~D, DF, F, x", 1390, move_type="projectile", damage=50, frame_count=6, hit_frame=4, hit_box=(22, -70, 70, -34), sound=(5, 3), ground_velocity=(-5, 0)),
    ],
    "auto_rushdown_move_suite": [
        _spec("Rush Jab", "rush_jab", "x", 460, damage=20, frame_count=3, ticks=3, hit_frame=2, hit_box=(14, -68, 48, -42), sound=(5, 0)),
        _spec("Rush Step Kick", "rush_step_kick", "F, b", 470, damage=48, frame_count=5, ticks=4, hit_frame=3, hit_box=(24, -58, 84, -18), sound=(5, 1), ground_velocity=(-4, 0)),
        _spec("Rush Slide", "rush_slide", "~D, DF, F, a", 1480, damage=58, frame_count=7, hit_frame=4, hit_box=(18, -30, 92, -4), body_box=(-24, -46, 26, 0), sound=(5, 2), ground_velocity=(-6, 0)),
        _spec("Rush Super", "rush_super", "~D, DF, F, D, DF, F, z", 3480, damage=175, frame_count=11, hit_frame=5, hit_box=(18, -84, 90, -24), sound=(5, 6), ground_velocity=(-9, 0), air_velocity=(-5, -7)),
    ],
    "auto_zoner_move_suite": [
        _spec("Zoner Poke", "zoner_poke", "y", 560, damage=34, frame_count=5, hit_frame=3, hit_box=(20, -72, 72, -38), sound=(5, 1)),
        _spec("Zoner Slow Shot", "zoner_slow_shot", "~D, DF, F, x", 1560, move_type="projectile", damage=42, frame_count=7, hit_frame=5, hit_box=(22, -68, 80, -34), sound=(5, 3), ground_velocity=(-2, 0)),
        _spec("Zoner Fast Shot", "zoner_fast_shot", "~D, DF, F, y", 1570, move_type="projectile", damage=56, frame_count=6, hit_frame=4, hit_box=(24, -70, 92, -32), sound=(5, 3), ground_velocity=(-5, 0)),
        _spec("Zoner Anti Air", "zoner_anti_air", "~F, D, DF, y", 1580, damage=78, frame_count=8, hit_frame=3, hit_box=(8, -104, 56, -22), sound=(5, 4), ground_velocity=(-3, -7), air_velocity=(-2, -8)),
    ],
    "auto_grappler_move_suite": [
        _spec("Grappler Body Blow", "grappler_body_blow", "y", 660, damage=52, frame_count=6, hit_frame=3, hit_box=(16, -70, 64, -28), sound=(5, 1), ground_velocity=(-4, 0)),
        _spec("Grappler Lariat", "grappler_lariat", "~D, DB, B, x", 1660, damage=72, frame_count=8, hit_frame=4, hit_box=(18, -78, 82, -22), sound=(5, 2), ground_velocity=(-6, 0)),
        _spec("Grappler Command Grab", "grappler_grab", "~D, DB, B, y", 1670, damage=95, frame_count=7, hit_frame=3, hit_box=(8, -76, 44, -22), sound=(5, 5), ground_velocity=(-2, -3), air_velocity=(-2, -5)),
        _spec("Grappler Super Grab", "grappler_super_grab", "~D, DB, B, D, DB, B, z", 3670, damage=220, frame_count=12, hit_frame=5, hit_box=(8, -84, 52, -18), sound=(5, 6), ground_velocity=(-4, -8), air_velocity=(-4, -9)),
    ],
    "auto_anti_air_reversal_pack": [
        _spec("Reversal Uppercut", "reversal_uppercut", "~F, D, DF, y", 1760, damage=86, frame_count=8, hit_frame=3, hit_box=(8, -108, 58, -22), sound=(5, 4), ground_velocity=(-3, -8), air_velocity=(-3, -9)),
        _spec("Reversal Kick", "reversal_kick", "~D, DB, B, b", 1770, damage=74, frame_count=7, hit_frame=3, hit_box=(10, -96, 62, -18), sound=(5, 4), ground_velocity=(-3, -7), air_velocity=(-2, -8)),
        _spec("Air Check", "air_check", "x", 680, damage=28, frame_count=4, hit_frame=2, hit_box=(14, -72, 54, -36), body_box=(-18, -82, 18, 2), sound=(5, 0), ground_velocity=(-3, -1), air_velocity=(-2, -4)),
    ],
}


MOVE_AUTOMATION_STEPS: Dict[str, Sequence[str]] = {
    "auto_starter_normals_route": ["auto_jab", "auto_mid_kick", "auto_sweep"],
    "auto_beginner_cancel_route": ["route_jab", "route_medium", "route_launcher", "route_fireball"],
    "auto_rushdown_move_suite": ["rush_jab", "rush_step_kick", "rush_slide", "rush_super"],
    "auto_zoner_move_suite": ["zoner_poke", "zoner_slow_shot", "zoner_fast_shot", "zoner_anti_air"],
    "auto_grappler_move_suite": ["grappler_body_blow", "grappler_lariat", "grappler_grab", "grappler_super_grab"],
    "auto_anti_air_reversal_pack": ["reversal_uppercut", "reversal_kick", "air_check"],
}


MOVE_AUTOMATION_NOTES: Dict[str, Sequence[str]] = {
    "auto_starter_normals_route": ["Use this as the first playable ground route.", "Tune sweep recovery after in-engine testing."],
    "auto_beginner_cancel_route": ["Cancel helpers route jab to medium to launcher to projectile ender.", "Move cancel windows later if the route feels too easy or too strict."],
    "auto_rushdown_move_suite": ["Designed for close-range pressure.", "Shorter frame timings make this kit feel faster than default normals."],
    "auto_zoner_move_suite": ["Designed for screen control.", "Test projectile speeds and recovery in the target engine."],
    "auto_grappler_move_suite": ["Designed for high-reward close-range play.", "Generated grab-like HitDefs are scaffolding; tune real throw behavior manually."],
    "auto_anti_air_reversal_pack": ["Designed to give a starter character defensive answers.", "Validate invulnerability, hitboxes, and recovery in-engine before release."],
}


MOVE_AUTOMATION_CANCELS: Dict[str, Sequence[tuple[int, str, int, int]]] = {
    "auto_starter_normals_route": [(260, "auto_mid_kick", 270, 3), (270, "auto_sweep", 280, 3)],
    "auto_beginner_cancel_route": [(360, "route_medium", 370, 3), (370, "route_launcher", 380, 3), (380, "route_fireball", 1390, 4)],
    "auto_rushdown_move_suite": [(460, "rush_step_kick", 470, 2), (470, "rush_slide", 1480, 3), (1480, "rush_super", 3480, 5)],
    "auto_zoner_move_suite": [(560, "zoner_slow_shot", 1560, 3), (1560, "zoner_fast_shot", 1570, 5)],
    "auto_grappler_move_suite": [(660, "grappler_lariat", 1660, 3), (1660, "grappler_grab", 1670, 4), (1670, "grappler_super_grab", 3670, 4)],
    "auto_anti_air_reversal_pack": [(1760, "reversal_kick", 1770, 4)],
}


def _training_macro_package(feature_id: str, preset: FeaturePreset) -> FeaturePackage:
    cmd = """[Command]
name = "mf_training_route_1"
command = x, y, z
time = 40
buffer.time = 6

[Command]
name = "mf_training_route_2"
command = x, y, D, z
time = 50
buffer.time = 6

[Command]
name = "mf_training_special"
command = D, DF, F, x
time = 20
buffer.time = 6
"""
    cns = """; MugenForge training macro router
[State -1, MugenForge Training Route 1]
type = ChangeState
triggerall = roundstate = 2
triggerall = command = "mf_training_route_1"
trigger1 = ctrl
value = 260

[State -1, MugenForge Training Route 2]
type = ChangeState
triggerall = roundstate = 2
triggerall = command = "mf_training_route_2"
trigger1 = ctrl
value = 360

[State -1, MugenForge Training Special]
type = ChangeState
triggerall = roundstate = 2
triggerall = command = "mf_training_special"
trigger1 = ctrl
value = 1390

[State -2, MugenForge Move Automation Readout]
type = DisplayToClipboard
trigger1 = 1
text = "Move automation: state=%d anim=%d elem=%d time=%d command routes installed"
params = stateno, anim, animelemno(0), time
ignorehitpause = 1
"""
    extra_files = _docs_file(
        feature_id,
        preset,
        ["mf_training_route_1", "mf_training_route_2", "mf_training_special"],
        ["Install after starter route packs so target StateDefs exist.", "Use this only for training and debugging; remove or disable before a public release if unwanted."],
    )
    return FeaturePackage(
        feature_id=feature_id,
        name=preset.name,
        cmd_block=_wrap(feature_id, preset.name, cmd),
        cns_block=_wrap(feature_id, preset.name, cns),
        extra_files=extra_files,
        summary="Adds training macro commands and a clipboard readout for generated move routes.",
        notes=list(preset.beginner_notes),
    )


def build_move_automation_feature(feature_id: str) -> Optional[FeaturePackage]:
    if feature_id == "auto_training_macro_routes":
        return _training_macro_package(feature_id, get_preset(feature_id))
    if feature_id not in MOVE_AUTOMATION_SPECS:
        return None
    return _pack(
        feature_id,
        MOVE_AUTOMATION_SPECS[feature_id],
        MOVE_AUTOMATION_STEPS[feature_id],
        MOVE_AUTOMATION_NOTES[feature_id],
        MOVE_AUTOMATION_CANCELS.get(feature_id, ()),
    )
