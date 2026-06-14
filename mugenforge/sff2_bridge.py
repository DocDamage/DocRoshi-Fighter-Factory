from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import json
import re
import shutil
import subprocess
import zipfile
from typing import Iterable, List, Optional, Tuple

IMAGE_EXTS = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}

@dataclass
class BridgeResult:
    title: str = 'SFF2 Bridge Result'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def merge(self, other: object, prefix: str = '') -> None:
        p = f'{prefix}: ' if prefix else ''
        for attr in ('created_files', 'changed_files', 'skipped_files', 'warnings', 'notes'):
            for item in getattr(other, attr, []) or []:
                getattr(self, attr).append(p + str(item))

    def to_text(self) -> str:
        lines = [self.title, '=' * len(self.title), '']
        for label, vals in [
            ('Notes', self.notes),
            ('Created', self.created_files),
            ('Changed', self.changed_files),
            ('Skipped', self.skipped_files),
            ('Warnings', self.warnings),
        ]:
            if vals:
                lines.append(label + ':')
                lines.extend(f'- {v}' for v in vals)
                lines.append('')
        if len(lines) <= 3:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


def _rel(root: Path, p: Path | str) -> str:
    try:
        return str(Path(p).relative_to(root)).replace('\\', '/')
    except Exception:
        return str(p).replace('\\', '/')


