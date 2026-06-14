from __future__ import annotations

import json
import struct
import zlib
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Sequence

from . import (
    SFF_SIGNATURE,
    SFF2_DECODABLE_FORMATS,
    SFF2_FORMAT_NAMES,
    SFF2_IMAGE_FORMATS,
    Sff2ImageRecord,
    Sff2PaletteRecord,
    Sff2StandardInfo,
    Sff2StandardRecord,
    SffInfo,
    SffSprite,
)
from .rle_lz5 import (
    _mf_decode_ele_lz5,
    _mf_decode_ele_rle5,
    _mf_decode_ele_rle8,
    _mf_encode_ele_lz5_literal,
    _mf_encode_ele_rle5,
    _mf_encode_ele_rle8,
    _mf_strip_size_prefix,
    _unpack_5bit_indices,
    decode_sff2_rle8_indices,
    encode_sff2_rle8_indices,
)


def _safe_u32(data: bytes, off: int) -> Optional[int]:
    try:
        if off < 0 or off + 4 > len(data):
            return None
        return struct.unpack_from('<I', data, off)[0]
    except Exception:
        return None


def _find_all(data: bytes, needle: bytes) -> List[int]:
    hits: List[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx < 0:
            return hits
        hits.append(idx)
        start = idx + 1


def _inspect_sff2_header(data: bytes) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    labels = [
        (16, 'slot_16'), (20, 'slot_20'), (24, 'slot_24'), (28, 'slot_28'),
        (32, 'slot_32'), (36, 'slot_36'), (40, 'slot_40'), (44, 'slot_44'),
        (48, 'slot_48'), (52, 'slot_52'), (56, 'slot_56'), (60, 'slot_60'),
    ]
    slots = {}
    for off, name in labels:
        val = _safe_u32(data, off)
        if val is not None:
            slots[name] = val
    meta['header_slots'] = slots
    plausible_offsets = []
    for name, val in slots.items():
        if 0 < val < len(data):
            sample = data[val:val+16]
            hint = 'png' if sample.startswith(b'\x89PNG') else 'pcx' if sample.startswith(b'\x0A') else 'zlib' if sample[:1] in {b'\x78'} else 'data'
            plausible_offsets.append({'field': name, 'offset': val, 'hint': hint, 'bytes': sample.hex(' ')})
    meta['plausible_offsets'] = plausible_offsets
    meta['png_markers'] = [i for i in _find_all(data, b'\x89PNG')[:20]]
    meta['pcx_markers'] = [i for i in _find_all(data, b'\x0A\x05')[:20]]
    meta['zlib_markers'] = [i for i in _find_all(data, b'\x78\x9c')[:20]] + [i for i in _find_all(data, b'\x78\xda')[:20]]
    return meta


def _safe_i16_v55(data: bytes, off: int) -> int:
    if off < 0 or off + 2 > len(data):
        raise ValueError(f'i16 read outside buffer at 0x{off:X}')
    return struct.unpack_from('<h', data, off)[0]


def _safe_u16_v55(data: bytes, off: int) -> int:
    if off < 0 or off + 2 > len(data):
        raise ValueError(f'u16 read outside buffer at 0x{off:X}')
    return struct.unpack_from('<H', data, off)[0]


def _safe_u32_v55(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ValueError(f'u32 read outside buffer at 0x{off:X}')
    return struct.unpack_from('<I', data, off)[0]


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _mf_i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _mf_try_u32(data: bytes, off: int) -> Optional[int]:
    try:
        if off < 0 or off + 4 > len(data):
            return None
        return struct.unpack_from('<I', data, off)[0]
    except Exception:
        return None


def _mf_parse_sff2_standard(data: bytes) -> Tuple[Dict[str, Any], List[Sff2StandardRecord], List[Sff2PaletteRecord], List[str]]:
    warnings: List[str] = []
    meta: Dict[str, Any] = {
        'parser': 'mugenforge.sff2.standard.v551',
        'format_table': SFF2_FORMAT_NAMES,
        'raw_version_bytes': list(data[12:16]) if len(data) >= 16 else [],
        'layout_note': 'common 28-byte sprite table / 16-byte palette table SFF2 layout',
    }
    records: List[Sff2StandardRecord] = []
    palettes: List[Sff2PaletteRecord] = []
    if len(data) < 68 or data[:12] != SFF_SIGNATURE:
        warnings.append('Not an ElecbyteSpr SFF or too small for common SFF2 header fields.')
        return meta, records, palettes, warnings

    sprite_offset = _mf_try_u32(data, 36) or 0
    sprite_total = _mf_try_u32(data, 40) or 0
    palette_offset = _mf_try_u32(data, 44) or 0
    palette_total = _mf_try_u32(data, 48) or 0
    ldata_offset = _mf_try_u32(data, 52) or 0
    ldata_length = _mf_try_u32(data, 56) or 0
    tdata_offset = _mf_try_u32(data, 60) or 0
    tdata_length = _mf_try_u32(data, 64) or 0
    meta.update({
        'sprite_offset': sprite_offset, 'sprite_total': sprite_total,
        'palette_offset': palette_offset, 'palette_total': palette_total,
        'ldata_offset': ldata_offset, 'ldata_length': ldata_length,
        'tdata_offset': tdata_offset, 'tdata_length': tdata_length,
        'sprite_record_size': 28, 'palette_record_size': 16,
    })

    if not (0 < sprite_offset < len(data) and 0 < sprite_total <= 250000 and sprite_offset + sprite_total * 28 <= len(data)):
        warnings.append('No plausible common SFF2 sprite table was found at header fields 0x24/0x28.')
        return meta, records, palettes, warnings
    if palette_total and not (0 < palette_offset < len(data) and palette_offset + palette_total * 16 <= len(data)):
        warnings.append('SFF2 palette table fields are not plausible; sprite records will be parsed without palette colors.')
        palette_total = 0

    if palette_total and 0 < palette_offset < len(data) and palette_offset + palette_total * 16 <= len(data):
        for idx in range(palette_total):
            off = palette_offset + idx * 16
            try:
                group = _u16(data, off + 0)
                item = _u16(data, off + 2)
                numcols = _u16(data, off + 4)
                link_index = _u16(data, off + 6)
                rel = _u32(data, off + 8)
                length = _u32(data, off + 12)
                abs_off = ldata_offset + rel
                colors: List[Tuple[int, int, int]] = []
                if length and 0 <= abs_off <= len(data) and abs_off + length <= len(data):
                    blob = data[abs_off:abs_off + length]
                    step = 4 if len(blob) >= max(1, int(numcols)) * 4 else 3
                    for pos in range(0, min(len(blob), max(0, int(numcols)) * step), step):
                        if pos + 2 < len(blob):
                            colors.append((blob[pos], blob[pos + 1], blob[pos + 2]))
                pal = Sff2PaletteRecord(
                    index=idx,
                    group=group,
                    item=item,
                    color_count=numcols,
                    link_index=link_index,
                    data_offset=rel,
                    data_length=length,
                    table_offset=off,
                    data_base=ldata_offset,
                )
                pal.colors = colors
                palettes.append(pal)
                if link_index != idx and length == 0:
                    meta.setdefault('linked_palette_records', []).append({'index': idx, 'link_index': link_index})
            except Exception as exc:
                warnings.append(f'Could not parse SFF2 palette record {idx}: {exc}')
                break

    for idx in range(int(sprite_total)):
        off = sprite_offset + idx * 28
        try:
            group = _u16(data, off + 0)
            image = _u16(data, off + 2)
            width = _u16(data, off + 4)
            height = _u16(data, off + 6)
            axis_x = _mf_i16(data, off + 8)
            axis_y = _mf_i16(data, off + 10)
            linked_index = _u16(data, off + 12)
            fmt = data[off + 14]
            depth = data[off + 15]
            rel = _u32(data, off + 16)
            length = _u32(data, off + 20)
            pal_idx = _u16(data, off + 24)
            flags = _u16(data, off + 26)
            base_off = ldata_offset if (flags & 1) == 0 else tdata_offset
            base_name = 'ldata' if (flags & 1) == 0 else 'tdata'
            abs_payload = base_off + rel
            note = ''
            if fmt == 1 or length == 0:
                note = 'linked/no payload'
            elif width <= 0 or height <= 0:
                note = 'zero-sized sprite'
            elif abs_payload < 0 or abs_payload + length > len(data):
                note = 'invalid payload range'
            elif fmt not in SFF2_FORMAT_NAMES:
                note = f'unknown SFF2 format code {fmt}'
            records.append(Sff2StandardRecord(
                index=idx,
                group=group,
                image=image,
                width=width,
                height=height,
                axis_x=axis_x,
                axis_y=axis_y,
                linked_index=linked_index,
                format_code=fmt,
                color_depth=depth,
                data_offset=rel,
                data_length=length,
                palette_index=pal_idx,
                flags=flags,
                table_offset=off,
                payload_offset=abs_payload,
                payload_base=base_name,
                note=note,
            ))
        except Exception as exc:
            warnings.append(f'Could not parse SFF2 sprite record {idx}: {exc}')
            break
    return meta, records, palettes, warnings


def _mf_palette_for_record(info: SffInfo, record: Sff2StandardRecord) -> List[Tuple[int, int, int]]:
    meta = info.v2_metadata or {}
    pal_rows = meta.get('sff2_palettes') or []
    for row in pal_rows:
        try:
            if int(row.get('index', -1)) == int(record.palette_index):
                colors = row.get('colors') or []
                out = []
                for c in colors[:256]:
                    out.append((int(c.get('r', 0)), int(c.get('g', 0)), int(c.get('b', 0))))
                if out:
                    return out
        except Exception:
            continue
    return [(i, i, i) for i in range(256)]


def _mf_png_from_indexed(width: int, height: int, pixels: bytes, palette: List[Tuple[int, int, int]]) -> bytes:
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required to render decoded SFF2 indexed sprites to PNG. Install with: pip install Pillow') from exc
    expected = max(0, int(width) * int(height))
    pixels = bytes(pixels[:expected]).ljust(expected, b'\x00')
    img = Image.frombytes('P', (max(1, int(width)), max(1, int(height))), pixels)
    flat: List[int] = []
    pal = list(palette[:256])
    while len(pal) < 256:
        pal.append((0, 0, 0))
    for r, g, b in pal[:256]:
        flat.extend([max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))])
    img.putpalette(flat)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _mf_standard_record_from_sprite(info: SffInfo, sprite: SffSprite) -> Optional[Sff2StandardRecord]:
    from .sff_v1 import _mf_standard_record_from_sprite as fallback
    return fallback(info, sprite)


