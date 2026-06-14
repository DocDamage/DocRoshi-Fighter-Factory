from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace('\\', '/')
    except Exception:
        return str(path).replace('\\', '/')


def _flex_path(*args: object) -> str:
    if len(args) >= 2:
        return _rel(Path(args[0]), Path(str(args[1])))
    if args:
        return str(args[0])
    return ''


def _uniq(items: list[object]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        value = str(item)
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


@dataclass
class BinaryCoreResult:
    title: str = 'Binary Core Result'
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_created(self, *args: object) -> None:
        self.created_files.append(_flex_path(*args))

    def add_changed(self, *args: object) -> None:
        self.changed_files.append(_flex_path(*args))

    def add_skipped(self, msg: object) -> None:
        self.skipped_files.append(str(msg))

    def add_warning(self, msg: object) -> None:
        self.warnings.append(str(msg))

    def add_note(self, msg: object) -> None:
        self.notes.append(str(msg))

    def merge(self, other: object, label: Optional[str] = None) -> 'BinaryCoreResult':
        if not other:
            return self
        prefix = f'{label}: ' if label else ''
        for attr in ('created_files', 'changed_files', 'skipped_files', 'warnings', 'notes'):
            vals = getattr(other, attr, []) or []
            getattr(self, attr).extend(prefix + str(v) for v in vals)
        return self

    def to_text(self) -> str:
        lines = [
            self.title,
            '=' * max(12, len(self.title)),
            f'Generated: {datetime.now().isoformat(timespec="seconds")}',
            '',
        ]
        for label, values in [
            ('Notes', _uniq(self.notes)),
            ('Created files/artifacts', _uniq(self.created_files)),
            ('Changed files', _uniq(self.changed_files)),
            ('Skipped', _uniq(self.skipped_files)),
            ('Warnings', _uniq(self.warnings)),
        ]:
            if values:
                lines.append(label + ':')
                lines.extend(f'- {value}' for value in values)
                lines.append('')
        if len(lines) <= 4:
            lines.append('No changes made.')
        return '\n'.join(lines).rstrip() + '\n'
