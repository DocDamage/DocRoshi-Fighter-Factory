from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from io import BytesIO
import csv
import html
import json
import math
import re
import shutil
import wave
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import write_csv_artifact, write_text_artifact
from .parsers import parse_air, parse_code, parse_def, read_text_safely, write_text_safely, COMMON_ANIMS
from .move_wizard import find_character_file
from .sff_codec import read_sff, export_sprite, sprite_lookup, SffSprite
from .snd_codec import read_snd, export_sound
from .palette_tools import read_act

IMAGE_EXTS = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
AUDIO_EXTS = {'.wav'}


@dataclass
class CreatorSuiteResult:
    title: str = 'Creator Suite'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root: Path, path: Path | str) -> None:
        self.created_files.append(_rel(root, path))

    def add_changed(self, root: Path, path: Path | str) -> None:
        self.changed_files.append(_rel(root, path))

    def add_warning(self, msg: str) -> None:
        self.warnings.append(str(msg))

    def add_note(self, msg: str) -> None:
        self.notes.append(str(msg))

    def merge(self, other: 'CreatorSuiteResult', label: Optional[str] = None) -> None:
        if not other:
            return
        prefix = f'{label}: ' if label else ''
        self.created_files.extend(prefix + x for x in other.created_files)
        self.changed_files.extend(prefix + x for x in other.changed_files)
        self.warnings.extend(prefix + x for x in other.warnings)
        self.notes.extend(prefix + x for x in other.notes)

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        if self.created_files:
            lines += ['Created files/artifacts:'] + [f'- {x}' for x in _uniq(self.created_files)] + ['']
        if self.changed_files:
            lines += ['Changed files:'] + [f'- {x}' for x in _uniq(self.changed_files)] + ['']
        if self.warnings:
            lines += ['Warnings:'] + [f'- {x}' for x in _uniq(self.warnings)] + ['']
        if self.notes:
            lines += ['Notes:'] + [f'- {x}' for x in _uniq(self.notes)] + ['']
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


