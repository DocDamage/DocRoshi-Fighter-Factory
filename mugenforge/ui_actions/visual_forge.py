from __future__ import annotations

import json
import re
from pathlib import Path
from tkinter import filedialog, messagebox

from ..move_wizard import normalize_spec
from ..parsers import parse_code, read_text_safely
from ..shared_utils import handle_ui_errors
from ..visual_forge import (
    BeginnerProjectSpec,
    MigrationSpec,
    SoundCueSpec,
    add_sound_cue_controller,
    build_sprite_offset_model,
    build_visual_timeline_model,
    compose_move2,
    create_backup_snapshot,
    create_visual_forge_project,
    install_template_architecture,
    install_training_debug_pack,
    log_error,
    migrate_existing_character,
    quick_start_pass,
    restore_latest_snapshot,
    update_air_frame_offset,
    update_air_frame_ticks,
    write_beginner_project_home,
    write_sound_cue_manifest,
    write_visual_sff2_bridge_pack,
    write_visual_timeline_manifest,
)


def _safe_preview_name(value: object, default: str = 'move') -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', str(value or '')).strip('_')
    return safe or default


class VisualForgeActions:
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

    @handle_ui_errors('Visual Forge wizard')
    def vf_create_project_from_wizard(self):
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

    @handle_ui_errors('Visual Forge Quick Start')
    def vf_quick_start_ui(self):
        if not self._vf_require_project():
            return
        result = quick_start_pass(self.project_root)
        self.set_text(self.vf_home_output, result.to_text())
        self.status_var.set('Visual Forge Quick Start finished')

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

    @handle_ui_errors('Write Visual Forge home docs')
    def vf_write_home_docs_ui(self):
        if not self._vf_require_project():
            return
        result = write_beginner_project_home(self.project_root, BeginnerProjectSpec(name=self.project_root.name))
        self.set_text(self.vf_home_output, result.to_text())
        self.status_var.set('Visual Forge home docs written')

    def vf_import_legacy_from_home(self):
        self.notebook.select(self.vf_migration_frame)

    @handle_ui_errors('Visual Timeline refresh')
    def vf_refresh_timeline_ui(self):
        if not self._vf_require_project():
            return
        self.vf_timeline_model = build_visual_timeline_model(self.project_root)
        actions = self.vf_timeline_model.get('actions', [])
        values = [f"{a.get('action')} :: {a.get('label') or 'action'} ({len(a.get('frames', []))} frames)" for a in actions]
        self.vf_timeline_action_combo.configure(values=values)
        if values:
            self.vf_timeline_action_var.set(values[0])
        self.vf_timeline_preview_ticks = {}
        self.vf_draw_timeline()
        self.status_var.set('Visual timeline refreshed')

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
            c.create_rectangle(x, y, x + w, y + row_h, fill=fill, outline=outline, width=3 if highlight_index == idx else 1, tags=('vf_frame', f'frame:{idx}'))
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

    @handle_ui_errors('Visual Timeline save ticks')
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
        result = update_air_frame_ticks(self.project_root, int(action.get('action')), idx, ticks)
        self.set_text(self.vf_timeline_info, result.to_text())
        self.vf_refresh_timeline_ui()
        self.reload_project()

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

    @handle_ui_errors('Timeline export')
    def vf_timeline_export_ui(self):
        if not self._vf_require_project():
            return
        action = self._vf_selected_timeline_action()
        action_no = int(action.get('action')) if action else None
        result = write_visual_timeline_manifest(self.project_root, action_no)
        self.set_text(self.vf_timeline_info, result.to_text())
        self.status_var.set('Timeline manifest exported')

    @handle_ui_errors('Offset refresh')
    def vf_refresh_offset_ui(self):
        if not self._vf_require_project():
            return
        self.vf_offset_model = build_sprite_offset_model(self.project_root)
        values = [f"{a.get('action')} :: {a.get('label') or 'action'} ({len(a.get('frames', []))} frames)" for a in self.vf_offset_model.get('actions', [])]
        self.vf_offset_action_combo.configure(values=values)
        if values:
            self.vf_offset_action_var.set(values[0])
        self.vf_on_offset_action()

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

    @handle_ui_errors('Offset save')
    def vf_save_offset_ui(self):
        if not self._vf_require_project():
            return
        action = self._vf_selected_offset_action()
        sel = self.vf_offset_frame_list.curselection()
        if not action or not sel:
            messagebox.showinfo('No frame selected', 'Choose an action/frame first.')
            return
        result = update_air_frame_offset(self.project_root, int(action.get('action')), sel[0], self._vf_int(self.vf_offset_x_var, 0), self._vf_int(self.vf_offset_y_var, 0))
        self.set_text(self.vf_offset_info, result.to_text())
        self.vf_refresh_offset_ui()
        self.reload_project()

    @handle_ui_errors('Sound cue refresh')
    def vf_refresh_sound_cues_ui(self):
        if not self._vf_require_project():
            return
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

    @handle_ui_errors('Add sound cue')
    def vf_add_sound_cue_ui(self):
        if not self._vf_require_project():
            return
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

    @handle_ui_errors('Cue manifest')
    def vf_export_sound_cue_manifest_ui(self):
        if not self._vf_require_project():
            return
        result = write_sound_cue_manifest(self.project_root)
        self.set_text(self.vf_sound_output, result.to_text())

    def _vf_composer2_spec(self):
        data = {k: v.get() for k, v in self.vf_compose_vars.items()}
        data['command_time'] = '12'
        data['sparkno'] = '2'
        data['guard_sparkno'] = '40'
        return normalize_spec(**data)

    @handle_ui_errors('Move Composer preview')
    def vf_composer2_preview(self):
        if not self._vf_require_project():
            return
        spec = self._vf_composer2_spec()
        result = compose_move2(self.project_root, spec, append=False)
        preview_name = _safe_preview_name(spec.move_name)
        out = self.project_root / 'visual_forge' / 'move_composer' / f'{preview_name}_preview.txt'
        text = result.to_text()
        if out.exists():
            text += '\n' + out.read_text(encoding='utf-8')
        self.set_text(self.vf_composer2_output, text)

    @handle_ui_errors('Move Composer append')
    def vf_composer2_append(self):
        if not self._vf_require_project():
            return
        spec = self._vf_composer2_spec()
        result = compose_move2(self.project_root, spec, append=True)
        result.merge(write_visual_timeline_manifest(self.project_root, spec.anim_no), 'Timeline Manifest')
        self.set_text(self.vf_composer2_output, result.to_text())
        self.reload_project()

    def vf_choose_import_source(self):
        folder = filedialog.askdirectory(title='Choose existing character folder to import')
        if folder:
            self.vf_migration_source_var.set(folder)
            self.vf_migration_name_var.set(Path(folder).name + '_mugenforge')

    def vf_choose_import_dest(self):
        folder = filedialog.askdirectory(title='Choose destination parent folder')
        if folder:
            self.vf_migration_dest_var.set(folder)

    @handle_ui_errors('Migration wizard')
    def vf_run_migration_ui(self):
        spec = MigrationSpec(Path(self.vf_migration_source_var.get().strip()), Path(self.vf_migration_dest_var.get().strip()), self.vf_migration_name_var.get().strip())
        result = migrate_existing_character(spec)
        self.set_text(self.vf_migration_output, result.to_text())
        dest = spec.destination_parent / (spec.new_name.strip() or spec.source_root.name)
        if dest.exists():
            self.load_project(dest)

    @handle_ui_errors('Training debug install')
    def vf_install_training_debug_ui(self):
        if not self._vf_require_project():
            return
        result = install_training_debug_pack(self.project_root)
        self.set_text(self.vf_training_output, result.to_text())
        self.reload_project()

    @handle_ui_errors('Template/plugin install')
    def vf_install_templates_ui(self):
        if not self._vf_require_project():
            return
        result = install_template_architecture(self.project_root)
        target = self.vf_plugin_output if hasattr(self, 'vf_plugin_output') else self.vf_home_output
        self.set_text(target, result.to_text())
        self.status_var.set('Template/plugin foundation installed')

    @handle_ui_errors('SFF2 Bridge Pack')
    def vf_sff2_pack_ui(self):
        if not self._vf_require_project():
            return
        folder = filedialog.askdirectory(title='Optional: choose image folder for Sprmake2 source project, or cancel to write guide only')
        img = Path(folder) if folder else None
        result = write_visual_sff2_bridge_pack(self.project_root, img)
        target = self.vf_plugin_output if hasattr(self, 'vf_plugin_output') else self.vf_home_output
        self.set_text(target, result.to_text())

    @handle_ui_errors('Backup snapshot')
    def vf_backup_snapshot_ui(self):
        if not self._vf_require_project():
            return
        label = self.vf_backup_label_var.get() if hasattr(self, 'vf_backup_label_var') else 'manual'
        result = create_backup_snapshot(self.project_root, label)
        target = self.vf_backup_output if hasattr(self, 'vf_backup_output') else self.vf_home_output
        self.set_text(target, result.to_text())
        self.status_var.set('Visual Forge backup snapshot created')

    @handle_ui_errors('Restore latest snapshot')
    def vf_restore_snapshot_ui(self):
        if not self._vf_require_project():
            return
        if not messagebox.askyesno('Restore latest snapshot', 'Restore the latest Visual Forge snapshot? A pre-restore guard snapshot will be created first.'):
            return
        result = restore_latest_snapshot(self.project_root)
        self.set_text(self.vf_backup_output, result.to_text())
        self.reload_project()

    def vf_view_error_log_ui(self):
        if not self._vf_require_project():
            return
        log = self.project_root / 'visual_forge' / 'error_log.txt'
        if log.exists():
            self.set_text(self.vf_backup_output, log.read_text(encoding='utf-8', errors='replace'))
        else:
            self.set_text(self.vf_backup_output, 'No Visual Forge error log exists yet.')
