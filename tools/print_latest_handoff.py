from __future__ import annotations

from pathlib import Path

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
CANDIDATES = sorted((ROOT / 'docs').glob('MUGENFORGE_HANDOFF_v*.md'), key=lambda p: p.name.lower())
if not CANDIDATES:
    raise SystemExit('No handoff file found.')
print(CANDIDATES[-1].read_text(encoding='utf-8', errors='replace'))
