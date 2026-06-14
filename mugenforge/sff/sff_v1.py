from __future__ import annotations

import json
import struct
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Sequence

from . import (
    SFF_SIGNATURE,
    Sff2StandardRecord,
    SffInfo,
    SffSprite,
)


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


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


def _read_sff_v1_reader(path: Path, max_sprites: int = 20000) -> SffInfo:
    data = path.read_bytes()
    if len(data) < 32:
        return SffInfo(path=path, version=(0, 0, 0, 0), warnings=['File is too small to be a normal SFF file.'])
    if data[:12] != SFF_SIGNATURE:
        return SffInfo(path=path, version=(0, 0, 0, 0), warnings=['No ElecbyteSpr signature found.'])

    version = tuple(data[12:16])
    info = SffInfo(
        path=path,
        version=version,
        group_count=_u32(data, 16) if len(data) >= 20 else 0,
        sprite_count=_u32(data, 20) if len(data) >= 24 else 0,
        first_subfile_offset=_u32(data, 24) if len(data) >= 28 else 0,
        subheader_size=_u32(data, 28) if len(data) >= 32 else 0,
        palette_type=_u32(data, 32) if len(data) >= 36 else 0,
    )

    if info.version[0] >= 2 or info.version[3] == 2 or info.subheader_size not in (0, 32):
        info.v2_metadata = _inspect_sff2_header(data)
        try:
            from .sff_v2 import read_sff2
            s2 = read_sff2(path)
            if s2.sprites:
                info.variant = 'sff2-standard-table'
                info.sprite_count = len(s2.sprites)
                info.group_count = len({s.group for s in s2.sprites})
                info.subheader_size = 28
                info.first_subfile_offset = s2.sprite_table_offset
                info.palette_type = len(s2.palettes)
                fmt_map = {'png8': 'png', 'png24': 'png', 'png32': 'png', 'raw': 'raw', 'rle8': 'rle8', 'rle5': 'rle5', 'lz5': 'lz5', 'linked': 'linked'}
                for spr in s2.sprites:
                    info.sprites.append(SffSprite(
                        index=spr.index, group=spr.group, image=spr.image, x=spr.axis_x, y=spr.axis_y,
                        length=spr.data_length, data_offset=spr.data_offset, next_offset=0, same_palette=spr.palette_index,
                        format_hint=fmt_map.get(spr.format_name, spr.format_name), comment=f'SFF2 {spr.format_name} depth={spr.color_depth}',
                        raw_header_offset=spr.raw_table_offset,
                    ))
                info.is_supported_for_extraction = any(s.format_hint in {'png', 'raw', 'rle8', 'rle5', 'lz5'} for s in info.sprites)
                info.warnings.extend(s2.warnings)
                return info
        except Exception as exc:
            info.warnings.append(f'SFF v2 standard-table parse was not available: {exc}')
        info.variant = 'sff2-metadata'
        info.warnings.append('SFF v2/non-v1 layout detected. Standard table parsing did not identify exportable records; metadata view only.')
        return info

    if info.first_subfile_offset <= 0 or info.first_subfile_offset >= len(data):
        info.variant = 'unknown'
        info.v2_metadata = _inspect_sff2_header(data)
        info.warnings.append(f'First subfile offset looks invalid: {info.first_subfile_offset}.')
        if info.v2_metadata:
            info.warnings.append('Header contains possible SFF v2 table/data offsets; metadata view only.')
        return info

    offset = info.first_subfile_offset
    seen = set()
    for idx in range(min(info.sprite_count or max_sprites, max_sprites)):
        if offset in seen:
            info.warnings.append(f'Subfile chain loop detected at 0x{offset:X}.')
            break
        seen.add(offset)
        if offset + 32 > len(data):
            info.warnings.append(f'Subfile header {idx} runs beyond EOF at 0x{offset:X}.')
            break
        next_offset = _u32(data, offset)
        length = _u32(data, offset + 4)
        x = _i16(data, offset + 8)
        y = _i16(data, offset + 10)
        group = _u16(data, offset + 12)
        image = _u16(data, offset + 14)
        same_palette = _u16(data, offset + 16)
        comment_raw = data[offset + 19: offset + 32]
        comment = comment_raw.split(b'\x00', 1)[0].decode('latin-1', errors='replace').strip()
        data_offset = offset + 32
        if length == 0 and next_offset > data_offset:
            length = max(0, next_offset - data_offset)
        if length < 0 or data_offset + length > len(data):
            info.warnings.append(f'Sprite {idx} ({group},{image}) has invalid data length {length}.')
            break
        payload = data[data_offset:data_offset + min(length, 16)]
        if payload.startswith(b'\x0A'):
            fmt = 'pcx'
        elif payload.startswith(b'\x89PNG'):
            fmt = 'png'
        else:
            fmt = 'unknown'
        info.sprites.append(SffSprite(
            index=idx, group=group, image=image, x=x, y=y, length=length,
            data_offset=data_offset, next_offset=next_offset, same_palette=same_palette,
            format_hint=fmt, comment=comment, raw_header_offset=offset
        ))
        if next_offset == 0:
            break
        if next_offset <= offset or next_offset >= len(data):
            info.warnings.append(f'Sprite {idx} next offset looks invalid: 0x{next_offset:X}.')
            break
        offset = next_offset

    if info.sprites:
        info.variant = 'sff1-linked'
        pcx_count = sum(1 for s in info.sprites if s.format_hint == 'pcx')
        png_count = sum(1 for s in info.sprites if s.format_hint == 'png')
        if pcx_count or png_count:
            info.is_supported_for_extraction = True
        if info.sprite_count and len(info.sprites) != info.sprite_count:
            info.warnings.append(f'Header says {info.sprite_count} sprites; parsed {len(info.sprites)} via v1-style subfile chain.')
    else:
        info.warnings.append('No v1-style sprite subfiles were parsed. This may be SFF v2 or a nonstandard file.')
    return info


