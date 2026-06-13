from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from ..ff_plus_tools import sound_cue_sheet
from ..snd_codec import (
    build_snd_from_manifest,
    export_all_sounds,
    export_sound,
    make_placeholder_sound_bank,
    make_snd_manifest_from_wav_folder,
    read_snd,
    summarize_snd_manifest,
)


class SoundPipelineActions:
    def populate_sound_browser(self, path: Path):
        self.snd_path = path
        self.snd_info = read_snd(path)
        self.sound_tree.delete(*self.sound_tree.get_children())
        lines = [
            f'SND: {path.name}',
            f'Signature: {"yes" if self.snd_info.has_signature else "not detected"}',
            f'Version bytes: {self.snd_info.version_text}',
            f'Header count hint: {self.snd_info.declared_count if self.snd_info.declared_count is not None else "unknown"}',
            f'RIFF/WAVE sounds found: {len(self.snd_info.sounds)}',
            'Export mode: read-only WAV payload extraction',
        ]
        if self.snd_info.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in self.snd_info.warnings[:8])
        self.set_text(self.sound_info, '\n'.join(lines))
        for snd in self.snd_info.sounds:
            fmt = []
            if snd.channels is not None:
                fmt.append(f'{snd.channels}ch')
            if snd.sample_rate is not None:
                fmt.append(f'{snd.sample_rate}Hz')
            if snd.bits_per_sample is not None:
                fmt.append(f'{snd.bits_per_sample}bit')
            if snd.format_tag is not None:
                fmt.append(f'fmt={snd.format_tag}')
            fmt_text = ', '.join(fmt) if fmt else 'unknown'
            self.sound_tree.insert('', 'end', text=str(snd.index), values=(snd.id_text, f'0x{snd.riff_offset:X}', f'{snd.length:,}', fmt_text), tags=(str(snd.index),))
        if self.snd_info.sounds:
            first = self.sound_tree.get_children()[0]
            self.sound_tree.selection_set(first)
            self.sound_tree.focus(first)
            self.on_sound_select()

    def _selected_sound(self):
        if not self.snd_info:
            return None
        sel = self.sound_tree.selection()
        if not sel:
            return None
        try:
            idx = int(self.sound_tree.item(sel[0], 'tags')[0])
        except Exception:
            return None
        for snd in self.snd_info.sounds:
            if snd.index == idx:
                return snd
        return None

    def on_sound_select(self, event=None):
        snd = self._selected_sound()
        if not snd:
            return
        lines = [
            f'Sound #{snd.index}',
            f'ID: {snd.id_text}',
            f'RIFF offset: 0x{snd.riff_offset:X}',
            f'WAV bytes: {snd.length:,}',
            f'Header offset guess: {"0x%X" % snd.header_offset if snd.header_offset is not None else "unknown"}',
            f'Format tag: {snd.format_tag if snd.format_tag is not None else "unknown"}',
            f'Channels: {snd.channels if snd.channels is not None else "unknown"}',
            f'Sample rate: {snd.sample_rate if snd.sample_rate is not None else "unknown"}',
            f'Byte rate: {snd.byte_rate if snd.byte_rate is not None else "unknown"}',
            f'Bits/sample: {snd.bits_per_sample if snd.bits_per_sample is not None else "unknown"}',
        ]
        if snd.warnings:
            lines.append('')
            lines.append('Warnings:')
            lines.extend(f'- {w}' for w in snd.warnings)
        self.set_text(self.sound_info, '\n'.join(lines))

    def export_wav_cue_sheet_ui(self):
        folder = filedialog.askdirectory(title='Choose folder of WAV files for cue sheet')
        if not folder:
            return
        out = filedialog.asksaveasfilename(title='Save WAV cue sheet', defaultextension='.md', initialfile='MUGENFORGE_SOUND_CUE_SHEET.md', filetypes=[('Markdown', '*.md'), ('Text', '*.txt')])
        if not out:
            return
        try:
            path = sound_cue_sheet(Path(folder), Path(out))
            self.set_text(self.sound_info, f'Cue sheet exported:\n{path}\n\n' + path.read_text(encoding='utf-8'))
            self.status_var.set(f'Cue sheet exported: {path.name}')
        except Exception as exc:
            messagebox.showerror('Cue sheet failed', str(exc))

    def export_selected_sound(self):
        snd = self._selected_sound()
        if not snd or not self.snd_path:
            messagebox.showinfo('No sound selected', 'Open an SND file and select a sound first.')
            return
        out_dir = filedialog.askdirectory(title='Choose WAV export folder')
        if not out_dir:
            return
        out = export_sound(self.snd_path, snd, Path(out_dir))
        self.status_var.set(f'Exported sound: {out}')
        messagebox.showinfo('Exported', f'Exported:\n{out}')

    def export_snd_sounds(self):
        path = self.snd_path
        if not path and self.current_path and self.current_path.suffix.lower() == '.snd':
            path = self.current_path
        if not path:
            messagebox.showinfo('No SND open', 'Open an .snd file first.')
            return
        out_dir = filedialog.askdirectory(title='Choose folder for SND WAV export')
        if not out_dir:
            return
        outputs = export_all_sounds(path, Path(out_dir))
        self.status_var.set(f'Exported {len(outputs)} WAV files from {path.name}')
        messagebox.showinfo('Export complete', f'Exported {len(outputs)} WAV files.\n\nFolder:\n{out_dir}')

    def make_placeholder_sound_bank_ui(self):
        if self.project_root:
            default_dir = self.project_root / 'sounds'
            default_dir.mkdir(exist_ok=True)
            folder = filedialog.askdirectory(title='Choose folder for placeholder WAV bank', initialdir=str(default_dir))
        else:
            folder = filedialog.askdirectory(title='Choose folder for placeholder WAV bank')
        if not folder:
            return
        try:
            manifest = make_placeholder_sound_bank(Path(folder))
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.notebook.select(7)
            self.status_var.set(f'Created placeholder sound bank: {manifest.name}')
            messagebox.showinfo('Placeholder sound bank created', f'Created silent placeholder WAVs and manifest:\n{manifest}\n\nUse Build SND to package them, then replace WAVs with real sounds later.')
        except Exception as exc:
            messagebox.showerror('Placeholder sound bank failed', str(exc))

    def make_snd_manifest(self):
        folder = filedialog.askdirectory(title='Choose folder containing WAV files')
        if not folder:
            return
        try:
            manifest = make_snd_manifest_from_wav_folder(Path(folder))
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.status_var.set(f'Created SND manifest: {manifest.name}')
            messagebox.showinfo('SND manifest created', f'Created manifest:\n{manifest}\n\nFilename IDs are inferred from names like 5_0.wav or sound_5_0.wav. Edit the JSON if the group/sound IDs need correction.')
        except Exception as exc:
            messagebox.showerror('SND manifest failed', str(exc))

    def _ask_snd_manifest_path(self):
        path = filedialog.askopenfilename(
            title='Choose MugenForge SND manifest',
            filetypes=[('MugenForge SND manifest', 'mugenforge_snd_manifest.json'), ('JSON files', '*.json'), ('All files', '*.*')]
        )
        return Path(path) if path else None

    def inspect_snd_manifest(self):
        manifest = self._ask_snd_manifest_path()
        if not manifest:
            return
        try:
            self.set_text(self.sound_info, summarize_snd_manifest(manifest))
            self.notebook.select(7)
            self.status_var.set(f'Inspected SND manifest: {manifest.name}')
        except Exception as exc:
            messagebox.showerror('SND manifest inspect failed', str(exc))

    def build_snd_from_manifest_ui(self):
        manifest = self._ask_snd_manifest_path()
        if not manifest:
            return
        default_name = 'staged_build.snd'
        out = filedialog.asksaveasfilename(
            title='Save built SND file',
            initialfile=default_name,
            defaultextension='.snd',
            filetypes=[('MUGEN SND', '*.snd'), ('All files', '*.*')]
        )
        if not out:
            return
        try:
            info = build_snd_from_manifest(manifest, Path(out))
            msg = [
                f'Built SND: {out}',
                f'Parsed sounds after build: {len(info.sounds)}',
                f'Header count hint: {info.declared_count}',
                '',
                'Important: this is a simple RIFF/WAVE SND builder for starter characters and pipeline testing. Keep backups before replacing mature production SND files.',
            ]
            if info.warnings:
                msg.append('')
                msg.append('Warnings:')
                msg.extend(f'- {w}' for w in info.warnings[:8])
            self.status_var.set(f'Built SND: {Path(out).name}')
            self.set_text(self.sound_info, '\n'.join(msg))
            if Path(out).exists():
                self.populate_sound_browser(Path(out))
                self.notebook.select(7)
            messagebox.showinfo('SND build complete', '\n'.join(msg[:5]))
        except Exception as exc:
            messagebox.showerror('SND build failed', str(exc))
