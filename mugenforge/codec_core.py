from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import shutil
import zipfile
from typing import Optional

from .binary_core import BinaryCoreResult, run_binary_core_pass, write_runtime_validation_lab, apply_sff_axis_sheet
from . import binary_deep as bd

CODEC_CORE_VERSION = '5.5.0'


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _cc(root: Path) -> Path:
    out = Path(root) / 'codec_core'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_text(path: Path, text: str, res: Optional[BinaryCoreResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')
    if res is not None:
        res.created_files.append(_rel(root or path.parent, path))
    return path


def _write_json(path: Path, payload: object, res: Optional[BinaryCoreResult] = None, root: Optional[Path] = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if res is not None:
        res.created_files.append(_rel(root or path.parent, path))
    return path


def write_codec_core_dashboard(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Codec Core Dashboard')
    out = _cc(root)
    _write_text(out / 'CODEC_CORE_START_HERE.md', '\n'.join([
        '# Codec Core v5.5', '',
        'Codec Core is the v5.5 consolidation layer for binary-gap work:', '',
        '- SFF2 decoded export through Binary Deep.',
        '- SFF2 mutation sheets and copied patch candidates.',
        '- Native SFF2 candidate builds from source manifests.',
        '- SND mutation sheets and guarded patch/rebuild candidates.',
        '- Runtime evidence scaffolding and log ingestion.', '',
        'Unknown or corrupt binary variants are reported instead of silently patched.',
    ]), res, root)
    return res


def write_sff2_full_decode_export(root: Path) -> BinaryCoreResult:
    return bd.export_deep_sff2_sprites(Path(root))


def export_sff2_mutation_sheet(root: Path) -> BinaryCoreResult:
    return bd.export_deep_sff2_mutation_sheet(Path(root))


def apply_sff2_mutation_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    return bd.apply_deep_sff2_mutation_sheet(Path(root), sheet_path=sheet_path, install=install)


def apply_sff2_axis_patch_copy(root: Path, sheet_path: Optional[Path] = None) -> BinaryCoreResult:
    return apply_sff_axis_sheet(Path(root), sheet_path=sheet_path)


def export_snd_mutation_sheet(root: Path) -> BinaryCoreResult:
    return bd.export_snd_direct_patch_sheet(Path(root))


def apply_snd_mutation_sheet(root: Path, sheet_path: Optional[Path] = None, install: bool = False) -> BinaryCoreResult:
    return bd.apply_snd_direct_patch_sheet(Path(root), sheet_path=sheet_path, install=install)


def ingest_runtime_evidence(root: Path, evidence_folder: Optional[Path] = None) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Runtime Evidence Ingest')
    src = Path(evidence_folder) if evidence_folder else root / 'binary_core' / 'runtime_lab' / 'runtime_logs'
    out = _cc(root) / 'runtime_evidence'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    if src.exists():
        for p in sorted(src.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file():
                dst = out / p.name
                if p.resolve() != dst.resolve():
                    shutil.copy2(p, dst)
                rows.append({'file': dst.name, 'bytes': dst.stat().st_size, 'source': str(p)})
                res.created_files.append(_rel(root, dst))
    else:
        res.add_warning(f'Runtime evidence folder not found: {src}')
    _write_json(out / 'runtime_evidence_index.json', {'generated': datetime.now().isoformat(timespec='seconds'), 'source': str(src), 'files': rows}, res, root)
    if rows:
        res.notes.append(f'Ingested {len(rows)} runtime evidence file(s).')
    return res


def build_codec_core_bundle(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('Codec Core Bundle')
    base = _cc(root)
    out_dir = base / 'bundles'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{root.name}_codec_core_bundle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for folder in [base, root / 'binary_deep', root / 'binary_core']:
            if folder.exists():
                for p in sorted(folder.rglob('*')):
                    if p.is_file() and p != out:
                        zf.write(p, p.relative_to(root))
    res.created_files.append(_rel(root, out))
    return res


def run_codec_core_pass(root: Path) -> BinaryCoreResult:
    root = Path(root)
    res = BinaryCoreResult('One-Click Codec Core Pass')
    for label, fn in [
        ('dashboard', write_codec_core_dashboard),
        ('binary core', run_binary_core_pass),
        ('binary deep', bd.run_binary_deep_pass),
        ('runtime lab', write_runtime_validation_lab),
        ('runtime evidence ingest', ingest_runtime_evidence),
    ]:
        try:
            res.merge(fn(root), label)
        except Exception as exc:
            res.add_warning(f'{label} failed: {exc}')
    try:
        res.merge(build_codec_core_bundle(root), 'bundle')
    except Exception as exc:
        res.add_warning(f'bundle failed: {exc}')
    return res
