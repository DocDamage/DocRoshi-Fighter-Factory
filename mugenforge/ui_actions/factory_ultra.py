from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..factory_ultra import (
    build_ultra_release_zip,
    create_autosave_snapshot,
    generate_ai_tuning_lab,
    generate_asset_usage_lab,
    generate_balance_lab,
    generate_beginner_task_board,
    generate_cancel_lab,
    generate_frame_data_lab,
    generate_input_map_assistant,
    generate_move_cards,
    generate_release_readiness_report,
    generate_sprite_axis_lab,
    one_click_ultra_production_pass,
    ultra_project_dashboard,
    write_no_code_feature_switchboard,
    write_production_bible,
)


class FactoryUltraActions:
    def _ultra_root_or_choose(self):
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

    def _ultra_show_result(self, result, title='Factory Ultra'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.factory_ultra_output, text)
        if hasattr(self, 'factory_ultra_frame'):
            self.notebook.select(self.factory_ultra_frame)
        self.status_var.set(title)

    def _ultra_run(self, fn, title):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = fn(root)
            self.reload_project()
            self._ultra_show_result(result, title)
        except Exception as exc:
            messagebox.showerror(title + ' failed', str(exc))

    def ultra_one_click_ui(self):
        self._ultra_run(one_click_ultra_production_pass, 'Ultra production pass finished')

    def ultra_snapshot_ui(self):
        self._ultra_run(create_autosave_snapshot, 'Ultra snapshot created')

    def ultra_release_zip_ui(self):
        self._ultra_run(build_ultra_release_zip, 'Ultra release ZIP built')

    def ultra_dashboard_ui(self):
        self._ultra_run(ultra_project_dashboard, 'Ultra dashboard written')

    def ultra_task_board_ui(self):
        self._ultra_run(generate_beginner_task_board, 'Ultra task board written')

    def ultra_bible_ui(self):
        self._ultra_run(write_production_bible, 'Ultra production bible written')

    def ultra_switchboard_ui(self):
        self._ultra_run(write_no_code_feature_switchboard, 'Ultra feature switchboard written')

    def ultra_readiness_ui(self):
        self._ultra_run(generate_release_readiness_report, 'Ultra release readiness written')

    def ultra_frame_data_ui(self):
        self._ultra_run(generate_frame_data_lab, 'Ultra frame data lab written')

    def ultra_balance_ui(self):
        self._ultra_run(generate_balance_lab, 'Ultra balance lab written')

    def ultra_cancel_ui(self):
        self._ultra_run(generate_cancel_lab, 'Ultra cancel/state flow lab written')

    def ultra_assets_ui(self):
        self._ultra_run(generate_asset_usage_lab, 'Ultra asset usage lab written')

    def ultra_axis_ui(self):
        self._ultra_run(generate_sprite_axis_lab, 'Ultra sprite axis lab written')

    def ultra_ai_ui(self):
        self._ultra_run(generate_ai_tuning_lab, 'Ultra AI tuning lab written')

    def ultra_move_cards_ui(self):
        self._ultra_run(generate_move_cards, 'Ultra move cards written')

    def ultra_input_map_ui(self):
        self._ultra_run(generate_input_map_assistant, 'Ultra input map assistant written')
