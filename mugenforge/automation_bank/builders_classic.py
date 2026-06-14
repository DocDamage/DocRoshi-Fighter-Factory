from __future__ import annotations

from typing import List, Dict, Optional, Sequence
from pathlib import Path
import json

from .base import (
    FeaturePreset,
    FeaturePackage,
    MoveWizardSpec,
    _wrap,
    _spec,
    _pack_from_specs,
    _basic_air_actions,
    _common_command_bank,
    _debug_overlay_block,
    _simple_pose_state,
    _simple_pose_air,
    _movement_fx_state,
    _state_minus_one,
    _command_block,
    beginner_guide_text,
    default_project_profile,
    get_preset,
)


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


def build_classic_feature(feature_id: str) -> Optional[FeaturePackage]:
    classic_ids = {
        "starter_basics", "common_commands", "debug_overlay",
        "light_punch", "medium_punch", "heavy_punch", "light_kick", "crouch_kick", "air_kick", "fireball", "dragon_punch", "dash_forward", "back_dash",
        "taunt", "intro_pose", "win_pose", "combo_three_hit", "projectile_plus_super",
        "medium_kick", "heavy_kick", "crouch_punch", "sweep", "launcher", "air_punch", "slow_fireball", "slide_kick", "spin_kick", "anti_air_kick", "air_fireball", "guard_cancel", "counter_attack", "super_rush", "super_uppercut",
        "roll_forward", "roll_back", "air_dash_forward", "teleport", "basic_throw", "command_grab", "parry", "pushblock", "power_install", "striker_assist", "trap_mine", "aura_fx", "afterimage_dash", "lose_pose", "simple_ai", "input_debug"
    }
    if feature_id not in classic_ids:
        return None

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
        cns = _movement_fx_state(140, 140, "Air Dash Forward", 6.0, -1.0, 15, afterimage=True).replace("type = S", "type = A", 1)
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

    return None
