from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .move_wizard import find_character_file
from .sff_codec import (
    SFF_SIGNATURE,
    SFF2_IMAGE_FORMATS,
    Sff2ImageRecord,
    Sff2StandardInfo,
    build_sff2_standard_from_records,
    build_sff2_standard_from_manifest,
    decode_sff2_image,
    export_all_sprites,
    export_sff2_decoded_images,
    parse_sff2_standard,
    read_sff,
    summarize_sff2_standard,
)
from .snd_codec import read_snd, export_sound

BINARY_MATURITY_VERSION = '5.5.0'
IMAGE_SUFFIXES = {'.png', '.pcx', '.bmp', '.gif', '.jpg', '.jpeg', '.webp'}
WAV_SUFFIXES = {'.wav'}

MATURITY_NOTE = (
    'Binary Maturity adds a standard SFF2 table parser, production decoders for raw8/raw24/raw32/RLE8/PNG8/PNG24/PNG32, '
    'controlled SFF2 rebuilds, payload-preserving mutation for unsupported compression rows, in-place-copy SND WAV patching, '
    'and a runtime test harness. RLE5/LZ5 controlled decode paths are available, with raw-payload preservation fallback for unusual variants.'
)

@dataclass
class BinaryMaturityResult:
    title: str = 'Binary Maturity Result'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, root_or_path: Path | str, path: Optional[Path | str] = None) -> None:
        self.created_files.append(_rel(Path(root_or_path), path) if path is not None else str(root_or_path))

    def add_changed(self, root_or_path: Path | str, path: Optional[Path | str] = None) -> None:
        self.changed_files.append(_rel(Path(root_or_path), path) if path is not None else str(root_or_path))

    def add_warning(self, msg: object) -> None:
        self.warnings.append(str(msg))

    def add_note(self, msg: object) -> None:
        self.notes.append(str(msg))

    def add_skipped(self, msg: object) -> None:
        self.skipped_files.append(str(msg))

    def merge(self, other: object, label: Optional[str] = None) -> 'BinaryMaturityResult':
        if not other:
            return self
        prefix = f'{label}: ' if label else ''
        for attr in ('created_files', 'changed_files', 'skipped_files', 'warnings', 'notes'):
            vals = getattr(other, attr, []) or []
            getattr(self, attr).extend(prefix + str(v) for v in vals)
        return self

    def to_text(self) -> str:
        lines = [self.title, '=' * max(12, len(self.title)), f'Generated: {datetime.now().isoformat(timespec="seconds")}', '']
        for label, values in [
            ('Notes', _uniq(self.notes)),
            ('Created files/artifacts', _uniq(self.created_files)),
            ('Changed files', _uniq(self.changed_files)),
            ('Skipped', _uniq(self.skipped_files)),
            ('Warnings', _uniq(self.warnings)),
        ]:
            if values:
                lines.append(label + ':')
                lines.extend(f'- {v}' for v in values)
                lines.append('')
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'


