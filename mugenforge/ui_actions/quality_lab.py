from __future__ import annotations

from tkinter import messagebox

from ..quality_lab import (
    build_alpha_clsn_suggestions,
    create_asset_swap_pack,
    create_backup_restore_bundle,
    run_quality_lab_pass,
    write_advanced_audit,
    write_alpha_clsn_air_copy,
    write_animation_timing_sheet,
    write_beginner_fix_plan,
    write_move_cards,
    write_searchable_html_index,
)


class QualityLabActions:
    def _quality_lab_root(self):
        root = self._plus_get_project_root()
        if not root:
            return None
        return root

    def _quality_lab_padding(self):
        try:
            return int(self.quality_lab_clsn_padding_var.get().strip())
        except Exception:
            return 2

    def _quality_lab_run(self, label, func, *args, **kwargs):
        root = self._quality_lab_root()
        if not root:
            return
        try:
            result = func(root, *args, **kwargs)
            self.reload_project()
            self.set_text(self.quality_lab_output, result.to_text())
            self.notebook.select(self.quality_lab_frame)
            self.status_var.set(label)
        except Exception as exc:
            messagebox.showerror(label, str(exc))

    def quality_lab_one_click_ui(self):
        self._quality_lab_run('Quality Lab pass complete.', run_quality_lab_pass)

    def quality_lab_audit_ui(self):
        self._quality_lab_run('Advanced audit written.', write_advanced_audit)

    def quality_lab_index_ui(self):
        self._quality_lab_run('Searchable index written.', write_searchable_html_index)

    def quality_lab_move_cards_ui(self):
        self._quality_lab_run('Move cards written.', write_move_cards)

    def quality_lab_alpha_clsn_ui(self):
        self._quality_lab_run('Alpha CLSN suggestions written.', build_alpha_clsn_suggestions, padding=self._quality_lab_padding())

    def quality_lab_alpha_copy_ui(self):
        self._quality_lab_run('AIR copy with generated body CLSN written.', write_alpha_clsn_air_copy, padding=self._quality_lab_padding())

    def quality_lab_timing_ui(self):
        self._quality_lab_run('Animation timing sheet written.', write_animation_timing_sheet)

    def quality_lab_asset_swap_ui(self):
        self._quality_lab_run('Asset swap pack created.', create_asset_swap_pack)

    def quality_lab_backup_ui(self):
        self._quality_lab_run('Backup/restore bundle created.', create_backup_restore_bundle)

    def quality_lab_fix_plan_ui(self):
        self._quality_lab_run('Beginner fix plan written.', write_beginner_fix_plan)
