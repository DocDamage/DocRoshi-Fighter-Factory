from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from ..parsers import (
    TEXT_EXTS,
    make_new_character,
    parse_air,
    parse_code,
    parse_def,
    read_text_safely,
    scan_project,
    summarize_binary,
    write_text_safely,
)


class ProjectCoreActions:
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
