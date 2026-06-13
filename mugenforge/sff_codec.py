from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import struct
from typing import Optional, List, Tuple, Dict, Any

SFF_SIGNATURE = b'ElecbyteSpr\x00'

@dataclass
class SffSprite:
    index: int
    group: int
    image: int
    x: int
    y: int
    length: int
    data_offset: int
    next_offset: int
    same_palette: int = 0
    format_hint: str = 'unknown'
    comment: str = ''
    raw_header_offset: int = 0

    @property
    def key(self) -> Tuple[int, int]:
        return (self.group, self.image)

@dataclass
class SffInfo:
    path: Path
    version: Tuple[int, int, int, int]
    sprite_count: int = 0
    group_count: int = 0
    first_subfile_offset: int = 0
    subheader_size: int = 0
    palette_type: int = 0
    warnings: List[str] = field(default_factory=list)
    sprites: List[SffSprite] = field(default_factory=list)
    is_supported_for_extraction: bool = False
    variant: str = 'unknown'
    v2_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version)


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def read_sff(path: Path, max_sprites: int = 20000) -> SffInfo:
    data = path.read_bytes()
    if len(data) < 32:
        return SffInfo(path=path, version=(0, 0, 0, 0), warnings=['File is too small to be a normal SFF file.'])
    if data[:12] != SFF_SIGNATURE:
        return SffInfo(path=path, version=(0, 0, 0, 0), warnings=['No ElecbyteSpr signature found.'])

    version = tuple(data[12:16])  # stored byte order varies in old notes; show raw and infer by layout
    info = SffInfo(
        path=path,
        version=version, 
        group_count=_u32(data, 16) if len(data) >= 20 else 0,
        sprite_count=_u32(data, 20) if len(data) >= 24 else 0,
        first_subfile_offset=_u32(data, 24) if len(data) >= 28 else 0,
        subheader_size=_u32(data, 28) if len(data) >= 32 else 0,
        palette_type=_u32(data, 32) if len(data) >= 36 else 0,
    )

    # SFF v2 and some nonstandard builds do not use a v1 32-byte linked subfile chain.
    # v5.5 adds a standard-table SFF2 parser. If that parser recognizes the file,
    # populate the generic sprite table so the rest of the app can inspect SFF2
    # records. Payload conversion lives in sff2_codec/binary_maturity; export_sprite
    # on this legacy class still writes raw payload bytes only.
    if info.version[0] >= 2 or info.version[3] == 2 or info.subheader_size not in (0, 32):
        info.v2_metadata = _inspect_sff2_header(data)
        try:
            from .sff2_codec import read_sff2  # local import avoids circular dependency
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

    # SFF v1 uses PCX payloads with a 32-byte subfile header chain. SFF v2 has different tables/encodings.
    # We detect v1 by walking the subfile chain and accepting plausible PCX payloads.
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


def _safe_u32(data: bytes, off: int) -> Optional[int]:
    try:
        if off < 0 or off + 4 > len(data):
            return None
        return struct.unpack_from('<I', data, off)[0]
    except Exception:
        return None


def _inspect_sff2_header(data: bytes) -> Dict[str, Any]:
    """Return conservative SFF v2-ish metadata without claiming full decode support.

    Elecbyte SFF2 files use tables and compressed image payloads rather than the old
    SFF1 linked PCX subfile chain. Offsets vary across notes/tools, so this function
    deliberately reports plausible table/data fields and byte signatures only.
    """
    meta: Dict[str, Any] = {}
    # Commonly referenced 32-bit header slots after the signature/version area.
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


def _find_all(data: bytes, needle: bytes) -> List[int]:
    hits: List[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx < 0:
            return hits
        hits.append(idx)
        start = idx + 1


def sprite_lookup(info: SffInfo) -> Dict[Tuple[int, int], SffSprite]:
    lookup: Dict[Tuple[int, int], SffSprite] = {}
    for spr in info.sprites:
        lookup.setdefault(spr.key, spr)
    return lookup


def export_sprite(path: Path, sprite: SffSprite, out_dir: Path) -> Path:
    data = path.read_bytes()
    ext = '.png' if sprite.format_hint == 'png' else '.pcx'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'g{sprite.group:04d}_i{sprite.image:04d}_idx{sprite.index:05d}{ext}'
    out.write_bytes(data[sprite.data_offset:sprite.data_offset + sprite.length])
    return out


def export_all_sprites(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:
    info = read_sff(path)
    outputs: List[Path] = []
    for sprite in info.sprites[:max_count or len(info.sprites)]:
        if sprite.format_hint in {'pcx', 'png'} and sprite.length > 0:
            outputs.append(export_sprite(path, sprite, out_dir))
    return outputs


def try_convert_to_png(src: Path, dst: Path) -> bool:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return False
    try:
        im = Image.open(src)
        im.save(dst)
        return True
    except Exception:
        return False


def summarize_sff_detailed(path: Path) -> str:
    info = read_sff(path)
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
        info.variant = 'sff1-linked'
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


def _encode_image_to_pcx_bytes(image_path: Path) -> bytes:
    """Convert a PNG/PCX image into an SFF v1-compatible PCX payload."""
    if image_path.suffix.lower() == '.pcx':
        return image_path.read_bytes()
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF files from PNG images. Install it with: pip install Pillow') from exc
    from io import BytesIO
    img = Image.open(image_path)
    # SFF v1 expects PCX payloads. Convert RGBA into an indexed PCX; transparency is flattened.
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
    import json
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list):
        raise ValueError('Manifest does not contain a sprites list.')
    return records


def build_sff_v1_from_manifest(manifest_path: Path, out_path: Path, *, force_pcx: bool = True) -> SffInfo:
    """Build a simple SFF v1-style file from a MugenForge staged sprite manifest.

    This is intentionally conservative: it writes a v1 subfile chain with PCX payloads.
    It is suitable for testing/starter characters and may need palette cleanup in mature projects.
    """
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
    # Common v1.01 raw bytes. Existing parser displays bytes as-is.
    header[12:16] = bytes([1, 0, 1, 0])
    struct.pack_into('<I', header, 16, len(group_set))
    struct.pack_into('<I', header, 20, len(sprite_payloads))
    struct.pack_into('<I', header, 24, header_size)
    struct.pack_into('<I', header, 28, subheader_size)
    struct.pack_into('<I', header, 32, 1)  # shared palette hint

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
    """Export supported sprites and create a replacement manifest for safe SFF v1 rebuilding.

    The manifest is deliberately simple: edit the exported files in place, or add a
    replace_with path per sprite record, then build a new SFF v1 from it.
    """
    import json
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
    import json
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
    """Build a new SFF v1 from a replacement manifest.

    This does not patch bytes into the original file. It creates a clean v1-style PCX
    SFF from the manifest records, preserving group/image/axis where possible.
    """
    import json, tempfile
    manifest_path = Path(manifest_path)
    records = _load_replacement_records(manifest_path)
    # Reuse the existing builder by writing a temporary normalized manifest with relative copies/paths.
    with tempfile.TemporaryDirectory(prefix='mugenforge_sff_replace_') as td:
        tmp = Path(td)
        norm_records = []
        for i, rec in enumerate(records):
            src = Path(rec['filename'])
            if not src.exists():
                raise FileNotFoundError(f'Replacement sprite file not found: {src}')
            # Keep original extension so the encoder can accept PCX directly or convert PNG.
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
    import json
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

# ---------------------------------------------------------------------------
# v5.5 Binary Mastery: broader clean-room SFF2 table parsing, decoding, axis
# patching, and source-manifest rebuild support.
#
# This section is intentionally self-contained and does not depend on any
# proprietary editor source. It implements a documented/common SFF2 table layout
# plus MugenForge's own round-trippable codecs. Unknown variants are still
# detected and reported rather than blindly mutated.

from dataclasses import dataclass as _mf_dataclass, field as _mf_field
from io import BytesIO as _MFBytesIO
import json as _mf_json
import zlib as _mf_zlib

# Preserve the original v1-oriented reader/exporters for fallback paths.
_mf_read_sff_v1_reader = read_sff
_mf_export_sprite_v1 = export_sprite
_mf_export_all_sprites_v1 = export_all_sprites
_mf_summarize_sff_detailed_v1 = summarize_sff_detailed

SFF2_FORMAT_NAMES = {
    0: 'raw',
    1: 'invalid',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png-direct',
    11: 'pcx-direct',
    12: 'zlib-png',
    13: 'zlib-pcx',
}
SFF2_NAME_TO_FORMAT = {v: k for k, v in SFF2_FORMAT_NAMES.items()}


@_mf_dataclass
class Sff2PaletteRecord:
    index: int
    group: int
    item: int
    num_colors: int
    data_offset: int
    data_length: int
    table_offset: int
    colors: List[Tuple[int, int, int]] = _mf_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'item': self.item,
            'num_colors': self.num_colors,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'table_offset': self.table_offset,
            'colors': [{'index': i, 'r': r, 'g': g, 'b': b} for i, (r, g, b) in enumerate(self.colors[:256])],
        }


