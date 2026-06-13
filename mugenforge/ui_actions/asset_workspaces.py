from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from ..ff_plus_tools import (
    build_act_from_folder,
    build_sff_from_image_folder,
    convert_images_to_pcx,
    create_stage_from_image,
    launch_mugen,
    make_air_from_image_sequence,
    make_animation_gif,
    make_sprite_contact_sheet,
    normalize_sprite_folder,
    summarize_image_folder,
    write_mugen_launch_config,
)


class AssetWorkspaceActions:
    def _sprite_lab_folder(self) -> Path | None:
        raw = self.sprite_lab_folder_var.get().strip()
        if not raw:
            messagebox.showinfo('No folder', 'Choose an image folder first.')
            return None
        folder = Path(raw)
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror('Folder not found', str(folder))
            return None
        return folder

    def _sprite_lab_int(self, var: tk.StringVar, default: int) -> int:
        try:
            return int(var.get().strip())
        except Exception:
            return default

    def sprite_lab_choose_folder_ui(self):
        path = filedialog.askdirectory(title='Choose sprite image folder')
        if path:
            self.sprite_lab_folder_var.set(path)
            self.sprite_lab_summary_ui()

    def sprite_lab_summary_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        try:
            self.set_text(self.sprite_lab_output, summarize_image_folder(folder))
        except Exception as exc:
            messagebox.showerror('Sprite summary failed', str(exc))

    def sprite_lab_contact_sheet_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save contact sheet', defaultextension='.png', initialfile='mugenforge_contact_sheet.png', filetypes=[('PNG', '*.png')])
        if not out:
            return
        try:
            path = make_sprite_contact_sheet(folder, Path(out))
            self.set_text(self.sprite_lab_output, f'Contact sheet written:\n{path}')
            self.status_var.set(f'Contact sheet: {path.name}')
        except Exception as exc:
            messagebox.showerror('Contact sheet failed', str(exc))

    def sprite_lab_normalize_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out_dir = filedialog.askdirectory(title='Choose output folder for normalized sprites')
        if not out_dir:
            return
        try:
            manifest = normalize_sprite_folder(
                folder, Path(out_dir),
                canvas_w=self._sprite_lab_int(self.sprite_lab_canvas_w_var, 96),
                canvas_h=self._sprite_lab_int(self.sprite_lab_canvas_h_var, 96),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                axis_x=self._sprite_lab_int(self.sprite_lab_axis_x_var, 48),
                axis_y=self._sprite_lab_int(self.sprite_lab_axis_y_var, 88),
                scale_percent=self._sprite_lab_int(self.sprite_lab_scale_var, 100),
                trim=bool(self.sprite_lab_trim_var.get()),
            )
            self.set_text(self.sprite_lab_output, f'Normalized sprites and manifest written:\n{manifest}\n\nUse Sheet Import / Build SFF v1 or Sprite Lab Build SFF v1 next.')
            self.status_var.set(f'Sprite manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Normalize failed', str(exc))

    def sprite_lab_build_sff_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        initial = f'{self.project_root.name if self.project_root else folder.name}.sff'
        out = filedialog.asksaveasfilename(title='Save built SFF v1', defaultextension='.sff', initialfile=initial, filetypes=[('SFF', '*.sff')])
        if not out:
            return
        try:
            out_path = build_sff_from_image_folder(
                folder, Path(out),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                canvas_w=self._sprite_lab_int(self.sprite_lab_canvas_w_var, 96),
                canvas_h=self._sprite_lab_int(self.sprite_lab_canvas_h_var, 96),
                axis_x=self._sprite_lab_int(self.sprite_lab_axis_x_var, 48),
                axis_y=self._sprite_lab_int(self.sprite_lab_axis_y_var, 88),
            )
            self.set_text(self.sprite_lab_output, f'SFF v1 built from folder:\n{out_path}\n\nOpen it in the project tree or Sprites tab to inspect records.')
            self.status_var.set(f'SFF built: {out_path.name}')
            if out_path.exists():
                self.populate_sprite_browser(out_path)
                self.notebook.select(5)
        except Exception as exc:
            messagebox.showerror('SFF build failed', str(exc))

    def sprite_lab_air_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save generated AIR block', defaultextension='.air', initialfile='generated_action.air', filetypes=[('AIR', '*.air'), ('Text', '*.txt')])
        if not out:
            return
        try:
            path = make_air_from_image_sequence(
                folder, Path(out),
                action=self._sprite_lab_int(self.sprite_lab_action_var, 200),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                ticks=self._sprite_lab_int(self.sprite_lab_ticks_var, 5),
            )
            self.set_text(self.sprite_lab_output, f'AIR action block written:\n{path}\n\n' + path.read_text(encoding='utf-8'))
            self.status_var.set(f'AIR block: {path.name}')
        except Exception as exc:
            messagebox.showerror('AIR generation failed', str(exc))

    def sprite_lab_gif_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save GIF preview', defaultextension='.gif', initialfile='animation_preview.gif', filetypes=[('GIF', '*.gif')])
        if not out:
            return
        try:
            ms = max(1, self._sprite_lab_int(self.sprite_lab_ticks_var, 5) * 1000 // 60)
            path = make_animation_gif(folder, Path(out), frame_ms=ms)
            self.set_text(self.sprite_lab_output, f'GIF preview written:\n{path}')
            self.status_var.set(f'GIF preview: {path.name}')
        except Exception as exc:
            messagebox.showerror('GIF failed', str(exc))

    def sprite_lab_palette_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save ACT palette', defaultextension='.act', initialfile='palette_from_folder.act', filetypes=[('ACT', '*.act')])
        if not out:
            return
        try:
            path = build_act_from_folder(folder, Path(out))
            self.set_text(self.sprite_lab_output, f'ACT palette built from folder:\n{path}\n\nOpen it in the Palettes tab to inspect colors.')
            self.status_var.set(f'ACT palette: {path.name}')
        except Exception as exc:
            messagebox.showerror('Palette build failed', str(exc))

    def sprite_lab_pcx_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out_dir = filedialog.askdirectory(title='Choose output folder for PCX files')
        if not out_dir:
            return
        try:
            outs = convert_images_to_pcx(folder, Path(out_dir))
            self.set_text(self.sprite_lab_output, f'Converted {len(outs)} image(s) to PCX in:\n{out_dir}\n\n' + '\n'.join(str(p.name) for p in outs[:120]))
            self.status_var.set(f'PCX converted: {len(outs)} file(s)')
        except Exception as exc:
            messagebox.showerror('PCX conversion failed', str(exc))

    def stage_choose_image_ui(self):
        path = filedialog.askopenfilename(title='Choose stage background image', filetypes=[('Images', '*.png *.pcx *.bmp *.jpg *.jpeg *.webp *.gif'), ('All files', '*.*')])
        if path:
            self.stage_image_var.set(path)
            if not self.stage_name_var.get().strip() or self.stage_name_var.get() == 'new_stage':
                self.stage_name_var.set(Path(path).stem)

    def stage_choose_output_ui(self):
        path = filedialog.askdirectory(title='Choose stages output folder')
        if path:
            self.stage_out_dir_var.set(path)

    def stage_create_ui(self):
        image = Path(self.stage_image_var.get().strip())
        out_dir = Path(self.stage_out_dir_var.get().strip() or (self.project_root.parent if self.project_root else Path.home()))
        if not image.exists():
            messagebox.showerror('Missing image', 'Choose a valid background image first.')
            return
        try:
            z = self.stage_zoffset_var.get().strip()
            def_path = create_stage_from_image(
                image, out_dir,
                stage_name=self.stage_name_var.get().strip() or image.stem,
                zoffset=int(z) if z else None,
                bound_width=int(self.stage_bound_var.get().strip() or '320'),
            )
            self.set_text(self.stage_output, f'Stage created:\n{def_path}\n\nFiles are in:\n{def_path.parent}\n\nOpen the DEF to tune camera, zoffset, music, and deltas.')
            self.status_var.set(f'Stage created: {def_path.name}')
        except Exception as exc:
            messagebox.showerror('Stage build failed', str(exc))

    def run_choose_mugen_exe_ui(self):
        path = filedialog.askopenfilename(title='Choose M.U.G.E.N executable', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if path:
            self.run_mugen_exe_var.set(path)

    def run_save_launch_config_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        exe = self.run_mugen_exe_var.get().strip()
        if not exe:
            messagebox.showinfo('No executable', 'Choose your M.U.G.E.N executable first.')
            return
        try:
            out = write_mugen_launch_config(self.project_root, Path(exe))
            self.set_text(self.run_output, f'Launch config written:\n{out}\n\nMugenForge does not include M.U.G.E.N. This only stores the path to your local executable.')
        except Exception as exc:
            messagebox.showerror('Launch config failed', str(exc))

    def run_launch_mugen_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            proc = launch_mugen(self.project_root)
            self.set_text(self.run_output, f'Launched M.U.G.E.N. Process id: {proc.pid}\n\nUse your engine window for live testing.')
        except Exception as exc:
            messagebox.showerror('Launch failed', str(exc))

    def run_select_def_snippet_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        snippet = f'; Add this to data/select.def under [Characters]\n{self.project_root.name}/{self.project_root.name}.def\n'
        self.set_text(self.run_output, snippet)
