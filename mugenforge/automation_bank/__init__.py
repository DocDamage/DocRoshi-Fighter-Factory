from __future__ import annotations

from .base import (
    FeaturePreset,
    FeaturePackage,
    ApplyResult,
    available_presets,
    get_preset,
    preset_display_list,
    preset_by_display,
    package_preview_text,
    apply_feature_package,
    apply_preset,
    apply_beginner_pack,
    default_project_profile,
    beginner_guide_text,
    _ensure_def_files_section,
    auto_setup_project,
    beginner_project_status,
    export_code_bank_template,
    kit_names,
    kit_preview_text,
    apply_feature_ids_pack,
    apply_kit,
    make_placeholder_sprite_sheet,
    feature_bank_stats,
    feature_bank_stats_text,
)
from .presets import FEATURE_PRESETS, KIT_PRESETS
from .builders_classic import build_classic_feature
from .builders_v22 import build_v22_feature
from .builders_v23_v25 import build_v23_v25_feature
from .builders_v26 import build_v26_feature
from .builders_labs import build_labs_feature
from .builders_moves import build_move_automation_feature


def build_feature_package(feature_id: str) -> FeaturePackage:
    # Mirror the original chain of overrides (from latest to oldest)
    pkg = build_move_automation_feature(feature_id)
    if pkg is not None:
        return pkg
    pkg = build_labs_feature(feature_id)
    if pkg is not None:
        return pkg
    pkg = build_v26_feature(feature_id)
    if pkg is not None:
        return pkg
    pkg = build_v23_v25_feature(feature_id)
    if pkg is not None:
        return pkg
    pkg = build_v22_feature(feature_id)
    if pkg is not None:
        return pkg
    pkg = build_classic_feature(feature_id)
    if pkg is not None:
        return pkg
    raise KeyError(feature_id)
