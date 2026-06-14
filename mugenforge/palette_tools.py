from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable, List, Tuple

Color = Tuple[int, int, int]

@dataclass
class PaletteInfo:
    path: Path
    colors: List[Color]
    warnings: List[str]


def _clamp(v: int) -> int:
    return max(0, min(255, int(v)))


def read_act(path: Path) -> PaletteInfo:
    data = Path(path).read_bytes()
    warnings: List[str] = []
    if len(data) < 768:
        warnings.append(f'ACT file is smaller than 768 bytes: {len(data)} bytes')
    if len(data) > 768:
        warnings.append(f'ACT file has {len(data) - 768} extra trailing bytes; first 256 colors were read.')
    data = data[:768].ljust(768, b'\x00')
    colors = [(data[i], data[i+1], data[i+2]) for i in range(0, 768, 3)]
    return PaletteInfo(path=Path(path), colors=colors, warnings=warnings)


def write_act(path: Path, colors: Iterable[Color]) -> None:
    buf = bytearray()
    color_list = list(colors)[:256]
    while len(color_list) < 256:
        color_list.append((0, 0, 0))
    for r, g, b in color_list:
        buf.extend(bytes((_clamp(r), _clamp(g), _clamp(b))))
    Path(path).write_bytes(bytes(buf))


def palette_to_json_text(info: PaletteInfo) -> str:
    data = {
        'source': str(info.path),
        'count': len(info.colors),
        'colors': [
            {'index': idx, 'r': r, 'g': g, 'b': b, 'hex': f'#{r:02X}{g:02X}{b:02X}'}
            for idx, (r, g, b) in enumerate(info.colors)
        ],
        'warnings': info.warnings,
    }
    return json.dumps(data, indent=2)


def write_palette_json(info: PaletteInfo, out_path: Path) -> None:
    Path(out_path).write_text(palette_to_json_text(info), encoding='utf-8')


def build_act_from_image(image_path: Path, out_path: Path, max_colors: int = 256) -> PaletteInfo:
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required to build ACT palettes from images. Install with: pip install Pillow') from exc
    img = Image.open(image_path).convert('RGBA')
    # Quantize to a palette, then extract RGB triplets.
    pal_img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=max(1, min(256, int(max_colors))))
    pal = pal_img.getpalette() or []
    colors: List[Color] = []
    for i in range(0, min(len(pal), 256 * 3), 3):
        colors.append((pal[i], pal[i+1], pal[i+2]))
    while len(colors) < 256:
        colors.append((0, 0, 0))
    write_act(out_path, colors)
    info = read_act(out_path)
    info.warnings.append(f'Built from image: {image_path.name}')
    return info


def remap_palette_order(colors: List[Color], transparent_index: int = 0) -> List[Color]:
    colors = list(colors[:256])
    if not colors:
        return [(0, 0, 0)] * 256
    idx = max(0, min(255, int(transparent_index)))
    if idx < len(colors):
        color = colors.pop(idx)
        colors.insert(0, color)
    while len(colors) < 256:
        colors.append((0, 0, 0))
    return colors[:256]
