from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from io import BytesIO
import csv
import json
import math
import struct
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SFF_SIGNATURE = b'ElecbyteSpr\x00'
SFF2_VERSION_BYTES = (0, 0, 0, 2)
SFF21_VERSION_BYTES = (0, 1, 0, 2)
SFF2_SPRITE_RECORD_SIZE = 28
SFF2_PALETTE_RECORD_SIZE = 16
SFF2_HEADER_SIZE = 68

FORMAT_NAMES = {
    0: 'raw',
    1: 'linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png8',
    11: 'png24',
    12: 'png32',
}


class Sff2Error(RuntimeError):
    pass


@dataclass
class Sff2PaletteRecord:
    index: int
    group: int
    item: int
    num_colors: int
    link_index: int
    data_offset: int
    data_length: int
    raw_table_offset: int
    relative_offset: int

    @property
    def is_linked(self) -> bool:
        return self.data_length == 0 and self.link_index != self.index

    def to_dict(self) -> Dict[str, object]:
        return {
            'index': self.index,
            'group': self.group,
            'item': self.item,
            'num_colors': self.num_colors,
            'link_index': self.link_index,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'raw_table_offset': self.raw_table_offset,
            'relative_offset': self.relative_offset,
            'is_linked': self.is_linked,
        }


@dataclass
class Sff2SpriteRecord:
    index: int
    group: int
    image: int
    width: int
    height: int
    axis_x: int
    axis_y: int
    link_index: int
    image_format: int
    color_depth: int
    data_offset: int
    data_length: int
    palette_index: int
    flags: int
    raw_table_offset: int
    relative_offset: int
    data_bank: str = 'ldata'
    notes: List[str] = field(default_factory=list)

    @property
    def key(self) -> Tuple[int, int]:
        return (self.group, self.image)

    @property
    def format_name(self) -> str:
        return FORMAT_NAMES.get(self.image_format, f'unknown_{self.image_format}')

    @property
    def is_linked(self) -> bool:
        return self.data_length == 0 or self.image_format == 1

    @property
    def can_decode_confidently(self) -> bool:
        return self.image_format in {0, 2, 10, 11, 12}

    @property
    def can_try_decode(self) -> bool:
        return self.image_format in {0, 2, 3, 4, 10, 11, 12}

    def to_dict(self) -> Dict[str, object]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.axis_x,
            'axis_y': self.axis_y,
            'link_index': self.link_index,
            'image_format': self.image_format,
            'format_name': self.format_name,
            'color_depth': self.color_depth,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'raw_table_offset': self.raw_table_offset,
            'relative_offset': self.relative_offset,
            'data_bank': self.data_bank,
            'is_linked': self.is_linked,
            'can_decode_confidently': self.can_decode_confidently,
            'can_try_decode': self.can_try_decode,
            'notes': '; '.join(self.notes),
        }


@dataclass
class Sff2Info:
    path: Path
    version: Tuple[int, int, int, int]
    sprite_table_offset: int = 0
    sprite_count: int = 0
    palette_table_offset: int = 0
    palette_count: int = 0
    ldata_offset: int = 0
    ldata_length: int = 0
    tdata_offset: int = 0
    tdata_length: int = 0
    sprites: List[Sff2SpriteRecord] = field(default_factory=list)
    palettes: List[Sff2PaletteRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parser_mode: str = 'standard'

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version)

    @property
    def can_export_any(self) -> bool:
        return any(s.can_try_decode and not s.is_linked for s in self.sprites)

    @property
    def can_export_confidently(self) -> bool:
        return any(s.can_decode_confidently and not s.is_linked for s in self.sprites)

    def to_dict(self) -> Dict[str, object]:
        return {
            'path': str(self.path),
            'version': list(self.version),
            'version_text': self.version_text,
            'sprite_table_offset': self.sprite_table_offset,
            'sprite_count': self.sprite_count,
            'palette_table_offset': self.palette_table_offset,
            'palette_count': self.palette_count,
            'ldata_offset': self.ldata_offset,
            'ldata_length': self.ldata_length,
            'tdata_offset': self.tdata_offset,
            'tdata_length': self.tdata_length,
            'parser_mode': self.parser_mode,
            'sprites': [s.to_dict() for s in self.sprites],
            'palettes': [p.to_dict() for p in self.palettes],
            'warnings': self.warnings,
        }