def _uniq(items: Iterable[object]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _rel(root: Path, path: Path | str | None) -> str:
    if path is None:
        return str(root)
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _now() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _bm(root: Path) -> Path:
    out = Path(root) / 'binary_maturity'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, result: Optional[BinaryMaturityResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')
    if result is not None:
        result.created_files.append(_rel(root or path.parent, path))
    return path


def _write_json(path: Path, data: object, result: Optional[BinaryMaturityResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if result is not None:
        result.created_files.append(_rel(root or path.parent, path))
    return path


def _write_csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str], result: Optional[BinaryMaturityResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in fields})
    if result is not None:
        result.created_files.append(_rel(root or path.parent, path))
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _find_file(root: Path, ext: str) -> Optional[Path]:
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
    skip = {'__pycache__', 'binary_core', 'binary_maturity', 'forge_timeline', 'forge_polish', '.mugenforge'}
    for p in sorted(root.rglob(f'*.{ext}'), key=lambda x: str(x).lower()):
        if p.is_file() and not any(part in skip for part in p.parts):
            return p
    return None


def _truth_lines() -> List[str]:
    return [
        MATURITY_NOTE,
        'Production SFF2 image decode is implemented for raw8/raw24/raw32, RLE8, PNG8, PNG24, PNG32, and zlib-wrapped PNG payloads.',
        'RLE5 and LZ5 are detected, indexed, exported as raw payloads, and preserved during rebuild when not replaced; they are not falsely decoded to pixels.',
        'SFF2 mutation writes a rebuilt candidate or patched copy; original files are not overwritten unless a separate install step is added by the user.',
        'SND in-place patching is copy-based and only patches replacement WAVs that fit inside the original payload slot; larger changes use rebuilt candidate SND files.',
        'Runtime telemetry becomes engine-backed only after a configured M.U.G.E.N/IKEMEN executable is actually run and logs/screenshots are captured.',
    ]


def _is_standard_sff2(path: Path) -> bool:
    try:
        data = Path(path).read_bytes()[:16]
        return len(data) >= 16 and data[:12] == SFF_SIGNATURE and data[12:16] in {b'\x00\x00\x00\x02', b'\x00\x01\x00\x02'}
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SFF2 maturity reports and decoded workspace


def write_sff2_maturity_report(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SFF2 Maturity Report')
    sff = _find_file(root, 'sff')
    out_dir = _bm(root) / 'sff2_maturity'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not sff or not sff.exists():
        res.add_warning('No SFF file found.')
        return res
    info = read_sff(sff)
    payload: Dict[str, object] = {
        'tool': 'MugenForge Binary Maturity',
        'version': BINARY_MATURITY_VERSION,
        'source_sff': str(sff),
        'source_sha256': _sha256(sff),
        'read_sff_variant': info.variant,
        'read_sff_version': info.version,
        'truth': _truth_lines(),
    }
    rows: List[Dict[str, object]] = []
    if _is_standard_sff2(sff):
        s2 = parse_sff2_standard(sff)
        payload['standard_sff2'] = s2.to_dict()
        for rec in s2.sprites:
            rows.append(rec.to_dict())
        _write_csv(out_dir / 'sff2_standard_sprite_table.csv', rows, ['index','group','image','width','height','axis_x','axis_y','link_index','image_format','format_name','color_depth','data_offset','data_length','palette_index','flags','table_offset','decodable','warnings'], res, root)
        pal_rows = [p.to_dict() for p in s2.palettes]
        _write_csv(out_dir / 'sff2_standard_palette_table.csv', pal_rows, ['index','group','item','color_count','link_index','data_offset','data_length','table_offset','data_base'], res, root)
        lines = ['# SFF2 Maturity Report', '', f'Source: `{_rel(root, sff)}`', f'SHA-256: `{payload["source_sha256"]}`', '', '```text', summarize_sff2_standard(sff), '```', '', '## Capability', *_truth_lines()]
    else:
        payload['legacy_or_nonstandard'] = {
            'variant': info.variant,
            'sprites': [s.__dict__ for s in info.sprites[:5000]],
            'warnings': info.warnings,
        }
        lines = ['# SFF2 Maturity Report', '', f'Source: `{_rel(root, sff)}`', f'Parser variant: `{info.variant}`', '', 'This file is not a standard SFF2 table layout recognized by the v5.5 parser. Existing v1 and rescue workflows remain available.', '', '## Capability', *_truth_lines()]
    _write_json(out_dir / 'sff2_maturity_report.json', payload, res, root)
    _write_text(out_dir / 'SFF2_MATURITY_REPORT.md', '\n'.join(lines), res, root)
    res.notes.append('Wrote SFF/SFF2 maturity report and table CSVs where available.')
    return res


def export_sff2_edit_workspace(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SFF2 Decoded Edit Workspace')
    sff = _find_file(root, 'sff')
    if not sff or not sff.exists():
        res.add_warning('No SFF file found.')
        return res
    out_dir = _bm(root) / 'sff2_edit_workspace'
    image_dir = out_dir / 'decoded_images'
    payload_dir = out_dir / 'preserved_payloads'
    image_dir.mkdir(parents=True, exist_ok=True)
    payload_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    data = sff.read_bytes()
    if _is_standard_sff2(sff):
        s2 = parse_sff2_standard(sff)
        for rec in s2.sprites:
            image_file = ''
            payload_file = ''
            note = ''
            if rec.decodable:
                out = image_dir / f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}.png'
                try:
                    decode_sff2_image(sff, rec, info=s2).save(out)
                    image_file = _rel(out_dir, out)
                    res.add_created(root, out)
                    note = 'Decoded PNG. Replace image_file or edit axis/strategy, then apply sheet.'
                except Exception as exc:
                    note = f'Decode failed; payload preserved: {exc}'
            if not image_file and rec.data_length:
                payload = payload_dir / f'g{rec.group:04d}_i{rec.image:04d}_idx{rec.index:05d}_{rec.format_name}.bin'
                payload.write_bytes(data[rec.data_offset:rec.data_offset + rec.data_length])
                payload_file = _rel(out_dir, payload)
                res.add_created(root, payload)
                if not note:
                    note = 'Unsupported compression payload preserved. Leave as keep, or provide replacement image_file.'
            rows.append({
                'enabled': 'yes',
                'action': 'keep',
                'source_index': rec.index,
                'group': rec.group,
                'image': rec.image,
                'axis_x': rec.x,
                'axis_y': rec.y,
                'image_file': image_file,
                'payload_file': payload_file,
                'strategy': 'png',
                'source_format': rec.image_format,
                'source_format_name': rec.format_name,
                'source_depth': rec.color_depth,
                'source_width': rec.width,
                'source_height': rec.height,
                'palette_index': rec.palette_index,
                'note': note,
            })
    else:
        # v1/legacy fallback: export whatever read_sff can decode and create a rebuild sheet.
        exported = export_all_sprites(sff, image_dir)
        for idx, img in enumerate(exported):
            rows.append({
                'enabled': 'yes', 'action': 'keep', 'source_index': idx,
                'group': 0, 'image': idx, 'axis_x': 0, 'axis_y': 0,
                'image_file': _rel(out_dir, img), 'payload_file': '', 'strategy': 'png',
                'source_format': '', 'source_format_name': 'legacy_export', 'source_depth': '',
                'source_width': '', 'source_height': '', 'palette_index': 0,
                'note': 'Legacy export row. Edit group/image/axis before rebuilding if needed.',
            })
        if not rows:
            res.add_warning('No exportable sprites were found for this SFF.')
    fields = ['enabled','action','source_index','group','image','axis_x','axis_y','image_file','payload_file','strategy','source_format','source_format_name','source_depth','source_width','source_height','palette_index','note']
    sheet = _write_csv(out_dir / 'sff2_sprite_edit_sheet.csv', rows, fields, res, root)
    _write_text(out_dir / 'README_SFF2_EDIT_WORKSPACE.md', '\n'.join([
        '# SFF2 Edit Workspace', '',
        'Edit `sff2_sprite_edit_sheet.csv`.', '',
        '- `enabled=yes` includes the row in the rebuilt candidate.',
        '- `action=delete` omits a row.',
        '- `image_file` may point to a replacement PNG/PCX/BMP/GIF/JPG/WebP.',
        '- `strategy` may be `png`, `raw8`, `rle8`, `raw24`, or `raw32`.',
        '- RLE5/LZ5 rows decode on controlled/common paths; unusual variants can still be preserved by payload if not replaced.',
        '- Applying creates a new SFF2 candidate under `binary_maturity/sff2_rebuilt/`.', '',
        *_truth_lines(),
    ]), res, root)
    res.notes.append(f'Wrote SFF2 edit workspace with {len(rows)} row(s): {_rel(root, sheet)}')
    return res


def _truthy(value: object) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def apply_sff2_edit_workspace(root: Path, sheet_path: Optional[Path] = None) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SFF2 Edit Workspace Apply')
    out_dir = _bm(root) / 'sff2_edit_workspace'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'sff2_sprite_edit_sheet.csv'
    if not sheet.exists():
        res.merge(export_sff2_edit_workspace(root), 'export')
    if not sheet.exists():
        res.add_warning('SFF2 edit sheet not found.')
        return res
    records: List[Dict[str, object]] = []
    skipped = 0
    for idx, row in enumerate(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline=''))):
        action = str(row.get('action') or 'keep').strip().lower()
        if not _truthy(row.get('enabled')) or action in {'delete', 'remove', 'omit', 'skip'}:
            skipped += 1
            continue
        image_file = str(row.get('image_file') or '').strip()
        payload_file = str(row.get('payload_file') or '').strip()
        rec: Dict[str, object] = {
            'group': _safe_int(row.get('group'), 0),
            'image': _safe_int(row.get('image'), idx),
            'axis_x': _safe_int(row.get('axis_x'), 0),
            'axis_y': _safe_int(row.get('axis_y'), 0),
            'palette_index': _safe_int(row.get('palette_index'), 0),
            'strategy': str(row.get('strategy') or 'png').strip().lower() or 'png',
        }
        if image_file:
            p = Path(image_file)
            if not p.is_absolute():
                p = (sheet.parent / p).resolve()
            if not p.exists():
                res.add_warning(f'Row {idx} replacement image not found: {p}')
                continue
            rec['image_file'] = str(p)
        elif payload_file:
            p = Path(payload_file)
            if not p.is_absolute():
                p = (sheet.parent / p).resolve()
            if not p.exists():
                res.add_warning(f'Row {idx} preserved payload not found: {p}')
                continue
            rec['payload'] = p.read_bytes()
            rec['image_format'] = _safe_int(row.get('source_format'), 1)
            rec['color_depth'] = _safe_int(row.get('source_depth'), 0)
            rec['width'] = _safe_int(row.get('source_width'), 0)
            rec['height'] = _safe_int(row.get('source_height'), 0)
        else:
            res.add_warning(f'Row {idx} has no image_file or payload_file; skipped.')
            continue
        records.append(rec)
    if not records:
        res.add_warning('No enabled rows available to rebuild SFF2.')
        return res
    out_build = _bm(root) / 'sff2_rebuilt'
    out_build.mkdir(parents=True, exist_ok=True)
    out = out_build / f'{root.name}_rebuilt_v55.sff'
    try:
        rebuilt = build_sff2_standard_from_records(records, out, default_strategy='png')
        res.add_created(root, out)
        _write_json(out_build / 'sff2_rebuild_report.json', {
            'source_sheet': str(sheet),
            'output': str(out),
            'output_sha256': _sha256(out),
            'included_rows': len(records),
            'skipped_rows': skipped,
            'parsed_sprite_records': len(rebuilt.sprites),
            'decodable_records': rebuilt.decodable_count,
            'unsupported_preserved_records': rebuilt.unsupported_count,
            'truth': _truth_lines(),
        }, res, root)
        _write_text(out_build / 'SFF2_REBUILD_REPORT.md', '\n'.join(['# SFF2 Rebuild Report', '', f'Output: `{_rel(root, out)}`', f'Included rows: {len(records)}', f'Skipped rows: {skipped}', '', '```text', summarize_sff2_standard(out), '```']), res, root)
        res.notes.append(f'Built standard SFF2 candidate with {len(records)} row(s).')
    except Exception as exc:
        res.add_warning(f'SFF2 rebuild failed: {exc}')
    return res


def build_sff2_from_source_folder(root: Path, source_folder: Optional[Path] = None, strategy: str = 'png') -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SFF2 Build From Source Folder')
    source = Path(source_folder) if source_folder else None
    if source is None:
        for cand in [root / 'source_sprites', root / 'sprites', root / 'staged_sprites', root / 'sprite_slices', root / 'binary_maturity' / 'sff2_edit_workspace' / 'decoded_images']:
            if cand.exists() and any(p.suffix.lower() in IMAGE_SUFFIXES for p in cand.rglob('*')):
                source = cand
                break
    if not source or not source.exists():
        res.add_warning('No source sprite folder found. Use source_sprites/, sprites/, staged_sprites/, or pass a folder.')
        return res
    images = [p for p in sorted(source.rglob('*'), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    if not images:
        res.add_warning(f'No supported image files in {source}.')
        return res
    import re
    records = []
    for idx, img in enumerate(images):
        nums = re.findall(r'-?\d+', img.stem)
        group = int(nums[-2]) if len(nums) >= 2 else 0
        image = int(nums[-1]) if len(nums) >= 2 else idx
        records.append({'group': group, 'image': image, 'axis_x': 0, 'axis_y': 0, 'image_file': str(img), 'strategy': strategy})
    out_dir = _bm(root) / 'sff2_source_build'
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / 'sff2_source_manifest.json'
    _write_json(manifest, {'tool': 'MugenForge Binary Maturity', 'sprites': records, 'strategy': strategy}, res, root)
    out = out_dir / f'{root.name}_source_v55.sff'
    try:
        built = build_sff2_standard_from_records(records, out, default_strategy=strategy)
        res.add_created(root, out)
        _write_text(out_dir / 'SFF2_SOURCE_BUILD_REPORT.md', '\n'.join(['# SFF2 Source Build Report', '', f'Source folder: `{source}`', f'Images: {len(images)}', f'Output: `{_rel(root, out)}`', '', '```text', summarize_sff2_standard(out), '```']), res, root)
        res.notes.append(f'Built SFF2 from {len(images)} source image(s) using strategy={strategy}.')
    except Exception as exc:
        res.add_warning(f'SFF2 source build failed: {exc}')
    return res


# ---------------------------------------------------------------------------
# SND slot patching: copy-based in-place replacement when a WAV fits.


def export_snd_slot_patch_sheet(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SND Slot Patch Sheet Export')
    snd = _find_file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found.')
        return res
    info = read_snd(snd)
    out_dir = _bm(root) / 'snd_slot_patch'
    wav_dir = out_dir / 'current_wavs'
    wav_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    for sound in info.sounds:
        try:
            wav = export_sound(snd, sound, wav_dir)
            wav_rel = _rel(out_dir, wav)
            res.add_created(root, wav)
        except Exception as exc:
            wav_rel = ''
            res.add_warning(f'Could not export sound #{sound.index}: {exc}')
        rows.append({
            'enabled': 'no',
            'index': sound.index,
            'group': sound.group if sound.group is not None else '',
            'sound': sound.sound if sound.sound is not None else '',
            'current_wav': wav_rel,
            'replace_wav': '',
            'max_bytes_for_inplace': sound.length,
            'riff_offset': sound.riff_offset,
            'header_offset': sound.header_offset if sound.header_offset is not None else '',
            'note': 'Set enabled=yes and replace_wav to a WAV. If replacement fits, Apply writes a patched copy; otherwise it is skipped here and should use SND rebuild.',
        })
    fields = ['enabled','index','group','sound','current_wav','replace_wav','max_bytes_for_inplace','riff_offset','header_offset','note']
    _write_csv(out_dir / 'snd_slot_patch_sheet.csv', rows, fields, res, root)
    _write_text(out_dir / 'README_SND_SLOT_PATCH.md', '\n'.join(['# SND Slot Patch', '', 'This workflow patches a copied SND only when the replacement WAV is less than or equal to the original payload slot length.', 'For larger WAVs, use the existing rebuilt SND workflow.', '', *_truth_lines()]), res, root)
    res.notes.append(f'Exported {len(rows)} SND slot rows.')
    res.warnings.extend(info.warnings)
    return res


def apply_snd_slot_patch_sheet(root: Path, sheet_path: Optional[Path] = None) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('SND Slot Patch Sheet Apply')
    snd = _find_file(root, 'snd')
    if not snd or not snd.exists():
        res.add_warning('No SND file found.')
        return res
    out_dir = _bm(root) / 'snd_slot_patch'
    sheet = Path(sheet_path) if sheet_path else out_dir / 'snd_slot_patch_sheet.csv'
    if not sheet.exists():
        res.merge(export_snd_slot_patch_sheet(root), 'export')
    if not sheet.exists():
        res.add_warning('SND slot patch sheet not found.')
        return res
    data = bytearray(snd.read_bytes())
    applied = 0
    skipped = 0
    errors: List[str] = []
    for idx, row in enumerate(csv.DictReader(sheet.open('r', encoding='utf-8-sig', newline=''))):
        if not _truthy(row.get('enabled')):
            skipped += 1
            continue
        repl = str(row.get('replace_wav') or '').strip()
        if not repl:
            skipped += 1
            continue
        p = Path(repl)
        if not p.is_absolute():
            p = (sheet.parent / p).resolve()
        if not p.exists():
            errors.append(f'Row {idx} replacement WAV not found: {p}')
            continue
        blob = p.read_bytes()
        if not (blob.startswith(b'RIFF') and blob[8:12] == b'WAVE'):
            errors.append(f'Row {idx} replacement is not RIFF/WAVE: {p}')
            continue
        riff_offset = _safe_int(row.get('riff_offset'), -1)
        max_len = _safe_int(row.get('max_bytes_for_inplace'), 0)
        if riff_offset < 0 or riff_offset + max_len > len(data) or max_len <= 0:
            errors.append(f'Row {idx} has invalid original slot offset/length.')
            continue
        if len(blob) > max_len:
            errors.append(f'Row {idx} replacement ({len(blob)} bytes) exceeds original slot ({max_len} bytes); use rebuilt SND workflow.')
            continue
        data[riff_offset:riff_offset + len(blob)] = blob
        if len(blob) < max_len:
            data[riff_offset + len(blob):riff_offset + max_len] = b'\x00' * (max_len - len(blob))
        header_offset = str(row.get('header_offset') or '').strip()
        if header_offset not in {'', 'None'}:
            off = _safe_int(header_offset, -1)
            if 0 <= off + 8 <= len(data):
                struct.pack_into('<I', data, off + 4, len(blob))
        applied += 1
    if applied:
        patched_dir = out_dir / 'patched'
        patched_dir.mkdir(parents=True, exist_ok=True)
        out = patched_dir / f'{snd.stem}_slot_patched_{_now()}{snd.suffix}'
        out.write_bytes(bytes(data))
        res.add_created(root, out)
        _write_json(patched_dir / 'snd_slot_patch_report.json', {
            'source': str(snd),
            'output': str(out),
            'source_sha256': _sha256(snd),
            'output_sha256': _sha256(out),
            'applied_rows': applied,
            'skipped_rows': skipped,
            'errors': errors,
            'note': 'Original SND was not overwritten.',
        }, res, root)
        res.notes.append(f'Created patched SND copy with {applied} replacement(s).')
    else:
        res.add_skipped('No SND slot replacements were applied.')
    res.warnings.extend(errors)
    return res


# ---------------------------------------------------------------------------
# Runtime harness: engine-backed test runner when configured.


def write_runtime_test_harness(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('Runtime Test Harness')
    out_dir = _bm(root) / 'runtime_lab'
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        'engine_executable': '',
        'working_directory': '',
        'character_folder': str(root),
        'character_name': root.name,
        'stage': '',
        'extra_args': [],
        'capture_stdout': True,
        'capture_stderr': True,
        'timeout_seconds': 30,
        'notes': 'Set engine_executable to mugen.exe or ikemen_go.exe. Then run the harness from the UI or command line.',
    }
    cfg_path = out_dir / 'runtime_test_config.json'
    if not cfg_path.exists():
        _write_json(cfg_path, cfg, res, root)
    script = out_dir / 'run_runtime_test.py'
    _write_text(script, """from pathlib import Path
import json, subprocess, sys, datetime
cfg = json.loads(Path('runtime_test_config.json').read_text(encoding='utf-8'))
exe = cfg.get('engine_executable') or ''
if not exe:
    raise SystemExit('Set engine_executable in runtime_test_config.json first.')
cmd = [exe] + list(cfg.get('extra_args') or [])
work = cfg.get('working_directory') or str(Path(exe).parent)
log_dir = Path('logs'); log_dir.mkdir(exist_ok=True)
tag = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=int(cfg.get('timeout_seconds') or 30))
(log_dir / f'runtime_stdout_{tag}.txt').write_text(proc.stdout or '', encoding='utf-8', errors='replace')
(log_dir / f'runtime_stderr_{tag}.txt').write_text(proc.stderr or '', encoding='utf-8', errors='replace')
(log_dir / f'runtime_exit_{tag}.json').write_text(json.dumps({'returncode': proc.returncode, 'cmd': cmd, 'cwd': work}, indent=2), encoding='utf-8')
print('returncode=', proc.returncode)
""", res, root)
    _write_text(out_dir / 'RUNTIME_TEST_HARNESS.md', '\n'.join([
        '# Runtime Test Harness', '',
        'This closes the static-report gap only when an actual M.U.G.E.N/IKEMEN executable is configured and run.', '',
        '1. Edit `runtime_test_config.json`.',
        '2. Set `engine_executable` to your local engine executable.',
        '3. Run `python run_runtime_test.py` from this folder, or use the MugenForge UI button.',
        '4. Review logs under `binary_maturity/runtime_lab/logs/`.', '',
        *_truth_lines(),
    ]), res, root)
    res.notes.append('Wrote runtime test harness config and runner script.')
    return res


def run_runtime_test_harness(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('Runtime Test Harness Run')
    out_dir = _bm(root) / 'runtime_lab'
    cfg_path = out_dir / 'runtime_test_config.json'
    if not cfg_path.exists():
        res.merge(write_runtime_test_harness(root), 'harness')
    if not cfg_path.exists():
        res.add_warning('Runtime config not found.')
        return res
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    exe = str(cfg.get('engine_executable') or '').strip()
    if not exe:
        res.add_warning('engine_executable is blank. Configure runtime_test_config.json first.')
        return res
    exe_path = Path(exe)
    if not exe_path.exists():
        res.add_warning(f'engine_executable does not exist: {exe}')
        return res
    cmd = [str(exe_path)] + [str(x) for x in (cfg.get('extra_args') or [])]
    cwd = Path(str(cfg.get('working_directory') or exe_path.parent))
    logs = out_dir / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    tag = _now()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=int(cfg.get('timeout_seconds') or 30))
        stdout = logs / f'runtime_stdout_{tag}.txt'
        stderr = logs / f'runtime_stderr_{tag}.txt'
        meta = logs / f'runtime_exit_{tag}.json'
        stdout.write_text(proc.stdout or '', encoding='utf-8', errors='replace')
        stderr.write_text(proc.stderr or '', encoding='utf-8', errors='replace')
        _write_json(meta, {'returncode': proc.returncode, 'cmd': cmd, 'cwd': str(cwd)}, res, root)
        res.add_created(root, stdout)
        res.add_created(root, stderr)
        res.notes.append(f'Runtime process exited with code {proc.returncode}.')
        if proc.returncode != 0:
            res.add_warning(f'Runtime executable returned nonzero exit code {proc.returncode}.')
    except Exception as exc:
        res.add_warning(f'Runtime test failed: {exc}')
    return res


# ---------------------------------------------------------------------------
# Bundles / one-click pass


def build_binary_maturity_bundle(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('Binary Maturity Bundle')
    base = _bm(root)
    if not base.exists():
        res.add_warning('binary_maturity folder does not exist yet.')
        return res
    out_dir = base / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_binary_maturity_bundle_{_now()}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(base.rglob('*')):
            if p.is_file() and p != out:
                zf.write(p, p.relative_to(base))
    res.add_created(root, out)
    return res


def run_binary_maturity_pass(root: Path) -> BinaryMaturityResult:
    root = Path(root)
    res = BinaryMaturityResult('One-Click Binary Maturity Pass')
    for label, fn in [
        ('sff2 maturity report', write_sff2_maturity_report),
        ('sff2 edit workspace', export_sff2_edit_workspace),
        ('snd slot patch sheet', export_snd_slot_patch_sheet),
        ('runtime harness', write_runtime_test_harness),
    ]:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f'{label} failed: {exc}')
    try:
        res.merge(build_binary_maturity_bundle(root), 'bundle')
    except Exception as exc:
        res.add_warning(f'bundle failed: {exc}')
    return res


# Compatibility names for UI drafts.
write_sff2_decode_workspace = export_sff2_edit_workspace
apply_sff2_rebuild_sheet = apply_sff2_edit_workspace
write_snd_inplace_patch_sheet = export_snd_slot_patch_sheet
apply_snd_inplace_patch_sheet = apply_snd_slot_patch_sheet