@_mf_dataclass
class Sff2StandardRecord:
    index: int
    group: int
    image: int
    width: int
    height: int
    axis_x: int
    axis_y: int
    linked_index: int
    format_code: int
    color_depth: int
    data_offset: int
    data_length: int
    palette_index: int
    flags: int
    table_offset: int
    payload_offset: int
    payload_base: str = 'ldata'
    note: str = ''

    @property
    def format_name(self) -> str:
        return SFF2_FORMAT_NAMES.get(self.format_code, f'unknown-{self.format_code}')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.axis_x,
            'axis_y': self.axis_y,
            'linked_index': self.linked_index,
            'format_code': self.format_code,
            'format_name': self.format_name,
            'color_depth': self.color_depth,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'table_offset': self.table_offset,
            'payload_offset': self.payload_offset,
            'payload_base': self.payload_base,
            'note': self.note,
        }


def _mf_i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _mf_u8(data: bytes, off: int) -> int:
    return data[off]


def _mf_try_u32(data: bytes, off: int) -> Optional[int]:
    try:
        if off < 0 or off + 4 > len(data):
            return None
        return struct.unpack_from('<I', data, off)[0]
    except Exception:
        return None


def _mf_plausible_range(off: int, count: int, size: int, data_len: int) -> bool:
    return 0 <= int(count) <= 250000 and 0 < int(off) <= data_len and off + count * size <= data_len


def _mf_parse_sff2_standard(data: bytes) -> Tuple[Dict[str, Any], List[Sff2StandardRecord], List[Sff2PaletteRecord], List[str]]:
    warnings: List[str] = []
    meta: Dict[str, Any] = {
        'parser': 'mugenforge.sff2.standard.v55',
        'format_table': SFF2_FORMAT_NAMES,
        'raw_version_bytes': list(data[12:16]) if len(data) >= 16 else [],
    }
    records: List[Sff2StandardRecord] = []
    palettes: List[Sff2PaletteRecord] = []
    if len(data) < 512 or data[:12] != SFF_SIGNATURE:
        warnings.append('Not an ElecbyteSpr SFF or file is too small for SFF2 header parsing.')
        return meta, records, palettes, warnings

    # Common SFF2 header layout used by M.U.G.E.N 1.x SFF2 files. Do not rely on
    # only one version-byte ordering; verify the table ranges instead.
    sprite_offset = _mf_try_u32(data, 36) or 0
    sprite_total = _mf_try_u32(data, 40) or 0
    palette_offset = _mf_try_u32(data, 44) or 0
    palette_total = _mf_try_u32(data, 48) or 0
    ldata_offset = _mf_try_u32(data, 52) or 0
    ldata_length = _mf_try_u32(data, 56) or 0
    tdata_offset = _mf_try_u32(data, 60) or 0
    tdata_length = _mf_try_u32(data, 64) or 0
    meta.update({
        'sprite_offset': sprite_offset,
        'sprite_total': sprite_total,
        'palette_offset': palette_offset,
        'palette_total': palette_total,
        'ldata_offset': ldata_offset,
        'ldata_length': ldata_length,
        'tdata_offset': tdata_offset,
        'tdata_length': tdata_length,
        'sprite_record_size': 28,
        'palette_record_size': 16,
    })

    sprite_table_ok = _mf_plausible_range(sprite_offset, sprite_total, 28, len(data))
    palette_table_ok = (palette_total == 0 and palette_offset == 0) or _mf_plausible_range(palette_offset, palette_total, 16, len(data))
    if not sprite_table_ok:
        warnings.append('No plausible common SFF2 sprite table was found at header offsets 0x24/0x28.')
        return meta, records, palettes, warnings
    if not palette_table_ok:
        warnings.append('SFF2 palette table header fields are not plausible; sprite records will still be inspected without palettes.')

    if palette_table_ok and palette_total:
        for idx in range(int(palette_total)):
            off = palette_offset + idx * 16
            try:
                group = _u16(data, off + 0)
                item = _u16(data, off + 2)
                numcols = _u16(data, off + 4)
                pal_index = _u16(data, off + 6)
                rel = _u32(data, off + 8)
                length = _u32(data, off + 12)
                abs_off = ldata_offset + rel
                colors: List[Tuple[int, int, int]] = []
                if 0 <= abs_off <= len(data) and 0 <= length <= len(data) - abs_off:
                    blob = data[abs_off:abs_off + length]
                    # SFF2 palette entries are commonly 4 bytes per color: RGB + pad/alpha.
                    step = 4 if len(blob) >= max(1, numcols) * 4 else 3
                    for pos in range(0, min(len(blob), max(0, numcols) * step), step):
                        if pos + 2 < len(blob):
                            colors.append((blob[pos], blob[pos + 1], blob[pos + 2]))
                else:
                    warnings.append(f'Palette record {idx} has an invalid payload range.')
                palettes.append(Sff2PaletteRecord(
                    index=pal_index if pal_index != 0 else idx,
                    group=group,
                    item=item,
                    num_colors=numcols,
                    data_offset=rel,
                    data_length=length,
                    table_offset=off,
                    colors=colors,
                ))
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
            fmt = _mf_u8(data, off + 14)
            depth = _mf_u8(data, off + 15)
            rel = _u32(data, off + 16)
            length = _u32(data, off + 20)
            pal_idx = _u16(data, off + 24)
            flags = _u16(data, off + 26)
            base_off = ldata_offset if flags == 0 else tdata_offset
            base_name = 'ldata' if flags == 0 else 'tdata'
            abs_payload = base_off + rel
            note = ''
            if width <= 0 or height <= 0:
                note = 'zero-sized sprite'
            elif abs_payload < 0 or length < 0 or abs_payload + length > len(data):
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
    if not records:
        warnings.append('SFF2 header looked plausible, but no sprite records were parsed.')
    return meta, records, palettes, warnings


def _mf_unpack_payload(blob: bytes, expected: int) -> Tuple[bytes, bytes, str]:
    """Return (headerless_payload, raw_after_zlib_or_input, note)."""
    if expected <= 0:
        expected = 0
    note = ''
    original = blob
    # Direct image payloads from MugenForge v5 experimental files.
    if blob.startswith(b'\x89PNG') or blob.startswith(b'\x0A'):
        return blob, blob, 'direct image bytes'
    for candidate in (blob, blob[4:] if len(blob) >= 4 else b''):
        if not candidate:
            continue
        try:
            decomp = _mf_zlib.decompress(candidate)
            if decomp:
                blob = decomp
                note = 'zlib wrapper decoded'
                break
        except Exception:
            pass
    if len(blob) >= 4:
        declared = _u32(blob, 0)
        if declared == expected or (expected > 0 and 0 < declared <= expected * 4) or declared == len(blob) - 4:
            return blob[4:], blob, note or f'4-byte size prefix={declared}'
    return blob, original, note


def _mf_decode_rle_pairs(comp: bytes, expected: int, max_value: int = 255) -> bytes:
    out = bytearray()
    pos = 0
    while pos + 1 < len(comp) and len(out) < expected:
        run = comp[pos]
        val = comp[pos + 1] & max_value
        pos += 2
        if run == 0:
            # A zero run is treated as a literal escape for resilience.
            if pos < len(comp):
                lit_count = min(comp[pos], max(0, len(comp) - pos - 1))
                pos += 1
                out.extend(comp[pos:pos + lit_count])
                pos += lit_count
            continue
        out.extend([val] * run)
    return bytes(out[:expected])


def _mf_encode_rle_pairs(raw: bytes, max_value: int = 255) -> bytes:
    if not raw:
        return b''
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        value = raw[i] & max_value
        run = 1
        while i + run < n and run < 255 and (raw[i + run] & max_value) == value:
            run += 1
        out.extend((run, value))
        i += run
    return bytes(out)