# ---------------------------------------------------------------------------
# Low-level readers


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _safe_u32(data: bytes, off: int, default: int = 0) -> int:
    try:
        if off < 0 or off + 4 > len(data):
            return default
        return _u32(data, off)
    except Exception:
        return default


def _in_range(off: int, length: int, size: int) -> bool:
    return 0 <= off <= size and 0 <= length <= size - off


def _looks_like_standard_sff2(data: bytes) -> bool:
    if len(data) < SFF2_HEADER_SIZE or data[:12] != SFF_SIGNATURE:
        return False
    version = tuple(data[12:16])
    if version not in {SFF2_VERSION_BYTES, SFF21_VERSION_BYTES} and not (version[3] == 2 or version[0] == 2):
        return False
    spr_off = _safe_u32(data, 36)
    spr_count = _safe_u32(data, 40)
    pal_off = _safe_u32(data, 44)
    pal_count = _safe_u32(data, 48)
    ldata = _safe_u32(data, 52)
    tdata = _safe_u32(data, 60)
    return (
        0 < spr_off < len(data)
        and 0 <= spr_count <= 200000
        and spr_off + spr_count * SFF2_SPRITE_RECORD_SIZE <= len(data)
        and 0 <= pal_count <= 200000
        and (pal_count == 0 or (0 < pal_off < len(data) and pal_off + pal_count * SFF2_PALETTE_RECORD_SIZE <= len(data)))
        and (0 <= ldata <= len(data))
        and (0 <= tdata <= len(data))
    )


# ---------------------------------------------------------------------------
# Standard SFF2 parser


def read_sff2(path: Path, *, strict: bool = False, max_records: int = 200000) -> Sff2Info:
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 16 or data[:12] != SFF_SIGNATURE:
        raise Sff2Error('No ElecbyteSpr signature found.')
    version = tuple(data[12:16])  # type: ignore[assignment]
    if not _looks_like_standard_sff2(data):
        msg = 'File does not match the standard SFF2 table layout used by M.U.G.E.N 1.0/1.1.'
        if strict:
            raise Sff2Error(msg)
        info = Sff2Info(path=path, version=version, parser_mode='unrecognized')
        info.warnings.append(msg)
        return info

    info = Sff2Info(
        path=path,
        version=version,
        sprite_table_offset=_u32(data, 36),
        sprite_count=min(_u32(data, 40), max_records),
        palette_table_offset=_u32(data, 44),
        palette_count=min(_u32(data, 48), max_records),
        ldata_offset=_u32(data, 52),
        ldata_length=_safe_u32(data, 56, 0),
        tdata_offset=_u32(data, 60),
        tdata_length=_safe_u32(data, 64, 0),
        parser_mode='standard-sff2',
    )

    if tuple(version) not in {SFF2_VERSION_BYTES, SFF21_VERSION_BYTES}:
        info.warnings.append(f'Noncanonical SFF2 version bytes {info.version_text}; standard tables still looked parseable.')

    # Palette records: group,item,numcolors,link,relative offset,length. Palette payloads live in ldata.
    if info.palette_count and info.palette_table_offset:
        for idx in range(info.palette_count):
            off = info.palette_table_offset + idx * SFF2_PALETTE_RECORD_SIZE
            if off + SFF2_PALETTE_RECORD_SIZE > len(data):
                info.warnings.append(f'Palette record {idx} overruns EOF.')
                break
            group = _u16(data, off + 0)
            item = _u16(data, off + 2)
            num_colors = _u16(data, off + 4)
            link_index = _u16(data, off + 6)
            rel = _u32(data, off + 8)
            length = _u32(data, off + 12)
            abs_off = info.ldata_offset + rel
            if length and not _in_range(abs_off, length, len(data)):
                info.warnings.append(f'Palette record {idx} payload range is invalid: offset=0x{abs_off:X}, length={length}.')
            info.palettes.append(Sff2PaletteRecord(
                index=idx,
                group=group,
                item=item,
                num_colors=num_colors,
                link_index=link_index,
                data_offset=abs_off,
                data_length=length,
                raw_table_offset=off,
                relative_offset=rel,
            ))

    # Sprite records: 28-byte table, image payloads live in ldata when flags == 0 and tdata otherwise.
    for idx in range(info.sprite_count):
        off = info.sprite_table_offset + idx * SFF2_SPRITE_RECORD_SIZE
        if off + SFF2_SPRITE_RECORD_SIZE > len(data):
            info.warnings.append(f'Sprite record {idx} overruns EOF.')
            break
        group = _u16(data, off + 0)
        image = _u16(data, off + 2)
        width = _u16(data, off + 4)
        height = _u16(data, off + 6)
        axis_x = _i16(data, off + 8)
        axis_y = _i16(data, off + 10)
        link_index = _u16(data, off + 12)
        image_format = data[off + 14]
        color_depth = data[off + 15]
        rel = _u32(data, off + 16)
        length = _u32(data, off + 20)
        palette_index = _u16(data, off + 24)
        flags = _u16(data, off + 26)
        base = info.ldata_offset if flags == 0 else info.tdata_offset
        data_bank = 'ldata' if flags == 0 else 'tdata'
        abs_off = base + rel
        notes: List[str] = []
        if image_format not in FORMAT_NAMES:
            notes.append(f'unknown image format {image_format}')
        if palette_index >= max(1, info.palette_count) and color_depth <= 8 and image_format not in {10, 11, 12}:
            notes.append('palette index exceeds palette table count')
        if length and not _in_range(abs_off, length, len(data)):
            notes.append(f'invalid payload range offset=0x{abs_off:X} length={length}')
        if width <= 0 or height <= 0:
            notes.append('zero width/height')
        if image_format in {3, 4}:
            notes.append('RLE5/LZ5 decoder is experimental and export will be marked provisional')
        rec = Sff2SpriteRecord(
            index=idx,
            group=group,
            image=image,
            width=width,
            height=height,
            axis_x=axis_x,
            axis_y=axis_y,
            link_index=link_index,
            image_format=image_format,
            color_depth=color_depth,
            data_offset=abs_off,
            data_length=length,
            palette_index=palette_index,
            flags=flags,
            raw_table_offset=off,
            relative_offset=rel,
            data_bank=data_bank,
            notes=notes,
        )
        if notes:
            info.warnings.extend(f'Sprite {idx}: {n}' for n in notes)
        info.sprites.append(rec)
    return info


