from __future__ import annotations


class AppBackedTab:
    """Adapter for tab controllers that still depend on main app services."""

    def __init__(self, app):
        self.app = app
        self.notebook = app.notebook
        self.frame = None

    def _set_text(self, widget, text: str):
        self.app.set_text(widget, text)

    def _set_status(self, text: str):
        self.app.status_var.set(text)

    def _reload_project(self):
        try:
            self.app.reload_project()
        except Exception:
            pass

    def _select(self, frame=None):
        try:
            self.notebook.select(frame or self.frame)
        except Exception:
            pass

    def _publish(self, *names: str):
        for name in names:
            setattr(self.app, name, getattr(self, name))

    def _create_scrolled_text(self, parent, height=15, row=None, column=None, columnspan=1):
        import tkinter as tk
        from tkinter import ttk
        text = tk.Text(parent, wrap='word', font=('Consolas', 10), state='disabled', height=height)
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        if row is not None and column is not None:
            text.grid(row=row, column=column, sticky='nsew', columnspan=columnspan)
            scrollbar.grid(row=row, column=column + columnspan, sticky='ns')
        return text, scrollbar

    def _create_input_grid(self, parent, fields, columns=2):
        from tkinter import ttk
        widgets = {}
        for idx, item in enumerate(fields):
            label_text = item[0]
            var = item[1]
            widget_type = 'entry'
            if len(item) > 2:
                widget_type = item[2]

            row = idx // columns
            col = (idx % columns) * 2

            lbl = ttk.Label(parent, text=label_text)
            lbl.grid(row=row, column=col, sticky='e', padx=(4, 4), pady=2)

            if widget_type in ('combobox', 'combo'):
                values = item[3] if len(item) > 3 else []
                width = item[4] if len(item) > 4 else 20
                w = ttk.Combobox(parent, textvariable=var, values=values, state='readonly', width=width)
            else:
                width = item[3] if len(item) > 3 else 20
                w = ttk.Entry(parent, textvariable=var, width=width)

            w.grid(row=row, column=col + 1, sticky='w', padx=(0, 8), pady=2)
            widgets[label_text] = (lbl, w)
        return widgets

    def _create_action_buttons(self, parent, button_specs, vertical=True):
        from tkinter import ttk
        buttons = []
        for idx, spec in enumerate(button_specs):
            text = spec[0]
            cmd = spec[1]
            btn = ttk.Button(parent, text=text, command=cmd)

            sticky = spec[2] if len(spec) > 2 else 'ew'
            pady = spec[3] if len(spec) > 3 else 2
            padx = spec[4] if len(spec) > 4 else 0

            if vertical:
                btn.grid(row=idx, column=0, sticky=sticky, pady=pady, padx=padx)
            else:
                btn.grid(row=0, column=idx, sticky=sticky, pady=pady, padx=padx)
            buttons.append(btn)
        return buttons
