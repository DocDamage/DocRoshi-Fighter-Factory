from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..code_authoring import (
    attack_state_template,
    command_template,
    helper_explod_template,
    inspect_character_folder,
    inspect_code_text,
    negative_one_changestate_template,
    package_character_zip,
    projectile_state_template,
)
from ..move_wizard import append_move_to_project, build_move_package, normalize_spec
from ..parsers import TEXT_EXTS


class CodeAuthoringActions:
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
