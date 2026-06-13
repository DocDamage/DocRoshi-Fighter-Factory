from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import AppBackedTab


class ImageFactoryTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        img = ttk.Frame(self.notebook)
        self.frame = img
        self.app.image_factory_frame = img
        img.columnconfigure(1, weight=1)
        img.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(img, text='Image Factory / Built-in Sprite Image Macros', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(
            header,
            text='Batch-process source sprites without coding: transparency keying, trim, mirror, scale, pad to canvas, outline, shadow, palette reduction, and palette variant folders.',
            wraplength=1120,
            justify='left',
        ).grid(row=0, column=0, sticky='ew')

        self.app.image_factory_in_var = tk.StringVar(value='')
        self.app.image_factory_out_var = tk.StringVar(value='')
        self.app.image_factory_scale_var = tk.StringVar(value='100')
        self.app.image_factory_canvas_w_var = tk.StringVar(value='0')
        self.app.image_factory_canvas_h_var = tk.StringVar(value='0')
        self.app.image_factory_palette_var = tk.StringVar(value='0')
        self.app.image_factory_transparency_var = tk.StringVar(value='none')
        self.app.image_factory_trim_var = tk.BooleanVar(value=True)
        self.app.image_factory_mirror_x_var = tk.BooleanVar(value=False)
        self.app.image_factory_mirror_y_var = tk.BooleanVar(value=False)
        self.app.image_factory_outline_var = tk.BooleanVar(value=False)
        self.app.image_factory_shadow_var = tk.BooleanVar(value=False)

        left = ttk.Frame(img, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        box = ttk.LabelFrame(left, text='Folders', padding=(6, 6))
        box.grid(row=0, column=0, sticky='ew')
        ttk.Label(box, text='input').grid(row=0, column=0, sticky='e')
        ttk.Entry(box, textvariable=self.app.image_factory_in_var, width=46).grid(row=0, column=1, sticky='w')
        ttk.Label(box, text='output').grid(row=1, column=0, sticky='e')
        ttk.Entry(box, textvariable=self.app.image_factory_out_var, width=46).grid(row=1, column=1, sticky='w')
        ttk.Button(box, text='Choose Input Folder', command=self.app.image_factory_choose_input_ui).grid(row=2, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(box, text='Choose Output Folder', command=self.app.image_factory_choose_output_ui).grid(row=3, column=0, columnspan=2, sticky='ew', pady=2)

        opts = ttk.LabelFrame(left, text='Macros', padding=(6, 6))
        opts.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        items = [
            ('scale %', self.app.image_factory_scale_var),
            ('canvas w', self.app.image_factory_canvas_w_var),
            ('canvas h', self.app.image_factory_canvas_h_var),
            ('palette colors', self.app.image_factory_palette_var),
        ]
        for i, (label, var) in enumerate(items):
            ttk.Label(opts, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=1)
            ttk.Entry(opts, textvariable=var, width=10).grid(row=i, column=1, sticky='w', padx=2, pady=1)
        ttk.Label(opts, text='transparency').grid(row=len(items), column=0, sticky='e', padx=2, pady=1)
        ttk.Combobox(opts, textvariable=self.app.image_factory_transparency_var, values=('none', 'top-left', 'magenta'), width=10, state='readonly').grid(row=len(items), column=1, sticky='w', padx=2, pady=1)
        checks = [
            ('trim', self.app.image_factory_trim_var),
            ('mirror X', self.app.image_factory_mirror_x_var),
            ('mirror Y', self.app.image_factory_mirror_y_var),
            ('outline', self.app.image_factory_outline_var),
            ('shadow', self.app.image_factory_shadow_var),
        ]
        for j, (label, var) in enumerate(checks, start=len(items) + 1):
            ttk.Checkbutton(opts, text=label, variable=var).grid(row=j, column=0, columnspan=2, sticky='w')

        actions = ttk.LabelFrame(left, text='Actions', padding=(6, 6))
        actions.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(actions, text='Run Batch Image Macros', command=self.app.image_factory_process_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Make Palette Variant Folders', command=self.app.image_factory_palette_variants_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Use Project source_sprites -> processed_sprites', command=self.app.image_factory_use_project_defaults_ui).grid(row=2, column=0, sticky='ew', pady=2)

        right = ttk.Frame(img, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.image_factory_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.app.image_factory_output.yview)
        self.app.image_factory_output.configure(yscrollcommand=sy.set)
        self.app.image_factory_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        self.notebook.add(img, text='Image Factory')
        self._set_text(self.app.image_factory_output, 'Choose a source folder of images. Output is always written to a separate folder so originals stay safe.')
