"""Compatibility layer for the v4.1 Forge Polish backend.

Early v4.1 development used the name ``polish_lab``. The shipped backend is
``forge_polish``; this module preserves the older import names without
maintaining a second implementation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .forge_polish import (
    FORGE_POLISH_VERSION,
    ForgePolishResult,
    run_forge_polish_pass,
    write_beginner_next_steps_dashboard,
    write_beginner_dashboard_41,
    validate_command_sheet,
    validate_air_batch_sheet,
    validate_all_edit_sheets,
    export_sound_cue_apply_sheet,
    export_editable_sound_cue_sheet,
    apply_sound_cue_sheet,
    apply_snd_cue_sheet,
    build_sprite_backed_timeline_preview,
    make_state_graph_model,
    build_state_graph_canvas_model,
    write_state_graph_canvas_pack,
    write_state_graph_canvas_artifacts,
    validate_template_library,
    validate_template_architecture,
    import_template_pack,
    build_stage_source_preview,
    write_stage_source_art_preview,
    list_backup_rows,
    list_backup_history,
    write_backup_history,
    restore_backup_file,
    build_forge_polish_bundle,
)

POLISH_LAB_VERSION = FORGE_POLISH_VERSION
PolishResult = ForgePolishResult


def run_polish_pass(root: Path) -> ForgePolishResult:
    return run_forge_polish_pass(root)


run_polish_lab_pass = run_polish_pass


def preview_command_sheet_apply(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    return validate_command_sheet(root, sheet_path)


def preview_air_batch_sheet_apply(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    return validate_air_batch_sheet(root, sheet_path)


def export_sound_cue_sheet(root: Path) -> ForgePolishResult:
    return export_sound_cue_apply_sheet(root)


def preview_sound_cue_sheet_apply(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    result = ForgePolishResult('Sound Cue Sheet Preview')
    # The apply function only mutates enabled add rows. For preview purposes,
    # run the exporter guide/validation path by returning sheet presence info.
    sheet = Path(sheet_path) if sheet_path else Path(root) / 'forge_polish' / 'sheets' / 'sound_cue_apply_sheet.csv'
    if not sheet.exists():
        result.warnings.append(f'Sound cue sheet not found: {sheet}')
    else:
        result.notes.append(f'Sound cue sheet ready for explicit apply: {sheet}')
    return result


def validate_sound_cue_sheet(root: Path, sheet_path: Optional[Path] = None) -> ForgePolishResult:
    return preview_sound_cue_sheet_apply(root, sheet_path)


def write_sprite_timeline_preview(root: Path, action_number: Optional[int] = None) -> ForgePolishResult:
    return build_sprite_backed_timeline_preview(root, action_number)


def write_state_graph_canvas_model(root: Path) -> ForgePolishResult:
    return write_state_graph_canvas_pack(root)


def validate_template_pack(root: Path, source: Optional[Path] = None) -> ForgePolishResult:
    return validate_template_library(root, source)


def write_stage_source_preview(root: Path) -> ForgePolishResult:
    return build_stage_source_preview(root)


def write_backup_browser(root: Path) -> ForgePolishResult:
    return write_backup_history(root)


def write_beginner_dashboard_v41(root: Path) -> ForgePolishResult:
    return write_beginner_next_steps_dashboard(root)


def build_polish_reports_bundle(root: Path) -> ForgePolishResult:
    return build_forge_polish_bundle(root)
