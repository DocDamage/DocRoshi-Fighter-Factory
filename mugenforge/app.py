from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

from .parsers import (
    TEXT_EXTS, IMAGE_EXTS, COMMON_ANIMS, read_text_safely, write_text_safely,
    parse_def, parse_air, parse_code, scan_project, summarize_binary, make_new_character
)
from .sff_codec import (
    read_sff, export_sprite, try_convert_to_png, sprite_lookup,
)
from .air_tools import parse_air_with_lines, update_frame_clsn_text, normalize_box
from .factory_ultra import (
    write_beginner_command_center, write_no_code_recipe_bank, write_generated_code_map,
    build_asset_dependency_map, write_combo_trial_builder,
    write_clsn_audit, create_sff_sprite_atlas, create_action_strip_previews,
    create_snd_waveform_sheet, write_controller_snippet_library, write_ultra_task_board,
)


from .ui_tabs.asset_workspaces import RunTestTab, SpriteLabTab, StageBuilderTab
from .ui_tabs.authority import AuthorityCoreTab, AuthorityLabTab
from .ui_tabs.binary import BinaryWorkspaceTabs
from .ui_tabs.closure_evidence import ClosureLabTab, EvidenceCoreTab
from .ui_tabs.continuity import HandoffCoreTab, MaintenanceCoreTab, OperatorConsoleTab
from .ui_tabs.creator_factory_tabs import AutoBuilderTab, CreatorOSTab, CreatorSuiteTab, FactoryMaxTab, FactoryUltraTab, QualityLabTab
from .ui_tabs.creator_hub import CreatorHubTab
from .ui_tabs.forge_workspaces import ForgeBeyondTab, ForgePolishTab, ForgeTimelineTab
from .ui_tabs.gap_closer import GapCloserTab
from .ui_tabs.image_factory import ImageFactoryTab
from .ui_tabs.palette import PaletteTab
from .ui_tabs.plus_workspaces import FactoryPlusTab, ForgePlusTab, StudioPlusTab
from .ui_tabs.rescue_lab import RescueLabTab
from .ui_tabs.runtime_lab import RuntimeLabTab
from .ui_tabs.sff2_bridge import Sff2BridgeTab
from .ui_tabs.visual_forge_tabs import (
    BackupLogTab,
    MigrationWizardTab,
    MoveComposer2Tab,
    PluginTemplateTab,
    SoundCueEditorTab,
    SpriteOffsetAxisTab,
    TrainingDebugTab,
    VisualForgeHomeTab,
    VisualTimelineTab,
)
from .ui_actions.creator_os import CreatorOSActions
from .ui_actions.creator_suite import CreatorSuiteActions
from .ui_actions.asset_workspaces import AssetWorkspaceActions
from .ui_actions.code_authoring import CodeAuthoringActions
from .ui_actions.feature_bank import FeatureBankActions
from .ui_actions.factory_max import FactoryMaxActions
from .ui_actions.factory_plus import FactoryPlusActions
from .ui_actions.factory_ultra import FactoryUltraActions
from .ui_actions.image_factory import ImageFactoryActions
from .ui_actions.palette import PaletteActions
from .ui_actions.plus_workspaces import PlusWorkspaceActions
from .ui_actions.quality_lab import QualityLabActions
from .ui_actions.sound_pipeline import SoundPipelineActions
from .ui_actions.sprite_pipeline import SpritePipelineActions
from .ui_actions.visual_forge import VisualForgeActions

APP_TITLE = 'MugenForge Studio 7.5 Continuity Core'

