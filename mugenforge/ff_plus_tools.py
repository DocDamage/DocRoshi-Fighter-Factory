from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from typing import Iterable, List, Sequence, Tuple, Optional

from .parsers import (
    TEXT_EXTS, COMMON_ANIMS, read_text_safely, write_text_safely,
    parse_air, parse_code, parse_def, scan_project,
)
from .move_wizard import find_character_file
from .palette_tools import write_act
from .sff_codec import build_sff_v1_from_manifest, read_sff
from .snd_codec import read_snd

IMAGE_INPUT_EXTS = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
WAV_EXTS = {'.wav'}


def _need_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
        return Image, ImageDraw, ImageFont, ImageOps, ImageChops
    except Exception as exc:
        raise RuntimeError('Pillow is required for this visual workflow. Install with: pip install Pillow') from exc


def _safe_stem(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', name).strip('_') or 'asset'


def image_files(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_INPUT_EXTS)


def wav_files(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in WAV_EXTS)


def summarize_image_folder(folder: Path) -> str:
    Image, *_ = _need_pillow()
    files = image_files(folder)
    lines = [f'Image folder: {Path(folder)}', f'Images found: {len(files)}']
    total_pixels = 0
    sizes: dict[tuple[int, int], int] = {}
    modes: dict[str, int] = {}
    for p in files[:5000]:
        try:
            with Image.open(p) as img:
                sizes[img.size] = sizes.get(img.size, 0) + 1
                modes[img.mode] = modes.get(img.mode, 0) + 1
                total_pixels += img.size[0] * img.size[1]
        except Exception:
            modes['unreadable'] = modes.get('unreadable', 0) + 1
    if sizes:
        lines += ['', 'Most common sizes:']
        for (w, h), count in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))[:12]:
            lines.append(f'- {w}x{h}: {count}')
    if modes:
        lines += ['', 'Modes:'] + [f'- {mode}: {count}' for mode, count in sorted(modes.items())]
    lines += ['', f'Total pixels scanned: {total_pixels:,}']
    return '\n'.join(lines).strip() + '\n'


