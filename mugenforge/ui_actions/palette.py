from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..palette_tools import (
    build_act_from_image,
    read_act,
    remap_palette_order,
    write_act,
    write_palette_json,
)


class PaletteActions:
    def choose_act_palette(self):
        path = filedialog.askopenfilename(
            title='Choose ACT palette',
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if path:
            self.populate_palette_browser(Path(path))
            self.notebook.select(self.palette_frame)

    def populate_palette_browser(self, path: Path):
        try:
            info = read_act(path)
        except Exception as exc:
            messagebox.showerror('Palette load failed', str(exc))
            return
        self.palette_info = info
        if hasattr(self, 'palette_tree'):
            self.palette_tree.delete(*self.palette_tree.get_children())
            for idx, (r, g, b) in enumerate(info.colors):
                self.palette_tree.insert('', 'end', text=str(idx), values=(f'{r}, {g}, {b}', f'#{r:02X}{g:02X}{b:02X}'))
        self.draw_palette_grid()
        lines = [f'Palette: {path.name}', f'Colors: {len(info.colors)}', '']
        if info.warnings:
            lines.append('Warnings:')
            lines += [f'- {w}' for w in info.warnings]
        else:
            lines.append('ACT palette loaded normally.')
        lines.append('\nTip: index 0 is commonly used as the transparent/background color in many sprite workflows. Use the move-to-index-0 button when your transparent color is in the wrong slot.')
        self.set_text(self.palette_info_text, '\n'.join(lines))
        self.status_var.set(f'Loaded palette: {path.name}')

    def draw_palette_grid(self, selected_index: int | None = None):
        if not hasattr(self, 'palette_canvas'):
            return
        self.palette_canvas.delete('all')
        info = self.palette_info
        if not info:
            self.palette_canvas.create_text(20, 20, anchor='nw', text='Open an ACT palette or build one from an image.')
            return
        size = 28
        pad = 8
        cols = 16
        for idx, (r, g, b) in enumerate(info.colors[:256]):
            x = pad + (idx % cols) * size
            y = pad + (idx // cols) * size
            color = f'#{r:02X}{g:02X}{b:02X}'
            outline = 'black' if selected_index == idx else '#777777'
            width = 3 if selected_index == idx else 1
            self.palette_canvas.create_rectangle(x, y, x + size - 3, y + size - 3, fill=color, outline=outline, width=width)
            if idx == 0:
                self.palette_canvas.create_text(x + 3, y + 2, anchor='nw', text='0', fill='white' if (r+g+b) < 384 else 'black', font=('Consolas', 8))

    def on_palette_select(self, event=None):
        if not self.palette_info or not hasattr(self, 'palette_tree'):
            return
        sel = self.palette_tree.selection()
        if not sel:
            return
        try:
            idx = int(self.palette_tree.item(sel[0], 'text'))
        except Exception:
            return
        self.draw_palette_grid(idx)
        r, g, b = self.palette_info.colors[idx]
        self.set_text(self.palette_info_text, f'Palette: {self.palette_info.path.name}\nSelected index: {idx}\nRGB: {r}, {g}, {b}\nHex: #{r:02X}{g:02X}{b:02X}')

    def export_palette_json_ui(self):
        if not self.palette_info:
            messagebox.showinfo('No palette', 'Open an ACT palette first.')
            return
        out = filedialog.asksaveasfilename(
            title='Export palette JSON',
            defaultextension='.json',
            initialfile=self.palette_info.path.with_suffix('.palette.json').name,
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')]
        )
        if not out:
            return
        write_palette_json(self.palette_info, Path(out))
        self.status_var.set(f'Exported palette JSON: {Path(out).name}')
        messagebox.showinfo('Palette exported', f'Wrote:\n{out}')

    def build_act_from_image_ui(self):
        image = filedialog.askopenfilename(
            title='Choose image to extract palette from',
            filetypes=[('Images', '*.png *.pcx *.bmp *.gif'), ('All files', '*.*')]
        )
        if not image:
            return
        out = filedialog.asksaveasfilename(
            title='Save ACT palette',
            defaultextension='.act',
            initialfile=Path(image).with_suffix('.act').name,
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_act_from_image(Path(image), Path(out))
        except Exception as exc:
            messagebox.showerror('Build ACT failed', str(exc))
            return
        self.populate_palette_browser(Path(out))
        self.status_var.set(f'Built ACT palette: {Path(out).name}')
        messagebox.showinfo('ACT palette built', f'Wrote:\n{out}\n\nColors: {len(info.colors)}')

    def palette_move_selected_to_zero_ui(self):
        if not self.palette_info:
            messagebox.showinfo('No palette', 'Open an ACT palette first.')
            return
        sel = self.palette_tree.selection()
        if not sel:
            messagebox.showinfo('No color selected', 'Select the color that should become index 0.')
            return
        try:
            idx = int(self.palette_tree.item(sel[0], 'text'))
        except Exception:
            return
        colors = remap_palette_order(self.palette_info.colors, idx)
        out = filedialog.asksaveasfilename(
            title='Save remapped ACT palette',
            defaultextension='.act',
            initialfile=self.palette_info.path.with_name(self.palette_info.path.stem + '_index0.act').name,
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if not out:
            return
        write_act(Path(out), colors)
        self.populate_palette_browser(Path(out))
        self.status_var.set(f'Remapped palette: {Path(out).name}')
        messagebox.showinfo('Palette remapped', f'Moved selected color {idx} to index 0 and wrote:\n{out}')