def _mf_decode_sff2_record_to_png_bytes(path: Path, info: SffInfo, record: Sff2StandardRecord) -> Tuple[bytes, str]:
    data = Path(path).read_bytes()
    if record.data_length < 0 or record.payload_offset < 0 or record.payload_offset + record.data_length > len(data):
        if record.format_code == 1 and 0 <= record.linked_index < len(info.sprites):
            linked = _mf_standard_record_from_sprite(info, info.sprites[record.linked_index])
            if linked is not None and linked.index != record.index:
                return _mf_decode_sff2_record_to_png_bytes(path, info, linked)
        raise ValueError(f'SFF2 record {record.index} has an invalid payload range.')
    if record.data_length == 0 and 0 <= record.linked_index < len(info.sprites):
        linked = _mf_standard_record_from_sprite(info, info.sprites[record.linked_index])
        if linked is not None and linked.index != record.index:
            return _mf_decode_sff2_record_to_png_bytes(path, info, linked)
    blob = data[record.payload_offset:record.payload_offset + record.data_length]
    candidates = [blob]
    for candidate in (blob, blob[4:] if len(blob) >= 4 else b''):
        try:
            dec = zlib.decompress(candidate)
            if dec:
                candidates.append(dec)
        except Exception:
            pass
    for candidate in candidates:
        if candidate.startswith(b'\x89PNG\r\n\x1a\n'):
            return candidate, 'direct/zlib PNG payload'
        if candidate.startswith(b'\x0A'):
            try:
                from PIL import Image
                img = Image.open(BytesIO(candidate)).convert('RGBA')
                buf = BytesIO()
                img.save(buf, format='PNG')
                return buf.getvalue(), 'direct/zlib PCX payload converted to PNG'
            except Exception:
                return candidate, 'direct/zlib PCX payload raw'
    if record.format_code in {10, 11, 12}:
        try:
            from PIL import Image
            img = Image.open(BytesIO(blob)).convert('RGBA')
            buf = BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue(), SFF2_FORMAT_NAMES.get(record.format_code, 'png')
        except Exception:
            pass
    expected = max(0, int(record.width) * int(record.height))
    payload = _mf_strip_size_prefix(blob, expected) if record.format_code == 0 else blob
    if record.format_code == 0:
        if record.color_depth == 24 and len(payload) >= expected * 3:
            from PIL import Image
            img = Image.frombytes('RGB', (record.width, record.height), payload[:expected * 3]).convert('RGBA')
            buf = BytesIO(); img.save(buf, format='PNG')
            return buf.getvalue(), 'raw24'
        if record.color_depth == 32 and len(payload) >= expected * 4:
            from PIL import Image
            img = Image.frombytes('RGBA', (record.width, record.height), payload[:expected * 4])
            buf = BytesIO(); img.save(buf, format='PNG')
            return buf.getvalue(), 'raw32'
        pixels = payload[:expected]
        if len(pixels) < expected:
            raise ValueError(f'Raw indexed payload has {len(pixels)} bytes; expected {expected}.')
        mode = 'raw8'
    elif record.format_code == 2:
        pixels = _mf_decode_ele_rle8(blob, expected)
        mode = 'rle8'
    elif record.format_code == 3:
        pixels = _mf_decode_ele_rle5(blob, expected)
        mode = 'rle5'
    elif record.format_code == 4:
        pixels = _mf_decode_ele_lz5(blob, expected)
        mode = 'lz5'
    else:
        raise ValueError(f'Unsupported SFF2 format code {record.format_code} for record {record.index}.')
    if len(pixels) < expected:
        raise ValueError(f'Decoder for record {record.index} produced {len(pixels)} bytes, expected {expected}.')
    palette = _mf_palette_for_record(info, record)
    return _mf_png_from_indexed(record.width, record.height, pixels, palette), mode


