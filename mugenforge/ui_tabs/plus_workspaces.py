from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import AppBackedTab


class StudioPlusTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        plus_frame = ttk.Frame(self.notebook)
        self.frame = plus_frame
        self.app.studio_plus_frame = plus_frame
        plus_frame.columnconfigure(1, weight=1)
        plus_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(plus_frame, text='Studio Plus: Fighter Factory-style workflows, no-code first', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Use these tools when you want the editor to do the boring work: diagnose the project, repair missing basics, build placeholder assets, '
            'export animation previews, make contact sheets, clone AIR actions, batch-import sprites, snapshot the project, and package a cleaner release.'
        )
        ttk.Label(header, text=intro, wraplength=1080, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(plus_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        doctor = ttk.LabelFrame(left, text='Project doctor / release', padding=(6, 6))
        doctor.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(doctor, text='Full Studio Doctor Report', command=self.app.plus_doctor_report_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(doctor, text='Write MD + JSON Reports', command=self.app.plus_write_reports_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(doctor, text='Auto Fix / Build Missing Assets', command=self.app.plus_auto_fix_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(doctor, text='Make Snapshot ZIP', command=self.app.plus_snapshot_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(doctor, text='Build Release ZIP + Manifest', command=self.app.plus_release_zip_ui).grid(row=4, column=0, sticky='ew', pady=2)

        assets = ttk.LabelFrame(left, text='Asset tools', padding=(6, 6))
        assets.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(assets, text='SFF Contact Sheet PNG', command=self.app.plus_contact_sheet_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Batch Import Sprite Folder -> SFF v1', command=self.app.plus_batch_import_sprites_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Generate AIR From SFF Groups', command=lambda: self.app.plus_air_from_sff_ui(False)).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Append AIR From SFF Groups (.bak)', command=lambda: self.app.plus_air_from_sff_ui(True)).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Export Action GIF', command=self.app.plus_export_action_gif_ui).grid(row=4, column=0, sticky='ew', pady=2)

        action_box = ttk.LabelFrame(left, text='Animation lab fields', padding=(6, 6))
        action_box.grid(row=2, column=0, sticky='ew', pady=(0, 6))
        self.app.plus_action_var = tk.StringVar(value='0')
        self.app.plus_clone_source_var = tk.StringVar(value='200')
        self.app.plus_clone_new_var = tk.StringVar(value='1200')
        self.app.plus_tick_scale_var = tk.StringVar(value='1.0')
        self.app.plus_x_offset_var = tk.StringVar(value='0')
        self.app.plus_y_offset_var = tk.StringVar(value='0')
        fields = [
            ('GIF action', self.app.plus_action_var),
            ('Clone source', self.app.plus_clone_source_var),
            ('Clone new', self.app.plus_clone_new_var),
            ('Tick scale', self.app.plus_tick_scale_var),
            ('X offset', self.app.plus_x_offset_var),
            ('Y offset', self.app.plus_y_offset_var),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(action_box, text=label).grid(row=i, column=0, sticky='e', padx=(0, 4), pady=1)
            ttk.Entry(action_box, textvariable=var, width=10).grid(row=i, column=1, sticky='w', pady=1)
        ttk.Button(action_box, text='Clone AIR Action Variant (.bak)', command=self.app.plus_clone_air_action_ui).grid(row=len(fields), column=0, columnspan=2, sticky='ew', pady=(4, 2))

        import_box = ttk.LabelFrame(left, text='Batch import defaults', padding=(6, 6))
        import_box.grid(row=3, column=0, sticky='ew', pady=(0, 6))
        self.app.plus_import_group_var = tk.StringVar(value='9000')
        self.app.plus_axis_x_var = tk.StringVar(value='32')
        self.app.plus_axis_y_var = tk.StringVar(value='64')
        self.app.plus_ticks_var = tk.StringVar(value='5')
        for i, (label, var) in enumerate((
            ('Default group', self.app.plus_import_group_var),
            ('Axis X', self.app.plus_axis_x_var),
            ('Axis Y', self.app.plus_axis_y_var),
            ('Ticks', self.app.plus_ticks_var),
        )):
            ttk.Label(import_box, text=label).grid(row=i, column=0, sticky='e', padx=(0, 4), pady=1)
            ttk.Entry(import_box, textvariable=var, width=10).grid(row=i, column=1, sticky='w', pady=1)

        stage_box = ttk.LabelFrame(left, text='Extra creator tools', padding=(6, 6))
        stage_box.grid(row=4, column=0, sticky='ew')
        ttk.Button(stage_box, text='Create Stage Template', command=self.app.plus_stage_template_ui).grid(row=0, column=0, sticky='ew', pady=2)

        right = ttk.Frame(plus_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.plus_output = tk.Text(right, wrap='none', font=('Consolas', 10), state='disabled')
        plus_y = ttk.Scrollbar(right, orient='vertical', command=self.app.plus_output.yview)
        plus_x = ttk.Scrollbar(right, orient='horizontal', command=self.app.plus_output.xview)
        self.app.plus_output.configure(yscrollcommand=plus_y.set, xscrollcommand=plus_x.set)
        self.app.plus_output.grid(row=0, column=0, sticky='nsew')
        plus_y.grid(row=0, column=1, sticky='ns')
        plus_x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(plus_frame, text='Studio Plus')
        self._set_text(
            self.app.plus_output,
            'Open a character folder, then run Full Studio Doctor Report. The Auto Fix button repairs common beginner blockers and generates placeholder assets so you can get back to the creative parts.',
        )
