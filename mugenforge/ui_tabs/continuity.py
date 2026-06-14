from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import handoff_core as ho_core
from .. import maintenance_core as maint_core
from .. import operator_console as op_console
from .base import AppBackedTab


class HandoffCoreTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self.root_var = None
        self.note = None
        self.output = None
        self._build()
        self.app.handoff_core_frame = self.frame
        self.app.handoff_core_root_var = self.root_var
        self.app.handoff_core_note = self.note
        self.app.handoff_core_output = self.output
        self._publish(
            '_handoff_core_root',
            '_handoff_core_show_result',
            'handoff_core_one_click_ui',
            'handoff_core_digest_ui',
            'handoff_core_inventory_ui',
            'handoff_core_regression_ui',
            'handoff_core_prompt_ui',
            'handoff_core_development_ui',
            'handoff_core_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook, padding=8)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(
            frame,
            text=f'Handoff Core v{ho_core.HANDOFF_CORE_VERSION} — continuity pack, package inventory, regression harness, and next-chat prompt',
            padding=(8, 6),
        )
        header.grid(row=0, column=0, sticky='ew')
        self.root_var = tk.StringVar(value='Current project folder; if none is open, uses the application package folder.')
        ttk.Label(header, textvariable=self.root_var, wraplength=1050, justify='left').grid(row=0, column=0, sticky='w')

        buttons = ttk.LabelFrame(frame, text='Continuity actions', padding=(8, 6))
        buttons.grid(row=1, column=0, sticky='ew', pady=(8, 6))
        actions = [
            ('One-Click Handoff Pass', self.handoff_core_one_click_ui),
            ('Context Digest', self.handoff_core_digest_ui),
            ('Package Inventory', self.handoff_core_inventory_ui),
            ('Regression Harness', self.handoff_core_regression_ui),
            ('Next Chat Prompt', self.handoff_core_prompt_ui),
            ('Development Handoff', self.handoff_core_development_ui),
            ('Bundle Handoff', self.handoff_core_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(actions):
            ttk.Button(buttons, text=label, command=cmd).grid(row=idx // 4, column=idx % 4, padx=3, pady=3, sticky='ew')
        for col in range(4):
            buttons.columnconfigure(col, weight=1)

        body = ttk.LabelFrame(frame, text='How to use this before context changes', padding=(8, 6))
        body.grid(row=2, column=0, sticky='nsew')
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=1)
        self.note = tk.Text(body, wrap='word', height=7, font=('Consolas', 10))
        self.note.grid(row=0, column=0, sticky='ew')
        self._set_text(
            self.note,
            'Run One-Click Handoff Pass before moving the project to another chat or machine. It writes a context digest, package inventory, smoke-test harness, next-chat prompt, and handoff bundle. This is a continuity system, not a replacement for real engine testing.',
        )
        self.output = tk.Text(body, wrap='word', height=20, font=('Consolas', 10))
        self.output.grid(row=1, column=0, sticky='nsew', pady=(6, 0))
        self.notebook.add(frame, text='Handoff Core')
        self._set_text(
            self.output,
            f'Handoff Core v{ho_core.HANDOFF_CORE_VERSION} is ready. Open a project, or run it against the application package when no project is open.',
        )

    def _handoff_core_root(self) -> Path:
        root = self.app.project_root or Path(__file__).resolve().parents[2]
        self.root_var.set(f'Handoff target: {root}')
        return Path(root)

    def _handoff_core_show_result(self, result, title='Handoff Core result'):
        self._set_text(self.output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(title)

    def handoff_core_one_click_ui(self):
        root = self._handoff_core_root()
        try:
            res = ho_core.run_handoff_core_pass(root)
            self._handoff_core_show_result(res, 'Handoff Core pass complete')
            messagebox.showinfo('Handoff Core complete', 'Handoff Core pass completed. Review handoff_core/HANDOFF_CORE_START_HERE.md and docs/NEXT_CHAT_PROMPT_v7_5.md.')
        except Exception as exc:
            messagebox.showerror('Handoff Core failed', str(exc))

    def handoff_core_digest_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.write_context_digest(root), 'Context digest written')
        except Exception as exc:
            messagebox.showerror('Context digest failed', str(exc))

    def handoff_core_inventory_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.write_package_inventory(root), 'Package inventory written')
        except Exception as exc:
            messagebox.showerror('Package inventory failed', str(exc))

    def handoff_core_regression_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.write_regression_harness(root), 'Regression harness written')
        except Exception as exc:
            messagebox.showerror('Regression harness failed', str(exc))

    def handoff_core_prompt_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.write_next_chat_prompt(root), 'Next-chat prompt written')
        except Exception as exc:
            messagebox.showerror('Next chat prompt failed', str(exc))

    def handoff_core_development_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.write_development_handoff(root), 'Development handoff written')
        except Exception as exc:
            messagebox.showerror('Development handoff failed', str(exc))

    def handoff_core_bundle_ui(self):
        root = self._handoff_core_root()
        try:
            self._handoff_core_show_result(ho_core.build_handoff_bundle(root), 'Handoff bundle built')
        except Exception as exc:
            messagebox.showerror('Handoff bundle failed', str(exc))


class OperatorConsoleTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self.output = None
        self._build()
        self.app.operator_console_frame = self.frame
        self.app.operator_console_output = self.output
        self._publish(
            '_operator_console_root',
            '_operator_console_show_result',
            'operator_console_one_click_ui',
            'operator_console_dashboard_ui',
            'operator_console_roadmap_ui',
            'operator_console_handoff_ui',
            'operator_console_decision_log_ui',
            'operator_console_readiness_ui',
            'operator_console_context_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Operator Console v{op_console.OPERATOR_CONSOLE_VERSION} — front door, handoff, and release readiness', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Operator Console is the consolidation layer for this very large toolset. Run it first: it writes a project dashboard, '
            'phase table, next-chat handoff, roadmap, release readiness packet, and a compact context bundle that excludes large binaries.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Operator Pass', self.operator_console_one_click_ui),
            ('Dashboard', self.operator_console_dashboard_ui),
            ('Roadmap', self.operator_console_roadmap_ui),
            ('Next-Chat Handoff', self.operator_console_handoff_ui),
            ('Decision Log Template', self.operator_console_decision_log_ui),
            ('Release Readiness Packet', self.operator_console_readiness_ui),
            ('Context Bundle', self.operator_console_context_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 4, column=idx % 4, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 4, weight=1)

        workflow = ttk.LabelFrame(frame, text='Recommended project flow', padding=(8, 6))
        workflow.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        text = (
            '1. Operator Console → refresh project state.  '
            '2. Forge Timeline → tune moves, timing, CLSN, HitDefs, palettes, and stage preview.  '
            '3. Binary Maturity / Evidence Core → validate SFF/SND candidates and runtime evidence.  '
            '4. Runtime Lab / Authority Lab → collect engine-backed evidence.  '
            '5. Build release/context bundles for handoff.'
        )
        ttk.Label(workflow, text=text, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Operator Console')
        self._set_text(self.output, 'Operator Console v7.5 is ready. Open or create a project, then run One-Click Operator Pass.')

    def _operator_console_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Operator Console', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _operator_console_show_result(self, result, status: str):
        self._set_text(self.output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select()
        self._reload_project()

    def operator_console_one_click_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.run_operator_console_pass(root), 'Operator Console pass complete')
            messagebox.showinfo('Operator Console complete', 'Operator Console pass completed. Start with operator_console/OPERATOR_START_HERE.md.')
        except Exception as exc:
            messagebox.showerror('Operator Console failed', str(exc))

    def operator_console_dashboard_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.write_operator_dashboard(root), 'Operator dashboard written')
        except Exception as exc:
            messagebox.showerror('Operator dashboard failed', str(exc))

    def operator_console_roadmap_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.write_operator_roadmap(root), 'Operator roadmap written')
        except Exception as exc:
            messagebox.showerror('Operator roadmap failed', str(exc))

    def operator_console_handoff_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.write_next_chat_handoff(root), 'Next-chat handoff written')
        except Exception as exc:
            messagebox.showerror('Next-chat handoff failed', str(exc))

    def operator_console_decision_log_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.write_decision_log_template(root), 'Decision log template written')
        except Exception as exc:
            messagebox.showerror('Decision log failed', str(exc))

    def operator_console_readiness_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.write_release_readiness_packet(root), 'Release readiness packet written')
        except Exception as exc:
            messagebox.showerror('Release readiness failed', str(exc))

    def operator_console_context_bundle_ui(self):
        root = self._operator_console_root()
        if not root:
            return
        try:
            self._operator_console_show_result(op_console.build_operator_context_bundle(root), 'Operator context bundle built')
        except Exception as exc:
            messagebox.showerror('Operator context bundle failed', str(exc))


class MaintenanceCoreTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self.output = None
        self._build()
        self.app.maintenance_core_frame = self.frame
        self.app.maintenance_core_output = self.output
        self._publish(
            '_maintenance_core_root',
            '_maintenance_core_show_result',
            'maintenance_core_one_click_ui',
            'maintenance_core_dashboard_ui',
            'maintenance_core_catalog_ui',
            'maintenance_core_ui_inventory_ui',
            'maintenance_core_lineage_ui',
            'maintenance_core_claims_ui',
            'maintenance_core_scripts_ui',
            'maintenance_core_backlog_ui',
            'maintenance_core_handoff_ui',
            'maintenance_core_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Maintenance Core v{maint_core.MAINTENANCE_CORE_VERSION} — handoff, architecture catalog, regression scripts, and honesty audits', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Maintenance Core is for continuity between releases and chats. It creates a developer handoff, module/API catalog, UI tab inventory, '
            'release lineage, claim-risk audit, smoke scripts, backlog, and a maintenance bundle. It does not modify gameplay code or user binaries.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Maintenance Pass', self.maintenance_core_one_click_ui),
            ('Maintainer Dashboard', self.maintenance_core_dashboard_ui),
            ('Module/API Catalog', self.maintenance_core_catalog_ui),
            ('UI Tab Inventory', self.maintenance_core_ui_inventory_ui),
            ('Release Lineage', self.maintenance_core_lineage_ui),
            ('Honesty Claims Audit', self.maintenance_core_claims_ui),
            ('Write Smoke Scripts', self.maintenance_core_scripts_ui),
            ('Maintenance Backlog', self.maintenance_core_backlog_ui),
            ('Write Handoff', self.maintenance_core_handoff_ui),
            ('Bundle Maintenance Core', self.maintenance_core_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 4, column=idx % 4, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 4, weight=1)

        body = ttk.LabelFrame(frame, text='Recommended handoff workflow', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'Run One-Click Maintenance Pass → open maintenance_core/MAINTAINER_START_HERE.md → run tools/run_mugenforge_smoke.py → '
            'read docs/MUGENFORGE_HANDOFF_v7_5.md → use the generated module catalog and UI inventory before the next edit.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Maintenance Core')
        self._set_text(
            self.output,
            'Maintenance Core v7.5 is ready. Open or create a project folder, then run One-Click Maintenance Pass for a context-safe handoff bundle.',
        )

    def _maintenance_core_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Maintenance Core', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _maintenance_core_show_result(self, result, status: str):
        self._set_text(self.output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select()
        self._reload_project()

    def maintenance_core_one_click_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.run_maintenance_core_pass(root), 'Maintenance Core pass complete')
            messagebox.showinfo('Maintenance Core complete', 'Maintenance Core pass completed. Review maintenance_core/MAINTAINER_START_HERE.md and docs/MUGENFORGE_HANDOFF_v7_5.md.')
        except Exception as exc:
            messagebox.showerror('Maintenance Core failed', str(exc))

    def maintenance_core_dashboard_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_maintainer_dashboard(root), 'Maintenance dashboard written')
        except Exception as exc:
            messagebox.showerror('Maintenance dashboard failed', str(exc))

    def maintenance_core_catalog_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_module_api_catalog(root), 'Module/API catalog written')
        except Exception as exc:
            messagebox.showerror('Module/API catalog failed', str(exc))

    def maintenance_core_ui_inventory_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_ui_tab_inventory(root), 'UI tab inventory written')
        except Exception as exc:
            messagebox.showerror('UI tab inventory failed', str(exc))

    def maintenance_core_lineage_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_release_lineage(root), 'Release lineage written')
        except Exception as exc:
            messagebox.showerror('Release lineage failed', str(exc))

    def maintenance_core_claims_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_honesty_claims_audit(root), 'Honesty claims audit written')
        except Exception as exc:
            messagebox.showerror('Honesty claims audit failed', str(exc))

    def maintenance_core_scripts_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_regression_test_scripts(root), 'Maintenance scripts written')
        except Exception as exc:
            messagebox.showerror('Maintenance scripts failed', str(exc))

    def maintenance_core_backlog_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_maintenance_backlog(root), 'Maintenance backlog written')
        except Exception as exc:
            messagebox.showerror('Maintenance backlog failed', str(exc))

    def maintenance_core_handoff_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.write_handoff_for_next_chat(root), 'Maintenance handoff written')
        except Exception as exc:
            messagebox.showerror('Maintenance handoff failed', str(exc))

    def maintenance_core_bundle_ui(self):
        root = self._maintenance_core_root()
        if not root:
            return
        try:
            self._maintenance_core_show_result(maint_core.build_maintenance_bundle(root), 'Maintenance bundle written')
        except Exception as exc:
            messagebox.showerror('Maintenance bundle failed', str(exc))
