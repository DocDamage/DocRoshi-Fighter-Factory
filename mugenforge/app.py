from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .app_mixins import AppBehaviorMixins
from .app_state import initialize_app_state
from .ui_tabs.core_builders import AppCoreTabBuilders

APP_TITLE = 'MugenForge Studio 7.5 Continuity Core'

class MugenForgeApp(AppCoreTabBuilders, AppBehaviorMixins, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('1400x850')
        self.minsize(1050, 680)
        initialize_app_state(self)
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
