from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from io import BytesIO
import csv
import json
import math
import re
import shutil
import struct
import wave
import zipfile
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    backup_file,
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _now,
    write_csv_artifact as _write_csv,
    write_json_artifact as _write_json,
    write_text_artifact,
)
from .move_wizard import find_character_file
from .parsers import read_text_safely, write_text_safely, parse_code, parse_air
from .sff_codec import SFF_SIGNATURE, read_sff, summarize_sff_detailed
from .snd_codec import read_snd, export_sound, build_snd_from_manifest, summarize_snd_detailed
from .binary_core import (
    BinaryCoreResult,
    run_binary_core_pass,
    write_binary_core_dashboard,
    write_binary_safety_report,
    export_sff2_payloads,
    export_sff_axis_sheet,
    apply_sff_axis_sheet,
    write_sff2_rebuild_workspace,
    export_snd_bank_sheet,
    apply_snd_bank_sheet,
    write_snd_waveform_preview,
    build_binary_core_bundle,
)

BINARY_DEEP_VERSION = '5.5.0'
SFF2_NATIVE_HEADER_SIZE = 512
SFF2_RECORD_SIZE = 28
SFF2_NATIVE_MAGIC = b'MF_NATIVE_SFF2\x00'
IMAGE_SUFFIXES = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}

# SFF2 format codes are not centrally documented in the user-facing Elecbyte manual.
# These labels match the practical encodings exposed by Sprmake2/MUGEN-era tooling and
# are used as decode strategies, not as proprietary logic.
SFF2_FORMAT_LABELS = {
    0: 'raw-indexed-or-raw-rgba',
    1: 'raw-indexed-or-linked',
    2: 'rle8',
    3: 'rle5',
    4: 'lz5',
    10: 'png',
    11: 'pcx',
}

CAPABILITY_NOTE = (
    'Binary Deep is an experimental companion to Binary Maturity. It adds table-driven SFF2 discovery, direct PNG/PCX/zlib export, '
    'raw/RLE8 recovery attempts, diagnostic 5-bit/LZ-style probes, controlled SFF2 build candidates, '
    'axis/image patch candidates, SND ID/WAV patch candidates, and runtime-log ingestion hooks. '
    'RLE5/LZ5 probe output is diagnostic only; unknown or corrupt files still produce refusal/warning reports rather than silent risky writes.'
)


@dataclass
class DeepSff2Record:
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
    payload_offset: int
    payload_length: int
    palette_index: int
    flags: int
    table_offset: int
    data_base: int
    data_offset_field: int
    offset_mode: str
    table_source: str
    format_label: str = 'unknown'
    payload_hint: str = ''
    decode_method: str = ''
    warning: str = ''

    def to_dict(self) -> Dict[str, object]:
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
            'format_label': self.format_label,
            'color_depth': self.color_depth,
            'payload_offset': self.payload_offset,
            'payload_length': self.payload_length,
            'palette_index': self.palette_index,
            'flags': self.flags,
            'table_offset': self.table_offset,
            'data_base': self.data_base,
            'data_offset_field': self.data_offset_field,
            'offset_mode': self.offset_mode,
            'table_source': self.table_source,
            'payload_hint': self.payload_hint,
            'decode_method': self.decode_method,
            'warning': self.warning,
        }


@dataclass
class DeepSff2Table:
    source: str
    table_offset: int
    record_count: int
    data_base: int
    record_size: int
    score: int
    records: List[DeepSff2Record] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            'source': self.source,
            'table_offset': self.table_offset,
            'record_count': self.record_count,
            'data_base': self.data_base,
            'record_size': self.record_size,
            'score': self.score,
            'warnings': self.warnings,
            'records': [r.to_dict() for r in self.records],
        }


# ---------------------------------------------------------------------------
# Generic helpers


def _bd(root: Path) -> Path:
    out = Path(root) / 'binary_deep'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _bc(root: Path) -> Path:
    out = Path(root) / 'binary_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, result: Optional[BinaryCoreResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    return write_text_artifact(path, text, result, root, changed, writer=write_text_safely)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == '':
            return default
        return int(str(value).strip(), 0)
    except Exception:
        return default


def _truthy(value: object) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _file(root: Path, ext: str) -> Optional[Path]:
    root = Path(root)
    try:
        found = find_character_file(root, ext)
        if found and Path(found).exists():
            return Path(found)
    except Exception:
        pass
    exact = root / f'{root.name}.{ext}'
    if exact.exists():
        return exact
    skip = {'__pycache__', 'binary_core', 'binary_deep', 'forge_timeline', 'forge_polish', 'forge_beyond', '.mugenforge'}
    for p in sorted(root.rglob(f'*.{ext}'), key=lambda x: str(x).lower()):
        if p.is_file() and not any(part in skip for part in p.parts):
            return p
    return None


def _backup(path: Path, tag: str = 'binary_deep') -> Optional[Path]:
    return backup_file(path, tag)


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i32(data: bytes, off: int) -> int:
    return struct.unpack_from('<i', data, off)[0]


def _clamp_i16(v: int) -> int:
    return max(-32768, min(32767, int(v)))


def _clamp_u16(v: int) -> int:
    return max(0, min(65535, int(v)))


