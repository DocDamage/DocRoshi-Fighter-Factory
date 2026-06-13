from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence


def rel_path(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def record_artifact(result: object, path: Path, root: Optional[Path], *, changed: bool = False) -> None:
    values = getattr(result, 'changed_files' if changed else 'created_files')
    values.append(rel_path(root or path.parent, path))


def write_text_artifact(
    path: Path,
    text: str,
    result: Optional[object] = None,
    root: Optional[Path] = None,
    changed: bool = False,
    *,
    writer: Optional[Callable[[Path, str], object]] = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = text.rstrip() + '\n'
    if writer is None:
        path.write_text(content, encoding='utf-8')
    else:
        writer(path, content)
    if result is not None:
        record_artifact(result, path, root, changed=changed)
    return path


def write_json_artifact(path: Path, payload: object, result: Optional[object] = None, root: Optional[Path] = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if result is not None:
        record_artifact(result, path, root)
    return path


def write_csv_artifact(
    path: Path,
    rows: Sequence[Dict[str, object]],
    fields: Sequence[str],
    result: Optional[object] = None,
    root: Optional[Path] = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, '') for field in fields})
    if result is not None:
        record_artifact(result, path, root)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup_file(path: Path, tag: str) -> Optional[Path]:
    path = Path(path)
    if not path.exists():
        return None
    backup = path.with_name(f'{path.name}.bak_{tag}_{timestamp()}')
    shutil.copy2(path, backup)
    return backup