def sprite_lookup(info: SffInfo) -> Dict[Tuple[int, int], SffSprite]:
    lookup: Dict[Tuple[int, int], SffSprite] = {}
    for spr in info.sprites:
        lookup.setdefault(spr.key, spr)
    return lookup


def try_convert_to_png(src: Path, dst: Path) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        im = Image.open(src)
        im.save(dst)
        return True
    except Exception:
        return False


def _encode_image_to_pcx_bytes(image_path: Path) -> bytes:
    if image_path.suffix.lower() == '.pcx':
        return image_path.read_bytes()
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF files from PNG images. Install it with: pip install Pillow') from exc
    img = Image.open(image_path)
    if img.mode == 'RGBA':
        bg = Image.new('RGBA', img.size, (0, 0, 0, 0))
        bg.alpha_composite(img)
        img = bg.convert('RGB')
    if img.mode not in {'P', 'L'}:
        img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
    buf = BytesIO()
    img.save(buf, format='PCX')
    return buf.getvalue()


def _load_manifest_records(manifest_path: Path) -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list):
        raise ValueError('Manifest does not contain a sprites list.')
    return records


def build_sff_v1_from_manifest(manifest_path: Path, out_path: Path, *, force_pcx: bool = True) -> SffInfo:
    from ..sff_codec import read_sff
    manifest_path = Path(manifest_path)
    out_path = Path(out_path)
    records = _load_manifest_records(manifest_path)
    if not records:
        raise ValueError('Manifest contains no sprite records.')
    base_dir = manifest_path.parent
    sprite_payloads: list[tuple[dict, bytes]] = []
    group_set = set()
    for rec in records:
        filename = rec.get('filename')
        if not filename:
            raise ValueError('A manifest sprite record is missing filename.')
        img_path = (base_dir / filename).resolve()
        if not img_path.exists():
            raise FileNotFoundError(f'Manifest sprite image not found: {img_path}')
        payload = _encode_image_to_pcx_bytes(img_path) if force_pcx else img_path.read_bytes()
        sprite_payloads.append((rec, payload))
        group_set.add(int(rec.get('group', 0)))

    header_size = 512
    subheader_size = 32
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(header_size)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = bytes([1, 0, 1, 0])
    struct.pack_into('<I', header, 16, len(group_set))
    struct.pack_into('<I', header, 20, len(sprite_payloads))
    struct.pack_into('<I', header, 24, header_size)
    struct.pack_into('<I', header, 28, subheader_size)
    struct.pack_into('<I', header, 32, 1)

    chunks: list[bytes] = [bytes(header)]
    cursor = header_size
    for idx, (rec, payload) in enumerate(sprite_payloads):
        next_offset = cursor + subheader_size + len(payload) if idx < len(sprite_payloads) - 1 else 0
        group = int(rec.get('group', 0))
        image = int(rec.get('image', idx))
        axis = rec.get('axis') or {}
        x = int(axis.get('x', 0))
        y = int(axis.get('y', 0))
        sub = bytearray(subheader_size)
        struct.pack_into('<I', sub, 0, next_offset)
        struct.pack_into('<I', sub, 4, len(payload))
        struct.pack_into('<h', sub, 8, x)
        struct.pack_into('<h', sub, 10, y)
        struct.pack_into('<H', sub, 12, group & 0xFFFF)
        struct.pack_into('<H', sub, 14, image & 0xFFFF)
        struct.pack_into('<H', sub, 16, 0 if idx == 0 else 1)
        sub[19:32] = b'MugenForge\x00\x00\x00'
        chunks.append(bytes(sub))
        chunks.append(payload)
        cursor = next_offset or cursor + subheader_size + len(payload)
    out_path.write_bytes(b''.join(chunks))
    return read_sff(out_path)