def make_sprite_contact_sheet(folder: Path, out_path: Path, thumb_size: int = 96, columns: int = 6) -> Path:
    Image, ImageDraw, ImageFont, *_ = _need_pillow()
    files = image_files(folder)
    if not files:
        raise ValueError(f'No supported images found in {folder}')
    thumb_size = max(32, min(512, int(thumb_size)))
    columns = max(1, min(24, int(columns)))
    label_h = 36
    pad = 12
    rows = math.ceil(len(files) / columns)
    sheet_w = columns * (thumb_size + pad) + pad
    sheet_h = rows * (thumb_size + label_h + pad) + pad
    sheet = Image.new('RGBA', (sheet_w, sheet_h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 10)
    except Exception:
        font = None
    for idx, path in enumerate(files):
        col = idx % columns
        row = idx // columns
        x = pad + col * (thumb_size + pad)
        y = pad + row * (thumb_size + label_h + pad)
        try:
            img = Image.open(path).convert('RGBA')
            img.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
            bx = x + (thumb_size - img.width) // 2
            by = y + (thumb_size - img.height) // 2
            # checker-ish background
            draw.rectangle([x, y, x + thumb_size, y + thumb_size], fill=(255, 255, 255, 255), outline=(180, 180, 180, 255))
            sheet.alpha_composite(img, (bx, by))
            label = f'{idx}: {path.name}'
            draw.text((x, y + thumb_size + 4), label[:28], fill=(0, 0, 0, 255), font=font)
        except Exception as exc:
            draw.rectangle([x, y, x + thumb_size, y + thumb_size], fill=(255, 220, 220, 255), outline=(180, 0, 0, 255))
            draw.text((x + 3, y + 3), f'ERR\n{path.name}\n{exc}', fill=(150, 0, 0, 255), font=font)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert('RGB').save(out_path)
    return out_path


def _trim_transparency(img):
    Image, ImageDraw, ImageFont, ImageOps, ImageChops = _need_pillow()
    rgba = img.convert('RGBA')
    alpha = rgba.getchannel('A')
    bbox = alpha.getbbox()
    if bbox:
        return rgba.crop(bbox), bbox
    return rgba, (0, 0, rgba.width, rgba.height)


def _place_on_canvas(img, canvas_w: int, canvas_h: int, anchor: str = 'bottom-center'):
    Image, *_ = _need_pillow()
    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    if img.width > canvas_w or img.height > canvas_h:
        copy = img.copy()
        copy.thumbnail((canvas_w, canvas_h), Image.LANCZOS)
        img = copy
    if anchor == 'center':
        x = (canvas_w - img.width) // 2
        y = (canvas_h - img.height) // 2
    elif anchor == 'top-left':
        x, y = 0, 0
    elif anchor == 'bottom-left':
        x, y = 0, canvas_h - img.height
    elif anchor == 'bottom-right':
        x, y = canvas_w - img.width, canvas_h - img.height
    else:
        x = (canvas_w - img.width) // 2
        y = canvas_h - img.height
    canvas.alpha_composite(img, (x, y))
    return canvas, (x, y)


def normalize_sprite_folder(
    src_dir: Path,
    out_dir: Path,
    *,
    canvas_w: int = 96,
    canvas_h: int = 96,
    trim: bool = True,
    scale_percent: int = 100,
    flip_x: bool = False,
    flip_y: bool = False,
    anchor: str = 'bottom-center',
    group: int = 200,
    start_image: int = 0,
    axis_x: Optional[int] = None,
    axis_y: Optional[int] = None,
) -> Path:
    Image, ImageDraw, ImageFont, ImageOps, *_ = _need_pillow()
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = image_files(src_dir)
    if not files:
        raise ValueError(f'No supported images found in {src_dir}')
    canvas_w = max(1, int(canvas_w))
    canvas_h = max(1, int(canvas_h))
    scale_percent = max(1, int(scale_percent))
    records = []
    for idx, path in enumerate(files):
        img = Image.open(path).convert('RGBA')
        original_size = img.size
        crop_box = None
        if trim:
            img, crop_box = _trim_transparency(img)
        if scale_percent != 100:
            w = max(1, round(img.width * scale_percent / 100))
            h = max(1, round(img.height * scale_percent / 100))
            img = img.resize((w, h), Image.NEAREST if scale_percent >= 100 else Image.LANCZOS)
        if flip_x:
            img = ImageOps.mirror(img)
        if flip_y:
            img = ImageOps.flip(img)
        canvas, placed_at = _place_on_canvas(img, canvas_w, canvas_h, anchor=anchor)
        filename = f'g{int(group):05d}_i{int(start_image) + idx:04d}_{_safe_stem(path.stem)}.png'
        out_img = out_dir / filename
        canvas.save(out_img)
        records.append({
            'index': idx,
            'group': int(group),
            'image': int(start_image) + idx,
            'axis': {'x': int(axis_x if axis_x is not None else canvas_w // 2), 'y': int(axis_y if axis_y is not None else canvas_h - 1)},
            'filename': filename,
            'source': str(path),
            'source_size': {'w': original_size[0], 'h': original_size[1]},
            'trim_box': list(crop_box) if crop_box else None,
            'placed_at': {'x': placed_at[0], 'y': placed_at[1]},
        })
    manifest = {
        'tool': 'MugenForge Studio',
        'schema': 'mugenforge.normalized_sprite_folder.v1',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'source_folder': str(src_dir),
        'canvas': {'w': canvas_w, 'h': canvas_h, 'anchor': anchor},
        'sprites': records,
    }
    manifest_path = out_dir / 'mugenforge_sprite_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest_path


def convert_images_to_pcx(src_dir: Path, out_dir: Path) -> List[Path]:
    Image, *_ = _need_pillow()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for path in image_files(src_dir):
        img = Image.open(path).convert('RGBA')
        bg = Image.new('RGBA', img.size, (0, 0, 0, 0))
        bg.alpha_composite(img)
        pal = bg.convert('RGB').convert('P', palette=Image.Palette.ADAPTIVE if hasattr(Image, 'Palette') else Image.ADAPTIVE, colors=256)
        out = out_dir / f'{_safe_stem(path.stem)}.pcx'
        pal.save(out, format='PCX')
        outputs.append(out)
    if not outputs:
        raise ValueError(f'No supported images found in {src_dir}')
    return outputs


def make_animation_gif(src_dir: Path, out_path: Path, frame_ms: int = 80) -> Path:
    Image, *_ = _need_pillow()
    files = image_files(src_dir)
    if not files:
        raise ValueError(f'No supported images found in {src_dir}')
    frames = [Image.open(p).convert('RGBA') for p in files]
    max_w = max(f.width for f in frames)
    max_h = max(f.height for f in frames)
    norm = []
    for f in frames:
        canvas, _ = _place_on_canvas(f, max_w, max_h, 'bottom-center')
        norm.append(canvas.convert('P', palette=Image.Palette.ADAPTIVE if hasattr(Image, 'Palette') else Image.ADAPTIVE, colors=256))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    norm[0].save(out_path, save_all=True, append_images=norm[1:], loop=0, duration=max(1, int(frame_ms)), disposal=2)
    return out_path


def make_air_from_image_sequence(src_dir: Path, out_path: Path, *, action: int = 200, group: int = 200, start_image: int = 0, ticks: int = 5, x: int = 0, y: int = 0) -> Path:
    files = image_files(src_dir)
    if not files:
        raise ValueError(f'No supported images found in {src_dir}')
    lines = [f'[Begin Action {int(action)}] ; generated from {Path(src_dir).name}']
    lines.append('Clsn2Default: 1')
    lines.append('Clsn2[0] = -18, -88, 18, 0')
    for idx, _ in enumerate(files):
        lines.append(f'{int(group)}, {int(start_image) + idx}, {int(x)}, {int(y)}, {int(ticks)}')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out_path


def build_sff_from_image_folder(src_dir: Path, out_sff: Path, *, stage_dir: Optional[Path] = None, group: int = 200, start_image: int = 0, canvas_w: int = 96, canvas_h: int = 96, axis_x: Optional[int] = None, axis_y: Optional[int] = None) -> Path:
    src_dir = Path(src_dir)
    out_sff = Path(out_sff)
    stage_dir = Path(stage_dir) if stage_dir else out_sff.parent / 'staged_sprites' / f'build_{_safe_stem(out_sff.stem)}'
    manifest = normalize_sprite_folder(src_dir, stage_dir, group=group, start_image=start_image, canvas_w=canvas_w, canvas_h=canvas_h, axis_x=axis_x, axis_y=axis_y)
    build_sff_v1_from_manifest(manifest, out_sff)
    return out_sff


def build_act_from_folder(src_dir: Path, out_act: Path, max_colors: int = 256) -> Path:
    Image, *_ = _need_pillow()
    files = image_files(src_dir)
    if not files:
        raise ValueError(f'No supported images found in {src_dir}')
    # Combine thumbnails to avoid huge memory use but preserve representative colors.
    thumbs = []
    for path in files[:2000]:
        img = Image.open(path).convert('RGBA')
        img.thumbnail((128, 128), Image.LANCZOS)
        thumbs.append(img.convert('RGB'))
    width = max(1, min(2048, sum(i.width for i in thumbs)))
    height = max(i.height for i in thumbs) if thumbs else 1
    atlas = Image.new('RGB', (width, height), (0, 0, 0))
    x = 0
    for img in thumbs:
        if x >= width:
            break
        atlas.paste(img, (x, 0))
        x += img.width
    pal_img = atlas.convert('P', palette=Image.Palette.ADAPTIVE if hasattr(Image, 'Palette') else Image.ADAPTIVE, colors=max(1, min(256, int(max_colors))))
    pal = pal_img.getpalette() or []
    colors: List[Tuple[int, int, int]] = []
    for i in range(0, min(len(pal), 256 * 3), 3):
        colors.append((int(pal[i]), int(pal[i + 1]), int(pal[i + 2])))
    while len(colors) < 256:
        colors.append((0, 0, 0))
    out_act = Path(out_act)
    out_act.parent.mkdir(parents=True, exist_ok=True)
    write_act(out_act, colors)
    return out_act


def sound_cue_sheet(folder: Path, out_path: Path) -> Path:
    files = wav_files(folder)
    if not files:
        raise ValueError(f'No WAV files found in {folder}')
    lines = ['# MugenForge Sound Cue Sheet', '', f'Source: `{Path(folder)}`', '', '| File | Group,Sound | Duration | Format |', '|---|---:|---:|---|']
    for idx, path in enumerate(files):
        nums = re.findall(r'-?\d+', path.stem)
        gid = f'{nums[-2]},{nums[-1]}' if len(nums) >= 2 else f'0,{idx}'
        duration = '?'
        fmt = '?'
        try:
            with wave.open(str(path), 'rb') as w:
                duration = f'{w.getnframes() / max(1, w.getframerate()):.2f}s'
                fmt = f'{w.getnchannels()}ch {w.getframerate()}Hz {w.getsampwidth() * 8}bit'
        except Exception as exc:
            fmt = f'unreadable: {exc}'
        lines.append(f'| `{path.name}` | `{gid}` | {duration} | {fmt} |')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out_path


def _first_def(root: Path) -> Optional[Path]:
    root = Path(root)
    exact = root / f'{root.name}.def'
    if exact.exists():
        return exact
    defs = sorted(root.glob('*.def'))
    return defs[0] if defs else None


def project_move_summary(root: Path) -> str:
    root = Path(root)
    lines = [f'# MugenForge Move List: {root.name}', '', f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
    cmd_path = find_character_file(root, 'cmd')
    cns_path = find_character_file(root, 'cns')
    air_path = find_character_file(root, 'air')
    if cmd_path and cmd_path.exists():
        cmd_scan = parse_code(read_text_safely(cmd_path))
        lines += ['## Commands', '']
        if cmd_scan.commands:
            lines += ['| Name | Input | Time | Line |', '|---|---|---:|---:|']
            for c in cmd_scan.commands:
                lines.append(f'| `{c.name}` | `{c.command}` | {c.time if c.time is not None else ""} | {c.line} |')
        else:
            lines.append('- No `[Command]` blocks detected.')
    else:
        lines += ['## Commands', '', '- CMD file not found.']
    lines += ['', '## StateDefs', '']
    state_files = [p for p in [cmd_path, cns_path] if p and p.exists()] + sorted(root.glob('*.st'))
    seen_states = set()
    if state_files:
        lines += ['| State | File | Line | Anim | Type | MoveType | Controllers |', '|---:|---|---:|---:|---|---|---:|']
        for path in state_files:
            scan = parse_code(read_text_safely(path))
            for st in scan.states:
                key = (st.number, path.name, st.line)
                if key in seen_states:
                    continue
                seen_states.add(key)
                lines.append(f'| {st.number} | `{path.name}` | {st.line} | {st.values.get("anim", "")} | {st.values.get("type", "")} | {st.values.get("movetype", "")} | {len(st.controllers)} |')
    else:
        lines.append('- No CNS/CMD/ST files found.')
    lines += ['', '## Animations', '']
    if air_path and air_path.exists():
        actions = parse_air(read_text_safely(air_path))
        if actions:
            lines += ['| Action | Label | Frames | Ticks | Sprite refs |', '|---:|---|---:|---:|---|']
            for a in actions:
                ticks = sum(max(0, f.ticks) for f in a.frames)
                refs = ', '.join(f'{f.group},{f.image}' for f in a.frames[:6])
                if len(a.frames) > 6:
                    refs += ', ...'
                lines.append(f'| {a.number} | {a.label or COMMON_ANIMS.get(a.number, "")} | {len(a.frames)} | {ticks} | `{refs}` |')
        else:
            lines.append('- No AIR actions detected.')
    else:
        lines.append('- AIR file not found.')
    lines += ['', '## Beginner Notes', '', '- Use this move list as the creator-facing index of what your character can do.', '- Use Feature Bank and Move Wizard for changes instead of manually editing CMD/CNS/AIR unless you are comfortable with M.U.G.E.N code.']
    return '\n'.join(lines).rstrip() + '\n'


def export_move_list(root: Path, out_path: Optional[Path] = None) -> Path:
    root = Path(root)
    out_path = Path(out_path) if out_path else root / 'MUGENFORGE_MOVE_LIST.md'
    out_path.write_text(project_move_summary(root), encoding='utf-8')
    return out_path


def write_creator_manual(root: Path) -> Path:
    root = Path(root)
    out = root / 'MUGENFORGE_CREATOR_MANUAL.md'
    text = f'''# MugenForge Creator Manual: {root.name}

This file is a non-coder checklist for building a character without touching raw M.U.G.E.N code unless necessary.

## Main workflow

1. Use **Feature Bank** to install moves/features.
2. Use **Sprite Lab** to clean images, build contact sheets, generate AIR blocks, and build SFF files.
3. Use **Animation Player** to check timing.
4. Use **CLSN Editor** to drag hitboxes around visually.
5. Use **Sounds** to build SND from WAV files.
6. Use **Forge+ Doctor** to find missing files, broken references, and next steps.
7. Use **Package ZIP** when the project is clean.

## What the tool handles for you

- CMD command blocks.
- CNS/ST state templates.
- AIR action blocks.
- Placeholder sprites and sounds.
- SFF/SND starter builds.
- Backups before generated code is appended.
- Project reports and move lists.

## What you still control

- Character idea and style.
- Sprite art.
- Sound choices.
- Move feel, speed, damage, timing, and hitbox polish.
- Balance decisions after testing.
'''
    out.write_text(text.strip() + '\n', encoding='utf-8')
    return out


def full_project_report(root: Path) -> str:
    root = Path(root)
    audit = scan_project(root)
    score = 100
    score -= len(audit.missing_required) * 10
    score -= min(25, len(audit.missing_references) * 3)
    score -= min(25, len(audit.asset_issues) * 5)
    score -= min(20, len(audit.code_issues) * 2)
    score = max(0, score)
    lines = ['MugenForge Forge+ Doctor', '=' * 72, f'Project: {root}', f'Checked: {datetime.now().isoformat(timespec="seconds")}', f'Beginner readiness score: {score}/100', '']
    lines += ['File counts:']
    for ext, count in sorted(audit.found_exts.items()):
        lines.append(f'- {ext or "[none]"}: {count}')
    lines += ['']
    if audit.missing_required:
        lines += ['Missing common files:'] + [f'- {x}' for x in audit.missing_required]
    else:
        lines.append('Common character file set detected: DEF, AIR, CMD, CNS, SFF, SND.')
    def_path = _first_def(root)
    if def_path:
        sections = parse_def(read_text_safely(def_path))
        files = sections.get('files')
        info = sections.get('info')
        lines += ['', f'Main DEF guess: {def_path.name}']
        if info:
            for k in ('name', 'displayname', 'author', 'mugenversion'):
                if k in info.values:
                    lines.append(f'- {k}: {info.values[k]}')
        if files:
            lines += ['DEF [Files] routing:']
            for k, v in files.values.items():
                exists = (def_path.parent / v.strip().strip('"')).exists() if v else False
                lines.append(f'- {k}: {v} {"OK" if exists else "MISSING"}')
    cmd_path = find_character_file(root, 'cmd')
    cns_path = find_character_file(root, 'cns')
    air_path = find_character_file(root, 'air')
    if cmd_path and cmd_path.exists():
        cs = parse_code(read_text_safely(cmd_path))
        lines += ['', f'CMD commands detected: {len(cs.commands)}']
    if cns_path and cns_path.exists():
        scan = parse_code(read_text_safely(cns_path))
        lines += [f'CNS StateDefs detected: {len(scan.states)}']
        hitdefs = sum(1 for c in scan.controllers if c.stype == 'hitdef')
        lines.append(f'CNS HitDefs detected: {hitdefs}')
    if air_path and air_path.exists():
        actions = parse_air(read_text_safely(air_path))
        frames = sum(len(a.frames) for a in actions)
        lines += [f'AIR actions detected: {len(actions)}', f'AIR frames detected: {frames}']
    sffs = sorted(root.glob('*.sff'))
    if sffs:
        try:
            info = read_sff(sffs[0])
            lines += [f'SFF sprite records parsed from {sffs[0].name}: {len(info.sprites)}', f'SFF extraction mode: {"supported" if info.is_supported_for_extraction else "metadata-only"}']
        except Exception as exc:
            lines.append(f'SFF scan failed: {exc}')
    snds = sorted(root.glob('*.snd'))
    if snds:
        try:
            info = read_snd(snds[0])
            lines.append(f'SND sounds parsed from {snds[0].name}: {len(info.sounds)}')
        except Exception as exc:
            lines.append(f'SND scan failed: {exc}')
    if audit.missing_references:
        lines += ['', 'Missing DEF references:'] + [f'- {x}' for x in audit.missing_references[:80]]
    if audit.asset_issues:
        lines += ['', 'AIR/SFF issues:'] + [f'- {x}' for x in audit.asset_issues[:80]]
    if audit.code_issues:
        lines += ['', 'Code issues:'] + [f'- {x}' for x in audit.code_issues[:80]]
    lines += ['', 'Plain-English next step:']
    if audit.missing_required:
        lines.append('- Use Auto Setup / Repair or One-Click Playable Prototype first. The character file set is incomplete.')
    elif audit.asset_issues:
        lines.append('- Rebuild placeholder SFF from AIR references, or update AIR frames to use existing sprite group/image pairs.')
    elif audit.code_issues:
        lines.append('- Use Feature Bank / Code Assistant to replace broken hand-written wiring, then re-run the Doctor.')
    else:
        lines.append('- The structure is usable. Work on sprites, sounds, hitboxes, timing, and playtesting.')
    return '\n'.join(lines).strip() + '\n'


def create_stage_from_image(image_path: Path, out_dir: Path, *, stage_name: Optional[str] = None, zoffset: Optional[int] = None, bound_width: int = 320) -> Path:
    Image, *_ = _need_pillow()
    image_path = Path(image_path)
    out_dir = Path(out_dir)
    stage_name = _safe_stem(stage_name or image_path.stem)
    stage_dir = out_dir / stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(image_path).convert('RGBA')
    bg_name = f'{stage_name}_bg.png'
    bg_path = stage_dir / bg_name
    img.save(bg_path)
    manifest = {
        'tool': 'MugenForge Studio',
        'schema': 'mugenforge.stage_single_bg.v1',
        'sprites': [{
            'index': 0,
            'group': 0,
            'image': 0,
            'axis': {'x': 0, 'y': 0},
            'filename': bg_name,
            'source_rect': {'x': 0, 'y': 0, 'w': img.width, 'h': img.height},
        }],
    }
    manifest_path = stage_dir / 'mugenforge_stage_sff_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    sff_path = stage_dir / f'{stage_name}.sff'
    build_sff_v1_from_manifest(manifest_path, sff_path)
    z = int(zoffset if zoffset is not None else max(180, img.height - 60))
    half_bound = max(160, int(bound_width))
    def_text = f'''[Info]
name = "{stage_name}"
displayname = "{stage_name}"
author = "MugenForge Studio"

[Camera]
startx = 0
starty = 0
boundleft = -{half_bound}
boundright = {half_bound}
boundhigh = -{max(120, img.height // 2)}
boundlow = 0
verticalfollow = .2
floortension = 50

[PlayerInfo]
p1startx = -70
p1starty = 0
p1facing = 1
p2startx = 70
p2starty = 0
p2facing = -1
leftbound = -1000
rightbound = 1000

[Scaling]
topz = 0
botz = 50
topscale = 1
botscale = 1.2

[Bound]
screenleft = 15
screenright = 15

[StageInfo]
zoffset = {z}
autoturn = 1
resetBG = 1

[Shadow]
color = 0,0,0
yscale = .2
reflect = 0

[Music]
bgmusic =
bgvolume = 0

[BGdef]
spr = {stage_name}.sff
debugbg = 0

[BG Background]
type = normal
spriteno = 0,0
start = 0,0
delta = 1,1
mask = 1
'''
    def_path = stage_dir / f'{stage_name}.def'
    def_path.write_text(def_text, encoding='utf-8')
    guide = stage_dir / 'MUGENFORGE_STAGE_README.md'
    guide.write_text(f'''# {stage_name} stage

Generated from `{image_path.name}`.

Files:

- `{stage_name}.def`
- `{stage_name}.sff`
- `{bg_name}` source copy
- `mugenforge_stage_sff_manifest.json`

Tune `zoffset`, camera bounds, deltas, shadows, and music in the DEF file after testing.
''', encoding='utf-8')
    return def_path


def write_mugen_launch_config(root: Path, mugen_exe: Path, extra_args: Optional[Sequence[str]] = None) -> Path:
    root = Path(root)
    data = {
        'tool': 'MugenForge Studio',
        'schema': 'mugenforge.launch_config.v1',
        'mugen_exe': str(Path(mugen_exe)),
        'extra_args': list(extra_args or []),
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }
    out = root / 'mugenforge_launch_config.json'
    out.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return out


def read_mugen_launch_config(root: Path) -> dict:
    path = Path(root) / 'mugenforge_launch_config.json'
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def launch_mugen(root: Path) -> subprocess.Popen:
    root = Path(root)
    cfg = read_mugen_launch_config(root)
    exe = Path(cfg.get('mugen_exe', ''))
    if not exe.exists():
        raise FileNotFoundError('Set a valid M.U.G.E.N executable path first.')
    args = [str(exe)] + [str(x) for x in cfg.get('extra_args', [])]
    return subprocess.Popen(args, cwd=str(exe.parent))
