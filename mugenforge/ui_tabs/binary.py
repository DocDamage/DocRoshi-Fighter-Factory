from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import binary_core as bc
from .. import binary_deep as bd
from .. import binary_maturity as bm
from .base import AppBackedTab


class BinaryWorkspaceTabs(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build_binary_core_tab()
        self._build_binary_deep_tab()
        self._build_binary_maturity_tab()
        self._publish(
            '_binary_core_root',
            '_binary_core_show_result',
            'binary_core_one_click_ui',
            'binary_core_dashboard_ui',
            'binary_core_safety_ui',
            'binary_core_sff2_inspect_ui',
            'binary_core_sff2_export_ui',
            'binary_core_export_axis_ui',
            'binary_core_apply_axis_ui',
            'binary_core_sff2_rebuild_pack_ui',
            'binary_core_sff2_png_copy_ui',
            'binary_core_export_snd_ui',
            'binary_core_apply_snd_ui',
            'binary_core_snd_waveform_ui',
            'binary_core_roundtrip_ui',
            'binary_core_bundle_ui',
            '_binary_deep_root',
            '_binary_deep_show_result',
            'binary_deep_one_click_ui',
            'binary_deep_dashboard_ui',
            'binary_deep_sff2_inspect_ui',
            'binary_deep_sff2_export_ui',
            'binary_deep_export_mutation_ui',
            'binary_deep_apply_mutation_ui',
            'binary_deep_build_native_sff2_ui',
            'binary_deep_export_snd_patch_ui',
            'binary_deep_apply_snd_patch_ui',
            'binary_deep_runtime_ui',
            'binary_deep_bundle_ui',
            '_binary_maturity_root',
            '_binary_maturity_show_result',
            'binary_maturity_one_click_ui',
            'binary_maturity_sff2_report_ui',
            'binary_maturity_export_sff2_workspace_ui',
            'binary_maturity_apply_sff2_workspace_ui',
            'binary_maturity_build_sff2_source_ui',
            'binary_maturity_export_snd_slot_ui',
            'binary_maturity_apply_snd_slot_ui',
            'binary_maturity_runtime_harness_ui',
            'binary_maturity_run_runtime_ui',
            'binary_maturity_bundle_ui',
        )

    def _project_root(self, title: str):
        if not self.app.project_root:
            messagebox.showinfo(title, 'Open or create a project folder first.')
            return None
        return self.app.project_root

    def _show_result(self, output, frame, result, status: str):
        self._set_text(output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._set_status(status)
        self._select(frame)

    def _run_action(self, root_getter, output, frame, func, status: str, error_title: str, *args):
        root = root_getter()
        if not root:
            return
        try:
            result = func(root, *args)
            self._reload_project()
            self._show_result(output, frame, result, status)
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))

    def _build_binary_core_tab(self):
        frame = ttk.Frame(self.notebook)
        self.app.binary_core_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Binary Core v{bc.BINARY_CORE_VERSION} — SFF/SND inspection, safe rebuilds, backups, and roundtrip reports', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        header.columnconfigure(1, weight=1)
        intro = (
            'This tab attacks the remaining binary gap directly. It performs native SFF/SND inspection, supported payload extraction, '
            'SFF v1 axis patching, source-based SFF2 rebuild pack generation, editable SND bank rebuilds, and safety reports. '
            'Unsupported arbitrary SFF2 mutation is refused instead of guessed.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 6))
        for col, (label, cmd) in enumerate([
            ('One-Click Binary Core Pass', self.binary_core_one_click_ui),
            ('Dashboard', self.binary_core_dashboard_ui),
            ('Safety Report', self.binary_core_safety_ui),
            ('Roundtrip Report', self.binary_core_roundtrip_ui),
            ('Bundle Reports', self.binary_core_bundle_ui),
        ]):
            ttk.Button(header, text=label, command=cmd).grid(row=1, column=col, padx=3, pady=2, sticky='ew')

        body = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self._button_panel(body, 'SFF / SFF2 Binary Tools', [
            ('SFF2 Native Inspection', self.binary_core_sff2_inspect_ui),
            ('Export Supported SFF Payloads', self.binary_core_sff2_export_ui),
            ('Export SFF Axis Sheet', self.binary_core_export_axis_ui),
            ('Apply SFF Axis Sheet', self.binary_core_apply_axis_ui),
            ('Create SFF2 Source Rebuild Pack', self.binary_core_sff2_rebuild_pack_ui),
            ('Build Experimental SFF2 PNG Copy', self.binary_core_sff2_png_copy_ui),
        ])
        self._button_panel(body, 'SND Bank Tools', [
            ('Export SND Bank Sheet', self.binary_core_export_snd_ui),
            ('Apply SND Bank Sheet', self.binary_core_apply_snd_ui),
            ('SND Waveform Preview', self.binary_core_snd_waveform_ui),
        ])

        self.app.binary_core_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.binary_core_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Binary Core')
        self._set_text(self.app.binary_core_output, 'Binary Core v5.5 is ready. Open a project, then run One-Click Binary Core Pass or inspect SFF/SND assets individually.')

    def _build_binary_deep_tab(self):
        frame = ttk.Frame(self.notebook)
        self.app.binary_deep_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Binary Deep v{bd.BINARY_DEEP_VERSION} — expanded SFF2 decoding/mutation, SND patch candidates, runtime validation', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        header.columnconfigure(1, weight=1)
        intro = (
            'Binary Deep is an experimental companion tab: broad SFF2 table discovery, PNG/PCX/zlib/raw/RLE8 recovery, diagnostic-only 5-bit/LZ-style probes, '
            'native table-backed SFF2 candidates, SFF2 mutation sheets, direct SND ID/WAV patch candidates, and runtime-log validation artifacts. '
            'It still writes warnings instead of making unproven destructive edits, and RLE5/LZ5 are not advertised as mature pixel decoders.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        for col, (label, cmd) in enumerate([
            ('One-Click Binary Deep Pass', self.binary_deep_one_click_ui),
            ('Dashboard', self.binary_deep_dashboard_ui),
            ('Runtime Validation Lab', self.binary_deep_runtime_ui),
            ('Bundle Reports', self.binary_deep_bundle_ui),
        ]):
            ttk.Button(header, text=label, command=cmd).grid(row=1, column=col, padx=3, pady=2, sticky='ew')

        body = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self._button_panel(body, 'Deep SFF2 Tools', [
            ('Deep SFF2 Inspection', self.binary_deep_sff2_inspect_ui),
            ('Export / Decode Deep SFF2 Sprites', self.binary_deep_sff2_export_ui),
            ('Export SFF2 Mutation Sheet', self.binary_deep_export_mutation_ui),
            ('Apply SFF2 Mutation Sheet', self.binary_deep_apply_mutation_ui),
            ('Build Native SFF2 From Manifest', self.binary_deep_build_native_sff2_ui),
        ])
        self._button_panel(body, 'Deep SND Tools', [
            ('Export SND Direct Patch Sheet', self.binary_deep_export_snd_patch_ui),
            ('Apply SND Direct Patch Sheet', self.binary_deep_apply_snd_patch_ui),
            ('SND Waveform Preview', self.binary_core_snd_waveform_ui),
        ])

        self.app.binary_deep_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.binary_deep_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Binary Deep')
        self._set_text(self.app.binary_deep_output, 'Binary Deep v5.5 is ready. Open a project, then run One-Click Binary Deep Pass or inspect SFF/SND assets individually.')

    def _build_binary_maturity_tab(self):
        frame = ttk.Frame(self.notebook)
        self.app.binary_maturity_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Binary Maturity v{bm.BINARY_MATURITY_VERSION} — standard SFF2, safe rebuild candidates, SND slot patches, runtime harness', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        header.columnconfigure(1, weight=1)
        intro = (
            'Binary Maturity targets the remaining v5 binary gaps with a standard SFF2 table parser, raw/RLE8/PNG decoders, '
            'payload-preserving SFF2 edit workspaces, controlled SFF2 rebuild candidates, same-or-smaller SND slot patch copies, and a runtime test harness. '
            'RLE5/LZ5 are detected and preserved/replaced when possible, but are not falsely advertised as mature pixel decoders.'
        )
        ttk.Label(header, text=intro, wraplength=1180, justify='left').grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 6))
        for col, (label, cmd) in enumerate([
            ('One-Click Binary Maturity Pass', self.binary_maturity_one_click_ui),
            ('SFF2 Maturity Report', self.binary_maturity_sff2_report_ui),
            ('Runtime Harness', self.binary_maturity_runtime_harness_ui),
            ('Run Runtime Harness', self.binary_maturity_run_runtime_ui),
            ('Bundle Reports', self.binary_maturity_bundle_ui),
        ]):
            ttk.Button(header, text=label, command=cmd).grid(row=1, column=col, padx=3, pady=2, sticky='ew')

        body = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self._button_panel(body, 'SFF2 Maturity Tools', [
            ('Export SFF2 Edit Workspace', self.binary_maturity_export_sff2_workspace_ui),
            ('Apply SFF2 Edit Workspace', self.binary_maturity_apply_sff2_workspace_ui),
            ('Build SFF2 From Source Folder', self.binary_maturity_build_sff2_source_ui),
        ])
        self._button_panel(body, 'SND Maturity Tools', [
            ('Export SND Slot Patch Sheet', self.binary_maturity_export_snd_slot_ui),
            ('Apply SND Slot Patch Sheet', self.binary_maturity_apply_snd_slot_ui),
            ('SND Waveform Preview', self.binary_core_snd_waveform_ui),
        ])

        self.app.binary_maturity_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.binary_maturity_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.notebook.add(frame, text='Binary Maturity')
        self._set_text(self.app.binary_maturity_output, 'Binary Maturity v5.5 is ready. Open a project, then run One-Click Binary Maturity Pass or use the focused SFF2/SND/runtime tools.')

    def _button_panel(self, parent, title: str, buttons):
        panel = ttk.LabelFrame(parent, text=title, padding=(6, 6))
        panel.columnconfigure(0, weight=1)
        for row, (label, cmd) in enumerate(buttons):
            ttk.Button(panel, text=label, command=cmd).grid(row=row, column=0, sticky='ew', padx=2, pady=2)
        parent.add(panel, weight=1)

    def _binary_core_root(self):
        return self._project_root('Binary Core')

    def _binary_core_show_result(self, result, status: str):
        self._show_result(self.app.binary_core_output, self.app.binary_core_frame, result, status)

    def binary_core_one_click_ui(self):
        root = self._binary_core_root()
        if not root:
            return
        try:
            result = bc.run_binary_core_pass(root)
            self._reload_project()
            self._binary_core_show_result(result, 'Binary Core v5.5 pass complete')
            messagebox.showinfo('Binary Core complete', 'v5.5 Binary Core pass completed. Open binary_core/BINARY_CORE_START_HERE.md to review next steps.')
        except Exception as exc:
            messagebox.showerror('Binary Core failed', str(exc))

    def binary_core_dashboard_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.write_binary_core_dashboard, 'Binary Core dashboard written', 'Binary Core dashboard failed')

    def binary_core_safety_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.write_binary_safety_report, 'Binary safety report written', 'Binary safety report failed')

    def binary_core_sff2_inspect_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.inspect_sff2_native, 'SFF2 native inspection complete', 'SFF2 inspection failed')

    def binary_core_sff2_export_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.export_supported_sff2_payloads, 'Supported SFF payload export complete', 'SFF payload export failed')

    def binary_core_export_axis_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.export_sff_axis_sheet, 'SFF axis sheet exported', 'SFF axis sheet export failed')

    def binary_core_apply_axis_ui(self):
        if messagebox.askyesno('Apply SFF Axis Sheet', 'Apply enabled SFF axis rows from binary_core/sff_axis_editor/sff_axis_edit_sheet.csv? This creates a patched copy; the original SFF is not overwritten.'):
            self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.apply_sff_axis_sheet, 'SFF axis sheet applied', 'SFF axis apply failed')

    def binary_core_sff2_rebuild_pack_ui(self):
        root = self._binary_core_root()
        if not root:
            return
        folder = None
        if messagebox.askyesno('SFF2 Source Rebuild Pack', 'Choose a source sprite image folder? Choose No to auto-detect source_sprites/sprites/staged_sprites.'):
            chosen = filedialog.askdirectory(title='Choose source sprite image folder')
            if chosen:
                folder = Path(chosen)
        try:
            result = bc.create_sff2_source_rebuild_pack(root, folder)
            self._reload_project()
            self._binary_core_show_result(result, 'SFF2 source rebuild pack created')
        except Exception as exc:
            messagebox.showerror('SFF2 source rebuild pack failed', str(exc))

    def binary_core_sff2_png_copy_ui(self):
        if messagebox.askyesno('Experimental SFF2 PNG Copy', 'Build the experimental MugenForge PNG-subset SFF2-style copy from the source workspace? This is for pipeline testing, not a full Sprmake2 replacement.'):
            self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.build_sff2_png_workspace_copy, 'Experimental SFF2 PNG copy built', 'Experimental SFF2 PNG copy failed')

    def binary_core_export_snd_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.export_snd_bank_sheet, 'SND bank sheet exported', 'SND bank sheet export failed')

    def binary_core_apply_snd_ui(self):
        if messagebox.askyesno('Apply SND Bank Sheet', 'Create a rebuilt SND candidate from binary_core/snd_editor/snd_bank_edit_sheet.csv? The current SND is not overwritten.'):
            self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.apply_snd_bank_sheet, 'SND bank sheet applied', 'SND bank apply failed')

    def binary_core_snd_waveform_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.write_snd_waveform_preview, 'SND waveform preview written', 'SND waveform preview failed')

    def binary_core_roundtrip_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.build_binary_roundtrip_report, 'Binary roundtrip report written', 'Binary roundtrip report failed')

    def binary_core_bundle_ui(self):
        self._run_action(self._binary_core_root, self.app.binary_core_output, self.app.binary_core_frame, bc.build_binary_core_bundle, 'Binary Core reports bundle built', 'Binary Core bundle failed')

    def _binary_deep_root(self):
        return self._project_root('Binary Deep')

    def _binary_deep_show_result(self, result, status: str):
        self._show_result(self.app.binary_deep_output, self.app.binary_deep_frame, result, status)

    def binary_deep_one_click_ui(self):
        root = self._binary_deep_root()
        if not root:
            return
        try:
            result = bd.run_binary_deep_pass(root)
            self._reload_project()
            self._binary_deep_show_result(result, 'Binary Deep v5.5 pass complete')
            messagebox.showinfo('Binary Deep complete', 'v5.5 Binary Deep pass completed. Open binary_deep/BINARY_DEEP_START_HERE.md to review outputs.')
        except Exception as exc:
            messagebox.showerror('Binary Deep failed', str(exc))

    def binary_deep_dashboard_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.write_binary_deep_dashboard, 'Binary Deep dashboard written', 'Binary Deep dashboard failed')

    def binary_deep_sff2_inspect_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.inspect_sff2_deep, 'Deep SFF2 inspection complete', 'Deep SFF2 inspection failed')

    def binary_deep_sff2_export_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.export_sff2_deep_sprites, 'Deep SFF2 export complete', 'Deep SFF2 export failed')

    def binary_deep_export_mutation_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.export_sff2_mutation_sheet, 'SFF2 mutation sheet exported', 'SFF2 mutation sheet export failed')

    def binary_deep_apply_mutation_ui(self):
        if messagebox.askyesno('Apply SFF2 Mutation Sheet', 'Apply enabled rows from binary_deep/sff2_mutation/deep_sff2_mutation_sheet.csv? This creates candidate patched/rebuilt files first.'):
            self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.apply_sff2_mutation_sheet, 'SFF2 mutation sheet applied', 'SFF2 mutation sheet apply failed')

    def binary_deep_build_native_sff2_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.build_native_sff2, 'Native SFF2 build completed', 'Native SFF2 build failed')

    def binary_deep_export_snd_patch_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.export_snd_patch_sheet, 'SND direct patch sheet exported', 'SND direct patch sheet export failed')

    def binary_deep_apply_snd_patch_ui(self):
        if messagebox.askyesno('Apply SND Direct Patch Sheet', 'Apply enabled rows from binary_deep/snd_direct_patch/snd_direct_patch_sheet.csv? This creates a patched candidate copy first.'):
            self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.apply_snd_patch_sheet, 'SND direct patch sheet applied', 'SND direct patch apply failed')

    def binary_deep_runtime_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.write_runtime_lab, 'Runtime validation lab written', 'Runtime validation lab failed')

    def binary_deep_bundle_ui(self):
        self._run_action(self._binary_deep_root, self.app.binary_deep_output, self.app.binary_deep_frame, bd.build_binary_deep_bundle, 'Binary Deep reports bundle built', 'Binary Deep bundle failed')

    def _binary_maturity_root(self):
        return self._project_root('Binary Maturity')

    def _binary_maturity_show_result(self, result, status: str):
        self._show_result(self.app.binary_maturity_output, self.app.binary_maturity_frame, result, status)

    def binary_maturity_one_click_ui(self):
        root = self._binary_maturity_root()
        if not root:
            return
        try:
            result = bm.run_binary_maturity_pass(root)
            self._reload_project()
            self._binary_maturity_show_result(result, 'Binary Maturity v5.5 pass complete')
            messagebox.showinfo('Binary Maturity complete', 'v5.5 Binary Maturity pass completed. Open binary_maturity/BINARY_MATURITY_START_HERE.md to review outputs.')
        except Exception as exc:
            messagebox.showerror('Binary Maturity failed', str(exc))

    def binary_maturity_sff2_report_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.write_sff2_maturity_report, 'SFF2 maturity report written', 'SFF2 maturity report failed')

    def binary_maturity_export_sff2_workspace_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.export_sff2_edit_workspace, 'SFF2 edit workspace exported', 'SFF2 edit workspace export failed')

    def binary_maturity_apply_sff2_workspace_ui(self):
        if messagebox.askyesno('Apply SFF2 Edit Workspace', 'Build a new SFF2 candidate from binary_maturity/sff2_edit_workspace/sff2_sprite_edit_sheet.csv? The original SFF is not overwritten.'):
            self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.apply_sff2_edit_workspace, 'SFF2 edit workspace applied', 'SFF2 edit workspace apply failed')

    def binary_maturity_build_sff2_source_ui(self):
        root = self._binary_maturity_root()
        if not root:
            return
        folder = filedialog.askdirectory(title='Choose source sprite folder, or cancel to auto-detect')
        try:
            result = bm.build_sff2_from_source_folder(root, Path(folder) if folder else None)
            self._reload_project()
            self._binary_maturity_show_result(result, 'SFF2 source build candidate written')
        except Exception as exc:
            messagebox.showerror('SFF2 source build failed', str(exc))

    def binary_maturity_export_snd_slot_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.export_snd_slot_patch_sheet, 'SND slot patch sheet exported', 'SND slot sheet export failed')

    def binary_maturity_apply_snd_slot_ui(self):
        if messagebox.askyesno('Apply SND Slot Patch Sheet', 'Apply enabled same-or-smaller WAV slot patches into a candidate SND copy? The original SND is not overwritten.'):
            self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.apply_snd_slot_patch_sheet, 'SND slot patch sheet applied', 'SND slot patch apply failed')

    def binary_maturity_runtime_harness_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.write_runtime_test_harness, 'Runtime harness written', 'Runtime harness write failed')

    def binary_maturity_run_runtime_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.run_runtime_test_harness, 'Runtime harness run complete', 'Runtime harness run failed')

    def binary_maturity_bundle_ui(self):
        self._run_action(self._binary_maturity_root, self.app.binary_maturity_output, self.app.binary_maturity_frame, bm.build_binary_maturity_bundle, 'Binary Maturity reports bundle built', 'Binary Maturity bundle failed')