def _mf_extract_palette_from_image(img) -> List[Tuple[int, int, int]]:
    try:
        pal = img.getpalette()
    except Exception:
        pal = None
    colors: List[Tuple[int, int, int]] = []
    if pal:
        for pos in range(0, min(len(pal), 768), 3):
            colors.append((int(pal[pos]), int(pal[pos + 1]), int(pal[pos + 2])))
    while len(colors) < 256:
        i = len(colors)
        colors.append((i, i, i))
    return colors[:256]


def _mf_quantize_image_to_indices(image_path: Path, max_colors: int = 256) -> Tuple[bytes, int, int, List[Tuple[int, int, int]]]:
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF2 files from source images. Install with: pip install Pillow') from exc
    img = Image.open(image_path)
    if img.mode != 'P':
        img = img.convert('RGBA').convert('P', palette=Image.ADAPTIVE, colors=max(2, min(256, int(max_colors))))
    w, h = img.size
    colors = _mf_extract_palette_from_image(img)
    pixels = img.tobytes()
    return pixels, w, h, colors


def patch_sff2_axis_copy(sff_path: Path, axis_rows: Iterable[Dict[str, Any]], out_path: Path) -> SffInfo:
    from ..sff_codec import read_sff
    sff_path = Path(sff_path)
    data = bytearray(sff_path.read_bytes())
    applied = 0
    for row in axis_rows:
        off = int(row.get('raw_header_offset', row.get('table_offset', -1)))
        rec_type = str(row.get('record_type', '')).lower()
        x = max(-32768, min(32767, int(row.get('new_x', row.get('axis_x', row.get('current_x', 0))))))
        y = max(-32768, min(32767, int(row.get('new_y', row.get('axis_y', row.get('current_y', 0))))))
        if off < 0:
            continue
        if rec_type in {'sff1_subfile', 'sff1'}:
            if off + 12 <= len(data):
                struct.pack_into('<h', data, off + 8, x)
                struct.pack_into('<h', data, off + 10, y)
                applied += 1
        else:
            if off + 12 <= len(data):
                struct.pack_into('<h', data, off + 8, x)
                struct.pack_into('<h', data, off + 10, y)
                applied += 1
    if not applied:
        raise ValueError('No valid axis rows were applied.')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(data))
    return read_sff(out_path)


