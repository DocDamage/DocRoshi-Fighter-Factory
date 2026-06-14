from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from ..sff_codec import (
    build_sff_v1_from_manifest,
    build_sff_v1_from_replacement_manifest,
    export_all_sprites,
    export_sprite,
    read_sff,
    stage_sff_replacement_manifest,
    summarize_manifest_for_sff,
    summarize_replacement_manifest,
    try_convert_to_png,
)
from ..spritesheet_tools import (
    compute_grid_slices,
    export_grid_slices,
    make_air_action_from_slices,
    make_preview_image,
    write_manifest,
)


class SpritePipelineActions:
    def populate_sprite_browser(self, path: Path):
        self.sff_path = path
        self.sff_info = read_sff(path)
        self.sprite_tree.delete(*self.sprite_tree.get_children())
        self.sprite_canvas.delete('all')
        self.current_preview_image = None
        lines = [
            f'SFF: {path.name}',
            f'Version bytes: {self.sff_info.version_text}',
            f'Header sprites: {self.sff_info.sprite_count}',
            f'Parsed sprites: {len(self.sff_info.sprites)}',
            f'Supported export: {"yes" if self.sff_info.is_supported_for_extraction else "metadata only"}',
        ]
        if self.sff_info.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in self.sff_info.warnings[:8])
        self.set_text(self.sprite_info, '\n'.join(lines))
        for spr in self.sff_info.sprites:
            self.sprite_tree.insert('', 'end', text=str(spr.index), values=(spr.group, spr.image, f'{spr.x},{spr.y}', f'{spr.length:,}', spr.format_hint), tags=(str(spr.index),))
        if self.sff_info.sprites:
            first = self.sprite_tree.get_children()[0]
            self.sprite_tree.selection_set(first)
            self.sprite_tree.focus(first)
            self.on_sprite_select()

    def _selected_sprite(self):
        if not self.sff_info:
            return None
        sel = self.sprite_tree.selection()
        if not sel:
            return None
        try:
            idx = int(self.sprite_tree.item(sel[0], 'tags')[0])
        except Exception:
            return None
        for spr in self.sff_info.sprites:
            if spr.index == idx:
                return spr
        return None

    def on_sprite_select(self, event=None):
        spr = self._selected_sprite()
        if not spr or not self.sff_path:
            return
        lines = [
            f'Sprite #{spr.index}',
            f'Group/Image: {spr.group},{spr.image}',
            f'Axis: {spr.x},{spr.y}',
            f'Payload bytes: {spr.length:,}',
            f'Payload offset: 0x{spr.data_offset:X}',
            f'Format hint: {spr.format_hint}',
            f'Same palette flag: {spr.same_palette}',
        ]
        if spr.comment:
            lines.append(f'Comment: {spr.comment}')
        self.set_text(self.sprite_info, '\n'.join(lines))
        self.sprite_canvas.delete('all')
        self.current_preview_image = None
        if spr.format_hint not in {'pcx', 'png'}:
            self.sprite_canvas.create_text(20, 20, anchor='nw', text='Preview unavailable for this payload type.')
            return
        tmp_dir = Path.home() / '.mugenforge_preview'
        try:
            exported = export_sprite(self.sff_path, spr, tmp_dir)
            preview_path = exported
            if exported.suffix.lower() == '.pcx':
                png_path = exported.with_suffix('.png')
                if try_convert_to_png(exported, png_path):
                    preview_path = png_path
                else:
                    self.sprite_canvas.create_text(20, 20, anchor='nw', text='PCX exported. Install Pillow for in-app PCX preview.\nUse Export Selected to save it.')
                    return
            img = tk.PhotoImage(file=str(preview_path))
            self.current_preview_image = img
            cw = max(360, self.sprite_canvas.winfo_width() or 360)
            ch = max(360, self.sprite_canvas.winfo_height() or 360)
            self.sprite_canvas.create_image(cw//2, ch//2, image=img)
        except Exception as exc:
            self.sprite_canvas.create_text(20, 20, anchor='nw', text=f'Preview failed: {exc}')

    def export_selected_sprite(self):
        spr = self._selected_sprite()
        if not spr or not self.sff_path:
            messagebox.showinfo('No sprite selected', 'Open an SFF file and select a sprite first.')
            return
        out_dir = filedialog.askdirectory(title='Choose sprite export folder')
        if not out_dir:
            return
        out = export_sprite(self.sff_path, spr, Path(out_dir))
        self.status_var.set(f'Exported sprite: {out}')
        messagebox.showinfo('Exported', f'Exported:\n{out}')

    def export_sff_sprites(self):
        path = self.sff_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.sff':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SFF open', 'Open an .sff file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SFF sprite export')
        if not out_dir:
            return
        outputs = export_all_sprites(path, Path(out_dir))
        self.status_var.set(f'Exported {len(outputs)} sprites from {path.name}')
        messagebox.showinfo('Export complete', f'Exported {len(outputs)} sprite payloads.\n\nFolder:\n{out_dir}')

    def stage_sff_replacement(self):
        path = self.sff_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.sff':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SFF open', 'Open an .sff file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SFF replacement staging')
        if not out_dir:
            return
        try:
            manifest = stage_sff_replacement_manifest(path, Path(out_dir))
            summary = summarize_replacement_manifest(manifest)
            self.set_text(self.sprite_info, summary)
            self.status_var.set(f'Staged SFF replacement manifest: {manifest.name}')
            messagebox.showinfo('Replacement manifest created', f'Created:\n{manifest}\n\nEdit the exported sprite files or set replace_with paths, then build a replaced SFF v1.')
        except Exception as exc:
            messagebox.showerror('SFF replacement staging failed', str(exc))

    def _ask_replacement_manifest_path(self):
        path = filedialog.askopenfilename(
            title='Choose SFF replacement manifest',
            filetypes=[('MugenForge SFF replacement manifest', 'mugenforge_sff_replacement_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_sff_replacement_manifest(self):
        manifest = self._ask_replacement_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sprite_info, summarize_replacement_manifest(manifest))
            self.status_var.set(f'Inspected replacement manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Replacement manifest inspect failed', str(exc))

    def build_replaced_sff(self):
        manifest = self._ask_replacement_manifest_path()
        if not manifest:
            return
        out = filedialog.asksaveasfilename(
            title='Save rebuilt SFF v1 file',
            initialfile='rebuilt_replacement.sff',
            defaultextension='.sff',
            filetypes=[('MUGEN SFF', '*.sff'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_sff_v1_from_replacement_manifest(manifest, Path(out))
            msg = [
                f'Built replaced SFF v1: {out}',
                f'Sprites: {len(info.sprites)}',
                f'Layout: {info.variant}',
                '',
                'Important: this creates a fresh SFF v1-style PCX chain. It does not patch or preserve SFF v2 tables/compression.',
            ]
            if info.warnings:
                msg += ['', 'Warnings:'] + [f'- {w}' for w in info.warnings[:8]]
            self.set_text(self.sprite_info, '\n'.join(msg))
            self.populate_sprite_browser(Path(out))
            self.status_var.set(f'Built replaced SFF v1: {Path(out).name}')
            messagebox.showinfo('Replaced SFF build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('Replaced SFF build failed', str(exc))

    def _sheet_int(self, name: str) -> int:
        try:
            return int(self.sheet_vars[name].get())
        except Exception as exc:
            raise ValueError(f'{name} must be an integer.') from exc

    def choose_sprite_sheet(self):
        path = filedialog.askopenfilename(title='Choose PNG sprite sheet', filetypes=[('PNG images', '*.png'), ('All files', '*.*')])
        if not path:
            return
        self.sheet_path = Path(path)
        self.status_var.set(f'Sprite sheet selected: {self.sheet_path.name}')
        self.preview_sprite_sheet_grid()

    def _compute_current_sheet_slices(self):
        if not self.sheet_path:
            raise ValueError('Choose a PNG sprite sheet first.')
        return compute_grid_slices(
            self.sheet_path,
            self._sheet_int('cell_w'), self._sheet_int('cell_h'),
            self._sheet_int('cols'), self._sheet_int('rows'),
            self._sheet_int('margin_x'), self._sheet_int('margin_y'),
            self._sheet_int('space_x'), self._sheet_int('space_y'),
            self._sheet_int('group'), self._sheet_int('start_image'),
            self._sheet_int('axis_x'), self._sheet_int('axis_y'),
        )

    def preview_sprite_sheet_grid(self):
        try:
            self.sheet_slices = self._compute_current_sheet_slices()
            self.sheet_tree.delete(*self.sheet_tree.get_children())
            for sl in self.sheet_slices:
                self.sheet_tree.insert('', 'end', text=str(sl.index), values=(sl.group, sl.image, f'{sl.x},{sl.y},{sl.w},{sl.h}', f'{sl.axis_x},{sl.axis_y}', sl.filename))
            self.sheet_canvas.delete('all')
            self.sheet_preview_photo = make_preview_image(self.sheet_path, self.sheet_slices)
            self.sheet_canvas.create_image(10, 10, anchor='nw', image=self.sheet_preview_photo)
            info = [
                f'Sheet: {self.sheet_path}',
                f'Slices: {len(self.sheet_slices)}',
                'This creates a staged PNG slice set and JSON manifest. Use Build SFF v1 to compile a simple SFF from the manifest.',
                'Use Append AIR Action while an AIR file is open to add matching group/image frame lines.',
                'Use Build SFF v1 after exporting slices + manifest to create a starter SFF.',
            ]
            self.set_text(self.sheet_info, '\n'.join(info))
        except Exception as exc:
            messagebox.showerror('Sprite sheet preview failed', str(exc))

    def export_sprite_sheet_slices(self):
        try:
            if not self.sheet_slices:
                self.sheet_slices = self._compute_current_sheet_slices()
            out_dir = filedialog.askdirectory(title='Choose output folder for staged sprite slices')
            if not out_dir:
                return
            out_path = Path(out_dir)
            outputs = export_grid_slices(self.sheet_path, self.sheet_slices, out_path)
            manifest = write_manifest(self.sheet_path, self.sheet_slices, out_path / 'mugenforge_sprite_manifest.json')
            self.status_var.set(f'Exported {len(outputs)} staged sprites + manifest')
            messagebox.showinfo('Export complete', f'Exported {len(outputs)} PNG slices.\nManifest:\n{manifest}')
        except Exception as exc:
            messagebox.showerror('Sprite sheet export failed', str(exc))

    def append_air_action_from_sheet(self):
        try:
            if not self.sheet_slices:
                self.sheet_slices = self._compute_current_sheet_slices()
            action_number = simpledialog.askinteger('AIR Action Number', 'Action number to append:', initialvalue=self._sheet_int('group'))
            if action_number is None:
                return
            ticks = self._sheet_int('ticks')
            block = make_air_action_from_slices(action_number, self.sheet_slices, ticks)
            if self.current_path and self.current_path.suffix.lower() == '.air':
                self.editor.configure(state='normal')
                existing = self.editor.get('1.0', 'end-1c').rstrip()
                new_text = existing + '\n\n' + block
                self.editor.delete('1.0', 'end')
                self.editor.insert('1.0', new_text)
                self.editor.edit_modified(True)
                self.dirty = True
                self.populate_air_timeline(new_text)
                self.populate_animation_player(new_text)
                self.populate_clsn_editor(new_text)
                self.status_var.set(f'Appended AIR action {action_number} from sprite sheet staging')
                messagebox.showinfo('AIR updated in editor', 'Action block was appended to the editor buffer. Review it, then save the AIR file.')
            else:
                out = filedialog.asksaveasfilename(title='Save AIR action block', defaultextension='.air', filetypes=[('AIR/Text', '*.air'), ('Text', '*.txt')])
                if not out:
                    return
                Path(out).write_text(block, encoding='utf-8')
                self.status_var.set(f'Saved AIR action block: {out}')
        except Exception as exc:
            messagebox.showerror('Append AIR action failed', str(exc))

    def _ask_manifest_path(self):
        # Prefer the last sheet export folder only when the user selects it explicitly; this avoids guessing.
        path = filedialog.askopenfilename(
            title='Choose MugenForge sprite manifest',
            filetypes=[('MugenForge manifest', 'mugenforge_sprite_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_sprite_manifest(self):
        manifest = self._ask_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sheet_info, summarize_manifest_for_sff(manifest))
            self.notebook.select(6)
            self.status_var.set(f'Inspected manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Manifest inspect failed', str(exc))

    def build_sff_from_sheet_manifest(self):
        manifest = self._ask_manifest_path()
        if not manifest:
            return
        default_name = 'staged_build.sff'
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            source_sheet = Path(str(data.get('source_sheet', '')))
            if source_sheet.name:
                default_name = source_sheet.stem + '.sff'
        except Exception:
            pass
        out = filedialog.asksaveasfilename(
            title='Save built SFF v1 file',
            initialfile=default_name,
            defaultextension='.sff',
            filetypes=[('MUGEN SFF', '*.sff'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_sff_v1_from_manifest(manifest, Path(out))
            msg = [
                f'Built SFF: {out}',
                f'Parsed sprites after build: {len(info.sprites)}',
                f'Header sprite count: {info.sprite_count}',
                '',
                'Important: this is an SFF v1-style PCX builder for staged sprites. It is meant for starter characters and pipeline testing, not full SFF v2 parity yet.',
            ]
            if info.warnings:
                msg.append('')
                msg.append('Warnings:')
                msg.extend(f'- {w}' for w in info.warnings[:8])
            self.status_var.set(f'Built SFF v1: {Path(out).name}')
            self.set_text(self.sheet_info, '\n'.join(msg))
            if Path(out).exists():
                self.populate_sprite_browser(Path(out))
                self.notebook.select(5)
            messagebox.showinfo('SFF build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('SFF build failed', str(exc))
