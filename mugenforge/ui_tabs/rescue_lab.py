from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..rescue_lab import (
    RESCUE_LAB_VERSION,
    build_recovered_sff_v1,
    build_recovery_manifest_from_air,
    create_rescue_contact_sheet,
    run_rescue_lab_pass,
    scan_project_embedded_assets,
    write_beginner_rescue_plan,
)
from .base import AppBackedTab


class RescueLabTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self._publish(
            '_rescue_lab_root',
            '_rescue_lab_run',
            'rescue_lab_one_click_ui',
            'rescue_lab_scan_ui',
            'rescue_lab_manifest_ui',
            'rescue_lab_contact_ui',
            'rescue_lab_build_sff_ui',
            'rescue_lab_plan_ui',
        )

    def _build(self):
        rescue = ttk.Frame(self.notebook)
        self.frame = rescue
        self.app.rescue_lab_frame = rescue
        rescue.columnconfigure(1, weight=1)
        rescue.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(rescue, text=f'Rescue Lab: asset recovery for unsupported packed files v{RESCUE_LAB_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Use Rescue Lab when a character has packed assets, unsupported/unknown SFF/SND layouts, missing source folders, or asset files that need to be salvaged. '
            'It scans for embedded PNG/PCX/WAV payloads, makes a contact sheet, maps extracted images back to AIR references when possible, and can build a fresh starter SFF v1 from recovered images.'
        )
        ttk.Label(header, text=intro, wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(rescue, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        main = ttk.LabelFrame(left, text='One-click rescue', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Rescue Lab Pass', command=self.rescue_lab_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Write Beginner Rescue Plan', command=self.rescue_lab_plan_ui).grid(row=1, column=0, sticky='ew', pady=2)

        assets = ttk.LabelFrame(left, text='Asset recovery steps', padding=(6, 6))
        assets.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(assets, text='Scan Embedded PNG/PCX/WAV', command=self.rescue_lab_scan_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Make Recovery Contact Sheet', command=self.rescue_lab_contact_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Build Recovery Manifest From AIR', command=self.rescue_lab_manifest_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(assets, text='Build Recovered SFF v1', command=self.rescue_lab_build_sff_ui).grid(row=3, column=0, sticky='ew', pady=2)

        self.rescue_lab_note = tk.Text(left, wrap='word', width=46, height=12, font=('Consolas', 9), state='disabled')
        self.app.rescue_lab_note = self.rescue_lab_note
        self.rescue_lab_note.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.rescue_lab_note,
            'Best beginner route: One-Click Rescue Lab Pass -> open rescue_lab/RECOVERY_CONTACT_SHEET.png -> replace bad/missing extracted images -> Build Recovery Manifest From AIR -> Build Recovered SFF v1 -> test in Animation Player and CLSN Editor. This is a rescue workflow, not byte-perfect SFF v2 rebuilding.',
        )

        right = ttk.Frame(rescue)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.rescue_lab_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.rescue_lab_output = self.rescue_lab_output
        y = ttk.Scrollbar(right, orient='vertical', command=self.rescue_lab_output.yview)
        x = ttk.Scrollbar(right, orient='horizontal', command=self.rescue_lab_output.xview)
        self.rescue_lab_output.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.rescue_lab_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(rescue, text='Rescue Lab')
        self._set_text(self.rescue_lab_output, 'Open a character folder, then run One-Click Rescue Lab Pass. Review the generated beginner plan before building replacement assets.')

    def _rescue_lab_root(self):
        root = self.app._plus_get_project_root()
        if not root:
            return None
        return root

    def _rescue_lab_run(self, label, func, *args, **kwargs):
        root = self._rescue_lab_root()
        if not root:
            return
        try:
            result = func(root, *args, **kwargs)
            self._reload_project()
            self._set_text(self.rescue_lab_output, result.to_text())
            self._select(self.frame)
            self._set_status(label)
        except Exception as exc:
            messagebox.showerror(label, str(exc))

    def rescue_lab_one_click_ui(self):
        self._rescue_lab_run('Rescue Lab pass complete.', run_rescue_lab_pass)

    def rescue_lab_scan_ui(self):
        self._rescue_lab_run('Embedded asset scan complete.', scan_project_embedded_assets)

    def rescue_lab_manifest_ui(self):
        self._rescue_lab_run('Recovery manifest written.', build_recovery_manifest_from_air)

    def rescue_lab_contact_ui(self):
        self._rescue_lab_run('Recovery contact sheet written.', create_rescue_contact_sheet)

    def rescue_lab_build_sff_ui(self):
        self._rescue_lab_run('Recovered SFF v1 built.', build_recovered_sff_v1)

    def rescue_lab_plan_ui(self):
        self._rescue_lab_run('Beginner rescue plan written.', write_beginner_rescue_plan)
