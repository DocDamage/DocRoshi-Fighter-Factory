from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..automation_bank import (
    apply_beginner_pack,
    apply_feature_package,
    apply_kit,
    auto_setup_project,
    beginner_project_status,
    build_feature_package,
    export_code_bank_template,
    feature_bank_stats_text,
    kit_preview_text,
    make_placeholder_sprite_sheet,
    package_preview_text,
    preset_by_display,
)
from ..no_code_director import (
    archetype_preview_text,
    no_code_director_summary,
    one_click_playable_skeleton,
    write_no_code_dashboard,
)


class FeatureBankActions:
    def _selected_auto_preset(self):
        if not hasattr(self, 'auto_feature_list'):
            return None
        sel = self.auto_feature_list.curselection()
        if not sel:
            if self.auto_preset_items:
                return preset_by_display(self.auto_preset_items[0])
            return None
        return preset_by_display(self.auto_feature_list.get(sel[0]))

    def auto_on_preset_select(self, event=None):
        preset = self._selected_auto_preset()
        if not preset:
            return
        lines = [f'{preset.name}', '', preset.description, '', f'Category: {preset.category}', f'Difficulty: {preset.difficulty}']
        if preset.beginner_notes:
            lines.append('\nBeginner notes:')
            lines += [f'- {note}' for note in preset.beginner_notes]
        lines.append('\nUse Preview Selected to see the generated code before applying it.')
        self.set_text(self.auto_output, '\n'.join(lines))

    def auto_preview_feature(self):
        preset = self._selected_auto_preset()
        if not preset:
            return
        package = build_feature_package(preset.feature_id)
        self.auto_last_package = package
        self.set_text(self.auto_output, package_preview_text(package))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_apply_selected_feature(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        preset = self._selected_auto_preset()
        if not preset:
            return
        package = build_feature_package(preset.feature_id)
        result = apply_feature_package(self.project_root, package)
        text = package_preview_text(package)
        text += '\n' + '=' * 72 + '\nAPPLY RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n'
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set(f'Feature Bank applied: {preset.name}')
        messagebox.showinfo('Feature applied', result.to_text())

    def auto_apply_beginner_pack_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        if not messagebox.askyesno('Install Beginner Pack', 'This will append multiple beginner features with backups: setup basics, attacks, fireball, dashes, taunt, and debug overlay. Continue?'):
            return
        result = apply_beginner_pack(self.project_root)
        text = 'Beginner Pack applied.\n\n' + result.to_text() + '\n\n' + beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set('Beginner Pack installed.')
        messagebox.showinfo('Beginner Pack complete', result.to_text())

    def auto_setup_project_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        result = auto_setup_project(root)
        self.load_project(root)
        text = 'Auto Setup / Repair complete.\n\n' + result.to_text() + '\n\n' + beginner_project_status(root)
        self.set_text(self.auto_output, text)
        self.notebook.select(self.auto_frame)
        self.status_var.set('Project setup/repair complete.')
        messagebox.showinfo('Setup complete', result.to_text())

    def auto_project_status_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        text = beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.notebook.select(self.auto_frame)

    def auto_export_code_bank_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        out = export_code_bank_template(self.project_root)
        self.set_text(self.auto_output, f'Wrote editable feature-bank planning template:\n{out}\n\nThis file is for planning and notes. Built-in Feature Bank presets are available directly in this tab.')
        self.reload_project()
        self.status_var.set(f'Wrote {out.name}')
        messagebox.showinfo('Code bank template written', f'Wrote:\n{out}')

    def auto_preview_kit(self):
        if not hasattr(self, 'auto_kit_var'):
            return
        kit_name = self.auto_kit_var.get().strip()
        if not kit_name:
            return
        self.set_text(self.auto_output, kit_preview_text(kit_name))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_apply_kit_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        kit_name = self.auto_kit_var.get().strip() if hasattr(self, 'auto_kit_var') else ''
        if not kit_name:
            messagebox.showinfo('No kit selected', 'Choose a Creator Kit first.')
            return
        if not messagebox.askyesno('Install Creator Kit', f'This will append the selected kit with backups:\n\n{kit_name}\n\nContinue?'):
            return
        result = apply_kit(self.project_root, kit_name)
        text = kit_preview_text(kit_name) + '\n' + '=' * 72 + '\nAPPLY RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set(f'Creator Kit installed: {kit_name}')
        messagebox.showinfo('Creator Kit complete', result.to_text())

    def auto_feature_bank_stats_ui(self):
        self.set_text(self.auto_output, feature_bank_stats_text())
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_preview_archetype(self):
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        self.set_text(self.auto_output, archetype_preview_text(name))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_write_dashboard_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        result = write_no_code_dashboard(root, name)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        text = archetype_preview_text(name) + '\n' + '=' * 72 + '\nDASHBOARD / CHECKLIST RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + no_code_director_summary(root, name)
        self.set_text(self.auto_output, text)
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('No-code dashboard/checklists written.')
        messagebox.showinfo('No-code dashboard written', result.to_text())

    def auto_one_click_skeleton_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        prompt = (
            'This will create/repair a project, install the selected archetype kit, generate no-code docs, '
            'make placeholder sprites/sounds, and try to build starter SFF/SND files. Backups are used for generated code.\n\n'
            f'Archetype: {name or "Balanced Arcade Fighter"}\n\nContinue?'
        )
        if not messagebox.askyesno('One-Click Playable Skeleton', prompt):
            return
        result = one_click_playable_skeleton(root, name)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        text = archetype_preview_text(name) + '\n' + '=' * 72 + '\nONE-CLICK SKELETON RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + beginner_project_status(root)
        self.set_text(self.auto_output, text)
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('One-click playable skeleton generated.')
        if result.warnings:
            messagebox.showwarning('One-click skeleton complete with warnings', result.to_text())
        else:
            messagebox.showinfo('One-click skeleton complete', result.to_text())

    def auto_make_placeholder_sheet_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        result = make_placeholder_sprite_sheet(root)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        self.set_text(self.auto_output, 'Placeholder Sprite Sheet result:\n\n' + result.to_text() + '\n\nNext: open Sheet Import, load the generated PNG, use the plan JSON settings, export slices, then build SFF v1.')
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('Placeholder sprite sheet generated.')
        if result.warnings:
            messagebox.showwarning('Placeholder sheet', result.to_text())
        else:
            messagebox.showinfo('Placeholder sheet generated', result.to_text())
