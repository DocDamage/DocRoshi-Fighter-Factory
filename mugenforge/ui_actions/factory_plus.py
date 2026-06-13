from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from .. import factory_plus as fp


class FactoryPlusActions:
    def _factory_root_or_choose(self):
        root = self.project_root
        if root:
            return root
        chosen = filedialog.askdirectory(title='Choose or create a character project folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _factory_show_result(self, result, title='Factory+'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        try:
            self.set_text(self.factory_plus_output, text)
            self.notebook.select(self.factory_plus_frame)
        except Exception:
            self.set_text(self.analysis, text)
            self.notebook.select(1)
        self.status_var.set(title)
        if getattr(result, 'warnings', None):
            messagebox.showwarning(title, text[:3000])
        else:
            messagebox.showinfo(title, text[:3000])

    def factory_smart_complete_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.smart_complete_project(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Smart Complete / Repair finished')

    def factory_doctor_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_doctor_report(root)
        report = fp.deep_factory_doctor(root)
        try:
            self.set_text(self.factory_plus_output, report + '\n' + result.to_text())
            self.notebook.select(self.factory_plus_frame)
        except Exception:
            self.set_text(self.analysis, report)
            self.notebook.select(1)
        self.status_var.set('Factory+ Doctor report written.')
        messagebox.showinfo('Factory+ Doctor', result.to_text())

    def factory_start_here_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_start_here(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Start Here guide written')

    def factory_function_bank_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_function_bank(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Function Bank written')

    def factory_complete_air_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.ensure_required_animations(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ AIR repair finished')

    def factory_placeholder_sff_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.rebuild_placeholder_sff_from_air(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ placeholder SFF built')

    def factory_bulk_import_sprites_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        folder = filedialog.askdirectory(title='Choose folder of PNG/PCX/GIF sprites named like g200_i0.png')
        if not folder:
            return
        append_air = messagebox.askyesno('Append AIR actions?', 'Append one AIR action per imported sprite group when that action does not already exist?')
        result = fp.bulk_import_sprite_folder(root, Path(folder), append_air=append_air)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ bulk sprite import finished')

    def factory_movelist_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_move_list(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ move list exported')

    def factory_state_map_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_state_map(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ state map exported')

    def factory_balance_sheet_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_balance_sheet(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ balance sheet exported')

    def factory_release_zip_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.build_release_zip(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ release ZIP built')