# ---------------------------------------------------------------------------
# Palette helpers


def _palette_payload(info: Sff2Info, palette_index: int, data: bytes, _seen: Optional[set[int]] = None) -> bytes:
    if not info.palettes:
        return b''
    palette_index = max(0, min(int(palette_index), len(info.palettes) - 1))
    _seen = _seen or set()
    if palette_index in _seen:
        return b''
    _seen.add(palette_index)
    rec = info.palettes[palette_index]
    if rec.is_linked and 0 <= rec.link_index < len(info.palettes):
        return _palette_payload(info, rec.link_index, data, _seen)
    if rec.data_length <= 0 or rec.data_offset + rec.data_length > len(data):
        return b''
    return data[rec.data_offset:rec.data_offset + rec.data_length]


def palette_rgba(info: Sff2Info, palette_index: int, data: Optional[bytes] = None, *, mode: str = 'rgba') -> List[Tuple[int, int, int, int]]:
    """Return a 256-entry palette as RGBA tuples.

    SFF2 palette byte order seen in the wild can be tool-dependent. `mode='rgba'`
    is the default used by MugenForge's own builder; callers may choose 'bgra' or
    'argb' for diagnostic re-export if a legacy file looks color-swapped.
    """
    if data is None:
        data = info.path.read_bytes()
    raw = _palette_payload(info, palette_index, data)
    colors: List[Tuple[int, int, int, int]] = []
    for i in range(0, min(len(raw), 256 * 4), 4):
        chunk = raw[i:i + 4]
        if len(chunk) < 4:
            break
        a, b, c, d = chunk
        if mode == 'bgra':
            colors.append((c, b, a, d))
        elif mode == 'argb':
            colors.append((b, c, d, a))
        elif mode == 'abgr':
            colors.append((d, c, b, a))
        else:  # rgba
            colors.append((a, b, c, d))
    while len(colors) < 256:
        idx = len(colors)
        colors.append((idx, idx, idx, 0 if idx == 0 else 255))
    return colors[:256]


def _indices_to_rgba_image(indices: bytes, width: int, height: int, palette: Sequence[Tuple[int, int, int, int]]):
    from PIL import Image  # type: ignore
    expected = width * height
    raw = bytes(indices[:expected]).ljust(expected, b'\x00')
    rgba = bytearray()
    for b in raw:
        rgba.extend(palette[b & 0xFF])
    return Image.frombytes('RGBA', (width, height), bytes(rgba))


# ---------------------------------------------------------------------------
# Decoders