def stage_sff_replacement_manifest(sff_path: Path, out_dir: Path) -> Path:
    from ..sff_codec import read_sff
    sff_path = Path(sff_path)
    out_dir = Path(out_dir)
    info = read_sff(sff_path)
    if not info.sprites or not info.is_supported_for_extraction:
        raise ValueError('This SFF has no supported PCX/PNG payloads to stage. SFF v2 files are metadata-only in this version.')
    sprite_dir = out_dir / 'sprites'
    sprite_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for spr in info.sprites:
        if spr.format_hint not in {'pcx', 'png'}:
            continue
        exported = export_sprite(sff_path, spr, sprite_dir)
        records.append({
            'index': spr.index,
            'group': spr.group,
            'image': spr.image,
            'axis': {'x': spr.x, 'y': spr.y},
            'filename': str(exported.relative_to(out_dir)).replace('\\', '/'),
            'original_format': spr.format_hint,
            'replace_with': '',
            'note': 'Edit filename in place or set replace_with to a PNG/PCX path relative to this manifest.',
        })
    manifest = {
        'schema': 'mugenforge.sff_replacement_manifest.v1',
        'source_sff': str(sff_path),
        'source_layout': info.variant,
        'sprites': records,
    }
    manifest_path = out_dir / 'mugenforge_sff_replacement_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest_path


def _load_replacement_records(manifest_path: Path) -> list[dict]:
    data = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list):
        raise ValueError('Replacement manifest does not contain a sprites list.')
    normalized = []
    base = Path(manifest_path).parent
    for rec in records:
        use_path = rec.get('replace_with') or rec.get('filename')
        if not use_path:
            raise ValueError('A replacement manifest record is missing filename/replace_with.')
        p = Path(str(use_path))
        if not p.is_absolute():
            p = base / p
        axis = rec.get('axis') or {}
        normalized.append({
            'group': int(rec.get('group', 0)),
            'image': int(rec.get('image', rec.get('index', 0))),
            'axis': {'x': int(axis.get('x', rec.get('x', 0))), 'y': int(axis.get('y', rec.get('y', 0)))},
            'filename': str(p),
        })
    return normalized


def build_sff_v1_from_replacement_manifest(manifest_path: Path, out_path: Path) -> SffInfo:
    import tempfile
    manifest_path = Path(manifest_path)
    records = _load_replacement_records(manifest_path)
    with tempfile.TemporaryDirectory(prefix='mugenforge_sff_replace_') as td:
        tmp = Path(td)
        norm_records = []
        for i, rec in enumerate(records):
            src = Path(rec['filename'])
            if not src.exists():
                raise FileNotFoundError(f'Replacement sprite file not found: {src}')
            dst = tmp / f'repl_{i:05d}{src.suffix.lower() or ".png"}'
            dst.write_bytes(src.read_bytes())
            norm_records.append({
                'group': rec['group'],
                'image': rec['image'],
                'axis': rec['axis'],
                'filename': dst.name,
            })
        tmp_manifest = tmp / 'mugenforge_sprite_manifest.json'
        tmp_manifest.write_text(json.dumps({'sprites': norm_records}, indent=2), encoding='utf-8')
        return build_sff_v1_from_manifest(tmp_manifest, out_path)


def summarize_replacement_manifest(manifest_path: Path) -> str:
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites') or []
    lines = [f'Replacement manifest: {manifest_path}', f'Source SFF: {data.get("source_sff", "unknown")}', f'Sprites: {len(records)}']
    groups = sorted({int(r.get('group', 0)) for r in records})
    lines.append(f'Groups: {", ".join(map(str, groups[:50]))}{" ..." if len(groups) > 50 else ""}')
    missing = []
    replacements = 0
    for rec in records:
        use_path = rec.get('replace_with') or rec.get('filename')
        if rec.get('replace_with'):
            replacements += 1
        p = Path(str(use_path))
        if not p.is_absolute():
            p = manifest_path.parent / p
        if not p.exists():
            missing.append(str(use_path))
    lines.append(f'Explicit replacements: {replacements}')
    if missing:
        lines.append('Missing files:')
        lines.extend(f'  - {m}' for m in missing[:100])
    else:
        lines.append('All referenced sprite files are present.')
    lines.append('Build mode: creates a fresh SFF v1-style PCX chain. It does not preserve SFF v2 compression/tables.')
    return '\n'.join(lines)


