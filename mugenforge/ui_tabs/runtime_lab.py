from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .. import runtime_lab as rt_lab
from .base import AppBackedTab


class RuntimeLabTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.runtime_lab_frame = self.frame
        self._publish(
            '_runtime_lab_root',
            '_runtime_lab_show_result',
            'runtime_lab_one_click_ui',
            'runtime_lab_config_ui',
            'runtime_lab_profiles_ui',
            'runtime_lab_launchers_ui',
            'runtime_lab_debug_overlay_ui',
            'runtime_lab_test_plan_ui',
            'runtime_lab_parse_logs_ui',
            'runtime_lab_evidence_ui',
            'runtime_lab_regression_ui',
            'runtime_lab_readiness_ui',
            'runtime_lab_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Runtime Lab v{rt_lab.RUNTIME_LAB_VERSION} — launch harnesses, playtest evidence, log parsing, and release readiness', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        intro = (
            'Runtime Lab closes the external-playtest gap. It does not simulate M.U.G.E.N/IKEMEN; it writes editable launchers, '
            'installs an optional DisplayToClipboard overlay, generates runtime test scenarios, parses logs, indexes evidence, '
            'and creates a release-readiness report from real engine-test artifacts.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        buttons = [
            ('One-Click Runtime Lab Pass', self.runtime_lab_one_click_ui),
            ('Runtime Config Template', self.runtime_lab_config_ui),
            ('Export Launch Profiles', self.runtime_lab_profiles_ui),
            ('Build Launch Scripts', self.runtime_lab_launchers_ui),
            ('Install Debug Overlay', self.runtime_lab_debug_overlay_ui),
            ('Runtime Test Plan', self.runtime_lab_test_plan_ui),
            ('Parse Runtime Logs', self.runtime_lab_parse_logs_ui),
            ('Evidence Index', self.runtime_lab_evidence_ui),
            ('Regression Checklist', self.runtime_lab_regression_ui),
            ('Readiness Report', self.runtime_lab_readiness_ui),
            ('Bundle Runtime Lab', self.runtime_lab_bundle_ui),
        ]
        for idx, (label, cmd) in enumerate(buttons):
            ttk.Button(header, text=label, command=cmd).grid(row=1 + idx // 5, column=idx % 5, sticky='ew', padx=3, pady=2)
            header.columnconfigure(idx % 5, weight=1)

        body = ttk.LabelFrame(frame, text='Recommended runtime loop', padding=(8, 6))
        body.grid(row=1, column=0, sticky='ew', padx=6, pady=(0, 6))
        workflow = (
            'One-Click Runtime Lab Pass → edit runtime_config.json → review launcher scripts → run the external engine → '
            'save logs/screenshots/video notes → Parse Runtime Logs → Evidence Index → Readiness Report. '
            'Readiness is a release aid, not engine-authoritative proof.'
        )
        ttk.Label(body, text=workflow, wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.runtime_lab_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.runtime_lab_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Runtime Lab')
        self._set_text(
            self.app.runtime_lab_output,
            f'Runtime Lab v{rt_lab.RUNTIME_LAB_VERSION} is ready. Generate configs and launchers, run the external engine, then feed logs/evidence back into MugenForge.',
        )

    def _runtime_lab_root(self):
        if not self.app.project_root:
            messagebox.showinfo('Runtime Lab', 'Open or create a project folder first.')
            return None
        return Path(self.app.project_root)

    def _runtime_lab_show_result(self, result, status: str):
        self._set_text(self.app.runtime_lab_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(self.app.runtime_lab_frame)

    def _run(self, func, status: str, error_title: str):
        root = self._runtime_lab_root()
        if not root:
            return
        try:
            result = func(root)
            self._reload_project()
            self._runtime_lab_show_result(result, status)
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))

    def runtime_lab_one_click_ui(self):
        root = self._runtime_lab_root()
        if not root:
            return
        try:
            result = rt_lab.run_runtime_lab_pass(root)
            self._reload_project()
            self._runtime_lab_show_result(result, 'Runtime Lab pass complete')
            messagebox.showinfo('Runtime Lab complete', 'Runtime Lab pass completed. Review runtime_lab/RUNTIME_LAB_START_HERE.md, configure your engine path, then run external playtests.')
        except Exception as exc:
            messagebox.showerror('Runtime Lab failed', str(exc))

    def runtime_lab_config_ui(self):
        self._run(rt_lab.write_runtime_config_template, 'Runtime config template written', 'Runtime config failed')

    def runtime_lab_profiles_ui(self):
        self._run(rt_lab.export_runtime_launch_profiles, 'Runtime launch profiles exported', 'Runtime profiles failed')

    def runtime_lab_launchers_ui(self):
        self._run(rt_lab.build_runtime_launch_scripts, 'Runtime launch scripts built', 'Runtime launchers failed')

    def runtime_lab_debug_overlay_ui(self):
        if messagebox.askyesno('Install Runtime Debug Overlay', 'Append a State -2 DisplayToClipboard helper to the project CNS/ST file? A backup is written first.'):
            self._run(rt_lab.install_runtime_debug_overlay, 'Runtime debug overlay installed', 'Runtime debug overlay failed')

    def runtime_lab_test_plan_ui(self):
        self._run(rt_lab.write_runtime_test_plan, 'Runtime test plan written', 'Runtime test plan failed')

    def runtime_lab_parse_logs_ui(self):
        self._run(rt_lab.parse_runtime_logs, 'Runtime logs parsed', 'Runtime log parse failed')

    def runtime_lab_evidence_ui(self):
        self._run(rt_lab.build_runtime_evidence_index, 'Runtime evidence indexed', 'Runtime evidence index failed')

    def runtime_lab_regression_ui(self):
        self._run(rt_lab.write_runtime_regression_checklist, 'Runtime regression checklist written', 'Runtime regression checklist failed')

    def runtime_lab_readiness_ui(self):
        self._run(rt_lab.write_runtime_readiness_report, 'Runtime readiness report written', 'Runtime readiness failed')

    def runtime_lab_bundle_ui(self):
        self._run(rt_lab.build_runtime_lab_bundle, 'Runtime Lab bundle written', 'Runtime Lab bundle failed')