def decode_rle8_indices(payload: bytes, width: int, height: int) -> bytes:
    if len(payload) < 4:
        raise Sff2Error('RLE8 payload is shorter than the 4-byte uncompressed-size prefix.')
    expected = width * height
    raw_size = _u32(payload, 0)
    if raw_size != expected:
        raise Sff2Error(f'RLE8 uncompressed byte count {raw_size} does not match width*height {expected}.')
    out = bytearray()
    pending_run: Optional[int] = None
    for value in payload[4:]:
        if pending_run is None and (value & 0xC0) == 0x40:
            pending_run = value - 0x40
            continue
        run = pending_run if pending_run is not None else 1
        if run < 0:
            raise Sff2Error('RLE8 negative run length encountered.')
        out.extend([value] * run)
        pending_run = None
        if len(out) >= expected:
            break
    if len(out) != expected:
        raise Sff2Error(f'RLE8 decoded {len(out)} bytes; expected {expected}.')
    return bytes(out)


def encode_rle8_indices(indices: bytes) -> bytes:
    """Encode 8-bit indices using the simple SFF2 RLE8 token grammar."""
    out = bytearray()
    out.extend(struct.pack('<I', len(indices)))
    i = 0
    n = len(indices)
    while i < n:
        value = indices[i]
        j = i + 1
        while j < n and indices[j] == value and j - i < 63:
            j += 1
        run = j - i
        # Values 0x40..0x7f must be escaped even for a single occurrence because they are run tokens.
        if run > 1 or (value & 0xC0) == 0x40:
            out.append(0x40 + run)
            out.append(value)
        else:
            out.append(value)
        i = j
    return bytes(out)


def _try_decode_rle5_indices(payload: bytes, width: int, height: int) -> Tuple[bytes, str]:
    """Experimental RLE5 decoder.

    Public documentation confirms the RLE5 format exists, but the byte grammar is
    poorly documented. This function uses guarded heuristics and only returns if the
    decoded size exactly matches width*height. It is useful for test/corpus work and
    is clearly marked provisional by callers.
    """
    expected = width * height
    if len(payload) >= 4:
        raw_size = _u32(payload, 0)
        body = payload[4:]
        if raw_size in {expected, math.ceil(expected * 5 / 8), expected * 5}:
            # Heuristic 1: same RLE grammar as RLE8, but color bytes are 0..31 palette entries.
            try:
                raw = decode_rle8_indices(payload, width, height)
                return bytes(b & 0x1F for b in raw), 'rle5-rle8-compatible-heuristic'
            except Exception:
                pass
            # Heuristic 2: packed 5-bit little-endian indices after the size prefix.
            unpacked = _unpack_5bit_indices(body, expected)
            if len(unpacked) == expected:
                return unpacked, 'rle5-packed5-heuristic'
    # Heuristic 3: no prefix packed 5-bit.
    unpacked = _unpack_5bit_indices(payload, expected)
    if len(unpacked) == expected:
        return unpacked, 'rle5-packed5-no-prefix-heuristic'
    raise Sff2Error('RLE5 decode did not match the expected pixel count with available safe heuristics.')


def _unpack_5bit_indices(data: bytes, expected: int) -> bytes:
    out = bytearray()
    bitbuf = 0
    bitcount = 0
    for b in data:
        bitbuf |= b << bitcount
        bitcount += 8
        while bitcount >= 5 and len(out) < expected:
            out.append(bitbuf & 0x1F)
            bitbuf >>= 5
            bitcount -= 5
        if len(out) >= expected:
            break
    return bytes(out) if len(out) == expected else b''


def _try_decode_lz5_indices(payload: bytes, width: int, height: int) -> Tuple[bytes, str]:
    """Experimental LZ5 probe decoder.

    The full LZ5 grammar is not standardized in public Elecbyte docs. This function
    handles a few safe corpus-development cases: uncompressed fallback blocks and
    zlib-wrapped streams sometimes produced by conversion tools. It refuses anything
    that does not exactly produce width*height indices.
    """
    import zlib
    expected = width * height
    body = payload
    if len(payload) >= 4:
        raw_size = _u32(payload, 0)
        if raw_size == expected:
            body = payload[4:]
            if len(body) == expected:
                return body, 'lz5-uncompressed-body-heuristic'
            try:
                raw = zlib.decompress(body)
                if len(raw) == expected:
                    return raw, 'lz5-zlib-wrapped-heuristic'
            except Exception:
                pass
    if len(payload) == expected:
        return payload, 'lz5-raw-no-prefix-heuristic'
    try:
        raw = zlib.decompress(payload)
        if len(raw) == expected:
            return raw, 'lz5-zlib-no-prefix-heuristic'
    except Exception:
        pass
    raise Sff2Error('LZ5 decode did not match the expected pixel count with available safe heuristics.')


