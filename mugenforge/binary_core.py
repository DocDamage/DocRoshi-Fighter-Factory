from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from io import BytesIO
import csv
import json
import re
import shutil
import struct
import wave
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .artifact_io import (
    backup_file,
    rel_path as _rel,
    sha256_file as _sha256,
    timestamp as _now,
    write_csv_artifact as _write_csv,
    write_json_artifact as _write_json,
    write_text_artifact as _write_text,
)
from .binary_results import BinaryCoreResult
from .move_wizard import find_character_file
from .sff_codec import (
    SFF_SIGNATURE,
    SffInfo,
    SffSprite,
    read_sff,
    export_all_sprites,
    build_sff_v1_from_manifest,
    summarize_sff_detailed,
)
from .snd_codec import read_snd, export_sound, build_snd_from_manifest, summarize_snd_detailed

BINARY_CORE_VERSION = '5.5.0'
IMAGE_SUFFIXES = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
TRUTH_NOTE = (
    'Binary Core v5.5 adds common-table SFF2 v2/v2.1 parsing, decoded export for PNG/raw/RLE8/RLE5/LZ5 paths, '
    'standard SFF2 candidate rebuilds from manifests, SFF1/SFF2 copied axis mutation, guarded SND slot patch candidates, '
    'and runtime evidence scaffolding. Unknown or corrupt variants are still refused with warnings rather than silently guessed.'
)

@dataclass
class Sff2ProbeRecord:
    index: int
    group: int
    image: int
    width: int = 0
    height: int = 0
    axis_x: int = 0
    axis_y: int = 0
    palette: int = 0
    format_code: int = 0
    flags: int = 0
    payload_offset: int = 0
    payload_length: int = 0
    table_offset: int = 0
    data_base: int = 0
    source: str = 'unknown'
    note: str = ''

    def to_dict(self) -> Dict[str, object]:
        return {
            'index': self.index,
            'group': self.group,
            'image': self.image,
            'width': self.width,
            'height': self.height,
            'axis_x': self.axis_x,
            'axis_y': self.axis_y,
            'palette': self.palette,
            'format_code': self.format_code,
            'flags': self.flags,
            'payload_offset': self.payload_offset,
            'payload_length': self.payload_length,
            'table_offset': self.table_offset,
            'data_base': self.data_base,
            'source': self.source,
            'note': self.note,
        }


# ---------------------------------------------------------------------------
# Generic helpers


