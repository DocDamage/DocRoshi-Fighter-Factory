from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable


@dataclass
class SheetSlice:
    index: int
    group: int
    image: int
    x: int
    y: int
    w: int
    h: int
    axis_x: int
    axis_y: int
    filename: str


def require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageTk  # type: ignore
        return Image, ImageDraw, ImageTk
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError('Pillow is required for sprite-sheet import. Install it with: pip install Pillow') from exc


def compute_grid_slices(
    sheet_path: Path,
    cell_w: int,
    cell_h: int,
    columns: int,
    rows: int,
    margin_x: int = 0,
    margin_y: int = 0,
    spacing_x: int = 0,
    spacing_y: int = 0,
    group: int = 0,
    start_image: int = 0,
    axis_x: int | None = None,
    axis_y: int | None = None,
) -> list[SheetSlice]:
    if cell_w <= 0 or cell_h <= 0:
        raise ValueError('Cell width and height must be greater than zero.')
    if columns <= 0 or rows <= 0:
        raise ValueError('Columns and rows must be greater than zero.')
    if axis_x is None:
        axis_x = cell_w // 2
    if axis_y is None:
        axis_y = cell_h
    slices: list[SheetSlice] = []
    stem = sheet_path.stem
    idx = 0
    for row in range(rows):
        for col in range(columns):
            x = margin_x + col * (cell_w + spacing_x)
            y = margin_y + row * (cell_h + spacing_y)
            img_no = start_image + idx
            filename = f'{stem}_g{group:04d}_i{img_no:04d}.png'
            slices.append(SheetSlice(idx, group, img_no, x, y, cell_w, cell_h, axis_x, axis_y, filename))
            idx += 1
    return slices


def export_grid_slices(sheet_path: Path, slices: Iterable[SheetSlice], out_dir: Path, trim_empty: bool = False) -> list[Path]:
    Image, _, _ = require_pillow()
    out_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(sheet_path).convert('RGBA')
    outputs: list[Path] = []
    for sl in slices:
        crop = image.crop((sl.x, sl.y, sl.x + sl.w, sl.y + sl.h))
        if trim_empty:
            bbox = crop.getbbox()
            if bbox:
                crop = crop.crop(bbox)
        out = out_dir / sl.filename
        crop.save(out)
        outputs.append(out)
    return outputs


def write_manifest(sheet_path: Path, slices: Iterable[SheetSlice], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for sl in slices:
        records.append({
            'index': sl.index,
            'group': sl.group,
            'image': sl.image,
            'source_rect': {'x': sl.x, 'y': sl.y, 'w': sl.w, 'h': sl.h},
            'axis': {'x': sl.axis_x, 'y': sl.axis_y},
            'filename': sl.filename,
        })
    data = {
        'tool': 'MugenForge Studio',
        'mode': 'sprite_sheet_staging',
        'source_sheet': str(sheet_path),
        'note': 'This manifest stages sprites for later SFF packing. It does not modify an SFF file.',
        'sprites': records,
    }
    out_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return out_path


def make_air_action_from_slices(action_number: int, slices: Iterable[SheetSlice], ticks: int = 5) -> str:
    if ticks <= 0:
        ticks = 1
    lines = [f'[Begin Action {action_number}]']
    for sl in slices:
        # AIR syntax: group, image, x, y, ticks, flags
        lines.append(f'{sl.group}, {sl.image}, 0, 0, {ticks}')
    return '\n'.join(lines) + '\n'


def make_preview_image(sheet_path: Path, slices: Iterable[SheetSlice], max_size: tuple[int, int] = (720, 420)):
    Image, ImageDraw, ImageTk = require_pillow()
    img = Image.open(sheet_path).convert('RGBA')
    draw = ImageDraw.Draw(img)
    for sl in slices:
        draw.rectangle((sl.x, sl.y, sl.x + sl.w, sl.y + sl.h), outline=(255, 0, 0, 255), width=2)
        draw.text((sl.x + 2, sl.y + 2), f'{sl.group},{sl.image}', fill=(255, 0, 0, 255))
    img.thumbnail(max_size)
    return ImageTk.PhotoImage(img)