def _mf_decode_lz5_stream(comp: bytes, expected: int) -> bytes:
    """Small LZSS-style decoder for MugenForge-built LZ5 streams.

    Tokens are grouped by a flag byte. Flag bit=1 means literal; bit=0 means a
    2-byte back-reference with 12-bit distance and 4-bit length+3. This decoder
    also accepts literal-only streams, which the v5.5 builder can emit safely.
    """
    out = bytearray()
    pos = 0
    while pos < len(comp) and len(out) < expected:
        flags = comp[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= expected or pos >= len(comp):
                break
            if flags & (1 << bit):
                out.append(comp[pos])
                pos += 1
            else:
                if pos + 1 >= len(comp):
                    break
                b1 = comp[pos]
                b2 = comp[pos + 1]
                pos += 2
                distance = ((b2 & 0xF0) << 4) | b1
                length = (b2 & 0x0F) + 3
                distance += 1
                if distance <= 0 or distance > len(out):
                    # Treat impossible references as zero fill instead of crashing.
                    out.extend(b'\x00' * length)
                else:
                    for _ in range(length):
                        out.append(out[-distance])
                        if len(out) >= expected:
                            break
    return bytes(out[:expected])


def _mf_encode_lz5_literal(raw: bytes) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(raw):
        chunk = raw[pos:pos + 8]
        out.append((1 << len(chunk)) - 1)
        out.extend(chunk)
        pos += len(chunk)
    return bytes(out)


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
        from PIL import Image  # type: ignore
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
    buf = _MFBytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _mf_decode_sff2_record_to_png_bytes(path: Path, info: SffInfo, record: Sff2StandardRecord) -> Tuple[bytes, str]:
    data = Path(path).read_bytes()
    if record.payload_offset < 0 or record.payload_length < 0 or record.payload_offset + record.payload_length > len(data):
        raise ValueError(f'SFF2 record {record.index} has an invalid payload range.')
    blob = data[record.payload_offset:record.payload_offset + record.payload_length]
    if record.format_code == 10 and blob.startswith(b'\x89PNG'):
        return blob, 'png-direct'
    if record.format_code == 11 and blob.startswith(b'\x0A'):
        try:
            from PIL import Image  # type: ignore
            img = Image.open(_MFBytesIO(blob))
            buf = _MFBytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue(), 'pcx-direct-converted'
        except Exception:
            return blob, 'pcx-direct-raw'
    payload, _, note = _mf_unpack_payload(blob, max(0, record.width * record.height))
    # Zlib-wrapped direct PNG/PCX support.
    if payload.startswith(b'\x89PNG'):
        return payload, note or 'zlib/direct png'
    if payload.startswith(b'\x0A'):
        try:
            from PIL import Image  # type: ignore
            img = Image.open(_MFBytesIO(payload))
            buf = _MFBytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue(), note or 'zlib/direct pcx converted'
        except Exception:
            return payload, note or 'zlib/direct pcx raw'

    expected = max(0, int(record.width) * int(record.height))
    if record.format_code == 0:
        pixels = payload[:expected]
        mode = 'raw'
    elif record.format_code == 2:
        pixels = _mf_decode_rle_pairs(payload, expected, 255)
        mode = 'rle8-pair'
    elif record.format_code == 3:
        pixels = _mf_decode_rle_pairs(payload, expected, 31)
        mode = 'rle5-pair'
    elif record.format_code == 4:
        pixels = _mf_decode_lz5_stream(payload, expected)
        mode = 'lz5-literal/lzss'
    elif record.format_code in {12, 13}:
        # Already attempted zlib above. Fall back to direct image conversion or indexed render.
        pixels = payload[:expected]
        mode = SFF2_FORMAT_NAMES.get(record.format_code, 'zlib-wrapper')
    else:
        raise ValueError(f'Unsupported SFF2 format code {record.format_code} for record {record.index}.')
    if len(pixels) < expected:
        raise ValueError(f'Decoder for record {record.index} produced {len(pixels)} bytes, expected {expected}.')
    palette = _mf_palette_for_record(info, record)
    return _mf_png_from_indexed(record.width, record.height, pixels, palette), mode


def _mf_standard_record_from_sprite(info: SffInfo, sprite: SffSprite) -> Optional[Sff2StandardRecord]:
    meta = info.v2_metadata or {}
    by_index = meta.get('sff2_record_by_index') or {}
    raw = by_index.get(str(sprite.index)) or by_index.get(sprite.index)
    if not isinstance(raw, dict):
        # Fall back from sprite comment if available.
        try:
            raw = _mf_json.loads(sprite.comment)
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


def read_sff(path: Path, max_sprites: int = 20000) -> SffInfo:  # type: ignore[no-redef]
    path = Path(path)
    data = path.read_bytes()
    base = _mf_read_sff_v1_reader(path, max_sprites=max_sprites)
    if len(data) < 512 or data[:12] != SFF_SIGNATURE:
        return base
    meta, records, palettes, warnings = _mf_parse_sff2_standard(data)
    if not records:
        if base.v2_metadata is None:
            base.v2_metadata = {}
        base.v2_metadata.update({'sff2_standard_probe': meta, 'sff2_standard_warnings': warnings})
        return base

    base.variant = 'sff2-standard'
    base.sprite_count = len(records)
    base.group_count = len({r.group for r in records})
    base.first_subfile_offset = int(meta.get('sprite_offset') or 0)
    base.subheader_size = 28
    base.palette_type = 2
    base.warnings = _uniq_list(base.warnings + warnings)
    sprites: List[SffSprite] = []
    extractable = 0
    record_dicts = [r.to_dict() for r in records[:max_sprites]]
    by_index = {str(r.index): r.to_dict() for r in records[:max_sprites]}
    for r in records[:max_sprites]:
        fmt_name = r.format_name
        if r.format_code in {0, 2, 3, 4, 10, 11, 12, 13} and not r.note.startswith('invalid'):
            extractable += 1
        sprites.append(SffSprite(
            index=r.index,
            group=r.group,
            image=r.image,
            x=r.axis_x,
            y=r.axis_y,
            length=r.data_length,
            data_offset=r.payload_offset,
            next_offset=0,
            same_palette=r.palette_index,
            format_hint=fmt_name,
            comment=_mf_json.dumps(r.to_dict(), separators=(',', ':')),
            raw_header_offset=r.table_offset,
        ))
    base.sprites = sprites
    base.is_supported_for_extraction = bool(extractable)
    base.v2_metadata.update({
        'sff2_standard': meta,
        'sff2_records': record_dicts,
        'sff2_record_by_index': by_index,
        'sff2_palettes': [p.to_dict() for p in palettes],
        'sff2_supported_codecs': ['raw', 'rle8-pair', 'rle5-pair', 'lz5-literal/lzss', 'png-direct', 'pcx-direct', 'zlib-png', 'zlib-pcx'],
        'sff2_codec_note': 'v5.5 decodes standard table records and MugenForge round-trippable raw/RLE/LZ streams; unknown third-party codec variants are reported.',
    })
    return base


def _uniq_list(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def export_sprite(path: Path, sprite: SffSprite, out_dir: Path) -> Path:  # type: ignore[no-redef]
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
    return _mf_export_sprite_v1(path, sprite, out_dir)


def export_all_sprites(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:  # type: ignore[no-redef]
    info = read_sff(path)
    outputs: List[Path] = []
    for sprite in info.sprites[:max_count or len(info.sprites)]:
        try:
            if info.variant == 'sff2-standard' or sprite.format_hint in {'pcx', 'png'}:
                outputs.append(export_sprite(path, sprite, out_dir))
        except Exception:
            continue
    return outputs


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
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF2 files from source images. Install with: pip install Pillow') from exc
    img = Image.open(image_path)
    if img.mode != 'P':
        img = img.convert('RGBA').convert('P', palette=Image.ADAPTIVE, colors=max(2, min(256, int(max_colors))))
    w, h = img.size
    colors = _mf_extract_palette_from_image(img)
    pixels = img.tobytes()
    return pixels, w, h, colors


def _mf_encode_sff2_payload(raw: bytes, compression: str) -> Tuple[int, int, bytes]:
    comp = str(compression or 'raw').strip().lower()
    if comp in {'none', 'raw', '0'}:
        return 0, 8, struct.pack('<I', len(raw)) + bytes(raw)
    if comp in {'rle8', '2'}:
        return 2, 8, struct.pack('<I', len(raw)) + _mf_encode_rle_pairs(raw, 255)
    if comp in {'rle5', '3'}:
        raw5 = bytes((b & 31) for b in raw)
        return 3, 5, struct.pack('<I', len(raw5)) + _mf_encode_rle_pairs(raw5, 31)
    if comp in {'lz5', '4'}:
        raw5 = bytes((b & 31) for b in raw)
        return 4, 5, struct.pack('<I', len(raw5)) + _mf_encode_lz5_literal(raw5)
    if comp in {'zlib-raw', 'zraw'}:
        return 0, 8, struct.pack('<I', len(raw)) + _mf_zlib.compress(bytes(raw))
    raise ValueError(f'Unsupported SFF2 build compression: {compression}')


def _mf_manifest_records_for_sff2(manifest_path: Path) -> List[Dict[str, Any]]:
    data = _mf_json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    records = data.get('sprites')
    if not isinstance(records, list):
        raise ValueError('SFF2 manifest does not contain a sprites list.')
    return records


def build_sff_v2_from_manifest(manifest_path: Path, out_path: Path, *, compression: str = 'raw') -> SffInfo:
    """Build a standard-table SFF2 candidate from a source sprite manifest.

    The writer uses a common SFF2 table layout, 256-color palette records, and
    MugenForge round-trippable raw/RLE/LZ payloads. It is designed for safe
    candidate builds and round-trip testing; always verify output in the target
    engine before shipping.
    """
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

    for idx, rec in enumerate(records):
        filename = rec.get('filename') or rec.get('file')
        if not filename:
            raise ValueError(f'Sprite manifest row {idx} is missing filename.')
        src = Path(str(filename))
        if not src.is_absolute():
            src = base_dir / src
        if not src.exists():
            raise FileNotFoundError(f'SFF2 source image not found: {src}')
        row_comp = str(rec.get('compression') or compression or 'raw').strip().lower()
        max_colors = 32 if row_comp in {'rle5', 'lz5', '3', '4'} else 256
        pixels, w, h, colors = _mf_quantize_image_to_indices(src, max_colors=max_colors)
        key = tuple(colors[:256])
        if key not in palette_map:
            pal_index = len(palette_records)
            palette_map[key] = pal_index
            pal_offset = len(ldata)
            for r, g, b in colors[:256]:
                ldata.extend(bytes((max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))), 0)))
            palette_records.append({'index': pal_index, 'group': 1, 'item': pal_index + 1, 'num_colors': 256, 'data_offset': pal_offset, 'data_length': 1024})
        else:
            pal_index = palette_map[key]
        fmt_code, depth, payload = _mf_encode_sff2_payload(pixels, row_comp)
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
            'linked_index': 0,
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
    # Version bytes are written with 2 in the first slot for compatibility with
    # MugenForge's legacy detector; the table fields are the real parser source.
    header[12:16] = bytes([2, 0, 0, 0])
    struct.pack_into('<I', header, 16, 0)
    struct.pack_into('<I', header, 20, 0)
    header[24:28] = bytes([2, 0, 0, 0])
    struct.pack_into('<I', header, 28, 0)
    struct.pack_into('<I', header, 32, 0)
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
        struct.pack_into('<H', pal_table, off + 6, int(pal['index']) & 0xFFFF)
        struct.pack_into('<I', pal_table, off + 8, int(pal['data_offset']))
        struct.pack_into('<I', pal_table, off + 12, int(pal['data_length']))

    spr_table = bytearray(sprite_total * 28)
    for idx, rec in enumerate(normalized):
        off = idx * 28
        struct.pack_into('<H', spr_table, off + 0, rec['group'] & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 2, rec['image'] & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 4, max(0, int(rec['width'])) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 6, max(0, int(rec['height'])) & 0xFFFF)
        struct.pack_into('<h', spr_table, off + 8, max(-32768, min(32767, int(rec['axis_x']))))
        struct.pack_into('<h', spr_table, off + 10, max(-32768, min(32767, int(rec['axis_y']))))
        struct.pack_into('<H', spr_table, off + 12, rec['linked_index'] & 0xFFFF)
        spr_table[off + 14] = int(rec['format_code']) & 0xFF
        spr_table[off + 15] = int(rec['color_depth']) & 0xFF
        struct.pack_into('<I', spr_table, off + 16, int(rec['data_offset']))
        struct.pack_into('<I', spr_table, off + 20, int(rec['data_length']))
        struct.pack_into('<H', spr_table, off + 24, int(rec['palette_index']) & 0xFFFF)
        struct.pack_into('<H', spr_table, off + 26, int(rec['flags']) & 0xFFFF)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(header) + bytes(pal_table) + bytes(spr_table) + bytes(ldata))
    return read_sff(out_path)


