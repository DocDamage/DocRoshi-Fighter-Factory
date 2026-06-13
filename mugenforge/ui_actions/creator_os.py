from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..creator_os import (
    build_creator_os_release_zip,
    creator_os_one_click,
    export_frame_data_sheet,
    export_input_cheatsheet,
    write_asset_shopping_list,
    write_autocode_cookbook,
    write_balance_report,
    write_beginner_lessons,
    write_character_blueprint,
    write_combo_routes,
    write_project_wiki,
    write_release_quality_gate,
)


class CreatorOSActions:
    def _creator_os_root_or_choose(self):
        if self.project_root:
            return self.project_root
        folder = filedialog.askdirectory(title='Choose character folder for Creator OS')
        if folder:
            self.project_root = Path(folder)
            self.reload_project()
            return self.project_root
        return None

    def _creator_os_show_result(self, result, title='Creator OS'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        if hasattr(self, 'creator_os_output'):
            self.set_text(self.creator_os_output, text)
            self.notebook.select(self.creator_os_frame)
        self.status_var.set(title)

    def _creator_os_profile(self):
        archetype = self.creator_os_archetype_var.get() if hasattr(self, 'creator_os_archetype_var') else 'Balanced Starter'
        complexity = self.creator_os_complexity_var.get() if hasattr(self, 'creator_os_complexity_var') else 'Beginner'
        style = self.creator_os_style_var.get() if hasattr(self, 'creator_os_style_var') else 'Arcade'
        return archetype, complexity, style

    def creator_os_one_click_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        archetype, complexity, style = self._creator_os_profile()
        try:
            result = creator_os_one_click(root, archetype=archetype, complexity=complexity, visual_style=style)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Autopilot finished')
            messagebox.showinfo('Creator OS', 'Creator OS Autopilot finished. Open docs/PROJECT_WIKI.md or START_HERE_CREATOR_OS.md next.')
        except Exception as exc:
            messagebox.showerror('Creator OS Autopilot failed', str(exc))

    def creator_os_blueprint_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        archetype, complexity, style = self._creator_os_profile()
        try:
            result = write_character_blueprint(root, archetype=archetype, complexity=complexity, visual_style=style)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Blueprint written')
        except Exception as exc:
            messagebox.showerror('Blueprint failed', str(exc))

    def creator_os_frame_data_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = export_frame_data_sheet(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Frame Data exported')
        except Exception as exc:
            messagebox.showerror('Frame Data export failed', str(exc))

    def creator_os_inputs_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = export_input_cheatsheet(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Input Cheatsheet exported')
        except Exception as exc:
            messagebox.showerror('Input Cheatsheet failed', str(exc))

    def creator_os_combo_routes_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_combo_routes(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Combo Routes written')
        except Exception as exc:
            messagebox.showerror('Combo Routes failed', str(exc))

    def creator_os_balance_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_balance_report(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Balance Report written')
        except Exception as exc:
            messagebox.showerror('Balance Report failed', str(exc))

    def creator_os_quality_gate_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_release_quality_gate(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Quality Gate finished')
        except Exception as exc:
            messagebox.showerror('Quality Gate failed', str(exc))

    def creator_os_asset_list_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_asset_shopping_list(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Asset Shopping List written')
        except Exception as exc:
            messagebox.showerror('Asset Shopping List failed', str(exc))

    def creator_os_lessons_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_beginner_lessons(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Beginner Lessons written')
        except Exception as exc:
            messagebox.showerror('Beginner Lessons failed', str(exc))

    def creator_os_wiki_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_project_wiki(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Project Wiki written')
        except Exception as exc:
            messagebox.showerror('Project Wiki failed', str(exc))

    def creator_os_codebook_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_autocode_cookbook(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Auto-Code Cookbook written')
        except Exception as exc:
            messagebox.showerror('Auto-Code Cookbook failed', str(exc))

    def creator_os_release_zip_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = build_creator_os_release_zip(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Release ZIP built')
            messagebox.showinfo('Creator OS Release ZIP', result.to_text())
        except Exception as exc:
            messagebox.showerror('Creator OS Release ZIP failed', str(exc))
