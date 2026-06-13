from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..automation_bank import kit_names, preset_display_list
from ..factory_max import FACTORY_MAX_VERSION
from ..factory_ultra import FACTORY_ULTRA_VERSION
from ..no_code_director import archetype_names
from .base import AppBackedTab


class AutoBuilderTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        auto_frame = ttk.Frame(self.notebook)
        self.frame = auto_frame
        self.app.auto_frame = auto_frame
        auto_frame.columnconfigure(1, weight=1)
        auto_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(auto_frame, text='No-code Feature Bank / Auto Builder', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Pick a feature, preview what it will add, then let MugenForge write the CMD/CNS/AIR code with backups. '
            'This tab is built for users who want to design moves, timing, sprites, and hitboxes without manually coding every block.'
        )
        ttk.Label(header, text=intro, wraplength=980, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(auto_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Label(left, text='Feature presets').grid(row=0, column=0, sticky='ew')
        self.app.auto_feature_list = tk.Listbox(left, width=42, height=24, font=('Consolas', 10), exportselection=False)
        self.app.auto_feature_list.grid(row=1, column=0, sticky='nsw', pady=(3, 6))
        self.app.auto_feature_list.bind('<<ListboxSelect>>', self.app.auto_on_preset_select)
        self.app.auto_preset_items = preset_display_list()
        for item in self.app.auto_preset_items:
            self.app.auto_feature_list.insert('end', item)
        if self.app.auto_preset_items:
            self.app.auto_feature_list.selection_set(0)

        buttons = ttk.LabelFrame(left, text='One-click actions', padding=(6, 6))
        buttons.grid(row=2, column=0, sticky='ew')
        ttk.Button(buttons, text='Preview Selected', command=self.app.auto_preview_feature).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Add Selected To Project (.bak)', command=self.app.auto_apply_selected_feature).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Install Beginner Pack (.bak)', command=self.app.auto_apply_beginner_pack_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Auto Setup / Repair Project', command=self.app.auto_setup_project_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Project Status / Next Step', command=self.app.auto_project_status_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Write Code Bank Template', command=self.app.auto_export_code_bank_ui).grid(row=5, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Make Placeholder Sprite Sheet', command=self.app.auto_make_placeholder_sheet_ui).grid(row=6, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Feature Bank Stats', command=self.app.auto_feature_bank_stats_ui).grid(row=7, column=0, sticky='ew', pady=2)

        kit_box = ttk.LabelFrame(left, text='Creator kits', padding=(6, 6))
        kit_box.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        kit_values = kit_names()
        self.app.auto_kit_var = tk.StringVar(value=kit_values[0] if kit_values else '')
        self.app.auto_kit_combo = ttk.Combobox(kit_box, values=kit_values, textvariable=self.app.auto_kit_var, state='readonly', width=36)
        self.app.auto_kit_combo.grid(row=0, column=0, sticky='ew', pady=(0, 3))
        ttk.Button(kit_box, text='Preview Kit', command=self.app.auto_preview_kit).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(kit_box, text='Install Kit (.bak)', command=self.app.auto_apply_kit_ui).grid(row=2, column=0, sticky='ew', pady=2)

        director_box = ttk.LabelFrame(left, text='No-code Director', padding=(6, 6))
        director_box.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        archetypes = archetype_names()
        self.app.auto_archetype_var = tk.StringVar(value=archetypes[0] if archetypes else '')
        self.app.auto_archetype_combo = ttk.Combobox(director_box, values=archetypes, textvariable=self.app.auto_archetype_var, state='readonly', width=36)
        self.app.auto_archetype_combo.grid(row=0, column=0, sticky='ew', pady=(0, 3))
        ttk.Button(director_box, text='Preview Archetype', command=self.app.auto_preview_archetype).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(director_box, text='Write Dashboard / Checklists', command=self.app.auto_write_dashboard_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(director_box, text='One-Click Playable Skeleton', command=self.app.auto_one_click_skeleton_ui).grid(row=3, column=0, sticky='ew', pady=2)

        self.app.auto_note = tk.Text(left, wrap='word', width=42, height=8, font=('Consolas', 9), state='disabled')
        self.app.auto_note.grid(row=5, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.app.auto_note,
            'Beginner Pack adds setup basics, punches, crouch kick, fireball, dash/backdash, taunt, and debug tools. Generated code is appended and marked so the app can avoid adding the same feature twice.',
        )

        right = ttk.Frame(auto_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.auto_output = tk.Text(right, wrap='none', font=('Consolas', 10), state='disabled')
        auto_y = ttk.Scrollbar(right, orient='vertical', command=self.app.auto_output.yview)
        auto_x = ttk.Scrollbar(right, orient='horizontal', command=self.app.auto_output.xview)
        self.app.auto_output.configure(yscrollcommand=auto_y.set, xscrollcommand=auto_x.set)
        self.app.auto_output.grid(row=0, column=0, sticky='nsew')
        auto_y.grid(row=0, column=1, sticky='ns')
        auto_x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(auto_frame, text='Feature Bank')
        self.app.auto_preview_feature()


class FactoryMaxTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        max_frame = ttk.Frame(self.notebook)
        self.frame = max_frame
        self.app.factory_max_frame = max_frame
        max_frame.columnconfigure(1, weight=1)
        max_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(max_frame, text=f'Factory Max / Better-than-FF Automation v{FACTORY_MAX_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'This tab targets Fighter Factory-style production workflows plus heavier beginner automation: code-sense banks, state graphs, safe imports, auto CLSN, storyboards, screenpack starters, sound cue banks, release QA, and one-click project upgrades.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(max_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click heavy lifting', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Factory Max Upgrade', command=self.app.max_one_click_upgrade_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Factory Max Profile Report', command=self.app.max_profile_report_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Build Factory Max Release ZIP', command=self.app.max_release_zip_ui).grid(row=2, column=0, sticky='ew', pady=2)

        code = ttk.LabelFrame(left, text='Code / structure tools', padding=(6, 6))
        code.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(code, text='Write CodeSense Bank', command=self.app.max_codesense_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Write State Graph', command=self.app.max_state_graph_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Write Organizer Manifest', command=self.app.max_organizer_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Safe Import From Project', command=self.app.max_safe_import_ui).grid(row=3, column=0, sticky='ew', pady=2)

        anim = ttk.LabelFrame(left, text='Animation / CLSN automation', padding=(6, 6))
        anim.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self.app.max_clsn_padding_var = tk.StringVar(value='2')
        self.app.max_retime_scale_var = tk.StringVar(value='1.0')
        self.app.max_renumber_offset_var = tk.StringVar(value='10000')
        row_items = [
            ('CLSN padding', self.app.max_clsn_padding_var),
            ('retime scale', self.app.max_retime_scale_var),
            ('clone offset', self.app.max_renumber_offset_var),
        ]
        for row, (label, var) in enumerate(row_items):
            ttk.Label(anim, text=label).grid(row=row, column=0, sticky='e', padx=2, pady=1)
            ttk.Entry(anim, textvariable=var, width=10).grid(row=row, column=1, sticky='w', padx=2, pady=1)
        ttk.Button(anim, text='Auto Body CLSN From SFF', command=self.app.max_auto_clsn_ui).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 2))
        ttk.Button(anim, text='Retime AIR Ticks', command=self.app.max_retime_air_ui).grid(row=4, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(anim, text='Clone/Renumber AIR Actions', command=self.app.max_renumber_air_ui).grid(row=5, column=0, columnspan=2, sticky='ew', pady=2)

        extras = ttk.LabelFrame(left, text='Full-project extras', padding=(6, 6))
        extras.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(extras, text='Create Storyboard Template', command=self.app.max_storyboard_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Create Screenpack Starter', command=self.app.max_screenpack_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Create Sound AutoBank', command=self.app.max_sound_autobank_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Write Quick Test Suite', command=self.app.max_quick_test_ui).grid(row=3, column=0, sticky='ew', pady=2)

        self.app.max_note = tk.Text(left, wrap='word', width=44, height=7, font=('Consolas', 9), state='disabled')
        self.app.max_note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.app.max_note,
            'Best beginner route: One-Click Factory Max Upgrade -> Animation Player -> CLSN Editor -> Image Factory/Sprite Lab -> Profile Report -> Release ZIP. CodeSense/state graph are there when you need to understand what happened.',
        )

        right = ttk.Frame(max_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.factory_max_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.app.factory_max_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.app.factory_max_output.xview)
        self.app.factory_max_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.app.factory_max_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(max_frame, text='Factory Max')
        self._set_text(
            self.app.factory_max_output,
            'Open/create a character folder, then run One-Click Factory Max Upgrade. It writes backups before changing active code files and keeps risky imports in an imports/ folder.',
        )


class FactoryUltraTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        ultra = ttk.Frame(self.notebook)
        self.frame = ultra
        self.app.factory_ultra_frame = ultra
        ultra.columnconfigure(1, weight=1)
        ultra.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(ultra, text=f'Factory Ultra / No-Code Production HQ v{FACTORY_ULTRA_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(header, text=(
            'A higher-level production hub for non-coders: snapshots, dashboards, frame data, balance review, asset usage, cancel/state flow, input maps, move cards, task boards, AI tuning, and release readiness.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(ultra, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click production', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Ultra Production Pass', command=self.app.ultra_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Create Safety Snapshot', command=self.app.ultra_snapshot_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Build Ultra Release ZIP', command=self.app.ultra_release_zip_ui).grid(row=2, column=0, sticky='ew', pady=2)

        reports = ttk.LabelFrame(left, text='Beginner reports', padding=(6, 6))
        reports.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(reports, text='Ultra Dashboard', command=self.app.ultra_dashboard_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Beginner Task Board', command=self.app.ultra_task_board_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Production Bible', command=self.app.ultra_bible_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Feature Switchboard', command=self.app.ultra_switchboard_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Release Readiness', command=self.app.ultra_readiness_ui).grid(row=4, column=0, sticky='ew', pady=2)

        labs = ttk.LabelFrame(left, text='No-code tuning labs', padding=(6, 6))
        labs.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(labs, text='Frame Data Lab', command=self.app.ultra_frame_data_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Balance Lab', command=self.app.ultra_balance_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Cancel / State Flow Lab', command=self.app.ultra_cancel_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Asset Usage Lab', command=self.app.ultra_assets_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Sprite Axis Lab', command=self.app.ultra_axis_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='AI Tuning Lab', command=self.app.ultra_ai_ui).grid(row=5, column=0, sticky='ew', pady=2)

        creator = ttk.LabelFrame(left, text='Creator-facing helpers', padding=(6, 6))
        creator.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(creator, text='Move Cards HTML', command=self.app.ultra_move_cards_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(creator, text='Input Map Assistant', command=self.app.ultra_input_map_ui).grid(row=1, column=0, sticky='ew', pady=2)

        right = ttk.Frame(ultra, padding=(0, 0, 6, 6))
        right.grid(row=1, column=1, sticky='nsew')
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.app.factory_ultra_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.app.factory_ultra_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.app.factory_ultra_output.xview)
        self.app.factory_ultra_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.app.factory_ultra_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(ultra, text='Factory Ultra')
        self._set_text(
            self.app.factory_ultra_output,
            'Best route for beginners: Create/New Character -> One-Click Ultra Production Pass -> replace art/sound -> Animation Player + CLSN Editor -> Frame Data/Balance/Asset labs -> Build Ultra Release ZIP.',
        )
