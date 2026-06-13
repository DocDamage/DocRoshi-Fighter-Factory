from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..factory_max import image_factory_process_folder, make_palette_variants


class ImageFactoryActions:
    def image_factory_choose_input_ui(self):
        folder = filedialog.askdirectory(title='Choose image input folder')
        if folder:
            self.image_factory_in_var.set(folder)
            if not self.image_factory_out_var.get().strip():
                self.image_factory_out_var.set(str(Path(folder).parent / (Path(folder).name + '_processed')))

    def image_factory_choose_output_ui(self):
        folder = filedialog.askdirectory(title='Choose image output folder')
        if folder:
            self.image_factory_out_var.set(folder)

    def image_factory_use_project_defaults_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        inp = root / 'source_sprites'
        out = root / 'processed_sprites'
        inp.mkdir(exist_ok=True)
        out.mkdir(exist_ok=True)
        self.image_factory_in_var.set(str(inp))
        self.image_factory_out_var.set(str(out))
        self.set_text(self.image_factory_output, f'Project sprite folders prepared:\n\nInput: {inp}\nOutput: {out}\n\nPut source PNG/PCX/BMP/GIF/JPG/WEBP files into source_sprites, then run batch macros.')
        self.notebook.select(self.image_factory_frame)

    def image_factory_process_ui(self):
        inp = Path(self.image_factory_in_var.get().strip())
        out = Path(self.image_factory_out_var.get().strip())
        if not inp.exists():
            messagebox.showinfo('Missing input folder', 'Choose an existing input image folder first.')
            return
        if not str(out):
            messagebox.showinfo('Missing output folder', 'Choose an output folder first.')
            return
        try:
            result = image_factory_process_folder(
                inp, out,
                scale_percent=self._plus_float(self.image_factory_scale_var, 100.0) if hasattr(self, '_plus_float') else float(self.image_factory_scale_var.get() or 100),
                trim=bool(self.image_factory_trim_var.get()),
                mirror_x=bool(self.image_factory_mirror_x_var.get()),
                mirror_y=bool(self.image_factory_mirror_y_var.get()),
                canvas_w=self._plus_int(self.image_factory_canvas_w_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_canvas_w_var.get() or 0),
                canvas_h=self._plus_int(self.image_factory_canvas_h_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_canvas_h_var.get() or 0),
                transparent_mode=self.image_factory_transparency_var.get(),
                palette_colors=self._plus_int(self.image_factory_palette_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_palette_var.get() or 0),
                outline=bool(self.image_factory_outline_var.get()),
                shadow=bool(self.image_factory_shadow_var.get()),
            )
            self.set_text(self.image_factory_output, result.to_text())
            self.notebook.select(self.image_factory_frame)
            self.status_var.set('Image Factory batch finished')
        except Exception as exc:
            messagebox.showerror('Image batch failed', str(exc))

    def image_factory_palette_variants_ui(self):
        inp = Path(self.image_factory_in_var.get().strip())
        out_base = Path(self.image_factory_out_var.get().strip() or (str(inp) + '_palettes'))
        if not inp.exists():
            messagebox.showinfo('Missing input folder', 'Choose an existing input image folder first.')
            return
        try:
            result = make_palette_variants(inp, out_base / 'palette_variants', variants=6)
            self.set_text(self.image_factory_output, result.to_text())
            self.notebook.select(self.image_factory_frame)
            self.status_var.set('Palette variants created')
        except Exception as exc:
            messagebox.showerror('Palette variants failed', str(exc))