def patch_sff2_axis_copy(sff_path: Path, axis_rows: Iterable[Dict[str, Any]], out_path: Path) -> SffInfo:
    """Patch SFF1/SFF2 axis table fields into a copied file and return parsed info."""
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
            # Standard SFF2 and MugenForge subset both place axis at record+8/+10.
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


def summarize_sff_detailed(path: Path) -> str:  # type: ignore[no-redef]
    info = read_sff(path)
    if info.variant != 'sff2-standard':
        return _mf_summarize_sff_detailed_v1(path)
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



# ---------------------------------------------------------------------------
# v5.5 Binary Maturity additions: standard SFF2 parser, decoded export, and
# controlled SFF2 rebuild support. This code is clean-room Python derived from
# public file-format behavior and keeps unsupported compression paths explicit.

from dataclasses import dataclass as _dataclass, field as _field
from pathlib import Path as _Path
from io import BytesIO as _BytesIO
import zlib as _zlib
import json as _json

SFF2_IMAGE_FORMATS = {
    0: 'raw',
    1: 'linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png8',
    11: 'png24',
    12: 'png32',
}
SFF2_DECODABLE_FORMATS = {0, 2, 10, 11, 12}
SFF2_EXPERIMENTAL_FORMATS = {3, 4}
SFF2_STANDARD_VERSIONS = {b'\x00\x00\x00\x02', b'\x00\x01\x00\x02'}
SFF2_LEGACY_LITTLE_VERSION = b'\x02\x00\x00\x00'

@_dataclass
class Sff2PaletteRecord:
    index: int
    group: int
    item: int
    color_count: int
    link_index: int
    data_offset: int
    data_length: int
    table_offset: int
    data_base: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'item': self.item,
            'color_count': self.color_count,
            'link_index': self.link_index,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'table_offset': self.table_offset,
            'data_base': self.data_base,
        }

@_dataclass
class Sff2ImageRecord:
    index: int
    group: int
    image: int
    width: int
    height: int
    x: int
    y: int
    link_index: int
    image_format: int
    color_depth: int
    data_offset: int
    data_length: int
    palette_index: int
    flags: int
    table_offset: int
    local_data_base: int
    translated_data_base: int
    warnings: List[str] = _field(default_factory=list)

    @property
    def format_name(self) -> str:
        return SFF2_IMAGE_FORMATS.get(int(self.image_format), f'unknown-{self.image_format}')

    @property
    def is_linked(self) -> bool:
        return self.data_length == 0 or self.image_format == 1

    @property
    def decodable(self) -> bool:
        return self.image_format in SFF2_DECODABLE_FORMATS and not self.is_linked

    @property
    def key(self) -> Tuple[int, int]:
        return (self.group, self.image)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.x,
            'axis_y': self.y,
            'link_index': self.link_index,
            'image_format': self.image_format,
            'format_name': self.format_name,
            'color_depth': self.color_depth,
            'data_offset': self.data_offset,
            'data_length': self.data_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'table_offset': self.table_offset,
            'local_data_base': self.local_data_base,
            'translated_data_base': self.translated_data_base,
            'decodable': self.decodable,
            'warnings': list(self.warnings),
        }

