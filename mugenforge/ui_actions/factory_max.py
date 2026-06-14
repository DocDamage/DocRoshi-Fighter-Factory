from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from ..factory_max import (
    build_factory_max_release_zip,
    create_quick_test_suite,
    create_screenpack_template,
    create_sound_autobank,
    create_storyboard_template,
    factory_max_profile_report,
    one_click_factory_max_upgrade,
    renumber_air_actions,
    retime_air,
    safe_import_from_project,
    suggest_clsn_from_sff,
    write_codesense_bank,
    write_organizer_manifest,
    write_state_graph,
)


class FactoryMaxActions:
    def _max_root_or_choose(self):
        if hasattr(self, '_factory_root_or_choose'):
            return self._factory_root_or_choose()
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _max_show_result(self, result, title='Factory Max'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.factory_max_output, text)
        if hasattr(self, 'factory_max_frame'):
            self.notebook.select(self.factory_max_frame)
        self.status_var.set(title)

    def max_one_click_upgrade_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = one_click_factory_max_upgrade(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max upgrade finished')
            messagebox.showinfo('Factory Max Upgrade', 'Factory Max upgrade finished. Review the report/output panel for created files and next steps.')
        except Exception as exc:
            messagebox.showerror('Factory Max upgrade failed', str(exc))

    def max_profile_report_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = factory_max_profile_report(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max report written')
        except Exception as exc:
            messagebox.showerror('Factory Max report failed', str(exc))

    def max_release_zip_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = build_factory_max_release_zip(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max release ZIP built')
            messagebox.showinfo('Release ZIP built', result.to_text())
        except Exception as exc:
            messagebox.showerror('Release ZIP failed', str(exc))

    def max_codesense_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_codesense_bank(root)
            self.reload_project()
            self._max_show_result(result, 'CodeSense bank written')
        except Exception as exc:
            messagebox.showerror('CodeSense failed', str(exc))

    def max_state_graph_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_state_graph(root)
            self.reload_project()
            self._max_show_result(result, 'State graph written')
        except Exception as exc:
            messagebox.showerror('State graph failed', str(exc))

    def max_organizer_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_organizer_manifest(root)
            self.reload_project()
            self._max_show_result(result, 'Organizer manifest written')
        except Exception as exc:
            messagebox.showerror('Organizer manifest failed', str(exc))

    def max_safe_import_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        source = filedialog.askdirectory(title='Choose source character/project folder to import safely')
        if not source:
            return
        try:
            result = safe_import_from_project(root, Path(source))
            self.reload_project()
            self._max_show_result(result, 'Safe project import complete')
        except Exception as exc:
            messagebox.showerror('Safe import failed', str(exc))

    def max_auto_clsn_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            padding = self._plus_int(self.max_clsn_padding_var, 2) if hasattr(self, '_plus_int') else int(self.max_clsn_padding_var.get() or 2)
            result = suggest_clsn_from_sff(root, padding=padding, save=True)
            self.reload_project()
            self._max_show_result(result, 'Auto CLSN from SFF finished')
        except Exception as exc:
            messagebox.showerror('Auto CLSN failed', str(exc))

    def max_retime_air_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            scale = self._plus_float(self.max_retime_scale_var, 1.0) if hasattr(self, '_plus_float') else float(self.max_retime_scale_var.get() or 1.0)
            result = retime_air(root, tick_scale=scale)
            self.reload_project()
            self._max_show_result(result, 'AIR retiming finished')
        except Exception as exc:
            messagebox.showerror('AIR retime failed', str(exc))

    def max_renumber_air_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            offset = self._plus_int(self.max_renumber_offset_var, 10000) if hasattr(self, '_plus_int') else int(self.max_renumber_offset_var.get() or 10000)
            result = renumber_air_actions(root, offset=offset)
            self.reload_project()
            self._max_show_result(result, 'AIR clone/renumber finished')
        except Exception as exc:
            messagebox.showerror('AIR clone/renumber failed', str(exc))

    def max_storyboard_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        name = simpledialog.askstring('Storyboard Template', 'Storyboard name:', initialvalue='intro') or 'intro'
        try:
            result = create_storyboard_template(root, name=name)
            self.reload_project()
            self._max_show_result(result, 'Storyboard template created')
        except Exception as exc:
            messagebox.showerror('Storyboard template failed', str(exc))

    def max_screenpack_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_screenpack_template(root)
            self.reload_project()
            self._max_show_result(result, 'Screenpack starter created')
        except Exception as exc:
            messagebox.showerror('Screenpack starter failed', str(exc))

    def max_sound_autobank_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_sound_autobank(root)
            self.reload_project()
            self._max_show_result(result, 'Sound AutoBank created')
        except Exception as exc:
            messagebox.showerror('Sound AutoBank failed', str(exc))

    def max_quick_test_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_quick_test_suite(root)
            self.reload_project()
            self._max_show_result(result, 'Quick Test Suite written')
        except Exception as exc:
            messagebox.showerror('Quick Test Suite failed', str(exc))
