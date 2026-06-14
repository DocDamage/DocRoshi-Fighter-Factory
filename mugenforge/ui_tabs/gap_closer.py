from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import gap_closer as gc
from .base import AppBackedTab


class GapCloserTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.gap_closer_frame = self.frame
        self._publish(
            '_gap_closer_root',
            '_gap_closer_show_result',
            'gap_closer_one_click_ui',
            'gap_closer_dashboard_ui',
            'gap_closer_engine_probe_ui',
            'gap_closer_source_model_ui',
            'gap_closer_scenario_dry_ui',
            'gap_closer_scenario_live_ui',
            'gap_closer_readiness_ui',
            'gap_closer_corpus_ui',
            'gap_closer_triage_ui',
            'gap_closer_commit_sheet_ui',
            'gap_closer_apply_commit_ui',
            'gap_closer_tuning_sheet_ui',
            'gap_closer_apply_tuning_ui',
            'gap_closer_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        header = ttk.LabelFrame(frame, text=f'Gap Closer v{gc.GAP_CLOSER_VERSION} — closes previous honest limitations with concrete tools', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        desc = (
            'Use this tab to turn the remaining limitation list into workflows: engine probing, source-runtime modeling, '
            'live scenario evidence, corpus validation, unknown binary triage, guarded binary commit, and generated-code tuning.'
        )
        ttk.Label(header, text=desc, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Gap Closer Pass', self.gap_closer_one_click_ui),
            ('Dashboard', self.gap_closer_dashboard_ui),
            ('Probe Engine Profile', self.gap_closer_engine_probe_ui),
            ('Source Runtime Model', self.gap_closer_source_model_ui),
            ('Engine Scenario Dry-Run', self.gap_closer_scenario_dry_ui),
            ('Engine Scenario Live Run', self.gap_closer_scenario_live_ui),
            ('Engine-Backed Readiness', self.gap_closer_readiness_ui),
            ('SFF/SND Corpus Lab', self.gap_closer_corpus_ui),
            ('Unknown Binary Triage', self.gap_closer_triage_ui),
            ('Export Binary Commit Sheet', self.gap_closer_commit_sheet_ui),
            ('Apply Binary Commit Sheet', self.gap_closer_apply_commit_ui),
            ('Generated Code Tuning Sheet', self.gap_closer_tuning_sheet_ui),
            ('Apply Code Tuning Sheet', self.gap_closer_apply_tuning_ui),
            ('Bundle Gap Closer Reports', self.gap_closer_bundle_ui),
        ]
        for i, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + i // 5, column=i % 5, padx=3, pady=2, sticky='ew')

        self.app.gap_closer_note = tk.Text(frame, wrap='word', height=5, font=('Consolas', 9), state='disabled')
        self.app.gap_closer_note.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        self._set_text(
            self.app.gap_closer_note,
            'Start with One-Click Gap Closer Pass. For live engine evidence, configure/probe an engine executable first. Guarded binary commits require enabled=yes and commit_token=COMMIT in the CSV sheet.',
        )
        self.app.gap_closer_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.gap_closer_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Gap Closer')
        self._set_text(self.app.gap_closer_output, f'Gap Closer v{gc.GAP_CLOSER_VERSION} is ready. Open a project, then run One-Click Gap Closer Pass.')

    def _gap_closer_root(self):
        root = self.app.project_root or (self.app.current_path.parent if self.app.current_path else None)
        if not root:
            messagebox.showinfo('Gap Closer', 'Open or create a project folder first.')
            return None
        return Path(root)

    def _gap_closer_show_result(self, result, status: str):
        self._set_text(self.app.gap_closer_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.gap_closer_frame)

    def _run(self, func, status: str, error_title: str, *args, **kwargs):
        root = self._gap_closer_root()
        if not root:
            return
        try:
            result = func(root, *args, **kwargs)
            self._reload_project()
            self._gap_closer_show_result(result, status)
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))

    def gap_closer_one_click_ui(self):
        root = self._gap_closer_root()
        if not root:
            return
        try:
            result = gc.run_gap_closer_pass(root)
            self._reload_project()
            self._gap_closer_show_result(result, 'Gap Closer pass complete')
            messagebox.showinfo('Gap Closer complete', 'Gap Closer pass completed. Review gap_closer/GAP_CLOSER_START_HERE.md.')
        except Exception as exc:
            messagebox.showerror('Gap Closer failed', str(exc))

    def gap_closer_dashboard_ui(self):
        self._run(gc.write_gap_closer_dashboard, 'Gap Closer dashboard written', 'Gap Closer dashboard failed')

    def gap_closer_engine_probe_ui(self):
        root = self._gap_closer_root()
        if not root:
            return
        engine = filedialog.askopenfilename(title='Choose mugen.exe / ikemen executable, or Cancel to write blank profile')
        try:
            result = gc.probe_engine_profile(root, engine or None)
            self._reload_project()
            self._gap_closer_show_result(result, 'Engine profile probe written')
        except Exception as exc:
            messagebox.showerror('Engine profile probe failed', str(exc))

    def gap_closer_source_model_ui(self):
        self._run(gc.build_source_runtime_model, 'Source runtime model written', 'Source runtime model failed')

    def gap_closer_scenario_dry_ui(self):
        self._run(gc.build_engine_scenario_sessions, 'Engine scenario dry-run written', 'Engine scenario dry-run failed', dry_run=True)

    def gap_closer_scenario_live_ui(self):
        root = self._gap_closer_root()
        if not root:
            return
        if not messagebox.askyesno('Run external engine?', 'This will run the configured external engine executable. Continue?'):
            return
        try:
            timeout = simpledialog.askfloat('Engine timeout', 'Timeout seconds:', initialvalue=12.0, minvalue=1.0, maxvalue=300.0) or 12.0
            result = gc.build_engine_scenario_sessions(root, dry_run=False, timeout_seconds=timeout)
            self._reload_project()
            self._gap_closer_show_result(result, 'Engine scenario live run attempted')
        except Exception as exc:
            messagebox.showerror('Engine scenario live run failed', str(exc))

    def gap_closer_readiness_ui(self):
        self._run(gc.build_engine_backed_readiness_gate, 'Engine-backed readiness gate written', 'Engine-backed readiness failed')

    def gap_closer_corpus_ui(self):
        root = self._gap_closer_root()
        if not root:
            return
        folder = filedialog.askdirectory(title='Optional corpus folder of characters/assets. Cancel to scan current project only.')
        try:
            result = gc.build_sff_snd_corpus_lab(root, folder or None)
            self._reload_project()
            self._gap_closer_show_result(result, 'SFF/SND corpus lab written')
        except Exception as exc:
            messagebox.showerror('SFF/SND corpus lab failed', str(exc))

    def gap_closer_triage_ui(self):
        self._run(gc.write_unknown_binary_triage, 'Unknown binary triage written', 'Unknown binary triage failed')

    def gap_closer_commit_sheet_ui(self):
        self._run(gc.export_binary_commit_sheet, 'Guarded binary commit sheet exported', 'Guarded binary commit sheet failed')

    def gap_closer_apply_commit_ui(self):
        if messagebox.askyesno('Apply guarded binary commits?', 'Only enabled rows with commit_token=COMMIT will be copied into target binary slots after hash checks and backups. Continue?'):
            self._run(gc.apply_binary_commit_sheet, 'Guarded binary commit sheet applied', 'Guarded binary commit apply failed')

    def gap_closer_tuning_sheet_ui(self):
        self._run(gc.export_generated_code_tuning_lab, 'Generated code tuning sheet exported', 'Generated code tuning sheet failed')

    def gap_closer_apply_tuning_ui(self):
        if messagebox.askyesno('Apply generated-code tuning?', 'Only enabled rows in generated_code_tuning_sheet.csv will be applied, with backups. Continue?'):
            self._run(gc.apply_generated_code_tuning_sheet, 'Generated code tuning sheet applied', 'Generated code tuning apply failed')

    def gap_closer_bundle_ui(self):
        self._run(gc.build_gap_closer_bundle, 'Gap Closer bundle built', 'Gap Closer bundle failed')
