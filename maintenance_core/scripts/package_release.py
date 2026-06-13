from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import zipfile

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
OUT = ROOT.parent / f'{ROOT.name}.zip'
SKIP_PARTS = {'__pycache__', '.git', '.pytest_cache', '.mypy_cache'}
SKIP_SUFFIXES = {'.pyc', '.pyo'}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def main() -> int:
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ROOT.rglob('*'), key=lambda x: str(x).lower()):
            if p.is_file() and not should_skip(p):
                zf.write(p, p.relative_to(ROOT.parent))
    print(f'Wrote {OUT}')
    print(f'Bytes {OUT.stat().st_size}')
    print(f'Generated {datetime.now().isoformat(timespec="seconds")}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
