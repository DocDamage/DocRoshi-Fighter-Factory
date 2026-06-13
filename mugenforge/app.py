from __future__ import annotations

import tkinter as tk
import json
import re
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime

from .parsers import (
    TEXT_EXTS, IMAGE_EXTS, COMMON_ANIMS, read_text_safely, write_text_safely,
    parse_def, parse_air, parse_code, scan_project, summarize_binary, make_new_character
)
from .sff_codec import (
    read_sff, export_all_sprites, export_sprite, try_convert_to_png, sprite_lookup,
    build_sff_v1_from_manifest, summarize_manifest_for_sff,
    stage_sff_replacement_manifest, summarize_replacement_manifest,
    build_sff_v1_from_replacement_manifest,
)
from .snd_codec import read_snd, export_all_sounds, export_sound, make_snd_manifest_from_wav_folder, build_snd_from_manifest, summarize_snd_manifest, make_placeholder_sound_bank
from .air_tools import parse_air_with_lines, update_frame_clsn_text, normalize_box
from .spritesheet_tools import compute_grid_slices, export_grid_slices, write_manifest, make_air_action_from_slices, make_preview_image
from .code_authoring import (
    command_template, negative_one_changestate_template, attack_state_template,
    projectile_state_template, helper_explod_template, inspect_code_text,
    inspect_character_folder, package_character_zip,
)
from .move_wizard import normalize_spec, build_move_package, append_move_to_project
from .automation_bank import (
    preset_display_list, preset_by_display, build_feature_package, package_preview_text,
    apply_feature_package, apply_beginner_pack, auto_setup_project, beginner_project_status,
    export_code_bank_template, kit_names, kit_preview_text, apply_kit, make_placeholder_sprite_sheet,
    feature_bank_stats_text,
)
from .no_code_director import (
    archetype_names, archetype_preview_text, write_no_code_dashboard,
    one_click_playable_skeleton, no_code_director_summary,
)
from .palette_tools import read_act, write_palette_json, build_act_from_image, remap_palette_order, write_act

from .ff_plus import (
    ff_plus_dashboard_report, ensure_ff_plus_workspace, make_hitbox_preset_library,
    generate_action_catalog, generate_asset_index, generate_move_list,
    write_smart_code_bank, generate_release_checklist,
    install_required_actions_library, install_smart_cancel_suite, install_training_suite,
    install_ff_plus_authoring_pack, one_click_fighter_factory_plus_pass,
    ff_plus_summary_after_result,
)
from .ff_plus_tools import (
    full_project_report, export_move_list, write_creator_manual, summarize_image_folder,
    make_sprite_contact_sheet, normalize_sprite_folder, convert_images_to_pcx,
    make_animation_gif, make_air_from_image_sequence, build_sff_from_image_folder,
    build_act_from_folder, sound_cue_sheet, create_stage_from_image,
    write_mugen_launch_config, launch_mugen,
)
from . import factory_plus as fp
from .studio_plus import (
    studio_plus_report_text, write_studio_plus_report, write_studio_plus_report_json,
    auto_fix_project_plus, make_project_snapshot, build_release_zip_plus,
    create_sff_contact_sheet, export_action_gif, batch_import_sprite_folder_to_sff,
    generate_air_from_sff_groups, clone_air_action_variant, make_stage_template,
)

from .factory_max import (
    FACTORY_MAX_VERSION, factory_max_profile_report, one_click_factory_max_upgrade,
    write_codesense_bank, write_state_graph, write_organizer_manifest,
    suggest_clsn_from_sff, retime_air, renumber_air_actions,
    create_storyboard_template, create_screenpack_template, create_sound_autobank,
    create_quick_test_suite, safe_import_from_project, build_factory_max_release_zip,
    image_factory_process_folder, make_palette_variants,
)
from .factory_ultra import (
    FACTORY_ULTRA_VERSION,
    one_click_ultra_production_pass, ultra_project_dashboard,
    generate_frame_data_lab, generate_balance_lab, generate_cancel_lab,
    generate_asset_usage_lab, generate_sprite_axis_lab, generate_beginner_task_board,
    generate_move_cards, generate_input_map_assistant, write_no_code_feature_switchboard,
    write_production_bible, create_autosave_snapshot, generate_ai_tuning_lab,
    generate_release_readiness_report, build_ultra_release_zip,
    one_click_factory_ultra_upgrade, build_factory_ultra_release_zip,
    write_beginner_command_center, write_no_code_recipe_bank, write_generated_code_map,
    build_asset_dependency_map, write_balance_lab, write_combo_trial_builder,
    write_clsn_audit, create_sff_sprite_atlas, create_action_strip_previews,
    create_snd_waveform_sheet, write_controller_snippet_library, write_ultra_task_board,
    write_ultra_audit, write_smart_next_steps, write_creator_home_dashboard,
    write_no_code_function_map, write_input_conflict_report, write_frame_data_report,
    write_combo_lab, write_compatibility_matrix, auto_tune_damage, create_character_variant,
)


from .quality_lab import (
    run_quality_lab_pass, write_advanced_audit, write_searchable_html_index,
    write_move_cards, build_alpha_clsn_suggestions, write_alpha_clsn_air_copy,
    write_animation_timing_sheet, create_asset_swap_pack,
    create_backup_restore_bundle, write_beginner_fix_plan,
)
from .visual_forge import (
    VISUAL_FORGE_VERSION, BeginnerProjectSpec, SoundCueSpec, MigrationSpec,
    create_visual_forge_project, write_beginner_project_home, quick_start_pass,
    build_visual_timeline_model, write_visual_timeline_manifest, update_air_frame_ticks,
    build_sprite_offset_model, update_air_frame_offset, write_sound_cue_manifest,
    add_sound_cue_controller, compose_move2, migrate_existing_character,
    install_training_debug_pack, install_template_architecture, write_visual_sff2_bridge_pack,
    create_backup_snapshot, restore_latest_snapshot, log_error,
)
from .ui_tabs.asset_workspaces import RunTestTab, SpriteLabTab, StageBuilderTab
from .ui_tabs.authority import AuthorityCoreTab, AuthorityLabTab
from .ui_tabs.binary import BinaryWorkspaceTabs
from .ui_tabs.closure_evidence import ClosureLabTab, EvidenceCoreTab
from .ui_tabs.continuity import HandoffCoreTab, MaintenanceCoreTab, OperatorConsoleTab
from .ui_tabs.creator_hub import CreatorHubTab
from .ui_tabs.forge_workspaces import ForgeBeyondTab, ForgePolishTab, ForgeTimelineTab
from .ui_tabs.gap_closer import GapCloserTab
from .ui_tabs.image_factory import ImageFactoryTab
from .ui_tabs.palette import PaletteTab
from .ui_tabs.plus_workspaces import FactoryPlusTab, ForgePlusTab, StudioPlusTab
from .ui_tabs.rescue_lab import RescueLabTab
from .ui_tabs.runtime_lab import RuntimeLabTab
from .ui_tabs.sff2_bridge import Sff2BridgeTab
from .creator_os import (
    CREATOR_OS_VERSION, creator_os_one_click, write_character_blueprint,
    export_frame_data_sheet, export_input_cheatsheet, write_combo_routes,
    write_balance_report, write_release_quality_gate, write_asset_shopping_list,
    write_beginner_lessons, write_project_wiki, write_autocode_cookbook,
    build_creator_os_release_zip,
)
from .creator_suite import (
    CREATOR_SUITE_VERSION, one_click_creator_autopilot, creator_suite_profile_report,
    write_character_dna_profile, write_asset_library, write_move_lab,
    write_combo_tree, write_art_task_board, install_beginner_tuning_panel,
    make_project_time_machine_snapshot, write_creator_dashboard as write_suite_creator_dashboard,
    write_final_qa_release_plan, write_training_pack, write_creator_indexes,
    export_hitdef_tuning_sheet, apply_hitdef_tuning_sheet, write_artist_handoff_pack,
)

APP_TITLE = 'MugenForge Studio 7.5 Continuity Core'

