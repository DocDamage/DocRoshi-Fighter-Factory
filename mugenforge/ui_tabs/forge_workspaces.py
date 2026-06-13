from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..forge_beyond import (
    FORGE_BEYOND_VERSION,
    ImageEditSpec,
    apply_air_batch_sheet as fb_apply_air_batch_sheet,
    apply_command_sheet as fb_apply_command_sheet,
    build_forge_beyond_release_bundle as fb_build_release_bundle,
    export_air_batch_sheet as fb_export_air_batch_sheet,
    export_command_sheet as fb_export_command_sheet,
    import_archive_project,
    run_forge_beyond_pass,
    run_source_image_editor,
    write_capability_matrix as fb_write_capability_matrix,
    write_sprite_sound_cross_reference as fb_write_sprite_sound_cross_reference,
    write_stage_authoring_pack as fb_write_stage_authoring_pack,
    write_state_graph as fb_write_state_graph,
    write_template_plugin_foundation as fb_write_template_plugin_foundation,
    write_unified_project_index as fb_write_unified_project_index,
    write_variable_usage_map as fb_write_variable_usage_map,
)
from .base import AppBackedTab


class ForgeBeyondTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()
        self.app.forge_beyond_frame = self.frame
        self._publish(
            '_fb_require_project',
            '_forge_beyond_root',
            '_forge_beyond_show_result',
            'forge_beyond_one_click_ui',
            'forge_beyond_capability_ui',
            'forge_beyond_index_ui',
            'forge_beyond_state_graph_ui',
            'forge_beyond_variable_map_ui',
            'forge_beyond_cross_refs_ui',
            'forge_beyond_export_command_sheet_ui',
            'forge_beyond_apply_command_sheet_ui',
            'forge_beyond_export_air_sheet_ui',
            'forge_beyond_apply_air_sheet_ui',
            'forge_beyond_templates_ui',
            'forge_beyond_stage_pack_ui',
            'forge_beyond_import_zip_ui',
            'forge_beyond_source_image_editor_ui',
            'forge_beyond_release_bundle_ui',
        )

    def _fb_require_project(self) -> bool:
        if self.app.project_root and Path(self.app.project_root).exists():
            return True
        messagebox.showwarning('No project loaded', 'Open or create a character/stage folder first.')
        return False

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.LabelFrame(frame, text=f'Forge Beyond v{FORGE_BEYOND_VERSION} — Clean-room parity+ command center', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Use this tab to push MugenForge toward full classic M.U.G.E.N editor parity and beyond-editor no-code workflows. '
            'It creates project-wide indexes, command/AIR batch sheets, state graphs, variable maps, template/plugin foundations, stage authoring packs, and release bundles. '
            'It stays honest: no proprietary source reuse, no arbitrary SFF2 binary patch claims, and generated gameplay still requires playtesting.'
        )
        ttk.Label(header, text=intro, wraplength=1160, justify='left').grid(row=0, column=0, sticky='ew')

        buttons = ttk.Frame(frame, padding=(6, 2))
        buttons.grid(row=1, column=0, sticky='ew')
        for idx, (label, command) in enumerate((
            ('One-Click Parity+ Pass', self.forge_beyond_one_click_ui),
            ('Capability Matrix', self.forge_beyond_capability_ui),
            ('Unified Project Index', self.forge_beyond_index_ui),
            ('State Graph HTML', self.forge_beyond_state_graph_ui),
            ('Variable Usage Map', self.forge_beyond_variable_map_ui),
            ('Sprite/Sound Cross Ref', self.forge_beyond_cross_refs_ui),
        )):
            ttk.Button(buttons, text=label, command=command).grid(row=idx // 3, column=idx % 3, padx=3, pady=2, sticky='ew')
        for idx, (label, command) in enumerate((
            ('Export Command Sheet', self.forge_beyond_export_command_sheet_ui),
            ('Apply Command Sheet', self.forge_beyond_apply_command_sheet_ui),
            ('Export AIR Batch Sheet', self.forge_beyond_export_air_sheet_ui),
            ('Apply AIR Batch Sheet', self.forge_beyond_apply_air_sheet_ui),
            ('Template / Plugin Foundation', self.forge_beyond_templates_ui),
            ('Stage Authoring Pack', self.forge_beyond_stage_pack_ui),
            ('Import ZIP Project', self.forge_beyond_import_zip_ui),
            ('Source Image Editor', self.forge_beyond_source_image_editor_ui),
            ('Build Reports ZIP', self.forge_beyond_release_bundle_ui),
        )):
            ttk.Button(buttons, text=label, command=command).grid(row=2 + idx // 4, column=idx % 4, padx=3, pady=2, sticky='ew')

        self.app.forge_beyond_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.app.forge_beyond_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=6)
        self.notebook.add(frame, text='Forge Beyond')
        self._set_text(
            self.app.forge_beyond_output,
            'Forge Beyond is ready. Open a project, then run One-Click Parity+ Pass to generate the new reports, sheets, graphs, templates, and bundle.',
        )

    def _forge_beyond_root(self):
        if not self.app.project_root:
            messagebox.showwarning('No project open', 'Open or create a character/stage project first.')
            return None
        return self.app.project_root

    def _forge_beyond_show_result(self, result, status: str):
        self._set_text(self.app.forge_beyond_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._select(self.app.forge_beyond_frame)
        self._set_status(status)

    def _run(self, func, status: str, error_title: str, *args):
        root = self._forge_beyond_root()
        if not root:
            return False
        try:
            result = func(root, *args)
            self._reload_project()
            self._forge_beyond_show_result(result, status)
            return True
        except Exception as exc:
            messagebox.showerror(error_title, str(exc))
            return False

    def forge_beyond_one_click_ui(self):
        if self._run(run_forge_beyond_pass, 'Forge Beyond parity+ pass complete', 'Forge Beyond failed'):
            messagebox.showinfo('Forge Beyond complete', 'One-Click Parity+ Pass completed. Open forge_beyond/FORGE_BEYOND_DASHBOARD.md to start.')

    def forge_beyond_capability_ui(self):
        self._run(fb_write_capability_matrix, 'Forge Beyond capability matrix written', 'Capability Matrix failed')

    def forge_beyond_index_ui(self):
        self._run(fb_write_unified_project_index, 'Forge Beyond unified project index written', 'Project Index failed')

    def forge_beyond_state_graph_ui(self):
        self._run(fb_write_state_graph, 'Forge Beyond state graph written', 'State Graph failed')

    def forge_beyond_variable_map_ui(self):
        self._run(fb_write_variable_usage_map, 'Forge Beyond variable usage map written', 'Variable Map failed')

    def forge_beyond_cross_refs_ui(self):
        self._run(fb_write_sprite_sound_cross_reference, 'Forge Beyond sprite/sound cross reference written', 'Sprite/Sound Cross Reference failed')

    def forge_beyond_export_command_sheet_ui(self):
        self._run(fb_export_command_sheet, 'Forge Beyond command sheet exported', 'Command Sheet export failed')

    def forge_beyond_apply_command_sheet_ui(self):
        root = self._forge_beyond_root()
        if not root:
            return
        default = root / 'forge_beyond' / 'sheets' / 'command_editor_sheet.csv'
        path = filedialog.askopenfilename(title='Choose command_editor_sheet.csv', initialdir=str(default.parent if default.parent.exists() else root), filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if not path:
            return
        if not messagebox.askyesno('Apply command sheet', 'Apply command/time/buffer edits to CMD files with backups?'):
            return
        try:
            result = fb_apply_command_sheet(root, Path(path))
            self._reload_project()
            self._forge_beyond_show_result(result, 'Forge Beyond command sheet applied')
        except Exception as exc:
            messagebox.showerror('Command Sheet apply failed', str(exc))

    def forge_beyond_export_air_sheet_ui(self):
        self._run(fb_export_air_batch_sheet, 'Forge Beyond AIR batch sheet exported', 'AIR Batch Sheet export failed')

    def forge_beyond_apply_air_sheet_ui(self):
        root = self._forge_beyond_root()
        if not root:
            return
        default = root / 'forge_beyond' / 'sheets' / 'air_batch_editor_sheet.csv'
        path = filedialog.askopenfilename(title='Choose air_batch_editor_sheet.csv', initialdir=str(default.parent if default.parent.exists() else root), filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if not path:
            return
        if not messagebox.askyesno('Apply AIR batch sheet', 'Apply group/image/x/y/ticks/flags edits to the AIR file with a backup?'):
            return
        try:
            result = fb_apply_air_batch_sheet(root, Path(path))
            self._reload_project()
            self._forge_beyond_show_result(result, 'Forge Beyond AIR batch sheet applied')
        except Exception as exc:
            messagebox.showerror('AIR Batch Sheet apply failed', str(exc))

    def forge_beyond_templates_ui(self):
        self._run(fb_write_template_plugin_foundation, 'Forge Beyond template/plugin foundation written', 'Template foundation failed')

    def forge_beyond_stage_pack_ui(self):
        self._run(fb_write_stage_authoring_pack, 'Forge Beyond stage authoring pack written', 'Stage authoring pack failed')

    def forge_beyond_import_zip_ui(self):
        archive = filedialog.askopenfilename(title='Choose ZIP project/archive', filetypes=[('ZIP archives', '*.zip'), ('All files', '*.*')])
        if not archive:
            return
        parent = filedialog.askdirectory(title='Choose destination parent folder')
        if not parent:
            return
        default = Path(archive).stem
        name = simpledialog.askstring('Imported project name', 'Destination folder name:', initialvalue=default)
        if name is None:
            return
        try:
            result = import_archive_project(Path(archive), Path(parent), name)
            self._reload_project()
            self._forge_beyond_show_result(result, 'Forge Beyond ZIP import complete')
        except Exception as exc:
            messagebox.showerror('ZIP import failed', str(exc))

    def forge_beyond_source_image_editor_ui(self):
        source = filedialog.askdirectory(title='Choose source image folder')
        if not source:
            return
        output = filedialog.askdirectory(title='Choose output folder, or cancel to use source/forge_beyond_edited')
        scale_txt = simpledialog.askstring('Scale', 'Scale factor:', initialvalue='1.0')
        if scale_txt is None:
            return
        fmt = simpledialog.askstring('Output format', 'Output format: png, pcx, bmp, or gif', initialvalue='png') or 'png'
        trim = messagebox.askyesno('Trim transparency', 'Trim transparent borders before saving?')
        try:
            spec = ImageEditSpec(
                source_folder=Path(source),
                output_folder=Path(output) if output else None,
                trim_transparency=bool(trim),
                scale=float(scale_txt or '1.0'),
                output_format=fmt,
            )
            result = run_source_image_editor(spec)
            self._reload_project()
            self._forge_beyond_show_result(result, 'Forge Beyond source image editor complete')
        except Exception as exc:
            messagebox.showerror('Source Image Editor failed', str(exc))

    def forge_beyond_release_bundle_ui(self):
        self._run(fb_build_release_bundle, 'Forge Beyond reports ZIP built', 'Reports ZIP failed')
