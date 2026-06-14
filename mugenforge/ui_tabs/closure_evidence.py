from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import closure_lab as cl
from .. import evidence_core as ev_core
from .base import AppBackedTab


class ClosureLabTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.closure_lab_frame = self.frame
        self._publish(
            '_closure_lab_root',
            '_closure_lab_show_result',
            'closure_lab_one_click_ui',
            'closure_lab_dashboard_ui',
            'closure_lab_offline_runtime_ui',
            'closure_lab_engine_adapter_ui',
            'closure_lab_validate_engine_ui',
            'closure_lab_dry_engine_ui',
            'closure_lab_run_engine_ui',
            'closure_lab_sff2_corpus_ui',
            'closure_lab_sff2_triage_ui',
            'closure_lab_export_commit_ui',
            'closure_lab_apply_commit_ui',
            'closure_lab_restore_commit_ui',
            'closure_lab_tuning_sheet_ui',
            'closure_lab_apply_tuning_ui',
            'closure_lab_evidence_contract_ui',
            'closure_lab_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Closure Lab v{cl.CLOSURE_LAB_VERSION} — runtime simulation, engine adapters, corpus validation, safe commit, tuning loop', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Closure Lab directly targets the previous honest-limitation list. It adds a source-level mini-runtime, validated external-engine adapters, '
            'SFF2 corpus validation and triage, opt-in binary commit/rollback, gameplay tuning sheets, and evidence-level contracts for reports.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Closure Pass', self.closure_lab_one_click_ui),
            ('Dashboard', self.closure_lab_dashboard_ui),
            ('Offline Runtime Simulation', self.closure_lab_offline_runtime_ui),
            ('Engine Adapter Suite', self.closure_lab_engine_adapter_ui),
            ('Validate Engine Adapter', self.closure_lab_validate_engine_ui),
            ('Dry-Run Engine Adapter', self.closure_lab_dry_engine_ui),
            ('Run Engine Adapter', self.closure_lab_run_engine_ui),
            ('SFF2 Corpus Validator', self.closure_lab_sff2_corpus_ui),
            ('Unknown SFF2 Triage', self.closure_lab_sff2_triage_ui),
            ('Export Commit Sheet', self.closure_lab_export_commit_ui),
            ('Apply Commit Sheet', self.closure_lab_apply_commit_ui),
            ('Restore Last Commit', self.closure_lab_restore_commit_ui),
            ('Gameplay Tuning Sheet', self.closure_lab_tuning_sheet_ui),
            ('Apply Gameplay Tuning', self.closure_lab_apply_tuning_ui),
            ('Evidence Contract', self.closure_lab_evidence_contract_ui),
            ('Closure Bundle', self.closure_lab_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 4, column=idx % 4, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 4, weight=1)

        body = ttk.LabelFrame(frame, text='What this closes', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'Suggested order: One-Click Closure Pass → configure engine_adapter_config.json if you have an engine → run dry-run command preview → '
            'run engine adapter/scenarios → tune gameplay sheet → validate corpus/candidates → commit vetted binary candidates only when rollback snapshots are acceptable.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.closure_lab_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.closure_lab_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Closure Lab')
        self._set_text(self.app.closure_lab_output, 'Closure Lab v7.0 is ready. Open a project, then run One-Click Closure Pass.')

    def _closure_lab_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Closure Lab', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _closure_lab_show_result(self, result, status: str):
        self._set_text(self.app.closure_lab_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.closure_lab_frame)
        self._reload_project()

    def _run(self, func, status: str, error_title: str, *args, **kwargs):
        root = self._closure_lab_root()
        if not root:
            return False
        try:
            self._closure_lab_show_result(func(root, *args, **kwargs), status)
            return True
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))
            return False

    def closure_lab_one_click_ui(self):
        if self._run(cl.run_closure_lab_pass, 'Closure Lab pass complete', 'Closure Lab failed'):
            messagebox.showinfo('Closure Lab complete', 'Closure Lab pass completed. Review closure_lab/CLOSURE_LAB_START_HERE.md.')

    def closure_lab_dashboard_ui(self):
        self._run(cl.write_closure_dashboard, 'Closure Lab dashboard written', 'Closure dashboard failed')

    def closure_lab_offline_runtime_ui(self):
        root = self._closure_lab_root()
        if not root:
            return
        start = simpledialog.askinteger('Offline runtime', 'Start StateDef:', initialvalue=0) or 0
        ticks = simpledialog.askinteger('Offline runtime', 'Ticks to simulate:', initialvalue=180, minvalue=1, maxvalue=10000) or 180
        try:
            self._closure_lab_show_result(cl.build_offline_runtime_simulation(root, start_state=start, max_ticks=ticks), 'Offline runtime simulation written')
        except Exception as exc:
            messagebox.showerror('Offline runtime simulation failed', str(exc))

    def closure_lab_engine_adapter_ui(self):
        self._run(cl.write_engine_adapter_suite, 'Engine adapter suite written', 'Engine adapter suite failed')

    def closure_lab_validate_engine_ui(self):
        self._run(cl.validate_engine_adapter_suite, 'Engine adapter validation written', 'Engine adapter validation failed')

    def closure_lab_dry_engine_ui(self):
        root = self._closure_lab_root()
        if not root:
            return
        profile = simpledialog.askstring('Engine adapter profile', 'Profile name:', initialvalue='quick_boot') or 'quick_boot'
        try:
            self._closure_lab_show_result(cl.run_engine_adapter_suite(root, profile_name=profile, dry_run=True), 'Engine adapter dry-run complete')
        except Exception as exc:
            messagebox.showerror('Engine adapter dry-run failed', str(exc))

    def closure_lab_run_engine_ui(self):
        root = self._closure_lab_root()
        if not root:
            return
        if not messagebox.askyesno('Run external engine', 'Run your configured local engine profile now? Configure and dry-run first. MugenForge captures stdout/stderr and result JSON.'):
            return
        profile = simpledialog.askstring('Engine adapter profile', 'Profile name:', initialvalue='quick_boot') or 'quick_boot'
        timeout = simpledialog.askinteger('Engine timeout', 'Timeout seconds:', initialvalue=20, minvalue=1, maxvalue=3600) or 20
        try:
            self._closure_lab_show_result(cl.run_engine_adapter_suite(root, profile_name=profile, dry_run=False, timeout_seconds=timeout), 'Engine adapter run complete')
        except Exception as exc:
            messagebox.showerror('Engine adapter run failed', str(exc))

    def closure_lab_sff2_corpus_ui(self):
        root = self._closure_lab_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('SFF2 corpus', 'Choose a folder of .sff files? Choose No to use closure_lab/sff2_corpus/drop_sff_files_here.'):
            chosen = filedialog.askdirectory(title='Choose SFF2 corpus folder')
            if chosen:
                folder = Path(chosen)
        try:
            self._closure_lab_show_result(cl.build_sff2_corpus_validator(root, folder), 'SFF2 corpus validator written')
        except Exception as exc:
            messagebox.showerror('SFF2 corpus validator failed', str(exc))

    def closure_lab_sff2_triage_ui(self):
        self._run(cl.write_sff2_unknown_triage, 'Unknown SFF2 triage written', 'Unknown SFF2 triage failed')

    def closure_lab_export_commit_ui(self):
        self._run(cl.export_direct_mutation_commit_sheet, 'Mutation commit sheet exported', 'Mutation commit sheet failed')

    def closure_lab_apply_commit_ui(self):
        if messagebox.askyesno('Apply mutation commit sheet', 'Apply enabled commit rows? This can overwrite project SFF/SND targets, but writes a rollback snapshot first.'):
            self._run(cl.apply_direct_mutation_commit_sheet, 'Mutation commit sheet applied', 'Apply mutation commit sheet failed')

    def closure_lab_restore_commit_ui(self):
        if messagebox.askyesno('Restore last mutation snapshot', 'Restore the last binary mutation snapshot?'):
            self._run(cl.restore_last_mutation_snapshot, 'Last mutation snapshot restored', 'Restore mutation snapshot failed')

    def closure_lab_tuning_sheet_ui(self):
        self._run(cl.export_gameplay_tuning_sheet, 'Gameplay tuning sheet exported', 'Gameplay tuning sheet failed')

    def closure_lab_apply_tuning_ui(self):
        self._run(cl.apply_gameplay_tuning_sheet, 'Gameplay tuning sheet applied', 'Apply gameplay tuning failed')

    def closure_lab_evidence_contract_ui(self):
        self._run(cl.write_report_evidence_contract, 'Report evidence contract written', 'Report evidence contract failed')

    def closure_lab_bundle_ui(self):
        self._run(cl.build_closure_lab_bundle, 'Closure Lab bundle built', 'Closure Lab bundle failed')


class EvidenceCoreTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.evidence_core_frame = self.frame
        self._publish(
            '_evidence_core_root',
            '_evidence_core_show_result',
            'evidence_core_one_click_ui',
            'evidence_core_dashboard_ui',
            'evidence_core_configure_engine_ui',
            'evidence_core_probe_engine_ui',
            'evidence_core_launch_matrix_ui',
            'evidence_core_dry_run_ui',
            'evidence_core_run_validation_ui',
            'evidence_core_ingest_ui',
            'evidence_core_authority_ui',
            'evidence_core_corpus_harness_ui',
            'evidence_core_corpus_run_ui',
            'evidence_core_candidate_sheet_ui',
            'evidence_core_apply_candidate_ui',
            'evidence_core_tuning_sheet_ui',
            'evidence_core_apply_tuning_ui',
            'evidence_core_playtest_closure_ui',
            'evidence_core_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Evidence Core v{ev_core.EVIDENCE_CORE_VERSION} — engine-backed evidence, corpus validation, and verified promotion', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Evidence Core turns the remaining honest limitations into practical workflows: configure/probe an external engine, '
            'build launch matrices, capture real stdout/stderr/log evidence, validate SFF2 files against a corpus, promote binary candidates only through a verified install sheet, '
            'and export/apply playtest-backed tuning sheets. It does not bundle or emulate M.U.G.E.N/IKEMEN.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Evidence Core Pass', self.evidence_core_one_click_ui),
            ('Dashboard', self.evidence_core_dashboard_ui),
            ('Configure Engine Profile', self.evidence_core_configure_engine_ui),
            ('Probe Engine', self.evidence_core_probe_engine_ui),
            ('Build Launch Matrix', self.evidence_core_launch_matrix_ui),
            ('Dry-Run Validation', self.evidence_core_dry_run_ui),
            ('Run Engine Validation', self.evidence_core_run_validation_ui),
            ('Ingest Evidence', self.evidence_core_ingest_ui),
            ('Authority Report', self.evidence_core_authority_ui),
            ('SFF2 Corpus Harness', self.evidence_core_corpus_harness_ui),
            ('Run SFF2 Corpus', self.evidence_core_corpus_run_ui),
            ('Verified Install Sheet', self.evidence_core_candidate_sheet_ui),
            ('Apply Verified Install', self.evidence_core_apply_candidate_ui),
            ('Runtime Tuning Sheet', self.evidence_core_tuning_sheet_ui),
            ('Apply Runtime Tuning', self.evidence_core_apply_tuning_ui),
            ('Playtest Closure', self.evidence_core_playtest_closure_ui),
            ('Evidence Bundle', self.evidence_core_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 5, column=idx % 5, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 5, weight=1)

        body = ttk.LabelFrame(frame, text='Gap-closure workflow', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'Suggested order: Configure Engine Profile → Probe Engine → Build Launch Matrix → Dry-Run Validation → Run Engine Validation → '
            'Ingest Evidence → Authority Report → Corpus Validation → Verified Install Sheet → Runtime Tuning / Playtest Closure.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.evidence_core_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.evidence_core_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Evidence Core')
        self._set_text(self.app.evidence_core_output, 'Evidence Core v7.0 is ready. Open a project, then run One-Click Evidence Core Pass or configure your local engine path.')

    def _evidence_core_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Evidence Core', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _evidence_core_show_result(self, result, status: str):
        self._set_text(self.app.evidence_core_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.evidence_core_frame)
        self._reload_project()

    def _run(self, func, status: str, error_title: str, *args, **kwargs):
        root = self._evidence_core_root()
        if not root:
            return False
        try:
            self._evidence_core_show_result(func(root, *args, **kwargs), status)
            return True
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))
            return False

    def evidence_core_one_click_ui(self):
        if self._run(ev_core.run_evidence_core_pass, 'Evidence Core pass complete', 'Evidence Core failed'):
            messagebox.showinfo('Evidence Core complete', 'Evidence Core pass completed. Review evidence_core/EVIDENCE_CORE_START_HERE.md.')

    def evidence_core_dashboard_ui(self):
        self._run(ev_core.write_evidence_core_dashboard, 'Evidence Core dashboard written', 'Evidence Core dashboard failed')

    def evidence_core_configure_engine_ui(self):
        root = self._evidence_core_root()
        if not root:
            return
        exe = filedialog.askopenfilename(title='Choose your local M.U.G.E.N / IKEMEN executable', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if not exe:
            return
        default_stage = simpledialog.askstring('Default test stage', 'Default stage entry:', initialvalue='stages/training.def') or 'stages/training.def'
        opponent = simpledialog.askstring('Default opponent', 'Default opponent entry:', initialvalue='kfm') or 'kfm'
        try:
            self._evidence_core_show_result(
                ev_core.write_engine_profile(root, engine_exe=Path(exe), game_root=Path(exe).parent, default_stage=default_stage, opponent=opponent),
                'Evidence Core engine profile written',
            )
        except Exception as exc:
            messagebox.showerror('Evidence Core profile failed', str(exc))

    def evidence_core_probe_engine_ui(self):
        self._run(ev_core.probe_engine_profile, 'Evidence Core engine probe written', 'Evidence Core engine probe failed')

    def evidence_core_launch_matrix_ui(self):
        self._run(ev_core.build_engine_launch_matrix, 'Evidence Core launch matrix written', 'Evidence Core launch matrix failed')

    def evidence_core_dry_run_ui(self):
        self._run(ev_core.run_engine_validation, 'Evidence Core dry-run validation written', 'Evidence Core dry-run failed', dry_run=True)

    def evidence_core_run_validation_ui(self):
        root = self._evidence_core_root()
        if not root:
            return
        if not messagebox.askyesno('Run external engine validation', 'Launch your configured local engine for enabled Evidence Core scenarios? Review the launch matrix first.'):
            return
        timeout = simpledialog.askfloat('Validation timeout', 'Seconds before MugenForge stops each process:', initialvalue=12.0, minvalue=0.1) or 12.0
        try:
            self._evidence_core_show_result(ev_core.run_engine_validation(root, dry_run=False, timeout_seconds=timeout), 'Evidence Core engine validation attempted')
        except Exception as exc:
            messagebox.showerror('Evidence Core validation failed', str(exc))

    def evidence_core_ingest_ui(self):
        root = self._evidence_core_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('Evidence ingest', 'Choose a folder containing engine logs/notes? Choose No to use evidence_core/evidence_inbox and runtime_lab folders.'):
            chosen = filedialog.askdirectory(title='Choose evidence folder')
            if chosen:
                folder = Path(chosen)
        try:
            self._evidence_core_show_result(ev_core.ingest_engine_evidence(root, folder), 'Evidence Core evidence ingested')
        except Exception as exc:
            messagebox.showerror('Evidence Core ingest failed', str(exc))

    def evidence_core_authority_ui(self):
        self._run(ev_core.write_evidence_authority_report, 'Evidence authority report written', 'Evidence authority report failed')

    def evidence_core_corpus_harness_ui(self):
        root = self._evidence_core_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('SFF2 corpus harness', 'Choose an external folder of SFF files? Choose No to scan this project and generated binary folders.'):
            chosen = filedialog.askdirectory(title='Choose SFF/SFF2 corpus folder')
            if chosen:
                folder = Path(chosen)
        try:
            self._evidence_core_show_result(ev_core.write_sff2_corpus_harness(root, folder), 'SFF2 corpus harness written')
        except Exception as exc:
            messagebox.showerror('SFF2 corpus harness failed', str(exc))

    def evidence_core_corpus_run_ui(self):
        self._run(ev_core.run_sff2_corpus_validation, 'SFF2 corpus validation written', 'SFF2 corpus validation failed')

    def evidence_core_candidate_sheet_ui(self):
        self._run(ev_core.export_verified_candidate_install_sheet, 'Verified candidate install sheet written', 'Verified candidate sheet failed')

    def evidence_core_apply_candidate_ui(self):
        if messagebox.askyesno('Apply verified candidate install sheet', 'Apply enabled rows from evidence_core/candidate_promotion/verified_candidate_install_sheet.csv? Current targets will be backed up first.'):
            self._run(ev_core.apply_verified_candidate_install_sheet, 'Verified candidate install sheet applied', 'Apply verified candidate sheet failed')

    def evidence_core_tuning_sheet_ui(self):
        self._run(ev_core.export_runtime_tuning_sheet, 'Runtime tuning sheet written', 'Runtime tuning sheet failed')

    def evidence_core_apply_tuning_ui(self):
        if messagebox.askyesno('Apply runtime tuning sheet', 'Apply enabled rows from evidence_core/runtime_tuning/runtime_tuning_sheet.csv? Source files will be backed up first.'):
            self._run(ev_core.apply_runtime_tuning_sheet, 'Runtime tuning sheet applied', 'Apply runtime tuning failed')

    def evidence_core_playtest_closure_ui(self):
        self._run(ev_core.write_playtest_closure_report, 'Playtest closure report written', 'Playtest closure failed')

    def evidence_core_bundle_ui(self):
        self._run(ev_core.build_evidence_core_bundle, 'Evidence Core bundle built', 'Evidence Core bundle failed')
