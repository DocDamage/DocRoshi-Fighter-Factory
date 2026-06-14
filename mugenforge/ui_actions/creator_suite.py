from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..creator_suite import (
    apply_hitdef_tuning_sheet,
    creator_suite_profile_report,
    export_hitdef_tuning_sheet,
    install_beginner_tuning_panel,
    make_project_time_machine_snapshot,
    one_click_creator_autopilot,
    write_artist_handoff_pack,
    write_asset_library,
    write_art_task_board,
    write_character_dna_profile,
    write_combo_tree,
    write_creator_dashboard as write_suite_creator_dashboard,
    write_creator_indexes,
    write_final_qa_release_plan,
    write_move_lab,
    write_training_pack,
)


class CreatorSuiteActions:
    def _creator_suite_root(self):
        if hasattr(self, '_max_root_or_choose'):
            return self._max_root_or_choose()
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _creator_suite_profile(self):
        arch = self.creator_suite_archetype_var.get().strip() if hasattr(self, 'creator_suite_archetype_var') else 'Balanced Starter'
        exp = self.creator_suite_experience_var.get().strip() if hasattr(self, 'creator_suite_experience_var') else 'Beginner'
        buttons = self.creator_suite_buttons_var.get().strip() if hasattr(self, 'creator_suite_buttons_var') else 'Six button'
        power = self.creator_suite_power_var.get().strip() if hasattr(self, 'creator_suite_power_var') else 'Standard meter'
        return arch, exp, buttons, power

    def _creator_suite_show_result(self, result, title='Creator Suite'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.creator_suite_output, text)
        if hasattr(self, 'creator_suite_frame'):
            self.notebook.select(self.creator_suite_frame)
        self.status_var.set(title)

    def _creator_suite_run(self, label, func, *args, confirm=None, **kwargs):
        root = self._creator_suite_root()
        if not root:
            return
        if confirm and not messagebox.askyesno(label, confirm):
            return
        try:
            result = func(root, *args, **kwargs)
            self.reload_project()
            self._creator_suite_show_result(result, label)
        except Exception as exc:
            messagebox.showerror(label + ' failed', str(exc))

    def creator_suite_autopilot_ui(self):
        arch, exp, buttons, power = self._creator_suite_profile()
        self._creator_suite_run('Creator AutoPilot finished', one_click_creator_autopilot, arch, exp, buttons, power)

    def creator_suite_profile_report_ui(self):
        self._creator_suite_run('Creator Suite profile report written', creator_suite_profile_report)

    def creator_suite_dna_ui(self):
        arch, exp, buttons, power = self._creator_suite_profile()
        self._creator_suite_run('Character DNA written', write_character_dna_profile, arch, exp, buttons, power)

    def creator_suite_asset_library_ui(self):
        self._creator_suite_run('Asset library written', write_asset_library)

    def creator_suite_move_lab_ui(self):
        self._creator_suite_run('Move lab written', write_move_lab)

    def creator_suite_combo_tree_ui(self):
        self._creator_suite_run('Combo tree written', write_combo_tree)

    def creator_suite_art_board_ui(self):
        self._creator_suite_run('Art task board written', write_art_task_board)

    def creator_suite_tuning_panel_ui(self):
        self._creator_suite_run('Beginner tuning panel installed', install_beginner_tuning_panel)

    def creator_suite_export_hitdef_tuning_ui(self):
        self._creator_suite_run('HitDef tuning sheet exported', export_hitdef_tuning_sheet)

    def creator_suite_apply_hitdef_tuning_ui(self):
        self._creator_suite_run(
            'HitDef tuning sheet applied',
            apply_hitdef_tuning_sheet,
            confirm='This applies values from reports/hitdef_tuning_sheet.csv back into CMD/CNS/ST HitDef blocks and writes backups first. Continue?',
        )

    def creator_suite_snapshot_ui(self):
        self._creator_suite_run('Time machine snapshot created', make_project_time_machine_snapshot)

    def creator_suite_dashboard_ui(self):
        self._creator_suite_run('Creator dashboard written', write_suite_creator_dashboard)

    def creator_suite_final_qa_ui(self):
        self._creator_suite_run('Final QA release plan written', write_final_qa_release_plan)

    def creator_suite_training_ui(self):
        self._creator_suite_run('Training pack written', write_training_pack)

    def creator_suite_indexes_ui(self):
        self._creator_suite_run('Creator indexes written', write_creator_indexes)

    def creator_suite_handoff_ui(self):
        self._creator_suite_run('Artist / sound handoff pack written', write_artist_handoff_pack)