@_dataclass
class Sff2StandardInfo:
    path: _Path
    version_bytes: Tuple[int, int, int, int]
    sprite_table_offset: int
    sprite_count: int
    palette_table_offset: int
    palette_count: int
    local_data_offset: int
    local_data_length: int
    translated_data_offset: int
    translated_data_length: int
    sprites: List[Sff2ImageRecord] = _field(default_factory=list)
    palettes: List[Sff2PaletteRecord] = _field(default_factory=list)
    warnings: List[str] = _field(default_factory=list)

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version_bytes)

    @property
    def decodable_count(self) -> int:
        return sum(1 for s in self.sprites if s.decodable)

    @property
    def unsupported_count(self) -> int:
        return sum(1 for s in self.sprites if not s.decodable and not s.is_linked)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': str(self.path),
            'version_bytes': list(self.version_bytes),
            'version_text': self.version_text,
            'sprite_table_offset': self.sprite_table_offset,
            'sprite_count': self.sprite_count,
            'palette_table_offset': self.palette_table_offset,
            'palette_count': self.palette_count,
            'local_data_offset': self.local_data_offset,
            'local_data_length': self.local_data_length,
            'translated_data_offset': self.translated_data_offset,
            'translated_data_length': self.translated_data_length,
            'decodable_count': self.decodable_count,
            'unsupported_count': self.unsupported_count,
            'sprites': [s.to_dict() for s in self.sprites],
            'palettes': [p.to_dict() for p in self.palettes],
            'warnings': list(self.warnings),
        }


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


def _is_standard_sff2_bytes(data: bytes) -> bool:
    return len(data) >= 68 and data[:12] == SFF_SIGNATURE and data[12:16] in SFF2_STANDARD_VERSIONS


def parse_sff2_standard(path: _Path, max_sprites: int = 250000, *, allow_legacy_subset: bool = False) -> Sff2StandardInfo:
    """Parse a standard SFF v2/v2.1 table layout without decoding pixels.

    Standard SFF2 uses separate sprite and palette tables. Image payload offsets
    are relative to either the local-data or translated-data area based on flags.
    """
    path = _Path(path)
    data = path.read_bytes()
    warnings: List[str] = []
    if len(data) < 68 or data[:12] != SFF_SIGNATURE:
        raise ValueError('Not an ElecbyteSpr file or too small for SFF2 header.')
    ver = data[12:16]
    if ver not in SFF2_STANDARD_VERSIONS:
        if not (allow_legacy_subset and ver == SFF2_LEGACY_LITTLE_VERSION):
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
            info.palettes.append(Sff2PaletteRecord(idx, group, item, ncol, link, actual, length, off, ldata_offset))
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


def decode_sff2_rle8_indices(payload: bytes, expected_pixels: int) -> bytes:
    if len(payload) < 4:
        raise ValueError('RLE8 payload is shorter than its uncompressed-size prefix.')
    declared = struct.unpack_from('<I', payload, 0)[0]
    if expected_pixels and declared not in {expected_pixels, 0}:
        # Continue but preserve caller visibility through short/long output checks.
        pass
    out = bytearray()
    run_len: Optional[int] = None
    for b in payload[4:]:
        if ((b & 0xC0) != 0x40) or run_len is not None:
            n = 1 if run_len is None else run_len
            if n > 0:
                out.extend(bytes([b]) * n)
            run_len = None
            if expected_pixels and len(out) >= expected_pixels:
                break
        else:
            run_len = b - 0x40
    if expected_pixels:
        if len(out) < expected_pixels:
            out.extend(b'\x00' * (expected_pixels - len(out)))
        elif len(out) > expected_pixels:
            del out[expected_pixels:]
    return bytes(out)


def encode_sff2_rle8_indices(indices: bytes) -> bytes:
    data = bytes(indices)
    out = bytearray(struct.pack('<I', len(data)))
    i = 0
    n = len(data)
    while i < n:
        value = data[i]
        run = 1
        while i + run < n and data[i + run] == value and run < 63:
            run += 1
        if run >= 2:
            out.append(0x40 + run)
            out.append(value)
            i += run
            continue
        if 0x40 <= value <= 0x7F:
            out.append(0x41)
            out.append(value)
        else:
            out.append(value)
        i += 1
    return bytes(out)


def _unpack_5bit_indices(payload: bytes, expected_pixels: int) -> bytes:
    """Diagnostic 5-bit unpacker used for raw/rle5/lz5 lab payload review.

    It is not claimed as the Elecbyte RLE5/LZ5 codec. It gives creators a safe
    preview instead of silently pretending unsupported compression was decoded.
    """
    out = bytearray()
    acc = 0
    bits = 0
    for b in payload:
        acc |= int(b) << bits
        bits += 8
        while bits >= 5 and (not expected_pixels or len(out) < expected_pixels):
            out.append(acc & 0x1F)
            acc >>= 5
            bits -= 5
        if expected_pixels and len(out) >= expected_pixels:
            break
    if expected_pixels and len(out) < expected_pixels:
        out.extend(b'\x00' * (expected_pixels - len(out)))
    return bytes(out[:expected_pixels] if expected_pixels else out)


def decode_sff2_image(path: _Path, record: Sff2ImageRecord, *, info: Optional[Sff2StandardInfo] = None):
    """Decode a supported SFF2 image record into a Pillow Image.

    Supported production decodes: raw8/raw24/raw32, RLE8, PNG8/24/32, zlib-wrapped
    PNG. RLE5/LZ5 are deliberately not presented as production-accurate decode.
    """
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required for SFF2 image decode/export. Install with: pip install Pillow') from exc
    path = _Path(path)
    data = path.read_bytes()
    info = info or parse_sff2_standard(path)
    if record.is_linked:
        if 0 <= record.link_index < len(info.sprites) and record.link_index != record.index:
            return decode_sff2_image(path, info.sprites[record.link_index], info=info)
        raise ValueError(f'Sprite #{record.index} is linked to invalid index {record.link_index}.')
    payload = data[record.data_offset:record.data_offset + record.data_length]
    if payload[:2] in {b'\x78\x9c', b'\x78\xda', b'\x78\x01'}:
        try:
            maybe = _zlib.decompress(payload)
            if maybe.startswith(b'\x89PNG\r\n\x1a\n'):
                payload = maybe
        except Exception:
            pass
    if record.image_format in {10, 11, 12} or payload.startswith(b'\x89PNG\r\n\x1a\n'):
        im = Image.open(_BytesIO(payload))
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
        colors = _sff2_palette_rgba(data, info, record.palette_index)
        rgba = bytearray()
        for idx in indices[:expected]:
            rgba.extend(colors[idx])
        return Image.frombytes('RGBA', (record.width, record.height), bytes(rgba))
    if record.image_format == 0:
        if record.color_depth == 8:
            indices = payload[:expected].ljust(expected, b'\x00')
            colors = _sff2_palette_rgba(data, info, record.palette_index)
            rgba = bytearray()
            for idx in indices[:expected]:
                rgba.extend(colors[idx])
            return Image.frombytes('RGBA', (record.width, record.height), bytes(rgba))
        if record.color_depth == 24:
            need = expected * 3
            raw = payload[:need].ljust(need, b'\x00')
            return Image.frombytes('RGB', (record.width, record.height), raw).convert('RGBA')
        if record.color_depth == 32:
            need = expected * 4
            raw = payload[:need].ljust(need, b'\x00')
            return Image.frombytes('RGBA', (record.width, record.height), raw)
        if record.color_depth == 5:
            indices = _unpack_5bit_indices(payload, expected)
            colors = _sff2_palette_rgba(data, info, record.palette_index)
            rgba = bytearray()
            for idx in indices[:expected]:
                rgba.extend(colors[idx])
            return Image.frombytes('RGBA', (record.width, record.height), bytes(rgba))
    raise ValueError(f'SFF2 format {record.format_name} depth {record.color_depth} is not production-decodable in this build.')


def export_sff2_decoded_images(path: _Path, out_dir: _Path, *, include_raw_payloads: bool = True) -> List[_Path]:
    path = _Path(path)
    out_dir = _Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = parse_sff2_standard(path)
    outputs: List[_Path] = []
    data = path.read_bytes()
    for rec in info.sprites:
        base = f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}'
        if rec.decodable:
            out = out_dir / f'{base}.png'
            try:
                decode_sff2_image(path, rec, info=info).save(out)
                outputs.append(out)
            except Exception:
                if include_raw_payloads and rec.data_length:
                    raw = out_dir / f'{base}_{rec.format_name}.bin'
                    raw.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
                    outputs.append(raw)
        elif include_raw_payloads and rec.data_length:
            raw = out_dir / f'{base}_{rec.format_name}_unsupported.bin'
            raw.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
            outputs.append(raw)
    return outputs


def _image_to_sff2_payload(image_path: _Path, strategy: str = 'png') -> Tuple[bytes, int, int, int, int]:
    """Return payload, format_code, color_depth, width, height."""
    from PIL import Image  # type: ignore
    image_path = _Path(image_path)
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
    buf = _BytesIO()
    rgba = im.convert('RGBA')
    rgba.save(buf, format='PNG')
    return buf.getvalue(), 12, 32, width, height


