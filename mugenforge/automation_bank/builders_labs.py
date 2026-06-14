from __future__ import annotations

from typing import List, Dict, Optional, Sequence
from pathlib import Path
import re

from .base import (
    FeaturePreset,
    FeaturePackage,
    _wrap,
    get_preset,
    _simple_pose_air,
)


# Quality Lab builders

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


# Rescue Lab builders

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


# Creator Hub builders

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


def build_labs_feature(feature_id: str) -> Optional[FeaturePackage]:
    # Quality Lab IDs
    quality_ids = {
        'ql_advanced_project_audit_docs', 'ql_searchable_index_docs', 'ql_beginner_fix_plan_docs',
        'ql_asset_swap_workflow_docs', 'ql_alpha_clsn_workflow_docs', 'ql_move_cards_docs',
        'ql_animation_timing_docs', 'ql_backup_restore_docs', 'ql_release_gate_docs',
        'ql_frame_tags_docs', 'ql_sprite_axis_docs', 'ql_sound_cue_docs', 'ql_palette_safety_docs',
        'ql_engine_test_loop_docs', 'ql_controller_input_docs', 'ql_balance_budget_docs',
        'ql_accessibility_pack_docs', 'ql_stage_camera_docs', 'ql_project_handoff_docs',
        'ql_ff_parity_migration_docs', 'ql_hitbox_debug_overlay', 'ql_balance_debug_overlay',
        'ql_sound_debug_overlay', 'ql_training_toggle_bank', 'ql_ai_test_router',
        'ql_placeholder_cleanup_docs', 'ql_combo_trial_docs', 'ql_hitdef_recipe_docs',
        'ql_sprite_naming_docs', 'ql_sound_naming_docs', 'ql_credits_license_docs',
        'ql_rc_smoke_test_docs', 'ql_no_code_guardrails_docs', 'ql_asset_manifest_docs',
        'ql_state_cleanup_docs', 'ql_command_cleanup_docs'
    }

    # Rescue Lab IDs
    rescue_ids = {
        'rescue_embedded_scan_docs', 'rescue_contact_sheet_docs', 'rescue_air_mapping_docs',
        'rescue_sff_rebuild_docs', 'rescue_audio_recovery_docs', 'rescue_source_art_handoff_docs',
        'rescue_migration_plan_docs', 'factory_complete_route_docs', 'factory_complete_safety_docs',
        'factory_complete_asset_policy_docs', 'factory_complete_beginner_debug_hook',
        'factory_complete_asset_missing_hook', 'factory_complete_tuning_knobs_hook'
    }

    # Creator Hub IDs
    creator_hub_ids = {
        'ch_creator_dashboard_docs', 'ch_task_board_docs', 'ch_input_conflict_docs',
        'ch_balance_autotune_docs', 'ch_combo_trial_docs', 'ch_asset_request_docs',
        'ch_controller_map_docs', 'ch_release_website_docs', 'ch_patch_macro_docs',
        'ch_artist_brief_docs', 'ch_sound_brief_docs', 'ch_voice_script_docs',
        'ch_palette_plan_docs', 'ch_stage_match_docs', 'ch_move_identity_docs',
        'ch_archetype_mix_docs', 'ch_risk_reward_docs', 'ch_meter_economy_docs',
        'ch_neutral_game_docs', 'ch_defense_flow_docs', 'ch_ai_personality_docs',
        'ch_boss_phase_docs', 'ch_training_mode_docs', 'ch_accessibility_docs',
        'ch_readme_install_docs', 'ch_credits_license_docs', 'ch_update_log_docs',
        'ch_playtest_form_docs', 'ch_bug_report_form_docs', 'ch_release_gate_docs',
        'ch_auto_meter_overlay', 'ch_input_echo_overlay', 'ch_combo_review_overlay',
        'ch_position_review_overlay', 'ch_ai_smoke_router', 'ch_round_flow_overlay',
        'ch_art_gap_overlay', 'ch_sound_gap_overlay', 'ch_balance_lab_overlay',
        'ch_release_candidate_overlay'
    }

    if feature_id in quality_ids:
        preset = get_preset(feature_id)
        if feature_id.endswith('_docs') or feature_id in {
            'ql_advanced_project_audit_docs', 'ql_searchable_index_docs', 'ql_beginner_fix_plan_docs',
            'ql_asset_swap_workflow_docs', 'ql_alpha_clsn_workflow_docs', 'ql_move_cards_docs',
            'ql_animation_timing_docs', 'ql_backup_restore_docs', 'ql_release_gate_docs',
            'ql_frame_tags_docs', 'ql_sprite_axis_docs', 'ql_sound_cue_docs', 'ql_palette_safety_docs',
            'ql_engine_test_loop_docs', 'ql_controller_input_docs', 'ql_balance_budget_docs',
            'ql_accessibility_pack_docs', 'ql_stage_camera_docs', 'ql_project_handoff_docs',
            'ql_ff_parity_migration_docs', 'ql_placeholder_cleanup_docs', 'ql_combo_trial_docs',
            'ql_hitdef_recipe_docs', 'ql_sprite_naming_docs', 'ql_sound_naming_docs',
            'ql_credits_license_docs', 'ql_rc_smoke_test_docs', 'ql_no_code_guardrails_docs',
            'ql_asset_manifest_docs', 'ql_state_cleanup_docs', 'ql_command_cleanup_docs'
        }:
            return _quality_doc(feature_id, preset)
        return _quality_system(feature_id, preset)

    if feature_id in rescue_ids:
        preset = get_preset(feature_id)
        if 'docs' in preset.blocks:
            return _rescue_doc_package(feature_id, preset)
        return _rescue_system_package(feature_id, preset)

    if feature_id in creator_hub_ids:
        preset = get_preset(feature_id)
        if feature_id.endswith('_overlay') or feature_id.endswith('_router') or feature_id == 'ch_release_candidate_overlay':
            return _creator_hub_system(feature_id, preset)
        return _creator_hub_doc(feature_id, preset)

    return None