def decode_sprite_image(info: Sff2Info, sprite: Sff2SpriteRecord, *, palette_mode: str = 'rgba', _seen: Optional[set[int]] = None):
    from PIL import Image  # type: ignore
    data = info.path.read_bytes()
    _seen = _seen or set()
    if sprite.index in _seen:
        raise Sff2Error(f'Linked sprite loop detected at index {sprite.index}.')
    _seen.add(sprite.index)
    if sprite.is_linked:
        if 0 <= sprite.link_index < len(info.sprites):
            return decode_sprite_image(info, info.sprites[sprite.link_index], palette_mode=palette_mode, _seen=_seen)
        raise Sff2Error(f'Sprite {sprite.index} is linked but link index {sprite.link_index} is invalid.')
    if sprite.data_length <= 0 or sprite.data_offset + sprite.data_length > len(data):
        raise Sff2Error(f'Sprite {sprite.index} has invalid payload range.')
    payload = data[sprite.data_offset:sprite.data_offset + sprite.data_length]
    fmt = sprite.image_format
    if fmt in {10, 11, 12} or payload.startswith(b'\x89PNG\r\n\x1a\n'):
        return Image.open(BytesIO(payload)).convert('RGBA')
    pal = palette_rgba(info, sprite.palette_index, data, mode=palette_mode)
    expected = sprite.width * sprite.height
    if fmt == 0:
        if sprite.color_depth <= 8:
            return _indices_to_rgba_image(payload[:expected], sprite.width, sprite.height, pal)
        if sprite.color_depth == 24:
            raw = payload[:expected * 3].ljust(expected * 3, b'\x00')
            rgba = bytearray()
            for i in range(0, len(raw), 3):
                rgba.extend([raw[i], raw[i + 1], raw[i + 2], 255])
            return Image.frombytes('RGBA', (sprite.width, sprite.height), bytes(rgba))
        if sprite.color_depth == 32:
            raw = payload[:expected * 4].ljust(expected * 4, b'\x00')
            return Image.frombytes('RGBA', (sprite.width, sprite.height), raw)
        raise Sff2Error(f'Raw sprite {sprite.index} has unsupported color depth {sprite.color_depth}.')
    if fmt == 2:
        return _indices_to_rgba_image(decode_rle8_indices(payload, sprite.width, sprite.height), sprite.width, sprite.height, pal)
    if fmt == 3:
        indices, _mode = _try_decode_rle5_indices(payload, sprite.width, sprite.height)
        # Reduced 32-color palettes usually correspond to the first 32 effective colors.
        return _indices_to_rgba_image(indices, sprite.width, sprite.height, pal)
    if fmt == 4:
        indices, _mode = _try_decode_lz5_indices(payload, sprite.width, sprite.height)
        return _indices_to_rgba_image(indices, sprite.width, sprite.height, pal)
    raise Sff2Error(f'Sprite {sprite.index} image format {fmt} is not supported for image export.')