def parse_sff2_standard(path: Path, max_sprites: int = 250000, *, allow_legacy_subset: bool = False) -> Sff2StandardInfo:
    path = Path(path)
    data = path.read_bytes()
    warnings: List[str] = []
    if len(data) < 68 or data[:12] != SFF_SIGNATURE:
        raise ValueError('Not an ElecbyteSpr file or too small for SFF2 header.')
    ver = data[12:16]
    if ver not in {b'\x00\x00\x00\x02', b'\x00\x01\x00\x02'}:
        if not (allow_legacy_subset and ver == b'\x02\x00\x00\x00'):
            raise ValueError(f'Not a standard SFF2 version byte sequence: {tuple(ver)}')
    spr_offset = _safe_u32_v55(data, 36)
    spr_count = _safe_u32_v55(data, 40)
    pal_offset = _safe_u32_v55(data, 44)
    pal_count = _safe_u32_v55(data, 48)
    ldata_offset = _safe_u32_v55(data, 52)
    ldata_length = _safe_u32_v55(data, 56) if len(data) >= 60 else 0
    tdata_offset = _safe_u32_v55(data, 60) if len(data) >= 64 else 0
    tdata_length = _safe_u32_v55(data, 64) if len(data) >= 68 else 0
    if not (0 < spr_offset < len(data)):
        raise ValueError(f'Sprite table offset is not valid: 0x{spr_offset:X}')
    if not (0 <= spr_count <= max_sprites):
        raise ValueError(f'Sprite count is outside safety range: {spr_count}')
    if spr_offset + spr_count * 28 > len(data):
        raise ValueError('Sprite table extends beyond EOF.')
    if pal_count and not (0 < pal_offset < len(data)):
        warnings.append(f'Palette table offset looks invalid: 0x{pal_offset:X}')
    if pal_count and pal_offset + pal_count * 16 > len(data):
        warnings.append('Palette table extends beyond EOF; palette rows after EOF will be skipped.')
    if not (0 < ldata_offset <= len(data)):
        warnings.append(f'Local data offset looks invalid: 0x{ldata_offset:X}')
    if tdata_offset and not (0 < tdata_offset <= len(data)):
        warnings.append(f'Translated data offset looks invalid: 0x{tdata_offset:X}')

    info = Sff2StandardInfo(
        path=path,
        version_bytes=tuple(ver),
        sprite_table_offset=spr_offset,
        sprite_count=spr_count,
        palette_table_offset=pal_offset,
        palette_count=pal_count,
        local_data_offset=ldata_offset,
        local_data_length=ldata_length,
        translated_data_offset=tdata_offset,
        translated_data_length=tdata_length,
        warnings=warnings,
    )
    for idx in range(min(pal_count, max(0, (len(data) - pal_offset) // 16))):
        off = pal_offset + idx * 16
        try:
            group = _safe_u16_v55(data, off)
            item = _safe_u16_v55(data, off + 2)
            ncol = _safe_u16_v55(data, off + 4)
            link = _safe_u16_v55(data, off + 6)
            rel = _safe_u32_v55(data, off + 8)
            length = _safe_u32_v55(data, off + 12)
            actual = ldata_offset + rel
            if length and (actual < 0 or actual + length > len(data)):
                warnings.append(f'Palette #{idx} payload range outside file: 0x{actual:X}+{length}')
            pal = Sff2PaletteRecord(
                index=idx,
                group=group,
                item=item,
                color_count=ncol,
                link_index=link,
                data_offset=rel,
                data_length=length,
                table_offset=off,
                data_base=ldata_offset,
            )
            colors: List[Tuple[int, int, int]] = []
            if length and 0 <= actual <= len(data) and actual + length <= len(data):
                blob = data[actual:actual + length]
                step = 4 if len(blob) >= max(1, int(ncol)) * 4 else 3
                for pos in range(0, min(len(blob), max(0, int(ncol)) * step), step):
                    if pos + 2 < len(blob):
                        colors.append((blob[pos], blob[pos + 1], blob[pos + 2]))
            pal.colors = colors
            info.palettes.append(pal)
        except Exception as exc:
            warnings.append(f'Palette record #{idx} parse failed: {exc}')
            break
    for idx in range(spr_count):
        off = spr_offset + idx * 28
        try:
            group = _safe_u16_v55(data, off)
            image = _safe_u16_v55(data, off + 2)
            width = _safe_u16_v55(data, off + 4)
            height = _safe_u16_v55(data, off + 6)
            x = _safe_i16_v55(data, off + 8)
            y = _safe_i16_v55(data, off + 10)
            link = _safe_u16_v55(data, off + 12)
            img_format = data[off + 14]
            cdep = data[off + 15]
            rel = _safe_u32_v55(data, off + 16)
            length = _safe_u32_v55(data, off + 20)
            pal_index = _safe_u16_v55(data, off + 24)
            flags = _safe_u16_v55(data, off + 26)
            base = ldata_offset if flags == 0 else (tdata_offset or ldata_offset)
            actual = base + rel
            row_warn: List[str] = []
            if img_format not in SFF2_IMAGE_FORMATS:
                row_warn.append(f'unknown image format code {img_format}')
            if length and (actual < 0 or actual + length > len(data)):
                row_warn.append(f'image payload range outside file: 0x{actual:X}+{length}')
            if pal_count and pal_index >= pal_count:
                row_warn.append(f'palette index {pal_index} outside palette count {pal_count}')
            rec = Sff2ImageRecord(
                index=idx,
                group=group,
                image=image,
                width=width,
                height=height,
                x=x,
                y=y,
                link_index=link,
                image_format=img_format,
                color_depth=cdep,
                data_offset=actual,
                data_length=length,
                palette_index=pal_index,
                flags=flags,
                table_offset=off,
                local_data_base=ldata_offset,
                translated_data_base=tdata_offset or ldata_offset,
                warnings=row_warn,
            )
            info.sprites.append(rec)
        except Exception as exc:
            warnings.append(f'Sprite record #{idx} parse failed: {exc}')
            break
    return info


def _sff2_palette_rgba(data: bytes, info: Sff2StandardInfo, palette_index: int) -> List[Tuple[int, int, int, int]]:
    if not info.palettes:
        return [(0, 0, 0, 0)] + [(i, i, i, 255) for i in range(1, 256)]
    palette_index = max(0, min(int(palette_index), len(info.palettes) - 1))
    pal = info.palettes[palette_index]
    if pal.data_length == 0 and 0 <= pal.link_index < len(info.palettes) and pal.link_index != palette_index:
        return _sff2_palette_rgba(data, info, pal.link_index)
    start = pal.data_offset
    length = min(pal.data_length, max(0, len(data) - start))
    raw = data[start:start + length]
    count = max(1, min(256, pal.color_count or len(raw) // 4 or 256))
    colors: List[Tuple[int, int, int, int]] = []
    alpha_bytes = [raw[i + 3] for i in range(0, min(len(raw), count * 4), 4) if i + 3 < len(raw)]
    all_alpha_zero = bool(alpha_bytes) and all(a == 0 for a in alpha_bytes)
    for idx in range(count):
        off = idx * 4
        if off + 4 <= len(raw):
            r, g, b, a = raw[off], raw[off + 1], raw[off + 2], raw[off + 3]
            if all_alpha_zero:
                a = 0 if idx == 0 else 255
            colors.append((r, g, b, a))
        else:
            colors.append((0, 0, 0, 0 if idx == 0 else 255))
    while len(colors) < 256:
        i = len(colors)
        colors.append((i, i, i, 255))
    return colors[:256]


def decode_sff2_image(path: Path, record: Sff2ImageRecord, *, info: Optional[Sff2StandardInfo] = None):
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required for SFF2 image decode/export. Install with: pip install Pillow') from exc
    path = Path(path)
    data = path.read_bytes()
    info = info or parse_sff2_standard(path)
    if record.is_linked:
        if 0 <= record.link_index < len(info.sprites) and record.link_index != record.index:
            return decode_sff2_image(path, info.sprites[record.link_index], info=info)
        raise ValueError(f'Sprite #{record.index} is linked to invalid index {record.link_index}.')
    payload = data[record.data_offset:record.data_offset + record.data_length]
    if payload[:2] in {b'\x78\x9c', b'\x78\xda', b'\x78\x01'}:
        try:
            maybe = zlib.decompress(payload)
            if maybe.startswith(b'\x89PNG\r\n\x1a\n'):
                payload = maybe
        except Exception:
            pass
    if record.image_format in {10, 11, 12} or payload.startswith(b'\x89PNG\r\n\x1a\n'):
        im = Image.open(BytesIO(payload))
        if record.image_format == 10 and im.mode == 'P':
            colors = _sff2_palette_rgba(data, info, record.palette_index)
            flat = []
            for r, g, b, _a in colors:
                flat.extend([r, g, b])
            im.putpalette(flat[:768])
            return im.convert('RGBA')
        return im.convert('RGBA')
    expected = max(0, int(record.width) * int(record.height))
    if record.image_format == 2:
        indices = decode_sff2_rle8_indices(payload, expected)
    elif record.image_format == 0:
        if record.color_depth == 8:
            indices = payload[:expected].ljust(expected, b'\x00')
        elif record.color_depth == 24:
            need = expected * 3
            raw = payload[:need].ljust(need, b'\x00')
            return Image.frombytes('RGB', (record.width, record.height), raw).convert('RGBA')
        elif record.color_depth == 32:
            need = expected * 4
            raw = payload[:need].ljust(need, b'\x00')
            return Image.frombytes('RGBA', (record.width, record.height), raw)
        elif record.color_depth == 5:
            indices = _unpack_5bit_indices(payload, expected)
        else:
            raise ValueError(f'Raw depth {record.color_depth} is not supported.')
    elif record.image_format == 3:
        indices = _mf_decode_ele_rle5(payload, expected)
    elif record.image_format == 4:
        indices = _mf_decode_ele_lz5(payload, expected)
    else:
        raise ValueError(f'SFF2 format {record.format_name} depth {record.color_depth} is not production-decodable in this build.')

    if len(indices) < expected:
        raise ValueError(f'SFF2 decoder produced {len(indices)} bytes, expected {expected}.')
    colors = _sff2_palette_rgba(data, info, record.palette_index)
    rgba = bytearray()
    for idx in indices[:expected]:
        rgba.extend(colors[int(idx) & 0xFF])
    return Image.frombytes('RGBA', (record.width, record.height), bytes(rgba))


def export_sff2_decoded_images(path: Path, out_dir: Path, *, include_raw_payloads: bool = True) -> List[Path]:
    path = Path(path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = parse_sff2_standard(path)
    outputs: List[Path] = []
    data = path.read_bytes()
    for rec in info.sprites:
        base = f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}'
        try:
            out = out_dir / f'{base}_{rec.format_name}.png'
            decode_sff2_image(path, rec, info=info).save(out)
            outputs.append(out)
        except Exception:
            if include_raw_payloads and rec.data_length:
                raw = out_dir / f'{base}_{rec.format_name}_unsupported.bin'
                raw.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
                outputs.append(raw)
    return outputs


def _image_to_sff2_payload(image_path: Path, strategy: str = 'png') -> Tuple[bytes, int, int, int, int]:
    from PIL import Image
    image_path = Path(image_path)
    strategy = (strategy or 'png').lower().strip()
    im = Image.open(image_path)
    width, height = im.size
    if strategy in {'raw8', 'rle8'}:
        pal = im.convert('P', palette=Image.ADAPTIVE, colors=256)
        indices = pal.tobytes()
        if strategy == 'rle8':
            return encode_sff2_rle8_indices(indices), 2, 8, width, height
        return indices, 0, 8, width, height
    if strategy == 'raw24':
        return im.convert('RGB').tobytes(), 0, 24, width, height
    if strategy == 'raw32':
        return im.convert('RGBA').tobytes(), 0, 32, width, height
    buf = BytesIO()
    rgba = im.convert('RGBA')
    rgba.save(buf, format='PNG')
    return buf.getvalue(), 12, 32, width, height


def _palette_from_image_or_default(image_paths: Sequence[Path]) -> bytes:
    try:
        from PIL import Image
        for p in image_paths:
            try:
                im = Image.open(p)
                if im.mode == 'P' and im.getpalette():
                    pal = im.getpalette()[:768]
                    raw = bytearray()
                    for i in range(256):
                        r = pal[i * 3] if i * 3 < len(pal) else i
                        g = pal[i * 3 + 1] if i * 3 + 1 < len(pal) else i
                        b = pal[i * 3 + 2] if i * 3 + 2 < len(pal) else i
                        a = 0 if i == 0 else 255
                        raw.extend([r, g, b, a])
                    return bytes(raw)
            except Exception:
                continue
    except Exception:
        pass
    raw = bytearray()
    for i in range(256):
        raw.extend([i, i, i, 0 if i == 0 else 255])
    return bytes(raw)


def build_sff2_standard_from_records(records: Sequence[Dict[str, Any]], out_path: Path, *, version_21: bool = True, default_strategy: str = 'png') -> Sff2StandardInfo:
    if not records:
        raise ValueError('No SFF2 records supplied.')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image_paths = []
    normalized: List[Dict[str, Any]] = []
    for idx, rec in enumerate(records):
        img_file = rec.get('image_file') or rec.get('filename') or ''
        if img_file:
            p = Path(str(img_file))
            image_paths.append(p)
        normalized.append(dict(rec, _index=idx))
    palette_payload = _palette_from_image_or_default(image_paths)
    payload_items: List[Tuple[Dict[str, Any], bytes, int, int, int, int]] = []
    base_dir = None
    for rec in normalized:
        img_file = rec.get('image_file') or rec.get('filename') or ''
        if img_file:
            p = Path(str(img_file))
            if not p.is_absolute() and base_dir is not None:
                p = base_dir / p
            payload, fmt, depth, width, height = _image_to_sff2_payload(p, str(rec.get('strategy') or default_strategy))
        else:
            payload = bytes(rec.get('payload') or b'')
            fmt = int(rec.get('image_format', 1 if not payload else 0))
            depth = int(rec.get('color_depth', 0))
            width = int(rec.get('width', 0))
            height = int(rec.get('height', 0))
        payload_items.append((rec, payload, fmt, depth, width, height))
    header_size = 512
    sprite_table_offset = header_size
    sprite_count = len(payload_items)
    palette_table_offset = sprite_table_offset + sprite_count * 28
    palette_count = 1
    ldata_offset = palette_table_offset + palette_count * 16
    ldata = bytearray()
    pal_rel = 0
    ldata.extend(palette_payload)
    sprite_payload_offsets: List[int] = []
    for _rec, payload, _fmt, _depth, _w, _h in payload_items:
        while len(ldata) % 4:
            ldata.append(0)
        sprite_payload_offsets.append(len(ldata))
        ldata.extend(payload)
    tdata_offset = ldata_offset + len(ldata)
    header = bytearray(header_size)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = b'\x00\x01\x00\x02' if version_21 else b'\x00\x00\x00\x02'
    struct.pack_into('<I', header, 16, len({int(r.get('group', 0)) for r, *_ in payload_items}))
    struct.pack_into('<I', header, 20, sprite_count)
    struct.pack_into('<I', header, 24, sprite_table_offset)
    struct.pack_into('<I', header, 28, 28)
    struct.pack_into('<I', header, 36, sprite_table_offset)
    struct.pack_into('<I', header, 40, sprite_count)
    struct.pack_into('<I', header, 44, palette_table_offset)
    struct.pack_into('<I', header, 48, palette_count)
    struct.pack_into('<I', header, 52, ldata_offset)
    struct.pack_into('<I', header, 56, len(ldata))
    struct.pack_into('<I', header, 60, tdata_offset)
    struct.pack_into('<I', header, 64, 0)
    header[80:80 + len(b'MugenForge SFF2 v5.5')] = b'MugenForge SFF2 v5.5'
    pal_table = bytearray(16)
    struct.pack_into('<H', pal_table, 0, 1)
    struct.pack_into('<H', pal_table, 2, 1)
    struct.pack_into('<H', pal_table, 4, 256)
    struct.pack_into('<H', pal_table, 6, 0)
    struct.pack_into('<I', pal_table, 8, pal_rel)
    struct.pack_into('<I', pal_table, 12, len(palette_payload))
    sprite_table = bytearray(sprite_count * 28)
    for idx, (rec, payload, fmt, depth, width, height) in enumerate(payload_items):
        off = idx * 28
        struct.pack_into('<H', sprite_table, off, int(rec.get('group', 0)) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 2, int(rec.get('image', rec.get('number', idx))) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 4, int(width) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 6, int(height) & 0xFFFF)
        struct.pack_into('<h', sprite_table, off + 8, max(-32768, min(32767, int(rec.get('axis_x', rec.get('x', 0))))))
        struct.pack_into('<h', sprite_table, off + 10, max(-32768, min(32767, int(rec.get('axis_y', rec.get('y', 0))))))
        struct.pack_into('<H', sprite_table, off + 12, int(rec.get('link_index', 0)) & 0xFFFF)
        sprite_table[off + 14] = int(fmt) & 0xFF
        sprite_table[off + 15] = int(depth) & 0xFF
        struct.pack_into('<I', sprite_table, off + 16, sprite_payload_offsets[idx])
        struct.pack_into('<I', sprite_table, off + 20, len(payload))
        struct.pack_into('<H', sprite_table, off + 24, int(rec.get('palette_index', 0)) & 0xFFFF)
        struct.pack_into('<H', sprite_table, off + 26, 0)
    out_path.write_bytes(bytes(header) + bytes(sprite_table) + bytes(pal_table) + bytes(ldata))
    return parse_sff2_standard(out_path)


def build_sff2_standard_from_manifest(manifest_path: Path, out_path: Path, *, default_strategy: str = 'png') -> Sff2StandardInfo:
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites') or data.get('records') or []
    if not isinstance(records, list):
        raise ValueError('SFF2 manifest does not contain a sprite records list.')
    base = manifest_path.parent
    norm = []
    for rec in records:
        r = dict(rec)
        fn = r.get('image_file') or r.get('filename')
        if fn:
            p = Path(str(fn))
            if not p.is_absolute():
                p = base / p
            r['image_file'] = str(p)
        axis = r.get('axis') if isinstance(r.get('axis'), dict) else {}
        if axis:
            r.setdefault('axis_x', axis.get('x', 0))
            r.setdefault('axis_y', axis.get('y', 0))
        norm.append(r)
    return build_sff2_standard_from_records(norm, out_path, default_strategy=default_strategy)


def summarize_sff2_standard(path: Path) -> str:
    info = parse_sff2_standard(path)
    lines = [
        f'File: {Path(path).name}',
        f'SFF2 version bytes: {info.version_text}',
        f'Sprite records: {len(info.sprites)}',
        f'Palette records: {len(info.palettes)}',
        f'Sprite table offset: 0x{info.sprite_table_offset:X}',
        f'Palette table offset: 0x{info.palette_table_offset:X}',
        f'Local data offset/length: 0x{info.local_data_offset:X} / {info.local_data_length}',
        f'Translated data offset/length: 0x{info.translated_data_offset:X} / {info.translated_data_length}',
        f'Production-decodable sprites: {info.decodable_count}',
        f'Unsupported compressed sprites: {info.unsupported_count}',
        '',
        'First sprites:',
    ]
    for rec in info.sprites[:80]:
        lines.append(f'  #{rec.index:05d} ({rec.group},{rec.image}) {rec.width}x{rec.height} axis=({rec.x},{rec.y}) fmt={rec.format_name} depth={rec.color_depth} bytes={rec.data_length} data=0x{rec.data_offset:X}')
    if info.warnings:
        lines += ['', 'Warnings:'] + [f'  - {w}' for w in info.warnings]
    return '\n'.join(lines)


def _mf_manifest_records_for_sff2(manifest_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list):
        raise ValueError('SFF2 manifest does not contain a sprites list.')
    return records


def _mf_png_payload_for_source(image_path: Path) -> Tuple[bytes, int, int]:
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF2 PNG payloads. Install with: pip install Pillow') from exc
    img = Image.open(image_path).convert('RGBA')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue(), img.width, img.height


def _mf_encode_sff2_payload_from_source(image_path: Path, compression: str) -> Tuple[int, int, bytes, int, int, List[Tuple[int, int, int]]]:
    comp = str(compression or 'png32').strip().lower()
    if comp in {'png', 'png32', '12'}:
        payload, w, h = _mf_png_payload_for_source(image_path)
        return 12, 32, payload, w, h, []
    max_colors = 32 if comp in {'rle5', 'lz5', '3', '4'} else 256
    pixels, w, h, colors = _mf_quantize_image_to_indices(image_path, max_colors=max_colors)
    if comp in {'none', 'raw', 'raw8', '0'}:
        return 0, 8, bytes(pixels), w, h, colors
    if comp in {'rle8', '2'}:
        return 2, 8, struct.pack('<I', len(pixels)) + _mf_encode_ele_rle8(pixels), w, h, colors
    if comp in {'rle5', '3'}:
        raw5 = bytes((b & 31) for b in pixels)
        return 3, 5, struct.pack('<I', len(raw5)) + _mf_encode_ele_rle5(raw5), w, h, colors
    if comp in {'lz5', '4'}:
        raw5 = bytes((b & 31) for b in pixels)
        return 4, 5, struct.pack('<I', len(raw5)) + _mf_encode_ele_lz5_literal(raw5), w, h, colors
    raise ValueError(f'Unsupported SFF2 build compression: {compression}')


def build_sff_v2_from_manifest(manifest_path: Path, out_path: Path, *, compression: str = 'png32') -> SffInfo:
    from ..sff_codec import read_sff
    manifest_path = Path(manifest_path)
    out_path = Path(out_path)
    records = _mf_manifest_records_for_sff2(manifest_path)
    if not records:
        raise ValueError('SFF2 manifest contains no sprite records.')
    base_dir = manifest_path.parent
    normalized: List[Dict[str, Any]] = []
    ldata = bytearray()
    palette_records: List[Dict[str, Any]] = []
    palette_map: Dict[Tuple[Tuple[int, int, int], ...], int] = {}

    def _ensure_palette(colors: List[Tuple[int, int, int]]) -> int:
        if not colors:
            colors = [(i, i, i) for i in range(256)]
        while len(colors) < 256:
            i = len(colors)
            colors.append((i, i, i))
        key = tuple(colors[:256])
        if key in palette_map:
            return palette_map[key]
        pal_index = len(palette_records)
        palette_map[key] = pal_index
        off = len(ldata)
        for r, g, b in colors[:256]:
            ldata.extend(bytes((max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))), 0)))
        palette_records.append({'index': pal_index, 'group': 1, 'item': pal_index + 1, 'num_colors': 256, 'data_offset': off, 'data_length': 1024})
        return pal_index

    for idx, rec in enumerate(records):
        filename = rec.get('filename') or rec.get('file')
        if not filename:
            raise ValueError(f'Sprite manifest row {idx} is missing filename.')
        src = Path(str(filename))
        if not src.is_absolute():
            src = base_dir / src
        if not src.exists():
            raise FileNotFoundError(f'SFF2 source image not found: {src}')
        row_comp = str(rec.get('compression') or compression or 'png32').strip().lower()
        fmt_code, depth, payload, w, h, colors = _mf_encode_sff2_payload_from_source(src, row_comp)
        pal_index = _ensure_palette(colors) if depth <= 8 else 0
        payload_offset = len(ldata)
        ldata.extend(payload)
        axis = rec.get('axis') if isinstance(rec.get('axis'), dict) else {}
        normalized.append({
            'group': int(rec.get('group', 0)),
            'image': int(rec.get('image', idx)),
            'width': int(rec.get('width') or w),
            'height': int(rec.get('height') or h),
            'axis_x': int(axis.get('x', rec.get('axis_x', w // 2))) if isinstance(axis, dict) else int(rec.get('axis_x', w // 2)),
            'axis_y': int(axis.get('y', rec.get('axis_y', h))) if isinstance(axis, dict) else int(rec.get('axis_y', h)),
            'linked_index': idx,
            'format_code': fmt_code,
            'color_depth': depth,
            'data_offset': payload_offset,
            'data_length': len(payload),
            'palette_index': pal_index,
            'flags': 0,
        })
    header_size = 512
    palette_offset = header_size
    palette_total = len(palette_records)
    sprite_offset = palette_offset + palette_total * 16
    sprite_total = len(normalized)
    ldata_offset = sprite_offset + sprite_total * 28
    ldata_length = len(ldata)
    header = bytearray(header_size)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = bytes([0, 1, 0, 2])
    struct.pack_into('<I', header, 36, sprite_offset)
    struct.pack_into('<I', header, 40, sprite_total)
    struct.pack_into('<I', header, 44, palette_offset if palette_total else 0)
    struct.pack_into('<I', header, 48, palette_total)
    struct.pack_into('<I', header, 52, ldata_offset)
    struct.pack_into('<I', header, 56, ldata_length)
    struct.pack_into('<I', header, 60, 0)
    struct.pack_into('<I', header, 64, 0)
    pal_table = bytearray(palette_total * 16)
    for idx, pal in enumerate(palette_records):
        off = idx * 16
        struct.pack_into('<H', pal_table, off + 0, int(pal['group']) & 0xFFFF)
        struct.pack_into('<H', pal_table, off + 2, int(pal['item']) & 0xFFFF)
        struct.pack_into('<H', pal_table, off + 4, int(pal['num_colors']) & 0xFFFF)
        struct.pack_into('<H', pal_table, off + 6, idx & 0xFFFF)
        struct.pack_into('<I', pal_table, off + 8, int(pal['data_offset']))
        struct.pack_into('<I', pal_table, off + 12, int(pal['data_length']))
    spr_table = bytearray(sprite_total * 28)
    for idx, rec in enumerate(normalized):
        off = idx * 28
        struct.pack_into('<H', spr_table, off + 0, int(rec['group']) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 2, int(rec['image']) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 4, max(0, int(rec['width'])) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 6, max(0, int(rec['height'])) & 0xFFFF)
        struct.pack_into('<h', spr_table, off + 8, max(-32768, min(32767, int(rec['axis_x']))))
        struct.pack_into('<h', spr_table, off + 10, max(-32768, min(32767, int(rec['axis_y']))))
        struct.pack_into('<H', spr_table, off + 12, int(rec['linked_index']) & 0xFFFF)
        spr_table[off + 14] = int(rec['format_code']) & 0xFF
        spr_table[off + 15] = int(rec['color_depth']) & 0xFF
        struct.pack_into('<I', spr_table, off + 16, int(rec['data_offset']))
        struct.pack_into('<I', spr_table, off + 20, int(rec['data_length']))
        struct.pack_into('<H', spr_table, off + 24, int(rec['palette_index']) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 26, int(rec['flags']) & 0xFFFF)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(header) + bytes(pal_table) + bytes(spr_table) + bytes(ldata))
    return read_sff(out_path)


def summarize_sff_detailed(path: Path) -> str:
    from ..sff_codec import read_sff
    info = read_sff(path)
    if info.variant != 'sff2-standard':
        lines = [f'File: {path.name}', f'Size: {path.stat().st_size:,} bytes']
        if info.version == (0, 0, 0, 0) and info.warnings:
            lines.extend(info.warnings)
            return '\n'.join(lines)
        lines += [
            f'Signature: ElecbyteSpr detected',
            f'Raw version bytes: {info.version_text}',
            f'Header group count: {info.group_count}',
            f'Header sprite count: {info.sprite_count}',
            f'First subfile offset: 0x{info.first_subfile_offset:X}',
            f'Subheader size: {info.subheader_size}',
            f'Palette type: {info.palette_type}',
            f'Parsed sprite records: {len(info.sprites)}',
            f'Layout: {info.variant}',
            f'Extraction status: {"PCX/PNG payload export available" if info.is_supported_for_extraction else "metadata only"}',
        ]
        if info.v2_metadata:
            lines += ['', 'SFF v2 / non-v1 metadata:']
            slots = info.v2_metadata.get('header_slots', {})
            for key in sorted(slots):
                val = slots[key]
                lines.append(f'  {key}: {val} (0x{val:X})')
            offsets = info.v2_metadata.get('plausible_offsets', [])
            if offsets:
                lines.append('  Plausible internal offsets:')
                for item in offsets[:20]:
                    lines.append(f"    - {item['field']} -> 0x{item['offset']:X} hint={item['hint']} bytes={item['bytes']}")
            for marker_name in ('png_markers', 'pcx_markers', 'zlib_markers'):
                hits = info.v2_metadata.get(marker_name, [])
                if hits:
                    lines.append(f"  {marker_name}: " + ', '.join(f'0x{x:X}' for x in hits[:20]))
        if info.sprites:
            pcx_count = sum(1 for s in info.sprites if s.format_hint == 'pcx')
            png_count = sum(1 for s in info.sprites if s.format_hint == 'png')
            other_count = len(info.sprites) - pcx_count - png_count
            lines += ['', f'Payload hints: PCX={pcx_count}, PNG={png_count}, unknown={other_count}', '', 'First sprites:']
            for spr in info.sprites[:60]:
                lines.append(f'  #{spr.index:05d} ({spr.group},{spr.image}) axis=({spr.x},{spr.y}) bytes={spr.length} fmt={spr.format_hint} data=0x{spr.data_offset:X}')
        if info.warnings:
            lines += ['', 'Warnings:']
            lines.extend(f'  - {w}' for w in info.warnings)
        return '\n'.join(lines)

    meta = info.v2_metadata.get('sff2_standard', {}) if info.v2_metadata else {}
    records = info.v2_metadata.get('sff2_records', []) if info.v2_metadata else []
    palettes = info.v2_metadata.get('sff2_palettes', []) if info.v2_metadata else []
    lines = [
        f'File: {Path(path).name}',
        f'Size: {Path(path).stat().st_size:,} bytes',
        'Signature: ElecbyteSpr detected',
        f'Raw version bytes: {info.version_text}',
        f'Layout: {info.variant}',
        f'Sprite records: {len(records)}',
        f'Palette records: {len(palettes)}',
        f'Sprite table offset: 0x{int(meta.get("sprite_offset", 0)):X}',
        f'Palette table offset: 0x{int(meta.get("palette_offset", 0)):X}',
        f'LData offset/length: 0x{int(meta.get("ldata_offset", 0)):X} / {int(meta.get("ldata_length", 0)):,}',
        f'TData offset/length: 0x{int(meta.get("tdata_offset", 0)):X} / {int(meta.get("tdata_length", 0)):,}',
        f'Extraction status: {"supported for decodable records" if info.is_supported_for_extraction else "metadata only"}',
        '',
        'Supported decode/write modes in this clean-room build:',
        '- raw indexed payloads',
        '- pair-RLE8 indexed payloads',
        '- pair-RLE5 32-color indexed payloads',
        '- literal/LZSS-style LZ5 streams generated by MugenForge',
        '- direct/zlib PNG or PCX payloads from MugenForge transitional files',
        '',
        'First SFF2 sprites:',
    ]
    for row in records[:80]:
        lines.append(
            f"  #{int(row.get('index', 0)):05d} ({row.get('group')},{row.get('image')}) "
            f"{row.get('width')}x{row.get('height')} axis=({row.get('axis_x')},{row.get('axis_y')}) "
            f"fmt={row.get('format_name')} depth={row.get('color_depth')} pal={row.get('palette_index')} "
            f"bytes={row.get('data_length')} payload=0x{int(row.get('payload_offset', 0)):X}"
        )
    if info.warnings:
        lines += ['', 'Warnings:'] + [f'  - {w}' for w in info.warnings]
    return '\n'.join(lines)
