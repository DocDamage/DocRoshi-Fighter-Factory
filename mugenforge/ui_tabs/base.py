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

