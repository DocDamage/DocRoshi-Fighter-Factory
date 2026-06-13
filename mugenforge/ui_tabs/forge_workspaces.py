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
from ..forge_polish import (
    FORGE_POLISH_VERSION,
    apply_snd_cue_sheet,
    build_forge_polish_bundle,
    build_sprite_backed_timeline_preview,
    build_state_graph_canvas_model as polish_build_state_graph_canvas_model,
    export_editable_sound_cue_sheet,
    import_template_pack as polish_import_template_pack,
    list_backup_rows,
    restore_backup_file,
    run_forge_polish_pass,
    validate_all_edit_sheets,
    validate_template_architecture,
    write_backup_history,
    write_beginner_dashboard_41,
    write_stage_source_art_preview,
    write_state_graph_canvas_artifacts,
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


class ForgePolishTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self.forge_polish_preview_photo = None
        self._build()
        self._publish(
            '_forge_polish_root',
            '_forge_polish_show_result',
            '_forge_polish_load_preview_image',
            '_forge_polish_draw_graph',
            '_forge_polish_refresh_backups',
            'forge_polish_one_click_ui',
            'forge_polish_dashboard_ui',
            'forge_polish_validate_sheets_ui',
            'forge_polish_export_sound_sheet_ui',
            'forge_polish_apply_sound_sheet_ui',
            'forge_polish_timeline_preview_ui',
            'forge_polish_state_graph_ui',
            'forge_polish_validate_template_ui',
            'forge_polish_import_template_ui',
            'forge_polish_stage_preview_ui',
            'forge_polish_backup_history_ui',
            'forge_polish_restore_backup_ui',
            'forge_polish_bundle_ui',
        )

    def _build(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame
        self.app.forge_polish_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=3)
        frame.rowconfigure(3, weight=2)

        header = ttk.LabelFrame(frame, text=f'Forge Polish v{FORGE_POLISH_VERSION} — v4.1 polish/stability cockpit', padding=(8, 6))
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Use this tab after Forge Beyond. It adds safer sheet validation previews, sprite-backed timeline contact sheets, an in-app state graph canvas, editable sound cue sheets, data-only template import, stage source-art preview, and backup history/restore helpers.'
        ), wraplength=1180, justify='left').grid(row=0, column=0, sticky='ew')

        buttons = ttk.Frame(frame, padding=(6, 0))
        buttons.grid(row=1, column=0, sticky='ew')
        actions = [
            ('One-Click Polish Pass', self.forge_polish_one_click_ui),
            ('Beginner Dashboard', self.forge_polish_dashboard_ui),
            ('Validate Command/AIR Sheets', self.forge_polish_validate_sheets_ui),
            ('Export Sound Cue Sheet', self.forge_polish_export_sound_sheet_ui),
            ('Apply Sound Cue Sheet', self.forge_polish_apply_sound_sheet_ui),
            ('Timeline Sprite Preview', self.forge_polish_timeline_preview_ui),
            ('Draw State Graph Canvas', self.forge_polish_state_graph_ui),
            ('Validate Templates', self.forge_polish_validate_template_ui),
            ('Import Template Pack', self.forge_polish_import_template_ui),
            ('Stage Source Preview', self.forge_polish_stage_preview_ui),
            ('Backup History', self.forge_polish_backup_history_ui),
            ('Restore Selected Backup', self.forge_polish_restore_backup_ui),
            ('Bundle Polish Reports', self.forge_polish_bundle_ui),
        ]
        for idx, (label, command) in enumerate(actions):
            ttk.Button(buttons, text=label, command=command).grid(row=idx // 5, column=idx % 5, padx=3, pady=2, sticky='ew')
        for col in range(5):
            buttons.columnconfigure(col, weight=1)

        body = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
        body.grid(row=2, column=0, sticky='nsew', padx=6, pady=6)

        graph_frame = ttk.LabelFrame(body, text='State Graph / Preview Canvas', padding=(4, 4))
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.rowconfigure(0, weight=1)
        self.forge_polish_canvas = tk.Canvas(graph_frame, bg='white', height=360, scrollregion=(0, 0, 1400, 900))
        self.app.forge_polish_canvas = self.forge_polish_canvas
        self.forge_polish_canvas.grid(row=0, column=0, sticky='nsew')
        graph_y = ttk.Scrollbar(graph_frame, orient='vertical', command=self.forge_polish_canvas.yview)
        graph_x = ttk.Scrollbar(graph_frame, orient='horizontal', command=self.forge_polish_canvas.xview)
        self.forge_polish_canvas.configure(yscrollcommand=graph_y.set, xscrollcommand=graph_x.set)
        graph_y.grid(row=0, column=1, sticky='ns')
        graph_x.grid(row=1, column=0, sticky='ew')
        body.add(graph_frame, weight=3)

        backup_frame = ttk.LabelFrame(body, text='Backup History', padding=(4, 4))
        backup_frame.columnconfigure(0, weight=1)
        backup_frame.rowconfigure(0, weight=1)
        self.forge_polish_backup_tree = ttk.Treeview(backup_frame, columns=('kind', 'modified', 'target', 'path'), show='headings', height=12)
        self.app.forge_polish_backup_tree = self.forge_polish_backup_tree
        for col, text, width in (('kind', 'Kind', 115), ('modified', 'Modified', 150), ('target', 'Restore target', 180), ('path', 'Backup path', 320)):
            self.forge_polish_backup_tree.heading(col, text=text)
            self.forge_polish_backup_tree.column(col, width=width, anchor='w')
        self.forge_polish_backup_tree.grid(row=0, column=0, sticky='nsew')
        backup_y = ttk.Scrollbar(backup_frame, orient='vertical', command=self.forge_polish_backup_tree.yview)
        self.forge_polish_backup_tree.configure(yscrollcommand=backup_y.set)
        backup_y.grid(row=0, column=1, sticky='ns')
        body.add(backup_frame, weight=2)

        self.forge_polish_output = tk.Text(frame, wrap='word', font=('Consolas', 10), state='disabled', height=12)
        self.app.forge_polish_output = self.forge_polish_output
        self.forge_polish_output.grid(row=3, column=0, sticky='nsew', padx=6, pady=(0, 6))
        self.app.forge_polish_preview_photo = self.forge_polish_preview_photo
        self.notebook.add(frame, text='Forge Polish')
        self._set_text(self.forge_polish_output, 'Forge Polish v4.1 is ready. Open a project, then run One-Click Polish Pass or validate sheets before applying CSV changes.')

    def _forge_polish_root(self):
        if not self.app.project_root:
            messagebox.showwarning('No project open', 'Open or create a character/stage project first.')
            return None
        return self.app.project_root

    def _forge_polish_show_result(self, result, status: str):
        self._set_text(self.forge_polish_output, result.to_text() if hasattr(result, 'to_text') else str(result))
        self._select(self.frame)
        self._set_status(status)

    def _forge_polish_load_preview_image(self, path: Path):
        canvas = self.forge_polish_canvas
        canvas.delete('all')
        if not path.exists():
            canvas.create_text(20, 20, anchor='nw', text=f'Preview not found:\n{path}')
            return
        try:
            from PIL import Image, ImageTk  # type: ignore
            img = Image.open(path)
            img.thumbnail((1150, 520))
            self.forge_polish_preview_photo = ImageTk.PhotoImage(img)
            self.app.forge_polish_preview_photo = self.forge_polish_preview_photo
            canvas.create_image(10, 10, anchor='nw', image=self.forge_polish_preview_photo)
            canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1200, 600))
        except Exception:
            try:
                self.forge_polish_preview_photo = tk.PhotoImage(file=str(path))
                self.app.forge_polish_preview_photo = self.forge_polish_preview_photo
                canvas.create_image(10, 10, anchor='nw', image=self.forge_polish_preview_photo)
                canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1200, 600))
            except Exception as exc:
                canvas.create_text(20, 20, anchor='nw', text=f'Could not load preview image:\n{path}\n{exc}')

    def _forge_polish_draw_graph(self):
        root = self._forge_polish_root()
        if not root:
            return
        model = polish_build_state_graph_canvas_model(root)
        canvas = self.forge_polish_canvas
        canvas.delete('all')
        nodes = {int(n.get('state')): n for n in model.get('states', []) if str(n.get('state', '')).lstrip('-').isdigit()}
        for edge in model.get('visible_edges', []):
            try:
                src = nodes[int(edge.get('source'))]
                dst = nodes[int(edge.get('target'))]
            except Exception:
                continue
            x1, y1 = int(src.get('x', 0)) + 55, int(src.get('y', 0)) + 22
            x2, y2 = int(dst.get('x', 0)) + 55, int(dst.get('y', 0)) + 22
            canvas.create_line(x1, y1, x2, y2, arrow='last')
        for state, node in nodes.items():
            x, y = int(node.get('x', 0)), int(node.get('y', 0))
            missing = any(e.get('missing') and str(e.get('target')) == str(state) for e in model.get('edges', []))
            fill = '#fff3f3' if missing else '#f7fbff' if int(node.get('outgoing', 0)) else '#f8f8f8'
            canvas.create_rectangle(x, y, x + 118, y + 50, fill=fill, outline='#555')
            title = f"State {state}"
            detail = f"anim {node.get('anim','')}  out {node.get('outgoing',0)}"
            canvas.create_text(x + 6, y + 8, anchor='nw', text=title, font=('Consolas', 10, 'bold'))
            canvas.create_text(x + 6, y + 28, anchor='nw', text=detail, font=('Consolas', 8))
        summary = f"States: {model.get('total_states', 0)}   ChangeState edges: {model.get('total_edges', 0)}"
        canvas.create_text(12, 12, anchor='nw', text=summary, font=('Consolas', 11, 'bold'))
        canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 1400, 900))

    def _forge_polish_refresh_backups(self):
        root = self._forge_polish_root()
        if not root:
            return
        self.forge_polish_backup_tree.delete(*self.forge_polish_backup_tree.get_children())
        for row in list_backup_rows(root)[:1000]:
            self.forge_polish_backup_tree.insert('', 'end', values=(row.get('kind', ''), row.get('modified', ''), row.get('restore_hint', ''), row.get('path', '')))

    def forge_polish_one_click_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = run_forge_polish_pass(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish v4.1 pass complete')
            self._forge_polish_draw_graph()
            self._forge_polish_refresh_backups()
            messagebox.showinfo('Forge Polish complete', 'v4.1 polish pass completed. Open forge_polish/FORGE_POLISH_START_HERE.md to start.')
        except Exception as exc:
            messagebox.showerror('Forge Polish failed', str(exc))

    def forge_polish_dashboard_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = write_beginner_dashboard_41(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish beginner dashboard written')
        except Exception as exc:
            messagebox.showerror('Dashboard failed', str(exc))

    def forge_polish_validate_sheets_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = validate_all_edit_sheets(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish sheet validation complete')
        except Exception as exc:
            messagebox.showerror('Sheet validation failed', str(exc))

    def forge_polish_export_sound_sheet_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = export_editable_sound_cue_sheet(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish sound cue sheet exported')
        except Exception as exc:
            messagebox.showerror('Sound cue export failed', str(exc))

    def forge_polish_apply_sound_sheet_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        default = root / 'forge_polish' / 'sheets' / 'sound_cue_apply_sheet.csv'
        path = filedialog.askopenfilename(title='Choose sound cue sheet', initialdir=str(default.parent if default.parent.exists() else root), initialfile=default.name, filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if not path:
            return
        if not messagebox.askyesno('Apply sound cue sheet', 'Apply enabled sound cue rows now? A backup will be written before text-code changes.'):
            return
        try:
            result = apply_snd_cue_sheet(root, Path(path))
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish sound cue sheet applied')
            self._forge_polish_refresh_backups()
        except Exception as exc:
            messagebox.showerror('Sound cue apply failed', str(exc))

    def forge_polish_timeline_preview_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        txt = simpledialog.askstring('Timeline action', 'Optional AIR action number. Leave blank for first actions:', initialvalue='')
        action = int(txt) if txt and txt.strip().lstrip('-').isdigit() else None
        try:
            result = build_sprite_backed_timeline_preview(root, action_number=action)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish timeline sprite preview written')
            png = root / 'forge_polish' / 'timeline_preview' / (f'timeline_action_{action}.png' if action is not None else 'timeline_contact_sheet.png')
            self._forge_polish_load_preview_image(png)
        except Exception as exc:
            messagebox.showerror('Timeline preview failed', str(exc))

    def forge_polish_state_graph_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = write_state_graph_canvas_artifacts(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish state graph model written')
            self._forge_polish_draw_graph()
        except Exception as exc:
            messagebox.showerror('State graph failed', str(exc))

    def forge_polish_validate_template_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = validate_template_architecture(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish template validation complete')
        except Exception as exc:
            messagebox.showerror('Template validation failed', str(exc))

    def forge_polish_import_template_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        use_folder = messagebox.askyesno('Template import source', 'Import a folder? Choose No for ZIP/file import.')
        source = filedialog.askdirectory(title='Choose template folder') if use_folder else filedialog.askopenfilename(title='Choose template ZIP/file', filetypes=[('Template archives/data', '*.zip *.json *.md *.txt *.csv'), ('All files', '*.*')])
        if not source:
            return
        try:
            result = polish_import_template_pack(root, Path(source))
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish template import complete')
        except Exception as exc:
            messagebox.showerror('Template import failed', str(exc))

    def forge_polish_stage_preview_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        image = None
        if messagebox.askyesno('Stage preview image', 'Choose a specific source image? Choose No to auto-detect.'):
            chosen = filedialog.askopenfilename(title='Choose stage/source image', filetypes=[('Images', '*.png *.pcx *.bmp *.gif *.jpg *.jpeg *.webp'), ('All files', '*.*')])
            if chosen:
                image = Path(chosen)
        try:
            result = write_stage_source_art_preview(root, image_path=image)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish stage preview written')
            self._forge_polish_load_preview_image(root / 'forge_polish' / 'stage_preview' / 'stage_source_preview.png')
        except Exception as exc:
            messagebox.showerror('Stage preview failed', str(exc))

    def forge_polish_backup_history_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = write_backup_history(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish backup history refreshed')
            self._forge_polish_refresh_backups()
        except Exception as exc:
            messagebox.showerror('Backup history failed', str(exc))

    def forge_polish_restore_backup_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        sel = self.forge_polish_backup_tree.selection()
        if not sel:
            self._forge_polish_refresh_backups()
            messagebox.showinfo('Restore backup', 'Select a backup row first. The list has been refreshed.')
            return
        values = self.forge_polish_backup_tree.item(sel[0], 'values')
        if len(values) < 4:
            return
        backup_rel = values[3]
        suggested = values[2]
        target = simpledialog.askstring('Restore target', 'Project-relative file path to restore to:', initialvalue=suggested)
        if not target:
            return
        if not messagebox.askyesno('Confirm restore', f'Restore backup:\n{backup_rel}\n\nTo:\n{target}\n\nA pre-restore guard copy will be created if the target exists.'):
            return
        try:
            result = restore_backup_file(root, backup_rel, target)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish backup restore complete')
            self._forge_polish_refresh_backups()
        except Exception as exc:
            messagebox.showerror('Backup restore failed', str(exc))

    def forge_polish_bundle_ui(self):
        root = self._forge_polish_root()
        if not root:
            return
        try:
            result = build_forge_polish_bundle(root)
            self._reload_project()
            self._forge_polish_show_result(result, 'Forge Polish reports bundle built')
        except Exception as exc:
            messagebox.showerror('Polish bundle failed', str(exc))