def _palette_from_image_or_default(image_paths: Sequence[_Path]) -> bytes:
    try:
        from PIL import Image  # type: ignore
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


def build_sff2_standard_from_records(records: Sequence[Dict[str, Any]], out_path: _Path, *, version_21: bool = True, default_strategy: str = 'png') -> Sff2StandardInfo:
    """Build a controlled standard SFF2 from record dictionaries.

    Each record may provide an image file (`filename`/`image_file`) or a binary
    payload copy (`payload`, `image_format`, `color_depth`, `width`, `height`).
    This is a real table-based SFF2 writer for supported records; it does not
    invent Elecbyte RLE5/LZ5 compression.
    """
    if not records:
        raise ValueError('No SFF2 records supplied.')
    out_path = _Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image_paths = []
    normalized: List[Dict[str, Any]] = []
    for idx, rec in enumerate(records):
        img_file = rec.get('image_file') or rec.get('filename') or ''
        if img_file:
            p = _Path(str(img_file))
            image_paths.append(p)
        normalized.append(dict(rec, _index=idx))
    palette_payload = _palette_from_image_or_default(image_paths)
    payload_items: List[Tuple[Dict[str, Any], bytes, int, int, int, int]] = []
    base_dir = None
    for rec in normalized:
        img_file = rec.get('image_file') or rec.get('filename') or ''
        if img_file:
            p = _Path(str(img_file))
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
        # 4-byte align each payload to keep offsets friendly.
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


def build_sff2_standard_from_manifest(manifest_path: _Path, out_path: _Path, *, default_strategy: str = 'png') -> Sff2StandardInfo:
    manifest_path = _Path(manifest_path)
    data = _json.loads(manifest_path.read_text(encoding='utf-8'))
    records = data.get('sprites') or data.get('records') or []
    if not isinstance(records, list):
        raise ValueError('SFF2 manifest does not contain a sprite records list.')
    base = manifest_path.parent
    norm = []
    for rec in records:
        r = dict(rec)
        fn = r.get('image_file') or r.get('filename')
        if fn:
            p = _Path(str(fn))
            if not p.is_absolute():
                p = base / p
            r['image_file'] = str(p)
        axis = r.get('axis') if isinstance(r.get('axis'), dict) else {}
        if axis:
            r.setdefault('axis_x', axis.get('x', 0))
            r.setdefault('axis_y', axis.get('y', 0))
        norm.append(r)
    return build_sff2_standard_from_records(norm, out_path, default_strategy=default_strategy)