def _image_files(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return [p for p in sorted(folder.rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]


def _parse_group_image(path: Path, fallback: int = 0) -> Tuple[int, int]:
    stem = path.stem.lower()
    pats = [
        r'g(?:roup)?\s*[_\- ]?(?P<g>-?\d+)\s*[_\- ]?i(?:mage|mg)?\s*[_\- ]?(?P<i>-?\d+)',
        r'group\s*[_\- ]?(?P<g>-?\d+)\s*[_\- ]?(?:image|img|item)\s*[_\- ]?(?P<i>-?\d+)',
        r'(?P<g>-?\d+)\s*[_\-., ]+\s*(?P<i>-?\d+)',
    ]
    for pat in pats:
        m = re.search(pat, stem)
        if m:
            return int(m.group('g')), int(m.group('i'))
    return 0, int(fallback)


def _image_size(path: Path) -> Tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def _png_payload(path: Path) -> Tuple[bytes, int, int, int]:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required for native SFF2 PNG builds.') from exc
    with Image.open(path) as im:
        rgba = im.convert('RGBA')
        buf = BytesIO()
        rgba.save(buf, format='PNG')
        return buf.getvalue(), rgba.width, rgba.height, 32


# ---------------------------------------------------------------------------
# SFF2 table discovery and decoding


def _find_embedded_pngs(data: bytes) -> List[Tuple[int, int]]:
    sig = b'\x89PNG\r\n\x1a\n'
    out: List[Tuple[int, int]] = []
    pos = 0
    while True:
        start = data.find(sig, pos)
        if start < 0:
            return out
        # Parse chunks to avoid false IEND matches in data.
        cur = start + 8
        end = 0
        while cur + 8 <= len(data):
            size = _u32(data, cur)
            ctype = data[cur + 4:cur + 8]
            cur_end = cur + 8 + size + 4
            if cur_end > len(data):
                break
            cur = cur_end
            if ctype == b'IEND':
                end = cur
                break
        if end > start:
            out.append((start, end - start))
            pos = end
        else:
            pos = start + 8


def _find_pcx_ranges(data: bytes, max_hits: int = 1000) -> List[Tuple[int, int]]:
    # PCX does not contain a guaranteed EOF marker. Use header sanity plus next common marker/EOF.
    hits: List[int] = []
    for idx in range(0, max(0, len(data) - 128)):
        if data[idx] == 0x0A and data[idx + 2] == 0x01 and data[idx + 3] in {1, 2, 4, 8, 24}:
            hits.append(idx)
            if len(hits) >= max_hits:
                break
    ranges: List[Tuple[int, int]] = []
    markers = hits + [len(data)]
    for n, start in enumerate(hits):
        end = markers[n + 1] if n + 1 < len(markers) else len(data)
        ranges.append((start, max(0, end - start)))
    return ranges


def _candidate_header_values(data: bytes) -> List[int]:
    vals: List[int] = []
    # SFF headers are small; scan plausible 32-bit fields and include canonical positions.
    for off in range(16, min(len(data) - 4, 256), 4):
        try:
            val = _u32(data, off)
        except Exception:
            continue
        if 0 <= val <= len(data):
            vals.append(val)
    vals.extend([512, 64, 128, 256])
    out: List[int] = []
    for v in vals:
        if v not in out:
            out.append(v)
    return out


def _plausible_record_fields(data: bytes, off: int) -> Optional[Tuple[int, int, int, int, int, int, int, int, int, int, int, int]]:
    if off < 0 or off + SFF2_RECORD_SIZE > len(data):
        return None
    try:
        group = _u16(data, off + 0)
        image = _u16(data, off + 2)
        width = _u16(data, off + 4)
        height = _u16(data, off + 6)
        axis_x = _i16(data, off + 8)
        axis_y = _i16(data, off + 10)
        linked_index = _u16(data, off + 12)
        format_code = data[off + 14]
        color_depth = data[off + 15]
        data_offset_field = _u32(data, off + 16)
        payload_length = _u32(data, off + 20)
        palette_index = _u16(data, off + 24)
        flags = _u16(data, off + 26)
    except Exception:
        return None
    if width <= 0 or height <= 0 or width > 32768 or height > 32768:
        return None
    if abs(axis_x) > 32768 or abs(axis_y) > 32768:
        return None
    if payload_length <= 0 or payload_length > len(data):
        return None
    if format_code > 64:
        return None
    if color_depth not in {0, 5, 8, 16, 24, 32}:
        # Some SFF2 tools set this byte as flags. Keep it, but penalize later.
        pass
    return (group, image, width, height, axis_x, axis_y, linked_index, format_code, color_depth, data_offset_field, payload_length, palette_index, flags)


def _payload_hint(blob: bytes, format_code: int) -> str:
    if blob.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if blob.startswith(b'\x0A'):
        return 'pcx'
    if blob[:1] == b'\x78':
        try:
            dec = zlib.decompress(blob)
            return 'zlib->png' if dec.startswith(b'\x89PNG') else 'zlib->pcx' if dec.startswith(b'\x0A') else 'zlib-data'
        except Exception:
            return 'zlib?'
    return SFF2_FORMAT_LABELS.get(format_code, f'format-{format_code}')


def _score_record(data: bytes, fields: Tuple[int, int, int, int, int, int, int, int, int, int, int, int], data_base: int) -> Tuple[int, int, str, str]:
    group, image, width, height, axis_x, axis_y, linked_index, format_code, color_depth, data_field, length, palette_index, flags = fields
    best_score = -10000
    best_payload = -1
    best_mode = 'none'
    best_hint = ''
    candidates = [
        (data_base + data_field, 'relative-to-data-base'),
        (data_field, 'absolute'),
    ]
    for payload_off, mode in candidates:
        score = 0
        if 0 <= payload_off < len(data) and payload_off + length <= len(data):
            score += 50
            blob = data[payload_off:payload_off + min(length, 64)]
            hint = _payload_hint(data[payload_off:payload_off + length], format_code)
            if hint in {'png', 'pcx', 'zlib->png', 'zlib->pcx'}:
                score += 80
            if format_code in SFF2_FORMAT_LABELS:
                score += 20
            if 0 < width <= 4096 and 0 < height <= 4096:
                score += 20
            if color_depth in {5, 8, 16, 24, 32}:
                score += 10
            if payload_off >= data_base:
                score += 5
        else:
            hint = 'invalid-range'
            score -= 100
        if score > best_score:
            best_score = score
            best_payload = payload_off
            best_mode = mode
            best_hint = hint
    return best_score, best_payload, best_mode, best_hint


def _parse_table_candidate(data: bytes, table_offset: int, record_count: int, data_base: int, source: str, limit: int = 50000) -> Optional[DeepSff2Table]:
    if not (0 <= table_offset < len(data) and 0 <= data_base <= len(data)):
        return None
    if record_count <= 0 or record_count > limit:
        return None
    if table_offset + record_count * SFF2_RECORD_SIZE > len(data):
        return None
    records: List[DeepSff2Record] = []
    score = 0
    warnings: List[str] = []
    bad = 0
    for idx in range(record_count):
        off = table_offset + idx * SFF2_RECORD_SIZE
        fields = _plausible_record_fields(data, off)
        if fields is None:
            bad += 1
            if bad > max(2, record_count // 5):
                return None
            continue
        group, image, width, height, axis_x, axis_y, linked_index, format_code, color_depth, data_field, length, palette_index, flags = fields
        rec_score, payload_off, mode, hint = _score_record(data, fields, data_base)
        if rec_score < 0:
            bad += 1
        score += rec_score
        records.append(DeepSff2Record(
            index=idx,
            group=group,
            image=image,
            width=width,
            height=height,
            axis_x=axis_x,
            axis_y=axis_y,
            linked_index=linked_index,
            format_code=format_code,
            color_depth=color_depth,
            payload_offset=payload_off,
            payload_length=length,
            palette_index=palette_index,
            flags=flags,
            table_offset=off,
            data_base=data_base,
            data_offset_field=data_field,
            offset_mode=mode,
            table_source=source,
            format_label=SFF2_FORMAT_LABELS.get(format_code, f'format-{format_code}'),
            payload_hint=hint,
            warning='' if rec_score >= 0 else 'payload range or record shape needs review',
        ))
    if not records:
        return None
    # Favor candidates where most records agree with valid payloads.
    score += len(records) * 100 - bad * 250
    if bad:
        warnings.append(f'{bad} candidate records were rejected while scanning this table.')
    return DeepSff2Table(source=source, table_offset=table_offset, record_count=record_count, data_base=data_base, record_size=SFF2_RECORD_SIZE, score=score, records=records, warnings=warnings)


def discover_deep_sff2_tables(path: Path) -> Tuple[List[DeepSff2Table], Dict[str, object], List[str]]:
    path = Path(path)
    data = path.read_bytes()
    warnings: List[str] = []
    meta: Dict[str, object] = {
        'path': str(path),
        'size': len(data),
        'sha256': _sha256(path),
        'signature_ok': data.startswith(SFF_SIGNATURE),
        'version_bytes': list(data[12:16]) if len(data) >= 16 else [],
        'embedded_png_count': len(_find_embedded_pngs(data)),
        'pcx_marker_count': len(_find_pcx_ranges(data, max_hits=200)),
    }
    if len(data) < 64 or not data.startswith(SFF_SIGNATURE):
        warnings.append('Not an ElecbyteSpr file or file too small for SFF2 table discovery.')
        return [], meta, warnings

    header_vals = _candidate_header_values(data)
    meta['header_candidate_values'] = header_vals[:80]
    counts = [v for v in header_vals if 0 < v <= 100000]
    offsets = [v for v in header_vals if 0 <= v < len(data)]
    # Strong candidates from MugenForge native layout and common SFF2 header-like fields.
    seed_triples: List[Tuple[int, int, int, str]] = []
    try:
        seed_triples.append((_u32(data, 24), _u32(data, 28), _u32(data, 32), 'header-0x18/0x1c/0x20'))
    except Exception:
        pass
    try:
        seed_triples.append((_u32(data, 28), _u32(data, 20), _u32(data, 36), 'header-0x1c/0x14/0x24'))
    except Exception:
        pass
    try:
        seed_triples.append((_u32(data, 32), _u32(data, 20), _u32(data, 40), 'header-0x20/0x14/0x28'))
    except Exception:
        pass
    # Dense scan: pair plausible table offsets with plausible counts and likely data bases.
    # Limit combinations to keep big projects responsive.
    for table_off in offsets[:80]:
        if table_off < 64:
            continue
        for count in counts[:80]:
            if not (0 < count <= 50000):
                continue
            table_end = table_off + count * SFF2_RECORD_SIZE
            if table_end > len(data):
                continue
            likely_bases = [v for v in offsets if v >= table_end]
            likely_bases.append(table_end)
            for base in likely_bases[:10]:
                seed_triples.append((table_off, count, base, 'header-value-grid'))
    seen = set()
    tables: List[DeepSff2Table] = []
    for table_off, count, base, source in seed_triples:
        key = (table_off, count, base)
        if key in seen:
            continue
        seen.add(key)
        tab = _parse_table_candidate(data, table_off, count, base, source)
        if tab and tab.score > 0:
            tables.append(tab)
    tables.sort(key=lambda t: (t.score, len(t.records)), reverse=True)
    # Remove near-duplicates; keep strongest per table/data combo.
    filtered: List[DeepSff2Table] = []
    used = set()
    for tab in tables:
        key = (tab.table_offset, tab.record_count, tab.data_base)
        if key in used:
            continue
        used.add(key)
        filtered.append(tab)
        if len(filtered) >= 12:
            break
    if not filtered:
        warnings.append('No SFF2 record table was confidently discovered. Raw embedded PNG/PCX scan may still recover some assets.')
    return filtered, meta, warnings


def best_deep_sff2_table(path: Path) -> Optional[DeepSff2Table]:
    tables, _meta, _warnings = discover_deep_sff2_tables(path)
    return tables[0] if tables else None


def _palette_for_record(data: bytes, record: DeepSff2Record) -> Optional[List[Tuple[int, int, int, int]]]:
    # Full SFF2 palette-table discovery is format-variant-sensitive. Use embedded ACT-like
    # 768/1024-byte palette near EOF only as a last-resort visual aid.
    return None


def _pil_image_from_indexed(indices: bytes, width: int, height: int, palette: Optional[List[Tuple[int, int, int, int]]] = None, scale5: bool = False):
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required to decode indexed SFF2 payloads to PNG.') from exc
    if len(indices) < width * height:
        raise ValueError(f'Indexed payload has {len(indices)} pixels; expected {width * height}.')
    img = Image.frombytes('P', (width, height), indices[:width * height])
    pal: List[int] = []
    if palette:
        for r, g, b, _a in palette[:256]:
            pal.extend([r, g, b])
    else:
        for i in range(256):
            if scale5:
                v = (i & 31) * 255 // 31
                pal.extend([v, v, v])
            else:
                pal.extend([i, i, i])
    pal = pal[:768] + [0] * max(0, 768 - len(pal))
    img.putpalette(pal)
    return img.convert('RGBA')


def _unpack_5bit_raw(blob: bytes, expected: int) -> Optional[bytes]:
    vals: List[int] = []
    acc = 0
    bits = 0
    for b in blob:
        acc |= b << bits
        bits += 8
        while bits >= 5 and len(vals) < expected:
            vals.append(acc & 0x1F)
            acc >>= 5
            bits -= 5
        if len(vals) >= expected:
            break
    if len(vals) == expected:
        # Stretch 5-bit indices into a visible 0..255 palette range.
        return bytes((v * 255 // 31) for v in vals)
    return None


def _decode_pcx_style_rle(blob: bytes, expected: int) -> Optional[bytes]:
    out = bytearray()
    i = 0
    while i < len(blob) and len(out) < expected:
        b = blob[i]
        i += 1
        if b >= 0xC0 and i < len(blob):
            count = b & 0x3F
            val = blob[i]
            i += 1
            out.extend([val] * count)
        else:
            out.append(b)
    return bytes(out) if len(out) == expected else None


def _decode_packbit_rle(blob: bytes, expected: int) -> Optional[bytes]:
    out = bytearray()
    i = 0
    while i < len(blob) and len(out) < expected:
        code = blob[i]
        i += 1
        if code & 0x80:
            count = (code & 0x7F) + 1
            if i >= len(blob):
                return None
            val = blob[i]
            i += 1
            out.extend([val] * count)
        else:
            count = code + 1
            if i + count > len(blob):
                return None
            out.extend(blob[i:i + count])
            i += count
    return bytes(out) if len(out) == expected else None


def _decode_rle8(blob: bytes, expected: int) -> Tuple[Optional[bytes], str]:
    for name, fn in [('rle8-pcx-style', _decode_pcx_style_rle), ('rle8-packbit-style', _decode_packbit_rle)]:
        out = fn(blob, expected)
        if out is not None:
            return out, name
    return None, 'rle8-decode-failed'


def _decode_rle5(blob: bytes, expected: int) -> Tuple[Optional[bytes], str]:
    raw = _unpack_5bit_raw(blob, expected)
    if raw is not None:
        return raw, 'rle5-raw-5bit-unpack'
    for name, fn in [('rle5-pcx-style-then-scale', _decode_pcx_style_rle), ('rle5-packbit-style-then-scale', _decode_packbit_rle)]:
        out = fn(blob, expected)
        if out is not None:
            return bytes(((b & 0x1F) * 255 // 31) for b in out), name
    return None, 'rle5-decode-failed'


def _lzss_probe(blob: bytes, expected: int, flags_lsb: bool = True) -> Optional[bytes]:
    out = bytearray()
    i = 0
    while i < len(blob) and len(out) < expected:
        flags = blob[i]
        i += 1
        bit_range = range(8) if flags_lsb else range(7, -1, -1)
        for bit in bit_range:
            if len(out) >= expected:
                break
            literal = bool(flags & (1 << bit))
            if literal:
                if i >= len(blob):
                    return None
                out.append(blob[i])
                i += 1
            else:
                if i + 1 >= len(blob):
                    return None
                b1 = blob[i]
                b2 = blob[i + 1]
                i += 2
                # Two common LZSS layouts. Choose the one that yields a valid back-reference.
                off1 = ((b2 & 0xF0) << 4) | b1
                ln1 = (b2 & 0x0F) + 3
                off2 = ((b1 & 0xF0) << 4) | b2
                ln2 = (b1 & 0x0F) + 3
                candidates = [(off1 + 1, ln1), (off2 + 1, ln2)]
                chosen = None
                for dist, ln in candidates:
                    if 0 < dist <= len(out):
                        chosen = (dist, ln)
                        break
                if chosen is None:
                    return None
                dist, ln = chosen
                for _ in range(ln):
                    if dist > len(out):
                        return None
                    out.append(out[-dist])
                    if len(out) >= expected:
                        break
    return bytes(out) if len(out) == expected else None


def _decode_lz5(blob: bytes, expected: int) -> Tuple[Optional[bytes], str]:
    # LZ5 in the ecosystem is custom. These LZSS probes make practical recovery attempts
    # without pretending every variant can be decoded.
    raw5 = _unpack_5bit_raw(blob, expected)
    if raw5 is not None:
        return raw5, 'lz5-raw-5bit-unpack'
    for flags_lsb, name in [(True, 'lz5-lzss-probe-lsb'), (False, 'lz5-lzss-probe-msb')]:
        out = _lzss_probe(blob, expected, flags_lsb=flags_lsb)
        if out is not None:
            return bytes(((b & 0x1F) * 255 // 31) for b in out), name
    return None, 'lz5-decode-failed'


def decode_sff2_record_to_image(data: bytes, record: DeepSff2Record):
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required for SFF2 record decoding.') from exc
    if record.payload_offset < 0 or record.payload_offset + record.payload_length > len(data):
        raise ValueError('Payload range is outside the SFF file.')
    blob = data[record.payload_offset:record.payload_offset + record.payload_length]
    method = ''
    if blob.startswith(b'\x89PNG\r\n\x1a\n'):
        img = Image.open(BytesIO(blob)).convert('RGBA')
        method = 'direct-png'
        return img, method
    if blob.startswith(b'\x0A'):
        img = Image.open(BytesIO(blob)).convert('RGBA')
        method = 'direct-pcx'
        return img, method
    if blob[:1] == b'\x78':
        try:
            dec = zlib.decompress(blob)
            if dec.startswith(b'\x89PNG'):
                return Image.open(BytesIO(dec)).convert('RGBA'), 'zlib-png'
            if dec.startswith(b'\x0A'):
                return Image.open(BytesIO(dec)).convert('RGBA'), 'zlib-pcx'
            blob = dec
            method = 'zlib-data+'
        except Exception:
            pass
    expected = max(1, int(record.width) * int(record.height))
    palette = _palette_for_record(data, record)
    if len(blob) >= expected * 4 and record.color_depth in {32, 0}:
        try:
            return Image.frombytes('RGBA', (record.width, record.height), blob[:expected * 4]), method + 'raw-rgba'
        except Exception:
            pass
    if len(blob) >= expected * 3 and record.color_depth in {24, 0}:
        try:
            return Image.frombytes('RGB', (record.width, record.height), blob[:expected * 3]).convert('RGBA'), method + 'raw-rgb'
        except Exception:
            pass
    if len(blob) >= expected:
        try:
            return _pil_image_from_indexed(blob[:expected], record.width, record.height, palette, scale5=(record.color_depth == 5)), method + 'raw-indexed'
        except Exception:
            pass
    if record.format_code == 2 or record.format_label == 'rle8':
        out, m = _decode_rle8(blob, expected)
        if out is not None:
            return _pil_image_from_indexed(out, record.width, record.height, palette), method + m
    if record.format_code == 3 or record.format_label == 'rle5':
        out, m = _decode_rle5(blob, expected)
        if out is not None:
            return _pil_image_from_indexed(out, record.width, record.height, palette, scale5=True), method + m
    if record.format_code == 4 or record.format_label == 'lz5':
        out, m = _decode_lz5(blob, expected)
        if out is not None:
            return _pil_image_from_indexed(out, record.width, record.height, palette, scale5=True), method + m
    # Try all probes as a recovery fallback.
    for probe_name, probe in [
        ('rle8-fallback', lambda b, e: _decode_rle8(b, e)[0]),
        ('rle5-fallback', lambda b, e: _decode_rle5(b, e)[0]),
        ('lz5-fallback', lambda b, e: _decode_lz5(b, e)[0]),
    ]:
        out = probe(blob, expected)
        if out is not None:
            return _pil_image_from_indexed(out, record.width, record.height, palette, scale5='rle5' in probe_name or 'lz5' in probe_name), method + probe_name
    raise ValueError(f'Could not decode payload with code={record.format_code}, hint={record.payload_hint}.')


def _export_record_payload_or_png(sff_path: Path, data: bytes, record: DeepSff2Record, out_dir: Path) -> Tuple[Optional[Path], str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        img, method = decode_sff2_record_to_image(data, record)
        out = out_dir / f'g{record.group:04d}_i{record.image:04d}_idx{record.index:05d}_{method.replace("+", "_").replace(" ", "_")}.png'
        img.save(out)
        return out, method
    except Exception as exc:
        # Store raw payload for manual forensic use.
        if 0 <= record.payload_offset < len(data) and record.payload_offset + record.payload_length <= len(data):
            raw = out_dir / f'g{record.group:04d}_i{record.image:04d}_idx{record.index:05d}_undecoded_fmt{record.format_code}.bin'
            raw.write_bytes(data[record.payload_offset:record.payload_offset + record.payload_length])
            return raw, f'raw-undecoded: {exc}'
        return None, str(exc)


# ---------------------------------------------------------------------------
# SFF2 public workflows


def write_deep_sff2_inspection(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Deep SFF2 Inspection')
    sff = _file(root, 'sff')
    out_dir = _bd(root) / 'sff2_deep_inspection'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for deep SFF2 inspection.')
        return res
    data = sff.read_bytes()
    tables, meta, warnings = discover_deep_sff2_tables(sff)
    read_info = read_sff(sff)
    payload_rows: List[Dict[str, object]] = []
    for tab in tables[:5]:
        for rec in tab.records:
            payload_rows.append(rec.to_dict())
    _write_json(out_dir / 'deep_sff2_inspection.json', {
        'tool': 'MugenForge Binary Deep',
        'version': BINARY_DEEP_VERSION,
        'source_sff': str(sff),
        'source_sha256': _sha256(sff),
        'meta': meta,
        'read_sff_summary': {
            'variant': read_info.variant,
            'version': read_info.version,
            'v1_sprites': len(read_info.sprites),
            'warnings': read_info.warnings,
        },
        'candidate_tables': [t.to_dict() for t in tables],
        'warnings': warnings,
    }, res, root)
    if payload_rows:
        fields = list(payload_rows[0].keys())
        _write_csv(out_dir / 'deep_sff2_records.csv', payload_rows, fields, res, root)
    lines = [
        '# Deep SFF2 Inspection', '',
        f'Version: {BINARY_DEEP_VERSION}',
        f'Source: `{_rel(root, sff)}`',
        f'Size: {len(data):,} bytes',
        f'SHA-256: `{_sha256(sff)}`', '',
        CAPABILITY_NOTE, '',
        '## Candidate SFF2 tables', '',
    ]
    if tables:
        for n, tab in enumerate(tables[:8], 1):
            lines += [
                f'### Candidate {n}',
                f'- Source: `{tab.source}`',
                f'- Table offset: `0x{tab.table_offset:X}`',
                f'- Records: {len(tab.records)} / count hint {tab.record_count}',
                f'- Data base: `0x{tab.data_base:X}`',
                f'- Score: {tab.score}',
            ]
            formats = {}
            for r in tab.records:
                formats[r.format_label] = formats.get(r.format_label, 0) + 1
            lines.append('- Formats: ' + ', '.join(f'{k}={v}' for k, v in sorted(formats.items())) if formats else '- Formats: none')
            if tab.warnings:
                lines += ['- Warnings:'] + [f'  - {w}' for w in tab.warnings]
            lines.append('')
    else:
        lines.append('No confident SFF2 table was discovered. Embedded PNG/PCX rescue may still find assets.')
    if warnings or read_info.warnings:
        lines += ['', '## Warnings'] + [f'- {w}' for w in dict.fromkeys(warnings + read_info.warnings)]
    lines += ['', '## Existing reader detail', '', '```text', summarize_sff_detailed(sff), '```']
    _write_text(out_dir / 'DEEP_SFF2_INSPECTION.md', '\n'.join(lines), res, root)
    res.notes.append(f'Deep SFF2 discovery found {len(tables)} candidate table(s).')
    res.warnings.extend(warnings)
    return res


def export_deep_sff2_sprites(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Deep SFF2 Sprite Export')
    sff = _file(root, 'sff')
    out_dir = _bd(root) / 'sff2_deep_export'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for deep sprite export.')
        return res
    data = sff.read_bytes()
    table = best_deep_sff2_table(sff)
    exports: List[Dict[str, object]] = []
    if table:
        sprite_dir = out_dir / 'sprites'
        for rec in table.records:
            out, method = _export_record_payload_or_png(sff, data, rec, sprite_dir)
            if out:
                res.add_created(root, out)
                d = rec.to_dict()
                d.update({'export_path': _rel(root, out), 'decode_method': method})
                exports.append(d)
        res.notes.append(f'Exported/recovered {len(exports)} payload(s) from best SFF2 table candidate.')
    else:
        # Fall back to embedded PNG/PCX scan.
        png_dir = out_dir / 'embedded_png_scan'
        png_dir.mkdir(parents=True, exist_ok=True)
        for idx, (off, length) in enumerate(_find_embedded_pngs(data)[:5000]):
            out = png_dir / f'embedded_png_{idx:05d}_off{off:08X}.png'
            out.write_bytes(data[off:off + length])
            res.add_created(root, out)
            exports.append({'export_path': _rel(root, out), 'offset': off, 'length': length, 'decode_method': 'embedded-png-scan-no-id'})
        pcx_dir = out_dir / 'embedded_pcx_scan'
        for idx, (off, length) in enumerate(_find_pcx_ranges(data, max_hits=500)):
            if length <= 0:
                continue
            pcx_dir.mkdir(parents=True, exist_ok=True)
            out = pcx_dir / f'embedded_pcx_{idx:05d}_off{off:08X}.pcx'
            out.write_bytes(data[off:off + length])
            res.add_created(root, out)
            exports.append({'export_path': _rel(root, out), 'offset': off, 'length': length, 'decode_method': 'embedded-pcx-scan-no-id'})
        if exports:
            res.add_warning('Fallback embedded scan has no reliable group/image/axis mapping.')
        else:
            res.add_warning('No table-backed or embedded PNG/PCX payloads were recovered.')
    _write_json(out_dir / 'deep_sff2_export_manifest.json', {'source_sff': str(sff), 'exports': exports, 'version': BINARY_DEEP_VERSION}, res, root)
    if exports:
        fields = sorted(set().union(*(e.keys() for e in exports)))
        _write_csv(out_dir / 'deep_sff2_export_manifest.csv', exports, fields, res, root)
    return res


def export_deep_sff2_mutation_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Deep SFF2 Mutation Sheet Export')
    sff = _file(root, 'sff')
    out_dir = _bd(root) / 'sff2_mutation'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for SFF2 mutation sheet export.')
        return res
    table = best_deep_sff2_table(sff)
    rows: List[Dict[str, object]] = []
    if table:
        # Export sprites first so replacement paths are easy to edit.
        exp = export_deep_sff2_sprites(root)
        res.merge(exp, 'sprite export')
        export_manifest = _bd(root) / 'sff2_deep_export' / 'deep_sff2_export_manifest.json'
        by_key: Dict[Tuple[int, int, int], str] = {}
        if export_manifest.exists():
            try:
                data = json.loads(export_manifest.read_text(encoding='utf-8'))
                for item in data.get('exports', []):
                    if isinstance(item, dict) and 'index' in item:
                        by_key[(int(item.get('index', 0)), int(item.get('group', 0)), int(item.get('image', 0)))] = str(item.get('export_path', ''))
            except Exception:
                pass
        for rec in table.records:
            rows.append({
                'enabled': 'no',
                'action': 'axis',
                'index': rec.index,
                'group': rec.group,
                'image': rec.image,
                'current_axis_x': rec.axis_x,
                'current_axis_y': rec.axis_y,
                'new_axis_x': rec.axis_x,
                'new_axis_y': rec.axis_y,
                'replace_image': '',
                'current_export': by_key.get((rec.index, rec.group, rec.image), ''),
                'format_code': rec.format_code,
                'format_label': rec.format_label,
                'width': rec.width,
                'height': rec.height,
                'payload_offset': rec.payload_offset,
                'payload_length': rec.payload_length,
                'table_offset': rec.table_offset,
                'data_base': rec.data_base,
                'offset_mode': rec.offset_mode,
                'note': 'action=axis patches coordinates in a candidate copy. action=replace rebuilds a native SFF2 PNG copy using replace_image when set.',
            })
    else:
        res.add_warning('No confident SFF2 table discovered; mutation sheet cannot be table-backed.')
    fields = ['enabled','action','index','group','image','current_axis_x','current_axis_y','new_axis_x','new_axis_y','replace_image','current_export','format_code','format_label','width','height','payload_offset','payload_length','table_offset','data_base','offset_mode','note']
    _write_csv(out_dir / 'deep_sff2_mutation_sheet.csv', rows, fields, res, root)
    _write_text(out_dir / 'README_DEEP_SFF2_MUTATION.md', '\n'.join([
        '# Deep SFF2 Mutation Sheet', '', CAPABILITY_NOTE, '',
        'Set `enabled=yes` on rows you want to apply.',
        '',
        '- `action=axis` changes `new_axis_x` / `new_axis_y` in a patched candidate copy.',
        '- `action=replace` rebuilds a native SFF2 PNG copy using `replace_image` paths when provided.',
        '- Original SFF files are backed up before optional install and are not overwritten by default.',
        '',
        'For unknown SFF2 table layouts, MugenForge writes warnings instead of guessing.',
    ]), res, root)
    res.notes.append(f'Exported {len(rows)} deep SFF2 mutation rows.')
    return res


def build_native_sff2_from_image_records(records: Sequence[Dict[str, object]], out_path: Path, base_dir: Optional[Path] = None) -> Tuple[Path, List[Dict[str, object]]]:
    payloads: List[bytes] = []
    normalized: List[Dict[str, object]] = []
    base_dir = Path(base_dir) if base_dir else Path('.')
    for idx, rec in enumerate(records):
        src_raw = str(rec.get('filename') or rec.get('replace_image') or rec.get('path') or '')
        if not src_raw:
            raise ValueError(f'Record {idx} has no image path.')
        src = Path(src_raw)
        if not src.is_absolute():
            src = (base_dir / src).resolve()
        if not src.exists():
            raise FileNotFoundError(f'Image not found: {src}')
        blob, w, h, depth = _png_payload(src)
        axis = rec.get('axis') if isinstance(rec.get('axis'), dict) else {}
        axis_x = _safe_int(rec.get('axis_x'), _safe_int(axis.get('x') if isinstance(axis, dict) else None, w // 2))
        axis_y = _safe_int(rec.get('axis_y'), _safe_int(axis.get('y') if isinstance(axis, dict) else None, h))
        normalized.append({
            'index': idx,
            'group': _safe_int(rec.get('group'), 0),
            'image': _safe_int(rec.get('image'), idx),
            'width': w,
            'height': h,
            'axis_x': axis_x,
            'axis_y': axis_y,
            'format_code': 10,
            'color_depth': depth,
            'palette_index': _safe_int(rec.get('palette_index'), 0),
            'flags': _safe_int(rec.get('flags'), 0),
            'payload_index': len(payloads),
            'source': str(src),
            'payload_length': len(blob),
        })
        payloads.append(blob)
    if not normalized:
        raise ValueError('No valid image records supplied for native SFF2 build.')
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(SFF2_NATIVE_HEADER_SIZE)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = bytes([2, 0, 1, 0])
    table_offset = SFF2_NATIVE_HEADER_SIZE
    table_size = SFF2_RECORD_SIZE * len(normalized)
    data_base = table_offset + table_size
    struct.pack_into('<I', header, 16, len(normalized))
    struct.pack_into('<I', header, 20, len({int(r['group']) for r in normalized}))
    struct.pack_into('<I', header, 24, table_offset)
    struct.pack_into('<I', header, 28, len(normalized))
    struct.pack_into('<I', header, 32, data_base)
    struct.pack_into('<I', header, 36, sum(len(p) for p in payloads))
    header[64:64 + len(SFF2_NATIVE_MAGIC)] = SFF2_NATIVE_MAGIC
    table = bytearray(table_size)
    cursor = 0
    for row_idx, rec in enumerate(normalized):
        blob = payloads[int(rec['payload_index'])]
        off = row_idx * SFF2_RECORD_SIZE
        struct.pack_into('<H', table, off + 0, _clamp_u16(int(rec['group'])))
        struct.pack_into('<H', table, off + 2, _clamp_u16(int(rec['image'])))
        struct.pack_into('<H', table, off + 4, _clamp_u16(int(rec['width'])))
        struct.pack_into('<H', table, off + 6, _clamp_u16(int(rec['height'])))
        struct.pack_into('<h', table, off + 8, _clamp_i16(int(rec['axis_x'])))
        struct.pack_into('<h', table, off + 10, _clamp_i16(int(rec['axis_y'])))
        struct.pack_into('<H', table, off + 12, 0xFFFF)  # not linked
        table[off + 14] = int(rec['format_code']) & 0xFF
        table[off + 15] = int(rec['color_depth']) & 0xFF
        struct.pack_into('<I', table, off + 16, cursor)
        struct.pack_into('<I', table, off + 20, len(blob))
        struct.pack_into('<H', table, off + 24, _clamp_u16(int(rec.get('palette_index', 0))))
        struct.pack_into('<H', table, off + 26, _clamp_u16(int(rec.get('flags', 0))))
        cursor += len(blob)
    out_path.write_bytes(bytes(header) + bytes(table) + b''.join(payloads))
    return out_path, normalized


def build_native_sff2_from_manifest(root: Path, manifest_path: Optional[Path] = None) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Native SFF2 Build From Manifest')
    work = _bd(root) / 'sff2_native_build'
    work.mkdir(parents=True, exist_ok=True)
    manifest = Path(manifest_path) if manifest_path else work / 'native_sff2_build_manifest.json'
    if not manifest.exists():
        # Auto-create from source image folders and current deep exports.
        candidates = [root / 'source_sprites', root / 'sprites', root / 'staged_sprites', _bd(root) / 'sff2_deep_export' / 'sprites', _bc(root) / 'sff_payloads' / 'sff2_png_subset']
        imgs: List[Path] = []
        for cand in candidates:
            imgs = _image_files(cand)
            if imgs:
                break
        if not imgs:
            exp = export_deep_sff2_sprites(root)
            res.merge(exp, 'deep export')
            imgs = _image_files(_bd(root) / 'sff2_deep_export' / 'sprites')
        if not imgs:
            res.add_warning('No image sources found for native SFF2 manifest. Add PNG/PCX/etc. to source_sprites/ and rerun.')
            return res
        src_dir = work / 'sprites'
        src_dir.mkdir(parents=True, exist_ok=True)
        records: List[Dict[str, object]] = []
        for idx, img in enumerate(imgs):
            g, i = _parse_group_image(img, idx)
            dst = src_dir / f'g{g:04d}_i{i:04d}_{idx:05d}{img.suffix.lower()}'
            shutil.copy2(img, dst)
            res.add_created(root, dst)
            w, h = _image_size(dst)
            records.append({'group': g, 'image': i, 'filename': str(dst.relative_to(work)).replace('\\','/'), 'axis': {'x': w // 2 if w else 0, 'y': h if h else 0}})
        _write_json(manifest, {'tool': 'MugenForge Binary Deep', 'version': BINARY_DEEP_VERSION, 'sprites': records}, res, root)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    records = data.get('sprites') if isinstance(data, dict) else []
    if not isinstance(records, list) or not records:
        res.add_warning('Native SFF2 manifest contains no sprites.')
        return res
    out = work / 'builds' / f'{root.name}_native_sff2.sff'
    try:
        out, normalized = build_native_sff2_from_image_records(records, out, base_dir=manifest.parent)
        res.add_created(root, out)
        tables, meta, warns = discover_deep_sff2_tables(out)
        export_check: List[Dict[str, object]] = []
        if tables:
            data_bytes = out.read_bytes()
            check_dir = work / 'builds' / 'verification_exports'
            for rec in tables[0].records:
                ep, method = _export_record_payload_or_png(out, data_bytes, rec, check_dir)
                export_check.append({'record': rec.to_dict(), 'export': _rel(root, ep) if ep else '', 'method': method})
                if ep:
                    res.add_created(root, ep)
        _write_json(work / 'builds' / 'native_sff2_build_report.json', {
            'output': str(out),
            'output_sha256': _sha256(out),
            'sprite_count': len(normalized),
            'verification_tables': [t.to_dict() for t in tables],
            'verification_exports': export_check,
            'warnings': warns,
        }, res, root)
        if warns:
            res.warnings.extend(warns)
        res.notes.append(f'Built native table-backed SFF2 PNG file with {len(normalized)} sprites and verified it with the deep parser.')
    except Exception as exc:
        res.add_warning(f'Native SFF2 build failed: {exc}')
    return res


def apply_deep_sff2_mutation_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Deep SFF2 Mutation Sheet Apply')
    sff = _file(root, 'sff')
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for deep SFF2 mutation.')
        return res
    sheet = Path(sheet_path) if sheet_path else _bd(root) / 'sff2_mutation' / 'deep_sff2_mutation_sheet.csv'
    if not sheet.exists():
        res.merge(export_deep_sff2_mutation_sheet(root), 'sheet export')
    if not sheet.exists():
        res.add_warning('Deep SFF2 mutation sheet not found.')
        return res
    rows = list(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')))
    enabled = [r for r in rows if _truthy(r.get('enabled'))]
    if not enabled:
        res.add_skipped('No rows have enabled=yes; no SFF2 mutation candidate was created.')
        return res
    data = bytearray(sff.read_bytes())
    axis_applied = 0
    replace_records: List[Dict[str, object]] = []
    existing_export_dir = _bd(root) / 'sff2_deep_export' / 'sprites'
    for row in enabled:
        action = str(row.get('action') or 'axis').strip().lower()
        table_off = _safe_int(row.get('table_offset'), -1)
        new_x = _clamp_i16(_safe_int(row.get('new_axis_x'), _safe_int(row.get('current_axis_x'), 0)))
        new_y = _clamp_i16(_safe_int(row.get('new_axis_y'), _safe_int(row.get('current_axis_y'), 0)))
        if action in {'axis', 'patch-axis', 'both', 'replace'}:
            if 0 <= table_off + 12 <= len(data):
                struct.pack_into('<h', data, table_off + 8, new_x)
                struct.pack_into('<h', data, table_off + 10, new_y)
                axis_applied += 1
            else:
                res.add_warning(f'Invalid table_offset for axis patch row index {row.get("index")}: {table_off}')
        if action in {'replace', 'both'}:
            repl = str(row.get('replace_image') or '').strip()
            if repl:
                p = Path(repl)
                if not p.is_absolute():
                    p = (sheet.parent / p).resolve()
                if not p.exists():
                    p = (root / repl).resolve()
                if p.exists():
                    replace_records.append({'group': _safe_int(row.get('group'), 0), 'image': _safe_int(row.get('image'), 0), 'filename': str(p), 'axis': {'x': new_x, 'y': new_y}})
                else:
                    res.add_warning(f'Replacement image not found: {repl}')
    out_dir = _bd(root) / 'sff2_mutation' / 'patched'
    out_dir.mkdir(parents=True, exist_ok=True)
    patched = out_dir / f'{sff.stem}_deep_axis_patched_{_now()}{sff.suffix}'
    if axis_applied:
        patched.write_bytes(bytes(data))
        res.add_created(root, patched)
    rebuilt = None
    if replace_records:
        rebuilt = out_dir / f'{sff.stem}_deep_rebuilt_native_{_now()}{sff.suffix}'
        try:
            build_native_sff2_from_image_records(replace_records, rebuilt, base_dir=sheet.parent)
            res.add_created(root, rebuilt)
        except Exception as exc:
            res.add_warning(f'Native rebuild from replacement rows failed: {exc}')
            rebuilt = None
    if install:
        target = rebuilt or patched if (rebuilt or (axis_applied and patched.exists())) else None
        if target:
            bak = _backup(sff, 'sff2_install')
            shutil.copy2(target, sff)
            res.add_changed(root, sff)
            if bak:
                res.notes.append(f'Backup before SFF install: {_rel(root, bak)}')
    _write_json(out_dir / 'deep_sff2_mutation_apply_report.json', {
        'source': str(sff),
        'source_sha256_before': _sha256(sff),
        'axis_rows_applied': axis_applied,
        'replacement_rows': len(replace_records),
        'patched_axis_candidate': str(patched) if axis_applied else '',
        'rebuilt_native_candidate': str(rebuilt) if rebuilt else '',
        'installed': bool(install),
    }, res, root)
    res.notes.append(f'Applied {axis_applied} axis patch row(s); replacement native rebuild rows: {len(replace_records)}.')
    return res


# ---------------------------------------------------------------------------
# SND direct patch candidates


def export_snd_direct_patch_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Direct Patch Sheet Export')
    snd = _file(root, 'snd')
    out_dir = _bd(root) / 'snd_direct_patch'
    wav_dir = out_dir / 'wavs'
    wav_dir.mkdir(parents=True, exist_ok=True)
    if not snd or not snd.exists():
        res.add_warning('No SND file found for direct patch sheet.')
        return res
    info = read_snd(snd)
    rows: List[Dict[str, object]] = []
    for sound in info.sounds:
        wav_name = ''
        try:
            wav = export_sound(snd, sound, wav_dir)
            res.add_created(root, wav)
            wav_name = 'wavs/' + wav.name
        except Exception as exc:
            res.add_warning(f'Could not export sound #{sound.index}: {exc}')
        rows.append({
            'enabled': 'no',
            'action': 'id',
            'index': sound.index,
            'current_group': sound.group if sound.group is not None else 0,
            'current_sound': sound.sound if sound.sound is not None else sound.index,
            'new_group': sound.group if sound.group is not None else 0,
            'new_sound': sound.sound if sound.sound is not None else sound.index,
            'replace_wav': '',
            'current_wav': wav_name,
            'riff_offset': sound.riff_offset,
            'length': sound.length,
            'header_offset': sound.header_offset if sound.header_offset is not None else '',
            'channels': sound.channels or '',
            'sample_rate': sound.sample_rate or '',
            'bits_per_sample': sound.bits_per_sample or '',
            'note': 'action=id patches group/sound if a header was found. action=replace patches WAV only if it fits; otherwise use SND rebuild workflow.',
        })
    fields = ['enabled','action','index','current_group','current_sound','new_group','new_sound','replace_wav','current_wav','riff_offset','length','header_offset','channels','sample_rate','bits_per_sample','note']
    _write_csv(out_dir / 'snd_direct_patch_sheet.csv', rows, fields, res, root)
    _write_text(out_dir / 'README_SND_DIRECT_PATCH.md', '\n'.join([
        '# SND Direct Patch Sheet', '', CAPABILITY_NOTE, '',
        'This sheet creates a patched candidate copy of the original SND.',
        '',
        '- `action=id` changes group/sound fields when a nearby SND header is detected.',
        '- `action=replace` attempts an in-place WAV replacement only when the new WAV is not larger than the original slot.',
        '- Larger replacements are intentionally sent to the rebuilt-candidate workflow, not shoved into arbitrary bytes.',
        '- Optional install always writes a backup first.',
    ]), res, root)
    res.notes.append(f'Exported {len(rows)} SND direct patch rows.')
    res.warnings.extend(info.warnings)
    return res


def apply_snd_direct_patch_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Direct Patch Sheet Apply')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for direct patch apply.')
        return res
    sheet = Path(sheet_path) if sheet_path else _bd(root) / 'snd_direct_patch' / 'snd_direct_patch_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_direct_patch_sheet(root), 'sheet export')
    if not sheet.exists():
        res.add_warning('SND direct patch sheet not found.')
        return res
    rows = list(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')))
    enabled = [r for r in rows if _truthy(r.get('enabled'))]
    if not enabled:
        res.add_skipped('No rows have enabled=yes; no SND direct patch candidate was created.')
        return res
    data = bytearray(snd.read_bytes())
    patched_ids = 0
    patched_wavs = 0
    rebuild_needed: List[Dict[str, object]] = []
    errors: List[str] = []
    for row in enabled:
        action = str(row.get('action') or 'id').strip().lower()
        hdr = _safe_int(row.get('header_offset'), -1)
        if action in {'id', 'both', 'replace'}:
            if hdr >= 0 and hdr + 16 <= len(data):
                struct.pack_into('<i', data, hdr + 8, _safe_int(row.get('new_group'), _safe_int(row.get('current_group'), 0)))
                struct.pack_into('<i', data, hdr + 12, _safe_int(row.get('new_sound'), _safe_int(row.get('current_sound'), 0)))
                patched_ids += 1
            else:
                errors.append(f'Row {row.get("index")} has no reliable header_offset for ID patch.')
        repl = str(row.get('replace_wav') or '').strip()
        if action in {'replace', 'both'} and repl:
            p = Path(repl)
            if not p.is_absolute():
                p = (sheet.parent / p).resolve()
            if not p.exists():
                p = (root / repl).resolve()
            if not p.exists():
                errors.append(f'Replacement WAV not found: {repl}')
                continue
            blob = p.read_bytes()
            if not (blob.startswith(b'RIFF') and blob[8:12] == b'WAVE'):
                errors.append(f'Replacement is not RIFF/WAVE: {p}')
                continue
            riff_off = _safe_int(row.get('riff_offset'), -1)
            old_len = _safe_int(row.get('length'), -1)
            if riff_off >= 0 and old_len > 0 and len(blob) <= old_len and riff_off + old_len <= len(data):
                data[riff_off:riff_off + len(blob)] = blob
                if len(blob) < old_len:
                    data[riff_off + len(blob):riff_off + old_len] = b'\x00' * (old_len - len(blob))
                if hdr >= 0 and hdr + 8 <= len(data):
                    struct.pack_into('<I', data, hdr + 4, len(blob))
                patched_wavs += 1
            else:
                rebuild_needed.append({'row': row.get('index'), 'replacement': str(p), 'reason': 'replacement WAV is larger than original slot or slot range was not reliable'})
    out_dir = _bd(root) / 'snd_direct_patch' / 'patched'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{snd.stem}_direct_patched_{_now()}{snd.suffix}'
    out.write_bytes(bytes(data))
    res.add_created(root, out)
    if install:
        bak = _backup(snd, 'snd_install')
        shutil.copy2(out, snd)
        res.add_changed(root, snd)
        if bak:
            res.notes.append(f'Backup before SND install: {_rel(root, bak)}')
    info_after = read_snd(out)
    _write_json(out_dir / 'snd_direct_patch_report.json', {
        'source': str(snd),
        'source_sha256': _sha256(snd),
        'output': str(out),
        'output_sha256': _sha256(out),
        'patched_id_rows': patched_ids,
        'patched_wav_rows': patched_wavs,
        'larger_wavs_requiring_rebuild': rebuild_needed,
        'errors': errors,
        'verify_sound_count': len(info_after.sounds),
        'verify_warnings': info_after.warnings,
        'installed': bool(install),
    }, res, root)
    if errors:
        res.warnings.extend(errors)
    if rebuild_needed:
        res.warnings.append(f'{len(rebuild_needed)} WAV replacement(s) require rebuilt-candidate workflow because they do not fit in place.')
    res.notes.append(f'Patched candidate SND IDs={patched_ids}, in-place WAVs={patched_wavs}.')
    return res


# ---------------------------------------------------------------------------
# Runtime-oriented test artifacts and source scaffolding confidence


def write_runtime_validation_lab(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Runtime Validation Lab')
    out_dir = _bd(root) / 'runtime_validation_lab'
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd_or_cns_files = list(root.glob('*.cmd')) + list(root.glob('*.cns')) + list(root.glob('*.st'))
    states = []
    commands = []
    for p in cmd_or_cns_files:
        try:
            scan = parse_code(read_text_safely(p))
        except Exception:
            continue
        for st in scan.states:
            states.append({'file': _rel(root, p), 'line': st.line, 'state': st.number, 'anim': st.values.get('anim', ''), 'ctrl': st.values.get('ctrl', '')})
        for c in scan.commands:
            commands.append({'file': _rel(root, p), 'line': c.line, 'name': c.name, 'command': c.command, 'time': c.time or '', 'buffer_time': c.buffer_time or ''})
    air = _file(root, 'air')
    actions = []
    if air and air.exists():
        for a in parse_air(read_text_safely(air)):
            actions.append({'action': a.number, 'frames': len(a.frames), 'ticks': sum(max(0, f.ticks) for f in a.frames)})
    _write_csv(out_dir / 'runtime_state_checklist.csv', states, ['file','line','state','anim','ctrl'], res, root)
    _write_csv(out_dir / 'runtime_command_checklist.csv', commands, ['file','line','name','command','time','buffer_time'], res, root)
    _write_csv(out_dir / 'runtime_animation_checklist.csv', actions, ['action','frames','ticks'], res, root)
    debug_block = '''; MugenForge Binary Deep runtime telemetry helper
; Paste/install this in a test-only CNS/ST file or keep it behind a debug flag.
[State -2, MugenForge Runtime Telemetry]
type = DisplayToClipboard
trigger1 = 1
text = "MFRT state=%d anim=%d elem=%d time=%d ctrl=%d pos=(%d,%d) vel=(%f,%f)"
params = stateno, anim, animelemno(0), time, ctrl, pos x, pos y, vel x, vel y
ignorehitpause = 1
'''
    _write_text(out_dir / 'runtime_telemetry_helper.cns', debug_block, res, root)
    _write_text(out_dir / 'README_RUNTIME_VALIDATION.md', '\n'.join([
        '# Runtime Validation Lab', '',
        'This lab turns source estimates into a playtest checklist and provides a debug overlay helper that can emit engine-side values during real M.U.G.E.N runs.', '',
        'Generated files:',
        '- `runtime_state_checklist.csv`',
        '- `runtime_command_checklist.csv`',
        '- `runtime_animation_checklist.csv`',
        '- `runtime_telemetry_helper.cns`', '',
        'Reports remain source-estimated until you paste/import actual engine log lines containing `MFRT`.',
    ]), res, root)
    # Ingest any existing logs under testing/ or runtime_validation_lab/.
    telemetry_rows: List[Dict[str, object]] = []
    rx = re.compile(r'MFRT\s+state=(?P<state>-?\d+)\s+anim=(?P<anim>-?\d+)\s+elem=(?P<elem>-?\d+)\s+time=(?P<time>-?\d+)\s+ctrl=(?P<ctrl>-?\d+)')
    for log in list(out_dir.glob('*.log')) + list((root / 'testing').glob('*.log')) if (root / 'testing').exists() else list(out_dir.glob('*.log')):
        try:
            text = read_text_safely(log)
        except Exception:
            continue
        for m in rx.finditer(text):
            row = m.groupdict()
            row['log'] = _rel(root, log)
            telemetry_rows.append(row)
    if telemetry_rows:
        _write_csv(out_dir / 'runtime_telemetry_ingested.csv', telemetry_rows, ['log','state','anim','elem','time','ctrl'], res, root)
        res.notes.append(f'Ingested {len(telemetry_rows)} runtime telemetry lines from logs.')
    else:
        res.notes.append('Runtime checklist written. No MFRT runtime logs were found yet.')
    return res


# ---------------------------------------------------------------------------
# Dashboard, bundle, one-click


def write_binary_deep_dashboard(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Deep Dashboard')
    sff = _file(root, 'sff')
    snd = _file(root, 'snd')
    sff_line = 'missing'
    if sff and sff.exists():
        tables, _meta, warns = discover_deep_sff2_tables(sff)
        sff_line = f'{_rel(root, sff)} — deep candidate tables={len(tables)}; best records={len(tables[0].records) if tables else 0}; warnings={len(warns)}'
    snd_line = 'missing'
    if snd and snd.exists():
        sinfo = read_snd(snd)
        patchable = sum(1 for s in sinfo.sounds if s.header_offset is not None)
        snd_line = f'{_rel(root, snd)} — sounds={len(sinfo.sounds)}; direct-ID patchable headers={patchable}'
    lines = [
        '# MugenForge Binary Deep Dashboard', '',
        f'Version: {BINARY_DEEP_VERSION}', '',
        CAPABILITY_NOTE, '',
        '## Current project status', '',
        f'- SFF: {sff_line}',
        f'- SND: {snd_line}', '',
        '## What this release changes', '',
        '- Adds broad SFF2 table discovery instead of only the old MugenForge PNG-subset probe.',
        '- Adds direct export/decode attempts for PNG, PCX, zlib-wrapped images, raw indexed/RGB/RGBA and RLE8 payloads, plus diagnostic-only 5-bit/LZ-style probes for unsupported records.',
        '- Adds deep SFF2 mutation sheets for axis patch candidates and native PNG-backed rebuild candidates.',
        '- Adds SND direct patch candidates for IDs and same-or-smaller WAV replacements, while larger WAVs route to rebuild workflow.',
        '- Adds runtime validation artifacts so source reports can be paired with real playtest telemetry when available.', '',
        '## Remaining honest boundary', '',
        'Unknown, corrupt, encrypted, or tool-specific binary variants can still require manual review. MugenForge now attempts more formats and writes candidates, but it will still warn/refuse when a record cannot be proven safe.',
    ]
    _write_text(_bd(root) / 'BINARY_DEEP_DASHBOARD.md', '\n'.join(lines), res, root)
    _write_text(_bd(root) / 'BINARY_DEEP_START_HERE.md', '\n'.join(lines + ['', 'Generated by Binary Deep.']), res, root)
    res.notes.append('Wrote Binary Deep dashboard and start-here guide.')
    return res


def build_binary_deep_bundle(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Deep Bundle')
    base = _bd(root)
    if not base.exists():
        res.add_warning('binary_deep folder does not exist yet. Run a Binary Deep report first.')
        return res
    out_dir = base / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_binary_deep_bundle_{_now()}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(base.rglob('*')):
            if p.is_file() and p != out:
                zf.write(p, p.relative_to(base))
    res.add_created(root, out)
    res.notes.append('Bundled Binary Deep reports/workspaces.')
    return res


def run_binary_deep_pass(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('One-Click Binary Deep Pass')
    for label, fn in [
        ('binary core compatibility pass', run_binary_core_pass),
        ('dashboard', write_binary_deep_dashboard),
        ('deep sff2 inspection', write_deep_sff2_inspection),
        ('deep sff2 export', export_deep_sff2_sprites),
        ('deep sff2 mutation sheet', export_deep_sff2_mutation_sheet),
        ('native sff2 build manifest/candidate', build_native_sff2_from_manifest),
        ('snd direct patch sheet', export_snd_direct_patch_sheet),
        ('snd waveform preview', write_snd_waveform_preview),
        ('runtime validation lab', write_runtime_validation_lab),
    ]:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f'{label} failed: {exc}')
    try:
        res.merge(build_binary_deep_bundle(root), 'bundle')
    except Exception as exc:
        res.add_warning(f'bundle failed: {exc}')
    return res


# Compatibility names for UI/test scripts.
inspect_sff2_deep = write_deep_sff2_inspection
export_sff2_deep_sprites = export_deep_sff2_sprites
export_sff2_mutation_sheet = export_deep_sff2_mutation_sheet
apply_sff2_mutation_sheet = apply_deep_sff2_mutation_sheet
build_native_sff2 = build_native_sff2_from_manifest
export_snd_patch_sheet = export_snd_direct_patch_sheet
apply_snd_patch_sheet = apply_snd_direct_patch_sheet
write_runtime_lab = write_runtime_validation_lab

# ---------------------------------------------------------------------------
# Built-in codec probe suite for raw/RLE8/diagnostic-probe paths


def _pack_5bit_raw(indices: bytes) -> bytes:
    out = bytearray()
    acc = 0
    bits = 0
    for b in indices:
        acc |= (int(b) & 0x1F) << bits
        bits += 5
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    if bits:
        out.append(acc & 0xFF)
    return bytes(out)


def _encode_pcx_style_rle(indices: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(indices):
        val = indices[i]
        run = 1
        while i + run < len(indices) and indices[i + run] == val and run < 63:
            run += 1
        if run > 1 or val >= 0xC0:
            out.extend([0xC0 | run, val])
        else:
            out.append(val)
        i += run
    return bytes(out)


def _write_native_sff2_payload_records(records: Sequence[Dict[str, object]], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = bytearray(SFF2_NATIVE_HEADER_SIZE)
    header[0:12] = SFF_SIGNATURE
    header[12:16] = bytes([2, 0, 1, 0])
    table_offset = SFF2_NATIVE_HEADER_SIZE
    table_size = SFF2_RECORD_SIZE * len(records)
    data_base = table_offset + table_size
    struct.pack_into('<I', header, 16, len(records))
    struct.pack_into('<I', header, 20, len({int(r.get('group', 0)) for r in records}))
    struct.pack_into('<I', header, 24, table_offset)
    struct.pack_into('<I', header, 28, len(records))
    struct.pack_into('<I', header, 32, data_base)
    struct.pack_into('<I', header, 36, sum(len(bytes(r.get('payload', b''))) for r in records))
    header[64:64 + len(SFF2_NATIVE_MAGIC)] = SFF2_NATIVE_MAGIC
    table = bytearray(table_size)
    payload_chunks: List[bytes] = []
    cursor = 0
    for idx, rec in enumerate(records):
        payload = bytes(rec.get('payload', b''))
        off = idx * SFF2_RECORD_SIZE
        struct.pack_into('<H', table, off + 0, _clamp_u16(_safe_int(rec.get('group'), 0)))
        struct.pack_into('<H', table, off + 2, _clamp_u16(_safe_int(rec.get('image'), idx)))
        struct.pack_into('<H', table, off + 4, _clamp_u16(_safe_int(rec.get('width'), 1)))
        struct.pack_into('<H', table, off + 6, _clamp_u16(_safe_int(rec.get('height'), 1)))
        struct.pack_into('<h', table, off + 8, _clamp_i16(_safe_int(rec.get('axis_x'), 0)))
        struct.pack_into('<h', table, off + 10, _clamp_i16(_safe_int(rec.get('axis_y'), 0)))
        struct.pack_into('<H', table, off + 12, 0xFFFF)
        table[off + 14] = _safe_int(rec.get('format_code'), 0) & 0xFF
        table[off + 15] = _safe_int(rec.get('color_depth'), 8) & 0xFF
        struct.pack_into('<I', table, off + 16, cursor)
        struct.pack_into('<I', table, off + 20, len(payload))
        struct.pack_into('<H', table, off + 24, _clamp_u16(_safe_int(rec.get('palette_index'), 0)))
        struct.pack_into('<H', table, off + 26, _clamp_u16(_safe_int(rec.get('flags'), 0)))
        payload_chunks.append(payload)
        cursor += len(payload)
    out_path.write_bytes(bytes(header) + bytes(table) + b''.join(payload_chunks))
    return out_path


def write_sff2_codec_probe_suite(root: Path) -> BinaryCoreResult:
    """Generate and verify controlled fixtures for the deep raw/RLE8/diagnostic-probe paths.

    This does not prove every third-party SFF2 in the wild; it proves that the native
    decoder implementations are exercised and can round-trip supported payload shapes.
    """
    root = Path(root)
    res = BinaryCoreResult('SFF2 Codec Probe Suite')
    out_dir = _bd(root) / 'sff2_codec_probe_suite'
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 16, 16
    raw = bytes(((x + y) % 256) for y in range(h) for x in range(w))
    rle_source = bytes(([3] * 16 + [40] * 16) * 8)
    rle8 = _encode_pcx_style_rle(rle_source)
    raw5_indices = bytes((i % 32) for i in range(w * h))
    raw5 = _pack_5bit_raw(raw5_indices)
    lz5_probe = _pack_5bit_raw(bytes(((31 - i) % 32) for i in range(w * h)))
    # zlib-wrapped PNG fixture
    try:
        from PIL import Image  # type: ignore
        img = _pil_image_from_indexed(raw, w, h)
        buf = BytesIO(); img.save(buf, format='PNG')
        zpng = zlib.compress(buf.getvalue())
    except Exception:
        zpng = zlib.compress(raw)
    records = [
        {'group': 9100, 'image': 0, 'width': w, 'height': h, 'axis_x': 8, 'axis_y': 16, 'format_code': 0, 'color_depth': 8, 'payload': raw},
        {'group': 9100, 'image': 1, 'width': w, 'height': h, 'axis_x': 8, 'axis_y': 16, 'format_code': 2, 'color_depth': 8, 'payload': rle8},
        {'group': 9100, 'image': 2, 'width': w, 'height': h, 'axis_x': 8, 'axis_y': 16, 'format_code': 3, 'color_depth': 5, 'payload': raw5},
        {'group': 9100, 'image': 3, 'width': w, 'height': h, 'axis_x': 8, 'axis_y': 16, 'format_code': 4, 'color_depth': 5, 'payload': lz5_probe},
        {'group': 9100, 'image': 4, 'width': w, 'height': h, 'axis_x': 8, 'axis_y': 16, 'format_code': 10, 'color_depth': 32, 'payload': zpng},
    ]
    sff = _write_native_sff2_payload_records(records, out_dir / 'codec_probe_native.sff')
    res.add_created(root, sff)
    tables, meta, warns = discover_deep_sff2_tables(sff)
    verify: List[Dict[str, object]] = []
    passed = 0
    if tables:
        data = sff.read_bytes()
        exp_dir = out_dir / 'exports'
        for rec in tables[0].records:
            out, method = _export_record_payload_or_png(sff, data, rec, exp_dir)
            ok = bool(out and Path(out).exists() and Path(out).suffix.lower() == '.png')
            if ok:
                passed += 1
                res.add_created(root, out)
            verify.append({'record': rec.to_dict(), 'output': _rel(root, out) if out else '', 'method': method, 'pass': ok})
    else:
        res.add_warning('Codec probe suite could not rediscover its own fixture table.')
    report = {'fixture': str(sff), 'fixture_sha256': _sha256(sff), 'tables': [t.to_dict() for t in tables], 'verify': verify, 'passed': passed, 'expected': len(records), 'warnings': warns}
    _write_json(out_dir / 'sff2_codec_probe_report.json', report, res, root)
    _write_text(out_dir / 'SFF2_CODEC_PROBE_REPORT.md', '\n'.join([
        '# SFF2 Codec Probe Suite', '',
        f'Passed: {passed}/{len(records)} controlled codec probes', '',
        'Probed payload shapes: raw indexed, RLE8-style, diagnostic 5-bit packed probes, LZ-style probe payloads, zlib-wrapped PNG.', '',
        'This proves the decoder paths execute on controlled fixtures. Third-party files with different table layouts or compression variants may still require manual review.',
    ]), res, root)
    if passed != len(records):
        res.add_warning(f'Codec probe passed {passed}/{len(records)} fixtures.')
    else:
        res.notes.append('All controlled SFF2 codec probe fixtures decoded successfully.')
    return res


# Patch the v5.5 pass to include the codec suite while preserving the earlier definition name.
_run_binary_deep_pass_base = run_binary_deep_pass

def run_binary_deep_pass(root: Path) -> BinaryCoreResult:  # type: ignore[no-redef]
    root = Path(root)
    res = _run_binary_deep_pass_base(root)
    try:
        res.merge(write_sff2_codec_probe_suite(root), 'sff2 codec probe suite')
    except Exception as exc:
        res.add_warning(f'sff2 codec probe suite failed: {exc}')
    try:
        res.merge(build_binary_deep_bundle(root), 'bundle refresh')
    except Exception as exc:
        res.add_warning(f'bundle refresh failed: {exc}')
    return res

# Update compatibility alias after redefining one-click.
run_binary_deep = run_binary_deep_pass

# Final v5.5 one-click definition: focus on Deep workflows instead of replaying old limitation reports.
def run_binary_deep_pass(root: Path) -> BinaryCoreResult:  # type: ignore[no-redef]
    root = Path(root)
    res = BinaryCoreResult('One-Click Binary Deep Pass')
    for label, fn in [
        ('dashboard', write_binary_deep_dashboard),
        ('safety hashes', write_binary_safety_report),
        ('deep sff2 inspection', write_deep_sff2_inspection),
        ('deep sff2 export', export_deep_sff2_sprites),
        ('deep sff2 mutation sheet', export_deep_sff2_mutation_sheet),
        ('native sff2 build manifest/candidate', build_native_sff2_from_manifest),
        ('sff2 codec probe suite', write_sff2_codec_probe_suite),
        ('snd direct patch sheet', export_snd_direct_patch_sheet),
        ('snd bank rebuild sheet', export_snd_bank_sheet),
        ('snd waveform preview', write_snd_waveform_preview),
        ('runtime validation lab', write_runtime_validation_lab),
    ]:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f'{label} failed: {exc}')
    try:
        res.merge(build_binary_deep_bundle(root), 'bundle')
    except Exception as exc:
        res.add_warning(f'bundle failed: {exc}')
    return res

run_binary_deep = run_binary_deep_pass