def _write_text(path: Path, text: str, res: Optional[BridgeResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(text, encoding='utf-8')
    if res is not None:
        bucket = res.changed_files if existed or changed else res.created_files
        bucket.append(_rel(root or path.parent, path))
    return path


def _image_files(folder: Path) -> List[Path]:
    folder = Path(folder)
    return [p for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in IMAGE_EXTS]


def parse_group_image_from_name(path: Path, fallback_index: int = 0) -> Tuple[int, int]:
    stem = path.stem.lower()
    patterns = [
        r'g(?P<g>-?\d+)[_\- ]*i(?P<i>-?\d+)',
        r'group(?P<g>-?\d+)[_\- ]*(?:image|img|item)(?P<i>-?\d+)',
        r'(?P<g>-?\d+)[_\- ]+(?P<i>-?\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, stem)
        if m:
            return int(m.group('g')), int(m.group('i'))
    # Keep unparseable files usable: group 0, sequential image id.
    return 0, int(fallback_index)


def _image_size(path: Path) -> Tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def _axis_for(path: Path, mode: str, explicit_x: Optional[int] = None, explicit_y: Optional[int] = None) -> Tuple[int, int]:
    if explicit_x is not None and explicit_y is not None:
        return int(explicit_x), int(explicit_y)
    w, h = _image_size(path)
    mode = (mode or 'feet').lower().strip()
    if mode in {'center', 'centre'}:
        return max(0, w // 2), max(0, h // 2)
    if mode in {'top-left', 'topleft', 'zero'}:
        return 0, 0
    if mode in {'bottom-center', 'bottom', 'feet', 'mugen'}:
        return max(0, w // 2), max(0, h)
    return max(0, w // 2), max(0, h)


def scan_image_folder_for_sprmake(folder: Path, *, axis_mode: str = 'feet') -> List[dict]:
    records: List[dict] = []
    for idx, p in enumerate(_image_files(Path(folder))):
        g, i = parse_group_image_from_name(p, idx)
        w, h = _image_size(p)
        ax, ay = _axis_for(p, axis_mode)
        records.append({
            'group': g,
            'image': i,
            'file': p,
            'filename': p.name,
            'relative': str(p.relative_to(folder)).replace('\\', '/') if Path(folder) in p.parents else p.name,
            'axisx': ax,
            'axisy': ay,
            'width': w,
            'height': h,
        })
    records.sort(key=lambda r: (int(r['group']), int(r['image']), str(r['relative']).lower()))
    return records


def _copy_images(records: Iterable[dict], source_root: Path, dest_dir: Path, res: BridgeResult, project_root: Path) -> List[dict]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: List[dict] = []
    used_names = set()
    for rec in records:
        src = Path(rec['file'])
        suffix = src.suffix.lower() or '.png'
        safe_name = f'g{int(rec["group"]):04d}_i{int(rec["image"]):04d}{suffix}'
        if safe_name in used_names:
            safe_name = f'g{int(rec["group"]):04d}_i{int(rec["image"]):04d}_{len(used_names):04d}{suffix}'
        used_names.add(safe_name)
        dst = dest_dir / safe_name
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
            res.created_files.append(_rel(project_root, dst))
        new = dict(rec)
        new['copied_filename'] = safe_name
        new['copied_path'] = dst
        copied.append(new)
    return copied


def write_sprmake2_def(def_path: Path, records: List[dict], *, output_sff: str, input_dir: str = 'sprites', compress8: str = 'rle8', compress5: str = 'lz5', compress24: str = 'none', usepal: str = '-1', autocrop: bool = True) -> Path:
    def esc(s: str) -> str:
        return s.replace('\\', '/')
    lines = [
        '; Generated by MugenForge Studio SFF2 Bridge',
        '; Edit group/image IDs, filenames, and axes here, then run the generated build BAT.',
        '',
        '[Output]',
        f'filename = {esc(output_sff)}',
        '',
        '[Option]',
        f'input.dir = {esc(input_dir)}',
        f'sprite.compress.5 = {compress5}',
        f'sprite.compress.8 = {compress8}',
        f'sprite.compress.24 = {compress24}',
        'sprite.decompressonload = 0',
        'sprite.detectduplicates = 1',
        f'sprite.autocrop = {1 if autocrop else 0}',
        'pal.detectduplicates = 1',
        'pal.discardduplicates = 1',
        'pal.reverseact = 0',
        'pal.reversepng = 0',
        f'sprite.usepal = {usepal}',
        '',
        '[Sprite]',
        '; group, itemno, filename, axisx, axisy',
    ]
    for rec in records:
        fn = rec.get('copied_filename') or rec.get('relative') or rec.get('filename')
        lines.append(f'{int(rec["group"]):5d}, {int(rec["image"]):5d}, {esc(str(fn))}, {int(rec["axisx"]):4d}, {int(rec["axisy"]):4d}')
    def_path.parent.mkdir(parents=True, exist_ok=True)
    def_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    return def_path


def write_sprmake2_bridge_project(project_root: Path, image_folder: Path, *, output_sff_name: str = '', def_name: str = 'mugenforge_sff2_sprmake.def', compress8: str = 'rle8', usepal: str = '-1', autocrop: bool = True, axis_mode: str = 'feet') -> BridgeResult:
    project_root = Path(project_root)
    image_folder = Path(image_folder)
    res = BridgeResult('SFF2 Bridge Project Written')
    if not image_folder.exists() or not image_folder.is_dir():
        raise FileNotFoundError(f'Image folder not found: {image_folder}')
    records = scan_image_folder_for_sprmake(image_folder, axis_mode=axis_mode)
    if not records:
        raise ValueError('No supported image files were found in the selected folder.')
    bridge_dir = project_root / 'sff2_bridge'
    sprite_dir = bridge_dir / 'sprites'
    copied = _copy_images(records, image_folder, sprite_dir, res, project_root)
    output_sff_name = output_sff_name.strip() or f'{project_root.name}.sff'
    def_path = bridge_dir / (def_name.strip() or 'mugenforge_sff2_sprmake.def')
    write_sprmake2_def(def_path, copied, output_sff=output_sff_name, input_dir='sprites', compress8=compress8, usepal=usepal, autocrop=autocrop)
    res.created_files.append(_rel(project_root, def_path))
    bat = bridge_dir / 'build_sff2_with_sprmake2.bat'
    bat_text = f'@echo off\r\nREM Generated by MugenForge Studio. Put sprmake2.exe next to this BAT or edit SPRMAKE2_EXE.\r\nset SPRMAKE2_EXE=sprmake2.exe\r\n"%SPRMAKE2_EXE%" -o "{output_sff_name}" "{def_path.name}"\r\npause\r\n'
    bat.write_text(bat_text, encoding='utf-8')
    res.created_files.append(_rel(project_root, bat))
    manifest = {
        'schema': 'mugenforge.sff2_bridge.v1',
        'generated': datetime.now().isoformat(timespec='seconds'),
        'source_folder': str(image_folder),
        'output_sff': output_sff_name,
        'def_file': _rel(project_root, def_path),
        'records': [{k: (str(v) if isinstance(v, Path) else v) for k, v in r.items() if k != 'file'} for r in copied],
    }
    manifest_path = bridge_dir / 'mugenforge_sff2_bridge_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    res.created_files.append(_rel(project_root, manifest_path))
    csv_path = bridge_dir / 'mugenforge_sff2_sprite_table.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['group', 'image', 'filename', 'axisx', 'axisy', 'width', 'height'])
        for r in copied:
            writer.writerow([r['group'], r['image'], r['copied_filename'], r['axisx'], r['axisy'], r['width'], r['height']])
    res.created_files.append(_rel(project_root, csv_path))
    res.notes.append(f'Prepared {len(copied)} sprites for Sprmake2 SFF v2 building.')
    res.notes.append('Use the generated BAT with your own sprmake2.exe, or set the executable path in the SFF2 Bridge tab and run it from MugenForge.')
    return res


def run_sprmake2(project_root: Path, sprmake2_exe: Path, def_path: Optional[Path] = None, *, output_sff_name: str = '') -> BridgeResult:
    project_root = Path(project_root)
    exe = Path(sprmake2_exe)
    res = BridgeResult('Sprmake2 Run')
    if not exe.exists():
        raise FileNotFoundError(f'sprmake2 executable not found: {exe}')
    bridge_dir = project_root / 'sff2_bridge'
    def_path = Path(def_path) if def_path else bridge_dir / 'mugenforge_sff2_sprmake.def'
    if not def_path.exists():
        raise FileNotFoundError(f'Sprmake2 definition file not found: {def_path}')
    cmd = [str(exe)]
    if output_sff_name.strip():
        cmd += ['-o', output_sff_name.strip()]
    cmd.append(str(def_path.name))
    proc = subprocess.run(cmd, cwd=str(def_path.parent), capture_output=True, text=True, timeout=180)
    log_path = bridge_dir / 'sprmake2_last_run.log'
    log_path.write_text('COMMAND: ' + ' '.join(cmd) + '\n\nSTDOUT:\n' + (proc.stdout or '') + '\n\nSTDERR:\n' + (proc.stderr or '') + f'\n\nEXIT CODE: {proc.returncode}\n', encoding='utf-8')
    res.created_files.append(_rel(project_root, log_path))
    if proc.returncode == 0:
        res.notes.append('Sprmake2 finished successfully.')
    else:
        res.warnings.append(f'Sprmake2 exited with code {proc.returncode}. See log for details.')
    return res


def export_current_sff1_to_sff2_source(project_root: Path, sff_path: Path, *, axis_mode: str = 'feet') -> BridgeResult:
    from .sff_codec import read_sff, export_sprite, try_convert_to_png
    project_root = Path(project_root)
    sff_path = Path(sff_path)
    res = BridgeResult('SFF v1 Exported To SFF2 Source Folder')
    info = read_sff(sff_path)
    if not info.sprites or not info.is_supported_for_extraction:
        raise ValueError('Current SFF has no supported SFF v1 PCX/PNG payloads to export. SFF v2 files cannot be round-tripped this way.')
    bridge_dir = project_root / 'sff2_bridge'
    src_dir = bridge_dir / 'sprites_from_current_sff'
    src_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for spr in info.sprites:
        if spr.format_hint not in {'pcx', 'png'} or spr.length <= 0:
            continue
        tmp = export_sprite(sff_path, spr, src_dir)
        out_name = f'g{spr.group:04d}_i{spr.image:04d}.png'
        out_path = src_dir / out_name
        if tmp.suffix.lower() == '.png':
            if tmp.name != out_name:
                shutil.copy2(tmp, out_path)
        else:
            ok = try_convert_to_png(tmp, out_path)
            if not ok:
                out_path = tmp
                out_name = tmp.name
        w, h = _image_size(out_path)
        ax = spr.x if spr.x or spr.y else _axis_for(out_path, axis_mode)[0]
        ay = spr.y if spr.x or spr.y else _axis_for(out_path, axis_mode)[1]
        records.append({'group': spr.group, 'image': spr.image, 'file': out_path, 'filename': out_name, 'relative': out_name, 'axisx': ax, 'axisy': ay, 'width': w, 'height': h})
    if not records:
        raise ValueError('No PCX/PNG payloads could be exported from the SFF.')
    def_path = bridge_dir / 'mugenforge_sff2_from_current_sff.def'
    write_sprmake2_def(def_path, records, output_sff=sff_path.name, input_dir='sprites_from_current_sff', compress8='rle8', usepal='-1', autocrop=False)
    res.created_files.extend([_rel(project_root, def_path)])
    res.notes.append(f'Exported {len(records)} supported sprites into {src_dir}.')
    res.notes.append('This creates an editable SFF2 source project. It does not preserve SFF2 compression tables from an existing v2 file.')
    return res


def inspect_sprmake2_def(def_path: Path) -> str:
    def_path = Path(def_path)
    if not def_path.exists():
        raise FileNotFoundError(def_path)
    text = def_path.read_text(encoding='utf-8', errors='replace')
    section = ''
    sprite_count = 0
    pal_count = 0
    output = ''
    options = {}
    groups = set()
    for raw in text.splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line.strip('[]').lower()
            continue
        if section == 'output' and '=' in line:
            k, v = [x.strip() for x in line.split('=', 1)]
            if k.lower() == 'filename':
                output = v
        elif section == 'option' and '=' in line:
            k, v = [x.strip() for x in line.split('=', 1)]
            options[k.lower()] = v
        elif section == 'sprite' and ',' in line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 5:
                sprite_count += 1
                try: groups.add(int(parts[0]))
                except Exception: pass
        elif section == 'pal' and ',' in line:
            pal_count += 1
    lines = [
        f'DEF: {def_path}',
        f'Output SFF: {output or "not specified"}',
        f'Sprites: {sprite_count}',
        f'Palette entries: {pal_count}',
        f'Groups: {", ".join(map(str, sorted(groups)[:60]))}{" ..." if len(groups) > 60 else ""}',
        '',
        'Important options:',
    ]
    for k in ['input.dir', 'sprite.compress.5', 'sprite.compress.8', 'sprite.compress.24', 'sprite.autocrop', 'sprite.usepal', 'pal.discardduplicates']:
        lines.append(f'- {k}: {options.get(k, "not set")}')
    return '\n'.join(lines).rstrip() + '\n'


def create_sff2_source_pack_zip(project_root: Path, zip_path: Optional[Path] = None) -> BridgeResult:
    project_root = Path(project_root)
    bridge_dir = project_root / 'sff2_bridge'
    if not bridge_dir.exists():
        raise FileNotFoundError('No sff2_bridge folder exists yet. Write a Sprmake2 bridge project first.')
    res = BridgeResult('SFF2 Source Pack ZIP')
    out = Path(zip_path) if zip_path else project_root / 'exports' / f'{project_root.name}_sff2_source_pack.zip'
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bridge_dir.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file() and p.resolve() != out.resolve() and p.suffix.lower() != '.zip':
                z.write(p, arcname=f'{project_root.name}/sff2_bridge/{p.relative_to(bridge_dir)}')
    res.created_files.append(_rel(project_root, out))
    res.notes.append('Source pack includes images, Sprmake2 DEF, BAT, CSV, and manifest files needed for rebuilding SFF v2 outside the editor.')
    return res


def write_sff2_bridge_guide(project_root: Path) -> BridgeResult:
    project_root = Path(project_root)
    res = BridgeResult('SFF2 Bridge Beginner Guide')
    guide = project_root / 'sff2_bridge' / 'README_SFF2_BRIDGE.md'
    text = f'''# SFF2 Bridge Guide

This folder is for building a M.U.G.E.N 1.0-style SFF v2 from normal image files without hand-writing the Sprmake2 definition.

## Beginner route

1. Put character sprites in a folder.
2. Name them like `g0_i0.png`, `g0_i1.png`, `g200_i0.png`, etc.
3. In MugenForge, open **SFF2 Bridge**.
4. Choose the image folder.
5. Click **Write Sprmake2 DEF + BAT**.
6. Use your own `sprmake2.exe` to run the generated BAT, or set the executable path and run from MugenForge.
7. Point the character `.def` `[Files] sprite = ...` line at the built `.sff`.

## File naming

Accepted patterns include:

```text
g200_i0.png
group200_image0.png
200_0.png
```

## Axis defaults

The default axis mode is **feet**: X is the sprite center and Y is the bottom of the image. This is usually a sane first guess for standing character frames. Tune axes later in your animation/player workflow.

## Why this exists

MugenForge can build starter SFF v1 files directly. For SFF v2, this bridge creates a clean Sprmake2 source project and lets the official external builder do the binary packing.
'''
    _write_text(guide, text, res, project_root)
    return res