def _uniq(items: Iterable[object]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _bc(root: Path) -> Path:
    out = Path(root) / 'binary_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _backup(path: Path) -> Optional[Path]:
    return backup_file(path, 'binary_core')


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
    hits = sorted(root.rglob(f'*.{ext}'), key=lambda p: str(p).lower())
    skip = {'__pycache__', 'binary_core', 'forge_timeline', 'forge_polish', 'forge_beyond', '.mugenforge'}
    for p in hits:
        if p.is_file() and not any(part in skip for part in p.parts):
            return p
    return None


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


def _truth_lines() -> List[str]:
    return [
        'Honest capability boundary:',
        '- Common SFF2 v2/v2.1 table parsing is implemented for the 28-byte sprite table / 16-byte palette table layout.',
        '- Decoded SFF2 export now supports direct PNG payloads, raw indexed/truecolor payloads, RLE8, RLE5, and LZ5 paths used by supported MugenForge/Sprmake2-style workflows.',
        '- Direct and zlib-wrapped PNG/PCX payload recovery remains available for transitional or rescue cases.',
        '- SFF axis mutation writes patched copies first for SFF1 subheaders and common SFF2 sprite-table axis fields.',
        '- Native SFF2 rebuilds are candidate files built from explicit source manifests; engine testing is still required before release.',
        '- SND editing supports rebuilt candidates and guarded same-or-smaller WAV slot patch copies; arbitrary unsafe byte patching is refused.',
        '- Generated gameplay code still requires real playtesting. Runtime Lab can capture configured external engine evidence, but static reports remain source-analysis aids.',
    ]


# ---------------------------------------------------------------------------
# SFF/SFF2 inspection and payload discovery


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from('<h', data, off)[0]


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _header_slots(data: bytes, start: int = 16, stop: int = 160) -> Dict[str, int]:
    slots: Dict[str, int] = {}
    stop = min(stop, len(data) - 4)
    for off in range(start, max(start, stop + 1), 4):
        try:
            slots[f'0x{off:02X}'] = _u32(data, off)
        except Exception:
            break
    return slots


def _find_embedded_pngs(data: bytes) -> List[Tuple[int, int]]:
    sig = b'\x89PNG\r\n\x1a\n'
    out: List[Tuple[int, int]] = []
    pos = 0
    while True:
        start = data.find(sig, pos)
        if start < 0:
            break
        iend_type = data.find(b'IEND', start + 8)
        if iend_type < 0:
            pos = start + 8
            continue
        end = iend_type + 8
        if start < end <= len(data):
            out.append((start, end - start))
        pos = max(end, start + 8)
    return out


def _find_pcx_markers(data: bytes, limit: int = 2000) -> List[int]:
    out: List[int] = []
    for idx in range(0, max(0, len(data) - 4)):
        if data[idx] == 0x0A and data[idx + 2] == 0x01 and data[idx + 3] in {1, 2, 4, 8, 24}:
            out.append(idx)
            if len(out) >= limit:
                break
    return out


def _probe_mugenforge_png_subset(path: Path) -> Tuple[List[Sff2ProbeRecord], Dict[str, object], List[str]]:
    data = Path(path).read_bytes()
    warnings: List[str] = []
    meta: Dict[str, object] = {
        'path': str(path),
        'size': len(data),
        'signature': data[:12].decode('latin-1', errors='replace') if len(data) >= 12 else '',
        'raw_version_bytes': list(data[12:16]) if len(data) >= 16 else [],
        'header_slots': _header_slots(data) if len(data) >= 32 else {},
        'embedded_png_count': len(_find_embedded_pngs(data)),
        'pcx_marker_count': len(_find_pcx_markers(data, limit=200)),
    }
    if len(data) < 64 or data[:12] != SFF_SIGNATURE:
        warnings.append('No ElecbyteSpr signature or file is too small for SFF inspection.')
        return [], meta, warnings
    if data[12] < 2:
        meta['probe_mode'] = 'sff-v1-or-older'
        return [], meta, warnings

    sprite_count = _u32(data, 16) if len(data) >= 20 else 0
    table_offset = _u32(data, 24) if len(data) >= 28 else 0
    record_count = _u32(data, 28) if len(data) >= 32 else 0
    data_base = _u32(data, 32) if len(data) >= 36 else 0
    data_size = _u32(data, 36) if len(data) >= 40 else 0
    meta.update({
        'probe_mode': 'sff2-conservative-png-subset-probe',
        'sprite_count_hint_0x10': sprite_count,
        'table_offset_hint_0x18': table_offset,
        'record_count_hint_0x1C': record_count,
        'data_base_hint_0x20': data_base,
        'data_size_hint_0x24': data_size,
        'record_size_assumed': 28,
    })
    records: List[Sff2ProbeRecord] = []
    if not (0 < record_count <= 100000 and 0 < table_offset < len(data) and 0 < data_base <= len(data)):
        warnings.append('No supported MugenForge PNG-subset SFF2 table was detected. General SFF2 remains metadata-only in this release.')
        return records, meta, warnings
    record_size = 28
    if table_offset + record_count * record_size > len(data):
        warnings.append('Candidate SFF2 record table runs beyond EOF; metadata-only.')
        return records, meta, warnings
    for idx in range(min(record_count, 100000)):
        off = table_offset + idx * record_size
        try:
            group = _u16(data, off)
            image = _u16(data, off + 2)
            width = _u16(data, off + 4)
            height = _u16(data, off + 6)
            axis_x = _i16(data, off + 8)
            axis_y = _i16(data, off + 10)
            palette = _u16(data, off + 12)
            format_code = data[off + 14]
            flags = data[off + 15]
            rel_payload = _u32(data, off + 16)
            length = _u32(data, off + 20)
        except Exception as exc:
            warnings.append(f'Could not parse candidate SFF2 record {idx}: {exc}')
            break
        payload_offset = data_base + rel_payload
        note = ''
        if length <= 0 or payload_offset + length > len(data):
            note = 'invalid payload range'
        elif data[payload_offset:payload_offset + 8] == b'\x89PNG\r\n\x1a\n':
            note = 'PNG payload'
        elif format_code not in {10}:
            note = 'non-PNG/unknown payload code; extraction refused'
        else:
            note = 'format code hints PNG but signature not found'
        records.append(Sff2ProbeRecord(
            index=idx,
            group=group,
            image=image,
            width=width,
            height=height,
            axis_x=axis_x,
            axis_y=axis_y,
            palette=palette,
            format_code=format_code,
            flags=flags,
            payload_offset=payload_offset,
            payload_length=length,
            table_offset=off,
            data_base=data_base,
            source='mugenforge_png_subset_probe',
            note=note,
        ))
    if not records:
        warnings.append('SFF2 table probe found no parseable records.')
    elif any('invalid' in r.note for r in records):
        warnings.append('Some candidate SFF2 records had invalid payload ranges.')
    return records, meta, warnings


def _sff2_records_from_info(info: SffInfo) -> List[Dict[str, object]]:
    if info.v2_metadata:
        rows = info.v2_metadata.get('sff2_records') or []
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _sff2_palettes_from_info(info: SffInfo) -> List[Dict[str, object]]:
    if info.v2_metadata:
        rows = info.v2_metadata.get('sff2_palettes') or []
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _truthy(value: object) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _auto_image_sources(root: Path) -> List[Path]:
    candidates = [
        root / 'source_sprites',
        root / 'sprites',
        root / 'staged_sprites',
        root / 'factory_plus_staged_sprites',
        root / 'sprite_slices',
        _bc(root) / 'sff_payloads' / 'sff1_supported',
        _bc(root) / 'sff_payloads' / 'sff2_png_subset',
        _bc(root) / 'sff_payloads' / 'embedded_png_scan',
    ]
    out: List[Path] = []
    for cand in candidates:
        imgs = _image_files(cand)
        if imgs:
            out.extend(imgs)
            break
    return out


def _png_bytes_for_sff2(path: Path) -> Tuple[bytes, int, int]:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        raise RuntimeError('Pillow is required for the experimental PNG-subset SFF copy builder.') from exc
    with Image.open(path) as im:
        rgba = im.convert('RGBA')
        buf = BytesIO()
        rgba.save(buf, format='PNG')
        return buf.getvalue(), rgba.width, rgba.height


# ---------------------------------------------------------------------------
# SFF/SFF2 inspection, payloads, axis sheets, rebuilds


def write_sff2_inspection(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SFF / SFF2 v5.5 Native Inspection')
    sff = _file(root, 'sff')
    out_dir = _bc(root) / 'sff_inspection'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for this project.')
        return res
    data = sff.read_bytes()
    info = read_sff(sff)
    sff2_rows = _sff2_records_from_info(info)
    palette_rows = _sff2_palettes_from_info(info)
    subset_records, subset_meta, subset_warnings = _probe_mugenforge_png_subset(sff)
    png_hits = _find_embedded_pngs(data)
    pcx_hits = _find_pcx_markers(data, limit=200)
    rows = [
        {
            'index': spr.index, 'group': spr.group, 'image': spr.image,
            'axis_x': spr.x, 'axis_y': spr.y, 'length': spr.length,
            'data_offset': spr.data_offset, 'next_offset': spr.next_offset,
            'same_palette': spr.same_palette, 'format': spr.format_hint,
            'raw_header_offset': spr.raw_header_offset,
        }
        for spr in info.sprites
    ]
    report = {
        'tool': 'MugenForge Studio Binary Core', 'version': BINARY_CORE_VERSION,
        'file': str(sff), 'size': len(data), 'sha256': _sha256(sff),
        'read_sff': {
            'version': info.version, 'version_text': info.version_text, 'variant': info.variant,
            'header_sprite_count': info.sprite_count, 'header_group_count': info.group_count,
            'supported_for_extraction': info.is_supported_for_extraction, 'warnings': info.warnings,
        },
        'common_sff2_sprite_records': sff2_rows,
        'common_sff2_palette_records': palette_rows,
        'all_sprite_rows_for_ui': rows,
        'mugenforge_png_subset_records': [r.to_dict() for r in subset_records],
        'embedded_png_ranges': [{'offset': off, 'length': length} for off, length in png_hits[:1000]],
        'pcx_marker_offsets': pcx_hits[:200],
        'warnings': _uniq(info.warnings + subset_warnings),
        'honest_capabilities': _truth_lines(),
    }
    _write_json(out_dir / 'sff_binary_inspection.json', report, res, root)
    if rows:
        _write_csv(out_dir / 'sff_sprite_records.csv', rows, ['index','group','image','axis_x','axis_y','length','data_offset','next_offset','same_palette','format','raw_header_offset'], res, root)
    if sff2_rows:
        fields = ['index','group','image','width','height','axis_x','axis_y','linked_index','format_code','format_name','color_depth','data_offset','data_length','palette_index','flags','table_offset','payload_offset','payload_base','note']
        _write_csv(out_dir / 'sff2_common_sprite_table.csv', sff2_rows, fields, res, root)
    if palette_rows:
        fields = ['index','group','item','num_colors','data_offset','data_length','table_offset']
        _write_csv(out_dir / 'sff2_common_palette_table.csv', palette_rows, fields, res, root)
    lines = [
        '# SFF / SFF2 v5.5 Native Inspection', '',
        f'File: `{_rel(root, sff)}`', f'Size: {len(data):,} bytes',
        f'SHA-256: `{report["sha256"]}`', f'Parser layout: `{info.variant}`',
        f'Raw version bytes: `{info.version_text}`',
        f'Parsed sprite rows: {len(rows)}',
        f'Common SFF2 table rows: {len(sff2_rows)}',
        f'Common SFF2 palette rows: {len(palette_rows)}',
        f'Embedded PNG payloads found: {len(png_hits)}', '',
    ]
    if info.variant == 'sff2-standard':
        lines.append('Supported path: common-table SFF2 decode/export, axis patch-copy, and manifest-based SFF2 rebuild candidates are available.')
    elif info.is_supported_for_extraction:
        lines.append('Supported path: SFF v1-style PCX/PNG payload extraction and axis patch-copy are available.')
    elif subset_records:
        lines.append('Supported path: MugenForge legacy PNG-subset recovery is available.')
    else:
        lines.append('Supported path: metadata and embedded payload discovery only; unsafe mutation is refused.')
    lines += ['', '## Honest capability boundary'] + _truth_lines()[1:]
    if info.warnings or subset_warnings:
        lines += ['', '## Warnings'] + [f'- {w}' for w in _uniq(info.warnings + subset_warnings)]
    lines += ['', '## Detail from reader', '', '```text', summarize_sff_detailed(sff), '```']
    _write_text(out_dir / 'SFF_BINARY_INSPECTION.md', '\n'.join(lines), res, root)
    res.notes.append('Wrote v5.5 common-table SFF2 inspection, CSVs, hashes, and capability notes.')
    res.warnings.extend(_uniq(info.warnings + subset_warnings))
    return res


def export_sff2_payloads(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Supported SFF Payload Export v5.5')
    sff = _file(root, 'sff')
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for payload export.')
        return res
    out_dir = _bc(root) / 'sff_payloads'
    out_dir.mkdir(parents=True, exist_ok=True)
    info = read_sff(sff)
    folder = out_dir / ('sff2_decoded_png' if info.variant == 'sff2-standard' else 'sff1_supported')
    exported = export_all_sprites(sff, folder)
    exports: List[Dict[str, object]] = []
    for p in exported:
        res.add_created(root, p)
        exports.append({'path': _rel(root, p), 'mode': 'decoded_sff2_or_supported_sff1'})
    if not exports:
        data = sff.read_bytes()
        folder = out_dir / 'embedded_png_scan'
        folder.mkdir(parents=True, exist_ok=True)
        for idx, (off, length) in enumerate(_find_embedded_pngs(data)[:5000]):
            out = folder / f'embedded_png_{idx:05d}_off{off:08X}.png'
            out.write_bytes(data[off:off + length])
            res.add_created(root, out)
            exports.append({'path': _rel(root, out), 'offset': off, 'length': length, 'mode': 'embedded_png_scan_no_sprite_id'})
        if exports:
            res.add_warning('Embedded PNG scan exported raw images without guaranteed group/image/axis mapping.')
    manifest = {
        'tool': 'MugenForge Binary Core', 'version': BINARY_CORE_VERSION,
        'mode': 'supported_sff_payload_export_v55',
        'source_sff': str(sff), 'source_sha256': _sha256(sff),
        'source_variant': info.variant, 'exports': exports,
        'warnings': info.warnings + res.warnings,
        'capabilities': _truth_lines(),
    }
    _write_json(out_dir / 'supported_sff_payload_export_manifest.json', manifest, res, root)
    if exports:
        res.notes.append(f'Exported {len(exports)} supported SFF payload/image artifact(s).')
    else:
        res.add_warning('No supported extractable SFF payloads found.')
    return res


def export_sff_axis_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SFF Axis Sheet Export v5.5')
    sff = _file(root, 'sff')
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for axis sheet export.')
        return res
    out_dir = _bc(root) / 'sff_axis_editor'
    out_dir.mkdir(parents=True, exist_ok=True)
    info = read_sff(sff)
    rows: List[Dict[str, object]] = []
    for spr in info.sprites:
        rows.append({
            'enabled': 'no',
            'record_type': 'sff2_standard_sprite' if info.variant == 'sff2-standard' else 'sff1_subfile',
            'index': spr.index, 'group': spr.group, 'image': spr.image,
            'current_x': spr.x, 'current_y': spr.y, 'new_x': spr.x, 'new_y': spr.y,
            'format': spr.format_hint, 'length': spr.length, 'raw_header_offset': spr.raw_header_offset,
            'note': 'Set enabled=yes and edit new_x/new_y. Apply creates a patched copy; original is not overwritten.',
        })
    fields = ['enabled','record_type','index','group','image','current_x','current_y','new_x','new_y','format','length','raw_header_offset','note']
    sheet = _write_csv(out_dir / 'sff_axis_edit_sheet.csv', rows, fields, res, root)
    _write_text(out_dir / 'README_SFF_AXIS_EDITOR.md', '\n'.join([
        '# SFF Axis Editor Sheet', '',
        'Edit `sff_axis_edit_sheet.csv` and set `enabled=yes` for rows to patch.',
        'SFF1 and common-table SFF2 axis fields are patched into a copied file under `patched/`.',
        'The original SFF is not overwritten by this workflow.', '', *_truth_lines(),
    ]), res, root)
    res.notes.append(f'Exported {len(rows)} axis rows to {sheet.name}.')
    if not rows:
        res.add_warning('No patchable SFF axis records were found.')
    return res


def apply_sff_axis_sheet(root: Path, sheet_path: Optional[Path] = None) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SFF Axis Sheet Apply v5.5')
    sff = _file(root, 'sff')
    if not sff or not sff.exists():
        res.add_warning('No SFF file found for axis patching.')
        return res
    sheet = Path(sheet_path) if sheet_path else _bc(root) / 'sff_axis_editor' / 'sff_axis_edit_sheet.csv'
    if not sheet.exists():
        res.add_warning('Axis sheet not found. Export the SFF Axis Sheet first.')
        return res
    rows = [r for r in csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')) if _truthy(r.get('enabled'))]
    if not rows:
        res.add_skipped('No rows have enabled=yes; no patched copy was created.')
        return res
    from .sff_codec import patch_sff2_axis_copy
    out_dir = _bc(root) / 'sff_axis_editor' / 'patched'
    out = out_dir / f'{sff.stem}_axis_patched_{_now()}{sff.suffix}'
    try:
        info2 = patch_sff2_axis_copy(sff, rows, out)
        res.add_created(root, out)
        _write_json(out_dir / 'axis_patch_report.json', {
            'source': str(sff), 'output': str(out), 'source_sha256': _sha256(sff),
            'output_sha256': _sha256(out), 'applied_rows': len(rows),
            'parsed_output_variant': info2.variant, 'note': 'The original SFF was not overwritten.',
        }, res, root)
        res.notes.append(f'Created patched SFF copy with {len(rows)} enabled axis row(s).')
    except Exception as exc:
        res.add_warning(f'Axis patch-copy failed: {exc}')
    return res


def write_sff2_rebuild_workspace(root: Path, image_folder: Optional[Path] = None) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SFF2 Standard Rebuild Workspace')
    work = _bc(root) / 'sff2_rebuild_workspace'
    src_dir = work / 'sprites'
    src_dir.mkdir(parents=True, exist_ok=True)
    images = _image_files(Path(image_folder)) if image_folder else _auto_image_sources(root)
    if not images:
        res.merge(export_sff2_payloads(root), 'payload export')
        images = _auto_image_sources(root)
    if not images:
        res.add_warning('No source images found for SFF2 rebuild workspace. Add PNG/PCX files to source_sprites/ and rerun.')
        return res
    records: List[Dict[str, object]] = []
    for idx, img in enumerate(images):
        g, i = _parse_group_image(img, idx)
        w, h = _image_size(img)
        dst_name = f'g{g:04d}_i{i:04d}_{idx:05d}{img.suffix.lower()}'
        dst = src_dir / dst_name
        shutil.copy2(img, dst)
        res.add_created(root, dst)
        records.append({
            'index': idx,
            'group': g,
            'image': i,
            'filename': f'sprites/{dst_name}',
            'width': w,
            'height': h,
            'axis': {'x': w // 2 if w else 0, 'y': h if h else 0},
            'compression': 'raw',
            'source': str(img),
            'note': 'compression may be raw, rle8, rle5, or lz5 for MugenForge round-trip builds',
        })
    manifest = {
        'tool': 'MugenForge Studio Binary Mastery',
        'version': BINARY_CORE_VERSION,
        'mode': 'sff2_standard_source_manifest',
        'default_compression': 'raw',
        'sprites': records,
        'note': 'This workspace can build standard-table SFF2 candidate files with raw/rle8/rle5/lz5 payloads. Test in target engine before release.',
    }
    _write_json(work / 'mugenforge_sff2_manifest.json', manifest, res, root)
    _write_json(work / 'mugenforge_sff2_png_manifest.json', manifest, res, root)
    _write_csv(work / 'sff2_axis_sheet.csv', [
        {
            'enabled': 'yes',
            'index': r['index'],
            'group': r['group'],
            'image': r['image'],
            'filename': r['filename'],
            'axis_x': r['axis']['x'],
            'axis_y': r['axis']['y'],
            'compression': r['compression'],
            'note': 'Edit this for source-axis planning; build uses manifest axis values.',
        }
        for r in records
    ], ['enabled','index','group','image','filename','axis_x','axis_y','compression','note'], res, root)
    guide = [
        '# SFF2 Standard Rebuild Workspace',
        '',
        'Edit `mugenforge_sff2_manifest.json` to control group/image, axis, and compression per sprite.',
        '',
        'Supported build compression values:',
        '- `raw` — indexed pixels with palette table.',
        '- `rle8` — pair-RLE8 stream generated by MugenForge.',
        '- `rle5` — 32-color pair-RLE5 stream generated by MugenForge.',
        '- `lz5` — literal/LZSS-style LZ5 stream generated by MugenForge.',
        '',
        'The builder creates a candidate SFF2 under `experimental/`; verify in the target engine before replacing a release file.',
        '',
        *(_truth_lines()),
    ]
    _write_text(work / 'README_SFF2_STANDARD_REBUILD.md', '\n'.join(guide), res, root)
    zip_path = work / f'{root.name}_sff2_standard_source_workspace.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for pth in sorted(work.rglob('*')):
            if pth.is_file() and pth != zip_path:
                zf.write(pth, pth.relative_to(work))
    res.add_created(root, zip_path)
    res.notes.append(f'Prepared {len(records)} sprite rows for standard SFF2 rebuild.')
    return res


def build_sff2_standard_workspace(root: Path, compression: Optional[str] = None) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Build Standard SFF2 Candidate')
    work = _bc(root) / 'sff2_rebuild_workspace'
    manifest = work / 'mugenforge_sff2_manifest.json'
    if not manifest.exists():
        res.merge(write_sff2_rebuild_workspace(root), 'workspace')
    if not manifest.exists():
        res.add_warning('SFF2 workspace manifest not found.')
        return res
    out_dir = work / 'experimental'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_standard_table.sff'
    try:
        from .sff_codec import build_sff_v2_from_manifest
        data = json.loads(manifest.read_text(encoding='utf-8'))
        default_comp = compression or str(data.get('default_compression') or 'raw')
        info = build_sff_v2_from_manifest(manifest, out, compression=default_comp)
    except Exception as exc:
        res.add_warning(f'SFF2 standard build failed: {exc}')
        return res
    res.add_created(root, out)
    rows = _sff2_records_from_info(info)
    _write_json(out_dir / 'standard_sff2_build_report.json', {
        'output': str(out),
        'output_sha256': _sha256(out),
        'variant': info.variant,
        'sprite_records': len(rows),
        'palettes': len(_sff2_palette_rows_from_info(info)),
        'warnings': info.warnings,
        'honest_capability_boundary': _truth_lines(),
    }, res, root)
    if rows:
        _write_csv(out_dir / 'standard_sff2_build_records.csv', rows, ['index','group','image','width','height','axis_x','axis_y','format_code','format_name','color_depth','data_length','palette_index','flags','table_offset','payload_offset','note'], res, root)
    res.notes.append(f'Built standard-table SFF2 candidate with {len(rows)} parsed sprite record(s).')
    res.warnings.extend(info.warnings)
    return res


def build_sff2_png_workspace_copy(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Standard SFF2 Build Candidate')
    work = _bc(root) / 'sff2_rebuild_workspace'
    manifest = work / 'mugenforge_sff2_png_manifest.json'
    if not manifest.exists():
        res.merge(write_sff2_rebuild_workspace(root), 'workspace')
    if not manifest.exists():
        res.add_warning('SFF2 workspace manifest not found; cannot build candidate.')
        return res
    out_dir = work / 'builds'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_standard_sff2_png32_candidate.sff'
    try:
        from .sff_codec import build_sff_v2_from_manifest
        info = build_sff_v2_from_manifest(manifest, out, compression='png32')
        res.add_created(root, out)
        _write_json(out_dir / 'standard_sff2_build_report.json', {
            'output': str(out), 'output_sha256': _sha256(out),
            'parsed_variant': info.variant, 'sprite_count': len(info.sprites),
            'warnings': info.warnings, 'capabilities': _truth_lines(),
        }, res, root)
        res.notes.append(f'Built standard-table SFF2 PNG32 candidate with {len(info.sprites)} sprite record(s).')
        res.warnings.extend(info.warnings)
    except Exception as exc:
        res.add_warning(f'SFF2 build candidate failed: {exc}')
    return res


# ---------------------------------------------------------------------------
# SND bank workspace, rebuild, waveform preview


def export_snd_bank_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Bank Sheet Export')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for bank sheet export.')
        return res
    out_dir = _bc(root) / 'snd_editor'
    wav_dir = out_dir / 'wavs'
    wav_dir.mkdir(parents=True, exist_ok=True)
    info = read_snd(snd)
    rows: List[Dict[str, object]] = []
    for order, sound in enumerate(info.sounds):
        try:
            wav_path = export_sound(snd, sound, wav_dir)
            res.add_created(root, wav_path)
            wav_name = f'wavs/{wav_path.name}'
        except Exception as exc:
            res.add_warning(f'Could not export sound #{sound.index}: {exc}')
            wav_name = ''
        rows.append({
            'enabled': 'yes',
            'action': 'keep',
            'order': order,
            'original_index': sound.index,
            'group': sound.group if sound.group is not None else 0,
            'sound': sound.sound if sound.sound is not None else sound.index,
            'new_group': sound.group if sound.group is not None else 0,
            'new_sound': sound.sound if sound.sound is not None else sound.index,
            'wav_filename': wav_name,
            'bytes': sound.length,
            'sample_rate': sound.sample_rate or '',
            'channels': sound.channels or '',
            'bits_per_sample': sound.bits_per_sample or '',
            'note': 'Use action=delete to omit, action=keep/replace/add to include. Rebuild creates a candidate SND first.',
        })
    fields = ['enabled','action','order','original_index','group','sound','new_group','new_sound','wav_filename','bytes','sample_rate','channels','bits_per_sample','note']
    _write_csv(out_dir / 'snd_bank_edit_sheet.csv', rows, fields, res, root)
    _write_json(out_dir / 'snd_bank_manifest.json', {
        'tool': 'MugenForge Binary Core',
        'mode': 'snd_bank_editor_workspace',
        'source_snd': str(snd),
        'source_sha256': _sha256(snd),
        'sounds': rows,
        'warnings': info.warnings,
    }, res, root)
    _write_text(out_dir / 'README_SND_EDITOR.md', '\n'.join([
        '# SND Bank Editor Sheet',
        '',
        'Edit `snd_bank_edit_sheet.csv`.',
        '',
        '- `enabled=yes` includes a row in the rebuilt candidate unless `action=delete`.',
        '- `new_group` and `new_sound` control the rebuilt sound ID.',
        '- `wav_filename` points to a WAV under this workspace. You may replace it with another WAV path.',
        '- Apply creates `binary_core/snd_editor/rebuilt/<name>_rebuilt.snd` first.',
        '- Optional install writes a backup before replacing the original SND.',
        '',
        *(_truth_lines()),
    ]), res, root)
    res.notes.append(f'Exported {len(rows)} SND sound rows.')
    res.warnings.extend(info.warnings)
    return res


def _sheet_rows_sorted(sheet: Path) -> List[Dict[str, str]]:
    rows = list(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')))
    def key(row: Dict[str, str]) -> Tuple[int, int]:
        return (_safe_int(row.get('order'), 999999), _safe_int(row.get('original_index'), 999999))
    return sorted(rows, key=key)


def apply_snd_bank_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False, replace_original: bool = False) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Bank Sheet Apply')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No original SND found. A rebuilt candidate can still be created only if the sheet references valid WAV files.')
    out_dir = _bc(root) / 'snd_editor'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'snd_bank_edit_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_bank_sheet(root), 'export')
    if not sheet.exists():
        res.add_warning('SND bank edit sheet not found.')
        return res
    source_dir = out_dir / 'rebuild_source'
    source_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, object]] = []
    skipped = 0
    for idx, row in enumerate(_sheet_rows_sorted(sheet)):
        action = str(row.get('action') or 'keep').strip().lower()
        if not _truthy(row.get('enabled')) or action in {'delete', 'remove', 'omit', 'skip'}:
            skipped += 1
            continue
        wav_name = str(row.get('wav_filename') or '').strip()
        if not wav_name:
            res.add_warning(f'Row {idx} has no wav_filename; skipped.')
            continue
        src = Path(wav_name)
        if not src.is_absolute():
            src = (sheet.parent / src).resolve()
        if not src.exists():
            res.add_warning(f'WAV file not found for row {idx}: {src}')
            continue
        dst_name = f'{idx:05d}_g{_safe_int(row.get("new_group"), _safe_int(row.get("group"), 0)):04d}_s{_safe_int(row.get("new_sound"), _safe_int(row.get("sound"), idx)):04d}_{src.name}'
        dst = source_dir / dst_name
        shutil.copy2(src, dst)
        records.append({
            'group': _safe_int(row.get('new_group'), _safe_int(row.get('group'), 0)),
            'sound': _safe_int(row.get('new_sound'), _safe_int(row.get('sound'), idx)),
            'filename': dst.name,
            'source': str(src),
            'action': action,
        })
    if not records:
        res.add_warning('No enabled WAV rows were available for rebuild.')
        return res
    manifest = {
        'tool': 'MugenForge Binary Core',
        'manifest_type': 'snd_wav_manifest',
        'version': 1,
        'sounds': records,
    }
    manifest_path = source_dir / 'mugenforge_snd_rebuild_manifest.json'
    _write_json(manifest_path, manifest, res, root)
    rebuilt_dir = out_dir / 'rebuilt'
    rebuilt_dir.mkdir(parents=True, exist_ok=True)
    out = rebuilt_dir / f'{root.name}_rebuilt.snd'
    try:
        rebuilt_info = build_snd_from_manifest(manifest_path, out)
        res.add_created(root, out)
        _write_json(rebuilt_dir / 'snd_rebuild_report.json', {
            'source_sheet': str(sheet),
            'output': str(out),
            'output_sha256': _sha256(out),
            'included_rows': len(records),
            'skipped_rows': skipped,
            'rebuilt_sound_count': len(rebuilt_info.sounds),
            'warnings': rebuilt_info.warnings,
            'original_snd': str(snd) if snd else None,
            'original_sha256': _sha256(snd) if snd and snd.exists() else None,
        }, res, root)
        res.notes.append(f'Built rebuilt SND candidate with {len(records)} sounds.')
    except Exception as exc:
        res.add_warning(f'SND rebuild failed: {exc}')
        return res
    if install or replace_original:
        if not snd:
            res.add_warning('No original SND path found for installation.')
        else:
            bak = _backup(snd)
            shutil.copy2(out, snd)
            res.add_changed(root, snd)
            if bak:
                res.notes.append(f'Original SND backup written: {_rel(root, bak)}')
    return res


def write_snd_waveform_preview(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Waveform Preview')
    out_dir = _bc(root) / 'snd_editor'
    sheet = out_dir / 'snd_bank_edit_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_bank_sheet(root), 'export')
    if not sheet.exists():
        res.add_warning('No SND sheet available for waveform preview.')
        return res
    rows = [r for r in _sheet_rows_sorted(sheet) if r.get('wav_filename')]
    if not rows:
        res.add_warning('No WAV rows available for waveform preview.')
        return res
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:
        res.add_warning(f'Pillow is required for waveform preview: {exc}')
        return res
    width = 1100
    row_h = 80
    label_w = 220
    height = max(row_h, row_h * min(len(rows), 80))
    img = Image.new('RGB', (width, height), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 11)
    except Exception:
        font = None
    for row_idx, row in enumerate(rows[:80]):
        top = row_idx * row_h
        mid = top + row_h // 2
        draw.rectangle([0, top, width - 1, top + row_h - 1], outline=(210, 210, 210))
        label = f"{row.get('new_group') or row.get('group')},{row.get('new_sound') or row.get('sound')}  {Path(str(row.get('wav_filename'))).name}"
        draw.text((8, top + 8), label[:36], fill=(0, 0, 0), font=font)
        src = Path(str(row.get('wav_filename')))
        if not src.is_absolute():
            src = (sheet.parent / src).resolve()
        samples: List[int] = []
        try:
            with wave.open(str(src), 'rb') as w:
                channels = w.getnchannels()
                width_bytes = w.getsampwidth()
                frames = w.readframes(w.getnframes())
                if width_bytes == 1:
                    vals = [b - 128 for b in frames[::max(1, channels)]]
                elif width_bytes == 2:
                    vals = [struct.unpack_from('<h', frames, i)[0] for i in range(0, len(frames) - 1, 2 * max(1, channels))]
                else:
                    vals = []
                samples = vals
        except Exception as exc:
            draw.text((label_w, top + 8), f'Could not read WAV: {exc}', fill=(130, 0, 0), font=font)
            continue
        plot_x0 = label_w
        plot_w = width - label_w - 20
        draw.line([plot_x0, mid, plot_x0 + plot_w, mid], fill=(170, 170, 170))
        if samples:
            bucket = max(1, len(samples) // plot_w)
            amp = max(1, max(abs(v) for v in samples))
            for x in range(plot_w):
                seg = samples[x * bucket:(x + 1) * bucket]
                if not seg:
                    continue
                lo = min(seg)
                hi = max(seg)
                y1 = mid - int((hi / amp) * (row_h // 2 - 8))
                y2 = mid - int((lo / amp) * (row_h // 2 - 8))
                draw.line([plot_x0 + x, y1, plot_x0 + x, y2], fill=(50, 50, 50))
    out = out_dir / 'snd_waveform_preview.png'
    img.save(out)
    res.add_created(root, out)
    _write_text(out_dir / 'SND_WAVEFORM_PREVIEW.md', 'Generated waveform preview for exported SND WAV rows. This is a visual editing aid, not an audio-normalization tool.', res, root)

    dst = _bc(root) / 'snd_bank' / 'snd_waveform_preview.png'
    if out.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, dst)
        res.add_created(root, dst)
    return res


# ---------------------------------------------------------------------------
# SND ID byte patch / Slot patch / Runtime verification / Roundtrip


def export_snd_byte_patch_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Byte Patch Sheet Export')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for byte patch sheet export.')
        return res
    out_dir = _bc(root) / 'snd_byte_patch'
    out_dir.mkdir(parents=True, exist_ok=True)
    info = read_snd(snd)
    rows: List[Dict[str, object]] = []
    for sound in info.sounds:
        if sound.header_offset is None:
            continue
        rows.append({
            'enabled': 'no',
            'index': sound.index,
            'current_group': sound.group if sound.group is not None else 0,
            'current_sound': sound.sound if sound.sound is not None else sound.index,
            'new_group': sound.group if sound.group is not None else 0,
            'new_sound': sound.sound if sound.sound is not None else sound.index,
            'riff_offset': sound.riff_offset,
            'length': sound.length,
            'header_offset': sound.header_offset,
            'note': 'Set enabled=yes and edit new_group/new_sound. Apply creates a patched SND copy first.',
        })
    fields = ['enabled','index','current_group','current_sound','new_group','new_sound','riff_offset','length','header_offset','note']
    _write_csv(out_dir / 'snd_byte_patch_sheet.csv', rows, fields, res, root)
    _write_json(out_dir / 'snd_byte_patch_manifest.json', {'source_snd': str(snd), 'source_sha256': _sha256(snd), 'rows': rows, 'warnings': info.warnings}, res, root)
    if not rows:
        res.add_warning('No recognized byte-patchable SND headers were found. Use the SND bank rebuild workflow instead.')
    else:
        res.notes.append(f'Exported {len(rows)} byte-patchable SND ID row(s).')
    return res


def apply_snd_byte_patch_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Byte Patch Sheet Apply')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for byte patching.')
        return res
    out_dir = _bc(root) / 'snd_byte_patch'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'snd_byte_patch_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_byte_patch_sheet(root), 'export')
    if not sheet.exists():
        res.add_warning('SND byte patch sheet not found.')
        return res
    rows = list(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')))
    enabled = [r for r in rows if _truthy(r.get('enabled'))]
    if not enabled:
        res.add_skipped('No rows have enabled=yes; no patched SND copy was created.')
        return res
    data = bytearray(snd.read_bytes())
    applied = 0
    errors: List[str] = []
    for row in enabled:
        off = _safe_int(row.get('header_offset'), -1)
        g = _safe_int(row.get('new_group'), _safe_int(row.get('current_group'), 0))
        s = _safe_int(row.get('new_sound'), _safe_int(row.get('current_sound'), 0))
        try:
            if off < 0 or off + 16 > len(data):
                raise ValueError(f'invalid SND header offset {off}')
            struct.pack_into('<i', data, off + 8, g)
            struct.pack_into('<i', data, off + 12, s)
            applied += 1
        except Exception as exc:
            errors.append(f"row {row.get('index')}: {exc}")
    if not applied:
        res.warnings.extend(errors or ['No rows were applied.'])
        return res
    patched = out_dir / 'patched'
    patched.mkdir(parents=True, exist_ok=True)
    out = patched / f'{snd.stem}_id_patched_{_now()}{snd.suffix}'
    out.write_bytes(bytes(data))
    res.add_created(root, out)
    parsed = read_snd(out)
    _write_json(patched / 'snd_byte_patch_report.json', {
        'source': str(snd),
        'output': str(out),
        'source_sha256': _sha256(snd),
        'output_sha256': _sha256(out),
        'applied_rows': applied,
        'parsed_sounds_after_patch': len(parsed.sounds),
        'warnings': parsed.warnings + errors,
        'note': 'Original SND was not overwritten unless install=True is used by an advanced caller.',
    }, res, root)
    if install:
        bak = _backup(snd)
        shutil.copy2(out, snd)
        res.add_changed(root, snd)
        if bak:
            res.notes.append(f'Original SND backup written: {_rel(root, bak)}')
    if errors:
        res.warnings.extend(errors)
    res.notes.append(f'Created patched SND copy with {applied} ID row(s) applied.')
    return res


def write_runtime_verification_pack(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Runtime Verification Pack')
    out_dir = _bc(root) / 'runtime_lab'
    logs = out_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    config = {
        'tool': 'MugenForge Runtime Verification Pack',
        'version': BINARY_CORE_VERSION,
        'engine_path': '',
        'character_folder': str(root),
        'recommended_log_folder': str(logs),
        'notes': [
            'Set engine_path to mugen.exe or ikemen_go executable before launching.',
            'Place captured logs/screenshots in logs/ then run Import Runtime Logs.',
            'Runtime-backed reports are only as authoritative as the supplied engine artifacts.',
        ],
    }
    _write_json(out_dir / 'mugen_runtime_config.json', config, res, root)
    bat = """@echo off
setlocal
rem Edit ENGINE below or set it in mugen_runtime_config.json
set ENGINE=
if "%ENGINE%"=="" (
  echo Set ENGINE to your mugen.exe or ikemen_go executable first.
  exit /b 1
)
mkdir logs 2>nul
"%ENGINE%" > "logs\\runtime_%DATE:/=-%_%TIME::=-%.txt" 2>&1
"""
    _write_text(out_dir / 'run_runtime_test_windows.bat', bat, res, root)
    _write_text(out_dir / 'MUGEN_RUNTIME_TEST_PLAN.md', '\n'.join([
        '# Runtime Verification Pack',
        '',
        'This pack gives Binary Mastery a path to engine-backed evidence.',
        '',
        '1. Edit `mugen_runtime_config.json` and set `engine_path`.',
        '2. Run the generated batch/script or run your engine manually.',
        '3. Save console logs, debug text captures, screenshots, or notes into `binary_core/runtime_lab/logs/`.',
        '4. Run Import Runtime Logs to build `runtime_trace_summary.csv` and `RUNTIME_VERIFICATION_REPORT.md`.',
        '',
        'Recommended debug text format if using DisplayToClipboard or log captures:',
        '`state=200 anim=200 elem=2 time=8 ctrl=0 pos=(0,0) vel=(0,0)`',
        '',
        *(_truth_lines()),
    ]), res, root)
    res.notes.append('Wrote runtime verification config, log folder, Windows launcher stub, and test plan.')
    return res


def import_runtime_logs(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Runtime Log Import')
    out_dir = _bc(root) / 'runtime_lab'
    logs = out_dir / 'logs'
    if not logs.exists():
        res.merge(write_runtime_verification_pack(root), 'runtime pack')
    rows: List[Dict[str, object]] = []
    rx = re.compile(r'state\s*=\s*(-?\d+).*?anim\s*=\s*(-?\d+)(?:.*?elem\s*=\s*(-?\d+))?(?:.*?time\s*=\s*(-?\d+))?(?:.*?ctrl\s*=\s*(-?\d+))?', re.I)
    for path in sorted(logs.glob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.txt', '.log', '.md', '.csv'}:
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            m = rx.search(line)
            if not m:
                continue
            rows.append({
                'file': _rel(root, path),
                'line': line_no,
                'state': m.group(1) or '',
                'anim': m.group(2) or '',
                'elem': m.group(3) or '',
                'time': m.group(4) or '',
                'ctrl': m.group(5) or '',
                'raw': line[:500],
            })
    _write_csv(out_dir / 'runtime_trace_summary.csv', rows, ['file','line','state','anim','elem','time','ctrl','raw'], res, root)
    state_counts: Dict[str, int] = {}
    for row in rows:
        state_counts[str(row.get('state', ''))] = state_counts.get(str(row.get('state', '')), 0) + 1
    _write_json(out_dir / 'runtime_trace_summary.json', {'rows': rows, 'state_counts': state_counts, 'engine_backed': bool(rows)}, res, root)
    lines = ['# Runtime Verification Report', '', f'Imported trace rows: {len(rows)}', '', '## Engine-backed status', '']
    if rows:
        lines.append('Runtime evidence was found. Reports can reference these imported trace rows for engine-backed checks.')
        lines += ['', '## State sample counts'] + [f'- State {state}: {count}' for state, count in sorted(state_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:100]]
    else:
        lines.append('No parseable runtime trace rows were found yet. Add logs to `binary_core/runtime_lab/logs/` and rerun this importer.')
    lines += ['', '## Honest capability boundary'] + _truth_lines()[1:]
    _write_text(out_dir / 'RUNTIME_VERIFICATION_REPORT.md', '\n'.join(lines), res, root)
    res.notes.append(f'Imported {len(rows)} runtime trace row(s).')
    return res


def export_snd_slot_patch_sheet(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Slot Patch Sheet Export')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for slot patch sheet export.')
        return res
    res.merge(export_snd_bank_sheet(root), 'bank sheet')
    sheet = _bc(root) / 'snd_editor' / 'snd_bank_edit_sheet.csv'
    if sheet.exists():
        rows = list(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')))
        for row in rows:
            row['action'] = 'replace_slot'
            row['enabled'] = 'no'
            row['note'] = 'Set enabled=yes and action=replace_slot. New WAV must be same size or smaller than the original slot for copied in-place patching.'
        fields = list(rows[0].keys()) if rows else ['enabled','action','order','original_index','group','sound','new_group','new_sound','wav_filename','bytes','note']
        patch_sheet = _write_csv(_bc(root) / 'snd_editor' / 'snd_slot_patch_sheet.csv', rows, fields, res, root)
        res.notes.append(f'Created guarded slot patch sheet: {patch_sheet.name}')
    return res


def apply_snd_slot_patch_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('SND Slot Patch Apply')
    snd = _file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found for slot patching.')
        return res
    info = read_snd(snd)
    by_index = {s.index: s for s in info.sounds}
    sheet = Path(sheet_path) if sheet_path else _bc(root) / 'snd_editor' / 'snd_slot_patch_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_slot_patch_sheet(root), 'export')
    if not sheet.exists():
        res.add_warning('SND slot patch sheet not found.')
        return res
    data = bytearray(snd.read_bytes())
    changed = 0
    errors: List[str] = []
    for row in csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline='')):
        if not _truthy(row.get('enabled')):
            continue
        if str(row.get('action') or '').strip().lower() not in {'replace_slot','slot_patch','patch'}:
            continue
        idx = _safe_int(row.get('original_index'), -1)
        sound = by_index.get(idx)
        if not sound:
            errors.append(f'No original sound index {idx}')
            continue
        wav_name = str(row.get('wav_filename') or '').strip()
        src = Path(wav_name)
        if not src.is_absolute():
            src = (sheet.parent / src).resolve()
        if not src.exists():
            errors.append(f'WAV file not found for row {idx}: {src}')
            continue
        blob = src.read_bytes()
        if not blob.startswith(b'RIFF') or b'WAVE' not in blob[:16]:
            errors.append(f'Row {idx} is not a RIFF/WAVE file: {src}')
            continue
        if len(blob) > int(sound.length):
            errors.append(f'Row {idx} WAV is larger than original slot ({len(blob)} > {sound.length}); use rebuild candidate instead.')
            continue
        start = int(sound.riff_offset)
        end = start + int(sound.length)
        if start < 0 or end > len(data):
            errors.append(f'Row {idx} original slot range is invalid.')
            continue
        data[start:end] = blob + b'\x00' * (int(sound.length) - len(blob))
        if sound.header_offset is not None and 0 <= sound.header_offset + 8 <= len(data):
            try:
                struct.pack_into('<I', data, int(sound.header_offset) + 4, len(blob))
            except Exception:
                pass
        changed += 1
    if changed:
        out_dir = _bc(root) / 'snd_editor' / 'patched'
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f'{snd.stem}_slot_patched_{_now()}{snd.suffix}'
        out.write_bytes(bytes(data))
        res.add_created(root, out)
        parsed = read_snd(out)
        _write_json(out_dir / 'snd_slot_patch_report.json', {
            'source': str(snd), 'output': str(out), 'source_sha256': _sha256(snd),
            'output_sha256': _sha256(out), 'patched_slots': changed,
            'parsed_sound_count': len(parsed.sounds), 'warnings': parsed.warnings + errors,
            'note': 'Original SND was not overwritten unless install=True was passed programmatically.',
        }, res, root)
        if install:
            bak = _backup(snd)
            shutil.copy2(out, snd)
            res.add_changed(root, snd)
            if bak:
                res.notes.append(f'Original SND backup written: {_rel(root, bak)}')
        res.notes.append(f'Created SND slot-patched copy with {changed} replaced slot(s).')
    else:
        res.add_skipped('No SND slots were patched.')
    res.warnings.extend(errors)
    return res


def write_runtime_validation_lab(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Runtime Validation Lab')
    out_dir = _bc(root) / 'runtime_lab'
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = out_dir / 'runtime_validation_config.json'
    if not cfg.exists():
        _write_json(cfg, {
            'engine_executable': '',
            'working_directory': '',
            'arguments': [],
            'timeout_seconds': 30,
            'notes': 'Set engine_executable and arguments manually. This lab captures stdout/stderr/exit code from a configured external M.U.G.E.N/IKEMEN run.',
        }, res, root)
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding='utf-8'))
        except Exception:
            data = {}
        engine = str(data.get('engine_executable') or '').strip()
        command = [engine] + [str(x) for x in data.get('arguments', [])] if engine else []
    else:
        command = []
    bat = out_dir / 'run_runtime_validation.bat'
    _write_text(bat, '\n'.join([
        '@echo off', 'REM MugenForge Runtime Validation Lab',
        'REM Edit runtime_validation_config.json with your engine path and arguments.',
        'python -m mugenforge.runtime_runner runtime_validation_config.json',
    ]), res, root)
    _write_text(out_dir / 'README_RUNTIME_VALIDATION.md', '\n'.join([
        '# Runtime Validation Lab', '',
        'This folder is for external engine evidence. Static source reports are useful, but not engine-authoritative.',
        'Fill in `runtime_validation_config.json`, run the BAT/helper from this folder, then keep generated logs with your release evidence.',
        '', 'Configured command preview:', f'`{command}`', '', *_truth_lines(),
    ]), res, root)
    res.notes.append('Created runtime validation scaffolding for external engine log/evidence capture.')
    return res


# ---------------------------------------------------------------------------
# Safety, Dashboard, Roundtrip, Bundles


def write_binary_safety_report(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Safety Report')
    out_dir = _bc(root) / 'safety'
    out_dir.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, object]] = []
    for ext in ('sff', 'snd'):
        p = _file(root, ext)
        if p and p.exists():
            files.append({'kind': ext.upper(), 'path': _rel(root, p), 'size': p.stat().st_size, 'sha256': _sha256(p)})
        else:
            files.append({'kind': ext.upper(), 'path': '', 'size': 0, 'sha256': '', 'warning': f'No {ext.upper()} file found'})
    _write_json(out_dir / 'binary_safety_hashes.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'files': files, 'limitations': _truth_lines()}, res, root)
    lines = ['# Binary Safety Report', '', TRUTH_NOTE, '', '## Current binary hashes', '']
    for f in files:
        if f.get('path'):
            lines.append(f"- {f['kind']}: `{f['path']}` — {int(f['size']):,} bytes — SHA-256 `{f['sha256']}`")
        else:
            lines.append(f"- {f['kind']}: not found")
    lines += ['', '## Policy'] + _truth_lines()[1:]
    _write_text(out_dir / 'BINARY_SAFETY_REPORT.md', '\n'.join(lines), res, root)
    res.notes.append('Wrote binary hashes and safety notes before mutation-oriented workflows.')
    return res


def write_binary_core_dashboard(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Mastery Dashboard')
    sff = _file(root, 'sff')
    snd = _file(root, 'snd')
    runtime_json = _bc(root) / 'runtime_lab' / 'runtime_trace_summary.json'
    sff_status = 'missing'
    sff_notes: List[str] = []
    if sff and sff.exists():
        try:
            info = read_sff(sff)
            std_rows = _sff2_records_from_info(info)
            sff_status = f'{info.variant}; parsed sprites={len(info.sprites)}; sff2_standard={len(std_rows)}; extractable={info.is_supported_for_extraction}'
            sff_notes = info.warnings
        except Exception as exc:
            sff_status = f'inspection failed: {exc}'
    snd_status = 'missing'
    snd_notes: List[str] = []
    if snd and snd.exists():
        try:
            sinfo = read_snd(snd)
            patchable = sum(1 for s in sinfo.sounds if s.header_offset is not None)
            snd_status = f'RIFF/WAVE sounds={len(sinfo.sounds)}; byte-patchable IDs={patchable}; signature={sinfo.has_signature}'
            snd_notes = sinfo.warnings
        except Exception as exc:
            snd_status = f'inspection failed: {exc}'
    runtime_status = 'not imported'
    if runtime_json.exists():
        try:
            data = json.loads(runtime_json.read_text(encoding='utf-8'))
            runtime_status = f"engine-backed rows={len(data.get('rows') or [])}"
        except Exception:
            runtime_status = 'runtime summary exists but could not be parsed'
    lines = [
        '# MugenForge Binary Mastery Dashboard',
        '',
        f'Version: {BINARY_CORE_VERSION}',
        '',
        TRUTH_NOTE,
        '',
        '## Project binary status',
        '',
        f'- SFF: {sff_status}',
        f'- SND: {snd_status}',
        f'- Runtime evidence: {runtime_status}',
        '',
        '## Recommended next actions',
        '',
        '1. Run **Safety Report** to capture hashes.',
        '2. Run **SFF/SFF2 Binary Mastery Inspection** to classify sprite tables and palettes.',
        '3. Run **Export Supported SFF Payloads** to decode SFF1/SFF2 records into source PNGs where supported.',
        '4. Use **SFF Axis Sheet** to patch axis fields into a copied SFF.',
        '5. Use **SFF2 Standard Rebuild Workspace** and **Build Standard SFF2 Candidate** for source-based candidate output.',
        '6. Use **SND Bank Sheet** for rebuilds or **SND Byte Patch Sheet** for recognized ID-header edits.',
        '7. Use **Runtime Verification Pack** and **Import Runtime Logs** when you need engine-backed evidence.',
        '',
        '## Honest capability boundary',
        *_truth_lines()[1:],
    ]
    if sff_notes or snd_notes:
        lines += ['', '## Current parser warnings'] + [f'- {w}' for w in _uniq(sff_notes + snd_notes)]
    _write_text(_bc(root) / 'BINARY_CORE_DASHBOARD.md', '\n'.join(lines), res, root)
    _write_text(_bc(root) / 'BINARY_CORE_START_HERE.md', '\n'.join(lines + ['', 'Generated by the v5.5 Binary Mastery cockpit.']), res, root)
    res.notes.append('Wrote Binary Mastery dashboard and start-here guide.')
    return res


def write_binary_roundtrip_lab(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Mastery Roundtrip Lab')
    out_dir = _bc(root) / 'roundtrip_lab'
    out_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, object] = {'generated': datetime.now().isoformat(timespec='seconds'), 'version': BINARY_CORE_VERSION, 'sff': {}, 'snd': {}, 'runtime': {}, 'capability_boundary': _truth_lines()}
    sff = _file(root, 'sff')
    if sff and sff.exists():
        info = read_sff(sff)
        sff_data: Dict[str, object] = {'source': str(sff), 'source_sha256': _sha256(sff), 'variant': info.variant, 'source_sprite_records': len(info.sprites), 'warnings': info.warnings}
        try:
            exp = export_sff2_payloads(root)
            res.merge(exp, 'sff export')
            sff_data['exported_artifacts'] = exp.created_files
            work_res = write_sff2_rebuild_workspace(root)
            res.merge(work_res, 'sff2 workspace')
            build_res = build_sff2_standard_workspace(root)
            res.merge(build_res, 'sff2 build')
            built = _bc(root) / 'sff2_rebuild_workspace' / 'experimental' / f'{root.name}_standard_table.sff'
            if built.exists():
                binfo = read_sff(built)
                sff_data.update({'rebuilt': str(built), 'rebuilt_sha256': _sha256(built), 'rebuilt_variant': binfo.variant, 'rebuilt_sprite_records': len(binfo.sprites), 'pass': len(binfo.sprites) > 0})
        except Exception as exc:
            sff_data.update({'pass': False, 'error': str(exc)})
        report['sff'] = sff_data
    else:
        report['sff'] = {'warning': 'No SFF file found.'}
    snd = _file(root, 'snd')
    if snd and snd.exists():
        sinfo = read_snd(snd)
        report['snd'] = {'source': str(snd), 'source_sha256': _sha256(snd), 'source_sounds': len(sinfo.sounds), 'warnings': sinfo.warnings}
        exp = export_snd_bank_sheet(root)
        res.merge(exp, 'snd sheet')
        rb = apply_snd_bank_sheet(root, install=False)
        res.merge(rb, 'snd rebuild')
        patch = export_snd_byte_patch_sheet(root)
        res.merge(patch, 'snd byte patch sheet')
        rebuilt = _bc(root) / 'snd_editor' / 'rebuilt' / f'{root.name}_rebuilt.snd'
        if rebuilt.exists():
            rinfo = read_snd(rebuilt)
            report['snd'] = {**report['snd'], 'rebuilt': str(rebuilt), 'rebuilt_sha256': _sha256(rebuilt), 'rebuilt_sounds': len(rinfo.sounds), 'pass': len(rinfo.sounds) == len(sinfo.sounds)}
    else:
        report['snd'] = {'warning': 'No SND file found.'}
    runtime = import_runtime_logs(root)
    res.merge(runtime, 'runtime logs')
    runtime_json = _bc(root) / 'runtime_lab' / 'runtime_trace_summary.json'
    if runtime_json.exists():
        try:
            report['runtime'] = json.loads(runtime_json.read_text(encoding='utf-8'))
        except Exception:
            report['runtime'] = {'warning': 'Runtime summary could not be parsed.'}
    _write_json(out_dir / 'binary_roundtrip_report.json', report, res, root)
    lines = ['# Binary Mastery Roundtrip Lab', '', TRUTH_NOTE, '', '## Results', '', '```json', json.dumps(report, indent=2), '```']
    _write_text(out_dir / 'BINARY_ROUNDTRIP_REPORT.md', '\n'.join(lines), res, root)
    return res


def build_binary_core_bundle(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Binary Core Bundle')
    base = _bc(root)
    if not base.exists():
        res.add_warning('binary_core folder does not exist yet. Run a Binary Core report first.')
        return res
    out_dir = base / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_binary_core_bundle_{_now()}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(base.rglob('*')):
            if p.is_file() and p != out:
                zf.write(p, p.relative_to(base))
    res.add_created(root, out)
    res.notes.append('Bundled Binary Core reports and safe workspaces.')
    return res


def run_binary_core_pass(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('One-Click Binary Core v5.5 Pass')
    for label, fn in [
        ('dashboard', write_binary_core_dashboard),
        ('safety', write_binary_safety_report),
        ('sff inspection', write_sff2_inspection),
        ('sff decoded payload export', export_sff2_payloads),
        ('sff axis sheet', export_sff_axis_sheet),
        ('sff2 source workspace', write_sff2_rebuild_workspace),
        ('standard sff2 candidate build', build_sff2_png_workspace_copy),
        ('snd bank sheet', export_snd_bank_sheet),
        ('snd slot patch sheet', export_snd_slot_patch_sheet),
        ('snd waveform preview', write_snd_waveform_preview),
        ('runtime validation lab', write_runtime_validation_lab),
        ('roundtrip lab', write_binary_roundtrip_lab),
    ]:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f'{label} failed: {exc}')
    try:
        res.merge(build_binary_core_bundle(root), 'bundle')
    except Exception as exc:
        res.add_warning(f'bundle failed: {exc}')
    return res


# Backward/compatibility public names for tests and UI variants.
write_binary_safety_audit = write_binary_safety_report
inspect_sff_binary = write_sff2_inspection
export_sff_supported_payloads = export_sff2_payloads
write_sff2_source_rebuild_pack = write_sff2_rebuild_workspace
create_sff2_source_rebuild_pack = write_sff2_rebuild_workspace
export_snd_bank_workspace = export_snd_bank_sheet
write_snd_waveform_board = write_snd_waveform_preview
run_binary_roundtrip_tests = write_binary_roundtrip_lab
write_sff_binary_audit = write_sff2_inspection
write_sff_axis_sheet = export_sff_axis_sheet
inspect_snd_bank = export_snd_bank_sheet
inspect_sff2_native = write_sff2_inspection
export_supported_sff2_payloads = export_sff2_payloads
write_runtime_lab = write_runtime_validation_lab
build_binary_roundtrip_report = write_binary_roundtrip_lab
