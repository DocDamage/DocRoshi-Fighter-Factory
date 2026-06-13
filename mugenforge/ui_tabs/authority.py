from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import authority_core as ac
from .. import authority_lab as auth_lab
from .base import AppBackedTab


class AuthorityCoreTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.authority_core_frame = self.frame
        self._publish(
            '_authority_core_root',
            '_authority_core_show_result',
            'authority_core_one_click_ui',
            'authority_core_dashboard_ui',
            'authority_core_contracts_ui',
            'authority_core_validate_engine_ui',
            'authority_core_dry_run_ui',
            'authority_core_run_engine_ui',
            'authority_core_parse_engine_ui',
            'authority_core_reconcile_ui',
            'authority_core_corpus_ui',
            'authority_core_triage_ui',
            'authority_core_install_sheet_ui',
            'authority_core_install_candidates_ui',
            'authority_core_tuning_sheet_ui',
            'authority_core_apply_tuning_ui',
            'authority_core_score_ui',
            'authority_core_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Authority Core v{ac.AUTHORITY_CORE_VERSION} — engine evidence, corpus validation, verified installs, and tuning feedback', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Authority Core targets the remaining honest limitations directly. It can run a configured local engine, capture stdout/stderr/result JSON, '
            'validate SFF/SND corpora, triage unknown binaries, install verified binary candidates with backups, and apply gameplay tuning feedback from playtests.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Authority Pass', self.authority_core_one_click_ui),
            ('Dashboard / Config', self.authority_core_dashboard_ui),
            ('Engine Contracts', self.authority_core_contracts_ui),
            ('Validate Engine Config', self.authority_core_validate_engine_ui),
            ('Dry-Run Engine Command', self.authority_core_dry_run_ui),
            ('Run Engine Scenario', self.authority_core_run_engine_ui),
            ('Parse Engine Runs', self.authority_core_parse_engine_ui),
            ('Runtime Reconciliation', self.authority_core_reconcile_ui),
            ('Corpus Validation', self.authority_core_corpus_ui),
            ('Unknown Binary Triage', self.authority_core_triage_ui),
            ('Binary Install Sheet', self.authority_core_install_sheet_ui),
            ('Install Enabled Candidates', self.authority_core_install_candidates_ui),
            ('Tuning Feedback Sheet', self.authority_core_tuning_sheet_ui),
            ('Apply Tuning Sheet', self.authority_core_apply_tuning_ui),
            ('Authority Score', self.authority_core_score_ui),
            ('Bundle Authority Core', self.authority_core_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 5, column=idx % 5, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 5, weight=1)

        body = ttk.LabelFrame(frame, text='Evidence-first loop', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'Write config → validate engine path/profile → dry-run command → run engine scenario → parse logs → reconcile telemetry → '
            'validate binary corpus → install only verified candidates → apply tuning feedback → regenerate Authority Score.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.authority_core_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.authority_core_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Authority Core')
        self._set_text(
            self.app.authority_core_output,
            f'Authority Core v{ac.AUTHORITY_CORE_VERSION} is ready. Start with One-Click Authority Pass, then configure authority_core/engine_config.json for real engine-backed runs.',
        )

    def _authority_core_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Authority Core', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _authority_core_show_result(self, result, status: str):
        self._set_text(self.app.authority_core_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.authority_core_frame)

    def _run(self, func, status: str, error_title: str, *args, **kwargs):
        root = self._authority_core_root()
        if not root:
            return
        try:
            self._authority_core_show_result(func(root, *args, **kwargs), status)
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))

    def authority_core_one_click_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        try:
            result = ac.run_authority_core_pass(root)
            self._reload_project()
            self._authority_core_show_result(result, 'Authority Core pass complete')
            messagebox.showinfo('Authority Core complete', 'Authority Core pass completed. Review authority_core/AUTHORITY_CORE_START_HERE.md and authority_core/authority_score/AUTHORITY_SCORE.md.')
        except Exception as exc:
            messagebox.showerror('Authority Core failed', str(exc))

    def authority_core_dashboard_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        try:
            res = ac.write_authority_dashboard(root)
            res.merge(ac.write_engine_contract_profiles(root), 'engine contracts')
            self._authority_core_show_result(res, 'Authority dashboard/config written')
        except Exception as exc:
            messagebox.showerror('Authority dashboard failed', str(exc))

    def authority_core_contracts_ui(self):
        self._run(ac.write_engine_contract_profiles, 'Engine contract profiles written', 'Engine contracts failed')

    def authority_core_validate_engine_ui(self):
        self._run(ac.validate_engine_configuration, 'Engine config validated', 'Engine config validation failed')

    def authority_core_dry_run_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        scenario = simpledialog.askstring('Authority Core dry-run', 'Scenario ID:', initialvalue='smoke') or 'smoke'
        try:
            self._authority_core_show_result(ac.run_authoritative_engine_scenario(root, scenario_id=scenario, dry_run=True), 'Engine command dry-run written')
        except Exception as exc:
            messagebox.showerror('Engine dry-run failed', str(exc))

    def authority_core_run_engine_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        if not messagebox.askyesno('Run external engine', 'Launch the configured local engine now? MugenForge will capture stdout/stderr/result JSON and will not modify your engine install.'):
            return
        scenario = simpledialog.askstring('Authority Core engine run', 'Scenario ID:', initialvalue='smoke') or 'smoke'
        timeout = simpledialog.askfloat('Engine timeout', 'Seconds before timeout:', initialvalue=30.0, minvalue=1.0) or 30.0
        try:
            self._authority_core_show_result(ac.run_authoritative_engine_scenario(root, scenario_id=scenario, timeout_seconds=timeout, dry_run=False), 'External engine scenario attempted')
        except Exception as exc:
            messagebox.showerror('Engine scenario failed', str(exc))

    def authority_core_parse_engine_ui(self):
        self._run(ac.parse_engine_run_results, 'Engine run results parsed', 'Engine result parsing failed')

    def authority_core_reconcile_ui(self):
        self._run(ac.write_runtime_reconciliation_report, 'Runtime reconciliation written', 'Runtime reconciliation failed')

    def authority_core_corpus_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('Binary corpus validation', 'Choose a corpus folder? Choose No to scan the current project folder.'):
            chosen = filedialog.askdirectory(title='Choose SFF/SND corpus folder')
            if chosen:
                folder = Path(chosen)
        try:
            self._authority_core_show_result(ac.write_sff_snd_corpus_validation_suite(root, folder), 'Binary corpus validation written')
        except Exception as exc:
            messagebox.showerror('Binary corpus validation failed', str(exc))

    def authority_core_triage_ui(self):
        self._run(ac.triage_unknown_binary_layouts, 'Unknown binary triage written', 'Unknown binary triage failed')

    def authority_core_install_sheet_ui(self):
        self._run(ac.export_binary_install_sheet, 'Binary install sheet written', 'Binary install sheet failed')

    def authority_core_install_candidates_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        if not messagebox.askyesno('Install verified binary candidates', 'Install rows marked enabled=yes in authority_core/verified_binary_install/verified_binary_install_sheet.csv? Backups will be written first.'):
            return
        try:
            self._authority_core_show_result(ac.install_verified_binary_candidates(root), 'Verified binary candidates installed')
            self._reload_project()
        except Exception as exc:
            messagebox.showerror('Binary candidate install failed', str(exc))

    def authority_core_tuning_sheet_ui(self):
        self._run(ac.write_gameplay_tuning_feedback_sheet, 'Gameplay tuning feedback sheet written', 'Gameplay tuning sheet failed')

    def authority_core_apply_tuning_ui(self):
        root = self._authority_core_root()
        if not root:
            return
        if not messagebox.askyesno('Apply gameplay tuning feedback', 'Apply enabled rows in authority_core/gameplay_tuning/gameplay_tuning_feedback_sheet.csv? Backups will be written first.'):
            return
        try:
            self._authority_core_show_result(ac.apply_gameplay_tuning_feedback_sheet(root), 'Gameplay tuning feedback applied')
            self._reload_project()
        except Exception as exc:
            messagebox.showerror('Gameplay tuning apply failed', str(exc))

    def authority_core_score_ui(self):
        self._run(ac.write_authority_score, 'Authority score written', 'Authority score failed')

    def authority_core_bundle_ui(self):
        self._run(ac.build_authority_core_bundle, 'Authority Core bundle built', 'Authority bundle failed')


class AuthorityLabTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.authority_lab_frame = self.frame
        self._publish(
            '_authority_lab_root',
            '_authority_lab_show_result',
            'authority_lab_one_click_ui',
            'authority_lab_dashboard_ui',
            'authority_lab_verify_engine_ui',
            'authority_lab_probe_engine_ui',
            'authority_lab_source_sim_ui',
            'authority_lab_corpus_ui',
            'authority_lab_commit_sheet_ui',
            'authority_lab_apply_commit_ui',
            'authority_lab_tuning_ui',
            'authority_lab_gate_ui',
            'authority_lab_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Authority Lab v{auth_lab.AUTHORITY_LAB_VERSION} — close remaining gaps with evidence and verified commits', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Authority Lab turns the previous limitation list into concrete workflows: engine profile verification/probing, '
            'source-runtime simulation, SFF2 corpus validation and fingerprinting, verified binary candidate promotion, '
            'gameplay tuning workbench sheets, and an evidence-backed release gate.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Authority Pass', self.authority_lab_one_click_ui),
            ('Dashboard', self.authority_lab_dashboard_ui),
            ('Verify Engine Profile', self.authority_lab_verify_engine_ui),
            ('Probe Engine', self.authority_lab_probe_engine_ui),
            ('Source Runtime Simulation', self.authority_lab_source_sim_ui),
            ('SFF2 Corpus Validation', self.authority_lab_corpus_ui),
            ('Binary Commit Sheet', self.authority_lab_commit_sheet_ui),
            ('Apply Binary Commit Sheet', self.authority_lab_apply_commit_ui),
            ('Gameplay Tuning Workbench', self.authority_lab_tuning_ui),
            ('Evidence Authority Gate', self.authority_lab_gate_ui),
            ('Authority Bundle', self.authority_lab_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 5, column=idx % 5, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 5, weight=1)

        body = ttk.LabelFrame(frame, text='What this replaces from the old limitations list', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'Suggested order: Dashboard → Verify/Probe Engine → Source Runtime Simulation → SFF2 Corpus Validation → '
            'Binary Commit Sheet for tested candidates → Gameplay Tuning Workbench → Evidence Authority Gate → Authority Bundle.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.authority_lab_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.authority_lab_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Authority Lab')
        self._set_text(self.app.authority_lab_output, 'Authority Lab v7.0 is ready. Open a project, then run One-Click Authority Pass.')

    def _authority_lab_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Authority Lab', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _authority_lab_show_result(self, result, status: str):
        self._set_text(self.app.authority_lab_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.authority_lab_frame)
        self._reload_project()

    def _run(self, func, status: str, error_title: str, *args, **kwargs):
        root = self._authority_lab_root()
        if not root:
            return
        try:
            self._authority_lab_show_result(func(root, *args, **kwargs), status)
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))

    def authority_lab_one_click_ui(self):
        root = self._authority_lab_root()
        if not root:
            return
        try:
            result = auth_lab.run_authority_lab_pass(root)
            self._authority_lab_show_result(result, 'Authority Lab pass complete')
            messagebox.showinfo('Authority Lab complete', 'Authority Lab pass completed. Review authority_lab/AUTHORITY_START_HERE.md and authority_lab/release_gate/.')
        except Exception as exc:
            messagebox.showerror('Authority Lab failed', str(exc))

    def authority_lab_dashboard_ui(self):
        self._run(auth_lab.write_authority_dashboard, 'Authority dashboard written', 'Authority dashboard failed')

    def authority_lab_verify_engine_ui(self):
        self._run(auth_lab.verify_engine_profile, 'Engine profile verified', 'Engine verification failed', run_probe=False)

    def authority_lab_probe_engine_ui(self):
        root = self._authority_lab_root()
        if not root:
            return
        if not messagebox.askyesno('Probe engine', 'Run the configured external engine command briefly? This uses runtime_lab/runtime_config.json and captures stdout/stderr.'):
            return
        timeout = simpledialog.askfloat('Probe timeout', 'Seconds before MugenForge terminates the probe:', initialvalue=5.0, minvalue=0.1) or 5.0
        try:
            self._authority_lab_show_result(auth_lab.verify_engine_profile(root, run_probe=True, timeout_seconds=timeout), 'Engine probe attempted')
        except Exception as exc:
            messagebox.showerror('Engine probe failed', str(exc))

    def authority_lab_source_sim_ui(self):
        self._run(auth_lab.build_source_runtime_simulation, 'Source runtime simulation written', 'Source runtime simulation failed')

    def authority_lab_corpus_ui(self):
        root = self._authority_lab_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('SFF2 corpus folder', 'Choose an extra folder of SFF/SFF2 files to validate? Choose No to scan the project and authority_lab/sff2_corpus/corpus_inbox.'):
            chosen = filedialog.askdirectory(title='Choose SFF2 corpus folder')
            if chosen:
                folder = Path(chosen)
        try:
            self._authority_lab_show_result(auth_lab.validate_sff2_corpus(root, folder), 'SFF2 corpus validation written')
        except Exception as exc:
            messagebox.showerror('SFF2 corpus validation failed', str(exc))

    def authority_lab_commit_sheet_ui(self):
        self._run(auth_lab.export_verified_binary_commit_sheet, 'Verified binary commit sheet written', 'Binary commit sheet failed')

    def authority_lab_apply_commit_ui(self):
        root = self._authority_lab_root()
        if not root:
            return
        if not messagebox.askyesno('Apply binary commit sheet', 'Apply enabled rows from authority_lab/binary_commit/verified_binary_commit_sheet.csv? Live files will be backed up first.'):
            return
        try:
            self._authority_lab_show_result(auth_lab.apply_verified_binary_commit_sheet(root), 'Verified binary commit sheet applied')
        except Exception as exc:
            messagebox.showerror('Apply binary commit sheet failed', str(exc))

    def authority_lab_tuning_ui(self):
        self._run(auth_lab.write_gameplay_tuning_workbench, 'Gameplay tuning workbench written', 'Gameplay tuning workbench failed')

    def authority_lab_gate_ui(self):
        self._run(auth_lab.write_evidence_authority_gate, 'Evidence authority gate written', 'Evidence authority gate failed')

    def authority_lab_bundle_ui(self):
        self._run(auth_lab.build_authority_bundle, 'Authority bundle built', 'Authority bundle failed')
