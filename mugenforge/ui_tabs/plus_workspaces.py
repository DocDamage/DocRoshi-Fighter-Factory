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


class FactoryPlusTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        factory_frame = ttk.Frame(self.notebook)
        self.frame = factory_frame
        self.app.factory_plus_frame = factory_frame
        factory_frame.columnconfigure(1, weight=1)
        factory_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(factory_frame, text='Factory+ / Fighter-Factory-style automation', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Factory+ is the beginner-facing heavy-lifting layer: project repair, required animations, placeholder SFF/SND, '
            'movelists, state maps, balance sheets, release packaging, and bulk sprite import. The creator chooses the fun direction; '
            'the tool writes or organizes the boring project wiring.'
        )
        ttk.Label(header, text=intro, wraplength=1080, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(factory_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        quick = ttk.LabelFrame(left, text='One-click beginner automation', padding=(6, 6))
        quick.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(quick, text='Smart Complete / Repair', command=self.app.factory_smart_complete_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(quick, text='Deep Doctor Report', command=self.app.factory_doctor_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(quick, text='Write Start Here Guide', command=self.app.factory_start_here_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(quick, text='Install Function Bank Docs', command=self.app.factory_function_bank_ui).grid(row=3, column=0, sticky='ew', pady=2)

        assets = ttk.LabelFrame(left, text='Sprite / animation automation', padding=(6, 6))
        assets.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        ttk.Button(assets, text='Complete Missing AIR Actions', command=self.app.factory_complete_air_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Rebuild Placeholder SFF From AIR', command=self.app.factory_placeholder_sff_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Bulk Import Sprite Folder -> SFF/AIR', command=self.app.factory_bulk_import_sprites_ui).grid(row=2, column=0, sticky='ew', pady=2)

        publish = ttk.LabelFrame(left, text='Docs, maps, tuning, release', padding=(6, 6))
        publish.grid(row=2, column=0, sticky='ew')
        ttk.Button(publish, text='Export Move List', command=self.app.factory_movelist_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(publish, text='Export State Map', command=self.app.factory_state_map_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(publish, text='Export Balance Sheet', command=self.app.factory_balance_sheet_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(publish, text='Build Release ZIP', command=self.app.factory_release_zip_ui).grid(row=3, column=0, sticky='ew', pady=2)

        self.app.factory_plus_tips = tk.Text(left, wrap='word', width=42, height=12, font=('Consolas', 9), state='disabled')
        self.app.factory_plus_tips.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.app.factory_plus_tips,
            'Best beginner flow:\n\n1. Smart Complete / Repair\n2. Feature Bank for no-code moves\n3. Animation Player + CLSN Editor\n4. Bulk Import Sprite Folder when art is ready\n5. Deep Doctor Report\n6. Build Release ZIP\n\nSprite filenames like g200_i0.png let MugenForge auto-wire group/image IDs.',
        )

        right = ttk.Frame(factory_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.factory_plus_output = tk.Text(right, wrap='none', font=('Consolas', 10), state='disabled')
        f_y = ttk.Scrollbar(right, orient='vertical', command=self.app.factory_plus_output.yview)
        f_x = ttk.Scrollbar(right, orient='horizontal', command=self.app.factory_plus_output.xview)
        self.app.factory_plus_output.configure(yscrollcommand=f_y.set, xscrollcommand=f_x.set)
        self.app.factory_plus_output.grid(row=0, column=0, sticky='nsew')
        f_y.grid(row=0, column=1, sticky='ns')
        f_x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(factory_frame, text='Factory+')
        self._set_text(
            self.app.factory_plus_output,
            'Open or create a character folder, then use Smart Complete / Repair. Factory+ writes backups before modifying existing text/code files.',
        )


class ForgePlusTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        forge = ttk.Frame(self.notebook)
        self.frame = forge
        self.app.forge_plus_frame = forge
        forge.columnconfigure(1, weight=1)
        forge.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(forge, text='Forge+ Doctor / Better-than-FF Automation', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'This tab is the beginner cockpit: diagnose the whole character, write readable docs, repair missing basics, '
            'rebuild placeholder assets, and export creator-facing move lists without hand-editing code.'
        ), wraplength=1050, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(forge, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        actions = ttk.LabelFrame(left, text='Project actions', padding=(6, 6))
        actions.grid(row=0, column=0, sticky='ew')
        ttk.Button(actions, text='Run Forge+ Doctor', command=self.app.forge_plus_report_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Auto Setup / Repair Basics', command=self.app.auto_setup_project_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='One-Click Prototype / Rebuild Assets', command=self.app.auto_one_click_skeleton_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Beginner Doctor Report', command=self.app.factory_doctor_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Export Move List', command=self.app.forge_plus_export_move_list_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Write Creator Manual', command=self.app.forge_plus_creator_manual_ui).grid(row=5, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Package Character ZIP', command=self.app.package_character).grid(row=6, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Refresh Project Tree', command=self.app.reload_project).grid(row=7, column=0, sticky='ew', pady=2)

        fast = ttk.LabelFrame(left, text='Fast beginner route', padding=(6, 6))
        fast.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Label(fast, text='1. Auto Setup / Repair\n2. Feature Bank archetype\n3. One-Click Prototype\n4. Animation Player\n5. CLSN Editor\n6. Package ZIP', justify='left').grid(row=0, column=0, sticky='w')

        right = ttk.Frame(forge, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.forge_plus_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.app.forge_plus_output.yview)
        self.app.forge_plus_output.configure(yscrollcommand=y.set)
        self.app.forge_plus_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(forge, text='Forge+ Doctor')
        self._set_text(self.app.forge_plus_output, 'Open a character folder, then run Forge+ Doctor. This gives a plain-English score and next step.')
