from __future__ import annotations

from tkinter import messagebox

from ..air_tools import normalize_box, parse_air_with_lines, update_frame_clsn_text
from ..parsers import COMMON_ANIMS, parse_air, parse_def, read_text_safely, write_text_safely
from ..sff_codec import read_sff, sprite_lookup


class AirEditorActions:
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
