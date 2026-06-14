from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from ..ff_plus_tools import export_move_list, full_project_report, write_creator_manual
from ..studio_plus import (
    auto_fix_project_plus,
    batch_import_sprite_folder_to_sff,
    build_release_zip_plus,
    clone_air_action_variant,
    create_sff_contact_sheet,
    export_action_gif,
    generate_air_from_sff_groups,
    make_project_snapshot,
    make_stage_template,
    studio_plus_report_text,
    write_studio_plus_report,
    write_studio_plus_report_json,
)


class PlusWorkspaceActions:
    def auto_make_playable_prototype_ui(self):
        # Compatibility route for Forge+ tab: use the newer Factory+ smart pass.
        self.factory_smart_complete_ui()

    def auto_beginner_doctor_ui(self):
        # Compatibility route for Forge+ tab: use the newer Factory+ doctor report.
        self.factory_doctor_ui()

    def forge_plus_report_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            text = full_project_report(self.project_root)
        except Exception as exc:
            text = f'Forge+ Doctor failed:\n{exc}'
        self.set_text(self.forge_plus_output, text)
        self.notebook.select(self.forge_plus_frame)

    def forge_plus_export_move_list_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            out = export_move_list(self.project_root)
            self.set_text(self.forge_plus_output, f'Move list exported:\n{out}\n\n' + out.read_text(encoding='utf-8'))
            self.status_var.set(f'Move list exported: {out.name}')
        except Exception as exc:
            messagebox.showerror('Move list failed', str(exc))

    def forge_plus_creator_manual_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            out = write_creator_manual(self.project_root)
            self.set_text(self.forge_plus_output, f'Creator manual written:\n{out}\n\n' + out.read_text(encoding='utf-8'))
            self.status_var.set(f'Creator manual written: {out.name}')
        except Exception as exc:
            messagebox.showerror('Creator manual failed', str(exc))

    def _plus_get_project_root(self):
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _plus_int(self, var, fallback=0):
        try:
            return int(str(var.get()).strip())
        except Exception:
            return fallback

    def _plus_float(self, var, fallback=1.0):
        try:
            return float(str(var.get()).strip())
        except Exception:
            return fallback

    def _plus_find_sff_path(self):
        if self.current_path and self.current_path.suffix.lower() == '.sff':
            return self.current_path
        if self.sff_path and self.sff_path.exists():
            return self.sff_path
        if self.project_root:
            exact = self.project_root / f'{self.project_root.name}.sff'
            if exact.exists():
                return exact
            found = sorted(self.project_root.glob('*.sff'))
            if found:
                return found[0]
        chosen = filedialog.askopenfilename(title='Choose SFF file', filetypes=[('SFF files', '*.sff'), ('All files', '*.*')])
        return Path(chosen) if chosen else None

    def plus_doctor_report_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            text = studio_plus_report_text(root)
            self.set_text(self.plus_output, text)
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Studio Plus Doctor report generated.')
        except Exception as exc:
            messagebox.showerror('Studio Plus Doctor failed', str(exc))

    def plus_write_reports_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            md = write_studio_plus_report(root)
            js = write_studio_plus_report_json(root)
            self.reload_project()
            self.set_text(self.plus_output, f'Wrote Studio Plus reports:\n\n- {md}\n- {js}\n\n' + studio_plus_report_text(root))
            self.notebook.select(self.studio_plus_frame)
            messagebox.showinfo('Reports written', f'Wrote:\n{md}\n{js}')
        except Exception as exc:
            messagebox.showerror('Write reports failed', str(exc))

    def plus_auto_fix_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        if not messagebox.askyesno('Auto Fix / Build Missing Assets', 'This will create/repair project files, append missing standard AIR placeholders with backups, rebuild placeholder SFF/SND assets, and write beginner docs/reports. Continue?'):
            return
        try:
            result = auto_fix_project_plus(root)
            self.reload_project()
            self.set_text(self.plus_output, result.to_text() + '\n' + studio_plus_report_text(root))
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Studio Plus auto-fix completed.')
            messagebox.showinfo('Auto Fix complete', result.to_text())
        except Exception as exc:
            messagebox.showerror('Auto Fix failed', str(exc))

    def plus_snapshot_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            out = make_project_snapshot(root)
            self.set_text(self.plus_output, f'Project snapshot created:\n\n{out}\n\nUse this before heavy edits so you can roll back manually if needed.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Snapshot created: {out.name}')
            messagebox.showinfo('Snapshot created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Snapshot failed', str(exc))

    def plus_release_zip_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            out = build_release_zip_plus(root)
            self.reload_project()
            self.set_text(self.plus_output, f'Release ZIP created:\n\n{out}\n\nThe ZIP includes a generated release manifest and Studio Plus report.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Release ZIP created: {out.name}')
            messagebox.showinfo('Release ZIP created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Release ZIP failed', str(exc))

    def plus_contact_sheet_ui(self):
        sff = self._plus_find_sff_path()
        if not sff:
            return
        default = sff.with_name(sff.stem + '_contact_sheet.png')
        out = filedialog.asksaveasfilename(title='Save SFF contact sheet', defaultextension='.png', initialfile=default.name, initialdir=str(default.parent), filetypes=[('PNG image', '*.png')])
        if not out:
            return
        try:
            written = create_sff_contact_sheet(sff, Path(out))
            self.set_text(self.plus_output, f'SFF contact sheet created:\n\n{written}\n\nThis is useful for browsing sprite group/image IDs visually, similar to a sprite browser but exportable.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Contact sheet created: {written.name}')
            messagebox.showinfo('Contact sheet created', f'Wrote:\n{written}')
        except Exception as exc:
            messagebox.showerror('Contact sheet failed', str(exc))

    def plus_export_action_gif_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        action_no = self._plus_int(self.plus_action_var, 0)
        default = root / f'action_{action_no}_preview.gif'
        out = filedialog.asksaveasfilename(title='Save AIR action GIF', defaultextension='.gif', initialfile=default.name, initialdir=str(root), filetypes=[('GIF image', '*.gif')])
        if not out:
            return
        try:
            written = export_action_gif(root, action_no, Path(out), scale=2, draw_clsn=True)
            self.set_text(self.plus_output, f'Action GIF exported:\n\nAction: {action_no}\nFile: {written}\n\nThe GIF includes sprite preview when available plus Clsn1/Clsn2 overlays.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Action GIF exported: {written.name}')
            messagebox.showinfo('Action GIF exported', f'Wrote:\n{written}')
        except Exception as exc:
            messagebox.showerror('Action GIF failed', str(exc))

    def plus_air_from_sff_ui(self, append: bool = False):
        root = self._plus_get_project_root()
        if not root:
            return
        if append and not messagebox.askyesno('Append AIR from SFF groups', 'This will append generated AIR actions to the project AIR file and create a backup first. Continue?'):
            return
        try:
            ticks = self._plus_int(self.plus_ticks_var, 5)
            out = generate_air_from_sff_groups(root, ticks=ticks, append=append)
            self.reload_project()
            action = 'Appended generated AIR actions to' if append else 'Generated AIR action file'
            self.set_text(self.plus_output, f'{action}:\n\n{out}\n\nEach SFF group becomes an AIR action and images are sorted by image number. Review timing and labels after generation.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'AIR generated from SFF groups: {out.name}')
            messagebox.showinfo('AIR generated', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Generate AIR failed', str(exc))

    def plus_clone_air_action_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        source = self._plus_int(self.plus_clone_source_var, 200)
        new = self._plus_int(self.plus_clone_new_var, 1200)
        tick_scale = self._plus_float(self.plus_tick_scale_var, 1.0)
        x_offset = self._plus_int(self.plus_x_offset_var, 0)
        y_offset = self._plus_int(self.plus_y_offset_var, 0)
        try:
            out = clone_air_action_variant(root, source, new, tick_scale=tick_scale, x_offset=x_offset, y_offset=y_offset)
            self.reload_project()
            self.set_text(self.plus_output, f'Cloned AIR action variant:\n\nSource action: {source}\nNew action: {new}\nTick scale: {tick_scale}\nOffset: {x_offset},{y_offset}\nChanged: {out}\n\nUse this for fast variants like EX timing, mirrored-feel timing tests, intro/win reuse, and prototype specials.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Cloned AIR action {source} -> {new}')
            messagebox.showinfo('AIR action cloned', f'Updated:\n{out}')
        except Exception as exc:
            messagebox.showerror('Clone AIR action failed', str(exc))

    def plus_batch_import_sprites_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        folder = filedialog.askdirectory(title='Choose folder of sprite images')
        if not folder:
            return
        default = root / f'{root.name}_batch_import.sff'
        out = filedialog.asksaveasfilename(title='Save built SFF v1', defaultextension='.sff', initialfile=default.name, initialdir=str(root), filetypes=[('SFF files', '*.sff')])
        if not out:
            return
        try:
            manifest, air_snippet = batch_import_sprite_folder_to_sff(
                Path(folder), Path(out),
                default_group=self._plus_int(self.plus_import_group_var, 9000),
                axis_x=self._plus_int(self.plus_axis_x_var, 32),
                axis_y=self._plus_int(self.plus_axis_y_var, 64),
                ticks=self._plus_int(self.plus_ticks_var, 5),
            )
            self.reload_project()
            self.set_text(self.plus_output, f'Batch sprite import complete:\n\nSFF: {out}\nManifest: {manifest}\nAIR snippets: {air_snippet}\n\nFilename tips: g200_i0.png and 200_0.png keep their IDs. Other files use the default group and sorted image index.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Batch sprite folder imported to SFF.')
            messagebox.showinfo('Batch import complete', f'Wrote:\n{out}\n{manifest}\n{air_snippet}')
        except Exception as exc:
            messagebox.showerror('Batch sprite import failed', str(exc))

    def plus_stage_template_ui(self):
        parent = self.project_root.parent if self.project_root else Path(filedialog.askdirectory(title='Choose parent folder for stage template') or '')
        if not parent or not str(parent):
            return
        name = simpledialog.askstring('Stage Template', 'Stage folder/name:', initialvalue='new_stage')
        if not name:
            return
        try:
            out = make_stage_template(parent, name)
            self.set_text(self.plus_output, f'Stage template created:\n\n{out}\n\nThis expands MugenForge beyond characters with a beginner-safe stage DEF starter. Add real stage art/SFF later.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Stage template created: {out.name}')
            messagebox.showinfo('Stage template created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Stage template failed', str(exc))
