from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..sff2_bridge import (
    create_sff2_source_pack_zip,
    export_current_sff1_to_sff2_source,
    inspect_sprmake2_def,
    run_sprmake2,
    write_sff2_bridge_guide,
    write_sprmake2_bridge_project,
)
from .base import AppBackedTab


class Sff2BridgeTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self._publish(
            '_sff2_bridge_root',
            '_sff2_bridge_show_result',
            'sff2_bridge_choose_images_ui',
            'sff2_bridge_choose_exe_ui',
            'sff2_bridge_guide_ui',
            'sff2_bridge_write_project_ui',
            'sff2_bridge_export_current_ui',
            'sff2_bridge_inspect_ui',
            'sff2_bridge_zip_ui',
            'sff2_bridge_run_sprmake_ui',
        )

    def _build(self):
        bridge = ttk.Frame(self.notebook)
        self.frame = bridge
        self.app.sff2_bridge_frame = bridge
        bridge.columnconfigure(1, weight=1)
        bridge.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(bridge, text='SFF2 Bridge: no-code Sprmake2 source project builder', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'This tab prepares a clean SFF v2 source project from normal sprite images. It writes the Sprmake2 DEF, manifest, CSV, BAT, and guide files so a non-coder can build through an external sprmake2.exe without hand-writing the source table. '
            'It does not pretend to be full arbitrary SFF v2 binary mutation; it is a safer source-project bridge.'
        )
        ttk.Label(header, text=intro, wraplength=1140, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(bridge, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        self.sff2_image_folder_var = tk.StringVar(value='')
        self.sff2_exe_var = tk.StringVar(value='')
        self.sff2_output_var = tk.StringVar(value='')
        self.sff2_axis_var = tk.StringVar(value='feet')
        self.sff2_compress_var = tk.StringVar(value='rle8')
        self.sff2_usepal_var = tk.StringVar(value='-1')
        self.app.sff2_image_folder_var = self.sff2_image_folder_var
        self.app.sff2_exe_var = self.sff2_exe_var
        self.app.sff2_output_var = self.sff2_output_var
        self.app.sff2_axis_var = self.sff2_axis_var
        self.app.sff2_compress_var = self.sff2_compress_var
        self.app.sff2_usepal_var = self.sff2_usepal_var

        source = ttk.LabelFrame(left, text='Source sprites', padding=(6, 6))
        source.grid(row=0, column=0, sticky='ew')
        source.columnconfigure(1, weight=1)
        ttk.Button(source, text='Choose Image Folder', command=self.sff2_bridge_choose_images_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Entry(source, textvariable=self.sff2_image_folder_var, width=42).grid(row=0, column=1, sticky='ew', padx=(4, 0), pady=2)
        ttk.Label(source, text='Output SFF').grid(row=1, column=0, sticky='e', pady=2)
        ttk.Entry(source, textvariable=self.sff2_output_var, width=26).grid(row=1, column=1, sticky='ew', padx=(4, 0), pady=2)
        ttk.Label(source, text='Axis mode').grid(row=2, column=0, sticky='e', pady=2)
        ttk.Combobox(source, textvariable=self.sff2_axis_var, values=('feet', 'center', 'top-left'), width=12, state='readonly').grid(row=2, column=1, sticky='w', padx=(4, 0), pady=2)
        ttk.Label(source, text='8-bit compression').grid(row=3, column=0, sticky='e', pady=2)
        ttk.Combobox(source, textvariable=self.sff2_compress_var, values=('rle8', 'lz5', 'none'), width=12, state='readonly').grid(row=3, column=1, sticky='w', padx=(4, 0), pady=2)
        ttk.Label(source, text='usepal').grid(row=4, column=0, sticky='e', pady=2)
        ttk.Entry(source, textvariable=self.sff2_usepal_var, width=12).grid(row=4, column=1, sticky='w', padx=(4, 0), pady=2)

        actions = ttk.LabelFrame(left, text='Beginner actions', padding=(6, 6))
        actions.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(actions, text='Write Beginner SFF2 Guide', command=self.sff2_bridge_guide_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Write Sprmake2 DEF + BAT', command=self.sff2_bridge_write_project_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Inspect Sprmake2 DEF', command=self.sff2_bridge_inspect_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Build SFF2 Source Pack ZIP', command=self.sff2_bridge_zip_ui).grid(row=3, column=0, sticky='ew', pady=2)

        convert = ttk.LabelFrame(left, text='Current project helpers', padding=(6, 6))
        convert.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(convert, text='Export Current SFF v1 -> SFF2 Source', command=self.sff2_bridge_export_current_ui).grid(row=0, column=0, sticky='ew', pady=2)

        runbox = ttk.LabelFrame(left, text='Optional external Sprmake2 runner', padding=(6, 6))
        runbox.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        runbox.columnconfigure(1, weight=1)
        ttk.Button(runbox, text='Choose sprmake2.exe', command=self.sff2_bridge_choose_exe_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Entry(runbox, textvariable=self.sff2_exe_var, width=42).grid(row=0, column=1, sticky='ew', padx=(4, 0), pady=2)
        ttk.Button(runbox, text='Run Sprmake2', command=self.sff2_bridge_run_sprmake_ui).grid(row=1, column=0, columnspan=2, sticky='ew', pady=2)

        self.sff2_bridge_note = tk.Text(left, wrap='word', width=50, height=10, font=('Consolas', 9), state='disabled')
        self.app.sff2_bridge_note = self.sff2_bridge_note
        self.sff2_bridge_note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self._set_text(
            self.sff2_bridge_note,
            'Best beginner route: name sprites like g200_i0.png -> choose image folder -> write Sprmake2 DEF + BAT -> inspect the DEF -> run the BAT with your own sprmake2.exe -> update the character DEF sprite reference.',
        )

        right = ttk.Frame(bridge)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.sff2_bridge_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.sff2_bridge_output = self.sff2_bridge_output
        y = ttk.Scrollbar(right, orient='vertical', command=self.sff2_bridge_output.yview)
        x = ttk.Scrollbar(right, orient='horizontal', command=self.sff2_bridge_output.xview)
        self.sff2_bridge_output.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.sff2_bridge_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(bridge, text='SFF2 Bridge')
        self._set_text(
            self.sff2_bridge_output,
            'Open/create a character folder, then use this tab to generate a Sprmake2 source project. This is source-based SFF2 support, not arbitrary SFF2 binary patching.',
        )

    def _sff2_bridge_root(self):
        root = self.app._plus_get_project_root()
        if root and not self.sff2_output_var.get().strip():
            self.sff2_output_var.set(f'{Path(root).name}.sff')
        return root

    def _sff2_bridge_show_result(self, result, label='SFF2 Bridge'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self._set_text(self.sff2_bridge_output, text)
        self._select(self.frame)
        self._set_status(label)

    def sff2_bridge_choose_images_ui(self):
        folder = filedialog.askdirectory(title='Choose folder of sprite images named like g200_i0.png')
        if folder:
            self.sff2_image_folder_var.set(folder)

    def sff2_bridge_choose_exe_ui(self):
        path = filedialog.askopenfilename(title='Choose sprmake2.exe', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if path:
            self.sff2_exe_var.set(path)

    def sff2_bridge_guide_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        try:
            result = write_sff2_bridge_guide(root)
            self._reload_project()
            self._sff2_bridge_show_result(result, 'SFF2 bridge guide written')
        except Exception as exc:
            messagebox.showerror('SFF2 bridge guide failed', str(exc))

    def sff2_bridge_write_project_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        folder = self.sff2_image_folder_var.get().strip()
        if not folder:
            folder = filedialog.askdirectory(title='Choose folder of sprite images named like g200_i0.png')
            if folder:
                self.sff2_image_folder_var.set(folder)
        if not folder:
            return
        try:
            result = write_sprmake2_bridge_project(
                root, Path(folder),
                output_sff_name=self.sff2_output_var.get().strip() or f'{Path(root).name}.sff',
                compress8=self.sff2_compress_var.get().strip() or 'rle8',
                usepal=self.sff2_usepal_var.get().strip() or '-1',
                axis_mode=self.sff2_axis_var.get().strip() or 'feet',
            )
            self._reload_project()
            self._sff2_bridge_show_result(result, 'SFF2 bridge project written')
        except Exception as exc:
            messagebox.showerror('SFF2 bridge project failed', str(exc))

    def sff2_bridge_export_current_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        sff = self.app._plus_find_sff_path() if hasattr(self.app, '_plus_find_sff_path') else None
        if not sff:
            chosen = filedialog.askopenfilename(title='Choose SFF v1 file to export', filetypes=[('SFF files', '*.sff'), ('All files', '*.*')])
            if not chosen:
                return
            sff = Path(chosen)
        try:
            result = export_current_sff1_to_sff2_source(root, sff, axis_mode=self.sff2_axis_var.get().strip() or 'feet')
            self._reload_project()
            self._sff2_bridge_show_result(result, 'Current SFF exported to SFF2 source')
        except Exception as exc:
            messagebox.showerror('Export current SFF failed', str(exc))

    def sff2_bridge_inspect_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        default_def = Path(root) / 'sff2_bridge' / 'mugenforge_sff2_sprmake.def'
        path = default_def
        if not path.exists():
            chosen = filedialog.askopenfilename(title='Choose Sprmake2 DEF to inspect', initialdir=str(Path(root) / 'sff2_bridge'), filetypes=[('DEF files', '*.def'), ('All files', '*.*')])
            if not chosen:
                return
            path = Path(chosen)
        try:
            text = inspect_sprmake2_def(path)
            self._set_text(self.sff2_bridge_output, text)
            self._select(self.frame)
            self._set_status('Sprmake2 DEF inspected')
        except Exception as exc:
            messagebox.showerror('Inspect Sprmake2 DEF failed', str(exc))

    def sff2_bridge_zip_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        try:
            result = create_sff2_source_pack_zip(root)
            self._reload_project()
            self._sff2_bridge_show_result(result, 'SFF2 source pack ZIP built')
        except Exception as exc:
            messagebox.showerror('SFF2 source pack failed', str(exc))

    def sff2_bridge_run_sprmake_ui(self):
        root = self._sff2_bridge_root()
        if not root:
            return
        exe = self.sff2_exe_var.get().strip()
        if not exe:
            exe = filedialog.askopenfilename(title='Choose sprmake2.exe', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
            if exe:
                self.sff2_exe_var.set(exe)
        if not exe:
            return
        if not messagebox.askyesno('Run external Sprmake2', 'This runs an external executable you selected. Continue?'):
            return
        try:
            result = run_sprmake2(root, Path(exe), output_sff_name=self.sff2_output_var.get().strip())
            self._reload_project()
            self._sff2_bridge_show_result(result, 'Sprmake2 run finished')
        except Exception as exc:
            messagebox.showerror('Run Sprmake2 failed', str(exc))