def summarize_manifest_for_sff(manifest_path: Path) -> str:
    records = _load_manifest_records(Path(manifest_path))
    lines = [f'Manifest: {manifest_path}', f'Sprites: {len(records)}']
    groups = sorted({int(r.get('group', 0)) for r in records})
    lines.append(f'Groups: {", ".join(map(str, groups[:40]))}{" ..." if len(groups) > 40 else ""}')
    missing = []
    for r in records:
        fn = r.get('filename', '')
        if fn and not (Path(manifest_path).parent / fn).exists():
            missing.append(fn)
    if missing:
        lines.append('Missing staged image files:')
        lines.extend(f'  - {m}' for m in missing[:80])
    else:
        lines.append('All referenced staged image files are present.')
    lines.append('Build mode: SFF v1-style PCX payload chain. This is a practical starter builder, not a full SFF v2 compiler.')
    return '\n'.join(lines)


def _mf_standard_record_from_sprite(info: SffInfo, sprite: SffSprite) -> Optional[Sff2StandardRecord]:
    meta = info.v2_metadata or {}
    by_index = meta.get('sff2_record_by_index') or {}
    raw = by_index.get(str(sprite.index)) or by_index.get(sprite.index)
    if not isinstance(raw, dict):
        try:
            raw = json.loads(sprite.comment)
        except Exception:
            raw = None
    if not isinstance(raw, dict):
        return None
    return Sff2StandardRecord(
        index=int(raw.get('index', sprite.index)),
        group=int(raw.get('group', sprite.group)),
        image=int(raw.get('image', sprite.image)),
        width=int(raw.get('width', 0)),
        height=int(raw.get('height', 0)),
        axis_x=int(raw.get('axis_x', sprite.x)),
        axis_y=int(raw.get('axis_y', sprite.y)),
        linked_index=int(raw.get('linked_index', 0)),
        format_code=int(raw.get('format_code', -1)),
        color_depth=int(raw.get('color_depth', 0)),
        data_offset=int(raw.get('data_offset', 0)),
        data_length=int(raw.get('data_length', sprite.length)),
        palette_index=int(raw.get('palette_index', 0)),
        flags=int(raw.get('flags', 0)),
        table_offset=int(raw.get('table_offset', sprite.raw_header_offset)),
        payload_offset=int(raw.get('payload_offset', sprite.data_offset)),
        payload_base=str(raw.get('payload_base', 'ldata')),
        note=str(raw.get('note', '')),
    )


def export_sprite(path: Path, sprite: SffSprite, out_dir: Path) -> Path:
    from ..sff_codec import read_sff
    from .sff_v2 import _mf_decode_sff2_record_to_png_bytes
    info = read_sff(path)
    if info.variant == 'sff2-standard':
        record = _mf_standard_record_from_sprite(info, sprite)
        if record is not None:
            png_bytes, mode = _mf_decode_sff2_record_to_png_bytes(path, info, record)
            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = '.png' if png_bytes.startswith(b'\x89PNG') else ('.pcx' if png_bytes.startswith(b'\x0A') else '.bin')
            out = out_dir / f'g{record.group:04d}_i{record.image:04d}_idx{record.index:05d}_{mode.replace("/", "-")}{suffix}'
            out.write_bytes(png_bytes)
            return out
    data = path.read_bytes()
    ext = '.png' if sprite.format_hint == 'png' else '.pcx'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'g{sprite.group:04d}_i{sprite.image:04d}_idx{sprite.index:05d}{ext}'
    out.write_bytes(data[sprite.data_offset:sprite.data_offset + sprite.length])
    return out


def export_all_sprites(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:
    from ..sff_codec import read_sff
    from .sff_v2 import parse_sff2_standard, decode_sff2_image
    info = read_sff(path)
    data = path.read_bytes()
    if len(data) >= 68 and data[:12] == SFF_SIGNATURE and data[12:16] in {b'\x00\x00\x00\x02', b'\x00\x01\x00\x02'}:
        s2 = parse_sff2_standard(path)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs: List[Path] = []
        for rec in s2.sprites[:max_count or len(s2.sprites)]:
            base = f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}'
            if rec.decodable:
                out = out_dir / f'{base}.png'
                try:
                    decode_sff2_image(path, rec, info=s2).save(out)
                    outputs.append(out)
                except Exception:
                    raw = out_dir / f'{base}_{rec.format_name}_decode_failed.bin'
                    raw.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
                    outputs.append(raw)
            elif rec.data_length:
                raw = out_dir / f'{base}_{rec.format_name}_unsupported.bin'
                raw.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
                outputs.append(raw)
        return outputs
    else:
        outputs = []
        for sprite in info.sprites[:max_count or len(info.sprites)]:
            if sprite.format_hint in {'pcx', 'png'} and sprite.length > 0:
                outputs.append(export_sprite(path, sprite, out_dir))
        return outputs