class MugenForgeApp(FeatureBankActions, CreatorOSActions, CreatorSuiteActions, AssetWorkspaceActions, CodeAuthoringActions, FactoryMaxActions, FactoryPlusActions, FactoryUltraActions, ImageFactoryActions, PaletteActions, PlusWorkspaceActions, QualityLabActions, SoundPipelineActions, SpritePipelineActions, VisualForgeActions, tk.Tk):
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
        try:
            self.notebook.select(self.operator_console_frame)
        except Exception:
            try:
                self.notebook.select(self.vf_home_frame)
            except Exception:
                pass
        paned.add(center, weight=4)

    def _build_auto_builder_tab(self):
        self.auto_builder_tab = AutoBuilderTab(self)


    def _build_factory_max_tab(self):
        self.factory_max_tab = FactoryMaxTab(self)


    def _build_creator_os_tab(self):
        self.creator_os_tab = CreatorOSTab(self)

    def _build_factory_ultra_tab(self):
        self.factory_ultra_tab = FactoryUltraTab(self)

    def _build_quality_lab_tab(self):
        self.quality_lab_tab = QualityLabTab(self)

    def _build_creator_suite_tab(self):
        self.creator_suite_tab = CreatorSuiteTab(self)

    def _build_creator_hub_tab(self):
        self.creator_hub_tab = CreatorHubTab(self)


    def _build_sff2_bridge_tab(self):
        self.sff2_bridge_tab = Sff2BridgeTab(self)


    def _build_rescue_lab_tab(self):
        self.rescue_lab_tab = RescueLabTab(self)


    def _build_image_factory_tab(self):
        self.image_factory_tab = ImageFactoryTab(self)


    def _build_palette_tab(self):
        self.palette_tab = PaletteTab(self)


    def _build_studio_plus_tab(self):
        self.studio_plus_tab = StudioPlusTab(self)


    def _build_factory_plus_tab(self):
        self.factory_plus_tab = FactoryPlusTab(self)


    def _build_forge_plus_tab(self):
        self.forge_plus_tab = ForgePlusTab(self)


    def _build_sprite_lab_tab(self):
        self.sprite_lab_tab = SpriteLabTab(self)


    def _build_stage_builder_tab(self):
        self.stage_builder_tab = StageBuilderTab(self)


    def _build_run_test_tab(self):
        self.run_test_tab = RunTestTab(self)


    # ------------------------------------------------------------------
    # Visual Forge v3.5 beginner-first workflow tabs
    # ------------------------------------------------------------------

    def _build_visual_forge_home_tab(self):
        self.visual_forge_home_tab = VisualForgeHomeTab(self)


    def _build_visual_timeline_editor_tab(self):
        self.visual_timeline_tab = VisualTimelineTab(self)


    def _build_sprite_offset_axis_tab(self):
        self.sprite_offset_axis_tab = SpriteOffsetAxisTab(self)

    def _build_sound_cue_editor_tab(self):
        self.sound_cue_editor_tab = SoundCueEditorTab(self)

    def _build_move_composer2_tab(self):
        self.move_composer2_tab = MoveComposer2Tab(self)

    def _build_migration_wizard_tab(self):
        self.migration_wizard_tab = MigrationWizardTab(self)

    def _build_training_debug_tab(self):
        self.training_debug_tab = TrainingDebugTab(self)

    def _build_plugin_template_tab(self):
        self.plugin_template_tab = PluginTemplateTab(self)

    def _build_backup_log_tab(self):
        self.backup_log_tab = BackupLogTab(self)

    def _bind_keys(self):
        self.bind('<Control-s>', lambda e: self.save_current())
        self.bind('<Control-o>', lambda e: self.open_folder())
        self.bind('<Control-r>', lambda e: self.reload_project())

    def set_text(self, widget: tk.Text, text: str):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def open_folder(self):
        path = filedialog.askdirectory(title='Select M.U.G.E.N character folder')
        if path:
            self.load_project(Path(path))

    def load_project(self, root: Path):
        self.project_root = root
        self.current_path = None
        self.tree.delete(*self.tree.get_children())
        root_id = self.tree.insert('', 'end', text=root.name, values=('dir', ''), open=True, tags=(str(root),))
        self._add_tree_children(root_id, root)
        self.status_var.set(f'Loaded: {root}')
        try:
            self._vf_note_recent(root)
        except Exception:
            pass
        self.validate_project(show_popup=False)

    def _add_tree_children(self, parent_id: str, path: Path):
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        for item in items:
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                node = self.tree.insert(parent_id, 'end', text=item.name, values=('dir', ''), open=False, tags=(str(item),))
                self._add_tree_children(node, item)
            else:
                size = f'{item.stat().st_size:,}'
                self.tree.insert(parent_id, 'end', text=item.name, values=(item.suffix.lower() or 'file', size), tags=(str(item),))

    def on_tree_select(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        path = Path(self.tree.item(selected[0], 'tags')[0])
        if path.is_dir():
            return
        if self.dirty and not messagebox.askyesno('Unsaved changes', 'Discard unsaved changes and open another file?'):
            return
        self.open_file(path)

    def open_file(self, path: Path):
        self.current_path = path
        ext = path.suffix.lower()
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.edit_modified(False)
        self.dirty = False
        self.clear_code_map()
        self.clear_air_timeline()
        if ext in TEXT_EXTS:
            text = read_text_safely(path)
            self.editor.insert('1.0', text)
            self.editor.configure(state='normal')
            self.analyze_text_file(path, text)
            self.set_text(self.preview, 'Text file loaded. Use Editor, Analysis, Code Map, or AIR Timeline tabs.')
            if ext == '.air':
                self.populate_air_timeline(text)
                self.populate_animation_player(text)
                self.populate_clsn_editor(text)
                self.notebook.select(3)
            elif ext in {'.cmd', '.cns', '.st'}:
                self.populate_code_map(text)
                self.notebook.select(2)
            else:
                self.notebook.select(0)
        else:
            self.editor.insert('1.0', f'Binary file: {path.name}\n\nEditing disabled in this build.')
            self.editor.configure(state='disabled')
            self.set_text(self.analysis, 'Binary file. No text analysis available.')
            self.set_text(self.preview, summarize_binary(path))
            if ext == '.sff':
                self.populate_sprite_browser(path)
                self.notebook.select(5)
            elif ext == '.snd':
                self.populate_sound_browser(path)
                self.notebook.select(7)
            elif ext == '.act':
                self.populate_palette_browser(path)
                self.notebook.select(self.palette_frame)
            else:
                self.notebook.select(8)
        self.status_var.set(f'Opened: {path.name}')

    def analyze_text_file(self, path: Path, text: str):
        ext = path.suffix.lower()
        lines = [f'File: {path.name}', f'Path: {path}', f'Lines: {len(text.splitlines())}', '']
        if ext == '.def':
            sections = parse_def(text)
            lines.append('DEF sections:')
            for sec in sections.values():
                lines.append(f'  [{sec.name}] - {len(sec.values)} keys')
                for k, v in list(sec.values.items())[:30]:
                    status = ''
                    if sec.name.lower() == 'files' and v:
                        target = (path.parent / v.strip().strip('"')).resolve()
                        status = '  OK' if target.exists() else '  MISSING'
                    lines.append(f'    {k} = {v}{status}')
        elif ext == '.air':
            actions = parse_air(text)
            total_frames = sum(len(a.frames) for a in actions)
            total_clsn = sum(len(f.clsn) for a in actions for f in a.frames)
            lines.append(f'AIR actions: {len(actions)}')
            lines.append(f'Total frames: {total_frames}')
            lines.append(f'CLSN boxes attached to frames: {total_clsn}')
            lines.append('')
            for action in actions[:120]:
                label = f' - {action.label}' if action.label else ''
                ticks = sum(max(0, f.ticks) for f in action.frames)
                lines.append(f'  Action {action.number}{label}: {len(action.frames)} frames, {ticks} ticks')
        elif ext in {'.cmd', '.cns', '.st'}:
            cs = parse_code(text)
            lines.append('Code scan:')
            lines.append(f'  Commands: {len(cs.commands)}')
            lines.append(f'  StateDefs: {len(cs.states)}')
            lines.append(f'  State controllers: {len(cs.controllers)}')
            hitdefs = sum(1 for c in cs.controllers if c.stype == 'hitdef')
            changestates = sum(1 for c in cs.controllers if c.stype == 'changestate')
            explods = sum(1 for c in cs.controllers if c.stype in {'explod', 'helper', 'projectile'})
            lines.append(f'  HitDefs: {hitdefs}')
            lines.append(f'  ChangeStates: {changestates}')
            lines.append(f'  Helpers/Projectiles/Explods: {explods}')
            if cs.commands:
                lines.append('\nCommands:')
                for cmd in cs.commands[:80]:
                    lines.append(f'  line {cmd.line}: {cmd.name} -> {cmd.command}')
            if cs.issues:
                lines.append('\nWarnings:')
                for issue in cs.issues[:80]:
                    lines.append(f'  - {issue}')
        else:
            lines.append('Generic text file. No specialized parser for this extension yet.')
        self.set_text(self.analysis, '\n'.join(lines))

    def clear_code_map(self):
        self.code_map.delete(*self.code_map.get_children())

    def populate_code_map(self, text: str):
        self.clear_code_map()
        cs = parse_code(text)
        cmd_root = self.code_map.insert('', 'end', text='Commands', values=('', 'group', str(len(cs.commands))), open=True)
        for c in cs.commands:
            self.code_map.insert(cmd_root, 'end', text=c.name, values=(c.line, 'Command', c.command))
        state_root = self.code_map.insert('', 'end', text='StateDefs', values=('', 'group', str(len(cs.states))), open=True)
        for st in cs.states:
            anim = st.values.get('anim', '')
            detail = f'anim={anim}, controllers={len(st.controllers)}'
            node = self.code_map.insert(state_root, 'end', text=str(st.number), values=(st.line, 'StateDef', detail), open=False)
            for ctrl in st.controllers:
                self.code_map.insert(node, 'end', text=ctrl.header, values=(ctrl.line, ctrl.stype or 'controller', ctrl.values.get('value', '') or ctrl.values.get('trigger1', '')))
        if cs.issues:
            issue_root = self.code_map.insert('', 'end', text='Issues', values=('', 'group', str(len(cs.issues))), open=True)
            for issue in cs.issues:
                self.code_map.insert(issue_root, 'end', text='Warning', values=('', 'Issue', issue))

    def clear_air_timeline(self):
        self.air_actions = []
        self.action_list.delete(0, 'end')
        self.air_canvas.delete('all')

    def populate_air_timeline(self, text: str):
        self.clear_air_timeline()
        self.load_linked_sff_for_air()
        self.air_actions = parse_air(text)
        for action in self.air_actions:
            label = action.label or COMMON_ANIMS.get(action.number, '')
            suffix = f' {label}' if label else ''
            self.action_list.insert('end', f'{action.number:>5} | {len(action.frames):>3}f |{suffix}')
        if self.air_actions:
            self.action_list.selection_set(0)
            self.draw_action(self.air_actions[0])

    def on_action_select(self, event=None):
        sel = self.action_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.air_actions):
            self.draw_action(self.air_actions[idx])

    def draw_action(self, action):
        c = self.air_canvas
        c.delete('all')
        width = max(900, c.winfo_width() or 900)
        y = 60
        x = 30
        c.create_text(20, 20, anchor='w', text=f'Action {action.number} {action.label or COMMON_ANIMS.get(action.number, "")} | {len(action.frames)} frames', font=('Consolas', 12, 'bold'))
        if not action.frames:
            c.create_text(30, 80, anchor='w', text='No frames in this action.')
            return
        scale = 12
        max_h = 120
        for idx, frame in enumerate(action.frames):
            w = max(18, frame.ticks * scale if frame.ticks > 0 else 22)
            if x + w > width - 40:
                x = 30
                y += 150
            has_sprite = (frame.group, frame.image) in self.sff_sprite_lookup
            c.create_rectangle(x, y, x + w, y + 90, outline='dark green' if has_sprite else 'black', width=2 if has_sprite else 1)
            c.create_text(x + 4, y + 5, anchor='nw', text=f'{idx}\n{frame.group},{frame.image}\n{frame.ticks}t', font=('Consolas', 9))
            # draw rough origin cross and CLSN mini-boxes; this is a structural preview, not sprite rendering yet
            ox, oy = x + w/2, y + 55
            c.create_line(ox - 6, oy, ox + 6, oy)
            c.create_line(ox, oy - 6, ox, oy + 6)
            for b_i, box in enumerate(frame.clsn[:4]):
                pad = 8 + b_i * 4
                c.create_rectangle(x + pad, y + 52 + pad/3, x + w - pad, y + 84 - pad/3, dash=(3, 2))
                c.create_text(x + pad, y + 38 + b_i*10, anchor='nw', text=box.kind, font=('Consolas', 7))
            if frame.flags:
                c.create_text(x + 4, y + 72, anchor='nw', text=frame.flags[:12], font=('Consolas', 8))
            x += w + 8
        c.create_text(30, y + 120, anchor='w', text='Timeline is based on AIR frame ticks. Green-linked frames have matching SFF sprite records loaded from the character DEF sprite file.', font=('Consolas', 10))

    def load_linked_sff_for_air(self):
        self.sff_sprite_lookup = {}
        if not self.project_root:
            return
        def_files = sorted(self.project_root.glob('*.def'))
        for def_path in def_files:
            try:
                sections = parse_def(read_text_safely(def_path))
                files = sections.get('files')
                if not files:
                    continue
                ref = files.values.get('sprite')
                if not ref:
                    continue
                sff_path = (def_path.parent / ref.strip().strip('"')).resolve()
                if sff_path.exists():
                    info = read_sff(sff_path)
                    self.sff_path = sff_path
                    self.sff_info = info
                    self.sff_sprite_lookup = sprite_lookup(info)
                    return
            except Exception:
                continue


    def populate_animation_player(self, text: str):
        self.pause_animation()
        self.air_actions = parse_air(text)
        values = []
        for action in self.air_actions:
            label = action.label or COMMON_ANIMS.get(action.number, '')
            suffix = f' - {label}' if label else ''
            values.append(f'{action.number} | {len(action.frames)} frames{suffix}')
        self.anim_action_combo.configure(values=values)
        if values:
            self.anim_action_combo.current(0)
            self.anim_frame_var.set(0)
            self.configure_anim_scrub()
            self.draw_animation_frame()
        else:
            self.anim_canvas.delete('all')
            self.set_text(self.anim_info, 'No AIR actions found.')

    def _selected_anim_action(self):
        idx = self.anim_action_combo.current()
        if 0 <= idx < len(self.air_actions):
            return self.air_actions[idx]
        return None

    def configure_anim_scrub(self):
        action = self._selected_anim_action()
        max_frame = max(0, len(action.frames) - 1) if action else 0
        self.anim_scrub.configure(from_=0, to=max_frame)
        if self.anim_frame_var.get() > max_frame:
            self.anim_frame_var.set(max_frame)

    def on_anim_action_select(self, event=None):
        self.pause_animation()
        self.anim_frame_var.set(0)
        self.configure_anim_scrub()
        self.draw_animation_frame()

    def on_anim_scrub(self, value=None):
        if not self.anim_is_playing:
            self.draw_animation_frame()

    def _load_anim_frame_photo(self, frame):
        if not frame or not self.sff_path or not self.sff_sprite_lookup:
            return None
        spr = self.sff_sprite_lookup.get((frame.group, frame.image))
        if not spr or spr.format_hint not in {'pcx', 'png'}:
            return None
        try:
            from io import BytesIO
            from PIL import Image, ImageTk  # type: ignore
            payload = self.sff_path.read_bytes()[spr.data_offset:spr.data_offset + spr.length]
            img = Image.open(BytesIO(payload)).convert('RGBA')
            zoom = max(1, int(self.anim_zoom_var.get()))
            if zoom != 1:
                img = img.resize((max(1, img.width * zoom), max(1, img.height * zoom)))
            return ImageTk.PhotoImage(img), spr, zoom, img.width, img.height
        except Exception:
            return None

    def draw_animation_frame(self, *args):
        c = self.anim_canvas
        c.delete('all')
        self.anim_photo = None
        action = self._selected_anim_action()
        if not action or not action.frames:
            c.create_text(20, 20, anchor='nw', text='Open an AIR file to preview animation playback.')
            self.set_text(self.anim_info, 'No selected action.')
            return
        idx = int(round(float(self.anim_frame_var.get())))
        idx = max(0, min(idx, len(action.frames) - 1))
        if self.anim_frame_var.get() != idx:
            self.anim_frame_var.set(idx)
        frame = action.frames[idx]
        width = max(760, c.winfo_width() or 760)
        height = max(420, c.winfo_height() or 420)
        ox, oy = width // 2, height // 2 + 80
        zoom = max(1, int(self.anim_zoom_var.get()))
        c.create_text(10, 10, anchor='nw', text=f'Action {action.number} | frame {idx+1}/{len(action.frames)} | sprite {frame.group},{frame.image} | ticks {frame.ticks}', font=('Consolas', 11, 'bold'))
        c.create_line(ox - 360, oy, ox + 360, oy, dash=(2,2))
        c.create_line(ox, oy - 300, ox, oy + 90, dash=(2,2))
        c.create_text(ox + 5, oy + 5, anchor='nw', text='AIR origin 0,0', font=('Consolas', 9))
        loaded = self._load_anim_frame_photo(frame)
        sprite_status = 'missing or unsupported'
        if loaded:
            photo, spr, scale, img_w, img_h = loaded
            self.anim_photo = photo
            top_left_x = ox + int(frame.x * scale) - int(spr.x * scale)
            top_left_y = oy + int(frame.y * scale) - int(spr.y * scale)
            c.create_image(top_left_x, top_left_y, image=photo, anchor='nw')
            c.create_rectangle(top_left_x, top_left_y, top_left_x + img_w, top_left_y + img_h, dash=(2,2))
            c.create_text(top_left_x, max(35, top_left_y - 14), anchor='w', text=f'SFF sprite axis {spr.x},{spr.y}', font=('Consolas', 8))
            sprite_status = f'loaded from {self.sff_path.name}'
        else:
            c.create_rectangle(ox - 32 * zoom, oy - 96 * zoom, ox + 32 * zoom, oy, dash=(4,2))
            c.create_text(ox - 120, oy - 125, anchor='nw', text='Sprite image unavailable. AIR timing still previews. Verify DEF sprite= path, SFF v1/PCX support, and Pillow.', font=('Consolas', 9))
        for b in frame.clsn:
            x1, y1 = ox + b.x1 * zoom, oy + b.y1 * zoom
            x2, y2 = ox + b.x2 * zoom, oy + b.y2 * zoom
            dash = () if b.kind == 'Clsn1' else (5, 3)
            c.create_rectangle(x1, y1, x2, y2, dash=dash, width=2)
            sx1, sy1 = min(x1,x2), min(y1,y2)
            c.create_text(sx1 + 3, sy1 + 3, anchor='nw', text=b.kind, font=('Consolas', 8))
        info = [
            f'Action: {action.number} {action.label or COMMON_ANIMS.get(action.number, "")}',
            f'Frame: {idx} / {len(action.frames)-1}',
            f'Sprite: {frame.group},{frame.image} ({sprite_status})',
            f'Frame offset: {frame.x},{frame.y}',
            f'Ticks: {frame.ticks}; playback assumes 60 ticks/sec and multiplies by Speed.',
            f'CLSN boxes on this frame: {len(frame.clsn)}',
            'Solid boxes are Clsn1 attack boxes; dashed boxes are Clsn2 vulnerability boxes.',
        ]
        self.set_text(self.anim_info, '\n'.join(info))

    def play_animation(self):
        action = self._selected_anim_action()
        if not action or not action.frames:
            return
        if self.anim_after_id:
            self.after_cancel(self.anim_after_id)
            self.anim_after_id = None
        self.anim_is_playing = True
        self._schedule_next_anim_frame(first=True)

    def pause_animation(self):
        self.anim_is_playing = False
        if self.anim_after_id:
            try:
                self.after_cancel(self.anim_after_id)
            except Exception:
                pass
            self.anim_after_id = None

    def step_animation(self, delta: int):
        self.pause_animation()
        action = self._selected_anim_action()
        if not action or not action.frames:
            return
        next_idx = max(0, min(len(action.frames) - 1, int(self.anim_frame_var.get()) + delta))
        self.anim_frame_var.set(next_idx)
        self.draw_animation_frame()

    def _schedule_next_anim_frame(self, first: bool = False):
        if not self.anim_is_playing:
            return
        action = self._selected_anim_action()
        if not action or not action.frames:
            self.pause_animation()
            return
        idx = int(self.anim_frame_var.get())
        idx = max(0, min(idx, len(action.frames) - 1))
        self.anim_frame_var.set(idx)
        self.draw_animation_frame()
        frame = action.frames[idx]
        speed = max(0.25, float(self.anim_speed_var.get() or 1.0))
        ticks = max(1, int(frame.ticks or 1))
        delay_ms = max(15, int((ticks / 60.0) * 1000 / speed))
        next_idx = idx + 1
        if next_idx >= len(action.frames):
            if self.anim_loop_var.get():
                next_idx = 0
            else:
                self.pause_animation()
                return
        self.anim_frame_var.set(next_idx)
        self.anim_after_id = self.after(delay_ms, self._schedule_next_anim_frame)


    def populate_clsn_editor(self, text: str):
        self.air_line_actions = parse_air_with_lines(text)
        self.clsn_boxes = []
        values = []
        for action in self.air_line_actions:
            label = f' - {action.label}' if action.label else ''
            values.append(f'{action.number} | {len(action.frames)} frames{label}')
        self.clsn_action_combo.configure(values=values)
        self.clsn_frame_list.delete(0, 'end')
        self.clsn_tree.delete(*self.clsn_tree.get_children())
        self.clsn_canvas.delete('all')
        self.set_text(self.clsn_help, 'Open an AIR file, choose an action/frame, then edit hitboxes. Drag inside a box to move it. Drag edges/corners to resize. Double-click empty canvas to add a new box using the current Kind. Apply changes to the text editor, then save. Sprite-backed preview works when Pillow can decode the linked SFF sprite.')
        if values:
            self.clsn_action_combo.current(0)
            self.on_clsn_action_select()

    def _selected_clsn_action(self):
        idx = self.clsn_action_combo.current()
        if 0 <= idx < len(self.air_line_actions):
            return self.air_line_actions[idx]
        return None

    def _selected_clsn_frame(self):
        action = self._selected_clsn_action()
        if not action:
            return None
        sel = self.clsn_frame_list.curselection()
        if not sel:
            return None
        idx = sel[0]
        if 0 <= idx < len(action.frames):
            return action.frames[idx]
        return None

    def on_clsn_action_select(self, event=None):
        action = self._selected_clsn_action()
        self.clsn_frame_list.delete(0, 'end')
        self.clsn_tree.delete(*self.clsn_tree.get_children())
        self.clsn_canvas.delete('all')
        if not action:
            return
        for frame in action.frames:
            self.clsn_frame_list.insert('end', f'{frame.frame_index:>3} | spr {frame.group},{frame.image} | {frame.ticks:>3}t | {len(frame.clsn)} box')
        if action.frames:
            self.clsn_frame_list.selection_set(0)
            self.on_clsn_frame_select()

    def on_clsn_frame_select(self, event=None):
        frame = self._selected_clsn_frame()
        self.clsn_tree.delete(*self.clsn_tree.get_children())
        self.clsn_boxes = []
        if not frame:
            self.draw_clsn_boxes()
            return
        self.clsn_boxes = [normalize_box(b.kind, b.x1, b.y1, b.x2, b.y2) for b in frame.clsn]
        self.refresh_clsn_tree()
        self.draw_clsn_boxes(frame)

    def refresh_clsn_tree(self):
        self.clsn_tree.delete(*self.clsn_tree.get_children())
        for i, b in enumerate(self.clsn_boxes):
            item = self.clsn_tree.insert('', 'end', text=str(i), values=(b.kind, b.x1, b.y1, b.x2, b.y2), tags=(str(i),))
            if self.clsn_drag and self.clsn_drag.get('idx') == i:
                self.clsn_tree.selection_set(item)

    def select_clsn_box_index(self, idx: int):
        for item in self.clsn_tree.get_children():
            try:
                if int(self.clsn_tree.item(item, 'tags')[0]) == idx:
                    self.clsn_tree.selection_set(item)
                    self.clsn_tree.focus(item)
                    self.clsn_tree.see(item)
                    self.on_clsn_box_select()
                    return
            except Exception:
                continue

    def on_clsn_box_select(self, event=None):
        sel = self.clsn_tree.selection()
        if not sel:
            return
        try:
            idx = int(self.clsn_tree.item(sel[0], 'tags')[0])
            b = self.clsn_boxes[idx]
        except Exception:
            return
        self.clsn_kind_var.set(b.kind)
        self.clsn_x1_var.set(str(b.x1))
        self.clsn_y1_var.set(str(b.y1))
        self.clsn_x2_var.set(str(b.x2))
        self.clsn_y2_var.set(str(b.y2))

    def _box_from_fields(self):
        try:
            return normalize_box(self.clsn_kind_var.get(), int(self.clsn_x1_var.get()), int(self.clsn_y1_var.get()), int(self.clsn_x2_var.get()), int(self.clsn_y2_var.get()))
        except ValueError:
            messagebox.showwarning('Invalid box', 'Box coordinates must be integers.')
            return None

    def add_clsn_box(self):
        box = self._box_from_fields()
        if not box:
            return
        self.clsn_boxes.append(box)
        self.refresh_clsn_tree()
        self.draw_clsn_boxes(self._selected_clsn_frame())

    def update_clsn_box(self):
        sel = self.clsn_tree.selection()
        if not sel:
            messagebox.showinfo('No box selected', 'Select a CLSN box first.')
            return
        box = self._box_from_fields()
        if not box:
            return
        idx = int(self.clsn_tree.item(sel[0], 'tags')[0])
        if 0 <= idx < len(self.clsn_boxes):
            self.clsn_boxes[idx] = box
            self.refresh_clsn_tree()
            self.draw_clsn_boxes(self._selected_clsn_frame())

    def delete_clsn_box(self):
        sel = self.clsn_tree.selection()
        if not sel:
            return
        idx = int(self.clsn_tree.item(sel[0], 'tags')[0])
        if 0 <= idx < len(self.clsn_boxes):
            del self.clsn_boxes[idx]
            self.refresh_clsn_tree()
            self.draw_clsn_boxes(self._selected_clsn_frame())

    def _load_clsn_frame_sprite_photo(self, frame):
        """Return a Tk PhotoImage plus placement metadata for the selected AIR frame, if possible."""
        if not frame or not self.sff_path or not self.sff_sprite_lookup:
            return None
        spr = self.sff_sprite_lookup.get((frame.group, frame.image))
        if not spr or spr.format_hint not in {'pcx', 'png'}:
            return None
        try:
            from io import BytesIO
            from PIL import Image, ImageTk  # type: ignore
            data = self.sff_path.read_bytes()[spr.data_offset:spr.data_offset + spr.length]
            img = Image.open(BytesIO(data)).convert('RGBA')
            max_w, max_h = 260, 220
            scale = min(max_w / max(1, img.width), max_h / max(1, img.height), 1.0)
            if scale < 1.0:
                img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
            photo = ImageTk.PhotoImage(img)
            return photo, spr, scale, img.width, img.height
        except Exception:
            return None

    def draw_clsn_boxes(self, frame=None):
        c = self.clsn_canvas
        c.delete('all')
        self.clsn_sprite_photo = None
        self.clsn_drawn_boxes = []
        width = max(620, c.winfo_width() or 620)
        height = max(315, c.winfo_height() or 315)
        ox, oy = width // 2, height // 2 + 40
        self.clsn_canvas_origin = (ox, oy)
        c.create_text(10, 10, anchor='w', text='CLSN preview: drag boxes to move, drag edges/corners to resize, double-click empty space to add.', font=('Consolas', 10, 'bold'))
        if frame:
            c.create_text(10, 30, anchor='w', text=f'Action {frame.action_number}, frame {frame.frame_index}, sprite {frame.group},{frame.image}, offset {frame.x},{frame.y}, ticks {frame.ticks}', font=('Consolas', 9))
            preview = self._load_clsn_frame_sprite_photo(frame)
            if preview:
                photo, spr, scale, img_w, img_h = preview
                self.clsn_sprite_photo = photo
                top_left_x = ox + int(frame.x * scale) - int(spr.x * scale)
                top_left_y = oy + int(frame.y * scale) - int(spr.y * scale)
                c.create_image(top_left_x, top_left_y, image=photo, anchor='nw')
                c.create_rectangle(top_left_x, top_left_y, top_left_x + img_w, top_left_y + img_h, dash=(2, 2))
                c.create_text(top_left_x, top_left_y - 12, anchor='w', text=f'sprite {frame.group},{frame.image}', font=('Consolas', 8))
            elif self.sff_sprite_lookup:
                c.create_text(10, 48, anchor='w', text='Sprite image preview unavailable for this frame. Install Pillow or verify the SFF payload is PCX/PNG.', font=('Consolas', 8))
        c.create_line(ox - 320, oy, ox + 320, oy, dash=(2, 2))
        c.create_line(ox, oy - 145, ox, oy + 120, dash=(2, 2))
        c.create_text(ox + 5, oy + 5, anchor='nw', text='0,0', font=('Consolas', 8))
        selected_idx = None
        sel = self.clsn_tree.selection()
        if sel:
            try:
                selected_idx = int(self.clsn_tree.item(sel[0], 'tags')[0])
            except Exception:
                selected_idx = None
        for i, b in enumerate(self.clsn_boxes):
            x1, y1, x2, y2 = ox + b.x1, oy + b.y1, ox + b.x2, oy + b.y2
            sx1, sx2 = sorted((x1, x2))
            sy1, sy2 = sorted((y1, y2))
            self.clsn_drawn_boxes.append((i, sx1, sy1, sx2, sy2))
            dash = () if b.kind == 'Clsn1' else (4, 2)
            width_px = 3 if i == selected_idx else 2
            c.create_rectangle(x1, y1, x2, y2, dash=dash, width=width_px, tags=(f'clsn_box_{i}',))
            c.create_text(sx1 + 3, sy1 + 3, anchor='nw', text=f'{i}:{b.kind}', font=('Consolas', 8))
            if i == selected_idx:
                for hx, hy in ((sx1, sy1), (sx2, sy1), (sx1, sy2), (sx2, sy2)):
                    c.create_rectangle(hx-3, hy-3, hx+3, hy+3, fill='black')

    def _hit_test_clsn_canvas(self, x: int, y: int):
        handle_pad = 7
        for idx, x1, y1, x2, y2 in reversed(self.clsn_drawn_boxes):
            near_left = abs(x - x1) <= handle_pad
            near_right = abs(x - x2) <= handle_pad
            near_top = abs(y - y1) <= handle_pad
            near_bottom = abs(y - y2) <= handle_pad
            inside_x = x1 - handle_pad <= x <= x2 + handle_pad
            inside_y = y1 - handle_pad <= y <= y2 + handle_pad
            if inside_x and inside_y and (near_left or near_right or near_top or near_bottom):
                mode = ''
                if near_left:
                    mode += 'w'
                elif near_right:
                    mode += 'e'
                if near_top:
                    mode += 'n'
                elif near_bottom:
                    mode += 's'
                return idx, (mode or 'move')
            if x1 <= x <= x2 and y1 <= y <= y2:
                return idx, 'move'
        return None, None

    def on_clsn_canvas_press(self, event):
        idx, mode = self._hit_test_clsn_canvas(event.x, event.y)
        if idx is None:
            self.clsn_drag = None
            return
        self.select_clsn_box_index(idx)
        b = self.clsn_boxes[idx]
        self.clsn_drag = {
            'idx': idx, 'mode': mode, 'start_x': event.x, 'start_y': event.y,
            'orig': (b.x1, b.y1, b.x2, b.y2),
        }

    def on_clsn_canvas_drag(self, event):
        if not self.clsn_drag:
            return
        idx = self.clsn_drag['idx']
        if not (0 <= idx < len(self.clsn_boxes)):
            return
        dx = event.x - self.clsn_drag['start_x']
        dy = event.y - self.clsn_drag['start_y']
        x1, y1, x2, y2 = self.clsn_drag['orig']
        mode = self.clsn_drag['mode']
        if mode == 'move':
            nx1, ny1, nx2, ny2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
        else:
            nx1, ny1, nx2, ny2 = x1, y1, x2, y2
            if 'w' in mode:
                nx1 = x1 + dx
            if 'e' in mode:
                nx2 = x2 + dx
            if 'n' in mode:
                ny1 = y1 + dy
            if 's' in mode:
                ny2 = y2 + dy
        b = self.clsn_boxes[idx]
        self.clsn_boxes[idx] = normalize_box(b.kind, nx1, ny1, nx2, ny2)
        self.clsn_x1_var.set(str(nx1)); self.clsn_y1_var.set(str(ny1)); self.clsn_x2_var.set(str(nx2)); self.clsn_y2_var.set(str(ny2))
        self.refresh_clsn_tree()
        self.draw_clsn_boxes(self._selected_clsn_frame())

    def on_clsn_canvas_release(self, event):
        if self.clsn_drag:
            idx = self.clsn_drag['idx']
            self.clsn_drag = None
            self.select_clsn_box_index(idx)
            self.draw_clsn_boxes(self._selected_clsn_frame())

    def on_clsn_canvas_double_click(self, event):
        idx, _mode = self._hit_test_clsn_canvas(event.x, event.y)
        if idx is not None:
            self.select_clsn_box_index(idx)
            return
        ox, oy = self.clsn_canvas_origin
        cx, cy = event.x - ox, event.y - oy
        half_w, half_h = 18, 24
        box = normalize_box(self.clsn_kind_var.get(), cx - half_w, cy - half_h, cx + half_w, cy + half_h)
        self.clsn_boxes.append(box)
        self.refresh_clsn_tree()
        self.select_clsn_box_index(len(self.clsn_boxes) - 1)
        self.draw_clsn_boxes(self._selected_clsn_frame())

    def apply_clsn_to_editor(self):
        frame = self._selected_clsn_frame()
        action = self._selected_clsn_action()
        if not frame or not action:
            messagebox.showinfo('No frame selected', 'Open an AIR file and select an action/frame first.')
            return
        if not self.current_path or self.current_path.suffix.lower() != '.air':
            messagebox.showwarning('Wrong file', 'The current editor file must be an AIR file.')
            return
        text = self.editor.get('1.0', 'end-1c')
        try:
            updated, warnings = update_frame_clsn_text(text, action.number, frame.frame_index, self.clsn_boxes)
        except Exception as exc:
            messagebox.showerror('CLSN update failed', str(exc))
            return
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', updated)
        self.editor.edit_modified(True)
        self.dirty = True
        self.populate_air_timeline(updated)
        self.populate_animation_player(updated)
        self.populate_clsn_editor(updated)
        msg = 'CLSN boxes were applied to the editor buffer. Review the AIR text, then save.'
        if warnings:
            msg += '\n\nWarnings:\n' + '\n'.join(warnings[:6])
        messagebox.showinfo('Applied', msg)

    def save_air_with_backup(self):
        if not self.current_path or self.current_path.suffix.lower() != '.air':
            messagebox.showwarning('Wrong file', 'Open an AIR file first.')
            return
        text = self.editor.get('1.0', 'end-1c')
        backup = self.current_path.with_suffix(self.current_path.suffix + '.bak')
        if self.current_path.exists():
            backup.write_text(read_text_safely(self.current_path), encoding='utf-8')
        write_text_safely(self.current_path, text)
        self.dirty = False
        self.status_var.set(f'Saved AIR with backup: {backup.name}')
        messagebox.showinfo('Saved', f'Saved AIR file and wrote backup:\n{backup}')

    def on_editor_modified(self, event=None):
        if self.editor.edit_modified():
            self.dirty = True
            name = self.current_path.name if self.current_path else 'Untitled'
            self.status_var.set(f'Modified: {name}')
            self.editor.edit_modified(False)

    def save_current(self):
        if not self.current_path:
            return
        if self.current_path.suffix.lower() not in TEXT_EXTS:
            messagebox.showwarning('Binary file', 'Binary editing is not enabled in this build.')
            return
        text = self.editor.get('1.0', 'end-1c')
        write_text_safely(self.current_path, text)
        self.dirty = False
        self.status_var.set(f'Saved: {self.current_path.name}')
        self.analyze_text_file(self.current_path, text)
        if self.current_path.suffix.lower() == '.air':
            self.populate_air_timeline(text)
            self.populate_clsn_editor(text)
        elif self.current_path.suffix.lower() in {'.cmd', '.cns', '.st'}:
            self.populate_code_map(text)

    def validate_project(self, show_popup=True):
        if not self.project_root:
            if show_popup:
                messagebox.showinfo('No project', 'Open a character folder first.')
            return
        audit = scan_project(self.project_root)
        lines = [f'Project: {audit.root}', f'Checked: {datetime.now().isoformat(timespec="seconds")}', '', 'File counts:']
        for ext, count in sorted(audit.found_exts.items()):
            lines.append(f'  {ext or "[none]"}: {count}')
        lines.append('')
        if audit.missing_required:
            lines.append('Missing common character files by extension: ' + ', '.join(audit.missing_required))
        else:
            lines.append('Common character file set found by extension: DEF, AIR, CMD, CNS, SFF, SND')
        if audit.def_references:
            lines.append('\nDEF [Files] references:')
            for def_path, refs in audit.def_references.items():
                lines.append(f'  {def_path.name}:')
                for key, ref in refs.items():
                    exists = (def_path.parent / ref.strip().strip('"')).exists()
                    lines.append(f'    {key}: {ref} {"OK" if exists else "MISSING"}')
        if audit.missing_references:
            lines.append('\nMissing DEF references:')
            for miss in audit.missing_references[:80]:
                lines.append(f'  - {miss}')
        if audit.code_issues:
            lines.append('\nCode issues:')
            for issue in audit.code_issues[:80]:
                lines.append(f'  - {issue}')
        if audit.asset_issues:
            lines.append('\nAIR/SFF asset issues:')
            for issue in audit.asset_issues[:80]:
                lines.append(f'  - {issue}')
        if audit.warnings:
            lines.append('\nWarnings:')
            for w in audit.warnings:
                lines.append(f'  - {w}')
        self.set_text(self.analysis, '\n'.join(lines))
        if show_popup:
            messagebox.showinfo('Validation complete', 'Project validation report is in the Analysis tab.')
        self.notebook.select(1)

    def export_audit(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        audit = scan_project(self.project_root)
        out = filedialog.asksaveasfilename(title='Save audit report', defaultextension='.md', filetypes=[('Markdown', '*.md'), ('Text', '*.txt')])
        if not out:
            return
        lines = [f'# MugenForge Audit: {audit.root.name}', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '', '## File Counts']
        for ext, count in sorted(audit.found_exts.items()):
            lines.append(f'- `{ext or "[none]"}`: {count}')
        lines += ['', '## Missing Common Character Files']
        if audit.missing_required:
            for m in audit.missing_required:
                lines.append(f'- `{m}`')
        else:
            lines.append('- None detected by extension')
        lines += ['', '## DEF File References']
        if audit.def_references:
            for def_path, refs in audit.def_references.items():
                lines.append(f'### `{def_path.name}`')
                for key, ref in refs.items():
                    exists = (def_path.parent / ref.strip().strip('"')).exists()
                    lines.append(f'- `{key}`: `{ref}` — {"OK" if exists else "MISSING"}')
        else:
            lines.append('- No DEF references found')
        lines += ['', '## Missing DEF References']
        if audit.missing_references:
            for m in audit.missing_references:
                lines.append(f'- {m}')
        else:
            lines.append('- None detected')
        lines += ['', '## Code Issues']
        if audit.code_issues:
            for issue in audit.code_issues:
                lines.append(f'- {issue}')
        else:
            lines.append('- None detected')
        lines += ['', '## AIR/SFF Asset Issues']
        if audit.asset_issues:
            for issue in audit.asset_issues:
                lines.append(f'- {issue}')
        else:
            lines.append('- None detected')
        lines += ['', '## Warnings']
        if audit.warnings:
            for w in audit.warnings:
                lines.append(f'- {w}')
        else:
            lines.append('- None')
        Path(out).write_text('\n'.join(lines), encoding='utf-8')
        self.status_var.set(f'Audit exported: {out}')

    def reload_project(self):
        if self.project_root:
            self.load_project(self.project_root)

    def find_todos(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        lines = ['TODO / FIXME / placeholder scan', '']
        found = 0
        for path in sorted(self.project_root.rglob('*')):
            if path.is_file() and path.suffix.lower() in TEXT_EXTS:
                text = read_text_safely(path)
                for idx, line in enumerate(text.splitlines(), start=1):
                    low = line.lower()
                    if 'todo' in low or 'fixme' in low or 'placeholder' in low:
                        rel = path.relative_to(self.project_root)
                        lines.append(f'{rel}:{idx}: {line.strip()}')
                        found += 1
        if not found:
            lines.append('No TODO/FIXME/placeholder markers found.')
        self.set_text(self.analysis, '\n'.join(lines))
        self.notebook.select(1)

    def _build_forge_beyond_tab(self):
        self.forge_beyond_tab = ForgeBeyondTab(self)


    def _build_forge_polish_tab(self):
        self.forge_polish_tab = ForgePolishTab(self)


    def _build_forge_timeline_tab(self):
        self.forge_timeline_tab = ForgeTimelineTab(self)


    def _build_binary_core_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)

    def _build_binary_deep_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)

    def _build_binary_maturity_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)


    def _build_runtime_lab_tab(self):
        self.runtime_lab_tab = RuntimeLabTab(self)


    def _build_gap_closer_tab(self):
        self.gap_closer_tab = GapCloserTab(self)


    def _build_authority_core_tab(self):
        self.authority_core_tab = AuthorityCoreTab(self)

    def _build_authority_lab_tab(self):
        self.authority_lab_tab = AuthorityLabTab(self)


    def _build_closure_lab_tab(self):
        self.closure_lab_tab = ClosureLabTab(self)

    def _build_evidence_core_tab(self):
        self.evidence_core_tab = EvidenceCoreTab(self)


    def _build_handoff_core_tab(self):
        self.handoff_core_tab = HandoffCoreTab(self)

    def _build_operator_console_tab(self):
        self.operator_console_tab = OperatorConsoleTab(self)

    def _build_maintenance_core_tab(self):
        self.maintenance_core_tab = MaintenanceCoreTab(self)

    def new_character(self):
        root = filedialog.askdirectory(title='Choose parent folder for new character')
        if not root:
            return
        name = simpledialog.askstring('New Character', 'Character folder/name:')
        if not name:
            return
        char_dir = make_new_character(Path(root), name)
        self.load_project(char_dir)
        messagebox.showinfo('Created', f'Created starter character files in:\n{char_dir}\n\nAdd your SFF and SND files next.')


def main():
    app = MugenForgeApp()
    app.mainloop()

if __name__ == '__main__':
    main()
