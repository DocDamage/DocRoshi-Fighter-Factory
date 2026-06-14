from __future__ import annotations

from typing import List, Dict, Optional, Sequence
from pathlib import Path

from .base import (
    FeaturePreset,
    FeaturePackage,
    MoveWizardSpec,
    _wrap,
    _spec,
    _pack_from_specs,
    _simple_pose_state,
    _simple_pose_air,
    _movement_fx_state,
    _state_minus_one,
    _command_block,
    get_preset,
)


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


def build_v22_feature(feature_id: str) -> Optional[FeaturePackage]:
    # v2.2 feature preset list
    v22_ids = {
        "overhead_attack", "close_heavy", "forward_punch", "forward_kick", "hop_kick", "crossup_kick",
        "dash_attack", "run_forward", "run_stop", "short_hop", "double_jump", "wall_jump",
        "quick_rise", "air_recovery", "guard_break", "armor_tackle", "invincible_reversal", "rekka_chain",
        "charge_fireball", "flash_kick", "power_wave", "beam_projectile", "boomerang_projectile", "homing_orb",
        "reflect_shield", "dive_kick", "ground_bounce", "wall_bounce", "target_combo", "auto_combo",
        "air_combo_starter", "launcher_air_route", "meter_charge", "small_heal", "super_beam", "cinematic_super",
        "command_super_grab", "install_dash_cancel", "stance_switch", "stance_special", "summon_clone",
        "dust_fx", "hit_spark_fx", "voice_callouts", "training_shortcuts", "ai_level_scaler", "round_state_helper",
        "dizzy_pose", "perfect_win_pose", "time_over_pose"
    }

    if feature_id not in v22_ids:
        return None

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
        elif feature_id == "stance_special":
            gate = '''; MugenForge note: Add this triggerall to the generated Stance Special -1 route if you only want it in stance mode.
; triggerall = Var(21) = 1
'''
            pkg.cns_block += _wrap(feature_id + "_stance_gate_note", "Stance-only gate note", gate)
        elif feature_id == "install_dash_cancel":
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

    return None
