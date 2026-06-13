from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..visual_forge import VISUAL_FORGE_VERSION
from .base import AppBackedTab


class VisualForgeHomeTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        home = ttk.Frame(self.notebook)
        self.frame = home
        self.app.vf_home_frame = home
        home.columnconfigure(1, weight=1)
        home.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(home, text=f'Project Home / Wizard Mode - Visual Forge v{VISUAL_FORGE_VERSION}', padding=(10, 8))
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=(
            'Start here. Visual Forge turns MugenForge into a guided no-code workflow: create a project, scaffold moves, edit timing visually, align offsets, place sounds, import legacy characters, and keep safe backups.'
        ), wraplength=1120, justify='left').grid(row=0, column=0, sticky='ew')
        self.app.vf_current_project_var = tk.StringVar(value='No project loaded.')
        ttk.Label(header, textvariable=self.app.vf_current_project_var).grid(row=1, column=0, sticky='w', pady=(6, 0))

        left = ttk.Frame(home, padding=(8, 0))
        left.grid(row=1, column=0, sticky='nsw')
        actions = ttk.LabelFrame(left, text='Start', padding=(8, 8))
        actions.grid(row=0, column=0, sticky='ew')
        ttk.Button(actions, text='Open Character Folder', command=self.app.open_folder).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Create From Wizard', command=self.app.vf_create_project_from_wizard).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Quick Start Current Project', command=self.app.vf_quick_start_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Tutorials / Beginner Workflow', command=self.app.vf_tutorials_ui).grid(row=3, column=0, sticky='ew', pady=2)
        ttk.Button(actions, text='Import Existing Character', command=self.app.vf_import_legacy_from_home).grid(row=4, column=0, sticky='ew', pady=2)

        recent = ttk.LabelFrame(left, text='Open Recent', padding=(8, 8))
        recent.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.app.vf_recent_list = tk.Listbox(recent, width=46, height=8, font=('Consolas', 9), exportselection=False)
        self.app.vf_recent_list.grid(row=0, column=0, sticky='ew')
        ttk.Button(recent, text='Open Selected', command=self.app._vf_open_recent_selected).grid(row=1, column=0, sticky='ew', pady=(4, 2))
        ttk.Button(recent, text='Refresh Recent List', command=self.app._vf_refresh_recent_list).grid(row=2, column=0, sticky='ew', pady=2)

        tools = ttk.LabelFrame(left, text='Project Tools', padding=(8, 8))
        tools.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(tools, text='Write Home Docs', command=self.app.vf_write_home_docs_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Install Templates / Plugins', command=self.app.vf_install_templates_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Write SFF2 Bridge Pack', command=self.app.vf_sff2_pack_ui).grid(row=2, column=0, sticky='ew', pady=2)
        ttk.Button(tools, text='Create Backup Snapshot', command=self.app.vf_backup_snapshot_ui).grid(row=3, column=0, sticky='ew', pady=2)

        right = ttk.Frame(home, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        wizard = ttk.LabelFrame(right, text='New Character Wizard', padding=(8, 8))
        wizard.grid(row=0, column=0, sticky='ew')
        self.app.vf_wizard_vars = {}
        rows = [
            ('parent', str(Path.cwd())), ('name', 'new_character'), ('author', 'MugenForge Creator'),
            ('project_type', 'character'), ('template', 'Balanced Starter'), ('archetype', 'Balanced Arcade Fighter'),
            ('life', '1000'), ('attack', '100'), ('defence', '100'), ('power_style', 'classic'),
        ]
        for idx, (key, value) in enumerate(rows):
            ttk.Label(wizard, text=key).grid(row=idx // 2, column=(idx % 2) * 2, sticky='e', padx=(2, 4), pady=2)
            var = tk.StringVar(value=value)
            self.app.vf_wizard_vars[key] = var
            if key == 'parent':
                entry = ttk.Entry(wizard, textvariable=var, width=52)
                entry.grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky='ew', padx=(0, 6), pady=2)
                ttk.Button(wizard, text='Choose', command=self.app.vf_choose_wizard_parent).grid(row=idx // 2, column=4, sticky='w', pady=2)
            elif key in {'project_type', 'template', 'archetype', 'power_style'}:
                values = {
                    'project_type': ('character', 'stage metadata'),
                    'template': ('Balanced Starter', 'Rushdown Starter', 'Projectile Zoner Starter', 'Grappler Starter', 'Anime Mobility Starter', 'Legacy Import'),
                    'archetype': ('Balanced Arcade Fighter', 'Rushdown Combo Fighter', 'Projectile Zoner Fighter', 'Grappler Fighter', 'Anime Air Mobility Fighter', 'Boss / Flashy Character'),
                    'power_style': ('classic', 'EX meter', 'super meter starter', 'none'),
                }[key]
                ttk.Combobox(wizard, textvariable=var, values=values, state='readonly', width=34).grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky='w', padx=(0, 8), pady=2)
            else:
                ttk.Entry(wizard, textvariable=var, width=36).grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky='w', padx=(0, 8), pady=2)
        wizard.columnconfigure(1, weight=1)
        self.app.vf_wizard_install_pack_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(wizard, text='Install Beginner Pack after creation', variable=self.app.vf_wizard_install_pack_var).grid(row=5, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(wizard, text='Create Project', command=self.app.vf_create_project_from_wizard).grid(row=5, column=2, sticky='w', pady=(6, 0))

        note = ttk.LabelFrame(right, text='What Visual Forge will do', padding=(8, 6))
        note.grid(row=1, column=0, sticky='ew', pady=(8, 8))
        ttk.Label(note, text=(
            'The wizard creates clean M.U.G.E.N starter files, writes a dashboard and beginner guide, prepares data-only templates/plugins, and optionally installs starter move scaffolds. It keeps SFF/SND work conservative and does not claim arbitrary SFF2 binary editing.'
        ), wraplength=900, justify='left').grid(row=0, column=0, sticky='ew')

        self.app.vf_home_output = tk.Text(right, wrap='word', font=('Consolas', 10), state='disabled')
        y = ttk.Scrollbar(right, orient='vertical', command=self.app.vf_home_output.yview)
        self.app.vf_home_output.configure(yscrollcommand=y.set)
        self.app.vf_home_output.grid(row=2, column=0, sticky='nsew')
        y.grid(row=2, column=1, sticky='ns')
        self.notebook.add(home, text='Project Home')
        self.app._vf_refresh_recent_list()
        self._set_text(
            self.app.vf_home_output,
            'Welcome to Visual Forge. Create a project with the wizard, open a recent project, or run Quick Start on an existing character folder.',
        )


class VisualTimelineTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        tab = ttk.Frame(self.notebook)
        self.frame = tab
        self.app.vf_timeline_frame = tab
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
        ttk.Button(left, text='Refresh From Project', command=self.app.vf_refresh_timeline_ui).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(left, text='Export Timeline Manifest', command=self.app.vf_timeline_export_ui).grid(row=1, column=0, sticky='ew', pady=2)
        ttk.Label(left, text='Action').grid(row=2, column=0, sticky='w', pady=(8, 2))
        self.app.vf_timeline_action_var = tk.StringVar()
        self.app.vf_timeline_action_combo = ttk.Combobox(left, textvariable=self.app.vf_timeline_action_var, state='readonly', width=34)
        self.app.vf_timeline_action_combo.grid(row=3, column=0, sticky='ew')
        self.app.vf_timeline_action_combo.bind('<<ComboboxSelected>>', self.app.vf_on_timeline_action)
        self.app.vf_timeline_info = tk.Text(left, wrap='word', width=38, height=15, font=('Consolas', 9), state='disabled')
        self.app.vf_timeline_info.grid(row=4, column=0, sticky='ew', pady=(8, 0))

        edit = ttk.LabelFrame(left, text='Selected frame', padding=(6, 6))
        edit.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        self.app.vf_timeline_frame_index_var = tk.StringVar(value='')
        self.app.vf_timeline_ticks_var = tk.StringVar(value='')
        ttk.Label(edit, text='Frame index').grid(row=0, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.app.vf_timeline_frame_index_var, width=8, state='readonly').grid(row=0, column=1, sticky='w')
        ttk.Label(edit, text='Ticks').grid(row=1, column=0, sticky='w')
        ttk.Entry(edit, textvariable=self.app.vf_timeline_ticks_var, width=8).grid(row=1, column=1, sticky='w')
        ttk.Button(edit, text='Save Ticks to AIR (.bak)', command=self.app.vf_timeline_save_ticks).grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))

        play = ttk.LabelFrame(left, text='Preview', padding=(6, 6))
        play.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        ttk.Button(play, text='Play Timeline', command=self.app.vf_timeline_play).grid(row=0, column=0, sticky='ew', pady=2)
        ttk.Button(play, text='Pause', command=self.app.vf_timeline_pause).grid(row=1, column=0, sticky='ew', pady=2)

        right = ttk.Frame(tab, padding=(0, 0))
        right.grid(row=1, column=1, sticky='nsew', padx=(0, 8), pady=(0, 8))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.app.vf_timeline_canvas = tk.Canvas(right, bg='white', height=520, scrollregion=(0, 0, 2400, 700))
        x = ttk.Scrollbar(right, orient='horizontal', command=self.app.vf_timeline_canvas.xview)
        y = ttk.Scrollbar(right, orient='vertical', command=self.app.vf_timeline_canvas.yview)
        self.app.vf_timeline_canvas.configure(xscrollcommand=x.set, yscrollcommand=y.set)
        self.app.vf_timeline_canvas.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        self.app.vf_timeline_canvas.bind('<ButtonPress-1>', self.app.vf_timeline_press)
        self.app.vf_timeline_canvas.bind('<B1-Motion>', self.app.vf_timeline_drag)
        self.app.vf_timeline_canvas.bind('<ButtonRelease-1>', self.app.vf_timeline_release)
        self.app.vf_timeline_model = {}
        self.app.vf_timeline_frame_boxes = {}
        self.app.vf_timeline_preview_ticks = {}
        self.app.vf_timeline_drag_data = None
        self.app.vf_timeline_play_after = None
        self.app.vf_timeline_play_idx = 0
        self.notebook.add(tab, text='Visual Timeline')
