from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import AppBackedTab


class SpriteLabTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        lab = ttk.Frame(self.notebook)
        self.frame = lab
        self.app.sprite_lab_frame = lab
        lab.columnconfigure(1, weight=1)
        lab.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(lab, text='Sprite Lab / Asset Pipeline', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(header, text=(
            'Batch-clean sprites, make contact sheets, build ACT palettes, generate AIR actions, create GIF previews, '
            'convert to PCX, and build SFF v1 from a folder of images. This is for users who want to focus on art, not file plumbing.'
        ), wraplength=1100, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.sprite_lab_folder_var = tk.StringVar(value='')
        self.app.sprite_lab_group_var = tk.StringVar(value='200')
        self.app.sprite_lab_start_image_var = tk.StringVar(value='0')
        self.app.sprite_lab_canvas_w_var = tk.StringVar(value='96')
        self.app.sprite_lab_canvas_h_var = tk.StringVar(value='96')
        self.app.sprite_lab_axis_x_var = tk.StringVar(value='48')
        self.app.sprite_lab_axis_y_var = tk.StringVar(value='88')
        self.app.sprite_lab_ticks_var = tk.StringVar(value='5')
        self.app.sprite_lab_action_var = tk.StringVar(value='200')
        self.app.sprite_lab_scale_var = tk.StringVar(value='100')
        self.app.sprite_lab_trim_var = tk.BooleanVar(value=True)

        left = ttk.Frame(lab, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        pick = ttk.LabelFrame(left, text='Folder', padding=(6, 6))
        pick.grid(row=0, column=0, sticky='ew')
        ttk.Entry(pick, textvariable=self.app.sprite_lab_folder_var, width=42).grid(row=0, column=0, sticky='ew')
        ttk.Button(pick, text='Choose Image Folder', command=self.app.sprite_lab_choose_folder_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(pick, text='Summarize Folder', command=self.app.sprite_lab_summary_ui).grid(row=2, column=0, sticky='ew', pady=2)

        fields = ttk.LabelFrame(left, text='Build settings', padding=(6, 6))
        fields.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        field_items = [
            ('group', self.app.sprite_lab_group_var),
            ('start image', self.app.sprite_lab_start_image_var),
            ('canvas w', self.app.sprite_lab_canvas_w_var),
            ('canvas h', self.app.sprite_lab_canvas_h_var),
            ('axis x', self.app.sprite_lab_axis_x_var),
            ('axis y', self.app.sprite_lab_axis_y_var),
            ('AIR action', self.app.sprite_lab_action_var),
            ('ticks', self.app.sprite_lab_ticks_var),
            ('scale %', self.app.sprite_lab_scale_var),
        ]
        for i, (label, var) in enumerate(field_items):
            ttk.Label(fields, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=1)
            ttk.Entry(fields, textvariable=var, width=10).grid(row=i, column=1, sticky='w', padx=2, pady=1)
        ttk.Checkbutton(fields, text='trim transparent edges', variable=self.app.sprite_lab_trim_var).grid(row=len(field_items), column=0, columnspan=2, sticky='w', pady=(4, 0))

        ops = ttk.LabelFrame(left, text='One-click sprite operations', padding=(6, 6))
        ops.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(ops, text='Make Contact Sheet', command=self.app.sprite_lab_contact_sheet_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Normalize / Trim To Manifest', command=self.app.sprite_lab_normalize_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Build SFF v1 From Folder', command=self.app.sprite_lab_build_sff_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Generate AIR From Folder', command=self.app.sprite_lab_air_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Make GIF Preview', command=self.app.sprite_lab_gif_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Build ACT Palette From Folder', command=self.app.sprite_lab_palette_ui).grid(row=5, column=0, sticky='ew', pady=2)
        ttk.Button(ops, text='Convert Folder To PCX', command=self.app.sprite_lab_pcx_ui).grid(row=6, column=0, sticky='ew', pady=2)

        right = ttk.Frame(lab)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.sprite_lab_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.app.sprite_lab_output.yview)
        self.app.sprite_lab_output.configure(yscrollcommand=sy.set)
        self.app.sprite_lab_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        self.notebook.add(lab, text='Sprite Lab')
        self._set_text(self.app.sprite_lab_output, 'Choose a folder of PNG/PCX/BMP/GIF/JPG/WEBP sprites. Use contact sheet first, then normalize/build SFF or generate AIR.')


class StageBuilderTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        stage = ttk.Frame(self.notebook)
        self.frame = stage
        self.app.stage_builder_frame = stage
        stage.columnconfigure(1, weight=1)
        stage.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(stage, text='No-code Stage Builder', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(
            header,
            text='Create a starter M.U.G.E.N stage from one background image. MugenForge writes the stage DEF, SFF v1, source manifest, and README.',
            wraplength=1100,
            justify='left',
        ).grid(row=0, column=0, sticky='ew')

        self.app.stage_image_var = tk.StringVar(value='')
        self.app.stage_name_var = tk.StringVar(value='new_stage')
        self.app.stage_out_dir_var = tk.StringVar(value='')
        self.app.stage_zoffset_var = tk.StringVar(value='')
        self.app.stage_bound_var = tk.StringVar(value='320')

        left = ttk.Frame(stage, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        box = ttk.LabelFrame(left, text='Stage settings', padding=(6, 6))
        box.grid(row=0, column=0, sticky='ew')
        rows = [
            ('image', self.app.stage_image_var),
            ('stage name', self.app.stage_name_var),
            ('output folder', self.app.stage_out_dir_var),
            ('zoffset blank=auto', self.app.stage_zoffset_var),
            ('bound width', self.app.stage_bound_var),
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=2)
            ttk.Entry(box, textvariable=var, width=42).grid(row=i, column=1, sticky='w', padx=2, pady=2)
        ttk.Button(box, text='Choose Background Image', command=self.app.stage_choose_image_ui).grid(row=len(rows), column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(box, text='Choose Output Folder', command=self.app.stage_choose_output_ui).grid(row=len(rows) + 1, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(box, text='Create Stage DEF + SFF', command=self.app.stage_create_ui).grid(row=len(rows) + 2, column=0, columnspan=2, sticky='ew', pady=(8, 2))

        right = ttk.Frame(stage)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.stage_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.app.stage_output.yview)
        self.app.stage_output.configure(yscrollcommand=y.set)
        self.app.stage_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(stage, text='Stage Builder')
        self._set_text(self.app.stage_output, 'Pick one background image and an output folder. The generated stage is a starter, not a finished camera/parallax setup.')


class RunTestTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        run = ttk.Frame(self.notebook)
        self.frame = run
        self.app.run_test_frame = run
        run.columnconfigure(1, weight=1)
        run.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(run, text='Run / Test Helper', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(
            header,
            text='Store a local M.U.G.E.N executable path and launch it from the editor. This does not bundle M.U.G.E.N; it only points to your own install.',
            wraplength=1100,
            justify='left',
        ).grid(row=0, column=0, sticky='ew')

        self.app.run_mugen_exe_var = tk.StringVar(value='')
        left = ttk.Frame(run, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        box = ttk.LabelFrame(left, text='M.U.G.E.N path', padding=(6, 6))
        box.grid(row=0, column=0, sticky='ew')
        ttk.Entry(box, textvariable=self.app.run_mugen_exe_var, width=52).grid(row=0, column=0, sticky='ew')
        ttk.Button(box, text='Choose MUGEN Executable', command=self.app.run_choose_mugen_exe_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(box, text='Save Launch Config', command=self.app.run_save_launch_config_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(box, text='Launch MUGEN', command=self.app.run_launch_mugen_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(box, text='Write select.def Entry Snippet', command=self.app.run_select_def_snippet_ui).grid(row=4, column=0, sticky='ew', pady=2)

        right = ttk.Frame(run)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.run_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.app.run_output.yview)
        self.app.run_output.configure(yscrollcommand=y.set)
        self.app.run_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(run, text='Run / Test')
        self._set_text(self.app.run_output, 'Open a project and set your own M.U.G.E.N executable path. The config is stored in the character folder.')
