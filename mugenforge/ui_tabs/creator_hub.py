from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..creator_hub import (
    run_creator_hub_pass as ch_run_creator_hub_pass,
    write_asset_request_pack as ch_write_asset_request_pack,
    write_balance_autotune_plan as ch_write_balance_autotune_plan,
    write_combo_trial_pack as ch_write_combo_trial_pack,
    write_controller_mapping_sheet as ch_write_controller_mapping_sheet,
    write_creator_dashboard as ch_write_creator_dashboard,
    write_input_conflict_lab as ch_write_input_conflict_lab,
    write_no_code_recipe_book as ch_write_no_code_recipe_book,
    write_patch_macro_bank as ch_write_patch_macro_bank,
    write_project_task_board as ch_write_project_task_board,
    write_release_website as ch_write_release_website,
)
from .base import AppBackedTab


class CreatorHubTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self._publish(
            '_creator_hub_root',
            '_creator_hub_run',
            'creator_hub_one_click_ui',
            'creator_hub_dashboard_ui',
            'creator_hub_task_board_ui',
            'creator_hub_input_lab_ui',
            'creator_hub_balance_ui',
            'creator_hub_combo_ui',
            'creator_hub_assets_ui',
            'creator_hub_recipes_ui',
            'creator_hub_controller_ui',
            'creator_hub_release_site_ui',
            'creator_hub_patch_bank_ui',
        )

    def _build(self):
        hub = ttk.Frame(self.notebook)
        self.frame = hub
        self.app.creator_hub_frame = hub
        hub.columnconfigure(1, weight=1)
        hub.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(hub, text='Creator Hub: no-code production cockpit / better-than-FF planning layer', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Creator Hub turns the project into a beginner-readable production board: dashboard, task cards, input conflicts, balance suggestions, '
            'combo trials, controller maps, asset requests, patch macro bank, and a release website. It is report/export focused, so it does not silently rewrite core gameplay files.'
        )
        ttk.Label(header, text=intro, wraplength=1140, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(hub, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click / beginner workflow', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Creator Hub Pass', command=self.creator_hub_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Creator Dashboard', command=self.creator_hub_dashboard_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Project Task Board', command=self.creator_hub_task_board_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Patch Macro Bank', command=self.creator_hub_patch_bank_ui).grid(row=3, column=0, sticky='ew', pady=2)

        labs = ttk.LabelFrame(left, text='No-code analysis labs', padding=(6, 6))
        labs.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(labs, text='Input Conflict Lab', command=self.creator_hub_input_lab_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Balance Autotune Plan', command=self.creator_hub_balance_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Combo Trial Pack', command=self.creator_hub_combo_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Controller Mapping Sheet', command=self.creator_hub_controller_ui).grid(row=3, column=0, sticky='ew', pady=2)

        production = ttk.LabelFrame(left, text='Production handoff / release', padding=(6, 6))
        production.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(production, text='Asset Request Pack', command=self.creator_hub_assets_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(production, text='No-Code Recipe Book', command=self.creator_hub_recipes_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(production, text='Release Website Scaffold', command=self.creator_hub_release_site_ui).grid(row=2, column=0, sticky='ew', pady=2)

        self.creator_hub_note = tk.Text(left, wrap='word', width=48, height=12, font=('Consolas', 9), state='disabled')
        self.app.creator_hub_note = self.creator_hub_note
        self.creator_hub_note.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.creator_hub_note,
            'Best route for a non-coder: run One-Click Creator Hub Pass, open CREATOR_DASHBOARD.html, clear high-priority task cards, then use Feature Bank/Move Wizard/Sprite Lab for the fun creative changes.',
        )

        right = ttk.Frame(hub)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.creator_hub_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.creator_hub_output = self.creator_hub_output
        y = ttk.Scrollbar(right, orient='vertical', command=self.creator_hub_output.yview)
        self.creator_hub_output.configure(yscrollcommand=y.set)
        self.creator_hub_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(hub, text='Creator Hub')
        self._set_text(
            self.creator_hub_output,
            'Open/create a character folder, then run One-Click Creator Hub Pass. It writes beginner dashboards, cards, trials, maps, recipes, and release scaffolding without silently changing active code.',
        )

    def _creator_hub_root(self):
        root = self.app._plus_get_project_root()
        if not root:
            return None
        return root

    def _creator_hub_run(self, label, func, *args, **kwargs):
        root = self._creator_hub_root()
        if not root:
            return
        try:
            result = func(root, *args, **kwargs)
            self._reload_project()
            self._set_text(self.creator_hub_output, result.to_text())
            self._select(self.frame)
            self._set_status(label)
        except Exception as exc:
            messagebox.showerror(label, str(exc))

    def creator_hub_one_click_ui(self):
        self._creator_hub_run('Creator Hub pass complete.', ch_run_creator_hub_pass)

    def creator_hub_dashboard_ui(self):
        self._creator_hub_run('Creator Dashboard written.', ch_write_creator_dashboard)

    def creator_hub_task_board_ui(self):
        self._creator_hub_run('Project Task Board written.', ch_write_project_task_board)

    def creator_hub_input_lab_ui(self):
        self._creator_hub_run('Input Conflict Lab written.', ch_write_input_conflict_lab)

    def creator_hub_balance_ui(self):
        self._creator_hub_run('Balance Autotune Plan written.', ch_write_balance_autotune_plan)

    def creator_hub_combo_ui(self):
        self._creator_hub_run('Combo Trial Pack written.', ch_write_combo_trial_pack)

    def creator_hub_assets_ui(self):
        self._creator_hub_run('Asset Request Pack written.', ch_write_asset_request_pack)

    def creator_hub_recipes_ui(self):
        self._creator_hub_run('No-Code Recipe Book written.', ch_write_no_code_recipe_book)

    def creator_hub_controller_ui(self):
        self._creator_hub_run('Controller Mapping Sheet written.', ch_write_controller_mapping_sheet)

    def creator_hub_release_site_ui(self):
        self._creator_hub_run('Release Website Scaffold written.', ch_write_release_website)

    def creator_hub_patch_bank_ui(self):
        self._creator_hub_run('Patch Macro Bank written.', ch_write_patch_macro_bank)