def summarize_sff2_standard(path: _Path) -> str:
    info = parse_sff2_standard(path)
    lines = [
        f'File: {_Path(path).name}',
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


# Override read_sff with standard SFF2 awareness while keeping the old parser.
_read_sff_v50 = read_sff

def read_sff(path: Path, max_sprites: int = 20000) -> SffInfo:  # type: ignore[no-redef]
    path = Path(path)
    data = path.read_bytes()
    if len(data) >= 68 and data[:12] == SFF_SIGNATURE and data[12:16] in SFF2_STANDARD_VERSIONS:
        try:
            s2 = parse_sff2_standard(path, max_sprites=max_sprites)
            info = SffInfo(
                path=path,
                version=tuple(data[12:16]),
                sprite_count=len(s2.sprites),
                group_count=len({r.group for r in s2.sprites}),
                first_subfile_offset=s2.sprite_table_offset,
                subheader_size=28,
                palette_type=2,
                variant='sff2-standard',
                is_supported_for_extraction=s2.decodable_count > 0,
                warnings=list(s2.warnings),
                v2_metadata={
                    'parser': 'standard_sff2_v55',
                    'standard': s2.to_dict(),
                    'header_slots': _inspect_sff2_header(data).get('header_slots', {}),
                    'supported_decode_formats': ['raw8', 'raw24', 'raw32', 'rle8', 'png8', 'png24', 'png32', 'zlib-wrapped-png'],
                    'unsupported_decode_formats': ['rle5', 'lz5'],
                },
            )
            for rec in s2.sprites:
                if rec.image_format in {10, 11, 12}:
                    fmt = 'png'
                elif rec.image_format == 0:
                    fmt = f'sff2_raw{rec.color_depth}'
                elif rec.image_format == 2:
                    fmt = 'sff2_rle8'
                elif rec.image_format == 3:
                    fmt = 'sff2_rle5'
                elif rec.image_format == 4:
                    fmt = 'sff2_lz5'
                elif rec.is_linked:
                    fmt = 'sff2_linked'
                else:
                    fmt = f'sff2_fmt{rec.image_format}'
                info.sprites.append(SffSprite(
                    index=rec.index,
                    group=rec.group,
                    image=rec.image,
                    x=rec.x,
                    y=rec.y,
                    length=rec.data_length,
                    data_offset=rec.data_offset,
                    next_offset=0,
                    same_palette=rec.palette_index,
                    format_hint=fmt,
                    comment=f'SFF2 {rec.format_name} {rec.width}x{rec.height} depth={rec.color_depth}',
                    raw_header_offset=rec.table_offset,
                ))
            if s2.unsupported_count:
                info.warnings.append(f'{s2.unsupported_count} SFF2 sprites use RLE5/LZ5/unsupported compression and are preserved as payloads, not production-decoded.')
            return info
        except Exception as exc:
            legacy = _read_sff_v50(path, max_sprites=max_sprites)
            legacy.warnings.append(f'SFF2 standard parser failed, fell back to legacy parser: {exc}')
            return legacy
    return _read_sff_v50(path, max_sprites=max_sprites)


# Override export_all_sprites so standard SFF2 decodable payloads export as PNG.
_export_all_sprites_v50 = export_all_sprites

def export_all_sprites(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:  # type: ignore[no-redef]
    path = Path(path)
    data = path.read_bytes()
    if len(data) >= 68 and data[:12] == SFF_SIGNATURE and data[12:16] in SFF2_STANDARD_VERSIONS:
        info = parse_sff2_standard(path)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs: List[Path] = []
        for rec in info.sprites[:max_count or len(info.sprites)]:
            base = f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}'
            if rec.decodable:
                out = out_dir / f'{base}.png'
                try:
                    decode_sff2_image(path, rec, info=info).save(out)
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
    return _export_all_sprites_v50(path, out_dir, max_count=max_count)

# ---------------------------------------------------------------------------
# v5.5.1 Standard SFF2 codec corrections.
# These final overrides replace the earlier broad probe labels with the common
# SFF2 table/header interpretation used by M.U.G.E.N 1.x tooling: raw, RLE8,
# RLE5, LZ5, PNG8/PNG24/PNG32. Transitional direct/zlib PCX/PNG payloads remain
# supported as payload-signature fallbacks for recovery work.

SFF2_FORMAT_NAMES = {
    0: 'raw',
    1: 'linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png8',
    11: 'png24',
    12: 'png32',
}
SFF2_NAME_TO_FORMAT = {v: k for k, v in SFF2_FORMAT_NAMES.items()}


def _mf_parse_sff2_standard(data: bytes) -> Tuple[Dict[str, Any], List[Sff2StandardRecord], List[Sff2PaletteRecord], List[str]]:  # type: ignore[no-redef]
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

    for idx in range(int(palette_total)):
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
            if length and 0 <= abs_off <= len(data) and 0 <= length <= len(data) - abs_off:
                blob = data[abs_off:abs_off + length]
                step = 4 if len(blob) >= max(1, int(numcols)) * 4 else 3
                for pos in range(0, min(len(blob), max(0, int(numcols)) * step), step):
                    if pos + 2 < len(blob):
                        colors.append((blob[pos], blob[pos + 1], blob[pos + 2]))
            elif length:
                warnings.append(f'Palette record {idx} has invalid payload range.')
            palettes.append(Sff2PaletteRecord(
                index=idx,
                group=group,
                item=item,
                num_colors=numcols,
                data_offset=rel,
                data_length=length,
                table_offset=off,
                colors=colors,
            ))
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


def _mf_strip_size_prefix(blob: bytes, expected: int) -> bytes:
    if len(blob) >= 4:
        declared = _u32(blob, 0)
        if declared == expected or declared == len(blob) - 4:
            return blob[4:]
    return blob


def _mf_decode_ele_rle8(comp: bytes, expected: int) -> bytes:
    comp = _mf_strip_size_prefix(comp, expected)
    out = bytearray()
    pos = 0
    while pos < len(comp) and len(out) < expected:
        b = comp[pos]
        pos += 1
        if (b & 0xC0) == 0x40:
            run = b & 0x3F
            if pos >= len(comp):
                break
            val = comp[pos]
            pos += 1
            out.extend([val] * run)
        else:
            out.append(b)
    if len(out) != expected:
        # Backward-compatible fallback for the earlier MugenForge pair codec.
        pair = _mf_decode_rle_pairs(_mf_strip_size_prefix(comp, expected), expected, 255)
        if len(pair) == expected:
            return pair
        raise ValueError(f'RLE8 decoded {len(out)} bytes, expected {expected}.')
    return bytes(out)


def _mf_encode_ele_rle8(raw: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        val = raw[i]
        run = 1
        while i + run < n and raw[i + run] == val and run < 63:
            run += 1
        if run > 1 or (val & 0xC0) == 0x40:
            out.append(0x40 | run)
            out.append(val)
        else:
            out.append(val)
        i += run
    return bytes(out)


def _mf_decode_ele_rle5(comp: bytes, expected: int) -> bytes:
    comp0 = _mf_strip_size_prefix(comp, expected)
    out = bytearray(expected)
    pos = 0
    j = 0
    try:
        while j < expected and pos < len(comp0):
            rl = comp0[pos]
            pos += 1
            if pos >= len(comp0):
                break
            token = comp0[pos]
            pos += 1
            dl = token & 0x7F
            c = 0
            if token & 0x80:
                if pos >= len(comp0):
                    break
                c = comp0[pos] & 0x1F
                pos += 1
            while True:
                if j < expected:
                    out[j] = c & 0x1F
                    j += 1
                rl -= 1
                if rl < 0:
                    dl -= 1
                    if dl < 0:
                        break
                    if pos >= len(comp0):
                        raise ValueError('RLE5 stream ended inside a delta run.')
                    t = comp0[pos]
                    pos += 1
                    c = t & 0x1F
                    rl = t >> 5
        if j == expected:
            return bytes(out)
    except Exception:
        pass
    # Fallback to earlier pair and packed-5 heuristics for recovery.
    try:
        pair = _mf_decode_rle_pairs(comp0, expected, 31)
        if len(pair) == expected:
            return pair
    except Exception:
        pass
    unpacked = _mf_unpack_5bit_for_v551(comp0, expected)
    if len(unpacked) == expected:
        return unpacked
    raise ValueError(f'RLE5 decoded {j} bytes, expected {expected}.')


def _mf_encode_ele_rle5(raw5: bytes) -> bytes:
    raw5 = bytes((b & 0x1F) for b in raw5)
    out = bytearray()
    pos = 0
    while pos < len(raw5):
        chunk = raw5[pos:pos + 128]
        if not chunk:
            break
        out.append(0)  # first value run length minus one
        out.append(0x80 | (len(chunk) - 1))
        out.append(chunk[0])
        for b in chunk[1:]:
            out.append(b & 0x1F)  # subsequent single-value runs
        pos += len(chunk)
    return bytes(out)


def _mf_unpack_5bit_for_v551(data: bytes, expected: int) -> bytes:
    out = bytearray()
    bitbuf = 0
    bitcount = 0
    for b in data:
        bitbuf |= int(b) << bitcount
        bitcount += 8
        while bitcount >= 5 and len(out) < expected:
            out.append(bitbuf & 0x1F)
            bitbuf >>= 5
            bitcount -= 5
        if len(out) >= expected:
            break
    return bytes(out)


def _mf_decode_ele_lz5(comp: bytes, expected: int) -> bytes:
    comp0 = _mf_strip_size_prefix(comp, expected)
    out = bytearray(expected)
    pos = 0
    j = 0
    try:
        if not comp0:
            raise ValueError('empty LZ5 stream')
        ctl = comp0[pos]
        pos += 1
        cts = 0
        rb = 0
        rbc = 0
        while j < expected and pos < len(comp0):
            d = comp0[pos]
            pos += 1
            if ctl & (1 << cts):
                rb |= (d & 0xC0) >> rbc
                rbc += 2
                n = d & 0x3F
                if rbc < 8:
                    if pos >= len(comp0):
                        break
                    dist = comp0[pos] + 1
                    pos += 1
                else:
                    dist = rb + 1
                    rb = 0
                    rbc = 0
                if dist <= 0 or dist > j:
                    raise ValueError('invalid LZ5 back-reference distance')
                for _ in range(n + 1):
                    if j >= expected:
                        break
                    out[j] = out[j - dist]
                    j += 1
            else:
                if d & 0xE0 == 0:
                    val = d & 0x1F
                    if pos >= len(comp0):
                        break
                    n = comp0[pos] + 8
                    pos += 1
                else:
                    n = d >> 5
                    val = d & 0x1F
                for _ in range(n):
                    if j >= expected:
                        break
                    out[j] = val
                    j += 1
            cts += 1
            if cts >= 8:
                cts = 0
                if pos >= len(comp0):
                    break
                ctl = comp0[pos]
                pos += 1
        if j == expected:
            return bytes(out)
    except Exception:
        pass
    # Backward-compatible fallback to the earlier literal/LZSS and packed-5 recovery paths.
    try:
        old = _mf_decode_lz5_stream(comp0, expected)
        if len(old) == expected:
            return old
    except Exception:
        pass
    unpacked = _mf_unpack_5bit_for_v551(comp0, expected)
    if len(unpacked) == expected:
        return unpacked
    raise ValueError(f'LZ5 decoded {j} bytes, expected {expected}.')


def _mf_encode_ele_lz5_literal(raw5: bytes) -> bytes:
    raw5 = bytes((b & 0x1F) for b in raw5)
    out = bytearray()
    pos = 0
    while pos < len(raw5):
        # Emit up to eight literal-run tokens under a zero control byte.
        control_pos = len(out)
        out.append(0)
        tokens = 0
        while tokens < 8 and pos < len(raw5):
            value = raw5[pos] & 0x1F
            run = 1
            while pos + run < len(raw5) and run < 263 and (raw5[pos + run] & 0x1F) == value:
                run += 1
            if run <= 7:
                out.append((run << 5) | value)
            else:
                out.append(value)
                out.append(run - 8)
            pos += run
            tokens += 1
        out[control_pos] = 0
    return bytes(out)


def _mf_decode_sff2_record_to_png_bytes(path: Path, info: SffInfo, record: Sff2StandardRecord) -> Tuple[bytes, str]:  # type: ignore[no-redef]
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
    # Direct or wrapped image payload recovery.
    candidates = [blob]
    for candidate in (blob, blob[4:] if len(blob) >= 4 else b''):
        try:
            dec = _mf_zlib.decompress(candidate)
            if dec:
                candidates.append(dec)
        except Exception:
            pass
    for candidate in candidates:
        if candidate.startswith(b'\x89PNG\r\n\x1a\n'):
            return candidate, 'direct/zlib PNG payload'
        if candidate.startswith(b'\x0A'):
            try:
                from PIL import Image  # type: ignore
                img = Image.open(_MFBytesIO(candidate)).convert('RGBA')
                buf = _MFBytesIO()
                img.save(buf, format='PNG')
                return buf.getvalue(), 'direct/zlib PCX payload converted to PNG'
            except Exception:
                return candidate, 'direct/zlib PCX payload raw'
    # PNG8/24/32 should normally be a direct PNG payload; try Pillow if signature was not at byte zero.
    if record.format_code in {10, 11, 12}:
        try:
            from PIL import Image  # type: ignore
            img = Image.open(_MFBytesIO(blob)).convert('RGBA')
            buf = _MFBytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue(), SFF2_FORMAT_NAMES.get(record.format_code, 'png')
        except Exception:
            pass
    expected = max(0, int(record.width) * int(record.height))
    payload = _mf_strip_size_prefix(blob, expected) if record.format_code == 0 else blob
    if record.format_code == 0:
        if record.color_depth == 24 and len(payload) >= expected * 3:
            from PIL import Image  # type: ignore
            img = Image.frombytes('RGB', (record.width, record.height), payload[:expected * 3]).convert('RGBA')
            buf = _MFBytesIO(); img.save(buf, format='PNG')
            return buf.getvalue(), 'raw24'
        if record.color_depth == 32 and len(payload) >= expected * 4:
            from PIL import Image  # type: ignore
            img = Image.frombytes('RGBA', (record.width, record.height), payload[:expected * 4])
            buf = _MFBytesIO(); img.save(buf, format='PNG')
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


def _mf_png_payload_for_source(image_path: Path) -> Tuple[bytes, int, int]:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required to build SFF2 PNG payloads. Install with: pip install Pillow') from exc
    img = Image.open(image_path).convert('RGBA')
    buf = _MFBytesIO()
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


def build_sff_v2_from_manifest(manifest_path: Path, out_path: Path, *, compression: str = 'png32') -> SffInfo:  # type: ignore[no-redef]
    """Build a common-table SFF2 v2.1 candidate from a MugenForge sprite manifest.

    Supported writer modes: png32, raw8, rle8, rle5, and lz5. The function returns
    a parsed SffInfo and refuses missing files/corrupt rows instead of guessing.
    """
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
    header[12:16] = bytes([0, 1, 0, 2])  # SFF v2.1-style raw bytes.
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

# Friendly alias used by some backend/UI code.
build_sff_v2_png_from_manifest = build_sff_v2_from_manifest

# Final v5.5.1 SFF reader/export binding. This comes after all compatibility
# sections so current imports use the corrected standard-table parser/decoders.

def read_sff(path: Path, max_sprites: int = 20000) -> SffInfo:  # type: ignore[no-redef]
    path = Path(path)
    data = path.read_bytes()
    base = _mf_read_sff_v1_reader(path, max_sprites=max_sprites)
    if len(data) < 68 or data[:12] != SFF_SIGNATURE:
        return base
    meta, records, palettes, warnings = _mf_parse_sff2_standard(data)
    if not records:
        base.v2_metadata.update({'sff2_standard_probe': meta, 'sff2_standard_warnings': warnings})
        return base
    info = SffInfo(
        path=path,
        version=tuple(data[12:16]),
        sprite_count=len(records),
        group_count=len({r.group for r in records}),
        first_subfile_offset=int(meta.get('sprite_offset') or 0),
        subheader_size=28,
        palette_type=2,
        warnings=_uniq_list(warnings),
        variant='sff2-standard',
        is_supported_for_extraction=any(r.format_code in {0, 2, 3, 4, 10, 11, 12} and 'invalid' not in r.note for r in records),
        v2_metadata={
            'sff2_standard': meta,
            'sff2_records': [r.to_dict() for r in records[:max_sprites]],
            'sff2_record_by_index': {str(r.index): r.to_dict() for r in records[:max_sprites]},
            'sff2_palettes': [p.to_dict() for p in palettes],
            'sff2_supported_codecs': ['raw8/raw24/raw32', 'rle8', 'rle5', 'lz5', 'png8/png24/png32', 'direct/zlib pcx/png recovery'],
        },
    )
    for r in records[:max_sprites]:
        info.sprites.append(SffSprite(
            index=r.index,
            group=r.group,
            image=r.image,
            x=r.axis_x,
            y=r.axis_y,
            length=r.data_length,
            data_offset=r.payload_offset,
            next_offset=0,
            same_palette=r.palette_index,
            format_hint=r.format_name,
            comment=_mf_json.dumps(r.to_dict(), separators=(',', ':')),
            raw_header_offset=r.table_offset,
        ))
    return info


def export_all_sprites(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:  # type: ignore[no-redef]
    info = read_sff(path)
    outputs: List[Path] = []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for sprite in info.sprites[:max_count or len(info.sprites)]:
        try:
            if info.variant == 'sff2-standard' or sprite.format_hint in {'pcx', 'png'}:
                outputs.append(export_sprite(path, sprite, out_dir))
        except Exception:
            if info.variant == 'sff2-standard' and sprite.length > 0:
                raw = out_dir / f'g{sprite.group:04d}_i{sprite.image:04d}_idx{sprite.index:05d}_{sprite.format_hint}_decode_failed.bin'
                data = Path(path).read_bytes()
                raw.write_bytes(data[sprite.data_offset:sprite.data_offset + sprite.length])
                outputs.append(raw)
    return outputs

# ---------------------------------------------------------------------------
# v5.5.2 decode/export public API corrections.
# The earlier parse/write path already supported common SFF2 format codes; these
# final wrappers expose the RLE5/LZ5 decode paths through decode_sff2_image and
# export_sff2_decoded_images as well.

_decode_sff2_image_v551 = decode_sff2_image

def decode_sff2_image(path: _Path, record: Sff2ImageRecord, *, info: Optional[Sff2StandardInfo] = None):  # type: ignore[no-redef]
    try:
        return _decode_sff2_image_v551(path, record, info=info)
    except ValueError as original_exc:
        if int(getattr(record, 'image_format', -999)) not in {3, 4}:
            raise
        try:
            from PIL import Image  # type: ignore
        except Exception as exc:
            raise RuntimeError('Pillow is required for SFF2 image decode/export. Install with: pip install Pillow') from exc
        path = _Path(path)
        data = path.read_bytes()
        info = info or parse_sff2_standard(path)
        payload = data[record.data_offset:record.data_offset + record.data_length]
        expected = max(0, int(record.width) * int(record.height))
        if record.image_format == 3:
            indices = _mf_decode_ele_rle5(payload, expected)
            mode = 'rle5'
        elif record.image_format == 4:
            indices = _mf_decode_ele_lz5(payload, expected)
            mode = 'lz5'
        else:
            raise original_exc
        if len(indices) < expected:
            raise ValueError(f'SFF2 {mode} decoder produced {len(indices)} bytes, expected {expected}.') from original_exc
        colors = _sff2_palette_rgba(data, info, record.palette_index)
        rgba = bytearray()
        for idx in indices[:expected]:
            rgba.extend(colors[int(idx) & 0xFF])
        return Image.frombytes('RGBA', (record.width, record.height), bytes(rgba))


def export_sff2_decoded_images(path: _Path, out_dir: _Path, *, include_raw_payloads: bool = True) -> List[_Path]:  # type: ignore[no-redef]
    path = _Path(path)
    out_dir = _Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = parse_sff2_standard(path)
    outputs: List[_Path] = []
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

# Palette-record compatibility patch: later compatibility modules define a
# Sff2PaletteRecord class with `color_count/link_index/data_base`; adapt the
# v5.5.1 parser and metadata exporter to that shape.
_mf_parse_sff2_standard_v551_prev = _mf_parse_sff2_standard

def _sff2_palette_record_to_dict_v551(self) -> Dict[str, Any]:
    colors = getattr(self, 'colors', []) or []
    return {
        'index': int(getattr(self, 'index', 0)),
        'group': int(getattr(self, 'group', 0)),
        'item': int(getattr(self, 'item', 0)),
        'num_colors': int(getattr(self, 'num_colors', getattr(self, 'color_count', 0))),
        'color_count': int(getattr(self, 'color_count', getattr(self, 'num_colors', 0))),
        'link_index': int(getattr(self, 'link_index', getattr(self, 'index', 0))),
        'data_offset': int(getattr(self, 'data_offset', 0)),
        'data_length': int(getattr(self, 'data_length', 0)),
        'table_offset': int(getattr(self, 'table_offset', 0)),
        'data_base': int(getattr(self, 'data_base', 0)),
        'colors': [{'index': i, 'r': int(r), 'g': int(g), 'b': int(b)} for i, (r, g, b) in enumerate(colors[:256])],
    }

try:
    Sff2PaletteRecord.to_dict = _sff2_palette_record_to_dict_v551  # type: ignore[attr-defined]
except Exception:
    pass


def _mf_parse_sff2_standard(data: bytes) -> Tuple[Dict[str, Any], List[Sff2StandardRecord], List[Sff2PaletteRecord], List[str]]:  # type: ignore[no-redef]
    meta, records, _bad_palettes, warnings = _mf_parse_sff2_standard_v551_prev(data)
    warnings = [w for w in warnings if 'Sff2PaletteRecord.__init__' not in str(w)]
    palettes: List[Sff2PaletteRecord] = []
    palette_offset = int(meta.get('palette_offset') or 0)
    palette_total = int(meta.get('palette_total') or 0)
    ldata_offset = int(meta.get('ldata_offset') or 0)
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
                try:
                    setattr(pal, 'colors', colors)
                except Exception:
                    pass
                palettes.append(pal)
            except Exception as exc:
                warnings.append(f'Could not parse SFF2 palette record {idx}: {exc}')
                break
    return meta, records, palettes, warnings