class MugenForgeApp(tk.Tk):
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
        auto_frame = ttk.Frame(self.notebook)
        self.auto_frame = auto_frame
        auto_frame.columnconfigure(1, weight=1)
        auto_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(auto_frame, text='No-code Feature Bank / Auto Builder', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Pick a feature, preview what it will add, then let MugenForge write the CMD/CNS/AIR code with backups. '
            'This tab is built for users who want to design moves, timing, sprites, and hitboxes without manually coding every block.'
        )
        ttk.Label(header, text=intro, wraplength=980, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(auto_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Label(left, text='Feature presets').grid(row=0, column=0, sticky='ew')
        self.auto_feature_list = tk.Listbox(left, width=42, height=24, font=('Consolas', 10), exportselection=False)
        self.auto_feature_list.grid(row=1, column=0, sticky='nsw', pady=(3, 6))
        self.auto_feature_list.bind('<<ListboxSelect>>', self.auto_on_preset_select)
        self.auto_preset_items = preset_display_list()
        for item in self.auto_preset_items:
            self.auto_feature_list.insert('end', item)
        if self.auto_preset_items:
            self.auto_feature_list.selection_set(0)

        buttons = ttk.LabelFrame(left, text='One-click actions', padding=(6, 6))
        buttons.grid(row=2, column=0, sticky='ew')
        ttk.Button(buttons, text='Preview Selected', command=self.auto_preview_feature).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Add Selected To Project (.bak)', command=self.auto_apply_selected_feature).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Install Beginner Pack (.bak)', command=self.auto_apply_beginner_pack_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Auto Setup / Repair Project', command=self.auto_setup_project_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Project Status / Next Step', command=self.auto_project_status_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Write Code Bank Template', command=self.auto_export_code_bank_ui).grid(row=5, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Make Placeholder Sprite Sheet', command=self.auto_make_placeholder_sheet_ui).grid(row=6, column=0, sticky='ew', pady=2)
        ttk.Button(buttons, text='Feature Bank Stats', command=self.auto_feature_bank_stats_ui).grid(row=7, column=0, sticky='ew', pady=2)

        kit_box = ttk.LabelFrame(left, text='Creator kits', padding=(6, 6))
        kit_box.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        kit_values = kit_names()
        self.auto_kit_var = tk.StringVar(value=kit_values[0] if kit_values else '')
        self.auto_kit_combo = ttk.Combobox(kit_box, values=kit_values, textvariable=self.auto_kit_var, state='readonly', width=36)
        self.auto_kit_combo.grid(row=0, column=0, sticky='ew', pady=(0, 3))
        ttk.Button(kit_box, text='Preview Kit', command=self.auto_preview_kit).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(kit_box, text='Install Kit (.bak)', command=self.auto_apply_kit_ui).grid(row=2, column=0, sticky='ew', pady=2)

        director_box = ttk.LabelFrame(left, text='No-code Director', padding=(6, 6))
        director_box.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        archetypes = archetype_names()
        self.auto_archetype_var = tk.StringVar(value=archetypes[0] if archetypes else '')
        self.auto_archetype_combo = ttk.Combobox(director_box, values=archetypes, textvariable=self.auto_archetype_var, state='readonly', width=36)
        self.auto_archetype_combo.grid(row=0, column=0, sticky='ew', pady=(0, 3))
        ttk.Button(director_box, text='Preview Archetype', command=self.auto_preview_archetype).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(director_box, text='Write Dashboard / Checklists', command=self.auto_write_dashboard_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(director_box, text='One-Click Playable Skeleton', command=self.auto_one_click_skeleton_ui).grid(row=3, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=42, height=8, font=('Consolas', 9), state='disabled')
        note.grid(row=5, column=0, sticky='ew', pady=(6, 0))
        self.auto_note = note
        self.set_text(self.auto_note, 'Beginner Pack adds setup basics, punches, crouch kick, fireball, dash/backdash, taunt, and debug tools. Generated code is appended and marked so the app can avoid adding the same feature twice.')

        right = ttk.Frame(auto_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.auto_output = tk.Text(right, wrap='none', font=('Consolas', 10), state='disabled')
        auto_y = ttk.Scrollbar(right, orient='vertical', command=self.auto_output.yview)
        auto_x = ttk.Scrollbar(right, orient='horizontal', command=self.auto_output.xview)
        self.auto_output.configure(yscrollcommand=auto_y.set, xscrollcommand=auto_x.set)
        self.auto_output.grid(row=0, column=0, sticky='nsew')
        auto_y.grid(row=0, column=1, sticky='ns')
        auto_x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(auto_frame, text='Feature Bank')
        self.auto_preview_feature()


    def _build_factory_max_tab(self):
        max_frame = ttk.Frame(self.notebook)
        self.factory_max_frame = max_frame
        max_frame.columnconfigure(1, weight=1)
        max_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(max_frame, text=f'Factory Max / Better-than-FF Automation v{FACTORY_MAX_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'This tab targets Fighter Factory-style production workflows plus heavier beginner automation: code-sense banks, state graphs, safe imports, auto CLSN, storyboards, screenpack starters, sound cue banks, release QA, and one-click project upgrades.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(max_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click heavy lifting', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Factory Max Upgrade', command=self.max_one_click_upgrade_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Factory Max Profile Report', command=self.max_profile_report_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Build Factory Max Release ZIP', command=self.max_release_zip_ui).grid(row=2, column=0, sticky='ew', pady=2)

        code = ttk.LabelFrame(left, text='Code / structure tools', padding=(6, 6))
        code.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(code, text='Write CodeSense Bank', command=self.max_codesense_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Write State Graph', command=self.max_state_graph_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Write Organizer Manifest', command=self.max_organizer_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(code, text='Safe Import From Project', command=self.max_safe_import_ui).grid(row=3, column=0, sticky='ew', pady=2)

        anim = ttk.LabelFrame(left, text='Animation / CLSN automation', padding=(6, 6))
        anim.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self.max_clsn_padding_var = tk.StringVar(value='2')
        self.max_retime_scale_var = tk.StringVar(value='1.0')
        self.max_renumber_offset_var = tk.StringVar(value='10000')
        row_items = [('CLSN padding', self.max_clsn_padding_var), ('retime scale', self.max_retime_scale_var), ('clone offset', self.max_renumber_offset_var)]
        for i, (label, var) in enumerate(row_items):
            ttk.Label(anim, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=1)
            ttk.Entry(anim, textvariable=var, width=10).grid(row=i, column=1, sticky='w', padx=2, pady=1)
        ttk.Button(anim, text='Auto Body CLSN From SFF', command=self.max_auto_clsn_ui).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 2))
        ttk.Button(anim, text='Retime AIR Ticks', command=self.max_retime_air_ui).grid(row=4, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(anim, text='Clone/Renumber AIR Actions', command=self.max_renumber_air_ui).grid(row=5, column=0, columnspan=2, sticky='ew', pady=2)

        extras = ttk.LabelFrame(left, text='Full-project extras', padding=(6, 6))
        extras.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(extras, text='Create Storyboard Template', command=self.max_storyboard_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Create Screenpack Starter', command=self.max_screenpack_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Create Sound AutoBank', command=self.max_sound_autobank_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(extras, text='Write Quick Test Suite', command=self.max_quick_test_ui).grid(row=3, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=44, height=7, font=('Consolas', 9), state='disabled')
        note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self.max_note = note
        self.set_text(self.max_note, 'Best beginner route: One-Click Factory Max Upgrade → Animation Player → CLSN Editor → Image Factory/Sprite Lab → Profile Report → Release ZIP. CodeSense/state graph are there when you need to understand what happened.')

        right = ttk.Frame(max_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.factory_max_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.factory_max_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.factory_max_output.xview)
        self.factory_max_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.factory_max_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(max_frame, text='Factory Max')
        self.set_text(self.factory_max_output, 'Open/create a character folder, then run One-Click Factory Max Upgrade. It writes backups before changing active code files and keeps risky imports in an imports/ folder.')


    def _build_factory_ultra_tab(self):
        ultra = ttk.Frame(self.notebook)
        self.factory_ultra_frame = ultra
        ultra.columnconfigure(1, weight=1)
        ultra.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(ultra, text=f'Factory Ultra / Guided No-Code Production v{FACTORY_ULTRA_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Factory Ultra is the beginner-first layer: it audits the character, writes a plain-English next-step queue, checks input conflicts, exports balance/frame-data sheets, creates creator dashboards, clones variants, and builds release ZIPs with the reports included.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(ultra, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click production suite', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Factory Ultra Upgrade', command=self.ultra_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Ultra Audit / Doctor', command=self.ultra_audit_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Smart Next-Step Queue', command=self.ultra_next_steps_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Creator Home Dashboard', command=self.ultra_dashboard_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='No-Code Function Map', command=self.ultra_function_map_ui).grid(row=4, column=0, sticky='ew', pady=2)

        lab = ttk.LabelFrame(left, text='Labs / reports', padding=(6, 6))
        lab.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(lab, text='Input Conflict Report', command=self.ultra_input_report_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(lab, text='Balance Lab Sheet', command=self.ultra_balance_lab_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(lab, text='Frame Data Export', command=self.ultra_frame_data_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(lab, text='Combo Lab / Trial Builder', command=self.ultra_combo_lab_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(lab, text='Compatibility Matrix', command=self.ultra_compatibility_ui).grid(row=4, column=0, sticky='ew', pady=2)

        tune = ttk.LabelFrame(left, text='Safe auto-tuning', padding=(6, 6))
        tune.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self.ultra_damage_scale_var = tk.StringVar(value='1.00')
        self.ultra_damage_max_var = tk.StringVar(value='180')
        ttk.Label(tune, text='damage scale').grid(row=0, column=0, sticky='e', padx=2, pady=1)
        ttk.Entry(tune, textvariable=self.ultra_damage_scale_var, width=10).grid(row=0, column=1, sticky='w', padx=2, pady=1)
        ttk.Label(tune, text='max damage').grid(row=1, column=0, sticky='e', padx=2, pady=1)
        ttk.Entry(tune, textvariable=self.ultra_damage_max_var, width=10).grid(row=1, column=1, sticky='w', padx=2, pady=1)
        ttk.Button(tune, text='Auto-Tune Damage (.bak)', command=self.ultra_auto_tune_damage_ui).grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 2))

        release = ttk.LabelFrame(left, text='Variants / release', padding=(6, 6))
        release.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(release, text='Clone Character Variant', command=self.ultra_clone_variant_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(release, text='Build Ultra Release ZIP', command=self.ultra_release_zip_ui).grid(row=1, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=44, height=8, font=('Consolas', 9), state='disabled')
        note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self.ultra_note = note
        self.set_text(self.ultra_note, 'Best beginner route: One-Click Factory Ultra Upgrade → Smart Next-Step Queue → Feature Bank kits → Animation Player / CLSN Editor → Balance + Input + Frame reports → Ultra Release ZIP.')

        right = ttk.Frame(ultra, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.factory_ultra_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.factory_ultra_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.factory_ultra_output.xview)
        self.factory_ultra_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.factory_ultra_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(ultra, text='Factory Ultra')
        self.set_text(self.factory_ultra_output, 'Open/create a character folder, then run One-Click Factory Ultra Upgrade. This layer is built for non-coders: it writes reports, task queues, function maps, and safe scaffolds before you touch art/timing/hitboxes.')


    def _build_creator_os_tab(self):
        os_frame = ttk.Frame(self.notebook)
        self.creator_os_frame = os_frame
        os_frame.columnconfigure(1, weight=1)
        os_frame.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(os_frame, text=f'Creator OS / Beginner Autopilot v{CREATOR_OS_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Creator OS is the no-code layer: choose an archetype/style, then it writes plans, reports, checklists, code-bank docs, frame data, combo routes, balance notes, asset shopping lists, and release gates so the user can focus on sprites, sounds, timing, hitboxes, and feel.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(os_frame, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        profile = ttk.LabelFrame(left, text='Creative profile', padding=(6, 6))
        profile.grid(row=0, column=0, sticky='ew')
        self.creator_os_archetype_var = tk.StringVar(value='Balanced Starter')
        self.creator_os_complexity_var = tk.StringVar(value='Beginner')
        self.creator_os_style_var = tk.StringVar(value='Arcade')
        rows = [
            ('archetype', self.creator_os_archetype_var, ('Balanced Starter', 'Rushdown', 'Zoner', 'Grappler', 'Anime Air-Dasher', 'Boss Prototype', 'Custom')),
            ('complexity', self.creator_os_complexity_var, ('Beginner', 'Intermediate', 'Advanced', 'Boss/Experimental')),
            ('visual style', self.creator_os_style_var, ('Arcade', 'Anime', 'Street', 'Retro', 'Dark Fantasy', 'Sci-Fi', 'Cartoon', 'Custom')),
        ]
        for i, (label, var, values) in enumerate(rows):
            ttk.Label(profile, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=2)
            ttk.Combobox(profile, textvariable=var, values=values, width=24, state='readonly').grid(row=i, column=1, sticky='w', padx=2, pady=2)

        autopilot = ttk.LabelFrame(left, text='One-click heavy lifting', padding=(6, 6))
        autopilot.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(autopilot, text='One-Click Creator OS Autopilot', command=self.creator_os_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(autopilot, text='Build Creator OS Release ZIP', command=self.creator_os_release_zip_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(autopilot, text='Write Character Blueprint', command=self.creator_os_blueprint_ui).grid(row=2, column=0, sticky='ew', pady=2)

        reports = ttk.LabelFrame(left, text='No-code reports', padding=(6, 6))
        reports.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(reports, text='Export Frame Data Sheet', command=self.creator_os_frame_data_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Export Input Cheatsheet', command=self.creator_os_inputs_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Build Combo Routes', command=self.creator_os_combo_routes_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Write Balance Report', command=self.creator_os_balance_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Write Asset Shopping List', command=self.creator_os_asset_list_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Run Release Quality Gate', command=self.creator_os_quality_gate_ui).grid(row=5, column=0, sticky='ew', pady=2)

        docs = ttk.LabelFrame(left, text='Beginner docs', padding=(6, 6))
        docs.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(docs, text='Write Beginner Lessons', command=self.creator_os_lessons_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(docs, text='Write Project Wiki', command=self.creator_os_wiki_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(docs, text='Write Auto-Code Cookbook', command=self.creator_os_codebook_ui).grid(row=2, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=44, height=8, font=('Consolas', 9), state='disabled')
        note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self.creator_os_note = note
        self.set_text(self.creator_os_note, 'Best beginner route: One-Click Creator OS Autopilot → Project Wiki → replace art/sounds → Animation Player → CLSN Editor → Frame Data/Balance → Quality Gate → Release ZIP.')

        right = ttk.Frame(os_frame, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.creator_os_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.creator_os_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.creator_os_output.xview)
        self.creator_os_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.creator_os_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(os_frame, text='Creator OS')
        self.set_text(self.creator_os_output, 'Open/create a character folder, choose a creative profile, then run One-Click Creator OS Autopilot. It builds the docs/reports/checklists around the project so non-coders can focus on the fun parts.')

    def _build_factory_ultra_tab(self):
        ultra = ttk.Frame(self.notebook)
        self.factory_ultra_frame = ultra
        ultra.columnconfigure(1, weight=1)
        ultra.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(ultra, text=f'Factory Ultra / No-Code Production HQ v{FACTORY_ULTRA_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(header, text=(
            'A higher-level production hub for non-coders: snapshots, dashboards, frame data, balance review, asset usage, cancel/state flow, input maps, move cards, task boards, AI tuning, and release readiness.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(ultra, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click production', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Ultra Production Pass', command=self.ultra_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Create Safety Snapshot', command=self.ultra_snapshot_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Build Ultra Release ZIP', command=self.ultra_release_zip_ui).grid(row=2, column=0, sticky='ew', pady=2)

        reports = ttk.LabelFrame(left, text='Beginner reports', padding=(6, 6))
        reports.grid(row=1, column=0, sticky='ew', pady=(8,0))
        ttk.Button(reports, text='Ultra Dashboard', command=self.ultra_dashboard_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Beginner Task Board', command=self.ultra_task_board_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Production Bible', command=self.ultra_bible_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Feature Switchboard', command=self.ultra_switchboard_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Release Readiness', command=self.ultra_readiness_ui).grid(row=4, column=0, sticky='ew', pady=2)

        labs = ttk.LabelFrame(left, text='No-code tuning labs', padding=(6, 6))
        labs.grid(row=2, column=0, sticky='ew', pady=(8,0))
        ttk.Button(labs, text='Frame Data Lab', command=self.ultra_frame_data_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Balance Lab', command=self.ultra_balance_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Cancel / State Flow Lab', command=self.ultra_cancel_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Asset Usage Lab', command=self.ultra_assets_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='Sprite Axis Lab', command=self.ultra_axis_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(labs, text='AI Tuning Lab', command=self.ultra_ai_ui).grid(row=5, column=0, sticky='ew', pady=2)

        creator = ttk.LabelFrame(left, text='Creator-facing helpers', padding=(6, 6))
        creator.grid(row=3, column=0, sticky='ew', pady=(8,0))
        ttk.Button(creator, text='Move Cards HTML', command=self.ultra_move_cards_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(creator, text='Input Map Assistant', command=self.ultra_input_map_ui).grid(row=1, column=0, sticky='ew', pady=2)

        right = ttk.Frame(ultra, padding=(0, 0, 6, 6))
        right.grid(row=1, column=1, sticky='nsew')
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.factory_ultra_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        sy = ttk.Scrollbar(right, orient='vertical', command=self.factory_ultra_output.yview)
        sx = ttk.Scrollbar(right, orient='horizontal', command=self.factory_ultra_output.xview)
        self.factory_ultra_output.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.factory_ultra_output.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.notebook.add(ultra, text='Factory Ultra')
        self.set_text(self.factory_ultra_output, 'Best route for beginners: Create/New Character → One-Click Ultra Production Pass → replace art/sound → Animation Player + CLSN Editor → Frame Data/Balance/Asset labs → Build Ultra Release ZIP.')

    def _build_quality_lab_tab(self):
        ql = ttk.Frame(self.notebook)
        self.quality_lab_frame = ql
        ql.columnconfigure(1, weight=1)
        ql.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(ql, text='Quality Lab: beginner-safe audit, polish, and asset handoff', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        header.columnconfigure(0, weight=1)
        intro = (
            'Quality Lab is the polish/repair layer: it checks commands, states, AIR actions, SFF sprite refs, SND sound refs, '
            'HitDef tuning, timing, and beginner next steps. It writes reports, asset-swap packs, backups, move cards, and auto-CLSN suggestions '
            'without forcing a non-coder to edit raw CMD/CNS/AIR by hand.'
        )
        ttk.Label(header, text=intro, wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(ql, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        main = ttk.LabelFrame(left, text='One-click / no-code quality operations', padding=(6, 6))
        main.grid(row=0, column=0, sticky='ew')
        ttk.Button(main, text='One-Click Quality Lab Pass', command=self.quality_lab_one_click_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Advanced Audit / Reference Matrix', command=self.quality_lab_audit_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Searchable HTML Project Index', command=self.quality_lab_index_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Beginner Fix Plan', command=self.quality_lab_fix_plan_ui).grid(row=3, column=0, sticky='ew', pady=2)

        author = ttk.LabelFrame(left, text='Creator-facing reports', padding=(6, 6))
        author.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(author, text='Write Move Cards', command=self.quality_lab_move_cards_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(author, text='Animation Timing Sheet', command=self.quality_lab_timing_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(author, text='Asset Swap Pack', command=self.quality_lab_asset_swap_ui).grid(row=2, column=0, sticky='ew', pady=2)

        auto = ttk.LabelFrame(left, text='Automatic hitbox assistance', padding=(6, 6))
        auto.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self.quality_lab_clsn_padding_var = tk.StringVar(value='2')
        ttk.Label(auto, text='alpha padding').grid(row=0, column=0, sticky='e', padx=2)
        ttk.Entry(auto, textvariable=self.quality_lab_clsn_padding_var, width=8).grid(row=0, column=1, sticky='w', padx=2)
        ttk.Button(auto, text='Generate Alpha CLSN Suggestions', command=self.quality_lab_alpha_clsn_ui).grid(row=1, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(auto, text='Create AIR Copy With Auto Body CLSN', command=self.quality_lab_alpha_copy_ui).grid(row=2, column=0, columnspan=2, sticky='ew', pady=2)

        safety = ttk.LabelFrame(left, text='Safety', padding=(6, 6))
        safety.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(safety, text='Backup + Restore Bundle', command=self.quality_lab_backup_ui).grid(row=0, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=46, height=10, font=('Consolas', 9), state='disabled')
        note.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        self.quality_lab_note = note
        self.set_text(self.quality_lab_note, 'The one-click pass is intentionally safe: it writes reports, copies, exports, and suggestions. It does not overwrite your main AIR with generated hitboxes unless you manually use the copy/replacement workflow.')

        right = ttk.Frame(ql)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.quality_lab_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.quality_lab_output.yview)
        self.quality_lab_output.configure(yscrollcommand=y.set)
        self.quality_lab_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(ql, text='Quality Lab')
        self.set_text(self.quality_lab_output, 'Open a character folder, then run One-Click Quality Lab Pass. Use the generated WHAT_TO_FIX_NEXT.md before manually editing code.')

    def _quality_lab_root(self):
        root = self._plus_get_project_root()
        if not root:
            return None
        return root

    def _quality_lab_padding(self):
        try:
            return int(self.quality_lab_clsn_padding_var.get().strip())
        except Exception:
            return 2

    def _quality_lab_run(self, label, func, *args, **kwargs):
        root = self._quality_lab_root()
        if not root:
            return
        try:
            result = func(root, *args, **kwargs)
            self.reload_project()
            self.set_text(self.quality_lab_output, result.to_text())
            self.notebook.select(self.quality_lab_frame)
            self.status_var.set(label)
        except Exception as exc:
            messagebox.showerror(label, str(exc))

    def quality_lab_one_click_ui(self):
        self._quality_lab_run('Quality Lab pass complete.', run_quality_lab_pass)

    def quality_lab_audit_ui(self):
        self._quality_lab_run('Advanced audit written.', write_advanced_audit)

    def quality_lab_index_ui(self):
        self._quality_lab_run('Searchable index written.', write_searchable_html_index)

    def quality_lab_move_cards_ui(self):
        self._quality_lab_run('Move cards written.', write_move_cards)

    def quality_lab_alpha_clsn_ui(self):
        self._quality_lab_run('Alpha CLSN suggestions written.', build_alpha_clsn_suggestions, padding=self._quality_lab_padding())

    def quality_lab_alpha_copy_ui(self):
        self._quality_lab_run('AIR copy with generated body CLSN written.', write_alpha_clsn_air_copy, padding=self._quality_lab_padding())

    def quality_lab_timing_ui(self):
        self._quality_lab_run('Animation timing sheet written.', write_animation_timing_sheet)

    def quality_lab_asset_swap_ui(self):
        self._quality_lab_run('Asset swap pack created.', create_asset_swap_pack)

    def quality_lab_backup_ui(self):
        self._quality_lab_run('Backup/restore bundle created.', create_backup_restore_bundle)

    def quality_lab_fix_plan_ui(self):
        self._quality_lab_run('Beginner fix plan written.', write_beginner_fix_plan)



    def _build_creator_suite_tab(self):
        suite = ttk.Frame(self.notebook)
        self.creator_suite_frame = suite
        suite.columnconfigure(1, weight=1)
        suite.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(suite, text=f'Creator Suite / No-Code Production Hub v{CREATOR_SUITE_VERSION}', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        ttk.Label(header, text=(
            'Creator Suite is the beginner-facing production layer: choose a character DNA/profile, run AutoPilot, then use reports, tuning sheets, art task boards, snapshots, and handoff packs instead of manually touching code first.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(suite, padding=(6, 0))
        left.grid(row=1, column=0, sticky='nsw')

        profile = ttk.LabelFrame(left, text='Creative profile', padding=(6, 6))
        profile.grid(row=0, column=0, sticky='ew')
        self.creator_suite_archetype_var = tk.StringVar(value='Balanced Starter')
        self.creator_suite_experience_var = tk.StringVar(value='Beginner')
        self.creator_suite_buttons_var = tk.StringVar(value='Six button')
        self.creator_suite_power_var = tk.StringVar(value='Standard meter')
        rows = [
            ('Archetype', self.creator_suite_archetype_var, ('Balanced Starter', 'Rushdown', 'Zoner', 'Grappler', 'Anime Movement', 'Boss Prototype', 'Full Creator')),
            ('Experience', self.creator_suite_experience_var, ('Beginner', 'Intermediate', 'Advanced')),
            ('Buttons', self.creator_suite_buttons_var, ('Six button', 'Four button', 'Simple / two button')),
            ('Power', self.creator_suite_power_var, ('Standard meter', 'EX heavy', 'Super heavy', 'No meter')),
        ]
        for i, (label, var, values) in enumerate(rows):
            ttk.Label(profile, text=label).grid(row=i, column=0, sticky='e', padx=2, pady=2)
            ttk.Combobox(profile, textvariable=var, values=values, width=28, state='readonly').grid(row=i, column=1, sticky='w', padx=2, pady=2)

        main = ttk.LabelFrame(left, text='One-click beginner workflow', padding=(6, 6))
        main.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(main, text='One-Click Creator AutoPilot', command=self.creator_suite_autopilot_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Creator Suite Profile Report', command=self.creator_suite_profile_report_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Character DNA Profile', command=self.creator_suite_dna_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Creator Dashboard', command=self.creator_suite_dashboard_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(main, text='Time Machine Snapshot', command=self.creator_suite_snapshot_ui).grid(row=4, column=0, sticky='ew', pady=2)

        reports = ttk.LabelFrame(left, text='Reports / task boards', padding=(6, 6))
        reports.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(reports, text='Asset Library / Organizer', command=self.creator_suite_asset_library_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Move Lab / Frame Sheet', command=self.creator_suite_move_lab_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Combo Tree', command=self.creator_suite_combo_tree_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Art Task Board', command=self.creator_suite_art_board_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Artist / Sound Handoff Pack', command=self.creator_suite_handoff_ui).grid(row=4, column=0, sticky='ew', pady=2)
        ttk.Button(reports, text='Creator Indexes', command=self.creator_suite_indexes_ui).grid(row=5, column=0, sticky='ew', pady=2)

        tuning = ttk.LabelFrame(left, text='No-code tuning', padding=(6, 6))
        tuning.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(tuning, text='Install Beginner Tuning Panel', command=self.creator_suite_tuning_panel_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(tuning, text='Export HitDef Tuning Sheet', command=self.creator_suite_export_hitdef_tuning_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(tuning, text='Apply HitDef Tuning Sheet', command=self.creator_suite_apply_hitdef_tuning_ui).grid(row=2, column=0, sticky='ew', pady=2)

        release = ttk.LabelFrame(left, text='Teaching / release', padding=(6, 6))
        release.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(release, text='Training Pack', command=self.creator_suite_training_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(release, text='Final QA Release Plan', command=self.creator_suite_final_qa_ui).grid(row=1, column=0, sticky='ew', pady=2)

        note = tk.Text(left, wrap='word', width=46, height=8, font=('Consolas', 9), state='disabled')
        note.grid(row=5, column=0, sticky='ew', pady=(6, 0))
        self.creator_suite_note = note
        self.set_text(self.creator_suite_note, 'Best beginner route: One-Click Creator AutoPilot → Creator Dashboard → Art Task Board / Handoff Pack → Animation Player → CLSN Editor → HitDef Tuning Sheet → Final QA.')

        right = ttk.Frame(suite)
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 6), pady=(0, 6))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.creator_suite_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.creator_suite_output.yview)
        self.creator_suite_output.configure(yscrollcommand=y.set)
        self.creator_suite_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(suite, text='Creator Suite')
        self.set_text(self.creator_suite_output, 'Open/create a character folder. Choose a creative profile, then run One-Click Creator AutoPilot. Most outputs are docs, CSVs, and backups so non-coders can stay in the creative lane.')

    def _creator_suite_root(self):
        if hasattr(self, '_max_root_or_choose'):
            return self._max_root_or_choose()
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _creator_suite_profile(self):
        arch = self.creator_suite_archetype_var.get().strip() if hasattr(self, 'creator_suite_archetype_var') else 'Balanced Starter'
        exp = self.creator_suite_experience_var.get().strip() if hasattr(self, 'creator_suite_experience_var') else 'Beginner'
        buttons = self.creator_suite_buttons_var.get().strip() if hasattr(self, 'creator_suite_buttons_var') else 'Six button'
        power = self.creator_suite_power_var.get().strip() if hasattr(self, 'creator_suite_power_var') else 'Standard meter'
        return arch, exp, buttons, power

    def _creator_suite_show_result(self, result, title='Creator Suite'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.creator_suite_output, text)
        if hasattr(self, 'creator_suite_frame'):
            self.notebook.select(self.creator_suite_frame)
        self.status_var.set(title)

    def _creator_suite_run(self, label, func, *args, confirm=None, **kwargs):
        root = self._creator_suite_root()
        if not root:
            return
        if confirm and not messagebox.askyesno(label, confirm):
            return
        try:
            result = func(root, *args, **kwargs)
            self.reload_project()
            self._creator_suite_show_result(result, label)
        except Exception as exc:
            messagebox.showerror(label + ' failed', str(exc))

    def creator_suite_autopilot_ui(self):
        arch, exp, buttons, power = self._creator_suite_profile()
        self._creator_suite_run('Creator AutoPilot finished', one_click_creator_autopilot, arch, exp, buttons, power)

    def creator_suite_profile_report_ui(self):
        self._creator_suite_run('Creator Suite profile report written', creator_suite_profile_report)

    def creator_suite_dna_ui(self):
        arch, exp, buttons, power = self._creator_suite_profile()
        self._creator_suite_run('Character DNA written', write_character_dna_profile, arch, exp, buttons, power)

    def creator_suite_asset_library_ui(self):
        self._creator_suite_run('Asset library written', write_asset_library)

    def creator_suite_move_lab_ui(self):
        self._creator_suite_run('Move lab written', write_move_lab)

    def creator_suite_combo_tree_ui(self):
        self._creator_suite_run('Combo tree written', write_combo_tree)

    def creator_suite_art_board_ui(self):
        self._creator_suite_run('Art task board written', write_art_task_board)

    def creator_suite_tuning_panel_ui(self):
        self._creator_suite_run('Beginner tuning panel installed', install_beginner_tuning_panel)

    def creator_suite_export_hitdef_tuning_ui(self):
        self._creator_suite_run('HitDef tuning sheet exported', export_hitdef_tuning_sheet)

    def creator_suite_apply_hitdef_tuning_ui(self):
        self._creator_suite_run('HitDef tuning sheet applied', apply_hitdef_tuning_sheet, confirm='This applies values from reports/hitdef_tuning_sheet.csv back into CMD/CNS/ST HitDef blocks and writes backups first. Continue?')

    def creator_suite_snapshot_ui(self):
        self._creator_suite_run('Time machine snapshot created', make_project_time_machine_snapshot)

    def creator_suite_dashboard_ui(self):
        self._creator_suite_run('Creator dashboard written', write_suite_creator_dashboard)

    def creator_suite_final_qa_ui(self):
        self._creator_suite_run('Final QA release plan written', write_final_qa_release_plan)

    def creator_suite_training_ui(self):
        self._creator_suite_run('Training pack written', write_training_pack)

    def creator_suite_indexes_ui(self):
        self._creator_suite_run('Creator indexes written', write_creator_indexes)

    def creator_suite_handoff_ui(self):
        self._creator_suite_run('Artist / sound handoff pack written', write_artist_handoff_pack)


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

    def _vf_int(self, var, default=0):
        try:
            return int(str(var.get()).strip())
        except Exception:
            return int(default)

    def _vf_float(self, var, default=0.0):
        try:
            return float(str(var.get()).strip())
        except Exception:
            return float(default)

    def _vf_require_project(self) -> bool:
        if not self.project_root:
            messagebox.showinfo('No project', 'Open or create a character folder first.')
            return False
        return True

    def _vf_recent_path(self) -> Path:
        return Path.home() / '.mugenforge_studio_recent.json'

    def _vf_load_recent_paths(self):
        try:
            data = json.loads(self._vf_recent_path().read_text(encoding='utf-8'))
            return [Path(p) for p in data if p]
        except Exception:
            return []

    def _vf_save_recent_paths(self, paths):
        try:
            data = []
            seen = set()
            for p in paths:
                s = str(Path(p))
                if s not in seen:
                    seen.add(s)
                    data.append(s)
            self._vf_recent_path().write_text(json.dumps(data[:12], indent=2), encoding='utf-8')
        except Exception:
            pass

    def _vf_note_recent(self, root: Path):
        paths = [Path(root)] + [p for p in self._vf_load_recent_paths() if Path(p) != Path(root)]
        self._vf_save_recent_paths(paths)
        if hasattr(self, 'vf_recent_list'):
            self._vf_refresh_recent_list()
        if hasattr(self, 'vf_current_project_var'):
            self.vf_current_project_var.set(str(root))

    def _vf_refresh_recent_list(self):
        if not hasattr(self, 'vf_recent_list'):
            return
        self.vf_recent_list.delete(0, 'end')
        for p in self._vf_load_recent_paths():
            label = str(p)
            if not p.exists():
                label += '  [missing]'
            self.vf_recent_list.insert('end', label)

    def _vf_open_recent_selected(self):
        sel = self.vf_recent_list.curselection()
        if not sel:
            messagebox.showinfo('Open recent', 'Select a recent project first.')
            return
        raw = self.vf_recent_list.get(sel[0]).replace('  [missing]', '')
        path = Path(raw)
        if not path.exists():
            messagebox.showerror('Missing project', str(path))
            return
        self.load_project(path)

    def _build_visual_forge_home_tab(self):
        home = ttk.Frame(self.notebook)
        self.vf_home_frame = home
        home.columnconfigure(1, weight=1)
        home.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(home, text=f'Project Home / Wizard Mode — Visual Forge v{VISUAL_FORGE_VERSION}', padding=(10, 8))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Start here. Visual Forge turns MugenForge into a guided no-code workflow: create a project, scaffold moves, edit timing visually, align offsets, place sounds, import legacy characters, and keep safe backups.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        self.vf_current_project_var = tk.StringVar(value='No project loaded.')
        ttk.Label(header, textvariable=self.vf_current_project_var).grid(row=1, column=0, sticky='w', pady=(6, 0))

        left = ttk.Frame(home, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        actions = ttk.LabelFrame(left, text='Start', padding=(8, 8))
        actions.grid(row=0, column=0, sticky='ew')
        ttk.Button(actions, text='Open Character Folder', command=self.open_folder).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Create From Wizard', command=self.vf_create_project_from_wizard).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Quick Start Current Project', command=self.vf_quick_start_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Tutorials / Beginner Workflow', command=self.vf_tutorials_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Import Existing Character', command=self.vf_import_legacy_from_home).grid(row=4, column=0, sticky='ew', pady=2)

        recent = ttk.LabelFrame(left, text='Open Recent', padding=(8, 8))
        recent.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.vf_recent_list = tk.Listbox(recent, width=46, height=8, font=('Consolas', 9), exportselection=False)
        self.vf_recent_list.grid(row=0, column=0, sticky='ew')
        ttk.Button(recent, text='Open Selected', command=self._vf_open_recent_selected).grid(row=1, column=0, sticky='ew', pady=(4, 2))
        ttk.Button(recent, text='Refresh Recent List', command=self._vf_refresh_recent_list).grid(row=2, column=0, sticky='ew', pady=2)

        tools = ttk.LabelFrame(left, text='Project Tools', padding=(8, 8))
        tools.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(tools, text='Write Home Docs', command=self.vf_write_home_docs_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Install Templates / Plugins', command=self.vf_install_templates_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Write SFF2 Bridge Pack', command=self.vf_sff2_pack_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Create Backup Snapshot', command=self.vf_backup_snapshot_ui).grid(row=3, column=0, sticky='ew', pady=2)

        right = ttk.Frame(home, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        wizard = ttk.LabelFrame(right, text='New Character Wizard', padding=(8, 8))
        wizard.grid(row=0, column=0, sticky='ew')
        self.vf_wizard_vars = {}
        rows = [
            ('parent', str(Path.cwd())), ('name', 'new_character'), ('author', 'MugenForge Creator'),
            ('project_type', 'character'), ('template', 'Balanced Starter'), ('archetype', 'Balanced Arcade Fighter'),
            ('life', '1000'), ('attack', '100'), ('defence', '100'), ('power_style', 'classic'),
        ]
        for idx, (key, value) in enumerate(rows):
            ttk.Label(wizard, text=key).grid(row=idx//2, column=(idx%2)*2, sticky='e', padx=(2, 4), pady=2)
            var = tk.StringVar(value=value)
            self.vf_wizard_vars[key] = var
            if key == 'parent':
                entry = ttk.Entry(wizard, textvariable=var, width=52)
                entry.grid(row=idx//2, column=(idx%2)*2+1, sticky='ew', padx=(0, 6), pady=2)
                ttk.Button(wizard, text='Choose', command=self.vf_choose_wizard_parent).grid(row=idx//2, column=4, sticky='w', pady=2)
            elif key in {'project_type', 'template', 'archetype', 'power_style'}:
                values = {
                    'project_type': ('character', 'stage metadata'),
                    'template': ('Balanced Starter', 'Rushdown Starter', 'Projectile Zoner Starter', 'Grappler Starter', 'Anime Mobility Starter', 'Legacy Import'),
                    'archetype': ('Balanced Arcade Fighter', 'Rushdown Combo Fighter', 'Projectile Zoner Fighter', 'Grappler Fighter', 'Anime Air Mobility Fighter', 'Boss / Flashy Character'),
                    'power_style': ('classic', 'EX meter', 'super meter starter', 'none'),
                }[key]
                ttk.Combobox(wizard, textvariable=var, values=values, state='readonly', width=34).grid(row=idx//2, column=(idx%2)*2+1, sticky='w', padx=(0, 8), pady=2)
            else:
                ttk.Entry(wizard, textvariable=var, width=36).grid(row=idx//2, column=(idx%2)*2+1, sticky='w', padx=(0, 8), pady=2)
        wizard.columnconfigure(1, weight=1)
        self.vf_wizard_install_pack_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(wizard, text='Install Beginner Pack after creation', variable=self.vf_wizard_install_pack_var).grid(row=5, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(wizard, text='Create Project', command=self.vf_create_project_from_wizard).grid(row=5, column=2, sticky='w', pady=(6, 0))

        note = ttk.LabelFrame(right, text='What Visual Forge will do', padding=(8, 6))
        note.grid(row=1, column=0, sticky='ew', pady=(8, 8))
        ttk.Label(note, text=(
            'The wizard creates clean M.U.G.E.N starter files, writes a dashboard and beginner guide, prepares data-only templates/plugins, and optionally installs starter move scaffolds. It keeps SFF/SND work conservative and does not claim arbitrary SFF2 binary editing.'
        ), wraplength=900, justify='left').grid(row=0, column=0, sticky='ew')

        self.vf_home_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_home_output.yview)
        self.vf_home_output.configure(yscrollcommand=y.set)
        self.vf_home_output.grid(row=2, column=0, sticky='nsew')
        y.grid(row=2, column=1, sticky='ns')
        self.notebook.add(home, text='Project Home')
        self._vf_refresh_recent_list()
        self.set_text(self.vf_home_output, 'Welcome to Visual Forge. Create a project with the wizard, open a recent project, or run Quick Start on an existing character folder.')

    def vf_choose_wizard_parent(self):
        folder = filedialog.askdirectory(title='Choose parent folder for the new project')
        if folder:
            self.vf_wizard_vars['parent'].set(folder)

    def _vf_wizard_spec(self) -> BeginnerProjectSpec:
        v = self.vf_wizard_vars
        return BeginnerProjectSpec(
            name=v['name'].get().strip() or 'new_character',
            author=v['author'].get().strip() or 'MugenForge Creator',
            project_type=v['project_type'].get().strip() or 'character',
            template=v['template'].get().strip() or 'Balanced Starter',
            archetype=v['archetype'].get().strip() or 'Balanced Arcade Fighter',
            life=self._vf_int(v['life'], 1000),
            attack=self._vf_int(v['attack'], 100),
            defence=self._vf_int(v['defence'], 100),
            power_style=v['power_style'].get().strip() or 'classic',
        )

    def vf_create_project_from_wizard(self):
        try:
            parent = Path(self.vf_wizard_vars['parent'].get().strip()).expanduser()
            if not str(parent):
                messagebox.showinfo('Parent folder needed', 'Choose a parent folder first.')
                return
            spec = self._vf_wizard_spec()
            result = create_visual_forge_project(parent, spec, install_pack=bool(self.vf_wizard_install_pack_var.get()))
            self.load_project(parent / spec.safe_name)
            self.set_text(self.vf_home_output, result.to_text())
            self.notebook.select(self.vf_home_frame)
            self.status_var.set(f'Visual Forge project created: {spec.safe_name}')
        except Exception as exc:
            messagebox.showerror('Wizard failed', str(exc))
            if self.project_root:
                log_error(self.project_root, 'Visual Forge wizard', exc)

    def vf_quick_start_ui(self):
        if not self._vf_require_project():
            return
        try:
            result = quick_start_pass(self.project_root)
            self.set_text(self.vf_home_output, result.to_text())
            self.status_var.set('Visual Forge Quick Start finished')
        except Exception as exc:
            messagebox.showerror('Quick Start failed', str(exc))
            log_error(self.project_root, 'Visual Forge Quick Start', exc)

    def vf_tutorials_ui(self):
        text = '''Visual Forge beginner path
============================

1. Project Home: create/open a project and run Quick Start.
2. Move Composer 2.0: scaffold a move package from creative choices.
3. Visual Timeline: adjust AIR frame timing and inspect hit/sound events.
4. Sprite Offset / Axis Editor: drag offsets into place. This edits AIR frame offsets, not arbitrary SFF2 binary axes.
5. Sound Cue Editor: add PlaySnd triggers to a chosen StateDef.
6. Training Debug: install the in-engine clipboard overlay for testing.
7. Backups / Logs: create snapshots before big changes.
8. Quality Lab / Run Test: validate and playtest.

Honest limits stay in force: generated code is scaffolding, balance/frame reports are estimates, and full mature SFF2 extraction/rebuild is not implemented.
'''
        self.set_text(self.vf_home_output, text)
        self.notebook.select(self.vf_home_frame)

    def vf_write_home_docs_ui(self):
        if not self._vf_require_project():
            return
        try:
            result = write_beginner_project_home(self.project_root, BeginnerProjectSpec(name=self.project_root.name))
            self.set_text(self.vf_home_output, result.to_text())
            self.status_var.set('Visual Forge home docs written')
        except Exception as exc:
            messagebox.showerror('Home docs failed', str(exc))
            log_error(self.project_root, 'Write Visual Forge home docs', exc)

    def vf_import_legacy_from_home(self):
        self.notebook.select(self.vf_migration_frame)

    def _build_visual_timeline_editor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_timeline_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Real Visual Move-Timeline Editor', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Source-backed AIR timeline. Drag a frame tile left/right to preview timing changes, then save to update the AIR frame ticks with a backup. Hitboxes and sound/HitDef events are drawn from parsed AIR/CNS/CMD data.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')

        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Button(left, text='Refresh From Project', command=self.vf_refresh_timeline_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(left, text='Export Timeline Manifest', command=self.vf_timeline_export_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Label(left, text='Action').grid(row=2, column=0, sticky='w', pady=(8, 2))
        self.vf_timeline_action_var = tk.StringVar()
        self.vf_timeline_action_combo = ttk.Combobox(left, textvariable=self.vf_timeline_action_var, state='readonly', width=34)
        self.vf_timeline_action_combo.grid(row=3, column=0, sticky='ew')
        self.vf_timeline_action_combo.bind('<<ComboboxSelected>>', self.vf_on_timeline_action)
        self.vf_timeline_info = tk.Text(left, wrap='word', width=38, height=15, font=('Consolas', 9), state='disabled')
        self.vf_timeline_info.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        edit = ttk.LabelFrame(left, text='Selected frame', padding=(6, 6))
        edit.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        self.vf_timeline_frame_index_var = tk.StringVar(value='')
        self.vf_timeline_ticks_var = tk.StringVar(value='')
        ttk.Label(edit, text='Frame index').grid(row=0, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.vf_timeline_frame_index_var, width=8, state='readonly').grid(row=0, column=1, sticky='w')
        ttk.Label(edit, text='Ticks').grid(row=1, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.vf_timeline_ticks_var, width=8).grid(row=1, column=1, sticky='w')
        ttk.Button(edit, text='Save Ticks to AIR (.bak)', command=self.vf_timeline_save_ticks).grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        play = ttk.LabelFrame(left, text='Preview', padding=(6, 6))
        play.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(play, text='Play Timeline', command=self.vf_timeline_play).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(play, text='Pause', command=self.vf_timeline_pause).grid(row=1, column=0, sticky='ew', pady=2)

        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_timeline_canvas = tk.Canvas(right, bg='white', height=520, scrollregion=(0, 0, 2400, 700))
        x = ttk.Scrollbar(right, orient='horizontal', command=self.vf_timeline_canvas.xview)
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_timeline_canvas.yview)
        self.vf_timeline_canvas.configure(xscrollcommand=x.set, yscrollcommand=y.set)
        self.vf_timeline_canvas.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        self.vf_timeline_canvas.bind('<ButtonPress-1>', self.vf_timeline_press)
        self.vf_timeline_canvas.bind('<B1-Motion>', self.vf_timeline_drag)
        self.vf_timeline_canvas.bind('<ButtonRelease-1>', self.vf_timeline_release)
        self.vf_timeline_model = {}
        self.vf_timeline_frame_boxes = {}
        self.vf_timeline_preview_ticks = {}
        self.vf_timeline_drag_data = None
        self.vf_timeline_play_after = None
        self.vf_timeline_play_idx = 0
        self.notebook.add(tab, text='Visual Timeline')

    def vf_refresh_timeline_ui(self):
        if not self._vf_require_project():
            return
        try:
            self.vf_timeline_model = build_visual_timeline_model(self.project_root)
            actions = self.vf_timeline_model.get('actions', [])
            values = [f"{a.get('action')} :: {a.get('label') or 'action'} ({len(a.get('frames', []))} frames)" for a in actions]
            self.vf_timeline_action_combo.configure(values=values)
            if values:
                self.vf_timeline_action_var.set(values[0])
            self.vf_timeline_preview_ticks = {}
            self.vf_draw_timeline()
            self.status_var.set('Visual timeline refreshed')
        except Exception as exc:
            messagebox.showerror('Timeline refresh failed', str(exc))
            log_error(self.project_root, 'Visual Timeline refresh', exc)

    def _vf_selected_timeline_action(self):
        raw = self.vf_timeline_action_var.get()
        if not raw:
            return None
        try:
            action_no = int(raw.split('::', 1)[0].strip())
        except Exception:
            return None
        for action in self.vf_timeline_model.get('actions', []):
            if int(action.get('action', -999999)) == action_no:
                return action
        return None

    def vf_on_timeline_action(self, event=None):
        self.vf_draw_timeline()

    def vf_draw_timeline(self, highlight_index=None):
        c = self.vf_timeline_canvas
        c.delete('all')
        self.vf_timeline_frame_boxes = {}
        action = self._vf_selected_timeline_action()
        if not action:
            c.create_text(30, 30, anchor='nw', text='Open a project and click Refresh From Project.', font=('Consolas', 12))
            return
        frames = action.get('frames', [])
        events = action.get('events', [])
        c.create_text(20, 18, anchor='nw', text=f"Action {action.get('action')} — {action.get('label') or ''} | {len(frames)} frame(s), {action.get('total_ticks')} tick(s)", font=('Consolas', 12, 'bold'))
        x = 20
        y = 80
        row_h = 112
        scale = 8
        for frame in frames:
            idx = int(frame.get('index', 0))
            base_ticks = int(frame.get('ticks', 1))
            ticks = int(self.vf_timeline_preview_ticks.get((int(action.get('action')), idx), base_ticks))
            w = max(38, ticks * scale)
            fill = '#fff2cc' if frame.get('has_hitbox') else '#d9ead3' if frame.get('has_bodybox') else '#eeeeee'
            outline = '#cc0000' if highlight_index == idx else '#333333'
            rect = c.create_rectangle(x, y, x + w, y + row_h, fill=fill, outline=outline, width=3 if highlight_index == idx else 1, tags=('vf_frame', f'frame:{idx}'))
            self.vf_timeline_frame_boxes[idx] = (x, y, x + w, y + row_h, frame)
            c.create_text(x + 6, y + 6, anchor='nw', text=f"#{idx+1}\n{frame.get('group')},{frame.get('image')}\n{ticks}t", font=('Consolas', 9), tags=(f'frame:{idx}',))
            if frame.get('has_hitbox'):
                c.create_rectangle(x + 5, y + row_h - 25, x + w - 5, y + row_h - 10, outline='#cc0000', tags=(f'frame:{idx}',))
                c.create_text(x + 8, y + row_h - 27, anchor='sw', text='CLSN1', fill='#cc0000', font=('Consolas', 8), tags=(f'frame:{idx}',))
            if frame.get('has_bodybox'):
                c.create_rectangle(x + 9, y + row_h - 48, x + w - 9, y + row_h - 32, outline='#38761d', tags=(f'frame:{idx}',))
                c.create_text(x + 10, y + row_h - 50, anchor='sw', text='CLSN2', fill='#38761d', font=('Consolas', 8), tags=(f'frame:{idx}',))
            frame_events = [e for e in events if int(e.get('frame', 0) or 0) == idx + 1]
            ey = y + row_h + 14
            for ev in frame_events[:4]:
                label = str(ev.get('event_type', 'event')).upper()
                c.create_oval(x + 5, ey, x + 15, ey + 10, fill='#6d9eeb', outline='')
                c.create_text(x + 20, ey - 1, anchor='nw', text=label, font=('Consolas', 8))
                ey += 14
            x += w + 12
        c.configure(scrollregion=(0, 0, max(1200, x + 40), 360))
        text_lines = [f"Action {action.get('action')} {action.get('label') or ''}", f"Frames: {len(frames)}", f"Total ticks: {action.get('total_ticks')} (~{action.get('estimated_seconds_at_60fps')} sec at 60fps)", '', 'Legend:', '- yellow = frame has CLSN1 attack box', '- green = frame has CLSN2 body box', '- blue markers = parsed code events']
        self.set_text(self.vf_timeline_info, '\n'.join(text_lines))

    def vf_timeline_press(self, event):
        action = self._vf_selected_timeline_action()
        if not action:
            return
        x = self.vf_timeline_canvas.canvasx(event.x)
        y = self.vf_timeline_canvas.canvasy(event.y)
        for idx, (x1, y1, x2, y2, frame) in self.vf_timeline_frame_boxes.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                ticks = int(self.vf_timeline_preview_ticks.get((int(action.get('action')), idx), frame.get('ticks', 1)))
                self.vf_timeline_drag_data = (int(action.get('action')), idx, x, ticks)
                self.vf_timeline_frame_index_var.set(str(idx))
                self.vf_timeline_ticks_var.set(str(ticks))
                self.vf_draw_timeline(highlight_index=idx)
                return

    def vf_timeline_drag(self, event):
        if not self.vf_timeline_drag_data:
            return
        action_no, idx, start_x, start_ticks = self.vf_timeline_drag_data
        x = self.vf_timeline_canvas.canvasx(event.x)
        delta = int(round((x - start_x) / 8.0))
        ticks = max(1, int(start_ticks) + delta)
        self.vf_timeline_preview_ticks[(action_no, idx)] = ticks
        self.vf_timeline_ticks_var.set(str(ticks))
        self.vf_draw_timeline(highlight_index=idx)

    def vf_timeline_release(self, event):
        self.vf_timeline_drag_data = None

    def vf_timeline_save_ticks(self):
        if not self._vf_require_project():
            return
        action = self._vf_selected_timeline_action()
        if not action:
            return
        idx = self._vf_int(self.vf_timeline_frame_index_var, -1)
        ticks = self._vf_int(self.vf_timeline_ticks_var, 1)
        if idx < 0:
            messagebox.showinfo('No frame selected', 'Click or drag a frame tile first.')
            return
        try:
            result = update_air_frame_ticks(self.project_root, int(action.get('action')), idx, ticks)
            self.set_text(self.vf_timeline_info, result.to_text())
            self.vf_refresh_timeline_ui()
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Save ticks failed', str(exc))
            log_error(self.project_root, 'Visual Timeline save ticks', exc)

    def vf_timeline_play(self):
        self.vf_timeline_pause()
        self.vf_timeline_play_idx = 0
        self._vf_timeline_play_step()

    def vf_timeline_pause(self):
        if getattr(self, 'vf_timeline_play_after', None):
            try:
                self.after_cancel(self.vf_timeline_play_after)
            except Exception:
                pass
        self.vf_timeline_play_after = None

    def _vf_timeline_play_step(self):
        action = self._vf_selected_timeline_action()
        if not action:
            return
        frames = action.get('frames', [])
        if not frames:
            return
        idx = self.vf_timeline_play_idx % len(frames)
        self.vf_draw_timeline(highlight_index=idx)
        ticks = int(frames[idx].get('ticks', 4) or 4)
        self.vf_timeline_play_idx += 1
        self.vf_timeline_play_after = self.after(max(60, int(ticks * 1000 / 60)), self._vf_timeline_play_step)

    def vf_timeline_export_ui(self):
        if not self._vf_require_project():
            return
        try:
            action = self._vf_selected_timeline_action()
            action_no = int(action.get('action')) if action else None
            result = write_visual_timeline_manifest(self.project_root, action_no)
            self.set_text(self.vf_timeline_info, result.to_text())
            self.status_var.set('Timeline manifest exported')
        except Exception as exc:
            messagebox.showerror('Timeline export failed', str(exc))
            log_error(self.project_root, 'Timeline export', exc)

    def _build_sprite_offset_axis_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_offset_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Sprite Offset / Axis Editor', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text=(
            'Drag the sprite preview to adjust AIR frame x/y offsets with coordinate display and snapping. Existing SFF axes are reference-only here; arbitrary SFF2 binary axis patching is not performed.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Button(left, text='Refresh Actions', command=self.vf_refresh_offset_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Label(left, text='Action').grid(row=1, column=0, sticky='w', pady=(8, 2))
        self.vf_offset_action_var = tk.StringVar()
        self.vf_offset_action_combo = ttk.Combobox(left, textvariable=self.vf_offset_action_var, state='readonly', width=34)
        self.vf_offset_action_combo.grid(row=2, column=0, sticky='ew')
        self.vf_offset_action_combo.bind('<<ComboboxSelected>>', self.vf_on_offset_action)
        ttk.Label(left, text='Frames').grid(row=3, column=0, sticky='w', pady=(8, 2))
        self.vf_offset_frame_list = tk.Listbox(left, width=38, height=10, font=('Consolas', 9), exportselection=False)
        self.vf_offset_frame_list.grid(row=4, column=0, sticky='ew')
        self.vf_offset_frame_list.bind('<<ListboxSelect>>', self.vf_on_offset_frame)
        edit = ttk.LabelFrame(left, text='Coordinates', padding=(6, 6))
        edit.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        self.vf_offset_x_var = tk.StringVar(value='0')
        self.vf_offset_y_var = tk.StringVar(value='0')
        self.vf_offset_snap_var = tk.StringVar(value='1')
        ttk.Label(edit, text='AIR x').grid(row=0, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.vf_offset_x_var, width=8).grid(row=0, column=1, sticky='w')
        ttk.Label(edit, text='AIR y').grid(row=1, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.vf_offset_y_var, width=8).grid(row=1, column=1, sticky='w')
        ttk.Label(edit, text='Snap').grid(row=2, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.vf_offset_snap_var, width=8).grid(row=2, column=1, sticky='w')
        ttk.Button(edit, text='Save Offset to AIR (.bak)', command=self.vf_save_offset_ui).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.vf_offset_info = tk.Text(left, wrap='word', width=38, height=9, font=('Consolas', 9), state='disabled')
        self.vf_offset_info.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_offset_canvas = tk.Canvas(right, bg='white', width=800, height=580)
        self.vf_offset_canvas.grid(row=0, column=0, sticky='nsew')
        self.vf_offset_canvas.bind('<ButtonPress-1>', self.vf_offset_canvas_press)
        self.vf_offset_canvas.bind('<B1-Motion>', self.vf_offset_canvas_drag)
        self.vf_offset_drag_data = None
        self.vf_offset_model = {}
        self.vf_offset_selected_frame = None
        self.notebook.add(tab, text='Offset / Axis')

    def vf_refresh_offset_ui(self):
        if not self._vf_require_project():
            return
        try:
            self.vf_offset_model = build_sprite_offset_model(self.project_root)
            values = [f"{a.get('action')} :: {a.get('label') or 'action'} ({len(a.get('frames', []))} frames)" for a in self.vf_offset_model.get('actions', [])]
            self.vf_offset_action_combo.configure(values=values)
            if values:
                self.vf_offset_action_var.set(values[0])
            self.vf_on_offset_action()
        except Exception as exc:
            messagebox.showerror('Offset refresh failed', str(exc))
            log_error(self.project_root, 'Offset refresh', exc)

    def _vf_selected_offset_action(self):
        raw = self.vf_offset_action_var.get()
        if not raw:
            return None
        try:
            action_no = int(raw.split('::', 1)[0].strip())
        except Exception:
            return None
        for action in self.vf_offset_model.get('actions', []):
            if int(action.get('action', -999999)) == action_no:
                return action
        return None

    def vf_on_offset_action(self, event=None):
        self.vf_offset_frame_list.delete(0, 'end')
        action = self._vf_selected_offset_action()
        if not action:
            self.vf_draw_offset_canvas()
            return
        for frame in action.get('frames', []):
            self.vf_offset_frame_list.insert('end', f"#{int(frame.get('index', 0))+1}  sprite {frame.get('group')},{frame.get('image')}  offset=({frame.get('offset_x')},{frame.get('offset_y')})")
        if action.get('frames'):
            self.vf_offset_frame_list.selection_set(0)
            self.vf_on_offset_frame()

    def vf_on_offset_frame(self, event=None):
        sel = self.vf_offset_frame_list.curselection()
        action = self._vf_selected_offset_action()
        if not sel or not action:
            return
        frame = action.get('frames', [])[sel[0]]
        self.vf_offset_selected_frame = frame
        self.vf_offset_x_var.set(str(frame.get('offset_x', 0)))
        self.vf_offset_y_var.set(str(frame.get('offset_y', 0)))
        self.vf_draw_offset_canvas()

    def vf_draw_offset_canvas(self):
        c = self.vf_offset_canvas
        c.delete('all')
        frame = getattr(self, 'vf_offset_selected_frame', None)
        cw = max(600, c.winfo_width() or 800)
        ch = max(420, c.winfo_height() or 580)
        axis_x = cw // 2
        axis_y = int(ch * 0.70)
        c.create_line(axis_x, 20, axis_x, ch - 20, fill='#999999', dash=(3, 3))
        c.create_line(20, axis_y, cw - 20, axis_y, fill='#999999', dash=(3, 3))
        c.create_text(axis_x + 8, axis_y + 8, anchor='nw', text='axis / floor reference', font=('Consolas', 9))
        if not frame:
            c.create_text(30, 30, anchor='nw', text='Refresh and choose a frame.', font=('Consolas', 12))
            return
        ox = self._vf_int(self.vf_offset_x_var, 0)
        oy = self._vf_int(self.vf_offset_y_var, 0)
        spr_w, spr_h = 110, 110
        sx = axis_x + ox - spr_w // 2
        sy = axis_y + oy - spr_h
        c.create_rectangle(sx, sy, sx + spr_w, sy + spr_h, fill='#d9ead3', outline='#38761d', width=2, tags=('sprite_preview',))
        c.create_text(sx + spr_w//2, sy + spr_h//2, text=f"{frame.get('group')},{frame.get('image')}\nAIR {ox},{oy}", font=('Consolas', 12), tags=('sprite_preview',))
        c.create_oval(axis_x - 4, axis_y - 4, axis_x + 4, axis_y + 4, fill='#cc0000', outline='')
        key = f"{frame.get('group')},{frame.get('image')}"
        axis_ref = self.vf_offset_model.get('sff_axis_reference', {}).get(key)
        info = [f"Frame #{int(frame.get('index', 0))+1}", f"Sprite: {key}", f"AIR offset: {ox},{oy}", 'Drag the rectangle to preview; Save writes the AIR frame line with backup.']
        if axis_ref:
            info.append(f"SFF axis reference: x={axis_ref.get('x')} y={axis_ref.get('y')} format={axis_ref.get('format')}")
        else:
            info.append('No SFF axis reference found for this sprite, or SFF unsupported for extraction.')
        self.set_text(self.vf_offset_info, '\n'.join(info))

    def vf_offset_canvas_press(self, event):
        self.vf_offset_drag_data = (event.x, event.y, self._vf_int(self.vf_offset_x_var, 0), self._vf_int(self.vf_offset_y_var, 0))

    def vf_offset_canvas_drag(self, event):
        if not self.vf_offset_drag_data:
            return
        sx, sy, ox, oy = self.vf_offset_drag_data
        snap = max(1, self._vf_int(self.vf_offset_snap_var, 1))
        nx = ox + int(round((event.x - sx) / snap)) * snap
        ny = oy + int(round((event.y - sy) / snap)) * snap
        self.vf_offset_x_var.set(str(nx))
        self.vf_offset_y_var.set(str(ny))
        self.vf_draw_offset_canvas()

    def vf_save_offset_ui(self):
        if not self._vf_require_project():
            return
        action = self._vf_selected_offset_action()
        sel = self.vf_offset_frame_list.curselection()
        if not action or not sel:
            messagebox.showinfo('No frame selected', 'Choose an action/frame first.')
            return
        try:
            result = update_air_frame_offset(self.project_root, int(action.get('action')), sel[0], self._vf_int(self.vf_offset_x_var, 0), self._vf_int(self.vf_offset_y_var, 0))
            self.set_text(self.vf_offset_info, result.to_text())
            self.vf_refresh_offset_ui()
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Offset save failed', str(exc))
            log_error(self.project_root, 'Offset save', exc)

    def _build_sound_cue_editor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_sound_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Sound Cue Editor', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='Assign and time PlaySnd cues to specific StateDefs/AnimElem frames. Inserts are text-based with backups and should be verified in M.U.G.E.N.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Button(left, text='Refresh / Build Cue Manifest', command=self.vf_refresh_sound_cues_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Label(left, text='Target StateDef').grid(row=1, column=0, sticky='w', pady=(8, 2))
        self.vf_sound_state_var = tk.StringVar(value='200')
        self.vf_sound_state_combo = ttk.Combobox(left, textvariable=self.vf_sound_state_var, width=34)
        self.vf_sound_state_combo.grid(row=2, column=0, sticky='ew')
        fields = ttk.LabelFrame(left, text='Cue', padding=(6, 6))
        fields.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        self.vf_sound_frame_var = tk.StringVar(value='2')
        self.vf_sound_group_var = tk.StringVar(value='5')
        self.vf_sound_index_var = tk.StringVar(value='0')
        self.vf_sound_channel_var = tk.StringVar(value='0')
        for r, (label, var) in enumerate((('AnimElem frame', self.vf_sound_frame_var), ('Sound group', self.vf_sound_group_var), ('Sound index', self.vf_sound_index_var), ('Channel', self.vf_sound_channel_var))):
            ttk.Label(fields, text=label).grid(row=r, column=0, sticky='w')
            ttk.Entry(fields, textvariable=var, width=10).grid(row=r, column=1, sticky='w')
        ttk.Button(fields, text='Add PlaySnd Cue (.bak)', command=self.vf_add_sound_cue_ui).grid(row=4, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Button(left, text='Export Cue Manifest Only', command=self.vf_export_sound_cue_manifest_ui).grid(row=4, column=0, sticky='ew', pady=(8, 2))
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_sound_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_sound_output.yview)
        self.vf_sound_output.configure(yscrollcommand=y.set)
        self.vf_sound_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(tab, text='Sound Cue Editor')

    def vf_refresh_sound_cues_ui(self):
        if not self._vf_require_project():
            return
        try:
            states = []
            for path in sorted(Path(self.project_root).rglob('*')):
                if path.suffix.lower() in {'.cmd', '.cns', '.st'} and path.is_file():
                    try:
                        for st in parse_code(read_text_safely(path)).states:
                            states.append(f"{st.number}  ({path.name}, anim {st.values.get('anim', '')})")
                    except Exception:
                        pass
            self.vf_sound_state_combo.configure(values=sorted(set(states), key=lambda s: int(str(s).split()[0]) if str(s).split()[0].lstrip('-').isdigit() else 0))
            result = write_sound_cue_manifest(self.project_root)
            self.set_text(self.vf_sound_output, result.to_text())
            self.status_var.set('Sound cue manifest refreshed')
        except Exception as exc:
            messagebox.showerror('Sound cue refresh failed', str(exc))
            log_error(self.project_root, 'Sound cue refresh', exc)

    def vf_add_sound_cue_ui(self):
        if not self._vf_require_project():
            return
        try:
            raw_state = self.vf_sound_state_var.get().strip().split()[0]
            cue = SoundCueSpec(
                state_no=int(raw_state),
                frame=self._vf_int(self.vf_sound_frame_var, 2),
                sound_group=self._vf_int(self.vf_sound_group_var, 5),
                sound_index=self._vf_int(self.vf_sound_index_var, 0),
                channel=self._vf_int(self.vf_sound_channel_var, 0),
                label='Visual Forge Sound Cue',
            )
            result = add_sound_cue_controller(self.project_root, cue)
            result.merge(write_sound_cue_manifest(self.project_root), 'Cue Manifest')
            self.set_text(self.vf_sound_output, result.to_text())
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Add sound cue failed', str(exc))
            log_error(self.project_root, 'Add sound cue', exc)

    def vf_export_sound_cue_manifest_ui(self):
        if not self._vf_require_project():
            return
        try:
            result = write_sound_cue_manifest(self.project_root)
            self.set_text(self.vf_sound_output, result.to_text())
        except Exception as exc:
            messagebox.showerror('Cue manifest failed', str(exc))
            log_error(self.project_root, 'Cue manifest', exc)

    def _build_move_composer2_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_composer2_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Move Composer 2.0', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='A no-code move builder tied to Visual Timeline, Sound Cue, and AIR/CLSN scaffolding. Preview first, then append to project files with backups.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        self.vf_compose_vars = {}
        defaults = [
            ('move_name', 'Light Punch'), ('command_name', 'light_punch'), ('command_input', 'x'), ('move_type', 'attack'),
            ('state_no', '200'), ('anim_no', '200'), ('sprite_group', '200'), ('start_image', '0'),
            ('frame_count', '4'), ('ticks', '4'), ('hit_frame', '2'), ('damage', '35'),
            ('sound_group', '5'), ('sound_index', '0'), ('hit_x1', '18'), ('hit_y1', '-72'), ('hit_x2', '58'), ('hit_y2', '-36'),
            ('body_x1', '-18'), ('body_y1', '-88'), ('body_x2', '18'), ('body_y2', '0'),
        ]
        for idx, (key, value) in enumerate(defaults):
            ttk.Label(left, text=key).grid(row=idx, column=0, sticky='e', padx=(0, 4), pady=1)
            var = tk.StringVar(value=value)
            self.vf_compose_vars[key] = var
            if key == 'move_type':
                ttk.Combobox(left, textvariable=var, values=('attack', 'projectile', 'movement'), state='readonly', width=18).grid(row=idx, column=1, sticky='w', pady=1)
            else:
                ttk.Entry(left, textvariable=var, width=20).grid(row=idx, column=1, sticky='w', pady=1)
        ttk.Button(left, text='Preview Move Package', command=self.vf_composer2_preview).grid(row=len(defaults), column=0, columnspan=2, sticky='ew', pady=(8, 2))
        ttk.Button(left, text='Append To Project (.bak)', command=self.vf_composer2_append).grid(row=len(defaults)+1, column=0, columnspan=2, sticky='ew', pady=2)
        ttk.Button(left, text='Open Visual Timeline', command=lambda: self.notebook.select(self.vf_timeline_frame)).grid(row=len(defaults)+2, column=0, columnspan=2, sticky='ew', pady=2)
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_composer2_output = tk.Text(right, wrap='none', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_composer2_output.yview)
        x = ttk.Scrollbar(right, orient='horizontal', command=self.vf_composer2_output.xview)
        self.vf_composer2_output.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.vf_composer2_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        self.notebook.add(tab, text='Move Composer 2.0')

    def _vf_composer2_spec(self):
        data = {k: v.get() for k, v in self.vf_compose_vars.items()}
        data['command_time'] = '12'
        data['sparkno'] = '2'
        data['guard_sparkno'] = '40'
        return normalize_spec(**data)

    def vf_composer2_preview(self):
        if not self._vf_require_project():
            return
        try:
            spec = self._vf_composer2_spec()
            result = compose_move2(self.project_root, spec, append=False)
            out = self.project_root / 'visual_forge' / 'move_composer' / f"{re.sub(r'[^A-Za-z0-9_\-]+', '_', spec.move_name).strip('_') or 'move'}_preview.txt"
            text = result.to_text()
            if out.exists():
                text += '\n' + out.read_text(encoding='utf-8')
            self.set_text(self.vf_composer2_output, text)
        except Exception as exc:
            messagebox.showerror('Composer preview failed', str(exc))
            log_error(self.project_root, 'Move Composer preview', exc)

    def vf_composer2_append(self):
        if not self._vf_require_project():
            return
        try:
            spec = self._vf_composer2_spec()
            result = compose_move2(self.project_root, spec, append=True)
            result.merge(write_visual_timeline_manifest(self.project_root, spec.anim_no), 'Timeline Manifest')
            self.set_text(self.vf_composer2_output, result.to_text())
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Composer append failed', str(exc))
            log_error(self.project_root, 'Move Composer append', exc)

    def _build_migration_wizard_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_migration_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Existing Character Import / Migration Wizard', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='Copy a legacy character into a MugenForge project folder, write a migration report, and guide repair steps. The original source folder is not modified.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        self.vf_migration_source_var = tk.StringVar()
        self.vf_migration_dest_var = tk.StringVar(value=str(Path.cwd()))
        self.vf_migration_name_var = tk.StringVar(value='imported_character')
        for r, (label, var, cmd) in enumerate((('Source character folder', self.vf_migration_source_var, self.vf_choose_import_source), ('Destination parent', self.vf_migration_dest_var, self.vf_choose_import_dest), ('New project folder name', self.vf_migration_name_var, None))):
            ttk.Label(left, text=label).grid(row=r*2, column=0, sticky='w', pady=(4, 1))
            ttk.Entry(left, textvariable=var, width=46).grid(row=r*2+1, column=0, sticky='ew')
            if cmd:
                ttk.Button(left, text='Choose', command=cmd).grid(row=r*2+1, column=1, padx=(4, 0))
        ttk.Button(left, text='Run Migration Wizard', command=self.vf_run_migration_ui).grid(row=7, column=0, sticky='ew', pady=(10, 2))
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_migration_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_migration_output.yview)
        self.vf_migration_output.configure(yscrollcommand=y.set)
        self.vf_migration_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(tab, text='Migration Wizard')

    def vf_choose_import_source(self):
        folder = filedialog.askdirectory(title='Choose existing character folder to import')
        if folder:
            self.vf_migration_source_var.set(folder)
            self.vf_migration_name_var.set(Path(folder).name + '_mugenforge')

    def vf_choose_import_dest(self):
        folder = filedialog.askdirectory(title='Choose destination parent folder')
        if folder:
            self.vf_migration_dest_var.set(folder)

    def vf_run_migration_ui(self):
        try:
            spec = MigrationSpec(Path(self.vf_migration_source_var.get().strip()), Path(self.vf_migration_dest_var.get().strip()), self.vf_migration_name_var.get().strip())
            result = migrate_existing_character(spec)
            self.set_text(self.vf_migration_output, result.to_text())
            dest = spec.destination_parent / (spec.new_name.strip() or spec.source_root.name)
            if dest.exists():
                self.load_project(dest)
        except Exception as exc:
            messagebox.showerror('Migration failed', str(exc))
            if self.project_root:
                log_error(self.project_root, 'Migration wizard', exc)

    def _build_training_debug_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_training_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Training / Debug Overlay Pack', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='Install beginner testing helpers and write docs/config for state, frame, velocity, and control debugging. Use engine playtesting for authoritative results.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Button(left, text='Install Training Debug Pack', command=self.vf_install_training_debug_ui).grid(row=0, column=0, sticky='ew', pady=2)
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_training_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_training_output.yview)
        self.vf_training_output.configure(yscrollcommand=y.set)
        self.vf_training_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(tab, text='Training Debug')

    def vf_install_training_debug_ui(self):
        if not self._vf_require_project():
            return
        try:
            result = install_training_debug_pack(self.project_root)
            self.set_text(self.vf_training_output, result.to_text())
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Training debug install failed', str(exc))
            log_error(self.project_root, 'Training debug install', exc)

    def _build_plugin_template_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_plugin_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Plugin / Template Architecture', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='Foundation for no-code presets, data-only community templates, and future plugins. Arbitrary third-party code execution is not enabled by default.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        ttk.Button(left, text='Install Template / Plugin Foundation', command=self.vf_install_templates_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(left, text='Write Honest SFF2 Bridge Pack', command=self.vf_sff2_pack_ui).grid(row=1, column=0, sticky='ew', pady=2)
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_plugin_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_plugin_output.yview)
        self.vf_plugin_output.configure(yscrollcommand=y.set)
        self.vf_plugin_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(tab, text='Templates / Plugins')

    def vf_install_templates_ui(self):
        if not self._vf_require_project():
            return
        try:
            result = install_template_architecture(self.project_root)
            target = self.vf_plugin_output if hasattr(self, 'vf_plugin_output') else self.vf_home_output
            self.set_text(target, result.to_text())
            self.status_var.set('Template/plugin foundation installed')
        except Exception as exc:
            messagebox.showerror('Template install failed', str(exc))
            log_error(self.project_root, 'Template/plugin install', exc)

    def vf_sff2_pack_ui(self):
        if not self._vf_require_project():
            return
        try:
            folder = filedialog.askdirectory(title='Optional: choose image folder for Sprmake2 source project, or cancel to write guide only')
            img = Path(folder) if folder else None
            result = write_visual_sff2_bridge_pack(self.project_root, img)
            target = self.vf_plugin_output if hasattr(self, 'vf_plugin_output') else self.vf_home_output
            self.set_text(target, result.to_text())
        except Exception as exc:
            messagebox.showerror('SFF2 bridge pack failed', str(exc))
            log_error(self.project_root, 'SFF2 Bridge Pack', exc)

    def _build_backup_log_tab(self):
        tab = ttk.Frame(self.notebook)
        self.vf_backup_frame = tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        header = ttk.LabelFrame(tab, text='Central Backup / Undo / Error Log', padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        ttk.Label(header, text='Create whole-project snapshots, restore the latest Visual Forge snapshot with a pre-restore guard backup, and inspect error logs.', wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        left = ttk.Frame(tab, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        self.vf_backup_label_var = tk.StringVar(value='manual')
        ttk.Label(left, text='Snapshot label').grid(row=0, column=0, sticky='w')
        ttk.Entry(left, textvariable=self.vf_backup_label_var, width=30).grid(row=1, column=0, sticky='ew')
        ttk.Button(left, text='Create Snapshot ZIP', command=self.vf_backup_snapshot_ui).grid(row=2, column=0, sticky='ew', pady=(8, 2))
        ttk.Button(left, text='Restore Latest Snapshot', command=self.vf_restore_snapshot_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(left, text='View Error Log', command=self.vf_view_error_log_ui).grid(row=4, column=0, sticky='ew', pady=2)
        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.vf_backup_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.vf_backup_output.yview)
        self.vf_backup_output.configure(yscrollcommand=y.set)
        self.vf_backup_output.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        self.notebook.add(tab, text='Backups / Logs')

    def vf_backup_snapshot_ui(self):
        if not self._vf_require_project():
            return
        try:
            label = self.vf_backup_label_var.get() if hasattr(self, 'vf_backup_label_var') else 'manual'
            result = create_backup_snapshot(self.project_root, label)
            target = self.vf_backup_output if hasattr(self, 'vf_backup_output') else self.vf_home_output
            self.set_text(target, result.to_text())
            self.status_var.set('Visual Forge backup snapshot created')
        except Exception as exc:
            messagebox.showerror('Backup failed', str(exc))
            log_error(self.project_root, 'Backup snapshot', exc)

    def vf_restore_snapshot_ui(self):
        if not self._vf_require_project():
            return
        if not messagebox.askyesno('Restore latest snapshot', 'Restore the latest Visual Forge snapshot? A pre-restore guard snapshot will be created first.'):
            return
        try:
            result = restore_latest_snapshot(self.project_root)
            self.set_text(self.vf_backup_output, result.to_text())
            self.reload_project()
        except Exception as exc:
            messagebox.showerror('Restore failed', str(exc))
            log_error(self.project_root, 'Restore latest snapshot', exc)

    def vf_view_error_log_ui(self):
        if not self._vf_require_project():
            return
        log = self.project_root / 'visual_forge' / 'error_log.txt'
        if log.exists():
            self.set_text(self.vf_backup_output, log.read_text(encoding='utf-8', errors='replace'))
        else:
            self.set_text(self.vf_backup_output, 'No Visual Forge error log exists yet.')


    def auto_make_playable_prototype_ui(self):
        # Compatibility route for Forge+ tab: use the newer Factory+ smart pass.
        self.factory_smart_complete_ui()

    def auto_beginner_doctor_ui(self):
        # Compatibility route for Forge+ tab: use the newer Factory+ doctor report.
        self.factory_doctor_ui()

    def forge_plus_report_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            text = full_project_report(self.project_root)
        except Exception as exc:
            text = f'Forge+ Doctor failed:\n{exc}'
        self.set_text(self.forge_plus_output, text)
        self.notebook.select(self.forge_plus_frame)

    def forge_plus_export_move_list_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            out = export_move_list(self.project_root)
            self.set_text(self.forge_plus_output, f'Move list exported:\n{out}\n\n' + out.read_text(encoding='utf-8'))
            self.status_var.set(f'Move list exported: {out.name}')
        except Exception as exc:
            messagebox.showerror('Move list failed', str(exc))

    def forge_plus_creator_manual_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            out = write_creator_manual(self.project_root)
            self.set_text(self.forge_plus_output, f'Creator manual written:\n{out}\n\n' + out.read_text(encoding='utf-8'))
            self.status_var.set(f'Creator manual written: {out.name}')
        except Exception as exc:
            messagebox.showerror('Creator manual failed', str(exc))

    def _sprite_lab_folder(self) -> Path | None:
        raw = self.sprite_lab_folder_var.get().strip()
        if not raw:
            messagebox.showinfo('No folder', 'Choose an image folder first.')
            return None
        folder = Path(raw)
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror('Folder not found', str(folder))
            return None
        return folder

    def _sprite_lab_int(self, var: tk.StringVar, default: int) -> int:
        try:
            return int(var.get().strip())
        except Exception:
            return default

    def sprite_lab_choose_folder_ui(self):
        path = filedialog.askdirectory(title='Choose sprite image folder')
        if path:
            self.sprite_lab_folder_var.set(path)
            self.sprite_lab_summary_ui()

    def sprite_lab_summary_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        try:
            self.set_text(self.sprite_lab_output, summarize_image_folder(folder))
        except Exception as exc:
            messagebox.showerror('Sprite summary failed', str(exc))

    def sprite_lab_contact_sheet_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save contact sheet', defaultextension='.png', initialfile='mugenforge_contact_sheet.png', filetypes=[('PNG', '*.png')])
        if not out:
            return
        try:
            path = make_sprite_contact_sheet(folder, Path(out))
            self.set_text(self.sprite_lab_output, f'Contact sheet written:\n{path}')
            self.status_var.set(f'Contact sheet: {path.name}')
        except Exception as exc:
            messagebox.showerror('Contact sheet failed', str(exc))

    def sprite_lab_normalize_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out_dir = filedialog.askdirectory(title='Choose output folder for normalized sprites')
        if not out_dir:
            return
        try:
            manifest = normalize_sprite_folder(
                folder, Path(out_dir),
                canvas_w=self._sprite_lab_int(self.sprite_lab_canvas_w_var, 96),
                canvas_h=self._sprite_lab_int(self.sprite_lab_canvas_h_var, 96),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                axis_x=self._sprite_lab_int(self.sprite_lab_axis_x_var, 48),
                axis_y=self._sprite_lab_int(self.sprite_lab_axis_y_var, 88),
                scale_percent=self._sprite_lab_int(self.sprite_lab_scale_var, 100),
                trim=bool(self.sprite_lab_trim_var.get()),
            )
            self.set_text(self.sprite_lab_output, f'Normalized sprites and manifest written:\n{manifest}\n\nUse Sheet Import / Build SFF v1 or Sprite Lab Build SFF v1 next.')
            self.status_var.set(f'Sprite manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Normalize failed', str(exc))

    def sprite_lab_build_sff_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        initial = f'{self.project_root.name if self.project_root else folder.name}.sff'
        out = filedialog.asksaveasfilename(title='Save built SFF v1', defaultextension='.sff', initialfile=initial, filetypes=[('SFF', '*.sff')])
        if not out:
            return
        try:
            out_path = build_sff_from_image_folder(
                folder, Path(out),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                canvas_w=self._sprite_lab_int(self.sprite_lab_canvas_w_var, 96),
                canvas_h=self._sprite_lab_int(self.sprite_lab_canvas_h_var, 96),
                axis_x=self._sprite_lab_int(self.sprite_lab_axis_x_var, 48),
                axis_y=self._sprite_lab_int(self.sprite_lab_axis_y_var, 88),
            )
            self.set_text(self.sprite_lab_output, f'SFF v1 built from folder:\n{out_path}\n\nOpen it in the project tree or Sprites tab to inspect records.')
            self.status_var.set(f'SFF built: {out_path.name}')
            if out_path.exists():
                self.populate_sprite_browser(out_path)
                self.notebook.select(5)
        except Exception as exc:
            messagebox.showerror('SFF build failed', str(exc))

    def sprite_lab_air_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save generated AIR block', defaultextension='.air', initialfile='generated_action.air', filetypes=[('AIR', '*.air'), ('Text', '*.txt')])
        if not out:
            return
        try:
            path = make_air_from_image_sequence(
                folder, Path(out),
                action=self._sprite_lab_int(self.sprite_lab_action_var, 200),
                group=self._sprite_lab_int(self.sprite_lab_group_var, 200),
                start_image=self._sprite_lab_int(self.sprite_lab_start_image_var, 0),
                ticks=self._sprite_lab_int(self.sprite_lab_ticks_var, 5),
            )
            self.set_text(self.sprite_lab_output, f'AIR action block written:\n{path}\n\n' + path.read_text(encoding='utf-8'))
            self.status_var.set(f'AIR block: {path.name}')
        except Exception as exc:
            messagebox.showerror('AIR generation failed', str(exc))

    def sprite_lab_gif_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save GIF preview', defaultextension='.gif', initialfile='animation_preview.gif', filetypes=[('GIF', '*.gif')])
        if not out:
            return
        try:
            ms = max(1, self._sprite_lab_int(self.sprite_lab_ticks_var, 5) * 1000 // 60)
            path = make_animation_gif(folder, Path(out), frame_ms=ms)
            self.set_text(self.sprite_lab_output, f'GIF preview written:\n{path}')
            self.status_var.set(f'GIF preview: {path.name}')
        except Exception as exc:
            messagebox.showerror('GIF failed', str(exc))

    def sprite_lab_palette_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save ACT palette', defaultextension='.act', initialfile='palette_from_folder.act', filetypes=[('ACT', '*.act')])
        if not out:
            return
        try:
            path = build_act_from_folder(folder, Path(out))
            self.set_text(self.sprite_lab_output, f'ACT palette built from folder:\n{path}\n\nOpen it in the Palettes tab to inspect colors.')
            self.status_var.set(f'ACT palette: {path.name}')
        except Exception as exc:
            messagebox.showerror('Palette build failed', str(exc))

    def sprite_lab_pcx_ui(self):
        folder = self._sprite_lab_folder()
        if not folder:
            return
        out_dir = filedialog.askdirectory(title='Choose output folder for PCX files')
        if not out_dir:
            return
        try:
            outs = convert_images_to_pcx(folder, Path(out_dir))
            self.set_text(self.sprite_lab_output, f'Converted {len(outs)} image(s) to PCX in:\n{out_dir}\n\n' + '\n'.join(str(p.name) for p in outs[:120]))
            self.status_var.set(f'PCX converted: {len(outs)} file(s)')
        except Exception as exc:
            messagebox.showerror('PCX conversion failed', str(exc))

    def stage_choose_image_ui(self):
        path = filedialog.askopenfilename(title='Choose stage background image', filetypes=[('Images', '*.png *.pcx *.bmp *.jpg *.jpeg *.webp *.gif'), ('All files', '*.*')])
        if path:
            self.stage_image_var.set(path)
            if not self.stage_name_var.get().strip() or self.stage_name_var.get() == 'new_stage':
                self.stage_name_var.set(Path(path).stem)

    def stage_choose_output_ui(self):
        path = filedialog.askdirectory(title='Choose stages output folder')
        if path:
            self.stage_out_dir_var.set(path)

    def stage_create_ui(self):
        image = Path(self.stage_image_var.get().strip())
        out_dir = Path(self.stage_out_dir_var.get().strip() or (self.project_root.parent if self.project_root else Path.home()))
        if not image.exists():
            messagebox.showerror('Missing image', 'Choose a valid background image first.')
            return
        try:
            z = self.stage_zoffset_var.get().strip()
            def_path = create_stage_from_image(
                image, out_dir,
                stage_name=self.stage_name_var.get().strip() or image.stem,
                zoffset=int(z) if z else None,
                bound_width=int(self.stage_bound_var.get().strip() or '320'),
            )
            self.set_text(self.stage_output, f'Stage created:\n{def_path}\n\nFiles are in:\n{def_path.parent}\n\nOpen the DEF to tune camera, zoffset, music, and deltas.')
            self.status_var.set(f'Stage created: {def_path.name}')
        except Exception as exc:
            messagebox.showerror('Stage build failed', str(exc))

    def run_choose_mugen_exe_ui(self):
        path = filedialog.askopenfilename(title='Choose M.U.G.E.N executable', filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if path:
            self.run_mugen_exe_var.set(path)

    def run_save_launch_config_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        exe = self.run_mugen_exe_var.get().strip()
        if not exe:
            messagebox.showinfo('No executable', 'Choose your M.U.G.E.N executable first.')
            return
        try:
            out = write_mugen_launch_config(self.project_root, Path(exe))
            self.set_text(self.run_output, f'Launch config written:\n{out}\n\nMugenForge does not include M.U.G.E.N. This only stores the path to your local executable.')
        except Exception as exc:
            messagebox.showerror('Launch config failed', str(exc))

    def run_launch_mugen_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        try:
            proc = launch_mugen(self.project_root)
            self.set_text(self.run_output, f'Launched M.U.G.E.N. Process id: {proc.pid}\n\nUse your engine window for live testing.')
        except Exception as exc:
            messagebox.showerror('Launch failed', str(exc))

    def run_select_def_snippet_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        snippet = f'; Add this to data/select.def under [Characters]\n{self.project_root.name}/{self.project_root.name}.def\n'
        self.set_text(self.run_output, snippet)


    def _max_root_or_choose(self):
        if hasattr(self, '_factory_root_or_choose'):
            return self._factory_root_or_choose()
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _max_show_result(self, result, title='Factory Max'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.factory_max_output, text)
        if hasattr(self, 'factory_max_frame'):
            self.notebook.select(self.factory_max_frame)
        self.status_var.set(title)

    def max_one_click_upgrade_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = one_click_factory_max_upgrade(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max upgrade finished')
            messagebox.showinfo('Factory Max Upgrade', 'Factory Max upgrade finished. Review the report/output panel for created files and next steps.')
        except Exception as exc:
            messagebox.showerror('Factory Max upgrade failed', str(exc))

    def max_profile_report_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = factory_max_profile_report(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max report written')
        except Exception as exc:
            messagebox.showerror('Factory Max report failed', str(exc))

    def max_release_zip_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = build_factory_max_release_zip(root)
            self.reload_project()
            self._max_show_result(result, 'Factory Max release ZIP built')
            messagebox.showinfo('Release ZIP built', result.to_text())
        except Exception as exc:
            messagebox.showerror('Release ZIP failed', str(exc))

    def max_codesense_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_codesense_bank(root)
            self.reload_project()
            self._max_show_result(result, 'CodeSense bank written')
        except Exception as exc:
            messagebox.showerror('CodeSense failed', str(exc))

    def max_state_graph_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_state_graph(root)
            self.reload_project()
            self._max_show_result(result, 'State graph written')
        except Exception as exc:
            messagebox.showerror('State graph failed', str(exc))

    def max_organizer_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = write_organizer_manifest(root)
            self.reload_project()
            self._max_show_result(result, 'Organizer manifest written')
        except Exception as exc:
            messagebox.showerror('Organizer manifest failed', str(exc))

    def max_safe_import_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        source = filedialog.askdirectory(title='Choose source character/project folder to import safely')
        if not source:
            return
        try:
            result = safe_import_from_project(root, Path(source))
            self.reload_project()
            self._max_show_result(result, 'Safe project import complete')
        except Exception as exc:
            messagebox.showerror('Safe import failed', str(exc))

    def max_auto_clsn_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            padding = self._plus_int(self.max_clsn_padding_var, 2) if hasattr(self, '_plus_int') else int(self.max_clsn_padding_var.get() or 2)
            result = suggest_clsn_from_sff(root, padding=padding, save=True)
            self.reload_project()
            self._max_show_result(result, 'Auto CLSN from SFF finished')
        except Exception as exc:
            messagebox.showerror('Auto CLSN failed', str(exc))

    def max_retime_air_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            scale = self._plus_float(self.max_retime_scale_var, 1.0) if hasattr(self, '_plus_float') else float(self.max_retime_scale_var.get() or 1.0)
            result = retime_air(root, tick_scale=scale)
            self.reload_project()
            self._max_show_result(result, 'AIR retiming finished')
        except Exception as exc:
            messagebox.showerror('AIR retime failed', str(exc))

    def max_renumber_air_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            offset = self._plus_int(self.max_renumber_offset_var, 10000) if hasattr(self, '_plus_int') else int(self.max_renumber_offset_var.get() or 10000)
            result = renumber_air_actions(root, offset=offset)
            self.reload_project()
            self._max_show_result(result, 'AIR clone/renumber finished')
        except Exception as exc:
            messagebox.showerror('AIR clone/renumber failed', str(exc))

    def max_storyboard_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        name = simpledialog.askstring('Storyboard Template', 'Storyboard name:', initialvalue='intro') or 'intro'
        try:
            result = create_storyboard_template(root, name=name)
            self.reload_project()
            self._max_show_result(result, 'Storyboard template created')
        except Exception as exc:
            messagebox.showerror('Storyboard template failed', str(exc))

    def max_screenpack_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_screenpack_template(root)
            self.reload_project()
            self._max_show_result(result, 'Screenpack starter created')
        except Exception as exc:
            messagebox.showerror('Screenpack starter failed', str(exc))

    def max_sound_autobank_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_sound_autobank(root)
            self.reload_project()
            self._max_show_result(result, 'Sound AutoBank created')
        except Exception as exc:
            messagebox.showerror('Sound AutoBank failed', str(exc))

    def max_quick_test_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        try:
            result = create_quick_test_suite(root)
            self.reload_project()
            self._max_show_result(result, 'Quick Test Suite written')
        except Exception as exc:
            messagebox.showerror('Quick Test Suite failed', str(exc))


    def _ultra_root_or_choose(self):
        return self._max_root_or_choose()

    def _ultra_show_result(self, result, title='Factory Ultra'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.factory_ultra_output, text)
        if hasattr(self, 'factory_ultra_frame'):
            self.notebook.select(self.factory_ultra_frame)
        self.status_var.set(title)

    def ultra_one_click_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = one_click_factory_ultra_upgrade(root)
            self.reload_project()
            self._ultra_show_result(result, 'Factory Ultra upgrade finished')
            messagebox.showinfo('Factory Ultra Upgrade', 'Factory Ultra upgrade finished. Open START_HERE_MUGENFORGE.md or review the output panel.')
        except Exception as exc:
            messagebox.showerror('Factory Ultra upgrade failed', str(exc))

    def ultra_audit_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_ultra_audit(root)
            self.reload_project()
            self._ultra_show_result(result, 'Factory Ultra audit written')
        except Exception as exc:
            messagebox.showerror('Ultra audit failed', str(exc))

    def ultra_next_steps_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_smart_next_steps(root)
            self.reload_project()
            self._ultra_show_result(result, 'Smart next-step queue written')
        except Exception as exc:
            messagebox.showerror('Next-step queue failed', str(exc))

    def ultra_dashboard_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_creator_home_dashboard(root)
            self.reload_project()
            self._ultra_show_result(result, 'Creator home dashboard written')
        except Exception as exc:
            messagebox.showerror('Creator dashboard failed', str(exc))

    def ultra_function_map_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_no_code_function_map(root)
            self.reload_project()
            self._ultra_show_result(result, 'No-code function map written')
        except Exception as exc:
            messagebox.showerror('Function map failed', str(exc))

    def ultra_input_report_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_input_conflict_report(root)
            self.reload_project()
            self._ultra_show_result(result, 'Input conflict report written')
        except Exception as exc:
            messagebox.showerror('Input report failed', str(exc))

    def ultra_balance_lab_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_balance_lab(root)
            self.reload_project()
            self._ultra_show_result(result, 'Balance Lab written')
        except Exception as exc:
            messagebox.showerror('Balance Lab failed', str(exc))

    def ultra_frame_data_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_frame_data_report(root)
            self.reload_project()
            self._ultra_show_result(result, 'Frame data exported')
        except Exception as exc:
            messagebox.showerror('Frame data export failed', str(exc))

    def ultra_combo_lab_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_combo_lab(root)
            self.reload_project()
            self._ultra_show_result(result, 'Combo Lab written')
        except Exception as exc:
            messagebox.showerror('Combo Lab failed', str(exc))

    def ultra_compatibility_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = write_compatibility_matrix(root)
            self.reload_project()
            self._ultra_show_result(result, 'Compatibility matrix written')
        except Exception as exc:
            messagebox.showerror('Compatibility matrix failed', str(exc))

    def ultra_auto_tune_damage_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            scale = self._plus_float(self.ultra_damage_scale_var, 1.0) if hasattr(self, '_plus_float') else float(self.ultra_damage_scale_var.get() or 1.0)
            max_damage = self._plus_int(self.ultra_damage_max_var, 180) if hasattr(self, '_plus_int') else int(self.ultra_damage_max_var.get() or 180)
            result = auto_tune_damage(root, damage_scale=scale, max_damage=max_damage)
            self.reload_project()
            self._ultra_show_result(result, 'Damage auto-tune finished')
        except Exception as exc:
            messagebox.showerror('Damage auto-tune failed', str(exc))

    def ultra_clone_variant_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        name = simpledialog.askstring('Clone Character Variant', 'Variant name:', initialvalue=f'{root.name}_variant')
        if not name:
            return
        try:
            result = create_character_variant(root, name)
            self._ultra_show_result(result, 'Character variant cloned')
            messagebox.showinfo('Variant cloned', result.to_text())
        except Exception as exc:
            messagebox.showerror('Variant clone failed', str(exc))

    def ultra_release_zip_ui(self):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = build_ultra_release_zip(root)
            self.reload_project()
            self._ultra_show_result(result, 'Ultra release ZIP built')
            messagebox.showinfo('Ultra Release ZIP', result.to_text())
        except Exception as exc:
            messagebox.showerror('Ultra release ZIP failed', str(exc))


    def _creator_os_root_or_choose(self):
        if self.project_root:
            return self.project_root
        folder = filedialog.askdirectory(title='Choose character folder for Creator OS')
        if folder:
            self.project_root = Path(folder)
            self.reload_project()
            return self.project_root
        return None

    def _creator_os_show_result(self, result, title='Creator OS'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        if hasattr(self, 'creator_os_output'):
            self.set_text(self.creator_os_output, text)
            self.notebook.select(self.creator_os_frame)
        self.status_var.set(title)

    def _creator_os_profile(self):
        archetype = self.creator_os_archetype_var.get() if hasattr(self, 'creator_os_archetype_var') else 'Balanced Starter'
        complexity = self.creator_os_complexity_var.get() if hasattr(self, 'creator_os_complexity_var') else 'Beginner'
        style = self.creator_os_style_var.get() if hasattr(self, 'creator_os_style_var') else 'Arcade'
        return archetype, complexity, style

    def creator_os_one_click_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        archetype, complexity, style = self._creator_os_profile()
        try:
            result = creator_os_one_click(root, archetype=archetype, complexity=complexity, visual_style=style)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Autopilot finished')
            messagebox.showinfo('Creator OS', 'Creator OS Autopilot finished. Open docs/PROJECT_WIKI.md or START_HERE_CREATOR_OS.md next.')
        except Exception as exc:
            messagebox.showerror('Creator OS Autopilot failed', str(exc))

    def creator_os_blueprint_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        archetype, complexity, style = self._creator_os_profile()
        try:
            result = write_character_blueprint(root, archetype=archetype, complexity=complexity, visual_style=style)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Blueprint written')
        except Exception as exc:
            messagebox.showerror('Blueprint failed', str(exc))

    def creator_os_frame_data_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = export_frame_data_sheet(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Frame Data exported')
        except Exception as exc:
            messagebox.showerror('Frame Data export failed', str(exc))

    def creator_os_inputs_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = export_input_cheatsheet(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Input Cheatsheet exported')
        except Exception as exc:
            messagebox.showerror('Input Cheatsheet failed', str(exc))

    def creator_os_combo_routes_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_combo_routes(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Combo Routes written')
        except Exception as exc:
            messagebox.showerror('Combo Routes failed', str(exc))

    def creator_os_balance_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_balance_report(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Balance Report written')
        except Exception as exc:
            messagebox.showerror('Balance Report failed', str(exc))

    def creator_os_quality_gate_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_release_quality_gate(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Quality Gate finished')
        except Exception as exc:
            messagebox.showerror('Quality Gate failed', str(exc))

    def creator_os_asset_list_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_asset_shopping_list(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Asset Shopping List written')
        except Exception as exc:
            messagebox.showerror('Asset Shopping List failed', str(exc))

    def creator_os_lessons_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_beginner_lessons(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Beginner Lessons written')
        except Exception as exc:
            messagebox.showerror('Beginner Lessons failed', str(exc))

    def creator_os_wiki_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_project_wiki(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Project Wiki written')
        except Exception as exc:
            messagebox.showerror('Project Wiki failed', str(exc))

    def creator_os_codebook_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = write_autocode_cookbook(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Auto-Code Cookbook written')
        except Exception as exc:
            messagebox.showerror('Auto-Code Cookbook failed', str(exc))

    def creator_os_release_zip_ui(self):
        root = self._creator_os_root_or_choose()
        if not root:
            return
        try:
            result = build_creator_os_release_zip(root)
            self.reload_project()
            self._creator_os_show_result(result, 'Creator OS Release ZIP built')
            messagebox.showinfo('Creator OS Release ZIP', result.to_text())
        except Exception as exc:
            messagebox.showerror('Creator OS Release ZIP failed', str(exc))

    def _ultra_root_or_choose(self):
        if hasattr(self, '_max_root_or_choose'):
            return self._max_root_or_choose()
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _ultra_show_result(self, result, title='Factory Ultra'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        self.set_text(self.factory_ultra_output, text)
        if hasattr(self, 'factory_ultra_frame'):
            self.notebook.select(self.factory_ultra_frame)
        self.status_var.set(title)

    def _ultra_run(self, fn, title):
        root = self._ultra_root_or_choose()
        if not root:
            return
        try:
            result = fn(root)
            self.reload_project()
            self._ultra_show_result(result, title)
        except Exception as exc:
            messagebox.showerror(title + ' failed', str(exc))

    def ultra_one_click_ui(self):
        self._ultra_run(one_click_ultra_production_pass, 'Ultra production pass finished')

    def ultra_snapshot_ui(self):
        self._ultra_run(create_autosave_snapshot, 'Ultra snapshot created')

    def ultra_release_zip_ui(self):
        self._ultra_run(build_ultra_release_zip, 'Ultra release ZIP built')

    def ultra_dashboard_ui(self):
        self._ultra_run(ultra_project_dashboard, 'Ultra dashboard written')

    def ultra_task_board_ui(self):
        self._ultra_run(generate_beginner_task_board, 'Ultra task board written')

    def ultra_bible_ui(self):
        self._ultra_run(write_production_bible, 'Ultra production bible written')

    def ultra_switchboard_ui(self):
        self._ultra_run(write_no_code_feature_switchboard, 'Ultra feature switchboard written')

    def ultra_readiness_ui(self):
        self._ultra_run(generate_release_readiness_report, 'Ultra release readiness written')

    def ultra_frame_data_ui(self):
        self._ultra_run(generate_frame_data_lab, 'Ultra frame data lab written')

    def ultra_balance_ui(self):
        self._ultra_run(generate_balance_lab, 'Ultra balance lab written')

    def ultra_cancel_ui(self):
        self._ultra_run(generate_cancel_lab, 'Ultra cancel/state flow lab written')

    def ultra_assets_ui(self):
        self._ultra_run(generate_asset_usage_lab, 'Ultra asset usage lab written')

    def ultra_axis_ui(self):
        self._ultra_run(generate_sprite_axis_lab, 'Ultra sprite axis lab written')

    def ultra_ai_ui(self):
        self._ultra_run(generate_ai_tuning_lab, 'Ultra AI tuning lab written')

    def ultra_move_cards_ui(self):
        self._ultra_run(generate_move_cards, 'Ultra move cards written')

    def ultra_input_map_ui(self):
        self._ultra_run(generate_input_map_assistant, 'Ultra input map assistant written')

    def image_factory_choose_input_ui(self):
        folder = filedialog.askdirectory(title='Choose image input folder')
        if folder:
            self.image_factory_in_var.set(folder)
            if not self.image_factory_out_var.get().strip():
                self.image_factory_out_var.set(str(Path(folder).parent / (Path(folder).name + '_processed')))

    def image_factory_choose_output_ui(self):
        folder = filedialog.askdirectory(title='Choose image output folder')
        if folder:
            self.image_factory_out_var.set(folder)

    def image_factory_use_project_defaults_ui(self):
        root = self._max_root_or_choose()
        if not root:
            return
        inp = root / 'source_sprites'
        out = root / 'processed_sprites'
        inp.mkdir(exist_ok=True)
        out.mkdir(exist_ok=True)
        self.image_factory_in_var.set(str(inp))
        self.image_factory_out_var.set(str(out))
        self.set_text(self.image_factory_output, f'Project sprite folders prepared:\n\nInput: {inp}\nOutput: {out}\n\nPut source PNG/PCX/BMP/GIF/JPG/WEBP files into source_sprites, then run batch macros.')
        self.notebook.select(self.image_factory_frame)

    def image_factory_process_ui(self):
        inp = Path(self.image_factory_in_var.get().strip())
        out = Path(self.image_factory_out_var.get().strip())
        if not inp.exists():
            messagebox.showinfo('Missing input folder', 'Choose an existing input image folder first.')
            return
        if not str(out):
            messagebox.showinfo('Missing output folder', 'Choose an output folder first.')
            return
        try:
            result = image_factory_process_folder(
                inp, out,
                scale_percent=self._plus_float(self.image_factory_scale_var, 100.0) if hasattr(self, '_plus_float') else float(self.image_factory_scale_var.get() or 100),
                trim=bool(self.image_factory_trim_var.get()),
                mirror_x=bool(self.image_factory_mirror_x_var.get()),
                mirror_y=bool(self.image_factory_mirror_y_var.get()),
                canvas_w=self._plus_int(self.image_factory_canvas_w_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_canvas_w_var.get() or 0),
                canvas_h=self._plus_int(self.image_factory_canvas_h_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_canvas_h_var.get() or 0),
                transparent_mode=self.image_factory_transparency_var.get(),
                palette_colors=self._plus_int(self.image_factory_palette_var, 0) if hasattr(self, '_plus_int') else int(self.image_factory_palette_var.get() or 0),
                outline=bool(self.image_factory_outline_var.get()),
                shadow=bool(self.image_factory_shadow_var.get()),
            )
            self.set_text(self.image_factory_output, result.to_text())
            self.notebook.select(self.image_factory_frame)
            self.status_var.set('Image Factory batch finished')
        except Exception as exc:
            messagebox.showerror('Image batch failed', str(exc))

    def image_factory_palette_variants_ui(self):
        inp = Path(self.image_factory_in_var.get().strip())
        out_base = Path(self.image_factory_out_var.get().strip() or (str(inp) + '_palettes'))
        if not inp.exists():
            messagebox.showinfo('Missing input folder', 'Choose an existing input image folder first.')
            return
        try:
            result = make_palette_variants(inp, out_base / 'palette_variants', variants=6)
            self.set_text(self.image_factory_output, result.to_text())
            self.notebook.select(self.image_factory_frame)
            self.status_var.set('Palette variants created')
        except Exception as exc:
            messagebox.showerror('Palette variants failed', str(exc))

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

    def populate_sprite_browser(self, path: Path):
        self.sff_path = path
        self.sff_info = read_sff(path)
        self.sprite_tree.delete(*self.sprite_tree.get_children())
        self.sprite_canvas.delete('all')
        self.current_preview_image = None
        lines = [
            f'SFF: {path.name}',
            f'Version bytes: {self.sff_info.version_text}',
            f'Header sprites: {self.sff_info.sprite_count}',
            f'Parsed sprites: {len(self.sff_info.sprites)}',
            f'Supported export: {"yes" if self.sff_info.is_supported_for_extraction else "metadata only"}',
        ]
        if self.sff_info.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in self.sff_info.warnings[:8])
        self.set_text(self.sprite_info, '\n'.join(lines))
        for spr in self.sff_info.sprites:
            iid = self.sprite_tree.insert('', 'end', text=str(spr.index), values=(spr.group, spr.image, f'{spr.x},{spr.y}', f'{spr.length:,}', spr.format_hint), tags=(str(spr.index),))
        if self.sff_info.sprites:
            first = self.sprite_tree.get_children()[0]
            self.sprite_tree.selection_set(first)
            self.sprite_tree.focus(first)
            self.on_sprite_select()

    def _selected_sprite(self):
        if not self.sff_info:
            return None
        sel = self.sprite_tree.selection()
        if not sel:
            return None
        try:
            idx = int(self.sprite_tree.item(sel[0], 'tags')[0])
        except Exception:
            return None
        for spr in self.sff_info.sprites:
            if spr.index == idx:
                return spr
        return None

    def on_sprite_select(self, event=None):
        spr = self._selected_sprite()
        if not spr or not self.sff_path:
            return
        lines = [
            f'Sprite #{spr.index}',
            f'Group/Image: {spr.group},{spr.image}',
            f'Axis: {spr.x},{spr.y}',
            f'Payload bytes: {spr.length:,}',
            f'Payload offset: 0x{spr.data_offset:X}',
            f'Format hint: {spr.format_hint}',
            f'Same palette flag: {spr.same_palette}',
        ]
        if spr.comment:
            lines.append(f'Comment: {spr.comment}')
        self.set_text(self.sprite_info, '\n'.join(lines))
        self.sprite_canvas.delete('all')
        self.current_preview_image = None
        if spr.format_hint not in {'pcx', 'png'}:
            self.sprite_canvas.create_text(20, 20, anchor='nw', text='Preview unavailable for this payload type.')
            return
        tmp_dir = Path.home() / '.mugenforge_preview'
        try:
            exported = export_sprite(self.sff_path, spr, tmp_dir)
            preview_path = exported
            if exported.suffix.lower() == '.pcx':
                png_path = exported.with_suffix('.png')
                if try_convert_to_png(exported, png_path):
                    preview_path = png_path
                else:
                    self.sprite_canvas.create_text(20, 20, anchor='nw', text='PCX exported. Install Pillow for in-app PCX preview.\nUse Export Selected to save it.')
                    return
            img = tk.PhotoImage(file=str(preview_path))
            self.current_preview_image = img
            cw = max(360, self.sprite_canvas.winfo_width() or 360)
            ch = max(360, self.sprite_canvas.winfo_height() or 360)
            self.sprite_canvas.create_image(cw//2, ch//2, image=img)
        except Exception as exc:
            self.sprite_canvas.create_text(20, 20, anchor='nw', text=f'Preview failed: {exc}')

    def export_selected_sprite(self):
        spr = self._selected_sprite()
        if not spr or not self.sff_path:
            messagebox.showinfo('No sprite selected', 'Open an SFF file and select a sprite first.')
            return
        out_dir = filedialog.askdirectory(title='Choose sprite export folder')
        if not out_dir:
            return
        out = export_sprite(self.sff_path, spr, Path(out_dir))
        self.status_var.set(f'Exported sprite: {out}')
        messagebox.showinfo('Exported', f'Exported:\n{out}')

    def export_sff_sprites(self):
        path = self.sff_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.sff':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SFF open', 'Open an .sff file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SFF sprite export')
        if not out_dir:
            return
        outputs = export_all_sprites(path, Path(out_dir))
        self.status_var.set(f'Exported {len(outputs)} sprites from {path.name}')
        messagebox.showinfo('Export complete', f'Exported {len(outputs)} sprite payloads.\n\nFolder:\n{out_dir}')



    def stage_sff_replacement(self):
        path = self.sff_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.sff':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SFF open', 'Open an .sff file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SFF replacement staging')
        if not out_dir:
            return
        try:
            manifest = stage_sff_replacement_manifest(path, Path(out_dir))
            summary = summarize_replacement_manifest(manifest)
            self.set_text(self.sprite_info, summary)
            self.status_var.set(f'Staged SFF replacement manifest: {manifest.name}')
            messagebox.showinfo('Replacement manifest created', f'Created:\n{manifest}\n\nEdit the exported sprite files or set replace_with paths, then build a replaced SFF v1.')
        except Exception as exc:
            messagebox.showerror('SFF replacement staging failed', str(exc))

    def _ask_replacement_manifest_path(self):
        path = filedialog.askopenfilename(
            title='Choose SFF replacement manifest',
            filetypes=[('MugenForge SFF replacement manifest', 'mugenforge_sff_replacement_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_sff_replacement_manifest(self):
        manifest = self._ask_replacement_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sprite_info, summarize_replacement_manifest(manifest))
            self.status_var.set(f'Inspected replacement manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Replacement manifest inspect failed', str(exc))

    def build_replaced_sff(self):
        manifest = self._ask_replacement_manifest_path()
        if not manifest:
            return
        out = filedialog.asksaveasfilename(
            title='Save rebuilt SFF v1 file',
            initialfile='rebuilt_replacement.sff',
            defaultextension='.sff',
            filetypes=[('MUGEN SFF', '*.sff'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_sff_v1_from_replacement_manifest(manifest, Path(out))
            msg = [
                f'Built replaced SFF v1: {out}',
                f'Sprites: {len(info.sprites)}',
                f'Layout: {info.variant}',
                '',
                'Important: this creates a fresh SFF v1-style PCX chain. It does not patch or preserve SFF v2 tables/compression.',
            ]
            if info.warnings:
                msg += ['', 'Warnings:'] + [f'- {w}' for w in info.warnings[:8]]
            self.set_text(self.sprite_info, '\n'.join(msg))
            self.populate_sprite_browser(Path(out))
            self.status_var.set(f'Built replaced SFF v1: {Path(out).name}')
            messagebox.showinfo('Replaced SFF build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('Replaced SFF build failed', str(exc))


    def _sheet_int(self, name: str) -> int:
        try:
            return int(self.sheet_vars[name].get())
        except Exception as exc:
            raise ValueError(f'{name} must be an integer.') from exc

    def choose_sprite_sheet(self):
        path = filedialog.askopenfilename(title='Choose PNG sprite sheet', filetypes=[('PNG images', '*.png'), ('All files', '*.*')])
        if not path:
            return
        self.sheet_path = Path(path)
        self.status_var.set(f'Sprite sheet selected: {self.sheet_path.name}')
        self.preview_sprite_sheet_grid()

    def _compute_current_sheet_slices(self):
        if not self.sheet_path:
            raise ValueError('Choose a PNG sprite sheet first.')
        return compute_grid_slices(
            self.sheet_path,
            self._sheet_int('cell_w'), self._sheet_int('cell_h'),
            self._sheet_int('cols'), self._sheet_int('rows'),
            self._sheet_int('margin_x'), self._sheet_int('margin_y'),
            self._sheet_int('space_x'), self._sheet_int('space_y'),
            self._sheet_int('group'), self._sheet_int('start_image'),
            self._sheet_int('axis_x'), self._sheet_int('axis_y'),
        )

    def preview_sprite_sheet_grid(self):
        try:
            self.sheet_slices = self._compute_current_sheet_slices()
            self.sheet_tree.delete(*self.sheet_tree.get_children())
            for sl in self.sheet_slices:
                self.sheet_tree.insert('', 'end', text=str(sl.index), values=(sl.group, sl.image, f'{sl.x},{sl.y},{sl.w},{sl.h}', f'{sl.axis_x},{sl.axis_y}', sl.filename))
            self.sheet_canvas.delete('all')
            self.sheet_preview_photo = make_preview_image(self.sheet_path, self.sheet_slices)
            self.sheet_canvas.create_image(10, 10, anchor='nw', image=self.sheet_preview_photo)
            info = [
                f'Sheet: {self.sheet_path}',
                f'Slices: {len(self.sheet_slices)}',
                'This creates a staged PNG slice set and JSON manifest. Use Build SFF v1 to compile a simple SFF from the manifest.',
                'Use Append AIR Action while an AIR file is open to add matching group/image frame lines.',
                'Use Build SFF v1 after exporting slices + manifest to create a starter SFF.',
            ]
            self.set_text(self.sheet_info, '\n'.join(info))
        except Exception as exc:
            messagebox.showerror('Sprite sheet preview failed', str(exc))

    def export_sprite_sheet_slices(self):
        try:
            if not self.sheet_slices:
                self.sheet_slices = self._compute_current_sheet_slices()
            out_dir = filedialog.askdirectory(title='Choose output folder for staged sprite slices')
            if not out_dir:
                return
            out_path = Path(out_dir)
            outputs = export_grid_slices(self.sheet_path, self.sheet_slices, out_path)
            manifest = write_manifest(self.sheet_path, self.sheet_slices, out_path / 'mugenforge_sprite_manifest.json')
            self.status_var.set(f'Exported {len(outputs)} staged sprites + manifest')
            messagebox.showinfo('Export complete', f'Exported {len(outputs)} PNG slices.\nManifest:\n{manifest}')
        except Exception as exc:
            messagebox.showerror('Sprite sheet export failed', str(exc))

    def append_air_action_from_sheet(self):
        try:
            if not self.sheet_slices:
                self.sheet_slices = self._compute_current_sheet_slices()
            action_number = simpledialog.askinteger('AIR Action Number', 'Action number to append:', initialvalue=self._sheet_int('group'))
            if action_number is None:
                return
            ticks = self._sheet_int('ticks')
            block = make_air_action_from_slices(action_number, self.sheet_slices, ticks)
            if self.current_path and self.current_path.suffix.lower() == '.air':
                self.editor.configure(state='normal')
                existing = self.editor.get('1.0', 'end-1c').rstrip()
                new_text = existing + '\n\n' + block
                self.editor.delete('1.0', 'end')
                self.editor.insert('1.0', new_text)
                self.editor.edit_modified(True)
                self.dirty = True
                self.populate_air_timeline(new_text)
                self.populate_animation_player(new_text)
                self.populate_clsn_editor(new_text)
                self.status_var.set(f'Appended AIR action {action_number} from sprite sheet staging')
                messagebox.showinfo('AIR updated in editor', 'Action block was appended to the editor buffer. Review it, then save the AIR file.')
            else:
                out = filedialog.asksaveasfilename(title='Save AIR action block', defaultextension='.air', filetypes=[('AIR/Text', '*.air'), ('Text', '*.txt')])
                if not out:
                    return
                Path(out).write_text(block, encoding='utf-8')
                self.status_var.set(f'Saved AIR action block: {out}')
        except Exception as exc:
            messagebox.showerror('Append AIR action failed', str(exc))


    def _ask_manifest_path(self):
        # Prefer the last sheet export folder only when the user selects it explicitly; this avoids guessing.
        path = filedialog.askopenfilename(
            title='Choose MugenForge sprite manifest',
            filetypes=[('MugenForge manifest', 'mugenforge_sprite_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_sprite_manifest(self):
        manifest = self._ask_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sheet_info, summarize_manifest_for_sff(manifest))
            self.notebook.select(6)
            self.status_var.set(f'Inspected manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('Manifest inspect failed', str(exc))

    def build_sff_from_sheet_manifest(self):
        manifest = self._ask_manifest_path()
        if not manifest:
            return
        default_name = 'staged_build.sff'
        try:
            import json
            data = json.loads(manifest.read_text(encoding='utf-8'))
            source_sheet = Path(str(data.get('source_sheet', '')))
            if source_sheet.name:
                default_name = source_sheet.stem + '.sff'
        except Exception:
            pass
        out = filedialog.asksaveasfilename(
            title='Save built SFF v1 file',
            initialfile=default_name,
            defaultextension='.sff',
            filetypes=[('MUGEN SFF', '*.sff'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_sff_v1_from_manifest(manifest, Path(out))
            msg = [
                f'Built SFF: {out}',
                f'Parsed sprites after build: {len(info.sprites)}',
                f'Header sprite count: {info.sprite_count}',
                '',
                'Important: this is an SFF v1-style PCX builder for staged sprites. It is meant for starter characters and pipeline testing, not full SFF v2 parity yet.',
            ]
            if info.warnings:
                msg.append('')
                msg.append('Warnings:')
                msg.extend(f'- {w}' for w in info.warnings[:8])
            self.status_var.set(f'Built SFF v1: {Path(out).name}')
            self.set_text(self.sheet_info, '\n'.join(msg))
            if Path(out).exists():
                self.populate_sprite_browser(Path(out))
                self.notebook.select(5)
            messagebox.showinfo('SFF build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('SFF build failed', str(exc))


    def populate_sound_browser(self, path: Path):
        self.snd_path = path
        self.snd_info = read_snd(path)
        self.sound_tree.delete(*self.sound_tree.get_children())
        lines = [
            f'SND: {path.name}',
            f'Signature: {"yes" if self.snd_info.has_signature else "not detected"}',
            f'Version bytes: {self.snd_info.version_text}',
            f'Header count hint: {self.snd_info.declared_count if self.snd_info.declared_count is not None else "unknown"}',
            f'RIFF/WAVE sounds found: {len(self.snd_info.sounds)}',
            'Export mode: read-only WAV payload extraction',
        ]
        if self.snd_info.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in self.snd_info.warnings[:8])
        self.set_text(self.sound_info, '\n'.join(lines))
        for snd in self.snd_info.sounds:
            fmt = []
            if snd.channels is not None:
                fmt.append(f'{snd.channels}ch')
            if snd.sample_rate is not None:
                fmt.append(f'{snd.sample_rate}Hz')
            if snd.bits_per_sample is not None:
                fmt.append(f'{snd.bits_per_sample}bit')
            if snd.format_tag is not None:
                fmt.append(f'fmt={snd.format_tag}')
            fmt_text = ', '.join(fmt) if fmt else 'unknown'
            self.sound_tree.insert('', 'end', text=str(snd.index), values=(snd.id_text, f'0x{snd.riff_offset:X}', f'{snd.length:,}', fmt_text), tags=(str(snd.index),))
        if self.snd_info.sounds:
            first = self.sound_tree.get_children()[0]
            self.sound_tree.selection_set(first)
            self.sound_tree.focus(first)
            self.on_sound_select()

    def _selected_sound(self):
        if not self.snd_info:
            return None
        sel = self.sound_tree.selection()
        if not sel:
            return None
        try:
            idx = int(self.sound_tree.item(sel[0], 'tags')[0])
        except Exception:
            return None
        for snd in self.snd_info.sounds:
            if snd.index == idx:
                return snd
        return None

    def on_sound_select(self, event=None):
        snd = self._selected_sound()
        if not snd:
            return
        lines = [
            f'Sound #{snd.index}',
            f'ID: {snd.id_text}',
            f'RIFF offset: 0x{snd.riff_offset:X}',
            f'WAV bytes: {snd.length:,}',
            f'Header offset guess: {"0x%X" % snd.header_offset if snd.header_offset is not None else "unknown"}',
            f'Format tag: {snd.format_tag if snd.format_tag is not None else "unknown"}',
            f'Channels: {snd.channels if snd.channels is not None else "unknown"}',
            f'Sample rate: {snd.sample_rate if snd.sample_rate is not None else "unknown"}',
            f'Byte rate: {snd.byte_rate if snd.byte_rate is not None else "unknown"}',
            f'Bits/sample: {snd.bits_per_sample if snd.bits_per_sample is not None else "unknown"}',
        ]
        if snd.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in snd.warnings)
        self.set_text(self.sound_info, '\n'.join(lines))

    def export_wav_cue_sheet_ui(self):
        folder = filedialog.askdirectory(title='Choose folder of WAV files for cue sheet')
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save WAV cue sheet', defaultextension='.md', initialfile='MUGENFORGE_SOUND_CUE_SHEET.md', filetypes=[('Markdown', '*.md'), ('Text', '*.txt')])
        if not out:
            return
        try:
            path = sound_cue_sheet(Path(folder), Path(out))
            self.set_text(self.sound_info, f'Cue sheet exported:\n{path}\n\n' + path.read_text(encoding='utf-8'))
            self.status_var.set(f'Cue sheet exported: {path.name}')
        except Exception as exc:
            messagebox.showerror('Cue sheet failed', str(exc))

    def export_selected_sound(self):
        snd = self._selected_sound()
        if not snd or not self.snd_path:
            messagebox.showinfo('No sound selected', 'Open an SND file and select a sound first.')
            return
        out_dir = filedialog.askdirectory(title='Choose WAV export folder')
        if not out_dir:
            return
        out = export_sound(self.snd_path, snd, Path(out_dir))
        self.status_var.set(f'Exported sound: {out}')
        messagebox.showinfo('Exported', f'Exported:\n{out}')

    def export_snd_sounds(self):
        path = self.snd_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.snd':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SND open', 'Open an .snd file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SND WAV export')
        if not out_dir:
            return
        outputs = export_all_sounds(path, Path(out_dir))
        self.status_var.set(f'Exported {len(outputs)} WAV files from {path.name}')
        messagebox.showinfo('Export complete', f'Exported {len(outputs)} WAV files.\n\nFolder:\n{out_dir}')

    def make_placeholder_sound_bank_ui(self):
        if self.project_root:
            default_dir = self.project_root / 'sounds'
            default_dir.mkdir(exist_ok=True)
            folder = filedialog.askdirectory(title='Choose folder for placeholder WAV bank', initialdir=str(default_dir))
        else:
            folder = filedialog.askdirectory(title='Choose folder for placeholder WAV bank')
        if not folder:
            return
        try:
            manifest = make_placeholder_sound_bank(Path(folder))
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.notebook.select(7)
            self.status_var.set(f'Created placeholder sound bank: {manifest.name}')
            messagebox.showinfo('Placeholder sound bank created', f'Created silent placeholder WAVs and manifest:\n{manifest}\n\nUse Build SND to package them, then replace WAVs with real sounds later.')
        except Exception as exc:
            messagebox.showerror('Placeholder sound bank failed', str(exc))

    def make_snd_manifest(self):
        folder = filedialog.askdirectory(title='Choose folder containing WAV files')
        if not folder:
            return
        try:
            manifest = make_snd_manifest_from_wav_folder(Path(folder))
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.status_var.set(f'Created SND manifest: {manifest.name}')
            messagebox.showinfo('SND manifest created', f'Created manifest:\n{manifest}\n\nFilename IDs are inferred from names like 5_0.wav or sound_5_0.wav. Edit the JSON if the group/sound IDs need correction.')
        except Exception as exc:
            messagebox.showerror('SND manifest failed', str(exc))

    def _ask_snd_manifest_path(self):
        path = filedialog.askopenfilename(
            title='Choose MugenForge SND manifest',
            filetypes=[('MugenForge SND manifest', 'mugenforge_snd_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_snd_manifest(self):
        manifest = self._ask_snd_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.notebook.select(7)
            self.status_var.set(f'Inspected SND manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('SND manifest inspect failed', str(exc))

    def build_snd_from_manifest_ui(self):
        manifest = self._ask_snd_manifest_path()
        if not manifest:
            return
        default_name = 'staged_build.snd'
        out = filedialog.asksaveasfilename(
            title='Save built SND file',
            initialfile=default_name,
            defaultextension='.snd',
            filetypes=[('MUGEN SND', '*.snd'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_snd_from_manifest(manifest, Path(out))
            msg = [
                f'Built SND: {out}',
                f'Parsed sounds after build: {len(info.sounds)}',
                f'Header count hint: {info.declared_count}',
                '',
                'Important: this is a simple RIFF/WAVE SND builder for starter characters and pipeline testing. Keep backups before replacing mature production SND files.',
            ]
            if info.warnings:
                msg.append('')
                msg.append('Warnings:')
                msg.extend(f'- {w}' for w in info.warnings[:8])
            self.status_var.set(f'Built SND: {Path(out).name}')
            self.set_text(self.sound_info, '\n'.join(msg))
            if Path(out).exists():
                self.populate_sound_browser(Path(out))
                self.notebook.select(7)
            messagebox.showinfo('SND build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('SND build failed', str(exc))

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

    def _author_int(self, name: str, default: int) -> int:
        try:
            return int(self.author_vars[name].get())
        except Exception:
            return default

    def _author_text(self, name: str, default: str) -> str:
        value = self.author_vars[name].get().strip()
        return value or default

    def _insert_editor_snippet(self, snippet: str):
        if not self.current_path or self.current_path.suffix.lower() not in TEXT_EXTS:
            messagebox.showinfo('No text file', 'Open a CMD, CNS, ST, or AIR/text file before inserting code.')
            return
        self.editor.configure(state='normal')
        if not snippet.startswith('\n'):
            snippet = '\n' + snippet
        self.editor.insert('insert', snippet)
        self.editor.edit_modified(True)
        self.dirty = True
        self.status_var.set('Inserted generated snippet. Save when ready.')

    def insert_command_template(self):
        snippet = command_template(
            name=self._author_text('cmd_name', 'x'),
            command=self._author_text('cmd_input', 'x'),
            time=self._author_int('cmd_time', 1),
        )
        self._insert_editor_snippet(snippet)

    def insert_changestate_template(self):
        snippet = negative_one_changestate_template(
            command_name=self._author_text('cmd_name', 'x'),
            state_no=self._author_int('state_no', 200),
        )
        self._insert_editor_snippet(snippet)

    def insert_attack_state_template(self):
        snippet = attack_state_template(
            state_no=self._author_int('state_no', 200),
            anim_no=self._author_int('anim_no', self._author_int('state_no', 200)),
            damage=self._author_int('damage', 35),
            sound_group=self._author_int('sound_group', 5),
            sound_index=self._author_int('sound_index', 0),
        )
        self._insert_editor_snippet(snippet)

    def insert_projectile_state_template(self):
        snippet = projectile_state_template(
            state_no=self._author_int('state_no', 1000),
            anim_no=self._author_int('anim_no', self._author_int('state_no', 1000)),
            damage=self._author_int('damage', 45),
        )
        self._insert_editor_snippet(snippet)

    def insert_helper_explod_template(self):
        state_no = self._author_int('state_no', 1200)
        snippet = helper_explod_template(state_no=state_no, helper_id=state_no, helper_state=state_no + 1, explod_anim=state_no + 2)
        self._insert_editor_snippet(snippet)

    def inspect_current_code(self):
        text = self.editor.get('1.0', 'end-1c')
        report = inspect_code_text(text)
        lines = ['Current code inspection', '']
        lines.append(f'Commands defined: {len(report.command_names)}')
        if report.command_names:
            lines.append('  ' + ', '.join(report.command_names[:80]))
        lines.append(f'StateDefs defined: {len(report.state_numbers)}')
        if report.state_numbers:
            lines.append('  ' + ', '.join(str(x) for x in report.state_numbers[:80]))
        if report.referenced_commands:
            lines.append('\nCommands referenced in triggers:')
            lines.append('  ' + ', '.join(report.referenced_commands[:80]))
        if report.missing_command_defs:
            lines.append('\nMissing command definitions:')
            for item in report.missing_command_defs:
                lines.append(f'  - {item}')
        if report.unreferenced_commands:
            lines.append('\nDefined commands not referenced in this file:')
            for item in report.unreferenced_commands[:80]:
                lines.append(f'  - {item}')
        if report.missing_state_targets:
            lines.append('\nChangeState targets without local StateDef:')
            for item in report.missing_state_targets[:80]:
                lines.append(f'  - {item}')
        if report.notes:
            lines.append('\nParser notes:')
            for note in report.notes[:80]:
                lines.append(f'  - {note}')
        self.set_text(self.author_output, '\n'.join(lines))
        self.notebook.select(self.author_frame)

    def inspect_whole_character_code(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        self.set_text(self.author_output, inspect_character_folder(self.project_root))
        self.notebook.select(self.author_frame)

    def package_character(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        out = filedialog.asksaveasfilename(
            title='Save packaged character ZIP',
            defaultextension='.zip',
            initialfile=f'{self.project_root.name}_mugenforge_package.zip',
            filetypes=[('Zip archive', '*.zip')],
        )
        if not out:
            return
        count = package_character_zip(self.project_root, Path(out), include_backups=False)
        self.status_var.set(f'Packaged {count} files: {out}')
        messagebox.showinfo('Package complete', f'Packaged {count} files into:\n{out}')

    def _wizard_spec(self):
        data = {name: var.get() for name, var in self.wizard_vars.items()}
        return normalize_spec(**data)

    def _wizard_package(self):
        spec = self._wizard_spec()
        package = build_move_package(spec)
        self.wizard_preview_cache = package
        return package

    def wizard_generate_preview(self):
        package = self._wizard_package()
        text = package.summary
        text += '\n' + '=' * 72 + '\nCMD BLOCK\n' + '=' * 72 + '\n' + package.cmd_block
        text += '\n' + '=' * 72 + '\nCNS/ST BLOCK\n' + '=' * 72 + '\n' + package.cns_block
        text += '\n' + '=' * 72 + '\nAIR BLOCK\n' + '=' * 72 + '\n' + package.air_block
        self.set_text(self.wizard_output, text)
        try:
            self.notebook.select(self.wizard_frame)
        except Exception:
            pass

    def wizard_insert_block(self, kind: str):
        package = self._wizard_package()
        block = {'cmd': package.cmd_block, 'cns': package.cns_block, 'air': package.air_block}[kind]
        if not self.current_path or self.current_path.suffix.lower() not in TEXT_EXTS:
            messagebox.showinfo('No text file', 'Open the target CMD, CNS/ST, or AIR file before inserting this block.')
            return
        expected = {'cmd': {'.cmd'}, 'cns': {'.cns', '.st'}, 'air': {'.air'}}[kind]
        if self.current_path.suffix.lower() not in expected:
            if not messagebox.askyesno('File type mismatch', f'This is normally inserted into {sorted(expected)} files. Insert into {self.current_path.name} anyway?'):
                return
        self._insert_editor_snippet(block)
        self.wizard_generate_preview()

    def wizard_append_to_project(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        package = self._wizard_package()
        results = append_move_to_project(self.project_root, package)
        text = package.summary + '\nAppend results:\n'
        text += '\n'.join(f'- {line}' for line in results)
        self.set_text(self.wizard_output, text)
        self.reload_project()
        messagebox.showinfo('Move appended', '\n'.join(results))

    def choose_act_palette(self):
        path = filedialog.askopenfilename(
            title='Choose ACT palette',
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if path:
            self.populate_palette_browser(Path(path))
            self.notebook.select(self.palette_frame)

    def populate_palette_browser(self, path: Path):
        try:
            info = read_act(path)
        except Exception as exc:
            messagebox.showerror('Palette load failed', str(exc))
            return
        self.palette_info = info
        if hasattr(self, 'palette_tree'):
            self.palette_tree.delete(*self.palette_tree.get_children())
            for idx, (r, g, b) in enumerate(info.colors):
                self.palette_tree.insert('', 'end', text=str(idx), values=(f'{r}, {g}, {b}', f'#{r:02X}{g:02X}{b:02X}'))
        self.draw_palette_grid()
        lines = [f'Palette: {path.name}', f'Colors: {len(info.colors)}', '']
        if info.warnings:
            lines.append('Warnings:')
            lines += [f'- {w}' for w in info.warnings]
        else:
            lines.append('ACT palette loaded normally.')
        lines.append('\nTip: index 0 is commonly used as the transparent/background color in many sprite workflows. Use the move-to-index-0 button when your transparent color is in the wrong slot.')
        self.set_text(self.palette_info_text, '\n'.join(lines))
        self.status_var.set(f'Loaded palette: {path.name}')

    def draw_palette_grid(self, selected_index: int | None = None):
        if not hasattr(self, 'palette_canvas'):
            return
        self.palette_canvas.delete('all')
        info = self.palette_info
        if not info:
            self.palette_canvas.create_text(20, 20, anchor='nw', text='Open an ACT palette or build one from an image.')
            return
        size = 28
        pad = 8
        cols = 16
        for idx, (r, g, b) in enumerate(info.colors[:256]):
            x = pad + (idx % cols) * size
            y = pad + (idx // cols) * size
            color = f'#{r:02X}{g:02X}{b:02X}'
            outline = 'black' if selected_index == idx else '#777777'
            width = 3 if selected_index == idx else 1
            self.palette_canvas.create_rectangle(x, y, x + size - 3, y + size - 3, fill=color, outline=outline, width=width)
            if idx == 0:
                self.palette_canvas.create_text(x + 3, y + 2, anchor='nw', text='0', fill='white' if (r+g+b) < 384 else 'black', font=('Consolas', 8))

    def on_palette_select(self, event=None):
        if not self.palette_info or not hasattr(self, 'palette_tree'):
            return
        sel = self.palette_tree.selection()
        if not sel:
            return
        try:
            idx = int(self.palette_tree.item(sel[0], 'text'))
        except Exception:
            return
        self.draw_palette_grid(idx)
        r, g, b = self.palette_info.colors[idx]
        self.set_text(self.palette_info_text, f'Palette: {self.palette_info.path.name}\nSelected index: {idx}\nRGB: {r}, {g}, {b}\nHex: #{r:02X}{g:02X}{b:02X}')

    def export_palette_json_ui(self):
        if not self.palette_info:
            messagebox.showinfo('No palette', 'Open an ACT palette first.')
            return
        out = filedialog.asksaveasfilename(
            title='Export palette JSON',
            defaultextension='.json',
            initialfile=self.palette_info.path.with_suffix('.palette.json').name,
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')]
        )
        if not out:
            return
        write_palette_json(self.palette_info, Path(out))
        self.status_var.set(f'Exported palette JSON: {Path(out).name}')
        messagebox.showinfo('Palette exported', f'Wrote:\n{out}')

    def build_act_from_image_ui(self):
        image = filedialog.askopenfilename(
            title='Choose image to extract palette from',
            filetypes=[('Images', '*.png *.pcx *.bmp *.gif'), ('All files', '*.*')]
        )
        if not image:
            return
        out = filedialog.asksaveasfilename(
            title='Save ACT palette',
            defaultextension='.act',
            initialfile=Path(image).with_suffix('.act').name,
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_act_from_image(Path(image), Path(out))
        except Exception as exc:
            messagebox.showerror('Build ACT failed', str(exc))
            return
        self.populate_palette_browser(Path(out))
        self.status_var.set(f'Built ACT palette: {Path(out).name}')
        messagebox.showinfo('ACT palette built', f'Wrote:\n{out}\n\nColors: {len(info.colors)}')

    def palette_move_selected_to_zero_ui(self):
        if not self.palette_info:
            messagebox.showinfo('No palette', 'Open an ACT palette first.')
            return
        sel = self.palette_tree.selection()
        if not sel:
            messagebox.showinfo('No color selected', 'Select the color that should become index 0.')
            return
        try:
            idx = int(self.palette_tree.item(sel[0], 'text'))
        except Exception:
            return
        colors = remap_palette_order(self.palette_info.colors, idx)
        out = filedialog.asksaveasfilename(
            title='Save remapped ACT palette',
            defaultextension='.act',
            initialfile=self.palette_info.path.with_name(self.palette_info.path.stem + '_index0.act').name,
            filetypes=[('ACT palette', '*.act'), ('All files', '*.*')]
        )
        if not out:
            return
        write_act(Path(out), colors)
        self.populate_palette_browser(Path(out))
        self.status_var.set(f'Remapped palette: {Path(out).name}')
        messagebox.showinfo('Palette remapped', f'Moved selected color {idx} to index 0 and wrote:\n{out}')

    def _selected_auto_preset(self):
        if not hasattr(self, 'auto_feature_list'):
            return None
        sel = self.auto_feature_list.curselection()
        if not sel:
            if self.auto_preset_items:
                return preset_by_display(self.auto_preset_items[0])
            return None
        return preset_by_display(self.auto_feature_list.get(sel[0]))

    def auto_on_preset_select(self, event=None):
        preset = self._selected_auto_preset()
        if not preset:
            return
        lines = [f'{preset.name}', '', preset.description, '', f'Category: {preset.category}', f'Difficulty: {preset.difficulty}']
        if preset.beginner_notes:
            lines.append('\nBeginner notes:')
            lines += [f'- {note}' for note in preset.beginner_notes]
        lines.append('\nUse Preview Selected to see the generated code before applying it.')
        self.set_text(self.auto_output, '\n'.join(lines))

    def auto_preview_feature(self):
        preset = self._selected_auto_preset()
        if not preset:
            return
        package = build_feature_package(preset.feature_id)
        self.auto_last_package = package
        self.set_text(self.auto_output, package_preview_text(package))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_apply_selected_feature(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        preset = self._selected_auto_preset()
        if not preset:
            return
        package = build_feature_package(preset.feature_id)
        result = apply_feature_package(self.project_root, package)
        text = package_preview_text(package)
        text += '\n' + '=' * 72 + '\nAPPLY RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n'
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set(f'Feature Bank applied: {preset.name}')
        messagebox.showinfo('Feature applied', result.to_text())

    def auto_apply_beginner_pack_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        if not messagebox.askyesno('Install Beginner Pack', 'This will append multiple beginner features with backups: setup basics, attacks, fireball, dashes, taunt, and debug overlay. Continue?'):
            return
        result = apply_beginner_pack(self.project_root)
        text = 'Beginner Pack applied.\n\n' + result.to_text() + '\n\n' + beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set('Beginner Pack installed.')
        messagebox.showinfo('Beginner Pack complete', result.to_text())

    def auto_setup_project_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        result = auto_setup_project(root)
        self.load_project(root)
        text = 'Auto Setup / Repair complete.\n\n' + result.to_text() + '\n\n' + beginner_project_status(root)
        self.set_text(self.auto_output, text)
        self.notebook.select(self.auto_frame)
        self.status_var.set('Project setup/repair complete.')
        messagebox.showinfo('Setup complete', result.to_text())

    def auto_project_status_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        text = beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.notebook.select(self.auto_frame)

    def auto_export_code_bank_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first.')
            return
        out = export_code_bank_template(self.project_root)
        self.set_text(self.auto_output, f'Wrote editable feature-bank planning template:\n{out}\n\nThis file is for planning and notes. Built-in Feature Bank presets are available directly in this tab.')
        self.reload_project()
        self.status_var.set(f'Wrote {out.name}')
        messagebox.showinfo('Code bank template written', f'Wrote:\n{out}')


    def auto_preview_kit(self):
        if not hasattr(self, 'auto_kit_var'):
            return
        kit_name = self.auto_kit_var.get().strip()
        if not kit_name:
            return
        self.set_text(self.auto_output, kit_preview_text(kit_name))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_apply_kit_ui(self):
        if not self.project_root:
            messagebox.showinfo('No project', 'Open a character folder first, or use Auto Setup / Repair Project and choose a folder.')
            return
        kit_name = self.auto_kit_var.get().strip() if hasattr(self, 'auto_kit_var') else ''
        if not kit_name:
            messagebox.showinfo('No kit selected', 'Choose a Creator Kit first.')
            return
        if not messagebox.askyesno('Install Creator Kit', f'This will append the selected kit with backups:\n\n{kit_name}\n\nContinue?'):
            return
        result = apply_kit(self.project_root, kit_name)
        text = kit_preview_text(kit_name) + '\n' + '=' * 72 + '\nAPPLY RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + beginner_project_status(self.project_root)
        self.set_text(self.auto_output, text)
        self.reload_project()
        self.status_var.set(f'Creator Kit installed: {kit_name}')
        messagebox.showinfo('Creator Kit complete', result.to_text())

    def auto_feature_bank_stats_ui(self):
        self.set_text(self.auto_output, feature_bank_stats_text())
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_preview_archetype(self):
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        self.set_text(self.auto_output, archetype_preview_text(name))
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass

    def auto_write_dashboard_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        result = write_no_code_dashboard(root, name)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        text = archetype_preview_text(name) + '\n' + '=' * 72 + '\nDASHBOARD / CHECKLIST RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + no_code_director_summary(root, name)
        self.set_text(self.auto_output, text)
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('No-code dashboard/checklists written.')
        messagebox.showinfo('No-code dashboard written', result.to_text())

    def auto_one_click_skeleton_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        name = self.auto_archetype_var.get().strip() if hasattr(self, 'auto_archetype_var') else ''
        prompt = (
            'This will create/repair a project, install the selected archetype kit, generate no-code docs, '
            'make placeholder sprites/sounds, and try to build starter SFF/SND files. Backups are used for generated code.\n\n'
            f'Archetype: {name or "Balanced Arcade Fighter"}\n\nContinue?'
        )
        if not messagebox.askyesno('One-Click Playable Skeleton', prompt):
            return
        result = one_click_playable_skeleton(root, name)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        text = archetype_preview_text(name) + '\n' + '=' * 72 + '\nONE-CLICK SKELETON RESULTS\n' + '=' * 72 + '\n' + result.to_text() + '\n\n' + beginner_project_status(root)
        self.set_text(self.auto_output, text)
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('One-click playable skeleton generated.')
        if result.warnings:
            messagebox.showwarning('One-click skeleton complete with warnings', result.to_text())
        else:
            messagebox.showinfo('One-click skeleton complete', result.to_text())

    def auto_make_placeholder_sheet_ui(self):
        root = self.project_root
        if not root:
            chosen = filedialog.askdirectory(title='Choose or create a character project folder')
            if not chosen:
                return
            root = Path(chosen)
        result = make_placeholder_sprite_sheet(root)
        if not self.project_root:
            self.load_project(root)
        else:
            self.reload_project()
        self.set_text(self.auto_output, 'Placeholder Sprite Sheet result:\n\n' + result.to_text() + '\n\nNext: open Sheet Import, load the generated PNG, use the plan JSON settings, export slices, then build SFF v1.')
        try:
            self.notebook.select(self.auto_frame)
        except Exception:
            pass
        self.status_var.set('Placeholder sprite sheet generated.')
        if result.warnings:
            messagebox.showwarning('Placeholder sheet', result.to_text())
        else:
            messagebox.showinfo('Placeholder sheet generated', result.to_text())


    def _factory_root_or_choose(self):
        root = self.project_root
        if root:
            return root
        chosen = filedialog.askdirectory(title='Choose or create a character project folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _factory_show_result(self, result, title='Factory+'):
        text = result.to_text() if hasattr(result, 'to_text') else str(result)
        try:
            self.set_text(self.factory_plus_output, text)
            self.notebook.select(self.factory_plus_frame)
        except Exception:
            self.set_text(self.analysis, text)
            self.notebook.select(1)
        self.status_var.set(title)
        if getattr(result, 'warnings', None):
            messagebox.showwarning(title, text[:3000])
        else:
            messagebox.showinfo(title, text[:3000])

    def factory_smart_complete_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.smart_complete_project(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Smart Complete / Repair finished')

    def factory_doctor_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_doctor_report(root)
        report = fp.deep_factory_doctor(root)
        try:
            self.set_text(self.factory_plus_output, report + '\n' + result.to_text())
            self.notebook.select(self.factory_plus_frame)
        except Exception:
            self.set_text(self.analysis, report)
            self.notebook.select(1)
        self.status_var.set('Factory+ Doctor report written.')
        messagebox.showinfo('Factory+ Doctor', result.to_text())

    def factory_start_here_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_start_here(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Start Here guide written')

    def factory_function_bank_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.write_function_bank(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ Function Bank written')

    def factory_complete_air_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.ensure_required_animations(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ AIR repair finished')

    def factory_placeholder_sff_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.rebuild_placeholder_sff_from_air(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ placeholder SFF built')

    def factory_bulk_import_sprites_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        folder = filedialog.askdirectory(title='Choose folder of PNG/PCX/GIF sprites named like g200_i0.png')
        if not folder:
            return
        append_air = messagebox.askyesno('Append AIR actions?', 'Append one AIR action per imported sprite group when that action does not already exist?')
        result = fp.bulk_import_sprite_folder(root, Path(folder), append_air=append_air)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ bulk sprite import finished')

    def factory_movelist_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_move_list(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ move list exported')

    def factory_state_map_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_state_map(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ state map exported')

    def factory_balance_sheet_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.export_balance_sheet(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ balance sheet exported')

    def factory_release_zip_ui(self):
        root = self._factory_root_or_choose()
        if not root:
            return
        result = fp.build_release_zip(root)
        self.reload_project()
        self._factory_show_result(result, 'Factory+ release ZIP built')


    def _plus_get_project_root(self):
        if self.project_root:
            return self.project_root
        chosen = filedialog.askdirectory(title='Choose or create a M.U.G.E.N character folder')
        if not chosen:
            return None
        root = Path(chosen)
        self.load_project(root)
        return root

    def _plus_int(self, var, fallback=0):
        try:
            return int(str(var.get()).strip())
        except Exception:
            return fallback

    def _plus_float(self, var, fallback=1.0):
        try:
            return float(str(var.get()).strip())
        except Exception:
            return fallback

    def _plus_find_sff_path(self):
        if self.current_path and self.current_path.suffix.lower() == '.sff':
            return self.current_path
        if self.sff_path and self.sff_path.exists():
            return self.sff_path
        if self.project_root:
            exact = self.project_root / f'{self.project_root.name}.sff'
            if exact.exists():
                return exact
            found = sorted(self.project_root.glob('*.sff'))
            if found:
                return found[0]
        chosen = filedialog.askopenfilename(title='Choose SFF file', filetypes=[('SFF files', '*.sff'), ('All files', '*.*')])
        return Path(chosen) if chosen else None

    def plus_doctor_report_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            text = studio_plus_report_text(root)
            self.set_text(self.plus_output, text)
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Studio Plus Doctor report generated.')
        except Exception as exc:
            messagebox.showerror('Studio Plus Doctor failed', str(exc))

    def plus_write_reports_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            md = write_studio_plus_report(root)
            js = write_studio_plus_report_json(root)
            self.reload_project()
            self.set_text(self.plus_output, f'Wrote Studio Plus reports:\n\n- {md}\n- {js}\n\n' + studio_plus_report_text(root))
            self.notebook.select(self.studio_plus_frame)
            messagebox.showinfo('Reports written', f'Wrote:\n{md}\n{js}')
        except Exception as exc:
            messagebox.showerror('Write reports failed', str(exc))

    def plus_auto_fix_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        if not messagebox.askyesno('Auto Fix / Build Missing Assets', 'This will create/repair project files, append missing standard AIR placeholders with backups, rebuild placeholder SFF/SND assets, and write beginner docs/reports. Continue?'):
            return
        try:
            result = auto_fix_project_plus(root)
            self.reload_project()
            self.set_text(self.plus_output, result.to_text() + '\n' + studio_plus_report_text(root))
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Studio Plus auto-fix completed.')
            messagebox.showinfo('Auto Fix complete', result.to_text())
        except Exception as exc:
            messagebox.showerror('Auto Fix failed', str(exc))

    def plus_snapshot_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            out = make_project_snapshot(root)
            self.set_text(self.plus_output, f'Project snapshot created:\n\n{out}\n\nUse this before heavy edits so you can roll back manually if needed.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Snapshot created: {out.name}')
            messagebox.showinfo('Snapshot created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Snapshot failed', str(exc))

    def plus_release_zip_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        try:
            out = build_release_zip_plus(root)
            self.reload_project()
            self.set_text(self.plus_output, f'Release ZIP created:\n\n{out}\n\nThe ZIP includes a generated release manifest and Studio Plus report.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Release ZIP created: {out.name}')
            messagebox.showinfo('Release ZIP created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Release ZIP failed', str(exc))

    def plus_contact_sheet_ui(self):
        sff = self._plus_find_sff_path()
        if not sff:
            return
        default = sff.with_name(sff.stem + '_contact_sheet.png')
        out = filedialog.asksaveasfilename(title='Save SFF contact sheet', defaultextension='.png', initialfile=default.name, initialdir=str(default.parent), filetypes=[('PNG image', '*.png')])
        if not out:
            return
        try:
            written = create_sff_contact_sheet(sff, Path(out))
            self.set_text(self.plus_output, f'SFF contact sheet created:\n\n{written}\n\nThis is useful for browsing sprite group/image IDs visually, similar to a sprite browser but exportable.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Contact sheet created: {written.name}')
            messagebox.showinfo('Contact sheet created', f'Wrote:\n{written}')
        except Exception as exc:
            messagebox.showerror('Contact sheet failed', str(exc))

    def plus_export_action_gif_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        action_no = self._plus_int(self.plus_action_var, 0)
        default = root / f'action_{action_no}_preview.gif'
        out = filedialog.asksaveasfilename(title='Save AIR action GIF', defaultextension='.gif', initialfile=default.name, initialdir=str(root), filetypes=[('GIF image', '*.gif')])
        if not out:
            return
        try:
            written = export_action_gif(root, action_no, Path(out), scale=2, draw_clsn=True)
            self.set_text(self.plus_output, f'Action GIF exported:\n\nAction: {action_no}\nFile: {written}\n\nThe GIF includes sprite preview when available plus Clsn1/Clsn2 overlays.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Action GIF exported: {written.name}')
            messagebox.showinfo('Action GIF exported', f'Wrote:\n{written}')
        except Exception as exc:
            messagebox.showerror('Action GIF failed', str(exc))

    def plus_air_from_sff_ui(self, append: bool = False):
        root = self._plus_get_project_root()
        if not root:
            return
        if append and not messagebox.askyesno('Append AIR from SFF groups', 'This will append generated AIR actions to the project AIR file and create a backup first. Continue?'):
            return
        try:
            ticks = self._plus_int(self.plus_ticks_var, 5)
            out = generate_air_from_sff_groups(root, ticks=ticks, append=append)
            self.reload_project()
            action = 'Appended generated AIR actions to' if append else 'Generated AIR action file'
            self.set_text(self.plus_output, f'{action}:\n\n{out}\n\nEach SFF group becomes an AIR action and images are sorted by image number. Review timing and labels after generation.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'AIR generated from SFF groups: {out.name}')
            messagebox.showinfo('AIR generated', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Generate AIR failed', str(exc))

    def plus_clone_air_action_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        source = self._plus_int(self.plus_clone_source_var, 200)
        new = self._plus_int(self.plus_clone_new_var, 1200)
        tick_scale = self._plus_float(self.plus_tick_scale_var, 1.0)
        x_offset = self._plus_int(self.plus_x_offset_var, 0)
        y_offset = self._plus_int(self.plus_y_offset_var, 0)
        try:
            out = clone_air_action_variant(root, source, new, tick_scale=tick_scale, x_offset=x_offset, y_offset=y_offset)
            self.reload_project()
            self.set_text(self.plus_output, f'Cloned AIR action variant:\n\nSource action: {source}\nNew action: {new}\nTick scale: {tick_scale}\nOffset: {x_offset},{y_offset}\nChanged: {out}\n\nUse this for fast variants like EX timing, mirrored-feel timing tests, intro/win reuse, and prototype specials.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Cloned AIR action {source} -> {new}')
            messagebox.showinfo('AIR action cloned', f'Updated:\n{out}')
        except Exception as exc:
            messagebox.showerror('Clone AIR action failed', str(exc))

    def plus_batch_import_sprites_ui(self):
        root = self._plus_get_project_root()
        if not root:
            return
        folder = filedialog.askdirectory(title='Choose folder of sprite images')
        if not folder:
            return
        default = root / f'{root.name}_batch_import.sff'
        out = filedialog.asksaveasfilename(title='Save built SFF v1', defaultextension='.sff', initialfile=default.name, initialdir=str(root), filetypes=[('SFF files', '*.sff')])
        if not out:
            return
        try:
            manifest, air_snippet = batch_import_sprite_folder_to_sff(
                Path(folder), Path(out),
                default_group=self._plus_int(self.plus_import_group_var, 9000),
                axis_x=self._plus_int(self.plus_axis_x_var, 32),
                axis_y=self._plus_int(self.plus_axis_y_var, 64),
                ticks=self._plus_int(self.plus_ticks_var, 5),
            )
            self.reload_project()
            self.set_text(self.plus_output, f'Batch sprite import complete:\n\nSFF: {out}\nManifest: {manifest}\nAIR snippets: {air_snippet}\n\nFilename tips: g200_i0.png and 200_0.png keep their IDs. Other files use the default group and sorted image index.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set('Batch sprite folder imported to SFF.')
            messagebox.showinfo('Batch import complete', f'Wrote:\n{out}\n{manifest}\n{air_snippet}')
        except Exception as exc:
            messagebox.showerror('Batch sprite import failed', str(exc))

    def plus_stage_template_ui(self):
        parent = self.project_root.parent if self.project_root else Path(filedialog.askdirectory(title='Choose parent folder for stage template') or '')
        if not parent or not str(parent):
            return
        name = simpledialog.askstring('Stage Template', 'Stage folder/name:', initialvalue='new_stage')
        if not name:
            return
        try:
            out = make_stage_template(parent, name)
            self.set_text(self.plus_output, f'Stage template created:\n\n{out}\n\nThis expands MugenForge beyond characters with a beginner-safe stage DEF starter. Add real stage art/SFF later.')
            self.notebook.select(self.studio_plus_frame)
            self.status_var.set(f'Stage template created: {out.name}')
            messagebox.showinfo('Stage template created', f'Wrote:\n{out}')
        except Exception as exc:
            messagebox.showerror('Stage template failed', str(exc))


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
