from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..automation_bank import kit_names, preset_display_list
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
