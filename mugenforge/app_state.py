from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any


def initialize_app_state(app: Any) -> None:
    app.project_root: Path | None = None
    app.current_path: Path | None = None
    app.dirty = False
    app.air_actions = []
    app.sff_info = None
    app.sff_path: Path | None = None
    app.sff_sprite_lookup = {}
    app.current_preview_image = None
    app.snd_info = None
    app.snd_path: Path | None = None
    app.air_line_actions = []
    app.clsn_boxes = []
    app.sheet_path: Path | None = None
    app.sheet_slices = []
    app.sheet_preview_photo = None
    app.clsn_sprite_photo = None
    app.clsn_canvas_origin = (0, 0)
    app.clsn_drag = None
    app.clsn_drawn_boxes = []
    app.anim_action_var = tk.StringVar()
    app.anim_frame_var = tk.IntVar(value=0)
    app.anim_speed_var = tk.DoubleVar(value=1.0)
    app.anim_zoom_var = tk.IntVar(value=2)
    app.anim_loop_var = tk.BooleanVar(value=True)
    app.anim_after_id = None
    app.anim_is_playing = False
    app.anim_photo = None
    app.wizard_vars = {}
    app.wizard_preview_cache = None
    app.auto_preset_items = []
    app.auto_last_package = None
    app.palette_info = None