def _uniq(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _suite_dir(root: Path) -> Path:
    out = Path(root) / 'creator_suite'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _backup(path: Path) -> None:
    path = Path(path)
    if path.exists():
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        path.with_name(path.name + f'.bak_{stamp}').write_bytes(path.read_bytes())


def _write(root: Path, path: Path, text: str, result: Optional[CreatorSuiteResult] = None, *, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, track_existing=changed)


def _csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> Path:
    return write_csv_artifact(path, rows, fields)


def _code_files(root: Path) -> List[Path]:
    exts = {'.cmd', '.cns', '.st'}
    return [p for p in sorted(Path(root).rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in exts]


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {'root': root}
    def_path = root / f'{root.name}.def'
    if not def_path.exists():
        defs = sorted(root.glob('*.def'), key=lambda p: p.name.lower())
        def_path = defs[0] if defs else def_path
    out['def'] = def_path if def_path.exists() else None
    refs: Dict[str, str] = {}
    if out['def']:
        try:
            files = parse_def(read_text_safely(out['def'])).get('files')
            if files:
                refs = {k.lower(): v.strip().strip('"') for k, v in files.values.items()}
        except Exception:
            refs = {}

    def pick(key: str, ext: str) -> Optional[Path]:
        if key in refs:
            candidate = (root / refs[key]).resolve()
            if candidate.exists():
                return candidate
        exact = root / f'{root.name}.{ext}'
        if exact.exists():
            return exact
        matches = sorted(root.glob(f'*.{ext}'), key=lambda p: p.name.lower())
        return matches[0] if matches else None

    out['cmd'] = pick('cmd', 'cmd')
    out['cns'] = pick('cns', 'cns') or pick('st', 'st')
    out['air'] = pick('anim', 'air')
    out['sff'] = pick('sprite', 'sff')
    out['snd'] = pick('sound', 'snd')
    return out


def _slug(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', str(text)).strip('_') or 'item'


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _find_images(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted([p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXTS], key=lambda p: str(p).lower())


def _parse_sprite_filename(path: Path, fallback_index: int = 0) -> Tuple[int, int]:
    name = path.stem.lower()
    patterns = [
        r'g(?:roup)?\s*[_\- ]?(\d+)\s*[_\- ]?i(?:mage)?\s*[_\- ]?(\d+)',
        r'group\s*[_\- ]?(\d+)\s*[_\- ]?image\s*[_\- ]?(\d+)',
        r'^(\d+)\s*[_\-., ]\s*(\d+)$',
        r'^(\d+)\s*[_\- ]i(\d+)$',
    ]
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            return int(m.group(1)), int(m.group(2))
    return 0, fallback_index


def _image_size(path: Path) -> Tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def _load_sprite_image(sff_path: Path, sprite: SffSprite):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        data = sff_path.read_bytes()[sprite.data_offset:sprite.data_offset + sprite.length]
        img = Image.open(BytesIO(data))
        return img.convert('RGBA')
    except Exception:
        return None


def _find_action_by_number(root: Path, action_number: Optional[int] = None):
    air = find_character_file(root, 'air')
    if not air or not air.exists():
        return None, []
    actions = parse_air(read_text_safely(air))
    if action_number is not None:
        for action in actions:
            if action.number == action_number:
                return air, [action]
        return air, []
    return air, actions


def create_sff2_source_project(root: Path, image_folder: Optional[Path] = None, output_name: Optional[str] = None) -> CreatorSuiteResult:
    """Create a Sprmake2-ready source folder and SFF v2 definition file.

    This deliberately generates source files/instructions, not a home-grown SFF v2 binary writer.
    It keeps the risky part explicit: users can build with Elecbyte sprmake2 if they have it.
    """
    root = Path(root)
    result = CreatorSuiteResult('SFF v2 Source Project')
    out = _suite_dir(root) / 'sff2_source_project'
    src_dir = out / 'sprites'
    src_dir.mkdir(parents=True, exist_ok=True)
    image_folder = Path(image_folder) if image_folder else None
    images: List[Path] = []
    source_note = ''

    if image_folder and image_folder.exists():
        images = _find_images(image_folder)
        source_note = f'Imported from image folder: {image_folder}'
    else:
        # Prefer source/staged images first. Avoid exporting arbitrary report images.
        candidates = [root / 'source_sprites', root / 'sprites', root / 'asset_swap_pack' / 'new_sprites', root / 'quality_lab' / 'asset_swap_pack' / 'sprites']
        for cand in candidates:
            imgs = _find_images(cand)
            if imgs:
                images = imgs
                source_note = f'Imported from existing project image folder: {cand}'
                break

    # If no loose images exist, export supported v1 sprites to PNG/PCX source folder.
    if not images:
        sff = find_character_file(root, 'sff')
        if sff and sff.exists():
            try:
                info = read_sff(sff)
                if info.is_supported_for_extraction and info.sprites:
                    export_dir = out / 'exported_from_current_sff'
                    export_dir.mkdir(parents=True, exist_ok=True)
                    exported = []
                    for spr in info.sprites:
                        if spr.format_hint in {'pcx', 'png'}:
                            exported.append(export_sprite(sff, spr, export_dir))
                    images = exported
                    source_note = f'Exported supported sprites from current SFF: {sff.name}'
                elif info.variant.startswith('sff2'):
                    result.add_warning('Current SFF looks like SFF v2/non-v1. This version generates SFF2 build projects, but does not extract mature SFF2 sprite tables.')
            except Exception as exc:
                result.add_warning(f'Could not export current SFF source sprites: {exc}')

    manifest_rows: List[Dict[str, object]] = []
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None  # type: ignore

    for idx, img in enumerate(images):
        group, item = _parse_sprite_filename(img, idx)
        dst_name = f'g{group:04d}_i{item:04d}{img.suffix.lower() or ".png"}'
        dst = src_dir / dst_name
        if img.resolve() != dst.resolve():
            try:
                if Image is not None:
                    with Image.open(img) as im:
                        if dst.suffix.lower() != '.png':
                            dst = dst.with_suffix('.png')
                        # Keep alpha and color depth when possible for SFF v2 source workflows.
                        im.save(dst)
                else:
                    shutil.copy2(img, dst)
            except Exception:
                shutil.copy2(img, dst)
        w, h = _image_size(dst)
        manifest_rows.append({
            'group': group,
            'image': item,
            'filename': dst.name,
            'axisx': max(0, w // 2),
            'axisy': max(0, h - 1),
            'width': w,
            'height': h,
        })

    sff_name = output_name or f'{root.name}.sff'
    def_lines = [
        '; MugenForge Creator Suite - Sprmake2 SFF v2 source definition',
        '; Edit group/image/axis values here, then run one of the build scripts if sprmake2 is available.',
        '',
        '[Output]',
        f'filename = {sff_name}',
        '',
        '[Option]',
        'input.dir = sprites',
        'sprite.compress.5 = lz5',
        'sprite.compress.8 = rle8',
        'sprite.compress.24 = none',
        'sprite.decompressonload = 0',
        'sprite.detectduplicates = 1',
        'sprite.autocrop = 0',
        'pal.detectduplicates = 1',
        'pal.discardduplicates = 0',
        'pal.reverseact = 0',
        'pal.reversepng = 0',
        'sprite.usepal = -1',
        '',
        '[Sprite]',
    ]
    for row in manifest_rows:
        def_lines.append(f"{row['group']}, {row['image']}, {row['filename']}, {row['axisx']}, {row['axisy']}")
    if not manifest_rows:
        def_lines.append('; No source sprites were found yet. Add PNG files to the sprites folder and rerun this tool.')

    manifest = {
        'schema': 'mugenforge.creator_suite.sff2_source.v1',
        'created': datetime.now().isoformat(timespec='seconds'),
        'source_note': source_note,
        'output_sff': sff_name,
        'sprites': manifest_rows,
        'next_steps': [
            'Review sprite axes in sprmake2_project.def.',
            'Run make_sff2_windows.bat from this folder if sprmake2.exe is available.',
            'Copy the generated SFF back to the character folder when satisfied.',
        ],
    }

    def_path = out / 'sprmake2_project.def'
    _write(root, def_path, '\n'.join(def_lines), result)
    _write(root, out / 'mugenforge_sff2_manifest.json', json.dumps(manifest, indent=2), result)
    _write(root, out / 'make_sff2_windows.bat', '@echo off\nsetlocal\nif not exist sprmake2.exe echo Put sprmake2.exe next to this BAT or add it to PATH.\nsprmake2.exe -o "' + sff_name + '" "sprmake2_project.def"\npause\n', result)
    sh = '#!/usr/bin/env sh\nset -e\ncommand -v sprmake2 >/dev/null 2>&1 || echo "sprmake2 not found in PATH"\nsprmake2 -o "' + sff_name + '" "sprmake2_project.def"\n'
    sh_path = out / 'make_sff2_unix.sh'
    _write(root, sh_path, sh, result)
    try:
        sh_path.chmod(0o755)
    except Exception:
        pass

    readme = f"""# SFF v2 Source Project

This folder is a safe SFF v2 build handoff. MugenForge writes the source image folder and Sprmake2 definition file; it does not pretend to safely patch unknown mature SFF v2 binary tables.

Source: {source_note or 'No source image folder found yet.'}
Sprites listed: {len(manifest_rows)}

## Beginner steps

1. Put or replace PNG sprites in `sprites/`.
2. Open `sprmake2_project.def` and adjust axes if needed.
3. Put `sprmake2.exe` in this folder or in PATH.
4. Run `make_sff2_windows.bat`.
5. Copy `{sff_name}` to your character folder.
6. Open the character in MugenForge and run Quality Lab.

Filename patterns MugenForge understands: `g0_i0.png`, `group0_image0.png`, `0_0.png`.
"""
    _write(root, out / 'README_SFF2_SOURCE_PROJECT.md', readme, result)
    if not manifest_rows:
        result.add_warning('No source sprites found. The SFF2 project folder was created as a template.')
    else:
        result.add_note(f'SFF2 source project includes {len(manifest_rows)} sprites.')
    return result


def make_animation_contact_sheets(root: Path, max_actions: int = 40) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Animation Contact Sheets')
    out = _suite_dir(root) / 'animation_contact_sheets'
    out.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        result.add_warning('Pillow is required for animation contact sheets. Install with: pip install Pillow')
        return result

    air_path, actions = _find_action_by_number(root)
    if not air_path or not actions:
        result.add_warning('No AIR file/actions found.')
        return result
    sff_path = find_character_file(root, 'sff')
    lookup = {}
    if sff_path and sff_path.exists():
        try:
            lookup = sprite_lookup(read_sff(sff_path))
        except Exception as exc:
            result.add_warning(f'Could not read SFF for contact sheets: {exc}')
    rows_csv = []
    for action in actions[:max_actions]:
        thumbs = []
        for fi, frame in enumerate(action.frames[:80]):
            spr = lookup.get((frame.group, frame.image)) if lookup else None
            img = _load_sprite_image(sff_path, spr) if spr and sff_path else None
            if img is None:
                img = Image.new('RGBA', (72, 96), (255, 255, 255, 0))
                d = ImageDraw.Draw(img)
                d.rectangle((1, 1, 70, 94), outline=(150, 150, 150, 255))
                d.text((4, 36), f'{frame.group},{frame.image}', fill=(0, 0, 0, 255))
            img.thumbnail((120, 120), Image.Resampling.LANCZOS)
            tile = Image.new('RGBA', (140, 160), (255, 255, 255, 255))
            x = (140 - img.width) // 2
            y = 18 + (110 - img.height) // 2
            tile.alpha_composite(img, (x, y))
            d = ImageDraw.Draw(tile)
            d.rectangle((0, 0, 139, 159), outline=(210, 210, 210, 255))
            d.text((4, 3), f'#{fi} t={frame.ticks}', fill=(0, 0, 0, 255))
            d.text((4, 138), f'g{frame.group},i{frame.image}', fill=(0, 0, 0, 255))
            thumbs.append(tile.convert('RGB'))
            rows_csv.append([action.number, COMMON_ANIMS.get(action.number, action.label), fi, frame.group, frame.image, frame.ticks, frame.x, frame.y, frame.flags])
        if not thumbs:
            continue
        cols = min(6, max(1, len(thumbs)))
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new('RGB', (cols * 140, rows * 160 + 32), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        label = f'Action {action.number} {COMMON_ANIMS.get(action.number, action.label)}'.strip()
        draw.text((6, 8), label, fill=(0, 0, 0))
        for i, tile in enumerate(thumbs):
            sheet.paste(tile, ((i % cols) * 140, 32 + (i // cols) * 160))
        p = out / f'action_{action.number}_{_slug(COMMON_ANIMS.get(action.number, action.label))}.png'
        sheet.save(p)
        result.add_created(root, p)
    csv_path = out / 'animation_frames.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['action', 'label', 'frame', 'group', 'image', 'ticks', 'x', 'y', 'flags'])
        writer.writerows(rows_csv)
    result.add_created(root, csv_path)
    result.add_note(f'Created contact sheets for {min(len(actions), max_actions)} AIR actions.')
    return result


def make_onion_skin_previews(root: Path, max_actions: int = 20) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Onion Skin Previews')
    out = _suite_dir(root) / 'onion_skin_previews'
    out.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        result.add_warning('Pillow is required for onion-skin previews. Install with: pip install Pillow')
        return result
    air_path, actions = _find_action_by_number(root)
    if not air_path or not actions:
        result.add_warning('No AIR file/actions found.')
        return result
    sff_path = find_character_file(root, 'sff')
    if not sff_path or not sff_path.exists():
        result.add_warning('No SFF file found for onion-skin previews.')
        return result
    try:
        lookup = sprite_lookup(read_sff(sff_path))
    except Exception as exc:
        result.add_warning(f'Could not read SFF: {exc}')
        return result

    made = 0
    for action in actions[:max_actions]:
        frames = action.frames[:60]
        if len(frames) < 2:
            continue
        canvas = Image.new('RGBA', (360, 300), (255, 255, 255, 255))
        origin = (180, 230)
        for idx, frame in enumerate(frames):
            spr = lookup.get((frame.group, frame.image))
            img = _load_sprite_image(sff_path, spr) if spr else None
            if img is None:
                continue
            alpha = int(35 + (idx / max(1, len(frames) - 1)) * 180)
            layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            img = img.copy()
            img.putalpha(min(alpha, 220))
            x = origin[0] - (spr.x if spr else 0) + frame.x
            y = origin[1] - (spr.y if spr else 0) + frame.y
            layer.alpha_composite(img, (int(x), int(y)))
            canvas = Image.alpha_composite(canvas, layer)
        draw = ImageDraw.Draw(canvas)
        draw.line((origin[0] - 18, origin[1], origin[0] + 18, origin[1]), fill=(0, 0, 0, 180))
        draw.line((origin[0], origin[1] - 18, origin[0], origin[1] + 18), fill=(0, 0, 0, 180))
        draw.text((8, 8), f'Action {action.number} onion skin', fill=(0, 0, 0, 255))
        p = out / f'action_{action.number}_onion.png'
        canvas.convert('RGB').save(p)
        result.add_created(root, p)
        made += 1
    if made == 0:
        result.add_warning('No onion-skin previews could be made. SFF payloads may be unsupported or actions may be empty.')
    else:
        result.add_note(f'Created {made} onion-skin preview images.')
    return result


def write_animation_doctor(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Animation Doctor')
    out = _suite_dir(root) / 'animation_doctor'
    out.mkdir(parents=True, exist_ok=True)
    air_path, actions = _find_action_by_number(root)
    if not air_path or not actions:
        result.add_warning('No AIR file/actions found.')
        return result
    rows = []
    warnings = []
    for action in actions:
        total_ticks = sum(max(0, f.ticks) for f in action.frames)
        zero = sum(1 for f in action.frames if f.ticks <= 0)
        long = sum(1 for f in action.frames if f.ticks >= 12)
        groups = {(f.group, f.image) for f in action.frames}
        x_jitter = max([f.x for f in action.frames] or [0]) - min([f.x for f in action.frames] or [0])
        y_jitter = max([f.y for f in action.frames] or [0]) - min([f.y for f in action.frames] or [0])
        clsn1 = sum(1 for f in action.frames for b in f.clsn if b.kind.lower() == 'clsn1')
        clsn2 = sum(1 for f in action.frames for b in f.clsn if b.kind.lower() == 'clsn2')
        score = 100
        if not action.frames:
            score -= 40; warnings.append(f'Action {action.number} has no frames.')
        if zero:
            score -= min(30, zero * 8); warnings.append(f'Action {action.number} has {zero} zero/negative tick frames.')
        if long:
            score -= min(20, long * 5)
        if x_jitter > 10 or y_jitter > 10:
            score -= 10
        rows.append({
            'action': action.number,
            'label': COMMON_ANIMS.get(action.number, action.label),
            'frames': len(action.frames),
            'unique_sprites': len(groups),
            'ticks': total_ticks,
            'seconds_at_60fps': round(total_ticks / 60.0, 3),
            'zero_tick_frames': zero,
            'long_tick_frames': long,
            'x_offset_range': x_jitter,
            'y_offset_range': y_jitter,
            'clsn1_boxes': clsn1,
            'clsn2_boxes': clsn2,
            'doctor_score': max(0, score),
        })
    csv_path = out / 'animation_doctor.csv'
    _csv(csv_path, rows, list(rows[0].keys()) if rows else ['action'])
    md = ['# Animation Doctor', '', f'AIR file: `{_rel(root, air_path)}`', '', '| Action | Label | Frames | Ticks | Seconds | CLSN1 | CLSN2 | Score | Notes |', '|---:|---|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        notes = []
        if r['zero_tick_frames']:
            notes.append('zero ticks')
        if r['long_tick_frames']:
            notes.append('long holds')
        if r['x_offset_range'] or r['y_offset_range']:
            notes.append(f"offset range {r['x_offset_range']}/{r['y_offset_range']}")
        md.append(f"| {r['action']} | {r['label']} | {r['frames']} | {r['ticks']} | {r['seconds_at_60fps']} | {r['clsn1_boxes']} | {r['clsn2_boxes']} | {r['doctor_score']} | {', '.join(notes)} |")
    if warnings:
        md += ['', '## Warnings'] + [f'- {w}' for w in warnings]
    md_path = out / 'ANIMATION_DOCTOR.md'
    _write(root, md_path, '\n'.join(md), result)
    result.add_created(root, csv_path)
    result.notes.append(f'Animation Doctor checked {len(actions)} actions.')
    return result


def create_sound_waveform_sheet(root: Path, wav_folder: Optional[Path] = None, max_sounds: int = 80) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Sound Waveform Sheet')
    out = _suite_dir(root) / 'sound_waveforms'
    out.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        result.add_warning('Pillow is required for sound waveform sheets. Install with: pip install Pillow')
        return result

    wavs: List[Path] = []
    wav_folder = Path(wav_folder) if wav_folder else None
    if wav_folder and wav_folder.exists():
        wavs = sorted(wav_folder.rglob('*.wav'), key=lambda p: str(p).lower())
    else:
        for cand in [root / 'sounds', root / 'sound', root / 'creator_suite' / 'sound_waveforms' / 'extracted_wavs']:
            if cand.exists():
                wavs = sorted(cand.rglob('*.wav'), key=lambda p: str(p).lower())
                if wavs:
                    break
        if not wavs:
            snd = find_character_file(root, 'snd')
            if snd and snd.exists():
                try:
                    info = read_snd(snd)
                    ex = out / 'extracted_wavs'
                    ex.mkdir(parents=True, exist_ok=True)
                    for sound in info.sounds[:max_sounds]:
                        if sound.format_hint.lower().startswith('wave') or sound.format_hint.lower() == 'wav':
                            wavs.append(export_sound(snd, sound, ex))
                except Exception as exc:
                    result.add_warning(f'Could not extract current SND sounds: {exc}')
    rows = []
    tiles = []
    for idx, wav_path in enumerate(wavs[:max_sounds]):
        try:
            with wave.open(str(wav_path), 'rb') as wf:
                channels = wf.getnchannels()
                rate = wf.getframerate()
                frames = wf.getnframes()
                width = wf.getsampwidth()
                raw = wf.readframes(frames)
                duration = frames / float(rate or 1)
            # Downsample raw PCM for a simple display. 8/16-bit PCM are enough for placeholders and most MUGEN WAVs.
            samples: List[int] = []
            if width == 1:
                vals = list(raw[::max(1, channels)])
                samples = [v - 128 for v in vals]
                scale = 128
            elif width >= 2:
                import struct
                step = width * channels
                count = len(raw) // step
                stride = max(1, count // 220)
                for i in range(0, count, stride):
                    off = i * step
                    samples.append(struct.unpack_from('<h', raw, off)[0])
                scale = 32768
            else:
                samples = []
                scale = 1
            tile = Image.new('RGB', (260, 86), (255, 255, 255))
            d = ImageDraw.Draw(tile)
            d.rectangle((0, 0, 259, 85), outline=(205, 205, 205))
            d.text((4, 4), wav_path.name[:32], fill=(0, 0, 0))
            d.text((4, 18), f'{channels}ch {rate}Hz {duration:.2f}s', fill=(0, 0, 0))
            mid = 58
            d.line((4, mid, 256, mid), fill=(180, 180, 180))
            if samples:
                points = []
                for x in range(4, 256):
                    si = int((x - 4) / 252 * max(1, len(samples) - 1))
                    amp = max(-1.0, min(1.0, samples[si] / float(scale)))
                    y = int(mid - amp * 24)
                    points.append((x, y))
                d.line(points, fill=(0, 0, 0))
            tiles.append(tile)
            rows.append({'file': _rel(root, wav_path), 'channels': channels, 'sample_rate': rate, 'sample_width': width, 'frames': frames, 'duration': round(duration, 4)})
        except Exception as exc:
            result.add_warning(f'Could not read WAV {wav_path.name}: {exc}')
    if tiles:
        cols = 2
        rows_count = math.ceil(len(tiles) / cols)
        sheet = Image.new('RGB', (cols * 260, rows_count * 86 + 28), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        d.text((6, 6), 'MugenForge Sound Waveform Sheet', fill=(0, 0, 0))
        for i, tile in enumerate(tiles):
            sheet.paste(tile, ((i % cols) * 260, 28 + (i // cols) * 86))
        p = out / 'SOUND_WAVEFORM_SHEET.png'
        sheet.save(p)
        result.add_created(root, p)
    csv_path = out / 'sound_waveforms.csv'
    fields = ['file', 'channels', 'sample_rate', 'sample_width', 'frames', 'duration']
    _csv(csv_path, rows, fields)
    result.add_created(root, csv_path)
    if not rows:
        result.add_warning('No WAV files found. Put WAVs in a sounds/ folder or open a project with a readable SND.')
    else:
        result.add_note(f'Waveform sheet indexed {len(rows)} WAV files.')
    return result


def write_palette_doctor(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Palette Doctor')
    out = _suite_dir(root) / 'palette_doctor'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for act in sorted(root.rglob('*.act'), key=lambda p: str(p).lower()):
        try:
            pal = read_act(act)
            colors = pal.colors
            unique = len(set(colors))
            transparent = colors[0] if colors else None
            rows.append({'file': _rel(root, act), 'colors': len(colors), 'unique_colors': unique, 'first_color_rgb': transparent, 'duplicate_colors': len(colors) - unique})
        except Exception as exc:
            rows.append({'file': _rel(root, act), 'colors': 0, 'unique_colors': 0, 'first_color_rgb': '', 'duplicate_colors': 0, 'error': str(exc)})
    image_rows = []
    try:
        from PIL import Image  # type: ignore
        for img in _find_images(root):
            if 'creator_suite' in img.parts or 'quality_lab' in img.parts:
                continue
            try:
                with Image.open(img) as im:
                    mode = im.mode
                    colors = im.getcolors(maxcolors=1000000)
                    color_count = len(colors) if colors is not None else '1000000+'
                    image_rows.append({'file': _rel(root, img), 'mode': mode, 'colors': color_count, 'size': f'{im.width}x{im.height}'})
            except Exception:
                pass
    except Exception:
        result.add_warning('Pillow not available; image color-mode audit skipped.')
    md = ['# Palette Doctor', '', '## ACT palettes', '', '| File | Colors | Unique | Duplicate | First color |', '|---|---:|---:|---:|---|']
    if rows:
        for r in rows:
            md.append(f"| {r.get('file')} | {r.get('colors')} | {r.get('unique_colors')} | {r.get('duplicate_colors')} | {r.get('first_color_rgb', '')} |")
    else:
        md.append('| _No ACT palettes found_ |  |  |  |  |')
    md += ['', '## Sprite/image color modes', '', '| File | Mode | Colors | Size |', '|---|---|---:|---|']
    for r in image_rows[:500]:
        md.append(f"| {r['file']} | {r['mode']} | {r['colors']} | {r['size']} |")
    md += ['', '## Beginner notes', '', '- Keep character sprites palette-consistent when using classic indexed workflows.', '- Use Image Factory palette reduction/variants for fast experiments.', '- Check transparent/background colors before release.', '- For SFF v2 source workflows, keep PNG originals organized so you can rebuild cleanly.']
    md_path = out / 'PALETTE_DOCTOR.md'
    _write(root, md_path, '\n'.join(md), result)
    csv_path = out / 'palette_doctor_act.csv'
    fields = ['file', 'colors', 'unique_colors', 'duplicate_colors', 'first_color_rgb']
    _csv(csv_path, rows, fields)
    result.add_created(root, csv_path)
    return result


def write_no_code_recipe_bank(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('No-Code Recipe Bank')
    out = _suite_dir(root) / 'no_code_recipe_bank'
    out.mkdir(parents=True, exist_ok=True)
    recipes = [
        {
            'name': 'Normal attack recipe',
            'user_choices': ['button', 'standing/crouching/air', 'startup', 'active', 'recovery', 'damage', 'hit level'],
            'auto_writes': ['CMD command', 'State -1 ChangeState trigger', 'StateDef', 'HitDef', 'AIR action', 'starter CLSN boxes'],
            'beginner_tip': 'Start with light/medium/heavy damage tiers before making complex chains.',
        },
        {
            'name': 'Projectile recipe',
            'user_choices': ['motion', 'speed', 'damage', 'lifetime', 'spark/sound', 'EX version'],
            'auto_writes': ['CMD input', 'startup state', 'Projectile controller', 'projectile animation', 'sound cue placeholders'],
            'beginner_tip': 'Keep projectile startup readable and leave recovery so opponents can punish.',
        },
        {
            'name': 'Throw recipe',
            'user_choices': ['range', 'damage', 'throw direction', 'techable?', 'animation IDs'],
            'auto_writes': ['CMD input', 'Throw/TargetBind skeleton', 'victim timing notes', 'sound/FX cues'],
            'beginner_tip': 'Throws need extra testing because the opponent animation state matters.',
        },
        {
            'name': 'Super recipe',
            'user_choices': ['motion', 'meter cost', 'startup freeze', 'damage budget', 'cinematic or simple'],
            'auto_writes': ['power check', 'superpause', 'HitDef/Projectile', 'FX/sound router', 'balance notes'],
            'beginner_tip': 'Do not make every super full-screen safe. Decide what the player is paying meter for.',
        },
        {
            'name': 'Movement recipe',
            'user_choices': ['dash/roll/teleport/jump option', 'velocity', 'invulnerability', 'cancel options'],
            'auto_writes': ['CMD input', 'movement StateDef', 'AIR action', 'safety notes'],
            'beginner_tip': 'Movement defines the character as much as attacks. Test feel before adding more moves.',
        },
    ]
    _write(root, out / 'NO_CODE_RECIPE_BANK.json', json.dumps({'schema': 'mugenforge.no_code_recipe_bank.v1', 'recipes': recipes}, indent=2), result)
    md = ['# No-Code Recipe Bank', '', 'This bank explains what a non-coder chooses and what MugenForge should generate behind the scenes.', '']
    for rec in recipes:
        md += [f"## {rec['name']}", '', '**User chooses:** ' + ', '.join(rec['user_choices']), '', '**MugenForge auto-writes:** ' + ', '.join(rec['auto_writes']), '', f"**Tip:** {rec['beginner_tip']}", '']
    _write(root, out / 'NO_CODE_RECIPE_BANK.md', '\n'.join(md), result)
    result.add_note('Recipe bank is documentation/structure for building more no-code forms and presets.')
    return result


def write_combo_blueprint(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Combo Blueprint Builder')
    out = _suite_dir(root) / 'combo_blueprints'
    out.mkdir(parents=True, exist_ok=True)
    texts: Dict[str, str] = {}
    for pat in ('*.cmd', '*.cns', '*.st'):
        for path in root.rglob(pat):
            if path.is_file():
                try:
                    texts[_rel(root, path)] = read_text_safely(path)
                except Exception:
                    pass
    commands = []
    states = []
    for rel, text in texts.items():
        scan = parse_code(text)
        for c in scan.commands:
            commands.append({'file': rel, 'name': c.name, 'command': c.command, 'time': c.time, 'buffer_time': c.buffer_time})
        for st in scan.states:
            anim = st.values.get('anim', '')
            ctrl = st.values.get('ctrl', '')
            type_ = st.values.get('type', '')
            physics = st.values.get('physics', '')
            hitdefs = [ctrlr for ctrlr in st.controllers if (ctrlr.stype or ctrlr.values.get('type', '')).lower() == 'hitdef']
            states.append({'file': rel, 'state': st.number, 'anim': anim, 'ctrl': ctrl, 'type': type_, 'physics': physics, 'hitdefs': len(hitdefs)})
    attack_states = [s for s in states if s['hitdefs']]
    blueprint = {
        'schema': 'mugenforge.combo_blueprints.v1',
        'commands': commands,
        'attack_states': attack_states,
        'starter_combo_ideas': [
            {'name': 'Light > Medium > Heavy', 'states': [s['state'] for s in attack_states[:3]], 'notes': 'Make each state cancel into the next only on hit/block first.'},
            {'name': 'Launcher > Air follow-up', 'states': [s['state'] for s in attack_states if int(s['state']) >= 600][:4], 'notes': 'Keep juggle limits conservative.'},
            {'name': 'Projectile confirm', 'states': [s['state'] for s in attack_states if int(s['state']) >= 1000][:3], 'notes': 'Only allow follow-up if projectile hitstun is long enough.'},
        ]
    }
    _write(root, out / 'COMBO_BLUEPRINTS.json', json.dumps(blueprint, indent=2), result)
    md = ['# Combo Blueprints', '', 'This is a beginner-readable view of existing commands and attack states.', '', '## Commands']
    for c in commands[:200]:
        md.append(f"- `{c['name']}` = `{c['command']}` ({c['file']})")
    md += ['', '## Attack states']
    for s in attack_states[:200]:
        md.append(f"- State `{s['state']}` anim `{s['anim']}` hitdefs `{s['hitdefs']}` file `{s['file']}`")
    md += ['', '## Starter combo ideas']
    for idea in blueprint['starter_combo_ideas']:
        md.append(f"- **{idea['name']}**: {idea['states']} — {idea['notes']}")
    _write(root, out / 'COMBO_BLUEPRINTS.md', '\n'.join(md), result)
    return result


def write_creator_command_center(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Creator Command Center')
    out = _suite_dir(root)
    links = []
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.suffix.lower() in {'.md', '.csv', '.json', '.png', '.html'}:
            links.append(p)
    if not links:
        links = []
    html_lines = ['<!doctype html><meta charset="utf-8"><title>MugenForge Creator Command Center</title>', '<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.4} code{background:#eee;padding:2px 4px} li{margin:6px 0}</style>', f'<h1>{html.escape(root.name)} — Creator Command Center</h1>', '<p>Open this file after running Creator Suite tools. It links the reports, previews, source projects, and beginner guides.</p>', '<h2>Fast route</h2>', '<ol><li>Run One-Click Creator Suite.</li><li>Open Animation Doctor and contact sheets.</li><li>Replace rough art/sounds in the asset folders.</li><li>Use the SFF v2 source project or SFF v1 builder depending on your target.</li><li>Run Quality Lab before packaging.</li></ol>', '<h2>Generated files</h2>', '<ul>']
    for p in links:
        rel = _rel(out, p)
        html_lines.append(f'<li><a href="{html.escape(rel)}">{html.escape(rel)}</a></li>')
    html_lines += ['</ul>']
    p = out / 'CREATOR_COMMAND_CENTER.html'
    _write(root, p, '\n'.join(html_lines), result)
    return result


def create_release_comparison_report(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('Factory-Style Parity Report')
    out = _suite_dir(root) / 'factory_parity'
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        ('Sprites/SFF v1', 'Build/extract/replacement pipeline', 'Available'),
        ('Sprites/SFF v2', 'Source-project generator for Sprmake2', 'Available as safe source workflow'),
        ('Animations/AIR', 'Timeline, playback, contact sheets, onion skin, timing doctor', 'Available'),
        ('Hitboxes/CLSN', 'Visual drag/resize plus generated suggestions', 'Available'),
        ('Sounds/SND', 'Inspect/extract/build starter SND plus waveform sheets', 'Available'),
        ('Palettes/ACT', 'Build/edit/audit/variant workflow', 'Available'),
        ('Code/CMD/CNS/ST', 'Feature Bank, Move Wizard, CodeSense, state graph, audits', 'Available'),
        ('No-code workflow', 'Archetypes, kits, repair passes, reports, recipe bank', 'Available'),
        ('Mature SFF v2 mutation', 'Direct binary patch/rebuild of arbitrary SFF2 tables', 'Not implemented; use source-project handoff'),
    ]
    md = ['# Factory-Style Parity Report', '', '| Area | MugenForge workflow | Status |', '|---|---|---|']
    md += [f'| {a} | {b} | {c} |' for a, b, c in rows]
    md += ['', '## Tell-it-like-it-is note', '', 'MugenForge is strongest when the project is source-organized: loose sprites, generated manifests, AIR/CMD/CNS text, WAVs, and repeatable build steps. It is intentionally conservative about patching mature SFF v2 binaries because corrupting sprite tables would be worse than forcing a rebuild from source.']
    _write(root, out / 'FACTORY_STYLE_PARITY_REPORT.md', '\n'.join(md), result)
    return result


def run_creator_suite_pass(root: Path) -> CreatorSuiteResult:
    root = Path(root)
    result = CreatorSuiteResult('One-Click Creator Suite Pass')
    for label, func in [
        ('SFF2 source project', create_sff2_source_project),
        ('Animation Doctor', write_animation_doctor),
        ('Animation contact sheets', make_animation_contact_sheets),
        ('Onion skin previews', make_onion_skin_previews),
        ('Sound waveform sheet', create_sound_waveform_sheet),
        ('Palette Doctor', write_palette_doctor),
        ('No-code recipe bank', write_no_code_recipe_bank),
        ('Combo blueprint', write_combo_blueprint),
        ('Factory-style parity report', create_release_comparison_report),
    ]:
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.add_warning(f'{label} failed: {exc}')
    try:
        result.merge(write_creator_command_center(root), 'Command center')
    except Exception as exc:
        result.add_warning(f'Command center failed: {exc}')
    result.add_note('Creator Suite pass finished. Open creator_suite/CREATOR_COMMAND_CENTER.html for the beginner dashboard.')
    return result


# ---------------------------------------------------------------------------
# v3.2 Creator Suite no-code tuning/handoff additions
# ---------------------------------------------------------------------------

def _hitdef_blocks_in_text(text: str):
    """Yield mutable HitDef block metadata from M.U.G.E.N code text."""
    block_re = re.compile(r'(^\s*\[\s*State\s+[^\]]+\]\s*$.*?)(?=^\s*\[|\Z)', re.I | re.M | re.S)
    kv_re = re.compile(r'^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$', re.M)
    for m in block_re.finditer(text):
        block = m.group(1)
        kv = {k.group(1).strip().lower(): k.group(2).strip() for k in kv_re.finditer(block)}
        if kv.get('type', '').lower() == 'hitdef':
            yield m.start(1), m.end(1), block, kv


def export_hitdef_tuning_sheet(root: Path) -> CreatorSuiteResult:
    """Export a beginner-editable CSV of HitDef tuning values.

    The creator can edit the CSV first, then use Apply HitDef Tuning Sheet to write values
    back to the code with backups. This keeps the code hidden until the user is ready.
    """
    root = Path(root)
    r = CreatorSuiteResult('HitDef Tuning Sheet Export')
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        text = read_text_safely(path)
        for idx, (start, end, block, kv) in enumerate(_hitdef_blocks_in_text(text), 1):
            state = ''
            before = text[:start]
            sm = list(re.finditer(r'^\s*\[\s*StateDef\s+(-?\d+)\s*\]', before, re.I | re.M))
            if sm:
                state = sm[-1].group(1)
            rows.append({
                'file': _rel(root, path),
                'hitdef_index_in_file': idx,
                'state': state,
                'damage': kv.get('damage', ''),
                'pausetime': kv.get('pausetime', ''),
                'ground.velocity': kv.get('ground.velocity', ''),
                'air.velocity': kv.get('air.velocity', ''),
                'hitflag': kv.get('hitflag', ''),
                'guardflag': kv.get('guardflag', ''),
                'sparkno': kv.get('sparkno', ''),
                'guard.sparkno': kv.get('guard.sparkno', ''),
                'priority': kv.get('priority', ''),
                'creator_notes': 'edit values here, then apply with backups',
            })
    out = root / 'reports'
    fields = ['file', 'hitdef_index_in_file', 'state', 'damage', 'pausetime', 'ground.velocity', 'air.velocity', 'hitflag', 'guardflag', 'sparkno', 'guard.sparkno', 'priority', 'creator_notes']
    _csv(out / 'hitdef_tuning_sheet.csv', rows, fields)
    r.created_files.append('reports/hitdef_tuning_sheet.csv')
    md = [f'# HitDef Tuning Sheet: {root.name}', '', 'Edit `reports/hitdef_tuning_sheet.csv`, then use **Apply HitDef Tuning Sheet**. Backups are written first.', '', f'HitDefs exported: {len(rows)}', '', '## Beginner columns', '- `damage`: main damage value; keep small normals lower than supers.', '- `pausetime`: hit freeze feel.', '- `ground.velocity` / `air.velocity`: pushback/launch feel.', '- `hitflag` / `guardflag`: who the move can hit/block.', '']
    md += [f"- State `{row['state']}` in `{row['file']}` damage `{row['damage']}`" for row in rows[:200]] or ['- No HitDefs found yet.']
    _write(root, out / 'HITDEF_TUNING_SHEET.md', '\n'.join(md) + '\n', r, changed=(out / 'HITDEF_TUNING_SHEET.md').exists())
    r.notes.append(f'Exported {len(rows)} HitDef rows for no-code tuning.')
    return r


def _replace_or_add_kv(block: str, key: str, value: str) -> str:
    if value is None or str(value).strip() == '':
        return block
    pattern = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*).*$' , re.I | re.M)
    if pattern.search(block):
        return pattern.sub(lambda m: m.group(1) + str(value), block, count=1)
    return block.rstrip() + f'\n{key} = {value}\n'


def apply_hitdef_tuning_sheet(root: Path, csv_path: Optional[Path] = None) -> CreatorSuiteResult:
    """Apply reports/hitdef_tuning_sheet.csv back to HitDef blocks with backups."""
    root = Path(root)
    r = CreatorSuiteResult('HitDef Tuning Sheet Apply')
    csv_path = Path(csv_path) if csv_path else root / 'reports' / 'hitdef_tuning_sheet.csv'
    if not csv_path.exists():
        r.warnings.append(f'Tuning sheet not found: {_rel(root, csv_path)}. Export it first.')
        return r
    rows_by_file: Dict[str, List[Dict[str, str]]] = {}
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            rows_by_file.setdefault(row.get('file', ''), []).append(dict(row))
    keys = ['damage', 'pausetime', 'ground.velocity', 'air.velocity', 'hitflag', 'guardflag', 'sparkno', 'guard.sparkno', 'priority']
    for rel, rows in rows_by_file.items():
        path = (root / rel).resolve()
        if not path.exists():
            r.warnings.append(f'Skipped missing file from sheet: {rel}')
            continue
        text = read_text_safely(path)
        blocks = list(_hitdef_blocks_in_text(text))
        if not blocks:
            continue
        replacements: List[Tuple[int, int, str]] = []
        for row in rows:
            try:
                idx = max(1, int(row.get('hitdef_index_in_file', '0'))) - 1
            except Exception:
                idx = -1
            if idx < 0 or idx >= len(blocks):
                r.warnings.append(f'Skipped bad HitDef index {row.get("hitdef_index_in_file")} in {rel}')
                continue
            start, end, block, kv = blocks[idx]
            new_block = block
            for key in keys:
                if key in row and str(row.get(key, '')).strip() != str(kv.get(key, '')).strip():
                    new_block = _replace_or_add_kv(new_block, key, str(row.get(key, '')).strip())
            if new_block != block:
                replacements.append((start, end, new_block))
        if replacements:
            _backup(path)
            for start, end, new_block in sorted(replacements, key=lambda x: x[0], reverse=True):
                text = text[:start] + new_block.rstrip() + '\n' + text[end:]
            write_text_safely(path, text)
            r.changed_files.append(_rel(root, path))
    r.notes.append('Applied editable HitDef tuning sheet values with backups.')
    return r


def write_artist_handoff_pack(root: Path) -> CreatorSuiteResult:
    """Create a beginner-safe art/sound handoff folder for replacing assets."""
    root = Path(root)
    r = CreatorSuiteResult('Artist / Sound Handoff Pack')
    out = root / 'handoff'
    out.mkdir(parents=True, exist_ok=True)
    files = _discover_files(root)
    sprite_rows: List[Dict[str, object]] = []
    sound_rows: List[Dict[str, object]] = []
    sff_keys = set()
    if files.get('sff') and files['sff'] and files['sff'].exists():
        try:
            sff_keys = set(sprite_lookup(read_sff(files['sff'])).keys())
        except Exception as e:
            r.warnings.append(f'SFF scan failed: {e}')
    if files.get('air') and files['air'] and files['air'].exists():
        try:
            for action in parse_air(read_text_safely(files['air'])):
                for idx, fr in enumerate(action.frames):
                    if fr.group < 0 or fr.image < 0:
                        continue
                    sprite_rows.append({
                        'action': action.number,
                        'frame': idx,
                        'group': fr.group,
                        'image': fr.image,
                        'ticks': fr.ticks,
                        'status': 'present' if (fr.group, fr.image) in sff_keys else 'missing_or_placeholder',
                        'artist_filename_suggestion': f'g{fr.group}_i{fr.image}.png',
                    })
        except Exception as e:
            r.warnings.append(f'AIR scan failed: {e}')
    # Sound requests from PlaySnd values.
    for path in _code_files(root):
        try:
            text = read_text_safely(path)
        except Exception:
            continue
        for m in re.finditer(r'type\s*=\s*PlaySnd\b.*?(?=^\s*\[|\Z)', text, re.I | re.M | re.S):
            block = m.group(0)
            vm = re.search(r'^\s*value\s*=\s*([^;\n]+)', block, re.I | re.M)
            if not vm:
                continue
            nums = re.findall(r'-?\d+', vm.group(1))
            if len(nums) >= 2:
                sound_rows.append({'file': _rel(root, path), 'group': nums[0], 'sound': nums[1], 'suggested_filename': f'{nums[0]}_{nums[1]}.wav', 'status': 'replace_or_verify'})
    _csv(out / 'sprite_requests.csv', sprite_rows, ['action', 'frame', 'group', 'image', 'ticks', 'status', 'artist_filename_suggestion'])
    _csv(out / 'sound_requests.csv', sound_rows, ['file', 'group', 'sound', 'suggested_filename', 'status'])
    r.created_files.extend(['handoff/sprite_requests.csv', 'handoff/sound_requests.csv'])
    md = [f'# Artist / Sound Handoff Pack: {root.name}', '', 'This folder is for creators who do not want to edit packed `.sff` / `.snd` files by hand.', '', '## Sprite workflow', '1. Open `sprite_requests.csv`.', '2. Draw/replace the suggested PNG files.', '3. Use Sprite Lab / Sheet Import / Build SFF v1.', '4. Preview with Animation Player and CLSN Editor.', '', '## Sound workflow', '1. Open `sound_requests.csv`.', '2. Create WAV files with suggested names like `5_0.wav`.', '3. Use Sounds → Make WAV Manifest → Build SND.', '', f'- Sprite rows: {len(sprite_rows)}', f'- Sound rows: {len(sound_rows)}']
    _write(root, out / 'README_HANDOFF.md', '\n'.join(md) + '\n', r, changed=(out / 'README_HANDOFF.md').exists())
    r.notes.append('Created a handoff pack for art and sound replacement.')
    return r