def export_sff2_sprites(path: Path, out_dir: Path, *, palette_mode: str = 'rgba', include_provisional: bool = True, max_count: Optional[int] = None) -> Tuple[List[Path], List[str]]:
    info = read_sff2(path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    warnings: List[str] = list(info.warnings)
    records = info.sprites[:max_count or len(info.sprites)]
    for spr in records:
        if spr.is_linked:
            continue
        if spr.image_format in {3, 4} and not include_provisional:
            warnings.append(f'Skipped sprite {spr.index} ({spr.group},{spr.image}) because {spr.format_name} export is provisional.')
            continue
        try:
            img = decode_sprite_image(info, spr, palette_mode=palette_mode)
        except Exception as exc:
            warnings.append(f'Could not decode sprite {spr.index} ({spr.group},{spr.image}) fmt={spr.format_name}: {exc}')
            continue
        suffix = '_provisional' if spr.image_format in {3, 4} else ''
        out = out_dir / f'g{spr.group:04d}_i{spr.image:04d}_idx{spr.index:05d}_{spr.format_name}{suffix}.png'
        img.save(out)
        outputs.append(out)
    return outputs, warnings


# ---------------------------------------------------------------------------
# Axis patch and builders


def write_sff2_axis_sheet(path: Path, out_csv: Path) -> Path:
    info = read_sff2(path)
    rows = []
    for spr in info.sprites:
        rows.append({
            'enabled': 'no',
            'index': spr.index,
            'group': spr.group,
            'image': spr.image,
            'current_x': spr.axis_x,
            'current_y': spr.axis_y,
            'new_x': spr.axis_x,
            'new_y': spr.axis_y,
            'format': spr.format_name,
            'color_depth': spr.color_depth,
            'table_offset': spr.raw_table_offset,
            'note': 'Set enabled=yes and edit new_x/new_y. Apply writes a patched copy, never the original.',
        })
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        fields = ['enabled','index','group','image','current_x','current_y','new_x','new_y','format','color_depth','table_offset','note']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return out_csv


def patch_sff2_axis_copy(path: Path, sheet_csv: Path, out_path: Path) -> Tuple[Path, int, List[str]]:
    path = Path(path)
    info = read_sff2(path)
    data = bytearray(path.read_bytes())
    warnings: List[str] = list(info.warnings)
    changed = 0
    by_index = {s.index: s for s in info.sprites}
    with Path(sheet_csv).open('r', encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            if str(row.get('enabled', '')).strip().lower() not in {'yes', 'y', '1', 'true'}:
                continue
            try:
                idx = int(str(row.get('index', '')).strip())
                x = int(float(str(row.get('new_x', '')).strip()))
                y = int(float(str(row.get('new_y', '')).strip()))
            except Exception as exc:
                warnings.append(f'Skipped invalid axis row {row}: {exc}')
                continue
            spr = by_index.get(idx)
            if not spr:
                warnings.append(f'Skipped axis row for missing sprite index {idx}.')
                continue
            if spr.raw_table_offset + 12 > len(data):
                warnings.append(f'Sprite {idx} table offset is invalid; skipped.')
                continue
            struct.pack_into('<h', data, spr.raw_table_offset + 8, max(-32768, min(32767, x)))
            struct.pack_into('<h', data, spr.raw_table_offset + 10, max(-32768, min(32767, y)))
            changed += 1
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(data))
    return out_path, changed, warnings


def _image_to_payload(path: Path, *, mode: str = 'png') -> Tuple[bytes, int, int, int, int, bytes]:
    """Return payload, width, height, format code, color depth, palette bytes."""
    from PIL import Image  # type: ignore
    with Image.open(path) as im:
        if mode == 'raw8':
            pim = im.convert('P', palette=Image.ADAPTIVE, colors=256)
            w, h = pim.size
            raw = pim.tobytes()
            pal_flat = (pim.getpalette() or [])[:256 * 3]
            colors = []
            for i in range(0, len(pal_flat), 3):
                r = pal_flat[i]
                g = pal_flat[i + 1] if i + 1 < len(pal_flat) else 0
                b = pal_flat[i + 2] if i + 2 < len(pal_flat) else 0
                colors.append((r, g, b, 0 if len(colors) == 0 else 255))
            while len(colors) < 256:
                idx = len(colors)
                colors.append((idx, idx, idx, 0 if idx == 0 else 255))
            pal = b''.join(bytes(c) for c in colors)
            return raw, w, h, 0, 8, pal
        if mode == 'rle8':
            pim = im.convert('P', palette=Image.ADAPTIVE, colors=256)
            w, h = pim.size
            raw = pim.tobytes()
            payload = encode_rle8_indices(raw)
            pal_flat = (pim.getpalette() or [])[:256 * 3]
            colors = []
            for i in range(0, len(pal_flat), 3):
                r = pal_flat[i]
                g = pal_flat[i + 1] if i + 1 < len(pal_flat) else 0
                b = pal_flat[i + 2] if i + 2 < len(pal_flat) else 0
                colors.append((r, g, b, 0 if len(colors) == 0 else 255))
            while len(colors) < 256:
                idx = len(colors)
                colors.append((idx, idx, idx, 0 if idx == 0 else 255))
            pal = b''.join(bytes(c) for c in colors)
            return payload, w, h, 2, 8, pal
        rgba = im.convert('RGBA')
        buf = BytesIO()
        rgba.save(buf, format='PNG')
        return buf.getvalue(), rgba.width, rgba.height, 12, 32, b''


def build_sff2_from_manifest(manifest_path: Path, out_path: Path, *, payload_mode: str = 'png') -> Sff2Info:
    """Build a standard-table SFF2 file from a MugenForge manifest.

    The output uses the standard SFF2 header/table offsets observed in Elecbyte-compatible
    readers. It supports PNG32, raw8, and RLE8 payloads. This is still a new writer and
    should be engine-tested, but it is no longer the earlier private PNG-subset layout.
    """
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list) or not records:
        raise ValueError('Manifest does not contain a non-empty sprites list.')
    base = manifest_path.parent
    normalized: List[Dict[str, object]] = []
    palette_blobs: List[bytes] = []
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        filename = str(rec.get('filename', '') or rec.get('file', ''))
        if not filename:
            raise ValueError(f'Sprite record {idx} is missing filename.')
        img_path = Path(filename)
        if not img_path.is_absolute():
            img_path = base / filename
        if not img_path.exists():
            raise FileNotFoundError(f'Sprite image not found: {img_path}')
        mode = str(rec.get('payload_mode', payload_mode)).strip().lower() or payload_mode
        payload, w, h, fmt, depth, pal = _image_to_payload(img_path, mode=mode)
        axis = rec.get('axis') if isinstance(rec.get('axis'), dict) else {}
        if pal:
            palette_index = len(palette_blobs)
            palette_blobs.append(pal)
        else:
            palette_index = 0
        normalized.append({
            'group': int(rec.get('group', 0)),
            'image': int(rec.get('image', rec.get('item', idx))),
            'axis_x': int(axis.get('x', rec.get('axis_x', w // 2)) if isinstance(axis, dict) else rec.get('axis_x', w // 2)),
            'axis_y': int(axis.get('y', rec.get('axis_y', h)) if isinstance(axis, dict) else rec.get('axis_y', h)),
            'width': int(rec.get('width', w) or w),
            'height': int(rec.get('height', h) or h),
            'format': fmt,
            'depth': depth,
            'palette_index': palette_index,
            'payload': payload,
            'source': str(img_path),
        })
    if not normalized:
        raise ValueError('No usable sprite records were found in the manifest.') 

    # Use a single fallback grayscale palette if PNG-only sources did not require one.
    if not palette_blobs:
        palette_blobs.append(b''.join(bytes((i, i, i, 0 if i == 0 else 255)) for i in range(256)))

    header_size = SFF2_HEADER_SIZE
    sprite_table_offset = header_size
    sprite_table_size = len(normalized) * SFF2_SPRITE_RECORD_SIZE
    palette_table_offset = sprite_table_offset + sprite_table_size
    palette_table_size = len(palette_blobs) * SFF2_PALETTE_RECORD_SIZE
    ldata_offset = palette_table_offset + palette_table_size

    # Palette payloads first, then image payloads. All use ldata so flags=0.
    ldata = bytearray()
    palette_rels: List[Tuple[int, int]] = []
    for pal in palette_blobs:
        palette_rels.append((len(ldata), len(pal)))
        ldata.extend(pal)
    sprite_rels: List[Tuple[int, int]] = []
    for rec in normalized:
        payload = rec['payload']  # type: ignore[assignment]
        sprite_rels.append((len(ldata), len(payload)))
        ldata.extend(payload)  # type: ignore[arg-type]
    tdata_offset = ldata_offset + len(ldata)
    tdata_length = 0

    header = bytearray(header_size)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = bytes(SFF2_VERSION_BYTES)
    # Leave legacy/reserved slots 16..35 as zero.
    struct.pack_into('<I', header, 36, sprite_table_offset)
    struct.pack_into('<I', header, 40, len(normalized))
    struct.pack_into('<I', header, 44, palette_table_offset)
    struct.pack_into('<I', header, 48, len(palette_blobs))
    struct.pack_into('<I', header, 52, ldata_offset)
    struct.pack_into('<I', header, 56, len(ldata))
    struct.pack_into('<I', header, 60, tdata_offset)
    struct.pack_into('<I', header, 64, tdata_length)

    sprite_table = bytearray(sprite_table_size)
    for idx, rec in enumerate(normalized):
        off = idx * SFF2_SPRITE_RECORD_SIZE
        rel, plen = sprite_rels[idx]
        struct.pack_into('<H', sprite_table, off + 0, int(rec['group']) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 2, int(rec['image']) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 4, int(rec['width']) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 6, int(rec['height']) & 0xFFFF)
        struct.pack_into('<h', sprite_table, off + 8, max(-32768, min(32767, int(rec['axis_x']))))
        struct.pack_into('<h', sprite_table, off + 10, max(-32768, min(32767, int(rec['axis_y']))))
        struct.pack_into('<H', sprite_table, off + 12, idx & 0xFFFF)
        sprite_table[off + 14] = int(rec['format']) & 0xFF
        sprite_table[off + 15] = int(rec['depth']) & 0xFF
        struct.pack_into('<I', sprite_table, off + 16, rel)
        struct.pack_into('<I', sprite_table, off + 20, plen)
        struct.pack_into('<H', sprite_table, off + 24, int(rec['palette_index']) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 26, 0)

    palette_table = bytearray(palette_table_size)
    for idx, pal in enumerate(palette_blobs):
        off = idx * SFF2_PALETTE_RECORD_SIZE
        rel, plen = palette_rels[idx]
        struct.pack_into('<H', palette_table, off + 0, 1)
        struct.pack_into('<H', palette_table, off + 2, idx + 1)
        struct.pack_into('<H', palette_table, off + 4, min(256, max(1, plen // 4)))
        struct.pack_into('<H', palette_table, off + 6, idx & 0xFFFF)
        struct.pack_into('<I', palette_table, off + 8, rel)
        struct.pack_into('<I', palette_table, off + 12, plen)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(header) + bytes(sprite_table) + bytes(palette_table) + bytes(ldata))
    return read_sff2(out_path, strict=True)


# ---------------------------------------------------------------------------
# Reports and artifacts


def write_sff2_report(path: Path, out_dir: Path) -> Dict[str, Path]:
    info = read_sff2(path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / 'sff2_standard_inspection.json'
    json_path.write_text(json.dumps(info.to_dict(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    sprite_csv = out_dir / 'sff2_sprite_table.csv'
    fields = ['index','group','image','width','height','axis_x','axis_y','link_index','image_format','format_name','color_depth','data_offset','data_length','palette_index','flags','raw_table_offset','relative_offset','data_bank','is_linked','can_decode_confidently','can_try_decode','notes']
    with sprite_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for spr in info.sprites:
            w.writerow(spr.to_dict())
    pal_csv = out_dir / 'sff2_palette_table.csv'
    pfields = ['index','group','item','num_colors','link_index','data_offset','data_length','raw_table_offset','relative_offset','is_linked']
    with pal_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=pfields)
        w.writeheader()
        for pal in info.palettes:
            w.writerow(pal.to_dict())
    md = out_dir / 'SFF2_STANDARD_INSPECTION.md'
    counts: Dict[str, int] = {}
    for spr in info.sprites:
        counts[spr.format_name] = counts.get(spr.format_name, 0) + 1
    lines = [
        '# SFF2 Standard Inspection',
        '',
        f'File: `{Path(path).name}`',
        f'Version bytes: `{info.version_text}`',
        f'Parser mode: `{info.parser_mode}`',
        f'Sprite records: {len(info.sprites)}',
        f'Palette records: {len(info.palettes)}',
        f'Sprite table offset: 0x{info.sprite_table_offset:X}',
        f'Palette table offset: 0x{info.palette_table_offset:X}',
        f'LData offset/length: 0x{info.ldata_offset:X} / {info.ldata_length}',
        f'TData offset/length: 0x{info.tdata_offset:X} / {info.tdata_length}',
        '',
        '## Format counts',
    ]
    if counts:
        lines.extend(f'- {k}: {v}' for k, v in sorted(counts.items()))
    else:
        lines.append('- none')
    lines += [
        '',
        '## Decode status',
        f'- Confident export path available: {"yes" if info.can_export_confidently else "no"}',
        f'- Provisional decoder path available: {"yes" if info.can_export_any else "no"}',
        '- PNG, RAW8/24/32, and RLE8 are direct native paths.',
        '- RLE5/LZ5 are attempted only through guarded provisional heuristics and are marked as provisional in exported filenames/reports.',
    ]
    if info.warnings:
        lines += ['', '## Warnings'] + [f'- {w}' for w in info.warnings]
    md.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    return {'json': json_path, 'sprites_csv': sprite_csv, 'palettes_csv': pal_csv, 'markdown': md}


# Compatibility wrapper for v7 authority/corpus tools.
def export_sff2_decoded_images(path, out_dir, *, include_raw_payloads=True):
    from .sff_codec import export_sff2_decoded_images as _export
    return _export(path, out_dir, include_raw_payloads=include_raw_payloads)
