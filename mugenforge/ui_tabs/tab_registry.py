from __future__ import annotations

from dataclasses import dataclass


WORKSPACE_ROLES = (
    'Beginner',
    'Visual',
    'Binary',
    'Runtime',
    'Release',
    'Maintenance',
)
WORKSPACE_ROLE_CHOICES = ('All', *WORKSPACE_ROLES)


@dataclass(frozen=True)
class FeatureTabSpec:
    builder: str
    label: str
    role: str


FEATURE_TABS = (
    FeatureTabSpec('_build_auto_builder_tab', 'Feature Bank', 'Beginner'),
    FeatureTabSpec('_build_factory_plus_tab', 'Factory+', 'Beginner'),
    FeatureTabSpec('_build_factory_max_tab', 'Factory Max', 'Beginner'),
    FeatureTabSpec('_build_factory_ultra_tab', 'Factory Ultra', 'Beginner'),
    FeatureTabSpec('_build_creator_os_tab', 'Creator OS', 'Beginner'),
    FeatureTabSpec('_build_quality_lab_tab', 'Quality Lab', 'Beginner'),
    FeatureTabSpec('_build_creator_suite_tab', 'Creator Suite', 'Beginner'),
    FeatureTabSpec('_build_creator_hub_tab', 'Creator Hub', 'Beginner'),
    FeatureTabSpec('_build_rescue_lab_tab', 'Rescue Lab', 'Maintenance'),
    FeatureTabSpec('_build_sff2_bridge_tab', 'SFF2 Bridge', 'Binary'),
    FeatureTabSpec('_build_image_factory_tab', 'Image Factory', 'Visual'),
    FeatureTabSpec('_build_palette_tab', 'Palettes', 'Visual'),
    FeatureTabSpec('_build_studio_plus_tab', 'Studio Plus', 'Beginner'),
    FeatureTabSpec('_build_forge_plus_tab', 'Forge+ Doctor', 'Maintenance'),
    FeatureTabSpec('_build_sprite_lab_tab', 'Sprite Lab', 'Visual'),
    FeatureTabSpec('_build_stage_builder_tab', 'Stage Builder', 'Visual'),
    FeatureTabSpec('_build_run_test_tab', 'Run / Test', 'Runtime'),
    FeatureTabSpec('_build_visual_forge_home_tab', 'Project Home', 'Visual'),
    FeatureTabSpec('_build_visual_timeline_editor_tab', 'Visual Timeline', 'Visual'),
    FeatureTabSpec('_build_sprite_offset_axis_tab', 'Offset / Axis', 'Visual'),
    FeatureTabSpec('_build_sound_cue_editor_tab', 'Sound Cue Editor', 'Visual'),
    FeatureTabSpec('_build_move_composer2_tab', 'Move Composer 2.0', 'Visual'),
    FeatureTabSpec('_build_migration_wizard_tab', 'Migration Wizard', 'Maintenance'),
    FeatureTabSpec('_build_training_debug_tab', 'Training Debug', 'Runtime'),
    FeatureTabSpec('_build_plugin_template_tab', 'Templates / Plugins', 'Maintenance'),
    FeatureTabSpec('_build_backup_log_tab', 'Backups / Logs', 'Maintenance'),
    FeatureTabSpec('_build_forge_beyond_tab', 'Forge Beyond', 'Visual'),
    FeatureTabSpec('_build_forge_polish_tab', 'Forge Polish', 'Release'),
    FeatureTabSpec('_build_forge_timeline_tab', 'Forge Timeline', 'Visual'),
    FeatureTabSpec('_build_binary_core_tab', 'Binary Core', 'Binary'),
    FeatureTabSpec('_build_binary_deep_tab', 'Binary Deep', 'Binary'),
    FeatureTabSpec('_build_binary_maturity_tab', 'Binary Maturity', 'Binary'),
    FeatureTabSpec('_build_closure_lab_tab', 'Closure Lab', 'Release'),
    FeatureTabSpec('_build_gap_closer_tab', 'Gap Closer', 'Maintenance'),
    FeatureTabSpec('_build_authority_core_tab', 'Authority Core', 'Release'),
    FeatureTabSpec('_build_runtime_lab_tab', 'Runtime Lab', 'Runtime'),
    FeatureTabSpec('_build_authority_lab_tab', 'Authority Lab', 'Release'),
    FeatureTabSpec('_build_evidence_core_tab', 'Evidence Core', 'Release'),
    FeatureTabSpec('_build_maintenance_core_tab', 'Maintenance Core', 'Maintenance'),
    FeatureTabSpec('_build_operator_console_tab', 'Operator Console', 'Maintenance'),
    FeatureTabSpec('_build_handoff_core_tab', 'Handoff Core', 'Maintenance'),
)

FEATURE_TAB_BUILDERS = tuple(tab.builder for tab in FEATURE_TABS)
FEATURE_TAB_LABELS = tuple(tab.label for tab in FEATURE_TABS)
FEATURE_TAB_ROLES = {tab.label: tab.role for tab in FEATURE_TABS}
