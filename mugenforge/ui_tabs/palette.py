from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import AppBackedTab


class PaletteTab(AppBackedTab):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        palette_frame = ttk.Frame(self.notebook)
        self.frame = palette_frame
        self.app.palette_frame = palette_frame
        palette_frame.columnconfigure(0, weight=1)
        palette_frame.rowconfigure(1, weight=1)

        top = ttk.Frame(palette_frame, padding=(4, 4))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Button(top, text='Open ACT', command=self.app.choose_act_palette).grid(row=0, column=0, padx=3)
        ttk.Button(top, text='Export Palette JSON', command=self.app.export_palette_json_ui).grid(row=0, column=1, padx=3)
        ttk.Button(top, text='Build ACT From Image', command=self.app.build_act_from_image_ui).grid(row=0, column=2, padx=3)
        ttk.Button(top, text='Move Selected Color To Index 0', command=self.app.palette_move_selected_to_zero_ui).grid(row=0, column=3, padx=3)

        body = ttk.Panedwindow(palette_frame, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky='nsew', padx=4, pady=4)
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.app.palette_tree = ttk.Treeview(left, columns=('rgb', 'hex'), show='tree headings')
        self.app.palette_tree.heading('#0', text='Index')
        self.app.palette_tree.heading('rgb', text='RGB')
        self.app.palette_tree.heading('hex', text='Hex')
        self.app.palette_tree.column('#0', width=70, anchor='e')
        self.app.palette_tree.column('rgb', width=160)
        self.app.palette_tree.column('hex', width=100)
        self.app.palette_tree.grid(row=0, column=0, sticky='nsew')
        self.app.palette_tree.bind('<<TreeviewSelect>>', self.app.on_palette_select)
        body.add(left, weight=1)

        right = ttk.Frame(body)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.app.palette_canvas = tk.Canvas(right, bg='white', width=560, height=560)
        self.app.palette_canvas.grid(row=0, column=0, sticky='nsew')
        self.app.palette_info_text = tk.Text(right, wrap='word', height=8, font=('Consolas', 10), state='disabled')
        self.app.palette_info_text.grid(row=1, column=0, sticky='ew', pady=(4, 0))
        body.add(right, weight=2)

        self.notebook.add(palette_frame, text='Palettes')
