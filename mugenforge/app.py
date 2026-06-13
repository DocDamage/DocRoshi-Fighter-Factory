from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path

from .ui_tabs.app_builders import AppTabBuilders
from .ui_actions.creator_os import CreatorOSActions
from .ui_actions.creator_suite import CreatorSuiteActions
from .ui_actions.air_editor import AirEditorActions
from .ui_actions.asset_workspaces import AssetWorkspaceActions
from .ui_actions.code_authoring import CodeAuthoringActions
from .ui_actions.feature_bank import FeatureBankActions
from .ui_actions.factory_max import FactoryMaxActions
from .ui_actions.factory_plus import FactoryPlusActions
from .ui_actions.factory_ultra import FactoryUltraActions
from .ui_actions.image_factory import ImageFactoryActions
from .ui_actions.palette import PaletteActions
from .ui_actions.plus_workspaces import PlusWorkspaceActions
from .ui_actions.project_core import ProjectCoreActions
from .ui_actions.quality_lab import QualityLabActions
from .ui_actions.sound_pipeline import SoundPipelineActions
from .ui_actions.sprite_pipeline import SpritePipelineActions
from .ui_actions.visual_forge import VisualForgeActions

APP_TITLE = 'MugenForge Studio 7.5 Continuity Core'

class MugenForgeApp(FeatureBankActions, CreatorOSActions, CreatorSuiteActions, AirEditorActions, AppTabBuilders, AssetWorkspaceActions, CodeAuthoringActions, FactoryMaxActions, FactoryPlusActions, FactoryUltraActions, ImageFactoryActions, PaletteActions, PlusWorkspaceActions, ProjectCoreActions, QualityLabActions, SoundPipelineActions, SpritePipelineActions, VisualForgeActions, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('1400x850')
        self.minsize(1050, 680)
        self.project_root: Path | None = None
        self.current_path: Path | None = None
        self.dirty = False
        self.air_actions = []
        self.sff_info = None
        self.sff_path: Path | None = None
        self.sff_sprite_lookup = {}
        self.current_preview_image = None
        self.snd_info = None
        self.snd_path: Path | None = None
        self.air_line_actions = []
        self.clsn_boxes = []
        self.sheet_path: Path | None = None
        self.sheet_slices = []
        self.sheet_preview_photo = None
        self.clsn_sprite_photo = None
        self.clsn_canvas_origin = (0, 0)
        self.clsn_drag = None
        self.clsn_drawn_boxes = []
        self.anim_action_var = tk.StringVar()
        self.anim_frame_var = tk.IntVar(value=0)
        self.anim_speed_var = tk.DoubleVar(value=1.0)
        self.anim_zoom_var = tk.IntVar(value=2)
        self.anim_loop_var = tk.BooleanVar(value=True)
        self.anim_after_id = None
        self.anim_is_playing = False
        self.anim_photo = None
        self.wizard_vars = {}
        self.wizard_preview_cache = None
        self.auto_preset_items = []
        self.auto_last_package = None
        self.palette_info = None
        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        paned, center = self._build_shell_layout()
        self._build_text_and_air_tabs()
        self._build_binary_and_animation_tabs()
        self._build_authoring_tabs()
        self._build_feature_tabs()
        self._select_initial_workspace()
        paned.add(center, weight=4)

    def _build_shell_layout(self):
        toolbar = ttk.Frame(self, padding=(6, 4))
        toolbar.grid(row=0, column=0, sticky='ew')
        ttk.Button(toolbar, text='Open Character Folder', command=self.open_folder).grid(row=0, column=0, padx=2)
        ttk.Button(toolbar, text='New Character', command=self.new_character).grid(row=0, column=1, padx=2)
        ttk.Button(toolbar, text='Save', command=self.save_current).grid(row=0, column=2, padx=2)
        ttk.Button(toolbar, text='Validate', command=self.validate_project).grid(row=0, column=3, padx=2)
        ttk.Button(toolbar, text='Export Audit', command=self.export_audit).grid(row=0, column=4, padx=2)
        ttk.Button(toolbar, text='Reload', command=self.reload_project).grid(row=0, column=5, padx=2)
        ttk.Button(toolbar, text='Find TODOs', command=self.find_todos).grid(row=0, column=6, padx=2)
        ttk.Button(toolbar, text='Package ZIP', command=self.package_character).grid(row=0, column=7, padx=2)
        self.status_var = tk.StringVar(value='Open a M.U.G.E.N character folder to begin.')
        ttk.Label(toolbar, textvariable=self.status_var).grid(row=0, column=8, padx=10, sticky='w')

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky='nsew')

        left = ttk.Frame(paned)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text='Project Files').grid(row=0, column=0, sticky='ew', padx=5, pady=(5, 0))
        self.tree = ttk.Treeview(left, columns=('type', 'size'), show='tree headings')
        self.tree.heading('#0', text='Name')
        self.tree.heading('type', text='Type')
        self.tree.heading('size', text='Size')
        self.tree.column('#0', width=285)
        self.tree.column('type', width=75, anchor='center')
        self.tree.column('size', width=90, anchor='e')
        self.tree.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        paned.add(left, weight=1)

        center = ttk.Frame(paned)
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(center)
        self.notebook.grid(row=0, column=0, sticky='nsew')
        return paned, center

    def _build_text_and_air_tabs(self):
        editor_frame = ttk.Frame(self.notebook)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        self.editor = tk.Text(editor_frame, wrap='none', undo=True, font=('Consolas', 11))
        yscroll = ttk.Scrollbar(editor_frame, orient='vertical', command=self.editor.yview)
        xscroll = ttk.Scrollbar(editor_frame, orient='horizontal', command=self.editor.xview)
        self.editor.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.editor.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        self.editor.bind('<<Modified>>', self.on_editor_modified)
        self.notebook.add(editor_frame, text='Editor')

        self.analysis = tk.Text(self.notebook, wrap='word', font=('Consolas', 10), state='disabled')
        self.notebook.add(self.analysis, text='Analysis')

        code_frame = ttk.Frame(self.notebook)
        code_frame.columnconfigure(0, weight=1)
        code_frame.rowconfigure(0, weight=1)
        self.code_map = ttk.Treeview(code_frame, columns=('line', 'type', 'detail'), show='tree headings')
        self.code_map.heading('#0', text='Item')
        self.code_map.heading('line', text='Line')
        self.code_map.heading('type', text='Type')
        self.code_map.heading('detail', text='Detail')
        self.code_map.column('#0', width=180)
        self.code_map.column('line', width=60, anchor='e')
        self.code_map.column('type', width=110)
        self.code_map.column('detail', width=520)
        self.code_map.grid(row=0, column=0, sticky='nsew')
        self.notebook.add(code_frame, text='Code Map')

        air_frame = ttk.Frame(self.notebook)
        air_frame.columnconfigure(1, weight=1)
        air_frame.rowconfigure(0, weight=1)
        self.action_list = tk.Listbox(air_frame, width=34, font=('Consolas', 10))
        self.action_list.grid(row=0, column=0, sticky='nsw')
        self.action_list.bind('<<ListboxSelect>>', self.on_action_select)
        self.air_canvas = tk.Canvas(air_frame, bg='white', height=420)
        self.air_canvas.grid(row=0, column=1, sticky='nsew', padx=6, pady=6)
        self.notebook.add(air_frame, text='AIR Timeline')

        clsn_frame = ttk.Frame(self.notebook)
        clsn_frame.columnconfigure(1, weight=1)
        clsn_frame.rowconfigure(1, weight=1)
        clsn_top = ttk.Frame(clsn_frame, padding=(4, 4))
        clsn_top.grid(row=0, column=0, columnspan=2, sticky='ew')
        ttk.Label(clsn_top, text='Action').grid(row=0, column=0, padx=(0, 4))
        self.clsn_action_var = tk.StringVar()
        self.clsn_action_combo = ttk.Combobox(clsn_top, textvariable=self.clsn_action_var, width=34, state='readonly')
        self.clsn_action_combo.grid(row=0, column=1, padx=3)
        self.clsn_action_combo.bind('<<ComboboxSelected>>', self.on_clsn_action_select)
        ttk.Button(clsn_top, text='Apply Boxes to Editor', command=self.apply_clsn_to_editor).grid(row=0, column=2, padx=3)
        ttk.Button(clsn_top, text='Save AIR with .bak', command=self.save_air_with_backup).grid(row=0, column=3, padx=3)
        self.clsn_frame_list = tk.Listbox(clsn_frame, width=38, font=('Consolas', 10))
        self.clsn_frame_list.grid(row=1, column=0, sticky='nsw', padx=4, pady=4)
        self.clsn_frame_list.bind('<<ListboxSelect>>', self.on_clsn_frame_select)
        clsn_right = ttk.Frame(clsn_frame)
        clsn_right.grid(row=1, column=1, sticky='nsew', padx=4, pady=4)
        clsn_right.columnconfigure(0, weight=1)
        clsn_right.rowconfigure(0, weight=1)
        self.clsn_tree = ttk.Treeview(clsn_right, columns=('kind','x1','y1','x2','y2'), show='tree headings', height=10)
        for col in ('kind','x1','y1','x2','y2'):
            self.clsn_tree.heading(col, text=col.upper())
            self.clsn_tree.column(col, width=80, anchor='e' if col != 'kind' else 'center')
        self.clsn_tree.grid(row=0, column=0, sticky='nsew')
        self.clsn_tree.bind('<<TreeviewSelect>>', self.on_clsn_box_select)
        edit = ttk.Frame(clsn_right, padding=(0, 6))
        edit.grid(row=1, column=0, sticky='ew')
        ttk.Label(edit, text='Kind').grid(row=0, column=0)
        self.clsn_kind_var = tk.StringVar(value='Clsn2')
        ttk.Combobox(edit, textvariable=self.clsn_kind_var, values=('Clsn1','Clsn2'), width=8, state='readonly').grid(row=0, column=1, padx=3)
        self.clsn_x1_var = tk.StringVar(value='-20')
        self.clsn_y1_var = tk.StringVar(value='-80')
        self.clsn_x2_var = tk.StringVar(value='20')
        self.clsn_y2_var = tk.StringVar(value='0')
        for i, (label, var) in enumerate((('X1', self.clsn_x1_var), ('Y1', self.clsn_y1_var), ('X2', self.clsn_x2_var), ('Y2', self.clsn_y2_var)), start=2):
            ttk.Label(edit, text=label).grid(row=0, column=i*2-2)
            ttk.Entry(edit, textvariable=var, width=8).grid(row=0, column=i*2-1, padx=3)
        ttk.Button(edit, text='Add Box', command=self.add_clsn_box).grid(row=0, column=10, padx=3)
        ttk.Button(edit, text='Update Box', command=self.update_clsn_box).grid(row=0, column=11, padx=3)
        ttk.Button(edit, text='Delete Box', command=self.delete_clsn_box).grid(row=0, column=12, padx=3)
        self.clsn_canvas = tk.Canvas(clsn_right, bg='white', height=320)
        self.clsn_canvas.grid(row=2, column=0, sticky='ew')
        self.clsn_canvas.bind('<ButtonPress-1>', self.on_clsn_canvas_press)
        self.clsn_canvas.bind('<B1-Motion>', self.on_clsn_canvas_drag)
        self.clsn_canvas.bind('<ButtonRelease-1>', self.on_clsn_canvas_release)
        self.clsn_canvas.bind('<Double-Button-1>', self.on_clsn_canvas_double_click)
        self.clsn_help = tk.Text(clsn_right, wrap='word', height=5, font=('Consolas', 9), state='disabled')
        self.clsn_help.grid(row=3, column=0, sticky='ew', pady=(4,0))
        self.notebook.add(clsn_frame, text='CLSN Editor')

    def _build_binary_and_animation_tabs(self):
        sprite_frame = ttk.Frame(self.notebook)
        sprite_frame.columnconfigure(0, weight=1)
        sprite_frame.rowconfigure(0, weight=1)
        sprite_left = ttk.Frame(sprite_frame)
        sprite_left.grid(row=0, column=0, sticky='nsew')
        sprite_left.columnconfigure(0, weight=1)
        sprite_left.rowconfigure(1, weight=1)
        sprite_toolbar = ttk.Frame(sprite_left, padding=(4, 4))
        sprite_toolbar.grid(row=0, column=0, sticky='ew')
        ttk.Button(sprite_toolbar, text='Export Selected', command=self.export_selected_sprite).grid(row=0, column=0, padx=3)
        ttk.Button(sprite_toolbar, text='Export All', command=self.export_sff_sprites).grid(row=0, column=1, padx=3)
        ttk.Button(sprite_toolbar, text='Stage Replace Manifest', command=self.stage_sff_replacement).grid(row=0, column=2, padx=3)
        ttk.Button(sprite_toolbar, text='Inspect Replace Manifest', command=self.inspect_sff_replacement_manifest).grid(row=0, column=3, padx=3)
        ttk.Button(sprite_toolbar, text='Build Replaced SFF v1', command=self.build_replaced_sff).grid(row=0, column=4, padx=3)
        self.sprite_tree = ttk.Treeview(sprite_left, columns=('group', 'image', 'axis', 'bytes', 'format'), show='tree headings')
        self.sprite_tree.heading('#0', text='#')
        self.sprite_tree.heading('group', text='Group')
        self.sprite_tree.heading('image', text='Image')
        self.sprite_tree.heading('axis', text='Axis')
        self.sprite_tree.heading('bytes', text='Bytes')
        self.sprite_tree.heading('format', text='Format')
        self.sprite_tree.column('#0', width=70, anchor='e')
        self.sprite_tree.column('group', width=80, anchor='e')
        self.sprite_tree.column('image', width=80, anchor='e')
        self.sprite_tree.column('axis', width=100)
        self.sprite_tree.column('bytes', width=100, anchor='e')
        self.sprite_tree.column('format', width=80)
        self.sprite_tree.grid(row=1, column=0, sticky='nsew')
        self.sprite_tree.bind('<<TreeviewSelect>>', self.on_sprite_select)
        sprite_right = ttk.Frame(sprite_frame, padding=(6, 6))
        sprite_right.grid(row=0, column=1, sticky='nsew')
        sprite_right.columnconfigure(0, weight=1)
        sprite_right.rowconfigure(1, weight=1)
        self.sprite_info = tk.Text(sprite_right, wrap='word', width=45, height=10, font=('Consolas', 10), state='disabled')
        self.sprite_info.grid(row=0, column=0, sticky='ew')
        self.sprite_canvas = tk.Canvas(sprite_right, bg='white', width=360, height=360)
        self.sprite_canvas.grid(row=1, column=0, sticky='nsew', pady=(6,0))
        self.notebook.add(sprite_frame, text='Sprites')


        sheet_frame = ttk.Frame(self.notebook)
        sheet_frame.columnconfigure(0, weight=1)
        sheet_frame.rowconfigure(2, weight=1)
        sheet_top = ttk.Frame(sheet_frame, padding=(4, 4))
        sheet_top.grid(row=0, column=0, sticky='ew')
        ttk.Button(sheet_top, text='Choose PNG Sheet', command=self.choose_sprite_sheet).grid(row=0, column=0, padx=3)
        ttk.Button(sheet_top, text='Preview Grid', command=self.preview_sprite_sheet_grid).grid(row=0, column=1, padx=3)
        ttk.Button(sheet_top, text='Export Slices + Manifest', command=self.export_sprite_sheet_slices).grid(row=0, column=2, padx=3)
        ttk.Button(sheet_top, text='Append AIR Action', command=self.append_air_action_from_sheet).grid(row=0, column=3, padx=3)
        ttk.Button(sheet_top, text='Build SFF v1', command=self.build_sff_from_sheet_manifest).grid(row=0, column=4, padx=3)
        ttk.Button(sheet_top, text='Inspect Manifest', command=self.inspect_sprite_manifest).grid(row=0, column=5, padx=3)
        sheet_fields = ttk.Frame(sheet_frame, padding=(4, 0))
        sheet_fields.grid(row=1, column=0, sticky='ew')
        self.sheet_vars = {}
        defaults = [
            ('cell_w','64'), ('cell_h','64'), ('cols','4'), ('rows','1'),
            ('margin_x','0'), ('margin_y','0'), ('space_x','0'), ('space_y','0'),
            ('group','200'), ('start_image','0'), ('axis_x','32'), ('axis_y','64'), ('ticks','5'),
        ]
        for i, (name, val) in enumerate(defaults):
            ttk.Label(sheet_fields, text=name).grid(row=i//7, column=(i%7)*2, sticky='e', padx=(2,1))
            var = tk.StringVar(value=val)
            self.sheet_vars[name] = var
            ttk.Entry(sheet_fields, textvariable=var, width=7).grid(row=i//7, column=(i%7)*2+1, sticky='w', padx=(1,5))
        sheet_body = ttk.Panedwindow(sheet_frame, orient=tk.HORIZONTAL)
        sheet_body.grid(row=2, column=0, sticky='nsew', padx=4, pady=4)
        sheet_left = ttk.Frame(sheet_body)
        sheet_left.columnconfigure(0, weight=1)
        sheet_left.rowconfigure(0, weight=1)
        self.sheet_tree = ttk.Treeview(sheet_left, columns=('group','image','rect','axis','file'), show='tree headings')
        self.sheet_tree.heading('#0', text='#')
        self.sheet_tree.heading('group', text='Group')
        self.sheet_tree.heading('image', text='Image')
        self.sheet_tree.heading('rect', text='Rect')
        self.sheet_tree.heading('axis', text='Axis')
        self.sheet_tree.heading('file', text='Filename')
        self.sheet_tree.column('#0', width=55, anchor='e')
        self.sheet_tree.column('group', width=70, anchor='e')
        self.sheet_tree.column('image', width=70, anchor='e')
        self.sheet_tree.column('rect', width=150)
        self.sheet_tree.column('axis', width=90)
        self.sheet_tree.column('file', width=260)
        self.sheet_tree.grid(row=0, column=0, sticky='nsew')
        sheet_body.add(sheet_left, weight=2)
        sheet_right = ttk.Frame(sheet_body)
        sheet_right.columnconfigure(0, weight=1)
        sheet_right.rowconfigure(0, weight=1)
        self.sheet_canvas = tk.Canvas(sheet_right, bg='white', width=760, height=450)
        self.sheet_canvas.grid(row=0, column=0, sticky='nsew')
        self.sheet_info = tk.Text(sheet_right, wrap='word', height=7, font=('Consolas', 9), state='disabled')
        self.sheet_info.grid(row=1, column=0, sticky='ew', pady=(4,0))
        sheet_body.add(sheet_right, weight=3)
        self.notebook.add(sheet_frame, text='Sheet Import')

        sound_frame = ttk.Frame(self.notebook)
        sound_frame.columnconfigure(0, weight=1)
        sound_frame.rowconfigure(1, weight=1)
        sound_toolbar = ttk.Frame(sound_frame, padding=(4, 4))
        sound_toolbar.grid(row=0, column=0, sticky='ew')
        ttk.Button(sound_toolbar, text='Export Selected WAV', command=self.export_selected_sound).grid(row=0, column=0, padx=3)
        ttk.Button(sound_toolbar, text='Export All WAV', command=self.export_snd_sounds).grid(row=0, column=1, padx=3)
        ttk.Button(sound_toolbar, text='Make WAV Manifest', command=self.make_snd_manifest).grid(row=0, column=2, padx=3)
        ttk.Button(sound_toolbar, text='Inspect SND Manifest', command=self.inspect_snd_manifest).grid(row=0, column=3, padx=3)
        ttk.Button(sound_toolbar, text='Build SND', command=self.build_snd_from_manifest_ui).grid(row=0, column=4, padx=3)
        ttk.Button(sound_toolbar, text='Make Placeholder Sound Bank', command=self.make_placeholder_sound_bank_ui).grid(row=0, column=5, padx=3)
        ttk.Button(sound_toolbar, text='Export WAV Cue Sheet', command=self.export_wav_cue_sheet_ui).grid(row=0, column=6, padx=3)
        self.sound_tree = ttk.Treeview(sound_frame, columns=('id', 'offset', 'bytes', 'format'), show='tree headings')
        self.sound_tree.heading('#0', text='#')
        self.sound_tree.heading('id', text='Group,Sound / ID')
        self.sound_tree.heading('offset', text='Offset')
        self.sound_tree.heading('bytes', text='Bytes')
        self.sound_tree.heading('format', text='WAVE Format')
        self.sound_tree.column('#0', width=70, anchor='e')
        self.sound_tree.column('id', width=130)
        self.sound_tree.column('offset', width=110, anchor='e')
        self.sound_tree.column('bytes', width=110, anchor='e')
        self.sound_tree.column('format', width=280)
        self.sound_tree.grid(row=1, column=0, sticky='nsew')
        self.sound_tree.bind('<<TreeviewSelect>>', self.on_sound_select)
        self.sound_info = tk.Text(sound_frame, wrap='word', height=8, font=('Consolas', 10), state='disabled')
        self.sound_info.grid(row=2, column=0, sticky='ew', padx=4, pady=4)
        self.notebook.add(sound_frame, text='Sounds')

        self.preview = tk.Text(self.notebook, wrap='word', font=('Consolas', 10), state='disabled')
        self.notebook.add(self.preview, text='Binary / Preview')

        anim_frame = ttk.Frame(self.notebook)
        anim_frame.columnconfigure(0, weight=1)
        anim_frame.rowconfigure(2, weight=1)
        anim_top = ttk.Frame(anim_frame, padding=(4, 4))
        anim_top.grid(row=0, column=0, sticky='ew')
        ttk.Label(anim_top, text='Action').grid(row=0, column=0, padx=(0, 4))
        self.anim_action_combo = ttk.Combobox(anim_top, textvariable=self.anim_action_var, width=36, state='readonly')
        self.anim_action_combo.grid(row=0, column=1, padx=3)
        self.anim_action_combo.bind('<<ComboboxSelected>>', self.on_anim_action_select)
        ttk.Button(anim_top, text='Play', command=self.play_animation).grid(row=0, column=2, padx=3)
        ttk.Button(anim_top, text='Pause', command=self.pause_animation).grid(row=0, column=3, padx=3)
        ttk.Button(anim_top, text='Prev', command=lambda: self.step_animation(-1)).grid(row=0, column=4, padx=3)
        ttk.Button(anim_top, text='Next', command=lambda: self.step_animation(1)).grid(row=0, column=5, padx=3)
        ttk.Checkbutton(anim_top, text='Loop', variable=self.anim_loop_var).grid(row=0, column=6, padx=3)
        ttk.Label(anim_top, text='Speed').grid(row=0, column=7, padx=(10, 2))
        ttk.Spinbox(anim_top, from_=0.25, to=4.0, increment=0.25, textvariable=self.anim_speed_var, width=6).grid(row=0, column=8, padx=3)
        ttk.Label(anim_top, text='Zoom').grid(row=0, column=9, padx=(10, 2))
        ttk.Spinbox(anim_top, from_=1, to=6, increment=1, textvariable=self.anim_zoom_var, width=5, command=self.draw_animation_frame).grid(row=0, column=10, padx=3)
        self.anim_scrub = ttk.Scale(anim_frame, from_=0, to=0, variable=self.anim_frame_var, orient='horizontal', command=self.on_anim_scrub)
        self.anim_scrub.grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 4))
        self.anim_canvas = tk.Canvas(anim_frame, bg='white', width=900, height=480)
        self.anim_canvas.grid(row=2, column=0, sticky='nsew', padx=6, pady=6)
        self.anim_info = tk.Text(anim_frame, wrap='word', height=7, font=('Consolas', 10), state='disabled')
        self.anim_info.grid(row=3, column=0, sticky='ew', padx=6, pady=(0,6))
        self.notebook.add(anim_frame, text='Animation Player')

    def _build_authoring_tabs(self):
        author_frame = ttk.Frame(self.notebook)
        self.author_frame = author_frame
        author_frame.columnconfigure(0, weight=1)
        author_frame.rowconfigure(2, weight=1)
        author_top = ttk.LabelFrame(author_frame, text='Command / State Generator', padding=(6, 6))
        author_top.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        self.author_vars = {}
        author_defaults = [
            ('cmd_name', 'x'), ('cmd_input', 'x'), ('cmd_time', '1'),
            ('state_no', '200'), ('anim_no', '200'), ('damage', '35'),
            ('sound_group', '5'), ('sound_index', '0'),
        ]
        for i, (name, val) in enumerate(author_defaults):
            ttk.Label(author_top, text=name).grid(row=i//4, column=(i%4)*2, sticky='e', padx=(2, 1), pady=2)
            var = tk.StringVar(value=val)
            self.author_vars[name] = var
            ttk.Entry(author_top, textvariable=var, width=14).grid(row=i//4, column=(i%4)*2+1, sticky='w', padx=(1, 8), pady=2)
        author_buttons = ttk.Frame(author_frame, padding=(6, 0))
        author_buttons.grid(row=1, column=0, sticky='ew')
        ttk.Button(author_buttons, text='Insert [Command]', command=self.insert_command_template).grid(row=0, column=0, padx=3)
        ttk.Button(author_buttons, text='Insert -1 ChangeState', command=self.insert_changestate_template).grid(row=0, column=1, padx=3)
        ttk.Button(author_buttons, text='Insert Attack State', command=self.insert_attack_state_template).grid(row=0, column=2, padx=3)
        ttk.Button(author_buttons, text='Insert Projectile State', command=self.insert_projectile_state_template).grid(row=0, column=3, padx=3)
        ttk.Button(author_buttons, text='Insert Helper/Explod', command=self.insert_helper_explod_template).grid(row=0, column=4, padx=3)
        ttk.Button(author_buttons, text='Inspect Current Code', command=self.inspect_current_code).grid(row=0, column=5, padx=3)
        ttk.Button(author_buttons, text='Inspect Whole Character', command=self.inspect_whole_character_code).grid(row=0, column=6, padx=3)
        self.author_output = tk.Text(author_frame, wrap='word', font=('Consolas', 10), state='disabled')
        self.author_output.grid(row=2, column=0, sticky='nsew', padx=6, pady=6)
        self.notebook.add(author_frame, text='Code Assistant')

        wizard_frame = ttk.Frame(self.notebook)
        self.wizard_frame = wizard_frame
        wizard_frame.columnconfigure(0, weight=1)
        wizard_frame.rowconfigure(3, weight=1)
        wiz_top = ttk.LabelFrame(wizard_frame, text='Move Wizard', padding=(6, 6))
        wiz_top.grid(row=0, column=0, sticky='ew', padx=6, pady=6)
        wizard_defaults = [
            ('move_name', 'Light Punch'), ('move_type', 'attack'), ('command_name', 'light_punch'), ('command_input', 'x'),
            ('command_time', '12'), ('state_no', '200'), ('anim_no', '200'), ('sprite_group', '200'),
            ('start_image', '0'), ('frame_count', '4'), ('ticks', '4'), ('hit_frame', '2'),
            ('damage', '35'), ('hit_x1', '18'), ('hit_y1', '-72'), ('hit_x2', '58'), ('hit_y2', '-36'),
            ('body_x1', '-18'), ('body_y1', '-88'), ('body_x2', '18'), ('body_y2', '0'),
            ('sound_group', '5'), ('sound_index', '0'), ('sparkno', '2'), ('guard_sparkno', '40'),
        ]
        for i, (name, val) in enumerate(wizard_defaults):
            ttk.Label(wiz_top, text=name).grid(row=i//4, column=(i%4)*2, sticky='e', padx=(2, 1), pady=2)
            var = tk.StringVar(value=val)
            self.wizard_vars[name] = var
            if name == 'move_type':
                ttk.Combobox(wiz_top, textvariable=var, values=('attack', 'projectile', 'movement'), width=14, state='readonly').grid(row=i//4, column=(i%4)*2+1, sticky='w', padx=(1, 8), pady=2)
            else:
                ttk.Entry(wiz_top, textvariable=var, width=14).grid(row=i//4, column=(i%4)*2+1, sticky='w', padx=(1, 8), pady=2)
        wiz_buttons = ttk.Frame(wizard_frame, padding=(6, 0))
        wiz_buttons.grid(row=1, column=0, sticky='ew')
        ttk.Button(wiz_buttons, text='Generate Preview', command=self.wizard_generate_preview).grid(row=0, column=0, padx=3)
        ttk.Button(wiz_buttons, text='Insert CMD Block', command=lambda: self.wizard_insert_block('cmd')).grid(row=0, column=1, padx=3)
        ttk.Button(wiz_buttons, text='Insert CNS/ST Block', command=lambda: self.wizard_insert_block('cns')).grid(row=0, column=2, padx=3)
        ttk.Button(wiz_buttons, text='Insert AIR Block', command=lambda: self.wizard_insert_block('air')).grid(row=0, column=3, padx=3)
        ttk.Button(wiz_buttons, text='Append To Project Files (.bak)', command=self.wizard_append_to_project).grid(row=0, column=4, padx=3)
        wiz_note = tk.Text(wizard_frame, wrap='word', height=4, font=('Consolas', 9), state='disabled')
        wiz_note.grid(row=2, column=0, sticky='ew', padx=6, pady=(6, 0))
        self.wizard_note = wiz_note
        self.set_text(self.wizard_note, 'Generate a full move package: CMD input, -1 ChangeState wiring, CNS/ST StateDef logic, and AIR frames/CLSN boxes. Use Append To Project Files to update the first DEF-referenced CMD/CNS/AIR files with backups.')
        self.wizard_output = tk.Text(wizard_frame, wrap='none', font=('Consolas', 10), state='disabled')
        self.wizard_output.grid(row=3, column=0, sticky='nsew', padx=6, pady=6)
        self.notebook.add(wizard_frame, text='Move Wizard')

    def _build_feature_tabs(self):
        self._build_auto_builder_tab()
        self._build_factory_plus_tab()
        self._build_factory_max_tab()
        self._build_factory_ultra_tab()
        self._build_creator_os_tab()
        self._build_quality_lab_tab()
        self._build_creator_suite_tab()
        self._build_creator_hub_tab()
        self._build_rescue_lab_tab()
        self._build_sff2_bridge_tab()
        self._build_image_factory_tab()
        self._build_palette_tab()
        self._build_studio_plus_tab()
        self._build_forge_plus_tab()
        self._build_sprite_lab_tab()
        self._build_stage_builder_tab()
        self._build_run_test_tab()
        self._build_visual_forge_home_tab()
        self._build_visual_timeline_editor_tab()
        self._build_sprite_offset_axis_tab()
        self._build_sound_cue_editor_tab()
        self._build_move_composer2_tab()
        self._build_migration_wizard_tab()
        self._build_training_debug_tab()
        self._build_plugin_template_tab()
        self._build_backup_log_tab()
        self._build_forge_beyond_tab()
        self._build_forge_polish_tab()
        self._build_forge_timeline_tab()
        self._build_binary_core_tab()
        self._build_binary_deep_tab()
        self._build_binary_maturity_tab()
        self._build_closure_lab_tab()
        self._build_gap_closer_tab()
        self._build_authority_core_tab()
        self._build_runtime_lab_tab()
        self._build_authority_lab_tab()
        self._build_evidence_core_tab()
        self._build_maintenance_core_tab()
        self._build_operator_console_tab()
        self._build_handoff_core_tab()

    def _select_initial_workspace(self):
        try:
            self.notebook.select(self.operator_console_frame)
        except Exception:
            try:
                self.notebook.select(self.vf_home_frame)
            except Exception:
                pass

    def _bind_keys(self):
        self.bind('<Control-s>', lambda e: self.save_current())
        self.bind('<Control-o>', lambda e: self.open_folder())
        self.bind('<Control-r>', lambda e: self.reload_project())

    def set_text(self, widget: tk.Text, text: str):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')


def main():
    app = MugenForgeApp()
    app.mainloop()


if __name__ == '__main__':
    main()
